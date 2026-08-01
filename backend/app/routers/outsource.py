"""委外订单模块 API 路由 — 销售转外发→维护加工信息→审核(应付)→完工(生成待入库单)"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import Product, Supplier
from app.models.inventory import StockInOrder
from app.models.production import OutsourceOrder
from app.models.purchase import AccountsPayable
from app.models.sales import SalesOrder, SalesOrderItem
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_doc_no

router = APIRouter()


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


@router.get("/orders", tags=["委外管理"])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str = Query("", description="状态筛选"),
    keyword: str = Query("", description="单号/产品搜索"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """委外订单列表"""
    query = db.query(OutsourceOrder)
    if status:
        query = query.filter(OutsourceOrder.status == status)
    if keyword:
        query = query.join(Product).filter(
            OutsourceOrder.outsource_no.like(f"%{keyword}%")
            | Product.code.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%")
        )
    total = query.count()
    items = query.order_by(OutsourceOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for os in items:
        prod = db.query(Product).filter(Product.id == os.product_id).first()
        sup = db.query(Supplier).filter(Supplier.id == os.outsourcer_id).first() if os.outsourcer_id else None
        # 已入库数量（来自关联待入库单）
        received = db.query(StockInOrder).filter(
            StockInOrder.outsource_order_id == os.id,
            StockInOrder.status != "已退回",
        ).all()
        received_qty = sum((r.received_qty or 0) for r in received)
        result.append({
            "id": os.id,
            "outsource_no": os.outsource_no,
            "sales_order_id": os.sales_order_id,
            "sales_item_id": os.sales_item_id,
            "product_id": os.product_id,
            "product_code": prod.code if prod else "",
            "product_name": prod.name_cn if prod else "",
            "quantity": os.quantity,
            "received_qty": received_qty,
            "outsourcer_id": os.outsourcer_id,
            "outsourcer_name": sup.name if sup else "",
            "unit_price": os.unit_price or 0,
            "amount": os.amount or 0,
            "due_date": str(os.due_date) if os.due_date else "",
            "status": os.status,
            "remark": os.remark or "",
            "created_at": str(os.created_at) if os.created_at else "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/orders/{order_id}", tags=["委外管理"])
def get_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    prod = db.query(Product).filter(Product.id == os.product_id).first()
    sup = db.query(Supplier).filter(Supplier.id == os.outsourcer_id).first() if os.outsourcer_id else None
    so = db.query(SalesOrder).filter(SalesOrder.id == os.sales_order_id).first() if os.sales_order_id else None
    return {
        "id": os.id,
        "outsource_no": os.outsource_no,
        "sales_order_no": so.order_no if so else "",
        "product_id": os.product_id,
        "product_code": prod.code if prod else "",
        "product_name": prod.name_cn if prod else "",
        "quantity": os.quantity,
        "outsourcer_id": os.outsourcer_id,
        "outsourcer_name": sup.name if sup else "",
        "unit_price": os.unit_price or 0,
        "amount": os.amount or 0,
        "due_date": str(os.due_date) if os.due_date else "",
        "status": os.status,
        "remark": os.remark or "",
        "created_at": str(os.created_at) if os.created_at else "",
    }


@router.put("/orders/{order_id}", tags=["委外管理"])
def update_order(
    order_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """维护委外订单（待确认状态：委外商/加工单价/交期/备注）"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "待确认":
        raise HTTPException(400, f"当前状态「{os.status}」不能编辑")
    if "outsourcer_id" in data:
        os.outsourcer_id = data["outsourcer_id"]
    if "unit_price" in data:
        os.unit_price = float(data["unit_price"] or 0)
        os.amount = round((os.quantity or 0) * (os.unit_price or 0), 2)
    if "due_date" in data:
        os.due_date = _parse_date(data["due_date"])
    if "remark" in data:
        os.remark = data.get("remark", "")
    db.commit()
    return {"message": "委外订单已更新"}


@router.post("/orders/{order_id}/approve", tags=["委外管理"])
def approve_order(
    order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """审核委外订单 → 生成加工费应付账款"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "待确认":
        raise HTTPException(400, f"当前状态「{os.status}」不能审核")
    if not os.outsourcer_id:
        raise HTTPException(400, "请先选择委外商（供应商）")
    if not (os.unit_price and os.unit_price > 0):
        raise HTTPException(400, "请先填写加工单价")
    os.amount = round((os.quantity or 0) * (os.unit_price or 0), 2)
    os.status = "已审核"
    # 生成应付账款（加工费）
    ap_no = generate_doc_no(db, "AP", AccountsPayable, "ap_no")
    ap = AccountsPayable(
        ap_no=ap_no,
        source_type="outsource",
        source_id=os.id,
        supplier_id=os.outsourcer_id,
        amount=os.amount,
        balance=os.amount,
        due_date=os.due_date,
        status="未付款",
    )
    db.add(ap)
    db.commit()
    return {"message": f"委外订单已审核，已生成应付账款 {ap_no}", "amount": os.amount}


@router.post("/orders/{order_id}/finish", tags=["委外管理"])
def finish_order(
    order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """确认完工 → 生成成品入库待入库单（收货走成品入库模块）"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "已审核":
        raise HTTPException(400, f"当前状态「{os.status}」不能确认完工")
    existing = db.query(StockInOrder).filter(
        StockInOrder.outsource_order_id == os.id,
        StockInOrder.status.in_(["待入库", "部分入库"]),
    ).first()
    if existing:
        raise HTTPException(400, f"已有待入库单（{existing.stock_in_no}），请先在成品入库模块收货")
    sin = StockInOrder(
        stock_in_no=generate_doc_no(db, "IN", StockInOrder, "stock_in_no"),
        source_type="outsource",
        sales_order_id=os.sales_order_id,
        sales_item_id=os.sales_item_id,
        outsource_order_id=os.id,
        product_id=os.product_id,
        quantity=os.quantity,
        status="待入库",
        created_by=current_user.display_name or current_user.username,
    )
    db.add(sin)
    os.status = "已完工"
    db.commit()
    return {"message": f"已确认完工，生成待入库单 {sin.stock_in_no}", "stock_in_no": sin.stock_in_no}


@router.delete("/orders/{order_id}", tags=["委外管理"])
def delete_order(
    order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """删除委外订单（仅待确认状态；删除后销售明细行回到未生产，可重新操作）"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "待确认":
        raise HTTPException(400, f"当前状态「{os.status}」不能删除")
    # 回写销售明细：已通知外发 → 未生产
    if os.sales_item_id:
        item = db.query(SalesOrderItem).filter(SalesOrderItem.id == os.sales_item_id).first()
        if item and item.production_status == "已通知外发":
            item.production_status = "未生产"
    db.delete(os)
    db.commit()
    return {"message": "委外订单已删除"}

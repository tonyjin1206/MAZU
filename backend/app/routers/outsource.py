"""委外订单模块 API 路由 — 销售转外发→维护加工信息→审核(应付)→完工(生成待入库单)"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import Product, Supplier, Customer
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
    # 生成待入库单（收货走成品入库模块，与销售订单转入库同逻辑）
    sin = StockInOrder(
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
    db.commit()
    return {"message": f"委外订单已审核：已生成应付账款 {ap_no}，待入库单已生成，收货请到「库存管理 → 成品入库」", "amount": os.amount}


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


# ==================== 销售订单转委外（与采购线对称） ====================

def _so_outsource_status(db: Session, order):
    """销售单委外状态: completed(绿)/partial(橙)/none(灰)
    判定口径: 该明细行关联的非退回委外单数量合计 >= 销售数量 => 委外完成
    已入库(走库存线)的行跳过，不计入委外判定"""
    row_statuses = []
    for si in order.items:
        if si.production_status in ("已停售", "已入库"):
            continue
        os_orders = db.query(OutsourceOrder).filter(
            OutsourceOrder.sales_item_id == si.id,
            OutsourceOrder.status != "已退回",
        ).all()
        if not os_orders:
            row_statuses.append("none")
        else:
            total_qty = sum((o.quantity or 0) for o in os_orders)
            if total_qty >= (si.quantity or 0):
                row_statuses.append("done")
            else:
                row_statuses.append("partial")
    if not row_statuses:
        return "none"
    if all(s == "done" for s in row_statuses):
        return "completed"
    if all(s == "none" for s in row_statuses):
        return "none"
    return "partial"


@router.get("/sales-to-outsource", tags=["委外管理"])
def list_sales_to_outsource(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
    keyword: str = Query(""), date_from: str = Query(""), date_to: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """销售订单转委外：已审核销售单列表 + 委外状态（completed绿/partial橙/none灰）
    只显示还有可转委外明细行的单（已入库行不计）"""
    query = db.query(SalesOrder).filter(SalesOrder.status.in_(["已审", "生产中", "部分发货"]))
    if keyword:
        query = query.join(Customer).filter(
            SalesOrder.order_no.like(f"%{keyword}%") | Customer.name_cn.like(f"%{keyword}%"))
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)
    total = query.count()
    items = query.order_by(SalesOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for o in items:
        # 有可转委外的行才显示（未生产/已通知外发=可追加；已入库/已停售不计）
        transferable = any(i.production_status in (None, "", "未生产", "已通知外发") for i in o.items)
        if not transferable:
            continue
        result.append({
            "id": o.id, "order_no": o.order_no,
            "order_date": str(o.order_date) if o.order_date else "",
            "customer_name": o.customer.name_cn if o.customer else "",
            "total_amount": o.total_amount or 0,
            "item_count": sum(1 for i in o.items if i.production_status not in ("已停售", "已入库")),
            "status": o.status,
            "outsource_status": _so_outsource_status(db, o),
        })
    return {"total": len(result), "page": page, "page_size": page_size, "items": result}


@router.get("/sales-to-outsource/{order_id}", tags=["委外管理"])
def get_sales_to_outsource(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售单转委外明细：产品行 + 已委外数量（委外商/加工单价在委外订单维护里填）"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status not in ("已审", "生产中", "部分发货"):
        raise HTTPException(400, f"该销售单状态「{order.status}」，不能转委外")
    rows = []
    for si in order.items:
        if si.production_status in ("已停售", "已入库"):
            continue
        os_orders = db.query(OutsourceOrder).filter(
            OutsourceOrder.sales_item_id == si.id,
            OutsourceOrder.status != "已退回",
        ).all()
        outsourced_qty = sum((o.quantity or 0) for o in os_orders)
        prod = si.product
        rows.append({
            "sales_item_id": si.id, "product_id": si.product_id,
            "code": prod.code if prod else "", "name": prod.name_cn if prod else "",
            "spec": (prod.spec or "") if prod else "", "unit": prod.unit if prod else "",
            "need_qty": si.quantity or 0, "outsourced_qty": round(outsourced_qty, 2),
            "production_status": si.production_status or "未生产",
        })
    return {
        "id": order.id, "order_no": order.order_no,
        "customer_name": order.customer.name_cn if order.customer else "",
        "outsource_status": _so_outsource_status(db, order),
        "rows": rows,
    }


@router.post("/orders/from-sales", tags=["委外管理"])
def create_outsource_from_sales(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售订单转委外：明细行批量生成委外订单（草稿，待确认）
    data: { sales_order_id: int, rows: [{sales_item_id, quantity}] }
    """
    sales_order_id = data.get("sales_order_id")
    rows = data.get("rows") or []
    if not sales_order_id or not rows:
        raise HTTPException(400, "参数不完整")
    order = db.query(SalesOrder).filter(SalesOrder.id == sales_order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status not in ("已审", "生产中", "部分发货"):
        raise HTTPException(400, f"该销售单状态「{order.status}」，不能转委外")

    created = []
    for r in rows:
        si = db.query(SalesOrderItem).filter(
            SalesOrderItem.id == r["sales_item_id"],
            SalesOrderItem.order_id == sales_order_id,
        ).first()
        if not si:
            raise HTTPException(400, "销售明细行不存在")
        # 已入库/已停售不可转；已通知外发可继续追加（分批转委外），数量校验控制总量
        if si.production_status in ("已入库", "已停售"):
            raise HTTPException(400, f"「{si.product.name_cn if si.product else ''}」当前状态为「{si.production_status}」，不能转委外（请先退回相关单据）")
        qty = float(r.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(400, "委外数量必须大于0")
        # 剩余量校验（非退回委外单累计）
        os_orders = db.query(OutsourceOrder).filter(
            OutsourceOrder.sales_item_id == si.id,
            OutsourceOrder.status != "已退回",
        ).all()
        already = sum((o.quantity or 0) for o in os_orders)
        if qty + already > (si.quantity or 0):
            raise HTTPException(400, f"{si.product.name_cn if si.product else ''} 委外数量超过销售数量（剩余 {round((si.quantity or 0) - already, 2)}）")
        os_order = OutsourceOrder(
            outsource_no=generate_doc_no(db, "WO", OutsourceOrder, "outsource_no"),
            sales_order_id=sales_order_id,
            sales_item_id=si.id,
            product_id=si.product_id,
            quantity=qty,
            status="待确认",
            created_by=current_user.display_name or current_user.username,
        )
        db.add(os_order)
        if si.production_status in (None, "", "未生产"):
            si.production_status = "已通知外发"
        created.append({"outsource_no": os_order.outsource_no, "product_name": si.product.name_cn if si.product else ""})
    db.commit()
    return {"message": f"已生成 {len(created)} 张委外订单（待确认，请在委外订单中维护委外商/加工单价后审核）", "orders": created}

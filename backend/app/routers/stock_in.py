"""成品入库模块 API 路由 — 待入库单→收货确认→完成/退回

来源：销售明细「转入库」、采购明细「转成品库入库」、委外订单「确认完工」
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import Product, Warehouse
from app.models.inventory import StockInOrder, WarehouseInventory, StockTransaction
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.purchase import PurchaseOrder, PurchaseOrderItem
from app.models.production import OutsourceOrder
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_batch_no, generate_doc_no

router = APIRouter()


def _source_label(db: Session, sin: StockInOrder) -> str:
    """来源单号描述"""
    if sin.source_type == "sales" and sin.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == sin.sales_order_id).first()
        return f"销售单 {so.order_no}" if so else f"销售单#{sin.sales_order_id}"
    if sin.source_type == "purchase" and sin.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == sin.purchase_order_id).first()
        return f"采购单 {po.order_no}" if po else f"采购单#{sin.purchase_order_id}"
    if sin.source_type == "outsource" and sin.outsource_order_id:
        os = db.query(OutsourceOrder).filter(OutsourceOrder.id == sin.outsource_order_id).first()
        return f"委外单 {os.outsource_no}" if os else f"委外单#{sin.outsource_order_id}"
    return ""


@router.get("", tags=["库存管理"])
def list_stock_in(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str = Query("", description="状态筛选"),
    source_type: str = Query("", description="来源: sales/purchase/outsource"),
    keyword: str = Query("", description="单号/产品搜索"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """待入库单列表"""
    query = db.query(StockInOrder)
    if status:
        query = query.filter(StockInOrder.status == status)
    if source_type:
        query = query.filter(StockInOrder.source_type == source_type)
    if keyword:
        query = query.join(Product).filter(
            StockInOrder.stock_in_no.like(f"%{keyword}%")
            | Product.code.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%")
        )
    total = query.count()
    items = query.order_by(StockInOrder.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for sin in items:
        prod = db.query(Product).filter(Product.id == sin.product_id).first()
        result.append({
            "id": sin.id,
            "stock_in_no": sin.stock_in_no,
            "source_type": sin.source_type,
            "source_label": _source_label(db, sin),
            "sales_order_id": sin.sales_order_id,
            "sales_item_id": sin.sales_item_id,
            "purchase_item_id": sin.purchase_item_id,
            "outsource_order_id": sin.outsource_order_id,
            "product_id": sin.product_id,
            "product_code": prod.code if prod else "",
            "product_name": prod.name_cn if prod else "",
            "quantity": sin.quantity,
            "received_qty": sin.received_qty or 0,
            "status": sin.status,
            "warehouse_id": sin.warehouse_id,
            "created_at": str(sin.created_at) if sin.created_at else "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


def _sync_downstream(db: Session, sin: StockInOrder):
    """收货后回写下游状态（未完成时）"""
    if sin.sales_item_id:
        item = db.query(SalesOrderItem).filter(SalesOrderItem.id == sin.sales_item_id).first()
        if item and item.production_status not in ("已入库", "已停售"):
            item.production_status = "部分入库"


def _after_complete(db: Session, sin: StockInOrder):
    """确认完成后回写下游"""
    if sin.sales_item_id:
        item = db.query(SalesOrderItem).filter(SalesOrderItem.id == sin.sales_item_id).first()
        if item and item.production_status != "已停售":
            item.production_status = "已入库"
    if sin.outsource_order_id:
        os = db.query(OutsourceOrder).filter(OutsourceOrder.id == sin.outsource_order_id).first()
        if os and os.status not in ("已退回",):
            os.status = "已入库"


@router.post("/{stock_in_id}/receive", tags=["库存管理"])
def receive_stock_in(
    stock_in_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """收货入库（可分批，收满自动完成，未满保持部分入库）"""
    sin = db.query(StockInOrder).filter(StockInOrder.id == stock_in_id).first()
    if not sin:
        raise HTTPException(404, "待入库单不存在")
    if sin.status not in ("待入库", "部分入库"):
        raise HTTPException(400, f"当前状态「{sin.status}」不能收货")
    qty = float(data.get("quantity") or 0)
    if qty <= 0:
        raise HTTPException(400, "入库数量必须大于 0")
    warehouse_id = data.get("warehouse_id")
    if not warehouse_id:
        raise HTTPException(400, "请选择入库仓库")

    operator = current_user.display_name or current_user.username
    batch_no = generate_batch_no(db, "FG")

    # 生成入库单号（每次收货唯一）
    from app.models.inventory import WarehouseInventory as _WI
    _today_receipt = (
        db.query(func.max(_WI.receipt_no))
        .filter(_WI.receipt_no.like(f"RE-{date.today().strftime('%Y%m%d')}-%"))
        .scalar()
    )
    _seq = 1
    if _today_receipt:
        _seq = int(_today_receipt.rsplit("-", 1)[1]) + 1
    receipt_no = f"RE-{date.today().strftime('%Y%m%d')}-{_seq:03d}"

    # 成本：优先取关联采购明细单价
    unit_cost = 0.0
    if sin.purchase_item_id:
        poi = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == sin.purchase_item_id).first()
        if poi:
            unit_cost = float(poi.unit_price_local or poi.unit_price or 0)

    inventory = WarehouseInventory(
        warehouse_id=warehouse_id,
        product_id=sin.product_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_cost=round(qty * unit_cost, 2),
        in_date=date.today(),
        source_type="stock_in",
        source_doc_id=sin.id,
        receipt_no=receipt_no,
    )
    db.add(inventory)

    trans = StockTransaction(
        trans_type="stock_in",
        warehouse_id=warehouse_id,
        product_id=sin.product_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_amount=round(qty * unit_cost, 2),
        before_qty=0,
        after_qty=qty,
        before_cost=0,
        after_cost=round(qty * unit_cost, 2),
        source_doc_type="成品入库",
        source_doc_no=sin.stock_in_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=operator,
    )
    db.add(trans)

    sin.received_qty = (sin.received_qty or 0) + qty
    sin.warehouse_id = warehouse_id

    # 收满自动完成；未满保持部分入库，人工确认完成
    if (sin.received_qty or 0) >= (sin.quantity or 0):
        sin.status = "已入库"
        _after_complete(db, sin)
    else:
        sin.status = "部分入库"
        _sync_downstream(db, sin)

    db.commit()
    return {"message": f"入库成功 {qty}，批次号 {batch_no}", "status": sin.status, "received_qty": sin.received_qty}


@router.post("/{stock_in_id}/complete", tags=["库存管理"])
def complete_stock_in(
    stock_in_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """人工确认完成入库（入库数量≠应入数量时由人工判定）"""
    sin = db.query(StockInOrder).filter(StockInOrder.id == stock_in_id).first()
    if not sin:
        raise HTTPException(404, "待入库单不存在")
    if sin.status not in ("待入库", "部分入库"):
        raise HTTPException(400, f"当前状态「{sin.status}」不能确认完成")
    sin.status = "已入库"
    _after_complete(db, sin)
    db.commit()
    return {"message": "已确认完成入库"}


@router.post("/{stock_in_id}/cancel", tags=["库存管理"])
def cancel_stock_in(
    stock_in_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退回待入库单（仅未收货时允许；下游退回后上游销售明细才可变更）"""
    sin = db.query(StockInOrder).filter(StockInOrder.id == stock_in_id).first()
    if not sin:
        raise HTTPException(404, "待入库单不存在")
    if (sin.received_qty or 0) > 0:
        raise HTTPException(400, "已有入库记录，不能退回")
    if sin.status != "待入库":
        raise HTTPException(400, f"当前状态「{sin.status}」不能退回")
    sin.status = "已退回"
    # 回写销售明细：已通知入库 → 未生产
    if sin.sales_item_id:
        item = db.query(SalesOrderItem).filter(SalesOrderItem.id == sin.sales_item_id).first()
        if item and item.production_status == "已通知入库":
            item.production_status = "未生产"
    # 回写采购明细：解除去向
    if sin.purchase_item_id:
        poi = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == sin.purchase_item_id).first()
        if poi and poi.receive_type == "成品库":
            poi.receive_type = ""
    # 回写委外单：已完工 → 已审核（可重新确认完工）
    if sin.outsource_order_id:
        os = db.query(OutsourceOrder).filter(OutsourceOrder.id == sin.outsource_order_id).first()
        if os and os.status == "已完工":
            os.status = "已审核"
    db.commit()
    return {"message": "待入库单已退回"}


@router.post("/{stock_in_id}/return", tags=["库存管理"])
def return_stock_in(
    stock_in_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """退回已入库/部分入库的收货数量（填错数量时纠正）"""
    sin = db.query(StockInOrder).filter(StockInOrder.id == stock_in_id).first()
    if not sin:
        raise HTTPException(404, "入库单不存在")
    if sin.status not in ("已入库", "部分入库"):
        raise HTTPException(400, f"当前状态「{sin.status}」不能退回")
    return_qty = body.get("return_qty", 0)
    if return_qty <= 0:
        raise HTTPException(400, "退回数量必须大于0")
    if return_qty > (sin.received_qty or 0):
        raise HTTPException(400, f"退回数量不能超过已入数量 {sin.received_qty}")
    # 减少已入数量
    sin.received_qty = (sin.received_qty or 0) - return_qty
    if sin.received_qty <= 0:
        sin.received_qty = 0
        sin.status = "待入库"
        # 回退销售明细状态：部分入库/已入库 → 已通知入库 或 未生产（取决于是否还有其他入库单）
        if sin.sales_item_id:
            item = db.query(SalesOrderItem).filter(SalesOrderItem.id == sin.sales_item_id).first()
            if item and item.production_status in ("部分入库", "已入库"):
                item.production_status = "已通知入库"
    else:
        sin.status = "部分入库"
    # 扣减库存批次
    inv = db.query(WarehouseInventory).filter(
        WarehouseInventory.source_doc_id == stock_in_id,
        WarehouseInventory.source_type == "stock_in",
        WarehouseInventory.quantity > 0
    ).first()
    if inv:
        inv.quantity -= return_qty
        inv.total_cost = inv.unit_cost * inv.quantity
    db.commit()
    return {"message": f"已退回 {return_qty}，当前已入 {sin.received_qty}"}


@router.get("/{stock_in_id}/records", tags=["库存管理"])
def get_stock_in_records(
    stock_in_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """穿透查询：该入库单的所有收货记录（批次库存）"""
    records = db.query(WarehouseInventory).filter(
        WarehouseInventory.source_doc_id == stock_in_id,
        WarehouseInventory.source_type == "stock_in"
    ).order_by(WarehouseInventory.id.desc()).all()
    items = []
    for inv in records:
        wh = db.query(Warehouse).filter(Warehouse.id == inv.warehouse_id).first()
        prod = db.query(Product).filter(Product.id == inv.product_id).first() if inv.product_id else None
        items.append({
            "id": inv.id,
            "warehouse": wh.name if wh else "",
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
            "batch_no": inv.batch_no,
            "receipt_no": inv.receipt_no or "",
            "quantity": inv.quantity,
            "in_date": str(inv.in_date),
        })
    return {"items": items}

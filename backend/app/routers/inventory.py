"""库存管理路由 — 收发存查询、库存流水、批次追溯"""

from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.auth import User
from app.models.inventory import WarehouseInventory, StockTransaction, StockInOrder
from app.models.foundation import Warehouse, Material, Product
from app.models.sales import SalesOrder, SalesOrderItem
from app.utils.auth import get_current_user

router = APIRouter()


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
def _calc_period_balance(db, warehouse_id, material_id, product_id, type, keyword, start_date_str, end_date_str, page, page_size):
    """计算期间库存余额：期初 + 期间收发 = 期末"""
    from sqlalchemy import and_, or_
    from app.models.inventory import StockTransaction as ST

    start_dt = datetime.combine(_parse_date(start_date_str) or date(2024, 1, 1), datetime.min.time())
    end_dt = datetime.combine(_parse_date(end_date_str) or date.today(), datetime.max.time().replace(microsecond=0))

    # 构建交易过滤条件
    conditions = []
    if warehouse_id:
        conditions.append(ST.warehouse_id == warehouse_id)
    if material_id:
        conditions.append(ST.material_id == material_id)
    if product_id:
        conditions.append(ST.product_id == product_id)
    if type == "material":
        conditions.append(ST.material_id.isnot(None))
    elif type == "product":
        conditions.append(ST.product_id.isnot(None))
    if keyword:
        mat_ids = [m.id for m in db.query(Material).filter(
            (Material.name.like(f"%{keyword}%")) | (Material.code.like(f"%{keyword}%"))
        ).all()]
        prod_ids = [p.id for p in db.query(Product).filter(
            (Product.name_cn.like(f"%{keyword}%")) | (Product.code.like(f"%{keyword}%"))
        ).all()]
        if mat_ids or prod_ids:
            conds = []
            if mat_ids: conds.append(ST.material_id.in_(mat_ids))
            if prod_ids: conds.append(ST.product_id.in_(prod_ids))
            conditions.append(or_(*conds))
        else:
            conditions.append(ST.id == -1)

    # 查询期间交易
    period_query = db.query(ST).filter(and_(ST.trans_date >= start_dt, ST.trans_date <= end_dt))
    if conditions:
        period_query = period_query.filter(and_(*conditions))

    # 查询期初交易（start_date 之前）
    opening_query = db.query(ST).filter(ST.trans_date < start_dt)
    if conditions:
        opening_query = opening_query.filter(and_(*conditions))

    # 查询期末交易（end_date 之前，含当天）
    closing_query = db.query(ST).filter(ST.trans_date <= end_dt)
    if conditions:
        closing_query = closing_query.filter(and_(*conditions))

    # 按物料分组计算期初/期间/期末
    results = []
    # 获取所有涉及的物料（去重）
    all_trans = closing_query.all()
    grouped = {}
    for t in all_trans:
        key = (t.warehouse_id, t.material_id, t.product_id)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(t)

    for (wh_id, mat_id, prod_id), trans_list in grouped.items():
        # 期初
        opening_qty = sum(t.quantity for t in trans_list if t.trans_date < start_dt)
        opening_cost = sum(t.total_amount for t in trans_list if t.trans_date < start_dt)

        # 期间收发
        period_in = sum(t.quantity for t in trans_list if start_dt <= t.trans_date <= end_dt and t.quantity > 0)
        period_out = sum(t.quantity for t in trans_list if start_dt <= t.trans_date <= end_dt and t.quantity < 0)
        period_in_cost = sum(t.total_amount for t in trans_list if start_dt <= t.trans_date <= end_dt and t.total_amount > 0)
        period_out_cost = sum(t.total_amount for t in trans_list if start_dt <= t.trans_date <= end_dt and t.total_amount < 0)

        # 期末
        closing_qty = sum(t.quantity for t in trans_list)
        closing_cost = sum(t.total_amount for t in trans_list)

        # 查名称
        wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
        mat = db.query(Material).filter(Material.id == mat_id).first() if mat_id else None
        prod = db.query(Product).filter(Product.id == prod_id).first() if prod_id else None

        # 批次号（取最新的一条）
        latest_batch = trans_list[-1].batch_no if trans_list else ""

        results.append({
            "warehouse": wh.name if wh else "",
            "material_name": mat.name if mat else "",
            "product_name": prod.name_cn if prod else "",
            "material_id": mat_id,
            "product_id": prod_id,
            "batch_no": latest_batch,
            "opening_qty": round(opening_qty, 2),
            "opening_cost": round(opening_cost, 2),
            "period_in_qty": round(period_in, 2),
            "period_out_qty": round(period_out, 2),
            "period_in_cost": round(period_in_cost, 2),
            "period_out_cost": round(period_out_cost, 2),
            "closing_qty": round(closing_qty, 2),
            "closing_cost": round(closing_cost, 2),
            "unit_cost": round(closing_cost / closing_qty, 2) if closing_qty else 0,
        })

    # 分页
    total = len(results)
    start_idx = (page - 1) * page_size
    paged = results[start_idx:start_idx + page_size]

    return {
        "total": total, "page": page, "page_size": page_size,
        "items": paged,
        "period": {"start_date": start_dt.isoformat(), "end_date": end_dt.isoformat()},
    }



@router.get("/balance", tags=["库存管理"])
def get_inventory_balance(
    warehouse_id: int | None = None,
    material_id: int | None = None,
    product_id: int | None = None,
    type: str | None = Query(None, description="类型: material/product"),
    keyword: str | None = Query(None, description="物料名称/编码搜索"),
    start_date: str | None = Query(None, description="开始日期: YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期: YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """库存余额查询（支持期初/期末，含数量+金额）
    
    无日期参数 → 显示当前库存快照
    有日期参数 → 显示期初 + 期间收发 + 期末
    """
    # ========== 有日期参数：按期间计算期初+收发+期末 ==========
    if start_date or end_date:
        return _calc_period_balance(
            db, warehouse_id, material_id, product_id, type, keyword,
            start_date, end_date, page, page_size
        )

    # ========== 无日期参数：当前库存快照 ==========
    query = db.query(WarehouseInventory).filter(WarehouseInventory.quantity > 0)
    if warehouse_id:
        query = query.filter(WarehouseInventory.warehouse_id == warehouse_id)
    if type == "material":
        query = query.filter(WarehouseInventory.material_id.isnot(None))
    elif type == "product":
        query = query.filter(WarehouseInventory.product_id.isnot(None))
    if material_id:
        query = query.filter(WarehouseInventory.material_id == material_id)
    if product_id:
        query = query.filter(WarehouseInventory.product_id == product_id)
    if keyword:
        mat_ids = [m.id for m in db.query(Material).filter(
            (Material.name.like(f"%{keyword}%")) | (Material.code.like(f"%{keyword}%"))
        ).all()]
        prod_ids = [p.id for p in db.query(Product).filter(
            (Product.name_cn.like(f"%{keyword}%")) | (Product.code.like(f"%{keyword}%"))
        ).all()]
        if mat_ids or prod_ids:
            from sqlalchemy import or_
            conditions = []
            if mat_ids:
                conditions.append(WarehouseInventory.material_id.in_(mat_ids))
            if prod_ids:
                conditions.append(WarehouseInventory.product_id.in_(prod_ids))
            query = query.filter(or_(*conditions))
        else:
            query = query.filter(WarehouseInventory.id == -1)

    total = query.count()
    # 按批次号汇总（同一批次多次收货合并为一行）
    all_items = query.order_by(WarehouseInventory.id.desc()).all()
    grouped = {}
    for inv in all_items:
        key = (inv.warehouse_id, inv.material_id, inv.product_id, inv.batch_no)
        if key not in grouped:
            grouped[key] = {"rows": [], "qty": 0.0, "cost": 0.0}
        grouped[key]["rows"].append(inv)
        grouped[key]["qty"] += inv.quantity or 0
        grouped[key]["cost"] += inv.total_cost or 0

    result = []
    for (wh_id, mat_id, prod_id, batch_no), g in grouped.items():
        inv = g["rows"][0]  # 取第一条作为代表
        wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
        mat = db.query(Material).filter(Material.id == mat_id).first() if mat_id else None
        prod = db.query(Product).filter(Product.id == prod_id).first() if prod_id else None

        # 关联销售订单（成品入库 → 销售明细 → 销售订单）
        so_order_no, so_order_qty, so_received_qty = "", 0, 0
        unit_cost = inv.unit_cost or 0
        if inv.source_doc_id:
            stock_in = db.query(StockInOrder).filter(StockInOrder.id == inv.source_doc_id).first()
            if stock_in and stock_in.sales_item_id:
                so_item = db.query(SalesOrderItem).filter(SalesOrderItem.id == stock_in.sales_item_id).first()
                if so_item:
                    so_order = db.query(SalesOrder).filter(SalesOrder.id == stock_in.sales_order_id).first()
                    so_order_no = so_order.order_no if so_order else ""
                    so_order_qty = so_item.quantity or 0
                    # 成本优先取库存真实成本（采购价/认领批次进价），无采购成本的旧数据才兜底销售单价
                    if not unit_cost:
                        unit_cost = so_item.unit_price or 0
                    # 该明细行累计已入库数量
                    so_received_qty = (
                        db.query(func.sum(StockInOrder.received_qty))
                        .filter(StockInOrder.sales_item_id == stock_in.sales_item_id, StockInOrder.status.in_(["已入库", "部分入库"]))
                        .scalar() or 0
                    )

        result.append({
            "id": inv.id,
            "warehouse": wh.name if wh else "",
            "material_id": mat_id,
            "material_name": mat.name if mat else "",
            "material_code": mat.code if mat else "",
            "material_spec": mat.spec if mat else "",
            "material_model": mat.model if mat else "",
            "product_id": prod_id,
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
            "product_spec": prod.spec if prod else "",
            "product_model": prod.model if prod else "",
            "batch_no": batch_no,
            "quantity": round(g["qty"], 2),
            "unit_cost": round(unit_cost, 2),
            "total_cost": round(unit_cost * g["qty"], 2),
            "in_date": str(inv.in_date),
            "source_type": "成品入库",
            "so_order_no": so_order_no,
            "so_order_qty": so_order_qty,
            "so_received_qty": so_received_qty,
            "receipt_count": len(g["rows"]),
        })

    # 分页
    total = len(result)
    start_idx = (page - 1) * page_size
    paged = result[start_idx:start_idx + page_size]

    return {"total": total, "page": page, "page_size": page_size, "items": paged}


@router.get("/batch-receipts", tags=["库存管理"])
def get_batch_receipts(
    batch_no: str = Query(..., description="批次号"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """穿透查询：某批次的所有入库记录（每次收货一条：入库单号/日期/仓库/数量）"""
    records = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no
    ).order_by(WarehouseInventory.id.desc()).all()
    items = []
    for inv in records:
        wh = db.query(Warehouse).filter(Warehouse.id == inv.warehouse_id).first()
        prod = db.query(Product).filter(Product.id == inv.product_id).first() if inv.product_id else None
        mat = db.query(Material).filter(Material.id == inv.material_id).first() if inv.material_id else None
        items.append({
            "receipt_no": inv.receipt_no or "",
            "warehouse": wh.name if wh else "",
            "product_name": prod.name_cn if prod else (mat.name if mat else ""),
            "product_code": prod.code if prod else (mat.code if mat else ""),
            "quantity": inv.quantity,
            "in_date": str(inv.in_date),
        })
    return {"batch_no": batch_no, "items": items}


@router.get("/summary", tags=["库存管理"])
def get_inventory_summary(
    group_by: str = Query("material", description="group by: material/warehouse/batch"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """库存汇总（按材料/仓库/批次汇总数量和金额）"""
    query = db.query(
        WarehouseInventory.warehouse_id,
        WarehouseInventory.material_id,
        WarehouseInventory.product_id,
        func.sum(WarehouseInventory.quantity).label("total_qty"),
        func.sum(WarehouseInventory.total_cost).label("total_amount"),
        func.count(WarehouseInventory.id).label("batch_count"),
    ).filter(WarehouseInventory.quantity > 0)

    if group_by == "warehouse":
        results = query.group_by(WarehouseInventory.warehouse_id).all()
    elif group_by == "batch":
        results = query.group_by(WarehouseInventory.warehouse_id, WarehouseInventory.batch_no).all()
    else:
        results = query.group_by(WarehouseInventory.warehouse_id, WarehouseInventory.material_id, WarehouseInventory.product_id).all()

    items = []
    for r in results:
        wh = db.query(Warehouse).filter(Warehouse.id == r[0]).first()
        mat = db.query(Material).filter(Material.id == r[1]).first() if r[1] else None
        prod = db.query(Product).filter(Product.id == r[2]).first() if r[2] else None
        items.append({
            "warehouse": wh.name if wh else "",
            "material_name": mat.name if mat else "",
            "material_code": mat.code if mat else "",
            "material_spec": mat.spec if mat else "",
            "material_model": mat.model if mat else "",
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
            "product_spec": prod.spec if prod else "",
            "product_model": prod.model if prod else "",
            "total_qty": round(r[3] or 0, 2),
            "total_amount": round(r[4] or 0, 2),
            "batch_count": r[5],
        })

    return {"items": items}


@router.get("/transactions", tags=["库存管理"])
def get_transactions(
    warehouse_id: int | None = None,
    material_id: int | None = None,
    product_id: int | None = None,
    trans_type: str | None = None,
    type: str | None = Query(None, description="类型: material/product"),
    direction: str | None = Query(None, description="方向: in/out"),
    keyword: str | None = Query(None, description="物料名称/编码搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """库存流水查询"""
    query = db.query(StockTransaction)
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)
    if material_id:
        query = query.filter(StockTransaction.material_id == material_id)
    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)
    if trans_type:
        query = query.filter(StockTransaction.trans_type == trans_type)
    if type == "material":
        query = query.filter(StockTransaction.material_id.isnot(None))
    elif type == "product":
        query = query.filter(StockTransaction.product_id.isnot(None))
    if direction == "in":
        query = query.filter(StockTransaction.quantity > 0)
    elif direction == "out":
        query = query.filter(StockTransaction.quantity < 0)
    if keyword:
        # 按流水号搜索
        txn_ids = [t.id for t in db.query(StockTransaction).filter(
            StockTransaction.trans_no.like(f"%{keyword}%")
        ).all()]
        mat_ids = [m.id for m in db.query(Material).filter(
            (Material.name.like(f"%{keyword}%")) | (Material.code.like(f"%{keyword}%"))
        ).all()]
        prod_ids = [p.id for p in db.query(Product).filter(
            (Product.name_cn.like(f"%{keyword}%")) | (Product.code.like(f"%{keyword}%"))
        ).all()]
        conditions = []
        if mat_ids: conditions.append(StockTransaction.material_id.in_(mat_ids))
        if prod_ids: conditions.append(StockTransaction.product_id.in_(prod_ids))
        if txn_ids: conditions.append(StockTransaction.id.in_(txn_ids))
        if conditions:
            from sqlalchemy import or_
            query = query.filter(or_(*conditions))
        else:
            query = query.filter(StockTransaction.id == -1)

    total = query.count()
    # 按时间正序：最老在前，最新在后
    items = query.order_by(StockTransaction.trans_date.asc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result = []
    for t in items:
        wh = db.query(Warehouse).filter(Warehouse.id == t.warehouse_id).first()
        mat = db.query(Material).filter(Material.id == t.material_id).first() if t.material_id else None
        prod = db.query(Product).filter(Product.id == t.product_id).first() if t.product_id else None
        result.append({
            "id": t.id,
            "trans_type": t.trans_type,
            "warehouse": wh.name if wh else "",
            "material_name": mat.name if mat else "",
            "product_name": prod.name_cn if prod else "",
            "batch_no": t.batch_no,
            "quantity": t.quantity,
            "unit_cost": round(t.unit_cost, 2),
            "total_amount": round(t.total_amount, 2),
            "before_qty": round(t.before_qty, 2),
            "after_qty": round(t.after_qty, 2),
            "source_doc_type": t.source_doc_type or "",
            "source_doc_no": t.source_doc_no or "",
            "trans_no": t.trans_no or "",
            "operator": t.operator or "",
            "trans_date": str(t.trans_date)[:19] if t.trans_date else "",
        })

    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/available-batches", tags=["库存管理"])
def get_available_batches(
    product_id: int = Query(..., description="产品ID"),
    warehouse_id: int | None = Query(None, description="仓库ID"),
    order_id: int | None = Query(None, description="当前发货订单ID，用于计算批次锁定"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询可用批次（按产品+仓库），返回每个批次的锁定/可发数量：
    - 批次归属订单未确认发货完成时，(订单量-已发) 锁定给该订单；当前订单自己的批次不锁定
    - 归属订单确认完成后锁定解除
    - 无归属（备货 FG- 批次）不锁定"""
    query = db.query(WarehouseInventory).filter(
        WarehouseInventory.product_id == product_id,
    )
    if warehouse_id:
        query = query.filter(WarehouseInventory.warehouse_id == warehouse_id)
    items = query.all()

    # 按批次号汇总（同一批次多条记录合并）
    batch_map = {}
    for inv in items:
        key = inv.batch_no
        if key not in batch_map:
            batch_map[key] = {"id": inv.id, "batch_no": key, "quantity": 0.0,
                              "unit_cost": round(inv.unit_cost or 0, 2),
                              "warehouse_id": inv.warehouse_id,
                              "warehouse_name": inv.warehouse.name if inv.warehouse else ""}
        batch_map[key]["quantity"] = round(batch_map[key]["quantity"] + (inv.quantity or 0), 2)

    result = []
    for key, b in batch_map.items():
        owner = db.query(SalesOrderItem).filter(SalesOrderItem.batch_no == key).first()
        locked = 0
        owner_order_no = ""
        if owner:
            owner_order_no = owner.order.order_no if owner.order else ""
            if owner.order_id != order_id and not owner.delivery_confirmed:
                locked = max(0, round((owner.quantity or 0) - (owner.delivered_qty or 0), 2))
        b["locked_qty"] = locked
        b["available"] = max(0, round(b["quantity"] - locked, 2))
        b["owner_order_no"] = owner_order_no
        result.append(b)
    return {"items": result}


@router.get("/trace/{batch_no}", tags=["库存管理"])
def trace_batch(
    batch_no: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批次追溯"""
    items = db.query(StockTransaction).filter(
        StockTransaction.batch_no == batch_no
    ).order_by(StockTransaction.trans_date).all()

    result = []
    for t in items:
        wh = db.query(Warehouse).filter(Warehouse.id == t.warehouse_id).first()
        result.append({
            "id": t.id,
            "trans_type": t.trans_type,
            "warehouse": wh.name if wh else "",
            "quantity": t.quantity,
            "unit_cost": round(t.unit_cost, 2),
            "total_amount": round(t.total_amount, 2),
            "before_qty": round(t.before_qty, 2),
            "after_qty": round(t.after_qty, 2),
            "source_doc_type": t.source_doc_type or "",
            "source_doc_no": t.source_doc_no or "",
            "trans_date": str(t.trans_date)[:19] if t.trans_date else "",
        })

    return {"batch_no": batch_no, "trace": result}

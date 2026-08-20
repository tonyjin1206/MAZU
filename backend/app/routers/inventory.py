"""库存管理路由 — 收发存查询、库存流水、批次追溯"""

from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.auth import User
from app.models.inventory import WarehouseInventory, StockTransaction, StockInOrder, Stocktake, StocktakeItem
from app.models.foundation import Warehouse, Material, Product
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

        # 批次号（取最新的一条 — 显式按时间排序，避免查询顺序不确定性）
        sorted_trans = sorted(trans_list, key=lambda t: (t.trans_date or datetime.min, t.id or 0))
        latest_batch = sorted_trans[-1].batch_no if sorted_trans else ""

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


@router.get("/material-receipts", tags=["库存管理"])
def get_material_receipts(
    material_id: int | None = Query(None, description="原料ID（与 product_id 二选一）"),
    product_id: int | None = Query(None, description="产品ID（与 material_id 二选一）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """入库明细：某原料/产品所有批次的所有入库记录（每次收货一条，按入库日期倒序）

    粒度与 batch-receipts 一致：inv_inventory 每行=一次入库（receipt_no 每次入库唯一，
    同一批次多次收货分行），故按物料直接查行即可还原"每次入库"。
    """
    if not material_id and not product_id:
        raise HTTPException(400, "请提供 material_id 或 product_id")
    query = db.query(WarehouseInventory).filter(WarehouseInventory.quantity > 0)
    if material_id:
        query = query.filter(WarehouseInventory.material_id == material_id)
    if product_id:
        query = query.filter(WarehouseInventory.product_id == product_id)
    records = query.order_by(WarehouseInventory.in_date.desc(), WarehouseInventory.id.desc()).all()

    items = []
    for inv in records:
        wh = db.query(Warehouse).filter(Warehouse.id == inv.warehouse_id).first()
        mat = db.query(Material).filter(Material.id == inv.material_id).first() if inv.material_id else None
        prod = db.query(Product).filter(Product.id == inv.product_id).first() if inv.product_id else None
        items.append({
            "in_date": str(inv.in_date),
            "warehouse": wh.name if wh else "",
            "receipt_no": inv.receipt_no or "",
            "quantity": round(inv.quantity or 0, 2),
            "batch_no": inv.batch_no or "",
            "unit_cost": round(inv.unit_cost or 0, 2),
            "total_cost": round(inv.total_cost or 0, 2),
            "material_name": mat.name if mat else "",
            "material_code": mat.code if mat else "",
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
        })
    return {"material_id": material_id, "product_id": product_id, "total": len(items), "items": items}


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
    product_id: int = Query(None, description="产品ID"),
    material_id: int | None = Query(None, description="材料ID（原料出库批次选择用）"),
    warehouse_id: int | None = Query(None, description="仓库ID"),
    order_id: int | None = Query(None, description="当前发货订单ID，用于计算批次锁定"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询可用批次，返回每个批次的锁定/可发数量：
    - 成品维度：product_id 必填，按产品+仓库；批次归属订单未确认发货完成时，(订单量-已发) 锁定给该订单；当前订单自己的批次不锁定
    - 材料维度：material_id 必填，按材料+仓库；材料无订单锁定，可发量=批次净库存"""
    if material_id is not None:
        query = db.query(WarehouseInventory).filter(
            WarehouseInventory.material_id == material_id,
        )
    else:
        if product_id is None:
            raise HTTPException(400, "product_id 或 material_id 必须二选一")
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
        locked = 0
        owner_order_no = ""
        if material_id is None:
            owner = db.query(SalesOrderItem).filter(SalesOrderItem.batch_no == key).first()
            if owner:
                owner_order_no = owner.order.order_no if owner.order else ""
                if owner.order_id != order_id and not owner.delivery_confirmed:
                    locked = max(0, round((owner.quantity or 0) - (owner.delivered_qty or 0), 2))
        b["locked_qty"] = locked
        b["available"] = max(0, round(b["quantity"] - locked, 2))
        b["owner_order_no"] = owner_order_no
        result.append(b)
    return {"items": result}


@router.post("/material-outs", tags=["库存管理"])
def create_material_out(
    data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """手动原料出库 — 一次可出多行明细 [{material_id, batch_no, quantity, remark}]。
    扣减 WarehouseInventory 对应材料+批次数量（精确批次，FIFO 跨多条库存记录）、写 StockTransaction。"""
    items = data.get("items") or [data]
    if not items:
        raise HTTPException(400, "出库明细不能为空")

    from app.utils.batch_no import generate_doc_no
    # MU 号存在流水 source_doc_no 字段（非 trans_no），必须指定字段查询，否则每天都是 2608xx01 撞号
    out_no = generate_doc_no(db, "MU", StockTransaction, "source_doc_no")
    operator = current_user.display_name or current_user.username
    created = []

    for it in items:
        material_id = it.get("material_id")
        batch_no = (it.get("batch_no") or "").strip()
        qty = float(it.get("quantity") or 0)
        if not material_id:
            raise HTTPException(400, "材料不能为空")
        material = db.query(Material).filter(Material.id == material_id, Material.is_active == 1).first()
        if not material:
            raise HTTPException(400, f"材料不存在或已停用 (id={material_id})")
        if qty <= 0:
            raise HTTPException(400, f"材料 {material.code} 出库数量必须大于0")
        if not batch_no:
            raise HTTPException(400, f"材料 {material.code} 未选择批次")

        invs = db.query(WarehouseInventory).filter(
            WarehouseInventory.material_id == material_id,
            WarehouseInventory.batch_no == batch_no,
        ).order_by(WarehouseInventory.id).all()
        stock = round(sum((i.quantity or 0) for i in invs), 2)
        if stock <= 0:
            raise HTTPException(400, f"材料 {material.code} 批次 {batch_no} 库存不足（当前 0）")
        if qty > stock:
            raise HTTPException(400, f"材料 {material.code} 批次 {batch_no} 库存不足（当前 {stock}，需出 {qty}）")
        warehouse_id = data.get("warehouse_id") or (invs[0].warehouse_id if invs else None)

        # FIFO 跨多条库存记录扣减，每条生成一条流水
        remaining = qty
        for inv in invs:
            if remaining <= 0:
                break
            take = min(inv.quantity or 0, remaining)
            if take <= 0:
                continue
            old_qty = inv.quantity
            inv_unit_cost = inv.unit_cost or 0
            inv.quantity = round(old_qty - take, 2)
            inv.total_cost = round(inv.quantity * inv_unit_cost, 2)
            trans = StockTransaction(
                trans_type="material_out",
                warehouse_id=inv.warehouse_id,
                material_id=material_id,
                batch_no=batch_no,
                quantity=-take,
                unit_cost=inv_unit_cost,
                total_amount=round(-take * inv_unit_cost, 2),
                before_qty=old_qty,
                after_qty=inv.quantity,
                before_cost=round(old_qty * inv_unit_cost, 2),
                after_cost=round(inv.quantity * inv_unit_cost, 2),
                source_doc_type="原料出库",
                source_doc_no=out_no,
                trans_no=generate_doc_no(db, "ST"),
                operator=operator,
                remark=(it.get("remark") or "").strip() or None,
            )
            db.add(trans)
            remaining = round(remaining - take, 2)

    db.commit()
    return {"out_no": out_no, "message": "原料出库成功，库存已扣减"}


@router.post("/material-outs/{out_no}/return", tags=["库存管理"])
def return_material_out(
    out_no: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """手动原料出库退回 — 按出库单号(MU-xxx)整单退回：库存回补原批次 + 红字流水(source_doc_type=原料出库退回)。
    仅手动出库可退（委外发料WO单的退回走委外单删除逻辑）；该单已退过则拒绝。"""
    if not out_no.startswith("MU-"):
        raise HTTPException(400, "仅手动出库单(MU单号)可退回，委外发料请到委外订单页处理")
    trans = db.query(StockTransaction).filter(
        StockTransaction.source_doc_no == out_no,
        StockTransaction.trans_type == "material_out",
    ).all()
    if not trans:
        raise HTTPException(404, f"出库单 {out_no} 不存在")
    already = db.query(StockTransaction).filter(
        StockTransaction.source_doc_no == out_no,
        StockTransaction.trans_type == "material_out_return",
    ).first()
    if already:
        raise HTTPException(400, f"出库单 {out_no} 已退回，不能重复退回")

    operator = current_user.display_name or current_user.username
    from app.utils.batch_no import generate_doc_no
    returned = []
    for t in trans:
        material_id = t.material_id
        batch_no = t.batch_no or ""
        back_qty = round(abs(t.quantity or 0), 2)
        if back_qty <= 0:
            continue
        # 库存回补口径与销售退货一致：优先回补正数库存记录；该批次正数记录已空则按原出库成本新建一条
        invs = db.query(WarehouseInventory).filter(
            WarehouseInventory.material_id == material_id,
            WarehouseInventory.batch_no == batch_no,
            WarehouseInventory.quantity > 0,
        ).order_by(WarehouseInventory.id).all()
        if invs:
            inv = invs[0]
        else:
            inv = WarehouseInventory(
                warehouse_id=t.warehouse_id,
                material_id=material_id,
                batch_no=batch_no,
                quantity=0,
                unit_cost=t.unit_cost or 0,
                total_cost=0,
                in_date=date.today(),
                source_type="material_out_return",
            )
            db.add(inv)
            db.flush()
        old_qty = inv.quantity or 0
        unit_cost = t.unit_cost if (t.unit_cost or 0) > 0 else (inv.unit_cost or 0)
        inv.quantity = round(old_qty + back_qty, 2)
        inv.total_cost = round(inv.quantity * unit_cost, 2)
        ret = StockTransaction(
            trans_type="material_out_return",
            warehouse_id=t.warehouse_id,
            material_id=material_id,
            batch_no=batch_no,
            quantity=back_qty,
            unit_cost=unit_cost,
            total_amount=round(back_qty * unit_cost, 2),
            before_qty=old_qty,
            after_qty=inv.quantity,
            before_cost=round(old_qty * unit_cost, 2),
            after_cost=round(inv.quantity * unit_cost, 2),
            source_doc_type="原料出库退回",
            source_doc_no=out_no,
            trans_no=generate_doc_no(db, "ST"),
            operator=operator,
            remark=f"退回出库单 {out_no}",
        )
        db.add(ret)
        returned.append({"material_id": material_id, "batch_no": batch_no, "quantity": back_qty})
    db.commit()
    return {"message": f"出库单 {out_no} 已退回，库存已回补", "returned": returned}


@router.get("/material-outs", tags=["库存管理"])
def list_material_outs(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    keyword: str = "", start_date: str = "", end_date: str = "",
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """原料出库记录列表 — 手动出库 + 委外/生产发料（source_doc_type=原料出库）的流水，按时间倒序。"""
    from sqlalchemy import or_
    q = db.query(StockTransaction).filter(StockTransaction.source_doc_type == "原料出库")
    if start_date:
        start_dt = datetime.combine(_parse_date(start_date), datetime.min.time())
        q = q.filter(StockTransaction.trans_date >= start_dt)
    if end_date:
        end_dt = datetime.combine(_parse_date(end_date), datetime.max.time().replace(microsecond=0))
        q = q.filter(StockTransaction.trans_date <= end_dt)
    if keyword:
        mat_ids = [m.id for m in db.query(Material).filter(
            (Material.name.like(f"%{keyword}%")) | (Material.code.like(f"%{keyword}%"))
        ).all()]
        if mat_ids:
            q = q.filter(or_(StockTransaction.material_id.in_(mat_ids),
                             StockTransaction.batch_no.like(f"%{keyword}%")))
        else:
            q = q.filter(StockTransaction.batch_no.like(f"%{keyword}%"))

    total = q.count()
    rows = q.order_by(StockTransaction.id.desc()).offset((page-1)*page_size).limit(page_size).all()

    items = []
    for t in rows:
        mat = db.query(Material).filter(Material.id == t.material_id).first() if t.material_id else None
        wh = db.query(Warehouse).filter(Warehouse.id == t.warehouse_id).first()
        doc_no = t.source_doc_no or ""
        source = "委外发料" if doc_no.startswith("WO-") else "手动出库"
        items.append({
            "id": t.id,
            "out_no": t.source_doc_no or "",
            "material_id": t.material_id,
            "material_code": mat.code if mat else "",
            "material_name": mat.name if mat else "",
            "material_spec": mat.spec if mat else "",
            "material_unit": mat.unit if mat else "",
            "batch_no": t.batch_no,
            "quantity": round(abs(t.quantity or 0), 2),
            "warehouse": wh.name if wh else "",
            "source": source,
            "remark": t.remark or "",
            "out_date": str(t.trans_date)[:19] if t.trans_date else "",
            "operator": t.operator or "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


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


# ==================== 盘点 ====================

@router.post("/stocktakes", tags=["库存管理"])
def create_stocktake(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建盘点单（草稿）— 自动带出该仓库所有有库存的批次作为盘点明细"""
    warehouse_id = data["warehouse_id"]
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id, Warehouse.is_active == 1).first()
    if not warehouse:
        raise HTTPException(400, "仓库档案不存在或已停用，请先在「基础档案-仓库管理」维护")

    stocktake_no = generate_doc_no(db, "STK", Stocktake, "stocktake_no")
    st = Stocktake(
        stocktake_no=stocktake_no,
        warehouse_id=warehouse_id,
        status="草稿",
        operator=current_user.display_name or current_user.username,
        remark=data.get("remark", ""),
    )
    db.add(st)
    db.flush()

    # 自动带出该仓所有有库存的批次（数量≠0）
    invs = db.query(WarehouseInventory).filter(
        WarehouseInventory.warehouse_id == warehouse_id,
        WarehouseInventory.quantity != 0,
    ).all()
    for inv in invs:
        db.add(StocktakeItem(
            stocktake_id=st.id,
            material_id=inv.material_id,
            product_id=inv.product_id,
            batch_no=inv.batch_no,
            book_qty=inv.quantity,
            actual_qty=inv.quantity,
            unit_cost=inv.unit_cost or 0,
        ))
    db.commit()
    return {"id": st.id, "stocktake_no": stocktake_no, "item_count": len(invs), "message": f"盘点单 {stocktake_no} 已创建"}


@router.get("/stocktakes", tags=["库存管理"])
def list_stocktakes(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """盘点单列表"""
    items = db.query(Stocktake).order_by(Stocktake.id.desc()).offset(
        (page - 1) * page_size).limit(page_size).all()
    total = db.query(Stocktake).count()
    return {"total": total, "page": page, "page_size": page_size, "items": [{
        "id": s.id, "stocktake_no": s.stocktake_no,
        "warehouse_name": s.warehouse.name if s.warehouse else "",
        "status": s.status,
        "item_count": len(s.items),
        "operator": s.operator or "",
        "remark": s.remark or "",
        "created_at": str(s.created_at)[:19] if s.created_at else "",
        "submitted_at": str(s.submitted_at)[:19] if s.submitted_at else "",
    } for s in items]}


@router.get("/stocktakes/{stocktake_id}", tags=["库存管理"])
def get_stocktake(stocktake_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """盘点单详情（含明细）"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    return {
        "id": s.id, "stocktake_no": s.stocktake_no,
        "warehouse_name": s.warehouse.name if s.warehouse else "",
        "status": s.status,
        "operator": s.operator or "",
        "remark": s.remark or "",
        "created_at": str(s.created_at)[:19] if s.created_at else "",
        "items": [{
            "id": it.id,
            "material_id": it.material_id,
            "material_name": it.material.name if it.material else "",
            "material_code": it.material.code if it.material else "",
            "product_id": it.product_id,
            "product_name": it.product.name_cn if it.product else "",
            "product_code": it.product.code if it.product else "",
            "batch_no": it.batch_no,
            "book_qty": it.book_qty,
            "actual_qty": it.actual_qty,
            "diff_qty": round(it.actual_qty - it.book_qty, 4),
            "unit_cost": it.unit_cost,
        } for it in s.items],
    }


@router.put("/stocktakes/{stocktake_id}/items/{item_id}", tags=["库存管理"])
def update_stocktake_item(
    stocktake_id: int, item_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """录入/修改实盘数（仅草稿状态）"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != "草稿":
        raise HTTPException(400, "已提交的盘点单不能修改")
    it = db.query(StocktakeItem).filter(StocktakeItem.id == item_id, StocktakeItem.stocktake_id == stocktake_id).first()
    if not it:
        raise HTTPException(404, "盘点明细不存在")
    actual = float(data["actual_qty"])
    if actual < 0:
        raise HTTPException(400, "实盘数量不能为负")
    it.actual_qty = actual
    db.commit()
    return {"message": "实盘数已更新"}


@router.post("/stocktakes/{stocktake_id}/items", tags=["库存管理"])
def add_stocktake_item(
    stocktake_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """盘点明细新增一行（仅草稿）— 支持账外批次盘盈

    body: {"material_id" 或 "product_id", "batch_no", "actual_qty", "unit_cost"(可选)}
    账面数自动取该批次当前台账数量（账外批次=0）
    """
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != "草稿":
        raise HTTPException(400, "已提交的盘点单不能新增明细")

    material_id = data.get("material_id")
    product_id = data.get("product_id")
    if not material_id and not product_id:
        raise HTTPException(400, "请选择物料或产品")
    batch_no = str(data.get("batch_no", "")).strip()
    if not batch_no:
        raise HTTPException(400, "请填写批次号")
    actual = float(data.get("actual_qty", 0))
    if actual < 0:
        raise HTTPException(400, "实盘数量不能为负")

    # 同批次不能重复录入
    dup = db.query(StocktakeItem).filter(
        StocktakeItem.stocktake_id == stocktake_id,
        StocktakeItem.batch_no == batch_no,
    ).first()
    if dup:
        raise HTTPException(400, f"批次 {batch_no} 已在盘点单中")

    # 账面数 = 该批次当前台账数量（账外批次 = 0）
    inv = None
    if material_id:
        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.batch_no == batch_no,
            WarehouseInventory.material_id == material_id,
        ).first()
    elif product_id:
        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.batch_no == batch_no,
            WarehouseInventory.product_id == product_id,
        ).first()
    book_qty = inv.quantity if inv else 0
    unit_cost = float(data.get("unit_cost", inv.unit_cost if inv else 0) or 0)

    it = StocktakeItem(
        stocktake_id=s.id,
        material_id=material_id,
        product_id=product_id,
        batch_no=batch_no,
        book_qty=book_qty,
        actual_qty=actual,
        unit_cost=unit_cost,
    )
    db.add(it)
    db.commit()
    return {"id": it.id, "book_qty": book_qty, "unit_cost": unit_cost,
            "message": f"已新增 {batch_no}（账面 {book_qty}，实盘 {actual}）"}


@router.delete("/stocktakes/{stocktake_id}/items/{item_id}", tags=["库存管理"])
def delete_stocktake_item(
    stocktake_id: int, item_id: int,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """删除盘点明细一行（仅草稿）"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != "草稿":
        raise HTTPException(400, "已提交的盘点单不能删除明细")
    it = db.query(StocktakeItem).filter(StocktakeItem.id == item_id, StocktakeItem.stocktake_id == stocktake_id).first()
    if not it:
        raise HTTPException(404, "盘点明细不存在")
    db.delete(it)
    db.commit()
    return {"message": f"已删除批次 {it.batch_no}"}


@router.post("/stocktakes/{stocktake_id}/submit", tags=["库存管理"])
def submit_stocktake(stocktake_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """提交盘点 — 按差异生成盘盈/盘亏流水并更新台账"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != "草稿":
        raise HTTPException(400, "该盘点单已提交")

    changed = 0
    for it in s.items:
        diff = round(it.actual_qty - it.book_qty, 4)
        if abs(diff) < 0.0001:
            continue

        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.batch_no == it.batch_no,
        ).first()
        if it.material_id:
            inv = db.query(WarehouseInventory).filter(
                WarehouseInventory.batch_no == it.batch_no,
                WarehouseInventory.material_id == it.material_id,
            ).first()
        elif it.product_id:
            inv = db.query(WarehouseInventory).filter(
                WarehouseInventory.batch_no == it.batch_no,
                WarehouseInventory.product_id == it.product_id,
            ).first()
        if not inv:
            # 账外批次（盘点新增行）：创建台账行，成本用盘点录入的成本
            uc = it.unit_cost or 0
            inv = WarehouseInventory(
                warehouse_id=s.warehouse_id,
                material_id=it.material_id,
                product_id=it.product_id,
                batch_no=it.batch_no,
                quantity=0,
                unit_cost=uc,
                total_cost=0,
                in_date=date.today(),
                source_type="stocktake",
            )
            db.add(inv)
            db.flush()

        uc = inv.unit_cost or it.unit_cost or 0
        old_qty = inv.quantity
        new_qty = round(old_qty + diff, 4)
        if new_qty < 0:
            raise HTTPException(400, f"批次 {it.batch_no} 盘亏超出账面库存（账面 {old_qty:.2f}）")
        inv.quantity = new_qty
        inv.total_cost = round(new_qty * uc, 2)

        trans_type = "stocktake_in" if diff > 0 else "stocktake_out"
        trans = StockTransaction(
            trans_type=trans_type,
            warehouse_id=s.warehouse_id,
            material_id=it.material_id,
            product_id=it.product_id,
            batch_no=it.batch_no,
            quantity=diff,
            unit_cost=uc,
            total_amount=round(diff * uc, 2),
            before_qty=old_qty,
            after_qty=new_qty,
            before_cost=round(old_qty * uc, 2),
            after_cost=round(new_qty * uc, 2),
            source_doc_type="盘点",
            source_doc_no=s.stocktake_no,
            trans_no=generate_doc_no(db, "ST"),
            operator=current_user.display_name or current_user.username,
        )
        db.add(trans)
        changed += 1

    if changed == 0:
        raise HTTPException(400, "没有差异，无需提交（如确无差异可删除该盘点单）")

    s.status = "已提交"
    s.submitted_at = func.now()
    db.commit()
    return {"message": f"盘点已提交，共 {changed} 项差异已入账"}


@router.delete("/stocktakes/{stocktake_id}", tags=["库存管理"])
def delete_stocktake(stocktake_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除盘点单（仅草稿）"""
    s = db.query(Stocktake).filter(Stocktake.id == stocktake_id).first()
    if not s:
        raise HTTPException(404, "盘点单不存在")
    if s.status != "草稿":
        raise HTTPException(400, "已提交的盘点单不能删除（可新建反向盘点调整）")
    db.delete(s)
    db.commit()
    return {"message": "盘点单已删除"}

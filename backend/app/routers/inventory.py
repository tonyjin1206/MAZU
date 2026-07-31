"""库存管理路由 — 收发存查询、库存流水、批次追溯"""

from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.auth import User
from app.models.inventory import WarehouseInventory, StockTransaction, Stocktake, StocktakeItem
from app.models.foundation import Warehouse, Material, Product
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
    items = query.order_by(WarehouseInventory.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result = []
    for inv in items:
        wh = db.query(Warehouse).filter(Warehouse.id == inv.warehouse_id).first()
        mat = db.query(Material).filter(Material.id == inv.material_id).first() if inv.material_id else None
        prod = db.query(Product).filter(Product.id == inv.product_id).first() if inv.product_id else None

        result.append({
            "id": inv.id,
            "warehouse": wh.name if wh else "",
            "material_id": inv.material_id,
            "material_name": mat.name if mat else "",
            "material_code": mat.code if mat else "",
            "material_spec": mat.spec if mat else "",
            "material_model": mat.model if mat else "",
            "product_id": inv.product_id,
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
            "product_spec": prod.spec if prod else "",
            "product_model": prod.model if prod else "",
            "batch_no": inv.batch_no,
            "quantity": inv.quantity,
            "unit_cost": round(inv.unit_cost, 2),
            "total_cost": round(inv.total_cost, 2),
            "in_date": str(inv.in_date),
            "source_type": inv.source_type or "",
            "is_frozen": inv.is_frozen,
        })

    return {"total": total, "page": page, "page_size": page_size, "items": result}


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


@router.get("/trace/{batch_no}", tags=["库存管理"])
@router.get("/available-batches", tags=["库存管理"])
def get_available_batches(
    product_id: int = Query(..., description="产品ID"),
    warehouse_id: int | None = Query(None, description="仓库ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询可用批次（按产品+仓库）"""
    query = db.query(WarehouseInventory).filter(
        WarehouseInventory.product_id == product_id,
        WarehouseInventory.quantity > 0,
    )
    if warehouse_id:
        query = query.filter(WarehouseInventory.warehouse_id == warehouse_id)
    items = query.all()
    return {"items": [
        {"id": inv.id, "batch_no": inv.batch_no, "quantity": inv.quantity,
         "unit_cost": round(inv.unit_cost, 2),
         "warehouse_id": inv.warehouse_id, "warehouse_name": inv.warehouse.name if inv.warehouse else ""}
        for inv in items
    ]}


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
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        raise HTTPException(404, "仓库不存在")

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
            raise HTTPException(400, f"批次 {it.batch_no} 台账不存在，无法盘点")

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

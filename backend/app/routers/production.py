"""生产与委外模块 API 路由 — 生产订单→委外工单→发料(批次)→完工入库(批次)"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import User
from app.models.foundation import Product, Material, Warehouse, Outsourcer, Process, Supplier
from app.models.production import (
    ProductionOrder, ProductionMaterial, ProductionProcess, ProductionReceipt, ProcessingInvoice,
    MaterialIssueItem,
)
from app.models.inventory import WarehouseInventory, StockTransaction
from app.models.purchase import AccountsPayable
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_batch_no, generate_doc_no
from sqlalchemy import func as sa_func


def _recalc_material_cost(prod_id: int, db: Session):
    """按库存流水汇总生产订单的物料成本"""
    issue_nos = [r[0] for r in db.query(MaterialIssueItem.issue_no).filter(
        MaterialIssueItem.production_id == prod_id
    ).all()]
    if not issue_nos:
        prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
        if prod:
            prod.total_material_cost = 0
        return
    txns = db.query(StockTransaction).filter(
        StockTransaction.source_doc_no.in_(issue_nos)
    ).all()
    total = 0.0
    for t in txns:
        if t.trans_type == "outsource_out":
            total += abs(t.total_amount or 0)
        elif t.trans_type == "issue_cancel":
            total -= abs(t.total_amount or 0)
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if prod:
        prod.total_material_cost = round(total, 2)


def _calc_material_issued_amount(prod_id: int, material_id: int, db: Session) -> float:
    """计算某个物料在该生产订单中的已发金额"""
    issue_nos = [r[0] for r in db.query(MaterialIssueItem.issue_no).filter(
        MaterialIssueItem.production_id == prod_id,
        MaterialIssueItem.material_id == material_id,
    ).all()]
    if not issue_nos:
        return 0.0
    txns = db.query(StockTransaction).filter(
        StockTransaction.source_doc_no.in_(issue_nos)
    ).all()
    total = 0.0
    for t in txns:
        if t.trans_type == "outsource_out":
            total += abs(t.total_amount or 0)
        elif t.trans_type == "issue_cancel":
            total -= abs(t.total_amount or 0)
    return round(total, 2)


router = APIRouter()


def _parse_date(val):
    """字符串转 date 对象"""
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


# ==================== 生产订单 ====================

@router.get("/productions", tags=["生产管理"])
def list_productions(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    status: str = Query(""), keyword: str = Query(""),
    date_from: str = Query(""), date_to: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(ProductionOrder)
    if status:
        query = query.filter(ProductionOrder.status == status)
    if keyword:
        query = query.outerjoin(Product).filter(
            ProductionOrder.order_no.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%"))
    if date_from:
        query = query.filter(ProductionOrder.created_at >= date_from)
    if date_to:
        query = query.filter(ProductionOrder.created_at <= date_to + " 23:59:59")
    total = query.count()
    items = query.order_by(ProductionOrder.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": p.id, "order_no": p.order_no,
         "product_id": p.product_id,
         "product_name": p.product.name_cn if p.product else "",
         "quantity": p.quantity, "status": p.status,
         "created_at": str(p.created_at)[:10] if p.created_at else "",
         "start_date": str(p.start_date) if p.start_date else "",
         "due_date": str(p.due_date) if p.due_date else "",
         "outsource_count": len(p.processes),
        } for p in items
    ]}


@router.get("/inventory/batch", tags=["生产管理"])
def query_batch_inventory(
    batch_no: str = Query("", description="批次号"),
    product_id: int = Query(None),
    material_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批次库存查询"""
    query = db.query(WarehouseInventory)
    if batch_no:
        query = query.filter(WarehouseInventory.batch_no.like(f"%{batch_no}%"))
    if product_id:
        query = query.filter(WarehouseInventory.product_id == product_id)
    if material_id:
        query = query.filter(WarehouseInventory.material_id == material_id)
    items = query.order_by(WarehouseInventory.id.desc()).limit(100).all()
    return {"items": [
        {"id": i.id, "warehouse": i.warehouse.name if i.warehouse else "",
         "batch_no": i.batch_no, "quantity": i.quantity,
         "in_date": str(i.in_date), "source_type": i.source_type,
        } for i in items
    ]}


@router.get("/inventory/trace", tags=["生产管理"])
def trace_batch(batch_no: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """批次号全程追溯"""
    transactions = db.query(StockTransaction).filter(
        StockTransaction.batch_no == batch_no
    ).order_by(StockTransaction.trans_date).all()
    return {"batch_no": batch_no, "trace": [
        {"id": t.id, "type": t.trans_type, "quantity": t.quantity,
         "before": t.before_qty, "after": t.after_qty,
         "doc_type": t.source_doc_type, "doc_no": t.source_doc_no,
         "date": str(t.trans_date),
        } for t in transactions
    ]}


# ==================== 新系统：生产订单详情 + 物料清单 + 工艺路线 ====================

@router.get("/productions/{prod_id}", tags=["生产管理-新"])
def get_production_detail(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """生产订单详情（含物料清单、工艺路线）"""
    p = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not p:
        raise HTTPException(404, "生产订单不存在")
    materials = db.query(ProductionMaterial).filter(ProductionMaterial.production_id == prod_id).order_by(ProductionMaterial.sort_order).all()
    processes = db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).order_by(ProductionProcess.seq).all()
    return {
        "id": p.id, "order_no": p.order_no, "sales_order_id": p.sales_order_id,
        "product_id": p.product_id, "product_name": p.product.name_cn if p.product else "",
        "quantity": p.quantity, "status": p.status,
        "total_material_cost": p.total_material_cost or 0,
        "total_process_cost": p.total_process_cost or 0,
        "due_date": str(p.due_date) if p.due_date else "",
        "remark": p.remark or "", "created_by": p.created_by or "",
        "created_at": str(p.created_at)[:10] if p.created_at else "",
        "materials": [{
            "id": m.id, "material_id": m.material_id,
            "material_name": m.material.name if m.material else "",
            "material_code": m.material.code if m.material else "",
            "material_spec": m.material.spec if m.material else "",
            "material_unit": m.material.unit if m.material else "",
            "planned_qty": m.planned_qty or 0, "actual_qty": m.actual_qty or 0,
            "unit_price": m.unit_price or 0, "subtotal": m.subtotal or 0,
            "issued_amount": _calc_material_issued_amount(prod_id, m.material_id, db),
            "sort_order": m.sort_order or 0,
        } for m in materials],
        "processes": [{
            "id": pr.id, "process_id": pr.process_id,
            "process_name": pr.process.name if pr.process else "",
            "process_code": pr.process.code if pr.process else "",
            "seq": pr.seq, "outsourcer_id": pr.outsourcer_id,
            "outsourcer_name": pr.outsourcer.supplier.name if pr.outsourcer and pr.outsourcer.supplier else "",
            "unit_price": pr.unit_price or 0,
            "process_qty": pr.process_qty or 0,
            "process_amount": pr.process_amount or 0,
            "status": pr.status,
        } for pr in processes],
    }


@router.put("/productions/{prod_id}", tags=["生产管理-新"])
def update_production(prod_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新生产订单（交期、备注）"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "订单不存在")
    if "due_date" in data and data["due_date"]:
        from datetime import date
        prod.due_date = date.fromisoformat(str(data["due_date"])[:10])
    if "remark" in data:
        prod.remark = data["remark"]
    db.commit()
    return {"message": "生产订单已更新"}


@router.post("/productions/{prod_id}/expand-bom", tags=["生产管理-新"])
def expand_bom(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """展开BOM → 生成物料需求清单"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    # 删除已有物料清单
    db.query(ProductionMaterial).filter(ProductionMaterial.production_id == prod_id).delete()
    # 从 BomItem 展开
    from app.models.foundation import BomItem
    bom_items = db.query(BomItem).filter(
        BomItem.product_id == prod.product_id,
        BomItem.is_active == 1,
    ).order_by(BomItem.sort_order).all()
    if not bom_items:
        raise HTTPException(400, "该产品没有配置 BOM")
    for idx, bi in enumerate(bom_items):
        mat = ProductionMaterial(
            production_id=prod_id,
            material_id=bi.material_id,
            planned_qty=bi.quantity * prod.quantity,
            actual_qty=0,
            unit_price=0,
            subtotal=0,
            sort_order=idx,
        )
        db.add(mat)
    # 同时：从产品工艺路线模板生成工序
    from app.models.foundation import ProductProcess
    existing_processes = db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).count()
    if existing_processes == 0:
        templates = db.query(ProductProcess).filter(
            ProductProcess.product_id == prod.product_id
        ).order_by(ProductProcess.seq).all()
        for tpl in templates:
            pp = ProductionProcess(
                production_id=prod_id,
                process_id=tpl.process_id,
                seq=tpl.seq,
                outsourcer_id=tpl.default_outsourcer_id,
                unit_price=tpl.default_unit_price,
                process_qty=prod.quantity,
                process_amount=tpl.default_unit_price * prod.quantity,
                status="待排产",
            )
            db.add(pp)
    db.commit()
    return {"message": f"BOM 已展开，生成 {len(bom_items)} 条物料需求", "material_count": len(bom_items)}


@router.put("/productions/{prod_id}/materials", tags=["生产管理-新"])
def save_materials(prod_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """批量保存物料清单"""
    items = data.get("items", [])
    # 删除旧的
    db.query(ProductionMaterial).filter(ProductionMaterial.production_id == prod_id).delete()
    for idx, item in enumerate(items):
        pm = ProductionMaterial(
            production_id=prod_id,
            material_id=item["material_id"],
            planned_qty=float(item.get("planned_qty", 0)),
            actual_qty=float(item.get("actual_qty", 0)),
            unit_price=float(item.get("unit_price", 0)),
            subtotal=float(item.get("actual_qty", 0)) * float(item.get("unit_price", 0)),
            sort_order=idx,
        )
        db.add(pm)
    db.commit()
    return {"message": f"物料清单已保存，共 {len(items)} 条"}


@router.put("/productions/{prod_id}/processes", tags=["生产管理-新"])
def save_processes(prod_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """批量保存工艺路线"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status not in ("待排产", "已排产"):
        raise HTTPException(400, "仅待排产或已排产状态可修改工艺路线")
    items = data.get("items", [])
    db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).delete()
    for idx, item in enumerate(items):
        qty = float(item.get("process_qty", prod.quantity or 0))
        up = float(item.get("unit_price", 0))
        pp = ProductionProcess(
            production_id=prod_id,
            process_id=item["process_id"],
            seq=idx + 1,
            outsourcer_id=item.get("outsourcer_id"),
            unit_price=up,
            process_qty=qty or (prod.quantity or 0),
            process_amount=round((qty or (prod.quantity or 0)) * up, 2),
            status="待排产",
        )
        db.add(pp)
    db.commit()
    return {"message": f"工艺路线已保存，共 {len(items)} 道工序"}


@router.post("/productions/{prod_id}/release", tags=["生产管理-新"])
def release_production_new(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """派产 — 锁定工艺路线，状态→已排产"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status != "待排产":
        raise HTTPException(400, f"当前状态 {prod.status} 不允许派产")
    # 检查是否有工艺路线
    process_count = db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).count()
    if process_count == 0:
        raise HTTPException(400, "请先维护工艺路线后再派产")
    prod.status = "已排产"
    # 工艺路线状态更新为"待发料"
    db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).update(
        {"status": "待发料"}
    )
    db.commit()
    return {"message": "派产成功，生产订单已转为已排产状态"}


@router.delete("/productions/{prod_id}", tags=["生产管理-新"])
def delete_production(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除生产订单（仅待排产状态允许）"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status != "待排产":
        raise HTTPException(400, "仅待排产状态的订单允许删除")
    db.delete(prod)
    db.commit()
    return {"message": "生产订单已删除"}


@router.get("/productions/{prod_id}/transactions", tags=["生产管理-新"])
def list_production_transactions(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """生产订单的出入库流水"""
    # 找到该订单所有发料单号
    issue_nos = [r[0] for r in db.query(MaterialIssueItem.issue_no).filter(
        MaterialIssueItem.production_id == prod_id
    ).all()]
    if not issue_nos:
        return {"items": []}
    txns = db.query(StockTransaction).filter(
        StockTransaction.source_doc_no.in_(issue_nos)
    ).order_by(StockTransaction.trans_date).all()
    return {"items": [{
        "id": t.id, "type": t.trans_type, "doc_no": t.source_doc_no,
        "material_name": db.query(Material.name).filter(Material.id == t.material_id).scalar() if t.material_id else (
            db.query(Product.name_cn).filter(Product.id == t.product_id).scalar() if t.product_id else ""
        ),
        "batch_no": t.batch_no,
        "quantity": t.quantity,
        "before_qty": t.before_qty,
        "after_qty": t.after_qty,
        "unit_cost": t.unit_cost,
        "operator": t.operator or "",
        "date": str(t.trans_date)[:16] if t.trans_date else "",
    } for t in txns]}


@router.post("/productions/{prod_id}/unrelease", tags=["生产管理-新"])
def unrelease_production(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """反派产 — 回到待排产状态"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status not in ("已排产", "生产中"):
        raise HTTPException(400, "当前状态不允许反派产")
    # 检查是否有工序已经发料或完工
    has_issue = db.query(MaterialIssueItem).filter(MaterialIssueItem.production_id == prod_id).first()
    if has_issue:
        raise HTTPException(400, "已有发料记录，不能反派产")
    prod.status = "待排产"
    db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).update(
        {"status": "待排产"}
    )
    db.commit()
    return {"message": "已反派产，生产订单回到待排产状态"}


# ==================== 按工序发料 ====================

@router.post("/productions/{prod_id}/processes/{proc_id}/issue", tags=["生产管理-新"])
def issue_material_to_process(
    prod_id: int, proc_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """按工序发料 — 指定原料批次出库、扣库存"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    proc = db.query(ProductionProcess).filter(ProductionProcess.id == proc_id, ProductionProcess.production_id == prod_id).first()
    if not proc:
        raise HTTPException(404, "工序不存在")

    material_id = data["material_id"]
    qty = float(data["quantity"])
    batch_no = data["batch_no"]
    warehouse_id = data.get("warehouse_id")

    # 检查批次库存
    inventory = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.material_id == material_id,
    ).first()
    if not inventory or inventory.quantity < qty:
        raise HTTPException(400, f"原料批次 {batch_no} 库存不足（当前: {inventory.quantity if inventory else 0}）")

    old_qty = inventory.quantity
    inv_unit_cost = inventory.unit_cost
    inventory.quantity -= qty
    inventory.total_cost = round(inventory.quantity * inv_unit_cost, 2)

    today_str = date.today().strftime("%Y%m%d")
    count = db.query(sa_func.count(MaterialIssueItem.id)).filter(
        MaterialIssueItem.issue_no.like(f"MI-{today_str}%")
    ).scalar() or 0
    issue_no = f"MI-{today_str}-{count+1:03d}"

    issue = MaterialIssueItem(
        issue_no=issue_no,
        production_id=prod_id,
        process_id=proc_id,
        material_id=material_id,
        batch_no=batch_no,
        quantity=qty,
        unit_price=data.get("unit_price", inv_unit_cost or 0),
        issue_date=_parse_date(data.get("issue_date")) or date.today(),
        warehouse_id=warehouse_id or inventory.warehouse_id,
        remark=data.get("remark", ""),
        operator=current_user.display_name or current_user.username,
    )
    db.add(issue)
    db.flush()

    # 库存流水
    trans = StockTransaction(
        trans_type="outsource_out",
        warehouse_id=inventory.warehouse_id,
        material_id=material_id,
        batch_no=batch_no,
        quantity=-qty,
        unit_cost=inv_unit_cost,
        total_amount=round(-qty * inv_unit_cost, 2),
        before_qty=old_qty,
        after_qty=inventory.quantity,
        before_cost=round(old_qty * inv_unit_cost, 2),
        after_cost=round(inventory.quantity * inv_unit_cost, 2),
        source_doc_type="工序发料",
        source_doc_no=issue_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 更新工序状态
    if proc.status == "待发料":
        proc.status = "已发料"

    # 更新物料实际已发量
    pm = db.query(ProductionMaterial).filter(
        ProductionMaterial.production_id == prod_id,
        ProductionMaterial.material_id == material_id,
    ).first()
    if pm:
        pm.actual_qty = (pm.actual_qty or 0) + qty
        pm.subtotal = pm.actual_qty * (pm.unit_price or 0)

    # 更新生产订单状态
    if prod.status == "已排产":
        prod.status = "生产中"

    db.commit()
    _recalc_material_cost(prod_id, db)
    db.commit()
    return {"id": issue.id, "issue_no": issue_no, "message": "发料成功"}


@router.get("/productions/{prod_id}/issues", tags=["生产管理-新"])
def list_production_issues(
    prod_id: int, process_id: int = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """查询生产订单的发料记录"""
    q = db.query(MaterialIssueItem).filter(MaterialIssueItem.production_id == prod_id)
    if process_id:
        q = q.filter(MaterialIssueItem.process_id == process_id)
    items = q.order_by(MaterialIssueItem.id.desc()).all()
    return {"items": [{
        "id": i.id, "issue_no": i.issue_no, "material_id": i.material_id,
        "material_name": i.material.name if i.material else "",
        "material_spec": i.material.spec if i.material else "",
        "material_model": i.material.model if i.material else "",
        "batch_no": i.batch_no, "quantity": i.quantity,
        "unit_price": i.unit_price or 0,
        "issue_date": str(i.issue_date),
    } for i in items]}


@router.get("/productions/{prod_id}/material-issues/{material_id}", tags=["生产管理-新"])
def list_material_issue_detail(prod_id: int, material_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """查询某个物料在订单中的发料/退料明细（含金额）"""
    from app.models.inventory import StockTransaction
    issues = db.query(MaterialIssueItem).filter(
        MaterialIssueItem.production_id == prod_id,
        MaterialIssueItem.material_id == material_id,
    ).order_by(MaterialIssueItem.id).all()

    items = []
    for iss in issues:
        txns = db.query(StockTransaction).filter(
            StockTransaction.source_doc_no == iss.issue_no
        ).order_by(StockTransaction.trans_date).all()
        for t in txns:
            items.append({
                "trans_no": t.trans_no or "",
                "batch_no": iss.batch_no,
                "type": t.trans_type,
                "type_label": "发料出库" if t.trans_type == "outsource_out" else ("取消发料" if t.trans_type == "issue_cancel" else t.trans_type),
                "quantity": abs(t.quantity or 0) if t.trans_type == "outsource_out" else (-abs(t.quantity or 0)),
                "amount": abs(t.total_amount or 0),
                "operator": t.operator or "",
                "date": str(t.trans_date)[:16] if t.trans_date else "",
            })

    # 汇总
    out_qty = sum(it["quantity"] for it in items if it["type"] == "outsource_out")
    out_amt = sum(it["amount"] for it in items if it["type"] == "outsource_out")
    cancel_qty = sum(it["quantity"] for it in items if it["type"] == "issue_cancel")
    cancel_amt = sum(it["amount"] for it in items if it["type"] == "issue_cancel")

    return {
        "items": items,
        "summary": {
            "out_qty": round(out_qty, 2),
            "out_amount": round(out_amt, 2),
            "cancel_qty": round(abs(cancel_qty), 2),
            "cancel_amount": round(cancel_amt, 2),
            "net_qty": round(out_qty - abs(cancel_qty), 2),
            "net_amount": round(out_amt - cancel_amt, 2),
        },
    }


@router.post("/productions/{prod_id}/issues/{issue_id}/cancel", tags=["生产管理-新"])
def cancel_material_issue(prod_id: int, issue_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消发料 — 恢复库存、删除发料记录"""
    issue = db.query(MaterialIssueItem).filter(
        MaterialIssueItem.id == issue_id,
        MaterialIssueItem.production_id == prod_id,
    ).first()
    if not issue:
        raise HTTPException(404, "发料记录不存在")

    qty = issue.quantity
    material_id = issue.material_id
    batch_no = issue.batch_no
    warehouse_id = issue.warehouse_id
    proc_id = issue.process_id

    # 恢复批次库存
    inventory = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.material_id == material_id,
    ).first()
    old_qty = inventory.quantity if inventory else 0
    unit_cost = inventory.unit_cost if inventory else 0
    if inventory:
        inventory.quantity += qty
        inventory.total_cost = round(inventory.quantity * unit_cost, 2)
    else:
        # 批次可能已被清空，重新创建
        inventory = WarehouseInventory(
            warehouse_id=warehouse_id,
            material_id=material_id,
            batch_no=batch_no,
            quantity=qty,
            unit_cost=0,
            total_cost=0,
            in_date=date.today(),
            source_type="issue_cancel",
        )
        db.add(inventory)

    # 库存流水（冲销）
    trans = StockTransaction(
        trans_type="issue_cancel",
        warehouse_id=warehouse_id,
        material_id=material_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_amount=round(qty * unit_cost, 2),
        before_qty=old_qty,
        after_qty=inventory.quantity if inventory else qty,
        before_cost=round(old_qty * unit_cost, 2),
        after_cost=round((inventory.quantity if inventory else qty) * unit_cost, 2),
        source_doc_type="取消发料",
        source_doc_no=issue.issue_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 更新物料实际已发量
    pm = db.query(ProductionMaterial).filter(
        ProductionMaterial.production_id == prod_id,
        ProductionMaterial.material_id == material_id,
    ).first()
    if pm:
        pm.actual_qty = max(0, (pm.actual_qty or 0) - qty)
        pm.subtotal = pm.actual_qty * (pm.unit_price or 0)

    # 先检查该工序还有几条发料记录（删除前）
    proc_id_for_check = issue.process_id
    remaining = db.query(MaterialIssueItem).filter(
        MaterialIssueItem.production_id == prod_id,
        MaterialIssueItem.process_id == proc_id_for_check,
    ).count() - 1  # 减去当前正要删除的这条

    # 删除发料记录
    db.delete(issue)

    # 如果没有剩余发料记录，工序状态回退到待发料
    if remaining <= 0 and proc_id_for_check:
        proc = db.query(ProductionProcess).filter(
            ProductionProcess.id == proc_id_for_check,
            ProductionProcess.production_id == prod_id,
        ).first()
        if proc and proc.status == "已发料":
            proc.status = "待发料"

    db.commit()
    _recalc_material_cost(prod_id, db)
    db.commit()
    return {"message": f"发料已取消，物料已退回批次 {batch_no}"}


# ==================== 工序完工 ====================

@router.post("/productions/{prod_id}/processes/{proc_id}/finish", tags=["生产管理-新"])
def finish_process(
    prod_id: int, proc_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """工序完工 — 必须录入加工费，上道完工下道自动流转"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    proc = db.query(ProductionProcess).filter(ProductionProcess.id == proc_id, ProductionProcess.production_id == prod_id).first()
    if not proc:
        raise HTTPException(404, "工序不存在")

    # 委外工序必须录入加工费
    if proc.outsourcer_id:
        unit_price = float(data.get("unit_price", 0))
        process_qty = float(data.get("process_qty", 0))
        if unit_price <= 0 or process_qty <= 0:
            raise HTTPException(400, "委外工序完工必须录入加工单价和加工数量")
    else:
        unit_price = float(data.get("unit_price", 0))
        process_qty = float(data.get("process_qty", proc.process_qty or prod.quantity or 0))

    proc.unit_price = unit_price
    proc.process_qty = process_qty
    proc.process_amount = round(process_qty * unit_price, 2)
    proc.status = "已完工"

    # 更新生产订单加工费合计
    all_processes = db.query(ProductionProcess).filter(ProductionProcess.production_id == prod_id).all()
    prod.total_process_cost = sum(p.process_amount or 0 for p in all_processes)

    # 自动流转：下一道工序→待发料（可能还需要发料）
    next_proc = db.query(ProductionProcess).filter(
        ProductionProcess.production_id == prod_id,
        ProductionProcess.seq == proc.seq + 1,
    ).first()
    if next_proc:
        next_proc.status = "待发料"

    # 检查是否所有工序都完工了
    all_done = all(p.status == "已完工" for p in all_processes)
    if all_done:
        prod.status = "已完成"

    db.commit()
    return {
        "message": f"工序「{proc.process.name}」已完工",
        "has_next": bool(next_proc),
        "next_process_name": next_proc.process.name if next_proc else "",
        "is_last": not bool(next_proc),
    }


@router.post("/productions/{prod_id}/processes/{proc_id}/revert", tags=["生产管理-新"])
def revert_process(prod_id: int, proc_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """反退工序到未开工状态"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    proc = db.query(ProductionProcess).filter(ProductionProcess.id == proc_id, ProductionProcess.production_id == prod_id).first()
    if not proc:
        raise HTTPException(404, "工序不存在")
    if proc.status == "待排产":
        raise HTTPException(400, "该工序尚未排产，无需反退")

    was_completed = proc.status == "已完工"
    proc.status = "待发料"
    proc.process_amount = 0
    proc.unit_price = 0
    proc.process_qty = 0

    if was_completed:
        prod.total_process_cost = sum(
            p.process_amount or 0 for p in db.query(ProductionProcess).filter(
                ProductionProcess.production_id == prod_id
            ).all()
        )
        if prod.status == "已完成":
            prod.status = "生产中"

    db.commit()
    return {"message": f"工序「{proc.process.name}」已反退到未开工状态"}


# ==================== 完工入库 ====================

@router.post("/productions/{prod_id}/receipt", tags=["生产管理-新"])
def receipt_production(prod_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """完工入库 — 末道工序完工后入库，允许损耗"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status == "已关闭":
        raise HTTPException(400, "该订单已关闭，无法操作")
    if prod.status not in ("已完成", "部分入库", "已入库"):
        raise HTTPException(400, "请先完成所有工序后再完工入库")

    qty = float(data["quantity"])
    warehouse_id = data["warehouse_id"]
    if qty <= 0:
        raise HTTPException(400, "入库数量必须大于 0")

    material_cost = float(data.get("material_cost", 0))
    process_cost = float(data.get("process_cost", 0))
    if material_cost < 0 or process_cost < 0:
        raise HTTPException(400, "转出成本不能为负数")

    # 校验累计转出成本不超过总投入
    new_mat_total = (prod.transferred_material_cost or 0) + material_cost
    new_proc_total = (prod.transferred_process_cost or 0) + process_cost
    if new_mat_total > (prod.total_material_cost or 0) + 0.01:
        raise HTTPException(400, f"材料成本转出合计 {new_mat_total:.2f} 超出总投入 {prod.total_material_cost:.2f}")
    if new_proc_total > (prod.total_process_cost or 0) + 0.01:
        raise HTTPException(400, f"加工费转出合计 {new_proc_total:.2f} 超出总投入 {prod.total_process_cost:.2f}")

    today_str = date.today().strftime("%Y%m%d")
    count = db.query(sa_func.count(ProductionReceipt.id)).filter(
        ProductionReceipt.receipt_no.like(f"FG-{today_str}%")
    ).scalar() or 0
    receipt_no = f"FG-{today_str}-{count+1:03d}"
    batch_no = generate_batch_no(db, prefix="FG")

    unit_cost = round((material_cost + process_cost) / qty, 2) if qty else 0

    receipt = ProductionReceipt(
        receipt_no=receipt_no,
        production_id=prod_id,
        product_id=prod.product_id,
        batch_no=batch_no,
        quantity=qty,
        warehouse_id=warehouse_id,
        material_cost=material_cost,
        process_cost=process_cost,
        unit_cost=unit_cost,
        receipt_date=_parse_date(data.get("receipt_date")) or date.today(),
        operator=current_user.display_name or current_user.username,
    )
    db.add(receipt)
    db.flush()

    # 成品库存
    inventory = WarehouseInventory(
        warehouse_id=warehouse_id,
        product_id=prod.product_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_cost=round(qty * unit_cost, 2),
        in_date=_parse_date(data.get("receipt_date")) or date.today(),
        source_type="production",
        source_doc_id=receipt.id,
    )
    db.add(inventory)

    # 库存流水
    trans = StockTransaction(
        trans_type="production_in",
        warehouse_id=warehouse_id,
        product_id=prod.product_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_amount=round(qty * unit_cost, 2),
        before_qty=0,
        after_qty=qty,
        before_cost=0,
        after_cost=round(qty * unit_cost, 2),
        source_doc_type="完工入库",
        source_doc_no=receipt_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 更新生产订单累计值
    prod.received_qty = (prod.received_qty or 0) + qty
    prod.transferred_material_cost = new_mat_total
    prod.transferred_process_cost = new_proc_total
    prod.status = "已入库" if (prod.received_qty or 0) >= prod.quantity else "部分入库"

    db.commit()
    return {
        "id": receipt.id, "receipt_no": receipt_no, "batch_no": batch_no,
        "message": f"完工入库成功，批次: {batch_no}，数量: {qty}，成本: ¥{qty * unit_cost:,.2f}",
    }


@router.post("/productions/{prod_id}/receipts/{receipt_id}/cancel", tags=["生产管理-新"])
def cancel_receipt(prod_id: int, receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消完工入库 — 删除库存、冲销流水、回退累计值"""
    from app.models.inventory import WarehouseInventory, StockTransaction

    receipt = db.query(ProductionReceipt).filter(ProductionReceipt.id == receipt_id, ProductionReceipt.production_id == prod_id).first()
    if not receipt:
        raise HTTPException(404, "入库单不存在")

    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")

    qty = receipt.quantity
    material_cost = receipt.material_cost or 0
    process_cost = receipt.process_cost or 0
    batch_no = receipt.batch_no

    # 删除成品库存
    db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.product_id == receipt.product_id,
    ).delete()

    # 库存流水（冲销）
    trans = StockTransaction(
        trans_type="receipt_cancel",
        warehouse_id=receipt.warehouse_id,
        product_id=receipt.product_id,
        batch_no=batch_no,
        quantity=-qty,
        unit_cost=receipt.unit_cost or 0,
        total_amount=round(-qty * (receipt.unit_cost or 0), 2),
        before_qty=qty,
        after_qty=0,
        before_cost=round(qty * (receipt.unit_cost or 0), 2),
        after_cost=0,
        source_doc_type="取消入库",
        source_doc_no=receipt.receipt_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 删除入库记录
    db.delete(receipt)
    db.flush()

    # 回退生产订单累计值
    prod.received_qty = max(0, (prod.received_qty or 0) - qty)
    prod.transferred_material_cost = max(0, (prod.transferred_material_cost or 0) - material_cost)
    prod.transferred_process_cost = max(0, (prod.transferred_process_cost or 0) - process_cost)

    # 如果没有任何入库了且仍有已完工工序，状态回到已完成
    remaining = db.query(sa_func.count(ProductionReceipt.id)).filter(
        ProductionReceipt.production_id == prod_id
    ).scalar() or 0
    if remaining == 0:
        has_done = db.query(ProductionProcess).filter(
            ProductionProcess.production_id == prod_id,
            ProductionProcess.status == "已完工",
        ).first()
        if has_done:
            prod.status = "已完成"
    else:
        prod.status = "已入库" if (prod.received_qty or 0) >= prod.quantity else "部分入库"

    db.commit()
    return {"message": f"入库已取消，批次 {batch_no} 已退回"}


@router.get("/productions/{prod_id}/receipts", tags=["生产管理-新"])
def list_production_receipts(prod_id: int, db: Session = Depends(get_db)):
    """查询生产订单的所有入库单"""
    receipts = db.query(ProductionReceipt).filter(ProductionReceipt.production_id == prod_id).order_by(ProductionReceipt.id.desc()).all()
    return {"items": [{
        "id": r.id, "receipt_no": r.receipt_no,
        "batch_no": r.batch_no, "quantity": r.quantity,
        "material_cost": r.material_cost or 0,
        "process_cost": r.process_cost or 0,
        "unit_cost": r.unit_cost or 0,
        "product_name": r.product.name_cn if r.product else "",
        "product_spec": r.product.spec if r.product else "",
        "product_model": r.product.model if r.product else "",
        "warehouse_name": r.warehouse.name if r.warehouse else "",
        "receipt_date": str(r.receipt_date) if r.receipt_date else "",
        "operator": r.operator or "",
    } for r in receipts]}


# ==================== 关闭/取消关闭 ====================

@router.post("/productions/{prod_id}/close", tags=["生产管理-新"])
def close_production(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """关闭生产订单"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status == "已关闭":
        raise HTTPException(400, "该订单已关闭")
    if prod.status not in ("已完成", "部分入库", "已入库"):
        raise HTTPException(400, "仅已完成/已入库的订单可以关闭")
    prod.status = "已关闭"
    db.commit()
    return {"message": "生产订单已关闭"}


@router.post("/productions/{prod_id}/unclose", tags=["生产管理-新"])
def unclose_production(prod_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消关闭生产订单"""
    prod = db.query(ProductionOrder).filter(ProductionOrder.id == prod_id).first()
    if not prod:
        raise HTTPException(404, "生产订单不存在")
    if prod.status != "已关闭":
        raise HTTPException(400, "仅已关闭状态可取消关闭")
    # 回到已入库/部分入库
    prod.status = "已入库" if (prod.received_qty or 0) >= prod.quantity else "部分入库"
    db.commit()
    return {"message": "已取消关闭"}


# ==================== 生产工作台 ====================

@router.get("/workspace", tags=["生产管理-新"])
def production_workspace(
    status: str = Query(""), keyword: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """生产工作台总览 — 查看每道工序状态"""
    query = db.query(ProductionOrder).filter(
        ProductionOrder.status.in_(["已排产", "生产中", "已完成", "部分入库", "已入库", "已关闭"])
    )
    if status:
        query = query.filter(ProductionOrder.status == status)
    if keyword:
        query = query.outerjoin(Product).filter(
            ProductionOrder.order_no.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%"))
    productions = query.order_by(ProductionOrder.id.desc()).all()

    result = []
    for p in productions:
        processes = db.query(ProductionProcess).filter(
            ProductionProcess.production_id == p.id
        ).order_by(ProductionProcess.seq).all()

        # 当前加工中的工序（按优先级：加工中 > 已发料 > 待发料）
        current_proc = None
        for pr in processes:
            if pr.status == "加工中":
                current_proc = pr
                break
        if not current_proc:
            for pr in processes:
                if pr.status == "已发料":
                    current_proc = pr
                    break
        if not current_proc:
            for pr in processes:
                if pr.status == "待发料":
                    current_proc = pr
                    break

        # 物料状态
        materials = db.query(ProductionMaterial).filter(
            ProductionMaterial.production_id == p.id
        ).all()
        total_planned = sum(m.planned_qty or 0 for m in materials)
        total_issued = sum(m.actual_qty or 0 for m in materials)
        material_pct = round(total_issued / total_planned * 100, 1) if total_planned else 0

        # 进度
        total_procs = len(processes)
        done_procs = sum(1 for pr in processes if pr.status == "已完工")
        progress = round(done_procs / total_procs * 100) if total_procs else 0

        # 查找最新的入库单
        last_receipt = db.query(ProductionReceipt).filter(
            ProductionReceipt.production_id == p.id
        ).order_by(ProductionReceipt.id.desc()).first()

        result.append({
            "id": p.id, "order_no": p.order_no,
            "product_name": p.product.name_cn if p.product else "",
            "quantity": p.quantity, "status": p.status,
            "total_material_cost": p.total_material_cost or 0,
            "total_process_cost": p.total_process_cost or 0,
            "received_qty": p.received_qty or 0,
            "transferred_material_cost": p.transferred_material_cost or 0,
            "transferred_process_cost": p.transferred_process_cost or 0,
            "last_receipt_id": last_receipt.id if last_receipt else None,
            "last_receipt_no": last_receipt.receipt_no if last_receipt else "",
            "material_pct": material_pct,
            "progress": progress,
            "total_processes": total_procs,
            "done_processes": done_procs,
            "current_process_name": current_proc.process.name if current_proc and current_proc.process else "",
            "current_process_status": current_proc.status if current_proc else "",
            "current_outsourcer_name": (
                current_proc.outsourcer.supplier.name
                if current_proc and current_proc.outsourcer and current_proc.outsourcer.supplier
                else ""
            ) if current_proc else "",
            "processes": [{
                "id": pr.id, "process_name": pr.process.name if pr.process else "",
                "seq": pr.seq, "status": pr.status,
                "outsourcer_name": (
                    pr.outsourcer.supplier.name if pr.outsourcer and pr.outsourcer.supplier else "自产"
                ),
                "unit_price": pr.unit_price or 0,
                "process_qty": pr.process_qty or 0,
            } for pr in processes],
        })

    return {"items": result}


# ==================== 加工费发票 ====================

@router.get("/processing-invoices", tags=["生产管理-加工费发票"])
def list_processing_invoices(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """加工费发票列表"""
    items = db.query(ProcessingInvoice).order_by(ProcessingInvoice.id.desc()).offset(
        (page - 1) * page_size).limit(page_size).all()
    total = db.query(ProcessingInvoice).count()
    return {"total": total, "page": page, "page_size": page_size, "items": [{
        "id": inv.id, "invoice_no": inv.invoice_no, "amount": inv.amount or 0,
        "production_id": inv.production_id,
        "order_no": db.query(ProductionOrder.order_no).filter(ProductionOrder.id == inv.production_id).scalar() or "",
        "receipt_id": inv.receipt_id,
        "receipt_no": db.query(ProductionReceipt.receipt_no).filter(ProductionReceipt.id == inv.receipt_id).scalar() if inv.receipt_id else "",
        "supplier_id": inv.supplier_id,
        "invoice_date": str(inv.invoice_date) if inv.invoice_date else "",
        "supplier_name": inv.supplier_name or "",
        "supplier_tax_id": inv.supplier_tax_id or "",
        "service_type": inv.service_type or "",
        "service_qty": inv.service_qty or 0,
        "unit_price": inv.unit_price or 0,
        "tax_rate": inv.tax_rate or 0,
        "amount_excl_tax": inv.amount_excl_tax or 0,
        "remark": inv.remark or "",
    } for inv in items]}


@router.post("/processing-invoices", tags=["生产管理-加工费发票"])
def create_processing_invoice(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建加工费发票（参照完工入库单或生产订单）"""
    receipt_id = data.get("receipt_id")
    production_id = data.get("production_id")
    receipt = None
    if receipt_id:
        receipt = db.query(ProductionReceipt).filter(ProductionReceipt.id == receipt_id).first()
        if not receipt:
            raise HTTPException(404, "完工入库单不存在")
        production_id = receipt.production_id

    if not production_id:
        raise HTTPException(400, "请指定生产订单或完工入库单")

    # 检查是否已开票
    existing = db.query(ProcessingInvoice).filter(
        ProcessingInvoice.production_id == production_id
    ).first()
    if existing:
        raise HTTPException(400, f"该生产订单已开票（发票号: {existing.invoice_no}）")

    # 计算加工费：该生产订单所有委外工序完工的加工费
    processes = db.query(ProductionProcess).filter(
        ProductionProcess.production_id == production_id,
        ProductionProcess.status == "已完工",
        ProductionProcess.outsourcer_id.isnot(None),
    ).all()
    if not processes:
        raise HTTPException(400, "该生产订单没有已完工的委外工序")

    # 取第一个委外工序的委外商对应的供应商
    first_proc = processes[0]
    supplier_id = first_proc.outsourcer.supplier_id if first_proc.outsourcer else None
    if not supplier_id:
        raise HTTPException(400, "委外商未关联供应商")

    total_amount = sum(p.process_amount or 0 for p in processes)

    today_str = date.today().strftime("%Y%m%d")
    count = db.query(sa_func.count(ProcessingInvoice.id)).filter(
        ProcessingInvoice.invoice_no.like(f"PI-{today_str}%")
    ).scalar() or 0
    invoice_no = f"PI-{today_str}-{count+1:03d}"

    inv = ProcessingInvoice(
        invoice_no=invoice_no,
        production_id=production_id,
        receipt_id=receipt_id or None,
        supplier_id=supplier_id,
        amount=total_amount,
        invoice_date=_parse_date(data.get("invoice_date")) or date.today(),
        remark=data.get("remark", ""),
        supplier_name=data.get("supplier_name", ""),
        supplier_tax_id=data.get("supplier_tax_id", ""),
        service_type=data.get("service_type", "加工费"),
        service_qty=float(data.get("service_qty", 0)),
        unit_price=float(data.get("unit_price", 0)),
        tax_rate=float(data.get("tax_rate", 0)),
        amount_excl_tax=float(data.get("amount_excl_tax", 0)),
        created_by=current_user.display_name or current_user.username,
    )
    db.add(inv)
    db.flush()

    # 生成应付账款
    today_str = date.today().strftime("%Y%m%d")
    ap_count = db.query(sa_func.count(AccountsPayable.id)).filter(
        AccountsPayable.ap_no.like(f"AP-{today_str}%")
    ).scalar() or 0
    ap_no_str = f"AP-{today_str}-{ap_count+1:03d}"
    ap = AccountsPayable(
        ap_no=ap_no_str,
        source_type="processing_invoice",
        source_id=inv.id,
        supplier_id=supplier_id,
        amount=total_amount,
        amount_fc=total_amount,
        paid_amount=0,
        balance=total_amount,
        status="未付款",
    )
    db.add(ap)
    db.commit()

    return {"id": inv.id, "invoice_no": invoice_no, "ap_no": ap_no_str, "message": f"加工费发票已创建，金额: ¥{total_amount:,.2f}，应付账款已生成"}


@router.delete("/processing-invoices/{invoice_id}", tags=["生产管理-加工费发票"])
def delete_processing_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除加工费发票（同时删除关联的应付账款）"""
    inv = db.query(ProcessingInvoice).filter(ProcessingInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "发票不存在")
    # 删除关联应付
    db.query(AccountsPayable).filter(
        AccountsPayable.source_type == "processing_invoice",
        AccountsPayable.source_id == invoice_id,
    ).delete()
    db.delete(inv)
    db.commit()
    return {"message": "加工费发票已删除"}


@router.get("/processing-invoices/receipt-candidates", tags=["生产管理-加工费发票"])
def list_processing_invoice_candidates(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """查询可开加工费发票的完工入库单（有委外工序但未开票的）"""
    invoiced_receipts = [r[0] for r in db.query(ProcessingInvoice.receipt_id).all()]
    invoiced_prods = [r[0] for r in db.query(ProcessingInvoice.production_id).all()]

    # 找所有有已完工委外工序的生产订单
    prods_with_done = db.query(ProductionProcess.production_id).filter(
        ProductionProcess.status == "已完工",
        ProductionProcess.outsourcer_id.isnot(None),
    ).distinct().all()
    prod_ids = [r[0] for r in prods_with_done]

    result = []
    for pid in prod_ids:
        if pid in invoiced_prods:
            continue
        processes = db.query(ProductionProcess).filter(
            ProductionProcess.production_id == pid,
            ProductionProcess.status == "已完工",
            ProductionProcess.outsourcer_id.isnot(None),
        ).all()
        if not processes:
            continue
        total_fee = sum(p.process_amount or 0 for p in processes)
        prod = db.query(ProductionOrder).filter(ProductionOrder.id == pid).first()
        if not prod:
            continue
        # 查找关联的入库单
        receipt = db.query(ProductionReceipt).filter(ProductionReceipt.production_id == pid).first()
        processes = db.query(ProductionProcess).filter(
            ProductionProcess.production_id == pid,
            ProductionProcess.status == "已完工",
            ProductionProcess.outsourcer_id.isnot(None),
        ).all()
        first_proc = processes[0] if processes else None
        supplier_id = first_proc.outsourcer.supplier_id if first_proc and first_proc.outsourcer else None
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first() if supplier_id else None

        result.append({
            "receipt_id": receipt.id if receipt else None,
            "receipt_no": receipt.receipt_no if receipt else f"FG-{pid:04d}(auto)",
            "production_id": pid,
            "order_no": prod.order_no or "",
            "product_name": prod.product.name_cn if prod.product else "",
            "batch_no": receipt.batch_no if receipt else "",
            "quantity": receipt.quantity if receipt else 0,
            "receipt_date": str(receipt.receipt_date) if receipt else "",
            "process_fee": round(total_fee, 2),
            "process_count": len(processes),
            "supplier_id": supplier.id if supplier else None,
            "supplier_name": supplier.name if supplier else "",
            "supplier_tax_id": supplier.tax_id if hasattr(supplier, 'tax_id') else "",
        })
    return {"items": result}

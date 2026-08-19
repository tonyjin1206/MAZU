"""委外订单模块 API 路由 — 销售转外发→维护加工信息→审核(应付)→完工(生成待入库单)"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import Product, Supplier, Customer, Process, ProductProcess
from app.models.inventory import StockInOrder, WarehouseInventory, StockTransaction
from app.models.production import OutsourceOrder, OutsourceMaterial
from app.models.purchase import AccountsPayable
from app.models.sales import SalesOrder, SalesOrderItem
from app.models.foundation import Material
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_doc_no

router = APIRouter()


def _os_materials(db: Session, os_order_id: int):
    """委外单材料认领明细"""
    mats = db.query(OutsourceMaterial).filter(OutsourceMaterial.outsource_order_id == os_order_id).all()
    return [{
        "material_id": m.material_id,
        "material_code": m.material.code if m.material else "",
        "material_name": m.material.name if m.material else "",
        "spec": m.material.spec or "" if m.material else "",
        "unit": m.material.unit or "" if m.material else "",
        "batch_no": m.batch_no or "",
        "quantity": m.quantity or 0,
        "unit_cost": m.unit_cost or 0,
        "supply_type": m.supply_type or "己方提供",
    } for m in mats]


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
        proc = db.query(Process).filter(Process.id == os.process_id).first() if os.process_id else None
        # 关联销售订单号（转委外的单一一对应；直接录入为空）
        sales_no = ""
        if os.sales_order_id:
            so = db.query(SalesOrder).filter(SalesOrder.id == os.sales_order_id).first()
            sales_no = so.order_no if so else ""
        # 已入库数量（来自关联待入库单）
        received = db.query(StockInOrder).filter(
            StockInOrder.outsource_order_id == os.id,
            StockInOrder.status != "已退回",
        ).all()
        received_qty = sum((r.received_qty or 0) for r in received)
        result.append({
            "id": os.id,
            "outsource_no": os.outsource_no,
            "sales_order_no": sales_no,
            "sales_order_id": os.sales_order_id,
            "sales_item_id": os.sales_item_id,
            "product_id": os.product_id,
            "product_code": prod.code if prod else "",
            "product_name": prod.name_cn if prod else "",
            "quantity": os.quantity,
            "received_qty": received_qty,
            "process_id": os.process_id,
            "process_name": proc.name if proc else "",
            "outsourcer_id": os.outsourcer_id,
            "outsourcer_name": sup.name if sup else "",
            "unit_price": os.unit_price or 0,
            "amount": os.amount or 0,
            "supply_type": os.supply_type or "己方提供",
            "materials": _os_materials(db, os.id),
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
    proc = db.query(Process).filter(Process.id == os.process_id).first() if os.process_id else None
    so = db.query(SalesOrder).filter(SalesOrder.id == os.sales_order_id).first() if os.sales_order_id else None
    return {
        "id": os.id,
        "outsource_no": os.outsource_no,
        "sales_order_no": so.order_no if so else "",
        "sales_item_id": os.sales_item_id,
        "product_id": os.product_id,
        "product_code": prod.code if prod else "",
        "product_name": prod.name_cn if prod else "",
        "quantity": os.quantity,
        "process_id": os.process_id,
        "process_name": proc.name if proc else "",
        "outsourcer_id": os.outsourcer_id,
        "outsourcer_name": sup.name if sup else "",
        "unit_price": os.unit_price or 0,
        "amount": os.amount or 0,
        "supply_type": os.supply_type or "己方提供",
        "materials": _os_materials(db, os.id),
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


def _is_last_process(db: Session, os_order) -> bool:
    """判定委外单工序是否该产品工艺路线末道工序。
    无工艺路线 / 未挂工序的委外单视为末道（保持原有行为）。"""
    if not os_order.process_id:
        return True
    pp = db.query(ProductProcess).filter(
        ProductProcess.product_id == os_order.product_id,
    ).order_by(ProductProcess.seq.desc(), ProductProcess.id.desc()).first()
    if pp is None:
        return True
    return pp.process_id == os_order.process_id


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
    # 末道工序判定：只有该产品工艺路线里 seq 最大的一道工序完工才出成品
    # 前面工序只生成应付账款（加工费），不生成成品待入库单；无工艺路线的产品视为末道，行为不变
    is_last = _is_last_process(db, os)
    if is_last:
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
    if is_last:
        return {"message": f"委外订单已审核：已生成应付账款 {ap_no}，待入库单已生成，收货请到「库存管理 → 成品入库」", "amount": os.amount}
    return {"message": f"该工序已审核，已生成应付账款 {ap_no}；非末道工序不生成成品待入库单，末道工序完工后统一入库", "amount": os.amount}


@router.post("/orders/{order_id}/unapprove", tags=["委外管理"])
def unapprove_order(
    order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """取消审核委外订单 → 回「待确认」（有下游应收/入库则拒绝）"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "已审核":
        raise HTTPException(400, f"当前状态「{os.status}」，不能取消审核")
    # 下游：应付账款（加工费）+ 待入库单
    ap = db.query(AccountsPayable).filter(
        AccountsPayable.source_type == "outsource",
        AccountsPayable.source_id == os.id,
    ).first()
    if ap and (ap.paid_amount or 0) > 0:
        raise HTTPException(400, f"该委外单应付账款 {ap.ap_no} 已付款，请先退回付款")
    if ap:
        db.delete(ap)
    sin = db.query(StockInOrder).filter(
        StockInOrder.source_type == "outsource",
        StockInOrder.outsource_order_id == os.id,
        StockInOrder.status.in_(["待入库", "部分入库"]),
    ).first()
    if sin and (sin.received_qty or 0) > 0:
        raise HTTPException(400, "该委外单已部分入库，请先退回入库单")
    if sin:
        db.delete(sin)
    os.status = "待确认"
    db.commit()
    return {"message": "已取消审核，可修改或删除委外订单"}


@router.delete("/orders/{order_id}", tags=["委外管理"])
def delete_order(
    order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """删除委外订单（仅待确认状态；已认领材料先退回原批次，单据链闭环；删除后销售明细行回到未生产，可重新操作）"""
    os = db.query(OutsourceOrder).filter(OutsourceOrder.id == order_id).first()
    if not os:
        raise HTTPException(404, "委外订单不存在")
    if os.status != "待确认":
        raise HTTPException(400, f"当前状态「{os.status}」不能删除")
    operator = current_user.display_name or current_user.username
    sid = os.sales_item_id
    try:
        # 单据链闭环：删除前先把已认领材料退回原批次（加回库存 + 原料出库退回流水）
        mats = db.query(OutsourceMaterial).filter(OutsourceMaterial.outsource_order_id == os.id).all()
        for m in mats:
            invs = db.query(WarehouseInventory).filter(
                WarehouseInventory.material_id == m.material_id,
                WarehouseInventory.batch_no == m.batch_no,
            ).order_by(WarehouseInventory.id).all()
            if invs:
                inv = invs[0]
                unit_cost = m.unit_cost or inv.unit_cost or 0
                old_qty = round(inv.quantity or 0, 2)
                inv.quantity = round(old_qty + (m.quantity or 0), 2)
                inv.total_cost = round(inv.quantity * unit_cost, 2)
                db.add(StockTransaction(
                    trans_type="material_out_return",
                    warehouse_id=inv.warehouse_id,
                    material_id=m.material_id,
                    batch_no=m.batch_no,
                    quantity=round(m.quantity or 0, 2),
                    unit_cost=unit_cost,
                    total_amount=round((m.quantity or 0) * unit_cost, 2),
                    before_qty=old_qty,
                    after_qty=inv.quantity,
                    before_cost=round(old_qty * unit_cost, 2),
                    after_cost=round(inv.quantity * unit_cost, 2),
                    source_doc_type="原料出库退回",
                    source_doc_no=os.outsource_no,
                    trans_no=generate_doc_no(db, "ST"),
                    operator=operator,
                ))
            db.delete(m)
        # 删除委外单（先 flush 让删除对后续查询可见，仍属同一事务）
        db.delete(os)
        db.flush()
        # 铁律：删除后检查该销售明细行是否还有其他委外单——没有了才解锁回未生产
        if sid:
            remain = db.query(OutsourceOrder).filter(
                OutsourceOrder.sales_item_id == sid,
                OutsourceOrder.status != "已退回",
            ).count()
            if remain == 0:
                item = db.query(SalesOrderItem).filter(SalesOrderItem.id == sid).first()
                if item and item.production_status == "已通知外发":
                    item.production_status = "未生产"
        db.commit()
    except Exception:
        db.rollback()
        raise
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
    """销售订单转委外：已「转外发」的销售明细行列表（按行显示产品+批次号）+ 委外状态"""
    from app.models.sales import SalesOrder, SalesOrderItem
    query = db.query(SalesOrderItem).join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id).filter(
        SalesOrderItem.production_status == "已通知外发",
        SalesOrder.status.in_(["已审", "生产中", "部分发货"]),
    )
    if keyword:
        query = query.join(Customer, Customer.id == SalesOrder.customer_id).filter(
            SalesOrder.order_no.like(f"%{keyword}%") | Customer.name_cn.like(f"%{keyword}%"))
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)
    total = query.count()
    items = query.order_by(SalesOrderItem.id.asc()).offset((page - 1) * page_size).limit(page_size).all()

    def row_status(si):
        """该明细行委外状态（人工判定完成）:
        none=未转委外 / partial=部分转委外(还可追加) / transferred=已转委外订单(工序已全部生成不可追加) / completed=委外完成(手动完成)
        工序判定: 已生成工序数 >= 工艺路线工序数 => transferred；完成判定: si.outsource_done=1"""
        if si.outsource_done:
            return "completed"
        os_orders = db.query(OutsourceOrder).filter(
            OutsourceOrder.sales_item_id == si.id,
            OutsourceOrder.status != "已退回",
        ).all()
        if not os_orders:
            return "none"
        # 有工艺路线的产品：按工序是否全部生成判定
        from app.models.foundation import ProductProcess
        total_procs = db.query(ProductProcess).filter(ProductProcess.product_id == si.product_id).count()
        if total_procs > 0:
            gen_procs = {o.process_id for o in os_orders if o.process_id}
            if len(gen_procs) >= total_procs:
                return "transferred"
            return "partial"
        # 无工艺路线兜底：按数量是否达上限判定
        total_qty = sum((o.quantity or 0) for o in os_orders)
        if total_qty >= (si.quantity or 0) * 1.1:
            return "transferred"
        return "partial"

    result = []
    for si in items:
        if si.production_status in ("已停售", "已入库"):
            continue
        prod = si.product
        result.append({
            "sales_item_id": si.id, "order_id": si.order_id,
            "order_no": si.order.order_no,
            "order_date": str(si.order.order_date) if si.order.order_date else "",
            "customer_name": si.order.customer.name_cn if si.order.customer else "",
            "product_id": si.product_id,
            "code": prod.code if prod else "", "name": prod.name_cn if prod else "",
            "spec": (prod.spec or "") if prod else "", "unit": prod.unit if prod else "",
            "quantity": si.quantity or 0, "batch_no": si.batch_no or "",
            "outsource_status": row_status(si),
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.post("/sales-to-outsource/{item_id}/return", tags=["委外管理"])
def return_sales_to_outsource(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """退回销售明细行关联的委外订单（销售订单明细变更前必须先退委外单）
    待确认的直接删除；已审核/已完工的先取消审核再删除；已入库(有下游)则拒绝"""
    from app.models.sales import SalesOrderItem
    from app.models.inventory import StockInOrder
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    os_orders = db.query(OutsourceOrder).filter(
        OutsourceOrder.sales_item_id == si.id,
        OutsourceOrder.status != "已退回",
    ).all()
    # 铁律：下游有单据，上游不能退回——先到委外订单页退回委外单
    if os_orders:
        nos_list = sorted({o.outsource_no for o in os_orders})
        raise HTTPException(400, f"该明细行已关联委外订单（{', '.join(nos_list)}），请先到「委外订单」页退回委外单后再操作")
    # 明细行回到未生产（仅撤销转外发，无委外单的情况）
    if si.production_status == "已通知外发":
        si.production_status = "未生产"
    db.commit()
    return {"message": "已退回（撤销转外发），销售明细行已解锁，可重新变更或转委外"}


@router.post("/sales-to-outsource/{item_id}/complete", tags=["委外管理"])
def complete_sales_to_outsource(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """人工确认委外完成（业务员判断数量足够）"""
    from app.models.sales import SalesOrderItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    si.outsource_done = 1
    db.commit()
    return {"message": "已标记委外完成"}


@router.post("/sales-to-outsource/{item_id}/uncomplete", tags=["委外管理"])
def uncomplete_sales_to_outsource(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消委外完成（业务员改主意，可继续追加委外）"""
    from app.models.sales import SalesOrderItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    si.outsource_done = 0
    db.commit()
    return {"message": "已取消委外完成，可继续追加委外"}


@router.get("/sales-to-outsource/{item_id}", tags=["委外管理"])
def get_sales_to_outsource(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细行转委外：产品行 + 工序支线（工艺路线工序 + 各工序BOM材料 + 已生成委外单）"""
    from app.models.sales import SalesOrderItem
    from app.models.foundation import ProductProcess, BomItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    if si.production_status in ("已停售", "已入库"):
        raise HTTPException(400, f"该明细行状态为「{si.production_status}」，不能转委外")
    os_orders = db.query(OutsourceOrder).filter(
        OutsourceOrder.sales_item_id == si.id,
        OutsourceOrder.status != "已退回",
    ).all()
    outsourced_qty = sum((o.quantity or 0) for o in os_orders)
    prod = si.product
    # 工艺路线工序
    procs = db.query(ProductProcess).filter(
        ProductProcess.product_id == si.product_id,
    ).order_by(ProductProcess.seq.asc(), ProductProcess.id.asc()).all()
    # BOM 材料（该产品全部启用材料，不按工序挂接；每道工序认领时人工选择）
    bom_items = db.query(BomItem).filter(
        BomItem.product_id == si.product_id,
        BomItem.is_active == 1,
    ).order_by(BomItem.sort_order.asc(), BomItem.id.asc()).all()
    all_bom_materials = []
    for b in bom_items:
        mat = b.material
        all_bom_materials.append({
            "material_id": b.material_id,
            "code": mat.code if mat else "",
            "name": mat.name if mat else "",
            "spec": mat.spec or "" if mat else "",
            "unit": mat.unit or "" if mat else "",
            "quantity": b.quantity or 1,
            "loss_rate": b.loss_rate or 0,
        })
    # 已生成委外单（按工序分组）
    gen_by_process = {}
    for o in os_orders:
        if o.process_id:
            gen_by_process.setdefault(o.process_id, []).append(o)
    processes = []
    for pp in procs:
        p = db.query(Process).filter(Process.id == pp.process_id).first()
        sup = db.query(Supplier).filter(Supplier.id == pp.default_supplier_id).first() if pp.default_supplier_id else None
        generated = []
        for o in gen_by_process.get(pp.process_id, []):
            o_sup = db.query(Supplier).filter(Supplier.id == o.outsourcer_id).first() if o.outsourcer_id else None
            generated.append({
                "outsource_no": o.outsource_no,
                "quantity": o.quantity or 0,
                "outsourcer_id": o.outsourcer_id,
                "outsourcer_name": o_sup.name if o_sup else "",
                "unit_price": o.unit_price or 0,
                "amount": o.amount or 0,
                "supply_type": o.supply_type or "己方提供",
                "status": o.status,
                "materials": _os_materials(db, o.id),
            })
        processes.append({
            "process_id": pp.process_id,
            "process_name": p.name if p else "",
            "process_code": p.code if p else "",
            "seq": pp.seq or 0,
            "default_unit_price": pp.default_unit_price or 0,
            "default_supplier_id": pp.default_supplier_id,
            "default_supplier_name": sup.name if sup else "",
            "bom_materials": all_bom_materials,
            "generated": generated,
        })
    return {
        "id": si.order_id, "order_no": si.order.order_no,
        "customer_name": si.order.customer.name_cn if si.order.customer else "",
        "batch_no": si.batch_no or "",
        "sales_item_id": si.id,
        "product_id": si.product_id,
        "product_code": prod.code if prod else "",
        "product_name": prod.name_cn if prod else "",
        "spec": (prod.spec or "") if prod else "",
        "unit": prod.unit if prod else "",
        "need_qty": si.quantity or 0,
        "outsourced_qty": round(outsourced_qty, 2),
        "production_status": si.production_status or "未生产",
        "processes": processes,
        "common_materials": [],
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

    # 损耗: 允许委外到 销售数量×(1+损耗%)，默认 10%
    loss_pct = float(data.get("loss_pct", 10) or 10)
    if loss_pct < 0 or loss_pct > 50:
        raise HTTPException(400, "损耗率须在 0~50% 之间")

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
        if qty + already > (si.quantity or 0) * (1 + loss_pct / 100):
            raise HTTPException(400, f"{si.product.name_cn if si.product else ''} 委外数量超过销售数量×（1+损耗{loss_pct:.0f}%）（还可转 {round((si.quantity or 0) * (1 + loss_pct / 100) - already, 2)}）")
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


@router.post("/orders/from-sales-process", tags=["委外管理"])
def create_outsource_from_sales_process(
    data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """销售订单转委外（按工序拆单）：每道工序生成一张委外订单 + 材料认领自动出库
    data: { sales_order_id: int, sales_item_id: int, loss_pct?: float,
            rows: [{process_id, outsourcer_id, unit_price, quantity, supply_type,
                    materials: [{material_id, batch_no, quantity, supply_type?}]}] }
    材料级供料方式（工序默认+材料级可覆盖）：materials[].supply_type 缺省=工序级 rows[].supply_type，
    再缺省='己方提供'；「包工包料」材料不校验数量、不写 os_order_material、不出库（由加工厂提供）。
    每张委外单：product_id=产品、quantity=委外数量、process_id=工序、outsourcer_id=加工商、
    unit_price=加工单价、amount=单价×数量、sales_order_id/sales_item_id、status=待确认；
    认领材料写入 os_order_material 并自动生成原料出库（扣库存 + StockTransaction 流水）。"""
    from app.models.foundation import ProductProcess, BomItem
    sales_order_id = data.get("sales_order_id")
    sales_item_id = data.get("sales_item_id")
    rows = data.get("rows") or []
    if not sales_order_id or not sales_item_id or not rows:
        raise HTTPException(400, "参数不完整")
    order = db.query(SalesOrder).filter(SalesOrder.id == sales_order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status not in ("已审", "生产中", "部分发货"):
        raise HTTPException(400, f"该销售单状态「{order.status}」，不能转委外")
    si = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == sales_item_id,
        SalesOrderItem.order_id == sales_order_id,
    ).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    if si.production_status in ("已入库", "已停售"):
        raise HTTPException(400, f"「{si.product.name_cn if si.product else ''}」当前状态为「{si.production_status}」，不能转委外（请先退回相关单据）")

    # 损耗: 允许委外到 销售数量×(1+损耗%)，默认 10%
    loss_pct = float(data.get("loss_pct", 10) or 10)
    if loss_pct < 0 or loss_pct > 50:
        raise HTTPException(400, "损耗率须在 0~50% 之间")

    # 该产品工艺路线工序集合 + BOM 材料集合（认领校验用）
    pp_rows = db.query(ProductProcess).filter(ProductProcess.product_id == si.product_id).all()
    valid_procs = {p.process_id for p in pp_rows}
    bom_mats = {
        b.material_id: (b.quantity or 1) for b in db.query(BomItem).filter(
            BomItem.product_id == si.product_id, BomItem.is_active == 1).all()
    }
    # 已有非退回委外单（分批追加校验按工序维度：同工序已生成量 + 本次 ≤ 销售数量×(1+损耗)）
    os_orders = db.query(OutsourceOrder).filter(
        OutsourceOrder.sales_item_id == si.id,
        OutsourceOrder.status != "已退回",
    ).all()
    operator = current_user.display_name or current_user.username
    created = []

    try:
        for r in rows:
            process_id = r.get("process_id")
            qty = float(r.get("quantity") or 0)
            if qty <= 0:
                raise HTTPException(400, "委外数量必须大于0")
            if process_id not in valid_procs:
                raise HTTPException(400, "工序不在该产品的工艺路线内，不能生成委外订单")
            supply_type = r.get("supply_type")
            if supply_type not in ("己方提供", "包工包料"):
                raise HTTPException(400, "供料方式必须为「己方提供」或「包工包料」")
            outsourcer_id = r.get("outsourcer_id")
            unit_price = float(r.get("unit_price") or 0)
            # 材料认领汇总（同材料+批次合并；按材料级供料方式分流：「包工包料」跳过）
            claims = {}
            material_supply = {}  # material_id -> 材料级供料方式（己方提供/包工包料）
            for m in r.get("materials") or []:
                mid = m.get("material_id")
                if mid not in bom_mats:
                    raise HTTPException(400, f"材料(id={mid})不在该产品BOM内，不能认领")
                m_supply = (str(m.get("supply_type") or "").strip()) or supply_type or "己方提供"
                if m_supply not in ("己方提供", "包工包料"):
                    raise HTTPException(400, "材料供料方式必须为「己方提供」或「包工包料」")
                if mid in material_supply and material_supply[mid] != m_supply:
                    raise HTTPException(400, f"材料(id={mid})供料方式冲突，同一种材料只能选一种供料方式")
                material_supply[mid] = m_supply
                if m_supply == "包工包料":
                    # 包工包料：由加工厂提供，我方不备料——不校验数量、不写认领记录、不出库
                    continue
                batch = str(m.get("batch_no") or "").strip()
                mqty = float(m.get("quantity") or 0)
                if mqty <= 0:
                    raise HTTPException(400, "认领材料数量必须大于0")
                if not batch:
                    raise HTTPException(400, "认领材料未选择批次")
                key = (mid, batch)
                claims[key] = round(claims.get(key, 0) + mqty, 2)
            # 材料级供料方式硬校验：「己方提供」材料认领数量须 ≥ 委外数量×BOM用量×(1+损耗%)，
            # 不足 400（提示材料名+需N已领M）；全部材料都标包工包料时无己方提供材料，不强制认领（等价于包工包料）
            if claims:
                proc_name = "工序"
                proc_row = db.query(Process).filter(Process.id == process_id).first()
                if proc_row:
                    proc_name = proc_row.name
                for (mid, batch), mqty in claims.items():
                    need = round(qty * (1 + loss_pct / 100) * bom_mats.get(mid, 1), 2)
                    if mqty < need:
                        mat_row = db.query(Material).filter(Material.id == mid).first()
                        mat_name = mat_row.name if mat_row else str(mid)
                        raise HTTPException(400, f"工序「{proc_name}」材料「{mat_name}」己方提供，认领数量不足（需 {need}，已领 {mqty}）")
            # 批次库存预检
            stock_invs = {}
            for (mid, batch), mqty in claims.items():
                invs = db.query(WarehouseInventory).filter(
                    WarehouseInventory.material_id == mid,
                    WarehouseInventory.batch_no == batch,
                ).order_by(WarehouseInventory.id).all()
                stock = round(sum((i.quantity or 0) for i in invs), 2)
                if stock <= 0:
                    raise HTTPException(400, f"材料批次库存不足（当前 0）")
                if mqty > stock:
                    raise HTTPException(400, f"材料批次库存不足（当前 {stock}，需认领 {mqty}）")
                stock_invs[(mid, batch)] = invs
            # 数量上限校验（按工序分批追加：同工序累计不超销售数量×（1+损耗））
            proc_already = round(sum((o.quantity or 0) for o in os_orders if o.process_id == process_id), 2)
            if qty + proc_already > (si.quantity or 0) * (1 + loss_pct / 100):
                raise HTTPException(400, f"工序(第{process_id}道)委外数量超过销售数量×（1+损耗{loss_pct:.0f}%）（还可转 {round((si.quantity or 0) * (1 + loss_pct / 100) - proc_already, 2)}）")
            # 生成委外订单（一工序一单）
            os_order = OutsourceOrder(
                outsource_no=generate_doc_no(db, "WO", OutsourceOrder, "outsource_no"),
                sales_order_id=sales_order_id,
                sales_item_id=si.id,
                product_id=si.product_id,
                process_id=process_id,
                quantity=qty,
                outsourcer_id=outsourcer_id,
                unit_price=unit_price,
                amount=round(qty * unit_price, 2),
                supply_type=supply_type,
                status="待确认",
                created_by=operator,
            )
            db.add(os_order)
            db.flush()
            # 材料认领 → 原料出库（FIFO 扣减批次库存 + 流水）
            for (mid, batch), mqty in claims.items():
                invs = stock_invs[(mid, batch)]
                remaining = mqty
                total_cost = 0.0
                for inv in invs:
                    if remaining <= 0:
                        break
                    take = round(min(inv.quantity or 0, remaining), 2)
                    if take <= 0:
                        continue
                    unit_cost = inv.unit_cost or 0
                    old_qty = inv.quantity
                    inv.quantity = round(old_qty - take, 2)
                    inv.total_cost = round(inv.quantity * unit_cost, 2)
                    total_cost += round(take * unit_cost, 2)
                    db.add(StockTransaction(
                        trans_type="material_out",
                        warehouse_id=inv.warehouse_id,
                        material_id=mid,
                        batch_no=batch,
                        quantity=-take,
                        unit_cost=unit_cost,
                        total_amount=round(-take * unit_cost, 2),
                        before_qty=old_qty,
                        after_qty=inv.quantity,
                        before_cost=round(old_qty * unit_cost, 2),
                        after_cost=round(inv.quantity * unit_cost, 2),
                        source_doc_type="原料出库",
                        source_doc_no=os_order.outsource_no,
                        trans_no=generate_doc_no(db, "ST"),
                        operator=operator,
                    ))
                    remaining = round(remaining - take, 2)
                # 认领明细（同材料同批次合并一行，成本取该批次加权成本）
                db.add(OutsourceMaterial(
                    outsource_order_id=os_order.id,
                    material_id=mid,
                    batch_no=batch,
                    quantity=mqty,
                    unit_cost=round(total_cost / mqty, 6) if mqty else 0,
                    supply_type="己方提供",
                ))
            if si.production_status in (None, "", "未生产"):
                si.production_status = "已通知外发"
            created.append({
                "outsource_no": os_order.outsource_no,
                "process_id": process_id,
                "product_name": si.product.name_cn if si.product else "",
            })
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": f"已生成 {len(created)} 张委外订单（按工序拆单，待确认）", "orders": created}

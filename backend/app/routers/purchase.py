"""采购模块 API 路由 — 订单→入库(批次)→发票→应付→付款"""

from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
from sqlalchemy import func as sa_func
from app.database import get_db
from app.models.auth import User
from app.models.foundation import Material, Supplier, Warehouse, Currency, Product
from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem,
    PurchaseReceipt, PurchaseReceiptItem,
    PurchaseInvoice,
    PurchaseRequisition,
    AccountsPayable, Payment, PaymentAllocation,
)
from app.models.inventory import WarehouseInventory, StockTransaction
from app.schemas.purchase import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderOut,
    PurchaseOrderItemCreate, PurchaseOrderItemOut,
    PurchaseReceiptCreate, PurchaseReceiptOut,
    PurchaseReceiptItemCreate, PurchaseReceiptItemOut,
    PurchaseInvoiceCreate, PurchaseInvoiceOut,
    AccountsPayableOut,
    PaymentCreate, PaymentOut, PaymentAllocationCreate,
)
from app.utils.auth import get_current_user, require_permission
from app.utils.batch_no import generate_batch_no, generate_doc_no

router = APIRouter()


# ==================== 采购需求（生产推式 → 采购转单） ====================

@router.get("/requisitions", tags=["采购管理"])
def list_requisitions(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    status: str = Query("", description="状态筛选: 待处理/已转单/已关闭"),
    keyword: str = Query("", description="需求单号/产品搜索"),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(PurchaseRequisition)
    if status:
        query = query.filter(PurchaseRequisition.status == status)
    if keyword:
        from app.models.foundation import Product
        query = query.outerjoin(Product).filter(
            PurchaseRequisition.requisition_no.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(PurchaseRequisition.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {
            "id": r.id, "requisition_no": r.requisition_no,
            "production_order_id": r.production_order_id,
            "production_order_no": r.production.order_no if r.production else "",
            "product_id": r.product_id,
            "product_name": r.product.name_cn if r.product else "",
            "product_code": r.product.code if r.product else "",
            "quantity": r.quantity,
            "status": r.status,
            "remark": r.remark or "",
            "created_by": r.created_by,
            "created_at": str(r.created_at)[:19] if r.created_at else "",
        } for r in items
    ]}


@router.get("/requisitions/{req_id}", tags=["采购管理"])
def get_requisition(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    r = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
    if not r:
        raise HTTPException(404, "采购需求不存在")
    return {
        "id": r.id, "requisition_no": r.requisition_no,
        "production_order_id": r.production_order_id,
        "production_order_no": r.production.order_no if r.production else "",
        "product_id": r.product_id,
        "product_name": r.product.name_cn if r.product else "",
        "product_code": r.product.code if r.product else "",
        "product_unit": r.product.unit if r.product else "",
        "quantity": r.quantity,
        "status": r.status,
        "remark": r.remark or "",
        "created_by": r.created_by,
        "created_at": str(r.created_at)[:19] if r.created_at else "",
    }


@router.post("/requisitions/{req_id}/close", tags=["采购管理"])
def close_requisition(req_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """关闭采购需求（仅待处理）→ 生产订单回到待采购，可重新推"""
    r = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
    if not r:
        raise HTTPException(404, "采购需求不存在")
    if r.status != "待处理":
        raise HTTPException(400, f"仅待处理状态的采购需求可关闭（当前：{r.status}）")
    r.status = "已关闭"
    # 解除生产订单关联，允许重新推需求
    from app.models.production import ProductionOrder
    mo = db.query(ProductionOrder).filter(ProductionOrder.id == r.production_order_id).first()
    if mo:
        mo.requisition_id = None
        if mo.production_type == "外购":
            mo.status = "待采购"
    db.commit()
    return {"message": f"采购需求 {r.requisition_no} 已关闭"}


@router.post("/requisitions/{req_id}/to-purchase", tags=["采购管理"])
def requisition_to_purchase(req_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """采购需求 → 生成采购订单（采购人员维护供应商/单价/税率，数量可改）"""
    r = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
    if not r:
        raise HTTPException(404, "采购需求不存在")
    if r.status != "待处理":
        raise HTTPException(400, f"仅待处理状态的采购需求可转采购订单（当前：{r.status}）")

    supplier_id = data.get("supplier_id")
    if not supplier_id:
        raise HTTPException(400, "请选择供应商")

    quantity = float(data.get("quantity", r.quantity) or r.quantity)
    unit_price = float(data.get("unit_price", 0) or 0)
    tax_rate = float(data.get("tax_rate", 13) or 13)
    total_amount = unit_price * quantity
    total_amount_excl_tax = round(total_amount / (1 + tax_rate / 100), 2)
    tax_amount = round(total_amount - total_amount_excl_tax, 2)

    from app.utils.batch_no import generate_doc_no
    po = PurchaseOrder(
        order_no=generate_doc_no(db, "PO", PurchaseOrder, "order_no"),
        supplier_id=supplier_id,
        order_date=date.today(),
        expected_date=_parse_date(data.get("expected_date")) or (r.production.due_date if r.production else None),
        status="待审核",
        total_amount=total_amount,
        total_amount_excl_tax=total_amount_excl_tax,
        tax_amount=tax_amount,
        tax_rate=tax_rate,
        remark=f"由采购需求 {r.requisition_no} 转单生成",
        created_by=current_user.display_name or current_user.username,
    )
    db.add(po)
    db.flush()

    poi = PurchaseOrderItem(
        order_id=po.id,
        product_id=r.product_id,
        quantity=quantity,
        unit_price=unit_price,
        unit_price_local=unit_price * (po.exchange_rate or 1),
        total_amount=total_amount,
        total_amount_excl_tax=total_amount_excl_tax,
        tax_rate=tax_rate,
        requisition_id=r.id,
    )
    db.add(poi)

    # 更新需求状态 + 生产订单
    r.status = "已转单"
    from app.models.production import ProductionOrder
    mo = db.query(ProductionOrder).filter(ProductionOrder.id == r.production_order_id).first()
    if mo:
        mo.status = "采购中"
    db.commit()

    return {
        "message": f"已生成采购订单 {po.order_no}",
        "purchase_order_id": po.id,
        "purchase_order_no": po.order_no,
    }


# ==================== 采购订单 ====================

@router.get("/orders", response_model=dict, tags=["采购管理"])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
    status: str = Query("", description="状态筛选"),
    keyword: str = Query("", description="订单号/供应商搜索"),
    date_from: str = Query(""), date_to: str = Query(""),
    amount_min: float = Query(None), amount_max: float = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """采购订单列表"""
    query = db.query(PurchaseOrder)
    if status:
        query = query.filter(PurchaseOrder.status == status)
    if keyword:
        query = query.join(Supplier).filter(
            PurchaseOrder.order_no.like(f"%{keyword}%")
            | Supplier.name.like(f"%{keyword}%")
        )
    if date_from:
        query = query.filter(PurchaseOrder.order_date >= date_from)
    if date_to:
        query = query.filter(PurchaseOrder.order_date <= date_to)
    if amount_min is not None:
        query = query.filter(PurchaseOrder.total_amount >= amount_min)
    if amount_max is not None:
        query = query.filter(PurchaseOrder.total_amount <= amount_max)
    total = query.count()
    items = query.order_by(PurchaseOrder.id.desc()).offset((page-1)*page_size).limit(page_size).all()

    # 批量聚合计算
    order_ids = [o.id for o in items]
    inv_agg = {}
    pay_agg = {}
    if order_ids:
        try:
            inv_rows = db.query(PurchaseInvoice.order_id, sa_func.coalesce(sa_func.sum(PurchaseInvoice.amount + sa_func.coalesce(PurchaseInvoice.tax_amount, 0)), 0)).filter(
                PurchaseInvoice.order_id.in_(order_ids)).group_by(PurchaseInvoice.order_id).all()
            inv_agg = {r[0]: float(r[1]) for r in inv_rows}
        except:
            inv_agg = {}
        try:
            # 通过应收→发票→订单，汇总已付款
            ap_list = db.query(AccountsPayable).filter(
                AccountsPayable.source_type == "purchase_invoice").all()
            ap_order_map = {}
            for ap in ap_list:
                inv = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == ap.source_id).first()
                if inv and inv.order_id in order_ids:
                    ap_order_map[ap.id] = inv.order_id
            if ap_order_map:
                pay_rows = db.query(PaymentAllocation.ap_account_id, sa_func.coalesce(sa_func.sum(PaymentAllocation.allocated_amount), 0)).filter(
                    PaymentAllocation.ap_account_id.in_(list(ap_order_map.keys()))
                ).group_by(PaymentAllocation.ap_account_id).all()
                for ap_id, amt in pay_rows:
                    oid = ap_order_map.get(ap_id)
                    if oid:
                        pay_agg[oid] = pay_agg.get(oid, 0) + float(amt)
        except:
            pay_agg = {}

    result = []
    for o in items:
        # 是否转采购生成（明细关联销售单）
        from_sales = any(item.sales_item_id for item in o.items)
        # 关联销售订单号（转采购的单一一对应；备货为空）
        sales_nos = sorted({item.sales_item.order.order_no for item in o.items if item.sales_item and item.sales_item.order})
        # 已入库金额
        received_amount = sum(
            (item.received_qty or 0) * (item.unit_price_local or item.unit_price or 0)
            for item in o.items
        )
        result.append({
            "id": o.id, "order_no": o.order_no, "order_date": str(o.order_date),
            "supplier_name": o.supplier.name if o.supplier else "",
            "supplier_id": o.supplier_id,
            "total_amount": o.total_amount, "total_amount_fc": o.total_amount_fc,
            "total_amount_excl_tax": o.total_amount_excl_tax,
            "tax_rate": o.tax_rate, "tax_amount": o.tax_amount,
            "currency_code": db.query(Currency).filter(Currency.id == o.currency_id).first().code if o.currency_id else "CNY",
            "status": o.status, "expected_date": str(o.expected_date) if o.expected_date else "",
            "item_count": len(o.items),
            "created_at": str(o.created_at) if o.created_at else "",
            "received_amount": round(received_amount, 2),
            "unreceived_amount": round((o.total_amount or 0) - received_amount, 2),
            "invoiced_amount": round(inv_agg.get(o.id, 0), 2),
            "uninvoiced_amount": round((o.total_amount or 0) - inv_agg.get(o.id, 0), 2),
            "paid_amount": round(pay_agg.get(o.id, 0), 2),
            "unpaid_amount": round(inv_agg.get(o.id, 0) - pay_agg.get(o.id, 0), 2),
            "from_sales": from_sales,
            "sales_order_no": ", ".join(sales_nos),
            "created_by": o.created_by or "",
        })

        # 状态只保留采购环节状态（待审核/已审核/已关闭），入库/开票/付款进度在明细和财务模块看
        computed_status = o.status
        if o.status not in ("待审核", "已审核", "已关闭"):
            computed_status = "已审核"

        result[-1]["status"] = computed_status

    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/orders/{order_id}", tags=["采购管理"])
def get_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    # 手动构建响应
    result = {
        "id": order.id, "order_no": order.order_no, "supplier_id": order.supplier_id,
        "supplier_name": order.supplier.name if order.supplier else "",
        "order_date": str(order.order_date), "expected_date": str(order.expected_date) if order.expected_date else None,
        "status": order.status, "currency_id": order.currency_id, "exchange_rate": order.exchange_rate,
        "total_amount": order.total_amount, "total_amount_fc": order.total_amount_fc,
        "total_amount_excl_tax": order.total_amount_excl_tax,
        "tax_rate": order.tax_rate, "tax_amount": order.tax_amount,
        "payment_terms": order.payment_terms, "remark": order.remark or "",
        "created_by": order.created_by, "created_at": str(order.created_at),
        "items": [
            {
                "id": item.id, "material_id": item.material_id,
                "material_code": item.material.code if item.material else (item.product.code if item.product else ""),
                "material_name": item.material.name if item.material else (item.product.name_cn if item.product else ""),
                "product_id": item.product_id,
                "product_code": item.product.code if item.product else "",
                "product_name": item.product.name_cn if item.product else "",
                "unit": item.material.unit if item.material else (item.product.unit if item.product else ""),
                "receive_type": item.receive_type or "",
                "sales_item_id": item.sales_item_id,
                "sales_order_no": item.sales_item.order.order_no if item.sales_item else "",
                "sales_batch_no": item.sales_item.batch_no if item.sales_item else "",
                "requisition_id": item.requisition_id,
                "quantity": item.quantity, "unit_price": item.unit_price,
                "total_amount": item.total_amount, "received_qty": item.received_qty or 0,
                "tax_rate": item.tax_rate or 0, "total_amount_excl_tax": item.total_amount_excl_tax or 0,
                "tax_amount": round((item.total_amount or 0) - (item.total_amount_excl_tax or 0), 2),
            } for item in order.items
        ],
    }
    return result


@router.delete("/orders/{order_id}", tags=["采购管理"])
def delete_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除采购订单（仅待审核状态允许，且无下游入库单/发票）"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "仅待审核状态的订单允许删除")
    receipts = db.query(PurchaseReceipt).filter(PurchaseReceipt.order_id == order_id).count()
    invoices = db.query(PurchaseInvoice).filter(PurchaseInvoice.order_id == order_id).count()
    if receipts > 0:
        raise HTTPException(400, "该订单已有关联入库单，无法删除")
    if invoices > 0:
        raise HTTPException(400, "该订单已有关联发票，无法删除")
    # 删除后：来源 PR 回到待处理，生产订单回到待采购
    from app.models.production import ProductionOrder
    from app.models.purchase import PurchaseRequisition
    # 找到该订单明细关联的采购需求
    po_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == order_id).all()
    linked_reqs = []
    for it in po_items:
        if it.requisition_id and it.requisition_id not in linked_reqs:
            linked_reqs.append(it.requisition_id)
    # 采购需求恢复待处理 + 生产订单回到待采购
    for req_id in linked_reqs:
        req = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
        if req and req.status == "已转单":
            req.status = "待处理"
        if req:
            mo = db.query(ProductionOrder).filter(ProductionOrder.id == req.production_order_id).first()
            if mo and mo.production_type == "外购":
                mo.status = "待采购"
    # 铁律：删除后检查该销售明细行是否还有其他采购单——没有了才解锁回未生产
    item_ids = {i.sales_item_id for i in order.items if i.sales_item_id}
    db.delete(order)
    db.commit()
    from app.models.sales import SalesOrderItem
    for sid in item_ids:
        remain = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
            PurchaseOrderItem.sales_item_id == sid,
            PurchaseOrder.status != "已关闭",
        ).count()
        if remain == 0:
            si = db.query(SalesOrderItem).filter(SalesOrderItem.id == sid).first()
            if si and si.production_status == "已通知入库":
                si.production_status = "未生产"
    db.commit()
    return {"message": "采购订单已删除"}


@router.put("/orders/{order_id}", tags=["采购管理"])
def update_order(order_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """修改采购订单（仅待审核状态允许）"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "仅待审核状态的订单允许修改")
    # 转采购生成的订单禁止直接编辑（保证销售单联动一致，只能退回）
    if any(item.sales_item_id for item in order.items):
        raise HTTPException(400, "该采购订单由「销售订单转采购」生成，不能直接编辑；请退回该订单后重新转采购")
    for field in ["supplier_id", "order_date", "payment_terms", "tax_rate", "remark"]:
        if field in data and data[field] is not None:
            if field == "order_date":
                setattr(order, field, _parse_date(data[field]))
            else:
                setattr(order, field, data[field])
    if "items" in data and isinstance(data["items"], list) and len(data["items"]) > 0:
        old_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == order_id).all()
        for item in old_items:
            db.delete(item)
        db.flush()
        total_fc = 0
        for item_data in data["items"]:
            unit_price_fc = float(item_data.get("unit_price", 0) or 0)
            qty = float(item_data.get("quantity", 1) or 1)
            if qty <= 0:
                raise HTTPException(400, "采购数量必须大于0")
            line_total = qty * unit_price_fc
            mid = item_data.get("material_id")
            pid = item_data.get("product_id")
            if not mid and not pid:
                raise HTTPException(400, "采购明细必须选择材料或产品")
            new_item = PurchaseOrderItem(
                order_id=order.id, material_id=mid or None, product_id=pid or None,
                sales_item_id=item_data.get("sales_item_id") or None,
                requisition_id=item_data.get("requisition_id") or None,
                quantity=qty, unit_price=unit_price_fc,
                total_amount=line_total,
                tax_rate=order.tax_rate or 13,
                total_amount_excl_tax=round(line_total / (1 + (order.tax_rate or 13) / 100), 6),
            )
            db.add(new_item)
            total_fc += line_total
        # 重算订单级金额
        tax_rate = (order.tax_rate or 13) / 100
        order.total_amount_fc = total_fc
        order.total_amount = total_fc
        order.total_amount_excl_tax = round(total_fc / (1 + tax_rate), 6)
        order.tax_amount = round(total_fc - order.total_amount_excl_tax, 6)
    db.commit()
    return {"message": "采购订单已更新"}


@router.post("/orders", tags=["采购管理"])
def create_order(
    data: PurchaseOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建采购订单"""
    from app.utils.batch_no import generate_doc_no
    from app.models.purchase import PurchaseOrder
    order_no = generate_doc_no(db, "PO", PurchaseOrder, "order_no")

    order = PurchaseOrder(
        order_no=order_no,
        supplier_id=data.supplier_id,
        order_date=data.order_date or date.today(),
        expected_date=data.expected_date,
        currency_id=data.currency_id or 1,
        exchange_rate=data.exchange_rate or 1,
        payment_terms=data.payment_terms,
        tax_rate=data.tax_rate,
        remark=data.remark,
        created_by=current_user.display_name or current_user.username,
    )
    db.add(order)
    db.flush()

    total_fc = 0
    for item_data in data.items:
        if not item_data.material_id and not item_data.product_id:
            raise HTTPException(400, "采购明细必须选择材料或产品")
        if item_data.quantity <= 0:
            raise HTTPException(400, "采购数量必须大于0")
        unit_price_fc = item_data.unit_price
        line_total_fc = item_data.quantity * unit_price_fc
        item = PurchaseOrderItem(
            order_id=order.id,
            material_id=item_data.material_id,
            product_id=item_data.product_id,
            sales_item_id=item_data.sales_item_id,
            quantity=item_data.quantity,
            unit_price=unit_price_fc,
            unit_price_local=unit_price_fc * (data.exchange_rate or 1),
            total_amount=line_total_fc,
            tax_rate=data.tax_rate,
            total_amount_excl_tax=round(line_total_fc / (1 + data.tax_rate / 100), 6),
            remark=item_data.remark,
        )
        db.add(item)
        total_fc += line_total_fc

    tax_rate = data.tax_rate / 100
    order.total_amount_fc = total_fc
    order.total_amount = total_fc * (data.exchange_rate or 1)
    order.total_amount_excl_tax = round(order.total_amount / (1 + tax_rate), 6)
    order.tax_amount = round(order.total_amount - order.total_amount_excl_tax, 6)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "order_no": order.order_no, "message": "采购订单创建成功"}


# ==================== 销售订单转采购（按供应商拆单） ====================

def _so_row_requirements(db: Session, si):
    """销售明细行的采购需求清单（按 BOM 展开，无 BOM 则产品本身）
    返回: [{'material_id'|'product_id', 'need_qty'}]"""
    from app.models.foundation import BomItem
    bom_items = db.query(BomItem).filter(
        BomItem.product_id == si.product_id, BomItem.is_active == 1).all()
    if bom_items:
        return [
            {
                "material_id": b.material_id, "product_id": None,
                "need_qty": round((si.quantity or 0) * (b.quantity or 1) * (1 + (b.loss_rate or 0) / 100), 2),
            } for b in bom_items
        ]
    return [{"material_id": None, "product_id": si.product_id, "need_qty": si.quantity or 0}]


def _so_purchase_status(db: Session, order):
    """计算销售单采购状态: completed(绿)/partial(橙)/none(灰)
    判定口径: 已采购数量(非关闭采购单) >= BOM 比例需求量 => 该行采购完成"""
    from app.models.purchase import PurchaseOrderItem
    row_statuses = []
    for si in order.items:
        if si.production_status == "已停售":
            continue
        pois = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
            PurchaseOrderItem.sales_item_id == si.id,
            PurchaseOrder.status != "已关闭",
        ).all()
        reqs = _so_row_requirements(db, si)
        if not reqs:
            continue
        row_done = True
        row_any = False
        for req in reqs:
            if req["material_id"]:
                purchased = sum((p.quantity or 0) for p in pois if p.material_id == req["material_id"])
            else:
                purchased = sum((p.quantity or 0) for p in pois if p.product_id == req["product_id"])
            if purchased <= 0:
                row_done = False
            elif purchased < req["need_qty"]:
                row_done = False
            if purchased > 0:
                row_any = True
        if not row_any:
            row_statuses.append("none")
        elif row_done:
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


@router.get("/sales-to-purchase", tags=["采购管理"])
def list_sales_to_purchase(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
    keyword: str = Query(""), date_from: str = Query(""), date_to: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """销售订单转采购：已「转入库」的销售明细行列表（按行显示产品+批次号）+ 采购状态"""
    from app.models.sales import SalesOrder, SalesOrderItem
    from app.models.foundation import Customer
    from app.models.purchase import PurchaseOrderItem
    # 只显示在销售订单那边点了「转入库」的明细行
    query = db.query(SalesOrderItem).join(SalesOrder, SalesOrder.id == SalesOrderItem.order_id).filter(
        SalesOrderItem.production_status.in_(["已通知入库", "已通知外发"]),
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
        """该明细行采购状态（人工判定完成）:
        none=未采购 / partial=部分采购(还可追加) / transferred=已转采购订单(达上限不可追加,未手动完成) / completed=采购完成(手动完成)
        上限判定: 已采购 >= 需求量×(1+损耗10%) 视为达上限
        完成判定: si.purchase_done=1 人工完成"""
        if si.purchase_done:
            return "completed"
        pois = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
            PurchaseOrderItem.sales_item_id == si.id,
            PurchaseOrder.status != "已关闭",
        ).all()
        if not pois:
            return "none"
        # 该行各材料: 已采购量 vs 需求量（含损耗上限）
        statuses = []
        for req in _so_row_requirements(db, si):
            if req["material_id"]:
                purchased = sum((p.quantity or 0) for p in pois if p.material_id == req["material_id"])
            else:
                purchased = sum((p.quantity or 0) for p in pois if p.product_id == si.product_id)
            statuses.append("done" if purchased >= req["need_qty"] * 1.1 else ("partial" if purchased > 0 else "none"))
        # 全部材料达上限
        if all(s == "done" for s in statuses):
            return "transferred"
        if all(s == "none" for s in statuses):
            return "none"
        return "partial"

    result = []
    for si in items:
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
            "source": "转直采" if si.production_status == "已通知入库" else "转外发",
            "purchase_status": row_status(si),
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.post("/sales-to-purchase/{item_id}/return", tags=["采购管理"])
def return_sales_to_purchase(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """退回销售明细行关联的采购订单（销售订单明细变更前必须先退采购单）
    待审核的直接删除；已审核的先取消审核再删除；有入库/发票的下游则拒绝"""
    from app.models.sales import SalesOrderItem
    from app.models.purchase import PurchaseOrderItem, PurchaseReceipt
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    pois = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
        PurchaseOrderItem.sales_item_id == si.id,
        PurchaseOrder.status != "已关闭",
    ).all()
    # 铁律：下游有单据，上游不能退回——先到采购订单页退回采购单
    if pois:
        nos_list = sorted({p.order.order_no for p in pois if p.order})
        raise HTTPException(400, f"该明细行已关联采购订单（{', '.join(nos_list)}），请先到「采购订单」页退回采购单后再操作")
    # 明细行回到未生产（仅撤销转入库，无采购单的情况）
    if si.production_status == "已通知入库":
        si.production_status = "未生产"
    db.commit()
    return {"message": "已退回（撤销转入库），销售明细行已解锁，可重新变更或转采购"}


@router.post("/sales-to-purchase/{item_id}/complete", tags=["采购管理"])
def complete_sales_to_purchase(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """人工确认采购完成（业务员判断数量足够）"""
    from app.models.sales import SalesOrderItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    si.purchase_done = 1
    db.commit()
    return {"message": "已标记采购完成"}


@router.post("/sales-to-purchase/{item_id}/uncomplete", tags=["采购管理"])
def uncomplete_sales_to_purchase(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消采购完成（业务员改主意，可继续追加采购）"""
    from app.models.sales import SalesOrderItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    si.purchase_done = 0
    db.commit()
    return {"message": "已取消采购完成，可继续追加采购"}


@router.get("/sales-to-purchase/{item_id}", tags=["采购管理"])
def get_sales_to_purchase(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细行采购需求：按 BOM 展开成物料清单（无 BOM 则直接采购产品本身）"""
    from app.models.sales import SalesOrderItem
    from app.models.foundation import BomItem
    from app.models.purchase import PurchaseOrderItem
    si = db.query(SalesOrderItem).filter(SalesOrderItem.id == item_id).first()
    if not si:
        raise HTTPException(404, "销售明细行不存在")
    if si.production_status not in ("已通知入库", "已通知外发"):
        raise HTTPException(400, f"该明细行状态为「{si.production_status}」，不能转采购（请先在销售订单明细行转直采/转外发）")

    pois = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
        PurchaseOrderItem.sales_item_id == si.id,
        PurchaseOrder.status != "已关闭",
    ).all()
    rows = []
    for req in _so_row_requirements(db, si):
        if req["material_id"]:
            mat = db.query(Material).filter(Material.id == req["material_id"]).first()
            purchased = sum((p.quantity or 0) for p in pois if p.material_id == mat.id)
            rows.append({
                "sales_item_id": si.id, "material_id": mat.id, "product_id": None,
                "code": mat.code if mat else "", "name": mat.name if mat else "",
                "spec": mat.spec or "" if mat else "", "unit": mat.unit if mat else "",
                "need_qty": req["need_qty"], "purchased_qty": round(purchased, 2),
                "ref_price": mat.purchase_price or 0 if mat else 0,
                "default_supplier_id": mat.default_supplier_id or None if mat else None,
            })
        else:
            prod = si.product
            purchased = sum((p.quantity or 0) for p in pois if p.product_id == si.product_id)
            rows.append({
                "sales_item_id": si.id, "material_id": None, "product_id": si.product_id,
                "code": prod.code if prod else "", "name": prod.name_cn if prod else "",
                "spec": (prod.spec or "") if prod else "", "unit": prod.unit if prod else "",
                    "need_qty": req["need_qty"], "purchased_qty": round(purchased, 2),
                    "ref_price": (prod.estimated_cost or 0) if prod else 0,
                    "default_supplier_id": None,
                })
    return {
        "id": si.order_id, "order_no": si.order.order_no,
        "customer_name": si.order.customer.name_cn if si.order.customer else "",
        "batch_no": si.batch_no or "",
        "product_code": si.product.code if si.product else "",
        "product_name": si.product.name_cn if si.product else "",
        "quantity": si.quantity or 0,
        "rows": rows,
    }


@router.post("/orders/from-sales", tags=["采购管理"])
def create_orders_from_sales(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售订单转采购：按供应商自动拆单，一次生成多张采购订单
    data: { sales_order_id: int, rows: [{sales_item_id, material_id?, product_id?, supplier_id, quantity, unit_price, tax_rate}] }
    """
    from app.models.sales import SalesOrder
    from app.models.foundation import Supplier
    from app.models.purchase import PurchaseOrderItem
    sales_order_id = data.get("sales_order_id")
    rows = data.get("rows") or []
    if not sales_order_id or not rows:
        raise HTTPException(400, "参数不完整")
    order = db.query(SalesOrder).filter(SalesOrder.id == sales_order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status not in ("已审", "生产中", "部分发货"):
        raise HTTPException(400, f"该销售单状态「{order.status}」，不能转采购")

    # 校验行 + 检查剩余量（硬校验：需求量以 BOM 比例为准，不接受前端传入的 need_qty）
    # 损耗: 允许采购到 需求量×(1+损耗%)，默认 10%
    loss_pct = float(data.get("loss_pct", 10) or 10)
    if loss_pct < 0 or loss_pct > 50:
        raise HTTPException(400, "损耗率须在 0~50% 之间")
    for r in rows:
        if not r.get("supplier_id"):
            raise HTTPException(400, "有明细行未选择供应商")
        if not r.get("quantity") or float(r.get("quantity")) <= 0:
            raise HTTPException(400, "采购数量必须大于0")
        if not r.get("unit_price") or float(r.get("unit_price")) <= 0:
            raise HTTPException(400, f"{r.get('name','')} 单价必须大于 0，请填写单价")
        if not r.get("material_id") and not r.get("product_id"):
            raise HTTPException(400, "明细行缺少物料/产品")
        # 找到对应销售明细行，按 BOM 计算真实需求量
        si = next((i for i in order.items if i.id == r["sales_item_id"]), None)
        if not si:
            raise HTTPException(400, "销售明细行不存在")
        if si.production_status not in ("已通知入库", "已通知外发"):
            raise HTTPException(400, f"该明细行状态为「{si.production_status}」，不能转采购（请先在销售订单明细行转直采/转外发）")
        req = next((x for x in _so_row_requirements(db, si)
                    if (x["material_id"] == r.get("material_id") and x["product_id"] == r.get("product_id"))), None)
        if not req:
            raise HTTPException(400, "该物料不在 BOM 比例内，不允许采购（请先维护 BOM）")
        # 剩余可采购量 = BOM 需求量 - 已采购
        pois = db.query(PurchaseOrderItem).join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.order_id).filter(
            PurchaseOrderItem.sales_item_id == r["sales_item_id"],
            PurchaseOrder.status != "已关闭",
        ).all()
        if r.get("material_id"):
            purchased = sum(p.quantity or 0 for p in pois if p.material_id == r["material_id"])
        else:
            purchased = sum(p.quantity or 0 for p in pois if p.product_id == r["product_id"])
        if float(r["quantity"]) + purchased > req["need_qty"] * (1 + loss_pct / 100):
            raise HTTPException(400, f"{r.get('name','')} 采购数量超过需求数量×（1+损耗{loss_pct:.0f}%）（还可采 {round(req['need_qty'] * (1 + loss_pct / 100) - purchased, 2)}）")

    # 按供应商分组
    groups = {}
    for r in rows:
        sid = r["supplier_id"]
        groups.setdefault(sid, []).append(r)

    created = []
    for sid, g_rows in groups.items():
        from app.utils.batch_no import generate_doc_no
        supplier = db.query(Supplier).filter(Supplier.id == sid).first()
        if not supplier:
            raise HTTPException(400, "供应商不存在")
        order_no = generate_doc_no(db, "PO", PurchaseOrder, "order_no")
        po = PurchaseOrder(
            order_no=order_no, supplier_id=sid,
            order_date=date.today(),
            currency_id=order.currency_id or 1,
            exchange_rate=order.exchange_rate or 1,
            tax_rate=g_rows[0].get("tax_rate") or 13,
            remark=f"销售订单 {order.order_no} 转采购",
            created_by=current_user.display_name or current_user.username,
        )
        db.add(po)
        db.flush()
        total_fc = 0
        for r in g_rows:
            qty = float(r["quantity"])
            unit_price = float(r.get("unit_price") or 0)
            line_total = qty * unit_price
            item = PurchaseOrderItem(
                order_id=po.id,
                material_id=r.get("material_id"),
                product_id=r.get("product_id"),
                sales_item_id=r["sales_item_id"],
                quantity=qty,
                unit_price=unit_price,
                unit_price_local=unit_price * (order.exchange_rate or 1),
                total_amount=line_total,
                tax_rate=po.tax_rate,
                total_amount_excl_tax=round(line_total / (1 + po.tax_rate / 100), 6),
                remark=f"销售订单 {order.order_no}",
            )
            db.add(item)
            total_fc += line_total
        po.total_amount_fc = total_fc
        po.total_amount = total_fc * (order.exchange_rate or 1)
        po.total_amount_excl_tax = round(po.total_amount / (1 + po.tax_rate / 100), 2)
        po.tax_amount = round(po.total_amount - po.total_amount_excl_tax, 2)
        created.append({"order_no": order_no, "supplier_name": supplier.name, "item_count": len(g_rows)})
    db.commit()
    return {"message": f"已生成 {len(created)} 张采购订单", "orders": created}



# ==================== 采购明细去向：转成品库入库 / 转原料库入库 ====================

@router.post("/orders/{order_id}/items/{item_id}/to-stock-in", tags=["采购管理"])
def to_stock_in(order_id: int, item_id: int, data: dict,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """采购明细「转成品库入库」— 生成/关联待入库单（成品入库模块收货）

    data: { stock_in_order_id: int | 0 }
      stock_in_order_id > 0: 关联到指定待入库单（人工选择）
      stock_in_order_id = 0: 新建备货待入库单
    """
    from app.models.inventory import StockInOrder
    from app.utils.batch_no import generate_doc_no
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "采购订单不存在")
    if order.status != "已审核":
        raise HTTPException(400, "仅已审核的采购订单可转成品库入库")
    item = db.query(PurchaseOrderItem).filter(
        PurchaseOrderItem.id == item_id, PurchaseOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "采购明细不存在")
    if not item.product_id:
        raise HTTPException(400, "该明细为材料采购，请使用「转原料库入库」")
    if item.receive_type:
        raise HTTPException(400, f"该明细已转「{item.receive_type}」，不能重复操作")
    target_id = int(data.get("stock_in_order_id") or 0)
    if target_id > 0:
        sin = db.query(StockInOrder).filter(StockInOrder.id == target_id).first()
        if not sin:
            raise HTTPException(404, "待入库单不存在")
        if sin.product_id != item.product_id:
            raise HTTPException(400, "待入库单产品与采购明细不一致")
        if sin.status not in ("待入库", "部分入库"):
            raise HTTPException(400, f"该待入库单状态「{sin.status}」，不能关联")
        if sin.purchase_item_id:
            raise HTTPException(400, "该待入库单已关联其他采购明细")
        sin.purchase_order_id = order_id
        sin.purchase_item_id = item_id
        sin.source_type = "purchase"
        item.receive_type = "成品库"
        db.commit()
        return {"message": "已关联待入库单，可在成品入库模块收货"}
    # 新建备货待入库单
    sin = StockInOrder(
        source_type="purchase",
        purchase_order_id=order_id,
        purchase_item_id=item_id,
        product_id=item.product_id,
        quantity=item.quantity,
        status="待入库",
        created_by=current_user.display_name or current_user.username,
    )
    # 关联了销售明细的采购：待入库单带上销售信息，收货批次直接用销售批次号（SO-xxx-01），成本归集到销售单
    if item.sales_item_id:
        from app.models.sales import SalesOrderItem
        sales_item = db.query(SalesOrderItem).filter(SalesOrderItem.id == item.sales_item_id).first()
        if sales_item:
            sin.sales_order_id = sales_item.order_id
            sin.sales_item_id = sales_item.id
    db.add(sin)
    item.receive_type = "成品库"
    db.commit()
    return {"message": "已生成待入库单，可在成品入库模块收货"}


@router.post("/orders/{order_id}/items/{item_id}/to-material", tags=["采购管理"])
def to_material(order_id: int, item_id: int,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """采购明细「转原料库入库」— 生成待入库单（原料入库模块收货）"""
    from app.models.inventory import StockInOrder
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "采购订单不存在")
    if order.status != "已审核":
        raise HTTPException(400, "仅已审核的采购订单可转原料库入库")
    item = db.query(PurchaseOrderItem).filter(
        PurchaseOrderItem.id == item_id, PurchaseOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "采购明细不存在")
    if not item.material_id:
        raise HTTPException(400, "该明细为产品采购，请使用「转成品库入库」")
    if item.receive_type:
        raise HTTPException(400, f"该明细已转「{item.receive_type}」，不能重复操作")
    # 生成待入库单（材料）→ 原料入库模块收货
    sin = StockInOrder(
        source_type="purchase",
        purchase_order_id=order_id,
        purchase_item_id=item_id,
        material_id=item.material_id,
        quantity=item.quantity,
        status="待入库",
        created_by=current_user.display_name or current_user.username,
    )
    db.add(sin)
    item.receive_type = "原料库"
    db.commit()
    return {"message": "已生成待入库单，可在「库存管理 → 原料入库」模块收货"}


@router.post("/orders/{order_id}/approve", tags=["采购管理"])
def approve_order(order_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(require_permission("menu:purchase:orders"))):
    """审核采购订单（需采购订单菜单权限）"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, f"当前状态不能审核: {order.status}")
    order.status = "已审核"
    db.commit()
    return {"message": "采购订单已审核"}


@router.post("/orders/{order_id}/unapprove", tags=["采购管理"])
def unapprove_order(order_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission("menu:purchase:orders"))):
    """反审核采购订单（无下游入库单/发票时允许，需采购订单菜单权限）"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "已审核":
        raise HTTPException(400, f"当前状态不能反审核: {order.status}")
    receipts = db.query(PurchaseReceipt).filter(PurchaseReceipt.order_id == order_id).count()
    invoices = db.query(PurchaseInvoice).filter(PurchaseInvoice.order_id == order_id).count()
    if receipts > 0:
        raise HTTPException(400, "该订单已有关联入库单，无法反审核")
    if invoices > 0:
        raise HTTPException(400, "该订单已有关联发票，无法反审核")
    order.status = "待审核"
    db.commit()
    return {"message": "采购订单已反审核"}


# ==================== 采购入库（含批次号生成） ====================

@router.post("/receipts", tags=["采购管理"])
def create_receipt(
    data: PurchaseReceiptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """采购入库 — 自动生成批次号并更新库存"""
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == data.order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    # 状态校验：待审核/已关闭订单不可入库
    if order.status in ("待审核", "已关闭", "已取消"):
        raise HTTPException(400, f"订单状态「{order.status}」不允许入库")

    # 仓库参照校验：必须存在于仓库档案且启用
    wh = db.query(Warehouse).filter(Warehouse.id == data.warehouse_id, Warehouse.is_active == 1).first()
    if not wh:
        raise HTTPException(400, f"仓库档案不存在或已停用 (id={data.warehouse_id})，请先在「基础档案-仓库管理」维护")

    # 生成入库单号
    from app.utils.batch_no import generate_doc_no
    from app.models.purchase import PurchaseReceipt
    receipt_no = generate_doc_no(db, "PR", PurchaseReceipt, "receipt_no")

    receipt = PurchaseReceipt(
        receipt_no=receipt_no,
        order_id=data.order_id,
        warehouse_id=data.warehouse_id,
        receipt_date=data.receipt_date or date.today(),
        operator=current_user.display_name or current_user.username,
        remark=data.remark,
    )
    db.add(receipt)
    db.flush()

    total_qty = 0
    # 预加载订单明细，按 material_id 和 product_id 分别索引
    order_items_by_material = {}
    order_items_by_product = {}
    for oi in order.items:
        if oi.material_id:
            order_items_by_material[oi.material_id] = oi
        if oi.product_id:
            order_items_by_product[oi.product_id] = oi

    for item_data in data.items:
        if item_data.quantity <= 0:
            raise HTTPException(400, "收货数量必须大于0")
        # 产品类明细（转成品库入库）不能走采购入库
        if not item_data.material_id:
            raise HTTPException(400, "产品类采购明细请使用「转成品库入库」收货")
        # 查找订单明细：优先按 order_item_id，其次按 material_id/product_id
        order_item = None
        if item_data.order_item_id:
            order_item = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.id == item_data.order_item_id
            ).first()
        elif item_data.material_id:
            order_item = order_items_by_material.get(item_data.material_id)
        elif item_data.product_id:
            order_item = order_items_by_product.get(item_data.product_id)

        is_product = bool(order_item and order_item.product_id)
        # 成本 = 订单明细单价(本币) 或 明细项单价
        inv_unit_cost = 0
        if order_item:
            inv_unit_cost = order_item.unit_price_local or order_item.unit_price
        elif item_data.unit_price:
            inv_unit_cost = item_data.unit_price

        # 生成批次号: YYYYMMDD-NNN
        batch_no = generate_batch_no(db)

        receipt_item = PurchaseReceiptItem(
            receipt_id=receipt.id,
            order_item_id=item_data.order_item_id,
            material_id=item_data.material_id or (order_item.material_id if order_item else None),
            product_id=item_data.product_id or (order_item.product_id if order_item else None),
            quantity=item_data.quantity,
            unit_price=inv_unit_cost,
            batch_no=batch_no,
            remark=item_data.remark,
        )
        db.add(receipt_item)
        total_qty += item_data.quantity

        # 更新订单明细已入库数量
        if order_item:
            order_item.received_qty = (order_item.received_qty or 0) + item_data.quantity

        # 写入批次库存台账（含成本）
        inventory = WarehouseInventory(
            warehouse_id=data.warehouse_id,
            material_id=item_data.material_id or (order_item.material_id if order_item else None),
            product_id=item_data.product_id or (order_item.product_id if order_item else None),
            batch_no=batch_no,
            quantity=item_data.quantity,
            unit_cost=inv_unit_cost,
            total_cost=round(item_data.quantity * inv_unit_cost, 2),
            in_date=_parse_date(data.receipt_date) or date.today(),
            source_type="purchase",
            source_doc_id=receipt.id,
        )
        db.add(inventory)

        # 写入库存流水（含成本）
        trans = StockTransaction(
            trans_type="purchase_in",
            warehouse_id=data.warehouse_id,
            material_id=item_data.material_id or (order_item.material_id if order_item else None),
            product_id=item_data.product_id or (order_item.product_id if order_item else None),
            batch_no=batch_no,
            quantity=item_data.quantity,
            unit_cost=inv_unit_cost,
            total_amount=round(item_data.quantity * inv_unit_cost, 2),
            before_qty=0,
            after_qty=item_data.quantity,
            before_cost=0,
            after_cost=round(item_data.quantity * inv_unit_cost, 2),
            source_doc_type="采购入库",
            source_doc_no=receipt_no,
            trans_no=generate_doc_no(db, "ST"),
            operator=current_user.display_name or current_user.username,
        )
        db.add(trans)

        # 回写最新采购单价
        if is_product:
            prod = db.query(Product).filter(Product.id == order_item.product_id).first()
            if prod and inv_unit_cost > 0:
                prod.estimated_cost = inv_unit_cost
        elif order_item and order_item.material_id:
            mat = db.query(Material).filter(Material.id == order_item.material_id).first()
            if mat and inv_unit_cost > 0:
                mat.purchase_price = inv_unit_cost

        # 刷新确保流水号唯一递增
        db.flush()

    receipt.total_qty = total_qty
    # 更新订单状态
    all_received = False
    if order:
        all_received = all(
            item.received_qty >= item.quantity
            for item in (db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == order.id).all() or [])
        )
        if all_received:
            order.status = "待开票"
        else:
            order.status = "部分入库"

    # 更新关联的生产订单（外购型 PO 入库完成 → MO 已入库）
    from app.models.production import ProductionOrder
    # 通过采购需求找 MO：订单明细 → requisition → production_order
    from app.models.purchase import PurchaseRequisition
    req_ids = [it.requisition_id for it in order.items if it.requisition_id]
    linked_mo = None
    for req_id in req_ids:
        req = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
        if req:
            linked_mo = db.query(ProductionOrder).filter(ProductionOrder.id == req.production_order_id).first()
            break
    if linked_mo and all_received:
        linked_mo.status = "已入库"
        linked_mo.received_qty = linked_mo.quantity

    db.commit()
    return {
        "id": receipt.id,
        "receipt_no": receipt_no,
        "message": f"入库成功，共 {len(data.items)} 项，已生成批次号",
    }


@router.get("/receipts", tags=["采购管理"])
def list_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """入库单列表"""
    items = db.query(PurchaseReceipt).order_by(PurchaseReceipt.id.desc()).offset(
        (page-1)*page_size).limit(page_size).all()
    total = db.query(PurchaseReceipt).count()
    result = []
    for r in items:
        batch_nos = [i.batch_no for i in r.items]
        red_of = db.query(PurchaseReceipt).filter(PurchaseReceipt.id == r.red_of_receipt_id).first() if r.red_of_receipt_id else None
        result.append({
            "id": r.id, "receipt_no": r.receipt_no,
            "order_no": r.order.order_no if r.order else "",
            "warehouse_name": r.warehouse.name if r.warehouse else "",
            "receipt_date": str(r.receipt_date),
            "total_qty": r.total_qty,
            "status": r.status,
            "is_red": r.is_red or 0,
            "red_of_receipt_id": r.red_of_receipt_id,
            "red_of_no": red_of.receipt_no if red_of else "",
            "batch_nos": batch_nos,
            "item_count": len(r.items),
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/receipts/{receipt_id}", tags=["采购管理"])
def get_receipt(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """入库单详情"""
    r = db.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()
    if not r:
        raise HTTPException(404, "入库单不存在")
    from app.models.foundation import Material
    return {
        "id": r.id, "receipt_no": r.receipt_no,
        "order_no": r.order.order_no if r.order else "",
        "warehouse_name": r.warehouse.name if r.warehouse else "",
        "receipt_date": str(r.receipt_date),
        "total_qty": r.total_qty,
        "status": r.status,
        "is_red": r.is_red or 0,
        "red_of_receipt_id": r.red_of_receipt_id,
        "remark": r.remark or "",
        "operator": r.operator or "",
        "created_at": str(r.created_at) if r.created_at else "",
        "items": [{
            "id": i.id,
            "material_id": i.material_id,
            "material_name": i.material.name if i.material else "",
            "material_code": i.material.code if i.material else "",
            "product_id": i.product_id,
            "product_name": i.product.name_cn if i.product else "",
            "quantity": i.quantity,
            "unit_price": i.unit_price,
            "total_amount": round(i.quantity * i.unit_price, 2),
            "batch_no": i.batch_no,
        } for i in r.items],
    }


@router.delete("/receipts/{receipt_id}", tags=["采购管理"])
def delete_receipt(receipt_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消入库 — 仅限批次未发生任何下游出入库；回滚库存、订单状态并补冲销流水"""
    receipt = db.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(404, "入库单不存在")
    if receipt.is_red:
        raise HTTPException(400, "红冲单不能取消，请直接删除红冲记录")

    # 检查下游发票
    invoices = db.query(PurchaseInvoice).filter(PurchaseInvoice.order_id == receipt.order_id).count()
    if invoices > 0:
        raise HTTPException(400, "该订单已有关联发票，无法取消入库")

    # 校验：批次若已被消耗（发料/发货/盘点/退货等），禁止物理取消 → 应走红冲
    for item in receipt.items:
        other_txn = db.query(StockTransaction).filter(
            StockTransaction.batch_no == item.batch_no,
            ~StockTransaction.trans_type.in_(["purchase_in", "purchase_return_out"]),
        ).first()
        if other_txn:
            raise HTTPException(400, f"批次 {item.batch_no} 已发生其他出入库，无法取消；请使用红冲")

    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.order_id).first()

    # 回滚库存和批次
    for item in receipt.items:
        # 补一条冲销流水（保留审计轨迹：入库+100 / 红冲-100 → 期末0）
        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.batch_no == item.batch_no,
        ).first()
        if inv:
            uc = inv.unit_cost or item.unit_price or 0
            trans = StockTransaction(
                trans_type="purchase_return_out",
                warehouse_id=receipt.warehouse_id,
                material_id=item.material_id,
                product_id=item.product_id,
                batch_no=item.batch_no,
                quantity=-item.quantity,
                unit_cost=uc,
                total_amount=round(-item.quantity * uc, 2),
                before_qty=inv.quantity,
                after_qty=max(0, inv.quantity - item.quantity),
                before_cost=round(inv.quantity * uc, 2),
                after_cost=round(max(0, inv.quantity - item.quantity) * uc, 2),
                source_doc_type="取消入库",
                source_doc_no=receipt.receipt_no,
                trans_no=generate_doc_no(db, "ST"),
                operator=current_user.display_name or current_user.username,
            )
            db.add(trans)
        # 删除库存台账记录（材料/成品双路径）
        inv_q = db.query(WarehouseInventory).filter(
            WarehouseInventory.source_type == "purchase",
            WarehouseInventory.source_doc_id == receipt.id,
            WarehouseInventory.batch_no == item.batch_no,
        )
        if item.material_id:
            inv_q = inv_q.filter(WarehouseInventory.material_id == item.material_id)
        elif item.product_id:
            inv_q = inv_q.filter(WarehouseInventory.product_id == item.product_id)
        inv_q.delete()
        # 回滚订单明细已入库数量
        if item.order_item_id:
            oi = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item.order_item_id).first()
        elif item.material_id:
            oi = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.order_id == receipt.order_id,
                PurchaseOrderItem.material_id == item.material_id
            ).first()
        else:
            oi = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.order_id == receipt.order_id,
                PurchaseOrderItem.product_id == item.product_id
            ).first()
        if oi:
            oi.received_qty = max(0, (oi.received_qty or 0) - item.quantity)

    # 回滚订单状态
    if order:
        remaining = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == order.id).all()
        if all((item.received_qty or 0) <= 0 for item in remaining):
            order.status = "已审核"
        elif not all((item.received_qty or 0) >= item.quantity for item in remaining):
            order.status = "部分入库"

    # 级联删除明细（cascade="all, delete-orphan"）
    db.delete(receipt)
    db.commit()
    return {"message": "入库已取消，库存已回滚（已补冲销流水）"}


@router.post("/receipts/{receipt_id}/red", tags=["采购管理"])
def red_receipt(
    receipt_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """红冲入库单 — 允许批次已被消耗的场景，生成负向红冲单+冲销流水，保留审计轨迹

    body: {"items": [{"receipt_item_id": 1, "quantity": 20}], "remark": "..."}
    - 不传 items → 按批次当前剩余全部红冲
    - 红冲数量不能超过该批次当前剩余库存
    """
    receipt = db.query(PurchaseReceipt).filter(PurchaseReceipt.id == receipt_id).first()
    if not receipt:
        raise HTTPException(404, "入库单不存在")
    if receipt.is_red:
        raise HTTPException(400, "红冲单不能再次红冲")

    # 检查下游发票
    invoices = db.query(PurchaseInvoice).filter(PurchaseInvoice.order_id == receipt.order_id).count()
    if invoices > 0:
        raise HTTPException(400, "该订单已有关联发票，无法红冲")

    # 已红冲数量（支持多次红冲）
    red_receipts = db.query(PurchaseReceipt).filter(
        PurchaseReceipt.red_of_receipt_id == receipt.id
    ).all()
    red_by_item = {}
    for rr in red_receipts:
        for ri in rr.items:
            key = ri.order_item_id or (ri.material_id or ri.product_id)
            red_by_item[key] = red_by_item.get(key, 0) + abs(ri.quantity or 0)

    # 解析红冲请求：默认全部
    req_items = {it["receipt_item_id"]: float(it["quantity"]) for it in (data.get("items") or [])}

    from app.models.production import ProductionOrder
    from app.models.purchase import PurchaseRequisition
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.order_id).first()

    red_receipt_no = generate_doc_no(db, "PR", PurchaseReceipt, "receipt_no")
    red = PurchaseReceipt(
        receipt_no=red_receipt_no,
        order_id=receipt.order_id,
        warehouse_id=receipt.warehouse_id,
        receipt_date=date.today(),
        status="已红冲",
        total_qty=0,
        is_red=1,
        red_of_receipt_id=receipt.id,
        remark=data.get("remark", ""),
        operator=current_user.display_name or current_user.username,
    )
    db.add(red)
    db.flush()

    red_total_qty = 0.0
    mo_reduced = 0.0
    for item in receipt.items:
        # 定位台账行（材料/成品双路径）
        inv = db.query(WarehouseInventory).filter(
            WarehouseInventory.batch_no == item.batch_no,
        ).first()
        if item.material_id:
            inv = db.query(WarehouseInventory).filter(
                WarehouseInventory.batch_no == item.batch_no,
                WarehouseInventory.material_id == item.material_id,
            ).first()
        elif item.product_id:
            inv = db.query(WarehouseInventory).filter(
                WarehouseInventory.batch_no == item.batch_no,
                WarehouseInventory.product_id == item.product_id,
            ).first()

        key = item.order_item_id or (item.material_id or item.product_id)
        already = red_by_item.get(key, 0)
        max_red = max(0, (item.quantity or 0) - already)
        remaining = inv.quantity if inv else 0

        if item.id in req_items:
            red_qty = min(req_items[item.id], max_red)
            if req_items[item.id] > max_red + 0.001:
                raise HTTPException(400, f"批次 {item.batch_no} 累计可红冲 {max_red:.2f}（本次请求 {req_items[item.id]:.2f}）")
        else:
            # 不指定数量 → 按"未冲销上限 与 当前剩余"的较小值（考虑已被发料/盘点消耗的部分）
            red_qty = min(max_red, remaining)
        if red_qty <= 0.001:
            continue

        uc = item.unit_price or (inv.unit_cost if inv else 0) or 0
        if red_qty > remaining + 0.001:
            raise HTTPException(400, f"批次 {item.batch_no} 当前剩余 {remaining:.2f}，不足红冲 {red_qty:.2f}")

        # 红冲单明细（红字：数量为负）
        ri = PurchaseReceiptItem(
            receipt_id=red.id,
            order_item_id=item.order_item_id,
            material_id=item.material_id,
            product_id=item.product_id,
            quantity=-red_qty,
            unit_price=uc,
            batch_no=item.batch_no,
            remark=data.get("remark", ""),
        )
        db.add(ri)

        # 扣台账
        if inv:
            old_qty = inv.quantity
            inv.quantity = round(old_qty - red_qty, 4)
            inv.total_cost = round(inv.quantity * uc, 2)
        else:
            old_qty = 0

        # 冲销流水
        trans = StockTransaction(
            trans_type="purchase_return_out",
            warehouse_id=receipt.warehouse_id,
            material_id=item.material_id,
            product_id=item.product_id,
            batch_no=item.batch_no,
            quantity=-red_qty,
            unit_cost=uc,
            total_amount=round(-red_qty * uc, 2),
            before_qty=old_qty,
            after_qty=inv.quantity if inv else 0,
            before_cost=round(old_qty * uc, 2),
            after_cost=round((inv.quantity if inv else 0) * uc, 2),
            source_doc_type="采购红冲",
            source_doc_no=red_receipt_no,
            trans_no=generate_doc_no(db, "ST"),
            operator=current_user.display_name or current_user.username,
        )
        db.add(trans)

        # 回退订单明细
        if item.order_item_id:
            oi = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == item.order_item_id).first()
        elif item.material_id:
            oi = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.order_id == receipt.order_id,
                PurchaseOrderItem.material_id == item.material_id
            ).first()
        else:
            oi = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.order_id == receipt.order_id,
                PurchaseOrderItem.product_id == item.product_id
            ).first()
        if oi:
            oi.received_qty = max(0, (oi.received_qty or 0) - red_qty)
        red_total_qty += red_qty
        mo_reduced += red_qty
        db.flush()

    if red_total_qty <= 0:
        raise HTTPException(400, "没有可红冲的数量（可能已全部红冲）")

    red.total_qty = red_total_qty

    # 原单标记已红冲
    receipt.status = "已红冲"

    # 订单状态回退
    if order:
        remaining_items = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.order_id == order.id).all()
        if all((it.received_qty or 0) <= 0 for it in remaining_items):
            order.status = "已审核"
        elif not all((it.received_qty or 0) >= it.quantity for it in remaining_items):
            order.status = "部分入库"

    # 外购型 MO 回退（PR → MO 链路）
    req_ids = [it.requisition_id for it in order.items if it.requisition_id] if order else []
    linked_mo = None
    for req_id in req_ids:
        req = db.query(PurchaseRequisition).filter(PurchaseRequisition.id == req_id).first()
        if req:
            linked_mo = db.query(ProductionOrder).filter(ProductionOrder.id == req.production_order_id).first()
            break
    if linked_mo and linked_mo.status in ("已入库", "部分入库"):
        new_received = max(0, (linked_mo.received_qty or 0) - mo_reduced)
        linked_mo.received_qty = new_received
        if new_received <= 0:
            linked_mo.status = "待采购"
        else:
            linked_mo.status = "部分入库"

    db.commit()
    return {
        "id": red.id, "red_receipt_no": red_receipt_no,
        "message": f"红冲成功：{red_total_qty:.2f}，红冲单 {red_receipt_no}",
    }


# ==================== 采购发票 ====================

@router.post("/invoices", tags=["采购管理"])
def create_invoice(
    data: PurchaseInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建采购发票并生成应付"""
    order_id = data.order_id if hasattr(data, 'order_id') else getattr(data, 'purchase_order_id', None) or getattr(data, 'order_id', None)
    order = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")

    # 发票号唯一性校验（数据库唯一约束冲突 → 409 业务错误）
    existing_inv = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.invoice_no == data.invoice_no).first()
    if existing_inv:
        raise HTTPException(409, f"发票号已存在: {data.invoice_no}")

    invoice = PurchaseInvoice(
        invoice_no=data.invoice_no,
        order_id=data.order_id,
        supplier_id=data.supplier_id or order.supplier_id,
        invoice_date=data.invoice_date or date.today(),
        invoice_type=data.invoice_type or "增值税专用发票",
        amount=data.amount,
        amount_fc=data.amount_fc,
        tax_amount=data.tax_amount,
        remark=data.remark,
    )
    db.add(invoice)
    db.flush()

    # 同步创建进项发票（退税用, 仅限可抵扣类型）
    from app.models.tax_refund import TaxRefundInputInvoice
    deductible_types = ["增值税专用发票", "海关进口缴款书", "农产品收购发票"]
    if data.invoice_type in deductible_types:
        try:
            existing = db.query(TaxRefundInputInvoice).filter(
                TaxRefundInputInvoice.invoice_no == data.invoice_no).first()
            if not existing:
                input_inv = TaxRefundInputInvoice(
                    invoice_no=data.invoice_no,
                    supplier_id=data.supplier_id or order.supplier_id,
                    purchase_invoice_id=invoice.id,
                    invoice_date=data.invoice_date or date.today(),
                    amount=data.amount,
                    tax_amount=data.tax_amount or 0,
                    total_amount=(data.amount or 0) + (data.tax_amount or 0),
                    certification_status="未认证",
                    refund_match_status="未匹配",
                )
                db.add(input_inv)
        except:
            pass

    # 自动生成应付账款（到期日 = 发票日期 + 供应商账期）
    total = (data.amount or 0) + (data.tax_amount or 0)
    supplier = db.query(Supplier).filter(Supplier.id == data.supplier_id).first()
    due_days = supplier.account_period if supplier else 30
    due_date = (data.invoice_date or date.today()) + timedelta(days=due_days)
    from app.utils.batch_no import generate_doc_no
    from app.models.purchase import AccountsPayable
    ap_no_str = generate_doc_no(db, "AP", AccountsPayable, "ap_no")
    ap = AccountsPayable(
        ap_no=ap_no_str,
        source_type="purchase_invoice",
        source_id=invoice.id,
        supplier_id=data.supplier_id or order.supplier_id,
        amount=total,
        amount_fc=data.amount_fc or total,
        currency_id=order.currency_id,
        paid_amount=0,
        balance=total,
        due_date=due_date,
        status="未付款",
    )
    db.add(ap)
    db.commit()
    return {"id": invoice.id, "invoice_no": data.invoice_no, "ap_no": ap_no_str, "message": "发票已创建，应付已生成"}


# ==================== 采购发票列表 ====================

@router.get("/invoice-statuses", tags=["采购管理"])
def list_invoice_statuses(db: Session = Depends(get_db)):
    rows = db.query(PurchaseInvoice.status).distinct().all()
    return [r[0] for r in rows if r[0]]

@router.get("/invoices", tags=["采购管理"])
def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PurchaseInvoice)
    total = query.count()
    items = query.order_by(PurchaseInvoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for inv in items:
        order = db.query(PurchaseOrder).filter(PurchaseOrder.id == inv.order_id).first() if inv.order_id else None
        supplier = db.query(Supplier).filter(Supplier.id == inv.supplier_id).first() if inv.supplier_id else None
        result.append({
            "id": inv.id, "invoice_no": inv.invoice_no,
            "supplier_id": inv.supplier_id,
            "supplier_name": supplier.name if supplier else "",
            "order_id": inv.order_id,
            "order_no": order.order_no if order else "",
            "amount": inv.amount, "tax_amount": inv.tax_amount or 0,
            "total_amount": (inv.amount or 0) + (inv.tax_amount or 0),
            "invoice_date": str(inv.invoice_date) if inv.invoice_date else "",
            "status": inv.status, "remark": inv.remark or "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.put("/invoices/{invoice_id}", tags=["采购管理"])
def update_invoice(invoice_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """修改采购发票"""
    inv = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "发票不存在")
    # 已付款的发票禁止改金额（先退付款单，保证应付一致）
    ap0 = db.query(AccountsPayable).filter(
        AccountsPayable.source_type == "purchase_invoice",
        AccountsPayable.source_id == invoice_id,
    ).first()
    if ap0 and (ap0.paid_amount or 0) > 0 and any(k in data for k in ["amount", "tax_amount", "tax_rate"]):
        raise HTTPException(400, f"该发票对应应付单已付款 ¥{ap0.paid_amount}，不能修改金额；请先删除付款单")
    for field in ["invoice_no", "amount", "tax_amount", "tax_rate", "invoice_date", "remark"]:
        if field in data:
            val = data[field]
            if field == "invoice_date":
                val = _parse_date(val)
            setattr(inv, field, val)
    db.commit()
    return {"message": "发票已更新"}


@router.delete("/invoices/{invoice_id}", tags=["采购管理"])
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除采购发票"""
    inv = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "发票不存在")
    # 级联删除进项发票（退税）
    from app.models.tax_refund import TaxRefundInputInvoice
    try:
        db.query(TaxRefundInputInvoice).filter(
            TaxRefundInputInvoice.purchase_invoice_id == invoice_id).delete()
    except:
        pass
    # 级联删除应付（先检查是否已付款）
    try:
        ap = db.query(AccountsPayable).filter(
            AccountsPayable.source_type == "purchase_invoice",
            AccountsPayable.source_id == invoice_id).first()
        if ap:
            if (ap.paid_amount or 0) > 0:
                raise HTTPException(400, f"该发票对应应付单已付款 ¥{ap.paid_amount}，请先删除付款单再删除发票")
            db.delete(ap)
    except HTTPException:
        raise
    except:
        pass
    db.delete(inv)
    db.commit()
    return {"message": "发票已删除"}


# ==================== 付款 ====================

@router.post("/payments", tags=["采购管理"])
def create_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """付款并核销应付"""
    from app.utils.batch_no import generate_doc_no
    from app.models.purchase import Payment
    payment_no = generate_doc_no(db, "PM", Payment, "payment_no")

    payment = Payment(
        payment_no=payment_no,
        supplier_id=data.supplier_id,
        payment_date=data.payment_date or date.today(),
        amount=data.amount,
        amount_fc=data.amount_fc,
        currency_id=data.currency_id,
        exchange_rate=data.exchange_rate or 1,
        payment_method=data.payment_method or "银行转账",
        remark=data.remark,
        operator=current_user.display_name or current_user.username,
    )
    db.add(payment)
    db.flush()

    # 核销应付
    if data.ap_account_ids:
        ap_account = db.query(AccountsPayable).filter(
            AccountsPayable.id == data.ap_account_ids
        ).first()
        if ap_account:
            alloc_amount = min(data.amount, ap_account.balance)
            alloc = PaymentAllocation(
                payment_id=payment.id,
                ap_account_id=ap_account.id,
                allocated_amount=alloc_amount,
            )
            db.add(alloc)
            ap_account.paid_amount = (ap_account.paid_amount or 0) + alloc_amount
            ap_account.balance = ap_account.amount - ap_account.paid_amount
            ap_account.status = "已付款" if ap_account.balance <= 0 else "部分付款"

    db.commit()
    return {"id": payment.id, "payment_no": payment_no, "message": "付款成功"}


# ==================== 付款单管理 ====================

@router.get("/payments", tags=["采购管理"])
def list_payments(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(Payment)
    if keyword:
        query = query.join(Supplier).filter(
            Payment.payment_no.like(f"%{keyword}%") | Supplier.name.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(Payment.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    result = []
    for p in items:
        supplier = db.query(Supplier).filter(Supplier.id == p.supplier_id).first()
        allocs = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == p.id).all()
        result.append({
            "id": p.id, "payment_no": p.payment_no,
            "supplier_id": p.supplier_id,
            "supplier_name": supplier.name if supplier else "",
            "payment_date": str(p.payment_date) if p.payment_date else "",
            "amount": p.amount, "amount_fc": p.amount_fc,
            "currency_id": p.currency_id,
            "exchange_rate": p.exchange_rate,
            "payment_method": p.payment_method,
            "remark": p.remark or "",
            "operator": p.operator or "",
            "allocated_amount": sum(a.allocated_amount or 0 for a in allocs),
            "created_at": str(p.created_at) if p.created_at else "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/payments/{payment_id}", tags=["采购管理"])
def get_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "付款单不存在")
    supplier = db.query(Supplier).filter(Supplier.id == p.supplier_id).first()
    allocs = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == p.id).all()
    ap_ids = [a.ap_account_id for a in allocs]
    ap_list = db.query(AccountsPayable).filter(AccountsPayable.id.in_(ap_ids)).all() if ap_ids else []
    ap_map = {ap.id: ap.ap_no or "" for ap in ap_list}
    return {
        "id": p.id, "payment_no": p.payment_no,
        "supplier_id": p.supplier_id, "supplier_name": supplier.name if supplier else "",
        "payment_date": str(p.payment_date) if p.payment_date else "",
        "amount": p.amount, "amount_fc": p.amount_fc,
        "currency_id": p.currency_id, "exchange_rate": p.exchange_rate,
        "payment_method": p.payment_method, "remark": p.remark or "",
        "operator": p.operator or "",
        "created_at": str(p.created_at) if p.created_at else "",
        "allocations": [{
            "id": a.id, "ap_account_id": a.ap_account_id,
            "ap_no": ap_map.get(a.ap_account_id, ""),
            "allocated_amount": a.allocated_amount,
        } for a in allocs],
    }


@router.put("/payments/{payment_id}", tags=["采购管理"])
def update_payment(payment_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "付款单不存在")
    for field in ["payment_method", "remark", "payment_date"]:
        if field in data:
            val = data[field]
            if field == "payment_date":
                val = _parse_date(val)
            setattr(p, field, val)
    db.commit()
    return {"message": "付款单已更新"}


@router.delete("/payments/{payment_id}", tags=["采购管理"])
def delete_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = db.query(Payment).filter(Payment.id == payment_id).first()
    if not p:
        raise HTTPException(404, "付款单不存在")
    allocs = db.query(PaymentAllocation).filter(PaymentAllocation.payment_id == p.id).all()
    for alloc in allocs:
        ap = db.query(AccountsPayable).filter(AccountsPayable.id == alloc.ap_account_id).first()
        if ap:
            ap.paid_amount = max(0, (ap.paid_amount or 0) - (alloc.allocated_amount or 0))
            ap.balance = ap.amount - ap.paid_amount
            ap.status = "已付款" if ap.balance <= 0 else ("部分付款" if ap.paid_amount > 0 else "未付款")
        db.delete(alloc)
    db.flush()
    db.delete(p)
    db.commit()
    return {"message": "付款单已删除，应付已回滚"}


# ==================== 应付账款 ====================

@router.get("/ap", tags=["采购管理"])
def list_ap(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("", description="状态筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """应付账款列表"""
    query = db.query(AccountsPayable)
    if status:
        query = query.filter(AccountsPayable.status == status)
    total = query.count()
    items = query.order_by(AccountsPayable.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    from app.models.foundation import Supplier
    result = []
    for ap in items:
        supplier = db.query(Supplier).filter(Supplier.id == ap.supplier_id).first()
        # 查来源发票日期
        invoice_date = ""
        payment_terms = supplier.payment_terms if supplier else ""
        account_period = supplier.account_period if supplier else 0
        if ap.source_type == "purchase_invoice" and ap.source_id:
            inv = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == ap.source_id).first()
            if inv:
                invoice_date = str(inv.invoice_date) if inv.invoice_date else ""
        result.append({
            "id": ap.id, "ap_no": ap.ap_no or "",
            "source_type": ap.source_type,
            "supplier_id": ap.supplier_id,
            "supplier_name": supplier.name if supplier else "",
            "amount": ap.amount, "paid_amount": ap.paid_amount,
            "balance": ap.balance, "due_date": str(ap.due_date) if ap.due_date else "",
            "status": ap.status, "created_at": str(ap.created_at),
            "invoice_date": invoice_date,
            "payment_terms": payment_terms,
            "account_period": account_period,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}

@router.get("/ap/payment-detail", tags=["采购管理"])
def list_ap_payment_detail(db: Session = Depends(get_db)):
    from app.models.purchase import Payment, PaymentAllocation
    rows = db.query(AccountsPayable, Payment, PaymentAllocation).outerjoin(
        PaymentAllocation, PaymentAllocation.ap_account_id == AccountsPayable.id
    ).outerjoin(Payment, Payment.id == PaymentAllocation.payment_id
    ).order_by(AccountsPayable.id).all()
    result, seen = [], set()
    for ap, pm, pa in rows:
        key = f"{ap.id}-{pa.id if pa else 0}"
        if key in seen: continue
        seen.add(key)
        sname = db.query(Supplier.name).filter(Supplier.id == ap.supplier_id).scalar() or ""
        result.append({"supplier_name": sname,
            "ap_date": str(ap.created_at)[:10] if ap.created_at else "",
            "ap_no": ap.ap_no or "", "ap_id": ap.id, "supplier_id": ap.supplier_id,
            "ap_amount": ap.amount or 0,
            "pm_date": str(pm.payment_date) if pm and pm.payment_date else "",
            "payment_no": pm.payment_no if pm else "",
            "payment_id": pm.id if pm else None,
            "paid_amount": pa.allocated_amount if pa else 0,
        })
    result.sort(key=lambda r: r["ap_date"])
    return {"items": result}

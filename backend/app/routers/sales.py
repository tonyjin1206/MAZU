"""销售模块 API 路由 — 报价→订单→生产驱动→发货(批次)→报关→发票→应收→收款"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session


def _parse_date(val):
    if val is None or isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None
from app.database import get_db
from app.models.auth import User
from app.models.foundation import Customer, Product, Currency, HsCode, TradeTerm
from app.models.sales import (
    SalesQuote, SalesOrder, SalesOrderItem,
    SalesDelivery, CustomsDeclaration,
    SalesInvoice,
    AccountsReceivable, Collection, CollectionAllocation,
)
from app.models.inventory import WarehouseInventory, StockTransaction
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_doc_no

router = APIRouter()


# ==================== 报价单 ====================

@router.post("/quotes", tags=["销售管理"])
def create_quote(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建报价单"""
    today = date.today().strftime("%Y%m%d")
    count_q = db.query(SalesQuote).filter(
        SalesQuote.quote_no.like(f"QT-{today}%")
    ).count()
    quote = SalesQuote(
        quote_no=f"QT-{today}-{count_q+1:03d}",
        customer_id=data["customer_id"],
        product_id=data["product_id"],
        quantity=data["quantity"],
        unit_price=data["unit_price"],
        total_amount=data["quantity"] * data["unit_price"],
        currency_id=data.get("currency_id"),
        trade_term_id=data.get("trade_term_id"),
        valid_until=data.get("valid_until"),
        remark=data.get("remark", ""),
        created_by=current_user.display_name or current_user.username,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return {"id": quote.id, "quote_no": quote.quote_no}


@router.get("/quotes", tags=["销售管理"])
def list_quotes(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    items = db.query(SalesQuote).order_by(SalesQuote.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": db.query(SalesQuote).count(), "page": page, "page_size": page_size, "items": [
        {"id": q.id, "quote_no": q.quote_no, "customer_name": q.customer.name_cn if q.customer else "",
         "product_name": q.product.name_cn if q.product else "", "quantity": q.quantity,
         "total_amount": q.total_amount, "status": q.status} for q in items
    ]}


# ==================== 销售订单 ====================

@router.post("/orders", tags=["销售管理"])
def create_sales_order(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建销售订单（定制产品触发生产）"""
    from datetime import date
    # 汇率换算
    currency_id = data.get("currency_id") or 1

    today_str = date.today().strftime("%Y%m%d")
    count = db.query(SalesOrder).filter(SalesOrder.order_no.like(f"SO-{today_str}%")).count()
    order_no = f"SO-{today_str}-{count+1:03d}"

    exchange_rate = data.get("exchange_rate") or 1
    # 汇总明细行金额
    items_data = data.get("items", [])
    if not items_data:
        raise HTTPException(400, "订单至少包含一行明细")

    total_amount_fc = 0
    for item in items_data:
        item_qty_safe = float(item.get("quantity", 0) or 0)
        item_price_safe = float(item.get("unit_price", 0) or 0)
        item_total_safe = float(item.get("total_amount", 0) or 0)
        if not item_total_safe:
            item_total_safe = item_qty_safe * item_price_safe
        total_amount_fc += item_total_safe
    total_amount_local = total_amount_fc * exchange_rate
    tax_amount_local = 0
    for item in items_data:
        item_tax_rate = float(item.get("tax_rate", 13) or 13) / 100
        item_qty_safe = float(item.get("quantity", 0) or 0)
        item_price_safe = float(item.get("unit_price", 0) or 0)
        item_total_safe = float(item.get("total_amount", 0) or 0) or (item_qty_safe * item_price_safe)
        item_local = item_total_safe * exchange_rate
        tax_amount_local += round(item_local * float(item.get("tax_rate", 13) or 13) / (100 + float(item.get("tax_rate", 13) or 13)), 2)
    total_excl_tax_fc = round(total_amount_fc - tax_amount_local / exchange_rate, 2)
    total_excl_tax_local = round(total_amount_local - tax_amount_local, 2)

    order = SalesOrder(
        order_no=order_no,
        quote_id=data.get("quote_id"),
        customer_id=data["customer_id"],
        total_amount=total_amount_fc,
        total_amount_local=total_amount_local,
        total_amount_excl_tax=total_excl_tax_fc,
        total_amount_excl_tax_local=total_excl_tax_local,
        tax_amount=tax_amount_local,
        currency_id=currency_id,
        exchange_rate=exchange_rate,
        trade_term_id=data.get("trade_term_id"),
        payment_terms=data.get("payment_terms", "TT"),
        order_date=_parse_date(data.get("order_date")) or date.today(),
        delivery_date=_parse_date(data.get("delivery_date")),
        remark=data.get("remark", ""),
        created_by=current_user.display_name or current_user.username,
    )
    db.add(order)
    db.flush()

    # 创建明细行
    from app.models.sales import SalesOrderItem
    for item in items_data:
        item_qty = float(item.get("quantity", 0) or 0)
        item_price = float(item.get("unit_price", 0) or 0)
        item_total_raw = float(item.get("total_amount", 0) or 0)
        item_total = item_total_raw if item_total_raw else (item_qty * item_price)
        item_tax_rate_val = float(item.get("tax_rate", 13) or 13)
        item_excl = round(item_total / (1 + item_tax_rate_val / 100), 2)
        item_tax = round(item_total - item_excl, 2)
        so_item = SalesOrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item_qty,
            unit_price=item_price,
            unit_price_local=round(item_price * exchange_rate, 2),
            total_amount=item_total,
            total_amount_local=round(item_total * exchange_rate, 2),
            total_amount_excl_tax=item_excl,
            total_amount_excl_tax_local=round(item_excl * exchange_rate, 2),
            tax_rate=item.get("tax_rate", 13),
            tax_amount=item_tax,
            hs_code_id=item.get("hs_code_id"),
            remark=item.get("remark", ""),
        )
        db.add(so_item)

    db.commit()
    db.refresh(order)
    return {"id": order.id, "order_no": order.order_no, "message": "销售订单创建成功，请审核后下达生产"}


@router.get("/orders", tags=["销售管理"])
def list_sales_orders(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    status: str = Query(""), keyword: str = Query(""),
    date_from: str = Query(""), date_to: str = Query(""),
    amount_min: float = Query(None), amount_max: float = Query(None),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(SalesOrder)
    if status:
        query = query.filter(SalesOrder.status == status)
    if keyword:
        query = query.join(Customer).filter(
            SalesOrder.order_no.like(f"%{keyword}%") | Customer.name_cn.like(f"%{keyword}%"))
    if date_from:
        query = query.filter(SalesOrder.order_date >= date_from)
    if date_to:
        query = query.filter(SalesOrder.order_date <= date_to)
    if amount_min is not None:
        query = query.filter(SalesOrder.total_amount >= amount_min)
    if amount_max is not None:
        query = query.filter(SalesOrder.total_amount <= amount_max)
    total = query.count()
    items = query.order_by(SalesOrder.id.desc()).offset((page-1)*page_size).limit(page_size).all()

    # 实时计算已开票金额
    order_ids = [o.id for o in items]
    invoice_agg = {}
    if order_ids:
        rows = db.query(SalesInvoice.order_id, sa_func.coalesce(sa_func.sum(SalesInvoice.total_amount), 0)).filter(
            SalesInvoice.order_id.in_(order_ids)
        ).group_by(SalesInvoice.order_id).all()
        invoice_agg = {r[0]: float(r[1]) for r in rows}

    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": o.id, "order_no": o.order_no,
         "order_date": str(o.order_date),
         "customer_id": o.customer_id,
         "customer_name": o.customer.name_cn if o.customer else "",
         "item_count": len(o.items),
         "total_amount": o.total_amount or 0,
         "total_amount_local": o.total_amount_local or 0,
         "tax_amount": o.tax_amount or 0,
         "total_amount_excl_tax": o.total_amount_excl_tax or 0,
         "invoiced_amount": invoice_agg.get(o.id, 0),
         "uninvoiced_amount": (o.total_amount or 0) - invoice_agg.get(o.id, 0),
         "delivered_amount": sum((item.unit_price or 0) * (item.delivered_qty or 0) for item in o.items),
         "undelivered_amount": sum((item.unit_price or 0) * ((item.quantity or 0) - (item.delivered_qty or 0)) for item in o.items),
         "collected_amount": sum(ar.collected_amount or 0 for ar in db.query(AccountsReceivable).filter(AccountsReceivable.source_type == "sales_invoice", AccountsReceivable.source_id.in_([inv.id for inv in db.query(SalesInvoice).filter(SalesInvoice.order_id == o.id)]))),
         "uncollected_amount": sum(ar.balance or 0 for ar in db.query(AccountsReceivable).filter(AccountsReceivable.source_type == "sales_invoice", AccountsReceivable.source_id.in_([inv.id for inv in db.query(SalesInvoice).filter(SalesInvoice.order_id == o.id)]))),
         "currency_code": o.currency.code if o.currency else "CNY",
         "trade_term": o.trade_term.code if o.trade_term else "",
         "order_date": str(o.order_date),
         "status": o.status,
         "delivery_date": str(o.delivery_date) if o.delivery_date else "",
         "payment_terms": o.payment_terms or "",
        } for o in items
    ]}


@router.get("/orders/{order_id}", tags=["销售管理"])
def get_sales_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    from app.models.sales import SalesOrderItem
    result = {
        "id": order.id, "order_no": order.order_no,
        "customer_id": order.customer_id,
        "customer_name": order.customer.name_cn if order.customer else "",
        "total_amount": order.total_amount, "total_amount_local": order.total_amount_local,
        "tax_amount": order.tax_amount,
        "currency_id": order.currency_id,
        "exchange_rate": order.exchange_rate,
        "trade_term_id": order.trade_term_id,
        "trade_term": order.trade_term.code if order.trade_term else "",
        "payment_terms": order.payment_terms,
        "order_date": str(order.order_date) if order.order_date else "",
        "delivery_date": str(order.delivery_date) if order.delivery_date else "",
        "status": order.status, "remark": order.remark or "",
        "invoiced_amount": db.query(sa_func.coalesce(sa_func.sum(SalesInvoice.total_amount), 0)).filter(SalesInvoice.order_id == order.id).scalar() or 0,
        "uninvoiced_amount": max(0, (order.total_amount or 0) - (db.query(sa_func.coalesce(sa_func.sum(SalesInvoice.total_amount), 0)).filter(SalesInvoice.order_id == order.id).scalar() or 0)),
        "items": [
            {"id": item.id, "product_id": item.product_id,
             "product_name": item.product.name_cn if item.product else "",
             "product_code": item.product.code if item.product else "",
             "quantity": item.quantity, "unit_price": item.unit_price,
             "total_amount": item.total_amount,
             "tax_rate": item.tax_rate, "tax_amount": item.tax_amount,
             "total_amount_excl_tax": item.total_amount_excl_tax,
             "delivered_qty": item.delivered_qty or 0}
            for item in order.items
        ],
    }
    return result


@router.delete("/orders/{order_id}", tags=["销售管理"])
def delete_sales_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "仅待审核状态的订单允许删除")
    db.delete(order)
    db.commit()
    return {"message": "销售订单已删除"}


@router.post("/orders/{order_id}/approve", tags=["销售管理"])
def approve_sales_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """审核销售订单并生成生产订单"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "状态不正确")
    order.status = "已审"

    # 遍历明细行，每个产品生成一个生产订单
    from app.models.production import ProductionOrder
    from datetime import date
    today_str = date.today().strftime("%Y%m%d")
    count = db.query(ProductionOrder).filter(
        ProductionOrder.order_no.like(f"MO-{today_str}%")).count()
    mo_nos = []
    for item in order.items:
        count += 1
        prod = ProductionOrder(
            order_no=f"MO-{today_str}-{count:03d}",
            sales_order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            due_date=order.delivery_date,
            status="待排产",
            created_by=current_user.display_name or current_user.username,
        )
        db.add(prod)
        mo_nos.append(prod.order_no)
    db.commit()
    return {"message": f"订单已审核，已生成{len(mo_nos)}个生产订单", "production_order_nos": mo_nos}


# ==================== 销售发货（批次出库） ====================

@router.post("/deliveries", tags=["销售管理"])
def create_delivery(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售发货 — 指定批次出库、扣库存、更新订单明细已发数量"""
    order = db.query(SalesOrder).filter(SalesOrder.id == data["order_id"]).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")

    # 查找订单明细行
    order_item_id = data.get("order_item_id")
    order_item = None
    if order_item_id:
        order_item = db.query(SalesOrderItem).filter(
            SalesOrderItem.id == order_item_id,
            SalesOrderItem.order_id == order.id,
        ).first()
    if not order_item:
        raise HTTPException(400, "订单明细行不存在")

    # 检查未发货数量
    qty_to_ship = data["quantity"]
    remaining = order_item.quantity - (order_item.delivered_qty or 0)
    if qty_to_ship > remaining:
        raise HTTPException(400, f"发货数量{qty_to_ship}超过未发数量{remaining}")

    from datetime import date
    today_str = date.today().strftime("%Y%m%d")
    count = db.query(SalesDelivery).filter(SalesDelivery.delivery_no.like(f"SD-{today_str}%")).count()
    delivery_no = f"SD-{today_str}-{count+1:03d}"

    # 检查批次库存是否足够
    product_id = order_item.product_id
    inventory = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == data["batch_no"],
        WarehouseInventory.product_id == product_id,
    ).first()
    if not inventory or inventory.quantity < qty_to_ship:
        raise HTTPException(400, f"批次 {data['batch_no']} 库存不足")

    delivery = SalesDelivery(
        delivery_no=delivery_no,
        order_id=order.id,
        order_item_id=order_item.id,
        product_id=product_id,
        warehouse_id=data.get("warehouse_id") or inventory.warehouse_id,
        batch_no=data["batch_no"],
        quantity=qty_to_ship,
        unit_price=order_item.unit_price,
        amount=round(qty_to_ship * order_item.unit_price, 2),
        delivery_date=_parse_date(data.get("delivery_date")) or date.today(),
        operator=current_user.display_name or current_user.username,
        remark=data.get("remark", ""),
    )
    db.add(delivery)
    db.flush()

    # 扣库存
    old_qty = inventory.quantity
    issue_qty = qty_to_ship
    inv_unit_cost = inventory.unit_cost
    inventory.quantity -= issue_qty
    inventory.total_cost = round(inventory.quantity * inv_unit_cost, 2)

    # 库存流水（含成本）
    trans = StockTransaction(
        trans_type="sale_out",
        warehouse_id=inventory.warehouse_id,
        product_id=product_id,
        batch_no=data["batch_no"],
        quantity=-issue_qty,
        unit_cost=inv_unit_cost,
        total_amount=round(-issue_qty * inv_unit_cost, 2),
        before_qty=old_qty,
        after_qty=inventory.quantity,
        before_cost=round(old_qty * inv_unit_cost, 2),
        after_cost=round(inventory.quantity * inv_unit_cost, 2),
        source_doc_type="销售发货",
        source_doc_no=delivery_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 更新订单明细已发数量
    order_item.delivered_qty = (order_item.delivered_qty or 0) + qty_to_ship

    # 判断订单整体发货状态
    all_fully_shipped = all((item.delivered_qty or 0) >= item.quantity for item in order.items)
    any_shipped = any((item.delivered_qty or 0) > 0 for item in order.items)
    if all_fully_shipped:
        order.status = "已发货"
    elif any_shipped:
        order.status = "部分发货"

    db.commit()
    return {"id": delivery.id, "delivery_no": delivery_no, "message": "发货成功，库存已扣减"}


@router.get("/deliveries", tags=["销售管理"])
def list_deliveries(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    items = db.query(SalesDelivery).order_by(SalesDelivery.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": db.query(SalesDelivery).count(), "page": page, "page_size": page_size, "items": [
        {"id": d.id, "delivery_no": d.delivery_no,
         "order_no": d.order.order_no if d.order else "",
         "product_id": d.order.items[0].product_id if d.order and d.order.items else None,
         "product_name": d.order.items[0].product.name_cn if d.order and d.order.items and d.order.items[0].product else "",
         "batch_no": d.batch_no, "quantity": d.quantity,
         "unit_price": d.order.items[0].unit_price if d.order and d.order.items else 0,
         "amount": d.quantity * (d.order.items[0].unit_price or 0) if d.order and d.order.items else 0,
         "delivery_date": str(d.delivery_date), "status": d.status,
         "created_at": str(d.created_at)[:19] if d.created_at else "",
        } for d in items
    ]}


# ==================== 报关单 ====================

@router.post("/customs", tags=["销售管理"])
def create_customs(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建报关单"""
    order = db.query(SalesOrder).filter(SalesOrder.id == data["order_id"]).first()
    if not order:
        raise HTTPException(404, "订单不存在")

    customs = CustomsDeclaration(
        customs_no=data["customs_no"],
        order_id=order.id,
        delivery_id=data.get("delivery_id"),
        hs_code_id=data["hs_code_id"] or order.hs_code_id,
        declare_amount=data["declare_amount"] or order.total_amount,
        declare_currency=data.get("declare_currency") or order.currency_id,
        declare_date=_parse_date(data.get("declare_date")) or date.today(),
        customs_broker=data.get("customs_broker", ""),
        remark=data.get("remark", ""),
    )
    db.add(customs)
    db.commit()
    db.refresh(customs)

    # 更新发货状态
    if customs.delivery_id:
        delivery = db.query(SalesDelivery).filter(SalesDelivery.id == customs.delivery_id).first()
        if delivery:
            delivery.status = "已报关"
    return {"id": customs.id, "customs_no": data["customs_no"], "message": "报关单创建成功"}


@router.get("/customs", tags=["销售管理"])
def list_customs(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    refund_status: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(CustomsDeclaration)
    if refund_status:
        query = query.filter(CustomsDeclaration.refund_status == refund_status)
    total = query.count()
    items = query.order_by(CustomsDeclaration.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": c.id, "customs_no": c.customs_no,
         "order_id": c.order_id,
         "order_no": c.order.order_no if c.order else "",
         "customer_name": c.order.customer.name_cn if c.order and c.order.customer else "",
         "declare_amount": c.declare_amount,
         "declare_currency": c.declare_currency,
         "currency_code": c.currency.code if c.currency else "",
         "hs_code_id": c.hs_code_id,
         "hs_code": c.hs_code.hs_code if c.hs_code else "",
         "customs_broker": c.customs_broker or "",
         "declare_date": str(c.declare_date),
         "status": c.status,
         "refund_status": c.refund_status,
         "remark": c.remark or "",
         "delivery_id": c.delivery_id,
         "created_at": str(c.created_at) if c.created_at else "",
        } for c in items
    ]}


@router.get("/customs/{customs_id}", tags=["销售管理"])
def get_customs(customs_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(CustomsDeclaration).filter(CustomsDeclaration.id == customs_id).first()
    if not c:
        raise HTTPException(404, "报关单不存在")
    return {
        "id": c.id, "customs_no": c.customs_no,
        "order_id": c.order_id,
        "order_no": c.order.order_no if c.order else "",
        "customer_name": c.order.customer.name_cn if c.order and c.order.customer else "",
        "declare_amount": c.declare_amount,
        "declare_currency": c.declare_currency,
        "currency_code": c.currency.code if c.currency else "",
        "hs_code_id": c.hs_code_id,
        "hs_code": c.hs_code.hs_code if c.hs_code else "",
        "customs_broker": c.customs_broker or "",
        "declare_date": str(c.declare_date),
        "status": c.status,
        "refund_status": c.refund_status,
        "remark": c.remark or "",
        "delivery_id": c.delivery_id,
        "created_at": str(c.created_at) if c.created_at else "",
    }


@router.put("/customs/{customs_id}", tags=["销售管理"])
def update_customs(customs_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(CustomsDeclaration).filter(CustomsDeclaration.id == customs_id).first()
    if not c:
        raise HTTPException(404, "报关单不存在")
    for k, v in data.items():
        if k in ("customs_no", "order_id", "delivery_id", "hs_code_id", "declare_amount",
                 "declare_currency", "declare_date", "customs_broker", "status", "refund_status", "remark"):
            if k == "declare_date":
                v = _parse_date(v)
            setattr(c, k, v)
    db.commit()
    return {"message": "报关单已更新"}


@router.delete("/customs/{customs_id}", tags=["销售管理"])
def delete_customs(customs_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(CustomsDeclaration).filter(CustomsDeclaration.id == customs_id).first()
    if not c:
        raise HTTPException(404, "报关单不存在")
    db.delete(c)
    db.commit()
    return {"message": "报关单已删除"}


# ==================== 销售发票 → 应收 → 收款 ====================

@router.post("/invoices", tags=["销售管理"])
def create_sales_invoice(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """开票 → 自动生成应收"""
    order_id = data.get("order_id") or data.get("sales_order_id")
    # 确保金额字段为 float
    for k in ["amount", "amount_fc", "tax_amount", "total_amount"]:
        if k in data and data[k] is not None:
            data[k] = float(data[k])
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")

    invoice = SalesInvoice(
        invoice_no=data["invoice_no"],
        order_id=order.id,
        customer_id=order.customer_id,
        invoice_date=_parse_date(data.get("invoice_date")) or date.today(),
        invoice_type=data.get("invoice_type", "出口发票"),
        amount=data.get("amount", 0),
        amount_fc=data.get("amount_fc", data.get("amount", 0)),
        tax_rate=data.get("tax_rate", 13),
        tax_amount=data.get("tax_amount", 0),
        total_amount=data.get("total_amount", 0),
        currency_id=order.currency_id,
        remark=data.get("remark", ""),
    )
    db.add(invoice)
    db.flush()

    # 生成应收
    today_str = date.today().strftime("%Y%m%d")
    ar_count = db.query(sa_func.count(AccountsReceivable.id)).filter(
        AccountsReceivable.ar_no.like(f"AR-{today_str}%")
    ).scalar() or 0
    ar_no_str = f"AR-{today_str}-{ar_count+1:03d}"
    ar = AccountsReceivable(
        ar_no=ar_no_str,
        source_type="sales_invoice",
        source_id=invoice.id,
        customer_id=order.customer_id,
        amount=data.get("total_amount") or data["amount"],
        amount_fc=data.get("amount_fc", data.get("total_amount", data["amount"])),
        currency_id=order.currency_id,
        collected_amount=0,
        balance=data.get("total_amount") or data["amount"],
        due_date=order.delivery_date,
        status="未收款",
    )
    db.add(ar)

    db.commit()
    return {"id": invoice.id, "invoice_no": data["invoice_no"], "ar_no": ar_no_str, "message": "开票成功，应收已生成"}


@router.post("/ar/{ar_id}/cancel-collection", tags=["销售管理"])
def cancel_collection(ar_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消收款 — 按应收记录ID取消"""
    ar = db.query(AccountsReceivable).filter(AccountsReceivable.id == ar_id).first()
    if not ar:
        raise HTTPException(404, "应收记录不存在")
    
    coll = db.query(Collection).filter(Collection.id == ar.source_id).first()
    if coll:
        # 先删关联的核销记录
        allocations = db.query(CollectionAllocation).filter(CollectionAllocation.collection_id == coll.id).all()
        for alloc in allocations:
            db.delete(alloc)
        db.flush()
        db.delete(coll)
    
    # 回滚应收
    ar.collected_amount = 0
    ar.balance = ar.amount
    ar.status = "未收款"
    
    db.commit()
    return {"message": "收款已取消"}


@router.get("/invoices", tags=["销售管理"])
def list_sales_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(SalesInvoice)
    total = query.count()
    items = query.order_by(SalesInvoice.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    result = []
    for inv in items:
        order = db.query(SalesOrder).filter(SalesOrder.id == inv.order_id).first() if inv.order_id else None
        customer = db.query(Customer).filter(Customer.id == inv.customer_id).first() if inv.customer_id else None
        result.append({
            "id": inv.id, "invoice_no": inv.invoice_no,
            "customer_id": inv.customer_id,
            "customer_name": customer.name_cn if customer else "",
            "order_id": inv.order_id,
            "order_no": order.order_no if order else "",
            "tax_rate": getattr(inv, "tax_rate", 13) or 13,
            "amount": inv.amount, "tax_amount": getattr(inv, "tax_amount", 0) or 0,
            "total_amount": (inv.amount or 0) + (inv.tax_amount or 0),
            "invoice_date": str(inv.invoice_date) if inv.invoice_date else "",
            "status": inv.status, "remark": inv.remark or "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.put("/invoices/{invoice_id}", tags=["销售管理"])
def update_sales_invoice(invoice_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """修改销售发票（同步更新应收单、订单已开票金额）"""
    for k in ["amount", "tax_amount", "total_amount"]:
        if k in data and data[k] is not None:
            data[k] = float(data[k])
    inv = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "发票不存在")
    
    old_total = inv.total_amount or inv.amount or 0
    for field in ["invoice_no", "amount", "tax_rate", "tax_amount", "total_amount", "invoice_date", "remark"]:
        if field in data:
            val = data[field]
            if field == "invoice_date":
                val = _parse_date(val)
            setattr(inv, field, val)
    new_total = inv.total_amount or inv.amount or 0
    
    # 同步更新应收单
    ar = db.query(AccountsReceivable).filter(
        AccountsReceivable.source_type == "sales_invoice",
        AccountsReceivable.source_id == invoice_id,
    ).first()
    if ar:
        ar.amount = new_total
        ar.balance = new_total - (ar.collected_amount or 0)
        ar.status = "已收款" if (ar.collected_amount or 0) >= new_total else ("部分收款" if (ar.collected_amount or 0) > 0 else "未收款")

    db.commit()
    return {"message": "发票已更新"}


@router.delete("/invoices/{invoice_id}", tags=["销售管理"])
def delete_sales_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除销售发票（同步删除应收单、回滚订单已开票金额）"""
    inv = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).first()
    if not inv:
        raise HTTPException(404, "发票不存在")
    
    # 删除对应的应收单
    ar = db.query(AccountsReceivable).filter(
        AccountsReceivable.source_type == "sales_invoice",
        AccountsReceivable.source_id == invoice_id,
    ).first()
    if ar:
        db.delete(ar)

    db.delete(inv)
    db.commit()
    return {"message": "发票已删除，应收单已同步删除"}


@router.get("/ar", tags=["销售管理"])
def list_ar(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    status: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """应收账款列表"""
    query = db.query(AccountsReceivable)
    if status:
        query = query.filter(AccountsReceivable.status == status)
    total = query.count()
    items = query.order_by(AccountsReceivable.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    from app.models.foundation import Customer
    result = []
    for ar in items:
        customer = db.query(Customer).filter(Customer.id == ar.customer_id).first()
        # 查来源发票日期
        invoice_date = ""
        payment_terms = customer.payment_terms if customer else ""
        account_period = customer.account_period if customer else 0
        if ar.source_type == "sales_invoice" and ar.source_id:
            inv = db.query(SalesInvoice).filter(SalesInvoice.id == ar.source_id).first()
            if inv:
                invoice_date = str(inv.invoice_date) if inv.invoice_date else ""
        result.append({
            "id": ar.id, "ar_no": ar.ar_no or "",
            "source_type": ar.source_type,
            "customer_id": ar.customer_id,
            "customer_name": customer.name_cn if customer else "",
            "amount": ar.amount, "collected_amount": ar.collected_amount,
            "balance": ar.balance, "due_date": str(ar.due_date) if ar.due_date else "",
            "status": ar.status,
            "invoice_date": invoice_date,
            "payment_terms": payment_terms,
            "account_period": account_period,
            "collection_id": ar.source_id if ar.source_type == "sales_collection" else None,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/ar/collection-detail", tags=["销售管理"])
def list_ar_collection_detail(db: Session = Depends(get_db)):
    """应收账款收付款明细 — 应收与收款配对，按应收日期排序"""
    from app.models.sales import Collection, CollectionAllocation
    rows = db.query(AccountsReceivable, Collection, CollectionAllocation).outerjoin(
        CollectionAllocation, CollectionAllocation.ar_account_id == AccountsReceivable.id
    ).outerjoin(Collection, Collection.id == CollectionAllocation.collection_id
    ).order_by(AccountsReceivable.id).all()
    result, seen = [], set()
    for ar, coll, ca in rows:
        key = f"{ar.id}-{ca.id if ca else 0}"
        if key in seen: continue
        seen.add(key)
        cname = db.query(Customer.name_cn).filter(Customer.id == ar.customer_id).scalar() or ""
        result.append({"customer_name": cname,
            "ar_date": str(ar.created_at)[:10] if ar.created_at else "",
            "ar_no": ar.ar_no or "", "ar_id": ar.id, "customer_id": ar.customer_id,
            "ar_amount": ar.amount or 0,
            "cr_date": str(coll.collection_date) if coll and coll.collection_date else "",
            "collection_no": coll.collection_no if coll else "",
            "collection_id": coll.id if coll else None,
            "collected_amount": ca.allocated_amount if ca else 0,
        })
    result.sort(key=lambda r: r["ar_date"])
    return {"items": result}


@router.post("/collections", tags=["销售管理"])
def create_collection(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """收款登记 → 核销应收"""
    for k in ["amount", "amount_fc"]:
        if k in data and data[k] is not None:
            data[k] = float(data[k])
    from datetime import date
    today_str = date.today().strftime("%Y%m%d")
    count = db.query(Collection).filter(Collection.collection_no.like(f"CR-{today_str}%")).count()
    coll_no = f"CR-{today_str}-{count+1:03d}"

    collection = Collection(
        collection_no=coll_no,
        customer_id=data["customer_id"],
        collection_date=_parse_date(data.get("collection_date")) or date.today(),
        amount=data["amount"],
        amount_fc=data.get("amount_fc", data["amount"]),
        currency_id=data.get("currency_id"),
        exchange_rate=data.get("exchange_rate", 1),
        payment_method=data.get("payment_method", "银行转账"),
        remark=data.get("remark", ""),
        operator=current_user.display_name or current_user.username,
    )
    db.add(collection)
    db.flush()

    # 核销应收
    ar_id = data.get("ar_account_id")
    if ar_id:
        ar = db.query(AccountsReceivable).filter(AccountsReceivable.id == ar_id).first()
        if ar:
            alloc_amount = min(data["amount"], ar.balance)
            alloc = CollectionAllocation(
                collection_id=collection.id,
                ar_account_id=ar.id,
                allocated_amount=alloc_amount,
            )
            db.add(alloc)
            ar.collected_amount = (ar.collected_amount or 0) + alloc_amount
            ar.balance = ar.amount - ar.collected_amount
            ar.status = "已收款" if ar.balance <= 0 else "部分收款"

    db.commit()
    return {"id": collection.id, "collection_no": coll_no, "message": "收款登记成功"}


# ==================== 收款单管理 ====================

@router.get("/collections", tags=["销售管理"])
def list_collections(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(Collection)
    if keyword:
        query = query.join(Customer).filter(
            Collection.collection_no.like(f"%{keyword}%") | Customer.name_cn.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(Collection.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    from app.models.foundation import Customer
    result = []
    for c in items:
        customer = db.query(Customer).filter(Customer.id == c.customer_id).first()
        allocs = db.query(CollectionAllocation).filter(CollectionAllocation.collection_id == c.id).all()
        result.append({
            "id": c.id, "collection_no": c.collection_no,
            "customer_id": c.customer_id,
            "customer_name": customer.name_cn if customer else "",
            "collection_date": str(c.collection_date) if c.collection_date else "",
            "amount": c.amount, "amount_fc": c.amount_fc,
            "currency_id": c.currency_id,
            "exchange_rate": c.exchange_rate,
            "payment_method": c.payment_method,
            "remark": c.remark or "",
            "operator": c.operator or "",
            "allocated_amount": sum(a.allocated_amount or 0 for a in allocs),
            "created_at": str(c.created_at) if c.created_at else "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/collections/{collection_id}", tags=["销售管理"])
def get_collection(collection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise HTTPException(404, "收款单不存在")
    from app.models.foundation import Customer
    customer = db.query(Customer).filter(Customer.id == c.customer_id).first()
    allocs = db.query(CollectionAllocation).filter(CollectionAllocation.collection_id == c.id).all()
    ar_ids = [a.ar_account_id for a in allocs]
    ar_list = db.query(AccountsReceivable).filter(AccountsReceivable.id.in_(ar_ids)).all() if ar_ids else []
    ar_map = {}
    for ar in ar_list:
        cust = db.query(Customer).filter(Customer.id == ar.customer_id).first()
        ar_map[ar.id] = {"ar_no": ar.ar_no or "", "customer_name": cust.name_cn if cust else ""}
    return {
        "id": c.id, "collection_no": c.collection_no,
        "customer_id": c.customer_id, "customer_name": customer.name_cn if customer else "",
        "collection_date": str(c.collection_date) if c.collection_date else "",
        "amount": c.amount, "amount_fc": c.amount_fc,
        "currency_id": c.currency_id, "exchange_rate": c.exchange_rate,
        "payment_method": c.payment_method, "remark": c.remark or "",
        "operator": c.operator or "",
        "created_at": str(c.created_at) if c.created_at else "",
        "allocations": [{
            "id": a.id, "ar_account_id": a.ar_account_id,
            "ar_no": ar_map.get(a.ar_account_id, {}).get("ar_no", ""),
            "allocated_amount": a.allocated_amount,
        } for a in allocs],
    }


@router.put("/collections/{collection_id}", tags=["销售管理"])
def update_collection(collection_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise HTTPException(404, "收款单不存在")
    for field in ["payment_method", "remark", "collection_date"]:
        if field in data:
            val = data[field]
            if field == "collection_date":
                val = _parse_date(val)
            setattr(c, field, val)
    db.commit()
    return {"message": "收款单已更新"}


@router.delete("/collections/{collection_id}", tags=["销售管理"])
def delete_collection(collection_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Collection).filter(Collection.id == collection_id).first()
    if not c:
        raise HTTPException(404, "收款单不存在")

    # 获取核销记录并回滚应收
    allocs = db.query(CollectionAllocation).filter(CollectionAllocation.collection_id == c.id).all()
    for alloc in allocs:
        ar = db.query(AccountsReceivable).filter(AccountsReceivable.id == alloc.ar_account_id).first()
        if ar:
            ar.collected_amount = max(0, (ar.collected_amount or 0) - (alloc.allocated_amount or 0))
            ar.balance = ar.amount - ar.collected_amount
            ar.status = "已收款" if ar.balance <= 0 else ("部分收款" if ar.collected_amount > 0 else "未收款")
        db.delete(alloc)

    db.flush()
    db.delete(c)
    db.commit()
    return {"message": "收款单已删除，应收已回滚"}

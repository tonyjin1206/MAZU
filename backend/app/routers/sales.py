"""销售模块 API 路由 — 报价→订单→生产驱动→发货(批次)→报关→发票→应收→收款"""

from datetime import date, timedelta
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
from app.models.inventory import WarehouseInventory, StockTransaction, StockInOrder
from app.utils.auth import get_current_user
from app.utils.batch_no import generate_doc_no

router = APIRouter()


# ==================== 报价单 ====================

@router.post("/quotes", tags=["销售管理"])
def create_quote(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建报价单"""
    from app.utils.batch_no import generate_doc_no
    from app.models.sales import SalesQuote
    quote_no = generate_doc_no(db, "QT", SalesQuote, "quote_no")
    quote = SalesQuote(
        quote_no=quote_no,
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

def _recalc_order_totals(order):
    """按明细行重算订单头金额（改明细后必须调用；已停售行不参与）"""
    active_items = [i for i in order.items if i.production_status != "已停售"]
    total_amount_fc = round(sum((i.total_amount or 0) for i in active_items), 2)
    exchange_rate = order.exchange_rate or 1
    order.total_amount = total_amount_fc
    # 汇率/不含税换算保留 6 位精度参与计算，显示时前端 2 位
    order.total_amount_local = round(total_amount_fc * exchange_rate, 6)
    order.tax_amount = round(sum((i.tax_amount or 0) for i in active_items) * exchange_rate, 6)
    order.total_amount_excl_tax = round(sum((i.total_amount_excl_tax or 0) for i in active_items), 6)
    order.total_amount_excl_tax_local = round(
        sum((i.total_amount_excl_tax or 0) for i in active_items) * exchange_rate, 6)

@router.post("/orders", tags=["销售管理"])
def create_sales_order(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建销售订单（定制产品触发生产）"""
    from datetime import date, timedelta    # 汇率换算
    currency_id = data.get("currency_id") or 1

    from app.utils.batch_no import generate_doc_no
    from app.models.sales import SalesOrder
    order_no = generate_doc_no(db, "SO", SalesOrder, "order_no")

    exchange_rate = data.get("exchange_rate") or 1
    # 汇总明细行金额
    items_data = data.get("items", [])
    if not items_data:
        raise HTTPException(400, "订单至少包含一行明细")

    # 校验客户存在（外键保护）
    from app.models.foundation import Customer
    customer = db.query(Customer).filter(Customer.id == data["customer_id"]).first()
    if not customer:
        raise HTTPException(400, f"客户不存在: {data['customer_id']}")
    # 校验产品存在 + 数量合法性
    from app.models.foundation import Product
    for item in items_data:
        if not item.get("product_id"):
            raise HTTPException(400, "明细缺少产品")
        if not db.query(Product).filter(Product.id == item["product_id"]).first():
            raise HTTPException(400, f"产品不存在: {item['product_id']}")
        try:
            qty = float(item.get("quantity", 0) or 0)
        except (ValueError, TypeError):
            raise HTTPException(400, f"产品 {item['product_id']} 数量必须是数字")
        if qty <= 0:
            raise HTTPException(400, f"产品 {item['product_id']} 数量必须大于 0")
        try:
            price = float(item.get("unit_price", 0) or 0)
        except (ValueError, TypeError):
            raise HTTPException(400, f"产品 {item['product_id']} 单价必须是数字")
        if price < 0:
            raise HTTPException(400, f"产品 {item['product_id']} 单价不能为负数")
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
        tax_amount_local += round(item_local * float(item.get("tax_rate", 13) or 13) / (100 + float(item.get("tax_rate", 13) or 13)), 6)
    total_excl_tax_fc = round(total_amount_fc - tax_amount_local / exchange_rate, 6)
    total_excl_tax_local = round(total_amount_local - tax_amount_local, 6)

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
    for idx, item in enumerate(items_data, 1):
        item_qty = float(item.get("quantity", 0) or 0)
        item_price = float(item.get("unit_price", 0) or 0)
        item_total_raw = float(item.get("total_amount", 0) or 0)
        item_total = item_total_raw if item_total_raw else (item_qty * item_price)
        item_tax_rate_val = float(item.get("tax_rate", 13) or 13)
        item_excl = round(item_total / (1 + item_tax_rate_val / 100), 6)
        item_tax = round(item_total - item_excl, 6)
        so_item = SalesOrderItem(
            order_id=order.id,
            product_id=item["product_id"],
            quantity=item_qty,
            unit_price=item_price,
            unit_price_local=round(item_price * exchange_rate, 6),
            total_amount=item_total,
            total_amount_local=round(item_total * exchange_rate, 6),
            total_amount_excl_tax=item_excl,
            total_amount_excl_tax_local=round(item_excl * exchange_rate, 6),
            tax_rate=item.get("tax_rate", 13),
            tax_amount=item_tax,
            hs_code_id=item.get("hs_code_id"),
            batch_no=f"{order_no}-{idx:02d}",
            remark=item.get("remark", ""),
        )
        db.add(so_item)

    db.commit()
    db.refresh(order)
    return {"id": order.id, "order_no": order.order_no, "message": "销售订单创建成功，请审核后下达生产"}


@router.get("/orders", tags=["销售管理"])
def list_sales_orders(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
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
         "pending_count": sum(1 for i in o.items if not i.production_status or i.production_status == "未生产"),
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
    from app.models.inventory import StockInOrder
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
             "batch_no": item.batch_no or "",
             "delivered_qty": item.delivered_qty or 0,
             "delivery_confirmed": item.delivery_confirmed or 0,
             "received_qty": sum(
                 (s.received_qty or 0) for s in db.query(StockInOrder).filter(
                     StockInOrder.sales_item_id == item.id,
                     StockInOrder.status != "已退回",
                 ).all()),
             "production_status": item.production_status or "未生产",
             "claimed_from_batch": item.claimed_from_batch or ""}
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


@router.put("/orders/{order_id}", tags=["销售管理"])
def update_sales_order(order_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """修改销售订单（仅待审核状态允许）"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "仅待审核状态的订单允许修改")
    for k in ("customer_id", "currency_id", "trade_term_id", "payment_terms", "remark"):
        if k in data:
            setattr(order, k, data[k])
    if "order_date" in data and data["order_date"]:
        order.order_date = _parse_date(data["order_date"])
    if "delivery_date" in data and data["delivery_date"]:
        order.delivery_date = _parse_date(data["delivery_date"])
    if "exchange_rate" in data:
        order.exchange_rate = float(data["exchange_rate"])
    # 更新明细行
    items_data = data.get("items", [])
    sent_ids = set()
    for item_data in items_data:
        item_id = item_data.get("id")
        if item_id:
            # 更新已有行
            item = db.query(SalesOrderItem).filter(
                SalesOrderItem.id == item_id,
                SalesOrderItem.order_id == order_id,
            ).first()
            if not item:
                continue
            # 仅未生产状态允许修改
            if item.production_status not in (None, "", "未生产"):
                continue
        else:
            # 新增行
            item = SalesOrderItem(
                order_id=order_id,
                production_status="未生产",
            )
            db.add(item)
        if "quantity" in item_data:
            item.quantity = float(item_data["quantity"])
        if "unit_price" in item_data:
            item.unit_price = float(item_data["unit_price"])
        if "tax_rate" in item_data:
            item.tax_rate = float(item_data["tax_rate"])
        if "product_id" in item_data and item_data["product_id"]:
            item.product_id = item_data["product_id"]
        if "remark" in item_data:
            item.remark = item_data.get("remark", "")
        # 新行先 flush 获取 id
        if not item_id:
            db.flush()
        # 重算金额
        qty = item.quantity or 0
        price = item.unit_price or 0
        rate = item.tax_rate or 13
        item.total_amount = round(qty * price, 2)
        item.total_amount_excl_tax = round(item.total_amount / (1 + rate / 100), 2)
        item.tax_amount = round(item.total_amount - item.total_amount_excl_tax, 2)
        sent_ids.add(item.id)
    # 删除前端没传回的行（即被用户删除的行），仅限未生产状态
    existing = db.query(SalesOrderItem).filter(
        SalesOrderItem.order_id == order_id,
    ).all()
    for ex in existing:
        if ex.id not in sent_ids and ex.production_status in (None, "", "未生产"):
            db.delete(ex)
    # 明细有变动，重算订单头金额
    _recalc_order_totals(order)
    db.commit()
    db.refresh(order)
    return {"message": "销售订单已更新"}


@router.post("/orders/{order_id}/approve", tags=["销售管理"])
def approve_sales_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """审核销售订单（审核后明细行可转入库/转外发/变更）"""
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "订单不存在")
    if order.status != "待审核":
        raise HTTPException(400, "状态不正确")
    order.status = "已审"
    # 明细行初始化生产状态（待转入库/转外发）
    for item in order.items:
        if item.production_status in (None, "", "未生产"):
            item.production_status = "未生产"
    db.commit()
    return {"message": "订单已审核"}


@router.post("/orders/{order_id}/items/{item_id}/re-produce", tags=["销售管理"])
def reproduce_order_item(order_id: int, item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """重发生产 — 为指定明细行重新生成生产订单（仅已删除生产订单的明细行）"""
    from app.models.production import ProductionOrder
    from app.utils.batch_no import generate_doc_no
    # 实时查最新状态
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id,
        SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    if item.production_status != "未生产":
        raise HTTPException(400, f"该明细行当前生产状态为「{item.production_status}」，不允许重发生产")
    # 检查是否已有活跃的生产订单
    existing = db.query(ProductionOrder).filter(
        ProductionOrder.sales_order_item_id == item_id,
        ProductionOrder.status.in_(["待排产", "已排产", "生产中", "已完成", "部分入库", "已入库"]),
    ).first()
    if existing:
        raise HTTPException(400, f"该明细行已有活跃生产订单（{existing.order_no}），不允许重复生成")
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    prod = ProductionOrder(
        order_no=generate_doc_no(db, "MO", ProductionOrder, "order_no"),
        sales_order_id=order.id,
        sales_order_item_id=item.id,
        product_id=item.product_id,
        quantity=item.quantity,
        due_date=order.delivery_date,
        status="待排产",
        created_by=current_user.display_name or current_user.username,
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return {"id": prod.id, "order_no": prod.order_no, "message": f"已重新生成生产订单 {prod.order_no}"}


# ==================== 销售明细行：转入库 / 转外发 / 变更 ====================

@router.post("/orders/{order_id}/items/{item_id}/stock-in", tags=["销售管理"])
def notify_stock_in(order_id: int, item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细「转直采」— 仅推送单据到「销售订单转采购」页（不生成采购单，采购在转采购页进行）"""
    from app.models.inventory import StockInOrder
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id, SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status != "已审":
        raise HTTPException(400, "订单审核通过后才能转直采")
    if item.production_status not in (None, "", "未生产"):
        raise HTTPException(400, f"该明细行状态为「{item.production_status}」，不能转直采")
    item.production_status = "已通知入库"
    db.commit()
    return {"message": "已转直采，请到「采购管理 → 销售订单转采购」办理采购"}


@router.post("/orders/{order_id}/items/{item_id}/outsource", tags=["销售管理"])
def notify_outsource(order_id: int, item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细「转外发」— 生成委外订单（草稿），明细状态→已通知外发"""
    from app.models.production import OutsourceOrder
    from app.utils.batch_no import generate_doc_no
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id, SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status != "已审":
        raise HTTPException(400, "订单审核通过后才能转外发")
    if item.production_status not in (None, "", "未生产"):
        raise HTTPException(400, f"该明细行状态为「{item.production_status}」，不能转外发")
    item.production_status = "已通知外发"
    db.commit()
    return {"message": "已转外发，请到「委外管理 → 销售订单转委外」办理委外"}


# ==================== 备货批次认领（场景2：货先进来，后期挂销售单） ====================

@router.post("/orders/{order_id}/items/{item_id}/claim-batch", tags=["销售管理"])
def claim_batch(order_id: int, item_id: int, data: dict,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细「认领库存」— 把库里的备货批次（FG-xxx 无归属）改名挂到本销售行，成本随之归集

    data: {batch_no: str, quantity: float}
    认领后库存批次号变为本销售明细批次号（SO-xxx-01），发货/追溯/锁定全部按批次自动生效。
    支持部分认领（批次自动拆分），也支持多次认领不同批次。
    """
    from app.utils.batch_no import generate_doc_no
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id, SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if order.status != "已审":
        raise HTTPException(400, "订单审核通过后才能认领库存")
    if item.production_status not in (None, "", "未生产", "部分入库"):
        raise HTTPException(400, f"该明细行状态为「{item.production_status}」，不能认领库存")
    if not item.batch_no:
        raise HTTPException(400, "该明细行没有批次号，无法认领")

    batch_no = (data.get("batch_no") or "").strip()
    quantity = float(data.get("quantity") or 0)
    if not batch_no:
        raise HTTPException(400, "请选择要认领的库存批次")
    if quantity <= 0:
        raise HTTPException(400, "认领数量必须大于 0")

    # 该批次必须是备货批次（无销售明细归属）
    owned = db.query(SalesOrderItem).filter(SalesOrderItem.batch_no == batch_no).first()
    if owned:
        raise HTTPException(400, f"批次 {batch_no} 已归属订单「{owned.order.order_no}」，不能认领")

    invs = db.query(WarehouseInventory).filter(
        WarehouseInventory.product_id == item.product_id,
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.quantity > 0,
    ).order_by(WarehouseInventory.id.asc()).all()
    if not invs:
        raise HTTPException(400, f"产品「{item.product.name_cn if item.product else ''}」没有可认领的库存批次 {batch_no}")
    total = round(sum((i.quantity or 0) for i in invs), 2)
    if quantity > total:
        raise HTTPException(400, f"认领数量 {quantity} 超过该批次库存 {total}")

    # 逐行拆分/改名（FIFO 按 id 顺序）
    remaining = quantity
    total_cost_move = 0.0
    for inv in invs:
        if remaining <= 0:
            break
        q = round(inv.quantity or 0, 2)
        if q <= remaining:
            # 整行改挂到销售批次
            inv.batch_no = item.batch_no
            inv.claimed_from_batch = batch_no
            total_cost_move += round((inv.total_cost or 0), 2)
            remaining = round(remaining - q, 2)
        else:
            # 拆行：原批次留 (q - remaining)，剩余部分建新行挂销售批次
            move_qty = remaining
            move_cost = round((inv.unit_cost or 0) * move_qty, 2)
            new_inv = WarehouseInventory(
                warehouse_id=inv.warehouse_id,
                product_id=inv.product_id,
                batch_no=item.batch_no,
                quantity=move_qty,
                unit_cost=inv.unit_cost,
                total_cost=move_cost,
                in_date=inv.in_date,
                source_type=inv.source_type,
                source_doc_id=inv.source_doc_id,
                receipt_no=None,
                claimed_from_batch=batch_no,
            )
            db.add(new_inv)
            inv.quantity = round(q - move_qty, 2)
            inv.total_cost = round((inv.total_cost or 0) - move_cost, 2)
            total_cost_move += move_cost
            remaining = 0

    # 生成流水：原批次出 / 销售批次入（数量同向记录，方向靠 batch_no 区分）
    unit_cost = invs[0].unit_cost or 0
    db.add(StockTransaction(
        trans_type="batch_claim", warehouse_id=invs[0].warehouse_id,
        product_id=item.product_id, batch_no=batch_no,
        quantity=-quantity, unit_cost=unit_cost,
        total_amount=round(-quantity * unit_cost, 2),
        before_qty=total, after_qty=round(total - quantity, 2),
        before_cost=round(total * unit_cost, 2), after_cost=round((total - quantity) * unit_cost, 2),
        source_doc_type="批次认领", source_doc_no=order.order_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    ))
    db.add(StockTransaction(
        trans_type="batch_claim", warehouse_id=invs[0].warehouse_id,
        product_id=item.product_id, batch_no=item.batch_no,
        quantity=quantity, unit_cost=unit_cost,
        total_amount=round(quantity * unit_cost, 2),
        before_qty=0, after_qty=quantity,
        before_cost=0, after_cost=round(quantity * unit_cost, 2),
        source_doc_type="批次认领", source_doc_no=order.order_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    ))

    # 明细状态：认领数量 >= 订单数量 → 已入库；不足 → 部分入库（可继续认领/转入库）
    claimed_total = quantity
    item.claimed_from_batch = batch_no
    if claimed_total >= (item.quantity or 0):
        item.production_status = "已入库"
    elif item.production_status != "已入库":
        item.production_status = "部分入库"
    db.commit()
    return {"message": f"已认领批次 {batch_no} 共 {quantity}，货已挂到本销售单，可在发货工作台发货"}


@router.post("/orders/{order_id}/items/{item_id}/unclaim-batch", tags=["销售管理"])
def unclaim_batch(order_id: int, item_id: int,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售明细「解绑认领」— 未发货的认领库存退回原备货批次"""
    from app.utils.batch_no import generate_doc_no
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id, SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not order:
        raise HTTPException(404, "销售订单不存在")
    if not item.claimed_from_batch:
        raise HTTPException(400, "该明细行未认领库存，无需解绑")
    if (item.delivered_qty or 0) > 0:
        raise HTTPException(400, "该明细行已发货，不能解绑")

    # 找到本销售批次下所有认领来的库存行，退回各自原批次
    invs = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == item.batch_no,
        WarehouseInventory.claimed_from_batch.isnot(None),
        WarehouseInventory.claimed_from_batch != "",
        WarehouseInventory.quantity > 0,
    ).order_by(WarehouseInventory.id.asc()).all()
    if not invs:
        raise HTTPException(400, "未找到可退回的认领库存（可能已全部发出）")

    total_back = 0.0
    for inv in invs:
        orig = inv.claimed_from_batch
        q = round(inv.quantity or 0, 2)
        # 找原批次同仓行（合并）或新建
        target = db.query(WarehouseInventory).filter(
            WarehouseInventory.warehouse_id == inv.warehouse_id,
            WarehouseInventory.product_id == inv.product_id,
            WarehouseInventory.batch_no == orig,
        ).first()
        if target:
            target.quantity = round((target.quantity or 0) + q, 2)
            target.total_cost = round((target.total_cost or 0) + (inv.total_cost or 0), 2)
            db.delete(inv)
        else:
            inv.batch_no = orig
            inv.claimed_from_batch = None
        total_back += q

    unit_cost = invs[0].unit_cost or 0
    db.add(StockTransaction(
        trans_type="batch_claim", warehouse_id=invs[0].warehouse_id,
        product_id=item.product_id, batch_no=item.batch_no,
        quantity=-total_back, unit_cost=unit_cost,
        total_amount=round(-total_back * unit_cost, 2),
        before_qty=total_back, after_qty=0,
        before_cost=round(total_back * unit_cost, 2), after_cost=0,
        source_doc_type="批次解绑", source_doc_no=order.order_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    ))
    db.add(StockTransaction(
        trans_type="batch_claim", warehouse_id=invs[0].warehouse_id,
        product_id=item.product_id, batch_no=item.claimed_from_batch,
        quantity=total_back, unit_cost=unit_cost,
        total_amount=round(total_back * unit_cost, 2),
        before_qty=0, after_qty=total_back,
        before_cost=0, after_cost=round(total_back * unit_cost, 2),
        source_doc_type="批次解绑", source_doc_no=order.order_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    ))

    item.claimed_from_batch = None
    item.production_status = "未生产"
    db.commit()
    return {"message": f"已解绑，{total_back} 退回原批次"}


# ==================== 销售发货（批次出库） ====================

@router.post("/deliveries", tags=["销售管理"])
def create_delivery(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售发货 — 指定批次出库、扣库存、更新订单明细已发数量。
    可发量规则（峰子拍板）：
    - 发货数量不按订单量限制，只看批次可发量（物理库存 - 其他订单锁定）
    - 批次归属订单未确认完成时，(订单量-已发) 部分锁定给该订单，超收部分可发其他订单
    - 归属订单确认完成后锁定解除，剩余库存全部开放
    - 已确认完成的产品行不能再发货"""
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

    # 已确认完成的行不能再发货
    if order_item.delivery_confirmed:
        raise HTTPException(400, "该产品已确认发货完成，不能再发货（如需补发请先撤销确认）")

    qty_to_ship = float(data["quantity"])
    if qty_to_ship <= 0:
        raise HTTPException(400, "发货数量必须大于0")
    product_id = order_item.product_id
    batch_no = data["batch_no"]

    # 批次库存（同一批次可能有多条库存记录，按净数量合计）
    invs = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.product_id == product_id,
    ).all()
    stock = round(sum((i.quantity or 0) for i in invs), 2)
    if stock <= 0:
        raise HTTPException(400, f"批次 {batch_no} 库存不足")

    # 锁定计算：批次归属其他订单且该行未确认完成时，(订单量-已发) 锁定
    owner = db.query(SalesOrderItem).filter(SalesOrderItem.batch_no == batch_no).first()
    locked = 0
    if owner and owner.order_id != order.id and not owner.delivery_confirmed:
        locked = max(0, round((owner.quantity or 0) - (owner.delivered_qty or 0), 2))
    available = max(0, round(stock - locked, 2))
    if qty_to_ship > available:
        tip = f"（其中{locked}已锁定给订单 {owner.order.order_no}）" if locked else ""
        raise HTTPException(400, f"发货数量{qty_to_ship}超过该批次可发数量{available}{tip}")

    from app.models.sales import SalesDelivery
    delivery_no = generate_doc_no(db, "SD", SalesDelivery, "delivery_no")

    delivery = SalesDelivery(
        delivery_no=delivery_no,
        order_id=order.id,
        order_item_id=order_item.id,
        product_id=product_id,
        warehouse_id=data.get("warehouse_id") or (invs[0].warehouse_id if invs else None),
        batch_no=batch_no,
        quantity=qty_to_ship,
        unit_price=order_item.unit_price,
        amount=round(qty_to_ship * (order_item.unit_price or 0), 2),
        delivery_date=_parse_date(data.get("delivery_date")) or date.today(),
        operator=current_user.display_name or current_user.username,
        remark=data.get("remark", ""),
    )
    db.add(delivery)
    db.flush()

    # 扣库存：按记录顺序（先进先出）循环扣减，每条记录生成一条流水
    remaining = qty_to_ship
    for inv in sorted(invs, key=lambda x: x.id):
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
            trans_type="sale_out",
            warehouse_id=inv.warehouse_id,
            product_id=product_id,
            batch_no=batch_no,
            quantity=-take,
            unit_cost=inv_unit_cost,
            total_amount=round(-take * inv_unit_cost, 2),
            before_qty=old_qty,
            after_qty=inv.quantity,
            before_cost=round(old_qty * inv_unit_cost, 2),
            after_cost=round(inv.quantity * inv_unit_cost, 2),
            source_doc_type="销售发货",
            source_doc_no=delivery_no,
            trans_no=generate_doc_no(db, "ST"),
            operator=current_user.display_name or current_user.username,
        )
        db.add(trans)
        remaining = round(remaining - take, 2)

    # 更新订单明细已发数量
    order_item.delivered_qty = round((order_item.delivered_qty or 0) + qty_to_ship, 2)

    # 订单状态以人工确认为准：全部明细确认完成=已发货；有发货/确认记录=部分发货
    _update_order_delivery_status(order)

    db.commit()
    return {"id": delivery.id, "delivery_no": delivery_no, "message": "发货成功，库存已扣减"}


def _update_order_delivery_status(order):
    """按明细行人工确认状态更新订单发货状态（已发货=全部行确认完成）"""
    items = order.items
    if not items:
        return
    if all((i.delivery_confirmed or 0) == 1 for i in items):
        order.status = "已发货"
    elif any((i.delivery_confirmed or 0) == 1 or (i.delivered_qty or 0) > 0 for i in items):
        order.status = "部分发货"


@router.post("/orders/{order_id}/items/{item_id}/delivery-confirm", tags=["销售管理"])
def confirm_order_item_delivery(
    order_id: int, item_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """确认/撤销 明细行发货完成（按产品行）。
    确认后：该行不能再发货，批次锁定解除（剩余库存开放给其他订单）。
    撤销后：恢复锁定，可继续发货。"""
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id,
        SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "订单明细行不存在")

    confirmed = bool(data.get("confirmed", True))
    if confirmed:
        if item.delivery_confirmed:
            raise HTTPException(400, "该产品行已确认过发货完成")
        item.delivery_confirmed = 1
    else:
        if not item.delivery_confirmed:
            raise HTTPException(400, "该产品行未确认过发货完成")
        item.delivery_confirmed = 0

    order = item.order
    _update_order_delivery_status(order)
    db.commit()
    return {
        "message": "已确认发货完成" if confirmed else "已撤销确认",
        "delivery_confirmed": item.delivery_confirmed,
        "order_status": order.status,
    }


@router.get("/deliveries", tags=["销售管理"])
def list_deliveries(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    order_item_id: int | None = Query(None, description="按订单明细行过滤（发货记录下表用）"),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    q = db.query(SalesDelivery)
    if order_item_id:
        q = q.filter(SalesDelivery.order_item_id == order_item_id)
    items = q.order_by(SalesDelivery.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": q.count(), "page": page, "page_size": page_size, "items": [
        {"id": d.id, "delivery_no": d.delivery_no,
         "order_no": d.order.order_no if d.order else "",
         "order_item_id": d.order_item_id,
         "product_id": d.product_id,
         "product_name": d.order_item.product.name_cn if d.order_item and d.order_item.product else "",
         "batch_no": d.batch_no, "quantity": d.quantity,
         "unit_price": d.unit_price or 0,
         "amount": d.amount or 0,
         "is_return": d.is_return or 0,
         "return_of_delivery_id": d.return_of_delivery_id,
         "delivery_date": str(d.delivery_date), "status": d.status,
         "remark": d.remark or "",
         "created_at": str(d.created_at)[:19] if d.created_at else "",
        } for d in items
    ]}


# ==================== 发货工作台（峰子 2026-08-03 拍板：上=产品发货记录，下=发货单明细） ====================

@router.get("/delivery-workbench", tags=["销售管理"])
def delivery_workbench(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
    keyword: str = "", status: str = "",
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """发货工作台上表：所有已审核销售订单的明细行（一行一产品）。
    字段：订单量/已入库/已发货/未发货/实物库存(该产品全部库存)/可用库存(实物-所有未完成订单锁定)/确认状态"""
    from app.models.inventory import StockInOrder as _SIO

    q = db.query(SalesOrderItem, SalesOrder, Product, Customer).join(
        SalesOrder, SalesOrderItem.order_id == SalesOrder.id,
    ).join(Product, SalesOrderItem.product_id == Product.id).join(
        Customer, SalesOrder.customer_id == Customer.id,
    ).filter(SalesOrder.status != "待审核")
    if status:
        q = q.filter(SalesOrder.status == status)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(sa_func.or_(
            SalesOrder.order_no.like(like),
            SalesOrderItem.batch_no.like(like),
            Product.name_cn.like(like),
            Product.code.like(like),
            Customer.name_cn.like(like),
        ))
    total = q.count()
    rows = q.order_by(SalesOrder.id.desc(), SalesOrderItem.id).offset((page-1)*page_size).limit(page_size).all()

    result = []
    for item, order, prod, cust in rows:
        # 已入库：该明细行累计收货
        received = sum(
            (s.received_qty or 0) for s in db.query(_SIO).filter(
                _SIO.sales_item_id == item.id, _SIO.status != "已退回").all()
        )
        # 实物库存：该产品所有批次库存净合计（含负数记录，峰子口径=实际在库）
        phys = db.query(sa_func.coalesce(sa_func.sum(WarehouseInventory.quantity), 0)).filter(
            WarehouseInventory.product_id == item.product_id,
        ).scalar() or 0
        # 可用库存 = 实物库存 - 该产品所有未确认完成明细行的锁定量之和
        locked_rows = db.query(SalesOrderItem).filter(
            SalesOrderItem.product_id == item.product_id,
            SalesOrderItem.delivery_confirmed == 0,
        ).all()
        locked = sum(max(0, (r.quantity or 0) - (r.delivered_qty or 0)) for r in locked_rows)
        available = max(0, round(float(phys) - locked, 2))
        result.append({
            "item_id": item.id,
            "order_id": order.id,
            "order_no": order.order_no,
            "customer_name": cust.name_cn if cust else "",
            "product_id": item.product_id,
            "product_name": prod.name_cn if prod else "",
            "product_code": prod.code if prod else "",
            "batch_no": item.batch_no or "",
            "quantity": item.quantity,
            "received_qty": round(received, 2),
            "delivered_qty": item.delivered_qty or 0,
            "undelivered_qty": round((item.quantity or 0) - (item.delivered_qty or 0), 2),
            "physical_stock": round(float(phys), 2),
            "available_stock": available,
            "delivery_confirmed": item.delivery_confirmed or 0,
            "order_status": order.status,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.post("/deliveries/return", tags=["销售管理"])
def create_delivery_return(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """销售退货（峰子 2026-08-03 拍板）：
    - 退到原批次，生成退货发货单（is_return=1）
    - 退货数量≤已发数量，多次退货合计≤已发数量
    - 库存加回、已发数量扣减、自动撤销发货完成确认（涉及补货时可继续发货）"""
    item = db.query(SalesOrderItem).filter(SalesOrderItem.id == data.get("order_item_id")).first()
    if not item:
        raise HTTPException(400, "订单明细行不存在")

    qty = float(data["quantity"])
    if qty <= 0:
        raise HTTPException(400, "退货数量必须大于0")
    batch_no = data["batch_no"]

    # 该批次必须是该行正常发货过的批次（退到原批次）
    shipped = db.query(SalesDelivery).filter(
        SalesDelivery.order_item_id == item.id,
        SalesDelivery.batch_no == batch_no,
        SalesDelivery.is_return == 0,
    ).order_by(SalesDelivery.id).all()
    if not shipped:
        raise HTTPException(400, f"批次 {batch_no} 没有该产品的正常发货记录")

    # 多次退货合计 ≤ 已发数量
    returned = db.query(sa_func.coalesce(sa_func.sum(SalesDelivery.quantity), 0)).filter(
        SalesDelivery.order_item_id == item.id,
        SalesDelivery.is_return == 1,
    ).scalar() or 0
    if qty + (returned or 0) > (item.delivered_qty or 0):
        raise HTTPException(400, f"退货数量{qty}超限：该产品已发{(item.delivered_qty or 0)}，已退{(returned or 0)}，最多再退{round((item.delivered_qty or 0) - (returned or 0), 2)}")

    # 生成退货发货单（红字单：is_return=1）
    delivery_no = generate_doc_no(db, "SD", SalesDelivery, "delivery_no")
    src = shipped[0]
    ret = SalesDelivery(
        delivery_no=delivery_no,
        order_id=item.order_id,
        order_item_id=item.id,
        product_id=item.product_id,
        warehouse_id=src.warehouse_id,
        batch_no=batch_no,
        quantity=qty,
        unit_price=item.unit_price,
        amount=round(qty * (item.unit_price or 0), 2),
        delivery_date=_parse_date(data.get("delivery_date")) or date.today(),
        operator=current_user.display_name or current_user.username,
        remark=data.get("remark", ""),
        status="已退货",
        is_return=1,
        return_of_delivery_id=src.id,
    )
    db.add(ret)
    db.flush()

    # 库存加回原批次（优先加到正数记录，全发空则新建一条）
    inv = db.query(WarehouseInventory).filter(
        WarehouseInventory.batch_no == batch_no,
        WarehouseInventory.product_id == item.product_id,
        WarehouseInventory.quantity > 0,
    ).order_by(WarehouseInventory.id).first()
    if inv:
        old_qty = inv.quantity
        unit_cost = inv.unit_cost or 0
        wh_id = inv.warehouse_id
        inv.quantity = round(old_qty + qty, 2)
        inv.total_cost = round(inv.quantity * unit_cost, 2)
        after_qty = inv.quantity
    else:
        from datetime import date as _date
        old_qty = 0
        unit_cost = 0
        wh_id = src.warehouse_id
        inv = WarehouseInventory(
            warehouse_id=wh_id,
            product_id=item.product_id,
            batch_no=batch_no,
            quantity=qty,
            unit_cost=0,
            total_cost=0,
            in_date=_date.today(),
            source_type="sale_return",
            source_doc_id=ret.id,
            receipt_no=delivery_no,
        )
        db.add(inv)
        db.flush()
        after_qty = qty

    # 库存流水（正数入库）
    trans = StockTransaction(
        trans_type="sale_return",
        warehouse_id=wh_id,
        product_id=item.product_id,
        batch_no=batch_no,
        quantity=qty,
        unit_cost=unit_cost,
        total_amount=round(qty * unit_cost, 2),
        before_qty=old_qty,
        after_qty=after_qty,
        before_cost=round(old_qty * unit_cost, 2),
        after_cost=round(after_qty * unit_cost, 2),
        source_doc_type="销售退货",
        source_doc_no=delivery_no,
        trans_no=generate_doc_no(db, "ST"),
        operator=current_user.display_name or current_user.username,
    )
    db.add(trans)

    # 已发数量扣减 + 自动撤销确认（补货时可直接继续发货）
    item.delivered_qty = round((item.delivered_qty or 0) - qty, 2)
    if item.delivery_confirmed:
        item.delivery_confirmed = 0
    _update_order_delivery_status(item.order)
    db.commit()
    return {"id": ret.id, "delivery_no": delivery_no, "message": "退货成功，库存已加回"}


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

    # 生成应收（计算到期日 = 发票日期 + 客户账期）
    customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
    due_days = customer.account_period if customer else 30
    due_date = (invoice.invoice_date or date.today()) + timedelta(days=due_days)
    from app.utils.batch_no import generate_doc_no
    from app.models.sales import AccountsReceivable
    ar_no_str = generate_doc_no(db, "AR", AccountsReceivable, "ar_no")
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
        due_date=due_date,
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
    
    # 已收款的发票禁止改金额（先退收款单，保证应收一致）
    ar0 = db.query(AccountsReceivable).filter(
        AccountsReceivable.source_type == "sales_invoice",
        AccountsReceivable.source_id == invoice_id,
    ).first()
    if ar0 and (ar0.collected_amount or 0) > 0 and any(k in data for k in ["amount", "tax_amount", "total_amount"]):
        raise HTTPException(400, f"该发票对应应收单已收款 ¥{ar0.collected_amount}，不能修改金额；请先删除收款单")

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
        if (ar.collected_amount or 0) > 0:
            raise HTTPException(400, f"该发票对应应收单已收款 ¥{ar.collected_amount}，请先删除收款单再删除发票")
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
    from app.utils.batch_no import generate_doc_no
    from app.models.sales import Collection
    coll_no = generate_doc_no(db, "CR", Collection, "collection_no")

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


# ==================== 销售订单明细行 ====================

@router.get("/order-items", tags=["销售管理"])
def list_order_items(
    page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200),
    production_status: str = Query(""), keyword: str = Query(""),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """按销售明细行查询（含生产状态）"""
    q = db.query(SalesOrderItem).join(SalesOrder).join(Customer)
    if production_status:
        q = q.filter(SalesOrderItem.production_status == production_status)
    if keyword:
        q = q.filter(
            SalesOrder.order_no.like(f"%{keyword}%")
            | Customer.name_cn.like(f"%{keyword}%")
            | Product.name_cn.like(f"%{keyword}%")
        )
    total = q.count()
    items = q.order_by(SalesOrderItem.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 查询每个明细行是否有活跃的生产订单
    from app.models.production import ProductionOrder
    item_ids = [item.id for item in items]
    active_mo_items = set()
    if item_ids:
        rows = db.query(ProductionOrder.sales_order_item_id).filter(
            ProductionOrder.sales_order_item_id.in_(item_ids),
            ProductionOrder.status.in_(["待排产", "已排产", "生产中", "已完成", "部分入库", "已入库"]),
        ).all()
        active_mo_items = {r[0] for r in rows}
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {
            "id": item.id, "order_id": item.order_id,
            "order_no": item.order.order_no if item.order else "",
            "order_date": str(item.order.order_date) if item.order and item.order.order_date else "",
            "customer_id": item.order.customer_id if item.order else None,
            "customer_name": item.order.customer.name_cn if item.order and item.order.customer else "",
            "product_id": item.product_id,
            "product_name": item.product.name_cn if item.product else "",
            "product_code": item.product.code if item.product else "",
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_amount": item.total_amount,
            "delivered_qty": item.delivered_qty or 0,
            "production_status": item.production_status or "未生产",
            "has_active_mo": item.id in active_mo_items,
        }
        for item in items
    ]}


@router.put("/orders/{order_id}/items/{item_id}", tags=["销售管理"])
def update_order_item(
    order_id: int, item_id: int, data: dict,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    """变更销售订单明细行 — 改数量 / 停售

    规则：
    - 未开始（无下游单据）：数量随便改，可停售
    - 已通知（有待入库单/委外单）：必须先退回/删除下游单据，明细回「未生产」后才能变更
    - 已入库一部分：只能改数量（新数量 ≥ 已入库数），不能停售
    - 已确认完成：不能变更
    """
    from app.models.inventory import StockInOrder
    from app.models.production import OutsourceOrder
    from app.models.purchase import PurchaseOrderItem, PurchaseOrder as PoOrder
    item = db.query(SalesOrderItem).filter(
        SalesOrderItem.id == item_id, SalesOrderItem.order_id == order_id,
    ).first()
    if not item:
        raise HTTPException(404, "明细行不存在")
    if item.production_status == "已停售":
        raise HTTPException(400, "该明细行已停售，不能变更")

    # 单据在「转采购/转委外」页（已转直采/已转外发）→ 必须先退回才能变更
    if item.production_status == "已通知入库":
        raise HTTPException(400, "该明细行已转直采，请先到「采购管理 → 销售订单转采购」退回后再变更")
    if item.production_status == "已通知外发":
        raise HTTPException(400, "该明细行已转外发，请先到「委外管理 → 销售订单转委外」退回后再变更")

    # 有活跃采购单引用（销售订单转采购生成）→ 必须先退回采购单
    active_po = db.query(PurchaseOrderItem).join(PoOrder, PoOrder.id == PurchaseOrderItem.order_id).filter(
        PurchaseOrderItem.sales_item_id == item_id,
        PoOrder.status != "已关闭",
    ).first()
    if active_po:
        raise HTTPException(400, f"该明细行已关联采购订单（{active_po.order.order_no}），请先退回采购订单再变更")

    # 已入库数量（成品入库累计收货，不含已退回）
    stock_ins = db.query(StockInOrder).filter(
        StockInOrder.sales_item_id == item_id,
        StockInOrder.status != "已退回",
    ).all()
    received_total = sum((s.received_qty or 0) for s in stock_ins)
    active_stock_ins = [s for s in stock_ins if s.status in ("待入库", "部分入库")]
    active_outsources = db.query(OutsourceOrder).filter(
        OutsourceOrder.sales_item_id == item_id,
        OutsourceOrder.status.in_(["待确认", "已审核", "已完工"]),
    ).all()

    stop_sale = bool(data.get("stop_sale"))

    if stop_sale:
        # ===== 停售 =====
        if received_total > 0:
            raise HTTPException(400, f"该明细行已入库 {received_total}，不能停售（货已动，只能改数量）")
        if (item.delivered_qty or 0) > 0:
            raise HTTPException(400, "该明细行已发货，不能停售")
        if active_stock_ins:
            raise HTTPException(400, "请先退回待入库单，再停售")
        if active_outsources:
            raise HTTPException(400, f"请先删除委外订单（{active_outsources[0].outsource_no}），再停售")
        item.production_status = "已停售"
        db.commit()
        _recalc_order_totals(db.query(SalesOrder).filter(SalesOrder.id == order_id).first())
        db.commit()
        return {"message": "该明细行已停售，金额已从订单中剔除"}

    # ===== 改数量 =====
    if "quantity" not in data:
        raise HTTPException(400, "请提供要变更的数量或停售标记")
    new_qty = float(data["quantity"])
    if new_qty <= 0:
        raise HTTPException(400, "数量必须大于0")
    if item.production_status == "已入库":
        raise HTTPException(400, "该明细行已完成入库，不能变更数量（客户要改请新建订单）")
    # 已通知但下游单据未处理 → 先退下游
    if item.production_status == "已通知入库" and active_stock_ins:
        raise HTTPException(400, "请先退回待入库单，再变更数量")
    if item.production_status == "已通知外发" and active_outsources:
        raise HTTPException(400, f"请先删除委外订单（{active_outsources[0].outsource_no}），再变更数量")
    # 新数量不能小于已入库数
    min_qty = max(received_total, item.delivered_qty or 0)
    if new_qty < min_qty:
        raise HTTPException(400, f"新数量 {new_qty} 小于已入库/已发货数量 {min_qty}，不能小于已交付数量")
    item.quantity = new_qty
    item.total_amount = round(new_qty * (item.unit_price or 0), 2)
    tax_rate_val = item.tax_rate or 13
    item.total_amount_excl_tax = round(item.total_amount / (1 + tax_rate_val / 100), 2)
    item.tax_amount = round(item.total_amount - item.total_amount_excl_tax, 2)
    # 同步待入库单应入数量（未完成的）
    for s in active_stock_ins:
        s.quantity = new_qty
    # 同步委外单数量（待确认/已审核的）
    for o in active_outsources:
        if o.status in ("待确认", "已审核"):
            o.quantity = new_qty
            o.amount = round(new_qty * (o.unit_price or 0), 2)
    # 重算订单头金额
    order = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if order:
        _recalc_order_totals(order)
    db.commit()
    return {"message": f"明细行数量已变更为 {new_qty}"}

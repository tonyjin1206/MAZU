"""管理驾驶舱 — Dashboard API"""

from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session
from app.database import get_db
from app.utils.auth import get_current_user
from app.models.auth import User
from app.models.purchase import AccountsPayable, Payment, PaymentAllocation
from app.models.sales import AccountsReceivable, Collection, CollectionAllocation
from app.models.inventory import StockTransaction

router = APIRouter()


@router.get("/dashboard", tags=["驾驶舱"])
def get_dashboard_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理驾驶舱总览数据"""

    # 1. 现金收入 — 按月汇总收款单金额（近6个月）
    now = date.today()
    
    # 生成完整的6个月列表（本月在最末）
    all_months = []
    for i in range(5, -1, -1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        all_months.append(f"{y:04d}-{m:02d}")
    six_months_ago_str = all_months[0] + "-01"
    
    collection_rows = db.query(
        sa_func.strftime("%Y-%m", Collection.collection_date).label("month"),
        sa_func.coalesce(sa_func.sum(Collection.amount), 0).label("total"),
    ).filter(
        Collection.collection_date >= six_months_ago_str,
        Collection.collection_date <= now,
    ).group_by("month").order_by("month").all()
    collection_map = {r[0]: float(r[1]) for r in collection_rows}
    cash_in = [{"month": m, "amount": collection_map.get(m, 0)} for m in all_months]

    # 2. 现金支付 — 按月汇总付款单金额
    payment_rows = db.query(
        sa_func.strftime("%Y-%m", Payment.payment_date).label("month"),
        sa_func.coalesce(sa_func.sum(Payment.amount), 0).label("total"),
    ).filter(
        Payment.payment_date >= six_months_ago_str,
        Payment.payment_date <= now,
    ).group_by("month").order_by("month").all()
    payment_map = {r[0]: float(r[1]) for r in payment_rows}
    cash_out = [{"month": m, "amount": payment_map.get(m, 0)} for m in all_months]

    # 3. 应收账款账龄
    from app.models.foundation import Customer
    ar_list = db.query(AccountsReceivable).filter(
        AccountsReceivable.balance > 0
    ).order_by(AccountsReceivable.created_at).all()
    ar_aging = []
    for ar in ar_list:
        customer = db.query(Customer).filter(Customer.id == ar.customer_id).first()
        due_date = ar.due_date if ar.due_date else (ar.created_at.date() + timedelta(days=30) if ar.created_at else now)
        overdue = (now - due_date).days if due_date < now else 0
        ar_aging.append({
            "customer_name": customer.name_cn if customer else "",
            "amount": ar.amount or 0,
            "collected": ar.collected_amount or 0,
            "balance": ar.balance or 0,
            "ar_date": str(ar.created_at.date()) if ar.created_at else "",
            "due_date": str(due_date),
            "overdue_days": overdue,
        })
    ar_aging.sort(key=lambda x: x["overdue_days"], reverse=True)

    # 4. 应付账款账龄
    from app.models.foundation import Supplier
    ap_list = db.query(AccountsPayable).filter(
        AccountsPayable.balance > 0
    ).order_by(AccountsPayable.created_at).all()
    ap_aging = []
    for ap in ap_list:
        supplier = db.query(Supplier).filter(Supplier.id == ap.supplier_id).first()
        due_date = ap.due_date if ap.due_date else (ap.created_at.date() + timedelta(days=30) if ap.created_at else now)
        overdue = (now - due_date).days if due_date < now else 0
        ap_aging.append({
            "supplier_name": supplier.name if supplier else "",
            "amount": ap.amount or 0,
            "paid": ap.paid_amount or 0,
            "balance": ap.balance or 0,
            "ap_date": str(ap.created_at.date()) if ap.created_at else "",
            "due_date": str(due_date),
            "overdue_days": overdue,
        })
    ap_aging.sort(key=lambda x: x["overdue_days"], reverse=True)

    # 5. 销售毛利 — 基于销售发货出库
    from app.models.sales import SalesDelivery
    from app.models.foundation import Product
    from app.models.inventory import StockTransaction
    deliveries = db.query(SalesDelivery).filter(
        SalesDelivery.status.in_(["已发货", "部分发货", "已出库", "部分出库", "已退货"])
    ).all()

    # 按发货单展开毛利
    profit_list = []
    for d in deliveries:
        order = d.order
        if not order: continue
        product = db.query(Product).filter(Product.id == d.product_id).first()
        # 退货单（is_return=1）= 红字冲减：收入/成本取负（两段式出库 source_doc_type=成品出库）
        is_return = 1 if getattr(d, "is_return", 0) else 0
        sign = -1 if is_return else 1
        revenue = sign * (d.quantity or 0) * (d.unit_price or 0)
        # 查该批次出库的库存成本
        txns = db.query(StockTransaction).filter(
            StockTransaction.source_doc_type.in_(["销售发货", "成品出库"]),
            StockTransaction.product_id == d.product_id,
            StockTransaction.batch_no == d.batch_no,
        ).all() if d.batch_no else []
        cost = 0
        if txns:
            total_qty = sum(abs(t.quantity or 0) for t in txns)
            total_cost = sum(abs((t.unit_cost or 0) * (t.quantity or 0)) for t in txns)
            unit_cost = total_cost / max(total_qty, 1) if total_qty else 0
            cost = sign * (d.quantity or 0) * unit_cost
        else:
            cost = 0
        gross = revenue - cost
        profit_list.append({
            "product_id": d.product_id,
            "product_name": product.name_cn if product else "",
            "order_no": order.order_no if order else "",
            "customer_name": order.customer.name_cn if order and order.customer else "",
            "qty": round(d.quantity or 0, 2),
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "gross_profit": round(gross, 2),
            "margin": round(gross / revenue * 100, 1) if revenue else 0,
        })
    profit_list.sort(key=lambda x: x["gross_profit"], reverse=True)

    return {
        "cash_in": cash_in,
        "cash_out": cash_out,
        "ar_aging": ar_aging,
        "ap_aging": ap_aging,
        "profit": profit_list,
    }


@router.get("/dashboard/profit-detail/{product_id}", tags=["驾驶舱"])
def get_profit_detail(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """销售毛利明细 — 按发货单列出收入与成本"""
    from app.models.sales import SalesDelivery, SalesInvoice
    from app.models.foundation import Product
    product = db.query(Product).filter(Product.id == product_id).first()
    deliveries = db.query(SalesDelivery).filter(
        SalesDelivery.product_id == product_id,
        SalesDelivery.status.in_(["已发货", "部分发货", "已出库", "部分出库", "已退货"]),
    ).order_by(SalesDelivery.delivery_date).all()

    detail = []
    total_revenue = 0
    total_cost = 0
    for d in deliveries:
        order = d.order
        customer_name = order.customer.name_cn if order and order.customer else ""
        # 查该订单的销售发票号
        invoice = db.query(SalesInvoice).filter(
            SalesInvoice.order_id == d.order_id,
            SalesInvoice.status != "已作废",
        ).first()
        invoice_no = invoice.invoice_no if invoice else ""
        # 查该批次出库的库存成本
        txns = db.query(StockTransaction).filter(
            StockTransaction.source_doc_type.in_(["销售发货", "成品出库"]),
            StockTransaction.product_id == product_id,
            StockTransaction.batch_no == d.batch_no,
        ).all() if d.batch_no else []
        unit_cost = 0
        trans_no = ""
        if txns:
            t = txns[0]
            trans_no = t.trans_no or ""
            total_qty = sum(abs(t.quantity or 0) for t in txns)
            total_amt = sum(abs((t.unit_cost or 0) * (t.quantity or 0)) for t in txns)
            unit_cost = total_amt / max(total_qty, 1) if total_qty else 0
        is_return = 1 if getattr(d, "is_return", 0) else 0
        sign = -1 if is_return else 1
        revenue = sign * (d.quantity or 0) * (d.unit_price or 0)
        cost = sign * (d.quantity or 0) * unit_cost
        total_revenue += revenue
        total_cost += cost
        detail.append({
            "order_no": order.order_no if order else "",
            "customer_name": customer_name,
            "qty": d.quantity or 0,
            "invoice_no": invoice_no,
            "unit_price": d.unit_price or 0,
            "revenue": round(revenue, 2),
            "trans_no": trans_no,
            "unit_cost": round(unit_cost, 2),
            "cost": round(cost, 2),
            "gross_profit": round(revenue - cost, 2),
            "delivery_no": d.delivery_no,
            "batch_no": d.batch_no or "",
        })

    return {
        "product_name": product.name_cn if product else "",
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_revenue - total_cost, 2),
        "detail": detail,
    }


@router.get("/dashboard/net-cash-detail/{month}", tags=["驾驶舱"])
def get_net_cash_detail(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """现金净收支明细 — 某月的收款和付款明细"""
    from app.models.sales import Collection
    from app.models.purchase import Payment
    year_month = month + "-01"
    next_month = f"{int(month[:4]) + (int(month[5:]) // 12):04d}-{(int(month[5:]) % 12) + 1:02d}-01"

    # 收款明细
    collections = db.query(Collection).filter(
        Collection.collection_date >= year_month,
        Collection.collection_date < next_month,
    ).all()
    collection_items = []
    for c in collections:
        collection_items.append({
            "doc_no": c.collection_no,
            "amount": c.amount or 0,
            "date": str(c.collection_date),
            "remark": c.remark or "",
        })

    # 付款明细
    payments = db.query(Payment).filter(
        Payment.payment_date >= year_month,
        Payment.payment_date < next_month,
    ).all()
    payment_items = []
    for p in payments:
        payment_items.append({
            "doc_no": p.payment_no,
            "amount": p.amount or 0,
            "date": str(p.payment_date),
            "remark": p.remark or "",
        })

    return {
        "month": month,
        "total_collection": round(sum(i["amount"] for i in collection_items), 2),
        "total_payment": round(sum(i["amount"] for i in payment_items), 2),
        "net": round(sum(i["amount"] for i in collection_items) - sum(i["amount"] for i in payment_items), 2),
        "collections": collection_items,
        "payments": payment_items,
    }

"""销售模块模型 — 报价、订单、发货、报关、发票、应收"""

from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class SalesQuote(Base):
    """报价单"""
    __tablename__ = "so_quote"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    quote_no = Column(String(64), unique=True, nullable=False, comment="报价单号: QT-YYYYMMDD-NNN")
    customer_id = Column(Integer, ForeignKey("fd_customer.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    quantity = Column(Float, nullable=False, comment="数量")
    unit_price = Column(Float, default=0, comment="单价(外币)")
    total_amount = Column(Float, default=0, comment="总金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    trade_term_id = Column(Integer, ForeignKey("fd_trade_term.id"), comment="贸易术语")
    valid_until = Column(Date, comment="有效期至")
    status = Column(String(16), default="有效", comment="状态: 有效/已转单/已过期")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    customer = relationship("Customer")
    product = relationship("Product")


class SalesOrder(Base):
    """销售订单（支持多产品明细）"""
    __tablename__ = "so_order"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_no = Column(String(64), unique=True, nullable=False, comment="订单号: SO-YYYYMMDD-NNN")
    quote_id = Column(Integer, ForeignKey("so_quote.id"), comment="来源报价单")
    customer_id = Column(Integer, ForeignKey("fd_customer.id"), nullable=False)
    # 汇总金额（由明细行汇总）
    total_amount = Column(Float, default=0, comment="含税总金额(外币)")
    total_amount_local = Column(Float, default=0, comment="含税总金额(本币)")
    total_amount_excl_tax = Column(Float, default=0, comment="不含税金额(外币)")
    total_amount_excl_tax_local = Column(Float, default=0, comment="不含税金额(本币)")
    tax_amount = Column(Float, default=0, comment="税额(本币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    exchange_rate = Column(Float, default=1, comment="汇率")
    trade_term_id = Column(Integer, ForeignKey("fd_trade_term.id"))
    payment_terms = Column(String(64), default="TT", comment="付款条件: TT/LC/DP/DA")
    order_date = Column(Date, nullable=False, default=date.today)
    delivery_date = Column(Date, comment="预计发货日")
    status = Column(String(16), default="待审核", comment="状态: 待审核/已审/生产中/部分发货/已发货/已完成/已关闭")
    invoiced_amount = Column(Float, default=0, comment="已开票金额")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    customer = relationship("Customer")
    currency = relationship("Currency")
    trade_term = relationship("TradeTerm")
    items = relationship("SalesOrderItem", cascade="all, delete-orphan", back_populates="order")


class SalesOrderItem(Base):
    """销售订单明细"""
    __tablename__ = "so_order_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("so_order.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    quantity = Column(Float, nullable=False, comment="数量")
    unit_price = Column(Float, default=0, comment="含税单价(外币)")
    unit_price_local = Column(Float, default=0, comment="含税单价(本币)")
    total_amount = Column(Float, default=0, comment="含税金额(外币)")
    total_amount_local = Column(Float, default=0, comment="含税金额(本币)")
    total_amount_excl_tax = Column(Float, default=0, comment="不含税金额(外币)")
    total_amount_excl_tax_local = Column(Float, default=0, comment="不含税金额(本币)")
    tax_rate = Column(Float, default=13, comment="增值税率(%)")
    tax_amount = Column(Float, default=0, comment="税额(本币)")
    hs_code_id = Column(Integer, ForeignKey("fd_hs_code.id"), comment="HS编码")
    delivered_qty = Column(Float, default=0, comment="已发货数量")
    remark = Column(Text)

    order = relationship("SalesOrder", back_populates="items")
    product = relationship("Product")
    hs_code = relationship("HsCode")


class SalesDelivery(Base):
    """销售出库单（批次出库）"""
    __tablename__ = "so_delivery"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    delivery_no = Column(String(64), unique=True, nullable=False, comment="发货单号: SD-YYYYMMDD-NNN")
    order_id = Column(Integer, ForeignKey("so_order.id"), nullable=False)
    order_item_id = Column(Integer, ForeignKey("so_order_item.id"), comment="关联订单明细行")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False, comment="产品ID")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    batch_no = Column(String(64), nullable=False, comment="出库批次号")
    quantity = Column(Float, nullable=False, comment="发货数量")
    unit_price = Column(Float, default=0, comment="含税单价(外币)")
    amount = Column(Float, default=0, comment="含税金额(外币)")
    delivery_date = Column(Date, nullable=False, default=date.today, comment="发货日期")
    status = Column(String(16), default="已发货", comment="状态: 已发货/已报关")
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    order = relationship("SalesOrder")
    order_item = relationship("SalesOrderItem")
    product = relationship("Product")
    warehouse = relationship("Warehouse")


class CustomsDeclaration(Base):
    """报关单"""
    __tablename__ = "so_customs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customs_no = Column(String(64), unique=True, nullable=False, comment="报关单号")
    order_id = Column(Integer, ForeignKey("so_order.id"), nullable=False)
    delivery_id = Column(Integer, ForeignKey("so_delivery.id"))
    hs_code_id = Column(Integer, ForeignKey("fd_hs_code.id"), nullable=False)
    declare_amount = Column(Float, default=0, comment="报关金额(FOB)")
    declare_currency = Column(Integer, ForeignKey("fd_currency.id"))
    declare_date = Column(Date, nullable=False, comment="报关日期")
    customs_broker = Column(String(128), comment="报关行")
    status = Column(String(16), default="已报关", comment="状态: 已报关/已放行/已结关")
    refund_status = Column(String(16), default="待申报", comment="退税状态: 待申报/已申报/已退税")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    order = relationship("SalesOrder")
    delivery = relationship("SalesDelivery")
    hs_code = relationship("HsCode")
    currency = relationship("Currency")


class SalesInvoice(Base):
    """销售发票"""
    __tablename__ = "so_invoice"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_no = Column(String(64), unique=True, nullable=False, comment="发票号")
    order_id = Column(Integer, ForeignKey("so_order.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("fd_customer.id"), nullable=False)
    invoice_date = Column(Date, nullable=False, comment="开票日期")
    invoice_type = Column(String(16), default="出口发票", comment="类型: 出口发票/增值税专票")
    amount = Column(Float, default=0, comment="发票金额(本币)")
    amount_fc = Column(Float, default=0, comment="发票金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    tax_rate = Column(Float, default=13, comment="增值税率(%)")
    tax_amount = Column(Float, default=0, comment="税额")
    total_amount = Column(Float, default=0, comment="价税合计")
    status = Column(String(16), default="已开票", comment="状态: 已开票/已作废")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())

    order = relationship("SalesOrder")
    customer = relationship("Customer")


class AccountsReceivable(Base):
    """应收账款"""
    __tablename__ = "ar_account"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ar_no = Column(String(64), unique=True, comment="应收单号: AR-YYYYMMDD-NNN")
    source_type = Column(String(32), comment="来源: sales_invoice")
    source_id = Column(Integer, comment="来源单据ID")
    customer_id = Column(Integer, ForeignKey("fd_customer.id"), nullable=False)
    amount = Column(Float, default=0, comment="应收金额(本币)")
    amount_fc = Column(Float, default=0, comment="应收金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    collected_amount = Column(Float, default=0, comment="已收金额")
    balance = Column(Float, default=0, comment="余额")
    due_date = Column(Date, comment="到期日")
    status = Column(String(16), default="未收款", comment="状态: 未收款/部分收款/已收款")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Collection(Base):
    """收款记录"""
    __tablename__ = "ar_collection"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    collection_no = Column(String(64), unique=True, nullable=False)
    customer_id = Column(Integer, ForeignKey("fd_customer.id"), nullable=False)
    collection_date = Column(Date, nullable=False)
    amount = Column(Float, default=0, comment="收款金额(本币)")
    amount_fc = Column(Float, default=0, comment="收款金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    exchange_rate = Column(Float, default=1)
    payment_method = Column(String(32), default="银行转账")
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())


class CollectionAllocation(Base):
    """收款核销明细"""
    __tablename__ = "ar_collection_alloc"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("ar_collection.id"), nullable=False)
    ar_account_id = Column(Integer, ForeignKey("ar_account.id"), nullable=False)
    allocated_amount = Column(Float, default=0, comment="核销金额")
    created_at = Column(DateTime, default=func.now())

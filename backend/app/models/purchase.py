"""采购模块模型 — 采购订单、入库、发票、应付"""

from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class PurchaseOrder(Base):
    """采购订单"""
    __tablename__ = "po_order"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_no = Column(String(64), unique=True, nullable=False, comment="订单号: PO-YYYYMMDD-NNN")
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False, comment="供应商")
    order_date = Column(Date, nullable=False, default=date.today, comment="下单日期")
    expected_date = Column(Date, comment="预计到货日")
    status = Column(String(16), default="待审核", comment="状态: 待审核/已审核/部分入库/已完成/已关闭")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"), comment="币种")
    exchange_rate = Column(Float, default=1, comment="汇率")
    total_amount = Column(Float, default=0, comment="含税金额(本币)")
    total_amount_fc = Column(Float, default=0, comment="含税金额(外币)")
    total_amount_excl_tax = Column(Float, default=0, comment="不含税金额(本币)")
    tax_rate = Column(Float, default=13, comment="增值税率(%)")
    tax_amount = Column(Float, default=0, comment="税额(本币)")
    payment_terms = Column(String(64), comment="付款条件")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    supplier = relationship("Supplier")
    items = relationship("PurchaseOrderItem", backref="order", lazy="selectin", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    """采购订单明细"""
    __tablename__ = "po_order_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("po_order.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False, comment="材料")
    quantity = Column(Float, nullable=False, comment="数量")
    unit_price = Column(Float, default=0, comment="单价(外币)")
    unit_price_local = Column(Float, default=0, comment="单价(本币)")
    total_amount = Column(Float, default=0, comment="含税金额")
    received_qty = Column(Float, default=0, comment="已入库数量")
    tax_rate = Column(Float, default=13, comment="增值税率(%)")
    total_amount_excl_tax = Column(Float, default=0, comment="不含税金额")
    remark = Column(Text)

    material = relationship("Material")


class PurchaseReceipt(Base):
    """采购入库单"""
    __tablename__ = "po_receipt"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_no = Column(String(64), unique=True, nullable=False, comment="入库单号: PR-YYYYMMDD-NNN")
    order_id = Column(Integer, ForeignKey("po_order.id"), nullable=False, comment="关联采购订单")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False, comment="入库仓库")
    receipt_date = Column(Date, nullable=False, default=date.today, comment="入库日期")
    status = Column(String(16), default="已入库", comment="状态: 已入库/已退货")
    total_qty = Column(Float, default=0)
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    order = relationship("PurchaseOrder")
    warehouse = relationship("Warehouse")
    items = relationship("PurchaseReceiptItem", backref="receipt", lazy="selectin", cascade="all, delete-orphan")


class PurchaseReceiptItem(Base):
    """采购入库明细（每一行生成一个批次号）"""
    __tablename__ = "po_receipt_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("po_receipt.id"), nullable=False)
    order_item_id = Column(Integer, ForeignKey("po_order_item.id"), comment="关联订单明细")
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False)
    quantity = Column(Float, nullable=False, comment="入库数量")
    unit_price = Column(Float, default=0, comment="入库单价")
    batch_no = Column(String(64), nullable=False, comment="批次号: YYYYMMDD-NNN")
    remark = Column(Text)

    material = relationship("Material")


class PurchaseInvoice(Base):
    """采购发票"""
    __tablename__ = "po_invoice"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_no = Column(String(64), unique=True, nullable=False, comment="发票号")
    order_id = Column(Integer, ForeignKey("po_order.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False)
    invoice_date = Column(Date, nullable=False, comment="开票日期")
    invoice_type = Column(String(16), default="专票", comment="类型: 专票/普票")
    amount = Column(Float, default=0, comment="发票金额(本币)")
    amount_fc = Column(Float, default=0, comment="发票金额(外币)")
    tax_amount = Column(Float, default=0, comment="税额")
    status = Column(String(16), default="未匹配", comment="状态: 未匹配/已匹配(退税)/已认证")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())

    order = relationship("PurchaseOrder")
    supplier = relationship("Supplier")


class AccountsPayable(Base):
    """应付账款"""
    __tablename__ = "ap_account"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ap_no = Column(String(64), unique=True, comment="应付单号: AP-YYYYMMDD-NNN")
    source_type = Column(String(32), comment="来源: purchase_invoice/processing_invoice")
    source_id = Column(Integer, comment="来源单据ID")
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False)
    amount = Column(Float, default=0, comment="应付金额(本币)")
    amount_fc = Column(Float, default=0, comment="应付金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    paid_amount = Column(Float, default=0, comment="已付金额")
    balance = Column(Float, default=0, comment="余额")
    due_date = Column(Date, comment="到期日")
    status = Column(String(16), default="未付款", comment="状态: 未付款/部分付款/已付款")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Payment(Base):
    """付款记录"""
    __tablename__ = "ap_payment"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payment_no = Column(String(64), unique=True, nullable=False)
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False)
    payment_date = Column(Date, nullable=False, comment="付款日期")
    amount = Column(Float, default=0, comment="付款金额(本币)")
    amount_fc = Column(Float, default=0, comment="付款金额(外币)")
    currency_id = Column(Integer, ForeignKey("fd_currency.id"))
    exchange_rate = Column(Float, default=1, comment="付款汇率")
    payment_method = Column(String(32), default="银行转账", comment="付款方式")
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())


class PaymentAllocation(Base):
    """付款核销明细"""
    __tablename__ = "ap_payment_alloc"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("ap_payment.id"), nullable=False)
    ap_account_id = Column(Integer, ForeignKey("ap_account.id"), nullable=False)
    allocated_amount = Column(Float, default=0, comment="核销金额")
    created_at = Column(DateTime, default=func.now())

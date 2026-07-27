"""退税模块模型（生产企业免抵退）"""

from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class TaxRefundInputInvoice(Base):
    """进项发票（退税专用，与采购发票关联）"""
    __tablename__ = "tr_input_invoice"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    purchase_invoice_id = Column(Integer, ForeignKey("po_invoice.id"), comment="关联采购发票")
    invoice_no = Column(String(64), unique=True, nullable=False, comment="进项发票号")
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False)
    invoice_date = Column(Date, nullable=False, comment="开票日期")
    amount = Column(Float, default=0, comment="发票金额(不含税)")
    tax_amount = Column(Float, default=0, comment="税额")
    total_amount = Column(Float, default=0, comment="价税合计")
    certification_date = Column(Date, comment="认证日期")
    certification_status = Column(String(16), default="未认证", comment="认证状态: 未认证/已认证/已抵扣")
    refund_match_status = Column(String(16), default="未匹配", comment="退税匹配: 未匹配/已匹配")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())

    supplier = relationship("Supplier")


class TaxRefundDeclaration(Base):
    """退税申报表"""
    __tablename__ = "tr_declaration"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    declaration_no = Column(String(64), unique=True, nullable=False, comment="申报批次号")
    declare_date = Column(Date, nullable=False, comment="申报日期")
    period = Column(String(8), nullable=False, comment="所属期: YYYYMM")
    batch = Column(Integer, default=1, comment="申报批次")

    # 本期数据
    export_amount_fob = Column(Float, default=0, comment="出口FOB金额(免抵退计税依据)")
    export_currency = Column(Integer, ForeignKey("fd_currency.id"))

    # 免抵退计算核心字段
    tax_rate = Column(Float, default=13, comment="征税率(%)")
    refund_rate = Column(Float, default=13, comment="退税率(%)")
    non_deductible_amount = Column(Float, default=0, comment="免抵退税不得免征和抵扣税额")
    domestic_tax = Column(Float, default=0, comment="内销销项税额")
    input_tax = Column(Float, default=0, comment="进项税额")
    last_period_deduction = Column(Float, default=0, comment="上期留抵税额")
    current_tax_due = Column(Float, default=0, comment="当期应纳税额(正=应纳/负=留抵)")
    current_deduction = Column(Float, default=0, comment="当期留抵税额")
    refundable_amount = Column(Float, default=0, comment="免抵退税额")
    actual_refund = Column(Float, default=0, comment="应退税额")
    actual_refund_amount = Column(Float, default=0, comment="实际退税金额")
    exemption_amount = Column(Float, default=0, comment="免抵税额")

    # 状态
    status = Column(String(16), default="待申报", comment="状态: 待申报/已申报/审核中/审核通过/已退税/已退库")

    # 关联
    customs_ids = Column(Text, comment="关联报关单ID列表(逗号分隔)")
    input_invoice_ids = Column(Text, comment="关联进项发票ID列表(逗号分隔)")

    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class TaxRefundDetail(Base):
    """退税申报明细（每张报关单的行）"""
    __tablename__ = "tr_declaration_detail"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    declaration_id = Column(Integer, ForeignKey("tr_declaration.id"), nullable=False)
    customs_id = Column(Integer, ForeignKey("so_customs.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("so_order.id"), nullable=False)
    hs_code_id = Column(Integer, ForeignKey("fd_hs_code.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)

    export_quantity = Column(Float, default=0, comment="出口数量")
    export_amount_fob = Column(Float, default=0, comment="出口FOB金额")
    refund_rate = Column(Float, default=0, comment="退税率(%)")
    refundable_amount = Column(Float, default=0, comment="该笔免抵退税额")

    # 关联进项发票
    input_invoice_ids = Column(Text, comment="匹配的进项发票ID")

    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())

    declaration = relationship("TaxRefundDeclaration", backref="details")


class TaxRefundDeclarationRow(Base):
    """退税申报明细行（标准格式：关联号→进项发票→商品）"""
    __tablename__ = "tr_declaration_row"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    declaration_id = Column(Integer, ForeignKey("tr_declaration.id"), nullable=False)
    seq = Column(String(8), comment="序号(8位流水)")
    assoc_no = Column(String(24), nullable=False, comment="关联号: YYYYMM+批次+流水")
    tax_type = Column(String(1), default="V", comment="税种: V/C")
    voucher_type = Column(String(32), comment="凭证种类")
    voucher_no = Column(String(64), comment="进货凭证号")
    supplier_tax_id = Column(String(32), comment="供货方纳税人识别号")
    invoice_date = Column(Date, comment="开票日期")
    product_code = Column(String(32), comment="出口商品代码")
    product_name = Column(String(128), comment="商品名称")
    unit = Column(String(16), comment="计量单位")
    quantity = Column(Float, default=0, comment="数量")
    taxable_amount = Column(Float, default=0, comment="计税金额")
    tax_rate = Column(Float, default=13, comment="征税率(%)")
    refund_rate = Column(Float, default=13, comment="退税率(%)")
    refundable_amount = Column(Float, default=0, comment="可退税额")
    input_invoice_id = Column(Integer, ForeignKey("tr_input_invoice.id"), comment="关联进项发票")

    declaration = relationship("TaxRefundDeclaration", backref="rows")
    input_invoice = relationship("TaxRefundInputInvoice")


class TaxRefundProgress(Base):
    """退税进度追踪"""
    __tablename__ = "tr_progress"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    declaration_id = Column(Integer, ForeignKey("tr_declaration.id"), nullable=False, comment="关联申报表")
    action = Column(String(32), nullable=False, comment="操作: 申报/审核/退库/补正")
    action_date = Column(DateTime, default=func.now(), comment="操作时间")
    operator = Column(String(32), comment="操作人")
    result = Column(String(32), comment="结果: 通过/驳回/待补正")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())

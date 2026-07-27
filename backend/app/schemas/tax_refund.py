"""退税模块 Schemas（生产企业免抵退）"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


# ========== 进项发票 ==========

class TaxRefundInputInvoiceCreate(BaseModel):
    purchase_invoice_id: Optional[int] = None
    invoice_no: str
    supplier_id: int
    invoice_date: date
    amount: float = 0
    tax_amount: float = 0
    total_amount: float = 0
    certification_date: Optional[date] = None
    remark: str = ""


class TaxRefundInputInvoiceOut(BaseModel):
    id: int
    purchase_invoice_id: Optional[int]
    invoice_no: str
    supplier_id: int
    invoice_date: date
    amount: float
    tax_amount: float
    total_amount: float
    certification_date: Optional[date]
    certification_status: str
    refund_match_status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 退税申报 ==========

class TaxRefundDeclarationCreate(BaseModel):
    declaration_no: str
    declare_date: date
    period: str
    batch: int = 1
    export_amount_fob: float = 0
    export_currency: Optional[int] = None
    tax_rate: float = 13
    refund_rate: float = 13
    domestic_tax: float = 0
    input_tax: float = 0
    last_period_deduction: float = 0
    customs_ids: str = ""
    input_invoice_ids: str = ""
    remark: str = ""


class TaxRefundDeclarationOut(BaseModel):
    id: int
    declaration_no: str
    declare_date: date
    period: str
    export_amount_fob: float
    tax_rate: float
    refund_rate: float
    non_deductible_amount: float
    domestic_tax: float
    input_tax: float
    last_period_deduction: float
    current_tax_due: float
    current_deduction: float
    refundable_amount: float
    actual_refund: float
    exemption_amount: float
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaxRefundCalculationRequest(BaseModel):
    """免抵退计算请求"""
    export_amount_fob: float = Field(..., description="出口FOB金额")
    refund_rate: float = Field(..., description="退税率(%)")
    tax_rate: float = Field(13, description="征税率(%)")
    domestic_tax: float = Field(0, description="内销销项税额")
    input_tax: float = Field(0, description="进项税额")
    last_period_deduction: float = Field(0, description="上期留抵税额")


class TaxRefundCalculationResult(BaseModel):
    """免抵退计算结果"""
    non_deductible_amount: float = Field(..., description="不得免征和抵扣税额")
    taxable_amount: float = Field(..., description="当期应纳税额")
    current_deduction: float = Field(..., description="当期留抵税额")
    refundable_amount: float = Field(..., description="当期免抵退税额")
    actual_refund: float = Field(..., description="应退税额")
    exemption_amount: float = Field(..., description="免抵税额")


# ========== 申报明细 ==========

class TaxRefundDetailCreate(BaseModel):
    declaration_id: int
    customs_id: int
    order_id: int
    hs_code_id: int
    product_id: int
    export_quantity: float = 0
    export_amount_fob: float = 0
    refund_rate: float = 0
    input_invoice_ids: str = ""
    remark: str = ""


class TaxRefundDetailOut(BaseModel):
    id: int
    declaration_id: int
    customs_id: int
    order_id: int
    hs_code_id: int
    product_id: int
    export_quantity: float
    export_amount_fob: float
    refund_rate: float
    refundable_amount: float
    input_invoice_ids: str

    class Config:
        from_attributes = True


# ========== 申报明细（标准格式行） ==========

class TaxRefundDeclarationRowCreate(BaseModel):
    input_invoice_id: int
    voucher_type: str = "增值税专用发票"
    product_code: str = ""
    product_name: str = ""
    unit: str = ""
    quantity: float = 0
    taxable_amount: float = 0
    tax_rate: float = 13
    refund_rate: float = 13


class TaxRefundDeclarationRowOut(BaseModel):
    id: int
    declaration_id: int
    seq: str = ""
    assoc_no: str = ""
    tax_type: str = "V"
    voucher_type: str = ""
    voucher_no: str = ""
    supplier_tax_id: str = ""
    invoice_date: str = ""
    product_code: str = ""
    product_name: str = ""
    unit: str = ""
    quantity: float = 0
    taxable_amount: float = 0
    tax_rate: float = 13
    refund_rate: float = 13
    refundable_amount: float = 0
    input_invoice_id: int | None = None
    invoice_no: str = ""
    supplier_name: str = ""

    class Config:
        from_attributes = True


# ========== 退税率进度 ==========

class TaxRefundProgressCreate(BaseModel):
    declaration_id: int
    action: str
    operator: str = ""
    result: str = ""
    remark: str = ""


class TaxRefundProgressOut(BaseModel):
    id: int
    declaration_id: int
    action: str
    action_date: datetime
    operator: Optional[str]
    result: Optional[str]
    remark: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

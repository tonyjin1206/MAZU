"""销售模块 Schemas — 报价单、销售订单、销售发货、报关单、销售发票、应收账款、收款、收款核销"""

from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


# ==================== 报价单 ====================

class SalesQuoteCreate(BaseModel):
    quote_no: str = Field(..., description="报价单号: QT-YYYYMMDD-NNN")
    customer_id: int = Field(..., description="客户ID")
    product_id: int = Field(..., description="产品ID")
    quantity: float = Field(..., description="数量")
    unit_price: float = Field(default=0, description="单价(外币)")
    total_amount: float = Field(default=0, description="总金额(外币)")
    currency_id: int | None = None
    trade_term_id: int | None = None
    valid_until: date | None = None
    status: str = Field(default="有效", description="状态: 有效/已转单/已过期")
    remark: str = ""
    created_by: str | None = None


class SalesQuoteUpdate(BaseModel):
    customer_id: int | None = None
    product_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_amount: float | None = None
    currency_id: int | None = None
    trade_term_id: int | None = None
    valid_until: date | None = None
    status: str | None = None
    remark: str | None = None


class SalesQuoteOut(BaseModel):
    id: int
    quote_no: str
    customer_id: int
    product_id: int
    customer_name: str | None = None
    product_name: str | None = None
    quantity: float
    unit_price: float
    total_amount: float
    currency_id: int | None
    currency_code: str | None = None
    trade_term_id: int | None
    trade_term_name: str | None = None
    valid_until: date | None
    status: str
    remark: str | None
    created_by: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 销售订单 ====================

class SalesOrderCreate(BaseModel):
    order_no: str = Field(..., description="订单号: SO-YYYYMMDD-NNN")
    quote_id: int | None = None
    customer_id: int = Field(..., description="客户ID")
    product_id: int = Field(..., description="产品ID")
    quantity: float = Field(..., description="数量")
    unit_price: float = Field(default=0, description="单价(外币)")
    total_amount: float = Field(default=0, description="总金额(外币)")
    total_amount_local: float = Field(default=0, description="总金额(本币)")
    currency_id: int | None = None
    exchange_rate: float = Field(default=1, description="汇率")
    trade_term_id: int | None = None
    payment_terms: str = Field(default="TT", description="付款条件: TT/LC/DP/DA")
    order_date: date | None = None
    delivery_date: date | None = None
    status: str = Field(default="待审核", description="状态: 待审核/已审/生产中/已发货/已完成/已关闭")
    hs_code_id: int | None = None
    tax_rate: float = Field(default=13, description="增值税率(%)")
    remark: str = ""
    created_by: str | None = None


class SalesOrderUpdate(BaseModel):
    quote_id: int | None = None
    customer_id: int | None = None
    product_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_amount: float | None = None
    total_amount_local: float | None = None
    currency_id: int | None = None
    exchange_rate: float | None = None
    trade_term_id: int | None = None
    payment_terms: str | None = None
    order_date: date | None = None
    delivery_date: date | None = None
    status: str | None = None
    hs_code_id: int | None = None
    remark: str | None = None


class SalesOrderOut(BaseModel):
    id: int
    order_no: str
    quote_id: int | None
    customer_id: int
    product_id: int
    customer_name: str | None = None
    product_name: str | None = None
    quantity: float
    unit_price: float
    total_amount: float
    total_amount_local: float
    currency_id: int | None
    currency_code: str | None = None
    exchange_rate: float
    trade_term_id: int | None
    trade_term_name: str | None = None
    payment_terms: str
    order_date: date
    delivery_date: date | None
    status: str
    hs_code_id: int | None
    hs_code: str | None = None
    remark: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ==================== 销售发货 ====================

class SalesDeliveryCreate(BaseModel):
    delivery_no: str = Field(..., description="发货单号: SD-YYYYMMDD-NNN")
    order_id: int = Field(..., description="销售订单ID")
    warehouse_id: int = Field(..., description="仓库ID")
    batch_no: str = Field(..., description="出库批次号")
    quantity: float = Field(..., description="发货数量")
    delivery_date: date | None = None
    status: str = Field(default="已发货", description="状态: 已发货/已报关")
    remark: str = ""
    operator: str | None = None


class SalesDeliveryUpdate(BaseModel):
    warehouse_id: int | None = None
    batch_no: str | None = None
    quantity: float | None = None
    delivery_date: date | None = None
    status: str | None = None
    remark: str | None = None
    operator: str | None = None


class SalesDeliveryOut(BaseModel):
    id: int
    delivery_no: str
    order_id: int
    order_no: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    batch_no: str
    quantity: float
    delivery_date: date
    status: str
    remark: str | None
    operator: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 报关单 ====================

class CustomsDeclarationCreate(BaseModel):
    customs_no: str = Field(..., description="报关单号")
    order_id: int = Field(..., description="销售订单ID")
    delivery_id: int | None = None
    hs_code_id: int = Field(..., description="HS编码ID")
    declare_amount: float = Field(default=0, description="报关金额(FOB)")
    declare_currency: int | None = None
    declare_date: date = Field(..., description="报关日期")
    customs_broker: str = Field(default="", description="报关行")
    status: str = Field(default="已报关", description="状态: 已报关/已放行/已结关")
    refund_status: str = Field(default="待申报", description="退税状态: 待申报/已申报/已退税")
    remark: str = ""


class CustomsDeclarationUpdate(BaseModel):
    delivery_id: int | None = None
    hs_code_id: int | None = None
    declare_amount: float | None = None
    declare_currency: int | None = None
    declare_date: date | None = None
    customs_broker: str | None = None
    status: str | None = None
    refund_status: str | None = None
    remark: str | None = None


class CustomsDeclarationOut(BaseModel):
    id: int
    customs_no: str
    order_id: int
    order_no: str | None = None
    delivery_id: int | None
    delivery_no: str | None = None
    hs_code_id: int
    hs_code: str | None = None
    declare_amount: float
    declare_currency: int | None
    currency_code: str | None = None
    declare_date: date
    customs_broker: str | None
    status: str
    refund_status: str
    remark: str | None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ==================== 销售发票 ====================

class SalesInvoiceCreate(BaseModel):
    invoice_no: str = Field(..., description="发票号")
    order_id: int = Field(..., description="销售订单ID")
    customer_id: int = Field(..., description="客户ID")
    invoice_date: date = Field(..., description="开票日期")
    invoice_type: str = Field(default="出口发票", description="类型: 出口发票/增值税专票")
    amount: float = Field(default=0, description="不含税金额(本币)")
    amount_fc: float = Field(default=0, description="发票金额(外币)")
    currency_id: int | None = None
    tax_rate: float = Field(default=13, description="增值税率(%)")
    tax_amount: float = Field(default=0, description="税额")
    total_amount: float = Field(default=0, description="价税合计")
    status: str = Field(default="已开票", description="状态: 已开票/已作废")
    remark: str = ""


class SalesInvoiceUpdate(BaseModel):
    customer_id: int | None = None
    invoice_date: date | None = None
    invoice_type: str | None = None
    amount: float | None = None
    amount_fc: float | None = None
    currency_id: int | None = None
    tax_rate: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    status: str | None = None
    remark: str | None = None


class SalesInvoiceOut(BaseModel):
    id: int
    invoice_no: str
    order_id: int
    order_no: str | None = None
    customer_id: int
    customer_name: str | None = None
    invoice_date: date
    invoice_type: str
    amount: float
    amount_fc: float
    currency_id: int | None
    currency_code: str | None = None
    tax_rate: float = 13
    tax_amount: float = 0
    total_amount: float = 0
    status: str
    remark: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 应收账款 ====================

class AccountsReceivableCreate(BaseModel):
    source_type: str = Field(default="sales_invoice", description="来源: sales_invoice")
    source_id: int | None = None
    customer_id: int = Field(..., description="客户ID")
    amount: float = Field(default=0, description="应收金额(本币)")
    amount_fc: float = Field(default=0, description="应收金额(外币)")
    currency_id: int | None = None
    collected_amount: float = Field(default=0, description="已收金额")
    balance: float = Field(default=0, description="余额")
    due_date: date | None = None
    status: str = Field(default="未收款", description="状态: 未收款/部分收款/已收款")


class AccountsReceivableUpdate(BaseModel):
    amount: float | None = None
    amount_fc: float | None = None
    currency_id: int | None = None
    collected_amount: float | None = None
    balance: float | None = None
    due_date: date | None = None
    status: str | None = None


class AccountsReceivableOut(BaseModel):
    id: int
    source_type: str | None
    source_id: int | None
    customer_id: int
    customer_name: str | None = None
    amount: float
    amount_fc: float
    currency_id: int | None
    currency_code: str | None = None
    collected_amount: float
    balance: float
    due_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ==================== 收款记录 ====================

class CollectionCreate(BaseModel):
    collection_no: str = Field(..., description="收款单号")
    customer_id: int = Field(..., description="客户ID")
    collection_date: date = Field(..., description="收款日期")
    amount: float = Field(default=0, description="收款金额(本币)")
    amount_fc: float = Field(default=0, description="收款金额(外币)")
    currency_id: int | None = None
    exchange_rate: float = Field(default=1, description="汇率")
    payment_method: str = Field(default="银行转账", description="付款方式")
    remark: str = ""
    operator: str | None = None


class CollectionUpdate(BaseModel):
    customer_id: int | None = None
    collection_date: date | None = None
    amount: float | None = None
    amount_fc: float | None = None
    currency_id: int | None = None
    exchange_rate: float | None = None
    payment_method: str | None = None
    remark: str | None = None
    operator: str | None = None


class CollectionOut(BaseModel):
    id: int
    collection_no: str
    customer_id: int
    customer_name: str | None = None
    collection_date: date
    amount: float
    amount_fc: float
    currency_id: int | None
    currency_code: str | None = None
    exchange_rate: float
    payment_method: str
    remark: str | None
    operator: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 收款核销明细 ====================

class CollectionAllocationCreate(BaseModel):
    collection_id: int = Field(..., description="收款记录ID")
    ar_account_id: int = Field(..., description="应收账款ID")
    allocated_amount: float = Field(default=0, description="核销金额")


class CollectionAllocationUpdate(BaseModel):
    allocated_amount: float | None = None


class CollectionAllocationOut(BaseModel):
    id: int
    collection_id: int
    ar_account_id: int
    collection_no: str | None = None
    customer_name: str | None = None
    allocated_amount: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

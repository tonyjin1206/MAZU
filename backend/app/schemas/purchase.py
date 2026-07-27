"""采购模块 Schemas — 采购订单、入库、发票、应付"""

from datetime import date, datetime
from pydantic import BaseModel, Field


# ==================== 采购订单 ====================

class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    order_date: date = Field(default_factory=date.today)
    expected_date: date | None = None
    currency_id: int | None = None
    exchange_rate: float = 1
    payment_terms: str = ""
    tax_rate: float = 13
    remark: str = ""
    items: list["PurchaseOrderItemCreate"] = []


class PurchaseOrderUpdate(BaseModel):
    supplier_id: int | None = None
    order_date: date | None = None
    expected_date: date | None = None
    status: str | None = None
    currency_id: int | None = None
    exchange_rate: float | None = None
    payment_terms: str | None = None
    remark: str | None = None


class PurchaseOrderOut(BaseModel):
    id: int
    order_no: str
    supplier_id: int
    supplier_name: str | None = None
    order_date: date
    expected_date: date | None
    status: str
    currency_id: int | None
    currency_code: str | None = None
    exchange_rate: float
    total_amount: float
    total_amount_fc: float
    total_amount_excl_tax: float = 0
    tax_rate: float = 13
    tax_amount: float = 0
    payment_terms: str | None
    remark: str | None
    created_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 采购订单明细 ====================

class PurchaseOrderItemCreate(BaseModel):
    order_id: int | None = None
    material_id: int
    quantity: float
    unit_price: float = 0
    unit_price_local: float = 0
    remark: str = ""


class PurchaseOrderItemUpdate(BaseModel):
    material_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    unit_price_local: float | None = None
    remark: str | None = None


class PurchaseOrderItemOut(BaseModel):
    id: int
    order_id: int
    material_id: int
    material_name: str | None = None
    material_code: str | None = None
    quantity: float
    unit_price: float
    unit_price_local: float
    total_amount: float
    received_qty: float
    remark: str | None

    class Config:
        from_attributes = True


# ==================== 采购入库单 ====================

class PurchaseReceiptCreate(BaseModel):
    order_id: int
    warehouse_id: int
    receipt_date: date = Field(default_factory=date.today)
    status: str = "已入库"
    total_qty: float = 0
    remark: str = ""
    operator: str = ""
    items: list["PurchaseReceiptItemCreate"] = []


class PurchaseReceiptUpdate(BaseModel):
    warehouse_id: int | None = None
    receipt_date: date | None = None
    status: str | None = None
    total_qty: float | None = None
    remark: str | None = None
    operator: str | None = None


class PurchaseReceiptOut(BaseModel):
    id: int
    receipt_no: str
    order_id: int
    order_no: str | None = None
    warehouse_id: int
    warehouse_name: str | None = None
    receipt_date: date
    status: str
    total_qty: float
    remark: str | None
    operator: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 采购入库明细 ====================

class PurchaseReceiptItemCreate(BaseModel):
    receipt_id: int | None = None
    order_item_id: int | None = None
    material_id: int
    quantity: float
    unit_price: float = 0
    batch_no: str = ""
    remark: str = ""


class PurchaseReceiptItemUpdate(BaseModel):
    order_item_id: int | None = None
    material_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    batch_no: str | None = None
    remark: str | None = None


class PurchaseReceiptItemOut(BaseModel):
    id: int
    receipt_id: int
    order_item_id: int | None
    material_id: int
    material_name: str | None = None
    material_code: str | None = None
    quantity: float
    unit_price: float
    batch_no: str
    remark: str | None

    class Config:
        from_attributes = True


# ==================== 采购发票 ====================

class PurchaseInvoiceCreate(BaseModel):
    invoice_no: str
    order_id: int
    supplier_id: int
    invoice_date: date = Field(default_factory=date.today)
    invoice_type: str = "专票"
    amount: float = 0
    amount_fc: float = 0
    tax_amount: float = 0
    status: str = "未匹配"
    remark: str = ""


class PurchaseInvoiceUpdate(BaseModel):
    invoice_no: str | None = None
    invoice_date: date | None = None
    invoice_type: str | None = None
    amount: float | None = None
    amount_fc: float | None = None
    tax_amount: float | None = None
    status: str | None = None
    remark: str | None = None


class PurchaseInvoiceOut(BaseModel):
    id: int
    invoice_no: str
    order_id: int
    order_no: str | None = None
    supplier_id: int
    supplier_name: str | None = None
    invoice_date: date
    invoice_type: str
    amount: float
    amount_fc: float
    tax_amount: float
    status: str
    remark: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 应付账款 ====================

class AccountsPayableCreate(BaseModel):
    source_type: str
    source_id: int
    supplier_id: int
    amount: float = 0
    amount_fc: float = 0
    currency_id: int | None = None
    paid_amount: float = 0
    balance: float = 0
    due_date: date | None = None
    status: str = "未付款"


class AccountsPayableUpdate(BaseModel):
    amount: float | None = None
    amount_fc: float | None = None
    paid_amount: float | None = None
    balance: float | None = None
    due_date: date | None = None
    status: str | None = None


class AccountsPayableOut(BaseModel):
    id: int
    source_type: str | None
    source_id: int | None
    supplier_id: int
    supplier_name: str | None = None
    amount: float
    amount_fc: float
    currency_id: int | None
    currency_code: str | None = None
    paid_amount: float
    balance: float
    due_date: date | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 付款记录 ====================

class PaymentCreate(BaseModel):
    supplier_id: int
    payment_date: date = Field(default_factory=date.today)
    amount: float = 0
    amount_fc: float = 0
    currency_id: int | None = None
    exchange_rate: float = 1
    payment_method: str = "银行转账"
    remark: str = ""
    operator: str = ""
    ap_account_ids: int | None = None


class PaymentUpdate(BaseModel):
    supplier_id: int | None = None
    payment_date: date | None = None
    amount: float | None = None
    amount_fc: float | None = None
    currency_id: int | None = None
    exchange_rate: float | None = None
    payment_method: str | None = None
    remark: str | None = None
    operator: str | None = None


class PaymentOut(BaseModel):
    id: int
    payment_no: str
    supplier_id: int
    supplier_name: str | None = None
    payment_date: date
    amount: float
    amount_fc: float
    currency_id: int | None
    currency_code: str | None = None
    exchange_rate: float
    payment_method: str
    remark: str | None
    operator: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 付款核销明细 ====================

class PaymentAllocationCreate(BaseModel):
    payment_id: int
    ap_account_id: int
    allocated_amount: float = 0


class PaymentAllocationOut(BaseModel):
    id: int
    payment_id: int
    payment_no: str | None = None
    ap_account_id: int
    allocated_amount: float
    created_at: datetime

    class Config:
        from_attributes = True

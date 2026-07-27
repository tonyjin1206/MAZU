"""基础档案 Schemas"""

from datetime import date, datetime
from pydantic import BaseModel, Field, model_validator


# ==================== 材料 ====================

class MaterialCreate(BaseModel):
    code: str
    name: str
    spec: str
    model: str = ""
    unit: str
    category: str = "原材料"
    purchase_price: float = 0
    default_supplier_id: int | None = None
    remark: str = ""


class MaterialUpdate(BaseModel):
    name: str | None = None
    spec: str | None = None
    model: str | None = None
    unit: str | None = None
    category: str | None = None
    purchase_price: float | None = None
    default_supplier_id: int | None = None
    remark: str | None = None
    is_active: int | None = None


class MaterialOut(BaseModel):
    id: int
    code: str
    name: str
    spec: str | None
    model: str | None
    unit: str
    category: str | None
    purchase_price: float
    is_active: int
    remark: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 产品 ====================

class ProductCreate(BaseModel):
    code: str
    name_cn: str
    name_en: str = ""
    spec: str
    model: str = ""
    unit: str
    estimated_cost: float = 0
    sale_price: float = 0
    hs_code_id: int | None = None
    hs_code: str = ""
    refund_rate: float = 13
    tax_rate: float = 13
    remark: str = ""


class ProductUpdate(BaseModel):
    name_cn: str | None = None
    name_en: str | None = None
    spec: str | None = None
    model: str | None = None
    unit: str | None = None
    estimated_cost: float | None = None
    sale_price: float | None = None
    hs_code_id: int | None = None
    remark: str | None = None
    is_active: int | None = None


class ProductOut(BaseModel):
    id: int
    code: str
    name_cn: str
    name_en: str | None
    spec: str | None
    model: str | None
    unit: str
    estimated_cost: float
    sale_price: float
    hs_code_id: int | None
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== BOM ====================

class BomItemCreate(BaseModel):
    bom_name: str
    product_id: int
    material_id: int
    quantity: float
    loss_rate: float = 0
    process_id: int | None = None
    sort_order: int = 0


class BomItemUpdate(BaseModel):
    quantity: float | None = None
    loss_rate: float | None = None
    process_id: int | None = None
    sort_order: int | None = None
    is_active: int | None = None


class BomItemOut(BaseModel):
    id: int
    bom_name: str
    product_id: int
    material_id: int
    material_name: str | None = None
    quantity: float
    loss_rate: float
    process_id: int | None
    sort_order: int

    class Config:
        from_attributes = True


# ==================== 工序 ====================

class ProcessCreate(BaseModel):
    code: str
    name: str
    unit_price: float = 0
    remark: str = ""


class ProcessUpdate(BaseModel):
    name: str | None = None
    unit_price: float | None = None
    remark: str | None = None
    is_active: int | None = None


class ProcessOut(BaseModel):
    id: int
    code: str
    name: str
    unit_price: float
    is_active: int

    class Config:
        from_attributes = True


# ==================== 部门 ====================

class DepartmentCreate(BaseModel):
    code: str
    name: str
    parent_id: int | None = None


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str
    parent_id: int | None

    class Config:
        from_attributes = True


# ==================== 人员 ====================

class EmployeeCreate(BaseModel):
    code: str
    name: str
    department_id: int | None = None
    phone: str = ""
    email: str = ""
    position: str = ""


class EmployeeOut(BaseModel):
    id: int
    code: str
    name: str
    department_id: int | None
    department_name: str | None = None
    phone: str | None
    position: str | None

    class Config:
        from_attributes = True


# ==================== 客户 ====================

class CustomerCreate(BaseModel):
    code: str = ""
    name_cn: str
    name_en: str = ""
    country: str
    contact_person: str
    phone: str
    email: str = ""
    tax_id: str
    address: str
    credit_limit: float = 0
    payment_terms: str = "TT"
    account_period: int = 30
    remark: str = ""


class CustomerUpdate(BaseModel):
    name_cn: str | None = None
    name_en: str | None = None
    country: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tax_id: str | None = None
    credit_limit: float | None = None
    payment_terms: str | None = None
    account_period: int | None = None
    remark: str | None = None
    is_active: int | None = None


class CustomerOut(BaseModel):
    id: int
    code: str
    name_cn: str
    name_en: str | None
    country: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    tax_id: str | None
    credit_limit: float
    payment_terms: str
    account_period: int
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 供应商 ====================

class SupplierCreate(BaseModel):
    code: str = ""
    name: str
    contact_person: str
    phone: str
    email: str = ""
    tax_id: str
    address: str
    payment_terms: str = "TT"
    account_period: int = 30
    supply_range: str = ""
    rating: int = 3
    supplier_type: str = "原材料"
    remark: str = ""


class SupplierUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    tax_id: str | None = None
    payment_terms: str | None = None
    account_period: int | None = None
    supply_range: str | None = None
    rating: int | None = None
    supplier_type: str | None = None
    remark: str | None = None
    is_active: int | None = None


class SupplierOut(BaseModel):
    id: int
    code: str
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    tax_id: str | None
    payment_terms: str
    account_period: int
    supplier_type: str
    rating: int
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 委外商 ====================

class OutsourcerCreate(BaseModel):
    supplier_id: int
    lead_time: int = 7


class OutsourcerOut(BaseModel):
    id: int
    supplier_id: int
    supplier_name: str | None = None
    lead_time: int
    is_active: int

    class Config:
        from_attributes = True


# ==================== 仓库 ====================

class WarehouseCreate(BaseModel):
    code: str
    name: str
    wh_type: str
    address: str = ""
    manager: str = ""


class WarehouseOut(BaseModel):
    id: int
    code: str
    name: str
    wh_type: str
    address: str | None
    manager: str | None
    is_active: int

    class Config:
        from_attributes = True


# ==================== 币种 ====================

class CurrencyCreate(BaseModel):
    code: str
    name: str
    symbol: str = ""
    is_base: int = 0


class CurrencyOut(BaseModel):
    id: int
    code: str
    name: str
    symbol: str | None
    is_base: int
    is_active: int

    class Config:
        from_attributes = True


class ExchangeRateCreate(BaseModel):
    currency_id: int
    rate: float
    rate_date: date = Field(default_factory=date.today)
    source: str = "手动"


class ExchangeRateOut(BaseModel):
    id: int
    currency_id: int
    currency_code: str | None = None
    rate: float
    rate_date: date
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== HS编码 ====================

class HsCodeCreate(BaseModel):
    hs_code: str
    name: str
    unit: str
    tax_rate: float = 13
    refund_rate: float = 13
    supervision_conditions: str = ""
    effective_date: date | None = None
    expiry_date: date | None = None
    policy_ref: str = ""
    remark: str = ""


class HsCodeUpdate(BaseModel):
    hs_code: str | None = None
    name: str | None = None
    unit: str | None = None
    tax_rate: float | None = None
    refund_rate: float | None = None
    supervision_conditions: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    policy_ref: str | None = None
    remark: str | None = None
    is_active: int | None = None

    @model_validator(mode="before")
    @classmethod
    def strip_empty_dates(cls, data):
        for f in ("effective_date", "expiry_date"):
            if isinstance(data, dict) and data.get(f) == "":
                data[f] = None
        return data


class HsCodeOut(BaseModel):
    id: int
    hs_code: str
    name: str
    unit: str
    tax_rate: float
    refund_rate: float
    supervision_conditions: str | None
    effective_date: date | None
    expiry_date: date | None
    is_active: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 贸易术语 ====================

class TradeTermCreate(BaseModel):
    code: str
    name: str
    description: str = ""


class TradeTermOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None

    class Config:
        from_attributes = True


# ==================== 产品工艺路线模板 ====================

class ProductProcessTemplateItem(BaseModel):
    """产品工艺路线模板单项（用于批量写入）"""
    process_id: int
    seq: int = 0
    default_outsourcer_id: int | None = None
    default_unit_price: float | None = None


class ProductProcessTemplateOut(BaseModel):
    """产品工艺路线模板输出"""
    id: int
    product_id: int
    process_id: int
    seq: int
    default_outsourcer_id: int | None
    default_unit_price: float | None
    created_at: datetime

    class Config:
        from_attributes = True

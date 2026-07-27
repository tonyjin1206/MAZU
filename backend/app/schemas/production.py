"""生产/委外模块 Schemas"""

from datetime import date, datetime
from pydantic import BaseModel, Field


# ==================== 生产工单 ====================

class ProductionOrderCreate(BaseModel):
    order_no: str = Field(..., description="工单编号")
    sales_order_id: int | None = None
    product_id: int
    quantity: float = Field(..., gt=0, description="计划数量")
    bom_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: str = "pending"
    remark: str = ""
    created_by: str = ""


class ProductionOrderUpdate(BaseModel):
    sales_order_id: int | None = None
    product_id: int | None = None
    quantity: float | None = None
    bom_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: str | None = None
    remark: str | None = None


class ProductionOrderOut(BaseModel):
    id: int
    order_no: str
    sales_order_id: int | None
    product_id: int
    product_name: str | None = None
    quantity: float
    bom_id: int | None
    start_date: date | None
    due_date: date | None
    status: str
    remark: str | None
    created_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 委外工单 ====================

class OutsourcingOrderCreate(BaseModel):
    outsource_no: str = Field(..., description="委外单号")
    production_id: int | None = None
    outsourcer_id: int
    product_id: int
    quantity: float = Field(..., gt=0, description="委外数量")
    unit_price: float = 0
    total_amount: float = 0
    process_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: str = "pending"
    material_status: str = "pending"
    received_qty: float = 0
    remark: str = ""
    created_by: str = ""


class OutsourcingOrderUpdate(BaseModel):
    production_id: int | None = None
    outsourcer_id: int | None = None
    product_id: int | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_amount: float | None = None
    process_id: int | None = None
    start_date: date | None = None
    due_date: date | None = None
    status: str | None = None
    material_status: str | None = None
    received_qty: float | None = None
    remark: str | None = None


class OutsourcingOrderOut(BaseModel):
    id: int
    outsource_no: str
    production_id: int | None
    production_order_no: str | None = None
    outsourcer_id: int
    outsourcer_name: str | None = None
    product_id: int
    product_name: str | None = None
    quantity: float
    unit_price: float
    total_amount: float
    process_id: int | None
    process_name: str | None = None
    start_date: date | None
    due_date: date | None
    status: str
    material_status: str
    received_qty: float
    remark: str | None
    created_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 领料单 ====================

class MaterialIssueItemCreate(BaseModel):
    issue_no: str = Field(..., description="领料单号")
    outsource_id: int
    material_id: int
    batch_no: str = ""
    quantity: float = Field(..., gt=0, description="领料数量")
    unit_price: float = 0
    issue_date: date | None = None
    warehouse_id: int | None = None
    remark: str = ""
    operator: str = ""


class MaterialIssueItemUpdate(BaseModel):
    material_id: int | None = None
    batch_no: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    issue_date: date | None = None
    warehouse_id: int | None = None
    remark: str | None = None
    operator: str | None = None


class MaterialIssueItemOut(BaseModel):
    id: int
    issue_no: str
    outsource_id: int
    outsource_no: str | None = None
    material_id: int
    material_name: str | None = None
    batch_no: str | None
    quantity: float
    unit_price: float
    total_amount: float | None = None
    issue_date: date | None
    warehouse_id: int | None
    warehouse_name: str | None = None
    remark: str | None
    operator: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 委外收货 ====================

class OutsourceReceiptItemCreate(BaseModel):
    receipt_no: str = Field(..., description="收货单号")
    outsource_id: int
    product_id: int
    batch_no: str = ""
    quantity: float = Field(..., gt=0, description="收货数量")
    unit_price: float = 0
    total_amount: float = 0
    receipt_date: date | None = None
    warehouse_id: int | None = None
    remark: str = ""
    operator: str = ""


class OutsourceReceiptItemUpdate(BaseModel):
    product_id: int | None = None
    batch_no: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_amount: float | None = None
    receipt_date: date | None = None
    warehouse_id: int | None = None
    remark: str | None = None
    operator: str | None = None


class OutsourceReceiptItemOut(BaseModel):
    id: int
    receipt_no: str
    outsource_id: int
    outsource_no: str | None = None
    product_id: int
    product_name: str | None = None
    batch_no: str | None
    quantity: float
    unit_price: float
    total_amount: float
    receipt_date: date | None
    warehouse_id: int | None
    warehouse_name: str | None = None
    remark: str | None
    operator: str | None
    created_at: datetime

    class Config:
        from_attributes = True

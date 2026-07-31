"""生产/委外模块 Schemas"""

from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)


# ==================== 领料单 ====================

class MaterialIssueItemCreate(BaseModel):
    issue_no: str = Field(..., description="领料单号")
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

    model_config = ConfigDict(from_attributes=True)

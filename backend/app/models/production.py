"""生产与委外模块模型 — 生产订单、物料清单、工艺路线、发料、完工入库"""

from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class ProductionOrder(Base):
    """生产订单"""
    __tablename__ = "mo_production"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_no = Column(String(64), unique=True, nullable=False, comment="生产订单号: MO-YYYYMMDD-NNN")
    sales_order_id = Column(Integer, ForeignKey("so_order.id"), comment="关联销售订单")
    sales_order_item_id = Column(Integer, ForeignKey("so_order_item.id"), comment="关联销售订单明细行")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False, comment="产品")
    quantity = Column(Float, nullable=False, comment="生产数量")
    bom_id = Column(Integer, comment="使用的BOM ID")
    start_date = Column(Date, comment="计划开始日")
    due_date = Column(Date, comment="计划完成日")
    status = Column(String(16), default="待确认", comment="状态: 待确认/待排产/已排产/生产中/已完成/部分入库/已入库/待采购/采购中/已关闭")
    production_type = Column(String(16), comment="备货方式: 自产/委外/外购")
    requisition_id = Column(Integer, ForeignKey("po_requisition.id"), comment="外购时关联的采购需求")
    total_material_cost = Column(Float, default=0, comment="物料成本合计(全部发出)")
    total_process_cost = Column(Float, default=0, comment="加工费合计(全部完工)")
    received_qty = Column(Float, default=0, comment="已入库数量")
    transferred_material_cost = Column(Float, default=0, comment="已转出材料成本")
    transferred_process_cost = Column(Float, default=0, comment="已转出加工费成本")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    product = relationship("Product")
    materials = relationship("ProductionMaterial", back_populates="production", cascade="all, delete-orphan")
    processes = relationship("ProductionProcess", back_populates="production", cascade="all, delete-orphan",
                             order_by="ProductionProcess.seq")


class ProductionMaterial(Base):
    """生产订单物料需求清单（由BOM展开生成，可修改）"""
    __tablename__ = "mo_production_material"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False)
    planned_qty = Column(Float, default=0, comment="计划用量")
    actual_qty = Column(Float, default=0, comment="已发总量")
    unit_price = Column(Float, default=0, comment="单价")
    subtotal = Column(Float, default=0, comment="小计(=actual_qty*unit_price)")
    sort_order = Column(Integer, default=0)

    production = relationship("ProductionOrder", back_populates="materials")
    material = relationship("Material")


class ProductionProcess(Base):
    """生产订单工艺路线（有序工序清单，替代旧委外工单）"""
    __tablename__ = "mo_production_process"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False)
    process_id = Column(Integer, ForeignKey("fd_process.id"), nullable=False)
    seq = Column(Integer, nullable=False, default=0, comment="工序序号")
    outsourcer_id = Column(Integer, ForeignKey("fd_supplier.id"), comment="委外商(供应商,空=自产)")
    unit_price = Column(Float, default=0, comment="加工单价")
    process_qty = Column(Float, default=0, comment="加工数量(默认=订单数量)")
    process_amount = Column(Float, default=0, comment="加工费金额(=process_qty*unit_price)")
    status = Column(String(16), default="待排产", comment="状态: 待排产/已发料/加工中/已完工")

    production = relationship("ProductionOrder", back_populates="processes")
    process = relationship("Process")
    outsourcer = relationship("Supplier")


class ProductionReceipt(Base):
    """完工入库（成品入库）"""
    __tablename__ = "mo_receipt"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_no = Column(String(64), unique=True, nullable=False, comment="入库单号: FG-YYYYMMDD-NNN")
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False)
    process_id = Column(Integer, ForeignKey("mo_production_process.id"), comment="末道工序")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    batch_no = Column(String(64), nullable=False, comment="成品批次号")
    quantity = Column(Float, nullable=False, comment="入库数量(≤订单数量，允许损耗)")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    material_cost = Column(Float, default=0, comment="转入材料成本")
    process_cost = Column(Float, default=0, comment="转入加工费成本")
    unit_cost = Column(Float, default=0, comment="入库单价(=(材料+加工费)/数量)")
    receipt_date = Column(Date, nullable=False, default=date.today, comment="入库日期")
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    production = relationship("ProductionOrder")
    product = relationship("Product")
    warehouse = relationship("Warehouse")


class ProcessingInvoice(Base):
    """加工费发票"""
    __tablename__ = "mo_processing_invoice"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    invoice_no = Column(String(64), unique=True, nullable=False, comment="发票号: PI-YYYYMMDD-NNN")
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False, comment="关联生产订单")
    receipt_id = Column(Integer, ForeignKey("mo_receipt.id"), nullable=True, comment="关联完工入库单")
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False, comment="供应商(委外商)")
    amount = Column(Float, default=0, comment="加工费金额")
    invoice_date = Column(Date, nullable=False, default=date.today, comment="开票日期")
    remark = Column(Text)
    supplier_name = Column(String(128), comment="销售方名称")
    supplier_tax_id = Column(String(32), comment="销售方税号")
    service_type = Column(String(64), comment="服务类型")
    service_qty = Column(Float, default=0, comment="服务数量")
    unit_price = Column(Float, default=0, comment="单价")
    tax_rate = Column(Float, default=0, comment="税率(%)")
    amount_excl_tax = Column(Float, default=0, comment="不含税金额")
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())


# ==================== 委外订单（销售转外发生成） ====================

class OutsourceOrder(Base):
    """委外订单（销售订单明细转外发生成）"""
    __tablename__ = "os_order"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    outsource_no = Column(String(64), unique=True, nullable=False, comment="委外单号: WO-YYYYMMDD-NNN")
    sales_order_id = Column(Integer, ForeignKey("so_order.id"), comment="关联销售订单")
    sales_item_id = Column(Integer, ForeignKey("so_order_item.id"), comment="关联销售明细行")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False, comment="产品")
    process_id = Column(Integer, ForeignKey("fd_process.id"), comment="工序")
    quantity = Column(Float, nullable=False, comment="委外数量")
    outsourcer_id = Column(Integer, ForeignKey("fd_supplier.id"), comment="委外商(供应商)")
    unit_price = Column(Float, default=0, comment="加工单价")
    amount = Column(Float, default=0, comment="加工费金额")
    supply_type = Column(String(16), default="己方提供", comment="供料方式: 己方提供/包工包料")
    due_date = Column(Date, comment="约定交期")
    status = Column(String(16), default="待确认", comment="状态: 待确认/已审核/已完工/已入库/已退回")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    product = relationship("Product")
    outsourcer = relationship("Supplier")
    process = relationship("Process")
    materials = relationship("OutsourceMaterial", back_populates="outsource_order",
                             cascade="all, delete-orphan", order_by="OutsourceMaterial.id")


class OsClaimMaterial(Base):
    """订单级材料认领（销售明细行转委外时认领原料，只管总发料，不挂工序/供应商）"""
    __tablename__ = "os_claim_material"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sales_item_id = Column(Integer, ForeignKey("so_order_item.id"), nullable=False, comment="销售订单明细行")
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False, comment="材料")
    batch_no = Column(String(64), nullable=False, comment="原料批次号")
    quantity = Column(Float, nullable=False, default=0, comment="认领数量")
    unit_cost = Column(Float, default=0, comment="认领时带出的材料成本")
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material")


class OutsourceMaterial(Base):
    """委外订单材料认领明细（认领原料库批次，自动生成原料出库）"""
    __tablename__ = "os_order_material"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    outsource_order_id = Column(Integer, ForeignKey("os_order.id"), nullable=False, comment="委外订单")
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False, comment="材料")
    batch_no = Column(String(64), nullable=False, comment="原料批次号")
    quantity = Column(Float, nullable=False, default=0, comment="认领数量")
    unit_cost = Column(Float, default=0, comment="认领时带出的材料成本")
    supply_type = Column(String(16), comment="材料级供料方式: 己方提供/包工包料;空=己方提供")
    created_at = Column(DateTime, default=func.now())

    outsource_order = relationship("OutsourceOrder", back_populates="materials")
    material = relationship("Material")


# ==================== 以下为旧模型（保留兼容，新代码不再使用） ====================

class OutsourcingOrder(Base):
    """委外工单（旧，以被 ProductionProcess 替代）"""
    __tablename__ = "mo_outsourcing"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    outsource_no = Column(String(64), unique=True, nullable=False, comment="委外单号: OS-YYYYMMDD-NNN")
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False, comment="关联生产订单")
    outsourcer_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False, comment="委外商(供应商)")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    quantity = Column(Float, nullable=False, comment="加工数量")
    unit_price = Column(Float, default=0, comment="加工单价")
    total_amount = Column(Float, default=0, comment="加工费总额")
    process_id = Column(Integer, ForeignKey("fd_process.id"), comment="工序")
    start_date = Column(Date, comment="发料日期")
    due_date = Column(Date, comment="约定交期")
    status = Column(String(16), default="待发料", comment="状态: 待发料/已发料/加工中/已入库/已完成/已关闭")
    material_status = Column(String(16), default="未发料", comment="发料状态: 未发料/部分发料/已发料")
    received_qty = Column(Float, default=0, comment="已入库数量")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    product = relationship("Product")
    process = relationship("Process")


class MaterialIssueItem(Base):
    """发料记录（关联生产订单+工序）"""
    __tablename__ = "mo_material_issue"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    issue_no = Column(String(64), nullable=False, comment="发料单号")
    production_id = Column(Integer, ForeignKey("mo_production.id"), comment="关联生产订单")
    process_id = Column(Integer, ForeignKey("mo_production_process.id"), comment="关联工序")
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False)
    batch_no = Column(String(64), nullable=False, comment="发料批次号")
    quantity = Column(Float, nullable=False, comment="发料数量")
    unit_price = Column(Float, default=0, comment="单价")
    issue_date = Column(Date, nullable=False, default=date.today, comment="发料日期")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    material = relationship("Material")
    warehouse = relationship("Warehouse")

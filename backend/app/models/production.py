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
    status = Column(String(16), default="待排产", comment="状态: 待排产/已排产/生产中/已完成/部分入库/已入库/已关闭")
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
    outsourcer_id = Column(Integer, ForeignKey("fd_outsourcer.id"), comment="委外商(空=自产)")
    unit_price = Column(Float, default=0, comment="加工单价")
    process_qty = Column(Float, default=0, comment="加工数量(默认=订单数量)")
    process_amount = Column(Float, default=0, comment="加工费金额(=process_qty*unit_price)")
    status = Column(String(16), default="待排产", comment="状态: 待排产/已发料/加工中/已完工")

    production = relationship("ProductionOrder", back_populates="processes")
    process = relationship("Process")
    outsourcer = relationship("Outsourcer")


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


# ==================== 以下为旧模型（保留兼容，新代码不再使用） ====================

class OutsourcingOrder(Base):
    """委外工单（旧，以被 ProductionProcess 替代）"""
    __tablename__ = "mo_outsourcing"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    outsource_no = Column(String(64), unique=True, nullable=False, comment="委外单号: OS-YYYYMMDD-NNN")
    production_id = Column(Integer, ForeignKey("mo_production.id"), nullable=False, comment="关联生产订单")
    outsourcer_id = Column(Integer, ForeignKey("fd_outsourcer.id"), nullable=False, comment="委外商")
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

    outsourcer = relationship("Outsourcer")
    product = relationship("Product")
    process = relationship("Process")
    material_issues = relationship("MaterialIssueItem", backref="outsourcing", lazy="selectin")
    receipts = relationship("OutsourceReceiptItem", backref="outsourcing", lazy="selectin")


class MaterialIssueItem(Base):
    """发料记录（支持新旧两套：outsource_id=旧，production_id+process_id=新）"""
    __tablename__ = "mo_material_issue"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    issue_no = Column(String(64), nullable=False, comment="发料单号")
    outsource_id = Column(Integer, ForeignKey("mo_outsourcing.id"), comment="旧:关联委外工单")
    production_id = Column(Integer, ForeignKey("mo_production.id"), comment="新:关联生产订单")
    process_id = Column(Integer, ForeignKey("mo_production_process.id"), comment="新:关联工序")
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


class OutsourceReceiptItem(Base):
    """委外完工入库明细（旧，以被 ProductionReceipt 替代）"""
    __tablename__ = "mo_outsource_receipt"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    receipt_no = Column(String(64), nullable=False, comment="入库单号: FR-YYYYMMDD-NNN")
    outsource_id = Column(Integer, ForeignKey("mo_outsourcing.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    batch_no = Column(String(64), nullable=False, comment="入库批次号(成品): FG-YYYYMMDD-NNN")
    quantity = Column(Float, nullable=False, comment="入库数量")
    unit_price = Column(Float, default=0, comment="加工单价")
    total_amount = Column(Float, default=0, comment="加工费金额")
    receipt_date = Column(Date, nullable=False, default=date.today, comment="入库日期")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    remark = Column(Text)
    operator = Column(String(32))
    created_at = Column(DateTime, default=func.now())

    product = relationship("Product")
    warehouse = relationship("Warehouse")

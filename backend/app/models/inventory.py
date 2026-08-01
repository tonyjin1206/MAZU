"""库存模型 — 批次库存、库存流水、盘点"""

from datetime import date
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


class WarehouseInventory(Base):
    """批次库存台账"""
    __tablename__ = "inv_inventory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False, comment="仓库")
    material_id = Column(Integer, ForeignKey("fd_material.id"), comment="原料ID")
    product_id = Column(Integer, ForeignKey("fd_product.id"), comment="产品ID")
    batch_no = Column(String(64), nullable=False, comment="批次号")
    quantity = Column(Float, default=0, comment="当前库存数量")
    unit_cost = Column(Float, default=0, comment="单位成本(本币)")
    total_cost = Column(Float, default=0, comment="库存总金额(本币)")
    in_date = Column(Date, nullable=False, comment="入库日期")
    source_type = Column(String(32), comment="来源: purchase/production/transfer/check")
    source_doc_id = Column(Integer, comment="来源单据ID")
    receipt_no = Column(String(64), unique=True, comment="入库单号: 每次入库唯一")
    is_frozen = Column(Integer, default=0, comment="1=冻结 0=正常")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse", backref="inventories")


class StockTransaction(Base):
    """库存流水（每一笔出入库的明细记录）"""
    __tablename__ = "inv_transaction"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trans_type = Column(String(32), nullable=False, comment="类型")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("fd_material.id"), comment="原料ID")
    product_id = Column(Integer, ForeignKey("fd_product.id"), comment="产品ID")
    batch_no = Column(String(64), nullable=False, comment="批次号")
    quantity = Column(Float, nullable=False, comment="数量(入库正/出库负)")
    unit_cost = Column(Float, default=0, comment="单位成本")
    total_amount = Column(Float, default=0, comment="总金额(本币)")
    before_qty = Column(Float, default=0, comment="操作前库存")
    after_qty = Column(Float, default=0, comment="操作后库存")
    before_cost = Column(Float, default=0, comment="操作前库存金额")
    after_cost = Column(Float, default=0, comment="操作后库存金额")
    source_doc_type = Column(String(32), comment="来源单据类型")
    source_doc_no = Column(String(64), comment="来源单据编号")
    operator = Column(String(32), comment="操作人")
    trans_no = Column(String(64), unique=True, comment="库存流水号: ST-YYYYMMDD-NNN")
    trans_date = Column(DateTime, default=func.now())
    remark = Column(Text)

    warehouse = relationship("Warehouse")


class StockCheck(Base):
    """库存盘点计划"""
    __tablename__ = "inv_stock_check"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    check_no = Column(String(64), unique=True, nullable=False, comment="盘点单号")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False)
    check_type = Column(String(16), default="全部", comment="盘点类型: 全部/抽盘")
    status = Column(String(16), default="待盘点", comment="状态: 待盘点/盘点中/已完成")
    check_date = Column(Date, nullable=False, comment="盘点日期")
    checker = Column(String(32), comment="盘点人")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)

    warehouse = relationship("Warehouse")
    items = relationship("StockCheckItem", backref="check", lazy="selectin")


class StockCheckItem(Base):
    """盘点明细"""
    __tablename__ = "inv_stock_check_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    check_id = Column(Integer, ForeignKey("inv_stock_check.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"))
    material_id = Column(Integer, ForeignKey("fd_material.id"), comment="原料")
    product_id = Column(Integer, ForeignKey("fd_product.id"), comment="产品")
    batch_no = Column(String(64), comment="批次号")
    book_qty = Column(Float, default=0, comment="账面数量")
    actual_qty = Column(Float, default=0, comment="实盘数量")
    diff_qty = Column(Float, default=0, comment="差异数量")
    remark = Column(Text)


class StockInOrder(Base):
    """成品入库单（销售转入库/采购转成品库/委外完工 → 收货确认）"""
    __tablename__ = "inv_stock_in"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stock_in_no = Column(String(64), comment="旧待入库单号(已废弃，不再生成)")
    source_type = Column(String(16), nullable=False, comment="来源: sales/purchase/outsource")
    sales_order_id = Column(Integer, ForeignKey("so_order.id"), comment="关联销售订单")
    sales_item_id = Column(Integer, ForeignKey("so_order_item.id"), comment="关联销售明细行")
    purchase_order_id = Column(Integer, ForeignKey("po_order.id"), comment="关联采购订单")
    purchase_item_id = Column(Integer, ForeignKey("po_order_item.id"), comment="关联采购明细行")
    outsource_order_id = Column(Integer, ForeignKey("os_order.id"), comment="关联委外订单")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False, comment="产品")
    quantity = Column(Float, nullable=False, comment="应入数量")
    received_qty = Column(Float, default=0, comment="已入数量")
    status = Column(String(16), default="待入库", comment="状态: 待入库/部分入库/已入库/已退回")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), comment="收货仓库")
    remark = Column(Text)
    created_by = Column(String(32))
    created_at = Column(DateTime, default=func.now())

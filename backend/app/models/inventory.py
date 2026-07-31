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
    is_frozen = Column(Integer, default=0, comment="1=冻结 0=正常")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse", backref="inventories")
    material = relationship("Material")
    product = relationship("Product")


class Stocktake(Base):
    """盘点单"""
    __tablename__ = "inv_stocktake"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stocktake_no = Column(String(64), unique=True, nullable=False, comment="盘点单号: STK-YYYYMMDD-NNN")
    warehouse_id = Column(Integer, ForeignKey("fd_warehouse.id"), nullable=False, comment="盘点仓库")
    status = Column(String(16), default="草稿", comment="状态: 草稿/已提交")
    operator = Column(String(32), comment="盘点人")
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    submitted_at = Column(DateTime, comment="提交时间")

    warehouse = relationship("Warehouse")
    items = relationship("StocktakeItem", backref="stocktake", lazy="selectin", cascade="all, delete-orphan")


class StocktakeItem(Base):
    """盘点明细（一行=一个批次）"""
    __tablename__ = "inv_stocktake_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    stocktake_id = Column(Integer, ForeignKey("inv_stocktake.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("fd_material.id"), comment="原料ID(与产品互斥)")
    product_id = Column(Integer, ForeignKey("fd_product.id"), comment="产品ID")
    batch_no = Column(String(64), nullable=False, comment="批次号")
    book_qty = Column(Float, default=0, comment="账面数量")
    actual_qty = Column(Float, default=0, comment="实盘数量")
    unit_cost = Column(Float, default=0, comment="盘点时批次成本")
    remark = Column(Text)

    material = relationship("Material")
    product = relationship("Product")


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

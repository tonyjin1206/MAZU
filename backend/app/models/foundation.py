"""基础档案模型 — 材料、产品、BOM、工序、部门、人员、客户、供应商、仓库、币种、HS编码"""

from datetime import date
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from app.database import Base


# ==================== 基础物料 ====================

class Material(Base):
    """原辅材料"""
    __tablename__ = "fd_material"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, index=True, nullable=False, comment="物料编码")
    name = Column(String(128), nullable=False, comment="物料名称")
    spec = Column(String(256), comment="规格")
    model = Column(String(128), comment="型号")
    unit = Column(String(16), nullable=False, default="个", comment="计量单位")
    category = Column(String(32), default="原材料", comment="类别: 原材料/辅料/包装等")
    purchase_price = Column(Float, default=0, comment="采购单价")
    default_supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), comment="默认供应商")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Product(Base):
    """产品档案（定制成品）"""
    __tablename__ = "fd_product"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, index=True, nullable=False, comment="产品编码")
    name_cn = Column(String(128), nullable=False, comment="中文名称")
    name_en = Column(String(256), comment="英文名称")
    spec = Column(String(256), comment="规格")
    model = Column(String(128), comment="型号")
    unit = Column(String(16), nullable=False, default="个", comment="计量单位")
    estimated_cost = Column(Float, default=0, comment="预估成本")
    sale_price = Column(Float, default=0, comment="销售单价")
    hs_code_id = Column(Integer, ForeignKey("fd_hs_code.id"), comment="关联HS编码")
    default_bom_id = Column(Integer, comment="默认BOM ID")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    hs_code = relationship("HsCode", backref="products")


class BomItem(Base):
    """BOM（物料清单）"""
    __tablename__ = "fd_bom_item"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    bom_name = Column(String(128), nullable=False, comment="BOM名称/版本")
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False, comment="成品ID")
    material_id = Column(Integer, ForeignKey("fd_material.id"), nullable=False, comment="子件ID")
    quantity = Column(Float, nullable=False, default=1, comment="标准用量")
    loss_rate = Column(Float, default=0, comment="损耗率(%)")
    process_id = Column(Integer, ForeignKey("fd_process.id"), comment="关联工序")
    sort_order = Column(Integer, default=0, comment="排序")
    is_active = Column(Integer, default=1, comment="1=启用 0=停用")
    created_at = Column(DateTime, default=func.now())

    product = relationship("Product", backref="bom_items")
    material = relationship("Material", backref="bom_items")


class Process(Base):
    """工序信息"""
    __tablename__ = "fd_process"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, comment="工序编码")
    name = Column(String(128), nullable=False, comment="工序名称")
    standard_hours = Column(Float, default=0, comment="标准工时(小时)")
    is_outsource = Column(Integer, default=0, comment="0=自制 1=委外")
    unit_price = Column(Float, default=0, comment="委外加工单价")
    is_active = Column(Integer, default=1)
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())


class ProductProcess(Base):
    """产品工艺路线模板"""
    __tablename__ = "fd_product_process"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("fd_product.id"), nullable=False)
    process_id = Column(Integer, ForeignKey("fd_process.id"), nullable=False)
    seq = Column(Integer, nullable=False, default=0, comment="工序序号")
    default_outsourcer_id = Column(Integer, ForeignKey("fd_outsourcer.id"), comment="默认委外商")
    default_unit_price = Column(Float, default=0, comment="默认加工单价")
    created_at = Column(DateTime, default=func.now())

    product = relationship("Product", backref="process_templates")
    process = relationship("Process")
    default_outsourcer = relationship("Outsourcer")


# ==================== 组织架构 ====================

class Department(Base):
    """部门"""
    __tablename__ = "fd_department"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, comment="部门编码")
    name = Column(String(64), nullable=False, comment="部门名称")
    parent_id = Column(Integer, ForeignKey("fd_department.id"), comment="上级部门")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())


class Employee(Base):
    """人员"""
    __tablename__ = "fd_employee"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, comment="员工编号")
    name = Column(String(32), nullable=False, comment="姓名")
    department_id = Column(Integer, ForeignKey("fd_department.id"), comment="所属部门")
    phone = Column(String(32), comment="电话")
    email = Column(String(128), comment="邮箱")
    position = Column(String(64), comment="岗位")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    department = relationship("Department", backref="employees")


# ==================== 客户 ====================

class Customer(Base):
    """客户"""
    __tablename__ = "fd_customer"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, comment="客户编码")
    name_cn = Column(String(128), nullable=False, comment="中文名称")
    name_en = Column(String(256), comment="英文名称")
    country = Column(String(64), comment="国家/地区")
    contact_person = Column(String(64), comment="联系人")
    phone = Column(String(32), comment="电话")
    email = Column(String(128), comment="邮箱")
    address = Column(String(256), comment="地址")
    tax_id = Column(String(64), comment="税号")
    credit_limit = Column(Float, default=0, comment="信用额度")
    payment_terms = Column(String(64), default="TT", comment="结算方式: TT/LC/DP/DA")
    account_period = Column(Integer, default=30, comment="账期(天)")
    bank_name = Column(String(128), comment="开户行")
    bank_account = Column(String(64), comment="银行账号")
    default_tax_rate = Column(Float, default=13, comment="默认税率(%)")
    rating = Column(Integer, default=3, comment="评级 1-5")
    is_active = Column(Integer, default=1)
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ==================== 供应商 ====================

class Supplier(Base):
    """供应商"""
    __tablename__ = "fd_supplier"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False, comment="供应商编码")
    name = Column(String(128), nullable=False, comment="供应商名称")
    country = Column(String(64), comment="国家/地区")
    contact_person = Column(String(64), comment="联系人")
    phone = Column(String(32), comment="电话")
    email = Column(String(128), comment="邮箱")
    address = Column(String(256), comment="地址")
    tax_id = Column(String(64), comment="税号")
    payment_terms = Column(String(64), default="TT", comment="付款方式")
    account_period = Column(Integer, default=30, comment="账期(天)")
    supply_range = Column(String(256), comment="供货范围")
    rating = Column(Integer, default=3, comment="评级 1-5")
    supplier_type = Column(String(32), default="原材料", comment="类型: 原材料/委外/辅料")
    bank_name = Column(String(128), comment="开户行")
    bank_account = Column(String(64), comment="银行账号")
    default_tax_rate = Column(Float, default=13, comment="默认税率(%)")
    is_active = Column(Integer, default=1)
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Outsourcer(Base):
    """委外加工商（供应商的委外类型，独立管理方便筛选）"""
    __tablename__ = "fd_outsourcer"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("fd_supplier.id"), nullable=False, comment="关联供应商")
    process_ids = Column(String(256), comment="可加工工序ID列表(逗号分隔)")
    unit_price_note = Column(String(256), comment="加工单价说明")
    lead_time = Column(Integer, default=7, comment="标准交期(天)")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    supplier = relationship("Supplier", backref="outsourcers")


# ==================== 仓库 ====================

class Warehouse(Base):
    """仓库"""
    __tablename__ = "fd_warehouse"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(32), unique=True, nullable=False, comment="仓库编码")
    name = Column(String(64), nullable=False, comment="仓库名称")
    wh_type = Column(String(32), default="原料仓", comment="类型: 原料仓/成品仓/半成品仓/不良品仓")
    address = Column(String(256), comment="地址")
    manager = Column(String(32), comment="负责人")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Warehouse {self.name}>"


# ==================== 币种 ====================

class Currency(Base):
    """币种"""
    __tablename__ = "fd_currency"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(8), unique=True, nullable=False, comment="币种代码: CNY/USD/EUR/JPY")
    name = Column(String(32), nullable=False, comment="币种名称")
    symbol = Column(String(8), comment="符号: ¥/$/€")
    is_base = Column(Integer, default=0, comment="1=本位币(CNY)")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.now())


class ExchangeRate(Base):
    """汇率"""
    __tablename__ = "fd_exchange_rate"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    currency_id = Column(Integer, ForeignKey("fd_currency.id"), nullable=False, comment="币种")
    rate = Column(Float, nullable=False, comment="兑本位币汇率")
    rate_date = Column(Date, nullable=False, comment="生效日期")
    source = Column(String(32), default="手动", comment="来源: 手动/API")
    created_at = Column(DateTime, default=func.now())

    currency = relationship("Currency", backref="rates")


# ==================== HS编码 & 退税率 ====================

class HsCode(Base):
    """HS编码与退税率"""
    __tablename__ = "fd_hs_code"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hs_code = Column(String(16), unique=True, nullable=False, comment="HS编码")
    name = Column(String(256), nullable=False, comment="商品名称")
    unit = Column(String(16), default="个", comment="计量单位")
    tax_rate = Column(Float, default=13, comment="增值税率(%)")
    refund_rate = Column(Float, default=13, comment="退税率(%)")
    supervision_conditions = Column(String(256), comment="监管条件")
    effective_date = Column(Date, comment="退税率生效日期")
    expiry_date = Column(Date, comment="退税率失效日期")
    policy_ref = Column(String(128), comment="政策文号")
    is_active = Column(Integer, default=1)
    remark = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ==================== 贸易术语 ====================

class TradeTerm(Base):
    """贸易术语（Incoterms）"""
    __tablename__ = "fd_trade_term"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code = Column(String(8), unique=True, nullable=False, comment="术语代码: FOB/CIF/CNF/EXW/DDP")
    name = Column(String(64), nullable=False, comment="术语名称")
    description = Column(Text, comment="费用构成说明")
    is_active = Column(Integer, default=1)


class Company(Base):
    """公司信息"""
    __tablename__ = "fd_company"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, comment="公司名称")
    name_en = Column(String(256), comment="英文名称")
    tax_id = Column(String(32), comment="纳税人识别号")
    address = Column(String(256), comment="地址")
    phone = Column(String(32), comment="电话")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class CompanyContact(Base):
    """公司联系人"""
    __tablename__ = "fd_company_contact"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey("fd_company.id"), nullable=False)
    seq = Column(Integer, default=1, comment="序号")
    name = Column(String(64), nullable=False, comment="姓名")
    role = Column(String(32), comment="岗位: 管理员/采购员/销售员/开票员/库存管理员")
    phone = Column(String(32), comment="电话")
    email = Column(String(128), comment="邮箱")
    created_at = Column(DateTime, default=func.now())

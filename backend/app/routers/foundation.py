"""基础档案 API 路由 — 使用通用 CRUD 注册所有基础数据"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import (
    Material, Product, BomItem, Process,
    Department, Employee,
    Customer, Supplier,
    Warehouse, Currency, ExchangeRate,
    HsCode, TradeTerm,
    Company, CompanyContact,
    ProductProcess,
    SystemParam,
    ProductCustomer,
)
from app.models.sales import (
    SalesQuote, SalesOrder, SalesOrderItem, SalesDelivery, CustomsDeclaration,
    SalesInvoice, AccountsReceivable, Collection,
)
from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem, PurchaseReceipt, PurchaseReceiptItem, PurchaseInvoice,
    AccountsPayable, Payment,
)
from app.models.production import (
    OutsourcingOrder, ProcessingInvoice,
    ProductionOrder, ProductionMaterial, ProductionReceipt, MaterialIssueItem,
)
from app.models.inventory import (
    WarehouseInventory, StockTransaction, StockCheckItem,
)
from app.models.tax_refund import TaxRefundInputInvoice
from app.schemas.foundation import (
    MaterialCreate, MaterialUpdate, MaterialOut,
    ProductCreate, ProductUpdate, ProductOut, ProductCustomersUpdate,
    BomItemCreate, BomItemUpdate, BomItemOut,
    ProcessCreate, ProcessUpdate, ProcessOut,
    DepartmentCreate, DepartmentOut,
    EmployeeCreate, EmployeeOut,
    CustomerCreate, CustomerUpdate, CustomerOut,
    SupplierCreate, SupplierUpdate, SupplierOut,
    WarehouseCreate, WarehouseOut,
    CurrencyCreate, CurrencyOut,
    ExchangeRateCreate, ExchangeRateOut,
    HsCodeCreate, HsCodeUpdate, HsCodeOut,
    TradeTermCreate, TradeTermOut,
    ProductProcessTemplateItem, ProductProcessTemplateOut,
    SystemParamCreate, SystemParamUpdate, SystemParamOut, SystemParamOptionOut,
)
from app.routers.base_crud import register_crud
from app.utils.auth import get_current_user

router = APIRouter()

# ==================== 参数设置（专用路由，必须注册在通用 CRUD 之前）====================

@router.get("/params/groups", response_model=list[str], tags=["基础档案-参数设置"])
def list_param_groups(db: Session = Depends(get_db)):
    """所有参数组名（按名称排序）"""
    rows = db.query(SystemParam.group_name).distinct().order_by(SystemParam.group_name).all()
    return [r[0] for r in rows]


@router.get("/params/options", response_model=list[SystemParamOptionOut], tags=["基础档案-参数设置"])
def list_param_options(group: str = Query(..., description="参数组名"), db: Session = Depends(get_db)):
    """某参数组的启用选项（供下拉选择）"""
    rows = (db.query(SystemParam)
            .filter(SystemParam.group_name == group, SystemParam.is_active == 1)
            .order_by(SystemParam.sort_order, SystemParam.id)
            .all())
    return [{"key": r.param_key, "label": r.param_label, "parent_key": r.parent_key or ""} for r in rows]


@router.get("/params/group/{group_name}", response_model=dict, tags=["基础档案-参数设置"])
def list_params_by_group(group_name: str, db: Session = Depends(get_db)):
    """某参数组的完整列表（含停用项，供维护页）"""
    rows = (db.query(SystemParam)
            .filter(SystemParam.group_name == group_name)
            .order_by(SystemParam.sort_order, SystemParam.id)
            .all())
    items = [SystemParamOut.model_validate(r).model_dump() for r in rows]
    return {"total": len(items), "items": items}


# ==================== 注册所有基础档案 CRUD ====================

def _process_delete_guard(db: Session, item: Process):
    """工序删除保护：被产品工艺引用的工序不能删，只能停用"""
    from app.models.foundation import ProductProcess
    if db.query(ProductProcess).filter(ProductProcess.process_id == item.id).first():
        raise HTTPException(400, "该工序已被产品工艺引用，不能删除，只能停用")


register_crud(router, Process,        ProcessCreate,    ProcessUpdate,    ProcessOut,    "processes",   "基础档案-工序",   search_fields=["code", "name"], delete_guard=_process_delete_guard)
register_crud(router, Department,     DepartmentCreate, None,             DepartmentOut, "departments", "基础档案-部门",   search_fields=["code", "name"])
register_crud(router, Employee,       EmployeeCreate,   None,             EmployeeOut,   "employees",   "基础档案-人员",   search_fields=["code", "name"])
def _warehouse_delete_guard(db: Session, item: Warehouse):
    """仓库删除保护：被库存单据引用的仓库不能删，只能停用"""
    from app.models.inventory import StockInOrder, WarehouseInventory, StockTransaction
    refs = [
        ("待入库单", db.query(StockInOrder).filter(StockInOrder.warehouse_id == item.id).count()),
        ("库存批次", db.query(WarehouseInventory).filter(WarehouseInventory.warehouse_id == item.id).count()),
        ("库存流水", db.query(StockTransaction).filter(StockTransaction.warehouse_id == item.id).count()),
    ]
    used = [(name, n) for name, n in refs if n > 0]
    if used:
        desc = "、".join(f"{name}{n}条" for name, n in used)
        raise HTTPException(400, f"该仓库已被使用（{desc}），不能删除，只能停用")


register_crud(router, Warehouse,      WarehouseCreate,  None,             WarehouseOut,  "warehouses",  "基础档案-仓库",   search_fields=["code", "name"], delete_guard=_warehouse_delete_guard)
register_crud(router, Currency,       CurrencyCreate,   None,             CurrencyOut,   "currencies",  "基础档案-币种",   search_fields=["code", "name"])
register_crud(router, ExchangeRate,   ExchangeRateCreate, None,           ExchangeRateOut, "exchange-rates", "基础档案-汇率", search_fields=["currency_id"])
register_crud(router, HsCode,         HsCodeCreate,     HsCodeUpdate,     HsCodeOut,     "hs-codes",    "基础档案-HS编码", search_fields=["hs_code", "name"])
register_crud(router, TradeTerm,      TradeTermCreate,  None,             TradeTermOut,  "trade-terms", "基础档案-贸易术语", search_fields=["code", "name"])
def _params_delete_guard(db: Session, item: SystemParam):
    """参数删除保护：被业务数据引用的参数不能删，只能停用（防止历史数据错乱）"""
    from app.models.foundation import Customer, Material, Product, Supplier
    from app.models.purchase import PurchaseOrder
    from app.models.sales import SalesOrder
    label = item.param_label
    g = item.group_name
    refs = []
    if g == "country":
        refs.append(("客户", db.query(Customer).filter(Customer.country == label).count()))
        refs.append(("供应商", db.query(Supplier).filter(Supplier.country == label).count()))
    elif g == "supplier_type":
        refs.append(("供应商", db.query(Supplier).filter(Supplier.supplier_type == label).count()))
    elif g == "unit":
        refs.append(("材料", db.query(Material).filter(Material.unit == label).count()))
        refs.append(("产品", db.query(Product).filter(Product.unit == label).count()))
    elif g in ("material_main_category", "material_category"):
        refs.append(("材料", db.query(Material).filter(Material.category == label).count()))
    elif g == "material_sub_category":
        refs.append(("材料", db.query(Material).filter(Material.category_sub == label).count()))
    elif g == "payment_method":
        refs.append(("采购订单", db.query(PurchaseOrder).filter(PurchaseOrder.payment_terms == label).count()))
        refs.append(("销售订单", db.query(SalesOrder).filter(SalesOrder.payment_terms == label).count()))
    used = [(name, n) for name, n in refs if n > 0]
    if used:
        desc = "、".join(f"{name}{n}条" for name, n in used)
        raise HTTPException(400, f"该参数已被使用（{desc}），不能删除，只能停用")


register_crud(router, SystemParam,    SystemParamCreate, SystemParamUpdate, SystemParamOut, "params",      "基础档案-参数设置", search_fields=["group_name", "param_key", "param_label"], delete_guard=_params_delete_guard)


@router.delete("/params/{item_id}/hard", tags=["基础档案-参数设置"])
def hard_delete_param(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """物理删除参数（通用 CRUD 是软删除，会与唯一约束冲突导致无法重建同名参数）"""
    item = db.query(SystemParam).filter(SystemParam.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="参数不存在")
    _params_delete_guard(db, item)  # 被引用的参数同样禁止物理删除
    db.delete(item)
    db.commit()
    return {"message": "已删除"}


def _ensure_unique_name(db, model, name_field, name_value, exclude_id=None, label="名称"):
    """名称唯一性校验：新增/编辑时重复禁止保存（含停用档案，防历史数据混淆）"""
    name_value = (name_value or "").strip()
    if not name_value:
        return
    q = db.query(model).filter(getattr(model, name_field) == name_value)
    if exclude_id:
        q = q.filter(model.id != exclude_id)
    dup = q.first()
    if dup:
        dup_code = getattr(dup, "code", "") or ""
        raise HTTPException(400, f"该{label}已存在：「{getattr(dup, name_field)}」（编码{dup_code}），请勿重复")


# ==================== 材料自定义创建（自动编码 RM+6位流水）====================

@router.post("/materials", tags=["基础档案-材料"])
def create_material(data: MaterialCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    code = data.code or _next_code(db, Material, "RM")
    _ensure_unique_name(db, Material, "name", data.name, label="材料名称")
    m = Material(code=code, name=data.name, spec=data.spec, model=data.model or "",
                 unit=data.unit, category=data.category or "原材料",
                 purchase_price=data.purchase_price or 0,
                 default_supplier_id=data.default_supplier_id, remark=data.remark or "")
    db.add(m)
    db.commit()
    db.refresh(m)
    return MaterialOut.model_validate(m)


@router.get("/materials", tags=["基础档案-材料"])
def list_materials(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                   keyword: str = Query(""), code: str = Query(""),
                   name: str = Query(""), spec: str = Query(""),
                   category: str = Query(""),
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    query = db.query(Material)
    if keyword:
        from sqlalchemy import or_
        query = query.filter(or_(Material.code.like(f"%{keyword}%"),
                                 Material.name.like(f"%{keyword}%")))
    else:
        if code:
            query = query.filter(Material.code.like(f"%{code}%"))
        if name:
            query = query.filter(Material.name.like(f"%{name}%"))
        if spec:
            query = query.filter(Material.spec.like(f"%{spec}%"))
    if category:
        query = query.filter(Material.category == category)
    total = query.count()
    items = query.order_by(Material.code.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [MaterialOut.model_validate(m) for m in items]}


@router.put("/materials/{item_id}", response_model=MaterialOut, tags=["基础档案-材料"])
def update_material(item_id: int, data: MaterialUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Material).filter(Material.id == item_id).first()
    if not item:
        raise HTTPException(404, "材料不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        _ensure_unique_name(db, Material, "name", update_data["name"], exclude_id=item_id, label="材料名称")
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return MaterialOut.model_validate(item)


@router.delete("/materials/{item_id}", tags=["基础档案-材料"])
def delete_material(item_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Material).filter(Material.id == item_id).first()
    if not item:
        raise HTTPException(404, "材料不存在")
    biz = _has_business_refs(db, Material, item_id, MATERIAL_REFS)
    if biz:
        raise HTTPException(400, f"该材料已有{biz}数据，不允许删除，可停用")
    db.delete(item)
    db.commit()
    return {"message": "材料已删除"}


# ==================== 产品自定义创建（HS编码自动关联 + 自动编码 P+6位流水）====================

@router.post("/products", tags=["基础档案-产品"])
def create_product_with_hs(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建产品，自动创建/关联 HS 编码，自动编码 FG+6位流水"""
    code = data.code or _next_code(db, Product, "FG")
    _ensure_unique_name(db, Product, "name_cn", data.name_cn, label="产品名称")
    hs_code_id = data.hs_code_id
    if data.hs_code and not hs_code_id:
        existing = db.query(HsCode).filter(HsCode.hs_code == data.hs_code).first()
        if existing:
            hs_code_id = existing.id
        else:
            hs = HsCode(
                hs_code=data.hs_code,
                name=data.name_cn,
                unit=data.unit,
                tax_rate=data.tax_rate or 13,
                refund_rate=data.refund_rate or 13,
            )
            db.add(hs)
            db.flush()
            hs_code_id = hs.id
    product = Product(
        code=code, name_cn=data.name_cn, name_en=data.name_en or "",
        spec=data.spec, model=data.model or "", unit=data.unit,
        estimated_cost=data.estimated_cost or 0, sale_price=data.sale_price or 0,
        hs_code_id=hs_code_id, can_purchase=data.can_purchase or 0, remark=data.remark or "",
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductOut.model_validate(product)


@router.get("/products", tags=["基础档案-产品"])
def list_products(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    keyword: str = Query(""), code: str = Query(""),
    name_cn: str = Query(""), spec: str = Query(""),
    customer_id: int | None = Query(None, description="只返回关联了该客户的产品（销售下单用）"),
    is_active: int | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(Product)
    if customer_id:
        query = query.join(ProductCustomer, ProductCustomer.product_id == Product.id).filter(ProductCustomer.customer_id == customer_id)
    if keyword:
        from sqlalchemy import or_
        query = query.filter(or_(Product.code.like(f"%{keyword}%"),
                                 Product.name_cn.like(f"%{keyword}%"),
                                 Product.name_en.like(f"%{keyword}%")))
    else:
        if code:
            query = query.filter(Product.code.like(f"%{code}%"))
        if name_cn:
            query = query.filter(Product.name_cn.like(f"%{name_cn}%"))
        if spec:
            query = query.filter(Product.spec.like(f"%{spec}%"))
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    total = query.count()
    items = query.order_by(Product.code.asc()).offset((page-1)*page_size).limit(page_size).all()
    result = []
    for item in items:
        obj = ProductOut.model_validate(item).model_dump()
        obj["customer_count"] = db.query(ProductCustomer.id).filter(ProductCustomer.product_id == item.id).count()
        if item.hs_code:
            obj["hs_code"] = item.hs_code.hs_code
            obj["refund_rate"] = item.hs_code.refund_rate
            obj["tax_rate"] = item.hs_code.tax_rate
        result.append(obj)
    return {"total": total, "page": page, "page_size": page_size, "items": result}


@router.get("/products/{item_id}", response_model=ProductOut, tags=["基础档案-产品"])
def get_product(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Product).filter(Product.id == item_id).first()
    if not item:
        raise HTTPException(404, "产品不存在")
    obj = ProductOut.model_validate(item).model_dump()
    obj["customer_count"] = db.query(ProductCustomer.id).filter(ProductCustomer.product_id == item.id).count()
    links = (db.query(ProductCustomer, Customer)
             .join(Customer, Customer.id == ProductCustomer.customer_id)
             .filter(ProductCustomer.product_id == item.id).all())
    obj["customers"] = [{"id": c.id, "name": c.name_cn, "code": c.code} for _, c in links]
    return obj


@router.put("/products/{item_id}/customers", tags=["基础档案-产品"])
def update_product_customers(item_id: int, data: ProductCustomersUpdate,
                             db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """设置产品关联客户（全量替换）"""
    product = db.query(Product).filter(Product.id == item_id).first()
    if not product:
        raise HTTPException(404, "产品不存在")
    # 校验客户存在
    ids = list(dict.fromkeys(data.customer_ids))
    if ids:
        exist = db.query(Customer.id).filter(Customer.id.in_(ids)).count()
        if exist != len(ids):
            raise HTTPException(400, "存在无效的客户")
    db.query(ProductCustomer).filter(ProductCustomer.product_id == item_id).delete()
    for cid in ids:
        db.add(ProductCustomer(product_id=item_id, customer_id=cid))
    db.commit()
    return {"message": "关联客户已更新"}


@router.put("/products/{item_id}", response_model=ProductOut, tags=["基础档案-产品"])
def update_product(
    item_id: int, data: ProductUpdate,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    item = db.query(Product).filter(Product.id == item_id).first()
    if not item:
        raise HTTPException(404, "产品不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "name_cn" in update_data:
        _ensure_unique_name(db, Product, "name_cn", update_data["name_cn"], exclude_id=item_id, label="产品名称")
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return ProductOut.model_validate(item)


@router.delete("/products/{item_id}", tags=["基础档案-产品"])
def delete_product(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Product).filter(Product.id == item_id).first()
    if not item:
        raise HTTPException(404, "产品不存在")
    biz = _has_business_refs(db, Product, item_id, PRODUCT_REFS)
    if biz:
        raise HTTPException(400, f"该产品已有{biz}数据，不允许删除，可停用")
    db.delete(item)
    db.commit()
    return {"message": "产品已删除"}


# ==================== 委外商（供应商类型=委外，不单独建表） ====================

@router.get("/outsourcers", tags=["基础档案-委外商"])
def list_outsourcers(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                     keyword: str = Query(""),
                     db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """委外商列表 = 供应商中 supplier_type=委外 的档案"""
    query = db.query(Supplier).filter(Supplier.supplier_type == "委外")
    if keyword:
        query = query.filter(Supplier.name.like(f"%{keyword}%") | Supplier.code.like(f"%{keyword}%"))
    total = query.count()
    items = query.order_by(Supplier.id.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": s.id, "supplier_id": s.id, "code": s.code, "name": s.name,
         "contact_person": s.contact_person, "phone": s.phone, "is_active": s.is_active}
        for s in items
    ]}


# ==================== 客户自定义创建（自动编码 CU+6位流水）====================

def _next_code(db, model, prefix: str, field="code"):
    """生成编码: 前缀 + 6位流水号（遍历取数字后缀最大者，跳过历史非数字编码）"""
    col = getattr(model, field)
    rows = db.query(col).filter(col.like(f"{prefix}%")).all()
    max_num = 0
    for (code,) in rows:
        suffix = str(code)[len(prefix):]
        if suffix.isdigit():
            max_num = max(max_num, int(suffix))
    return f"{prefix}{max_num + 1:06d}"


@router.get("/customers/next-code", tags=["基础档案-客户"])
def preview_customer_code(db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """预览下一个客户编码（仅预览，不消耗流水）"""
    return {"code": _next_code(db, Customer, "CU")}


@router.post("/customers", tags=["基础档案-客户"])
def create_customer(data: CustomerCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    code = _next_code(db, Customer, "CU")  # 编码强制自动生成，不允许手动输入
    _ensure_unique_name(db, Customer, "name_cn", data.name_cn, label="客户名称")
    # 编码唯一性校验（避免唯一约束冲突 → 500）
    if db.query(Customer).filter(Customer.code == code).first():
        raise HTTPException(409, f"客户编码已存在: {code}")
    c = Customer(code=code, name_cn=data.name_cn, name_en=data.name_en or "",
                 country=data.country or "", contact_person=data.contact_person or "",
                 phone=data.phone or "", email=data.email or "", tax_id=data.tax_id or "",
                 address=data.address or "", credit_limit=data.credit_limit or 0,
                 payment_terms=data.payment_terms or "TT",
                 account_period=data.account_period or 30,
                 bank_name=data.bank_name or "", bank_account=data.bank_account or "",
                 default_tax_rate=data.default_tax_rate or 13, rating=data.rating or 3,
                 remark=data.remark or "")
    db.add(c)
    db.commit()
    db.refresh(c)
    return CustomerOut.model_validate(c)


@router.get("/customers", tags=["基础档案-客户"])
def list_customers(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                   keyword: str = Query(""), code: str = Query(""),
                   name_cn: str = Query(""), contact_person: str = Query(""),
                   country: str = Query(""),
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    query = db.query(Customer)
    if keyword:
        from sqlalchemy import or_
        query = query.filter(or_(Customer.code.like(f"%{keyword}%"),
                                 Customer.name_cn.like(f"%{keyword}%"),
                                 Customer.name_en.like(f"%{keyword}%")))
    else:
        if code:
            query = query.filter(Customer.code.like(f"%{code}%"))
        if name_cn:
            query = query.filter(Customer.name_cn.like(f"%{name_cn}%"))
        if contact_person:
            query = query.filter(Customer.contact_person.like(f"%{contact_person}%"))
        if country:
            query = query.filter(Customer.country.like(f"%{country}%"))
    total = query.count()
    items = query.order_by(Customer.code.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [CustomerOut.model_validate(c) for c in items]}


@router.put("/customers/{item_id}", response_model=CustomerOut, tags=["基础档案-客户"])
def update_customer(item_id: int, data: CustomerUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Customer).filter(Customer.id == item_id).first()
    if not item:
        raise HTTPException(404, "客户不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "name_cn" in update_data:
        _ensure_unique_name(db, Customer, "name_cn", update_data["name_cn"], exclude_id=item_id, label="客户名称")
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return CustomerOut.model_validate(item)


def _has_business_refs(db: Session, model, item_id: int, refs: list) -> str | None:
    """检查业务数据引用，返回被引用的业务名称，无引用返回 None"""
    for table_name, field_name, biz_name in refs:
        try:
            exists = db.query(table_name).filter(getattr(table_name, field_name) == item_id).first()
        except Exception:
            continue
        if exists:
            return biz_name
    return None


# 客户被引用的业务表：销售报价/订单/发货/报关/发票/应收/收款
CUSTOMER_REFS = [
    (SalesQuote, "customer_id", "报价单"),
    (SalesOrder, "customer_id", "销售订单"),
    (SalesDelivery, "customer_id", "销售发货"),
    (CustomsDeclaration, "customer_id", "报关单"),
    (SalesInvoice, "customer_id", "销售发票"),
    (AccountsReceivable, "customer_id", "应收账款"),
    (Collection, "customer_id", "收款单"),
]

# 供应商被引用的业务表：采购订单/入库/发票/应付/付款/委外/加工费/进项发票
SUPPLIER_REFS = [
    (PurchaseOrder, "supplier_id", "采购订单"),
    (PurchaseReceipt, "supplier_id", "采购入库"),
    (PurchaseInvoice, "supplier_id", "采购发票"),
    (AccountsPayable, "supplier_id", "应付账款"),
    (Payment, "supplier_id", "付款单"),
    (OutsourcingOrder, "supplier_id", "委外工单"),
    (ProcessingInvoice, "supplier_id", "加工费发票"),
    (TaxRefundInputInvoice, "supplier_id", "进项发票"),
]

# 材料被引用的业务表：采购明细/入库明细/BOM/生产物料/发料/库存/流水/盘点
MATERIAL_REFS = [
    (PurchaseOrderItem, "material_id", "采购订单"),
    (PurchaseReceiptItem, "material_id", "采购入库"),
    (BomItem, "material_id", "BOM"),
    (ProductionMaterial, "material_id", "生产订单"),
    (MaterialIssueItem, "material_id", "发料记录"),
    (WarehouseInventory, "material_id", "库存"),
    (StockTransaction, "material_id", "库存流水"),
    (StockCheckItem, "material_id", "盘点单"),
]

# 产品被引用的业务表：报价/销售明细/发货/BOM/工艺/生产/完工入库/委外/加工费/库存/流水/进项发票
PRODUCT_REFS = [
    (SalesQuote, "product_id", "销售报价"),
    (SalesOrderItem, "product_id", "销售订单"),
    (SalesDelivery, "product_id", "销售发货"),
    (BomItem, "product_id", "BOM"),
    (ProductProcess, "product_id", "工艺路线"),
    (ProductionOrder, "product_id", "生产订单"),
    (ProductionMaterial, "product_id", "生产物料"),
    (ProductionReceipt, "product_id", "完工入库"),
    (OutsourcingOrder, "product_id", "委外工单"),
    (ProcessingInvoice, "product_id", "加工费发票"),
    (WarehouseInventory, "product_id", "库存"),
    (StockTransaction, "product_id", "库存流水"),
    (StockCheckItem, "product_id", "盘点单"),
    (TaxRefundInputInvoice, "product_id", "进项发票"),
]


@router.delete("/customers/{item_id}", tags=["基础档案-客户"])
def delete_customer(item_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Customer).filter(Customer.id == item_id).first()
    if not item:
        raise HTTPException(404, "客户不存在")
    biz = _has_business_refs(db, Customer, item_id, CUSTOMER_REFS)
    if biz:
        raise HTTPException(400, f"该客户已有{biz}数据，不允许删除，可停用")
    db.delete(item)
    db.commit()
    return {"message": "客户已删除"}


@router.delete("/suppliers/{item_id}", tags=["基础档案-供应商"])
def delete_supplier(item_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Supplier).filter(Supplier.id == item_id).first()
    if not item:
        raise HTTPException(404, "供应商不存在")
    biz = _has_business_refs(db, Supplier, item_id, SUPPLIER_REFS)
    if biz:
        raise HTTPException(400, f"该供应商已有{biz}数据，不允许删除，可停用")
    db.delete(item)
    db.commit()
    return {"message": "供应商已删除"}


# ==================== 供应商自定义创建（自动编码 SU+6位流水）====================

@router.get("/suppliers/next-code", tags=["基础档案-供应商"])
def preview_supplier_code(db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """预览下一个供应商编码（仅预览，不消耗流水）"""
    return {"code": _next_code(db, Supplier, "SU")}


@router.post("/suppliers", tags=["基础档案-供应商"])
def create_supplier(data: SupplierCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    code = _next_code(db, Supplier, "SU")  # 编码强制自动生成，不允许手动输入
    _ensure_unique_name(db, Supplier, "name", data.name, label="供应商名称")
    # 编码唯一性校验（避免唯一约束冲突 → 500）
    if db.query(Supplier).filter(Supplier.code == code).first():
        raise HTTPException(409, f"供应商编码已存在: {code}")
    s = Supplier(code=code, name=data.name, country=data.country or "",
                 contact_person=data.contact_person or "",
                 phone=data.phone or "", email=data.email or "", tax_id=data.tax_id or "",
                 address=data.address or "", payment_terms=data.payment_terms or "TT",
                 account_period=data.account_period or 30,
                 supply_range=data.supply_range or "",
                 rating=data.rating or 3, supplier_type=data.supplier_type or "原材料",
                 bank_name=data.bank_name or "", bank_account=data.bank_account or "",
                 default_tax_rate=data.default_tax_rate or 13,
                 remark=data.remark or "")
    db.add(s)
    db.commit()
    db.refresh(s)
    return SupplierOut.model_validate(s)


@router.get("/suppliers", tags=["基础档案-供应商"])
def list_suppliers(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                   keyword: str = Query(""), code: str = Query(""),
                   name: str = Query(""), contact_person: str = Query(""),
                   country: str = Query(""),
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    query = db.query(Supplier)
    if keyword:
        from sqlalchemy import or_
        query = query.filter(or_(Supplier.code.like(f"%{keyword}%"),
                                 Supplier.name.like(f"%{keyword}%")))
    else:
        if code:
            query = query.filter(Supplier.code.like(f"%{code}%"))
        if name:
            query = query.filter(Supplier.name.like(f"%{name}%"))
        if contact_person:
            query = query.filter(Supplier.contact_person.like(f"%{contact_person}%"))
        if country:
            query = query.filter(Supplier.country.like(f"%{country}%"))
    total = query.count()
    items = query.order_by(Supplier.code.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [SupplierOut.model_validate(s) for s in items]}


@router.put("/suppliers/{item_id}", response_model=SupplierOut, tags=["基础档案-供应商"])
def update_supplier(item_id: int, data: SupplierUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    item = db.query(Supplier).filter(Supplier.id == item_id).first()
    if not item:
        raise HTTPException(404, "供应商不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "name" in update_data:
        _ensure_unique_name(db, Supplier, "name", update_data["name"], exclude_id=item_id, label="供应商名称")
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return SupplierOut.model_validate(item)


# ==================== BOM 特殊路由 ====================

@router.get("/bom/by-product/{product_id}", tags=["基础档案-BOM"])
def get_bom_by_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定产品的 BOM 清单（树形结构）"""
    items = db.query(BomItem).filter(
        BomItem.product_id == product_id,
        BomItem.is_active == 1,
    ).order_by(BomItem.sort_order).all()

    result = []
    for item in items:
        material = db.query(Material).filter(Material.id == item.material_id).first()
        process = db.query(Process).filter(Process.id == item.process_id).first() if item.process_id else None
        result.append({
            "id": item.id,
            "bom_name": item.bom_name,
            "material_id": item.material_id,
            "material_code": material.code if material else "",
            "material_name": material.name if material else "",
            "material_spec": material.spec if material else "",
            "material_unit": material.unit if material else "",
            "quantity": item.quantity,
            "loss_rate": item.loss_rate,
            "process_name": process.name if process else "",
            "sort_order": item.sort_order,
        })
    return {"product_id": product_id, "items": result}


@router.post("/bom", response_model=BomItemOut, tags=["基础档案-BOM"])
def create_bom_item(
    data: BomItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 BOM 明细"""
    # 校验产品和材料存在（外键保护）
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=400, detail=f"产品不存在: {data.product_id}")
    material = db.query(Material).filter(Material.id == data.material_id).first()
    if not material:
        raise HTTPException(status_code=400, detail=f"材料不存在: {data.material_id}")
    if data.process_id:
        process = db.query(Process).filter(Process.id == data.process_id).first()
        if not process:
            raise HTTPException(status_code=400, detail=f"工序不存在: {data.process_id}")
    if data.quantity is not None and data.quantity <= 0:
        raise HTTPException(status_code=400, detail="BOM 用量必须大于 0")
    item = BomItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return BomItemOut.model_validate(item)


@router.put("/bom/{item_id}", response_model=BomItemOut, tags=["基础档案-BOM"])
def update_bom_item(
    item_id: int,
    data: BomItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 BOM 明细"""
    item = db.query(BomItem).filter(BomItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="BOM 明细不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return BomItemOut.model_validate(item)


@router.delete("/bom/{item_id}", tags=["基础档案-BOM"])
def delete_bom_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 BOM 明细"""
    item = db.query(BomItem).filter(BomItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="BOM 明细不存在")
    db.delete(item)
    db.commit()
    return {"message": "BOM 明细已删除"}


# ==================== 汇率特殊路由 ====================

@router.get("/exchange-rates/latest", tags=["基础档案-汇率"])
def get_latest_rates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取所有币种的最新汇率"""
    from sqlalchemy import func
    subq = (
        db.query(
            ExchangeRate.currency_id,
            func.max(ExchangeRate.rate_date).label("max_date"),
        )
        .group_by(ExchangeRate.currency_id)
        .subquery()
    )
    rates = (
        db.query(ExchangeRate)
        .join(
            subq,
            (ExchangeRate.currency_id == subq.c.currency_id)
            & (ExchangeRate.rate_date == subq.c.max_date),
        )
        .all()
    )
    result = []
    for rate in rates:
        currency = db.query(Currency).filter(Currency.id == rate.currency_id).first()
        result.append({
            "id": rate.id,
            "currency_id": rate.currency_id,
            "currency_code": currency.code if currency else "",
            "rate": rate.rate,
            "rate_date": rate.rate_date.isoformat(),
        })
    return result


@router.post("/exchange-rates/fetch", tags=["基础档案-汇率"])
def fetch_latest_rates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """手动触发：从腾讯财经（国内源）拉取最新汇率并入库

    拉取全部非本位币种兑本位币汇率；同币种+同日已存在 → 更新（source=API），否则新建。
    """
    from datetime import date as _date
    from app.services.exchange_rate_fetcher import fetch_rates, convert_to_base

    currencies = db.query(Currency).filter(Currency.is_active == 1).all()
    base = next((c for c in currencies if c.is_base == 1), None)
    codes = [c.code for c in currencies if not (base and c.id == base.id)]
    if not codes:
        raise HTTPException(400, "没有可拉取的币种（请先维护币种档案）")

    rates_cny = fetch_rates(codes)
    if not rates_cny:
        raise HTTPException(502, "汇率获取失败：腾讯财经不可达或返回为空，请检查网络后重试")

    rates = convert_to_base(rates_cny, base.code if base else "CNY")
    today = _date.today()
    updated, created, failed = 0, 0, []
    for c in currencies:
        if base and c.id == base.id:
            continue
        rate_val = rates.get(c.code)
        if rate_val is None:
            failed.append(c.code)
            continue
        row = db.query(ExchangeRate).filter(
            ExchangeRate.currency_id == c.id,
            ExchangeRate.rate_date == today,
        ).first()
        if row:
            row.rate = rate_val
            row.source = "API"
            updated += 1
        else:
            db.add(ExchangeRate(currency_id=c.id, rate=rate_val,
                                rate_date=today, source="API"))
            created += 1
    db.commit()
    return {
        "message": f"汇率更新完成：新增 {created}，更新 {updated}，失败 {len(failed)}",
        "created": created, "updated": updated,
        "failed": failed, "base": base.code if base else "CNY",
        "rate_date": today.isoformat(),
        "rates": {c.code: rates.get(c.code) for c in currencies if not (base and c.id == base.id)},
    }


@router.get("/processes-select", tags=["基础档案-选择器"])
def processes_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """工序选择器"""
    query = db.query(Process).filter(Process.is_active == 1)
    if keyword:
        query = query.filter(Process.name.like(f"%{keyword}%") | Process.code.like(f"%{keyword}%"))
    items = query.order_by(Process.code.asc()).limit(100).all()
    return [{"id": p.id, "code": p.code, "name": p.name, "unit_price": p.unit_price} for p in items]


@router.get("/warehouses-select", tags=["基础档案-选择器"])
def warehouses_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仓库选择器"""
    query = db.query(Warehouse).filter(Warehouse.is_active == 1)
    if keyword:
        query = query.filter(Warehouse.name.like(f"%{keyword}%") | Warehouse.code.like(f"%{keyword}%"))
    items = query.order_by(Warehouse.code.asc()).limit(100).all()
    return [{"id": w.id, "code": w.code, "name": w.name, "wh_type": w.wh_type} for w in items]


@router.get("/outsourcers-select", tags=["基础档案-选择器"])
def outsourcers_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """委外商选择器 = 供应商中 supplier_type=委外 的档案"""
    query = db.query(Supplier).filter(Supplier.supplier_type == "委外", Supplier.is_active == 1)
    if keyword:
        query = query.filter(Supplier.name.like(f"%{keyword}%") | Supplier.code.like(f"%{keyword}%"))
    items = query.order_by(Supplier.id.desc()).limit(100).all()
    return [{"id": s.id, "supplier_id": s.id, "code": s.code,
             "name": s.name, "lead_time": 7} for s in items]


# ==================== 客户/供应商/产品/材料下拉数据 ====================

@router.get("/customers-select", tags=["基础档案-选择器"])
def customers_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """客户选择器（精简数据）"""
    query = db.query(Customer).filter(Customer.is_active == 1)
    if keyword:
        query = query.filter(
            Customer.name_cn.like(f"%{keyword}%")
            | Customer.code.like(f"%{keyword}%")
        )
    items = query.order_by(Customer.code.asc()).limit(100).all()
    return [{"id": c.id, "code": c.code, "name": c.name_cn, "payment_terms": c.payment_terms} for c in items]


@router.get("/suppliers-select", tags=["基础档案-选择器"])
def suppliers_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """供应商选择器"""
    query = db.query(Supplier).filter(Supplier.is_active == 1)
    if keyword:
        query = query.filter(Supplier.name.like(f"%{keyword}%") | Supplier.code.like(f"%{keyword}%"))
    items = query.order_by(Supplier.code.asc()).limit(100).all()
    return [{"id": s.id, "code": s.code, "name": s.name, "payment_terms": s.payment_terms} for s in items]


@router.get("/products-select", tags=["基础档案-选择器"])
def products_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """产品选择器"""
    query = db.query(Product).filter(Product.is_active == 1)
    if keyword:
        query = query.filter(
            Product.name_cn.like(f"%{keyword}%")
            | Product.code.like(f"%{keyword}%")
        )
    items = query.order_by(Product.code.asc()).limit(100).all()
    return [{"id": p.id, "code": p.code, "name": p.name_cn, "spec": p.spec or "", "model": p.model or "", "unit": p.unit, "sale_price": p.sale_price} for p in items]


@router.get("/materials-select", tags=["基础档案-选择器"])
def materials_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """材料选择器"""
    query = db.query(Material).filter(Material.is_active == 1)
    if keyword:
        query = query.filter(Material.name.like(f"%{keyword}%") | Material.code.like(f"%{keyword}%"))
    items = query.order_by(Material.code.asc()).limit(100).all()
    return [{"id": m.id, "code": m.code, "name": m.name, "spec": m.spec, "model": m.model, "unit": m.unit, "purchase_price": m.purchase_price} for m in items]


@router.get("/procurement-items-select", tags=["基础档案-选择器"])
def procurement_items_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """采购选品：原材料 + 可外购成品"""
    results = []
    # 材料
    mat_query = db.query(Material).filter(Material.is_active == 1)
    if keyword:
        mat_query = mat_query.filter(Material.name.like(f"%{keyword}%") | Material.code.like(f"%{keyword}%"))
    for m in mat_query.order_by(Material.id.desc()).limit(100).all():
        results.append({
            "id": m.id, "type": "material", "code": m.code, "name": m.name,
            "spec": m.spec or "", "model": m.model or "", "unit": m.unit,
            "purchase_price": m.purchase_price,
        })
    # 可外购成品
    prod_query = db.query(Product).filter(Product.is_active == 1, Product.can_purchase == 1)
    if keyword:
        prod_query = prod_query.filter(
            Product.name_cn.like(f"%{keyword}%") | Product.code.like(f"%{keyword}%"))
    for p in prod_query.order_by(Product.id.desc()).limit(100).all():
        results.append({
            "id": p.id, "type": "product", "code": p.code, "name": p.name_cn,
            "spec": p.spec or "", "model": p.model or "", "unit": p.unit,
            "purchase_price": p.estimated_cost,
        })
    return results


@router.get("/currencies", tags=["基础档案-选择器"])
def list_currencies(
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    query = db.query(Currency).filter(Currency.is_active == 1)
    total = query.count()
    items = query.order_by(Currency.id).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": c.id, "code": c.code, "name": c.name, "name_cn": c.name_cn or ""} for c in items
    ]}


# ==================== 公司信息 ====================

@router.get("/company", tags=["基础档案"])
def get_company(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取公司信息（含联系人）"""
    company = db.query(Company).first()
    if not company:
        return None
    contacts = db.query(CompanyContact).filter(
        CompanyContact.company_id == company.id).order_by(CompanyContact.seq).all()
    return {
        "id": company.id, "name": company.name, "name_en": company.name_en or "",
        "tax_id": company.tax_id or "", "address": company.address or "",
        "phone": company.phone or "",
        "contacts": [{
            "id": c.id, "seq": c.seq, "name": c.name, "role": c.role or "",
            "phone": c.phone or "", "email": c.email or "",
        } for c in contacts],
    }


@router.post("/company", tags=["基础档案"])
def save_company(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """保存公司信息（仅一条，有则更新）"""
    company = db.query(Company).first()
    if company:
        for field in ["name", "name_en", "tax_id", "address", "phone"]:
            if field in data:
                setattr(company, field, data[field])
    else:
        company = Company(
            name=data.get("name", ""), name_en=data.get("name_en", ""),
            tax_id=data.get("tax_id", ""), address=data.get("address", ""),
            phone=data.get("phone", ""),
        )
        db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": company.id, "message": "公司信息已保存"}


@router.post("/company/contacts", tags=["基础档案"])
def save_contact(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """新增联系人"""
    company = db.query(Company).first()
    if not company:
        raise HTTPException(400, "请先填写公司信息")
    max_seq = db.query(CompanyContact.seq).filter(
        CompanyContact.company_id == company.id).order_by(CompanyContact.seq.desc()).first()
    seq = (max_seq[0] or 0) + 1 if max_seq else 1
    contact = CompanyContact(
        company_id=company.id, seq=seq,
        name=data.get("name", ""), role=data.get("role", ""),
        phone=data.get("phone", ""), email=data.get("email", ""),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return {"id": contact.id, "message": "联系人已添加"}


@router.put("/company/contacts/{contact_id}", tags=["基础档案"])
def update_contact(contact_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """修改联系人"""
    contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()
    if not contact:
        raise HTTPException(404, "联系人不存在")
    for field in ["name", "role", "phone", "email"]:
        if field in data:
            setattr(contact, field, data[field])
    db.commit()
    return {"message": "联系人已更新"}


@router.delete("/company/contacts/{contact_id}", tags=["基础档案"])
def delete_contact(contact_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除联系人"""
    contact = db.query(CompanyContact).filter(CompanyContact.id == contact_id).first()
    if not contact:
        raise HTTPException(404, "联系人不存在")
    db.delete(contact)
    db.commit()
    return {"message": "联系人已删除"}


# ==================== 产品工艺路线模板（schema版，由 subagent 实现）====================

@router.get("/products/{product_id}/processes", response_model=list[ProductProcessTemplateOut], tags=["基础档案-产品工艺路线"])
def list_product_process_templates(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出产品的所有工艺路线模板，按 seq 排序"""
    items = (
        db.query(ProductProcess)
        .filter(ProductProcess.product_id == product_id)
        .order_by(ProductProcess.seq)
        .all()
    )
    supplier_ids = {i.default_supplier_id for i in items if i.default_supplier_id}
    suppliers = {}
    if supplier_ids:
        suppliers = {s.id: s.name for s in db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()}
    result = []
    for i in items:
        out = ProductProcessTemplateOut.model_validate(i)
        out.supplier_name = suppliers.get(i.default_supplier_id, "") if i.default_supplier_id else ""
        result.append(out)
    return result


@router.put("/products/{product_id}/processes", response_model=list[ProductProcessTemplateOut], tags=["基础档案-产品工艺路线"])
def batch_save_product_process_templates(
    product_id: int,
    templates: list[ProductProcessTemplateItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量保存产品工艺路线模板（全量替换）"""
    # 删除现有模板
    db.query(ProductProcess).filter(ProductProcess.product_id == product_id).delete()

    # 插入新模板
    new_items = []
    for t in templates:
        item = ProductProcess(
            product_id=product_id,
            process_id=t.process_id,
            seq=t.seq,
            default_outsourcer_id=t.default_outsourcer_id,
            default_supplier_id=t.default_supplier_id,
            default_unit_price=t.default_unit_price or 0,
        )
        db.add(item)
        new_items.append(item)

    db.commit()
    for item in new_items:
        db.refresh(item)

    return [ProductProcessTemplateOut.model_validate(i) for i in new_items]


@router.delete("/products/{product_id}/processes/{pid}", tags=["基础档案-产品工艺路线"])
def delete_product_process_template(
    product_id: int,
    pid: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除单个产品工艺路线模板"""
    item = db.query(ProductProcess).filter(
        ProductProcess.id == pid,
        ProductProcess.product_id == product_id,
    ).first()
    if not item:
        raise HTTPException(404, "产品工艺路线模板不存在")
    db.delete(item)
    db.commit()
    return {"message": "已删除"}

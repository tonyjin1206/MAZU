"""基础档案 API 路由 — 使用通用 CRUD 注册所有基础数据"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.foundation import (
    Material, Product, BomItem, Process,
    Department, Employee,
    Customer, Supplier, Outsourcer,
    Warehouse, Currency, ExchangeRate,
    HsCode, TradeTerm,
    Company, CompanyContact,
    ProductProcess,
)
from app.schemas.foundation import (
    MaterialCreate, MaterialUpdate, MaterialOut,
    ProductCreate, ProductUpdate, ProductOut,
    BomItemCreate, BomItemUpdate, BomItemOut,
    ProcessCreate, ProcessUpdate, ProcessOut,
    DepartmentCreate, DepartmentOut,
    EmployeeCreate, EmployeeOut,
    CustomerCreate, CustomerUpdate, CustomerOut,
    SupplierCreate, SupplierUpdate, SupplierOut,
    OutsourcerCreate, OutsourcerOut,
    WarehouseCreate, WarehouseOut,
    CurrencyCreate, CurrencyOut,
    ExchangeRateCreate, ExchangeRateOut,
    HsCodeCreate, HsCodeUpdate, HsCodeOut,
    TradeTermCreate, TradeTermOut,
    ProductProcessTemplateItem, ProductProcessTemplateOut,
)
from app.routers.base_crud import register_crud
from app.utils.auth import get_current_user

router = APIRouter()

# ==================== 注册所有基础档案 CRUD ====================

register_crud(router, Material,       MaterialCreate,   MaterialUpdate,   MaterialOut,   "materials",   "基础档案-材料",   search_fields=["code", "name"])
register_crud(router, Product,        ProductCreate,    ProductUpdate,    ProductOut,    "products",    "基础档案-产品",   search_fields=["code", "name_cn", "name_en"])
register_crud(router, Process,        ProcessCreate,    ProcessUpdate,    ProcessOut,    "processes",   "基础档案-工序",   search_fields=["code", "name"])
register_crud(router, Department,     DepartmentCreate, None,             DepartmentOut, "departments", "基础档案-部门",   search_fields=["code", "name"])
register_crud(router, Employee,       EmployeeCreate,   None,             EmployeeOut,   "employees",   "基础档案-人员",   search_fields=["code", "name"])
register_crud(router, Customer,       CustomerCreate,   CustomerUpdate,   CustomerOut,   "customers",   "基础档案-客户",   search_fields=["code", "name_cn", "name_en"])
register_crud(router, Supplier,       SupplierCreate,   SupplierUpdate,   SupplierOut,   "suppliers",   "基础档案-供应商", search_fields=["code", "name"])
register_crud(router, Outsourcer,     OutsourcerCreate, None,             OutsourcerOut, "outsourcers", "基础档案-委外商", search_fields=[])
register_crud(router, Warehouse,      WarehouseCreate,  None,             WarehouseOut,  "warehouses",  "基础档案-仓库",   search_fields=["code", "name"])
register_crud(router, Currency,       CurrencyCreate,   None,             CurrencyOut,   "currencies",  "基础档案-币种",   search_fields=["code", "name"])
register_crud(router, HsCode,         HsCodeCreate,     HsCodeUpdate,     HsCodeOut,     "hs-codes",    "基础档案-HS编码", search_fields=["hs_code", "name"])
register_crud(router, TradeTerm,      TradeTermCreate,  None,             TradeTermOut,  "trade-terms", "基础档案-贸易术语", search_fields=["code", "name"])


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
    items = query.order_by(Process.id.desc()).limit(100).all()
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
    items = query.order_by(Warehouse.id.desc()).limit(100).all()
    return [{"id": w.id, "code": w.code, "name": w.name, "wh_type": w.wh_type} for w in items]


@router.get("/outsourcers-select", tags=["基础档案-选择器"])
def outsourcers_select(
    keyword: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """委外商选择器"""
    from sqlalchemy.orm import joinedload
    query = db.query(Outsourcer).filter(Outsourcer.is_active == 1)
    if keyword:
        query = query.join(Supplier).filter(Supplier.name.like(f"%{keyword}%"))
    items = query.limit(100).all()
    return [{"id": o.id, "supplier_id": o.supplier_id,
             "name": o.supplier.name if o.supplier else "",
             "lead_time": o.lead_time} for o in items]


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
    items = query.order_by(Customer.id.desc()).limit(100).all()
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
    items = query.order_by(Supplier.id.desc()).limit(100).all()
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
    items = query.order_by(Product.id.desc()).limit(100).all()
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
    items = query.order_by(Material.id.desc()).limit(100).all()
    return [{"id": m.id, "code": m.code, "name": m.name, "spec": m.spec, "model": m.model, "unit": m.unit, "purchase_price": m.purchase_price} for m in items]


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
    return [ProductProcessTemplateOut.model_validate(i) for i in items]


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

"""生产（自产）模块 API 路由 — 生产订单/工作台/加工费发票已下线，仅保留批次追溯。

v2.8.x 改造：公司无自产，删除 /productions* 与 /workspace 端点、/processing-invoices* 端点；
批次追溯挪到库存管理菜单，后端路径 /inventory/batch、/inventory/trace 保持不变（/api/production/inventory/*）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.auth import User
from app.models.foundation import Material, Product
from app.models.inventory import WarehouseInventory, StockTransaction
from app.utils.auth import require_any_permission
from sqlalchemy import or_

# ==================== 读端点授权域 ====================
# 批次追溯（挪到库存管理菜单）：库管员/库存角色可读；生产域已收缩为「批次」一域。
PRODUCTION_BATCH_READ_PERMS = ("menu:production:batch", "menu:inventory")

router = APIRouter()


@router.get("/inventory/batch", tags=["生产管理"])
def query_batch_inventory(
    batch_no: str = Query("", description="批次号"),
    keyword: str = Query("", description="物料/产品名称或编码"),
    warehouse_id: int = Query(None, description="仓库ID"),
    product_id: int = Query(None),
    material_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any_permission(*PRODUCTION_BATCH_READ_PERMS)),
):
    """批次库存查询"""
    query = db.query(WarehouseInventory)
    if batch_no:
        query = query.filter(WarehouseInventory.batch_no.like(f"%{batch_no}%"))
    if warehouse_id:
        query = query.filter(WarehouseInventory.warehouse_id == warehouse_id)
    if product_id:
        query = query.filter(WarehouseInventory.product_id == product_id)
    if material_id:
        query = query.filter(WarehouseInventory.material_id == material_id)
    if keyword:
        kw = f"%{keyword}%"
        query = query.outerjoin(Material, WarehouseInventory.material_id == Material.id) \
            .outerjoin(Product, WarehouseInventory.product_id == Product.id) \
            .filter(or_(Material.code.like(kw), Material.name.like(kw),
                        Product.code.like(kw), Product.name_cn.like(kw)))
    query = query.filter(WarehouseInventory.quantity != 0)
    items = query.order_by(WarehouseInventory.id.desc()).limit(100).all()
    return {"items": [
        {"id": i.id, "warehouse": i.warehouse.name if i.warehouse else "",
         "batch_no": i.batch_no, "quantity": i.quantity,
         "material_name": i.material.name if i.material else "",
         "product_name": i.product.name_cn if i.product else "",
         "in_date": str(i.in_date), "source_type": i.source_type,
        } for i in items
    ]}


@router.get("/inventory/trace", tags=["生产管理"])
def trace_batch(batch_no: str, db: Session = Depends(get_db), current_user: User = Depends(require_any_permission(*PRODUCTION_BATCH_READ_PERMS))):
    """批次号全程追溯"""
    batch = db.query(WarehouseInventory).filter(WarehouseInventory.batch_no == batch_no).first()
    item_name = ""
    if batch:
        if batch.material:
            item_name = batch.material.name
        elif batch.product:
            item_name = batch.product.name_cn
    transactions = db.query(StockTransaction).filter(
        StockTransaction.batch_no == batch_no
    ).order_by(StockTransaction.trans_date).all()
    return {"batch_no": batch_no, "item_name": item_name, "trace": [
        {"id": t.id, "type": t.trans_type, "quantity": t.quantity,
         "before": t.before_qty, "after": t.after_qty,
         "doc_type": t.source_doc_type, "doc_no": t.source_doc_no,
         "date": str(t.trans_date),
        } for t in transactions
    ]}

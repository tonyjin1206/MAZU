"""基础档案 — 通用 CRUD 路由"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.database import get_db
from app.models.auth import User
from app.utils.auth import get_current_user

router = APIRouter()


def _paginate(db: Session, model, page: int = 1, page_size: int = 50, **filters):
    """通用分页查询"""
    query = db.query(model)
    for key, value in filters.items():
        if value is not None:
            column = getattr(model, key, None)
            if column is not None:
                query = query.filter(column == value)
    total = query.count()
    items = query.order_by(model.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def _get_or_404(db: Session, model, item_id: int):
    """获取单个记录，不存在则 404"""
    item = db.query(model).filter(model.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"{model.__name__} 不存在")
    return item


# ==================== 通用 CRUD 注册函数 ====================

def register_crud(
    router: APIRouter,
    model,
    create_schema,
    update_schema,
    out_schema,
    prefix: str,
    tag: str,
    search_fields: list[str] | None = None,
    list_requires_admin: bool = False,
    delete_guard=None,
):
    """为模型注册标准 CRUD 路由"""

    entity_name = model.__name__
    # 未提供独立 update schema 时复用 create schema（修复 PUT 422 Field required）
    UpdateSchema = update_schema or create_schema

    # 列表查询
    @router.get(f"/{prefix}", response_model=dict, tags=[tag])
    def list_items(
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        keyword: str = Query("", description="搜索关键词"),
        code: str = Query("", description="按编码模糊搜索"),
        name: str = Query("", description="按名称模糊搜索"),
        hs_code: str = Query("", description="按HS编码模糊搜索"),
        is_active: int | None = Query(None, description="启用状态"),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        """分页查询"""
        query = db.query(model)

        from sqlalchemy import or_
        conditions = []
        if keyword and search_fields:
            for field in search_fields:
                column = getattr(model, field, None)
                if column is not None:
                    conditions.append(column.like(f"%{keyword}%"))
            if conditions:
                query = query.filter(or_(*conditions))
        else:
            if code and hasattr(model, 'code'):
                query = query.filter(model.code.like(f"%{code}%"))
            if name and hasattr(model, 'name'):
                query = query.filter(model.name.like(f"%{name}%"))
            if hs_code and hasattr(model, 'hs_code'):
                query = query.filter(model.hs_code.like(f"%{hs_code}%"))

        if is_active is not None:
            query = query.filter(model.is_active == is_active)

        total = query.count()
        items = query.order_by(model.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [out_schema.model_validate(item) for item in items],
        }

    # 获取单个
    @router.get(f"/{prefix}/{{item_id}}", response_model=out_schema, tags=[tag])
    def get_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
        item = _get_or_404(db, model, item_id)
        return out_schema.model_validate(item)

    # 创建
    @router.post(f"/{prefix}", response_model=out_schema, tags=[tag])
    def create_item(
        data: create_schema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        item = model(**data.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        return out_schema.model_validate(item)

    # 更新
    @router.put(f"/{prefix}/{{item_id}}", response_model=out_schema, tags=[tag])
    def update_item(
        item_id: int,
        data: UpdateSchema,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        item = _get_or_404(db, model, item_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return out_schema.model_validate(item)

    # 删除（软删除，修改 is_active；delete_guard 可阻止删除）
    @router.delete(f"/{prefix}/{{item_id}}", tags=[tag])
    def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        item = _get_or_404(db, model, item_id)
        if delete_guard:
            delete_guard(db, item)
        if hasattr(item, "is_active"):
            item.is_active = 0
            db.commit()
        else:
            db.delete(item)
            db.commit()
        return {"message": f"{entity_name} 已删除"}

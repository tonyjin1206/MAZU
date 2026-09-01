"""站内通知 API — 个人消息中心 + 管理端全量查询"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import User
from app.models.system_config import Notification
from app.schemas.notification import NotificationOut, NotificationAdminOut, NotificationReadUpdate
from app.utils.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/notifications", tags=["站内通知"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    read_status: int | None = Query(None, description="0=未读 1=已读，缺省全部"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """当前用户通知列表（read_status 筛选 + 未读优先，分页）"""
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_active == 1,
    )
    if read_status is not None:
        query = query.filter(Notification.read_status == read_status)
    items = query.order_by(
        Notification.read_status.asc(),
        Notification.created_at.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return [NotificationOut.model_validate(n) for n in items]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """未读数（铃铛红点）"""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_active == 1,
        Notification.read_status == 0,
    ).count()
    return {"count": count}


@router.get("/latest", response_model=list[NotificationOut])
def latest_notifications(
    limit: int = Query(5, ge=1, le=50),
    only_unread: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """工作台待办区/铃铛拉取最近 N 条（only_unread=true 只返回未读）"""
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_active == 1,
    )
    if only_unread:
        query = query.filter(Notification.read_status == 0)
    items = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [NotificationOut.model_validate(n) for n in items]


@router.put("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    data: NotificationReadUpdate | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """标记已读（只能操作自己的通知）"""
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(404, "通知不存在")
    n.read_status = data.read_status if data else 1
    db.commit()
    db.refresh(n)
    return NotificationOut.model_validate(n)


@router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """全部已读"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.read_status == 0,
    ).update({"read_status": 1})
    db.commit()
    return {"message": "已全部标记为已读"}


@router.get("/admin-query")
def admin_query(
    user_id: int | None = Query(None),
    role_code: str | None = Query(None),
    point_code: str | None = Query(None),
    doc_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """管理端全量查询（测试验证/管理查看）— 按用户/角色/提醒点/单据类型筛选"""
    from app.models.auth import Role
    query = db.query(Notification).filter(Notification.is_active == 1)
    if user_id:
        query = query.filter(Notification.user_id == user_id)
    if role_code:
        query = query.filter(
            Notification.user_id.in_(
                db.query(User.id).join(Role, User.role_id == Role.id).filter(Role.code == role_code)
            )
        )
    if point_code:
        query = query.filter(Notification.point_code == point_code)
    if doc_type:
        query = query.filter(Notification.doc_type == doc_type)
    total = query.count()
    items = query.order_by(Notification.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result = []
    for n in items:
        out = NotificationAdminOut.model_validate(n)
        if n.user:
            out.user_name = n.user.display_name or n.user.username
            out.role_name = n.user.role_name if n.user.role else None
        result.append(out)
    return {"items": result, "total": total}

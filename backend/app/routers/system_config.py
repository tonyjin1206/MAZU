"""系统配置 API — 企业微信 / AI Bot / 提醒管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models.auth import User
from app.utils.auth import get_current_user, get_current_admin
from app.models.system_config import (
    WecomConfig, BotConfig, BotConversation,
    ReminderConfig, ReminderLog,
)
from app.schemas.system_config import (
    WecomConfigCreate, WecomConfigUpdate, WecomConfigOut,
    BotConfigCreate, BotConfigUpdate, BotConfigOut,
    DEFAULT_SYSTEM_PROMPT,
    ReminderConfigCreate, ReminderConfigUpdate, ReminderConfigOut,
    ReminderLogOut, REMINDER_TYPES,
)

router = APIRouter(prefix="/system", tags=["系统配置"])


# ==================== 企业微信配置 ====================

@router.get("/wecom", response_model=list[WecomConfigOut])
def list_wecom(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(WecomConfig).order_by(WecomConfig.id.desc()).all()
    return [WecomConfigOut.model_validate(w) for w in items]


@router.post("/wecom", response_model=WecomConfigOut)
def create_wecom(
    data: WecomConfigCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = WecomConfig(**data.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return WecomConfigOut.model_validate(config)


@router.put("/wecom/{config_id}", response_model=WecomConfigOut)
def update_wecom(
    config_id: int,
    data: WecomConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(WecomConfig).filter(WecomConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return WecomConfigOut.model_validate(config)


@router.delete("/wecom/{config_id}")
def delete_wecom(
    config_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(WecomConfig).filter(WecomConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    db.delete(config)
    db.commit()
    return {"message": "已删除"}


# ==================== AI Bot 配置 ====================

@router.get("/bot", response_model=list[BotConfigOut])
def list_bot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(BotConfig).order_by(BotConfig.id.desc()).all()
    return [BotConfigOut.model_validate(b) for b in items]


@router.get("/bot/active", response_model=BotConfigOut | None)
def get_active_bot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = db.query(BotConfig).filter(BotConfig.is_active == 1).first()
    if not config:
        return None
    return BotConfigOut.model_validate(config)


@router.post("/bot", response_model=BotConfigOut)
def create_bot(
    data: BotConfigCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = BotConfig(**data.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return BotConfigOut.model_validate(config)


@router.put("/bot/{config_id}", response_model=BotConfigOut)
def update_bot(
    config_id: int,
    data: BotConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(BotConfig).filter(BotConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return BotConfigOut.model_validate(config)


@router.delete("/bot/{config_id}")
def delete_bot(
    config_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(BotConfig).filter(BotConfig.id == config_id).first()
    if not config:
        raise HTTPException(404, "配置不存在")
    db.delete(config)
    db.commit()
    return {"message": "已删除"}


@router.get("/bot/default-prompt")
def get_default_prompt():
    """获取默认提示词"""
    return {"system_prompt": DEFAULT_SYSTEM_PROMPT}


# ==================== 提醒配置 ====================

@router.get("/reminder-types")
def list_reminder_types():
    """获取提醒类型列表"""
    return [{"type": t[0], "label": t[1]} for t in REMINDER_TYPES]


@router.get("/reminders", response_model=list[ReminderConfigOut])
def list_reminders(
    user_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ReminderConfig)
    if user_id:
        query = query.filter(ReminderConfig.user_id == user_id)
    items = query.order_by(ReminderConfig.user_id, ReminderConfig.type).all()
    type_map = dict(REMINDER_TYPES)
    result = []
    for r in items:
        out = ReminderConfigOut.model_validate(r)
        out.type_label = type_map.get(r.type, r.type)
        if r.user:
            out.user_name = r.user.display_name or r.user.username
        result.append(out)
    return result


@router.post("/reminders", response_model=ReminderConfigOut)
def create_reminder(
    data: ReminderConfigCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing = db.query(ReminderConfig).filter(
        ReminderConfig.user_id == data.user_id,
        ReminderConfig.type == data.type,
    ).first()
    if existing:
        raise HTTPException(400, "该用户已存在此类型的提醒配置")
    config = ReminderConfig(**data.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return ReminderConfigOut.model_validate(config)


@router.put("/reminders/{reminder_id}", response_model=ReminderConfigOut)
def update_reminder(
    reminder_id: int,
    data: ReminderConfigUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(ReminderConfig).filter(ReminderConfig.id == reminder_id).first()
    if not config:
        raise HTTPException(404, "提醒配置不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    out = ReminderConfigOut.model_validate(config)
    out.type_label = dict(REMINDER_TYPES).get(config.type, config.type)
    if config.user:
        out.user_name = config.user.display_name or config.user.username
    return out


@router.delete("/reminders/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = db.query(ReminderConfig).filter(ReminderConfig.id == reminder_id).first()
    if not config:
        raise HTTPException(404, "提醒配置不存在")
    db.delete(config)
    db.commit()
    return {"message": "已删除"}


# ==================== 推送日志 ====================

@router.get("/reminder-logs", response_model=list[ReminderLogOut])
def list_reminder_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = db.query(ReminderLog).order_by(
        ReminderLog.pushed_at.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return [ReminderLogOut.model_validate(r) for r in items]

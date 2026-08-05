"""系统配置 API — 企业微信 / AI Bot / 提醒管理"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.models.auth import User
from app.utils.auth import get_current_user, get_current_admin
from app.models.system_config import (
    WecomConfig, BotConfig, BotConversation,
    ReminderConfig, ReminderLog, ReminderRule,
)
from app.utils.crypto import encrypt, decrypt, is_ciphertext
from app.schemas.system_config import (
    WecomConfigCreate, WecomConfigUpdate, WecomConfigOut,
    BotConfigCreate, BotConfigUpdate, BotConfigOut,
    DEFAULT_SYSTEM_PROMPT,
    ReminderConfigCreate, ReminderConfigUpdate, ReminderConfigOut,
    ReminderLogOut, REMINDER_TYPES,
    ReminderRuleCreate, ReminderRuleUpdate, ReminderRuleOut,
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
    config.secret = encrypt(config.secret)
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
    # secret 守卫：空值 / 脱敏回传 / 原密文回传 → 保留原值，避免双重加密
    secret_raw = update_data.get("secret")
    if secret_raw is None or not secret_raw or "****" in secret_raw \
            or is_ciphertext(secret_raw) or secret_raw == config.secret:
        update_data.pop("secret", None)
    for k, v in update_data.items():
        setattr(config, k, v)
    if "secret" in update_data:
        config.secret = encrypt(update_data["secret"])
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
    result = []
    for b in items:
        out = BotConfigOut.model_validate(b)
        # 脱敏显示
        if out.api_key and len(out.api_key) > 8:
            out.api_key = out.api_key[:4] + "****" + out.api_key[-4:]
        result.append(out)
    return result


@router.get("/bot/active", response_model=BotConfigOut | None)
def get_active_bot(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    config = db.query(BotConfig).filter(BotConfig.is_active == 1).first()
    if not config:
        return None
    out = BotConfigOut.model_validate(config)
    if out.api_key and len(out.api_key) > 8:
        out.api_key = out.api_key[:4] + "****" + out.api_key[-4:]
    return out


@router.post("/bot", response_model=BotConfigOut)
def create_bot(
    data: BotConfigCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    config = BotConfig(**data.model_dump())
    config.api_key = encrypt(config.api_key)
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
    # api_key 守卫：空值 / 脱敏回传 / 原密文回传 → 保留原值，避免双重加密
    api_key_raw = update_data.get("api_key")
    if api_key_raw is None or not api_key_raw or "****" in api_key_raw \
            or is_ciphertext(api_key_raw) or api_key_raw == config.api_key:
        update_data.pop("api_key", None)
    for k, v in update_data.items():
        setattr(config, k, v)
    if "api_key" in update_data:
        config.api_key = encrypt(update_data["api_key"])
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


# ==================== 提醒规则（D8：规则配置化） ====================

@router.get("/reminder-rules", response_model=list[ReminderRuleOut])
def list_reminder_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提醒规则列表（按提醒点编码排序）"""
    items = db.query(ReminderRule).order_by(ReminderRule.code).all()
    return [ReminderRuleOut.model_validate(r) for r in items]


@router.post("/reminder-rules", response_model=ReminderRuleOut)
def create_reminder_rule(
    data: ReminderRuleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """新建提醒规则（code 必须对应代码埋点，不可凭空造触发逻辑 — D8 边界）"""
    existing = db.query(ReminderRule).filter(ReminderRule.code == data.code).first()
    if existing:
        raise HTTPException(400, f"提醒点 {data.code} 已存在规则")
    rule = ReminderRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ReminderRuleOut.model_validate(rule)


@router.put("/reminder-rules/{rule_id}", response_model=ReminderRuleOut)
def update_reminder_rule(
    rule_id: int,
    data: ReminderRuleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """更新提醒规则（内容/周期/方式/角色/去重窗口全可配）"""
    rule = db.query(ReminderRule).filter(ReminderRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "提醒规则不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return ReminderRuleOut.model_validate(rule)


@router.delete("/reminder-rules/{rule_id}")
def delete_reminder_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    rule = db.query(ReminderRule).filter(ReminderRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, "提醒规则不存在")
    db.delete(rule)
    db.commit()
    return {"message": "已删除"}

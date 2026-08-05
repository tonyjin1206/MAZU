"""提醒服务 — 事件埋点统一调用入口

埋点代码只传 (point_code, doc_type, doc_id, doc_no, data)，
标题/内容/收件人/渠道/去重全部由 sys_reminder_rule 规则决定（D8 规则配置化）。
"""
from datetime import datetime, timedelta, timezone


class _SafeDict(dict):
    """模板渲染兜底：缺失占位符保留原文，不抛 KeyError"""

    def __missing__(self, key):
        return f"{{{key}}}"


def render_template(tpl: str | None, data: dict | None) -> str:
    """渲染 {order_no}/{amount}/{due_date} 占位符模板"""
    if not tpl:
        return ""
    return tpl.format_map(_SafeDict(data or {}))


def resolve_recipients(rule, db) -> list[int]:
    """接收人解析 — 第一版：按规则 target_roles 查全部启用用户

    第二版（单据加业务员字段后）：单据归属人优先，无则按角色兜底 —— 只改此函数
    """
    roles = rule.target_roles or []
    if not roles:
        return []
    from app.models.auth import User, Role
    users = db.query(User).filter(
        User.is_active == 1,
        User.role_id.in_(db.query(Role.id).filter(Role.code.in_(roles))),
    ).all()
    return [u.id for u in users]


def notify(db, point_code: str, doc_type: str, doc_id, doc_no="", data: dict | None = None) -> int:
    """事件提醒入口：查规则 → 渲染 → 解析收件人 → 去重 → 写通知（落库即视为已发 D7）

    返回写入的通知条数（0 = 规则停用或去重命中）
    """
    from app.models.system_config import ReminderRule, Notification

    rule = db.query(ReminderRule).filter(
        ReminderRule.code == point_code,
        ReminderRule.enabled == 1,
    ).first()
    if not rule:
        return 0

    dedup_key = f"{point_code}:{doc_type}:{doc_id}"

    # 去重：同单据同提醒点在 dedup_hours 窗口内不重复推（D5）
    # 注意：SQLite func.now() = CURRENT_TIMESTAMP 存 UTC，须用 UTC 比较（本地时间会永远不命中）
    hours = rule.dedup_hours or 1
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    exists = db.query(Notification).filter(
        Notification.dedup_key == dedup_key,
        Notification.created_at >= cutoff,
    ).first()
    if exists:
        return 0

    title = render_template(rule.title_template, data)
    content = render_template(rule.content_template, data)
    recipients = resolve_recipients(rule, db)
    if not recipients:
        return 0

    count = 0
    for uid in recipients:
        db.add(Notification(
            user_id=uid,
            point_code=point_code,
            title=title or rule.name,
            content=content,
            doc_type=doc_type,
            doc_id=doc_id,
            doc_no=doc_no,
            dedup_key=dedup_key,
        ))
        count += 1
    db.commit()

    # 渠道钩子：channel 含 wecom 时未来在此转发企微（步骤4）
    # if "wecom" in (rule.channel or []):
    #     _push_wecom(rule, recipients, title, content)

    return count

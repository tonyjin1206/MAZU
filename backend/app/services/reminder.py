"""预警提醒服务 — 事件埋点统一调用入口 + 定时账期扫描入口

埋点代码只传 (point_code, doc_type, doc_id, doc_no, data)，
标题/内容/收件人/渠道/去重全部由 sys_reminder_rule 规则决定（D8 规则配置化）。

产品逻辑约定（v2.8.0，按当前 main 基底重校）：
- 无「生产订单」模块（弃用），销售订单下游走「转直采 / 转外发 / 转生产(自产)」三分支，
  故不设 MO_* 提醒点；以 SO_TO_PURCHASE / SO_TO_OUTSOURCE / SO_TO_PRODUCTION
  替代原 AO 的 MO_PLANNED / MO_OUTSOURCED。
- 事件提醒点：SO_APPROVED / SO_TO_PURCHASE / SO_TO_OUTSOURCE / SO_TO_PRODUCTION
  / DELIVERY_NOTIFIED / DELIVERY_CONFIRMED / AR_CREATED。
- 定时提醒点（每日扫描 + 启动补扫）：AR_DUE_SOON / AR_OVERDUE / AP_DUE_SOON / AP_OVERDUE。
- 站内为主（sys_notification 落库即视为已发，D7）；企微通道为预留钩子（本项目未启用）。
"""
from datetime import datetime, timedelta, timezone, date


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

    未来单据加业务员字段后：单据归属人优先，无则按角色兜底 —— 只改此函数。
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
    """事件 / 定时提醒统一入口：查规则 → 渲染 → 解析收件人 → 去重 → 写通知（落库即视为已发 D7）

    返回写入的通知条数（0 = 规则停用/无收件人/去重命中）。
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
    # 注意：SQLite func.now() = CURRENT_TIMESTAMP 存 UTC，须用 UTC 比较
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

    # 渠道钩子：channel 含 wecom 时未来在此转发企微（推进步骤，本项目未启用）
    # if "wecom" in (rule.channel or []):
    #     _push_wecom(rule, recipients, title, content)

    return count


def run_scheduled_scan(db) -> dict:
    """每日定时账期扫描（应收/应付 将到期 + 逾期）— 返回各提醒点写入条数。

    触发：应用启动时补扫一次（D4），此后每日按 schedule_cron 扫描。
    """
    from app.models.sales import AccountsReceivable
    from app.models.purchase import AccountsPayable
    from app.models.system_config import ReminderRule

    today = date.today()
    summary = {}

    def _scan(rule_code, records, kind):
        rule = db.query(ReminderRule).filter(ReminderRule.code == rule_code, ReminderRule.enabled == 1).first()
        if not rule:
            summary[rule_code] = 0
            return
        advance = rule.advance_days or 0
        upper = today + timedelta(days=advance)
        cnt = 0
        skip = set()
        for rec in records:
            # rec: (doc_id, doc_no, balance, due_date, label)
            doc_id, doc_no, balance, due_date, label = rec
            if not due_date or (balance or 0) <= 0:
                continue
            if rule_code.endswith("_DUE_SOON"):
                # 到期日在 [今+1, 今+N] 且未收清/未付清
                if not (today < due_date <= upper):
                    continue
            else:  # _OVERDUE
                if not (due_date < today):
                    continue
            key = f"{doc_id}:{due_date}"
            if key in skip:
                continue
            skip.add(key)
            cnt += notify(db, rule_code, kind, doc_id, doc_no,
                          {"doc_no": doc_no, "amount": round(balance, 2), "due_date": str(due_date)})
        summary[rule_code] = cnt

    # 应收（蓝字，余额>0，未收清）
    ars = [(a.id, a.ar_no or "", a.balance or 0, a.due_date, "ar") for a in
           db.query(AccountsReceivable).filter(AccountsReceivable.is_red != 1).all()]
    _scan("AR_DUE_SOON", ars, "ar_account")
    _scan("AR_OVERDUE", ars, "ar_account")

    # 应付（未付清）
    aps = [(p.id, p.ap_no or "", p.balance or 0, p.due_date, "ap") for p in
           db.query(AccountsPayable).all()]
    _scan("AP_DUE_SOON", aps, "ap_account")
    _scan("AP_OVERDUE", aps, "ap_account")

    return summary


def seed_reminder_rules(db):
    """幂等种子：预警提醒规则定义（事件 + 定时）。已有则跳过（只加不改，可手动在配置页调参）。"""
    from app.models.system_config import ReminderRule

    event_rules = [
        {"code": "SO_APPROVED", "name": "销售订单审核通过", "trigger_type": "event",
         "title_template": "销售订单 {order_no} 已审核",
         "content_template": "订单 {order_no}（{amount}）已审核，请对明细行进行转直采/转委外并安排发货。",
         "target_roles": ["sales_manager"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "SO_TO_PURCHASE", "name": "销售明细转直采", "trigger_type": "event",
         "title_template": "销售订单 {order_no} 已转直采",
         "content_template": "订单 {order_no} 有明细行转入直采，请到「采购管理→销售订单转采购」办理采购。（替代原生产订单排产提醒）",
         "target_roles": ["purchase_manager"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "SO_TO_OUTSOURCE", "name": "销售明细转外发", "trigger_type": "event",
         "title_template": "销售订单 {order_no} 已转外发",
         "content_template": "订单 {order_no} 有明细行转入委外，请到「委外管理→销售订单转委外」安排工序与原料采购。",
         "target_roles": ["purchase_manager"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "SO_TO_PRODUCTION", "name": "销售明细转生产（自产）", "trigger_type": "event",
         "title_template": "销售订单 {order_no} 已转生产",
         "content_template": "订单 {order_no} 有明细行转入自产，已生成生产订单 {mo_no}，请到「生产管理」安排排产与发料。",
         "target_roles": ["production_manager"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "DELIVERY_NOTIFIED", "name": "已通知发货（待出库）", "trigger_type": "event",
         "title_template": "发货单 {delivery_no} 已通知发货",
         "content_template": "发货单 {delivery_no}（{amount}）已通知发货，请到「成品出库」按批次完成出库。",
         "target_roles": ["warehouse_keeper"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "DELIVERY_CONFIRMED", "name": "明细行发货完成", "trigger_type": "event",
         "title_template": "销售订单 {order_no} 已发货",
         "content_template": "订单 {order_no} 明细行已确认发货完成，请安排开票。",
         "target_roles": ["sales_manager"], "channel": ["inapp"], "dedup_hours": 1},
        {"code": "AR_CREATED", "name": "应收生成", "trigger_type": "event",
         "title_template": "应收 {ar_no} 已生成（{amount}）",
         "content_template": "应收 {ar_no}（{amount}）已生成，财务请入账，销售请跟进催收。",
         "target_roles": ["finance_manager", "sales_manager"], "channel": ["inapp"], "dedup_hours": 1},
    ]

    schedule_rules = [
        {"code": "AR_DUE_SOON", "name": "应收将到期", "trigger_type": "schedule",
         "title_template": "应收 {doc_no} 将于 {due_date} 到期（{amount}）",
         "content_template": "应收 {doc_no} 将于 {due_date} 到期，余额 {amount}，请销售安排催收。",
         "target_roles": ["sales_manager"], "channel": ["inapp"], "schedule_cron": "0 9 * * *",
         "advance_days": 7, "dedup_hours": 48},
        {"code": "AR_OVERDUE", "name": "应收逾期", "trigger_type": "schedule",
         "title_template": "应收 {doc_no} 已逾期（{amount}）",
         "content_template": "应收 {doc_no} 已于 {due_date} 到期仍未收清，余额 {amount}，请销售催收升级、财务跟进。",
         "target_roles": ["sales_manager", "finance_manager"], "channel": ["inapp"],
         "schedule_cron": "0 9 * * *", "advance_days": 0, "dedup_hours": 24},
        {"code": "AP_DUE_SOON", "name": "应付将到期", "trigger_type": "schedule",
         "title_template": "应付 {doc_no} 将于 {due_date} 到期（{amount}）",
         "content_template": "应付 {doc_no} 将于 {due_date} 到期，余额 {amount}，请财务安排付款。",
         "target_roles": ["finance_manager"], "channel": ["inapp"], "schedule_cron": "0 9 * * *",
         "advance_days": 7, "dedup_hours": 48},
        {"code": "AP_OVERDUE", "name": "应付逾期", "trigger_type": "schedule",
         "title_template": "应付 {doc_no} 已逾期（{amount}）",
         "content_template": "应付 {doc_no} 已于 {due_date} 到期仍未付清，余额 {amount}，请财务安排付款、采购知悉。",
         "target_roles": ["finance_manager", "purchase_manager"], "channel": ["inapp"],
         "schedule_cron": "0 9 * * *", "advance_days": 0, "dedup_hours": 24},
    ]

    for r in event_rules + schedule_rules:
        exists = db.query(ReminderRule).filter(ReminderRule.code == r["code"]).first()
        if not exists:
            db.add(ReminderRule(**r))
    db.commit()

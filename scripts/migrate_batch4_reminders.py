#!/usr/bin/env python3
"""
SP 移植线批 4 预警提醒系统数据库迁移：通知内核(sys_notification) + 规则配置(sys_reminder_rule)
用法: python scripts/migrate_batch4_reminders.py [数据库路径，默认 backend/data/erp.db]

包含：
1. 新建 sys_reminder_rule（预警提醒规则，事件/定时，规则配置化）
2. 新建 sys_notification（站内通知，落库即视为已发）
3. 幂等：已存在的表自动跳过；提醒规则种子（缺失才补，可重复执行）。
"""
import sqlite3
import sys
from pathlib import Path

CREATE_REMINDER_RULE = """
CREATE TABLE IF NOT EXISTS sys_reminder_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code VARCHAR(64) NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    trigger_type VARCHAR(16) NOT NULL DEFAULT 'event',
    enabled INTEGER DEFAULT 1,
    title_template VARCHAR(256),
    content_template TEXT,
    target_roles TEXT,
    channel TEXT,
    schedule_cron VARCHAR(32) DEFAULT '0 9 * * *',
    advance_days INTEGER DEFAULT 7,
    dedup_hours INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_NOTIFICATION = """
CREATE TABLE IF NOT EXISTS sys_notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    point_code VARCHAR(64) NOT NULL,
    title VARCHAR(256),
    content TEXT,
    doc_type VARCHAR(32),
    doc_id INTEGER,
    doc_no VARCHAR(64),
    dedup_key VARCHAR(128),
    read_status INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES sys_user(id)
)
"""

# 提醒规则种子（与 services/reminder.seed_reminder_rules 保持一致；缺失才补）
RULES = [
    # 事件型（6 个，按当前产品逻辑：无生产订单模块，销售订单下游走转直采/转外发）
    ("SO_APPROVED", "销售订单审核通过", "event", 1,
     "销售订单 {order_no} 已审核",
     "订单 {order_no}（{amount}）已审核，请对明细行进行转直采/转委外并安排发货。",
     '["sales_manager"]', '["inapp"]', "0 9 * * *", 7, 1),
    ("SO_TO_PURCHASE", "销售明细转直采", "event", 1,
     "销售订单 {order_no} 已转直采",
     "订单 {order_no} 有明细行转入直采，请到「采购管理→销售订单转采购」办理采购。（替代原生产订单排产提醒）",
     '["purchase_manager"]', '["inapp"]', "0 9 * * *", 7, 1),
    ("SO_TO_OUTSOURCE", "销售明细转外发", "event", 1,
     "销售订单 {order_no} 已转外发",
     "订单 {order_no} 有明细行转入委外，请到「委外管理→销售订单转委外」安排工序与原料采购。",
     '["production_manager", "purchase_manager"]', '["inapp"]', "0 9 * * *", 7, 1),
    ("DELIVERY_NOTIFIED", "已通知发货（待出库）", "event", 1,
     "发货单 {delivery_no} 已通知发货",
     "发货单 {delivery_no}（{amount}）已通知发货，请到「成品出库」按批次完成出库。",
     '["warehouse_keeper"]', '["inapp"]', "0 9 * * *", 7, 1),
    ("DELIVERY_CONFIRMED", "明细行发货完成", "event", 1,
     "销售订单 {order_no} 已发货",
     "订单 {order_no} 明细行已确认发货完成，请安排开票。",
     '["sales_manager"]', '["inapp"]', "0 9 * * *", 7, 1),
    ("AR_CREATED", "应收生成", "event", 1,
     "应收 {ar_no} 已生成（{amount}）",
     "应收 {ar_no}（{amount}）已生成，财务请入账，销售请跟进催收。",
     '["finance_manager", "sales_manager"]', '["inapp"]', "0 9 * * *", 7, 1),
    # 定时型（4 个，应收/应付 将到期 + 逾期）
    ("AR_DUE_SOON", "应收将到期", "schedule", 1,
     "应收 {doc_no} 将于 {due_date} 到期（{amount}）",
     "应收 {doc_no} 将于 {due_date} 到期，余额 {amount}，请销售安排催收。",
     '["sales_manager"]', '["inapp"]', "0 9 * * *", 7, 48),
    ("AR_OVERDUE", "应收逾期", "schedule", 1,
     "应收 {doc_no} 已逾期（{amount}）",
     "应收 {doc_no} 已于 {due_date} 到期仍未收清，余额 {amount}，请销售催收升级、财务跟进。",
     '["sales_manager", "finance_manager"]', '["inapp"]', "0 9 * * *", 0, 24),
    ("AP_DUE_SOON", "应付将到期", "schedule", 1,
     "应付 {doc_no} 将于 {due_date} 到期（{amount}）",
     "应付 {doc_no} 将于 {due_date} 到期，余额 {amount}，请财务安排付款。",
     '["finance_manager"]', '["inapp"]', "0 9 * * *", 7, 48),
    ("AP_OVERDUE", "应付逾期", "schedule", 1,
     "应付 {doc_no} 已逾期（{amount}）",
     "应付 {doc_no} 已于 {due_date} 到期仍未付清，余额 {amount}，请财务安排付款、采购知悉。",
     '["finance_manager", "purchase_manager"]', '["inapp"]', "0 9 * * *", 0, 24),
]


def migrate(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        cur.execute(CREATE_REMINDER_RULE)
        cur.execute(CREATE_NOTIFICATION)
        print("✓ 表 sys_reminder_rule / sys_notification 已就绪")

        # 幂等种子提醒规则
        for r in RULES:
            cur.execute("SELECT COUNT(*) FROM sys_reminder_rule WHERE code=?", (r[0],))
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """INSERT INTO sys_reminder_rule
                    (code, name, trigger_type, enabled, title_template, content_template,
                     target_roles, channel, schedule_cron, advance_days, dedup_hours)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""", r)
                print(f"  + 规则 {r[0]}")
        conn.commit()
        total = cur.execute("SELECT COUNT(*) FROM sys_reminder_rule").fetchone()[0]
        print(f"✓ 提醒规则种子完成（共 {total} 条）")
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "backend" / "data" / "erp.db"
    if not db_path.exists():
        print(f"⚠ 数据库不存在：{db_path}（将跳过）")
        sys.exit(0)
    migrate(db_path)

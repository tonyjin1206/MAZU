"""重置本地开发库：清空全部业务数据，保留系统表（用户/角色/权限/配置）

用途：测试/演示数据跑脏本地库后一键恢复干净种子状态。
- 保留：sys_user（仅 admin）、sys_role、sys_permission、sys_role_permission、
        sys_bot_config、sys_bot_conversation、sys_reminder_config、sys_reminder_log、sys_wecom_config
- 清空：fd_* 基础档案、mo_* 生产、po_* 采购、so_* 销售、ap_*/ar_* 财务、
        inv_* 库存、tr_* 退税、sys_operation_log 审计日志
- 重置被清空表的自增 id（sqlite_sequence）

用法: python scripts/reset_local_db.py [数据库路径，默认 backend/data/erp.db]
⚠️ 危险操作：先手动备份（脚本不自动备份）
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

# 保留的系统表
KEEP = {
    "sys_user", "sys_role", "sys_permission", "sys_role_permission",
    "sys_bot_config", "sys_bot_conversation",
    "sys_reminder_config", "sys_reminder_log", "sys_reminder_rule",
    "sys_notification", "sys_wecom_config",
}


def reset(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    try:
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]

        cleared = []
        for t in tables:
            if t in KEEP:
                continue
            cur.execute(f"DELETE FROM {t}")
            cleared.append(t)

        # 清理测试用户（保留 admin）
        cur.execute("DELETE FROM sys_user WHERE username != 'admin'")
        cleared.append("sys_user(测试用户)")

        # 重置被清空表的自增 id（sqlite_sequence 可能不存在：非 AUTOINCREMENT 表无此表）
        has_seq = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone()
        if has_seq:
            cleared_set = set(cleared)
            for row in cur.execute("SELECT name FROM sqlite_sequence").fetchall():
                if row[0] not in KEEP or row[0] == "sys_user":
                    cur.execute("DELETE FROM sqlite_sequence WHERE name=?", (row[0],))

        conn.commit()
        # WAL checkpoint
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print(f"已清空 {len(cleared)} 组业务数据：\n  " + ", ".join(sorted(set(cleared))))
        print(f"保留：admin 用户、7 角色、{cur.execute('SELECT COUNT(*) FROM sys_permission').fetchone()[0]} 权限码、角色关联、系统配置")
        print("✅ 清理完成（自增 id 已归位）")
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在: {db}")
        sys.exit(1)
    confirm = input(f"确认清理 {db} 的全部业务数据？[y/N] ")
    if confirm.strip().lower() != "y":
        print("已取消")
        sys.exit(0)
    reset(db)

"""迁移：仓库管理独立菜单（2026-07-31）

背景：仓库档案此前无前端维护界面，新增「基础档案-仓库管理」菜单。

- Permission 表补 menu:warehouses（幂等）
- 角色权限关联补新码（幂等，只加不删，不覆盖手工勾选）：
  管理员 / 生产经理（拥有基础档案权限的角色）

用法: python scripts/migrate_warehouse_menu.py [数据库路径，默认 backend/data/erp.db]
"""

import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "backend" / "data" / "erp.db"

NEW_CODE = "menu:warehouses"
NEW_NAME = "仓库管理"
ROLES_WITH_FOUNDATION = ["admin", "production_manager"]


def migrate(db_path: Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    changed = False
    try:
        # 1. 权限码（sys_permission 主键=code，无 id 列）
        if cur.execute("SELECT code FROM sys_permission WHERE code=?", (NEW_CODE,)).fetchone():
            print(f"[跳过] 权限码 {NEW_CODE} 已存在")
        else:
            cur.execute(
                "INSERT INTO sys_permission (code, name, module, description) VALUES (?,?,?,?)",
                (NEW_CODE, NEW_NAME, "基础档案", ""))
            print(f"[执行] 插入权限码 {NEW_CODE}（{NEW_NAME}）")
            changed = True

        # 2. 角色关联（按角色 code 找 role id，只加不删）
        for role_code in ROLES_WITH_FOUNDATION:
            role = cur.execute("SELECT id FROM sys_role WHERE code=?", (role_code,)).fetchone()
            if not role:
                print(f"[跳过] 角色 {role_code} 不存在")
                continue
            role_id = role[0]
            if cur.execute(
                "SELECT 1 FROM sys_role_permission WHERE role_id=? AND permission_code=?",
                (role_id, NEW_CODE)).fetchone():
                print(f"[跳过] {role_code} 已有关联")
                continue
            cur.execute(
                "INSERT INTO sys_role_permission (role_id, permission_code) VALUES (?,?)",
                (role_id, NEW_CODE))
            print(f"[执行] {role_code} 补关联 {NEW_CODE}")
            changed = True

        conn.commit()
        print("\n迁移完成 ✅" if changed else "\n已是最新结构，无需迁移 ✅")
        return changed
    finally:
        conn.close()


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    if not db.exists():
        print(f"数据库不存在: {db}（新环境由启动种子自动创建，无需迁移）")
        sys.exit(0)
    migrate(db)

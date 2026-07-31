"""迁移：权限清单与真实菜单对齐（2026-07-31）

背景：角色管理页的权限清单缺 6 个真实菜单的权限码
（采购需求/完工入库/企业微信配置/AI模型配置/AI助手/提醒管理）。

- Permission 表补 6 码（幂等）
- 角色权限关联补新码（幂等，只加不删，不覆盖手工勾选）：
  - 管理员: 全部 6 码
  - 采购经理: menu:purchase:requisitions
  - 生产经理: menu:production:receipts

用法: python scripts/migrate_permissions_sync.py
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.database import SessionLocal  # noqa: E402
from app.models.auth import Permission, Role, RolePermission  # noqa: E402

NEW_PERMS = [
    {"code": "menu:purchase:requisitions", "name": "采购需求", "module": "采购管理", "description": ""},
    {"code": "menu:production:receipts", "name": "完工入库", "module": "生产管理", "description": ""},
    {"code": "menu:system:wecom", "name": "企业微信配置", "module": "系统管理", "description": ""},
    {"code": "menu:system:bot", "name": "AI 模型配置", "module": "系统管理", "description": ""},
    {"code": "menu:system:bot-chat", "name": "AI 助手", "module": "系统管理", "description": ""},
    {"code": "menu:system:reminders", "name": "提醒管理", "module": "系统管理", "description": ""},
]

# 角色 → 应补的新码
ROLE_EXTRA = {
    "admin": [p["code"] for p in NEW_PERMS],
    "purchase_manager": ["menu:purchase:requisitions"],
    "production_manager": ["menu:production:receipts"],
}


def main():
    db = SessionLocal()
    added_perms = 0
    for pd in NEW_PERMS:
        if not db.query(Permission).filter(Permission.code == pd["code"]).first():
            db.add(Permission(**pd))
            added_perms += 1
    db.flush()

    total_link = 0
    for role_code, codes in ROLE_EXTRA.items():
        role = db.query(Role).filter(Role.code == role_code).first()
        if not role:
            print(f"  ! 角色 {role_code} 不存在，跳过")
            continue
        for pc in codes:
            exists = db.query(RolePermission).filter(
                RolePermission.role_id == role.id,
                RolePermission.permission_code == pc,
            ).first()
            if not exists:
                db.add(RolePermission(role_id=role.id, permission_code=pc))
                total_link += 1

    db.commit()
    total = db.query(Permission).count()
    print(f"✅ 权限定义总数: {total}（新增 {added_perms}）")
    print(f"✅ 角色权限关联新增: {total_link} 条")
    db.close()


if __name__ == "__main__":
    main()

"""幂等迁移：新增 menu:currencies 权限码 + 按角色规则补 RolePermission（只补不删）

背景：main.py _seed_rbac 只在角色不存在时写 RolePermission，已有库新增权限码后
角色关联是旧快照。本脚本按 main.py 的分组规则给每个角色补新码，
绝不重算覆盖（用户可能手工勾选/取消过）。

用法：cd backend && venv/Scripts/python.exe ../scripts/migrate_currencies_permission.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("ERP_DEV", "1")

from app.database import SessionLocal  # noqa: E402
from app.models.auth import Role, RolePermission, Permission  # noqa: E402

# 新权限码及其归属分组（与 main.py role_defs 分组规则一致）
NEW_CODE = "menu:currencies"
GROUP_FOUNDATION = True  # 归属 foundation 组（生产经理）

# 哪些角色补新码（按 main.py 角色分组规则）
ROLE_RULES = {
    "admin": True,                     # 全部权限
    "production_manager": True,        # foundation 组
    "sales_manager": False,
    "purchase_manager": False,
    "finance_manager": False,
    "warehouse_keeper": False,
    "readonly": False,
}


def main():
    db = SessionLocal()
    try:
        perm = db.query(Permission).filter(Permission.code == NEW_CODE).first()
        if not perm:
            db.add(Permission(code=NEW_CODE, name="币种/汇率", module="基础档案", description=""))
            db.flush()
            print(f"  + 插入权限码 {NEW_CODE}")

        added = 0
        for role in db.query(Role).all():
            if not ROLE_RULES.get(role.code, False):
                continue
            exists = db.query(RolePermission).filter(
                RolePermission.role_id == role.id,
                RolePermission.permission_code == NEW_CODE,
            ).first()
            if not exists:
                db.add(RolePermission(role_id=role.id, permission_code=NEW_CODE))
                added += 1
                print(f"  + {role.code} 补 {NEW_CODE}")
        db.commit()
        print(f"✅ 迁移完成：{added} 个角色补充权限码 {NEW_CODE}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

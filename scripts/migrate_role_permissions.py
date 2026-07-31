"""幂等迁移：按角色规则补齐缺失权限关联（只加不删，尊重手工配置）

修复历史快照过期：production_manager 缺完工入库/盘点、purchase_manager 缺采购需求等。
规则与 main.py _seed_rbac 分组一致。admin 由 _seed_rbac 启动自动全量同步，无需处理。

用法：cd backend && venv/Scripts/python.exe ../scripts/migrate_role_permissions.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
os.environ.setdefault("ERP_DEV", "1")

from app.database import SessionLocal  # noqa: E402
from app.models.auth import Role, RolePermission  # noqa: E402


def _role_rules(db):
    """角色 → 应有权重码集合（与 main.py 分组一致）"""
    from sqlalchemy import text
    rows = db.execute(text("SELECT code FROM sys_permission")).fetchall()
    all_codes = {r[0] for r in rows}

    foundation = {c for c in all_codes if c.startswith(("menu:customers", "menu:suppliers", "menu:materials",
                   "menu:products", "menu:bom", "menu:processes", "menu:hs-codes", "menu:warehouses",
                   "menu:currencies"))}
    purchase_all = {c for c in all_codes if c.startswith("menu:purchase:")}
    purchase_finance = {c for c in purchase_all if c.endswith(("invoices", "ap", "payments"))}
    sales_all = {c for c in all_codes if c.startswith("menu:sales:")}
    sales_finance = {c for c in sales_all if c.endswith(("invoices", "ar", "collections"))}
    production = {c for c in all_codes if c.startswith("menu:production:")}
    inventory = {c for c in all_codes if c.startswith(("menu:inventory", "menu:production:batch"))}
    tax = {c for c in all_codes if c.startswith("menu:tax")}
    dashboard = {c for c in all_codes if c.startswith("menu:dashboard")}

    return {
        "sales_manager": dashboard | sales_all,
        "purchase_manager": dashboard | purchase_all,
        "production_manager": dashboard | foundation | production | inventory,
        "finance_manager": dashboard | purchase_finance | sales_finance | inventory | tax,
        "warehouse_keeper": dashboard | inventory,
        "readonly": dashboard,
        # admin 不在此处理（_seed_rbac 启动自动全量同步）
    }


def main():
    db = SessionLocal()
    try:
        rules = _role_rules(db)
        total = 0
        for role in db.query(Role).all():
            expected = rules.get(role.code)
            if expected is None:
                continue
            have = {rp.permission_code for rp in role.role_permissions}
            missing = sorted(expected - have)
            for pc in missing:
                db.add(RolePermission(role_id=role.id, permission_code=pc))
                total += 1
            if missing:
                print(f"  + {role.code} 补 {len(missing)} 个: {missing}")
        db.commit()
        print(f"✅ 迁移完成：共补 {total} 条角色权限关联（只加不删）")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

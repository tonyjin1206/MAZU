"""FastAPI 应用工厂"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


def _seed_rbac(db):
    """种子数据：预置权限和角色"""
    from app.models.auth import User, Role, Permission, RolePermission
    from app.utils.auth import get_password_hash

    # ====== 权限定义 ======
    permission_defs = [
        # 工作台
        {"code": "menu:dashboard", "name": "驾驶舱", "module": "工作台", "description": "首页工作台"},
        # 基础档案
        {"code": "menu:customers", "name": "客户管理", "module": "基础档案", "description": ""},
        {"code": "menu:suppliers", "name": "供应商管理", "module": "基础档案", "description": ""},
        {"code": "menu:materials", "name": "原辅材料", "module": "基础档案", "description": ""},
        {"code": "menu:products", "name": "产品档案", "module": "基础档案", "description": ""},
        {"code": "menu:bom", "name": "BOM管理", "module": "基础档案", "description": ""},
        {"code": "menu:processes", "name": "工序管理", "module": "基础档案", "description": ""},
        {"code": "menu:params", "name": "参数设置", "module": "基础档案", "description": ""},
        {"code": "menu:warehouses", "name": "仓库管理", "module": "基础档案", "description": ""},
        {"code": "menu:currencies", "name": "币种/汇率", "module": "基础档案", "description": ""},
        # 采购管理
        {"code": "menu:purchase:from-sales", "name": "销售订单转采购", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:requisitions", "name": "采购需求", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:orders", "name": "采购订单", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:receipts", "name": "采购入库", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:invoices", "name": "采购发票", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:ap", "name": "应付账款", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:payments", "name": "付款管理", "module": "采购管理", "description": ""},
        # 销售管理
        {"code": "menu:sales:orders", "name": "销售订单", "module": "销售管理", "description": ""},
        {"code": "menu:sales:deliveries", "name": "销售发货", "module": "销售管理", "description": ""},
        {"code": "menu:sales:invoices", "name": "销售发票", "module": "销售管理", "description": ""},
        {"code": "menu:sales:ar", "name": "应收账款", "module": "销售管理", "description": ""},
        {"code": "menu:sales:collections", "name": "收款管理", "module": "销售管理", "description": ""},
        # 生产管理（生产订单/工作台/加工费发票/完工入库已下线，仅保留批次追溯）
        {"code": "menu:production:batch", "name": "批次追溯", "module": "生产管理", "description": ""},
        # 库存管理
        {"code": "menu:inventory", "name": "库存收发存", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:stocktake", "name": "盘点管理", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:summary", "name": "收发存", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:stock-ins", "name": "成品入库", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:material-ins", "name": "原料入库", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:material-outs", "name": "原料出库", "module": "库存管理", "description": ""},
        {"code": "menu:inventory:delivery-outs", "name": "成品出库", "module": "库存管理", "description": ""},
        {"code": "menu:outsource:from-sales", "name": "销售订单转委外", "module": "委外管理", "description": ""},
        {"code": "menu:outsource:orders", "name": "委外订单", "module": "委外管理", "description": ""},
        # 退税管理
        # 系统管理
        {"code": "menu:system:users", "name": "用户管理", "module": "系统管理", "description": ""},
        {"code": "menu:system:roles", "name": "角色管理", "module": "系统管理", "description": ""},
        {"code": "menu:system:wecom", "name": "企业微信配置", "module": "系统管理", "description": ""},
        {"code": "menu:system:bot", "name": "Agent设置", "module": "系统管理", "description": ""},
        {"code": "menu:system:bot-chat", "name": "AI 助手", "module": "系统管理", "description": ""},
        {"code": "menu:system:reminders", "name": "预警提醒设置", "module": "系统管理", "description": ""},
    ]

    # 报关/退税/HS 编码功能已从前端取消（代码保留，下个版本再发布）—— 权限码一并移除
    # 生产管理（生产订单/工作台/加工费发票/完工入库）已下线：权限码并入弃用清理逻辑
    DEPRECATED_PERMS = (
        "menu:hs-codes", "menu:sales:customs", "menu:tax",
        "menu:production:orders", "menu:production:workspace",
        "menu:production:invoices", "menu:production:receipts",
    )

    # 插入权限（不存在则创建）
    for pd in permission_defs:
        existing = db.query(Permission).filter(Permission.code == pd["code"]).first()
        if not existing:
            db.add(Permission(**pd))

    # 清理已弃用权限码（报关/退税/HS编码已从前端取消，代码保留）——
    # 先删角色关联再删权限定义（幂等，对已有库生效）
    for deprecated in DEPRECATED_PERMS:
        db.query(RolePermission).filter(RolePermission.permission_code == deprecated).delete()
        existing = db.query(Permission).filter(Permission.code == deprecated).first()
        if existing:
            db.delete(existing)

    # ====== 角色定义 ======
    all_codes = [p["code"] for p in permission_defs]
    foundation = [c for c in all_codes if c.startswith("menu:customers") or c.startswith("menu:suppliers")
                  or c.startswith("menu:materials") or c.startswith("menu:products")
                  or c.startswith("menu:bom") or c.startswith("menu:processes")
                  or c.startswith("menu:warehouses")
                  or c.startswith("menu:currencies")]
    purchase_all = [c for c in all_codes if c.startswith("menu:purchase:")]
    purchase_base = [c for c in purchase_all if not c.endswith(("invoices", "ap", "payments"))]
    purchase_finance = [c for c in purchase_all if c.endswith(("invoices", "ap", "payments"))]
    sales_all = [c for c in all_codes if c.startswith("menu:sales:")]
    sales_base = [c for c in sales_all if not c.endswith(("invoices", "ar", "collections"))]
    sales_finance = [c for c in sales_all if c.endswith(("invoices", "ar", "collections"))]
    production = [c for c in all_codes if c.startswith("menu:production:")]
    inventory = ["menu:inventory", "menu:inventory:stocktake", "menu:inventory:stock-ins", "menu:inventory:material-ins", "menu:inventory:material-outs", "menu:inventory:delivery-outs", "menu:production:batch"]
    tax = []
    sys_menu = [c for c in all_codes if c.startswith("menu:system:")]

    dashboard = ["menu:dashboard"]
    biz_all = [c for c in all_codes if not c.startswith("menu:system:")]

    role_defs = [
        {"name": "管理员", "code": "admin", "description": "系统管理员，拥有全部权限",
         "is_system": 1, "permissions": all_codes},
        {"name": "销售经理", "code": "sales_manager", "description": "销售管理",
         "is_system": 1, "permissions": dashboard + sales_all},
        {"name": "采购经理", "code": "purchase_manager", "description": "采购管理",
         "is_system": 1, "permissions": dashboard + purchase_all},
        {"name": "生产经理", "code": "production_manager", "description": "生产管理（含基础档案和库存）",
         "is_system": 1, "permissions": dashboard + foundation + production + inventory},
        {"name": "财务经理", "code": "finance_manager", "description": "财务（含发票、应收应付、收款付款、库存）",
         "is_system": 1, "permissions": dashboard + purchase_finance + sales_finance + inventory + tax},
        {"name": "库管员", "code": "warehouse_keeper", "description": "库存管理",
         "is_system": 1, "permissions": dashboard + inventory},
        {"name": "只读", "code": "readonly", "description": "仅可查看驾驶舱",
         "is_system": 1, "permissions": dashboard},
    ]

    admin_role = None
    for rd in role_defs:
        role = db.query(Role).filter(Role.code == rd["code"]).first()
        if not role:
            role = Role(name=rd["name"], code=rd["code"],
                        description=rd["description"], is_system=rd["is_system"])
            db.add(role)
            db.flush()
            # 关联权限（去重：production 前缀列表与 inventory 硬编码的 menu:production:batch 重叠）
            for pc in dict.fromkeys(rd["permissions"]):
                perm = db.query(Permission).filter(Permission.code == pc).first()
                if perm:
                    db.add(RolePermission(role_id=role.id, permission_code=pc))
        if rd["code"] == "admin":
            # 管理员 = 全量权限：每次启动补齐缺失关联（只加不删，防快照过期）
            db.flush()  # 先落库新建角色的关联（SessionLocal autoflush=False，否则 exists 查不到会重复插入）
            for pc in all_codes:
                exists = db.query(RolePermission).filter(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_code == pc,
                ).first()
                if not exists:
                    db.add(RolePermission(role_id=role.id, permission_code=pc))
            admin_role = role

    # ====== 默认管理员用户 ======
    if admin_role:
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                display_name="系统管理员",
                role_id=admin_role.id,
                is_active=1,
            )
            db.add(admin)
            print(f"✅ 默认管理员已创建: {settings.DEFAULT_ADMIN_USERNAME}")

    db.commit()
    print("✅ RBAC 种子数据已初始化")


def _seed_params(db):
    """种子数据：参数设置默认选项（按分组幂等：该组无记录才插入，不覆盖用户已维护数据）"""
    from app.models.foundation import SystemParam

    defaults = [
        # 供应商类型
        ("supplier_type", "01", "原材料", 1, "供应商类型"),
        ("supplier_type", "02", "委外", 2, "供应商类型"),
        ("supplier_type", "03", "辅料", 3, "供应商类型"),
        # 材料类别
        ("material_category", "01", "原材料", 1, "原辅材料类别"),
        ("material_category", "02", "辅料", 2, "原辅材料类别"),
        ("material_category", "03", "包装材料", 3, "原辅材料类别"),
        # 计量单位
        ("unit", "01", "个", 1, "计量单位"),
        ("unit", "02", "件", 2, "计量单位"),
        ("unit", "03", "套", 3, "计量单位"),
        ("unit", "04", "台", 4, "计量单位"),
        ("unit", "05", "千克", 5, "计量单位"),
        ("unit", "06", "米", 6, "计量单位"),
        ("unit", "07", "平方米", 7, "计量单位"),
        ("unit", "08", "立方米", 8, "计量单位"),
        # 付款方式
        ("payment_method", "01", "银行转账", 1, "收付款方式"),
        ("payment_method", "02", "现金", 2, "收付款方式"),
        ("payment_method", "03", "承兑汇票", 3, "收付款方式"),
        # 国家（客户/供应商等表格通用下拉）
        ("country", "01", "中国", 1, "国家"),
        ("country", "02", "美国", 2, "国家"),
        ("country", "03", "日本", 3, "国家"),
        ("country", "04", "韩国", 4, "国家"),
        ("country", "05", "德国", 5, "国家"),
        ("country", "06", "英国", 6, "国家"),
        ("country", "07", "法国", 7, "国家"),
        ("country", "08", "新加坡", 8, "国家"),
        ("country", "09", "中国香港", 9, "国家"),
        ("country", "10", "印度", 10, "国家"),
        ("country", "11", "越南", 11, "国家"),
        ("country", "12", "泰国", 12, "国家"),
    ]
    # 按分组幂等：该分组无任何记录才插入默认（历史库不覆盖，新库/空组自动补）
    grouped = {}
    for group, key, label, sort, remark in defaults:
        grouped.setdefault(group, []).append((key, label, sort, remark))
    added = 0
    for group, rows in grouped.items():
        if db.query(SystemParam).filter(SystemParam.group_name == group).count() > 0:
            continue
        for key, label, sort, remark in rows:
            db.add(SystemParam(group_name=group, param_key=key, param_label=label, sort_order=sort, remark=remark))
        added += len(rows)
    if added:
        db.commit()
        print(f"✅ 参数设置种子数据已初始化（新增 {added} 条，覆盖分组：{list(grouped)}）")


# ====== 常用币种种子数据 ======

BASE_CURRENCIES = [
    {"code": "CNY", "name": "人民币", "symbol": "¥", "is_base": 1},
    {"code": "USD", "name": "美元", "symbol": "$", "is_base": 0},
    {"code": "EUR", "name": "欧元", "symbol": "€", "is_base": 0},
    {"code": "JPY", "name": "日元", "symbol": "¥", "is_base": 0},
    {"code": "GBP", "name": "英镑", "symbol": "£", "is_base": 0},
    {"code": "HKD", "name": "港币", "symbol": "HK$", "is_base": 0},
    {"code": "AUD", "name": "澳元", "symbol": "A$", "is_base": 0},
]


def _seed_currencies(db):
    """预置常用币种（幂等：code 已存在则跳过）"""
    from app.models.foundation import Currency
    added = 0
    for c in BASE_CURRENCIES:
        existing = db.query(Currency).filter(Currency.code == c["code"]).first()
        if not existing:
            db.add(Currency(**c))
            added += 1
    if added:
        db.commit()
        print(f"✅ 已预置 {added} 个常用币种")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _seed_rbac(db)
        _seed_params(db)
        _seed_currencies(db)
        from app.services.reminder import seed_reminder_rules
        seed_reminder_rules(db)
    finally:
        db.close()
    # 每日汇率定时任务（每天 09:00 从腾讯财经拉取一次，失败静默次日重试）
    task = asyncio.create_task(_daily_rate_task())
    # 预警提醒定时扫描（启动补扫一次 + 每日 09:00 扫描应收/应付账期，D4）
    reminder_task = asyncio.create_task(_daily_reminder_task())
    yield
    task.cancel()
    reminder_task.cancel()


async def _daily_rate_task():
    """每天 09:00 拉取汇率入库（国内源腾讯财经）；任务随进程生命周期运行"""
    import logging
    logger = logging.getLogger("daily_rate")
    while True:
        now = datetime.now()
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep(max(1.0, (next_run - now).total_seconds()))
        try:
            from app.routers.foundation import fetch_latest_rates
            from app.database import SessionLocal as _SL
            _db = _SL()
            try:
                result = fetch_latest_rates(_db, current_user=None)
                logger.info(f"每日汇率更新: {result.get('message', '')}")
            finally:
                _db.close()
        except Exception as e:
            logger.error(f"每日汇率更新失败: {e}")


async def _daily_reminder_task():
    """预警提醒定时扫描 — 启动立即补扫一次（D4 弥补未运行期间漏掉），此后每日 09:00 扫描。

    同单据同提醒点在 dedup_hours 窗口内不重复推（规则可配）；失败静默次日重试。
    """
    import logging
    logger = logging.getLogger("daily_reminder")

    async def _scan_once():
        from app.services.reminder import run_scheduled_scan
        from app.database import SessionLocal as _SL
        _db = _SL()
        try:
            summary = run_scheduled_scan(_db)
            fired = {k: v for k, v in summary.items() if v}
            if fired:
                logger.info(f"账期扫描提醒: {fired}")
        except Exception as e:
            logger.error(f"账期扫描失败: {e}")
        finally:
            _db.close()

    # 启动补扫一次（应用可能深夜重启，漏过当天 09:00 的扫描）
    await _scan_once()
    while True:
        now = datetime.now()
        next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        await asyncio.sleep(max(1.0, (next_run - now).total_seconds()))
        await _scan_once()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 所有 API 响应强制不缓存
    @app.middleware("http")
    async def no_cache_middleware(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # 注册路由
    from app.routers import auth, foundation, purchase, sales, production, tax_refund, inventory, dashboard, outsource, stock_in
    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
    app.include_router(foundation.router, prefix="/api/foundation", tags=["基础档案"])
    app.include_router(purchase.router, prefix="/api/purchase", tags=["采购管理"])
    app.include_router(sales.router, prefix="/api/sales", tags=["销售管理"])
    app.include_router(production.router, prefix="/api/production", tags=["生产管理"])
    app.include_router(outsource.router, prefix="/api/outsource", tags=["委外管理"])
    app.include_router(stock_in.router, prefix="/api/stock-in", tags=["库存管理"])
    app.include_router(tax_refund.router, prefix="/api/tax-refund", tags=["退税管理"])
    app.include_router(inventory.router, prefix="/api/inventory", tags=["库存管理"])
    app.include_router(dashboard.router, prefix="/api", tags=["驾驶舱"])
    from app.routers.system_config import router as system_config_router
    app.include_router(system_config_router, prefix="/api")
    from app.routers.bot_chat import router as bot_chat_router
    app.include_router(bot_chat_router, prefix="/api")
    from app.routers.notification import router as notification_router
    app.include_router(notification_router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": settings.APP_VERSION}

    # 生产模式下 serve 前端静态文件
    import os
    if not os.environ.get("ERP_DEV"):
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse
        frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
        if frontend_dist.exists():
            app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static_assets")
            @app.get("/{full_path:path}")
            async def serve_spa(full_path: str):
                file_path = frontend_dist / full_path
                if file_path.is_file():
                    return FileResponse(str(file_path))
                return FileResponse(str(frontend_dist / "index.html"))

    return app

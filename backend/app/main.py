"""FastAPI 应用工厂"""

from contextlib import asynccontextmanager
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
        {"code": "menu:hs-codes", "name": "HS编码", "module": "基础档案", "description": ""},
        # 采购管理
        {"code": "menu:purchase:orders", "name": "采购订单", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:receipts", "name": "采购入库", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:invoices", "name": "采购发票", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:ap", "name": "应付账款", "module": "采购管理", "description": ""},
        {"code": "menu:purchase:payments", "name": "付款管理", "module": "采购管理", "description": ""},
        # 销售管理
        {"code": "menu:sales:orders", "name": "销售订单", "module": "销售管理", "description": ""},
        {"code": "menu:sales:deliveries", "name": "销售发货", "module": "销售管理", "description": ""},
        {"code": "menu:sales:invoices", "name": "销售发票", "module": "销售管理", "description": ""},
        {"code": "menu:sales:customs", "name": "报关管理", "module": "销售管理", "description": ""},
        {"code": "menu:sales:ar", "name": "应收账款", "module": "销售管理", "description": ""},
        {"code": "menu:sales:collections", "name": "收款管理", "module": "销售管理", "description": ""},
        # 生产管理
        {"code": "menu:production:orders", "name": "生产订单", "module": "生产管理", "description": ""},
        {"code": "menu:production:workspace", "name": "生产工作台", "module": "生产管理", "description": ""},
        {"code": "menu:production:invoices", "name": "加工费发票", "module": "生产管理", "description": ""},
        {"code": "menu:production:batch", "name": "批次追溯", "module": "生产管理", "description": ""},
        # 库存管理
        {"code": "menu:inventory", "name": "库存收发存", "module": "库存管理", "description": ""},
        # 退税管理
        {"code": "menu:tax", "name": "退税申报", "module": "退税管理", "description": ""},
        # 系统管理
        {"code": "menu:system:users", "name": "用户管理", "module": "系统管理", "description": ""},
        {"code": "menu:system:roles", "name": "角色管理", "module": "系统管理", "description": ""},
    ]

    # 插入权限（不存在则创建）
    for pd in permission_defs:
        existing = db.query(Permission).filter(Permission.code == pd["code"]).first()
        if not existing:
            db.add(Permission(**pd))

    # ====== 角色定义 ======
    all_codes = [p["code"] for p in permission_defs]
    foundation = [c for c in all_codes if c.startswith("menu:customers") or c.startswith("menu:suppliers")
                  or c.startswith("menu:materials") or c.startswith("menu:products")
                  or c.startswith("menu:bom") or c.startswith("menu:processes")
                  or c.startswith("menu:hs-codes")]
    purchase_all = [c for c in all_codes if c.startswith("menu:purchase:")]
    purchase_base = [c for c in purchase_all if not c.endswith(("invoices", "ap", "payments"))]
    purchase_finance = [c for c in purchase_all if c.endswith(("invoices", "ap", "payments"))]
    sales_all = [c for c in all_codes if c.startswith("menu:sales:")]
    sales_base = [c for c in sales_all if not c.endswith(("invoices", "ar", "collections"))]
    sales_finance = [c for c in sales_all if c.endswith(("invoices", "ar", "collections"))]
    production = [c for c in all_codes if c.startswith("menu:production:")]
    inventory = ["menu:inventory", "menu:production:batch"]
    tax = ["menu:tax"]
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
        {"name": "财务经理", "code": "finance_manager", "description": "财务（含发票、应收应付、收款付款、库存、退税）",
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
            # 关联权限
            for pc in rd["permissions"]:
                perm = db.query(Permission).filter(Permission.code == pc).first()
                if perm:
                    db.add(RolePermission(role_id=role.id, permission_code=pc))
        if rd["code"] == "admin":
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _seed_rbac(db)
    finally:
        db.close()
    yield


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
    from app.routers import auth, foundation, purchase, sales, production, tax_refund, inventory, dashboard
    app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
    app.include_router(foundation.router, prefix="/api/foundation", tags=["基础档案"])
    app.include_router(purchase.router, prefix="/api/purchase", tags=["采购管理"])
    app.include_router(sales.router, prefix="/api/sales", tags=["销售管理"])
    app.include_router(production.router, prefix="/api/production", tags=["生产管理"])
    app.include_router(tax_refund.router, prefix="/api/tax-refund", tags=["退税管理"])
    app.include_router(inventory.router, prefix="/api/inventory", tags=["库存管理"])
    app.include_router(dashboard.router, prefix="/api", tags=["驾驶舱"])
    from app.routers.system_config import router as system_config_router
    app.include_router(system_config_router, prefix="/api")

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

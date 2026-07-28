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
        {"code": "dashboard:read", "name": "查看驾驶舱", "module": "工作台", "description": "查看首页工作台数据"},
        # 基础档案
        {"code": "foundation:read", "name": "查看基础档案", "module": "基础档案", "description": "查看客户/供应商/物料/产品等基础数据"},
        {"code": "foundation:write", "name": "编辑基础档案", "module": "基础档案", "description": "增删改基础档案数据"},
        # 采购管理
        {"code": "purchase:read", "name": "查看采购", "module": "采购管理", "description": "查看采购订单/入库/发票/应付等"},
        {"code": "purchase:write", "name": "编辑采购", "module": "采购管理", "description": "增删改采购单据"},
        {"code": "purchase:approve", "name": "审批采购", "module": "采购管理", "description": "审核/反审核采购订单"},
        # 销售管理
        {"code": "sales:read", "name": "查看销售", "module": "销售管理", "description": "查看销售订单/发货/发票/应收等"},
        {"code": "sales:write", "name": "编辑销售", "module": "销售管理", "description": "增删改销售单据"},
        {"code": "sales:approve", "name": "审批销售", "module": "销售管理", "description": "审核/反审核销售订单"},
        # 生产管理
        {"code": "production:read", "name": "查看生产", "module": "生产管理", "description": "查看生产订单/工作台/加工费等"},
        {"code": "production:write", "name": "编辑生产", "module": "生产管理", "description": "增删改生产单据"},
        # 库存管理
        {"code": "inventory:read", "name": "查看库存", "module": "库存管理", "description": "查看库存收发存"},
        {"code": "inventory:write", "name": "编辑库存", "module": "库存管理", "description": "库存调整操作"},
        # 退税管理
        {"code": "tax:read", "name": "查看退税", "module": "退税管理", "description": "查看退税申报"},
        {"code": "tax:write", "name": "编辑退税", "module": "退税管理", "description": "增删改退税申报"},
        # 系统管理
        {"code": "system:admin", "name": "系统管理", "module": "系统管理", "description": "用户管理/角色管理/系统设置"},
    ]

    # 插入权限（不存在则创建）
    for pd in permission_defs:
        existing = db.query(Permission).filter(Permission.code == pd["code"]).first()
        if not existing:
            db.add(Permission(**pd))

    # ====== 角色定义 ======
    all_codes = [p["code"] for p in permission_defs]
    read_codes = [c for c in all_codes if c.endswith(":read")]
    biz_write_codes = [c for c in all_codes if not c.startswith("system:") and c != "dashboard:read"]
    biz_no_approve = [c for c in biz_write_codes if not c.endswith(":approve")]

    role_defs = [
        {
            "name": "管理员", "code": "admin", "description": "系统管理员，拥有全部权限",
            "is_system": 1, "permissions": all_codes,
        },
        {
            "name": "经理", "code": "manager", "description": "业务经理，拥有所有业务权限（含审批）",
            "is_system": 1, "permissions": [c for c in all_codes if c != "system:admin"],
        },
        {
            "name": "操作员", "code": "operator", "description": "业务操作员，可增删改但不可审批",
            "is_system": 1, "permissions": biz_no_approve,
        },
        {
            "name": "只读", "code": "readonly", "description": "仅可查看所有页面",
            "is_system": 1, "permissions": read_codes + ["dashboard:read"],
        },
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

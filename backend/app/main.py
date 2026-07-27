"""FastAPI 应用工厂"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    init_db()
    # 初始化默认管理员
    from app.database import SessionLocal
    from app.models.auth import User
    from app.utils.auth import get_password_hash
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin_user = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                display_name="系统管理员",
                role="admin",
            )
            db.add(admin_user)
            db.commit()
            print(f"✅ 默认管理员已创建: {settings.DEFAULT_ADMIN_USERNAME}")
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

    # 初始化默认管理员
    @app.on_event("startup")
    def init_admin():
        from app.database import SessionLocal
        from app.models.auth import User
        from app.utils.auth import get_password_hash
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
            if not admin:
                admin_user = User(
                    username=settings.DEFAULT_ADMIN_USERNAME,
                    password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                    display_name="系统管理员",
                    role="admin",
                )
                db.add(admin_user)
                db.commit()
                print(f"✅ 默认管理员已创建: {settings.DEFAULT_ADMIN_USERNAME}")
        finally:
            db.close()

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

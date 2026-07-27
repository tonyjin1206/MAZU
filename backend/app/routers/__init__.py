"""路由包"""

from app.routers.auth import router as auth_router
from app.routers.foundation import router as foundation_router
from app.routers.purchase import router as purchase_router
from app.routers.sales import router as sales_router
from app.routers.production import router as production_router
from app.routers.tax_refund import router as tax_refund_router

__all__ = [
    "auth_router", "foundation_router",
    "purchase_router", "sales_router",
    "production_router", "tax_refund_router",
]

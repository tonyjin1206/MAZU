"""模型包 — 导入所有模型确保注册"""

from app.models.base import BaseMixin
from app.models.auth import User, Role, Permission, RolePermission
from app.models.foundation import (
    Material, Product, BomItem, Process,
    Department, Employee,
    Customer, Supplier, Outsourcer,
    Warehouse, Currency, ExchangeRate,
    HsCode, TradeTerm,
)
from app.models.inventory import (
    WarehouseInventory, StockTransaction,
    StockCheck, StockCheckItem,
)
from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem,
    PurchaseReceipt, PurchaseReceiptItem,
    PurchaseInvoice,
    AccountsPayable, Payment, PaymentAllocation,
)
from app.models.production import (
    ProductionOrder, ProductionMaterial, ProductionProcess, ProductionReceipt, ProcessingInvoice,
    OutsourcingOrder, OutsourceReceiptItem,
    MaterialIssueItem,
)
from app.models.sales import (
    SalesQuote, SalesOrder,
    SalesDelivery, CustomsDeclaration,
    SalesInvoice,
    AccountsReceivable, Collection, CollectionAllocation,
)
from app.models.tax_refund import (
    TaxRefundInputInvoice, TaxRefundDeclaration,
    TaxRefundDetail, TaxRefundProgress,
)

__all__ = [
    "BaseMixin",
    "User", "Role", "Permission", "RolePermission",
    "Material", "Product", "BomItem", "Process",
    "Department", "Employee",
    "Customer", "Supplier", "Outsourcer",
    "Warehouse", "Currency", "ExchangeRate",
    "HsCode", "TradeTerm",
    "WarehouseInventory", "StockTransaction",
    "StockCheck", "StockCheckItem",
    "PurchaseOrder", "PurchaseOrderItem",
    "PurchaseReceipt", "PurchaseReceiptItem",
    "PurchaseInvoice",
    "AccountsPayable", "Payment", "PaymentAllocation",
    "ProductionOrder", "ProductionMaterial", "ProductionProcess", "ProductionReceipt", "ProcessingInvoice", "OutsourcingOrder",
    "MaterialIssueItem", "OutsourceReceiptItem",
    "SalesQuote", "SalesOrder",
    "SalesDelivery", "CustomsDeclaration",
    "SalesInvoice",
    "AccountsReceivable", "Collection", "CollectionAllocation",
    "TaxRefundInputInvoice", "TaxRefundDeclaration",
    "TaxRefundDetail", "TaxRefundProgress",
]

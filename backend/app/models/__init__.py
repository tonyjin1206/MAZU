"""模型包 — 导入所有模型确保注册"""

from app.models.base import BaseMixin
from app.models.auth import User, Role, Permission, RolePermission
from app.models.foundation import (
    Material, Product, BomItem, Process, ProductProcess, ProductCustomer,
    Department, Employee,
    Customer, Supplier,
    Warehouse, Currency, ExchangeRate,
    HsCode, TradeTerm,
    SystemParam,
)
from app.models.inventory import (
    WarehouseInventory, StockTransaction,
    Stocktake, StocktakeItem,
    StockCheck, StockCheckItem,
    StockInOrder,
)
from app.models.purchase import (
    PurchaseOrder, PurchaseOrderItem,
    PurchaseReceipt, PurchaseReceiptItem,
    PurchaseInvoice,
    PurchaseRequisition,
    AccountsPayable, Payment, PaymentAllocation,
)
from app.models.production import (
    ProductionOrder, ProductionMaterial, ProductionProcess, ProductionReceipt, ProcessingInvoice,
    OutsourcingOrder,
    OutsourceOrder,
    OutsourceMaterial,
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
from app.models.system_config import (
    WecomConfig, BotConfig, BotConversation,
    ReminderConfig, ReminderLog, OperationLog,
)

__all__ = [
    "BaseMixin",
    "User", "Role", "Permission", "RolePermission",
    "Material", "Product", "BomItem", "Process", "ProductProcess", "ProductCustomer",
    "Department", "Employee",
    "Customer", "Supplier",
    "Warehouse", "Currency", "ExchangeRate",
    "HsCode", "TradeTerm",
    "SystemParam",
    "WarehouseInventory", "StockTransaction",
    "Stocktake", "StocktakeItem",
    "StockCheck", "StockCheckItem",
    "StockInOrder",
    "PurchaseOrder", "PurchaseOrderItem",
    "PurchaseReceipt", "PurchaseReceiptItem",
    "PurchaseInvoice", "PurchaseRequisition",
    "AccountsPayable", "Payment", "PaymentAllocation",
    "ProductionOrder", "ProductionMaterial", "ProductionProcess", "ProductionReceipt", "ProcessingInvoice",
    "OutsourcingOrder",
    "OutsourceOrder",
    "OutsourceMaterial",
    "MaterialIssueItem",
    "SalesQuote", "SalesOrder",
    "SalesDelivery", "CustomsDeclaration",
    "SalesInvoice",
    "AccountsReceivable", "Collection", "CollectionAllocation",
    "TaxRefundInputInvoice", "TaxRefundDeclaration",
    "TaxRefundDetail", "TaxRefundProgress",
    "WecomConfig", "BotConfig", "BotConversation",
    "ReminderConfig", "ReminderLog", "OperationLog",
]

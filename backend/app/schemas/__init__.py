"""Pydantic Schemas 包"""

from app.schemas.auth import (
    UserCreate, UserUpdate, UserOut,
    LoginRequest, TokenResponse,
)
from app.schemas.foundation import (
    MaterialCreate, MaterialUpdate, MaterialOut,
    ProductCreate, ProductUpdate, ProductOut,
    BomItemCreate, BomItemUpdate, BomItemOut,
    ProcessCreate, ProcessUpdate, ProcessOut,
    DepartmentCreate, DepartmentOut,
    EmployeeCreate, EmployeeOut,
    CustomerCreate, CustomerUpdate, CustomerOut,
    SupplierCreate, SupplierUpdate, SupplierOut,
    OutsourcerCreate, OutsourcerOut,
    WarehouseCreate, WarehouseOut,
    CurrencyCreate, CurrencyOut,
    ExchangeRateCreate, ExchangeRateOut,
    HsCodeCreate, HsCodeUpdate, HsCodeOut,
    TradeTermCreate, TradeTermOut,
)
from app.schemas.purchase import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderOut,
    PurchaseOrderItemCreate, PurchaseOrderItemOut,
    PurchaseReceiptCreate, PurchaseReceiptOut,
    PurchaseReceiptItemCreate, PurchaseReceiptItemOut,
    PurchaseInvoiceCreate, PurchaseInvoiceOut,
    AccountsPayableOut,
    PaymentCreate, PaymentOut,
    PaymentAllocationCreate,
)
from app.schemas.production import (
    ProductionOrderCreate, ProductionOrderUpdate, ProductionOrderOut,
    OutsourcingOrderCreate, OutsourcingOrderUpdate, OutsourcingOrderOut,
    MaterialIssueItemCreate, MaterialIssueItemOut,
    OutsourceReceiptItemCreate, OutsourceReceiptItemOut,
)
from app.schemas.sales import (
    SalesQuoteCreate, SalesQuoteOut,
    SalesOrderCreate, SalesOrderUpdate, SalesOrderOut,
    SalesDeliveryCreate, SalesDeliveryOut,
    CustomsDeclarationCreate, CustomsDeclarationUpdate, CustomsDeclarationOut,
    SalesInvoiceCreate, SalesInvoiceOut,
    AccountsReceivableOut,
    CollectionCreate, CollectionOut,
    CollectionAllocationCreate,
)
from app.schemas.tax_refund import (
    TaxRefundInputInvoiceCreate, TaxRefundInputInvoiceOut,
    TaxRefundDeclarationCreate, TaxRefundDeclarationOut,
    TaxRefundCalculationRequest, TaxRefundCalculationResult,
    TaxRefundDetailCreate, TaxRefundDetailOut,
    TaxRefundProgressCreate, TaxRefundProgressOut,
)

__all__ = [
    # auth
    "UserCreate", "UserUpdate", "UserOut", "LoginRequest", "TokenResponse",
    # foundation
    "MaterialCreate", "MaterialUpdate", "MaterialOut",
    "ProductCreate", "ProductUpdate", "ProductOut",
    "BomItemCreate", "BomItemUpdate", "BomItemOut",
    "ProcessCreate", "ProcessUpdate", "ProcessOut",
    "DepartmentCreate", "DepartmentOut",
    "EmployeeCreate", "EmployeeOut",
    "CustomerCreate", "CustomerUpdate", "CustomerOut",
    "SupplierCreate", "SupplierUpdate", "SupplierOut",
    "OutsourcerCreate", "OutsourcerOut",
    "WarehouseCreate", "WarehouseOut",
    "CurrencyCreate", "CurrencyOut",
    "ExchangeRateCreate", "ExchangeRateOut",
    "HsCodeCreate", "HsCodeUpdate", "HsCodeOut",
    "TradeTermCreate", "TradeTermOut",
    # purchase
    "PurchaseOrderCreate", "PurchaseOrderUpdate", "PurchaseOrderOut",
    "PurchaseOrderItemCreate", "PurchaseOrderItemOut",
    "PurchaseReceiptCreate", "PurchaseReceiptOut",
    "PurchaseReceiptItemCreate", "PurchaseReceiptItemOut",
    "PurchaseInvoiceCreate", "PurchaseInvoiceOut",
    "AccountsPayableOut",
    "PaymentCreate", "PaymentOut", "PaymentAllocationCreate",
    # production
    "ProductionOrderCreate", "ProductionOrderUpdate", "ProductionOrderOut",
    "OutsourcingOrderCreate", "OutsourcingOrderUpdate", "OutsourcingOrderOut",
    "MaterialIssueItemCreate", "MaterialIssueItemOut",
    "OutsourceReceiptItemCreate", "OutsourceReceiptItemOut",
    # sales
    "SalesQuoteCreate", "SalesQuoteOut",
    "SalesOrderCreate", "SalesOrderUpdate", "SalesOrderOut",
    "SalesDeliveryCreate", "SalesDeliveryOut",
    "CustomsDeclarationCreate", "CustomsDeclarationUpdate", "CustomsDeclarationOut",
    "SalesInvoiceCreate", "SalesInvoiceOut",
    "AccountsReceivableOut",
    "CollectionCreate", "CollectionOut", "CollectionAllocationCreate",
    # tax refund
    "TaxRefundInputInvoiceCreate", "TaxRefundInputInvoiceOut",
    "TaxRefundDeclarationCreate", "TaxRefundDeclarationOut",
    "TaxRefundCalculationRequest", "TaxRefundCalculationResult",
    "TaxRefundDetailCreate", "TaxRefundDetailOut",
    "TaxRefundProgressCreate", "TaxRefundProgressOut",
]

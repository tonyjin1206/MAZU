"""批次号与单据编号生成工具"""

from datetime import date, datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Type, Any


def generate_batch_no(db: Session, prefix: str = "") -> str:
    """
    生成批次号：YYYYMMDD-NNN
    同一天从 001 开始递增（使用 MAX+1 避免冲突）
    prefix: 可选前缀，如 RA-(原料) FG-(成品)
    """
    today = date.today()
    date_str = today.strftime("%Y%m%d")
    prefix_str = f"{prefix}-" if prefix else ""

    from app.models.inventory import StockTransaction

    # 使用 MAX+1 而非 COUNT+1 — 避免并发冲突和删除后编号复用
    max_batch = (
        db.query(func.max(StockTransaction.batch_no))
        .filter(
            StockTransaction.batch_no.like(f"{prefix_str}{date_str}-%"),
            func.date(StockTransaction.trans_date) == today,
        )
        .scalar()
    )

    if max_batch:
        parts = max_batch.rsplit("-", 1)
        seq = int(parts[1]) + 1
    else:
        seq = 1

    return f"{prefix_str}{date_str}-{seq:03d}"


def generate_doc_no(db: Session, prefix: str, model: Type[Any] = None,
                    field_name: str = None) -> str:
    """
    生成单据编号：前缀 + YYMMDD + NN（短格式，峰子 2026-08-01 拍板）
    如：SO-26080101（6位日期+2位序号），避免长编码

    使用 MAX+1 而非 COUNT+1，避免：
    - 并发请求同时查询到相同 count 导致编号冲突
    - 删除记录后 count 减少导致编号重复

    Args:
        db: 数据库会话
        prefix: 单据前缀（如 'SO', 'PO', 'AR', 'ST' 等）
        model: SQLAlchemy 模型类。若不传，默认使用 StockTransaction
        field_name: 要查询的字段名。若不传，基于 prefix 自动识别
    """
    today = date.today()
    date_str = today.strftime("%y%m%d")

    if model is None:
        from app.models.inventory import StockTransaction
        model = StockTransaction
        field_name = "trans_no"
    elif field_name is None:
        # 根据模型自动推断字段名
        field_name = _infer_field_name(prefix, model)

    field = getattr(model, field_name)

    # 🔴 峰子修复 2026-08-03: 先flush，让同一事务内刚add的记录对max查询可见
    # 否则循环里连续生成流水号（销售发货/采购入库/成品入库等）会得到重复编号
    # → UNIQUE constraint failed: inv_transaction.trans_no
    db.flush()

    # 查询当天最大的单据编号
    max_no = (
        db.query(func.max(field))
        .filter(field.like(f"{prefix}-{date_str}%"))
        .scalar()
    )

    if max_no:
        # 短格式单据号 = 前缀-6位日期+2位序号（无分隔符，如 SD-26080301）
        # 不能 rsplit("-")（无横杠会把整串当序号），取前缀+日期之后的数字部分
        core = max_no[len(prefix) + 1 + len(date_str):]
        seq = (int(core) + 1) if core.isdigit() else 2
    else:
        seq = 1

    return f"{prefix}-{date_str}{seq:02d}"


def _infer_field_name(prefix: str, model: Type[Any]) -> str:
    """根据单据前缀推断模型中的字段名"""
    prefix_field_map = {
        "SO": "order_no",       # SalesOrder
        "QT": "quote_no",       # SalesQuote
        "SD": "delivery_no",    # SalesDelivery
        "MO": "order_no",       # ProductionOrder
        "WO": "outsource_no",   # OutsourceOrder (委外订单)
        "IN": "stock_in_no",    # StockInOrder (成品入库)
        "MI": "issue_no",       # MaterialIssueItem
        "AR": "ar_no",          # AccountsReceivable
        "CR": "collection_no",  # Collection
        "PO": "order_no",       # PurchaseOrder
        "PR": "receipt_no",     # PurchaseReceipt
        "PM": "payment_no",     # Payment
        "AP": "payable_no",     # AccountsPayable
        "PI": "invoice_no",    # ProcessingInvoice (加工费发票)
        "FG": "receipt_no",    # ProductionReceipt (完工入库)
        "ST": "trans_no",       # StockTransaction
    }
    return prefix_field_map.get(prefix, "trans_no")

"""批次号生成工具"""

from datetime import date, datetime
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inventory import StockTransaction


def generate_batch_no(db: Session, prefix: str = "") -> str:
    """
    生成批次号：YYYYMMDD-NNN
    同一天从 001 开始递增
    prefix: 可选前缀，如 RA-(原料) FG-(成品)
    """
    today = date.today()
    date_str = today.strftime("%Y%m%d")
    prefix_str = f"{prefix}-" if prefix else ""

    # 查询当天最大的序号
    max_batch = (
        db.query(func.max(StockTransaction.batch_no))
        .filter(
            StockTransaction.batch_no.like(f"{prefix_str}{date_str}-%"),
            func.date(StockTransaction.trans_date) == today,
        )
        .scalar()
    )

    if max_batch:
        # 提取序号部分并 +1
        parts = max_batch.rsplit("-", 1)
        seq = int(parts[1]) + 1
    else:
        seq = 1

    return f"{prefix_str}{date_str}-{seq:03d}"


def generate_doc_no(db: Session, prefix: str) -> str:
    """生成单据编号：前缀 + YYYYMMDD + NNN"""
    today = date.today()
    date_str = today.strftime("%Y%m%d")
    from sqlalchemy import func
    from app.models.inventory import StockTransaction
    count = db.query(func.count(StockTransaction.id)).filter(
        StockTransaction.trans_no.like(f"{prefix}-{date_str}%")
    ).scalar() or 0
    return f"{prefix}-{date_str}-{count+1:03d}"

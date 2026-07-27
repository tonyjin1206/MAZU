"""数据库引擎与会话管理"""

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# 确保数据目录存在
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
    pool_pre_ping=True,
)

# SQLite 开启 WAL 模式 + 外键约束
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表"""
    import app.models  # noqa: F401 — 确保模型被注册
    Base.metadata.create_all(bind=engine)

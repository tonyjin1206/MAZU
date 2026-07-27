"""应用配置 — 支持从 .env 文件读取"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "Lightweight Trade Management Platform"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = True

    # 数据库
    DATA_DIR: Path = Path(os.environ.get("ERP_DATA_DIR", str(BASE_DIR / "data")))
    DATABASE_URL: str = f"sqlite:///{DATA_DIR / 'erp.db'}"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8788", "http://127.0.0.1:5173"]

    # JWT
    JWT_SECRET: str = "erp-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # 默认管理员
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# 确保 data 目录存在
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

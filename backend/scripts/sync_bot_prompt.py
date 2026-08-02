"""同步 DB 中 BotConfig.system_prompt 到最新版（与 schemas DEFAULT_SYSTEM_PROMPT 对齐）。

用法: cd backend && ./venv/bin/python scripts/sync_bot_prompt.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models.system_config import BotConfig  # noqa: E402
from app.schemas.system_config import DEFAULT_SYSTEM_PROMPT  # noqa: E402

db = SessionLocal()
try:
    configs = db.query(BotConfig).all()
    for cfg in configs:
        old_head = (cfg.system_prompt or "")[:40]
        cfg.system_prompt = DEFAULT_SYSTEM_PROMPT
        print(f"✅ config id={cfg.id} 已更新（原开头: {old_head!r}...）")
    db.commit()
    print("完成")
finally:
    db.close()

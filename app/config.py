from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env if present
load_dotenv()


class Settings(BaseModel):
    telegram_bot_token: str
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/app.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    admin_tg_ids: list[int] = []


@lru_cache()
def get_settings() -> Settings:
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    # Re-load .env to ensure vars are present when called from different contexts
    load_dotenv(override=False)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Create a .env file with TELEGRAM_BOT_TOKEN=..."
        )
    admin_str = os.getenv("ADMIN_TG_IDS", "")
    admin_ids: list[int] = []
    if admin_str:
        for part in admin_str.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                admin_ids.append(int(part))
            except ValueError:
                pass
    return Settings(telegram_bot_token=token, admin_tg_ids=admin_ids)

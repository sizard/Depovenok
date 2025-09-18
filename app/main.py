from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from .config import get_settings
from .logger import setup_logging, logger
from .db.base import setup_engine, init_db
from .handlers import setup_routers


async def main() -> None:
    settings = get_settings()

    # Logging
    setup_logging(settings.log_level)
    logger.info("Starting bot...")

    # DB
    setup_engine(settings.database_url)
    await init_db()

    # Bot + Dispatcher
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(setup_routers())

    # Start polling
    logger.info("Bot is running with long polling")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        # Graceful shutdown
        logger.info("Bot stopped")

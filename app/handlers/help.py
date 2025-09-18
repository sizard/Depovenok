from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name=__name__)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n\n"
        "/start — стартовое сообщение\n"
        "/help — помощь\n\n"
        "Также доступны кнопки и пересылка файлов."
    )

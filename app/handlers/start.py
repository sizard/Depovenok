from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from ..keyboards import main_menu_kb

router = Router(name=__name__)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот. Я умею работать с файлами и кнопками. Нажми кнопку или отправь файл.",
        reply_markup=main_menu_kb(),
    )

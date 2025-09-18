from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message

router = Router(name=__name__)


@router.message(F.text, StateFilter(None))
async def echo_text(message: Message) -> None:
    # Простое эхо на любые текстовые сообщения, не перехваченные другими хендлерами
    await message.answer(f"Эхо: {message.text}")

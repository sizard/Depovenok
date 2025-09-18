from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from ..keyboards.blocks import blocks_menu_kb

router = Router(name=__name__)


@router.message(Command("blocks"))
async def cmd_blocks(message: Message) -> None:
    # Сначала скрываем reply-клавиатуру (главное меню)
    await message.answer("Открываю раздел 'Блоки'...", reply_markup=ReplyKeyboardRemove(remove_keyboard=True))
    # Затем отправляем меню c inline-кнопками
    await message.answer("Раздел: Блоки. Выберите действие:", reply_markup=blocks_menu_kb())


@router.message(F.text.casefold() == "блоки")
async def btn_blocks(message: Message) -> None:
    await message.answer("Открываю раздел 'Блоки'...", reply_markup=ReplyKeyboardRemove(remove_keyboard=True))
    await message.answer("Раздел: Блоки. Выберите действие:", reply_markup=blocks_menu_kb())



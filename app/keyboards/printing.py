from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def print_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="print:confirm:yes")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="print:confirm:no")],
        ]
    )

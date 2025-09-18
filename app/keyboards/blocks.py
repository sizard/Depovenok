from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def blocks_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Принять", callback_data="blocks:receive")],
            [InlineKeyboardButton(text="📤 Выдать", callback_data="blocks:issue")],
            [InlineKeyboardButton(text="🛠 Ремонт", callback_data="blocks:repair")],
        ]
    )

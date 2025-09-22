from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def blocks_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Принять", callback_data="blocks:receive")],
            [InlineKeyboardButton(text="📤 Выдать", callback_data="blocks:issue")],
            [InlineKeyboardButton(text="🛠 Ремонт", callback_data="blocks:repair")],
            [InlineKeyboardButton(text="📦 Экспорт XML", callback_data="blocks:export")],
        ]
    )


def unit_card_kb(unit_id: int) -> InlineKeyboardMarkup:
    """Кнопки для карточки блока: История / Выдать / Ремонт"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 История", callback_data=f"unit:history:{unit_id}")],
            [InlineKeyboardButton(text="📤 Выдать", callback_data=f"unit:issue:{unit_id}")],
            [InlineKeyboardButton(text="🛠 Ремонт", callback_data=f"unit:repair:{unit_id}")],
            [
                InlineKeyboardButton(text="🔗 Изменить машину", callback_data=f"unit:machine:set:{unit_id}"),
                InlineKeyboardButton(text="🚫 Снять привязку", callback_data=f"unit:machine:clear:{unit_id}"),
            ],
        ]
    )


def back_to_blocks_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="blocks:menu")],
        ]
    )


def history_nav_kb(unit_id: int, page: int, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    row = []
    if has_prev:
        row.append(InlineKeyboardButton(text="◀️", callback_data=f"unit:history:{unit_id}:{page-1}"))
    row.append(InlineKeyboardButton(text=f"Стр. {page+1}", callback_data="noop"))
    if has_next:
        row.append(InlineKeyboardButton(text="▶️", callback_data=f"unit:history:{unit_id}:{page+1}"))
    # Добавим кнопку Назад отдельной строкой
    rows = [row, [InlineKeyboardButton(text="⬅️ Назад", callback_data="blocks:menu")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def export_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="На складе (без выданных)", callback_data="blocks:export:stock")],
            [InlineKeyboardButton(text="Все блоки", callback_data="blocks:export:all")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="blocks:menu")],
        ]
    )

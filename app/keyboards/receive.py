from __future__ import annotations

from typing import Iterable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def status_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Исправный", callback_data="recv:cond:ok")],
            [InlineKeyboardButton(text="❌ Не исправный", callback_data="recv:cond:bad")],
            [InlineKeyboardButton(text="🛡 Гарантийный", callback_data="recv:cond:warranty")],
            [InlineKeyboardButton(text="🧪 На проверку", callback_data="recv:cond:check")],
        ]
    )


def ra_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="РА1", callback_data="recv:ra:RA1")],
            [InlineKeyboardButton(text="РА2", callback_data="recv:ra:RA2")],
            [InlineKeyboardButton(text="РА3", callback_data="recv:ra:RA3")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="recv:ra:skip")],
        ]
    )


def skip_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⏭️ Пропустить", callback_data="recv:skip")]]
    )


def choices_kb(values: Iterable[str], prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=v, callback_data=f"{prefix}:{v}")] for v in values]
    # add manual entry option at the end
    rows.append([InlineKeyboardButton(text="✍️ Ввести вручную", callback_data=f"{prefix}:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def choices_paged_kb(values: list[str], prefix: str, page: int, page_size: int = 5) -> InlineKeyboardMarkup:
    total = len(values)
    start = max(page, 0) * page_size
    end = min(start + page_size, total)
    page = start // page_size  # normalize

    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(start, end):
        text = values[idx]
        rows.append([InlineKeyboardButton(text=text, callback_data=f"{prefix}:idx:{idx}")])

    nav_row: list[InlineKeyboardButton] = []
    if start > 0:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:page:{page-1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page+1}/{(total-1)//page_size+1}", callback_data="noop"))
    if end < total:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:page:{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="✍️ Ввести вручную", callback_data=f"{prefix}:manual")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

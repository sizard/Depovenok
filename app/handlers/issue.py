from __future__ import annotations

from typing import List, Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from sqlalchemy import select

from ..db import base as db_base
from ..db.models import Unit, User, UnitEvent
from ..keyboards.receive import choices_paged_kb, ra_kb, skip_kb
from ..config import get_settings
from ..keyboards import main_menu_kb
from ..db.base import setup_engine, init_db

router = Router(name=__name__)


class IssueStates(StatesGroup):
    number = State()
    unit_choice = State()
    destination_machine = State()
    destination_number = State()
    confirm = State()


async def ensure_db() -> None:
    if db_base.async_session is None:
        settings = get_settings()
        setup_engine(settings.database_url)
        await init_db()


@router.callback_query(F.data == "blocks:issue")
async def start_issue(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(IssueStates.number)
    await callback.message.answer("Укажите номер блока для выдачи:")


@router.message(IssueStates.number, F.text)
async def set_number(message: Message, state: FSMContext) -> None:
    number = (message.text or "").strip()
    if not number:
        await message.answer("Номер не должен быть пустым. Введите номер ещё раз:")
        return

    await ensure_db()
    items: List[tuple[int, str, str]] = []
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q = (
                select(Unit.id, Unit.name, Unit.type, Unit.status)
                .where(Unit.number == number)
                .order_by(Unit.name.asc(), Unit.type.asc())
            )
            rows = await session.execute(q)
            for r in rows.all():
                unit_id, name, type_, status = r
                label = f"{name or '-'} | {type_ or '-'} | {status}"
                items.append((unit_id, name or '-', label))

    if not items:
        await message.answer("Блоки с таким номером не найдены. Введите другой номер:")
        return

    # Сохраняем полные списки в состоянии и показываем первую страницу
    await state.update_data(unit_ids=[i[0] for i in items], unit_labels=[i[2] for i in items], unit_names=[i[1] for i in items], number=number)
    await state.set_state(IssueStates.unit_choice)
    await message.answer("Выберите блок для выдачи:", reply_markup=choices_paged_kb([i[2] for i in items], "issue:unit", page=0, page_size=5))


@router.callback_query(IssueStates.unit_choice, F.data.startswith("issue:unit:page:"))
async def unit_page(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    labels: List[str] = data.get("unit_labels", [])
    try:
        page = int((callback.data or "").split(":")[-1])
    except ValueError:
        page = 0
    await callback.message.edit_reply_markup(reply_markup=choices_paged_kb(labels, "issue:unit", page=page, page_size=5))


@router.callback_query(IssueStates.unit_choice, F.data.startswith("issue:unit:idx:"))
async def unit_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    unit_ids: List[int] = data.get("unit_ids", [])
    unit_names: List[str] = data.get("unit_names", [])
    try:
        idx = int((callback.data or "").split(":")[-1])
        unit_id = unit_ids[idx]
    except Exception:
        await callback.message.answer("Ошибка выбора. Повторите ввод номера.")
        await state.set_state(IssueStates.number)
        return

    await ensure_db()
    status_ok = False
    unit_label = unit_names[idx] if 0 <= idx < len(unit_names) else "-"
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            u = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            if u and u.status == "done":
                status_ok = True
                unit_label = f"{u.name or '-'} | {u.type or '-'} | готов"
            elif u:
                unit_label = f"{u.name or '-'} | {u.type or '-'} | {u.status}"

    if not status_ok:
        await callback.message.answer(f"Этот блок нельзя выдать: статус '{unit_label.split('|')[-1].strip()}'. Завершите ремонт.")
        await state.clear()
        return

    await state.update_data(unit_id=unit_id)
    # Сначала спросим место назначения (РА1/РА2/РА3) или пропустить
    await state.set_state(IssueStates.destination_machine)
    await callback.message.answer("Укажите место назначения (РА1/РА2/РА3) или пропустите:", reply_markup=ra_kb())


@router.callback_query(IssueStates.destination_machine, F.data.startswith("recv:ra:"))
async def issue_set_machine(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = (callback.data or "").split(":")[-1]
    if value == "skip":
        await state.update_data(dest_machine=None)
    else:
        await state.update_data(dest_machine=value)
    # Переходим к номеру машины (можно пропустить)
    await state.set_state(IssueStates.destination_number)
    await callback.message.answer("Укажите номер машины (например, 105-01) или пропустите:", reply_markup=skip_kb())


@router.callback_query(IssueStates.destination_number, F.data == "recv:skip")
async def issue_skip_machine_number(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(dest_machine_number=None)
    await ask_issue_confirm(callback, state)


@router.message(IssueStates.destination_number, F.text)
async def issue_set_machine_number(message: Message, state: FSMContext) -> None:
    num = (message.text or "").strip()
    await state.update_data(dest_machine_number=num)
    # Показать подтверждение
    await ask_issue_confirm(message, state)


async def ask_issue_confirm(target_message: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    unit_id = data.get("unit_id")
    dest_machine = data.get("dest_machine")
    dest_number = data.get("dest_machine_number")
    label = f"Назначение: {dest_machine or '—'} {dest_number or ''}".strip()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Выдать", callback_data="issue:confirm:yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="issue:confirm:no")],
    ])
    # ВАЖНО: установим состояние подтверждения, чтобы обработчики сработали
    await state.set_state(IssueStates.confirm)
    if isinstance(target_message, Message):
        await target_message.answer(f"Подтвердите выдачу. {label}", reply_markup=kb)
    else:
        await target_message.message.answer(f"Подтвердите выдачу. {label}", reply_markup=kb)


@router.callback_query(IssueStates.confirm, F.data == "issue:confirm:no")
async def issue_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Отменено")
    await state.clear()


@router.callback_query(IssueStates.confirm, F.data == "issue:confirm:yes")
async def issue_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    unit_id: Optional[int] = data.get("unit_id")
    if not isinstance(unit_id, int):
        await callback.message.answer("Ошибка состояния. Начните заново.")
        await state.clear()
        return

    await ensure_db()
    issued_at_str = None
    issued_unit = None
    issued_by = None
    dest_machine = None
    dest_number = None
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            u = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            if not u:
                await callback.message.answer("Блок не найден.")
                await state.clear()
                return
            u.status = "issued"
            # Определим выдавшего пользователя и фамилию
            by_user = None
            by_name = None
            if callback.from_user is not None:
                user = (await session.execute(select(User).where(User.tg_id == callback.from_user.id))).scalar_one_or_none()
                if user:
                    by_user = user.id
                    if user.full_name:
                        by_name = user.full_name.split()[0]
                if by_name is None:
                    # fallback к данным Telegram
                    ln = callback.from_user.last_name or ""
                    fn = callback.from_user.first_name or ""
                    by_name = (ln or fn) or None
            # Достаем назначение из state
            data = await state.get_data()
            dest_machine = data.get("dest_machine")
            dest_number = data.get("dest_machine_number")
            # Пишем событие
            evt = UnitEvent(
                unit_id=unit_id,
                event_type="issued",
                by_user_id=by_user,
                by_user_name=by_name,
                destination_machine=dest_machine,
                destination_machine_number=dest_number,
            )
            session.add(evt)
            await session.commit()
            # Подготовим данные для карточки
            issued_unit = u
            issued_by = by_name
            from datetime import datetime as _dt
            issued_at_str = _dt.now().strftime('%d-%m-%Y %H:%M')

    # Итоговая карточка
    if issued_unit is not None:
        lines = [
            "Выдача оформлена:",
            f"Название: {issued_unit.name}",
            f"Тип: {issued_unit.type}",
            f"Номер: {issued_unit.number}",
            f"Статус: issued",
            f"Куда: {dest_machine or '—'} {dest_number or ''}",
            f"Кто выдал: {issued_by or '—'}",
            f"Время: {issued_at_str or ''}",
        ]
        await callback.message.answer("\n".join(lines), reply_markup=main_menu_kb())
    else:
        await callback.message.answer("Блок выдан. Статус: issued", reply_markup=main_menu_kb())
    await state.clear()

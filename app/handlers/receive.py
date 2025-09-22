from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove

from sqlalchemy import select, func

from ..db import base as db_base
from ..db.models import Unit, User, UnitEvent
from ..keyboards.receive import status_kb, ra_kb, skip_kb, choices_kb, choices_paged_kb
from ..keyboards import main_menu_kb
from ..config import get_settings
from ..db.base import setup_engine, init_db

router = Router(name=__name__)


async def ensure_db() -> None:
    if db_base.async_session is None:
        settings = get_settings()
        setup_engine(settings.database_url)
        await init_db()


class ReceiveStates(StatesGroup):
    number = State()
    name_choice = State()
    name_manual = State()
    type_choice = State()
    type_manual = State()
    condition = State()
    machine = State()
    machine_number = State()


@router.callback_query(F.data == "blocks:receive")
async def start_receive(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(ReceiveStates.number)
    # Просим ввести номер и скрываем реплай-клавиатуру (главное меню), чтобы не мешала
    await callback.message.answer(
        "Введите номер блока:", reply_markup=ReplyKeyboardRemove(remove_keyboard=True)
    )


@router.message(ReceiveStates.number, F.text)
async def set_number(message: Message, state: FSMContext) -> None:
    number = (message.text or "").strip()
    if not number:
        await message.answer("Номер не должен быть пустым. Введите номер ещё раз:")
        return

    await state.update_data(number=number)

    # Подгружаем весь справочник названий (distinct) и листаем пагинацией
    names: list[str] = []
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q_all = select(func.distinct(Unit.name)).where(Unit.name.is_not(None)).order_by(Unit.name.asc())
            rows = (await session.execute(q_all)).scalars().all()
            names = [r for r in rows if r]

    if names:
        await state.update_data(names_all=names)
        await state.set_state(ReceiveStates.name_choice)
        await message.answer("Название блока:", reply_markup=choices_paged_kb(names, "recv:name", page=0))
    else:
        await state.set_state(ReceiveStates.name_manual)
        await message.answer("Введите название блока:")


@router.callback_query(ReceiveStates.name_choice, F.data == "recv:name:manual")
async def name_manual_switch(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ReceiveStates.name_manual)
    await callback.message.edit_text("Введите название блока:")


@router.callback_query(ReceiveStates.name_choice, F.data.startswith("recv:name:page:"))
async def name_page(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    names: list[str] = data.get("names_all", [])
    try:
        page = int((callback.data or "").split(":")[-1])
    except ValueError:
        page = 0
    await callback.message.edit_reply_markup(reply_markup=choices_paged_kb(names, "recv:name", page=page))


@router.callback_query(ReceiveStates.name_choice, F.data.startswith("recv:name:idx:"))
async def name_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    names: list[str] = data.get("names_all", [])
    try:
        idx = int((callback.data or "").split(":")[-1])
        value = names[idx]
    except Exception:
        await callback.message.answer("Ошибка выбора. Введите название вручную:")
        await state.set_state(ReceiveStates.name_manual)
        return
    await state.update_data(name=value)
    await proceed_to_type(callback.message, state)


@router.message(ReceiveStates.name_manual, F.text)
async def set_name_manual(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не должно быть пустым. Введите ещё раз:")
        return
    await state.update_data(name=name)
    await proceed_to_type(message, state)


async def proceed_to_type(target_message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    number = data.get("number")
    # Полный справочник типов
    types: list[str] = []
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q_all = select(func.distinct(Unit.type)).where(Unit.type.is_not(None)).order_by(Unit.type.asc())
            rows = (await session.execute(q_all)).scalars().all()
            types = [r for r in rows if r]

    if types:
        await state.update_data(types_all=types)
        await state.set_state(ReceiveStates.type_choice)
        await target_message.answer("Тип блока:", reply_markup=choices_paged_kb(types, "recv:type", page=0))
    else:
        await state.set_state(ReceiveStates.type_manual)
        await target_message.answer("Введите тип блока:")


@router.callback_query(ReceiveStates.type_choice, F.data == "recv:type:manual")
async def type_manual_switch(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ReceiveStates.type_manual)
    await callback.message.edit_text("Введите тип блока:")


@router.callback_query(ReceiveStates.type_choice, F.data.startswith("recv:type:page:"))
async def type_page(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    types: list[str] = data.get("types_all", [])
    try:
        page = int((callback.data or "").split(":")[-1])
    except ValueError:
        page = 0
    await callback.message.edit_reply_markup(reply_markup=choices_paged_kb(types, "recv:type", page=page))


@router.callback_query(ReceiveStates.type_choice, F.data.startswith("recv:type:idx:"))
async def type_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    types: list[str] = data.get("types_all", [])
    try:
        idx = int((callback.data or "").split(":")[-1])
        value = types[idx]
    except Exception:
        await callback.message.answer("Ошибка выбора. Введите тип вручную:")
        await state.set_state(ReceiveStates.type_manual)
        return
    await state.update_data(type=value)
    await ask_condition(callback.message, state)


@router.message(ReceiveStates.type_manual, F.text)
async def set_type_manual(message: Message, state: FSMContext) -> None:
    v = (message.text or "").strip()
    if not v:
        await message.answer("Тип не должен быть пустым. Введите ещё раз:")
        return
    await state.update_data(type=v)
    await ask_condition(message, state)


async def ask_condition(target_message: Message, state: FSMContext) -> None:
    await state.set_state(ReceiveStates.condition)
    await target_message.answer("Статус блока:", reply_markup=status_kb())


@router.callback_query(ReceiveStates.condition, F.data.startswith("recv:cond:"))
async def set_condition(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = (callback.data or "").split(":")[-1]
    mapping = {"ok": "Исправный", "bad": "Не исправный", "warranty": "Гарантийный", "check": "На проверку"}
    await state.update_data(condition=mapping.get(value, value))
    await ask_machine(callback.message, state)


async def ask_machine(target_message: Message, state: FSMContext) -> None:
    await state.set_state(ReceiveStates.machine)
    await target_message.answer("Указать машину (РА1/РА2/РА3) или пропустить:", reply_markup=ra_kb())


@router.callback_query(ReceiveStates.machine, F.data.startswith("recv:ra:"))
async def set_machine(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = (callback.data or "").split(":")[-1]
    if value == "skip":
        await state.update_data(machine=None)
    else:
        await state.update_data(machine=value)
    await ask_machine_number(callback.message, state)


async def ask_machine_number(target_message: Message, state: FSMContext) -> None:
    await state.set_state(ReceiveStates.machine_number)
    await target_message.answer("Указать номер машины (например: 105-01) или пропустить:", reply_markup=skip_kb())


@router.callback_query(ReceiveStates.machine_number, F.data == "recv:skip")
async def skip_machine_number(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(machine_number=None)
    await ask_accepted_at(callback.message, state)


@router.message(ReceiveStates.machine_number, F.text)
async def set_machine_number(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    await state.update_data(machine_number=value)
    await finish_receive(message, state)

async def finish_receive(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    number = data.get("number")
    name = data.get("name")
    type_ = data.get("type")
    condition = data.get("condition")
    machine = data.get("machine")
    machine_number = data.get("machine_number")
    accepted_at = datetime.now()

    # Определяем фамилию автоматически
    surname: Optional[str] = None
    await ensure_db()
    if message.from_user is not None and db_base.async_session is not None:
        async with db_base.async_session() as session:
            result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
            u = result.scalar_one_or_none()
            if u and u.full_name:
                parts = u.full_name.strip().split()
                if parts:
                    surname = parts[0]
    if not surname and message.from_user and message.from_user.last_name:
        surname = message.from_user.last_name
    if not surname and message.from_user and message.from_user.first_name:
        surname = message.from_user.first_name  # fallback

    await ensure_db()
    if db_base.async_session is None:
        await message.answer("База данных не инициализирована.")
        await state.clear()
        return

    async with db_base.async_session() as session:
        unit = Unit(
            number=str(number),
            name=str(name),
            type=str(type_),
            status="received",
            condition=str(condition) if condition else None,
            machine=str(machine) if machine else None,
            machine_number=str(machine_number) if machine_number else None,
            accepted_at=accepted_at,
            master_surname=surname,
        )
        session.add(unit)
        await session.commit()
        # Запишем событие 'received'
        by_user_id: int | None = None
        by_user_name: str | None = surname
        if message.from_user is not None:
            u = (await session.execute(select(User).where(User.tg_id == message.from_user.id))).scalar_one_or_none()
            if u:
                by_user_id = u.id
                if not by_user_name and u.full_name:
                    parts = u.full_name.strip().split()
                    if parts:
                        by_user_name = parts[0]
            if not by_user_name:
                ln = message.from_user.last_name or ""
                fn = message.from_user.first_name or ""
                by_user_name = (ln or fn) or None
        evt = UnitEvent(
            unit_id=unit.id,
            event_type="received",
            by_user_id=by_user_id,
            by_user_name=by_user_name,
        )
        session.add(evt)
        await session.commit()

    await message.answer(
        "Блок принят на склад:\n"
        f"Номер: {number}\n"
        f"Название: {name}\n"
        f"Тип: {type_}\n"
        f"Статус: {condition}\n"
        f"Машина: {machine or '—'}\n"
        f"Номер машины: {machine_number or '—'}\n"
        f"Дата приёмки: {accepted_at.strftime('%d-%m-%Y %H:%M')}\n"
        f"Принимал: {surname or '—'}",
        reply_markup=main_menu_kb(),
    )

    await state.clear()

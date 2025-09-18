from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from ..db.base import async_session
from ..db.models import User
from ..config import get_settings

router = Router(name=__name__)


class RegStates(StatesGroup):
    waiting_full_name = State()


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Невозможно определить пользователя.")
        return

    tg_id = message.from_user.id

    # Check if already registered
    if async_session is not None:
        async with async_session() as session:
            existing = await session.scalar(
                session.query(User).filter(User.tg_id == tg_id)  # type: ignore[attr-defined]
            )
            # SQLAlchemy 2.0 style would be select(User)... keeping simple for now
    
    # Ask full name
    await message.answer("Введите вашу Фамилию и Имя (например: Иванов Иван):")
    await state.set_state(RegStates.waiting_full_name)


@router.message(RegStates.waiting_full_name, F.text)
async def reg_set_full_name(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        await message.answer("Невозможно определить пользователя.")
        return

    full_name = (message.text or "").strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, укажите Фамилию и Имя через пробел.")
        return

    tg_id = message.from_user.id
    username = message.from_user.username

    settings = get_settings()
    role = "admin" if tg_id in settings.admin_tg_ids else "master"
    status = "active" if role == "admin" else "pending"

    if async_session is None:
        await message.answer("База данных не инициализирована.")
        await state.clear()
        return

    # Upsert user
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(tg_id=tg_id, full_name=full_name, username=username, role=role, status=status)
            session.add(user)
        else:
            user.full_name = full_name
            user.username = username
            user.role = role if user.role != "admin" else user.role
            if user.status != "active" and role == "admin":
                user.status = "active"
        await session.commit()

    if role == "admin":
        await message.answer("Вы зарегистрированы как администратор и активированы.")
    else:
        await message.answer("Заявка на регистрацию отправлена администратору. Ожидайте подтверждения.")

    await state.clear()


@router.message(Command("approve"))
async def cmd_approve(message: Message) -> None:
    if message.from_user is None:
        return

    settings = get_settings()
    if message.from_user.id not in settings.admin_tg_ids:
        await message.answer("Команда доступна только администратору.")
        return

    args = (message.text or "").split()[1:]
    if not args:
        await message.answer("Укажите tg_id пользователя: /approve 123456789")
        return

    try:
        target_tg_id = int(args[0])
    except ValueError:
        await message.answer("tg_id должен быть числом.")
        return

    if async_session is None:
        await message.answer("База данных не инициализирована.")
        return

    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == target_tg_id))
        user = result.scalar_one_or_none()
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        user.status = "active"
        await session.commit()

    await message.answer(f"Пользователь {target_tg_id} активирован.")

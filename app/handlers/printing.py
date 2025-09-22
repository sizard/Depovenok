from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from sqlalchemy import select

from ..db import base as db_base
from ..db.models import User, PrintJob, PrintEvent, Printer
from ..config import get_settings
from ..db.base import setup_engine, init_db
from ..keyboards.printing import print_confirm_kb

router = Router(name=__name__)


async def ensure_db() -> None:
    if db_base.async_session is None:
        settings = get_settings()
        setup_engine(settings.database_url)
        await init_db()


class PrintStates(StatesGroup):
    file = State()
    photo = State()
    printer = State()
    time = State()
    confirm = State()


@router.message(Command("print"))
async def start_print(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PrintStates.file)
    await message.answer(
        "Загрузите файл модели для печати (STL или 3MF). Можно переслать как документ."
    )


def _is_allowed_model(filename: str | None) -> bool:
    if not filename:
        return False
    fn = filename.lower()
    return fn.endswith(".stl") or fn.endswith(".3mf")


@router.message(PrintStates.file, F.document)
async def got_model_file(message: Message, state: FSMContext) -> None:
    doc = message.document
    if not doc or not _is_allowed_model(doc.file_name):
        await message.answer("Допустимы только файлы STL или 3MF. Отправьте корректный файл.")
        return
    await state.update_data(model_file_id=doc.file_id, model_filename=doc.file_name)
    await state.set_state(PrintStates.photo)
    await message.answer("Прикрепите фото детали (по желанию) или напишите 'пропустить'.")


@router.message(PrintStates.photo, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    # Берём самую большую версию
    ph = message.photo[-1]
    await state.update_data(photo_file_id=ph.file_id)
    await state.set_state(PrintStates.printer)
    await message.answer("Укажите название принтера (например: Prusa-MK3 или RA1).")


@router.message(PrintStates.photo, F.text.casefold() == "пропустить")
async def skip_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await state.set_state(PrintStates.printer)
    await message.answer("Укажите название принтера (например: Prusa-MK3 или RA1).")


@router.message(PrintStates.printer, F.text)
async def set_printer(message: Message, state: FSMContext) -> None:
    printer_name = (message.text or "").strip()
    await state.update_data(printer_name=printer_name)
    # Проверим, не на обслуживании ли принтер
    await ensure_db()
    warn = None
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            pr = (
                await session.execute(select(Printer).where(Printer.name == printer_name))
            ).scalar_one_or_none()
            if pr and pr.status == "maintenance":
                if pr.maintenance_until and pr.maintenance_until > datetime.utcnow():
                    until = pr.maintenance_until.strftime('%d-%m-%Y %H:%M')
                    warn = f"Внимание: принтер на обслуживании до {until}."
    await state.set_state(PrintStates.time)
    await message.answer((warn + "\n") if warn else "" + "Укажите ожидаемое время печати в минутах (например, 120).")


@router.message(PrintStates.time, F.text)
async def set_time(message: Message, state: FSMContext) -> None:
    txt = (message.text or "").strip()
    try:
        minutes = int(txt)
        if minutes <= 0:
            raise ValueError
    except Exception:
        await message.answer("Введите положительное число минут, например: 90")
        return
    await state.update_data(expected_time_min=minutes)
    # Показать подтверждение
    data = await state.get_data()
    lines = [
        "Заявка на печать:",
        f"Файл: {data.get('model_filename')}",
        f"Принтер: {data.get('printer_name')}",
        f"Ожидаемое время: {minutes} мин",
        f"Фото: {'есть' if data.get('photo_file_id') else 'нет'}",
    ]
    await state.set_state(PrintStates.confirm)
    await message.answer("\n".join(lines), reply_markup=print_confirm_kb())


@router.callback_query(PrintStates.confirm, F.data == "print:confirm:no")
async def print_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Отменено")
    await state.clear()


@router.callback_query(PrintStates.confirm, F.data == "print:confirm:yes")
async def print_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    model_file_id: Optional[str] = data.get("model_file_id")
    model_filename: Optional[str] = data.get("model_filename")
    photo_file_id: Optional[str] = data.get("photo_file_id")
    printer_name: Optional[str] = data.get("printer_name")
    expected_time_min: Optional[int] = data.get("expected_time_min")
    if not model_file_id:
        await callback.message.answer("Файл модели не найден. Начните заново: /print")
        await state.clear()
        return

    await ensure_db()
    job_id = None
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            by_user_id = None
            if callback.from_user is not None:
                u = (
                    await session.execute(select(User).where(User.tg_id == callback.from_user.id))
                ).scalar_one_or_none()
                if u:
                    by_user_id = u.id
            job = PrintJob(
                user_id=by_user_id,
                printer_name=printer_name,
                file_id=model_file_id,
                filename=model_filename,
                photo_file_id=photo_file_id,
                expected_time_min=expected_time_min,
                status="requested",
            )
            session.add(job)
            await session.commit()
            # событие
            evt = PrintEvent(
                job_id=job.id,
                event_type="requested",
                by_user_id=by_user_id,
                comment=f"Заявка создана. Время: {expected_time_min} мин. Принтер: {printer_name}",
            )
            session.add(evt)
            await session.commit()
            job_id = job.id
    if job_id:
        await callback.message.answer(
            f"Заявка на печать создана (ID: {job_id}). Статус: requested."
        )
    await state.clear()


@router.message(Command("printers"))
async def list_printers(message: Message) -> None:
    await ensure_db()
    lines = ["Принтеры:"]
    items = []
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            rows = await session.execute(select(Printer))
            items = rows.scalars().all()
    if not items:
        lines.append("— нет записей. Добавьте принтер через /add_printer <имя>.")
    else:
        for p in items:
            maint = (
                f", обслуживание до {p.maintenance_until.strftime('%d-%m-%Y %H:%M')}"
                if p.status == "maintenance" and p.maintenance_until
                else ""
            )
            lines.append(f"• {p.name}: {p.status}{maint}")
    await message.answer("\n".join(lines))


@router.message(Command("add_printer"))
async def add_printer(message: Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /add_printer <имя>")
        return
    name = args[1].strip()
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            exists = (
                await session.execute(select(Printer).where(Printer.name == name))
            ).scalar_one_or_none()
            if exists:
                await message.answer("Такой принтер уже есть")
                return
            p = Printer(name=name)
            session.add(p)
            await session.commit()
    await message.answer("Принтер добавлен")


@router.message(Command("maint"))
async def set_maintenance(message: Message) -> None:
    # /maint <имя> <минут>
    args = (message.text or "").split()
    if len(args) < 3:
        await message.answer("Использование: /maint <имя> <минут>")
        return
    name = args[1]
    try:
        mins = int(args[2])
        if mins <= 0:
            raise ValueError
    except Exception:
        await message.answer("Минуты должны быть положительным числом")
        return
    until = datetime.utcnow() + timedelta(minutes=mins)
    await ensure_db()
    ok = False
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            p = (
                await session.execute(select(Printer).where(Printer.name == name))
            ).scalar_one_or_none()
            if not p:
                await message.answer("Принтер не найден")
                return
            p.status = "maintenance"
            p.maintenance_until = until
            await session.commit()
            ok = True
    if ok:
        await message.answer(
            f"Принтер {name} переведён в обслуживание до {until.strftime('%d-%m-%Y %H:%M')}"
        )

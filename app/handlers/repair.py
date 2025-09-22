from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from sqlalchemy import select

from ..db import base as db_base
from ..db.models import Unit, Repair, User, Attachment, UnitEvent
from ..keyboards.receive import choices_paged_kb
from ..config import get_settings
from ..db.base import setup_engine, init_db

router = Router(name=__name__)


class RepairStates(StatesGroup):
    number = State()
    unit_choice = State()
    fault = State()
    summary = State()


async def ensure_db() -> None:
    if db_base.async_session is None:
        settings = get_settings()
        setup_engine(settings.database_url)
        await init_db()


@router.callback_query(F.data == "blocks:repair")
async def start_repair(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(RepairStates.number)
    await callback.message.answer("Укажите номер блока для ремонта:")


@router.message(RepairStates.number, F.text)
async def set_number(message: Message, state: FSMContext) -> None:
    number = (message.text or "").strip()
    if not number:
        await message.answer("Номер не должен быть пустым. Введите номер ещё раз:")
        return

    await ensure_db()
    items: List[tuple[int, str]] = []
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q = (
                select(Unit.id, Unit.name, Unit.type)
                .where(Unit.number == number)
                .order_by(Unit.name.asc(), Unit.type.asc())
            )
            rows = await session.execute(q)
            for r in rows.all():
                unit_id, name, type_ = r
                label = f"{name or '-'} | {type_ or '-'}"
                items.append((unit_id, label))

    if not items:
        await message.answer("Блоки с таким номером не найдены. Введите другой номер:")
        return

    # Сохраняем полные списки в состоянии и показываем первую страницу
    await state.update_data(unit_ids=[i[0] for i in items], unit_labels=[i[1] for i in items], number=number)
    await state.set_state(RepairStates.unit_choice)
    await message.answer("Выберите блок:", reply_markup=choices_paged_kb([i[1] for i in items], "repair:unit", page=0, page_size=5))


@router.callback_query(RepairStates.unit_choice, F.data.startswith("repair:unit:page:"))
async def unit_page(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    labels: List[str] = data.get("unit_labels", [])
    # page number is last token
    try:
        page = int((callback.data or "").split(":")[-1])
    except ValueError:
        page = 0
    await callback.message.edit_reply_markup(reply_markup=choices_paged_kb(labels, "repair:unit", page=page, page_size=5))


@router.callback_query(RepairStates.unit_choice, F.data.startswith("repair:unit:idx:"))
async def unit_pick(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    unit_ids: List[int] = data.get("unit_ids", [])
    try:
        idx = int((callback.data or "").split(":")[-1])
        unit_id = unit_ids[idx]
    except Exception:
        await callback.message.answer("Ошибка выбора. Повторите ввод номера.")
        await state.set_state(RepairStates.number)
        return

    await state.update_data(unit_id=unit_id)
    # Зафиксируем событие начала ремонта
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            by_user_id = None
            by_user_name = None
            if callback.from_user is not None:
                u = (await session.execute(select(User).where(User.tg_id == callback.from_user.id))).scalar_one_or_none()
                if u:
                    by_user_id = u.id
                    if u.full_name:
                        by_user_name = (u.full_name.strip().split() or [None])[0]
                if by_user_name is None:
                    ln = callback.from_user.last_name or ""
                    fn = callback.from_user.first_name or ""
                    by_user_name = (ln or fn) or None
            evt = UnitEvent(
                unit_id=unit_id,
                event_type="repair_open",
                by_user_id=by_user_id,
                by_user_name=by_user_name,
            )
            session.add(evt)
            await session.commit()

    # Переходим к вводу неисправности
    await state.set_state(RepairStates.fault)
    await callback.message.answer("Опишите неисправность (кратко):")


# Убрали шаг ввода даты: дата будет выставлена автоматически


@router.callback_query(F.data.startswith("unit:repair:"))
async def start_repair_from_card(callback: CallbackQuery, state: FSMContext) -> None:
    """Старт ремонта из карточки блока по unit_id."""
    await callback.answer()
    try:
        unit_id = int((callback.data or "").split(":")[-1])
    except Exception:
        await callback.message.answer("Некорректный идентификатор блока")
        return
    await state.clear()
    await state.update_data(unit_id=unit_id)
    # Зафиксируем событие начала ремонта
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            by_user_id = None
            by_user_name = None
            if callback.from_user is not None:
                u = (await session.execute(select(User).where(User.tg_id == callback.from_user.id))).scalar_one_or_none()
                if u:
                    by_user_id = u.id
                    if u.full_name:
                        by_user_name = (u.full_name.strip().split() or [None])[0]
                if by_user_name is None:
                    ln = callback.from_user.last_name or ""
                    fn = callback.from_user.first_name or ""
                    by_user_name = (ln or fn) or None
            evt = UnitEvent(
                unit_id=unit_id,
                event_type="repair_open",
                by_user_id=by_user_id,
                by_user_name=by_user_name,
            )
            session.add(evt)
            await session.commit()
    # Переходим к вводу неисправности
    await state.set_state(RepairStates.fault)
    await callback.message.answer("Опишите неисправность (кратко):")


@router.message(RepairStates.fault, F.text)
async def set_fault(message: Message, state: FSMContext) -> None:
    fault = (message.text or "").strip()
    await state.update_data(fault=fault)
    await state.set_state(RepairStates.summary)
    await message.answer("Опишите выполненные работы/замены (кратко):")


@router.message(RepairStates.summary, F.text)
async def finish_repair(message: Message, state: FSMContext) -> None:
    summary = (message.text or "").strip()
    data = await state.get_data()
    unit_id = data.get("unit_id")
    fault: Optional[str] = data.get("fault")

    if not unit_id or not isinstance(unit_id, int):
        await message.answer("Ошибка состояния. Начните заново.")
        await state.clear()
        return

    await ensure_db()
    by_user_id: Optional[int] = None
    by_user_name: Optional[str] = None
    if db_base.async_session is not None and message.from_user is not None:
        async with db_base.async_session() as session:
            # определить пользователя
            u = (await session.execute(select(User).where(User.tg_id == message.from_user.id))).scalar_one_or_none()
            if u:
                by_user_id = u.id
                if u.full_name:
                    by_user_name = (u.full_name.strip().split() or [None])[0]
            if by_user_name is None:
                ln = message.from_user.last_name or ""
                fn = message.from_user.first_name or ""
                by_user_name = (ln or fn) or None
            # создать запись о ремонте и обновить статус блока
            closed = datetime.now()
            rep = Repair(
                unit_id=unit_id,
                opened_at=datetime.now(),
                closed_at=closed,
                status="done",
                summary=(f"Неисправность: {fault}. Работы: {summary}" if fault else summary) or None,
                by_user_id=by_user_id,
            )
            session.add(rep)
            # обновить статус блока
            unit = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            if unit:
                unit.status = "done"
            # Запишем событие о завершении ремонта
            evt = UnitEvent(
                unit_id=unit_id,
                event_type="repair_close",
                by_user_id=by_user_id,
                by_user_name=by_user_name,
                comment=(f"Неисправность: {fault}. Работы: {summary}" if fault else (summary or None)),
            )
            session.add(evt)
            await session.commit()
            # Сгенерировать QR и отправить картинку
            if unit:
                # Текст для QR
                qr_payload = f"{unit.number};{unit.name};{closed.strftime('%d-%m-%Y %H:%M')}"
                # Базовый QR
                qr_img = qrcode.make(qr_payload).convert("RGB")
                # Подпись внутри изображения под QR
                caption_text = f"{unit.name or ''} — {unit.number or ''}"
                # Подготовим полотно: добавим место под текст (около 60-100px)
                padding = 16
                text_area_h = 80
                canvas = Image.new(
                    "RGB",
                    (qr_img.width + padding * 2, qr_img.height + padding * 2 + text_area_h),
                    color=(255, 255, 255),
                )
                canvas.paste(qr_img, (padding, padding))
                draw = ImageDraw.Draw(canvas)
                # Пытаемся загрузить TTF-шрифт с поддержкой кириллицы
                font = None
                font_candidates = [
                    # Распространённые шрифты Windows
                    r"C:\\Windows\\Fonts\\arial.ttf",
                    r"C:\\Windows\\Fonts\\arialuni.ttf",
                    r"C:\\Windows\\Fonts\\segoeui.ttf",
                    r"C:\\Windows\\Fonts\\tahoma.ttf",
                ]
                for fp in font_candidates:
                    try:
                        if Path(fp).exists():
                            font = ImageFont.truetype(fp, size=16)
                            break
                    except Exception:
                        continue
                if font is None:
                    # Последний шанс — встроенный (может не покрывать кириллицу)
                    try:
                        font = ImageFont.load_default()
                    except Exception:
                        font = None
                # Центрируем текст
                text_y = qr_img.height + padding + (text_area_h // 2)
                # Первая строка: payload (мелко)
                payload_bbox = draw.textbbox((0, 0), qr_payload, font=font)
                payload_w = payload_bbox[2] - payload_bbox[0]
                payload_h = payload_bbox[3] - payload_bbox[1]
                draw.text(
                    ((canvas.width - payload_w) // 2, text_y - payload_h - 4),
                    qr_payload,
                    fill=(0, 0, 0),
                    font=font,
                )
                # Вторая строка: подпись (название — номер)
                cap_bbox = draw.textbbox((0, 0), caption_text, font=font)
                cap_w = cap_bbox[2] - cap_bbox[0]
                cap_h = cap_bbox[3] - cap_bbox[1]
                draw.text(
                    ((canvas.width - cap_w) // 2, text_y + 4),
                    caption_text,
                    fill=(0, 0, 0),
                    font=font,
                )

                # Сохраняем в файл и также отправляем как фото
                qr_dir = Path("data/qr")
                qr_dir.mkdir(parents=True, exist_ok=True)
                filename = f"repair_qr_{rep.id}.png"
                file_path = qr_dir / filename
                canvas.save(file_path, format="PNG")

                # Отправляем в Telegram
                with file_path.open("rb") as f:
                    photo = BufferedInputFile(f.read(), filename=filename)
                sent = await message.answer_photo(photo=photo)

                # Сохраняем вложение в БД (file_id и filename)
                tg_file_id = None
                if sent.photo:
                    tg_file_id = sent.photo[-1].file_id
                attach = Attachment(
                    entity_type="repair",
                    entity_id=rep.id,
                    file_id=tg_file_id,
                    filename=str(file_path.name),
                )
                session.add(attach)
                await session.commit()

    await message.answer("Ремонт сохранён и завершён. Статус блока: готов.")
    await state.clear()

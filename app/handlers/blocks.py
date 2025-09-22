from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import select

from ..db import base as db_base
from ..db.models import Unit, UnitEvent
from ..keyboards.blocks import blocks_menu_kb, unit_card_kb, back_to_blocks_kb, history_nav_kb, export_menu_kb
from ..config import get_settings
from ..db.base import setup_engine, init_db
from ..keyboards.receive import ra_kb, skip_kb

router = Router(name=__name__)


class MachineStates(StatesGroup):
    set_machine = State()
    set_number = State()


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


async def ensure_db() -> None:
    if db_base.async_session is None:
        settings = get_settings()
        setup_engine(settings.database_url)
        await init_db()


@router.callback_query(F.data == "blocks:menu")
async def back_to_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("Раздел: Блоки. Выберите действие:", reply_markup=blocks_menu_kb())


@router.callback_query(F.data == "blocks:export")
async def cb_blocks_export(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer("Экспорт XML:", reply_markup=export_menu_kb())


@router.callback_query(F.data == "blocks:export:stock")
async def cb_blocks_export_stock(callback: CallbackQuery) -> None:
    await callback.answer()
    await cmd_export_xml(callback.message)


@router.callback_query(F.data == "blocks:export:all")
async def cb_blocks_export_all(callback: CallbackQuery) -> None:
    await callback.answer()
    await cmd_export_xml_all(callback.message)


@router.message(Command("unit"))
async def cmd_unit(message: Message) -> None:
    """Показ карточки блока по номеру. Использование: /unit 123"""
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /unit <номер>. Пример: /unit 123")
        return
    number = args[1].strip()

    await ensure_db()
    items: list[tuple[int, str]] = []
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q = select(Unit.id, Unit.name, Unit.type, Unit.status).where(Unit.number == number).order_by(Unit.name.asc())
            rows = await session.execute(q)
            for r in rows.all():
                uid, name, type_, status = r
                label = f"{name or '-'} | {type_ or '-'} | {status}"
                items.append((uid, label))

    if not items:
        await message.answer("Блоки с таким номером не найдены")
        return

    if len(items) == 1:
        await show_unit_card(message, items[0][0])
        return

    # Список выбора
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"unit:card:{uid}")]
        for uid, label in items[:10]
    ])
    await message.answer("Выберите блок:", reply_markup=kb)


@router.callback_query(F.data.startswith("unit:card:"))
async def cb_unit_card(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        unit_id = int((callback.data or "").split(":")[-1])
    except Exception:
        return
    await show_unit_card(callback, unit_id)


async def show_unit_card(target: Message | CallbackQuery, unit_id: int) -> None:
    await ensure_db()
    unit = None
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            unit = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
    if not unit:
        if isinstance(target, Message):
            await target.answer("Блок не найден")
        else:
            await target.message.answer("Блок не найден")
        return
    machine_text = (f"{unit.machine} {unit.machine_number or ''}".strip()) if unit.machine else "Без привязки"
    text = (
        "Карточка блока:\n"
        f"Название: {unit.name}\n"
        f"Тип: {unit.type}\n"
        f"Номер: {unit.number}\n"
        f"Статус: {unit.status}\n"
        f"Машина: {machine_text}\n"
    )
    kb = unit_card_kb(unit.id)
    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb)
    else:
        await target.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("unit:history:"))
async def cb_unit_history(callback: CallbackQuery) -> None:
    await callback.answer()
    # поддержка форматов: unit:history:<unit_id> и unit:history:<unit_id>:<page>
    tokens = (callback.data or "").split(":")
    unit_id = None
    page = 0
    try:
        if len(tokens) >= 3:
            unit_id = int(tokens[2])
        if len(tokens) >= 4:
            page = int(tokens[3])
    except Exception:
        unit_id = None
    if unit_id is None:
        return
    await ensure_db()
    events: list[UnitEvent] = []
    unit = None
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            unit = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            q = select(UnitEvent).where(UnitEvent.unit_id == unit_id).order_by(UnitEvent.timestamp.desc())
            rows = await session.execute(q)
            events = rows.scalars().all()
    if not unit:
        await callback.message.answer("Блок не найден")
        return
    if not events:
        await callback.message.answer("История пуста", reply_markup=back_to_blocks_kb())
        return
    # пагинация: по 8 записей на страницу
    page_size = 8
    total = len(events)
    start = page * page_size
    end = start + page_size
    chunk = events[start:end]
    has_prev = page > 0
    has_next = end < total

    # удобочитаемые метки и иконки типов
    labels = {
        "received": "Принят",
        "repair_open": "Ремонт начат",
        "repair_close": "Ремонт завершён",
        "issued": "Выдан",
    }
    icons = {
        "received": "📥",
        "repair_open": "🛠",
        "repair_close": "✅",
        "issued": "📤",
    }
    lines = [f"История блока {unit.name} — {unit.number} (записи {start+1}-{min(end, total)} из {total}):"]
    for e in chunk:
        ts = e.timestamp.strftime('%d-%m-%Y %H:%M') if e.timestamp else ''
        who = e.by_user_name or '—'
        ev = labels.get(e.event_type, e.event_type)
        icon = icons.get(e.event_type, '•')
        extra = ''
        if e.event_type == 'issued':
            if e.destination_machine:
                extra = f" → {e.destination_machine} {e.destination_machine_number or ''}"
            else:
                extra = " → без привязки"
        elif e.event_type == 'received':
            if unit.machine:
                extra = f" (машина: {unit.machine} {unit.machine_number or ''})"
        # Комментарий (например, из repair_close)
        comment = f"\n   ↳ {e.comment}" if e.comment else ''
        lines.append(f"{icon} {ts}: {ev} (кем: {who}){extra}{comment}")
    kb = history_nav_kb(unit.id, page, has_prev, has_next)
    await callback.message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(F.data.startswith("unit:machine:clear:"))
async def cb_unit_machine_clear(callback: CallbackQuery) -> None:
    await callback.answer()
    try:
        unit_id = int((callback.data or "").split(":")[-1])
    except Exception:
        return
    await ensure_db()
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            u = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            if not u:
                await callback.message.answer("Блок не найден")
                return
            u.machine = None
            u.machine_number = None
            await session.commit()
    await callback.message.answer("Привязка к машине снята.")
    await show_unit_card(callback, unit_id)


@router.callback_query(F.data.startswith("unit:machine:set:"))
async def cb_unit_machine_set(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    try:
        unit_id = int((callback.data or "").split(":")[-1])
    except Exception:
        return
    await state.clear()
    await state.update_data(edit_unit_id=unit_id)
    await state.set_state(MachineStates.set_machine)
    await callback.message.answer("Укажите машину (РА1/РА2/РА3) или пропустите:", reply_markup=ra_kb())


@router.callback_query(MachineStates.set_machine, F.data.startswith("recv:ra:"))
async def cb_unit_machine_pick_ra(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    value = (callback.data or "").split(":")[-1]
    if value == "skip":
        await state.update_data(new_machine=None)
    else:
        await state.update_data(new_machine=value)
    await state.set_state(MachineStates.set_number)
    await callback.message.answer("Укажите номер машины (например, 105-01) или пропустите:", reply_markup=skip_kb())


@router.callback_query(MachineStates.set_number, F.data == "recv:skip")
async def cb_unit_machine_skip_number(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(new_machine_number=None)
    await finalize_machine_update(callback, state)


@router.message(MachineStates.set_number, F.text)
async def cb_unit_machine_set_number_text(message: Message, state: FSMContext) -> None:
    num = (message.text or "").strip()
    await state.update_data(new_machine_number=num)
    await finalize_machine_update(message, state)


async def finalize_machine_update(target: Message | CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    unit_id = data.get("edit_unit_id")
    new_machine = data.get("new_machine")
    new_number = data.get("new_machine_number")
    await ensure_db()
    if db_base.async_session is not None and isinstance(unit_id, int):
        async with db_base.async_session() as session:
            u = (await session.execute(select(Unit).where(Unit.id == unit_id))).scalar_one_or_none()
            if not u:
                if isinstance(target, Message):
                    await target.answer("Блок не найден")
                else:
                    await target.message.answer("Блок не найден")
                await state.clear()
                return
            u.machine = new_machine
            u.machine_number = new_number
            await session.commit()
    msg = "Машина обновлена." if new_machine else "Привязка к машине снята."
    if isinstance(target, Message):
        await target.answer(msg)
    else:
        await target.message.answer(msg)
    await show_unit_card(target, unit_id)
    await state.clear()


# ===== XML экспорт списка блоков =====


def _unit_to_xml_element(unit: Unit, meta: dict | None = None):
    # Ленивая локальная зависимость, чтобы не тянуть её наверх
    import xml.etree.ElementTree as ET
    el = ET.Element("unit")
    ET.SubElement(el, "id").text = str(unit.id)
    ET.SubElement(el, "number").text = unit.number or ""
    ET.SubElement(el, "name").text = unit.name or ""
    ET.SubElement(el, "type").text = unit.type or ""
    ET.SubElement(el, "status").text = unit.status or ""
    ET.SubElement(el, "machine").text = unit.machine or ""
    ET.SubElement(el, "machine_number").text = unit.machine_number or ""
    ET.SubElement(el, "accepted_at").text = unit.accepted_at.strftime('%Y-%m-%dT%H:%M:%S') if unit.accepted_at else ""
    ET.SubElement(el, "created_at").text = unit.created_at.strftime('%Y-%m-%dT%H:%M:%S') if unit.created_at else ""
    # Доп. сведения из событий
    if meta:
        ET.SubElement(el, "received_by").text = meta.get("received_by", "") or ""
        ET.SubElement(el, "issued_by").text = meta.get("issued_by", "") or ""
        ET.SubElement(el, "last_repair_at").text = meta.get("last_repair_at", "") or ""
        ET.SubElement(el, "last_repair_summary").text = meta.get("last_repair_summary", "") or ""
    return el


async def _export_units_xml(message: Message, include_all: bool = False) -> None:
    await ensure_db()
    units: list[Unit] = []
    if db_base.async_session is not None:
        async with db_base.async_session() as session:
            q = select(Unit)
            if not include_all:
                # На складе: всё, что не выдано
                from sqlalchemy import not_, literal
                q = q.where(Unit.status != "issued")
            q = q.order_by(Unit.number.asc(), Unit.name.asc())
            rows = await session.execute(q)
            units = rows.scalars().all()

            # Подтянем события для доп. полей: received_by, issued_by, last_repair
            unit_ids = [u.id for u in units]
            metas: dict[int, dict] = {uid: {} for uid in unit_ids}
            if unit_ids:
                from sqlalchemy import or_, desc
                ev_q = (
                    select(UnitEvent)
                    .where(UnitEvent.unit_id.in_(unit_ids))
                    .where(UnitEvent.event_type.in_(["received", "issued", "repair_close"]))
                    .order_by(UnitEvent.unit_id.asc(), UnitEvent.timestamp.desc())
                )
                ev_rows = await session.execute(ev_q)
                events = ev_rows.scalars().all()
                # Пробежим и заберём первые подходящие по типу для каждого unit
                seen_received = set()
                seen_issued = set()
                seen_repair = set()
                for e in events:
                    uid = e.unit_id
                    if e.event_type == "received" and uid not in seen_received:
                        metas.setdefault(uid, {})["received_by"] = e.by_user_name or ""
                        seen_received.add(uid)
                    elif e.event_type == "issued" and uid not in seen_issued:
                        metas.setdefault(uid, {})["issued_by"] = e.by_user_name or ""
                        seen_issued.add(uid)
                    elif e.event_type == "repair_close" and uid not in seen_repair:
                        metas.setdefault(uid, {})["last_repair_at"] = (
                            e.timestamp.strftime('%Y-%m-%dT%H:%M:%S') if e.timestamp else ""
                        )
                        metas[uid]["last_repair_summary"] = e.comment or ""
                        seen_repair.add(uid)

    # Построим XML
    import xml.etree.ElementTree as ET
    root = ET.Element("units")
    root.set("generated_at", message.date.strftime('%Y-%m-%dT%H:%M:%S') if message.date else "")
    root.set("scope", "all" if include_all else "in_stock")
    # Если метаданные собрали
    try:
        metas
    except NameError:
        metas = {}
    for u in units:
        root.append(_unit_to_xml_element(u, metas.get(u.id)))
    tree = ET.ElementTree(root)

    # Сериализация в память
    import io
    bio = io.BytesIO()
    tree.write(bio, encoding="utf-8", xml_declaration=True)
    data = bio.getvalue()
    filename = "units_all.xml" if include_all else "units_in_stock.xml"
    await message.answer_document(BufferedInputFile(data, filename=filename), caption=("Все блоки" if include_all else "Блоки на складе"))


@router.message(Command("export_xml"))
async def cmd_export_xml(message: Message) -> None:
    """Экспорт XML списка блоков на складе (все, кроме выданных)."""
    await _export_units_xml(message, include_all=False)


@router.message(Command("export_xml_all"))
async def cmd_export_xml_all(message: Message) -> None:
    """Экспорт XML полного списка блоков (все статусы)."""
    await _export_units_xml(message, include_all=True)


from __future__ import annotations

from pathlib import Path

from aiogram import Router, F
from aiogram.types import Message
from aiogram import Bot

from ..services import FileService
from ..db.models import Document
from ..db.base import async_session

router = Router(name=__name__)
file_service = FileService()


@router.message(F.document)
async def handle_document(message: Message, bot: Bot) -> None:
    doc = message.document
    assert doc is not None

    # Определяем имя файла
    filename = doc.file_name or f"document_{doc.file_id}.bin"
    target_path: Path = file_service.base_dir / filename

    # Скачиваем файл напрямую в целевой путь
    await bot.download(doc, destination=target_path)

    # Сохраняем метаданные в БД
    if async_session is not None:
        async with async_session() as session:
            session.add(
                Document(
                    user_id=message.from_user.id if message.from_user else 0,
                    file_id=doc.file_id,
                    filename=filename,
                )
            )
            await session.commit()

    await message.answer(f"Файл сохранён: {filename}")


@router.message(F.photo)
async def handle_photo(message: Message, bot: Bot) -> None:
    # Берём фото максимального размера
    photo = message.photo[-1]
    filename = f"photo_{photo.file_id}.jpg"
    target_path: Path = file_service.base_dir / filename

    await bot.download(photo, destination=target_path)

    if async_session is not None:
        async with async_session() as session:
            session.add(
                Document(
                    user_id=message.from_user.id if message.from_user else 0,
                    file_id=photo.file_id,
                    filename=filename,
                )
            )
            await session.commit()

    await message.answer(f"Фото сохранено: {filename}")

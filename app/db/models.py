from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(index=True, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="master")  # master | admin
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | active | blocked
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), index=True)  # 'unit' | 'repair' | 'action'
    entity_id: Mapped[int] = mapped_column(index=True)
    file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Telegram file_id
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # local filename or original
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())


class Repair(Base):
    __tablename__ = "repairs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(index=True)
    opened_at: Mapped[datetime] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="done")  # open/in_progress/done
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # краткое описание работ/замен
    by_user_id: Mapped[int | None] = mapped_column(nullable=True)


class UnitEvent(Base):
    __tablename__ = "unit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)  # received | issued | repair_open | repair_close
    by_user_id: Mapped[int | None] = mapped_column(nullable=True)
    by_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destination_machine: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # RA1/RA2/RA3
    destination_machine_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 105-01
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())
    comment: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(index=True)
    file_id: Mapped[str] = mapped_column(String(255))  # Telegram file_id
    filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    number: Mapped[str] = mapped_column(String(64), index=True)  # не уникален, могут быть буквы
    name: Mapped[str] = mapped_column(String(255))  # Название блока (БУД и т.п.)
    type: Mapped[str] = mapped_column(String(255))  # Тип: 750-05.01
    status: Mapped[str] = mapped_column(String(32), index=True, default="received")  # received/in_repair/done/issued + Исправный/Неисправный/Гарантийный как атрибут при приёмке
    condition: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Исправный | Не исправный | Гарантийный
    machine: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # РА1 | РА2 | РА3
    machine_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 105-01, 113-02 и т.п.
    accepted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # Дата приёмки
    master_surname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Фамилия принимающего
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, server_default=func.now())

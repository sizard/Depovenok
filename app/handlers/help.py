from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name=__name__)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Справка по командам:\n\n"
        "• /start — стартовое сообщение и главное меню.\n"
        "• /help — эта справка.\n\n"
        "Управление блоками:\n"
        "• /blocks — открыть раздел 'Блоки' с кнопками (Принять, Выдать, Ремонт).\n"
        "• /unit <номер> — показать карточку блока по номеру (если несколько — будет выбор).\n\n"
        "Регистрация пользователей:\n"
        "• /register — отправить ФИО для регистрации.\n"
        "• /approve <tg_id> — (админ) активировать пользователя.\n\n"
        "3D-печать:\n"
        "• /print — создать заявку на печать (STL/3MF, фото, принтер, время печати).\n"
        "• /printers — список принтеров и статус обслуживания.\n"
        "• /add_printer <имя> — добавить принтер.\n"
        "• /maint <имя> <минут> — перевести принтер в обслуживание на N минут.\n\n"
        "Экспорт:\n"
        "• /export_xml — экспорт XML списка блоков на складе (без выданных).\n"
        "• /export_xml_all — экспорт XML всех блоков.\n\n"
        "Подсказки:\n"
        "• Отправляйте документы/фото — бот их сохранит.\n"
        "• Раздел 'Блоки' поддерживает историю событий, быстрые действия и экспорт XML.\n"
    )

# Telegram Bot (aiogram 3, async SQLAlchemy)

Стек: Python 3.11+, aiogram v3, SQLAlchemy (async, SQLite), Loguru, python-dotenv.
Запуск локально через long-polling.

## Структура проекта

```
telegram-bot/
├─ app/
│  ├─ __init__.py
│  ├─ main.py                 # Точка входа: python -m app.main
│  ├─ config.py               # Загрузка .env и настройки
│  ├─ logger.py               # Настройка логирования (loguru)
│  ├─ keyboards/              # Клавиатуры (Reply/Inline)
│  │  ├─ __init__.py
│  │  └─ main_menu.py
│  ├─ handlers/               # Хендлеры
│  │  ├─ __init__.py          # Регистрация роутеров
│  │  ├─ start.py             # /start
│  │  ├─ help.py              # /help
│  │  ├─ files.py             # загрузка документов и фото, сохранение
│  │  └─ echo.py              # эхо на текст
│  ├─ services/               # Бизнес-логика, сервисы
│  │  ├─ __init__.py
│  │  └─ files.py             # сохранение/чтение файлов
│  └─ db/
│     ├─ __init__.py
│     ├─ base.py              # движок и сессии SQLAlchemy async
│     └─ models.py            # модели (Document)
├─ requirements.txt
├─ env.example                # шаблон переменных окружения
└─ .gitignore
```

Слои:
- keyboards: Только сборка клавиатур (Reply/Inline) — никакой логики
- handlers: Принимают апдейты, обращаются к сервисам/БД, возвращают ответы
- services: Прикладная логика (работа с файлами, API и т.д.)
- db: Инициализация и модели SQLAlchemy

## Подготовка окружения (Windows, PowerShell)

1) Скопируйте `env.example` в `.env` и заполните токен:

```
TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
DATABASE_URL=sqlite+aiosqlite:///data/app.db
LOG_LEVEL=INFO
```

2) Создайте и активируйте виртуальное окружение:

```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3) Установите зависимости:

```
pip install --upgrade pip
pip install -r requirements.txt
```

4) Запустите бота:

```
python -m app.main
```

Бот будет работать через long-polling. В Telegram отправьте сообщение вашему боту.

## Где добавлять кнопки и хендлеры

- Новые клавиатуры: `app/keyboards/` (создайте новый файл и экспортируйте фабрику клавиатуры)
- Новые хендлеры: `app/handlers/` (новый модуль с `router = Router()`, затем подключить в `app/handlers/__init__.py` через `include_router`)
- Новые сервисы: `app/services/`
- Новые модели БД: `app/db/models.py` (после изменений таблицы будут созданы автоматически при старте)

## Дальнейшие шаги

- Добавить Inline-кнопки и callback-хендлеры
- Реализовать список файлов пользователя и выдачу по кнопке
- Добавить обработку исключений/мидлвари для логирования апдейтов
- При необходимости подключить полноценную БД (Postgres) и деплой

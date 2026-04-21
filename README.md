# WebFace - ComfyUI Web Interface

Веб-интерфейс для генерации изображений и видео через ComfyUI.

## Описание

WebFace — это Flask-приложение для работы с ComfyUI, предоставляющее:

- Генерацию изображений из текста (Text-to-Image)
- Генерацию видео из текста (Text-to-Video)
- Редактирование изображений AI
- Систему токенов и балансов пользователей
- Публичные и пользовательские галереи
- Пресеты генераций
- Telegram бота для администрирования
- API документацию (Swagger)

## Требования

- Python 3.10+
- ComfyUI (запущенный локально или удалённо)

## Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/TagirovAlex/WebFace.git
cd WebFace
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Скопируйте и настройте .env:
```bash
copy .env.example .env
# Отредактируйте .env
```

5. Создайте базу данных и админа:
```bash
python app.py
# При первом запуске создастся база данных
python create_admin.py  # Создать админа
```

6. Запустите:
```bash
python app.py
```

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| SECRET_KEY | Секретный ключ | auto-generated |
| COMFY_URL | URL ComfyUI | http://127.0.0.1:8188 |
| DATABASE_URL | База данных | sqlite:///webface.db |
| FLASK_ENV | Режим | development |
| TELEGRAM_BOT_TOKEN | Токен бота | - |
| TELEGRAM_ADMIN_CHAT_ID | Chat ID админа | - |

### Запуск ComfyUI

Убедитесь что ComfyUI запущен и доступен по COMFY_URL.

## Особенности

### Создание генераций
- Text-to-Image: `/` — главная страница
- Text-to-Video: `/` — выберите тип "Видео"
- Image-to-Image: `/` — загрузите изображения

### API
- `/apidocs` — Swagger документация
- `/api/generate-image` — POST генерация изображений
- `/api/generate-video` — POST генерация видео
- `/api/edit-images` — POST редактирование
- `/api/history` — история пользователя
- `/api/presets` — управление пресетами

### Галереи
- `/gallery` — публичная галерея
- `/user/<username>/gallery` — галерея пользователя
- `/gallery/<id>` — конкретная генерация

### Telegram бот
```bash
python telegram_bot.py
```

Команды: /stats, /users, /last, /user <id>, /add_tokens, /gens, /toggle_admin

## Структура проекта

```
WebFace/
├── app.py              # Основное приложение
├── config.py          # Конфигурация
├── models.py          # Модели БД
├── telegram_bot.py    # Telegram бот
├── create_admin.py   # Создание админа
���── migrate_db.py    # Миграция БД
├── requirements.txt  # Зависимости
├── modules/         # Генерационные модули
├── templates/      # HTML шаблоны
├── static/         # CSS/JS
├── uploads/        # Загруженные файлы
└── results/       # Результаты
```

## Безопасность

- CSRF защита
- Rate limiting
- Валидация файлов
- Хэширование паролей
- Защита от path traversal

## Используемые библиотеки, ПО и ссылки

### Ядро приложения

- [Flask](https://flask.palletsprojects.com/) — BSD-3-Clause
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) — BSD-3-Clause
- [SQLAlchemy](https://www.sqlalchemy.org/) — MIT
- [Flask-Login](https://flask-login.readthedocs.io/) — MIT
- [Flask-Bcrypt](https://flask-bcrypt.readthedocs.io/) — MIT
- [Flask-WTF](https://flask-wtf.readthedocs.io/) — BSD
- [WTForms](https://wtforms.readthedocs.io/) — BSD
- [Flask-Limiter](https://flask-limiter.readthedocs.io/) — MIT
- [Werkzeug](https://werkzeug.palletsprojects.com/) — MIT
- [Pillow](https://pillow.readthedocs.io/) — MIT
- [python-dotenv](https://github.com/theskumar/python-dotenv) — BSD-3-Clause
- [requests](https://requests.readthedocs.io/) — Apache-2.0

### Интеграции

- [aiogram](https://aiogram.dev/) — MIT
- [Flasgger](https://flaskgger.readthedocs.io/) — MIT

### Runtime / Инфраструктура

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — AGPL-3.0
- [SQLite](https://sqlite.org/) — Public Domain

### Инструменты безопасности (рекомендуемые)

- [pip-audit](https://github.com/pypa/pip-audit) — Apache-2.0
- [Bandit](https://bandit.readthedocs.io/) — Apache-2.0

## Лицензия

MIT License - см. [LICENSE](LICENSE)

## Автор

[TagirovAlex](https://github.com/TagirovAlex)

## Ссылки

- [Репозиторий](https://github.com/TagirovAlex/WebFace)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
- [Документация ComfyUI API](https://docs.comfy.org/)
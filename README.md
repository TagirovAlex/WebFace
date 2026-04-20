# WebFace - Веб-интерфейс для ComfyUI

Простой и удобный веб-интерфейс для работы с ComfyUI по сети.

## 📋 Описание

WebFace — это веб-приложение на Flask, предоставляющее удобный интерфейс для генерации изображений и видео с использованием ComfyUI. Приложение поддерживает:

- 🎨 Генерацию изображений из текста (Text-to-Image)
- 🎬 Генерацию видео из текста (Text-to-Video)  
- ✏️ Редактирование изображений с помощью AI
- 👥 Систему пользователей с ролями
- 📊 Историю генераций

## 🛠️ Технологический стек

### Backend
| Библиотека | Версия | Назначение |
|------------|--------|------------|
| Flask | 3.0.0 | Основной веб-фреймворк |
| Flask-SQLAlchemy | 3.1.1 | ORM для работы с базой данных |
| Flask-Login | 0.6.3 | Управление сессиями пользователей |
| Flask-Bcrypt | 1.0.1 | Хэширование паролей |
| Pillow | 10.2.0 | Обработка изображений |
| Requests | 2.31.0 | HTTP клиент для ComfyUI API |
| python-dotenv | 1.0.0 | Загрузка переменных окружения |
| Werkzeug | 3.0.1 | WSGI утилиты |

### Frontend
- HTML5 / CSS3
- Vanilla JavaScript
- Jinja2 Templates

### База данных
- SQLite (по умолчанию)
- Поддержка PostgreSQL/MySQL через переменные окружения

## 📁 Структура проекта

```
WebFace/
├── app.py              # Основное Flask приложение
├── config.py           # Конфигурация приложения
├── models.py           # SQLAlchemy модели
├── create_admin.py     # Утилита для управления пользователями
├── migrate_db.py        # Миграция базы данных v1->v2
├── requirements.txt    # Python зависимости
├── setup.bat           # Скрипт установки для Windows
├── .env.example        # Пример файла окружения
├── modules/            # Модульная система
│   ├── __init__.py
│   ├── text_to_image/
│   ├── text_to_video/
│   ├── image_edit/
│   └── image_edit_multi/
├── static/
│   ├── css/            # Стили
│   └── js/             # Клиентский JavaScript
├── templates\
│   ├── admin\
│   │   ├── dashboard.html      # Дашборд генераций
│   │   ├── generation_detail.html
│   │   ├── generations.html
│   │   ├── users.html
│   │   ├── user_detail.html
│   │   ├── generation_types.html
│   │   └── tokens.html
│   ├── base.html       # Базовый шаблон
│   ├── history.html    # История генераций
│   ├── index.html     # Главная страница
│   ├── profile.html   # Настройки пользователя
│   ├── login.html     # Страница входа
│   └── register.html # Страница регистрации
├── uploads/           # Загруженные изображения
└── results/         # Результаты генерации
```
WebFace/
├── app.py              # Основное Flask приложение
├── config.py           # Конфигурация приложения
├── models.py           # SQLAlchemy модели (User, Generation)
├── create_admin.py     # Утилита для управления пользователями
├── fix_admin.py        # Утилита для исправления админа
├── requirements.txt    # Python зависимости
├── setup.bat           # Скрипт установки для Windows
├── .env.example        # Пример файла окружения
├── static/
│   ├── css/           		# Стили
│   └── js/
│       └── main.js    		# Клиентский JavaScript
├── templates\
│   ├── admin\
│   │   ├── dashboard.html				#Дашбоард генераций
│   │   ├── generation_detail.html		#Детали генерации
│   │   ├── generations.html			#список генераций
│   │   └── users.html					#управление пользователем
│   ├── base.html			# Базовый шаблон
│   ├── history.html		# История генераций
│   ├── index.html			# Главная страница
│   ├── login.html			# Страница входа
│   └── register.html		# Страница регистрации
├── uploads/           		# Загруженные изображения
└── results/           		# Результаты генерации
```

## 🚀 Установка

### Требования
- Python 3.10+
- ComfyUI (запущенный на указанном в настройках адресе)

### Шаги установки

1. Клонируйте репозиторий:
```bash
git clone https://github.com/TagirovAlex/WebFace.git
cd WebFace
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env файл
```

5. Создайте администратора:
```bash
python create_admin.py
```

6. Запустите приложение:
```bash
python app.py
```

## ⚙️ Конфигурация

### Переменные окружения (.env)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| SECRET_KEY | Секретный ключ Flask | ⚠️ Обязательно изменить! |
| COMFY_URL | URL ComfyUI сервера | http://127.0.0.1:8188 |
| DATABASE_URL | URL базы данных | sqlite:///comfyui.db |
| MAX_IMAGES_PER_GENERATION | Макс. изображений за раз | 3 |
| MAX_IMAGE_SIZE_MB | Макс. размер файла (МБ) | 10 |
| MAX_VIDEO_DURATION | Макс. длительность видео (сек) | 15 |
| MAX_IMAGE_DIMENSION | Макс. размер стороны (px) | 1280 |
| FLASK_DEBUG | Режим отладки | False |



## 📝 Лицензия

MIT License

## 👤 Автор

[TagirovAlex](https://github.com/TagirovAlex)

---

---

## 🆕 v2.0 Release

### Новые возможности
- **Система токенов** - баланс пользователей, транзакции, ценообразование
- **Модульная система** - подключаемые генерационные модули
- **Приоритеты пользователей** - Admin/High/Normal/Low
- **Скрытые генерации** - возможность скрыть генерации от пользователя

### Миграция базы данных
```bash
python migrate_db.py --backup
```

### Структура модулей
```
modules/
├── __init__.py           # BaseModule, ModuleRegistry
├── text_to_image/       # WAN 2.2 генерация изображений
├── text_to_video/       # WAN 2.2 генерация видео
├── image_edit/          # Редактирование одного изображения
└── image_edit_multi/   # Редактирование нескольких изображений
```

*Отчёт о безопасности сгенерирован автоматически*

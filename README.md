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
├── models.py           # SQLAlchemy модели (User, Generation)
├── create_admin.py     # Утилита для управления пользователями
├── fix_admin.py        # Утилита для исправления админа
├── requirements.txt    # Python зависимости
├── setup.bat           # Скрипт установки для Windows
├── .env.example        # Пример файла окружения
├── static/
│   ├── css/           # Стили
│   └── js/
│       └── main.js    # Клиентский JavaScript
├── templates/
│   ├── base.html      # Базовый шаблон
│   ├── index.html     # Главная страница
│   ├── login.html     # Страница входа
│   ├── register.html  # Страница регистрации
│   ├── history.html   # История генераций
│   └── admin/         # Админ-панель
├── uploads/           # Загруженные изображения
└── results/           # Результаты генерации
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

## 🔒 Отчёт о безопасности

### Обнаруженные уязвимости

#### 🔴 CRITICAL (1)
| ID | Уязвимость | Описание | Расположение |
|----|------------|----------|--------------|
| VULN-001 | Небезопасный SECRET_KEY | Жёстко закодированный fallback-ключ 'dev-secret-key-change-in-production' | config.py |

**Рекомендация:** Убрать fallback-значение. Приложение должно падать при отсутствии SECRET_KEY в production. Использовать `secrets.token_hex(32)` для генерации ключа.

#### 🟠 HIGH (3)
| ID | Уязвимость | Описание | Расположение |
|----|------------|----------|--------------|
| VULN-002 | Отсутствие CSRF защиты | Формы отправляются без CSRF токенов | app.py, templates/*.html |
| VULN-003 | SQL Injection риски | Необходим аудит ORM запросов с пользовательским вводом | app.py, create_admin.py |
| VULN-004 | Недостаточная валидация файлов | Проверка только по расширению, без проверки содержимого | app.py |

**Рекомендации:**
- Установить `flask-wtf` и использовать `CSRFProtect(app)`
- Использовать `python-magic` для проверки MIME-типа файлов
- Добавить антивирусное сканирование загружаемых файлов

#### 🟡 MEDIUM (4)
| ID | Уязвимость | Описание | Расположение |
|----|------------|----------|--------------|
| VULN-005 | Отсутствие Rate Limiting | Возможны brute-force атаки на логин | app.py |
| VULN-006 | Нет HTTP заголовков безопасности | Отсутствует CSP, X-Frame-Options, HSTS | app.py |
| VULN-007 | Размер поля пароля | 255 символов может быть недостаточно для Argon2 | models.py |
| VULN-008 | Path Traversal риски | Недостаточная проверка путей файлов | app.py |

**Рекомендации:**
- Установить `flask-limiter` с ограничением 5 попыток логина в минуту
- Установить `flask-talisman` для HTTP заголовков безопасности
- Увеличить размер поля password_hash до 512 символов
- Добавить проверку `os.path.realpath()` для валидации путей

#### 🔵 LOW (2)
| ID | Уязвимость | Описание | Расположение |
|----|------------|----------|--------------|
| VULN-009 | Debug информация в логах | print() в production может раскрыть информацию | app.py |
| VULN-010 | Слабая политика паролей | Минимум 6 символов недостаточно | create_admin.py, app.py |

**Рекомендации:**
- Использовать модуль `logging` с уровнем WARNING в production
- Минимум 12 символов, требовать сложность, проверять по базе HaveIBeenPwned

#### ⚪ INFO (2)
| ID | Уязвимость | Описание | Расположение |
|----|------------|----------|--------------|
| VULN-011 | SQLite в production | Не подходит для высокой нагрузки | config.py |
| VULN-012 | Нет сброса пароля | Нет механизма "Забыли пароль?" | app.py |

### Рекомендуемые пакеты безопасности

```bash
pip install flask-wtf flask-limiter flask-talisman python-magic
```

### Пример улучшенной конфигурации безопасности

```python
# security.py
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

def init_security(app):
    # CSRF защита
    csrf = CSRFProtect(app)
    
    # Rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # HTTP заголовки безопасности
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: blob:",
    }
    Talisman(app, content_security_policy=csp, force_https=False)
    
    return csrf, limiter
```

## 📝 Лицензия

MIT License

## 👤 Автор

[TagirovAlex](https://github.com/TagirovAlex)

---

⚠️ **Внимание**: Перед использованием в production обязательно устраните все выявленные уязвимости безопасности!

---

*Отчёт о безопасности сгенерирован автоматически*

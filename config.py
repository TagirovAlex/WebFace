"""
Configuration for ComfyUI Web Interface

SECURITY PATCHED VERSION
"""

import os
import secrets
from datetime import timedelta

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _load_or_create_secret_key():
    """Загрузка или создание SECRET_KEY с сохранением в файл"""
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key

    secret_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.flask_secret')

    if os.path.exists(secret_file):
        try:
            with open(secret_file, 'r') as f:
                saved_key = f.read().strip()
            if saved_key and len(saved_key) >= 32:
                return saved_key
        except (IOError, OSError):
            pass

    new_key = secrets.token_hex(32)

    try:
        with open(secret_file, 'w') as f:
            f.write(new_key)
        os.chmod(secret_file, 0o600)
    except (IOError, OSError):
        import warnings
        warnings.warn(
            "Cannot save SECRET_KEY to file. Key will be regenerated on restart. "
            "Set SECRET_KEY environment variable for production!",
            RuntimeWarning
        )

    return new_key


class Config:
    """Конфигурация приложения"""

    # ==================== SECURITY ====================

    # КРИТИЧНО: SECRET_KEY должен быть уникальным и секретным!
    # Загружается из файла .flask_secret или переменной окружения
    SECRET_KEY = _load_or_create_secret_key()

    # Дополнительная проверка безопасности ключа
    if len(SECRET_KEY) < 32:
        raise ValueError("SECRET_KEY must be at least 32 characters long!")
    
    # ==================== SESSION SECURITY ====================
    
    # Защита сессии
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True  # Запрет доступа к cookie из JavaScript
    SESSION_COOKIE_SAMESITE = 'Lax'  # Защита от CSRF
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # WTF CSRF защита
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 час
    WTF_CSRF_SSL_STRICT = os.environ.get('WTF_CSRF_SSL_STRICT', 'False').lower() == 'true'
    
    # ==================== DATABASE ====================
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///webface.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # ==================== COMFYUI ====================

    COMFY_URL = os.environ.get('COMFY_URL', 'http://127.0.0.1:8188')
    WORKFLOWS_DIR = os.environ.get('WORKFLOWS_DIR', 'workflows')

    # Timeout settings (in seconds)
    COMFY_TIMEOUT_IMAGE = int(os.environ.get('COMFY_TIMEOUT_IMAGE', '300'))   # 5 min default
    COMFY_TIMEOUT_VIDEO = int(os.environ.get('COMFY_TIMEOUT_VIDEO', '900'))   # 15 min default
    COMFY_TIMEOUT_EDIT = int(os.environ.get('COMFY_TIMEOUT_EDIT', '600'))     # 10 min default
    COMFY_TIMEOUT_MAX = int(os.environ.get('COMFY_TIMEOUT_MAX', '1800'))       # 30 min max

    # ==================== FILE UPLOADS ====================
    
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
    RESULTS_FOLDER = os.environ.get('RESULTS_FOLDER', 'results')
    
    # Безопасные расширения файлов
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Лимиты
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB макс размер запроса
    MAX_IMAGE_SIZE_MB = int(os.environ.get('MAX_IMAGE_SIZE_MB', '16'))
    MAX_IMAGE_DIMENSION = int(os.environ.get('MAX_IMAGE_DIMENSION', '1280'))
    MAX_IMAGES_PER_GENERATION = int(os.environ.get('MAX_IMAGES_PER_GENERATION', '4'))
    MAX_VIDEO_DURATION = int(os.environ.get('MAX_VIDEO_DURATION', '10'))
    
    # ==================== RATE LIMITING ====================
    
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_HEADERS_ENABLED = True
    
    # ==================== MODELS ====================
    
    MODELS = {
        'wan22': {
            'name': 'WAN 2.2',
            'description': 'Основная модель для генерации изображений',
            'type': 'image'
        },
        'wan22_video': {
            'name': 'WAN 2.2 Video',
            'description': 'Модель для генерации видео',
            'type': 'video'
        },
        'qwen_single': {
            'name': 'Qwen Single Image',
            'description': 'Редактирование одного изображения',
            'type': 'edit'
        },
        'qwen_multi': {
            'name': 'Qwen Multi Image',
            'description': 'Редактирование нескольких изображений',
            'type': 'edit'
        }
    }


class DevelopmentConfig(Config):
    """Конфигурация для разработки"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Конфигурация для продакшена"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True
    
    # В продакшене SECRET_KEY ОБЯЗАТЕЛЕН
    @classmethod
    def init_app(cls, app):
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError(
                "SECRET_KEY environment variable is required in production! "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )


class TestingConfig(Config):
    """Конфигурация для тестирования"""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Выбор конфигурации по окружению
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Получить конфигурацию для текущего окружения"""
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])

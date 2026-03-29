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


class Config:
    """Конфигурация приложения"""
    
    # ==================== SECURITY ====================
    
    # КРИТИЧНО: SECRET_KEY должен быть уникальным и секретным!
    # Генерируется автоматически если не задан в переменных окружения
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # В production ОБЯЗАТЕЛЬНО задавать через переменную окружения!
        import warnings
        warnings.warn(
            "SECRET_KEY not set! Using auto-generated key. "
            "Set SECRET_KEY environment variable for production!",
            RuntimeWarning
        )
        SECRET_KEY = secrets.token_hex(32)
    
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

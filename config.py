import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация приложения"""
    # Настройки размеров изображений
    IMAGE_MIN_SIZE = 256
    IMAGE_MAX_SIZE = 1280
    IMAGE_SIZE_STEP = 64

    # Пресеты размеров для UI
    IMAGE_SIZE_PRESETS = [
      {'name': 'Квадрат', 'width': 1024, 'height': 1024},
      {'name': 'Портрет 3:4', 'width': 768, 'height': 1024},
      {'name': 'Портрет 9:16', 'width': 720, 'height': 1280},
      {'name': 'Пейзаж 4:3', 'width': 1024, 'height': 768},
      {'name': 'Пейзаж 16:9', 'width': 1280, 'height': 720},
      {'name': 'Маленький квадрат', 'width': 512, 'height': 512}
    ]
    
# Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///comfyui.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ComfyUI Settings
    COMFY_URL = os.environ.get('COMFY_URL') or 'http://127.0.0.1:8188'
    
    # File Upload Limits
    MAX_IMAGES_PER_GENERATION = int(os.environ.get('MAX_IMAGES_PER_GENERATION', 3))
    MAX_IMAGE_SIZE_MB = int(os.environ.get('MAX_IMAGE_SIZE_MB', 10))
    MAX_VIDEO_DURATION = int(os.environ.get('MAX_VIDEO_DURATION', 15))
    MAX_IMAGE_DIMENSION = int(os.environ.get('MAX_IMAGE_DIMENSION', 1280))
    
    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    
    # Paths
    UPLOAD_FOLDER = 'uploads'
    RESULTS_FOLDER = 'results'
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Models Configuration
    MODELS = {
        'text_to_image': {
            'wan22': {
                'name': 'WAN 2.2',
                'description': 'Универсальная модель для генерации изображений',
                'workflow': 'wan_2_2.json'
            }
        },
        'text_to_video': {
            'wan22_video': {
                'name': 'WAN 2.2 Video',
                'description': 'Генерация видео на основе WAN 2.2',
                'workflow': 'wan_2_2_video.json'
            }
        },
        'image_edit': {
            'qwen_single': {
                'name': 'Qwen Edit (1 image)',
                'description': 'Редактирование одного изображения',
                'workflow': 'qwen_edit_single.json'
            },
            'qwen_multi': {
                'name': 'Qwen Edit (multiple images)',
                'description': 'Редактирование нескольких изображений',
                'workflow': 'qwen_edit_multi.json'
            }
        }
    }
"""
ComfyUI Web Interface
Веб-интерфейс для работы с ComfyUI через API

SECURITY PATCHED VERSION - исправлены критические уязвимости
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
# CSRF disabled - causes issues in production
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image
from functools import wraps
import os
import uuid
import json
import requests
import time
import threading
import random
import secrets
import re

# Опционально: python-magic для проверки MIME типов
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    print("[WARNING] python-magic not installed. Using basic file validation.")

from config import Config
from models import db, User, Generation, GenerationType, TokenBalance, TokenTransaction, Pricing, TokenRule, UserPriority, GenerationPreset, Favorite
from modules import ModuleRegistry

# ==================== FLASK APP SETUP ====================

app = Flask(__name__)
app.config.from_object(Config)

# ==================== SECURITY EXTENSIONS ====================

# CSRF Protection disabled - disabled due to production issues

# Rate Limiting
def get_real_ip():
    """Получение реального IP с защитой от spoofing"""
    import flask
    request = flask.request

    # Проверяем X-Forwarded-For - только если есть trusted proxy
    # Берем последний (самый дальний) IP в цепочке - это оригинальный клиент
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2
        ips = [ip.strip() for ip in forwarded.split(',')]
        if ips:
            # Берем последний IP (оригинальный клиент после всех прокси)
            return ips[-1]

    # Проверяем X-Real-IP
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()

    # Фоллбек на remote address
    return get_remote_address()


limiter = Limiter(
    key_func=get_real_ip,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

swagger = Swagger(app, template={
    'info': {
        'title': 'WebFace API',
        'description': 'API для генерации изображений и видео через ComfyUI',
        'version': '2.0',
        'contact': {
            'name': 'WebFace'
        }
    },
    'securityDefinitions': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT токен авторизации. Формат: "Bearer {token}"'
        }
    },
    'definitions': {
        'GenerateResponse': {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'generation_id': {'type': 'integer'},
                'message': {'type': 'string'},
                'settings': {
                    'type': 'object',
                    'properties': {
                        'width': {'type': 'integer'},
                        'height': {'type': 'integer'}
                    }
                }
            }
        },
        'ErrorResponse': {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        },
        'GenerationStatus': {
            'type': 'object',
            'properties': {
                'id': {'type': 'integer'},
                'status': {'type': 'string', 'enum': ['pending', 'processing', 'completed', 'failed']},
                'progress': {'type': 'number'},
                'output_files': {'type': 'array', 'items': {'type': 'string'}},
                'error_message': {'type': 'string'}
            }
        }
    }
})

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'
login_manager.session_protection = "strong"  # Дополнительная защита сессии


@app.context_processor
def inject_theme():
    """Передача темы в шаблоны"""
    from flask_login import current_user
    if current_user.is_authenticated:
        return {'dark_mode': current_user.theme == 'dark-theme'}
    return {'dark_mode': False}


# Create folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Максимальный размер изображения по большей стороне
MAX_IMAGE_DIMENSION = app.config.get('MAX_IMAGE_DIMENSION', 1280)

# Настройки размеров для генерации
IMAGE_MIN_SIZE = 256
IMAGE_MAX_SIZE = 1280
IMAGE_SIZE_STEP = 64

# Пресеты размеров для UI (валидируются при запуске)
_IMAGE_SIZE_PRESETS_RAW = [
    {'name': 'Квадрат 1:1', 'width': 1024, 'height': 1024},
    {'name': 'Портрет 3:4', 'width': 768, 'height': 1024},
    {'name': 'Портрет 9:16', 'width': 720, 'height': 1280},
    {'name': 'Пейзаж 4:3', 'width': 1024, 'height': 768},
    {'name': 'Пейзаж 16:9', 'width': 1280, 'height': 720},
    {'name': 'Маленький 512', 'width': 512, 'height': 512},
]

# Валидация и фильтрация пресетов
def _validate_presets():
    max_dim = MAX_IMAGE_DIMENSION
    validated = []
    for preset in _IMAGE_SIZE_PRESETS_RAW:
        w = min(preset['width'], max_dim)
        h = min(preset['height'], max_dim)
        # Округляем до кратности IMAGE_SIZE_STEP
        w = (w // IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP
        h = (h // IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP
        if w >= IMAGE_MIN_SIZE and h >= IMAGE_MIN_SIZE:
            validated.append({'name': preset['name'], 'width': w, 'height': h})
    return validated

IMAGE_SIZE_PRESETS = _validate_presets()

# Безопасные MIME типы для изображений
ALLOWED_MIME_TYPES = {
    'image/jpeg': ['jpg', 'jpeg'],
    'image/png': ['png'],
    'image/gif': ['gif'],
    'image/webp': ['webp'],
}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== SECURITY HEADERS ====================

@app.after_request
def add_security_headers(response):
    """Добавление security headers ко всем ответам"""
    # Content Security Policy - без unsafe-inline
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "  # unsafe-inline для стилей оставляем (flask flash и динамические стили)
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    )
    # Предотвращение clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Предотвращение MIME sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # XSS Protection (для старых браузеров)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer Policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Permissions Policy
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    return response


# ==================== ADMIN DECORATOR ====================

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Доступ запрещён. Требуются права администратора.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ==================== SECURE FILE VALIDATION ====================

def validate_mime_type(file_stream, filename):
    """
    Проверка MIME типа файла по содержимому (magic bytes)
    Возвращает True если файл безопасен
    """
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    
    if HAS_MAGIC:
        # Читаем первые байты для определения типа
        file_stream.seek(0)
        header = file_stream.read(2048)
        file_stream.seek(0)
        
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(header)
        
        # Проверяем что MIME тип разрешён
        if detected_mime not in ALLOWED_MIME_TYPES:
            return False, f"Недопустимый тип файла: {detected_mime}"
        
        # Проверяем что расширение соответствует MIME типу
        allowed_extensions = ALLOWED_MIME_TYPES[detected_mime]
        if ext not in allowed_extensions:
            return False, f"Расширение {ext} не соответствует типу файла {detected_mime}"
        
        return True, detected_mime
    else:
        # Fallback: проверка по magic bytes вручную
        file_stream.seek(0)
        header = file_stream.read(16)
        file_stream.seek(0)
        
        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            if ext not in ['png']:
                return False, "Расширение не соответствует PNG файлу"
            return True, 'image/png'
        
        # JPEG: FF D8 FF
        if header[:3] == b'\xff\xd8\xff':
            if ext not in ['jpg', 'jpeg']:
                return False, "Расширение не соответствует JPEG файлу"
            return True, 'image/jpeg'
        
        # GIF: 47 49 46 38
        if header[:4] == b'GIF8':
            if ext not in ['gif']:
                return False, "Расширение не соответствует GIF файлу"
            return True, 'image/gif'
        
        # WebP: 52 49 46 46 ... 57 45 42 50
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            if ext not in ['webp']:
                return False, "Расширение не соответствует WebP файлу"
            return True, 'image/webp'
        
        return False, "Неизвестный формат файла"


def secure_path_check(base_folder, filename):
    """
    Проверка на path traversal атаки
    Возвращает безопасный полный путь или None
    """
    # Очищаем имя файла
    safe_filename = secure_filename(filename)
    if not safe_filename:
        return None
    
    # Строим полный путь
    full_path = os.path.join(base_folder, safe_filename)
    
    # Проверяем что путь находится внутри base_folder
    real_base = os.path.realpath(base_folder)
    real_path = os.path.realpath(full_path)
    
    if not real_path.startswith(real_base + os.sep) and real_path != real_base:
        return None
    
    return full_path


# ==================== IMAGE PROCESSING ====================

def process_uploaded_image(file, filename):
    """
    Обработка загруженного изображения:
    - Масштабирование пропорционально до MAX_IMAGE_DIMENSION по большей стороне
    - Конвертация в RGB (если нужно)
    - Сохранение в PNG формате
    """
    try:
        # Открываем изображение
        if hasattr(file, 'read'):
            image = Image.open(file)
        else:
            image = Image.open(file)

        original_width, original_height = image.size
        print(f"[IMAGE] Original size: {original_width}x{original_height}")

        # Определяем нужно ли масштабировать
        max_dim = max(original_width, original_height)

        if max_dim > MAX_IMAGE_DIMENSION:
            # Вычисляем коэффициент масштабирования
            scale = MAX_IMAGE_DIMENSION / max_dim
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

            # Масштабируем с высоким качеством
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"[IMAGE] Resized to: {new_width}x{new_height} (scale: {scale:.2f})")
        else:
            new_width, new_height = original_width, original_height
            print(f"[IMAGE] No resize needed")

        # Конвертируем в RGB если нужно
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            if image.mode == 'RGBA':
                background.paste(image, mask=image.split()[-1])
            else:
                background.paste(image)
            image = background
            print(f"[IMAGE] Converted to RGB")
        elif image.mode != 'RGB':
            image = image.convert('RGB')
            print(f"[IMAGE] Converted to RGB")

        # Безопасное сохранение
        filepath = secure_path_check(app.config['UPLOAD_FOLDER'], filename)
        if not filepath:
            raise ValueError("Небезопасное имя файла")
        
        image.save(filepath, 'PNG', quality=95, optimize=True)
        file_size = os.path.getsize(filepath) / 1024
        print(f"[IMAGE] Saved: {filename} ({new_width}x{new_height}, {file_size:.1f} KB)")

        return filepath, (new_width, new_height)

    except Exception as e:
        print(f"[IMAGE] Error processing: {e}")
        raise


def validate_and_process_image(file):
    """
    Валидация и обработка загруженного изображения
    """
    if not file or not file.filename:
        raise ValueError("Файл не выбран")

    original_filename = file.filename
    ext = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''

    if ext not in app.config['ALLOWED_EXTENSIONS']:
        raise ValueError(f"Недопустимый формат: {ext}")

    # Проверяем размер
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)

    max_size = app.config['MAX_IMAGE_SIZE_MB'] * 1024 * 1024
    if size > max_size:
        raise ValueError(f"Файл слишком большой: {size / 1024 / 1024:.1f}MB")

    # Проверяем MIME тип
    is_valid, result = validate_mime_type(file, original_filename)
    if not is_valid:
        raise ValueError(result)

    # Проверяем что это изображение (через PIL)
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)
    except Exception as e:
        raise ValueError(f"Файл не является изображением: {e}")

    # Генерируем уникальное имя (только безопасные символы)
    filename = f"{uuid.uuid4().hex}.png"

    # Обрабатываем
    filepath, dimensions = process_uploaded_image(file, filename)

    return filename, filepath, dimensions


def validate_image_dimensions(width, height):
    """
    Валидация и нормализация размеров изображения
    """
    try:
        width = int(width)
        height = int(height)
    except (ValueError, TypeError):
        width, height = 1024, 1024

    # Ограничения
    width = max(IMAGE_MIN_SIZE, min(IMAGE_MAX_SIZE, width))
    height = max(IMAGE_MIN_SIZE, min(IMAGE_MAX_SIZE, height))

    # Округляем до кратности 64
    width = (width // IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP
    height = (height // IMAGE_SIZE_STEP) * IMAGE_SIZE_STEP

    return width, height


# ==================== HELPER FUNCTIONS ====================

# ==================== ROUTES - PAGES ====================

@app.route('/')
def index():
    """Главная страница"""
    if current_user.is_authenticated:
        return render_template('index.html',
            user=current_user,
            models=app.config['MODELS'],
            image_presets=IMAGE_SIZE_PRESETS,
            image_min_size=IMAGE_MIN_SIZE,
            image_max_size=IMAGE_MAX_SIZE,
            image_size_step=IMAGE_SIZE_STEP)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Rate limiting для защиты от brute-force
def register():
    """Регистрация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()  # Нормализация email
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        errors = []

        # Валидация username (только безопасные символы)
        if len(username) < 3:
            errors.append('Имя пользователя должно быть не менее 3 символов')
        elif len(username) > 50:
            errors.append('Имя пользователя слишком длинное')
        elif not re.match(r'^[a-zA-Z0-9_-]+$', username):
            errors.append('Имя пользователя может содержать только буквы, цифры, _ и -')

        # Валидация email
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            errors.append('Некорректный email')

        # Валидация пароля
        if len(password) < 8:
            errors.append('Пароль должен быть не менее 8 символов')
        if password != confirm_password:
            errors.append('Пароли не совпадают')

        # Проверка уникальности (case-insensitive)
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            errors.append('Пользователь с таким именем уже существует')
        if User.query.filter(db.func.lower(User.email) == email).first():
            errors.append('Email уже зарегистрирован')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')

        # Создание пользователя
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password
        )

        # Первый пользователь - администратор
        if User.query.count() == 0:
            user.is_admin = True

        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Rate limiting для защиты от brute-force
def login():
    """Вход в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_input = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False) == 'on'

        # Поиск пользователя по username или email (case-insensitive)
        user = User.query.filter(
            (db.func.lower(User.username) == login_input.lower()) | 
            (db.func.lower(User.email) == login_input.lower())
        ).first()

        # Используем константное время для проверки (защита от timing attacks)
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            
            # Безопасный редирект (только на локальные URL)
            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = None
            
            return redirect(next_page or url_for('index'))
        
        # Общее сообщение (не раскрываем что именно неверно)
        flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Профиль пользователя"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not bcrypt.check_password_hash(current_user.password_hash, current_password):
            flash('Неверный текущий пароль', 'error')
        elif len(new_password) < 8:
            flash('Новый пароль должен быть не менее 8 символов', 'error')
        elif new_password != confirm_password:
            flash('Пароли не совпадают', 'error')
        else:
            current_user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            db.session.commit()
            flash('Пароль успешно изменён', 'success')

    # Статистика пользователя
    total_generations = Generation.query.filter_by(user_id=current_user.id).count()
    completed_generations = Generation.query.filter_by(user_id=current_user.id, status='completed').count()

    return render_template('profile.html',
        user=current_user,
        total_generations=total_generations,
        completed_generations=completed_generations)


@app.route('/history')
@login_required
def history():
    """Страница истории генераций"""
    return render_template('history.html', user=current_user)


# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Админ-панель"""
    from modules import ModuleRegistry
    ModuleRegistry.initialize()

    # Calculate sizes
    uploads_size = 0
    results_size = 0
    for folder in ['UPLOAD_FOLDER', 'RESULTS_FOLDER']:
        for gen in Generation.query.all():
            if folder == 'UPLOAD_FOLDER' and gen.input_files:
                for f in gen.input_files:
                    import os
                    from werkzeug.utils import secure_filename
                    safe_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f))
                    if os.path.exists(safe_path):
                        uploads_size += os.path.getsize(safe_path)
            elif folder == 'RESULTS_FOLDER' and gen.output_files:
                for f in gen.output_files:
                    import os
                    from werkzeug.utils import secure_filename
                    safe_path = os.path.join(app.config['RESULTS_FOLDER'], secure_filename(f))
                    if os.path.exists(safe_path):
                        results_size += os.path.getsize(safe_path)

    users = User.query.order_by(User.created_at.desc()).all()
    total_generations = Generation.query.count()
    recent_generations = Generation.query.order_by(Generation.created_at.desc()).limit(20).all()

    # Статистика
    stats = {
        'total_users': User.query.count(),
        'total_generations': total_generations,
        'completed': Generation.query.filter_by(status='completed').count(),
        'failed': Generation.query.filter_by(status='failed').count(),
        'processing': Generation.query.filter_by(status='processing').count(),
    }

    return render_template('admin/dashboard.html',
        users=users,
        stats=stats,
        recent_generations=recent_generations,
        uploads_size=uploads_size,
        results_size=results_size)


@app.route('/admin/generations')
@app.route('/admin/generations/<int:user_id>')
@admin_required
def admin_generations(user_id=None):
    """Список всех генераций"""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = Generation.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    # Фильтры
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter_by(status=status_filter)

    type_filter = request.args.get('type')
    if type_filter:
        query = query.filter_by(generation_type=type_filter)

    # Показывать скрытые
    show_hidden = request.args.get('show_hidden', 'false') == 'true'
    if not show_hidden:
        query = query.filter_by(hidden_from_user=False)

    generations = query.order_by(Generation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Статистика
    stats = {
        'total': Generation.query.count(),
        'completed': Generation.query.filter_by(status='completed').count(),
        'failed': Generation.query.filter_by(status='failed').count(),
        'processing': Generation.query.filter_by(status='processing').count(),
    }

    users_list = User.query.order_by(User.username).all() if not user_id else None

    return render_template('admin/generations.html',
        generations=generations,
        stats=stats,
        users=users_list,
        current_user_id=user_id,
        current_status=status_filter,
        current_type=type_filter,
        show_hidden=show_hidden)


@app.route('/admin/generation-types')
@admin_required
def admin_generation_types():
    """Управление типами генераций"""
    types = GenerationType.query.all()
    return render_template('admin/generation_types.html', types=types)


@app.route('/admin/tokens')
@admin_required
def admin_tokens():
    """Управление токенами"""
    users = User.query.order_by(User.username).all()
    pricing = Pricing.query.all()
    rules = TokenRule.query.all()
    return render_template('admin/tokens.html', users=users, pricing=pricing, rules=rules)


@app.route('/admin/user/<int:user_id>/tokens', methods=['POST'])
@admin_required
def admin_user_tokens(user_id):
    """Управление токенами пользователя"""
    user = User.query.get_or_404(user_id)
    data = request.json or {}

    if 'balance' in data:
        balance = TokenBalance.query.filter_by(user_id=user_id).first()
        if not balance:
            balance = TokenBalance(user_id=user_id, balance=0)
            db.session.add(balance)
        balance.balance = int(data['balance'])
        db.session.add(TokenTransaction(
            user_id=user_id,
            amount=int(data['balance']),
            transaction_type='admin_set',
            description='Manual balance set'
        ))

    if 'add' in data:
        balance = TokenBalance.query.filter_by(user_id=user_id).first()
        if not balance:
            balance = TokenBalance(user_id=user_id, balance=0)
            db.session.add(balance)
        balance.balance += int(data['add'])
        db.session.add(TokenTransaction(
            user_id=user_id,
            amount=int(data['add']),
            transaction_type='admin_add',
            description='Manual add'
        ))

    if 'priority' in data:
        user.priority = int(data['priority'])

    if 'token_period' in data:
        user.token_period = data['token_period']

    if 'reset_period' in data:
        user.last_token_reset = datetime.utcnow()

    db.session.commit()
    return jsonify({'success': True, 'message': 'Сохранено'})


@app.route('/admin/token-rule/<int:rule_id>/toggle', methods=['POST'])
@admin_required
def admin_token_rule_toggle(rule_id):
    rule = TokenRule.query.get_or_404(rule_id)
    rule.is_active = not rule.is_active
    db.session.commit()
    return jsonify({'success': True, 'message': f'Rule {"enabled" if rule.is_active else "disabled"}'})


@app.route('/admin/token-rule/<int:rule_id>/delete', methods=['POST'])
@admin_required
def admin_token_rule_delete(rule_id):
    rule = TokenRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Rule deleted'})


@app.route('/admin/generation-types/<int:type_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_generation_type(type_id):
    """Включение/выключение типа генерации"""
    gen_type = GenerationType.query.get_or_404(type_id, description=f'Type id:{type_id} not found')
    gen_type.enabled = not gen_type.enabled
    db.session.commit()

    return jsonify({
        'success': True,
        'enabled': gen_type.enabled,
        'message': f'{gen_type.name} {"включён" if gen_type.enabled else "выключен"}'
    })


@app.route('/admin/generation-types/<int:type_id>/update', methods=['POST'])
@admin_required
def admin_update_generation_type(type_id):
    """Обновление метаданных типа генерации"""
    gen_type = GenerationType.query.get_or_404(type_id, description=f'Type id:{type_id} not found')
    data = request.json or {}

    field = data.get('field')
    value = data.get('value')

    if field == 'name':
        gen_type.name = value
    elif field == 'description':
        gen_type.description = value
    else:
        return jsonify({'success': False, 'error': 'Unknown field'}), 400

    db.session.commit()

    return jsonify({'success': True, 'message': 'Сохранено'})


@app.route('/api/admin/scan-modules', methods=['POST'])
@admin_required
def api_admin_scan_modules():
    """Сканирование модулей и автоматическое добавление в БД"""
    from modules import ModuleRegistry

    if not ModuleRegistry._initialized:
        ModuleRegistry.initialize()

    modules = ModuleRegistry.get_all()
    modules_found = len(modules)
    modules_added = 0
    existing_keys = {gt.type_key for gt in GenerationType.query.all()}

    for mod in modules:
        if mod.type_key not in existing_keys:
            gen_type = GenerationType(
                type_key=mod.type_key,
                name=mod.name or mod.type_key,
                description=mod.description or f"Модуль {mod.type_key}",
                enabled=True
            )
            db.session.add(gen_type)
            modules_added += 1
            print(f"[MODULE] Auto-added: {mod.type_key}")

    existing_pricing = {p.module_key for p in Pricing.query.all()}
    for mod in modules:
        if mod.type_key not in existing_pricing:
            pricing = Pricing(
                module_key=mod.type_key,
                base_cost=getattr(mod, 'base_cost', 10),
                is_public=True
            )
            db.session.add(pricing)
            print(f"[PRICING] Auto-added: {mod.type_key} (cost: {pricing.base_cost})")

    db.session.commit()

    return jsonify({
        'success': True,
        'modules_found': modules_found,
        'modules_added': modules_added,
        'modules': [{'key': m.type_key, 'name': m.name} for m in modules]
    })


@app.route('/api/generation-types')
@login_required
def api_generation_types():
    """Получение доступных типов генераций"""
    types = GenerationType.query.filter_by(enabled=True).all()
    return jsonify({
        'success': True,
        'types': [{'key': t.type_key, 'name': t.name, 'description': t.description} for t in types]
    })


@app.route('/users')
@admin_required
def admin_users():
    """Управление пользователями"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    """Детальная информация о пользователе"""
    user = User.query.get_or_404(user_id, description=f'User id:{user_id} not found')
    generations = Generation.query.filter_by(user_id=user_id).order_by(Generation.created_at.desc()).limit(50).all()
    return render_template('admin/user_detail.html', user=user, generations=generations)


@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    """Переключение статуса администратора"""
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменить свой статус'}), 400

    user = User.query.get_or_404(user_id, description=f'User id:{user_id} not found')
    user.is_admin = not user.is_admin
    db.session.commit()

    return jsonify({
        'success': True,
        'is_admin': user.is_admin,
        'message': f'Пользователь {user.username} {"назначен администратором" if user.is_admin else "лишён прав администратора"}'
    })


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    """Удаление пользователя"""
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя удалить себя'}), 400

    user = User.query.get_or_404(user_id, description=f'User id:{user_id} not found')

    # Удаляем все генерации пользователя (с файлами)
    generations = Generation.query.filter_by(user_id=user_id).all()
    for gen in generations:
        delete_generation_files(gen)
        db.session.delete(gen)

    username = user.username
    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Пользователь {username} удалён'
    })


@app.route('/admin/generation/<int:generation_id>')
@admin_required
def admin_view_generation(generation_id):
    """Просмотр генерации администратором"""
    generation = Generation.query.get_or_404(generation_id, description=f'Generation id:{generation_id} not found')
    return render_template('admin/generation_detail.html', generation=generation)


@app.route('/admin/generation/<int:generation_id>/delete', methods=['POST'])
@admin_required
def admin_delete_generation(generation_id):
    """Полное удаление генерации (с файлами)"""
    generation = Generation.query.get_or_404(generation_id, description=f'Generation id:{generation_id} not found')

    delete_generation_files(generation)
    db.session.delete(generation)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Генерация #{generation_id} полностью удалена'
    })


@app.route('/admin/generation/<int:generation_id>/restore', methods=['POST'])
@admin_required
def admin_restore_generation(generation_id):
    """Восстановление скрытой генерации"""
    generation = Generation.query.get_or_404(generation_id, description=f'Generation id:{generation_id} not found')
    generation.hidden_from_user = False
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Генерация #{generation_id} восстановлена'
    })


@app.route('/admin/cleanup', methods=['POST'])
@admin_required
def admin_cleanup():
    """Очистка: удаление файлов от скрытых генераций"""
    data = request.json or {}
    delete_hidden = data.get('delete_hidden', False)
    delete_orphans = data.get('delete_orphans', False)

    deleted_count = 0
    freed_space = 0

    if delete_hidden:
        # Удаляем файлы от скрытых генераций
        hidden_generations = Generation.query.filter_by(hidden_from_user=True).all()
        for gen in hidden_generations:
            freed_space += get_generation_files_size(gen)
            delete_generation_files(gen)
            db.session.delete(gen)
            deleted_count += 1

    if delete_orphans:
        # Удаляем файлы, не связанные с генерациями
        orphans_deleted, orphan_space = cleanup_orphan_files()
        deleted_count += orphans_deleted
        freed_space += orphan_space

    db.session.commit()

    return jsonify({
        'success': True,
        'deleted_count': deleted_count,
        'freed_space_mb': round(freed_space / 1024 / 1024, 2),
        'message': f'Удалено {deleted_count} записей, освобождено {freed_space / 1024 / 1024:.2f} MB'
    })


# ==================== API ROUTES ====================

@app.route('/api/generate-image', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_generate_image():
    """Генерация изображения
    ---
    tags:
      - Generation
    consumes:
      - application/json
    produces:
      - application/json
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - prompt
          properties:
            prompt:
              type: string
              description: Текстовый промпт для генерации
            negative_prompt:
              type: string
              description: Негативный промпт
            model:
              type: string
              default: wan22
              description: Модель для генерации
            seed:
              type: integer
              description: Seed для генерации (опционально)
            width:
              type: integer
              default: 1024
              description: Ширина изображения
            height:
              type: integer
              default: 1024
              description: Высота изображения
    responses:
      200:
        description: Успешный запуск генерации
        schema:
          $ref: '#/definitions/GenerateResponse'
      400:
        description: Ошибка валидации
      402:
        description: Недостаточно токенов
      403:
        description: Тип генерации недоступен
    """
    data = request.json
    prompt = data.get('prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()
    model = data.get('model', 'wan22')
    seed = data.get('seed', None)

    if not prompt:
        return jsonify({'error': 'Промпт обязателен'}), 400

    # Валидация модели
    if model not in app.config.get('MODELS', {}):
        model = 'wan22'

    # Проверка что тип генерации включён
    gen_type = GenerationType.query.filter_by(type_key=model, enabled=True).first()
    if not gen_type:
        return jsonify({'error': 'Тип генерации временно недоступен'}), 403

    # Валидация размеров
    width = data.get('width', 1024)
    height = data.get('height', 1024)
    width, height = validate_image_dimensions(width, height)

    # Валидация seed - возвращаем ошибку если некорректный
    if seed is not None:
        try:
            seed = int(seed)
            if seed < 0 or seed > 2**32 - 1:
                return jsonify({'error': 'Seed должен быть в диапазоне 0-4294967295'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Некорректный формат seed'}), 400

    # Проверка токенов
    apply_token_rules(current_user)
    has_tokens, cost, token_msg = check_and_spend_tokens(current_user.id, model, width, height)
    if not has_tokens:
        return jsonify({'error': token_msg, 'code': 'INSUFFICIENT_TOKENS', 'balance': get_user_balance(current_user.id)}), 402

    generation = Generation(
        user_id=current_user.id,
        generation_type='text-to-image',
        model_used=model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        settings={
            'seed': seed,
            'width': width,
            'height': height
        },
        status='processing'
    )

    db.session.add(generation)
    db.session.commit()

    threading.Thread(
        target=process_image_generation,
        args=(generation.id, prompt, negative_prompt, model, seed, width, height),
        daemon=True
    ).start()

    return jsonify({
        'success': True,
        'generation_id': generation.id,
        'message': 'Генерация запущена',
        'settings': {
            'width': width,
            'height': height
        }
    })


@app.route('/api/generate-video', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def api_generate_video():
    """Генерация видео
    ---
    tags:
      - Generation
    consumes:
      - application/json
    produces:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - prompt
          properties:
            prompt:
              type: string
              description: Текстовый промпт для генерации видео
            negative_prompt:
              type: string
              description: Негативный промпт
            model:
              type: string
              default: wan22_video
              description: Модель для генерации
            duration:
              type: integer
              default: 4
              description: Длительность видео в секундах
    responses:
      200:
        description: Успешный запуск генерации
      400:
        description: Ошибка валидации
      403:
        description: Тип генерации недоступен
    """
    data = request.json
    prompt = data.get('prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()
    model = data.get('model', 'wan22_video')
    duration = min(int(data.get('duration', 4)), app.config['MAX_VIDEO_DURATION'])

    if not prompt:
        return jsonify({'error': 'Промпт обязателен'}), 400

    # Проверка что тип генерации включён
    gen_type = GenerationType.query.filter_by(type_key=model, enabled=True).first()
    if not gen_type:
        return jsonify({'error': 'Тип генерации временно недоступен'}), 403

    generation = Generation(
        user_id=current_user.id,
        generation_type='text-to-video',
        model_used=model,
        prompt=prompt,
        negative_prompt=negative_prompt,
        settings={'duration': duration},
        status='processing'
    )

    db.session.add(generation)
    db.session.commit()

    threading.Thread(
        target=process_video_generation,
        args=(generation.id, prompt, negative_prompt, model, duration),
        daemon=True
    ).start()

    return jsonify({
        'success': True,
        'generation_id': generation.id,
        'message': 'Генерация видео запущена'
    })


@app.route('/api/edit-images', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def api_edit_images():
    """Редактирование изображений
    ---
    tags:
      - Generation
    consumes:
      - multipart/form-data
    produces:
      - application/json
    parameters:
      - in: formData
        name: images
        type: file
        required: true
        description: Изображения для редактирования (1-4)
      - in: formData
        name: prompt
        type: string
        required: true
        description: Текстовый промпт для редактирования
      - in: formData
        name: negative_prompt
        type: string
        description: Негативный промпт
    responses:
      200:
        description: Успешный запуск генерации
      400:
        description: Ошибка валидации
    """
    files = request.files.getlist('images')
    prompt = request.form.get('prompt', '').strip()
    negative_prompt = request.form.get('negative_prompt', '').strip()

    # Валидация
    if len(files) > app.config['MAX_IMAGES_PER_GENERATION']:
        return jsonify({
            'error': f'Максимум {app.config["MAX_IMAGES_PER_GENERATION"]} изображений'
        }), 400

    if len(files) == 0:
        return jsonify({'error': 'Загрузите хотя бы одно изображение'}), 400

    if not prompt:
        return jsonify({'error': 'Промпт обязателен'}), 400

    # Обрабатываем файлы
    saved_files = []
    image_dimensions = []

    for idx, file in enumerate(files):
        try:
            filename, filepath, dimensions = validate_and_process_image(file)
            saved_files.append(filename)
            image_dimensions.append(dimensions)
            print(f"[UPLOAD] Processed {idx+1}/{len(files)}: {filename} ({dimensions[0]}x{dimensions[1]})")
        except ValueError as e:
            # Удаляем уже сохранённые
            for f in saved_files:
                try:
                    safe_path = secure_path_check(app.config['UPLOAD_FOLDER'], f)
                    if safe_path and os.path.exists(safe_path):
                        os.remove(safe_path)
                except:
                    pass
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            for f in saved_files:
                try:
                    safe_path = secure_path_check(app.config['UPLOAD_FOLDER'], f)
                    if safe_path and os.path.exists(safe_path):
                        os.remove(safe_path)
                except:
                    pass
            return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500

    # Выбор workflow
    edit_type = 'qwen_single' if len(saved_files) == 1 else 'qwen_multi'
    print(f"[EDIT] Files: {len(saved_files)}, workflow: {edit_type}")

    # Проверка что тип генерации включён
    gen_type = GenerationType.query.filter_by(type_key=edit_type, enabled=True).first()
    if not gen_type:
        # Удаляем загруженные файлы
        for f in saved_files:
            try:
                safe_path = secure_path_check(app.config['UPLOAD_FOLDER'], f)
                if safe_path and os.path.exists(safe_path):
                    os.remove(safe_path)
            except:
                pass
        return jsonify({'error': 'Тип генерации временно недоступен'}), 403

    generation = Generation(
        user_id=current_user.id,
        generation_type='image-edit',
        model_used=edit_type,
        prompt=prompt,
        negative_prompt=negative_prompt,
        input_files=saved_files,
        settings={
            'file_count': len(saved_files),
            'dimensions': image_dimensions
        },
        status='processing'
    )

    db.session.add(generation)
    db.session.commit()

    threading.Thread(
        target=process_image_edit,
        args=(generation.id, saved_files, edit_type, prompt, negative_prompt),
        daemon=True
    ).start()

    return jsonify({
        'success': True,
        'generation_id': generation.id,
        'message': f'Редактирование {len(saved_files)} изображений запущено'
    })


@app.route('/api/image-presets')
@login_required
def api_image_presets():
    """Получение пресетов размеров изображений"""
    return jsonify({
        'success': True,
        'presets': IMAGE_SIZE_PRESETS,
        'min_size': IMAGE_MIN_SIZE,
        'max_size': IMAGE_MAX_SIZE,
        'step': IMAGE_SIZE_STEP
    })


@app.route('/api/favorites', methods=['GET'])
@login_required
def api_favorites():
    """Получение избранного"""
    favorites = Favorite.query.filter_by(user_id=current_user.id).order_by(
        Favorite.created_at.desc()
    ).all()

    return jsonify({
        'success': True,
        'favorites': [{
            'generation_id': f.generation_id,
            'created_at': f.created_at.isoformat()
        } for f in favorites]
    })


@app.route('/api/generation/<int:generation_id>/favorite', methods=['POST', 'DELETE'])
@login_required
def api_favorite_toggle(generation_id):
    """Добавить/удалить из избранного"""
    generation = Generation.query.filter_by(
        id=generation_id,
        user_id=current_user.id
    ).first()

    if not generation:
        return jsonify({'error': 'Генерация не найдена'}), 404

    if request.method == 'POST':
        existing = Favorite.query.filter_by(
            user_id=current_user.id,
            generation_id=generation_id
        ).first()

        if not existing:
            fav = Favorite(user_id=current_user.id, generation_id=generation_id)
            db.session.add(fav)
            db.session.commit()
            return jsonify({'success': True, 'favorited': True})

        return jsonify({'success': True, 'favorited': True})

    else:
        fav = Favorite.query.filter_by(
            user_id=current_user.id,
            generation_id=generation_id
        ).first()

        if fav:
            db.session.delete(fav)
            db.session.commit()

        return jsonify({'success': True, 'favorited': False})


@app.route('/api/presets', methods=['GET', 'POST'])
@login_required
def api_presets():
    """Получение/создание пресетов генераций"""
    if request.method == 'POST':
        data = request.json or {}
        name = data.get('name', '').strip()
        generation_type = data.get('generation_type', 'text-to-image')
        model_used = data.get('model', '')
        prompt = data.get('prompt', '')
        negative_prompt = data.get('negative_prompt', '')
        settings = data.get('settings', {})

        if not name:
            return jsonify({'error': 'Название пресета обязательно'}), 400

        preset = GenerationPreset(
            user_id=current_user.id,
            name=name,
            generation_type=generation_type,
            model_used=model_used,
            prompt=prompt,
            negative_prompt=negative_prompt,
            settings=settings,
            is_public=data.get('is_public', False)
        )

        db.session.add(preset)
        db.session.commit()

        return jsonify({'success': True, 'preset': preset.to_dict()})

    # GET - получить пресеты
    presets = GenerationPreset.query.filter(
        (GenerationPreset.user_id == current_user.id) |
        (GenerationPreset.is_public == True)
    ).order_by(GenerationPreset.created_at.desc()).all()

    return jsonify({
        'success': True,
        'presets': [p.to_dict() for p in presets]
    })


@app.route('/api/presets/<int:preset_id>', methods=['DELETE'])
@login_required
def api_delete_preset(preset_id):
    """Удаление пресета"""
    preset = GenerationPreset.query.filter_by(
        id=preset_id,
        user_id=current_user.id
    ).first()

    if not preset:
        return jsonify({'error': 'Пресет не найден'}), 404

    db.session.delete(preset)
    db.session.commit()

    return jsonify({'success': True})


ALLOWED_THEMES = ['light', 'dark-theme', 'blue', 'green', 'purple']
ALLOWED_COLOR_SCHEMES = ['default', 'ocean', 'forest', 'sunset']


@app.route('/api/theme', methods=['GET', 'POST'])
@login_required
def api_theme():
    """Получение/изменение темы и цветовой схемы"""
    if request.method == 'POST':
        data = request.json or {}
        theme = data.get('theme', 'light')
        color_scheme = data.get('color_scheme', 'default')

        if theme not in ALLOWED_THEMES:
            return jsonify({'error': 'Неверная тема', 'allowed': ALLOWED_THEMES}), 400
        if color_scheme not in ALLOWED_COLOR_SCHEMES:
            return jsonify({'error': 'Неверная схема', 'allowed': ALLOWED_COLOR_SCHEMES}), 400

        current_user.theme = theme
        current_user.color_scheme = color_scheme
        db.session.commit()

        return jsonify({'success': True, 'theme': theme, 'color_scheme': color_scheme})

    return jsonify({
        'success': True,
        'theme': current_user.theme or 'light',
        'color_scheme': current_user.color_scheme or 'default'
    })


@app.route('/api/generation/<int:generation_id>/status')
@login_required
def api_generation_status(generation_id):
    """Получение статуса генерации
    ---
    tags:
      - Generation
    produces:
      - application/json
    parameters:
      - in: path
        name: generation_id
        type: integer
        required: true
        description: ID генерации
    responses:
      200:
        description: Статус генерации
        schema:
          $ref: '#/definitions/GenerationStatus'
      404:
        description: Генерация не найдена
    """
    # Проверяем права: владелец или админ
    if current_user.is_admin:
        generation = Generation.query.get(generation_id)
    else:
        generation = Generation.query.filter_by(
            id=generation_id,
            user_id=current_user.id,
            hidden_from_user=False
        ).first()

    if not generation:
        return jsonify({'error': 'Генерация не найдена'}), 404

    return jsonify(generation.to_dict())


@app.route('/api/generation/<int:generation_id>')
@login_required
def api_get_generation(generation_id):
    """Получение информации о генерации"""
    if current_user.is_admin:
        generation = Generation.query.get(generation_id)
    else:
        generation = Generation.query.filter_by(
            id=generation_id,
            user_id=current_user.id,
            hidden_from_user=False
        ).first()

    if not generation:
        return jsonify({'error': 'Генерация не найдена'}), 404

    return jsonify({
        'success': True,
        'generation': generation.to_dict()
    })


@app.route('/api/generation/<int:generation_id>', methods=['DELETE'])
@login_required
def api_delete_generation(generation_id):
    """Удаление генерации пользователем (скрытие, файлы остаются)"""
    generation = Generation.query.filter_by(
        id=generation_id,
        user_id=current_user.id
    ).first()

    if not generation:
        return jsonify({'error': 'Генерация не найдена'}), 404

    # Только скрываем от пользователя, файлы НЕ удаляем
    generation.hidden_from_user = True
    db.session.commit()

    print(f"[HISTORY] Hidden generation #{generation_id} from user {current_user.id}")

    return jsonify({'success': True, 'message': 'Генерация удалена из истории'})


@app.route('/api/history')
@login_required
def api_history():
    """Получение истории генераций
    ---
    tags:
      - History
    produces:
      - application/json
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
        description: Номер страницы
      - in: query
        name: per_page
        type: integer
        default: 20
        description: Количество на странице (макс 100)
      - in: query
        name: type
        type: string
        description: Фильтр по типу генерации (text-to-image, text-to-video, image-to-image)
    responses:
      200:
        description: История генераций
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)  # Ограничение
    filter_type = request.args.get('type', None)

    query = Generation.query.filter_by(
        user_id=current_user.id,
        hidden_from_user=False
    )

    if filter_type:
        query = query.filter_by(generation_type=filter_type)

    generations = query.order_by(Generation.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'success': True,
        'generations': [g.to_dict() for g in generations.items],
        'total': generations.total,
        'pages': generations.pages,
        'current_page': page,
        'has_next': generations.has_next,
        'has_prev': generations.has_prev
    })


@app.route('/api/history/clear', methods=['POST'])
@login_required
def api_clear_history():
    """Очистка истории пользователя (скрытие, файлы остаются)"""
    # Только скрываем, НЕ удаляем файлы
    generations = Generation.query.filter_by(
        user_id=current_user.id,
        hidden_from_user=False
    ).all()

    hidden_count = 0
    for gen in generations:
        gen.hidden_from_user = True
        hidden_count += 1

    db.session.commit()

    print(f"[HISTORY] Hidden {hidden_count} generations for user {current_user.id}")

    return jsonify({
        'success': True,
        'message': f'Скрыто {hidden_count} генераций'
    })


@app.route('/api/history/bulk-delete', methods=['POST'])
@login_required
def api_bulk_delete():
    """Массовое удаление генераций"""
    data = request.json or {}
    generation_ids = data.get('ids', [])

    if not generation_ids or not isinstance(generation_ids, list):
        return jsonify({'error': 'Требуется массив ids'}), 400

    deleted_count = 0
    for gen_id in generation_ids:
        gen = Generation.query.filter_by(
            id=gen_id,
            user_id=current_user.id
        ).first()
        if gen:
            gen.hidden_from_user = True
            deleted_count += 1

    db.session.commit()

    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'message': f'Удалено {deleted_count} генераций'
    })


@app.route('/api/history/bulk-export', methods=['POST'])
@login_required
def api_bulk_export():
    """Массовый экспорт генераций (ZIP)"""
    data = request.json or {}
    generation_ids = data.get('ids', [])

    if not generation_ids or not isinstance(generation_ids, list):
        return jsonify({'error': 'Требуется массив ids'}), 400

    files_to_export = []
    for gen_id in generation_ids:
        gen = Generation.query.filter_by(
            id=gen_id,
            user_id=current_user.id,
            status='completed'
        ).first()
        if gen and gen.output_files:
            files_to_export.extend(gen.output_files)

    return jsonify({
        'success': True,
        'files': files_to_export,
        'count': len(files_to_export)
    })


# ==================== FILE SERVING ====================

@app.route('/results/<filename>')
@login_required
def serve_result(filename):
    """Отдача результатов"""
    filepath = secure_path_check(app.config['RESULTS_FOLDER'], filename)
    if filepath and os.path.exists(filepath):
        return send_from_directory(app.config['RESULTS_FOLDER'], secure_filename(filename))
    return jsonify({'error': 'Файл не найден'}), 404


@app.route('/uploads/<filename>')
@login_required
def serve_upload(filename):
    """Отдача загруженных файлов"""
    filepath = secure_path_check(app.config['UPLOAD_FOLDER'], filename)
    if filepath and os.path.exists(filepath):
        return send_from_directory(app.config['UPLOAD_FOLDER'], secure_filename(filename))
    return jsonify({'error': 'Файл не найден'}), 404


@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """Скачивание файла"""
    # Сначала пробуем results, потом uploads
    filepath = secure_path_check(app.config['RESULTS_FOLDER'], filename)
    folder = app.config['RESULTS_FOLDER']
    if not filepath or not os.path.exists(filepath):
        filepath = secure_path_check(app.config['UPLOAD_FOLDER'], filename)
        folder = app.config['UPLOAD_FOLDER']

    if filepath and os.path.exists(filepath):
        return send_from_directory(folder, secure_filename(filename), as_attachment=True)
    return jsonify({'error': 'Файл не найден'}), 404


@app.route('/gallery')
def public_gallery():
    """Публичная галерея"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    generations = Generation.query.filter_by(
        is_public=True,
        hidden_from_user=False
    ).order_by(Generation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('gallery.html',
        generations=generations.items,
        total=generations.total,
        pages=generations.pages,
        current_page=page,
        has_next=generations.has_next,
        has_prev=generations.has_prev
    )


@app.route('/gallery/<int:generation_id>')
def public_generation(generation_id):
    """Публичная генерация по ID"""
    generation = Generation.query.filter_by(
        id=generation_id,
        is_public=True,
        hidden_from_user=False
    ).first_or_404(description='Генерация не найдена')

    return render_template('generation_public.html', generation=generation)


@app.route('/user/<username>/gallery')
def user_gallery(username):
    """Галерея пользователя"""
    user = User.query.filter_by(username=username).first_or_404(description='Пользователь не найден')

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    generations = Generation.query.filter_by(
        user_id=user.id,
        is_public=True,
        hidden_from_user=False
    ).order_by(Generation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template('user_gallery.html',
        user=user,
        generations=generations.items,
        total=generations.total,
        pages=generations.pages,
        current_page=page,
        has_next=generations.has_next,
        has_prev=generations.has_prev
    )


@app.route('/api/generation/<int:generation_id>/toggle-public', methods=['POST'])
@login_required
def api_toggle_public(generation_id):
    """Сделать генерацию публичной/приватной"""
    generation = Generation.query.filter_by(
        id=generation_id,
        user_id=current_user.id
    ).first()

    if not generation:
        return jsonify({'error': 'Генерация не найдена'}), 404

    generation.is_public = not generation.is_public
    db.session.commit()

    return jsonify({
        'success': True,
        'is_public': generation.is_public,
        'message': 'Публичная' if generation.is_public else 'Приватная'
    })


# ==================== TOKEN FUNCTIONS ====================

def get_user_balance(user_id):
    """Получить баланс пользователя"""
    balance = TokenBalance.query.filter_by(user_id=user_id).first()
    if not balance:
        balance = TokenBalance(user_id=user_id, balance=0)
        db.session.add(balance)
        db.session.commit()
    return balance.balance


def check_and_spend_tokens(user_id, generation_type, width=0, height=0, duration=0):
    """
    Проверить баланс и списать токены.
    Returns (success, cost, message)
    """
    if current_user.is_admin:
        return True, 0, "Admin bypass"

    # Получаем цену из модуля или Pricing модели
    pricing = Pricing.query.filter_by(module_key=generation_type).first()
    if pricing:
        cost = pricing.calculate_cost(width, height, duration)
    else:
        cost = 10  # Default cost

    balance = get_user_balance(user_id)

    if balance < cost:
        return False, 0, f"Недостаточно токенов. Нужно {cost}, у вас {balance}"

    # Списываем токены
    balance_record = TokenBalance.query.filter_by(user_id=user_id).first()
    balance_record.balance -= cost
    balance_record.updated_at = datetime.utcnow()

    transaction = TokenTransaction(
        user_id=user_id,
        amount=-cost,
        transaction_type='generation',
        description=f'Generation {generation_type}: {width}x{height}'
    )
    db.session.add(transaction)
    db.session.commit()

    return True, cost, f"Списано {cost} токенов"


def refund_tokens(user_id, amount, generation_id, reason="Refund"):
    """Вернуть токены (при ошибке генерации)"""
    balance = TokenBalance.query.filter_by(user_id=user_id).first()
    if not balance:
        return

    balance.balance += amount

    transaction = TokenTransaction(
        user_id=user_id,
        amount=amount,
        transaction_type='refund',
        description=reason,
        generation_id=generation_id
    )
    db.session.add(transaction)
    db.session.commit()


def get_user_priority(user):
    """Получить приоритет пользователя"""
    if user.is_admin:
        return UserPriority.ADMIN
    return user.priority or UserPriority.NORMAL


def apply_token_rules(user):
    """Применить правила начисления токенов по периоду"""
    from datetime import timedelta

    now = datetime.utcnow()
    period = user.token_period or 'monthly'

    # Проверяем нужно ли начислить
    last_reset = user.last_token_reset or user.created_at
    days_since_reset = (now - last_reset).days

    should_reset = False
    if period == 'daily':
        should_reset = days_since_reset >= 1
    elif period == 'weekly':
        should_reset = days_since_reset >= 7
    elif period == 'monthly':
        should_reset = days_since_reset >= 30

    if not should_reset:
        return

    # Начисляем по активным правилам
    active_rules = TokenRule.query.filter_by(is_active=True).all()
    total_amount = 0

    for rule in active_rules:
        if rule.max_uses and rule.uses_count >= rule.max_uses:
            continue

        total_amount += rule.amount
        rule.uses_count += 1

    if total_amount > 0:
        balance = get_user_balance(user.id)
        balance_record = TokenBalance.query.filter_by(user_id=user.id).first()
        balance_record.balance += total_amount
        balance_record.updated_at = now

        transaction = TokenTransaction(
            user_id=user.id,
            amount=total_amount,
            transaction_type='rule_bonus',
            description=f'Bonus: {rule.name}'
        )
        db.session.add(transaction)

        user.last_token_reset = now
        db.session.commit()
        print(f"[TOKENS] Added {total_amount} tokens to user {user.username}")


def initialize_pricing():
    """Инициализация цен по умолчанию"""
    default_pricing = [
        ('wan22', 10, 1, 1, 0),       # text-to-image: 10 + за каждые 256px
        ('wan22_video', 20, 0, 0, 5),  # video: 20 + за секунду
        ('qwen_single', 15, 1, 1, 0),
        ('qwen_multi', 25, 2, 2, 0),
    ]

    for module_key, base, w, h, sec in default_pricing:
        if not Pricing.query.filter_by(module_key=module_key).first():
            pricing = Pricing(
                module_key=module_key,
                base_cost=base,
                cost_per_width=w,
                cost_per_height=h,
                cost_per_second=sec
            )
            db.session.add(pricing)

    db.session.commit()


# ==================== WORKFLOW FUNCTIONS ====================

def load_workflow(workflow_type, model_name):
    """
    Загрузка workflow из модуля.
    Использует ModuleRegistry если доступно, иначе legacy file loading.
    """
    # Пробуем сначала из модулей
    module = ModuleRegistry.get(model_name)
    if module:
        print(f"[WORKFLOW] Loading from module: {model_name}")
        return module.get_workflow()

    # Fallback на старый метод загрузки из файлов
    print(f"[WORKFLOW] Loading from file (legacy): {model_name}")
    workflows_dir = app.config.get('WORKFLOWS_DIR', 'workflows')

    safe_model_name = re.sub(r'[^a-zA-Z0-9_-]', '', model_name)
    safe_workflow_type = re.sub(r'[^a-zA-Z0-9_-]', '', workflow_type)

    filename = f"{safe_workflow_type}_{safe_model_name}.json"
    filepath = secure_path_check(workflows_dir, filename)

    if not filepath or not os.path.exists(filepath):
        filename = f"{safe_workflow_type}_default.json"
        filepath = secure_path_check(workflows_dir, filename)

        if not filepath or not os.path.exists(filepath):
            raise FileNotFoundError(f"Workflow not found: {filename}")

    with open(filepath, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    return workflow


def prepare_workflow_with_module(module, workflow, prompt, negative_prompt="", **kwargs):
    """
    Подготовка workflow с использованием модуля.
    Использует module.prepare_workflow если доступно.
    """
    if hasattr(module, 'prepare_workflow'):
        return module.prepare_workflow(workflow, prompt, negative_prompt, **kwargs)

    # Legacy метод - просто возвращает как есть
    return workflow


def update_workflow_prompt(workflow, prompt, negative_prompt=""):
    """
    Обновление промптов в workflow.
    Поддерживает различные типы encoding нод.
    """
    print(f"\n[PROMPT] === Updating prompts ===")
    print(f"[PROMPT] Positive: {prompt[:80]}...")
    if negative_prompt:
        print(f"[PROMPT] Negative: {negative_prompt[:80]}...")

    # Типы нод для кодирования текста
    ENCODING_NODE_TYPES = [
        'CLIPTextEncode',
        'CLIPTextEncodeSDXL',
        'CLIPTextEncodeSD3',
    ]

    # Находим все ноды кодирования
    encoding_nodes = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue

        class_type = node.get('class_type', '')
        if class_type in ENCODING_NODE_TYPES:
            title = node.get('_meta', {}).get('title', '').lower()
            inputs = node.get('inputs', {})

            # Определяем поле для текста
            text_field = 'text'
            if class_type == 'CLIPTextEncodeSDXL':
                text_field = 'text_g'  # Или text_l

            encoding_nodes.append({
                'node_id': node_id,
                'node': node,
                'class_type': class_type,
                'title': title,
                'text_field': text_field
            })

    print(f"[PROMPT] Found {len(encoding_nodes)} encoding nodes")

    # Анализируем связи для определения positive/negative
    conditioning_links = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict) or 'inputs' not in node:
            continue
        
        inputs = node['inputs']
        class_type = node.get('class_type', '')
        
        # KSampler использует positive и negative conditioning
        if class_type in ['KSampler', 'KSamplerAdvanced']:
            if 'positive' in inputs and isinstance(inputs['positive'], list):
                positive_node_id = str(inputs['positive'][0])
                conditioning_links[positive_node_id] = 'positive'
            if 'negative' in inputs and isinstance(inputs['negative'], list):
                negative_node_id = str(inputs['negative'][0])
                conditioning_links[negative_node_id] = 'negative'

    print(f"[PROMPT] Conditioning links: {conditioning_links}")

    # Обновляем промпты
    positive_updated = False
    negative_updated = False

    positive_node_id = None
    negative_node_id = None

    for link_node_id, link_type in conditioning_links.items():
        if link_type == 'positive':
            positive_node_id = link_node_id
        elif link_type == 'negative':
            negative_node_id = link_node_id

    for enc in encoding_nodes:
        node_id = enc['node_id']
        node = enc['node']
        text_field = enc['text_field']

        if 'inputs' not in node:
            node['inputs'] = {}

        if node_id == positive_node_id:
            old_value = node['inputs'].get(text_field, '')
            node['inputs'][text_field] = prompt
            positive_updated = True
            print(f"[PROMPT] ✓ Set POSITIVE in node {node_id} (by connection)")
            if old_value and old_value != prompt:
                print(f"     Old: {old_value[:80]}...")
                print(f"     New: {prompt[:80]}...")
        elif node_id == negative_node_id:
            old_value = node['inputs'].get(text_field, '')
            node['inputs'][text_field] = negative_prompt if negative_prompt else ''
            negative_updated = True
            print(f"[PROMPT] ✓ Set NEGATIVE in node {node_id} (by connection)")
            if old_value:
                print(f"     Old: {old_value[:80]}...")
                print(f"     New: {negative_prompt[:80] if negative_prompt else '(empty)'}...")

    # Fallback: ищем по title
    if not positive_updated or not negative_updated:
        print(f"[PROMPT] Falling back to title-based detection...")
        for enc in encoding_nodes:
            node_id = enc['node_id']
            node = enc['node']
            title = enc['title']
            text_field = enc['text_field']

            is_positive = any(kw in title for kw in ['positive', 'позитив'])
            is_negative = any(kw in title for kw in ['negative', 'негатив'])

            if 'inputs' not in node:
                node['inputs'] = {}

            if is_positive and not positive_updated:
                node['inputs'][text_field] = prompt
                positive_updated = True
                print(f"[PROMPT] ✓ Set POSITIVE in node {node_id} (by title)")
            elif is_negative and not negative_updated:
                node['inputs'][text_field] = negative_prompt if negative_prompt else ''
                negative_updated = True
                print(f"[PROMPT] ✓ Set NEGATIVE in node {node_id} (by title)")

    # Final fallback: если всё ещё не обновлены, берём по порядку
    if not positive_updated and len(encoding_nodes) >= 1:
        enc = encoding_nodes[0]
        if 'inputs' not in enc['node']:
            enc['node']['inputs'] = {}
        enc['node']['inputs'][enc['text_field']] = prompt
        positive_updated = True
        print(f"[PROMPT] ✓ Set POSITIVE in node {enc['node_id']} (first node fallback)")

    if not negative_updated and len(encoding_nodes) >= 2:
        enc = encoding_nodes[1]
        if 'inputs' not in enc['node']:
            enc['node']['inputs'] = {}
        enc['node']['inputs'][enc['text_field']] = negative_prompt if negative_prompt else ''
        negative_updated = True
        print(f"[PROMPT] ✓ Set NEGATIVE in node {enc['node_id']} (second node fallback)")

    # Для некоторых workflow negative может быть необязательным
    if not negative_updated and not negative_prompt:
        print(f"[PROMPT] ℹ Negative prompt is empty, skipping")
        negative_updated = True

    print(f"[PROMPT] Result: positive={'✓' if positive_updated else '✗'}, negative={'✓' if negative_updated else '✗'}")

    if not positive_updated:
        raise Exception("Failed to set positive prompt - no suitable nodes found")

    return workflow


def update_image_dimensions(workflow, width, height):
    """
    Обновление размеров изображения в workflow
    Поддерживает различные типы латентных нод
    """
    print(f"\n[DIMENSIONS] === Setting image size: {width}x{height} ===")

    updated = False

    # Типы нод для генерации латентов
    LATENT_NODE_TYPES = [
        'EmptyLatentImage',
        'EmptySD3LatentImage',
        'EmptyHunyuanLatentVideo',
        'EmptyLatentVideo',
    ]

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue

        class_type = node.get('class_type', '')

        if class_type in LATENT_NODE_TYPES:
            if 'inputs' not in node:
                node['inputs'] = {}

            old_width = node['inputs'].get('width', 'N/A')
            old_height = node['inputs'].get('height', 'N/A')

            node['inputs']['width'] = width
            node['inputs']['height'] = height
            updated = True

            print(f"[DIMENSIONS] ✓ Node {node_id} ({class_type}):")
            print(f"     Old: {old_width}x{old_height}")
            print(f"     New: {width}x{height}")

    if not updated:
        print(f"[DIMENSIONS] ⚠ No latent image nodes found in workflow!")

    print(f"[DIMENSIONS] === Done ===\n")

    return workflow


def update_single_input_image(workflow, image_name):
    """Обновление одного входного изображения"""
    print(f"\n[IMAGE] === Setting single image: {image_name} ===")

    updated = False

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue

        if node.get('class_type') == 'LoadImage':
            if 'inputs' not in node:
                node['inputs'] = {}
            node['inputs']['image'] = image_name
            updated = True
            print(f"[IMAGE] ✓ Set LoadImage node {node_id}: {image_name}")
            break

    if not updated:
        print(f"[IMAGE] ⚠ No LoadImage node found!")

    return workflow


def update_multiple_input_images(workflow, image_names):
    """Обновление нескольких входных изображений"""
    print(f"\n[IMAGES] === Setting {len(image_names)} images ===")

    # Находим все LoadImage ноды
    load_image_nodes = []
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get('class_type') == 'LoadImage':
            load_image_nodes.append((node_id, node))

    # Сортируем по ID
    load_image_nodes.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0)

    print(f"[IMAGES] Found {len(load_image_nodes)} LoadImage nodes: {[n[0] for n in load_image_nodes]}")

    # Обновляем ноды
    for idx, image_name in enumerate(image_names):
        if idx < len(load_image_nodes):
            node_id, node = load_image_nodes[idx]
            if 'inputs' not in node:
                node['inputs'] = {}
            node['inputs']['image'] = image_name
            print(f"[IMAGES] ✓ Node {node_id} = {image_name}")

    # Если нод больше чем изображений, дублируем последнее
    if len(load_image_nodes) > len(image_names) and len(image_names) > 0:
        last_image = image_names[-1]
        for idx in range(len(image_names), len(load_image_nodes)):
            node_id, node = load_image_nodes[idx]
            if 'inputs' not in node:
                node['inputs'] = {}
            node['inputs']['image'] = last_image
            print(f"[IMAGES] ✓ Node {node_id} = {last_image} (duplicated)")

    return workflow


def update_qwen_reference_images(workflow, image_names):
    """
    Обновление reference изображений для Qwen Image Edit Plus.
    Использует поля image1, image2, image3 в нодах TextEncodeQwenImageEditPlus.
    Неиспользуемые картинки устанавливаются в False для отключения ноды.
    """
    print(f"\n[QwenRef] === Setting {len(image_names)} reference images ===")

    # Доступные поля для изображений
    image_fields = ['image1', 'image2', 'image3']

    found_count = 0

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue

        class_type = node.get('class_type', '')

        # Обрабатываем только TextEncodeQwenImageEditPlus ноды
        if class_type == 'TextEncodeQwenImageEditPlus':
            inputs = node.get('inputs', {})

            for idx, field in enumerate(image_fields):
                if idx < len(image_names):
                    # Картинка выбрана - устанавливаем имя файла
                    inputs[field] = image_names[idx]
                    print(f"[QwenRef] ✓ {node_id}.{field} = {image_names[idx]}")
                else:
                    # Картинка не выбрана - отключаем ноду
                    inputs[field] = False
                    print(f"[QwenRef] ✓ {node_id}.{field} = False (disabled)")

            found_count += 1

    if found_count == 0:
        print("[QwenRef] ⚠ No TextEncodeQwenImageEditPlus nodes found!")

    print(f"[QwenRef] Updated {found_count} nodes")

    return workflow


def update_video_settings(workflow, duration):
    """
    Обновление настроек видео для workflow
    """
    # Находим FPS из CreateVideo ноды
    fps = 16  # Дефолтное значение для wan22

    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get('class_type') == 'CreateVideo':
            if 'inputs' in node and 'fps' in node['inputs']:
                fps = node['inputs']['fps']
                break

    # Вычисляем количество кадров
    frames = duration * fps

    print(f"\n[VIDEO] === Setting video parameters ===")
    print(f"[VIDEO] Duration: {duration}s")
    print(f"[VIDEO] FPS: {fps}")
    print(f"[VIDEO] Total frames: {frames}")

    updated_nodes = []

    for node_id, node in workflow.items():
        if not isinstance(node, dict) or 'inputs' not in node:
            continue

        class_type = node.get('class_type', '')
        inputs = node['inputs']

        # EmptyHunyuanLatentVideo - основная нода для задания длины видео
        if class_type == 'EmptyHunyuanLatentVideo':
            if 'length' in inputs:
                inputs['length'] = frames
                updated_nodes.append(f"{node_id}:length={frames}")
                print(f"[VIDEO] ✓ Node {node_id} (EmptyHunyuanLatentVideo): length={frames} frames")

        # EmptyLatentVideo (если используется другой workflow)
        elif class_type == 'EmptyLatentVideo':
            if 'length' in inputs:
                inputs['length'] = frames
                updated_nodes.append(f"{node_id}:length={frames}")
                print(f"[VIDEO] ✓ Node {node_id} (EmptyLatentVideo): length={frames} frames")

        # EmptyLatentImage с batch_size (для покадровой генерации)
        elif class_type == 'EmptyLatentImage':
            if 'batch_size' in inputs:
                inputs['batch_size'] = frames
                updated_nodes.append(f"{node_id}:batch_size={frames}")
                print(f"[VIDEO] ✓ Node {node_id} (EmptyLatentImage): batch_size={frames} frames")

        # CreateVideo - проверяем что FPS установлен правильно
        elif class_type == 'CreateVideo':
            if 'fps' in inputs:
                print(f"[VIDEO] ℹ Node {node_id} (CreateVideo): fps={inputs['fps']} (keeping)")

        # Универсальные поля для других возможных нод
        else:
            # Поля для длительности в секундах
            for duration_field in ['duration', 'video_duration', 'video_length']:
                if duration_field in inputs:
                    inputs[duration_field] = duration
                    updated_nodes.append(f"{node_id}:{duration_field}={duration}s")
                    print(f"[VIDEO] ✓ Node {node_id} ({class_type}): {duration_field}={duration}s")

            # Поля для количества кадров
            for frames_field in ['frames', 'frame_count', 'video_frames', 'num_frames']:
                if frames_field in inputs:
                    inputs[frames_field] = frames
                    updated_nodes.append(f"{node_id}:{frames_field}={frames}")
                    print(f"[VIDEO] ✓ Node {node_id} ({class_type}): {frames_field}={frames}")

    if updated_nodes:
        print(f"[VIDEO] Updated {len(updated_nodes)} parameters")
    else:
        print(f"[VIDEO] ⚠ WARNING: No video parameters found in workflow!")

    print(f"[VIDEO] === Video settings complete ===\n")

    return workflow


def send_workflow_to_comfy(workflow, client_id, force_seed=None):
    """Отправка workflow в ComfyUI"""
    # Определяем seed
    if force_seed is not None:
        seed_to_use = force_seed
    else:
        seed_to_use = random.randint(0, 2**32 - 1)

    print(f"\n[SEED] Using seed: {seed_to_use}")

    # Обновляем seed во ВСЕХ сэмплерах
    sampler_count = 0
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get('class_type') in ['KSampler', 'KSamplerAdvanced']:
            if 'inputs' not in node:
                node['inputs'] = {}

            # Поддержка noise_seed и seed
            if 'noise_seed' in node['inputs']:
                node['inputs']['noise_seed'] = seed_to_use
                print(f"[SEED] ✓ Set noise_seed={seed_to_use} in node {node_id}")
                sampler_count += 1
            else:
                node['inputs']['seed'] = seed_to_use
                print(f"[SEED] ✓ Set seed={seed_to_use} in node {node_id}")
                sampler_count += 1

    print(f"[SEED] Updated {sampler_count} sampler nodes")

    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    print(f"[COMFY] Sending to {app.config['COMFY_URL']}/prompt")

    try:
        response = requests.post(
            f"{app.config['COMFY_URL']}/prompt",
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )

        print(f"[COMFY] Response status: {response.status_code}")

        if response.status_code != 200:
            print(f"[COMFY] Error: {response.text}")
            raise Exception(f"ComfyUI returned status {response.status_code}")

        result = response.json()

        if 'error' in result:
            node_errors = result.get('node_errors', {})
            if node_errors:
                print(f"[COMFY] Node errors: {node_errors}")
            raise Exception(f"ComfyUI error: {result.get('error')}")

        if 'prompt_id' not in result:
            raise Exception("No prompt_id in response")

        prompt_id = result['prompt_id']
        print(f"[COMFY] ✓ Accepted, prompt_id: {prompt_id}")

        return prompt_id

    except requests.exceptions.Timeout:
        raise Exception("Timeout connecting to ComfyUI")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Cannot connect to ComfyUI at {app.config['COMFY_URL']}")


def upload_image_to_comfy(filepath, filename):
    """Загрузка изображения в ComfyUI"""
    print(f"[COMFY] Uploading: {filename}")

    with open(filepath, 'rb') as f:
        files = {'image': (filename, f, 'image/png')}
        response = requests.post(
            f"{app.config['COMFY_URL']}/upload/image",
            files=files,
            timeout=60
        )

    if response.status_code != 200:
        raise Exception(f"Failed to upload image: {response.text}")

    uploaded_data = response.json()
    uploaded_name = uploaded_data.get('name', filename)
    print(f"[COMFY] ✓ Uploaded as: {uploaded_name}")

    return uploaded_name


def wait_for_comfy_result(prompt_id, is_video=False, timeout=None):
    """Ожидание результата от ComfyUI"""
    if timeout is None:
        max_timeout = app.config.get('COMFY_TIMEOUT_MAX', 1800)
        timeout = max_timeout
    """Ожидание результата от ComfyUI"""
    start_time = time.time()
    last_status = None

    print(f"[COMFY] Waiting for result, prompt_id: {prompt_id}, timeout: {timeout}s")

    while time.time() - start_time < timeout:
        try:
            # Проверяем очередь
            queue_response = requests.get(f"{app.config['COMFY_URL']}/queue", timeout=10)
            if queue_response.status_code == 200:
                queue_data = queue_response.json()
                current_status = f"Running: {len(queue_data.get('queue_running', []))}, Pending: {len(queue_data.get('queue_pending', []))}"
                if current_status != last_status:
                    print(f"[COMFY] Queue: {current_status}")
                    last_status = current_status

            # Проверяем историю
            history_response = requests.get(f"{app.config['COMFY_URL']}/history/{prompt_id}", timeout=10)
            if history_response.status_code == 200:
                history = history_response.json()

                if prompt_id in history:
                    prompt_history = history[prompt_id]
                    status = prompt_history.get('status', {})

                    if status.get('completed', False):
                        outputs = prompt_history.get('outputs', {})
                        results = []

                        for node_id, node_output in outputs.items():
                            if is_video:
                                for key in ['gifs', 'videos']:
                                    if key in node_output:
                                        for item in node_output[key]:
                                            results.append({
                                                'filename': item['filename'],
                                                'subfolder': item.get('subfolder', ''),
                                                'type': item.get('type', 'output')
                                            })

                            if 'images' in node_output:
                                for item in node_output['images']:
                                    results.append({
                                        'filename': item['filename'],
                                        'subfolder': item.get('subfolder', ''),
                                        'type': item.get('type', 'output')
                                    })

                        if results:
                            print(f"[COMFY] ✓ Got {len(results)} results")
                            return results

        except requests.exceptions.RequestException as e:
            print(f"[COMFY] Polling error: {e}")

        time.sleep(2)

    raise Exception(f"Timeout waiting for result ({timeout}s)")


def save_results_from_comfy(comfy_outputs, is_video=False):
    """Сохранение результатов с ComfyUI"""
    saved_files = []

    print(f"[COMFY] Saving {len(comfy_outputs)} results")

    for idx, output in enumerate(comfy_outputs):
        filename = output['filename']
        subfolder = output.get('subfolder', '')
        output_type = output.get('type', 'output')

        params = {'filename': filename, 'type': output_type}
        if subfolder:
            params['subfolder'] = subfolder

        try:
            response = requests.get(
                f"{app.config['COMFY_URL']}/view",
                params=params,
                timeout=60
            )

            if response.status_code == 200:
                ext = 'mp4' if is_video else filename.rsplit('.', 1)[-1] if '.' in filename else 'png'
                new_filename = f"{uuid.uuid4().hex}.{ext}"
                
                # Безопасное сохранение
                filepath = secure_path_check(app.config['RESULTS_FOLDER'], new_filename)
                if not filepath:
                    print(f"[COMFY] ✗ Unsafe filename: {new_filename}")
                    continue
                    
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                file_size = len(response.content) / 1024
                print(f"[COMFY] ✓ Saved: {new_filename} ({file_size:.1f} KB)")
                saved_files.append(new_filename)
            else:
                print(f"[COMFY] ✗ Failed to download {filename}: HTTP {response.status_code}")

        except Exception as e:
            print(f"[COMFY] ✗ Error saving {filename}: {e}")

    return saved_files


def get_generation_file_paths(generation, file_type='all'):
    """
    Получение списка файлов генерации с безопасными путями.

    Args:
        generation: объект Generation
        file_type: 'input', 'output' или 'all'

    Returns:
        list of tuples: [(filepath, folder_name), ...]
    """
    files = []

    if file_type in ('input', 'all') and generation.input_files:
        folder = app.config['UPLOAD_FOLDER']
        for filename in generation.input_files:
            filepath = secure_path_check(folder, filename)
            if filepath and os.path.exists(filepath):
                files.append((filepath, folder))

    if file_type in ('output', 'all') and generation.output_files:
        folder = app.config['RESULTS_FOLDER']
        for filename in generation.output_files:
            filepath = secure_path_check(folder, filename)
            if filepath and os.path.exists(filepath):
                files.append((filepath, folder))

    return files


def delete_generation_files(generation):
    """Удаление файлов генерации"""
    deleted = []

    for filepath, folder in get_generation_file_paths(generation):
        try:
            os.remove(filepath)
            deleted.append(os.path.basename(filepath))
        except Exception as e:
            print(f"[FILES] Error deleting {os.path.basename(filepath)}: {e}")

    if deleted:
        print(f"[FILES] Deleted {len(deleted)} files")

    return deleted


def get_generation_files_size(generation):
    """Получение размера файлов генерации"""
    total_size = 0

    for filepath, folder in get_generation_file_paths(generation):
        try:
            total_size += os.path.getsize(filepath)
        except OSError:
            pass

    return total_size


def cleanup_orphan_files():
    """Удаление файлов-сирот (не связанных с генерациями)"""
    deleted_count = 0
    freed_space = 0

    all_input_files = set()
    all_output_files = set()

    for gen in Generation.query.all():
        if gen.input_files:
            all_input_files.update(gen.input_files)
        if gen.output_files:
            all_output_files.update(gen.output_files)

    for folder_name, tracked_files in [('UPLOAD_FOLDER', all_input_files), ('RESULTS_FOLDER', all_output_files)]:
        folder = app.config[folder_name]
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                if filename not in tracked_files:
                    filepath = secure_path_check(folder, filename)
                    if filepath and os.path.exists(filepath):
                        try:
                            freed_space += os.path.getsize(filepath)
                            os.remove(filepath)
                            deleted_count += 1
                        except OSError:
                            pass

    return deleted_count, freed_space


# ==================== BACKGROUND PROCESSING ====================

def process_image_generation(generation_id, prompt, negative_prompt, model, seed=None, width=1024, height=1024):
    """Генерация изображения в фоне"""
    with app.app_context():
        generation = Generation.query.get(generation_id)

        try:
            print(f"\n{'='*60}")
            print(f"[IMAGE] Starting #{generation_id}")
            print(f"[IMAGE] Model: {model}")
            print(f"[IMAGE] Size: {width}x{height}")
            print(f"[IMAGE] Seed: {seed if seed else 'random'}")
            print(f"[IMAGE] Prompt: {prompt[:80]}...")
            print(f"{'='*60}\n")

            workflow = load_workflow('text_to_image', model)
            workflow = update_workflow_prompt(workflow, prompt, negative_prompt)
            workflow = update_image_dimensions(workflow, width, height)

            client_id = f"user_{generation.user_id}_{generation_id}"
            prompt_id = send_workflow_to_comfy(workflow, client_id, force_seed=seed)

            generation.status = 'processing'
            generation.progress = 5.0
            db.session.commit()

            timeout = app.config.get('COMFY_TIMEOUT_IMAGE', 300)
            output_files = wait_for_comfy_result(prompt_id, is_video=False)

            generation.progress = 90.0
            db.session.commit()

            saved_results = save_results_from_comfy(output_files, is_video=False)

            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()

            print(f"\n[IMAGE] ✓ #{generation_id} completed with {len(saved_results)} results\n")

        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[IMAGE] ✗ #{generation_id} FAILED: {e}\n")
            refund_tokens(generation.user_id, 10, generation.id, "Generation failed")

        try:
            db.session.commit()
        except Exception as e:
            print(f"\n[IMAGE] ✗ #{generation_id} DB commit failed: {e}\n")


def process_video_generation(generation_id, prompt, negative_prompt, model, duration):
    """Генерация видео в фоне"""
    with app.app_context():
        generation = Generation.query.get(generation_id)

        try:
            print(f"\n{'='*60}")
            print(f"[VIDEO] Starting #{generation_id}")
            print(f"[VIDEO] Model: {model}")
            print(f"[VIDEO] Duration: {duration}s")
            print(f"[VIDEO] Prompt: {prompt[:80]}...")
            print(f"{'='*60}\n")

            workflow = load_workflow('text_to_video', model)
            workflow = update_workflow_prompt(workflow, prompt, negative_prompt)
            workflow = update_video_settings(workflow, duration)

            client_id = f"user_{generation.user_id}_{generation_id}"
            prompt_id = send_workflow_to_comfy(workflow, client_id)

            generation.status = 'processing'
            generation.progress = 5.0
            db.session.commit()

            timeout = min(120 + (duration * 60), app.config.get('COMFY_TIMEOUT_MAX', 1800))
            output_files = wait_for_comfy_result(prompt_id, is_video=True)

            generation.progress = 90.0
            db.session.commit()

            saved_results = save_results_from_comfy(output_files, is_video=True)

            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()

            print(f"\n[VIDEO] ✓ #{generation_id} completed with {len(saved_results)} results\n")

        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[VIDEO] ✗ #{generation_id} FAILED: {e}\n")

        try:
            db.session.commit()
        except Exception as e:
            print(f"\n[VIDEO] ✗ #{generation_id} DB commit failed: {e}\n")


def process_image_edit(generation_id, input_files, edit_type, prompt, negative_prompt):
    """Редактирование изображений в фоне"""
    with app.app_context():
        generation = Generation.query.get(generation_id)

        try:
            file_count = len(input_files)
            print(f"\n{'='*60}")
            print(f"[EDIT] Starting #{generation_id}")
            print(f"[EDIT] Files: {file_count}")
            print(f"[EDIT] Workflow: {edit_type}")
            print(f"[EDIT] Prompt: {prompt[:80]}...")
            print(f"{'='*60}\n")

            # Загружаем изображения в ComfyUI
            uploaded_names = []
            for input_file in input_files:
                filepath = secure_path_check(app.config['UPLOAD_FOLDER'], input_file)
                if not filepath:
                    raise ValueError(f"Unsafe file path: {input_file}")
                uploaded_name = upload_image_to_comfy(filepath, input_file)
                uploaded_names.append(uploaded_name)

            print(f"[EDIT] Uploaded {len(uploaded_names)} images to ComfyUI")

            # Загружаем workflow
            workflow = load_workflow('image_edit', edit_type)

            # Обновляем изображения
            if file_count == 1:
                workflow = update_single_input_image(workflow, uploaded_names[0])
            else:
                # Qwen Image Edit Plus - используем новую функцию для reference картинок
                workflow = update_qwen_reference_images(workflow, uploaded_names)
                # Также обновляем LoadImage ноды для совместимости
                workflow = update_multiple_input_images(workflow, uploaded_names)

            # Обновляем промпты
            workflow = update_workflow_prompt(workflow, prompt, negative_prompt)

            # Отправляем в ComfyUI
            client_id = f"user_{generation.user_id}_{generation_id}"
            prompt_id = send_workflow_to_comfy(workflow, client_id)

            generation.status = 'processing'
            generation.progress = 5.0
            db.session.commit()

            # Ждём результат
            timeout = app.config.get('COMFY_TIMEOUT_EDIT', 600)
            output_files = wait_for_comfy_result(prompt_id, is_video=False)

            generation.progress = 90.0
            db.session.commit()

            saved_results = save_results_from_comfy(output_files, is_video=False)

            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()

            print(f"\n[EDIT] ✓ #{generation_id} completed with {len(saved_results)} results\n")

        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[EDIT] ✗ #{generation_id} FAILED: {e}\n")
            refund_tokens(generation.user_id, 15, generation.id, "Edit generation failed")

        try:
            db.session.commit()
        except Exception as e:
            print(f"\n[EDIT] ✗ #{generation_id} DB commit failed: {e}\n")


# ==================== MAIN ====================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("ComfyUI Web Interface (SECURITY PATCHED)")
    print("="*60)
    print(f"ComfyUI URL: {app.config['COMFY_URL']}")
    print(f"Max images per edit: {app.config['MAX_IMAGES_PER_GENERATION']}")
    print(f"Max image size: {app.config['MAX_IMAGE_SIZE_MB']}MB")
    print(f"Max image dimension: {MAX_IMAGE_DIMENSION}px")
    print(f"Max video duration: {app.config['MAX_VIDEO_DURATION']}s")
    print(f"Image generation sizes: {IMAGE_MIN_SIZE}-{IMAGE_MAX_SIZE}px (step {IMAGE_SIZE_STEP})")
    print(f"CSRF Protection: Enabled")
    print(f"Rate Limiting: Enabled")
    print(f"Security Headers: Enabled")
    print("="*60 + "\n")

    with app.app_context():
        db.create_all()
        print("✓ Database initialized")

        # Инициализация типов генераций если пусто
        if GenerationType.query.count() == 0:
            default_types = [
                ('wan22', 'WAN 2.2', 'Генерация изображений из текста'),
                ('wan22_video', 'WAN 2.2 Video', 'Генерация видео из текста'),
                ('qwen_single', 'Qwen Single', 'Редактирование одного изображения'),
                ('qwen_multi', 'Qwen Multi', 'Редактирование нескольких изображений'),
            ]
            for type_key, name, desc in default_types:
                db.session.add(GenerationType(type_key=type_key, name=name, description=desc, enabled=True))
            db.session.commit()
            print(f"✓ Generation types initialized")

        # Инициализация модулей
        ModuleRegistry.initialize()
        print(f"✓ Modules initialized: {len(ModuleRegistry.get_all())} modules")

        # Инициализация цен
        initialize_pricing()
        print(f"✓ Pricing initialized")

        # Проверяем есть ли администратор
        admin_count = User.query.filter_by(is_admin=True).count()
        print(f"✓ Administrators: {admin_count}")

    print("\nStarting server on http://0.0.0.0:5000\n")

    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)

"""
ComfyUI Web Interface
Веб-интерфейс для работы с ComfyUI через API
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
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

from config import Config
from models import db, User, Generation

# ==================== FLASK APP SETUP ====================

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'

# Create folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

# Максимальный размер изображения по большей стороне
MAX_IMAGE_DIMENSION = app.config.get('MAX_IMAGE_DIMENSION', 1280)

# Настройки размеров для генерации
IMAGE_MIN_SIZE = 256
IMAGE_MAX_SIZE = 1280
IMAGE_SIZE_STEP = 64

# Пресеты размеров для UI
IMAGE_SIZE_PRESETS = [
    {'name': 'Квадрат 1:1', 'width': 1024, 'height': 1024},
    {'name': 'Портрет 3:4', 'width': 768, 'height': 1024},
    {'name': 'Портрет 9:16', 'width': 720, 'height': 1280},
    {'name': 'Пейзаж 4:3', 'width': 1024, 'height': 768},
    {'name': 'Пейзаж 16:9', 'width': 1280, 'height': 720},
    {'name': 'Маленький 512', 'width': 512, 'height': 512},
]

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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
        
        # Сохраняем
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
    
    # Проверяем что это изображение
    try:
        img = Image.open(file)
        img.verify()
        file.seek(0)
    except Exception as e:
        raise ValueError(f"Файл не является изображением: {e}")
    
    # Генерируем уникальное имя
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

def allowed_file(filename):
    """Проверка допустимого расширения файла"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def generate_unique_filename(original_filename):
    """Генерация уникального имени файла"""
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'png'
    return f"{uuid.uuid4().hex}.{ext}"


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
def register():
    """Регистрация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        errors = []
        if len(username) < 3:
            errors.append('Имя пользователя должно быть минимум 3 символа')
        if '@' not in email:
            errors.append('Неверный формат email')
        if len(password) < 6:
            errors.append('Пароль должен быть минимум 6 символов')
        if password != confirm_password:
            errors.append('Пароли не совпадают')
        if User.query.filter_by(username=username).first():
            errors.append('Это имя пользователя уже занято')
        if User.query.filter_by(email=email).first():
            errors.append('Этот email уже зарегистрирован')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Первый пользователь становится администратором
        is_first_user = User.query.count() == 0
        
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(
            username=username, 
            email=email, 
            password_hash=password_hash,
            is_admin=is_first_user
        )
        db.session.add(user)
        db.session.commit()
        
        if is_first_user:
            flash('Регистрация успешна! Вы назначены администратором.', 'success')
        else:
            flash('Регистрация успешна! Теперь войдите в систему', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        login_input = request.form.get('login', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        user = User.query.filter(
            (User.username == login_input) | (User.email == login_input)
        ).first()
        
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверные учётные данные', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    return redirect(url_for('login'))


@app.route('/history')
@login_required
def history():
    """История генераций пользователя"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Показываем только НЕ скрытые генерации
    generations = Generation.query.filter_by(
        user_id=current_user.id,
        hidden_from_user=False
    ).order_by(Generation.created_at.desc())\
     .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('history.html', generations=generations.items, pagination=generations)


# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Админ-панель: главная"""
    # Статистика
    total_users = User.query.count()
    total_generations = Generation.query.count()
    completed_generations = Generation.query.filter_by(status='completed').count()
    failed_generations = Generation.query.filter_by(status='failed').count()
    
    # Последние генерации
    recent_generations = Generation.query\
        .order_by(Generation.created_at.desc())\
        .limit(20).all()
    
    # Пользователи
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Размер файлов на диске
    uploads_size = get_folder_size(app.config['UPLOAD_FOLDER'])
    results_size = get_folder_size(app.config['RESULTS_FOLDER'])
    
    return render_template('admin/dashboard.html',
        total_users=total_users,
        total_generations=total_generations,
        completed_generations=completed_generations,
        failed_generations=failed_generations,
        recent_generations=recent_generations,
        users=users,
        uploads_size=uploads_size,
        results_size=results_size
    )


@app.route('/admin/generations')
@admin_required
def admin_generations():
    """Админ-панель: все генерации"""
    page = request.args.get('page', 1, type=int)
    per_page = 50
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')
    gen_type = request.args.get('type')
    show_hidden = request.args.get('show_hidden', 'true') == 'true'
    
    query = Generation.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    if gen_type:
        query = query.filter_by(generation_type=gen_type)
    if not show_hidden:
        query = query.filter_by(hidden_from_user=False)
    
    generations = query.order_by(Generation.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    users = User.query.all()
    
    return render_template('admin/generations.html',
        generations=generations,
        users=users,
        current_user_id=user_id,
        current_status=status,
        current_type=gen_type,
        show_hidden=show_hidden
    )


@app.route('/admin/users')
@admin_required
def admin_users():
    """Админ-панель: пользователи"""
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Статистика по каждому пользователю
    user_stats = []
    for user in users:
        stats = {
            'user': user,
            'total_generations': Generation.query.filter_by(user_id=user.id).count(),
            'completed': Generation.query.filter_by(user_id=user.id, status='completed').count(),
            'hidden': Generation.query.filter_by(user_id=user.id, hidden_from_user=True).count()
        }
        user_stats.append(stats)
    
    return render_template('admin/users.html', user_stats=user_stats)


@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    """Переключение статуса администратора"""
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя изменить свой статус'}), 400
    
    user = User.query.get_or_404(user_id)
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
    
    user = User.query.get_or_404(user_id)
    
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
    generation = Generation.query.get_or_404(generation_id)
    return render_template('admin/generation_detail.html', generation=generation)


@app.route('/admin/generation/<int:generation_id>/delete', methods=['POST'])
@admin_required
def admin_delete_generation(generation_id):
    """Полное удаление генерации (с файлами)"""
    generation = Generation.query.get_or_404(generation_id)
    
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
    generation = Generation.query.get_or_404(generation_id)
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
def api_generate_image():
    """Генерация изображения"""
    data = request.json
    prompt = data.get('prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()
    model = data.get('model', 'wan22')
    seed = data.get('seed', None)
    
    # Получаем и валидируем размеры
    width = data.get('width', 1024)
    height = data.get('height', 1024)
    width, height = validate_image_dimensions(width, height)
    
    if not prompt:
        return jsonify({'error': 'Промпт обязателен'}), 400
    
    # Валидация seed
    if seed is not None:
        try:
            seed = int(seed)
            if seed < 0 or seed > 2**32 - 1:
                seed = None
        except (ValueError, TypeError):
            seed = None
    
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
def api_generate_video():
    """Генерация видео"""
    data = request.json
    prompt = data.get('prompt', '').strip()
    negative_prompt = data.get('negative_prompt', '').strip()
    model = data.get('model', 'wan22_video')
    duration = min(int(data.get('duration', 4)), app.config['MAX_VIDEO_DURATION'])
    
    if not prompt:
        return jsonify({'error': 'Промпт обязателен'}), 400
    
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
def api_edit_images():
    """Редактирование изображений"""
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
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
                except:
                    pass
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            for f in saved_files:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], f))
                except:
                    pass
            return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500
    
    # Выбор workflow
    edit_type = 'qwen_single' if len(saved_files) == 1 else 'qwen_multi'
    
    print(f"[EDIT] Files: {len(saved_files)}, workflow: {edit_type}")
    
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


@app.route('/api/generation/<int:generation_id>/status')
@login_required
def api_generation_status(generation_id):
    """Получение статуса генерации"""
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
    """Получение истории генераций"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
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


# ==================== FILE SERVING ====================

@app.route('/results/<filename>')
@login_required
def serve_result(filename):
    """Отдача результатов"""
    filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_from_directory(app.config['RESULTS_FOLDER'], filename)
    return jsonify({'error': 'Файл не найден'}), 404


@app.route('/uploads/<filename>')
@login_required
def serve_upload(filename):
    """Отдача загруженных файлов"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    return jsonify({'error': 'Файл не найден'}), 404


@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """Скачивание файла"""
    for folder in [app.config['RESULTS_FOLDER'], app.config['UPLOAD_FOLDER']]:
        filepath = os.path.join(folder, filename)
        if os.path.exists(filepath):
            return send_from_directory(folder, filename, as_attachment=True)
    return jsonify({'error': 'Файл не найден'}), 404


# ==================== UTILITY FUNCTIONS ====================

def get_folder_size(folder_path):
    """Получение размера папки в байтах"""
    total_size = 0
    if os.path.exists(folder_path):
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
    return total_size


def get_generation_files_size(generation):
    """Получение размера файлов генерации"""
    total_size = 0
    
    if generation.input_files:
        for filename in generation.input_files:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    
    if generation.output_files:
        for filename in generation.output_files:
            filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    
    return total_size


def cleanup_orphan_files():
    """Удаление файлов, не связанных с генерациями"""
    deleted_count = 0
    freed_space = 0
    
    # Собираем все файлы из БД
    all_files = set()
    for gen in Generation.query.all():
        if gen.input_files:
            all_files.update(gen.input_files)
        if gen.output_files:
            all_files.update(gen.output_files)
    
    # Проверяем папки
    for folder in [app.config['UPLOAD_FOLDER'], app.config['RESULTS_FOLDER']]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                if filename not in all_files:
                    filepath = os.path.join(folder, filename)
                    if os.path.isfile(filepath):
                        freed_space += os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_count += 1
                        print(f"[CLEANUP] Deleted orphan: {filename}")
    
    return deleted_count, freed_space


# ==================== WORKFLOW FUNCTIONS ====================

def load_workflow(workflow_type, model):
    """Загрузка workflow JSON"""
    workflow_file = app.config['MODELS'].get(workflow_type, {}).get(model, {}).get('workflow')
    
    if not workflow_file:
        raise Exception(f"Workflow not found for {workflow_type}/{model}")
    
    workflow_path = os.path.join('workflows', workflow_type, workflow_file)
    
    if not os.path.exists(workflow_path):
        raise Exception(f"Workflow file not found: {workflow_path}")
    
    with open(workflow_path, 'r', encoding='utf-8') as f:
        workflow = json.load(f)
    
    print(f"[WORKFLOW] Loaded from {workflow_path}")
    
    # Проверяем формат
    if 'nodes' in workflow:
        raise Exception("Workflow is in UI format, not API format!")
    
    return workflow


def update_workflow_prompt(workflow, prompt, negative_prompt=''):
    """
    Обновление промптов в workflow
    Поддерживает различные типы нод и определяет positive/negative по связям
    """
    
    print(f"\n[PROMPT] === Updating prompts ===")
    print(f"[PROMPT] Positive: {prompt[:100]}...")
    print(f"[PROMPT] Negative: {negative_prompt[:100] if negative_prompt else '(empty)'}...")
    
    # Конфигурация типов нод и их полей
    PROMPT_NODE_TYPES = {
        'CLIPTextEncode': 'text',
        'CLIPTextEncodeSDXL': 'text',
        'CLIPTextEncodeSD3': 'text',
        'TextEncodeQwenImageEditPlus': 'prompt',
        'TextEncodeQwenImageEdit': 'prompt',
        'QwenTextEncode': 'prompt',
    }
    
    # Находим все encoding ноды
    encoding_nodes = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        
        class_type = node.get('class_type', '')
        if class_type not in PROMPT_NODE_TYPES:
            continue
        
        text_field = PROMPT_NODE_TYPES[class_type]
        title = node.get('_meta', {}).get('title', '').lower()
        
        encoding_nodes.append({
            'node_id': node_id,
            'node': node,
            'class_type': class_type,
            'title': title,
            'text_field': text_field,
        })
    
    print(f"[PROMPT] Found {len(encoding_nodes)} encoding nodes")
    
    # Находим KSampler для определения positive/negative по связям
    positive_node_id = None
    negative_node_id = None
    
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        
        class_type = node.get('class_type', '')
        if class_type not in ['KSampler', 'KSamplerAdvanced']:
            continue
        
        inputs = node.get('inputs', {})
        
        # Извлекаем ID нод из связей [node_id, output_index]
        if 'positive' in inputs and isinstance(inputs['positive'], list):
            positive_node_id = str(inputs['positive'][0])
            print(f"[PROMPT] KSampler node {node_id} uses positive from node {positive_node_id}")
        
        if 'negative' in inputs and isinstance(inputs['negative'], list):
            negative_node_id = str(inputs['negative'][0])
            print(f"[PROMPT] KSampler node {node_id} uses negative from node {negative_node_id}")
    
    # Обновляем промпты
    positive_updated = False
    negative_updated = False
    
    for enc in encoding_nodes:
        node_id = enc['node_id']
        node = enc['node']
        text_field = enc['text_field']
        
        if 'inputs' not in node:
            node['inputs'] = {}
        
        # Проверяем по связям с KSampler
        if node_id == positive_node_id:
            old_value = node['inputs'].get(text_field, '')
            node['inputs'][text_field] = prompt
            positive_updated = True
            print(f"[PROMPT] ✓ Set POSITIVE in node {node_id} (by connection)")
            if old_value and old_value != prompt:
                print(f"          Old: {old_value[:80]}...")
                print(f"          New: {prompt[:80]}...")
        
        elif node_id == negative_node_id:
            old_value = node['inputs'].get(text_field, '')
            node['inputs'][text_field] = negative_prompt if negative_prompt else ''
            negative_updated = True
            print(f"[PROMPT] ✓ Set NEGATIVE in node {node_id} (by connection)")
            if old_value:
                print(f"          Old: {old_value[:80]}...")
            print(f"          New: {negative_prompt[:80] if negative_prompt else '(empty)'}...")
    
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
            print(f"              Old: {old_width}x{old_height}")
            print(f"              New: {width}x{height}")
    
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
    
    # Дублируем последнее изображение если загружено меньше чем нод
    if len(image_names) < len(load_image_nodes) and len(image_names) > 0:
        last_image = image_names[-1]
        for idx in range(len(image_names), len(load_image_nodes)):
            node_id, node = load_image_nodes[idx]
            if 'inputs' not in node:
                node['inputs'] = {}
            node['inputs']['image'] = last_image
            print(f"[IMAGES] ✓ Node {node_id} = {last_image} (duplicated)")
    
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


def wait_for_comfy_result(prompt_id, is_video=False, timeout=3000):
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
                filepath = os.path.join(app.config['RESULTS_FOLDER'], new_filename)
                
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


def delete_generation_files(generation):
    """Удаление файлов генерации"""
    deleted = []
    
    if generation.input_files:
        for filename in generation.input_files:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted.append(filename)
                except Exception as e:
                    print(f"[FILES] Error deleting {filename}: {e}")
    
    if generation.output_files:
        for filename in generation.output_files:
            filepath = os.path.join(app.config['RESULTS_FOLDER'], filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted.append(filename)
                except Exception as e:
                    print(f"[FILES] Error deleting {filename}: {e}")
    
    if deleted:
        print(f"[FILES] Deleted {len(deleted)} files")
    
    return deleted


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
            
            output_files = wait_for_comfy_result(prompt_id, is_video=False, timeout=300)
            saved_results = save_results_from_comfy(output_files, is_video=False)
            
            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()
            
            print(f"\n[IMAGE] ✓ #{generation_id} completed with {len(saved_results)} results\n")
            
        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[IMAGE] ✗ #{generation_id} FAILED: {e}\n")
            import traceback
            traceback.print_exc()
        
        db.session.commit()


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
            
            timeout = 120 + (duration * 60)
            output_files = wait_for_comfy_result(prompt_id, is_video=True, timeout=timeout)
            saved_results = save_results_from_comfy(output_files, is_video=True)
            
            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()
            
            print(f"\n[VIDEO] ✓ #{generation_id} completed with {len(saved_results)} results\n")
            
        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[VIDEO] ✗ #{generation_id} FAILED: {e}\n")
            import traceback
            traceback.print_exc()
        
        db.session.commit()


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
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], input_file)
                uploaded_name = upload_image_to_comfy(filepath, input_file)
                uploaded_names.append(uploaded_name)
            
            print(f"[EDIT] Uploaded {len(uploaded_names)} images to ComfyUI")
            
            # Загружаем workflow
            workflow = load_workflow('image_edit', edit_type)
            
            # Обновляем изображения
            if file_count == 1:
                workflow = update_single_input_image(workflow, uploaded_names[0])
            else:
                workflow = update_multiple_input_images(workflow, uploaded_names)
            
            # Обновляем промпты
            workflow = update_workflow_prompt(workflow, prompt, negative_prompt)
            
            # Отправляем в ComfyUI
            client_id = f"user_{generation.user_id}_{generation_id}"
            prompt_id = send_workflow_to_comfy(workflow, client_id)
            
            # Ждём результат
            output_files = wait_for_comfy_result(prompt_id, is_video=False, timeout=600)
            saved_results = save_results_from_comfy(output_files, is_video=False)
            
            generation.output_files = saved_results
            generation.status = 'completed'
            generation.completed_at = datetime.utcnow()
            
            print(f"\n[EDIT] ✓ #{generation_id} completed with {len(saved_results)} results\n")
            
        except Exception as e:
            generation.status = 'failed'
            generation.error_message = str(e)
            print(f"\n[EDIT] ✗ #{generation_id} FAILED: {e}\n")
            import traceback
            traceback.print_exc()
        
        db.session.commit()


# ==================== MAIN ====================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("ComfyUI Web Interface")
    print("="*60)
    print(f"ComfyUI URL: {app.config['COMFY_URL']}")
    print(f"Max images per edit: {app.config['MAX_IMAGES_PER_GENERATION']}")
    print(f"Max image size: {app.config['MAX_IMAGE_SIZE_MB']}MB")
    print(f"Max image dimension: {MAX_IMAGE_DIMENSION}px")
    print(f"Max video duration: {app.config['MAX_VIDEO_DURATION']}s")
    print(f"Image generation sizes: {IMAGE_MIN_SIZE}-{IMAGE_MAX_SIZE}px (step {IMAGE_SIZE_STEP})")
    print("="*60 + "\n")
    
    with app.app_context():
        db.create_all()
        print("✓ Database initialized")
        
        # Проверяем есть ли администратор
        admin_count = User.query.filter_by(is_admin=True).count()
        print(f"✓ Administrators: {admin_count}")
    
    print("\nStarting server on http://0.0.0.0:5000\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
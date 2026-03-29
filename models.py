from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    generations = db.relationship('Generation', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'


class Generation(db.Model):
    """Модель генерации"""
    __tablename__ = 'generations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    generation_type = db.Column(db.String(50), nullable=False)  # text-to-image, text-to-video, image-edit
    model_used = db.Column(db.String(100))
    prompt = db.Column(db.Text)
    negative_prompt = db.Column(db.Text)
    input_files = db.Column(db.JSON)  # Список входных файлов
    output_files = db.Column(db.JSON)  # Список выходных файлов
    settings = db.Column(db.JSON)  # Дополнительные настройки
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Флаг: скрыто ли от пользователя (при "очистке" истории)
    hidden_from_user = db.Column(db.Boolean, default=False, nullable=False)
    
    def __repr__(self):
        return f'<Generation {self.id} by User {self.user_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'generation_type': self.generation_type,
            'model_used': self.model_used,
            'prompt': self.prompt,
            'negative_prompt': self.negative_prompt,
            'input_files': self.input_files or [],
            'output_files': self.output_files or [],
            'settings': self.settings or {},
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'hidden_from_user': self.hidden_from_user
        }
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class GenerationType(db.Model):
    """Типы генераций - управление доступностью"""
    __tablename__ = 'generation_types'

    id = db.Column(db.Integer, primary_key=True)
    type_key = db.Column(db.String(50), unique=True, nullable=False)  # wan22, wan22_video, qwen_single, qwen_multi
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<GenerationType {self.type_key}: {"enabled" if self.enabled else "disabled"}>'


class User(UserMixin, db.Model):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    theme = db.Column(db.String(20), default='light')  # 'light' or 'dark'
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


class TokenBalance(db.Model):
    """Баланс токенов пользователя"""
    __tablename__ = 'token_balances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('token_balance', uselist=False))

    def __repr__(self):
        return f'<TokenBalance user:{self.user_id} balance:{self.balance}>'


class TokenTransaction(db.Model):
    """История транзакций токенов"""
    __tablename__ = 'token_transactions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Положительное = начисление, отрицательное = списание
    transaction_type = db.Column(db.String(50), nullable=False)  # generation, admin_add, rule_bonus, refund
    description = db.Column(db.String(255))
    generation_id = db.Column(db.Integer, db.ForeignKey('generations.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('token_transactions', lazy='dynamic', order_by=desc(TokenTransaction.created_at)))
    generation = db.relationship('Generation', backref=db.backref('token_transaction', uselist=False))

    def __repr__(self):
        return f'<TokenTransaction user:{self.user_id} amount:{self.amount} type:{self.transaction_type}>'


class Pricing(db.Model):
    """Стоимость генераций по модулям"""
    __tablename__ = 'pricing'

    id = db.Column(db.Integer, primary_key=True)
    module_key = db.Column(db.String(50), nullable=False, unique=True)  # wan22, wan22_video, qwen_single, qwen_multi
    base_cost = db.Column(db.Integer, default=10, nullable=False)  # Базовая стоимость
    cost_per_width = db.Column(db.Integer, default=0)  # За каждые 256 пикселей ширины
    cost_per_height = db.Column(db.Integer, default=0)  # За каждые 256 пикселей высоты
    cost_per_second = db.Column(db.Integer, default=0)  # За секунду видео

    def calculate_cost(self, width=0, height=0, duration=0):
        """Рассчитать стоимость генерации"""
        cost = self.base_cost
        if self.cost_per_width and width:
            cost += (width // 256) * self.cost_per_width
        if self.cost_per_height and height:
            cost += (height // 256) * self.cost_per_height
        if self.cost_per_second and duration:
            cost += duration * self.cost_per_second
        return max(cost, 1)  # Минимум 1 токен

    def __repr__(self):
        return f'<Pricing {self.module_key} cost:{self.base_cost}>'


class TokenRule(db.Model):
    """Правила начисления токенов"""
    __tablename__ = 'token_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rule_type = db.Column(db.String(50), nullable=False)  # daily, weekly, first_generation, referral
    amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    max_uses = db.Column(db.Integer, default=None)  # Максимальное использование (None = безлимит)
    uses_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TokenRule {self.name} amount:{self.amount}>'


class UserPriority:
    """Константы приоритетов пользователей"""
    ADMIN = 100
    LOW = 25
    NORMAL = 50
    HIGH = 75

    @staticmethod
    def get_name(value):
        names = {100: 'Admin', 75: 'High', 50: 'Normal', 25: 'Low'}
        return names.get(value, 'Normal')


# Добавим поле приоритета в User
User.priority = db.Column(db.Integer, default=50, nullable=False)  # 25/50/75/100
User.token_period = db.Column(db.String(20), default='monthly')  # daily, weekly, monthly
User.last_token_reset = db.Column(db.DateTime, default=datetime.utcnow)
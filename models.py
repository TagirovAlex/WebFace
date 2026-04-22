from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import desc

db = SQLAlchemy()


class GenerationType(db.Model):
    """Типы генераций - управление доступностью"""
    __tablename__ = 'generation_types'

    id = db.Column(db.Integer, primary_key=True)
    type_key = db.Column(db.String(50), unique=True, nullable=False)
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
    theme = db.Column(db.String(20), default='light')
    color_scheme = db.Column(db.String(20), default='default')
    telegram_chat_id = db.Column(db.String(20))
    notify_on_complete = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    priority = db.Column(db.Integer, default=50, nullable=False)
    token_period = db.Column(db.String(20), default='monthly')
    last_token_reset = db.Column(db.DateTime, default=datetime.utcnow)

    generations = db.relationship('Generation', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'


class Generation(db.Model):
    """Модель генерации"""
    __tablename__ = 'generations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    generation_type = db.Column(db.String(50), nullable=False)
    model_used = db.Column(db.String(100))
    prompt = db.Column(db.Text)
    negative_prompt = db.Column(db.Text)
    input_files = db.Column(db.JSON)
    output_files = db.Column(db.JSON)
    settings = db.Column(db.JSON)
    status = db.Column(db.String(20), default='pending')
    progress = db.Column(db.Float, default=0.0)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    hidden_from_user = db.Column(db.Boolean, default=False, nullable=False)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    tags = db.Column(db.String(500))

    favorited_by = db.relationship('Favorite', backref='generation', lazy='dynamic')


class Favorite(db.Model):
    """Избранное пользователя"""
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    generation_id = db.Column(db.Integer, db.ForeignKey('generations.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'generation_id', name='uq_user_generation'),
    )

    def __repr__(self):
        return f'<Favorite User {self.user_id} -> Gen {self.generation_id}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'generation_id': self.generation_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
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
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255))
    generation_id = db.Column(db.Integer, db.ForeignKey('generations.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('token_transactions', lazy='dynamic'))
    generation = db.relationship('Generation', backref=db.backref('token_transaction', uselist=False))

    def __repr__(self):
        return f'<TokenTransaction user:{self.user_id} amount:{self.amount} type:{self.transaction_type}>'


class Pricing(db.Model):
    """Стоимость генераций по модулям"""
    __tablename__ = 'pricing'

    id = db.Column(db.Integer, primary_key=True)
    module_key = db.Column(db.String(50), nullable=False, unique=True)
    base_cost = db.Column(db.Integer, default=10, nullable=False)
    cost_per_width = db.Column(db.Integer, default=0)
    cost_per_height = db.Column(db.Integer, default=0)
    cost_per_second = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=False)

    def calculate_cost(self, width=0, height=0, duration=0):
        cost = self.base_cost
        if self.cost_per_width and width:
            cost += (width // 256) * self.cost_per_width
        if self.cost_per_height and height:
            cost += (height // 256) * self.cost_per_height
        if self.cost_per_second and duration:
            cost += duration * self.cost_per_second
        return max(cost, 1)

    def __repr__(self):
        return f'<Pricing {self.module_key} cost:{self.base_cost}>'


class GenerationPreset(db.Model):
    """Пресеты генераций пользователя"""
    __tablename__ = 'generation_presets'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    generation_type = db.Column(db.String(50), nullable=False)
    model_used = db.Column(db.String(100))
    prompt = db.Column(db.Text)
    negative_prompt = db.Column(db.Text)
    settings = db.Column(db.JSON)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'generation_type': self.generation_type,
            'model_used': self.model_used,
            'prompt': self.prompt,
            'negative_prompt': self.negative_prompt,
            'settings': self.settings or {}
        }

    def __repr__(self):
        return f'<Preset {self.name} for User {self.user_id}>'


class TokenRule(db.Model):
    """Правила начисления токенов"""
    __tablename__ = 'token_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rule_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    max_uses = db.Column(db.Integer, default=None)
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

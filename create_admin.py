#!/usr/bin/env python3
"""
Скрипт для создания администратора
Использует ту же конфигурацию что и основное приложение
"""

import sys
import os

# Добавляем текущую директорию
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем ВСЁ из основного приложения
from app import app, db, bcrypt
from models import User

def main():
    with app.app_context():
        print("\n" + "="*50)
        print("УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ")
        print("="*50)
        
        # Показываем путь к базе
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'unknown')
        print(f"\nБаза данных: {db_uri}\n")
        
        # Убеждаемся что таблицы существуют
        db.create_all()
        
        # Показываем всех пользователей
        users = User.query.all()
        print(f"Пользователей в базе: {len(users)}")
        
        if users:
            print("\nСписок пользователей:")
            print("-" * 50)
            for u in users:
                admin_str = "✓ ADMIN" if u.is_admin else "user"
                print(f"  #{u.id}: {u.username} ({u.email}) [{admin_str}]")
            print("-" * 50)
        
        print("\nДействия:")
        print("  1. Создать нового администратора")
        print("  2. Сделать существующего пользователя админом")
        print("  3. Сбросить пароль пользователю")
        print("  4. Показать всех пользователей")
        print("  0. Выход")
        
        choice = input("\nВыберите действие: ").strip()
        
        if choice == '1':
            create_new_admin()
        elif choice == '2':
            make_existing_admin()
        elif choice == '3':
            reset_password()
        elif choice == '4':
            show_users()
        elif choice == '0':
            print("Выход.")
        else:
            print("Неверный выбор")


def create_new_admin():
    """Создание нового администратора"""
    print("\n--- Создание нового администратора ---\n")
    
    username = input("Имя пользователя: ").strip()
    if not username or len(username) < 3:
        print("❌ Имя должно быть минимум 3 символа!")
        return
    
    if User.query.filter_by(username=username).first():
        print(f"❌ Пользователь '{username}' уже существует!")
        return
    
    email = input("Email: ").strip()
    if not email or '@' not in email:
        print("❌ Неверный формат email!")
        return
    
    if User.query.filter_by(email=email).first():
        print(f"❌ Email '{email}' уже используется!")
        return
    
    password = input("Пароль: ").strip()
    if len(password) < 6:
        print("❌ Пароль должен быть минимум 6 символов!")
        return
    
    # Создаём
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    admin = User(
        username=username,
        email=email,
        password_hash=password_hash,
        is_admin=True
    )
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"\n✅ Администратор '{username}' создан!")


def make_existing_admin():
    """Назначение существующего пользователя админом"""
    print("\n--- Назначение администратора ---\n")
    
    users = User.query.filter_by(is_admin=False).all()
    if not users:
        print("Нет обычных пользователей для назначения")
        return
    
    print("Обычные пользователи:")
    for u in users:
        print(f"  #{u.id}: {u.username}")
    
    user_id = input("\nВведите ID пользователя: ").strip()
    
    try:
        user = User.query.get(int(user_id))
        if not user:
            print("❌ Пользователь не найден!")
            return
        
        user.is_admin = True
        db.session.commit()
        print(f"\n✅ Пользователь '{user.username}' назначен администратором!")
    except ValueError:
        print("❌ Неверный ID!")


def reset_password():
    """Сброс пароля пользователя"""
    print("\n--- Сброс пароля ---\n")
    
    username = input("Имя пользователя: ").strip()
    user = User.query.filter_by(username=username).first()
    
    if not user:
        print(f"❌ Пользователь '{username}' не найден!")
        return
    
    new_password = input("Новый пароль: ").strip()
    if len(new_password) < 6:
        print("❌ Пароль должен быть минимум 6 символов!")
        return
    
    user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    
    print(f"\n✅ Пароль для '{username}' изменён!")


def show_users():
    """Показать всех пользователей"""
    print("\n--- Все пользователи ---\n")
    
    users = User.query.all()
    if not users:
        print("База данных пуста")
        return
    
    for u in users:
        admin_str = "✓ ADMIN" if u.is_admin else "user"
        created = u.created_at.strftime('%d.%m.%Y %H:%M') if u.created_at else "?"
        print(f"#{u.id}: {u.username}")
        print(f"    Email: {u.email}")
        print(f"    Роль: {admin_str}")
        print(f"    Создан: {created}")
        print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрервано.")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
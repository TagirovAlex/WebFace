#!/usr/bin/env python3
"""
Восстановление/создание администратора
"""

from app import app, db, bcrypt
from models import User

with app.app_context():
    print("\n=== Управление администратором ===\n")
    
    # Показываем всех пользователей
    users = User.query.all()
    print(f"Пользователей в базе: {len(users)}\n")
    
    if users:
        print("Существующие пользователи:")
        for u in users:
            admin_mark = " ✓ ADMIN" if u.is_admin else ""
            print(f"  #{u.id}: {u.username} ({u.email}){admin_mark}")
        print()
    
    # Спрашиваем что делать
    if users:
        print("Выберите действие:")
        print("  1 - Сделать существующего пользователя админом")
        print("  2 - Сбросить пароль существующему пользователю")
        print("  3 - Создать нового администратора")
        choice = input("\nВаш выбор: ").strip()
    else:
        choice = '3'  # Если нет пользователей - создаём
    
    if choice == '1':
        # Назначить админа
        username = input("Имя пользователя: ").strip()
        user = User.query.filter_by(username=username).first()
        
        if user:
            user.is_admin = True
            db.session.commit()
            print(f"✅ Пользователь '{username}' назначен администратором!")
        else:
            print(f"❌ Пользователь '{username}' не найден!")
    
    elif choice == '2':
        # Сбросить пароль
        username = input("Имя пользователя: ").strip()
        new_password = input("Новый пароль: ").strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            user.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
            
            # Спросим про права админа
            make_admin = input("Сделать администратором? (y/n): ").strip().lower()
            if make_admin == 'y':
                user.is_admin = True
            
            db.session.commit()
            print(f"✅ Пароль изменён! Админ: {user.is_admin}")
        else:
            print(f"❌ Пользователь '{username}' не найден!")
    
    elif choice == '3':
        # Создать нового
        print("\nСоздание нового администратора:\n")
        
        username = input("Имя пользователя: ").strip()
        email = input("Email: ").strip()
        password = input("Пароль: ").strip()
        
        # Проверки
        if User.query.filter_by(username=username).first():
            print(f"❌ Пользователь '{username}' уже существует!")
        elif User.query.filter_by(email=email).first():
            print(f"❌ Email '{email}' уже используется!")
        elif len(password) < 6:
            print("❌ Пароль должен быть минимум 6 символов!")
        else:
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
            print(f"✅ Администратор '{username}' создан!")
    
    else:
        print("Отмена")
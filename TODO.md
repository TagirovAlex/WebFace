# TODO - WebFace

## Навигация

- [x] Готовые задачи
- [ ] Активные задачи
- [ ] Безопасность (Security)
- [ ] Согласованность кода
- [ ] Функционал
- [ ] Новые фичи

---

## ✅ Готовые задачи (22)

- [x] **#18** Add missing templates/profile.html
- [x] **#19** Add missing templates/admin/user_detail.html
- [x] **#20** Fix seed validation - validate before use
- [x] **#21** Fix width/height validation before using
- [x] **#22** @login_required already validates auth
- [x] **#23** MAX_IMAGE_SIZE_MB naming is consistent
- [x] **#24** Add error handling for db.session.commit
- [x] **#25** Fix IMAGE_SIZE_PRESETS validation
- [x] **#5** Remove traceback.print_exc() (security)
- [x] **#4** Add admin detailed user action history view
- [x] **#5new** Add 'Coming Soon' block on user page
- [x] **#3** SECRET_KEY persistence — сохранение в .flask_secret
- [x] **#8** Timeout limit — добавлены конфигурируемые лимиты
- [x] **#7** Rate limiting bypass — добавлена защита от X-Forwarded-For spoofing
- [x] **#15** get_or_404 with custom descriptions
- [x] **#11** Duplicate file logic — рефакторинг get_generation_file_paths
- [x] **#12** Unused filename functions removed
- [x] **#2** Admin generation types toggle (БД + UI + API проверки)
- [x] **#1new** Light/dark theme toggle (БД + API + JS синхронизация)

---

## 🔄 Активные задачи

*Нет*

---

## 🔒 Безопасность (Security) - ВСЕ ✅

- [x] **#6** CSP unsafe-inline — убран из script-src, оставлен для style
- ~~#4~~ ❌ УДАЛЕНО - локальное подключение к ComfyUI, SSL не требуется
- ~~#3~~ ✅ SECRET_KEY persistence
- ~~#5~~ ✅ Remove traceback.print_exc()
- ~~#7~~ ✅ Rate limiting bypass
- ~~#8~~ ✅ Timeout limit

---

## 🔵 Согласованность кода - ВСЕ ✅

- ~~#11~~ ✅ Duplicate file logic functions (рефакторинг: универсальная get_generation_file_paths)
- ~~#12~~ ✅ Overlapping filename functions (удалены неиспользуемые allowed_file, generate_unique_filename, sanitize)
- ~~#15~~ ✅ get_or_404 with custom description

---

## 🟢 Функционал - ВСЕ ВЫПОЛНЕНЫ ✅

- [x] **#18** profile.html missing
- [x] **#19** user_detail.html missing

---

## ✨ Новые фичи - ВСЕ ✅

- [x] **#1** Light/dark theme toggle ✅
- [x] **#2** Admin ability to enable/disable generation types globally ⭐HIGH
- [x] **#3** Module system for generation types ⭐HIGH (BaseModule + ModuleRegistry + примеры модулей)
- [x] ~~#4~~ **DONE** Admin detailed user action history view
- [x] ~~#5~~ **DONE** Coming Soon block

---

## 🏷️ Приоритеты

| Приоритет | Описание |
|-----------|----------|
| high | Критично для функционирования |
| medium | Важно, улучшает UX/безопасность |
| low | Nice to have |

---

## 📋 Сводка

| Статус | Количество |
|--------|-----------|
| ✅ Выполнено | 23 |
| 🔒 Безопасность | 0 (все выполнены) |
| ✨ Фичи | 0 (все выполнены) |

---

## 🆕 v2.0 Release (e2ab3cb)

### Коммит
```
git commit -m "v2.0 release: token system, module system, security fixes"
```

### Добавлено
- `migrate_db.py` - скрипт миграции БД
- Token система: TokenBalance, TokenTransaction, Pricing, TokenRule
- Module система: BaseModule + ModuleRegistry
- 4 генерационных модуля в modules/
- Поля users: priority, token_period, last_token_reset
- generations.hidden_from_user

---

## 🔮 Желаемый функционал (Backlog)

### High Priority
- [ ] **F1** API документация (Swagger/OpenAPI)
- [ ] **F2** Асинхронная генерация (Celery/Redis)
- [ ] **F3** Пуш-уведомления о завершении генерации
- [ ] **F4** Публичные галереи/галереи пользователей
- [ ] **F5** Пресеты генерации (сохранение настроек)
- [x] **F6** Telegram бот (aiogram3) - управление для админа ⭐HIGH
  - [x] **F6.1** Подключение бота через BOT_TOKEN
  - [x] **F6.2** Команда /stats - статистика генераций
  - [x] **F6.3** Команда /users - список пользователей
  - [x] **F6.4** Команда /last - последние генерации
  - [ ] **F6.5** Пуш-уведомления админу о новых генерациях
  - [x] **F6.6** Управление пользователями
    - [x] **F6.6.1** /user <id> - информация о пользователе
    - [x] **F6.6.2** /add_tokens <id> <amount> - добавить токены
    - [x] **F6.6.3** /remove_tokens <id> <amount> - списать токены
    - [x] **F6.6.4** /set_tokens <id> <amount> - установить баланс
    - [x] **F6.6.5** /set_limit <id> <period> - установить период
    - [x] **F6.6.6** /set_priority <id> <priority> - установить приоритет
    - [x] **F6.6.7** /gens <id> - просмотр генераций
    - [x] **F6.6.8** /toggle_admin <id> - сделать админом
    - [x] **F6.6.9** /ban <id> - заблокировать
    - [x] **F6.6.10** /unban <id> - разблокировать

### Medium Priority
- [ ] **F7** Шаринг генераций по ссылке
- [ ] **F8** Лайки/избранное
- [ ] **F9** Тегирование генераций
- [ ] **F10** Bulk operations (удаление/экспорт)

### Low Priority
- [ ] **F11** Темы интерфейса (дополнительные)
- [ ] **F12** Плагины/расширения

### Технические
- [ ] **T1** Flask-Migrate (Alembic)
- [ ] **T2** Кэширование (Redis)
- [ ] **T3** Тесты (pytest)
- [ ] **T4** CI/CD пайплайн

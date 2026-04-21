"""
Telegram Bot for WebFace Admin Management

Uses aiogram3 for bot functionality.

Start bot:
    python telegram_bot.py

Commands:
    /start - Welcome message
    /stats - Generation statistics
    /users - User list
    /last - Last 10 generations
    /user <id> - User info
    /add_tokens <id> <amount> - Add tokens
    /set_limit <id> <period> <amount> - Set token limit
    /set_priority <id> <priority> - Set priority (25/50/75/100)
    /gens <id> - User generations
    /toggle_admin <id> - Toggle admin status
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, BotCommand
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import Config

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import User, Generation, TokenBalance, UserPriority

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = Config.TELEGRAM_BOT_TOKEN
ADMIN_CHAT_ID = Config.TELEGRAM_ADMIN_CHAT_ID

if not BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN not set. Bot will not start.")
    sys.exit(0)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
router = Router()
dp = Dispatcher()
dp.include_router(router)


def get_db_session():
    """Get database session"""
    with app.app_context():
        return db.session


async def check_admin(chat_id: int) -> bool:
    """Check if user is admin"""
    if not ADMIN_CHAT_ID:
        return False
    return str(chat_id) == str(ADMIN_CHAT_ID)


def format_stats() -> str:
    """Format statistics message"""
    with app.app_context():
        total_users = User.query.count()
        total_gens = Generation.query.count()
        today_gens = Generation.query.filter(
            Generation.created_at >= datetime.utcnow() - timedelta(days=1)
        ).count()
        completed = Generation.query.filter_by(status='completed').count()
        failed = Generation.query.filter_by(status='failed').count()

        pending = Generation.query.filter_by(status='pending').count()
        processing = Generation.query.filter_by(status='processing').count()

        return (
            f"<b>📊 Статистика</b>\n\n"
            f"<b>Пользователи:</b> {total_users}\n"
            f"<b>Всего генераций:</b> {total_gens}\n"
            f"<b>За сегодня:</b> {today_gens}\n"
            f"<b>Выполнено:</b> {completed}\n"
            f"<b>Ошибки:</b> {failed}\n"
            f"<b>В очереди:</b> {pending}\n"
            f"<b>Обработка:</b> {processing}"
        )


def format_users(limit: int = 10) -> str:
    """Format users list"""
    with app.app_context():
        users = User.query.order_by(User.created_at.desc()).limit(limit).all()

        if not users:
            return "Нет пользователей"

        lines = ["<b>👥 Пользователи</b>\n"]
        for u in users:
            priority_name = UserPriority.get_name(u.priority or 50)
            admin_mark = "👑" if u.is_admin else ""
            lines.append(
                f"{u.id}. {u.username} {admin_mark}\n"
                f"   priority: {priority_name} | "
                f"tokens: {u.token_balance.balance if u.token_balance else 0}\n"
            )

        return "".join(lines)


def format_last_gens(limit: int = 10) -> str:
    """Format last generations"""
    with app.app_context():
        gens = Generation.query.order_by(
            Generation.created_at.desc()
        ).limit(limit).all()

        if not gens:
            return "Нет генераций"

        lines = ["<b>📜 Последние генерации</b>\n"]
        for g in gens:
            username = g.user.username if g.user else "Unknown"
            status_emoji = {
                "completed": "✅",
                "failed": "❌",
                "processing": "⏳",
                "pending": "⏸"
            }.get(g.status, "❓")

            lines.append(
                f"{g.id}. {status_emoji} {g.generation_type}\n"
                f"   {username} | {g.created_at.strftime('%d.%m %H:%M')}\n"
            )

        return "".join(lines)


def format_user(user_id: int) -> str:
    """Format user info"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        priority_name = UserPriority.get_name(user.priority or 50)
        balance = user.token_balance.balance if user.token_balance else 0
        gen_count = user.generations.count()

        active_status = "Активен" if getattr(user, 'is_active', True) else "Заблокирован"

        return (
            f"<b>👤 Пользователь #{user.id}</b>\n\n"
            f"<b>Имя:</b> {user.username}\n"
            f"<b>Email:</b> {user.email}\n"
            f"<b>Статус:</b> {active_status}\n"
            f"<b>Приоритет:</b> {priority_name}\n"
            f"<b>Токены:</b> {balance}\n"
            f"<b>Период токенов:</b> {user.token_period}\n"
            f"<b>Генераций:</b> {gen_count}\n"
            f"<b>Admin:</b> {'Да' if user.is_admin else 'Нет'}\n"
            f"<b>Дата регистрации:</b> {user.created_at.strftime('%d.%m.%Y %H:%M')}"
        )


def add_tokens(user_id: int, amount: int) -> str:
    """Add tokens to user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        balance = user.token_balance
        if not balance:
            balance = TokenBalance(user_id=user_id, balance=amount)
            db.session.add(balance)
        else:
            balance.balance += amount

        db.session.commit()
        return f"Добавлено {amount} токенов пользователю {user.username}"


def remove_tokens(user_id: int, amount: int) -> str:
    """Remove tokens from user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        balance = user.token_balance
        if not balance or balance.balance < amount:
            return f"Недостаточно токенов"

        balance.balance -= amount
        db.session.commit()
        return f"Списано {amount} токенов у {user.username}"


def set_tokens(user_id: int, amount: int) -> str:
    """Set token balance for user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        balance = user.token_balance
        if not balance:
            balance = TokenBalance(user_id=user_id, balance=amount)
            db.session.add(balance)
        else:
            balance.balance = amount

        db.session.commit()
        return f"Установлено {amount} токенов для {user.username}"


def set_limit(user_id: int, period: str, amount: int) -> str:
    """Set token limit"""
    valid_periods = ['daily', 'weekly', 'monthly']
    if period not in valid_periods:
        return f"Неверный период. Доступные: {', '.join(valid_periods)}"

    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.token_period = period
        db.session.commit()
        return f"Установлен период {period} для {user.username}"


def set_priority(user_id: int, priority: int) -> str:
    """Set user priority"""
    valid_priorities = [25, 50, 75, 100]
    if priority not in valid_priorities:
        return f"Неверный приоритет. Доступные: {', '.join(map(str, valid_priorities))}"

    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.priority = priority
        db.session.commit()
        return f"Установлен приоритет {priority} для {user.username}"


def toggle_admin(user_id: int) -> str:
    """Toggle admin status"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.is_admin = not user.is_admin
        db.session.commit()
        status = "админ" if user.is_admin else "пользователь"
        return f"{user.username} теперь {status}"


def format_user_gens(user_id: int, limit: int = 10) -> str:
    """Format user generations"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        gens = user.generations.order_by(
            Generation.created_at.desc()
        ).limit(limit).all()

        if not gens:
            return f"Нет генераций у {user.username}"

        lines = [f"<b>📜 Генерации {user.username}</b>\n"]
        for g in gens:
            status_emoji = {
                "completed": "✅",
                "failed": "❌",
                "processing": "⏳",
                "pending": "⏸"
            }.get(g.status, "❓")

            lines.append(
                f"{g.id}. {status_emoji} {g.generation_type}\n"
                f"   {g.created_at.strftime('%d.%m %H:%M')}\n"
            )

        return "".join(lines)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    await message.answer(
        "<b>🤖 WebFace Bot</b>\n\n"
        "Доступные команды:\n"
        "/stats - Статистика\n"
        "/users - Пользователи\n"
        "/last - Последние генерации\n"
        "/user <id> - Информация о пользователе\n"
        "/add_tokens <id> <amount> - Добавить токены\n"
        "/set_limit <id> <period> <amount> - Установить лимит\n"
        "/set_priority <id> <priority> - Установить приоритет\n"
        "/gens <id> - Генерации пользователя\n"
        "/toggle_admin <id> - Сделать/забрать админа"
    )


def link_telegram_account(user_id: int, chat_id: int) -> str:
    """Link Telegram account to user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.telegram_chat_id = str(chat_id)
        db.session.commit()
        return f"Аккаунт Telegram привязан к {user.username}"


def unlink_telegram_account(user_id: int) -> str:
    """Unlink Telegram account from user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.telegram_chat_id = None
        db.session.commit()
        return f"Аккаунт Telegram отвязан от {user.username}"


@router.message(Command("link"))
async def cmd_link(message: Message):
    """Handle /link command - link telegram to user account"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /link <user_id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    result = link_telegram_account(user_id, message.chat.id)
    await message.answer(result)


@router.message(Command("unlink"))
async def cmd_unlink(message: Message):
    """Handle /unlink command"""
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unlink <user_id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    result = unlink_telegram_account(user_id)
    await message.answer(result)


async def notify_admin_new_gen(gen_type: str, username: str):
    """Notify admin of new generation (F6.5)"""
    if not ADMIN_CHAT_ID:
        return
    try:
        text = f"🆕 Новая генерация\n\nUser: {username}\nType: {gen_type}"
        await bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Handle /stats command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    await message.answer(await format_stats())


@router.message(Command("users"))
async def cmd_users(message: Message):
    """Handle /users command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    await message.answer(format_users())


@router.message(Command("last"))
async def cmd_last(message: Message):
    """Handle /last command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    await message.answer(format_last_gens())


@router.message(Command("user"))
async def cmd_user(message: Message):
    """Handle /user command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /user <id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    await message.answer(format_user(user_id))


@router.message(Command("add_tokens"))
async def cmd_add_tokens(message: Message):
    """Handle /add_tokens command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /add_tokens <id> <amount>")
        return

    try:
        user_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("Неверные параметры")
        return

    await message.answer(add_tokens(user_id, amount))


@router.message(Command("set_limit"))
async def cmd_set_limit(message: Message):
    """Handle /set_limit command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /set_limit <id> <period>")
        return

    try:
        user_id = int(parts[1])
        period = parts[2]
    except ValueError:
        await message.answer("Неверные параметры")
        return

    await message.answer(set_limit(user_id, period, 0))


@router.message(Command("remove_tokens"))
async def cmd_remove_tokens(message: Message):
    """Handle /remove_tokens command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /remove_tokens <id> <amount>")
        return

    try:
        user_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("Неверные параметры")
        return

    await message.answer(remove_tokens(user_id, amount))


@router.message(Command("set_tokens"))
async def cmd_set_tokens(message: Message):
    """Handle /set_tokens command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /set_tokens <id> <amount>")
        return

    try:
        user_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.answer("Неверные параметры")
        return

    await message.answer(set_tokens(user_id, amount))


@router.message(Command("set_priority"))
async def cmd_set_priority(message: Message):
    """Handle /set_priority command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /set_priority <id> <priority>")
        return

    try:
        user_id = int(parts[1])
        priority = int(parts[2])
    except ValueError:
        await message.answer("Неверные параметры")
        return

    await message.answer(set_priority(user_id, priority))


@router.message(Command("gens"))
async def cmd_gens(message: Message):
    """Handle /gens command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /gens <id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    await message.answer(format_user_gens(user_id))


@router.message(Command("toggle_admin"))
async def cmd_toggle_admin(message: Message):
    """Handle /toggle_admin command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /toggle_admin <id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    await message.answer(toggle_admin(user_id))


def ban_user(user_id: int) -> str:
    """Ban user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.is_active = False
        db.session.commit()
        return f"Пользователь {user.username} заблокирован"


def unban_user(user_id: int) -> str:
    """Unban user"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user:
            return f"Пользователь {user_id} не найден"

        user.is_active = True
        db.session.commit()
        return f"Пользователь {user.username} разблокирован"


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    """Handle /ban command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /ban <id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    await message.answer(ban_user(user_id))


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    """Handle /unban command"""
    if not await check_admin(message.chat.id):
        await message.answer("Доступ запрещен")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /unban <id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID пользователя")
        return

    await message.answer(unban_user(user_id))


async def notify_user(user_id: int, text: str):
    """Send notification to user"""
    with app.app_context():
        user = User.query.get(user_id)
        if user and user.telegram_chat_id and user.notify_on_complete:
            try:
                await bot.send_message(chat_id=int(user.telegram_chat_id), text=text)
            except Exception as e:
                logger.error(f"Failed to send user notification: {e}")


async def notify_admin(text: str):
    """Send notification to admin"""
    if ADMIN_CHAT_ID:
        try:
            await bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


async def notify_generation_complete(user_id: int, gen_type: str, generation_id: int, success: bool, error: str = None):
    """Notify user that generation is complete"""
    with app.app_context():
        user = User.query.get(user_id)
        if not user or not user.telegram_chat_id or not user.notify_on_complete:
            return

        if success:
            status_text = f"✅ Генерация #{generation_id} завершена!\n\nТип: {gen_type}"
        else:
            error_text = error[:100] if error else "Unknown error"
            status_text = f"❌ Генерация #{generation_id} не удалась\n\nОшибка: {error_text}"

        try:
            await bot.send_message(chat_id=int(user.telegram_chat_id), text=status_text)
        except Exception as e:
            logger.error(f"Failed to send generation notification: {e}")


async def notify_new_generation(user_id: int, gen_type: str, generation_id: int):
    """Notify admin of new generation"""
    if not ADMIN_CHAT_ID:
        return

    with app.app_context():
        user = User.query.get(user_id)
        username = user.username if user else "Unknown"

    try:
        text = f"🆕 Новая генерация #{generation_id}\n\nПользователь: {username}\nТип: {gen_type}"
        await bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def main():
    """Main function"""
    logger.info("Starting WebFace Telegram Bot...")

    await bot.set_my_commands([
        BotCommand(command="start", description="Запуск"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="users", description="Пользователи"),
        BotCommand(command="last", description="Последние генерации"),
    ])

    logger.info("Bot started. Press Ctrl+C to stop.")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
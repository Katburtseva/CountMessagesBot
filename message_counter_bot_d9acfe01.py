"""
Telegram-бот: счётчик сообщений за день.
Считает сообщения каждого участника в чате.
В 23:59 по МСК автоматически отправляет итоги дня и сбрасывает счётчик.

Установка зависимостей:
    pip install python-telegram-bot==20.7 apscheduler==3.10.4

Запуск:
    BOT_TOKEN=your_token_here python bot.py
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8326506470:AAGmKizzO_wKwKBIylJuzu00ZbUYW9B9AEs")
MSK = timezone(timedelta(hours=3))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Хранилище ────────────────────────────────────────────────
# Структура: { chat_id: { user_display_name: count } }
counters: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
# Запоминаем chat_id всех чатов, где бот активен
active_chats: set[int] = set()


# ── Вспомогательные функции ──────────────────────────────────
def get_display_name(user) -> str:
    """Возвращает читаемое имя пользователя."""
    if user is None:
        return "Неизвестный"
    name = user.full_name or user.first_name or ""
    if user.username:
        name += f" (@{user.username})"
    return name or "Неизвестный"


def build_report(chat_id: int) -> str | None:
    """Формирует текст отчёта для чата. Возвращает None, если сообщений не было."""
    data = counters.get(chat_id)
    if not data:
        return None

    today = datetime.now(MSK).strftime("%d.%m.%Y")
    total = sum(data.values())

    lines = [f"📊 Итоги дня ({today})\n"]
    for name, count in sorted(data.items(), key=lambda x: -x[1]):
        lines.append(f"  • {name}: {count}")
    lines.append(f"\nВсего сообщений: {total}")

    return "\n".join(lines)


# ── Обработчики ──────────────────────────────────────────────
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Считает каждое входящее сообщение."""
    if update.effective_chat is None or update.effective_user is None:
        return

    chat_id = update.effective_chat.id
    name = get_display_name(update.effective_user)

    counters[chat_id][name] += 1
    active_chats.add(chat_id)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /stats — показать текущую статистику за сегодня."""
    if update.effective_chat is None:
        return

    report = build_report(update.effective_chat.id)
    if report:
        await update.message.reply_text(report)
    else:
        await update.message.reply_text("Сегодня сообщений пока не было.")


# ── Ежедневная рассылка в 23:59 МСК ─────────────────────────
async def daily_report(app) -> None:
    """Отправляет итоги дня во все активные чаты и сбрасывает счётчики."""
    logger.info("Отправка ежедневного отчёта...")

    for chat_id in list(active_chats):
        report = build_report(chat_id)
        if report:
            try:
                await app.bot.send_message(chat_id=chat_id, text=report)
            except Exception as e:
                logger.error("Не удалось отправить отчёт в чат %s: %s", chat_id, e)

    # Сброс счётчиков
    counters.clear()
    active_chats.clear()
    logger.info("Счётчики сброшены.")


# ── Колбэк после старта event loop ───────────────────────────
async def post_init(app) -> None:
    """Запускаем планировщик после того, как event loop уже работает."""
    scheduler = AsyncIOScheduler(timezone=MSK)
    scheduler.add_job(
        daily_report,
        trigger=CronTrigger(hour=23, minute=59, timezone=MSK),
        args=[app],
    )
    scheduler.start()
    logger.info("Бот запущен. Ежедневный отчёт будет в 23:59 МСК.")


# ── Точка входа ──────────────────────────────────────────────
def main() -> None:
    if not BOT_TOKEN:
        logger.error("Переменная окружения BOT_TOKEN не задана!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики
    app.add_handler(CommandHandler("stats", cmd_stats))
    # Считаем все типы сообщений (текст, фото, стикеры и т.д.)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

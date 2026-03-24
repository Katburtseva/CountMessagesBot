"""
Telegram-бот: Счётчик сообщений за день.

Считает количество сообщений каждого участника чата за текущий день.
Команды:
  /start  — приветствие и инструкция
  /stats  — статистика сообщений за сегодня
  /reset  — сброс статистики (только для админов группы)

Использование:
  1. Вставьте свой BOT_TOKEN ниже (или задайте переменную окружения BOT_TOKEN).
  2. Добавьте бота в групповой чат и дайте ему права на чтение сообщений.
  3. Запустите: python message_counter_bot.py
"""

import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode

# ─── Конфигурация ────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8326506470:AAGmKizzO_wKwKBIylJuzu00ZbUYW9B9AEs")
# ─────────────────────────────────────────────────────────────────────────────

router = Router()

# Хранилище: {chat_id: {user_id: {"name": str, "count": int, "date": str}}}
stats: dict[int, dict[int, dict]] = defaultdict(lambda: defaultdict(dict))


def today() -> str:
    """Текущая дата как строка YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")


def get_user_display_name(user: types.User) -> str:
    """Читаемое имя пользователя."""
    if user.full_name:
        return user.full_name
    if user.username:
        return f"@{user.username}"
    return f"User {user.id}"


def ensure_today(chat_id: int, user_id: int, user: types.User) -> None:
    """Если дата сменилась — обнуляем счётчик пользователя."""
    current = today()
    entry = stats[chat_id].get(user_id)
    if not entry or entry.get("date") != current:
        stats[chat_id][user_id] = {
            "name": get_user_display_name(user),
            "count": 0,
            "date": current,
        }


# ─── Подсчёт каждого сообщения ──────────────────────────────────────────────
@router.message(~Command("start", "stats", "reset"))
async def count_message(message: types.Message) -> None:
    """Считаем каждое входящее сообщение (кроме команд бота)."""
    if not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    ensure_today(chat_id, user_id, message.from_user)
    stats[chat_id][user_id]["count"] += 1
    stats[chat_id][user_id]["name"] = get_user_display_name(message.from_user)


# ─── /start ──────────────────────────────────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    await message.answer(
        "<b>Привет!</b> Я считаю сообщения в этом чате.\n\n"
        "Просто пишите как обычно — я веду подсчёт автоматически.\n\n"
        "<b>Команды:</b>\n"
        "/stats — статистика за сегодня\n"
        "/reset — сбросить счётчик (только админы)",
        parse_mode=ParseMode.HTML,
    )


# ─── /stats ──────────────────────────────────────────────────────────────────
@router.message(Command("stats"))
async def cmd_stats(message: types.Message) -> None:
    chat_id = message.chat.id
    current = today()

    # Фильтруем только сегодняшние записи
    today_stats = {
        uid: data
        for uid, data in stats.get(chat_id, {}).items()
        if data.get("date") == current and data.get("count", 0) > 0
    }

    if not today_stats:
        await message.answer("За сегодня пока нет сообщений (или бот только что добавлен).")
        return

    # Сортируем по количеству сообщений
    sorted_users = sorted(today_stats.items(), key=lambda x: x[1]["count"], reverse=True)

    total = sum(d["count"] for _, d in sorted_users)

    lines = [f"<b>📊 Статистика за {current}</b>\n"]
    for i, (uid, data) in enumerate(sorted_users, 1):
        pct = data["count"] / total * 100 if total else 0
        bar_len = round(pct / 5)  # макс ~20 символов
        bar = "▓" * bar_len + "░" * (20 - bar_len)
        lines.append(
            f"{i}. <b>{data['name']}</b>\n"
            f"   {bar} {data['count']} сообщ. ({pct:.0f}%)"
        )

    lines.append(f"\n<b>Всего:</b> {total} сообщений")

    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


# ─── /reset ──────────────────────────────────────────────────────────────────
@router.message(Command("reset"))
async def cmd_reset(message: types.Message, bot: Bot) -> None:
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    # В личных чатах разрешаем всем, в группах — только админам
    if message.chat.type != "private":
        if user_id:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ("administrator", "creator"):
                await message.answer("Сбросить статистику могут только администраторы.")
                return

    stats[chat_id].clear()
    await message.answer("Статистика сброшена. Подсчёт начнётся заново.")


# ─── Запуск ──────────────────────────────────────────────────────────────────
async def main() -> None:
    if BOT_TOKEN == "ВСТАВЬТЕ_СВОЙ_ТОКЕН_СЮДА":
        print("❌ Ошибка: укажите BOT_TOKEN!")
        print("   Либо задайте переменную окружения: export BOT_TOKEN='ваш_токен'")
        print("   Либо замените значение прямо в коде.")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

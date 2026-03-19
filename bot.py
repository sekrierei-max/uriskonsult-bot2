#!/usr/bin/env python3
"""
Основной бот для управления статьями и публикациями
ВЕРСИЯ ДЛЯ WEBHOOK (СТАБИЛЬНАЯ)
"""

import asyncio
import logging
import sys
import time
import uuid
import inspect
import os
import signal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler

from src.core.config import config
from src.core.logger import setup_logger
from database import db
from models import Article, ScheduledPost

# ============================================
# ПРИНУДИТЕЛЬНОЕ ЛОГИРОВАНИЕ
# ============================================
sys.stdout = open(1, 'w', encoding='utf-8', closefd=False)
sys.stderr = open(2, 'w', encoding='utf-8', closefd=False)

def signal_handler(sig, frame):
    print(f"🔴 Получен сигнал {sig}, бот завершается")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

print("🚀 Бот ЗАПУЩЕН, принудительное логирование включено")
print(f"📊 Python версия: {sys.version}")
print(f"📁 Текущая директория: {os.getcwd()}")
print(f"📂 Файлы в директории: {os.listdir('.')}")

# ============================================
# Настройка логирования
# ============================================
logger = setup_logger('bot')
print(f"🤖 Инициализация бота с токеном: {config['BOT_TOKEN'][:10]}...")
bot = Bot(token=config['BOT_TOKEN'])
dp = Dispatcher(storage=MemoryStorage())

# ============================================
# ЗАЩИТА ОТ СПАМА
# ============================================
user_message_counts = defaultdict(int)
user_last_reset = {}

def check_message_limit(user_id: int) -> bool:
    current_time = time.time()
    one_day = 24 * 60 * 60
    
    if user_id not in user_last_reset or current_time - user_last_reset[user_id] > one_day:
        user_message_counts[user_id] = 0
        user_last_reset[user_id] = current_time
    
    return user_message_counts[user_id] < 3

async def reset_limits_daily():
    while True:
        await asyncio.sleep(24 * 60 * 60)
        user_message_counts.clear()
        user_last_reset.clear()
        logger.info("✅ Лимиты сообщений сброшены")

# ============================================
# ДАННЫЕ (КОНТРАКТЫ, ДОКУМЕНТЫ, КЕЙСЫ)
# ============================================
# ... (все ваши CONTRACTS, FREE_DOCS, cases_db, DEEP_ARTICLES)
# ВСТАВЬТЕ СЮДА ВСЕ ВАШИ БОЛЬШИЕ СЛОВАРИ ИЗ ТЕКУЩЕГО ФАЙЛА
# Я их не копирую сюда для краткости, но вы должны их оставить

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================
def is_admin(user_id: int) -> bool:
    return user_id == config['ADMIN_ID']

def admin_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id != config['ADMIN_ID']:
            await message.answer("⛔ У вас нет прав для выполнения этой команды.")
            logger.warning(f"Unauthorized access attempt by user {message.from_user.id}")
            return
        return await func(message, *args, **kwargs)
    return wrapper

# ============================================
# КЛАВИАТУРЫ
# ============================================
# ... (все ваши функции get_main_keyboard, get_shop_keyboard и т.д.)
# ВСТАВЬТЕ ИХ СЮДА ИЗ ТЕКУЩЕГО ФАЙЛА

# ============================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================
# ... (ВСЕ ВАШИ КОМАНДЫ: /start, /help, /admin, /add_article и т.д.)
# ВСТАВЬТЕ ИХ СЮДА ИЗ ТЕКУЩЕГО ФАЙЛА
# (от @dp.message(Command("start")) до @dp.errors())

# ============================================
# ФУНКЦИИ ДЛЯ ТИЗЕРОВ
# ============================================
def detect_article_type(text: str) -> str:
    text_lower = text.lower()
    if any(word in text_lower for word in ['инструкция', 'как', 'шаги', 'порядок', 'пошагово']):
        return "instruction"
    elif any(word in text_lower for word in ['кейс', 'пример', 'ситуация', 'дело', 'случай']):
        return "case"
    else:
        return "news"

def format_teaser_by_type(full_text: str, article_type: str = "news") -> str:
    lines = full_text.strip().split('\n')
    title = lines[0].strip() if lines else "Статья"
    body = ' '.join([line.strip() for line in lines[1:] if line.strip()])[:400]
    
    templates = {
        "news": f"⚜️ **{title}**\n\n🔹 **Главное:** {body}...\n\n⚠️ Читайте полностью в боте 👇",
        "instruction": f"📋 **{title}**\n\n🔹 **Пошаговая инструкция:**\n{body}...\n\n✅ Полная версия в боте 👇",
        "case": f"⚖️ **{title}**\n\n🔹 **Суть дела:** {body}...\n\n📌 Детали в боте 👇"
    }
    return templates.get(article_type, templates["news"])

def get_channel_post_keyboard(article_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔴 ЧИТАТЬ ПОЛНОСТЬЮ В БОТЕ", 
        url=f"https://t.me/uriskonsult_bot?start=article_{article_id}"
    ))
    return builder.as_markup()

# ============================================
# ПЛАНИРОВЩИК (ТОЛЬКО ДЛЯ ЛОГОВ)
# ============================================
async def run_scheduler():
    """Простой планировщик для логов (без публикаций)"""
    logger.info("🚀 Планировщик логов запущен")
    
    while True:
        try:
            await asyncio.sleep(30)
            logger.info(f"⏰ Пинг планировщика в {datetime.now().strftime('%H:%M:%S')}")
            logger.debug("Планировщик работает")
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            await asyncio.sleep(10)

# ============================================
# WEBHOOK НАСТРОЙКИ
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
# ВАЖНО: Создайте переменную WEBHOOK_URL в Amvera!
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 80))

async def on_startup_webhook():
    """Действия при старте вебхука"""
    if not WEBHOOK_URL:
        logger.error("❌ WEBHOOK_URL не задан! Бот не сможет работать.")
        return
    
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    logger.info(f"✅ Webhook установлен на {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    # Запускаем планировщик в фоне
    asyncio.create_task(run_scheduler())
    asyncio.create_task(reset_limits_daily())
    
    # Подключаемся к БД
    await db.connect()
    
    logger.info("✅ Бот готов к работе через webhook")

async def on_shutdown_webhook():
    """Действия при остановке"""
    await bot.delete_webhook()
    logger.info("✅ Webhook удален")
    
    if hasattr(db, 'pool') and db.pool:
        await db.pool.close()
    
    await bot.session.close()
    logger.info("👋 Бот остановлен")

# Создаём aiohttp приложение
app = web.Application()

# Регистрируем обработчик вебхуков
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

# Привязываем функции запуска и остановки
app.on_startup.append(lambda _: on_startup_webhook())
app.on_shutdown.append(lambda _: on_shutdown_webhook())

# ============================================
# ТОЧКА ВХОДА
# ============================================
if __name__ == "__main__":
    if not WEBHOOK_URL:
        logger.critical("❌ WEBHOOK_URL не задан! Добавьте переменную в Amvera")
        sys.exit(1)
    
    logger.info(f"🚀 Запуск веб-сервера на порту {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)

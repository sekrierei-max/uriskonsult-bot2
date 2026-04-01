#!/usr/bin/env python3
"""
Основной бот для управления статьями и публикациями
ВЕРСИЯ ДЛЯ WEBHOOK (РАБОЧАЯ)
"""

import asyncio
import os
import sys
import uuid
import inspect
import time
import signal
from datetime import datetime, timedelta
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

logger = setup_logger('bot')
print("🚀 Бот ЗАПУЩЕН")

bot = Bot(token=config['BOT_TOKEN'])
dp = Dispatcher(storage=MemoryStorage())

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 80))

# ============================================
# ДАННЫЕ ДЛЯ БЕСПЛАТНЫХ ДОКУМЕНТОВ
# ============================================
FREE_DOCS = {
    "zaliv": {
        "name": "💧 Залив",
        "items": {
            1: {"name": "Вас затопили", "file": "Памятка_Вас_затопили.pdf"},
            2: {"name": "Вы затопили", "file": "Памятка_Вы_затопили.pdf"},
            3: {"name": "Акт о заливе", "file": "Акт_о_заливе_шаблон.pdf"}
        }
    },
    "dtp": {
        "name": "🚗 ДТП / Авто",
        "items": {
            1: {"name": "Памятка при ДТП", "file": "Памятка_ДТП.pdf"},
            2: {"name": "Памятка ущерб на стоянке", "file": "Памятка_Повреждение_на_стоянке.pdf"}
        }
    },
    "jkx": {
        "name": "🏢 ЖКХ / УК",
        "items": {
            1: {"name": "Памятка по ОДПУ", "file": "Памятка_ОДПУ_общедомовые_приборы_учета.pdf"},
            2: {"name": "Чек-лист проверки квитанции и УК", "file": "Чек-лист_проверка_квитанции_и_УК.pdf"}
        }
    },
    "arenda": {
        "name": "🏠 Аренда/найм помещений",
        "items": {
            1: {"name": "Памятка арендатору", "file": "Памятка_арендатору_с_чек_листом.pdf"},
            2: {"name": "Чек-лист", "file": "Чек-лист_наним_аренд.pdf"}
        }
    },
    "docs": {
        "name": "📄 Документы",
        "items": {
            1: {"name": "Претензия досудебная", "file": "Претензия_досудебная.pdf"},
            2: {"name": "Расписка о получении денег", "file": "Расписка_о_получении_денег.pdf"},
            3: {"name": "Универсальный акт", "file": "Универсальный_акт.pdf"}
        }
    }
}

# ============================================
# ДАННЫЕ ДЛЯ МАГАЗИНА
# ============================================
CONTRACTS = {
    1: {"name": "🏠 Базовый", "description": "Для физлиц с 1 объектом.", "price": 1900, "upgrade_price": 4900, "file": "dogovor1.pdf"},
    2: {"name": "🏢 Профи", "description": "Для самозанятых и ИП.", "price": 4900, "upgrade_price": 4900, "file": "dogovor2.pdf"},
    3: {"name": "🏨 Гостиничный", "description": "Для ИП/ООО.", "price": 3900, "upgrade_price": 4900, "file": "dogovor3.pdf"},
    4: {"name": "🤝 Агентский", "description": "Для собственников и управляющих.", "price": 5900, "upgrade_price": 4900, "file": "dogovor4.pdf"},
    5: {"name": "📦 Пакет «Всё для аренды»", "description": "Все 5 договоров.", "price": 7900, "upgrade_price": 4900, "file": "pack_all.pdf"}
}

# ============================================
# ДАННЫЕ ДЛЯ КЕЙСОВ
# ============================================
cases_db = {
    1: {
        "title": "Счётчик тепла (ОДПУ) — кто платит за ремонт?",
        "category": "Общедомовые нужды",
        "date": "15.03.2025",
        "situation": "Жильцы получили квитанции на ремонт ОДПУ...",
        "question": "Кто должен оплачивать ремонт?",
        "solution": "Подготовили жалобу в Жилищную инспекцию...",
        "result": "УК сделала перерасчёт...",
        "published": True
    }
}

# ============================================
# КЛАВИАТУРЫ
# ============================================
def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Кейсы", callback_data="menu_cases")],
        [InlineKeyboardButton(text="📚 Бесплатные документы", callback_data="menu_free")],
        [InlineKeyboardButton(text="🏪 Магазин договоров", callback_data="menu_shop")],
        [InlineKeyboardButton(text="📞 Консультация", callback_data="menu_consult")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")]
    ])

def get_shop_keyboard():
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=CONTRACTS[i]["name"], callback_data=f"contract_{i}")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def get_free_categories_keyboard():
    builder = InlineKeyboardBuilder()
    for cat_key, cat_data in FREE_DOCS.items():
        builder.button(text=cat_data["name"], callback_data=f"cat_{cat_key}")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def get_cases_keyboard():
    builder = InlineKeyboardBuilder()
    for case_id, case_data in cases_db.items():
        if case_data.get("published"):
            builder.button(text=f"📁 {case_id}. {case_data['title'][:30]}...", callback_data=f"case_{case_id}")
    builder.adjust(1)
    return builder.as_markup() if builder.buttons else None

def get_consult_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать вопрос", callback_data="consult_write")],
        [InlineKeyboardButton(text="🎤 Озвучить вопрос", callback_data="consult_speak")]
    ])

# ============================================
# КОМАНДА /start
# ============================================
async def send_welcome_post(message: Message):
    text = (
        "👋 Добро пожаловать!\n\n"
        "Меня зовут Эдуард Секриер, я юрист с 29-летним стажем.\n"
        "Здесь вы найдёте полезные материалы по ЖКХ, недвижимости, банкротству, наследству.\n\n"
        "📌 Чтобы продолжить, выберите нужный раздел в меню 👇"
    )
    await message.answer(text, reply_markup=get_main_keyboard())

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await send_welcome_post(message)

# ============================================
# КОМАНДА /help
# ============================================
@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📋 Доступные команды:\n\n"
        "👤 Для всех:\n"
        "/start - Начать работу\n"
        "/help - Это меню\n"
        "/calculator - Калькулятор ЖКХ\n"
        "/shop - Магазин договоров\n"
        "/consult - Консультация\n"
        "/free - Бесплатные документы\n"
        "/cases - Кейсы\n\n"
    )
    await message.answer(help_text)

# ============================================
# КОМАНДА /calculator
# ============================================
@dp.message(Command("calculator"))
async def cmd_calculator(message: Message):
    text = (
        "🧮 **Калькулятор коммунальных платежей**\n\n"
        "👉 [Открыть калькулятор](https://jkh-calculator-hrzuucss2p44fwj5bjeappd.streamlit.app)\n\n"
        "📌 Если калькулятор не открывается — напишите @SekrierEI"
    )
    await message.answer(text, parse_mode="Markdown")

# ============================================
# КОМАНДА /shop
# ============================================
@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    await message.answer("🛒 **МАГАЗИН ДОГОВОРОВ**\n\nВыберите договор:", reply_markup=get_shop_keyboard())

# ============================================
# КОМАНДА /free
# ============================================
@dp.message(Command("free"))
async def cmd_free(message: Message):
    await message.answer("📚 **БЕСПЛАТНЫЕ ДОКУМЕНТЫ**\n\nВыберите категорию:", reply_markup=get_free_categories_keyboard())

# ============================================
# КОМАНДА /cases
# ============================================
@dp.message(Command("cases"))
async def cmd_cases(message: Message):
    keyboard = get_cases_keyboard()
    if keyboard:
        await message.answer("📋 Выберите интересующий вас кейс:", reply_markup=keyboard)
    else:
        await message.answer("📭 Пока нет опубликованных кейсов.")

# ============================================
# КОМАНДА /consult
# ============================================
@dp.message(Command("consult"))
async def cmd_consult(message: Message):
    await message.answer("👨‍⚖️ Запись на консультацию\n\nВыберите способ обращения:", reply_markup=get_consult_main_keyboard())

# ============================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================
@dp.callback_query(lambda c: c.data == "menu_cases")
async def menu_cases(callback: CallbackQuery):
    await cmd_cases(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_free")
async def menu_free(callback: CallbackQuery):
    await cmd_free(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_shop")
async def menu_shop(callback: CallbackQuery):
    await cmd_shop(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_consult")
async def menu_consult(callback: CallbackQuery):
    await cmd_consult(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "menu_help")
async def menu_help(callback: CallbackQuery):
    await cmd_help(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.answer("📌 Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()

# ============================================
# ОБРАБОТЧИК КАТЕГОРИЙ БЕСПЛАТНЫХ ДОКУМЕНТОВ
# ============================================
@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def handle_category(callback: CallbackQuery):
    category_key = callback.data.replace("cat_", "")
    category = FREE_DOCS.get(category_key)
    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for doc_id, doc in category["items"].items():
        builder.button(text=doc["name"], callback_data=f"doc_{category_key}_{doc_id}")
    builder.button(text="◀️ Назад", callback_data="back_to_free")
    builder.adjust(1)
    await callback.message.answer(f"📁 **{category['name']}**\n\nВыберите документ:", reply_markup=builder.as_markup())

# ============================================
# ОБРАБОТЧИК ВЫБОРА ДОКУМЕНТА
# ============================================
@dp.callback_query(lambda c: c.data.startswith("doc_"))
async def handle_document(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    category_key = parts[1]
    doc_id = int(parts[2])
    category = FREE_DOCS.get(category_key)
    if not category or doc_id not in category["items"]:
        await callback.answer("Документ не найден", show_alert=True)
        return
    await callback.answer()
    doc = category["items"][doc_id]
    file_path = os.path.join("files", doc["file"])
    if os.path.exists(file_path):
        try:
            document = FSInputFile(file_path)
            await callback.message.answer_document(document, caption=f"📄 **{doc['name']}**\n\nФайл готов к скачиванию.")
        except Exception as e:
            logger.error(f"Ошибка отправки файла: {e}")
            await callback.message.answer("❌ Ошибка при отправке файла.")
    else:
        await callback.message.answer(f"❌ Файл не найден: {doc['file']}")

# ============================================
# ОБРАБОТЧИК НАЗАД К КАТЕГОРИЯМ
# ============================================
@dp.callback_query(lambda c: c.data == "back_to_free")
async def back_to_free(callback: CallbackQuery):
    await callback.answer()
    await cmd_free(callback.message)

# ============================================
# ОБРАБОТЧИК МАГАЗИНА ДОГОВОРОВ
# ============================================
class ContractStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_comment = State()

@dp.callback_query(lambda c: c.data.startswith("contract_"))
async def handle_contract(callback: CallbackQuery, state: FSMContext = None):
    contract_id = int(callback.data.split("_")[1])
    contract = CONTRACTS.get(contract_id)
    if not contract:
        await callback.answer("Договор не найден", show_alert=True)
        return
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Оставить заявку", callback_data=f"request_contract_{contract_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_shop")]
    ])
    await callback.message.answer(
        f"📄 **{contract['name']}**\n\n{contract['description']}\n\n💰 **Цена:** {contract['price']} ₽\n\nДля получения договора нажмите кнопку ниже.",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("request_contract_"))
async def request_contract(callback: CallbackQuery, state: FSMContext):
    contract_id = int(callback.data.split("_")[2])
    contract = CONTRACTS.get(contract_id)
    if not contract:
        await callback.answer("Договор не найден", show_alert=True)
        return
    await callback.answer()
    await state.update_data(contract_id=contract_id)
    await state.set_state(ContractStates.waiting_for_phone)
    await callback.message.answer("📞 Отправьте ваш номер телефона в формате: +7 123 456-78-90")

@dp.message(ContractStates.waiting_for_phone)
async def process_contract_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    import re
    if not re.search(r'^(\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$', phone):
        await message.answer("❌ Неверный формат. Пример: +7 123 456-78-90")
        return
    await state.update_data(phone=phone)
    await state.set_state(ContractStates.waiting_for_comment)
    await message.answer("📝 Напишите комментарий к заявке (или отправьте 'нет')")

@dp.message(ContractStates.waiting_for_comment)
async def process_contract_comment(message: Message, state: FSMContext):
    comment = message.text.strip()
    if comment.lower() in ['нет', 'skip', '-']:
        comment = "Без комментария"
    data = await state.get_data()
    contract = CONTRACTS.get(data['contract_id'])
    admin_id = config.get('ADMIN_ID')
    if admin_id:
        await bot.send_message(
            admin_id,
            f"🔔 **НОВЫЙ ЗАПРОС НА ДОГОВОР**\n\n📄 {contract['name']}\n💰 {contract['price']} ₽\n📞 {data['phone']}\n💬 {comment}\n👤 @{message.from_user.username}"
        )
    await message.answer(f"✅ Заявка на договор **{contract['name']}** принята. Мы свяжемся с вами.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "back_to_shop")
async def back_to_shop(callback: CallbackQuery):
    await callback.answer()
    await cmd_shop(callback.message)

# ============================================
# ОБРАБОТЧИКИ КОНСУЛЬТАЦИЙ
# ============================================
class ConsultStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_voice = State()

@dp.callback_query(lambda c: c.data == "consult_write")
async def consult_write(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ConsultStates.waiting_for_text)
    await callback.message.answer("✍️ **Напишите ваш вопрос**\n\nОтмена: /cancel")

@dp.callback_query(lambda c: c.data == "consult_speak")
async def consult_speak(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ConsultStates.waiting_for_voice)
    await callback.message.answer("🎤 **Отправьте голосовое сообщение**\n\nОтмена: /cancel")

@dp.message(ConsultStates.waiting_for_text)
async def process_consult_text(message: Message, state: FSMContext):
    admin_id = config.get('ADMIN_ID')
    if admin_id:
        await bot.send_message(admin_id, f"✍️ **ВОПРОС (текст)**\n\n👤 @{message.from_user.username}\n📝 {message.text}")
    await message.answer("✅ Вопрос принят. Я отвечу в ближайшее время.")
    await state.clear()

@dp.message(ConsultStates.waiting_for_voice)
async def process_consult_voice(message: Message, state: FSMContext):
    if not message.voice:
        await message.answer("❌ Отправьте голосовое сообщение.")
        return
    admin_id = config.get('ADMIN_ID')
    if admin_id:
        await message.forward(admin_id)
        await bot.send_message(admin_id, f"🎤 **ВОПРОС (голос)**\n\n👤 @{message.from_user.username}")
    await message.answer("✅ Голосовое сообщение принято.")
    await state.clear()

# ============================================
# КОМАНДА /cancel
# ============================================
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer("❌ Нет активных действий.")
        return
    await state.clear()
    await message.answer("✅ Действие отменено.")

# ============================================
# WEBHOOK НАСТРОЙКИ
# ============================================
async def on_startup_webhook():
    await bot.set_webhook(f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    print(f"✅ Вебхук установлен")

async def on_shutdown_webhook():
    await bot.delete_webhook()
    print("✅ Webhook удален")

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
app.on_startup.append(lambda _: on_startup_webhook())
app.on_shutdown.append(lambda _: on_shutdown_webhook())

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
    
# ============================================
# ПЛАНИРОВЩИК С ПУБЛИКАЦИЕЙ ПОСТОВ (УПРОЩЁННАЯ ВЕРСИЯ)
# ============================================

async def run_scheduler():
    """Функция планировщика, запускаемая в фоне"""
    logger.info("🚀 Планировщик запущен")
    
    while True:
        try:
            # Проверяем каждые 15 секунд
            await asyncio.sleep(15)
            
            now_utc = datetime.now()
            logger.info(f"⏰ Проверка постов в {now_utc.strftime('%H:%M:%S')} UTC")
            
            # Получаем все неопубликованные статьи
            all_articles = await db.get_articles_list()
            posts_to_publish = []
            
            for article in all_articles:
                if article.get('published'):
                    continue
                
                teaser_time_msk = article.get('teaser_time')
                if not teaser_time_msk:
                    continue
                
                teaser_time_utc = teaser_time_msk - timedelta(hours=3)
                
                if teaser_time_utc <= now_utc:
                    posts_to_publish.append(article)
                    logger.info(f"📊 Статья #{article['id']} ГОТОВА к публикации!")
            
            # Публикуем
            for post in posts_to_publish:
                try:
                    channel = config['CHANNEL_ID']
                    
                    post_text = (
                        f"📌 **ТЕМА ДНЯ**\n\n"
                        f"**{post['teaser_title']}**\n\n"
                        f"{post['teaser_text']}\n\n"
                        f"**ЧИТАТЬ ПОЛНОСТЬЮ В БОТЕ**\n"
                        f"https://t.me/uriskonsult_test_bot?start=article_{post['id']}"
                    )
                    
                    photo_file_id = post.get('teaser_photo')
                    logger.info(f"📸 Фото для статьи #{post['id']}: {photo_file_id}")
                    
                    if photo_file_id:
                        await bot.send_photo(
                            chat_id=channel,
                            photo=photo_file_id,
                            caption=post_text,
                            parse_mode='HTML'
                        )
                        logger.info(f"✅ Пост #{post['id']} опубликован С ФОТО")
                    else:
                        await bot.send_message(
                            chat_id=channel,
                            text=post_text,
                            parse_mode='HTML'
                        )
                        logger.info(f"✅ Пост #{post['id']} опубликован БЕЗ ФОТО")
                    
                    # Помечаем как опубликованное
                    await db.update_post_status(post['id'], 'published')
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста #{post['id']}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            await asyncio.sleep(10)
            
# ============================================
# СЛЕДУЮЩИЙ БЛОК (WEBHOOK НАСТРОЙКИ)
# ============================================

import json
from aiohttp import web

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEBHOOK_PATH = "/webhook"
PORT = int(os.getenv("PORT", 80))

@web.middleware
async def log_requests(request, handler):
    print(f"\n🔴🔴🔴 ПОЛУЧЕН HTTP-ЗАПРОС: {request.method} {request.path}")
    print(f"🔴 Headers: {dict(request.headers)}")
    try:
        body = await request.text()
        if body:
            body_preview = body[:500] + "..." if len(body) > 500 else body
            print(f"🔴 Body (первые 500 символов): {body_preview}")
            if 'application/json' in request.headers.get('Content-Type', ''):
                try:
                    json_body = json.loads(body)
                    print(f"🔴 JSON структура: {json.dumps(json_body, indent=2, ensure_ascii=False)[:500]}")
                except:
                    pass
    except Exception as e:
        print(f"🔴 Не удалось прочитать тело запроса: {e}")
    response = await handler(request)
    print(f"🔴 Ответ: {response.status}")
    return response

async def handle_root(request):
    return web.Response(
        text="✅ Бот работает! Webhook endpoint: /webhook\n"
             f"📊 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
             f"🔗 URL для вебхука: {WEBHOOK_URL}{WEBHOOK_PATH}"
    )

async def handle_health(request):
    return web.Response(text="OK", status=200)

async def on_startup_webhook():
    print("\n🚀🚀🚀 ЗАПУСК WEBHOOK НАСТРОЙКИ")
    
    if not WEBHOOK_URL:
        logger.error("❌ WEBHOOK_URL не задан!")
        print("❌ WEBHOOK_URL не задан!")
        return
    
    print(f"📌 Устанавливаем вебхук на: {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Старый вебхук удалён")
    
    await bot.set_webhook(
    url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
    allowed_updates=["message", "callback_query"]
)
    print(f"✅ Вебхук установлен на {WEBHOOK_URL}{WEBHOOK_PATH}")
    
    webhook_info = await bot.get_webhook_info()
    print(f"📊 Информация о вебхуке:")
    print(f"   URL: {webhook_info.url}")
    print(f"   Ожидающих обновлений: {webhook_info.pending_update_count}")
    print(f"   Последняя ошибка: {webhook_info.last_error_message}")
    
    asyncio.create_task(run_scheduler())
    asyncio.create_task(reset_limits_daily())
    
    await db.connect()
    
    logger.info("✅ Бот готов к работе через webhook")
    print("✅ Бот готов к работе через webhook")

async def on_shutdown_webhook():
    print("\n🛑🛑🛑 ОСТАНОВКА WEBHOOK")
    await bot.delete_webhook()
    print("✅ Webhook удален")
    
    if hasattr(db, 'pool') and db.pool:
        await db.pool.close()
    
    await bot.session.close()
    logger.info("👋 Бот остановлен")
    print("👋 Бот остановлен")

app = web.Application(middlewares=[log_requests])
app.router.add_get('/', handle_root)
app.router.add_get('/health', handle_health)

print(f"📌 Регистрируем обработчик вебхуков на путь: {WEBHOOK_PATH}")
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

app.on_startup.append(lambda _: on_startup_webhook())
app.on_shutdown.append(lambda _: on_shutdown_webhook())

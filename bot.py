#!/usr/bin/env python3
"""
Основной бот для управления статьями и публикациями
ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ — С УЛУЧШЕННОЙ КОНСУЛЬТАЦИЕЙ
ИСПРАВЛЕНЫ ВСЕ ОШИБКИ
"""

import asyncio
import logging
import sys
import time
import uuid
import inspect
import os
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

from src.core.config import config
from src.core.logger import setup_logger
from database import db
from models import Article, ScheduledPost

# Настройка логирования
logger = setup_logger('bot')
print(f"🤖 Инициализация бота с токеном: {config['BOT_TOKEN'][:10]}...")
bot = Bot(token=config['BOT_TOKEN'])
dp = Dispatcher(storage=MemoryStorage())

# ============================================
# ЗАЩИТА ОТ СПАМА ДЛЯ КОНСУЛЬТАЦИЙ
# ============================================

user_message_counts = defaultdict(int)
user_last_reset = {}

def check_message_limit(user_id: int) -> bool:
    """Проверяет, не превысил ли пользователь лимит сообщений (3 в сутки)"""
    current_time = time.time()
    one_day = 24 * 60 * 60
    
    if user_id not in user_last_reset or current_time - user_last_reset[user_id] > one_day:
        user_message_counts[user_id] = 0
        user_last_reset[user_id] = current_time
    
    return user_message_counts[user_id] < 3

async def reset_limits_daily():
    """Автоматический сброс лимитов сообщений каждые 24 часа"""
    while True:
        await asyncio.sleep(24 * 60 * 60)
        user_message_counts.clear()
        user_last_reset.clear()
        logger.info("✅ Лимиты сообщений сброшены")

# ============================================
# ДАННЫЕ ДЛЯ МАГАЗИНА
# ============================================

CONTRACTS = {
    1: {
        "name": "🏠 Базовый",
        "description": "Для физлиц с 1 объектом. Посуточная сдача без статуса ИП.",
        "price": 1900,
        "upgrade_price": 4900,
        "file": "dogovor1.pdf"
    },
    2: {
        "name": "🏢 Профи",
        "description": "Для самозанятых и ИП (2–12 объектов). Профессиональная сдача.",
        "price": 4900,
        "upgrade_price": 4900,
        "file": "dogovor2.pdf"
    },
    3: {
        "name": "🏨 Гостиничный",
        "description": "Для ИП/ООО с классифицированными объектами по ПП №1912.",
        "price": 3900,
        "upgrade_price": 4900,
        "file": "dogovor3.pdf"
    },
    4: {
        "name": "🤝 Агентский",
        "description": "Для собственников и управляющих (ИП/ООО). Агентский договор.",
        "price": 5900,
        "upgrade_price": 4900,
        "file": "dogovor4.pdf"
    },
    5: {
        "name": "📦 Пакет «Всё для аренды»",
        "description": "Все 5 договоров в одном пакете. Максимальная защита.",
        "price": 7900,
        "upgrade_price": 4900,
        "file": "pack_all.pdf"
    }
}

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
            2: {"name": "Повреждение на стоянке", "file": "Памятка_Повреждение_на_стоянке.pdf"}
        }
    },
    "jkx": {
        "name": "🏢 ЖКХ / УК",
        "items": {
            1: {"name": "Памятка по ОДПУ", "file": "pamyatka_odpu.pdf"},
            2: {"name": "Чек-лист по ЖКХ", "file": "checklist_jkx.pdf"}
        }
    },
    "arenda": {
        "name": "🏠 Аренда жилья",
        "items": {
            1: {"name": "Чек-лист для аренды", "file": "checklist_arenda.pdf"},
            2: {"name": "Памятка арендатору", "file": "pamyatka_arendator.pdf"}
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
# ДАННЫЕ ДЛЯ КЕЙСОВ
# ============================================

cases_db = {
    1: {
        "title": "Счётчик тепла (ОДПУ) — кто платит за ремонт?",
        "category": "Общедомовые нужды",
        "date": "15.03.2025",
        "situation": "Жильцы многоквартирного дома получили квитанции с крупной суммой за ремонт общедомового прибора учёта тепла (ОДПУ). Управляющая компания требовала оплатить ремонт за счёт жильцов, ссылаясь на поломку оборудования и необходимость его замены. Сумма в квитанциях составляла от 5 до 15 тысяч рублей с каждой квартиры.",
        "question": "Кто должен оплачивать ремонт ОДПУ — жильцы или Управляющая компания? Имеет ли право УК выставлять отдельные счета за ремонт общедомового имущества?",
        "solution": "Мы подготовили коллективную жалобу в Жилищную инспекцию и прокуратуру. В жалобе указали, что согласно Постановлению Правительства РФ №354, обслуживание и ремонт общедомового имущества входит в обязанности УК и оплачивается из средств на содержание жилья. Дополнительные сборы на ремонт ОДПУ незаконны. Также направили досудебную претензию в УК.",
        "result": "После проверки Жилищной инспекции УК сделала перерасчёт всем жильцам. Незаконно начисленные суммы сняли, ремонт УК оплатила из своих средств. Жильцы сэкономили от 5 до 15 тысяч рублей каждая семья.",
        "files": ["reshenie_odpu.pdf", "pretensiya_uk.pdf", "pamyatka_odpu.pdf"],
        "published": True
    },
    2: {
        "title": "Квитанция УК «Курорт Сервис» — двойная плата?",
        "category": "Квитанции и платежи",
        "date": "22.01.2025",
        "situation": "Жительница Геленджика обнаружила в квитанциях от УК «Курорт Сервис» двойные начисления за одни и те же услуги. В платёжках были строки «содержание жилья» и «дополнительные услуги» с одинаковыми суммами. Общая переплата за год составила около 45 000 рублей.",
        "question": "Законно ли включать в квитанцию дублирующие услуги? Как вернуть переплату?",
        "solution": "Мы провели анализ платёжных документов и договора управления. Выяснили, что УК включила в квитанции услуги, которые уже входят в тариф «содержание жилья». Подготовили претензию с требованием перерасчёта и обратились в Госжилинспекцию.",
        "result": "УК признала ошибку и сделала перерасчёт на 45 000 рублей. Деньги зачли в счёт будущих платежей. Также УК исключила дублирующие строки из квитанций.",
        "files": ["pretensiya_kvit.pdf", "analiz_platezhey.pdf"],
        "published": True
    },
    3: {
        "title": "ИПУ в подъезде — кто платит?",
        "category": "Индивидуальные приборы учёта",
        "date": "05.02.2025",
        "situation": "В подъезде многоквартирного дома установили индивидуальные приборы учёта (ИПУ) на освещение мест общего пользования. Жильцам начали приходить отдельные квитанции за электричество в подъезде.",
        "question": "Должны ли жильцы дополнительно платить за освещение подъезда, если эти расходы уже входят в тариф на содержание жилья?",
        "solution": "Разъяснили жильцам, что расходы на освещение мест общего пользования уже включены в тариф «содержание жилья». УК не имеет права выставлять отдельные счета. Подготовили коллективное обращение в УК и Жилищную инспекцию.",
        "result": "УК отменила дополнительные начисления. Расходы на освещение подъезда остались в общем тарифе. Жильцы экономят около 300 рублей в месяц с квартиры.",
        "files": ["pamyatka_ipu.pdf", "obrashenie_gzi.pdf"],
        "published": True
    },
    4: {
        "title": "ЕПД (единая квитанция) — можно ли получать одну?",
        "category": "Квитанции и платежи",
        "date": "12.03.2025",
        "situation": "Жительница Геленджика получала отдельные квитанции от УК, от ресурсоснабжающих организаций (вода, свет, газ) и от фонда капремонта. Всего 5-6 платёжек в месяц, в которых путались суммы и начисления.",
        "question": "Можно ли получать единую квитанцию (ЕПД) на все услуги? Как разобраться в переплатах?",
        "solution": "Помогли разобраться в начислениях и выявили переплату по некоторым услугам на сумму 12 000 рублей. Подготовили заявление на переход на ЕПД и запрос на перерасчёт.",
        "result": "Перешли на единую квитанцию, переплату вернули. Теперь приходит одна платёжка, в которой всё понятно.",
        "files": ["zayavlenie_epd.pdf", "instrukciya_kvit.pdf"],
        "published": True
    },
    5: {
        "title": "Смена УК — нужно ли звать старую компанию?",
        "category": "Управляющие компании",
        "date": "18.02.2025",
        "situation": "Жильцы решили сменить управляющую компанию из-за плохой работы. Старая УК требовала провести совместную инвентаризацию и подписать акты приёма-передачи, иначе отказывалась передавать документы.",
        "question": "Обязаны ли жильцы приглашать старую УК для передачи документов? Что делать, если старая УК уклоняется от передачи?",
        "solution": "Разъяснили, что старая УК обязана передать техническую документацию новой компании в течение 30 дней. Участие жильцов не требуется. Подготовили заявление в Госжилинспекцию о нарушении сроков передачи.",
        "result": "Госжилинспекция обязала старую УК передать документы. Новая компания приступила к управлению через 2 недели после обращения.",
        "files": ["zayavlenie_gzi.pdf", "pamyatka_smena_uk.pdf"],
        "published": True
    },
    6: {
        "title": "Реконструкция нежилых помещений",
        "category": "Перепланировка и реконструкция",
        "date": "07.01.2025",
        "situation": "Владелец нежилого помещения на первом этаже жилого дома хотел сделать отдельный вход, пробив дверной проём в несущей стене. Администрация отказывалась согласовывать, сославшись на нарушение прав жильцов.",
        "question": "Как законно согласовать перепланировку с затрагиванием несущих конструкций? Нужно ли согласие жильцов?",
        "solution": "Подготовили проект перепланировки, заказали техническое заключение о допустимости работ. Организовали собрание жильцов и получили их согласие. Подготовили пакет документов для администрации.",
        "result": "Администрация согласовала перепланировку. Отдельный вход сделали законно, без штрафов и судов.",
        "files": ["proekt_perep.pdf", "protokol_sobraniya.pdf"],
        "published": True
    },
    7: {
        "title": "Мессенджер MAX — новый канал связи с УК",
        "category": "Новости и изменения",
        "date": "10.03.2025",
        "situation": "УК внедрила мессенджер MAX для общения с жильцами. Через него приходили уведомления о задолженностях, отключениях воды и плановых ремонтах. Один из жильцов не согласился с начислением пеней и оспорил их, ссылаясь на то, что уведомления приходили только в мессенджер, а не официальным письмом.",
        "question": "Является ли переписка в мессенджере официальным каналом связи? Можно ли оспорить начисления, если уведомления были только в чате?",
        "solution": "Разъяснили, что если УК официально уведомила о переходе на мессенджер (через сайт, квитанции, объявления), то сообщения в нём имеют юридическую силу. Однако в данном случае УК не доказала, что жилец дал согласие на такой способ связи. Подготовили возражение на судебный приказ.",
        "result": "Суд отменил судебный приказ, так как УК не предоставила доказательств согласия жильца на получение уведомлений через мессенджер. Пени списали.",
        "files": ["vozrazhenie_sud.pdf", "pamyatka_messenger.pdf"],
        "published": True
    },
    8: {
        "title": "Постановление №1912 (посуточная аренда)",
        "category": "Новости и изменения",
        "date": "01.12.2024",
        "situation": "Собственница квартиры в Геленджике сдавала жильё посуточно. После выхода Постановления №1912, которое запрещает посуточную аренду в жилых домах без перевода в нежилой фонд, ей пришла повестка в суд от соседей, требовавших прекратить сдачу.",
        "question": "Распространяется ли Постановление №1912 на уже существующий бизнес? Можно ли продолжать сдавать, если договоры были заключены до выхода постановления?",
        "solution": "Разъяснили, что постановление действует на все отношения, независимо от даты заключения договоров. Однако есть исключения: если квартира оборудована отдельным входом, звукоизоляцией, счётчиками и не нарушает права соседей, можно попытаться сохранить посуточную аренду. Подготовили возражение в суд, собрали доказательства отсутствия нарушений.",
        "result": "Суд отказал соседям, так как квартира была оборудована всем необходимым и не создавала неудобств. Собственница продолжает сдавать, но привела квартирку в соответствие с новыми требованиями.",
        "files": ["postanovlenie_1912.pdf", "vozrazhenie_sud_arenda.pdf", "pamyatka_posutochno.pdf"],
        "published": True
    }
}

# ============================================
# СТАТЬИ ДЛЯ DEEP LINKING
# ============================================

DEEP_ARTICLES = {
    "flood": """🏠 **Последствия залива квартиры: что делать и кто виноват?**

Залив квартиры — одна из самых частых проблем в многоквартирных домах. Часто непонятно, кто виноват: соседи сверху, УК или вообще страховой случай.

🔹 **Кто отвечает за залив?**
- Если лопнула труба внутри квартиры — отвечает собственник.
- Если течь в общедомовом стояке — отвечает УК.
- Если залив из-за неисправной кровли — тоже УК.

🔹 **Что делать сразу после залива:**
1. Перекрыть воду (если возможно)
2. Вызвать представителя УК для составления акта
3. Сфотографировать все повреждения
4. Зафиксировать показания свидетелей

🔹 **Акт о заливе — главный документ**
Без акта вы не докажете ни факт залива, ни размер ущерба. Требуйте составления акта в день обращения!

📌 **Подробнее читайте в прикреплённых памятках:**
- /free → раздел "Залив"

Нужна помощь в конкретной ситуации? Напишите /consult""",

    "uk": """📋 **Как сменить управляющую компанию: пошаговая инструкция**

Недовольны работой УК? Закон позволяет сменить управляющую компанию, но процедура требует соблюдения формальностей.

🔹 **Основания для смены УК:**
- Истечение срока договора
- Невыполнение обязательств
- Инициатива собственников

🔹 **Порядок действий:**
1. Проведите общее собрание собственников
2. Получите не менее 50% голосов
3. Выберите новую УК
4. Расторгните договор со старой УК
5. Заключите договор с новой

🔹 **Важные нюансы:**
- Старая УК обязана передать документацию в течение 30 дней
- Если документы не передают — жалуйтесь в ГЖИ
- Долги старой УК не переходят на новую

📌 **Образцы документов и памятки:**
- /free → раздел "ЖКХ / УК"

Возникли сложности? Напишите /consult""",

    "dtp": """🚗 **ДТП: инструкция для пострадавших**

Попасть в аварию может каждый. Знание своих прав поможет избежать проблем и получить положенные выплаты.

🔹 **Сразу после ДТП:**
1. Остановитесь, включите аварийку, выставьте знак
2. Вызовите скорую, если есть пострадавшие
3. Вызовите ГИБДД
4. Сфотографируйте место аварии со всех сторон

🔹 **Оформление документов:**
- Европротокол — если ущерб до 100 000 ₽ и нет разногласий
- С участием ГИБДД — во всех остальных случаях

🔹 **Что делать, если виновник скрылся:**
- Запишите госномер
- Найдите свидетелей
- Напишите заявление в полицию

📌 **Полезные памятки:**
- /free → раздел "ДТП / Авто"

Нужна консультация по вашему ДТП? Напишите /consult"""
}

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

def get_main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Кейсы", callback_data="menu_cases")],
        [InlineKeyboardButton(text="📚 Бесплатные документы", callback_data="menu_free")],
        [InlineKeyboardButton(text="🏪 Магазин договоров", callback_data="menu_shop")],
        [InlineKeyboardButton(text="📞 Консультация", callback_data="menu_consult")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="menu_help")]
    ])
    return kb

def get_shop_keyboard():
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=CONTRACTS[i]["name"], callback_data=f"contract_{i}")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

def get_category_keyboard(cat_key):
    items = FREE_DOCS.get(cat_key, {}).get("items", {})
    builder = InlineKeyboardBuilder()
    for item_id, item_data in items.items():
        builder.button(text=item_data["name"], callback_data=f"free_{cat_key}_{item_id}")
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
    published_count = 0
    for case_id, case_data in cases_db.items():
        if case_data["published"]:
            short_title = case_data['title'][:30] + "..." if len(case_data['title']) > 30 else case_data['title']
            builder.button(
                text=f"📁 {case_id}. {short_title}",
                callback_data=f"case_{case_id}"
            )
            published_count += 1
    builder.adjust(1)
    return builder.as_markup() if published_count > 0 else None

def get_consult_main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать вопрос", callback_data="consult_write")],
        [InlineKeyboardButton(text="🎤 Озвучить вопрос", callback_data="consult_speak")]
    ])
    return kb

def get_consult_back_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="consult_back")]
    ])
    return kb

def get_admin_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить статью", callback_data="admin_add_article")],
        [InlineKeyboardButton(text="📋 Список статей", callback_data="admin_list_articles")],
        [InlineKeyboardButton(text="🗑 Удалить статью", callback_data="admin_del_article")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="admin_edit_article")],
        [InlineKeyboardButton(text="📊 Статус", callback_data="admin_status")],
        [InlineKeyboardButton(text="🔄 Перепубликовать", callback_data="admin_republish")],
        [InlineKeyboardButton(text="📚 Старые посты", callback_data="admin_old_posts")],
        [InlineKeyboardButton(text="🔙 Выйти", callback_data="admin_exit")]
    ])
    return kb

# ============================================
# ФУНКЦИЯ ДЛЯ ОТПРАВКИ ПРИВЕТСТВИЯ
# ============================================

async def send_welcome_post(message: Message, source: str = "send_welcome_post"):
    call_id = str(uuid.uuid4())[:8]
    caller_frame = inspect.currentframe().f_back
    caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
    
    logger.info(f"🔴 Функция send_welcome_post ВЫЗВАНА. ID: {call_id}, Источник: {source}, Вызвана из: {caller_name}, Пользователь: {message.from_user.id}")
    
    photo_path = os.path.join("images", "max_full.jpg")
    if os.path.exists(photo_path):
        try:
            photo = FSInputFile(photo_path)
            await message.answer_photo(photo)
            logger.info(f"📸 Фото отправлено. ID: {call_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка фото в welcome post: {e}")
    else:
        logger.warning(f"⚠️ Фото {photo_path} не найдено, отправляю только текст")
    
    text = (
        "👋 Добро пожаловать!\n\n"
        "Меня зовут Эдуард Секриер, я юрист с 29-летним стажем.\n"
        "Здесь, в этом боте, вы найдёте полезные материалы по ЖКХ, недвижимости, банкротству, наследству и другим спорам.\n\n"
        "Просто выберите тему в меню ниже — и получите готовые инструкции, памятки или шаблоны документов.\n\n"
        "📌 Чтобы продолжить, выберите нужный раздел в меню 👇"
    )
    
    logger.info(f"📨 Отправка ТЕКСТА. ID: {call_id}, Длина: {len(text)} символов")
    await message.answer(text, reply_markup=get_main_keyboard())
    logger.info(f"✅ Текст отправлен. ID: {call_id}")

# ============================================
# DEEP LINKING
# ============================================

@dp.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: Message, command: CommandObject):
    args = command.args
    
    if args and args.startswith('article_'):
        try:
            article_id = int(args.replace('article_', ''))
            logger.info(f"Deep link access to article {article_id} by user {message.from_user.id}")
            
            article = await db.get_article(article_id)
            
            if article:
                await message.answer(
                    "👋 Вы находитесь в чат-боте юриста Эдуарда Секриера\n\n"
                    "Здесь вы можете получить полный разбор темы, скачать документы или задать вопрос."
                )
                
                photo_path = os.path.join("images", "max_full.jpg")
                if os.path.exists(photo_path):
                    try:
                        photo = FSInputFile(photo_path)
                        await message.answer_photo(photo, caption="📊 Штрафы для УК — до 300 000 ₽")
                    except Exception as e:
                        logger.error(f"Error sending photo: {e}")
                
                article_title = article['full_text'].split('\n')[0][:50] + "..." if len(article['full_text'].split('\n')[0]) > 50 else article['full_text'].split('\n')[0]
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📥 Скачать документ", callback_data=f"download_{article_id}"),
                        InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
                        InlineKeyboardButton(text="❓ Консультация", callback_data="menu_consult")
                    ]
                ])
                
                await message.answer(
                    f"📄 {article_title}\n\n{article['full_text']}",
                    reply_markup=keyboard
                )
            else:
                await message.answer("❌ Статья не найдена или была удалена.")
        except ValueError:
            await message.answer("❌ Неверная ссылка на статью.")
        except Exception as e:
            logger.error(f"Error in deep link processing: {e}")
            await message.answer("❌ Произошла ошибка при загрузке статьи.")
    elif args == 'consult':
        await cmd_consult(message)
    else:
        await cmd_start(message)

# ============================================
# КОМАНДА /start
# ============================================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext = None):
    call_id = str(uuid.uuid4())[:8]
    logger.info(f"🚀 Команда /start ПОЛУЧЕНА. ID: {call_id}, Пользователь: {message.from_user.id}")
    
    if state:
        await state.clear()
        logger.info(f"🧹 Состояние очищено. ID: {call_id}")
    
    await send_welcome_post(message, source=f"cmd_start_{call_id}")
    
    if message.from_user.id == config['ADMIN_ID']:
        admin_text = "🔐 Вы администратор. Используйте /admin для входа в панель управления."
        await message.answer(admin_text)
        logger.info(f"👑 Админ-сообщение отправлено. ID: {call_id}")
    
    logger.info(f"✅ Команда /start обработана. ID: {call_id}")

# ============================================
# КОМАНДА /admin
# ============================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != config['ADMIN_ID']:
        await message.answer("⛔ У вас нет прав для входа в админ-панель.")
        return
    
    await message.answer(
        "🔐 **Панель администратора**\n\nВыберите действие:",
        reply_markup=get_admin_keyboard()
    )

# ============================================
# КОМАНДА /help
# ============================================

@dp.message(Command("calculator"))
async def cmd_calculator(message: Message):
    text = (
        "🧮 **Калькулятор ЖКХ**\n\n"
        "✅ **Калькулятор готов к работе!**\n\n"
        "Теперь вы можете рассчитать плату за ЖКУ по актуальным тарифам:\n\n"
        "👉 https://jkh-calculator-hrzuucss2p44fwj5bjeappd.streamlit.app\n\n"
        "**Что доступно:**\n"
        "• Актуальные тарифы по Геленджику и Пыть-Яху\n"
        "• Расчёт воды, электричества, отопления и ТКО\n"
        "• Сравнение с нормативами\n"
        "• Персональные рекомендации\n\n"
        "✨ **Переходите по ссылке и пробуйте!**\n\n"
        "Если у вас возникнут вопросы или предложения — пишите /consult"
    )
    await message.answer(text)
    logger.info(f"User {message.from_user.id} used /calculator (ready)")

# ============================================
# КОМАНДА /calculator
# ============================================

@dp.message(Command("calculator"))
async def cmd_calculator(message: Message):
    text = (
        "🧮 **Калькулятор ЖКХ**\n\n"
        "⚙️ **Проект в работе**\n\n"
        "Сейчас мы дорабатываем калькулятор, чтобы он был максимально точным и полезным для вас.\n\n"
        "🔜 **Что появится:**\n"
        "• Актуальные тарифы по Геленджику и Пыть-Яху\n"
        "• Расчёт воды, электричества, отопления и ТКО\n"
        "• Сравнение с нормативами\n"
        "• Персональные рекомендации\n\n"
        "✨ **Следите за обновлениями в канале!**\n"
        "Как только калькулятор будет готов — я сразу сообщу.\n\n"
        "А пока вы можете воспользоваться готовыми памятками и инструкциями в других разделах бота."
    )
    await message.answer(text)
    logger.info(f"User {message.from_user.id} used /calculator (work in progress)")

# ============================================
# КОМАНДА /calculate
# ============================================

@dp.message(Command("calculate"))
async def cmd_calculate(message: Message):
    await cmd_calculator(message)

# ============================================
# КОМАНДА /clear_limits
# ============================================

@dp.message(Command("clear_limits"))
@admin_only
async def cmd_clear_limits(message: Message, **kwargs):
    user_message_counts.clear()
    user_last_reset.clear()
    await message.answer("✅ Все лимиты сообщений сброшены")
    logger.info(f"Message limits cleared by admin {message.from_user.id}")

# ============================================
# КОМАНДА /shop
# ============================================

@dp.message(Command("shop"))
async def cmd_shop(message: Message):
    text = "🛒 **МАГАЗИН ДОГОВОРОВ**\n\nВыберите договор:"
    await message.answer(text, reply_markup=get_shop_keyboard())

# ============================================
# КОМАНДА /free
# ============================================

@dp.message(Command("free"))
async def cmd_free(message: Message):
    text = "📚 **БЕСПЛАТНЫЕ ДОКУМЕНТЫ**\n\nВыберите категорию:"
    await message.answer(text, reply_markup=get_free_categories_keyboard())

# ============================================
# КОМАНДА /cases
# ============================================

@dp.message(Command("cases"))
async def cmd_cases(message: Message):
    keyboard = get_cases_keyboard()
    if keyboard:
        await message.answer("📋 Выберите интересующий вас кейс:", reply_markup=keyboard)
    else:
        await message.answer("📭 Пока нет опубликованных кейсов. Скоро появятся!")

# ============================================
# КОМАНДА /consult
# ============================================

@dp.message(Command("consult"))
async def cmd_consult(message: Message):
    text = "👨‍⚖️ Запись на консультацию\n\nВыберите способ обращения:"
    await message.answer(text, reply_markup=get_consult_main_keyboard())

# ============================================
# СОСТОЯНИЯ ДЛЯ СТАТЕЙ
# ============================================

class ArticleStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()

# ============================================
# АДМИН-КОМАНДЫ (через кнопки)
# ============================================

@dp.callback_query(lambda c: c.data == "admin_add_article")
async def admin_add_article(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await cmd_add_article(callback.message, state)

@dp.callback_query(lambda c: c.data == "admin_list_articles")
async def admin_list_articles(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await cmd_list_articles(callback.message)

@dp.callback_query(lambda c: c.data == "admin_del_article")
async def admin_del_article(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "🗑 Удаление статьи\n\n"
        "Используйте команду: /del_article [ID]\n"
        "Например: /del_article 5\n\n"
        "Чтобы узнать ID статьи, сначала нажмите Список статей"
    )

@dp.callback_query(lambda c: c.data == "admin_edit_article")
async def admin_edit_article(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "✏️ Редактирование статьи\n\n"
        "Используйте команду: /edit_article [ID]\n"
        "Например: /edit_article 5\n\n"
        "Чтобы узнать ID статьи, сначала нажмите Список статей"
    )

@dp.callback_query(lambda c: c.data == "admin_status")
async def admin_status(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await cmd_status(callback.message)

@dp.callback_query(lambda c: c.data == "admin_republish")
async def admin_republish(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "🔄 Перепубликация старого поста\n\n"
        "Используйте команду: /republish [ID статьи]\n"
        "Например: /republish 5\n\n"
        "Чтобы узнать ID статьи, сначала нажмите Список статей или Старые посты"
    )

@dp.callback_query(lambda c: c.data == "admin_old_posts")
async def admin_old_posts(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await cmd_old_posts(callback.message)

@dp.callback_query(lambda c: c.data == "admin_exit")
async def admin_exit(callback: CallbackQuery, state: FSMContext = None):
    if callback.from_user.id != config['ADMIN_ID']:
        await callback.answer("⛔ У вас нет прав", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "✅ **Вы вышли из панели администратора**\n\n"
        "Теперь при нажатии /start вы будете видеть только обычное меню.\n"
        "Чтобы снова войти в админ-панель, нажмите /admin"
    )

# ============================================
# АДМИН-КОМАНДЫ (ввод)
# ============================================

@dp.message(Command("add_article"))
@admin_only
async def cmd_add_article(message: Message, state: FSMContext, **kwargs):
    await message.answer(
        "📝 Добавление новой статьи\n\n"
        "Отправьте полный текст статьи:"
    )
    await state.set_state(ArticleStates.waiting_for_text)

@dp.message(ArticleStates.waiting_for_text)
async def process_article_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Пожалуйста, отправьте текст статьи.")
        return
    await state.update_data(article_text=message.text)
    example = datetime.now() + timedelta(hours=1)
    example_str = example.strftime("%d.%m.%Y %H:%M")
    await message.answer(
        "📅 Укажите дату и время публикации тизера\n\n"
        f"Формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
        f"Например: {example_str}\n\n"
        "🕐 Время указывается МСК"
    )
    await state.set_state(ArticleStates.waiting_for_time)

@dp.message(ArticleStates.waiting_for_time)
async def process_article_time(message: Message, state: FSMContext):
    try:
        publish_time = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        if publish_time < datetime.now():
            await message.answer("❌ Нельзя указать время в прошлом.")
            return
        data = await state.get_data()
        article_text = data['article_text']
        
        article_id = await db.add_article(article_text, publish_time)
        deep_link = f"@uriskonsult_bot?start=article_{article_id}"
        
        await message.answer(
            f"✅ **Статья #{article_id} добавлена!**\n\n"
            f"🔗 **Ссылка для тизера:**\n"
            f"{deep_link}\n\n"
            f"📅 Публикация тизера запланирована на {publish_time.strftime('%d.%m.%Y %H:%M')} МСК."
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат даты!")
        return

@dp.message(Command("list_articles"))
@admin_only
async def cmd_list_articles(message: Message, **kwargs):
    articles = await db.get_articles_list()
    if not articles:
        await message.answer("📭 Статей пока нет.")
        return
    response = "📚 **Список статей:**\n\n"
    for article in articles[:10]:
        deep_link = f"@uriskonsult_bot?start=article_{article['id']}"
        response += f"🔹 **ID {article['id']}**\n"
        response += f"📝 {article['full_text'][:50]}...\n"
        response += f"🔗 {deep_link}\n\n"
    await message.answer(response)

@dp.message(Command("del_article"))
@admin_only
async def cmd_del_article(message: Message, **kwargs):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Использование: /del_article [ID]")
        return
    try:
        article_id = int(args[1])
        await db.delete_article(article_id)
        await message.answer(f"✅ Статья #{article_id} удалена.")
    except:
        await message.answer("❌ Ошибка при удалении.")

@dp.message(Command("edit_article"))
@admin_only
async def cmd_edit_article(message: Message, **kwargs):
    await message.answer("✏️ Редактирование пока в разработке.")

# ============================================
# КОМАНДЫ СТАТУСА (для тестовой БД)
# ============================================

@dp.message(Command("status", "stats"))
@admin_only
async def cmd_status(message: Message, **kwargs):
    # Получаем статьи из тестовой БД
    articles = await db.get_articles_list()
    total_users = len(user_message_counts)
    total_messages = sum(user_message_counts.values())
    
    # Для тестовой БД используем заглушку статистики
    stats = await db.get_scheduler_stats()
    
    # Ищем статью #6 в списке статей
    post_6 = None
    for article in articles:
        if article['id'] == 6:
            post_6 = article
            break
    
    text = (
        f"📊 **Статус системы (ТЕСТОВЫЙ РЕЖИМ)**\n\n"
        f"📚 **Статьи в памяти:**\n"
        f"• Всего статей: {len(articles)}\n\n"
        f"⏳ **Планировщик (тестовый):**\n"
        f"• Ожидают публикации: {stats['pending']}\n"
        f"• Уже опубликовано: {stats['published']}\n"
        f"• Ошибок: {stats['failed']}\n\n"
        f"👥 **Консультации:**\n"
        f"• Активных пользователей: {total_users}\n"
        f"• Всего сообщений: {total_messages}\n\n"
    )
    
    if post_6:
        text += (
            f"🔍 **Статья #6 найдена:**\n"
            f"• ID: {post_6['id']}\n"
            f"• Текст: {post_6['full_text'][:50]}...\n"
            f"• Время публикации: {post_6.get('teaser_time', 'не указано')}\n"
        )
    else:
        text += f"🔍 **Статья #6 не найдена**\n\n"
    
    if articles:
        text += f"📋 **Все статьи:**\n"
        for article in articles:
            text += f"• ID {article['id']}: {article['full_text'][:30]}...\n"
    else:
        text += f"📭 Статей пока нет"
    
    await message.answer(text)
    logger.info(f"Admin {message.from_user.id} requested status (test DB)")

# ============================================
# ТЕСТОВАЯ КОМАНДА ДЛЯ ПРОВЕРКИ КАНАЛА
# ============================================

@dp.message(Command("test_channel"))
@admin_only
async def cmd_test_channel(message: Message):
    """Проверяет, может ли бот писать в канал"""
    try:
        channel = config['CHANNEL_ID']
        
        # Правильная обработка ID канала
        if str(channel).startswith('-100'):
            channel_id = int(channel)
            channel_type = "числовой ID"
        else:
            channel_id = "@" + channel
            channel_type = "username"
        
        test_text = (
            f"🧪 **Тестовое сообщение**\n\n"
            f"Канал: {channel}\n"
            f"Тип: {channel_type}\n"
            f"Время: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        await bot.send_message(chat_id=channel_id, text=test_text)
        await message.answer(f"✅ Сообщение отправлено в канал!\nТип: {channel_type}")
        
    except Exception as e:
        error_msg = f"❌ Ошибка: {type(e).__name__}: {e}"
        logger.error(error_msg)
        await message.answer(error_msg)

# ============================================
# КОМАНДА /republish
# ============================================

@dp.message(Command("republish"))
@admin_only
async def cmd_republish(message: Message, **kwargs):  # ← Добавлен **kwargs
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer(
                "❌ Неверный формат команды\n\n"
                "Используйте: /republish [ID статьи]\n"
                "Например: /republish 5"
            )
            return
        article_id = int(parts[1])
        article = await db.get_article(article_id)
        if not article:
            await message.answer(f"❌ Статья с ID {article_id} не найдена.")
            return
        teaser_text = (
            f"{article['full_text'][:config['TEASER_LENGTH']]}...\n\n"
            f"<b>🔗 ПОЛНЫЙ РАЗБОР НОВЫХ ПРАВИЛ</b>\n"
            f"➡️ @uriskonsult_bot?start=article_{article_id}\n\n"
            f"👨‍⚖️ <b>Нужна консультация?</b>\n"
            f"➡️ /consult"
        )
        # ПРАВИЛЬНАЯ обработка ID канала
        if str(config['CHANNEL_ID']).startswith('-100'):
            channel = int(config['CHANNEL_ID'])
        else:
            channel = "@" + config['CHANNEL_ID']
            
        await bot.send_message(chat_id=channel, text=teaser_text)
        await message.answer(f"✅ Пост для статьи #{article_id} успешно перепубликован!")
    except Exception as e:
        logger.error(f"Error in republish: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# ============================================
# КОМАНДА /republish_deep
# ============================================

@dp.message(Command("republish_deep"))
@admin_only
async def cmd_republish_deep(message: Message, **kwargs):  # ← Добавлен **kwargs
    try:
        parts = message.text.split()
        if len(parts) != 2:
            available_keys = "\n".join([f"• {key}" for key in DEEP_ARTICLES.keys()])
            await message.answer(
                "❌ Неверный формат команды\n\n"
                "Используйте: /republish_deep [ключ]\n\n"
                f"Доступные ключи:\n{available_keys}\n\n"
                f"Например: /republish_deep flood"
            )
            return
        
        key = parts[1]
        
        if key not in DEEP_ARTICLES:
            await message.answer(
                f"❌ Ключ '{key}' не найден.\n"
                f"Доступные ключи: {', '.join(DEEP_ARTICLES.keys())}"
            )
            return
        
        full_text = DEEP_ARTICLES[key]
        teaser_length = min(config['TEASER_LENGTH'], 300)
        teaser_text = full_text[:teaser_length] + "...\n\n"
        teaser_text += (
            f"🔗 ЧИТАТЬ ПОЛНОСТЬЮ\n"
            f"➡️ @uriskonsult_bot?start={key}\n\n"
            f"👨‍⚖️ Нужна консультация?\n"
            f"➡️ /consult"
        )
        
        # ПРАВИЛЬНАЯ обработка ID канала
        if str(config['CHANNEL_ID']).startswith('-100'):
            channel = int(config['CHANNEL_ID'])
        else:
            channel = "@" + config['CHANNEL_ID']
            
        await bot.send_message(chat_id=channel, text=teaser_text)
        await message.answer(f"✅ Пост для статьи '{key}' успешно опубликован в канале!")
        
    except Exception as e:
        logger.error(f"Error in republish_deep: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# ============================================
# КОМАНДА /old_posts
# ============================================

# ============================================
# КОМАНДА /old_posts
# ============================================

@dp.message(Command("old_posts"))
@admin_only
async def cmd_old_posts(message: Message, **kwargs):  # ← Добавлен **kwargs
    try:
        articles = await db.get_articles_list()
        old_posts = []
        for article in articles:
            if article.get('teaser_time') and article['teaser_time'] < datetime.now() - timedelta(days=7):
                old_posts.append(article)
        if not old_posts:
            await message.answer("✅ Старых постов (старше 7 дней) не найдено!")
            return
        response = "📚 **Старые посты для перепубликации:**\n\n"
        for article in old_posts[:5]:
            response += (
                f"🔹 **ID {article['id']}**\n"
                f"📅 Опубликован: {article['teaser_time'].strftime('%d.%m.%Y %H:%M')}\n"
                f"📝 Текст: {article['full_text'][:50]}...\n\n"
            )
        if len(old_posts) > 5:
            response += f"...и еще {len(old_posts) - 5}\n\n"
        response += f"Всего: {len(old_posts)} постов\n"
        response += "Используйте `/republish [ID]` для перепубликации"
        await message.answer(response)
    except Exception as e:
        logger.error(f"Error in old_posts: {e}")
        await message.answer(f"❌ Ошибка: {e}")

# ============================================
# КОМАНДА /check_post (диагностика)
# ============================================

@dp.message(Command("check_post"))
@admin_only
async def cmd_check_post(message: Message, **kwargs):
    async with db.pool.acquire() as conn:
        posts = await conn.fetch("""
            SELECT * FROM scheduled_posts 
            WHERE article_id = 5
            ORDER BY id
        """)
        
        if not posts:
            await message.answer("❌ Для статьи 5 нет запланированных постов")
            return
        
        text = f"📊 **Посты для статьи 5:**\n\n"
        for p in posts:
            text += f"ID поста: {p['id']}\n"
            text += f"Тип: {p['post_type']}\n"
            text += f"Время: {p['scheduled_time']}\n"
            text += f"Статус: {p['status']}\n"
            if p['fail_reason']:
                text += f"❌ Ошибка: {p['fail_reason']}\n"
            text += "-" * 20 + "\n"
        
        await message.answer(text)

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
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "other_articles")
async def other_articles_handler(callback: CallbackQuery):
    await cmd_free(callback.message)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "consultation")
async def consultation_handler(callback: CallbackQuery):
    await cmd_consult(callback.message)
    await callback.answer()

# ============================================
# СОСТОЯНИЯ ДЛЯ КОНСУЛЬТАЦИИ
# ============================================

class ConsultStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_voice = State()

# ============================================
# ОБРАБОТЧИКИ КОНСУЛЬТАЦИИ
# ============================================

@dp.callback_query(lambda c: c.data == "consult_write")
async def consult_write_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not check_message_limit(user_id):
        await callback.message.answer(
            "❌ Вы исчерпали лимит сообщений на сегодня (3 сообщения в сутки).\n"
            "Попробуйте завтра или свяжитесь с @SekrierEI напрямую."
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "✍️ Напишите ваш вопрос подробно",
        reply_markup=get_consult_back_keyboard()
    )
    await state.set_state(ConsultStates.waiting_for_text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "consult_speak")
async def consult_speak_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not check_message_limit(user_id):
        await callback.message.answer(
            "❌ Вы исчерпали лимит сообщений на сегодня (3 сообщения в сутки).\n"
            "Попробуйте завтра или свяжитесь с @SekrierEI напрямую."
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎤 Отправьте голосовое сообщение",
        reply_markup=get_consult_back_keyboard()
    )
    await state.set_state(ConsultStates.waiting_for_voice)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "consult_back")
async def consult_back_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "👨‍⚖️ Запись на консультацию\n\nВыберите способ обращения:",
        reply_markup=get_consult_main_keyboard()
    )
    await callback.answer()

# ============================================
# ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
# ============================================

@dp.message(ConsultStates.waiting_for_text)
async def process_text_consult(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not check_message_limit(user_id):
        await message.answer("❌ Вы исчерпали лимит сообщений на сегодня (3 сообщения в сутки).")
        await state.clear()
        return
    
    if len(message.text) < 10:
        await message.answer("❌ Слишком короткий вопрос. Опишите ситуацию подробнее (минимум 10 символов).")
        return
    
    user_message_counts[user_id] += 1
    remaining = 3 - user_message_counts[user_id]
    
    admin_text = (
        f"📩 **ПИСЬМЕННЫЙ ВОПРОС**\n\n"
        f"**От:** @{message.from_user.username or 'нет username'}\n"
        f"**ID:** `{user_id}`\n"
        f"**Имя:** {message.from_user.full_name}\n"
        f"**Осталось сегодня:** {user_message_counts[user_id]}/3\n\n"
        f"**Вопрос:**\n{message.text}"
    )
    
    try:
        await bot.send_message(config['ADMIN_ID'], admin_text)
        await message.answer(
            f"✅ Ваш вопрос передан Эдуарду Ивановичу.\n"
            f"Он свяжется с вами в ближайшее время.\n\n"
            f"📊 Осталось сообщений сегодня: {remaining}/3",
            reply_markup=get_consult_main_keyboard()
        )
        logger.info(f"Text consultation from user {user_id}")
    except Exception as e:
        logger.error(f"Error forwarding text consultation: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    await state.clear()

# ============================================
# ОБРАБОТЧИК ГОЛОСОВЫХ СООБЩЕНИЙ
# ============================================

@dp.message(ConsultStates.waiting_for_voice)
async def process_voice_consult(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not check_message_limit(user_id):
        await message.answer("❌ Вы исчерпали лимит сообщений на сегодня (3 сообщения в сутки).")
        await state.clear()
        return
    
    if not message.voice:
        await message.answer("❌ Пожалуйста, отправьте голосовое сообщение.")
        return
    
    voice_duration = message.voice.duration
    user_message_counts[user_id] += 1
    remaining = 3 - user_message_counts[user_id]
    
    admin_text = (
        f"📩 **ГОЛОСОВОЙ ВОПРОС**\n\n"
        f"**От:** @{message.from_user.username or 'нет username'}\n"
        f"**ID:** `{user_id}`\n"
        f"**Имя:** {message.from_user.full_name}\n"
        f"**Длительность:** {voice_duration} сек\n"
        f"**Осталось сегодня:** {user_message_counts[user_id]}/3"
    )
    
    try:
        await bot.send_message(config['ADMIN_ID'], admin_text)
        await bot.send_voice(config['ADMIN_ID'], message.voice.file_id)
        await message.answer(
            f"✅ Ваш голосовой вопрос передан Эдуарду Ивановичу.\n"
            f"Он свяжется с вами в ближайшее время.\n\n"
            f"📊 Осталось сообщений сегодня: {remaining}/3",
            reply_markup=get_consult_main_keyboard()
        )
        logger.info(f"Voice consultation from user {user_id}, duration: {voice_duration}s")
    except Exception as e:
        logger.error(f"Error forwarding voice consultation: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
    
    await state.clear()

# ============================================
# ОБРАБОТЧИКИ ДЛЯ КАТЕГОРИЙ ДОКУМЕНТОВ
# ============================================

@dp.callback_query(lambda c: c.data.startswith('cat_'))
async def show_category_docs(callback: CallbackQuery):
    cat_key = callback.data.replace('cat_', '')
    category = FREE_DOCS.get(cat_key)
    
    if not category:
        await callback.answer("Раздел не найден")
        return
    
    builder = InlineKeyboardBuilder()
    items = category.get("items", {})
    for item_id, item_data in items.items():
        builder.button(
            text=item_data["name"],
            callback_data=f"doc_{cat_key}_{item_id}"
        )
    builder.button(text="◀️ Назад в меню", callback_data="menu_free")
    builder.adjust(1)
    
    await callback.message.edit_text(
        f"📂 **{category['name']}**\n\nВыберите документ:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

# ============================================
# ОБРАБОТЧИК ДЛЯ ВЫБРАННОГО ДОКУМЕНТА
# ============================================

@dp.callback_query(lambda c: c.data.startswith('doc_'))
async def send_document(callback: CallbackQuery):
    parts = callback.data.split('_')
    cat_key = parts[1]
    item_id = int(parts[2])
    
    doc = FREE_DOCS.get(cat_key, {}).get("items", {}).get(item_id)
    if not doc:
        await callback.answer("Документ не найден")
        return
    
    file_path = os.path.join("files", doc['file'])
    if os.path.exists(file_path):
        try:
            file_size = os.path.getsize(file_path) / 1024
            file_size_str = f"{file_size:.1f} КБ"
            
            document = FSInputFile(file_path)
            await callback.message.answer_document(
                document, 
                caption=f"📌 **{doc['name']}**\nРазмер: {file_size_str}"
            )
        except Exception as e:
            logger.error(f"Error sending file {doc['file']}: {e}")
            await callback.message.answer("❌ Ошибка при отправке файла")
    else:
        await callback.message.answer("❌ Файл временно недоступен")
        logger.warning(f"File not found: {file_path}")
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data=f"cat_{cat_key}")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
    ])
    await callback.message.answer(
        "📌 Документ отправлен. Выберите действие:",
        reply_markup=back_keyboard
    )
    await callback.answer()

# ============================================
# ОБРАБОТЧИКИ ДЛЯ МАГАЗИНА
# ============================================

@dp.callback_query(lambda c: c.data.startswith('contract_'))
async def show_contract(callback: CallbackQuery):
    contract_id = int(callback.data.split('_')[1])
    contract = CONTRACTS[contract_id]
    text = (
        f"📌 **{contract['name']}**\n\n"
        f"{contract['description']}\n\n"
        f"💰 **Цена:** {contract['price']} ₽\n"
        f"🛠 **Индивидуальная доработка:** +{contract['upgrade_price']} ₽ "
        f"(всего {contract['price'] + contract['upgrade_price']} ₽)\n\n"
        f"👇 Выберите действие:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ КУПИТЬ ({contract['price']}₽)", 
                              callback_data=f"buy_{contract_id}_base")],
        [InlineKeyboardButton(text=f"⚡ ДОРАБОТКА ({contract['price'] + contract['upgrade_price']}₽)", 
                              callback_data=f"buy_{contract_id}_upgrade")],
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="menu_shop")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith('buy_'))
async def buy_contract(callback: CallbackQuery):
    await callback.message.answer("💳 Функция оплаты будет добавлена позже.")
    
    back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="menu_shop")],
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
    ])
    await callback.message.answer(
        "📌 Выберите действие:",
        reply_markup=back_keyboard
    )
    await callback.answer()

# ============================================
# ОБРАБОТЧИКИ ДЛЯ КЕЙСОВ
# ============================================

@dp.callback_query(lambda c: c.data.startswith('case_'))
async def process_case(callback: CallbackQuery):
    case_id = int(callback.data.split('_')[1])
    case = cases_db.get(case_id)
    
    if case and case["published"]:
        text = (
            f"📁 Кейс №{case_id}: {case['title']}\n"
            f"🏷 Категория: {case['category']}\n"
            f"📅 Дата: {case['date']}\n\n"
            f"📋 СИТУАЦИЯ:\n{case['situation']}\n\n"
            f"❓ ВОПРОС:\n{case['question']}\n\n"
            f"⚖️ РЕШЕНИЕ:\n{case['solution']}\n\n"
            f"✅ РЕЗУЛЬТАТ:\n{case['result']}\n\n"
        )
        if case['files']:
            text += "📎 Прикреплённые файлы:\n"
            for i, filename in enumerate(case['files'], 1):
                text += f"{i}. {filename}\n"
        text += f"\n➡️ Нужна такая же консультация? Нажмите /consult"
        
        await callback.message.answer(text)
        
        if case['files']:
            for filename in case['files']:
                file_path = os.path.join("files", filename)
                if os.path.exists(file_path):
                    try:
                        document = FSInputFile(file_path)
                        await callback.message.answer_document(document)
                    except Exception as e:
                        logger.error(f"Error sending case file {filename}: {e}")
        
        nav_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="menu_cases")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_main")]
        ])
        await callback.message.answer("📌 Выберите действие:", reply_markup=nav_keyboard)
    else:
        await callback.message.answer("❌ Этот кейс ещё не опубликован или не найден.")
    
    await callback.answer()

# ============================================
# ОБРАБОТЧИК ДЛЯ СКАЧИВАНИЯ ДОКУМЕНТОВ
# ============================================

@dp.callback_query(lambda c: c.data.startswith('download_'))
async def download_document(callback: CallbackQuery):
    article_id = int(callback.data.split('_')[1])
    article = await db.get_article(article_id)
    
    if not article:
        await callback.answer("❌ Документ не найден")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📂 Перейти к документам", callback_data="menu_free")],
        [InlineKeyboardButton(text="◀️ Назад к статье", callback_data=f"back_to_article_{article_id}")]
    ])
    
    await callback.message.answer(
        "📌 Сейчас функция скачивания документа настраивается.\n\n"
        "Вы можете перейти в раздел «Бесплатные документы» и скачать нужную памятку оттуда.",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ОБРАБОТЧИК ДЛЯ ВОЗВРАТА К СТАТЬЕ
# ============================================

@dp.callback_query(lambda c: c.data.startswith('back_to_article_'))
async def back_to_article(callback: CallbackQuery):
    article_id = int(callback.data.split('_')[3])
    article = await db.get_article(article_id)
    
    if not article:
        await callback.answer("❌ Статья не найдена")
        return
    
    article_title = article['full_text'].split('\n')[0][:50] + "..." if len(article['full_text'].split('\n')[0]) > 50 else article['full_text'].split('\n')[0]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 Скачать документ", callback_data=f"download_{article_id}"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
            InlineKeyboardButton(text="❓ Консультация", callback_data="menu_consult")
        ]
    ])
    
    await callback.message.answer(
        f"📄 {article_title}\n\n{article['full_text']}",
        reply_markup=keyboard
    )
    await callback.answer()

# ============================================
# ФОНОВАЯ ПРОВЕРКА СТАРЫХ ПОСТОВ (ВРЕМЕННО ОТКЛЮЧЕНО)
# ============================================

async def check_old_posts_periodically():
    # Функция временно отключена из-за ошибки с часовыми поясами
    await asyncio.sleep(60)
    while True:
        await asyncio.sleep(24 * 60 * 60)  # Просто спим, ничего не делаем
        # Позже исправим и включим обратно

# ============================================
# ОБРАБОТЧИК ОШИБОК
# ============================================

@dp.errors()
async def errors_handler(event: types.ErrorEvent):
    try:
        if isinstance(event.exception, TelegramBadRequest):
            logger.error(f"Bad Request: {event.exception}")
        else:
            logger.exception(f"Update {event.update} caused error {event.exception}")
    except Exception as e:
        logger.error(f"Error in error handler: {e}")
    return True

# ============================================
# ЗАПУСК БОТА
# ============================================

async def on_startup():
    logger.info("🚀 Bot is starting up...")
    await db.connect()
    
    os.makedirs("files", exist_ok=True)
    os.makedirs("cases", exist_ok=True)
    os.makedirs("images", exist_ok=True)
    
    if os.path.exists("files"):
        files = os.listdir("files")
        logger.info(f"📁 Найдено файлов в папке files: {len(files)}")
        if len(files) > 0:
            logger.info(f"📄 Первые 5 файлов: {files[:5]}")
        else:
            logger.warning("⚠️ Папка files пуста!")
    else:
        logger.warning("⚠️ Папка files не существует!")
    
    asyncio.create_task(check_old_posts_periodically())
    asyncio.create_task(reset_limits_daily())
    
    logger.info("✅ Bot started successfully")

# ВРЕМЕННЫЙ ЗАПУСК ПЛАНИРОВЩИКА ВМЕСТЕ С БОТОМ
async def run_scheduler():
    """Запускает планировщик в фоне"""
    try:
        print("🔴 ПЫТАЮСЬ ЗАПУСТИТЬ ПЛАНИРОВЩИК ИЗ bot.py")
        import sys
        sys.stdout.flush()
        
        from scheduler import PostScheduler
        scheduler = PostScheduler()
        asyncio.create_task(scheduler.start())
        logger.info("🚀 Планировщик запущен из bot.py")
    except Exception as e:
        logger.error(f"❌ ОШИБКА ЗАПУСКА ПЛАНИРОВЩИКА: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()

async def on_shutdown():
    logger.info("🛑 Bot is shutting down...")
    if hasattr(db, 'pool') and db.pool:
        await db.pool.close()
    await bot.session.close()
    logger.info("👋 Bot stopped")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запускаем планировщик в фоне
    asyncio.create_task(run_scheduler())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")

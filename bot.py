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

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📋 Доступные команды:\n\n"
        "👤 Для всех:\n"
        "/start - Начать работу\n"
        "/help - Это меню\n"
        "/calculator - Калькулятор ЖКХ\n"
        "/calculate - То же самое\n"
        "/shop - Магазин договоров\n"
        "/consult - Консультация\n"
        "/free - Бесплатные документы\n"
        "/cases - Кейсы\n\n"
    )
    
    # Проверяем, является ли пользователь администратором
    is_admin_user = message.from_user.id == config.get('ADMIN_ID', 0)
    
    if is_admin_user:
        help_text += (
            "🔰 Для администратора:\n"
            "/admin - Войти в панель управления\n"
            "/test_channel - Проверить доступ к каналу\n"
            "/add_article - Добавить статью\n"
            "/list_articles - Список статей\n"
            "/del_article [ID] - Удалить статью\n"
            "/edit_article [ID] - Редактировать\n"
            "/status - Статус планировщика\n"
            "/stats - То же, что /status\n"
            "/republish [ID] - Перепубликовать старый пост\n"
            "/republish_deep [ключ] - Опубликовать deep link статью\n"
            "/old_posts - Список старых постов\n"
            "/clear_limits - Сбросить лимиты сообщений\n"
        )
    
    await message.answer(help_text)
    logger.info(f"User {message.from_user.id} requested help")

# ============================================
# КОМАНДА /calculator
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
# КОМАНДА /shop (ИСПРАВЛЕННАЯ, БЕЗ ДУБЛИКАТОВ)
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
        # Получаем время от пользователя (МСК)
        msk_time = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        
        # Текущее время по МСК (UTC+3)
        now_msk = datetime.utcnow() + timedelta(hours=3)
        
        # Проверяем, что время не в прошлом (по МСК)
        if msk_time < now_msk:
            await message.answer(
                f"❌ Нельзя указать время в прошлом!\n"
                f"Текущее время МСК: {now_msk.strftime('%d.%m.%Y %H:%M')}\n"
                f"Вы указали: {msk_time.strftime('%d.%m.%Y %H:%M')}"
            )
            return
        
        data = await state.get_data()
        article_text = data['article_text']
        
        # Сохраняем в БД время МСК (база сама сконвертирует при сравнении)
        article_id = await db.add_article(article_text, msk_time)
        deep_link = f"@uriskonsult_bot?start=article_{article_id}"
        
        await message.answer(
            f"✅ **Статья #{article_id} добавлена!**\n\n"
            f"🔗 **Ссылка для тизера:**\n"
            f"{deep_link}\n\n"
            f"📅 Публикация тизера запланирована на {msk_time.strftime('%d.%m.%Y %H:%M')} МСК."
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ ЧЧ:ММ")
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
# ТЕСТОВАЯ КОМАНДА ДЛЯ ПРОВЕРКИ КАНАЛА (С ОТЛАДКОЙ)
# ============================================

@dp.message(Command("test_channel"))
@admin_only
async def cmd_test_channel(message: Message, **kwargs):
    """Проверяет, может ли бот писать в канал"""
    try:
        # Отладка: что лежит в config
        print(f"🔍 ОТЛАДКА: config['CHANNEL_ID'] = {config['CHANNEL_ID']} (тип: {type(config['CHANNEL_ID']).__name__})")
        logger.info(f"🔍 ОТЛАДКА: config['CHANNEL_ID'] = {config['CHANNEL_ID']} (тип: {type(config['CHANNEL_ID']).__name__})")
        
        channel = config['CHANNEL_ID']
        
        # Правильная обработка ID канала
        if str(channel).startswith('-100'):
            channel_id = int(channel)
            channel_type = "числовой ID"
        else:
            channel_id = "@" + channel
            channel_type = "username"
        
        # Отладка: что получилось
        print(f"🔍 ОТЛАДКА: channel_id = {channel_id} (тип: {type(channel_id).__name__})")
        logger.info(f"🔍 ОТЛАДКА: channel_id = {channel_id} (тип: {type(channel_id).__name__})")
        
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
        print(f"🔴 ОШИБКА: {error_msg}")
        logger.error(error_msg)
        await message.answer(error_msg)

# ============================================
# КОМАНДА /republish
# ============================================

@dp.message(Command("republish"))
@admin_only
async def cmd_republish(message: Message, **kwargs):
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
async def cmd_republish_deep(message: Message, **kwargs):
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

@dp.message(Command("old_posts"))
@admin_only
async def cmd_old_posts(message: Message, **kwargs):
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
    # Эта команда требует подключения к PostgreSQL, в тестовой БД не работает
    await message.answer("❌ Команда /check_post требует PostgreSQL. Используйте тестовую БД.")

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

async def on_shutdown():  # ← ЭТА ФУНКЦИЯ ДОЛЖНА БЫТЬ ДО main()!
    logger.info("🛑 Bot is shutting down...")
    if hasattr(db, 'pool') and db.pool:
        await db.pool.close()
    await bot.session.close()
    logger.info("👋 Bot stopped")

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ТИЗЕРОВ
# ============================================

def detect_article_type(text: str) -> str:
    """Определяет тип статьи по ключевым словам"""
    text_lower = text.lower()
    if any(word in text_lower for word in ['инструкция', 'как', 'шаги', 'порядок', 'пошагово']):
        return "instruction"
    elif any(word in text_lower for word in ['кейс', 'пример', 'ситуация', 'дело', 'случай']):
        return "case"
    elif any(word in text_lower for word in ['новость', 'изменения', 'теперь', 'начало']):
        return "news"
    else:
        return "news"  # По умолчанию

def format_teaser_by_type(full_text: str, article_type: str = "news") -> str:
    """
    Форматирует тизер в зависимости от типа статьи
    article_type: news, instruction, case
    """
    lines = full_text.strip().split('\n')
    title = lines[0].strip() if lines else "Статья"
    
    # Собираем остальной текст
    body = ' '.join([line.strip() for line in lines[1:] if line.strip()])
    
    # Обрезаем до 400 символов для тизера
    if len(body) > 400:
        last_space = body[:400].rfind(' ')
        body = body[:last_space] + "..." if last_space > 0 else body[:400] + "..."
    
    # Шаблоны для разных типов статей
    templates = {
        "news": (
            f"⚜️ **{title}**\n\n"
            f"🔹 **Главное:** {body}\n\n"
            f"⚠️ Нажмите кнопку ниже, чтобы прочитать полностью в боте 👇"
        ),
        "instruction": (
            f"📋 **{title}**\n\n"
            f"🔹 **Пошаговая инструкция:**\n{body}\n\n"
            f"✅ Полная версия с деталями — в боте 👇"
        ),
        "case": (
            f"⚖️ **{title}**\n\n"
            f"🔹 **Суть дела:** {body}\n\n"
            f"📌 Результат и юридические детали — в боте 👇"
        )
    }
    
    return templates.get(article_type, templates["news"])

def get_channel_post_keyboard(article_id: int):
    """Клавиатура для поста в канале с красной кнопкой"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔴 ЧИТАТЬ ПОЛНОСТЬЮ В БОТЕ", 
        url=f"https://t.me/uriskonsult_bot?start=article_{article_id}"
    ))
    return builder.as_markup()

# ============================================
# ПРОСТОЙ ПЛАНИРОВЩИК С ФОТО И УМНЫМИ ТИЗЕРАМИ
# ============================================

async def run_scheduler():
    """Простой фоновый планировщик с фото и умными тизерами"""
    logger.info("🚀 Простой планировщик запущен")
    
    while True:
        try:
            await asyncio.sleep(30)
            
            current_time = datetime.now()
            logger.info(f"⏰ Проверка постов в {current_time.strftime('%H:%M:%S')}")
            
            if not hasattr(db, 'get_pending_posts'):
                logger.error("❌ Нет метода get_pending_posts в database.py")
                continue
            
            try:
                posts = await db.get_pending_posts()
            except Exception as e:
                logger.error(f"❌ Ошибка при получении постов: {e}")
                continue
            
            if posts:
                logger.info(f"📋 Найдено {len(posts)} постов для публикации")
                
                for post in posts:
                    try:
                        channel = config['CHANNEL_ID']
                        
                        # Определяем тип статьи и форматируем тизер
                        article_type = detect_article_type(post['content'])
                        post_text = format_teaser_by_type(post['content'], article_type)
                        
                        # Путь к фото
                        photo_path = os.path.join("images", "max_full.jpg")
                        
                        # Отправляем в канал с фото и кнопкой
                        if os.path.exists(photo_path):
                            photo = FSInputFile(photo_path)
                            await bot.send_photo(
                                chat_id=channel,
                                photo=photo,
                                caption=post_text,
                                parse_mode='HTML',
                                reply_markup=get_channel_post_keyboard(post['id'])
                            )
                            logger.info(f"✅ Пост {post['id']} опубликован в канале с фото и кнопкой")
                        else:
                            # Если фото нет, отправляем только текст
                            await bot.send_message(
                                chat_id=channel,
                                text=post_text,
                                parse_mode='HTML',
                                reply_markup=get_channel_post_keyboard(post['id'])
                            )
                            logger.warning(f"⚠️ Пост {post['id']} опубликован без фото (файл не найден)")
                        
                        # Обновляем статус
                        if hasattr(db, 'update_post_status'):
                            await db.update_post_status(post['id'], 'published')
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка публикации поста {post['id']}: {e}")
            else:
                logger.info("📭 Нет постов для публикации")
                
        except asyncio.CancelledError:
            logger.info("🛑 Планировщик остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в планировщике: {e}")
            logger.info("🔄 Перезапуск планировщика через 10 секунд...")
            await asyncio.sleep(10)

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================

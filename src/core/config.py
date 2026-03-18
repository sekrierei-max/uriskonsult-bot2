"""
Конфигурация бота
Поддерживает локальный запуск и деплой на Amvera
"""
import os
from pathlib import Path

# 🔥 Отладочный вывод (можно удалить после проверки)
print("🔥🔥🔥 config.py загружается")

# Определяем базовые пути
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("AMVERA_DATA_PATH", BASE_DIR / "data"))
LOGS_DIR = DATA_DIR / "logs"

# Создаём папки, если их нет
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# === ПОЛУЧАЕМ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")

# ⚠️ ВАЖНО: ID канала должен быть ЧИСЛОМ для Telegram API
# Обрабатываем возможные проблемы с тире и пробелами
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")

if CHANNEL_ID_RAW:
    # Приводим к строке и удаляем пробелы
    cleaned = str(CHANNEL_ID_RAW).strip()
    # Заменяем все возможные виды тире на обычный дефис
    # (длинное тире, короткое тире, минус и т.д.)
    for dash in ['–', '—', '−', '‐']:
        cleaned = cleaned.replace(dash, '-')
    
    # Проверяем, начинается ли с -100 (теперь точно с обычным дефисом)
    if cleaned.startswith('-100') and cleaned[1:].replace('-', '').isdigit():
        CHANNEL_ID = int(cleaned)
        print(f"✅ CHANNEL_ID преобразован в число: {CHANNEL_ID}")
    else:
        CHANNEL_ID = cleaned
        print(f"⚠️ CHANNEL_ID оставлен как строка: {CHANNEL_ID}")
else:
    CHANNEL_ID = None
    print("⚠️ CHANNEL_ID не задан")

# Настройки планировщика
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow")
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "9"))
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", "0"))

# === ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПЕРЕМЕННЫХ ===
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не задан!")
    
if ADMIN_ID == 0:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: ADMIN_ID не задан или равен 0")
    
if not CHANNEL_ID:
    print("⚠️ ПРЕДУПРЕЖДЕНИЕ: CHANNEL_ID не задан")
else:
    print(f"✅ CHANNEL_ID загружен: {CHANNEL_ID} (тип: {type(CHANNEL_ID).__name__})")

# Создаём объект config для обратной совместимости
config = {
    "BOT_TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "DATABASE_URL": DATABASE_URL,
    "CHANNEL_ID": CHANNEL_ID,  # Теперь это ЧИСЛО (если начинается с -100)
    "SCHEDULER_TIMEZONE": SCHEDULER_TIMEZONE,
    "SCHEDULER_HOUR": SCHEDULER_HOUR,
    "SCHEDULER_MINUTE": SCHEDULER_MINUTE,
    "DATA_DIR": DATA_DIR,
    "LOGS_DIR": LOGS_DIR,
    # Добавляем длину тизера (можно вынести в переменные окружения позже)
    "TEASER_LENGTH": 200,
}

print(f"✅ config.py загружен, CHANNEL_ID={config['CHANNEL_ID']} ({type(config['CHANNEL_ID']).__name__})")

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
# Если в переменных окружения канал указан как строка, преобразуем в int
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
if CHANNEL_ID_RAW and str(CHANNEL_ID_RAW).startswith('-100'):
    CHANNEL_ID = int(CHANNEL_ID_RAW)  # Преобразуем строку в число
else:
    CHANNEL_ID = CHANNEL_ID_RAW  # Оставляем как есть (может быть @username)

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
    "CHANNEL_ID": CHANNEL_ID,  # Теперь это ЧИСЛО, а не строка!
    "SCHEDULER_TIMEZONE": SCHEDULER_TIMEZONE,
    "SCHEDULER_HOUR": SCHEDULER_HOUR,
    "SCHEDULER_MINUTE": SCHEDULER_MINUTE,
    "DATA_DIR": DATA_DIR,
    "LOGS_DIR": LOGS_DIR,
    # Добавляем длину тизера (можно вынести в переменные окружения позже)
    "TEASER_LENGTH": 200,
}

print(f"✅ config.py загружен, CHANNEL_ID={config['CHANNEL_ID']} ({type(config['CHANNEL_ID']).__name__})")

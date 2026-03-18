import os
from pathlib import Path

# Определяем базовые пути
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.getenv("AMVERA_DATA_PATH", BASE_DIR / "data"))
LOGS_DIR = DATA_DIR / "logs"

# Создаём папки, если их нет
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Ваши существующие переменные
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Настройки планировщика
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "Europe/Moscow")
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "9"))
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", "0"))

# Создаём объект config для обратной совместимости
config = {
    "BOT_TOKEN": BOT_TOKEN,
    "ADMIN_ID": ADMIN_ID,
    "DATABASE_URL": DATABASE_URL,
    "CHANNEL_ID": CHANNEL_ID,
    "SCHEDULER_TIMEZONE": SCHEDULER_TIMEZONE,
    "SCHEDULER_HOUR": SCHEDULER_HOUR,
    "SCHEDULER_MINUTE": SCHEDULER_MINUTE,
    "DATA_DIR": DATA_DIR,
    "LOGS_DIR": LOGS_DIR,
}
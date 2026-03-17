import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0").strip())
    CHANNEL_ID: str = os.getenv("CHANNEL_ID", "sekrier_gel").strip()
    
    DB_HOST: str = os.getenv("DB_HOST", "localhost").strip()
    DB_PORT: int = int(os.getenv("DB_PORT", "5432").strip())
    DB_NAME: str = os.getenv("DB_NAME", "telegram_bot").strip()
    DB_USER: str = os.getenv("DB_USER", "postgres").strip()
    DB_PASS: str = os.getenv("DB_PASS", "").strip()
    
    TEASER_LENGTH: int = int(os.getenv("TEASER_LENGTH", "500").strip())
    REMINDER_DELAY_HOURS: int = int(os.getenv("REMINDER_DELAY_HOURS", "24").strip())
    
    SCHEDULER_LOG: str = os.getenv("SCHEDULER_LOG", "/data/logs/scheduler.log").strip()
    BOT_LOG: str = os.getenv("BOT_LOG", "/data/logs/bot.log").strip()
    
    DEBUG: bool = os.getenv("DEBUG", "False").strip().lower() == "true"
    
    def __post_init__(self):
        errors = []
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
        if self.ADMIN_ID == 0:
            errors.append("ADMIN_ID не установлен или равен 0")
        if not self.CHANNEL_ID:
            errors.append("CHANNEL_ID не установлен")
        if not self.DB_PASS:
            errors.append("DB_PASS не установлен")
        if self.TEASER_LENGTH < 100:
            errors.append("TEASER_LENGTH должен быть не менее 100 символов")
        if self.REMINDER_DELAY_HOURS < 1:
            errors.append("REMINDER_DELAY_HOURS должен быть не менее 1 часа")
        if errors:
            error_msg = "\n".join(errors)
            raise ValueError(f"Ошибки конфигурации:\n{error_msg}")
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

try:
    config = Config()
except ValueError as e:
    print(f"❌ {e}")
    print("Пожалуйста, проверьте файл .env")
    exit(1)
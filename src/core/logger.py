import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.core.config import LOGS_DIR


def setup_logger(name: str = "urikonsult") -> logging.Logger:
    """Настраивает логгер с ротацией файлов."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный вывод
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    # Файловый вывод с ротацией
    if LOGS_DIR and LOGS_DIR.exists():
        log_file = LOGS_DIR / f"{name}.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_485_760,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Отдельный файл для ошибок
        error_file = LOGS_DIR / f"{name}_error.log"
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=10_485_760,
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
    
    return logger


# Создаём основной логгер
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """Возвращает логгер для указанного модуля."""
    if name:
        return logging.getLogger(f"urikonsult.{name}")
    return logger
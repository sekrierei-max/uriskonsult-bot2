#!/usr/bin/env python3
"""
Настройка логирования с ротацией файлов
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional

def setup_logger(name: str, log_file: str, level: Optional[int] = None, use_timed_rotation: bool = False):
    """
    Настройка логгера с ротацией файлов
    
    Args:
        name: Имя логгера
        log_file: Путь к файлу лога
        level: Уровень логирования (по умолчанию INFO или DEBUG из окружения)
        use_timed_rotation: Использовать временную ротацию (по дням) вместо ротации по размеру
    """
    # Определяем уровень логирования
    if level is None:
        level = logging.DEBUG if os.getenv("DEBUG", "False").lower() == "true" else logging.INFO
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Создаем директорию для логов, если её нет
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Выбираем тип ротации
    if use_timed_rotation:
        # Ротация по дням, храним 30 дней
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
    else:
        # Ротация по размеру (10 MB на файл, храним 5 файлов)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
    
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    
    # Handler для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    
    # Настраиваем логгер
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Удаляем старые обработчики, если они есть
    logger.handlers.clear()
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Отключаем передачу логов в родительские логгеры
    logger.propagate = False
    
    return logger
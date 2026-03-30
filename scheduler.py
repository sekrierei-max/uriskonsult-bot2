"""
Модуль планировщика (УСТАРЕЛ - используется простой цикл в bot.py)
Оставлен для совместимости
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger('bot')

class Scheduler:
    """Заглушка для обратной совместимости"""
    
    def __init__(self):
        self.running = False
        logger.info("⚠️ Scheduler.py устарел, используется планировщик в bot.py")
    
    async def start(self):
        """Заглушка"""
        self.running = True
        logger.info("📅 Планировщик (заглушка) запущен")
    
    async def stop(self):
        """Заглушка"""
        self.running = False
        logger.info("📅 Планировщик (заглушка) остановлен")
    
    async def check_posts(self):
        """Заглушка"""
        pass

# Создаём глобальный экземпляр для совместимости
scheduler = Scheduler()

"""
Упрощённая версия database.py для тестирования без PostgreSQL
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    """Класс-заглушка для тестирования"""
    
    def __init__(self):
        self.articles = {}
        self.next_id = 1
    
    async def connect(self):
        """Имитация подключения к БД"""
        logger.info("✅ Тестовая БД подключена (без PostgreSQL)")
        return True
    
    async def close(self):
        """Закрытие соединения"""
        logger.info("🛑 Тестовая БД отключена")
    
    async def add_article(self, text: str, publish_time: datetime) -> int:
        """Добавление статьи в память"""
        article_id = self.next_id
        self.articles[article_id] = {
            'id': article_id,
            'full_text': text,
            'teaser_time': publish_time,
            'created_at': datetime.now()
        }
        self.next_id += 1
        logger.info(f"📝 Добавлена тестовая статья #{article_id}")
        return article_id
    
    async def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Получение статьи по ID"""
        return self.articles.get(article_id)
    
    async def get_articles_list(self) -> List[Dict[str, Any]]:
        """Список всех статей"""
        return list(self.articles.values())
    
    async def delete_article(self, article_id: int) -> bool:
        """Удаление статьи"""
        if article_id in self.articles:
            del self.articles[article_id]
            logger.info(f"🗑 Удалена тестовая статья #{article_id}")
            return True
        return False
    
    async def get_scheduler_stats(self) -> Dict[str, int]:
        """Статистика (заглушка)"""
        return {
            'pending': 0,
            'published': 0,
            'failed': 0
        }

# Создаём глобальный экземпляр БД
db = Database()
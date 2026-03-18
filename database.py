#!/usr/bin/env python3
"""
Упрощённая версия database.py для тестирования без PostgreSQL
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any  # ← ВАЖНО: добавили List и Dict

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
            'created_at': datetime.now(),
            'published': False  # Добавлено для отслеживания
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
    
    async def get_pending_posts(self) -> List[Dict]:
        """
        Возвращает статьи, которые нужно опубликовать сейчас.
        Для тестовой БД просто возвращаем все статьи,
        у которых teaser_time <= текущего времени
        """
        now = datetime.now()
        pending = []
        
        for article_id, article in self.articles.items():
            teaser_time = article.get('teaser_time')
            if teaser_time and teaser_time <= now and not article.get('published', False):
                # Создаём пост с нужными полями
                pending_post = {
                    'id': article_id,
                    'article_id': article_id,
                    'post_type': 'teaser',
                    'content': article['full_text'],
                    'scheduled_time': teaser_time,
                    'status': 'pending'
                }
                pending.append(pending_post)
                article['published'] = True  # Помечаем как опубликованную
                logger.info(f"📊 Пост #{article_id} готов к публикации")
        
        logger.info(f"📊 get_pending_posts: найдено {len(pending)} постов")
        return pending
    
    async def update_post_status(self, post_id: int, status: str, fail_reason: str = None, retry_count: int = None):
        """Обновление статуса поста (для совместимости)"""
        # В тестовой БД просто логируем
        logger.info(f"📊 Пост #{post_id} обновлён статус: {status}")
        if fail_reason:
            logger.error(f"❌ Ошибка поста #{post_id}: {fail_reason}")

# Создаём глобальный экземпляр БД
db = Database()

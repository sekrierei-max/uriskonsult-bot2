"""
Тестовая база данных для планировщика (в памяти)
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger('bot')

class Database:
    def __init__(self):
        self.articles = {}  # Хранилище статей в памяти
        self.next_id = 1    # Счётчик для ID статей
    
    async def connect(self):
        """Подключение к БД (заглушка)"""
        logger.info("📦 Тестовая БД подключена (в памяти)")
    
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
        logger.info(f"📝 Добавлена тестовая статья #{article_id} на {publish_time}")
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
        # Подсчитываем реальные данные
        pending = 0
        published = 0
        
        for article in self.articles.values():
            if article.get('published', False):
                published += 1
            else:
                teaser_time = article.get('teaser_time')
                if teaser_time and teaser_time > datetime.now():
                    pending += 1
        
        return {
            'pending': pending,
            'published': published,
            'failed': 0
        }
    
    async def get_pending_posts(self) -> List[Dict]:
        """
        Возвращает статьи, которые нужно опубликовать сейчас.
        Исправлено: учитываем часовой пояс + максимальная отладка
        """
        now_utc = datetime.now()  # Серверное время UTC
        pending = []
        
        logger.info(f"🔍 get_pending_posts: всего статей в БД: {len(self.articles)}")
        
        for article_id, article in self.articles.items():
            logger.info(f"🔍 Проверка статьи #{article_id}: {article}")
            
            teaser_time = article.get('teaser_time')
            published = article.get('published', False)
            
            logger.info(f"   teaser_time={teaser_time}, published={published}, now_utc={now_utc}")
            
            # Проверяем: время публикации наступило И ещё не опубликовано
            if teaser_time and teaser_time <= now_utc and not published:
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
                logger.info(f"📊 Пост #{article_id} ГОТОВ к публикации!")
            elif teaser_time:
                if teaser_time > now_utc:
                    logger.info(f"⏳ Пост #{article_id} ещё не готов: {teaser_time} > {now_utc}")
                elif published:
                    logger.info(f"✅ Пост #{article_id} уже опубликован")
            else:
                logger.warning(f"⚠️ У статьи #{article_id} нет teaser_time!")
        
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

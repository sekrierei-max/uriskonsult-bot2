"""
Тестовая база данных для планировщика (в памяти)
"""
import logging
from datetime import datetime, timedelta
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
            'teaser_time': publish_time,  # Время в МСК от пользователя
            'created_at': datetime.now(),
            'published': False
        }
        self.next_id += 1
        logger.info(f"📝 Добавлена тестовая статья #{article_id} на {publish_time} МСК")
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
        """Статистика планировщика"""
        pending = 0
        published = 0
        now_utc = datetime.now()
        
        for article in self.articles.values():
            if article.get('published', False):
                published += 1
            else:
                teaser_time = article.get('teaser_time')
                if teaser_time:
                    # Переводим время статьи из МСК в UTC для сравнения
                    teaser_time_utc = teaser_time - timedelta(hours=3)
                    if teaser_time_utc > now_utc:
                        pending += 1
        
        return {
            'pending': pending,
            'published': published,
            'failed': 0
        }
    
    async def get_pending_posts(self) -> List[Dict]:
        """
        Возвращает статьи, которые нужно опубликовать сейчас.
        ИСПРАВЛЕНО: правильное сравнение времени с учётом часовых поясов
        """
        now_utc = datetime.now()  # Серверное время UTC
        pending = []
        
        logger.info(f"🔍 get_pending_posts: всего статей в БД: {len(self.articles)}")
        logger.info(f"🔍 Текущее время UTC: {now_utc}")
        
        for article_id, article in self.articles.items():
            logger.info(f"🔍 Проверка статьи #{article_id}")
            
            teaser_time_msk = article.get('teaser_time')  # Время в МСК
            published = article.get('published', False)
            
            if teaser_time_msk:
                # Переводим время статьи из МСК в UTC для сравнения
                teaser_time_utc = teaser_time_msk - timedelta(hours=3)
                
                logger.info(f"   Время статьи (МСК): {teaser_time_msk}")
                logger.info(f"   Время статьи (UTC): {teaser_time_utc}")
                logger.info(f"   Текущее время (UTC): {now_utc}")
                logger.info(f"   Опубликована: {published}")
                
                # Проверяем: время публикации наступило (по UTC) И ещё не опубликовано
                if teaser_time_utc <= now_utc and not published:
                    # Создаём пост с нужными полями
                    pending_post = {
                        'id': article_id,
                        'article_id': article_id,
                        'post_type': 'teaser',
                        'content': article['full_text'],
                        'scheduled_time': teaser_time_msk,  # Сохраняем МСК для пользователя
                        'status': 'pending'
                    }
                    pending.append(pending_post)
                    article['published'] = True  # Помечаем как опубликованную
                    logger.info(f"📊 ПОСТ #{article_id} ГОТОВ К ПУБЛИКАЦИИ!")
                elif teaser_time_utc > now_utc:
                    logger.info(f"⏳ Пост #{article_id} ещё не готов (по UTC)")
                elif published:
                    logger.info(f"✅ Пост #{article_id} уже опубликован")
            else:
                logger.warning(f"⚠️ У статьи #{article_id} нет teaser_time!")
        
        logger.info(f"📊 get_pending_posts: найдено {len(pending)} постов для публикации")
        return pending
        
    async def update_post_status(self, post_id: int, status: str, fail_reason: str = None, retry_count: int = None):
        """Обновление статуса поста (для совместимости)"""
        logger.info(f"📊 Пост #{post_id} обновлён статус: {status}")
        if fail_reason:
            logger.error(f"❌ Ошибка поста #{post_id}: {fail_reason}")

# Создаём глобальный экземпляр БД
db = Database()

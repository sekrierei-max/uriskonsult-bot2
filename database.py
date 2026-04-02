class Database:
    def __init__(self):
        self.articles = {}  # Хранилище статей в памяти
        self.next_id = 1    # Счётчик для ID статей
    
    async def connect(self):
        """Подключение к БД (заглушка — без PostgreSQL)"""
        logger.info("📦 Тестовая БД подключена (в памяти)")
        # Не создаём pool, так как используем тестовую БД
        self.pool = None
    
    async def add_article(self, full_text: str, teaser_title: str, teaser_text: str, publish_time: datetime, photo_file_id: str = None) -> int:
        """
        Добавляет новую статью в БД
        
        Args:
            full_text: Полный текст для бота
            teaser_title: Заголовок тизера (для канала)
            teaser_text: Короткий текст тизера (для канала)
            publish_time: Время публикации (МСК)
            photo_file_id: file_id фото (опционально)
        """
        article_id = self.next_id
        self.articles[article_id] = {
            'id': article_id,
            'full_text': full_text,
            'teaser_title': teaser_title,
            'teaser_text': teaser_text,
            'teaser_time': publish_time,
            'teaser_photo': photo_file_id,
            'created_at': datetime.now(),
            'published': False
        }
        self.next_id += 1
        # Логируем сохранение фото
        if photo_file_id:
            logger.info(f"📸 Фото для статьи #{article_id} сохранено: {photo_file_id[:20]}...")
        else:
            logger.info(f"📝 Добавлена статья #{article_id}: {teaser_title} (без фото)")
        return article_id
    
    async def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Получение статьи по ID"""
        return self.articles.get(article_id)
    
    async def get_articles_list(self) -> List[Dict[str, Any]]:
        """Список всех статей"""
        articles_list = []
        for article_id, article in self.articles.items():
            articles_list.append({
                'id': article_id,
                'full_text': article.get('full_text', ''),
                'teaser_title': article.get('teaser_title', ''),
                'teaser_text': article.get('teaser_text', ''),
                'teaser_time': article.get('teaser_time'),
                'published': article.get('published', False),
                'teaser_photo': article.get('teaser_photo')
            })
        return articles_list
    
    async def delete_article(self, article_id: int) -> bool:
        """Удаление статьи"""
        if article_id in self.articles:
            del self.articles[article_id]
            logger.info(f"🗑 Удалена статья #{article_id}")
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
        """
        now_utc = datetime.now()
        pending = []
        
        logger.info(f"🔍 get_pending_posts: всего статей в БД: {len(self.articles)}")
        logger.info(f"🔍 Текущее время UTC: {now_utc}")
        
        for article_id, article in self.articles.items():
            teaser_time_msk = article.get('teaser_time')
            published = article.get('published', False)
            
            if teaser_time_msk:
                teaser_time_utc = teaser_time_msk - timedelta(hours=3)
                
                logger.info(f"🔍 Проверка статьи #{article_id}")
                logger.info(f"   Заголовок: {article.get('teaser_title', 'Без заголовка')}")
                logger.info(f"   Время статьи (МСК): {teaser_time_msk}")
                logger.info(f"   Время статьи (UTC): {teaser_time_utc}")
                logger.info(f"   Текущее время (UTC): {now_utc}")
                logger.info(f"   Опубликована: {published}")
                logger.info(f"   teaser_photo: {article.get('teaser_photo') is not None}")
                
                if teaser_time_utc <= now_utc and not published:
                    pending_post = {
                        'id': article_id,
                        'teaser_title': article.get('teaser_title', ''),
                        'teaser_text': article.get('teaser_text', ''),
                        'teaser_photo': article.get('teaser_photo'),
                        'full_text': article.get('full_text', '')
                    }
                    pending.append(pending_post)
                    article['published'] = True
                    logger.info(f"📊 ПОСТ #{article_id} ГОТОВ К ПУБЛИКАЦИИ!")
                elif teaser_time_utc > now_utc:
                    logger.info(f"⏳ Пост #{article_id} ещё не готов")
                elif published:
                    logger.info(f"✅ Пост #{article_id} уже опубликован")
            else:
                logger.warning(f"⚠️ У статьи #{article_id} нет teaser_time!")
        
        logger.info(f"📊 get_pending_posts: найдено {len(pending)} постов для публикации")
        return pending
    
    async def update_article_photo(self, article_id: int, photo_path: str):
        """Обновляет фото статьи (сохраняет file_id)"""
        if article_id in self.articles:
            self.articles[article_id]['teaser_photo'] = photo_path
            logger.info(f"📸 Фото для статьи #{article_id} сохранено: {photo_path[:20]}...")
            return True
        logger.warning(f"⚠️ Статья #{article_id} не найдена, фото не сохранено")
        return False
    
    async def update_post_status(self, post_id: int, status: str, fail_reason: str = None, retry_count: int = None):
        """Обновление статуса поста"""
        if post_id in self.articles:
            self.articles[post_id]['published'] = (status == 'published')
        logger.info(f"📊 Пост #{post_id} обновлён статус: {status}")
        if fail_reason:
            logger.error(f"❌ Ошибка поста #{post_id}: {fail_reason}")

# Создаём глобальный экземпляр БД
db = Database()

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
            # Создаём копию с нужными полями
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
    
    print(f"📊 get_pending_posts: найдено {len(pending)} постов")
    return pending

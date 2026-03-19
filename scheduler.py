# ============================================
# ПРОСТОЙ ПЛАНИРОВЩИК БЕЗ APSCHEDULER (С ЗАЩИТОЙ)
# ============================================

async def run_scheduler():
    """Простой фоновый планировщик с защитой от падений"""
    logger.info("🚀 Простой планировщик запущен")
    
    while True:
        try:
            # Проверяем посты каждые 30 секунд
            await asyncio.sleep(30)
            
            current_time = datetime.now()
            print(f"⏰ Проверка постов в {current_time.strftime('%H:%M:%S')}")
            logger.info(f"⏰ Проверка постов в {current_time.strftime('%H:%M:%S')}")
            
            # Проверяем, есть ли метод get_pending_posts
            if hasattr(db, 'get_pending_posts'):
                try:
                    posts = await db.get_pending_posts()
                except Exception as e:
                    logger.error(f"❌ Ошибка при получении постов: {e}")
                    continue
                
                if posts:
                    logger.info(f"📋 Найдено {len(posts)} постов для публикации")
                    
                    for post in posts:
                        # Публикуем пост
                        try:
                            channel = config['CHANNEL_ID']
                            
                            # Отправляем в канал
                            await bot.send_message(
                                chat_id=channel,
                                text=post['content'],
                                parse_mode='HTML'
                            )
                            logger.info(f"✅ Пост {post['id']} опубликован")
                            
                            # Обновляем статус
                            if hasattr(db, 'update_post_status'):
                                await db.update_post_status(post['id'], 'published')
                            else:
                                # Если нет метода, просто логируем
                                logger.info(f"✅ Пост {post['id']} обработан")
                                
                        except Exception as e:
                            logger.error(f"❌ Ошибка публикации поста {post['id']}: {e}")
                else:
                    print("📭 Нет постов для публикации")
                    logger.info("📭 Нет постов для публикации")
            else:
                print("❌ Нет метода get_pending_posts")
                logger.error("❌ Нет метода get_pending_posts в database.py")
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в планировщике: {e}")
            logger.info("🔄 Перезапуск планировщика через 10 секунд...")
            await asyncio.sleep(10)

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================

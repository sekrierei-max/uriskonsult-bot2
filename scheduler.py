# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ТИЗЕРОВ
# ============================================

def detect_article_type(text: str) -> str:
    """Определяет тип статьи по ключевым словам"""
    text_lower = text.lower()
    if any(word in text_lower for word in ['инструкция', 'как', 'шаги', 'порядок', 'пошагово']):
        return "instruction"
    elif any(word in text_lower for word in ['кейс', 'пример', 'ситуация', 'дело', 'случай']):
        return "case"
    elif any(word in text_lower for word in ['новость', 'изменения', 'теперь', 'начало']):
        return "news"
    else:
        return "news"  # По умолчанию

def format_teaser_by_type(full_text: str, article_type: str = "news") -> str:
    """
    Форматирует тизер в зависимости от типа статьи
    article_type: news, instruction, case
    """
    lines = full_text.strip().split('\n')
    title = lines[0].strip() if lines else "Статья"
    
    # Собираем остальной текст
    body = ' '.join([line.strip() for line in lines[1:] if line.strip()])
    
    # Обрезаем до 400 символов для тизера
    if len(body) > 400:
        last_space = body[:400].rfind(' ')
        body = body[:last_space] + "..." if last_space > 0 else body[:400] + "..."
    
    # Шаблоны для разных типов статей
    templates = {
        "news": (
            f"⚜️ **{title}**\n\n"
            f"🔹 **Главное:** {body}\n\n"
            f"⚠️ Нажмите кнопку ниже, чтобы прочитать полностью в боте 👇"
        ),
        "instruction": (
            f"📋 **{title}**\n\n"
            f"🔹 **Пошаговая инструкция:**\n{body}\n\n"
            f"✅ Полная версия с деталями — в боте 👇"
        ),
        "case": (
            f"⚖️ **{title}**\n\n"
            f"🔹 **Суть дела:** {body}\n\n"
            f"📌 Результат и юридические детали — в боте 👇"
        )
    }
    
    return templates.get(article_type, templates["news"])

def get_channel_post_keyboard(article_id: int):
    """Клавиатура для поста в канале с красной кнопкой"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔴 ЧИТАТЬ ПОЛНОСТЬЮ В БОТЕ", 
        url=f"https://t.me/uriskonsult_bot?start=article_{article_id}"
    ))
    return builder.as_markup()

# ============================================
# ПРОСТОЙ ПЛАНИРОВЩИК С ФОТО И УМНЫМИ ТИЗЕРАМИ
# ============================================

async def run_scheduler():
    """Простой фоновый планировщик с фото и умными тизерами"""
    logger.info("🚀 Простой планировщик запущен")
    
    while True:
        try:
            await asyncio.sleep(30)
            
            current_time = datetime.now()
            logger.info(f"⏰ Проверка постов в {current_time.strftime('%H:%M:%S')}")
            
            if not hasattr(db, 'get_pending_posts'):
                logger.error("❌ Нет метода get_pending_posts в database.py")
                continue
            
            try:
                posts = await db.get_pending_posts()
            except Exception as e:
                logger.error(f"❌ Ошибка при получении постов: {e}")
                continue
            
            if posts:
                logger.info(f"📋 Найдено {len(posts)} постов для публикации")
                
                for post in posts:
                    try:
                        channel = config['CHANNEL_ID']
                        
                        # Определяем тип статьи и форматируем тизер
                        article_type = detect_article_type(post['content'])
                        post_text = format_teaser_by_type(post['content'], article_type)
                        
                        # Путь к фото
                        photo_path = os.path.join("images", "max_full.jpg")
                        
                        # Отправляем в канал с фото и кнопкой
                        if os.path.exists(photo_path):
                            photo = FSInputFile(photo_path)
                            await bot.send_photo(
                                chat_id=channel,
                                photo=photo,
                                caption=post_text,
                                parse_mode='HTML',
                                reply_markup=get_channel_post_keyboard(post['id'])
                            )
                            logger.info(f"✅ Пост {post['id']} опубликован в канале с фото и кнопкой")
                        else:
                            # Если фото нет, отправляем только текст
                            await bot.send_message(
                                chat_id=channel,
                                text=post_text,
                                parse_mode='HTML',
                                reply_markup=get_channel_post_keyboard(post['id'])
                            )
                            logger.warning(f"⚠️ Пост {post['id']} опубликован без фото (файл не найден)")
                        
                        # Обновляем статус
                        if hasattr(db, 'update_post_status'):
                            await db.update_post_status(post['id'], 'published')
                            
                    except Exception as e:
                        logger.error(f"❌ Ошибка публикации поста {post['id']}: {e}")
            else:
                logger.info("📭 Нет постов для публикации")
                
        except asyncio.CancelledError:
            logger.info("🛑 Планировщик остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в планировщике: {e}")
            await asyncio.sleep(10)

# ============================================
# ГЛАВНАЯ ФУНКЦИЯ ЗАПУСКА
# ============================================

#!/usr/bin/env python3
"""
Независимый планировщик публикаций в Telegram канал
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Set

# ============================================
# МАКСИМАЛЬНАЯ ДИАГНОСТИКА
# ============================================
print("="*60)
print("🔴 SCHEDULER FORCED DIAGNOSTICS - STARTING")
print(f"🔴 1. Текущее время: {datetime.now()}")
print(f"🔴 2. BOT_TOKEN из os.environ: {os.getenv('BOT_TOKEN', 'НЕТ ТОКЕНА')[:15]}...")
print(f"🔴 3. CHANNEL_ID из os.environ: {os.getenv('CHANNEL_ID', 'НЕТ ID')}")
print("="*60)
sys.stdout.flush()

# Пробуем импортировать APScheduler
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor, ProcessPoolExecutor
    from pytz import timezone
    print("✅ APScheduler импортирован успешно")
except Exception as e:
    print(f"❌ ОШИБКА ИМПОРТА APScheduler: {e}")
    sys.exit(1)

# Пробуем импортировать aiogram
try:
    from aiogram import Bot
    from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter, TelegramForbiddenError
    print("✅ Aiogram импортирован успешно")
except Exception as e:
    print(f"❌ ОШИБКА ИМПОРТА aiogram: {e}")
    sys.exit(1)

# Пробуем импортировать локальные модули
try:
    from config import config
    from database import db
    from logger_config import setup_logger
    print("✅ Локальные модули импортированы успешно")
except Exception as e:
    print(f"❌ ОШИБКА ИМПОРТА локальных модулей: {e}")
    sys.exit(1)

print("🔴 Все импорты выполнены, создаю логгер...")
sys.stdout.flush()

# Настройка логирования
logger = setup_logger('scheduler', config.SCHEDULER_LOG)
print("✅ Логгер создан")

class PostScheduler:
    """Независимый планировщик постов"""
    
    def __init__(self):
        print("🔴 4. Инициализация PostScheduler...")
        sys.stdout.flush()
        
        self.bot = Bot(token=config.BOT_TOKEN)
        self.moscow_tz = timezone('Europe/Moscow')
        
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(20),
            'processpool': ProcessPoolExecutor(5)
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3,
            'misfire_grace_time': 60
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=self.moscow_tz
        )
        
        self.processing_posts: Set[int] = set()
        
        self.stats = {
            'published_today': 0,
            'failed_today': 0,
            'last_check': None,
            'start_time': datetime.now(self.moscow_tz)
        }
        
        self.is_running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        print("🔴 5. PostScheduler инициализирован")
        sys.stdout.flush()

    def signal_handler(self, signum, frame):
        """Обработка сигналов завершения"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.is_running = False

    async def publish_post(self, post: Dict):
        """Публикация одного поста с повторными попытками"""
        post_id = post['id']
        retry_count = post.get('retry_count', 0)
        
        if post_id in self.processing_posts:
            logger.debug(f"Post {post_id} is already being processed")
            return
        
        self.processing_posts.add(post_id)
        
        try:
            logger.info(f"📤 Attempting to publish post {post_id} (type: {post['post_type']}, attempt: {retry_count + 1})")
            
            # ПРАВИЛЬНАЯ обработка ID канала
            if str(config.CHANNEL_ID).startswith('-100'):
                # Это числовой ID канала (например, -1003811104379)
                channel = int(config.CHANNEL_ID)
                logger.info(f"📢 Канал (числовой ID): {channel}")
            else:
                # Это юзернейм (например, @channelname)
                channel = "@" + config.CHANNEL_ID
                logger.info(f"📢 Канал (юзернейм): {channel}")
            
            message = await self.bot.send_message(
                chat_id=channel,
                text=post['content'],
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
            
            await db.update_post_status(post_id, 'published')
            
            logger.info(f"✅ Post {post_id} published successfully (message_id: {message.message_id})")
            
            await self.bot.send_message(
                config.ADMIN_ID,
                f"✅ Пост #{post_id} ({post['post_type']}) успешно опубликован в канале"
            )
            
            self.stats['published_today'] += 1
            
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            logger.warning(f"⏳ Flood control for post {post_id}, waiting {wait_time} seconds")
            
            self.scheduler.add_job(
                self.publish_post,
                'date',
                run_date=datetime.now(self.moscow_tz) + timedelta(seconds=wait_time),
                args=[{**post, 'retry_count': retry_count + 1}],
                id=f"retry_{post_id}_{retry_count + 1}",
                replace_existing=True
            )
            
        except TelegramForbiddenError as e:
            error_msg = f"Bot blocked or no rights: {e}"
            logger.error(f"❌ {error_msg}")
            await db.update_post_status(post_id, 'failed', error_msg, retry_count + 1)
            
            await self.bot.send_message(
                config.ADMIN_ID,
                f"❌ КРИТИЧЕСКАЯ ОШИБКА: {error_msg}\nПроверьте права бота в канале!"
            )
            
            self.stats['failed_today'] += 1
            
        except TelegramAPIError as e:
            error_msg = str(e)
            logger.error(f"❌ Telegram API error for post {post_id}: {error_msg}")
            
            if retry_count < 2:
                retry_time = datetime.now(self.moscow_tz) + timedelta(minutes=5)
                self.scheduler.add_job(
                    self.publish_post,
                    'date',
                    run_date=retry_time,
                    args=[{**post, 'retry_count': retry_count + 1}],
                    id=f"retry_{post_id}_{retry_count + 1}",
                    replace_existing=True
                )
                logger.info(f"⏰ Scheduled retry #{retry_count + 1} for post {post_id} at {retry_time}")
            else:
                await db.update_post_status(post_id, 'failed', error_msg, retry_count + 1)
                logger.error(f"❌ Post {post_id} failed after {retry_count + 1} attempts")
                
                await self.bot.send_message(
                    config.ADMIN_ID,
                    f"❌ Пост #{post_id} ({post['post_type']}) не удалось опубликовать после 3 попыток.\n"
                    f"Ошибка: {error_msg[:200]}"
                )
                
                self.stats['failed_today'] += 1
                
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            logger.exception(f"❌ {error_msg} for post {post_id}")
            
            await db.update_post_status(post_id, 'failed', error_msg, retry_count + 1)
            
            await self.bot.send_message(
                config.ADMIN_ID,
                f"❌ Непредвиденная ошибка при публикации поста #{post_id}:\n{error_msg[:200]}"
            )
            
            self.stats['failed_today'] += 1
            
        finally:
            self.processing_posts.remove(post_id)

    async def check_pending_posts(self):
        """Проверка и публикация ожидающих постов"""
        current_time = datetime.now().strftime('%H:%M:%S')
        print(f"🔍🔍🔍 check_pending_posts ВЫЗВАНА в {current_time}! 🔍🔍🔍")
        sys.stdout.flush()
        
        try:
            logger.debug("🔍 Checking for pending posts...")
            self.stats['last_check'] = datetime.now(self.moscow_tz)
            
            # Проверяем, есть ли метод get_pending_posts
            if not hasattr(db, 'get_pending_posts'):
                print("❌ ВНИМАНИЕ: у db нет метода get_pending_posts!")
                sys.stdout.flush()
                return
            
            posts = await db.get_pending_posts()
            
            if posts:
                logger.info(f"📋 Found {len(posts)} pending posts")
                print(f"📋 Найдено {len(posts)} ожидающих постов")
                sys.stdout.flush()
                
                for post in posts:
                    job_id = f"post_{post['id']}"
                    if not self.scheduler.get_job(job_id) and post['id'] not in self.processing_posts:
                        self.scheduler.add_job(
                            self.publish_post,
                            'date',
                            run_date=datetime.now(self.moscow_tz),
                            args=[post],
                            id=job_id
                        )
                        logger.debug(f"⏰ Scheduled post {post['id']} for immediate publishing")
                        print(f"⏰ Запланирован пост {post['id']}")
                        sys.stdout.flush()
            else:
                logger.debug("No pending posts found")
                print("📭 Нет ожидающих постов")
                sys.stdout.flush()
                
        except Exception as e:
            logger.error(f"❌ Error checking pending posts: {e}")
            print(f"❌ Ошибка в check_pending_posts: {e}")
            sys.stdout.flush()
            logger.exception(e)
            
            try:
                await self.bot.send_message(
                    config.ADMIN_ID,
                    f"⚠️ Критическая ошибка планировщика при проверке постов:\n{str(e)[:200]}"
                )
            except:
                pass

    # ========== ИСПРАВЛЕННЫЙ WRAPPER ==========
    def check_pending_posts_wrapper(self):
        """Обёртка для вызова асинхронной функции - синхронная (для APScheduler)"""
        print(f"🔄 Wrapper вызван в {datetime.now().strftime('%H:%M:%S')}")
        # Создаём задачу для асинхронного выполнения
        asyncio.create_task(self._check_pending_posts_async())

    async def _check_pending_posts_async(self):
        """Асинхронная часть проверки постов"""
        try:
            await self.check_pending_posts()
        except Exception as e:
            logger.error(f"❌ Ошибка в планировщике: {e}")
            print(f"❌ Ошибка: {e}")
            sys.stdout.flush()
    # ==========================================

    async def send_daily_report(self):
        """Отправка ежедневного отчёта администратору"""
        try:
            report = (
                f"📊 **Ежедневный отчёт планировщика**\n\n"
                f"✅ Опубликовано сегодня: {self.stats['published_today']}\n"
                f"❌ Ошибок сегодня: {self.stats['failed_today']}\n"
                f"🕐 Время работы: {datetime.now(self.moscow_tz) - self.stats['start_time']}\n"
                f"📅 Дата: {datetime.now(self.moscow_tz).strftime('%d.%m.%Y')}\n\n"
            )
            
            stats = await db.get_scheduler_stats()
            report += (
                f"⏳ Ожидают: {stats['pending']}\n"
                f"📤 Всего опубликовано: {stats['published']}\n"
                f"❌ Всего ошибок: {stats['failed']}"
            )
            
            await self.bot.send_message(config.ADMIN_ID, report)
            
            self.stats['published_today'] = 0
            self.stats['failed_today'] = 0
            
            logger.info("Daily report sent")
            
        except Exception as e:
            logger.error(f"Failed to send daily report: {e}")

    async def health_check(self):
        """Проверка здоровья планировщика"""
        try:
            await db.get_scheduler_stats()
            await self.bot.send_chat_action(config.ADMIN_ID, "typing")
            logger.debug("Health check passed")
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            try:
                await db.connect()
                logger.info("Reconnected to database")
            except:
                pass

    async def start(self):
        """Запуск планировщика"""
        try:
            print("🔴 6. Подключение к базе данных...")
            sys.stdout.flush()
            
            await db.connect()
            logger.info("✅ Database connected")
            print("🔴 7. База данных подключена")
            sys.stdout.flush()
            
            try:
                await self.bot.send_message(
                    config.ADMIN_ID,
                    f"🟢 **Планировщик успешно запущен**\n"
                    f"🕐 Время: {datetime.now(self.moscow_tz).strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
                    f"📊 Проверка постов: каждую минуту\n"
                    f"🔄 Повторные попытки: до 3 раз"
                )
                logger.info("Startup notification sent to admin")
                print("🔴 8. Уведомление админу отправлено")
            except Exception as e:
                logger.error(f"Failed to send startup notification: {e}")
                print(f"🔴 8. Ошибка отправки уведомления: {e}")
            
            sys.stdout.flush()
            
            # Добавляем задачу через синхронный wrapper
            self.scheduler.add_job(
                self.check_pending_posts_wrapper,  # ← теперь это синхронная функция
                trigger=IntervalTrigger(minutes=1),
                id='check_posts',
                replace_existing=True,
                misfire_grace_time=30
            )
            print("✅ Задача check_posts добавлена в планировщик (через синхронный wrapper)")
            sys.stdout.flush()
            
            self.scheduler.add_job(
                self.send_daily_report,
                trigger=CronTrigger(hour=23, minute=59, timezone=self.moscow_tz),
                id='daily_report',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                self.health_check,
                trigger=IntervalTrigger(minutes=5),
                id='health_check',
                replace_existing=True
            )
            
            self.scheduler.add_job(
                lambda: db.cleanup_old_posts(30),
                trigger=CronTrigger(day_of_week='sun', hour=3, minute=0, timezone=self.moscow_tz),
                id='cleanup_old_posts',
                replace_existing=True
            )
            
            self.scheduler.start()
            logger.info("🚀 Scheduler started successfully")
            print("🔴 9. Планировщик успешно запущен и работает!")
            sys.stdout.flush()
            
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.exception(f"Fatal error in scheduler: {e}")
            print(f"🔴 ФАТАЛЬНАЯ ОШИБКА: {e}")
            sys.stdout.flush()
            
            try:
                await self.bot.send_message(
                    config.ADMIN_ID,
                    f"💥 **Фатальная ошибка планировщика**\n{str(e)[:200]}"
                )
            except:
                pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down scheduler...")
        self.scheduler.shutdown(wait=True)
        # Убираем попытку закрыть db.pool, так как в тестовой БД его нет
        # await db.pool.close()
        await self.bot.session.close()
        logger.info("👋 Scheduler stopped")

async def main():
    """Точка входа"""
    print("🔴 0. Запуск main() функции scheduler.py")
    sys.stdout.flush()
    scheduler = PostScheduler()
    await scheduler.start()

if __name__ == "__main__":
    print("🔴 Scheduler.py запущен как главный модуль")
    sys.stdout.flush()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Scheduler terminated by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        print(f"🔴 НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ: {e}")
        sys.stdout.flush()
        sys.exit(1)

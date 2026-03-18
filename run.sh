#!/bin/bash

echo "🚀 Запуск Telegram Publisher..."
echo "================================"

# Создаем папку для логов
mkdir -p logs
echo "📁 Папка logs создана" | tee -a logs/startup.log

# Проверяем переменные окружения
echo "🔍 Проверка переменных:" | tee -a logs/startup.log
echo "BOT_TOKEN: ${BOT_TOKEN:0:10}... (первые 10 символов)" | tee -a logs/startup.log
echo "ADMIN_ID: $ADMIN_ID" | tee -a logs/startup.log
echo "CHANNEL_ID: $CHANNEL_ID" | tee -a logs/startup.log

# Запускаем планировщик
echo "📅 Запускаю планировщик..." | tee -a logs/startup.log
nohup python scheduler.py > logs/scheduler_output.log 2>&1 &
SCHEDULER_PID=$!
echo "✅ Планировщик запущен с PID: $SCHEDULER_PID" | tee -a logs/startup.log

# Ждём 3 секунды
sleep 3

# Запускаем бота
echo "🤖 Запускаю бота..." | tee -a logs/startup.log
nohup python bot.py > logs/bot_output.log 2>&1 &
BOT_PID=$!
echo "✅ Бот запущен с PID: $BOT_PID" | tee -a logs/startup.log

# Проверяем процессы
echo "" | tee -a logs/startup.log
echo "📊 Проверка процессов:" | tee -a logs/startup.log
ps aux | grep python | grep -v grep | tee -a logs/startup.log

echo "" | tee -a logs/startup.log
echo "✅ Все процессы запущены!" | tee -a logs/startup.log
echo "📝 Смотрите логи в папке logs/" | tee -a logs/startup.log

# Держим контейнер активным
tail -f /dev/null

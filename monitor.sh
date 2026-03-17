#!/bin/bash

# Скрипт для мониторинга процессов и автоматического перезапуска

LOG_FILE="logs/monitor.log"
PROCESS_CHECK_INTERVAL=60  # Проверка каждые 60 секунд

# Создаем директорию для логов если её нет
mkdir -p logs

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_process() {
    if pgrep -f "python.*$1" > /dev/null; then
        return 0
    else
        return 1
    fi
}

restart_process() {
    log "🔄 Перезапуск $1..."
    cd "$(dirname "$0")"
    
    # Активируем виртуальное окружение если есть
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    nohup python "$1" >> "logs/${1%.py}_output.log" 2>&1 &
    NEW_PID=$!
    log "✅ $1 перезапущен с PID: $NEW_PID"
}

log "🚀 Мониторинг процессов запущен"
log "Интервал проверки: $PROCESS_CHECK_INTERVAL секунд"

# Бесконечный цикл мониторинга
while true; do
    # Проверяем планировщик
    if ! check_process "scheduler.py"; then
        log "❌ Планировщик не работает!"
        restart_process "scheduler.py"
    fi
    
    # Проверяем бота
    if ! check_process "bot.py"; then
        log "❌ Бот не работает!"
        restart_process "bot.py"
    fi
    
    # Ждём перед следующей проверкой
    sleep $PROCESS_CHECK_INTERVAL
done
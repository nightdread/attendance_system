#!/bin/bash
# Скрипт для развертывания системы учета посещаемости на продакшн сервере

set -e

echo "🚀 Развертывание Attendance System"
echo "=================================="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

echo "✅ Python3 найден: $(python3 --version)"

# Создание виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активация и установка зависимостей
echo "📦 Установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Проверка Redis
echo "💾 Проверка Redis..."
if docker ps | grep -q redis-attendance; then
    echo "✅ Redis контейнер уже запущен"
elif command -v docker &> /dev/null; then
    echo "🐳 Запуск Redis контейнера..."
    docker run -d --name redis-attendance \
        --restart unless-stopped \
        -p 6379:6379 \
        redis:alpine
    echo "✅ Redis контейнер запущен"
else
    echo "⚠️  Docker не найден, Redis будет использоваться через системный сервис"
fi

# Проверка конфигурации
if [ ! -f "config/config.py" ]; then
    echo "⚠️  config/config.py не найден, создайте его из config.example.py"
    echo "   cp config.example.py config/config.py"
    echo "   nano config/config.py"
fi

# Инициализация базы данных
echo "🗄️  Инициализация базы данных..."
python3 -c "from database import Database; Database('attendance.db')"
echo "✅ База данных инициализирована"

# Проверка systemd сервисов
if [ -f "/etc/systemd/system/attendance-backend.service" ]; then
    echo "✅ Systemd сервисы уже созданы"
else
    echo "📝 Создайте systemd сервисы (см. DEPLOY.md)"
fi

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Настройте config/config.py"
echo "2. Создайте systemd сервисы (см. DEPLOY.md)"
echo "3. Запустите сервисы:"
echo "   sudo systemctl start attendance-backend"
echo "   sudo systemctl start attendance-bot"
echo ""
echo "🌐 Система будет доступна на http://localhost:8000"

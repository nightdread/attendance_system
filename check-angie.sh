#!/bin/bash

# Скрипт для проверки настройки Angie

echo "🔍 Проверка настройки Angie"
echo "==========================="

# Проверка переменных окружения
echo ""
echo "📄 Переменные окружения:"
if [ -f ".env" ]; then
    source .env
    echo "✅ .env файл найден"
    if [ -n "$DOMAIN" ]; then
        echo "✅ DOMAIN: $DOMAIN"
    else
        echo "❌ DOMAIN не установлена в .env"
    fi
else
    echo "❌ .env файл не найден"
fi

# Проверка файлов
echo ""
echo "📁 Файлы настройки:"
if [ -f "angie.conf.template" ]; then
    echo "✅ angie.conf.template найден"
else
    echo "❌ angie.conf.template не найден"
fi

if [ -f "generate-angie-conf.sh" ]; then
    echo "✅ generate-angie-conf.sh найден"
else
    echo "❌ generate-angie-conf.sh не найден"
fi

if [ -f "angie.conf" ]; then
    echo "✅ angie.conf сгенерирован"
    if grep -q "$DOMAIN" angie.conf 2>/dev/null; then
        echo "✅ Домен подставлен в конфигурацию"
    else
        echo "❌ Домен не подставлен в конфигурацию"
    fi
else
    echo "❌ angie.conf не сгенерирован"
fi

# Проверка сертификатов
echo ""
echo "🔒 SSL сертификаты:"
if [ -d "ssl" ]; then
    echo "✅ Директория ssl/ существует"
    cert_files=$(ls ssl/ 2>/dev/null | wc -l)
    if [ "$cert_files" -gt 0 ]; then
        echo "✅ Найдено файлов сертификатов: $cert_files"
        ls -la ssl/
    else
        echo "❌ Сертификаты не найдены в ssl/"
    fi
else
    echo "❌ Директория ssl/ не существует"
fi

# Проверка Docker контейнера
echo ""
echo "🐳 Docker контейнер:"
if docker-compose ps | grep -q "attendance_angie"; then
    echo "✅ Angie контейнер запущен"
    status=$(docker-compose ps angie | tail -n 1 | awk '{print $4}')
    echo "📊 Статус: $status"

    # Проверка Docker модуля
    echo ""
    echo "🔍 Docker модуль Angie:"
    echo "Запустите ./test-angie-docker.sh для подробной проверки Docker модуля"
else
    echo "❌ Angie контейнер не запущен"
fi

# Проверка доступности
echo ""
echo "🌐 Доступность:"
if [ -n "$DOMAIN" ]; then
    echo "Проверка HTTPS: https://$DOMAIN"
    if curl -k -s --max-time 10 "https://$DOMAIN" > /dev/null 2>&1; then
        echo "✅ HTTPS доступен"
    else
        echo "❌ HTTPS недоступен"
    fi
else
    echo "❌ Домен не указан"
fi

echo ""
echo "📋 Следующие шаги:"
echo "1. Установите DOMAIN=your-domain.com в .env"
echo "2. Поместите SSL сертификаты в ssl/ директорию"
echo "3. Запустите: docker-compose up angie -d"
echo "4. Проверьте: ./check-angie.sh"

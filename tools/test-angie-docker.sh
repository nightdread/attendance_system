#!/bin/bash

# Скрипт для тестирования Docker модуля Angie

echo "🧪 Тестирование Docker модуля Angie"
echo "==================================="

# Проверить, запущен ли Angie
if ! docker-compose ps | grep -q "attendance_angie"; then
    echo "❌ Angie контейнер не запущен"
    echo "Запустите: docker-compose up angie -d"
    exit 1
fi

echo "✅ Angie контейнер запущен"

# Проверить Docker модуль
echo ""
echo "🔍 Проверка Docker модуля:"

# Проверить переменную окружения
DOCKER_MODULES=$(docker-compose exec -T angie env | grep ANGIE_LOAD_MODULES || echo "Переменная не найдена")
if [[ "$DOCKER_MODULES" == *"docker"* ]]; then
    echo "✅ ANGIE_LOAD_MODULES содержит 'docker'"
else
    echo "⚠️  ANGIE_LOAD_MODULES: $DOCKER_MODULES"
fi

# Проверить доступ к Docker socket
if docker-compose exec -T angie test -S /var/run/docker.sock; then
    echo "✅ Docker socket доступен"
else
    echo "❌ Docker socket недоступен"
fi

# Проверить метки контейнера attendance_app
echo ""
echo "🏷️  Проверка меток контейнера:"
CONTAINER_ID=$(docker-compose ps -q attendance_app)
if [ -n "$CONTAINER_ID" ]; then
    LABELS=$(docker inspect $CONTAINER_ID | grep -A 2 "angie.http.upstreams" || echo "Метки не найдены")
    if [[ "$LABELS" == *"attendance_backend"* ]]; then
        echo "✅ Метки Angie найдены в attendance_app"
    else
        echo "❌ Метки Angie не найдены"
        echo "$LABELS"
    fi
else
    echo "❌ Контейнер attendance_app не найден"
fi

# Проверить upstream статус
echo ""
echo "🌊 Проверка upstream группы:"
UPSTREAM_INFO=$(docker-compose exec -T angie angie -s status 2>/dev/null | grep -A 3 "attendance_backend" || echo "Upstream не найден")
if [[ "$UPSTREAM_INFO" == *"attendance_backend"* ]]; then
    echo "✅ Upstream группа attendance_backend найдена"
    echo "$UPSTREAM_INFO"
else
    echo "❌ Upstream группа не найдена"
    echo "Возможно, модуль Docker не загружен или контейнеры не обнаружены"
fi

# Проверить логи Angie на ошибки
echo ""
echo "📋 Последние логи Angie:"
docker-compose logs --tail=5 angie 2>/dev/null | grep -E "(error|warn|docker)" || echo "Ошибок в логах не найдено"

echo ""
echo "🎯 Рекомендации:"
echo "- Если upstream пустой: проверьте метки контейнера"
echo "- Если модуль не работает: проверьте ANGIE_LOAD_MODULES=docker"
echo "- Если socket недоступен: проверьте монтирование /var/run/docker.sock"


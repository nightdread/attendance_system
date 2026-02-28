#!/bin/bash

# Генерация angie.conf из шаблона (для автономного развёртывания с локальным Angie).
# При использовании центрального прокси /opt/angie_web_server этот скрипт не нужен.

set -e

# Загружаем переменные из .env файла (без выполнения команд)
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Проверяем наличие DOMAIN
if [ -z "$DOMAIN" ]; then
    echo "❌ Ошибка: переменная DOMAIN не установлена!"
    echo "Добавьте DOMAIN=your-domain.com в .env файл"
    exit 1
fi

echo "🔧 Генерация angie.conf для домена: $DOMAIN"
echo "📋 Используем шаблон С Docker модулем"

# Заменяем только DOMAIN в шаблоне
sed "s/\${DOMAIN}/$DOMAIN/g" docs/angie.conf.template > angie.conf

echo "✅ angie.conf сгенерирован успешно!"
echo "📄 Проверьте файл: cat angie.conf"

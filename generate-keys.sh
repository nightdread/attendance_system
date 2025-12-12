#!/bin/bash
# Скрипт для генерации безопасных ключей для .env файла

echo "🔑 Генерация ключей для .env файла"
echo "=================================="

# Генерация SECRET_KEY (64 символа)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
echo "SECRET_KEY=${SECRET_KEY}"

# Генерация API_KEY (32 символа)  
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "API_KEY=${API_KEY}"

# Генерация JWT_SECRET_KEY (64 символа)
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
echo "JWT_SECRET_KEY=${JWT_SECRET_KEY}"

# Генерация WEB_PASSWORD (16 символов, читаемый)
WEB_PASSWORD=$(python3 -c "
import secrets
import string
chars = string.ascii_letters + string.digits + '!@#\$%^&*'
password = ''.join(secrets.choice(chars) for _ in range(16))
print(password)
")
echo "WEB_PASSWORD=${WEB_PASSWORD}"

echo ""
echo "📋 Скопируйте эти значения в ваш .env файл"
echo "⚠️  Храните эти ключи в безопасности!"
echo "🔄 Сгенерируйте новые ключи для продакшна"

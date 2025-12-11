#!/bin/bash

# Скрипт для автоматической настройки SSL сертификатов
# Использование: ./setup-ssl.sh your-domain.com your-email@example.com

set -e

DOMAIN="${1:-}"
EMAIL="${2:-}"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Использование: $0 <domain> <email>"
    echo "Пример: $0 example.com admin@example.com"
    exit 1
fi

echo "Настройка SSL для домена: $DOMAIN"
echo "Email для уведомлений: $EMAIL"

# Создаем директории
mkdir -p certbot/conf certbot/www logs

# Обновляем nginx.conf с правильным доменом
sed -i "s/your-domain.com/$DOMAIN/g" nginx.conf
sed -i "s/www.your-domain.com/www.$DOMAIN/g" nginx.conf

# Создаем временный nginx конфиг для получения сертификата
cat > nginx-temp.conf <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Let\\'s Encrypt validation';
        add_header Content-Type text/plain;
    }
}
EOF

echo "Запуск временного nginx для получения сертификата..."
docker run -d --name nginx-temp \
  -v "$(pwd)/nginx-temp.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  -p 80:80 \
  nginx:alpine

sleep 5

echo "Получение SSL сертификата..."
docker run -it --rm \
  -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
  -v "$(pwd)/certbot/www:/var/www/certbot" \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d "$DOMAIN" \
  -d "www.$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos \
  --non-interactive

echo "Остановка временного nginx..."
docker stop nginx-temp
docker rm nginx-temp

echo "Проверка сертификатов..."
if [ -f "certbot/conf/live/$DOMAIN/fullchain.pem" ]; then
    echo "✓ Сертификаты успешно получены!"
    echo "Теперь запустите: docker-compose -f ../docker-compose.yml -f docker-compose.nginx.yml up -d"
else
    echo "✗ Ошибка: сертификаты не найдены"
    exit 1
fi


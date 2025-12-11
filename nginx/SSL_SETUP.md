# Настройка SSL для Attendance System

Это руководство поможет настроить SSL сертификаты через Let's Encrypt для вашего сервиса учета времени.

## Предварительные требования

1. Домен должен быть настроен и указывать на ваш сервер (A-запись)
2. Порты 80 и 443 должны быть открыты в firewall
3. Docker и docker-compose должны быть установлены

## Шаг 1: Подготовка директорий

```bash
cd /root/attendance_system/nginx
mkdir -p certbot/conf certbot/www logs
```

## Шаг 2: Обновление конфигурации nginx

Отредактируйте файл `nginx.conf` и замените:
- `your-domain.com` на ваш реальный домен
- `www.your-domain.com` на ваш домен с www (если нужен)

## Шаг 3: Временный запуск nginx для получения сертификата

Сначала запустите nginx без SSL для прохождения ACME challenge:

```bash
# Временно измените nginx.conf - закомментируйте редирект на HTTPS
# Или используйте временный конфиг только для получения сертификата
```

Создайте временный конфиг `nginx-temp.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'Let\'s Encrypt validation';
        add_header Content-Type text/plain;
    }
}
```

Запустите nginx с временным конфигом:

```bash
docker run -it --rm \
  -v $(pwd)/nginx-temp.conf:/etc/nginx/conf.d/default.conf:ro \
  -v $(pwd)/certbot/www:/var/www/certbot \
  -p 80:80 \
  nginx:alpine
```

## Шаг 4: Получение SSL сертификата

В другом терминале выполните:

```bash
docker run -it --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -v $(pwd)/certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d your-domain.com \
  -d www.your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive
```

**Важно:** Замените:
- `your-domain.com` на ваш домен
- `your-email@example.com` на ваш email

## Шаг 5: Обновление nginx.conf

Убедитесь, что в `nginx.conf` указаны правильные пути к сертификатам:
- `/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- `/etc/letsencrypt/live/your-domain.com/privkey.pem`
- `/etc/letsencrypt/live/your-domain.com/chain.pem`

## Шаг 6: Запуск production конфигурации

Остановите временный nginx и запустите полную конфигурацию:

```bash
# Остановите временный контейнер
docker stop <container_id>

# Запустите основной docker-compose с nginx
cd /root/attendance_system
docker-compose -f docker-compose.yml -f nginx/docker-compose.nginx.yml up -d
```

## Шаг 7: Проверка SSL

Проверьте SSL сертификат:
- Откройте https://your-domain.com в браузере
- Проверьте на [SSL Labs](https://www.ssllabs.com/ssltest/)

## Автоматическое обновление сертификатов

Сертификаты Let's Encrypt действительны 90 дней. Контейнер `certbot` автоматически обновляет их каждые 12 часов. Nginx перезагружается каждые 6 часов для применения новых сертификатов.

## Альтернативный способ: Использование certbot в режиме standalone

Если у вас нет доступа к порту 80, можно использовать standalone режим:

```bash
# Остановите nginx
docker-compose down

# Получите сертификат в standalone режиме
docker run -it --rm \
  -v $(pwd)/certbot/conf:/etc/letsencrypt \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d your-domain.com \
  -d www.your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --non-interactive

# Запустите nginx снова
docker-compose up -d
```

## Troubleshooting

### Проблема: "Failed to obtain certificate"

**Решение:**
- Убедитесь, что домен указывает на ваш сервер
- Проверьте, что порт 80 открыт: `sudo ufw allow 80`
- Проверьте логи: `docker logs attendance_certbot`

### Проблема: "Connection refused"

**Решение:**
- Убедитесь, что основной docker-compose запущен: `docker-compose ps`
- Проверьте, что сервис `attendance_app` доступен: `docker-compose logs attendance_app`
- Проверьте сеть: `docker network ls` и убедитесь, что `attendance_network` существует

### Проблема: "SSL certificate problem"

**Решение:**
- Проверьте пути к сертификатам в nginx.conf
- Убедитесь, что volumes правильно смонтированы
- Проверьте права доступа: `ls -la certbot/conf/live/your-domain.com/`

## Проверка конфигурации nginx

```bash
# Проверка синтаксиса
docker run --rm -v $(pwd)/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t

# Просмотр конфигурации
docker exec attendance_nginx nginx -t
```

## Обновление сертификата вручную

Если нужно обновить сертификат вручную:

```bash
docker exec attendance_certbot certbot renew --force-renewal
docker exec attendance_nginx nginx -s reload
```


# Nginx Reverse Proxy с SSL

Конфигурация nginx для проксирования Attendance System с поддержкой SSL через Let's Encrypt.

## Быстрый старт

1. **Настройте домен** - убедитесь, что DNS записи указывают на ваш сервер

2. **Получите SSL сертификат**:
   ```bash
   cd nginx
   ./setup-ssl.sh your-domain.com your-email@example.com
   ```

3. **Запустите nginx**:
   ```bash
   cd ..
   docker-compose -f docker-compose.yml -f nginx/docker-compose.nginx.yml up -d
   ```

## Файлы

- `nginx.conf` - основная конфигурация nginx с SSL
- `docker-compose.nginx.yml` - docker-compose для nginx и certbot
- `setup-ssl.sh` - скрипт для автоматической настройки SSL
- `SSL_SETUP.md` - подробная инструкция по настройке

## Важные замечания

1. **Перед запуском** замените `your-domain.com` на ваш реальный домен в `nginx.conf`
2. **Порты 80 и 443** должны быть открыты в firewall
3. **Сеть docker** - убедитесь, что `attendance_network` существует или создайте её:
   ```bash
   docker network create attendance_network
   ```

## Проверка работы

После запуска проверьте:
- HTTP редирект: `http://your-domain.com` → должен редиректить на HTTPS
- HTTPS доступ: `https://your-domain.com` → должен открываться сайт
- SSL сертификат: проверьте в браузере или на [SSL Labs](https://www.ssllabs.com/ssltest/)

## Обновление сертификатов

Сертификаты обновляются автоматически каждые 12 часов через контейнер `certbot`. Nginx перезагружается каждые 6 часов.

Для ручного обновления:
```bash
docker exec attendance_certbot certbot renew
docker exec attendance_nginx nginx -s reload
```


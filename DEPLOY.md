# 🚀 Инструкция по развертыванию на продакшн сервере

## 📋 Требования

- Python 3.12+
- Docker и Docker Compose (для Redis)
- Система инициализации (systemd/supervisor)
- Nginx (опционально, для reverse proxy)

## 🔧 Шаги развертывания

### 1. Копирование файлов

```bash
# Скопируйте всю директорию attendance_system на продакшн сервер
scp -r attendance_system/ user@prod-server:/opt/
```

### 2. Установка зависимостей

```bash
cd /opt/attendance_system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Настройка конфигурации

```bash
# Скопируйте и отредактируйте переменные окружения
cp .env.example .env
nano .env
```

**Важные настройки для продакшн:**
- `SECRET_KEY` - сгенерируйте новый безопасный ключ
- `BOT_TOKEN` - токен Telegram бота
- `WEB_PASSWORD` - сильный пароль для админки
- `REDIS_ENABLED = True` - включить Redis
- `API_HOST = "0.0.0.0"` - для доступа извне
- `API_PORT = 8000` - или другой порт

### 4. Запуск Redis

```bash
# Через Docker
docker run -d --name redis-attendance \
  --restart unless-stopped \
  -p 6379:6379 \
  redis:alpine

# Или установите Redis напрямую
sudo apt update && sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 5. Инициализация базы данных

```bash
cd /opt/attendance_system
source venv/bin/activate
python3 -c "from database import Database; Database('attendance.db')"
```

### 6. Создание systemd сервисов

#### Backend сервис (`/etc/systemd/system/attendance-backend.service`):

```ini
[Unit]
Description=Attendance System Backend
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/attendance_system/backend
Environment="PATH=/opt/attendance_system/venv/bin"
ExecStart=/opt/attendance_system/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### Bot сервис (`/etc/systemd/system/attendance-bot.service`):

```ini
[Unit]
Description=Attendance System Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/attendance_system/bot
Environment="PATH=/opt/attendance_system/venv/bin"
ExecStart=/opt/attendance_system/venv/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 7. Запуск сервисов

```bash
sudo systemctl daemon-reload
sudo systemctl enable attendance-backend
sudo systemctl enable attendance-bot
sudo systemctl start attendance-backend
sudo systemctl start attendance-bot
```

### 8. Проверка статуса

```bash
sudo systemctl status attendance-backend
sudo systemctl status attendance-bot
docker ps | grep redis
```

### 9. Настройка Nginx (опционально)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔐 Безопасность

1. **Смените все пароли по умолчанию**
2. **Настройте firewall** (откройте только нужные порты)
3. **Используйте HTTPS** (Let's Encrypt)
4. **Регулярные бэкапы** базы данных
5. **Мониторинг логов** на ошибки

## 📊 Мониторинг

```bash
# Логи backend
sudo journalctl -u attendance-backend -f

# Логи bot
sudo journalctl -u attendance-bot -f

# Логи Redis
docker logs redis-attendance -f
```

## 🔄 Обновление

```bash
cd /opt/attendance_system
git pull  # если используете git
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart attendance-backend
sudo systemctl restart attendance-bot
```

## 🗄️ Бэкапы

```bash
# Бэкап базы данных
cp attendance.db backups/attendance_$(date +%Y%m%d_%H%M%S).db

# Автоматический бэкап (cron)
0 2 * * * cp /opt/attendance_system/attendance.db /backups/attendance_$(date +\%Y\%m\%d).db
```

## ✅ Чеклист перед запуском

- [ ] Все зависимости установлены
- [ ] Конфигурация настроена
- [ ] Redis запущен и доступен
- [ ] База данных инициализирована
- [ ] Systemd сервисы созданы и запущены
- [ ] Firewall настроен
- [ ] Бэкапы настроены
- [ ] Мониторинг настроен

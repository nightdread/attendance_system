# 🚀 Быстрый старт на продакшн сервере

## 1. Копирование на сервер

```bash
# С вашего компьютера
scp -r attendance_system/ user@prod-server:/opt/
```

## 2. На продакшн сервере

```bash
cd /opt/attendance_system
./deploy.sh
```

## 3. Настройка конфигурации

```bash
nano config/config.py
# Измените:
# - SECRET_KEY
# - BOT_TOKEN  
# - WEB_PASSWORD
# - REDIS_ENABLED = True
```

## 4. Создание systemd сервисов

См. файл `DEPLOY.md` раздел "Создание systemd сервисов"

## 5. Запуск

```bash
sudo systemctl start attendance-backend
sudo systemctl start attendance-bot
sudo systemctl status attendance-backend
sudo systemctl status attendance-bot
```

## 6. Проверка

```bash
curl http://localhost:8000/api/health
# Должен вернуть: {"status":"healthy",...}
```

## 📝 Важные файлы

- `DEPLOY.md` - полная инструкция по развертыванию
- `PRODUCTION_CHECKLIST.md` - чеклист перед запуском
- `config/config.py` - основная конфигурация
- `requirements.txt` - зависимости Python

## 🔧 Текущая конфигурация

- **Backend**: FastAPI на порту 8000
- **Bot**: Telegram бот @qr_uchet_bot
- **Redis**: Docker контейнер на порту 6379
- **База данных**: SQLite (attendance.db)
- **Кэширование**: Redis включен

## ⚠️ Важно перед продакшн

1. Смените все пароли по умолчанию
2. Настройте HTTPS
3. Настройте firewall
4. Настройте бэкапы
5. Проверьте все сервисы

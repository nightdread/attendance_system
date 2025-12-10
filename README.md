# Система учета прихода/ухода сотрудников

Система учета рабочего времени на базе Telegram-бота и QR-кодов.

**Текущая версия:** 1.0.0

## Возможности

- ✅ **JWT Аутентификация** - безопасная аутентификация пользователей
- ✅ **Redis Кэширование** - высокая производительность (опционально)
- ✅ **Унифицированная система** - общий учет для всех сотрудников
- ✅ **Одноразовые QR-коды** - каждый код используется только один раз
- ✅ **Автоматическая генерация** новых токенов после использования
- ✅ **Регистрация пользователей** через Telegram-бот
- ✅ **Отметка прихода/ухода** для всех сотрудников
- ✅ **Веб-терминал** для отображения QR-кодов
- ✅ **Интерактивная аналитика** - графики и отчеты в реальном времени
- ✅ **Структурированное логирование** с ротацией
- ✅ **API Документация** - Swagger/OpenAPI
- ✅ **Docker поддержка** - легкое развертывание

## Архитектура

- **Backend**: FastAPI + SQLite + Redis (опционально)
- **Bot**: Python Telegram Bot
- **Web Interface**: HTML/JS с Chart.js для графиков
- **Cache**: Redis или in-memory fallback
- **Database**: SQLite (файл `attendance.db`)
- **Authentication**: JWT tokens

## Установка и запуск (локально, без Docker)

1. Клонирование
   ```bash
   git clone <repository-url>
   cd attendance_system
   ```
2. Виртуальное окружение и зависимости
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Обязательные переменные окружения
   ```bash
   export SECRET_KEY="your-secret"
   export BOT_TOKEN="your-telegram-bot-token"
   export BOT_USERNAME="your_bot_username"
   export WEB_PASSWORD="strong-admin-password"
   # опционально: export API_KEY="your_api_key"    # для защиты API
   # опционально: export REDIS_ENABLED=true REDIS_HOST=localhost REDIS_PORT=6379
   ```
4. Запуск
   - Backend:
     ```bash
     source .venv/bin/activate
     python backend/main.py
     ```
   - Бот (в отдельном терминале):
     ```bash
     source .venv/bin/activate
     python bot/bot.py
     ```
   Приложение: `http://localhost:8000`

## Запуск через Docker (при необходимости)
- Установите переменные окружения (как выше), при использовании `docker-compose` добавьте их в `.env`.
- Команды:
  ```bash
  docker compose up -d
  # или собрать образ:
  docker compose build
  ```

## Использование

### 1. Настройка бота
- Создайте бота через [@BotFather](https://t.me/botfather)
- Получите токен и username бота
- Установите их в `config/config.py`

### 2. Доступ к веб-терминалу
- Откройте браузер: `http://localhost:8000/login`
- Введите логин/пароль из конфига
- Выберите локацию и сканируйте QR-код

### 3. Работа с ботом
- Пользователи сканируют QR-код на терминале
- При первом использовании вводят ФИО
- Выбирают "Пришёл" или "Ушёл"

### 4. Команды бота
- `/start` - начало работы
- `/my_last` - последние события пользователя
- `/who_here` - кто сейчас в офисе

### 5. Админ-панель
- `http://localhost:8000/admin` - просмотр присутствующих
- `http://localhost:8000/admin/user/{id}` - история пользователя

## API Endpoints

### Получение токена
```
GET /api/active_token
```
Возвращает активный токен (глобальный). Требуется `X-API-Key` если задан API_KEY, или сессионный доступ с терминала.

### Веб-интерфейсы
- `/login` — вход в систему
- `/terminal` — публичный терминал с QR-кодом (сессия помечается для вызова `/api/active_token`)
- `/admin` — админ-панель (требует логин)
- `/logout` — выход

### Дефолтные пользователи (создаются автоматически на пустой БД)
- admin (role=admin)
- manager (role=manager)
- hr (role=hr)

Пароли генерируются при первой инициализации пустой БД и выводятся в stdout (логи контейнера). Внутри контейнера не сохраняются.

## Структура базы данных

### Таблицы:
- `people` - пользователи (tg_user_id, fio, username)
- `events` - события (user_id, location, action, timestamp)
- `tokens` - токены (token, location, used, timestamps)

## Разработка

### Добавление новой локации
Добавьте локацию в `config/config.py` в список `LOCATIONS`.

### Кастомизация
- Шаблоны: `templates/`
- Стили: редактируйте HTML в шаблонах
- Логика: `backend/database.py`, `bot/bot.py`

## Безопасность

- Обязательные секреты из ENV: `SECRET_KEY`, `BOT_TOKEN`, `BOT_USERNAME`, `WEB_PASSWORD`; при необходимости `API_KEY`.
- `/api/analytics/*` и `/api/active_token` требуют API-ключ или авторизованную сессию.
- QR-коды одноразовые, токены истекают через 24 часа.
- Данные хранятся локально в SQLite (рассмотрите бэкапы/шифрование/перенос в внешний DB).

## TODO (будущие улучшения)

- [ ] ESP32 интеграция
- [ ] PostgreSQL поддержка
- [ ] Более детальная отчетность
- [ ] Экспорт данных в Excel
- [ ] Мобильное приложение
- [ ] Push-уведомления

## Лицензия

MIT License

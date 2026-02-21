# Система учёта рабочего времени

Система учёта прихода/ухода сотрудников на базе Telegram-бота и QR-кодов.

**Версия:** 1.3.0

---

## Возможности

### Учёт посещаемости
- Одноразовые QR-коды — каждый код используется единожды, новый генерируется автоматически
- Отметка прихода/ухода через Telegram-бот
- Поддержка удалённой работы (без сканирования QR)
- Веб-терминал для отображения QR-кода (режим 24/7)
- Защита от двойной отметки и race condition при одновременном сканировании

### Аналитика и отчёты
- Интерактивная аналитика с графиками (Chart.js)
- Интерактивный календарь с выделением праздников и выходных
- Сравнение двух произвольных периодов
- Анализ опозданий и переработок
- Распределение рабочего времени по дням недели
- Топ сотрудников по отработанным часам
- Статистика по отделам
- Экспорт в **Excel** (pivot-таблица) и **iCal**
- Отправка отчётов по **email**

### HR-функции
- Учёт отпусков и больничных
- Шаблоны отчётов
- Интеграция с производственным календарём (праздники, рабочие дни)
- Аудит-лог всех операций

### Telegram-бот
- Автоматические напоминания об открытой сессии (> 8 часов)
- Напоминание тем, кто не отметился к 11:00 (только в рабочие дни)
- Еженедельные сводки по прошлой неделе
- Напоминание о конце месяца
- Восстановление пароля веб-портала через бот

### Безопасность
- JWT-аутентификация с поддержкой zero-downtime ротации ключей
- CSRF-защита всех мутирующих операций
- Rate limiting для всех API-эндпоинтов (Redis или in-memory)
- Валидация и санитизация всех входных данных
- IP-whitelist для администраторов (опционально)
- Параметризованные SQL-запросы (защита от инъекций)
- Расширенное логирование безопасности (неудачные логины, смена ролей, подозрительная активность)

---

## Архитектура

```
Backend   FastAPI + SQLite + Redis (опционально)
Bot       python-telegram-bot + APScheduler
Frontend  HTML/JS, Chart.js, PWA
Proxy     Angie (nginx fork) — HTTPS, SSL/TLS
Auth      JWT + Session (Starlette SessionMiddleware)
Export    openpyxl (Excel), icalendar (iCal), SMTP (email)
```

---

## Структура проекта

```
attendance_system/
├── backend/            # FastAPI-приложение
│   ├── main.py         # Маршруты, middleware, handlers
│   └── schemas.py      # Pydantic-схемы для API
├── bot/
│   └── bot.py          # Telegram-бот
├── config/
│   └── config.py       # Конфигурация из переменных окружения
├── auth/
│   ├── jwt_handler.py  # JWT: создание, верификация, ротация
│   └── middleware.py   # Auth middleware
├── utils/
│   ├── cache.py        # Redis / in-memory кэш
│   ├── csrf.py         # CSRF-защита
│   ├── email_sender.py # Отправка email через SMTP
│   ├── logger.py       # Структурированное логирование
│   ├── metrics.py      # Метрики системы
│   ├── production_calendar.py  # Производственный календарь
│   ├── rate_limit.py   # Rate limiting
│   ├── time_formatter.py
│   └── validators.py   # Валидация входных данных
├── templates/          # Jinja2 HTML-шаблоны
├── static/             # Статика (PWA manifest, service worker)
├── tests/              # Тесты pytest
├── tools/              # Операционные скрипты (бэкапы, ротация, деплой)
├── docs/               # Документация и шаблоны конфигов
├── examples/           # Примеры для ESP32 / микроконтроллеров
├── ssl/                # SSL-сертификаты (не в git)
├── logs/               # Логи приложения и Angie (не в git)
├── database.py         # Слой работы с БД (SQLite)
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
└── requirements.txt
```

---

## Быстрый старт

### Требования
- Docker и Docker Compose
- Telegram-бот (создать через [@BotFather](https://t.me/botfather))
- Домен с SSL-сертификатами (для production)

### Запуск

```bash
git clone <repository-url>
cd attendance_system

# Скопировать и заполнить переменные окружения
cp .env.example .env

# Сгенерировать секретные ключи (заполнит .env автоматически)
./tools/generate-keys.sh

# Запустить все сервисы
docker compose up -d
```

Приложение доступно по `https://your-domain.com` после настройки SSL.

---

## Настройка

### Переменные окружения

**Обязательные:**

| Переменная | Описание |
|---|---|
| `SECRET_KEY` | Секретный ключ для шифрования сессий |
| `BOT_TOKEN` | Токен бота от @BotFather |
| `BOT_USERNAME` | Username бота (без @) |
| `WEB_PASSWORD` | Пароль первичного деплоя (используется только для проверки при старте) |
| `DOMAIN` | Домен для HTTPS (например, `example.com`) |

**Опциональные:**

| Переменная | По умолчанию | Описание |
|---|---|---|
| `TIMEZONE` | `Europe/Moscow` | Часовой пояс для отображения времени |
| `JWT_SECRET_KEY` | `SECRET_KEY` | Ключ подписи JWT (можно ротировать отдельно) |
| `JWT_SECRET_KEY_PREV` | — | Предыдущий JWT-ключ (zero-downtime ротация) |
| `SESSION_SECRET_KEY` | `SECRET_KEY` | Ключ для сессионных cookie |
| `API_KEY` | — | API-ключ для внешнего доступа и микроконтроллеров |
| `REDIS_ENABLED` | `true` | Включить Redis-кэш |
| `REDIS_HOST` | `localhost` | Redis хост |
| `REDIS_PASSWORD` | — | Redis пароль |
| `ADMIN_IP_WHITELIST` | — | Разрешённые IP для администраторов (через запятую) |
| `SMTP_HOST` | — | SMTP-сервер для отправки отчётов по email |
| `SMTP_PORT` | `587` | SMTP-порт |
| `SMTP_USER` | — | SMTP логин |
| `SMTP_PASSWORD` | — | SMTP пароль / app password |
| `SMTP_FROM_EMAIL` | — | Email отправителя |
| `PRODUCTION_CALENDAR_API_URL` | `https://isdayoff.ru` | API производственного календаря |
| `PRODUCTION_CALENDAR_FILE` | — | Путь к локальному JSON-файлу календаря |
| `DB_PATH` | `/app/attendance.db` | Путь к файлу SQLite |

### SSL-сертификаты

Поместите сертификаты Let's Encrypt в директорию `ssl/`:
```
ssl/fullchain.pem   — цепочка сертификатов
ssl/privkey.pem     — приватный ключ
```

Для генерации конфига Angie из шаблона:
```bash
./tools/generate-angie-conf.sh   # требует DOMAIN в .env
```

### Часовой пояс

Все события хранятся в UTC. `TIMEZONE` влияет только на отображение в интерфейсе и отчётах.

```bash
TIMEZONE=Europe/Moscow   # или UTC, Asia/Yekaterinburg и т.д.
```

### Производственный календарь

Используется для выделения праздников в аналитике и пропуска bot-напоминаний в выходные.

**Вариант 1 — внешний API (по умолчанию):**
```bash
PRODUCTION_CALENDAR_API_URL=https://isdayoff.ru
```

**Вариант 2 — локальный JSON-файл:**
```bash
PRODUCTION_CALENDAR_FILE=/app/data/production_calendar.json
```

Формат файла:
```json
{
  "2025": {
    "holidays": ["2025-01-01", "2025-01-07", "2025-03-08"],
    "workdays": ["2025-04-26"],
    "short_days": ["2025-02-21", "2025-12-31"]
  }
}
```

Подробнее: `docs/PRODUCTION_CALENDAR.md`

---

## База данных

SQLite, файл `attendance.db`. Схема:

| Таблица | Описание |
|---|---|
| `people` | Telegram-пользователи (tg_user_id, fio, username) |
| `events` | События прихода/ухода (user_id, location, action, ts) |
| `tokens` | QR-токены (token, used, expires_at) |
| `web_users` | Пользователи веб-портала (username, password_hash, role, department, position) |
| `roles` | Описание ролей и разрешений |
| `user_permissions` | Кастомные разрешения для конкретных пользователей |
| `audit_log` | Аудит всех операций |
| `vacations` | Записи об отпусках |
| `sick_leaves` | Записи о больничных |
| `report_templates` | Сохранённые шаблоны отчётов |

Все таблицы содержат индексы для ускорения аналитических запросов.

### Хранение БД вне контейнера

```yaml
# docker-compose.yml
services:
  attendance_app:
    environment:
      - DB_PATH=/data/attendance.db
    volumes:
      - ./data:/data
  attendance_bot:
    environment:
      - DB_PATH=/data/attendance.db
    volumes:
      - ./data:/data
```

---

## Роли пользователей

| Роль | Доступ |
|---|---|
| `admin` | Полный доступ |
| `manager` | Аналитика, управление пользователями |
| `hr` | Аналитика, управление сотрудниками и отпусками |
| `user` | Личный кабинет (`/me`) |
| `terminal` | Только страница терминала с QR-кодом |

**Пользователи по умолчанию** создаются автоматически при первом запуске на пустой БД. Сгенерированные пароли выводятся однократно в логах контейнера и на первой загрузке `/admin`. Сохраните их сразу.

---

## Веб-интерфейс

| URL | Описание |
|---|---|
| `/login` | Вход в систему |
| `/terminal` | Терминал с QR-кодом (роль `terminal`) |
| `/admin` | Список присутствующих (роль `admin/manager/hr`) |
| `/analytics` | Аналитика и экспорт (роль `admin/manager/hr`) |
| `/users` | Управление пользователями (роль `admin/manager`) |
| `/me` | Личный кабинет сотрудника |
| `/logout` | Выход |

---

## API

Полная документация: `https://your-domain.com/docs` (Swagger UI)

### Аутентификация

- **API Key** — заголовок `X-API-Key` (если настроен `API_KEY`)
- **JWT/Session** — сессионный cookie или заголовок `Authorization: Bearer <token>`

### Основные эндпоинты

**Токены:**
- `GET /api/active_token` — активный QR-токен _(auth, 120/мин)_
- `GET /api/token` — токен для микроконтроллеров _(опц. API key)_

**Пользователи:**
- `GET /api/user/{id}` _(admin/manager, 20/мин)_
- `PUT /api/user/{id}` _(admin/manager, CSRF, 10/мин)_
- `GET /api/employee/{id}` — детальная статистика сотрудника
- `GET /api/employees/date/{date}` — список за дату

**Аналитика:**
- `GET /api/analytics/daily/{date}`
- `GET /api/analytics/weekly`
- `GET /api/analytics/hourly/{date}`
- `GET /api/analytics/calendar/{year}/{month}`
- `GET /api/analytics/compare`
- `GET /api/analytics/late-arrivals`
- `GET /api/analytics/overtime`
- `GET /api/analytics/weekly-distribution`

**HR:**
- `GET/POST /api/vacations` _(POST требует CSRF)_
- `GET/POST /api/sick-leaves` _(POST требует CSRF)_
- `GET/POST /api/report-templates` _(POST требует CSRF)_
- `DELETE /api/report-templates/{id}` _(требует CSRF)_

**Экспорт:**
- `GET /api/export/pivot` — Excel pivot-таблица
- `GET /api/export/ical` — iCal-файл
- `POST /api/export/send-email` — отправить на email

**Аудит:**
- `GET /api/audit-log` _(только admin)_

**Мониторинг:**
- `GET /api/health`
- `GET /api/metrics`

---

## Операционные инструменты

Все скрипты находятся в `tools/` и запускаются из корня проекта.

### Бэкапы

```bash
# Создать бэкап
python3 tools/backup_db.py --verify

# Восстановить
python3 tools/restore_db.py backups/attendance_backup_YYYYMMDD_HHMMSS.db.gz

# Настроить автоматический cron
./tools/setup_backup_cron.sh
```

Подробнее: `docs/BACKUP_README.md`

### Ротация JWT-ключей (zero-downtime)

```bash
# Проверить статус
python3 tools/rotate_jwt_keys.py --status

# Выполнить ротацию
python3 tools/rotate_jwt_keys.py

# Перезапустить контейнеры после ротации
docker compose restart attendance_app attendance_bot
```

Как работает: `JWT_SECRET_KEY` — текущий ключ для новых токенов, `JWT_SECRET_KEY_PREV` — предыдущий ключ для верификации старых. Старые токены продолжают работать до истечения срока (по умолчанию 30 минут).

Подробнее: `docs/JWT_ROTATION_GUIDE.md`

### Управление сессиями

```bash
# Показать активные сессии
./tools/reset_session.sh --list

# Закрыть сессию конкретного пользователя
./tools/reset_session.sh <telegram_user_id>

# Закрыть все активные сессии
./tools/reset_session.sh --all
```

### Сброс паролей

```bash
python3 tools/reset_passwords.py
```

### Инициализация пользователей

```bash
python3 tools/init_users.py
```

---

## Docker

```bash
# Запустить все сервисы
docker compose up -d

# Пересобрать и перезапустить (после обновления кода)
docker compose build --no-cache attendance_app attendance_bot
docker compose up -d attendance_app attendance_bot

# Просмотр логов
docker compose logs -f attendance_app
docker compose logs -f attendance_bot

# Статус и health checks
docker compose ps
```

**Сервисы:**
- `attendance_app` — FastAPI backend (порт 8000 внутри сети)
- `attendance_bot` — Telegram-бот
- `redis` — кэш
- `angie` — HTTPS reverse-proxy (порт 443)

---

## Тесты

```bash
# Установить зависимости для тестов
pip install -r requirements.txt

# Запустить все тесты
pytest tests/

# С покрытием
pytest tests/ --cov=. --cov-report=html
```

---

## Мониторинг

```bash
# Health check
curl https://your-domain.com/api/health

# Метрики производительности
curl -H "Authorization: Bearer <token>" https://your-domain.com/api/metrics
```

Health check проверяет: БД, Redis, системные ресурсы (CPU/RAM/диск).

---

## Безопасность

- HTTPS обязателен в production (Angie + Let's Encrypt)
- Все мутирующие API требуют CSRF-токен (`X-CSRF-Token` заголовок или поле формы)
- Rate limiting по IP: `/login` — 5 попыток/5 мин, блокировка на 15 мин
- QR-токены одноразовые, истекают через 24 часа
- Пароли хешируются через argon2 (bcrypt как fallback)
- Сессии Terminal-роли — 1 год (для работы 24/7 без перелогина)

**Рекомендации:**
- Ротировать JWT и Session ключи каждые 90 дней
- Настроить `ADMIN_IP_WHITELIST` в production
- Настроить автоматические бэкапы БД (`tools/setup_backup_cron.sh`)
- Мониторить `logs/errors.log` на подозрительную активность

---

## Микроконтроллеры (ESP32)

Для отображения QR-кода на физическом дисплее используйте эндпоинт `/api/token`:

```bash
GET /api/token
Headers: X-API-Key: <your_api_key>   # если API_KEY настроен
```

Примеры скетчей для ESP32 с разными дисплеями: `examples/`

Подробнее: `docs/MICROCONTROLLER_INTEGRATION.md`

---

## Лицензия

MIT License

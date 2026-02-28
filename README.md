# Система учёта рабочего времени

Учёт прихода/ухода сотрудников: QR-коды, Telegram-бот, веб-терминал, аналитика, отчёты в Excel и iCal, отпуска и больничные, производственный календарь.

---

## Быстрый старт

**Нужно:** Docker и Docker Compose, бот от [@BotFather](https://t.me/botfather).

### Вариант 1 — из репозитория

```bash
git clone <repository-url>
cd attendance_system
cp .env.example .env
# Заполнить в .env: SECRET_KEY, BOT_TOKEN, BOT_USERNAME, WEB_PASSWORD
./tools/generate-keys.sh   # сгенерирует ключи в .env
docker compose up -d
```

### Вариант 2 — только образ с Docker Hub

Образы публикуются при релизах (теги `v*`). Теги: `v1.4.0`, `1.4.0`, `1.4`, `latest`.

```bash
mkdir attendance_deploy && cd attendance_deploy
curl -sLO https://raw.githubusercontent.com/<owner>/<repo>/v1.4.0/docker-compose.yml
# В docker-compose заменить build: . на image: docker.io/<DOCKERHUB_USERNAME>/attendance_system:v1.4.0
# для сервисов attendance_app и attendance_bot
export SECRET_KEY=...
export BOT_TOKEN=...
export BOT_USERNAME=...
export WEB_PASSWORD=...
docker compose up -d
```

---

## Переменные окружения

**Обязательные:** `SECRET_KEY`, `BOT_TOKEN`, `BOT_USERNAME`, `WEB_PASSWORD`.

**Часто нужные:** `TIMEZONE` (по умолчанию `Europe/Moscow`), `DB_PATH`, `REDIS_HOST` (при отдельном Redis). Для production: reverse proxy с HTTPS (например Angie), при необходимости `ADMIN_IP_WHITELIST`, `SMTP_*` для отправки отчётов по email. Полный список — в `.env.example` и в документации в `docs/`.

---

## Сервисы и доступ

- **Сервисы Docker:** `attendance_app` (веб, порт 8000), `attendance_bot`, `redis`.
- **Роли:** admin (полный доступ), manager/hr (аналитика, пользователи), user (личный кабинет), terminal (страница с QR).
- **Страницы:** `/login`, `/terminal` (QR), `/admin` (кто на работе), `/analytics`, `/users`, `/me` (личный кабинет). API и Swagger: `https://ваш-домен/docs`.
- При первом запуске на пустой БД создаются пользователи по умолчанию; пароли один раз показываются в логах и на `/admin` — сохраните их.

---

## Бэкапы и операции

- Бэкап БД: `python3 tools/backup_db.py --verify`. Восстановление: `python3 tools/restore_db.py backups/...`. Автобэкапы: `./tools/setup_backup_cron.sh`.
- Остальные скрипты (сброс паролей, сессии, JWT-ротация): в каталоге `tools/`, подробности в `docs/`.

---

## Полезные команды

```bash
docker compose up -d
docker compose build && docker compose up -d   # после обновления
docker compose logs -f attendance_app
docker compose ps
```

---

## Лицензия

MIT License

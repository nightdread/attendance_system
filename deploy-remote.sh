#!/bin/bash
# Скрипт для развертывания на удаленной машине

# Настройки
DOCKER_HUB_USER="ВАШ_DOCKERHUB_USERNAME"
IMAGE_NAME="${DOCKER_HUB_USER}/attendance_system:latest"

# Создать .env файл с переменными окружения
cat > .env << ENV_EOF
SECRET_KEY=your-super-secret-key-change-this
BOT_TOKEN=your-telegram-bot-token
BOT_USERNAME=your_bot_username  
WEB_PASSWORD=your-admin-password
API_KEY=optional-api-key
DB_PATH=/app/data/attendance.db
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
ENV_EOF

echo "Создан .env файл. Отредактируйте его с правильными значениями!"

# Docker Compose для удаленного развертывания
cat > docker-compose.remote.yml << COMPOSE_EOF
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes
    networks:
      - attendance_network

  attendance_app:
    image: ${IMAGE_NAME}
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - redis
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/api/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    networks:
      - attendance_network

  attendance_bot:
    image: ${IMAGE_NAME}
    env_file:
      - .env
    depends_on:
      - attendance_app
    command: ["python", "bot/bot.py"]
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://attendance_app:8000/api/health || exit 1"]
      interval: 45s
      timeout: 10s
      retries: 3
      start_period: 20s
    networks:
      - attendance_network

volumes:
  redis_data:

networks:
  attendance_network:
    driver: bridge
COMPOSE_EOF

echo "Создан docker-compose.remote.yml"
echo ""
echo "Запуск:"
echo "1. Отредактируйте .env файл"
echo "2. docker compose -f docker-compose.remote.yml up -d"
echo "3. Проверьте: curl http://localhost:8000/api/health"

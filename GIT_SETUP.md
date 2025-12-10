# 📦 Настройка Git репозитория

## ✅ Репозиторий уже создан!

Первый коммит выполнен:
```
163d03f Initial commit: Attendance System with Redis caching, analytics, and employee statistics
```

## 🚀 Отправка в GitHub/GitLab

### Вариант 1: GitHub

1. **Создайте новый репозиторий на GitHub:**
   - Перейдите на https://github.com/new
   - Название: `attendance-system` (или любое другое)
   - НЕ создавайте README, .gitignore или лицензию (они уже есть)

2. **Добавьте remote и отправьте:**
   ```bash
   cd /home/nightdread/attendance_system
   
   # Переименуйте ветку в main (современный стандарт)
   git branch -M main
   
   # Добавьте remote (замените username на ваш)
   git remote add origin https://github.com/username/attendance-system.git
   
   # Или используйте SSH (если настроен):
   # git remote add origin git@github.com:username/attendance-system.git
   
   # Отправьте код
   git push -u origin main
   ```

### Вариант 2: GitLab

```bash
git branch -M main
git remote add origin https://gitlab.com/username/attendance-system.git
git push -u origin main
```

### Вариант 3: Bitbucket

```bash
git branch -M main
git remote add origin https://bitbucket.org/username/attendance-system.git
git push -u origin main
```

## 🔧 Полезные команды

### Проверка статуса
```bash
git status
```

### Просмотр истории
```bash
git log --oneline
```

### Просмотр remote репозиториев
```bash
git remote -v
```

### Отправка изменений
```bash
git add .
git commit -m "Описание изменений"
git push
```

### Получение изменений
```bash
git pull
```

## ⚠️ Важно

- **НЕ коммитьте** файлы с секретами:
  - `attendance.db` (база данных)
  - `config/config.py` (может содержать токены)
  - `.env` файлы
  - `cookies.txt`

- Все эти файлы уже в `.gitignore`

## 📝 Настройка Git (глобально, опционально)

```bash
git config --global user.name "Ваше Имя"
git config --global user.email "your.email@example.com"
```

## 🔐 Если используете SSH

1. Сгенерируйте SSH ключ (если еще нет):
   ```bash
   ssh-keygen -t ed25519 -C "your.email@example.com"
   ```

2. Добавьте публичный ключ на GitHub/GitLab:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```
   Скопируйте вывод и добавьте в настройки SSH ключей на платформе.

3. Используйте SSH URL для remote:
   ```bash
   git remote set-url origin git@github.com:username/attendance-system.git
   ```

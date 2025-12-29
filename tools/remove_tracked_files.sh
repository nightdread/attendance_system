#!/bin/bash
# Простой скрипт для удаления отслеживаемых файлов из git
# Используйте: ./tools/remove_tracked_files.sh

set -e

echo "🧹 Удаление отслеживаемых файлов из git"
echo "========================================"
echo ""

# Удалить .md файлы (кроме README.md)
echo "📝 Удаление .md файлов (кроме README.md)..."
git rm --cached ANGIE_SETUP.md DEPLOY.md IMPROVEMENTS.md MICROCONTROLLER_INTEGRATION.md PRODUCTION_CHECKLIST.md REMINDERS.md BACKUP_README.md JWT_ROTATION_GUIDE.md CLEANUP_REPORT.md GIT_CLEANUP_GUIDE.md 2>/dev/null || true
echo "✅ .md файлы удалены из git"

# Проверить другие файлы
echo ""
echo "📋 Проверка других игнорируемых файлов..."

# Логи
if git ls-files | grep -q '\.log$'; then
    echo "   Найдены .log файлы, удаление..."
    git rm --cached $(git ls-files | grep '\.log$') 2>/dev/null || true
fi

# Базы данных
if git ls-files | grep -q '\.db$'; then
    echo "   Найдены .db файлы, удаление..."
    git rm --cached $(git ls-files | grep '\.db$') 2>/dev/null || true
fi

# .env файлы
if git ls-files | grep -q '^\.env$'; then
    echo "   Найден .env файл, удаление..."
    git rm --cached .env 2>/dev/null || true
fi

# angie.conf
if git ls-files | grep -q '^angie\.conf$'; then
    echo "   Найден angie.conf, удаление..."
    git rm --cached angie.conf 2>/dev/null || true
fi

echo ""
echo "✅ Готово!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Проверьте: git status"
echo "2. Закоммитьте: git commit -m 'Remove ignored files from git'"
echo "3. Отправьте: git push"


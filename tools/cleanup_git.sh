#!/bin/bash
# Скрипт для удаления игнорируемых файлов из git репозитория
# ВНИМАНИЕ: Это удалит файлы из git истории (но не с диска)

set -e

echo "🧹 Очистка git репозитория от игнорируемых файлов"
echo "=================================================="
echo ""
echo "⚠️  ВНИМАНИЕ: Этот скрипт удалит файлы из git индекса!"
echo "   Файлы останутся на диске, но перестанут отслеживаться git"
echo ""

# Подтверждение
read -p "Продолжить? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Отменено."
    exit 0
fi

echo ""
echo "📋 Удаление .md файлов (кроме README.md)..."
git rm --cached -r --ignore-unmatch *.md 2>/dev/null || true
git rm --cached -r --ignore-unmatch **/*.md 2>/dev/null || true
# Восстанавливаем README.md если случайно удалили
git add -f README.md 2>/dev/null || true
echo "✅ .md файлы удалены из git"

echo ""
echo "📋 Удаление логов..."
git rm --cached -r --ignore-unmatch logs/ 2>/dev/null || true
git rm --cached -r --ignore-unmatch backend/logs/ 2>/dev/null || true
git rm --cached -r --ignore-unmatch bot/logs/ 2>/dev/null || true
git rm --cached --ignore-unmatch *.log 2>/dev/null || true
git rm --cached --ignore-unmatch **/*.log 2>/dev/null || true
echo "✅ Логи удалены из git"

echo ""
echo "📋 Удаление баз данных..."
git rm --cached --ignore-unmatch *.db 2>/dev/null || true
git rm --cached --ignore-unmatch *.sqlite 2>/dev/null || true
git rm --cached --ignore-unmatch *.sqlite3 2>/dev/null || true
echo "✅ Базы данных удалены из git"

echo ""
echo "📋 Удаление кэша Python..."
git rm --cached -r --ignore-unmatch __pycache__/ 2>/dev/null || true
git rm --cached -r --ignore-unmatch **/__pycache__/ 2>/dev/null || true
git rm --cached --ignore-unmatch *.pyc 2>/dev/null || true
git rm --cached --ignore-unmatch *.pyo 2>/dev/null || true
echo "✅ Кэш Python удален из git"

echo ""
echo "📋 Удаление .env файлов..."
git rm --cached --ignore-unmatch .env 2>/dev/null || true
git rm --cached --ignore-unmatch .env.local 2>/dev/null || true
git rm --cached --ignore-unmatch .env.*.local 2>/dev/null || true
echo "✅ .env файлы удалены из git"

echo ""
echo "📋 Удаление сгенерированных файлов..."
git rm --cached --ignore-unmatch angie.conf 2>/dev/null || true
echo "✅ Сгенерированные файлы удалены из git"

echo ""
echo "✅ Очистка завершена!"
echo ""
echo "📝 Следующие шаги:"
echo "1. Проверьте изменения: git status"
echo "2. Закоммитьте изменения: git commit -m 'Remove ignored files from git'"
echo "3. Отправьте на GitHub: git push"
echo ""
echo "⚠️  ВАЖНО: Если файлы уже были в истории git, они останутся там."
echo "   Для полного удаления из истории используйте git filter-branch или BFG Repo-Cleaner"


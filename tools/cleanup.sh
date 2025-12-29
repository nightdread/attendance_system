#!/bin/bash
# Скрипт для очистки проекта от временных и ненужных файлов

set -e

echo "🧹 Очистка проекта от временных файлов"
echo "======================================"

# Удаление кэша Python
echo "📦 Удаление кэша Python..."
find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name "*.pyd" -delete 2>/dev/null || true
find . -name ".Python" -delete 2>/dev/null || true
echo "✅ Кэш Python удален"

# Удаление временных файлов IDE
echo "🔧 Удаление временных файлов IDE..."
find . -name "*.swp" -delete 2>/dev/null || true
find . -name "*.swo" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true
echo "✅ Временные файлы IDE удалены"

# Удаление файлов сборки
echo "📦 Удаление файлов сборки..."
find . -type d -name "build" -exec rm -r {} + 2>/dev/null || true
find . -type d -name "dist" -exec rm -r {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
find . -name "*.egg" -delete 2>/dev/null || true
echo "✅ Файлы сборки удалены"

# Удаление кэша pytest
echo "🧪 Удаление кэша тестов..."
find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
find . -type d -name ".coverage" -exec rm -r {} + 2>/dev/null || true
find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
find . -name ".coverage.*" -delete 2>/dev/null || true
echo "✅ Кэш тестов удален"

# Удаление кэша других инструментов
echo "🔧 Удаление другого кэша..."
find . -type d -name ".tox" -exec rm -r {} + 2>/dev/null || true
find . -type d -name ".cache" -exec rm -r {} + 2>/dev/null || true
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
echo "✅ Другой кэш удален"

echo ""
echo "✅ Очистка завершена!"
echo ""
echo "⚠️  Примечание: Логи и база данных не удаляются (они в .gitignore)"


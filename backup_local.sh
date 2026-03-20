#!/bin/bash
# Скрипт для создания архива локального проекта

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="Artgranit"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$SCRIPT_DIR/backups"
ARCHIVE_NAME="${PROJECT_NAME}_local_${TIMESTAMP}.tar.gz"

echo "=========================================="
echo "Архивация локального проекта"
echo "=========================================="
echo ""

# Создаем директорию для бэкапов
mkdir -p "$BACKUP_DIR"

# Исключаем ненужные файлы и директории
EXCLUDE_PATTERNS=(
    "--exclude=backups"
    "--exclude=.git"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=*.pyo"
    "--exclude=.pytest_cache"
    "--exclude=.env"
    "--exclude=*.log"
    "--exclude=node_modules"
    "--exclude=.DS_Store"
    "--exclude=wallet_*"
    "--exclude=Wallet_*.zip"
)

echo "Создание архива: $ARCHIVE_NAME"
echo ""

cd "$SCRIPT_DIR/.."
# Исключаем директорию backups из архива
tar -czf "$BACKUP_DIR/$ARCHIVE_NAME" \
    --exclude="$PROJECT_NAME/backups" \
    ${EXCLUDE_PATTERNS[@]} \
    "$PROJECT_NAME/"

if [ $? -eq 0 ]; then
    ARCHIVE_SIZE=$(du -h "$BACKUP_DIR/$ARCHIVE_NAME" | cut -f1)
    echo "✓ Архив создан успешно!"
    echo "  Путь: $BACKUP_DIR/$ARCHIVE_NAME"
    echo "  Размер: $ARCHIVE_SIZE"
    echo ""
    echo "Архив сохранен в: $BACKUP_DIR"
else
    echo "✗ Ошибка при создании архива!"
    exit 1
fi

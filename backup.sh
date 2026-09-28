#!/bin/bash

# Скрипт полного архивирования/бэкапа проекта Oracle SQL Developer Web

PROJECT_NAME="oracle_test_app"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="${PROJECT_NAME}_backup_${TIMESTAMP}.tar.gz"

echo "=== Создание бэкапа проекта ==="
echo "Проект: $PROJECT_NAME"
echo "Время: $(date)"

# Создаем папку для бэкапов, если её нет
mkdir -p "$BACKUP_DIR"

# Создаем временную папку для архивации
TEMP_DIR=$(mktemp -d)
echo "Временная папка: $TEMP_DIR"

# Копируем файлы проекта (исключая ненужное)
echo "Копирование файлов..."

# Основные файлы
cp app.py "$TEMP_DIR/" 2>/dev/null
cp config.py "$TEMP_DIR/" 2>/dev/null
cp requirements.txt "$TEMP_DIR/" 2>/dev/null
cp README.md "$TEMP_DIR/" 2>/dev/null
cp backup.sh "$TEMP_DIR/" 2>/dev/null || true
cp install.py "$TEMP_DIR/" 2>/dev/null || true
cp full_restart.sh "$TEMP_DIR/" 2>/dev/null
cp full_restart2.sh "$TEMP_DIR/" 2>/dev/null || true

# Папки (исключая __pycache__ и .pyc файлы)
rsync -av --exclude='__pycache__' --exclude='*.pyc' controllers "$TEMP_DIR/" 2>/dev/null || \
    (mkdir -p "$TEMP_DIR/controllers" && find controllers -type f ! -path "*/__pycache__/*" ! -name "*.pyc" -exec cp --parents {} "$TEMP_DIR/" \; 2>/dev/null)

rsync -av --exclude='__pycache__' --exclude='*.pyc' models "$TEMP_DIR/" 2>/dev/null || \
    (mkdir -p "$TEMP_DIR/models" && find models -type f ! -path "*/__pycache__/*" ! -name "*.pyc" -exec cp --parents {} "$TEMP_DIR/" \; 2>/dev/null)

cp -r templates "$TEMP_DIR/" 2>/dev/null

# Wallet ZIP (если есть)
if [ -f "Wallet_HXPAVUNKCLU9HE7Q.zip" ]; then
    cp Wallet_HXPAVUNKCLU9HE7Q.zip "$TEMP_DIR/" 2>/dev/null
fi

# Создаем архив
echo "Создание архива..."
cd "$TEMP_DIR"
tar -czf "$OLDPWD/$BACKUP_DIR/$ARCHIVE_NAME" .

# Очистка
cd "$OLDPWD"
rm -rf "$TEMP_DIR"

# Проверка результата
if [ -f "$BACKUP_DIR/$ARCHIVE_NAME" ]; then
    SIZE=$(du -h "$BACKUP_DIR/$ARCHIVE_NAME" | cut -f1)
    echo "✅ Бэкап успешно создан!"
    echo "Файл: $BACKUP_DIR/$ARCHIVE_NAME"
    echo "Размер: $SIZE"
else
    echo "❌ Ошибка при создании бэкапа!"
    exit 1
fi

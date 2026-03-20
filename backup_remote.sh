#!/bin/bash
# Скрипт для создания архива проекта на удаленном сервере

set -e

# Загружаем настройки из .env
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "✗ Файл .env не найден!"
    exit 1
fi

# Читаем настройки удаленного сервера
REMOTE_HOST=$(grep "^REMOTE_SERVER_HOST=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
REMOTE_PORT=$(grep "^REMOTE_SSH_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "22")
REMOTE_USER=$(grep "^REMOTE_USER=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "ubuntu")
REMOTE_SSH_KEY=$(grep "^REMOTE_SSH_KEY=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "")
REMOTE_PATH=$(grep "^REMOTE_PATH=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'" || echo "/opt/artgranit")

if [ -z "$REMOTE_HOST" ]; then
    echo "✗ REMOTE_SERVER_HOST не указан в .env!"
    exit 1
fi

PROJECT_NAME="Artgranit"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_NAME="${PROJECT_NAME}_remote_${TIMESTAMP}.tar.gz"

echo "=========================================="
echo "Архивация проекта на удаленном сервере"
echo "=========================================="
echo "Сервер: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
echo "Путь: $REMOTE_PATH"
echo ""

# Формируем команду SSH с ключом если указан
SSH_CMD="ssh"
if [ -n "$REMOTE_SSH_KEY" ]; then
    SSH_CMD="ssh -i $REMOTE_SSH_KEY"
fi
if [ "$REMOTE_PORT" != "22" ]; then
    SSH_CMD="$SSH_CMD -p $REMOTE_PORT"
fi

# Проверяем подключение
echo "Проверка подключения к серверу..."
if ! $SSH_CMD "$REMOTE_USER@$REMOTE_HOST" "test -d $REMOTE_PATH" 2>/dev/null; then
    echo "⚠ Директория $REMOTE_PATH не существует на сервере"
    echo "  Создать директорию? (y/n)"
    read -r answer
    if [ "$answer" = "y" ]; then
        $SSH_CMD "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_PATH"
    else
        echo "✗ Отменено"
        exit 1
    fi
fi

# Создаем архив на удаленном сервере
echo "Создание архива на удаленном сервере..."
$SSH_CMD "$REMOTE_USER@$REMOTE_HOST" << EOF
    cd "$REMOTE_PATH/.."
    if [ -d "$REMOTE_PATH" ]; then
        tar -czf "$REMOTE_PATH/../$ARCHIVE_NAME" \\
            --exclude="backups" \\
            --exclude=".git" \\
            --exclude="__pycache__" \\
            --exclude="*.pyc" \\
            --exclude="*.pyo" \\
            --exclude=".pytest_cache" \\
            --exclude="*.log" \\
            --exclude="node_modules" \\
            --exclude=".DS_Store" \\
            --exclude="wallet_*" \\
            --exclude="Wallet_*.zip" \\
            "$(basename $REMOTE_PATH)/"
        echo "✓ Архив создан: $REMOTE_PATH/../$ARCHIVE_NAME"
    else
        echo "✗ Директория $REMOTE_PATH не существует!"
        exit 1
    fi
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Архив на удаленном сервере создан успешно!"
    echo "  Путь: $REMOTE_PATH/../$ARCHIVE_NAME"
else
    echo "✗ Ошибка при создании архива на сервере!"
    exit 1
fi

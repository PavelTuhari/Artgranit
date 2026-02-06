#!/bin/bash
# Скрипт для копирования проекта с локального на удаленный сервер

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

echo "=========================================="
echo "Развертывание проекта на удаленный сервер"
echo "=========================================="
echo "Сервер: $REMOTE_USER@$REMOTE_HOST:$REMOTE_PORT"
echo "Путь: $REMOTE_PATH"
echo ""

# Формируем команды SSH/SCP с ключом если указан
SSH_CMD="ssh"
SCP_CMD="scp"
if [ -n "$REMOTE_SSH_KEY" ]; then
    SSH_CMD="ssh -i $REMOTE_SSH_KEY"
    SCP_CMD="scp -i $REMOTE_SSH_KEY"
fi
if [ "$REMOTE_PORT" != "22" ]; then
    SSH_CMD="$SSH_CMD -p $REMOTE_PORT"
    SCP_CMD="$SCP_CMD -P $REMOTE_PORT"
fi

# Шаг 1: Создание архива на удаленном сервере (если проект существует)
echo "Шаг 1: Создание резервной копии на удаленном сервере..."
if $SSH_CMD "$REMOTE_USER@$REMOTE_HOST" "test -d $REMOTE_PATH" 2>/dev/null; then
    echo "  Найден существующий проект, создаем резервную копию..."
    bash "$SCRIPT_DIR/backup_remote.sh"
    echo ""
else
    echo "  Проект на сервере не найден, пропускаем резервное копирование"
    echo ""
fi

# Шаг 2: Создание архива локального проекта
echo "Шаг 2: Создание архива локального проекта..."
bash "$SCRIPT_DIR/backup_local.sh"
echo ""

# Шаг 3: Создание временного архива для передачи
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_ARCHIVE="${PROJECT_NAME}_deploy_${TIMESTAMP}.tar.gz"

echo "Шаг 3: Подготовка архива для передачи..."
cd "$SCRIPT_DIR/.."

EXCLUDE_PATTERNS=(
    "--exclude=$PROJECT_NAME/backups"
    "--exclude=$PROJECT_NAME/${PROJECT_NAME}_deploy_*.tar.gz"
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
    "--exclude=$PROJECT_NAME/venv"
)

tar -czf "$SCRIPT_DIR/$TEMP_ARCHIVE" \
    ${EXCLUDE_PATTERNS[@]} \
    "$PROJECT_NAME/"

ARCHIVE_SIZE=$(du -h "$SCRIPT_DIR/$TEMP_ARCHIVE" | cut -f1)
echo "  ✓ Архив создан: $TEMP_ARCHIVE ($ARCHIVE_SIZE)"
echo ""

# Шаг 4: Копирование на удаленный сервер
echo "Шаг 4: Копирование на удаленный сервер..."
echo "  Это может занять некоторое время..."

# Копируем архив во временную директорию на сервере
TEMP_REMOTE_PATH="/tmp/$TEMP_ARCHIVE"
$SCP_CMD "$SCRIPT_DIR/$TEMP_ARCHIVE" "$REMOTE_USER@$REMOTE_HOST:$TEMP_REMOTE_PATH"

# Распаковываем на сервере
echo "Шаг 5: Распаковка на удаленном сервере..."
$SSH_CMD "$REMOTE_USER@$REMOTE_HOST" << EOF
    ENV_BAK="/tmp/.env.artgranit.\$(date +%s).bak"
    if [ -f "$REMOTE_PATH/.env" ]; then
        cp "$REMOTE_PATH/.env" "\$ENV_BAK" && echo "  Сохранён .env (wallet не трогаем)"
    fi
    
    mkdir -p "$(dirname $REMOTE_PATH)"
    
    if [ -d "$REMOTE_PATH" ]; then
        echo "  Удаление старой версии..."
        rm -rf "$REMOTE_PATH"
    fi
    
    echo "  Распаковка архива..."
    cd "$(dirname $REMOTE_PATH)"
    tar -xzf "$TEMP_REMOTE_PATH"
    
    if [ -d "$PROJECT_NAME" ] && [ "$PROJECT_NAME" != "\$(basename $REMOTE_PATH)" ]; then
        mv "$PROJECT_NAME" "$REMOTE_PATH"
    elif [ ! -d "$REMOTE_PATH" ]; then
        mkdir -p "$REMOTE_PATH"
        echo "  ⚠ Директория создана, но архив не распакован правильно"
    fi
    
    if [ -f "\$ENV_BAK" ]; then
        cp "\$ENV_BAK" "$REMOTE_PATH/.env" && echo "  ✓ Восстановлен .env (wallet не тронут)"
        rm -f "\$ENV_BAK"
    fi
    
    rm -f "$TEMP_REMOTE_PATH"
    
    if [ -d "$REMOTE_PATH" ]; then
        chmod -R 755 "$REMOTE_PATH"
        echo "  ✓ Проект развернут в $REMOTE_PATH"
    else
        echo "  ✗ Ошибка: директория $REMOTE_PATH не создана"
        exit 1
    fi
EOF

rm -f "$SCRIPT_DIR/$TEMP_ARCHIVE"

# Шаг 6: развёртывание Oracle (таблицы, пакеты, включая CRED_REPORTS_PKG)
echo "Шаг 6: Развёртывание Oracle-объектов..."
$SSH_CMD "$REMOTE_USER@$REMOTE_HOST" "bash -s" << REMOTEEOF
  cd $REMOTE_PATH
  if venv/bin/python3 deploy_oracle_objects.py 2>/dev/null; then
    echo '  ✓ Oracle-объекты развёрнуты (CRED_REPORTS_PKG и др.)'
  else
    echo '  ⚠ deploy_oracle_objects.py не выполнен — проверьте .env и доступ к БД'
  fi
REMOTEEOF

# Шаг 7: установка зависимостей и перезапуск приложения (wallet не трогаем)
echo "Шаг 7: Установка зависимостей и перезапуск приложения..."
$SSH_CMD "$REMOTE_USER@$REMOTE_HOST" "bash -s" << REMOTEEOF
  set -e
  cd $REMOTE_PATH
  [ -d venv ] || python3 -m venv venv
  venv/bin/python3 -m pip install -q -r requirements.txt
  pkill -f 'python.*app\\.py' 2>/dev/null || true
  sleep 2
  nohup venv/bin/python3 app.py >> app.log 2>&1 &
  sleep 3
  pgrep -af app.py >/dev/null && echo '  ✓ Зависимости установлены, приложение перезапущено' || echo '  ⚠ Приложение могло не запуститься — проверьте app.log'
REMOTEEOF

echo ""
echo "=========================================="
echo "✓ Развертывание завершено успешно!"
echo "=========================================="
echo ""
echo "Проект: $REMOTE_PATH | .env и wallet не тронуты."
echo ""

#!/bin/bash

# Скрипт для локального запуска на Mac
# Запускает приложение на localhost:3003

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || { echo "❌ ОШИБКА: Не удалось перейти в директорию проекта!"; exit 1; }

echo "=== 🚀 Запуск Oracle SQL Developer Web на Mac ==="
echo "📍 Директория проекта: $PROJECT_DIR"
echo ""

# Проверяем виртуальное окружение
if [ ! -f "venv/bin/activate" ]; then
    echo "❌ ОШИБКА: Виртуальное окружение (venv) не найдено!"
    echo "📦 Создаю виртуальное окружение..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ ОШИБКА: Не удалось создать виртуальное окружение!"
        exit 1
    fi
fi

# Активируем виртуальное окружение
echo "🔌 Активирую виртуальное окружение..."
source venv/bin/activate

# Проверяем установлены ли зависимости (используем python из venv)
if [ ! -d "venv/lib/python3.12/site-packages/flask" ] || ! python -c "import dotenv" 2>/dev/null; then
    echo "📦 Устанавливаю зависимости..."
    pip install --upgrade pip
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ ОШИБКА: Не удалось установить зависимости!"
        exit 1
    fi
    echo "✅ Зависимости установлены"
fi

# Устанавливаем переменные окружения для локального режима
export ENVIRONMENT=LOCAL
export PORT=3003
export SERVER_HOST=0.0.0.0  # Разрешаем доступ по локальному IP

# Получаем локальный IP адрес
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

echo "✅ Окружение настроено"
echo ""
echo "🌐 Доступ к приложению:"
echo "   • Localhost: http://localhost:3003"
if [ -n "$LOCAL_IP" ]; then
    echo "   • Локальная сеть: http://${LOCAL_IP}:3003"
fi
echo ""
echo "📊 Dashboard:"
echo "   • http://localhost:3003/UNA.md/orasldev/dashboard"
if [ -n "$LOCAL_IP" ]; then
    echo "   • http://${LOCAL_IP}:3003/UNA.md/orasldev/dashboard"
    echo "   • Fullscreen: http://${LOCAL_IP}:3003/UNA.md/orasldev/dashboard/01"
fi
echo ""
echo "=== Запуск сервера ==="
echo "Для остановки нажмите Ctrl+C"
echo ""

# Запускаем приложение (используем python из venv)
python app.py


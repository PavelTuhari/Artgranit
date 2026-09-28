#!/bin/bash

# Полная перезагрузка Flask приложения (Oracle Test App)
# Выполняет очистку портов, убивает старые процессы и запускает приложение начисто.

PROJECT_DIR="/home/ubuntu/oracle_test_app"

echo "=== [1/5] Остановка старых процессов... ==="
# Убиваем всё, что может держать порт 8000 или быть старым процессом Python
sudo killall -9 python3 2>/dev/null || true
sudo pkill -9 -f "python3" 2>/dev/null || true
sudo pkill -9 -f "http.server" 2>/dev/null || true

# Дополнительная зачистка по порту 8000 (если установлен lsof)
if command -v lsof >/dev/null 2>&1; then
    sudo lsof -i :8000 | grep python | awk '{print $2}' | xargs -r sudo kill -9 2>/dev/null || true
fi

echo "=== [2/5] Отключение старых systemd сервисов... ==="
systemctl --user disable --now web-server.service 2>/dev/null || true
systemctl --user stop web-server.service 2>/dev/null || true

echo "=== [3/5] Подготовка окружения... ==="
cd "$PROJECT_DIR" || { echo "❌ ОШИБКА: Папка $PROJECT_DIR не найдена!"; exit 1; }

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ ОШИБКА: Виртуальное окружение (venv) не найдено!"
    exit 1
fi

echo "=== [4/5] Запуск приложения... ==="
# Запуск в фоне с перенаправлением логов
nohup python3 app.py > app.log 2>&1 &

echo "=== [5/5] Проверка статуса... ==="
sleep 3

# Проверяем, жив ли процесс
if ps aux | grep "app.py" | grep -v grep > /dev/null; then
    PID=$(ps aux | grep "app.py" | grep -v grep | awk '{print $2}')
    echo "✅ УСПЕХ: Приложение запущено (PID: $PID)"
    echo "---------------------------------------------------"
    ps aux | grep "app.py" | grep -v grep
    echo "---------------------------------------------------"
    echo "Логи доступны в файле: app.log"
    echo "Проверка в браузере: http://92.5.3.187:8000/test.html"
else
    echo "❌ ОШИБКА: Приложение не запустилось. Последние строки лога:"
    echo "---------------------------------------------------"
    tail -n 10 app.log
    echo "---------------------------------------------------"
fi

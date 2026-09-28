#!/bin/bash
echo "Останавливаем старые процессы..."
sudo fuser -k 8000/tcp 2>/dev/null
pkill -f "python3 app.py"
pkill -f "http.server"
sleep 2

echo "Запускаем приложение..."
cd /home/ubuntu/oracle_test_app
source venv/bin/activate
nohup python3 app.py > app.log 2>&1 &

echo "Готово! Логи пишутся в app.log"
sleep 2
tail -n 5 app.log

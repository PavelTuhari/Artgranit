#!/bin/bash

# Скрипт для проверки сетевого доступа к приложению

echo "🔍 Диагностика сетевого доступа к приложению"
echo ""

# Получаем локальный IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

if [ -z "$LOCAL_IP" ]; then
    echo "❌ Не удалось определить локальный IP адрес"
    exit 1
fi

echo "📍 Локальный IP: $LOCAL_IP"
echo ""

# Проверяем статус файрвола
echo "🔒 Проверка файрвола:"
FIREWALL_STATUS=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -i "enabled\|disabled")
echo "   $FIREWALL_STATUS"
echo ""

# Проверяем, слушает ли что-то на порту 3003
echo "🔌 Проверка порта 3003:"
LISTENING=$(netstat -an | grep "3003" | grep "LISTEN")
if [ -n "$LISTENING" ]; then
    echo "   ✅ Порт 3003 используется:"
    echo "$LISTENING" | while read line; do
        echo "   $line"
    done
else
    echo "   ❌ Порт 3003 не используется (приложение не запущено?)"
fi
echo ""

# Проверяем доступность через localhost
echo "🌐 Тестирование доступности:"
echo -n "   • localhost:3003 - "
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://localhost:3003/api/status 2>/dev/null | grep -q "200\|401\|302"; then
    echo "✅ Доступен"
else
    echo "❌ Недоступен"
fi

# Проверяем доступность через локальный IP
echo -n "   • $LOCAL_IP:3003 - "
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 http://$LOCAL_IP:3003/api/status 2>/dev/null | grep -q "200\|401\|302"; then
    echo "✅ Доступен"
else
    echo "❌ Недоступен"
    echo ""
    echo "💡 Возможные причины:"
    echo "   1. Приложение не запущено или не слушает на 0.0.0.0"
    echo "   2. Файрвол блокирует подключения (хотя он отключен)"
    echo "   3. Проблемы с сетевым интерфейсом"
    echo ""
    echo "🔧 Решения:"
    echo "   1. Убедитесь, что приложение запущено: ./run_local.sh"
    echo "   2. Проверьте, что SERVER_HOST = '0.0.0.0' в config.py"
    echo "   3. Попробуйте подключиться с другого устройства в той же сети"
fi

echo ""
echo "📋 Проверка конфигурации:"
if grep -q "SERVER_HOST = os.environ.get('SERVER_HOST', '0.0.0.0')" config.py 2>/dev/null; then
    echo "   ✅ SERVER_HOST настроен на 0.0.0.0"
else
    echo "   ⚠️  SERVER_HOST может быть не настроен правильно"
    echo "   Проверьте config.py"
fi

echo ""
echo "🌐 Попробуйте открыть в браузере:"
echo "   http://$LOCAL_IP:3003/UNA.md/orasldev/dashboard"
echo ""


#!/bin/bash
# Скрипт для исправления прав доступа после проблем с worktree в Cursor 2.0

echo "🔧 Исправление прав доступа для Cursor..."

# Получаем текущего пользователя
USER=$(whoami)
GROUP=$(id -gn)

echo "Пользователь: $USER"
echo "Группа: $GROUP"
echo ""

# Проверяем, существует ли проблемная папка
if [ -d "/Users/cursorsprojects" ]; then
    echo "📁 Папка /Users/cursorsprojects существует, исправляем права..."
    sudo chown -R "$USER:$GROUP" /Users/cursorsprojects/OCI 2>/dev/null || echo "⚠️  Не удалось исправить права на /Users/cursorsprojects/OCI"
    sudo chown "$USER:$GROUP" /Users/cursorsprojects 2>/dev/null || echo "⚠️  Не удалось исправить права на /Users/cursorsprojects"
    sudo chmod 755 /Users/cursorsprojects 2>/dev/null || echo "⚠️  Не удалось изменить права на /Users/cursorsprojects"
else
    echo "📁 Папка /Users/cursorsprojects не существует"
    echo "🔗 Создаём символическую ссылку..."
    sudo mkdir -p /Users/cursorsprojects/OCI
    sudo ln -s /Users/$USER/cursorsprojects/OCI/Artgranit /Users/cursorsprojects/OCI/Artgranit
    sudo chown -R "$USER:$GROUP" /Users/cursorsprojects
    sudo chmod 755 /Users/cursorsprojects
    echo "✅ Символическая ссылка создана"
fi

# Исправляем права на основной репозиторий (на всякий случай)
echo ""
echo "📁 Исправляем права на основной репозиторий..."
REPO_PATH="/Users/$USER/cursorsprojects/OCI/Artgranit"
if [ -d "$REPO_PATH" ]; then
    sudo chown -R "$USER:$GROUP" "$REPO_PATH"
    echo "✅ Права на основной репозиторий исправлены"
else
    echo "⚠️  Основной репозиторий не найден: $REPO_PATH"
fi

echo ""
echo "✅ Готово! Теперь:"
echo "1. Полностью закройте Cursor (Cmd+Q)"
echo "2. Откройте проект заново: /Users/$USER/cursorsprojects/OCI/Artgranit"
echo "3. Проверьте, что Apply changes работает"

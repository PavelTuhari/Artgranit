#!/bin/bash
# Скрипт для очистки кэша Cursor после проблем с worktree

echo "🧹 Очистка кэша Cursor..."

# Очистка кэша Cursor на macOS
CACHE_DIR="$HOME/Library/Caches/com.cursorsh.Cursorr"

if [ -d "$CACHE_DIR" ]; then
    echo "📁 Найден кэш Cursor: $CACHE_DIR"
    echo "🗑️  Удаление кэша..."
    rm -rf "$CACHE_DIR"
    echo "✅ Кэш Cursor очищен"
else
    echo "ℹ️  Кэш Cursor не найден (возможно, уже очищен)"
fi

# Также очищаем остатки worktree
echo ""
echo "🧹 Очистка остатков worktree..."

if [ -d "$HOME/.cursor/worktrees" ]; then
    echo "📁 Найдены остатки worktree: $HOME/.cursor/worktrees"
    rm -rf "$HOME/.cursor/worktrees"
    echo "✅ Остатки worktree удалены"
else
    echo "✅ Остатки worktree не найдены"
fi

echo ""
echo "✅ Готово! Теперь:"
echo "1. Полностью закройте Cursor (Cmd+Q)"
echo "2. Запустите Cursor заново"
echo "3. Откройте проект: /Users/$(whoami)/cursorsprojects/OCI/Artgranit"
echo "4. Дождитесь завершения индексации Git"
echo ""
echo "⚠️  После перезапуска отключите Parallel Models в настройках Composer!"

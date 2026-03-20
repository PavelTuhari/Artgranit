#!/bin/bash
# Полная очистка всех ссылок на worktree для Cursor 2.0

echo "🔧 Полная очистка worktree для Cursor 2.0"
echo ""

REPO_PATH="/Users/paveltuhari/cursorsprojects/OCI/Artgranit"
cd "$REPO_PATH" || exit 1

echo "=== 1. Проверка Git worktree ==="
git worktree list
echo ""

echo "=== 2. Очистка мёртвых ссылок Git ==="
git worktree prune -v
echo ""

echo "=== 3. Удаление остатков из ~/.cursor/worktrees ==="
if [ -d "$HOME/.cursor/worktrees" ]; then
    echo "🗑️  Удаление: $HOME/.cursor/worktrees"
    rm -rf "$HOME/.cursor/worktrees"
    echo "✅ Удалено"
else
    echo "✅ Папка не существует"
fi
echo ""

echo "=== 4. Удаление остатков из .git/worktrees ==="
if [ -d ".git/worktrees" ]; then
    echo "🗑️  Удаление: .git/worktrees"
    rm -rf .git/worktrees
    echo "✅ Удалено"
else
    echo "✅ Папка не существует"
fi
echo ""

echo "=== 5. Проверка .git/config на ссылки worktree ==="
if grep -q "worktree" .git/config 2>/dev/null; then
    echo "⚠️  Найдены упоминания worktree в .git/config"
    echo "Содержимое:"
    grep -A 3 -B 3 "worktree" .git/config
    echo ""
    echo "⚠️  ВНИМАНИЕ: Возможно, нужно вручную отредактировать .git/config"
else
    echo "✅ Нет упоминаний worktree в .git/config"
fi
echo ""

echo "=== 6. Очистка кэша Cursor ==="
CACHE_DIR="$HOME/Library/Caches/com.cursorsh.Cursorr"
if [ -d "$CACHE_DIR" ]; then
    echo "🗑️  Удаление кэша: $CACHE_DIR"
    rm -rf "$CACHE_DIR"
    echo "✅ Кэш очищен"
else
    echo "ℹ️  Кэш не найден"
fi
echo ""

echo "=== 7. Финальная проверка ==="
echo "Git worktree list:"
git worktree list
echo ""

echo "Остатки в ~/.cursor/worktrees:"
ls -la "$HOME/.cursor/worktrees" 2>&1 || echo "✅ Не найдено"
echo ""

echo "=== ✅ Очистка завершена! ==="
echo ""
echo "📋 Следующие шаги:"
echo "1. Полностью закройте Cursor (Cmd+Q)"
echo "2. Запустите Cursor заново"
echo "3. Откройте проект: $REPO_PATH"
echo "4. Дождитесь завершения индексации Git"
echo "5. Отключите Parallel Models в настройках Composer"
echo ""
echo "⚠️  Если ошибка 'Worktree not found' всё ещё появляется:"
echo "   - Игнорируйте её (она исчезнет после перезапуска)"
echo "   - Или попробуйте применить изменения вручную через Git"

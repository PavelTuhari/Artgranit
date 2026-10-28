#!/usr/bin/env bash
# agent_audit.sh — аудит начала и конца сессии (правила №6 и №7 CLAUDE.md). Только чтение.
#
#   scripts/agent_audit.sh
#
# Показывает: где ты (ветка, каталог), незакоммиченные файлы во ВСЕХ worktree,
# ветки без upstream, коммиты текущей ветки, которых нет в origin, и ветки,
# не слитые в origin/main. Найденное чужое — не трогать, сказать владельцу.
set -uo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
git fetch -q origin 2>/dev/null || echo "(origin недоступен — проверка по локальным данным)"
cur=$(git branch --show-current)
echo "== ты здесь: $root  [$cur]"
if [ "$root" = "/Users/pt/Projects.AI/Artgranit" ] && [ "$cur" != "main" ]; then
  echo "   ⚠ общий каталог не на main — здесь чужая ветка, работать в своём worktree"
fi

echo "== незакоммиченное по worktree:"
git worktree list --porcelain | awk '/^worktree /{print $2}' | while read -r wt; do
  n=$(git -C "$wt" status --porcelain 2>/dev/null | grep -v '^?? wallet_' | wc -l | tr -d ' ')
  [ "$n" != "0" ] && echo "   $n файл(ов): $wt [$(git -C "$wt" branch --show-current)]"
done
echo "   (пусто = чисто)"

echo "== коммиты $cur, которых нет в origin:"
if git rev-parse -q --verify "origin/$cur" >/dev/null 2>&1; then
  git log --oneline "origin/$cur..HEAD" | sed 's/^/   /'
else
  echo "   ⚠ у ветки нет upstream — git push -u origin $cur"
fi

echo "== локальные ветки без upstream:"
git for-each-ref --format='%(refname:short) %(upstream:short)' refs/heads | awk '$2==""{print "   "$1}'

echo "== ветки, не слитые в origin/main:"
git branch --no-merged origin/main | sed 's/^/   /'
echo "== конец аудита"

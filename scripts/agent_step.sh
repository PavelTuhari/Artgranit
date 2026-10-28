#!/usr/bin/env bash
# agent_step.sh — «шаг закончен → commit → push» одной командой (правило №7 CLAUDE.md).
#
#   scripts/agent_step.sh "<ключ>: что сделано" <путь> [<путь>...]
#   scripts/agent_step.sh --shared "<ключ>: что сделано" app.py models/x.py
#
# Зачем: hook PostToolUse коммитит только файлы, записанные через Write/Edit.
# Файлы, созданные через shell (cat >, python-патч, sed), hook НЕ видит —
# 02.09.2026 так пролежал незакоммиченным весь код TBControl mTLS и был затёрт.
# Скрипт:
#   1. отказывается коммитить на main и без явного списка путей;
#   2. общие файлы (app.py, CLAUDE.md, AGENTS.md, README.md, deploy_oracle_objects.py,
#      controllers/, models/database.py, templates/ старых модулей) принимает
#      только с флагом --shared и показывает их последние коммиты — чтобы было
#      видно, что правка точечная и поверх чужой версии;
#   3. git add ТОЛЬКО указанных путей (чужие незакоммиченные файлы не трогает);
#   4. commit, push -u origin HEAD, проверка origin/<ветка>..HEAD == пусто.
set -euo pipefail

shared=0
if [ "${1:-}" = "--shared" ]; then shared=1; shift; fi
msg="${1:-}"; shift || true
if [ -z "$msg" ] || [ $# -eq 0 ]; then
  echo "использование: $0 [--shared] \"<сообщение>\" <путь>..." >&2; exit 2
fi

root=$(git rev-parse --show-toplevel)
cd "$root"
branch=$(git branch --show-current)
if [ -z "$branch" ]; then echo "detached HEAD — сначала создай ветку" >&2; exit 2; fi
if [ "$branch" = "main" ] && [ "${AGENT_STEP_ALLOW_MAIN:-0}" != "1" ]; then
  echo "на main коммитить напрямую нельзя: своя задача — свой worktree/ветка" >&2; exit 2
fi

shared_re='^(app\.py|config\.py|deploy_oracle_objects\.py|deploy_to_remote\.sh|CLAUDE\.md|AGENTS\.md|README\.md|controllers/|models/database\.py|templates/[^/]+\.html|static/(css|js)/)'
for p in "$@"; do
  if [[ "$p" =~ $shared_re ]]; then
    if [ $shared -eq 0 ]; then
      echo "ОБЩИЙ файл: $p — только точечная правка; повтори с --shared, если это так" >&2
      echo "  история: $(git log --oneline -3 -- "$p" | tr '\n' ';')" >&2
      exit 3
    fi
    echo "общий файл $p, последние коммиты:"; git log --oneline -3 -- "$p" | sed 's/^/    /'
  fi
done

git add -- "$@"
if git diff --cached --quiet; then echo "нечего коммитить по указанным путям"; exit 0; fi
git commit -q -m "$msg" -- "$@"
git push -q -u origin HEAD
left=$(git log --oneline "origin/$branch..HEAD" | wc -l | tr -d ' ')
if [ "$left" != "0" ]; then echo "ВНИМАНИЕ: $left коммитов не ушли в origin" >&2; exit 4; fi
echo "✔ $branch → origin: $(git log --oneline -1)"

#!/usr/bin/env bash
# TexFlow: полный прогон — тесты, браузер со скриншотами, HTML-документация, акт, презентация.
#   tools/run_all.sh            из каталога standalone/texflow
# Нужны: python3 (flask, reportlab, pytest, markdown), node + playwright с Chromium, pdftoppm (poppler).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/html
mkdir -p "$OUT"
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"

echo "== 1/4 pytest"
python3 -m pytest -q -p no:cacheprovider --junitxml="$OUT/pytest_results.xml" || PYTEST_FAILED=1

echo "== 2/4 сквозной прогон в браузере (скриншоты)"
node tools/e2e.js "$OUT" || E2E_FAILED=1

echo "== 3/4 mermaid для схем без интернета"
if [ -z "${MERMAID_JS:-}" ]; then
  if [ ! -f tools/.cache/node_modules/mermaid/dist/mermaid.min.js ]; then
    npm install --silent --prefix tools/.cache mermaid@10.9.1 >/dev/null 2>&1 || echo "   mermaid не установлен — схемы будут подключаться с CDN"
  fi
  [ -f tools/.cache/node_modules/mermaid/dist/mermaid.min.js ] && export MERMAID_JS="$PWD/tools/.cache/node_modules/mermaid/dist/mermaid.min.js"
fi

echo "== 4/4 HTML: документация RU/RO/EN, галереи, акт, презентация"
python3 tools/build_html.py
node tools/render_pdf.js "$OUT" || echo "   PDF не собран"

echo
echo "Готово: $OUT/index.html · $OUT/test_act.html · $OUT/presentation.html"
echo "Архив git-версии: tools/make_archive.sh (после commit)"
[ -z "${PYTEST_FAILED:-}" ] && [ -z "${E2E_FAILED:-}" ] || { echo "ЕСТЬ ПРОВАЛЫ — см. акт"; exit 1; }

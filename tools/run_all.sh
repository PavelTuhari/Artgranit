#!/usr/bin/env bash
# TexFlow: полный прогон — тесты, браузер и окно программы со скриншотами, установка и сборка,
# HTML-документация RU/RO/EN, акт тестирования, презентация (HTML + PDF).
#   tools/run_all.sh                  из каталога standalone/texflow
#   TEXFLOW_TK_PYTHON=/path/python    Python с Tkinter и reportlab/openpyxl/flask/pytest (для окна программы)
#   TEXFLOW_BUILD=1                   добавить сборку PyInstaller (нужен pyinstaller в TEXFLOW_TK_PYTHON)
# Нужны: node + playwright (Chromium), pdftoppm, ImageMagick import; без X-дисплея — xvfb-run.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/html
mkdir -p "$OUT"
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
PY="${TEXFLOW_TK_PYTHON:-python3}"
if ! "$PY" -c "import tkinter" 2>/dev/null; then
  for c in python3.13 python3.12 python3.11 python3.10; do
    if command -v $c >/dev/null && $c -c "import tkinter" 2>/dev/null; then PY=$c; break; fi
  done
fi
xrun() { if [ -n "${DISPLAY:-}" ]; then "$@"; else xvfb-run -a -s "-screen 0 1360x860x24" "$@"; fi; }

echo "== 1/6 pytest ($PY)"
xrun "$PY" -m pytest -q -p no:cacheprovider --junitxml="$OUT/pytest_results.xml" || PYTEST_FAILED=1

echo "== 2/6 браузер (веб-версия, скриншоты)"
node tools/e2e.js "$OUT" || E2E_FAILED=1

echo "== 3/6 нативное приложение (окно, скриншоты)"
xrun "$PY" tools/desktop_e2e.py "$OUT" || DESK_FAILED=1

echo "== 4/6 установка / удаление${TEXFLOW_BUILD:+ / сборка}"
xrun "$PY" tools/install_check.py "$OUT" ${TEXFLOW_BUILD:+--build} || INST_FAILED=1

echo "== 5/6 mermaid для схем без интернета"
if [ -z "${MERMAID_JS:-}" ]; then
  if [ ! -f tools/.cache/node_modules/mermaid/dist/mermaid.min.js ]; then
    npm install --silent --prefix tools/.cache mermaid@10.9.1 >/dev/null 2>&1 || echo "   mermaid не установлен — схемы будут подключаться с CDN"
  fi
  [ -f tools/.cache/node_modules/mermaid/dist/mermaid.min.js ] && export MERMAID_JS="$PWD/tools/.cache/node_modules/mermaid/dist/mermaid.min.js"
fi

echo "== 6/6 HTML: документация RU/RO/EN, галереи, акт, презентация + PDF"
python3 tools/build_html.py
node tools/render_pdf.js "$OUT" || echo "   PDF не собран"

echo
echo "Готово: $OUT/index.html · $OUT/test_act.html · $OUT/presentation.html"
echo "Архив git-версии: tools/make_archive.sh (после commit)"
[ -z "${PYTEST_FAILED:-}${E2E_FAILED:-}${DESK_FAILED:-}${INST_FAILED:-}" ] || { echo "ЕСТЬ ПРОВАЛЫ — см. акт"; exit 1; }

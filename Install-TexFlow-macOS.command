#!/bin/bash
# TexFlow — установка на macOS двойным щелчком (Finder). Права администратора не нужны.
cd "$(dirname "$0")"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys,tkinter;sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Нужен Python 3.10+ с Tk. Открываю страницу загрузки python.org (macOS installer включает Tk)."
  echo "Или через Homebrew: brew install python python-tk"
  open "https://www.python.org/downloads/macos/"
  read -r -p "После установки Python запустите этот файл снова. Enter — закрыть." _
  exit 1
fi
xattr -dr com.apple.quarantine "$(pwd)" 2>/dev/null || true
"$PY" install/install.py "$@"
read -r -p "Готово. Enter — закрыть окно." _

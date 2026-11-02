#!/bin/sh
# TexFlow — установка на Linux: sh install-texflow-linux.sh  (права root не нужны, кроме доустановки python3-tk)
cd "$(dirname "$0")"
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys,tkinter,venv,ensurepip;sys.exit(0 if sys.version_info>=(3,10) else 1)" 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Нужен Python 3.10+ с Tkinter и venv."
  if command -v apt-get >/dev/null 2>&1; then echo "  sudo apt install python3 python3-tk python3-venv"; CMD="apt-get install -y python3 python3-tk python3-venv"
  elif command -v dnf >/dev/null 2>&1; then echo "  sudo dnf install python3 python3-tkinter"; CMD="dnf install -y python3 python3-tkinter"
  elif command -v pacman >/dev/null 2>&1; then echo "  sudo pacman -S python tk"; CMD="pacman -S --noconfirm python tk"
  fi
  if [ -n "$CMD" ] && [ "$1" = "--with-system-packages" ]; then sudo sh -c "$CMD" && exec sh "$0"; fi
  echo "Повторите после установки или запустите: sh $0 --with-system-packages"
  exit 1
fi
[ "$1" = "--with-system-packages" ] && shift
exec "$PY" install/install.py "$@"

#!/bin/sh
# RO: actualizarea automata a preturilor Ultra — lantul complet, o data pe ora.
#     1) sincronizare incrementala prin /api/changes (reperul PARTNER_ULTRA_SINCE)
#     2) publicare prin conveierul standard (import_file, p_src=ULTRA):
#        pozitiile existente primesc perioada noua de pret DOAR daca pretul
#        difera, cele noi se creeaza. Rularea repetata e sigura (idempotenta).
# EN: hourly Ultra price refresh: incremental sync, then standard-pipeline publish.
#
# crontab (server sau statia care are acces la ERP):
#   17 * * * * /Users/pt/Projects.AI/Artgranit-ultrafix/modules/partner/scripts/ultra_cron.sh
#
# Jurnal: /tmp/ultra_cron.log (ultimele rulari) + YBIRO_IMPORT_LOG / PAPI_LOG in baza.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PY="${PY:-/Users/pt/Projects.AI/Artgranit/venv/bin/python}"
LOG="${LOG:-/tmp/ultra_cron.log}"
LOCK="/tmp/ultra_cron.lock"

# RO: o singura rulare la un moment dat — sincronizarea completa poate depasi ora
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "$(date '+%F %T') sare: rulare anterioara inca activa (pid $(cat "$LOCK"))" >> "$LOG"
  exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

cd "$ROOT" || exit 1
{
  echo "=== $(date '+%F %T') sync incremental ==="
  "$PY" modules/partner/scripts/ultra_sync.py || { echo "sync ESUAT"; exit 1; }
  echo "=== $(date '+%F %T') publish ==="
  "$PY" modules/partner/scripts/ultra_publish.py --commit --xlsx /tmp/ULTRA_cron.xlsx
  echo "=== $(date '+%F %T') gata ==="
} >> "$LOG" 2>&1

#!/bin/bash
# RO: aduce instalarea WordPress officeplus.md (fisiere + dump DB) in copia
#     locala de lucru wordpress_officeplus/. Regula: modificarile se fac
#     local si se publica cu wp_push.sh; pull inainte de a incepe lucrul.
# EN: pull the live WP install (files + DB dump) into the local working copy.
set -euo pipefail
KEY=/Users/pt/Projects.AI/BIRO26/biro26_rsa
HOST=ubuntu@89.168.115.20
WP_PATH=/home/admin/web/officeplus.md/public_html
LOCAL="$(cd "$(dirname "$0")/.." && pwd)/wordpress_officeplus"

echo "== arhivez pe server =="
ssh -i "$KEY" "$HOST" "sudo tar czf /tmp/wp_files.tar.gz --exclude=public_html/.tmb \
  -C /home/admin/web/officeplus.md public_html && sudo chown ubuntu /tmp/wp_files.tar.gz && \
  sudo -u www-data wp --path=$WP_PATH db export /tmp/officeplus_wp.sql >/dev/null && \
  sudo gzip -f /tmp/officeplus_wp.sql && sudo chown ubuntu /tmp/officeplus_wp.sql.gz"

echo "== descarc =="
mkdir -p "$LOCAL/db"
scp -i "$KEY" "$HOST:/tmp/wp_files.tar.gz" "$LOCAL/"
scp -i "$KEY" "$HOST:/tmp/officeplus_wp.sql.gz" "$LOCAL/db/officeplus_wp.sql.gz"

echo "== dezarhivez local =="
rm -rf "$LOCAL/public_html"
tar xzf "$LOCAL/wp_files.tar.gz" -C "$LOCAL"
rm "$LOCAL/wp_files.tar.gz"
echo "OK: $LOCAL/public_html + db/officeplus_wp.sql.gz"

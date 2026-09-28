#!/bin/bash
# RO: publica FISIERELE WordPress din copia locala wordpress_officeplus/
#     pe serverul live. Implicit DRY-RUN (arata ce s-ar schimba);
#     ruleaza cu --go pentru publicare efectiva.
#     NB: doar fisiere (teme/plugin-uri/uploads). CONTINUTUL (pagini,
#     meniuri, setari) traieste in DB si se publica punctual prin wp-cli —
#     vezi wordpress_officeplus/README.md. wp-config.php NU se sincronizeaza.
# EN: push local WP FILES to the live server; dry-run by default (--go to
#     apply). Content lives in the DB and is pushed per-page via wp-cli.
set -euo pipefail
KEY=/Users/pt/Projects.AI/BIRO26/biro26_rsa
HOST=ubuntu@89.168.115.20
LOCAL="$(cd "$(dirname "$0")/.." && pwd)/wordpress_officeplus/public_html"
REMOTE_TMP=/tmp/wp_push_stage

DRY="--dry-run"
[ "${1:-}" = "--go" ] && DRY=""

[ -d "$LOCAL" ] || { echo "Lipseste $LOCAL — ruleaza intai wp_pull.sh"; exit 1; }

echo "== rsync ${DRY:-(PUBLICARE EFECTIVA)} =="
# RO: staging pe server (rsync nu poate scrie direct ca admin), apoi sudo copy
rsync -avz $DRY --delete \
  --exclude 'wp-config.php' --exclude '.htaccess' --exclude '.tmb' \
  -e "ssh -i $KEY" "$LOCAL/" "$HOST:$REMOTE_TMP/"

if [ -z "$DRY" ]; then
  ssh -i "$KEY" "$HOST" "sudo rsync -a --exclude wp-config.php --exclude .htaccess \
    $REMOTE_TMP/ /home/admin/web/officeplus.md/public_html/ && \
    sudo chown -R admin:admin /home/admin/web/officeplus.md/public_html && \
    echo 'publicat + chown admin OK'"
  echo "== verificare =="
  curl -s -o /dev/null -w 'officeplus.md: %{http_code}\n' https://officeplus.md/
else
  echo "(dry-run — nimic publicat; ruleaza cu --go pentru publicare)"
fi

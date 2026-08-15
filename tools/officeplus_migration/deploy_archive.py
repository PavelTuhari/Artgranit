#!/usr/bin/env python3
"""Шаг 2. Разворачивание архива officeplus (из make_archive.py) на НОВЫЙ сервер.

Полностью автономный скрипт: python3 + ssh/scp, чистый Ubuntu 24.04 (подходит
Oracle Always Free 1 GB RAM). Ставит: nginx + PHP-FPM + MariaDB + WordPress +
Flask artgranit + Oracle Instant Client + systemd + защиту WP + fail2ban.
Пароль MySQL для WordPress генерируется ЗАНОВО и прописывается сразу в
wp-config.php и в .env Flask (WP_DB_PASSWORD — модуль соц-аналитики).

Запуск (все шаги по порядку):
    python3 deploy_archive.py --archive ./archives/officeplus_20260815_1200 \
        --ip 1.2.3.4 --key ~/.ssh/new-server.key

Отдельные шаги (повторный запуск безопасен):
    python3 deploy_archive.py --archive ... --ip ... --key ... base upload flask
    шаги: base upload flask wp nginx harden check tls

После check: перенастроить DNS A-записи домена на новый IP, затем запустить
шаг tls (certbot). Подробности: README.md рядом.
"""
import argparse
import os
import secrets
import subprocess
import sys

SSH_OPT = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15"]
ART = ["code.tar.gz", "wallets.tar.gz", "ic.tar.gz", "wp_files.tar.gz",
       "wp_db.sql.gz", "nginx_site.conf", "artgranit.service"]


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd[:8]), "…" if len(cmd) > 8 else "")
    return subprocess.run(cmd, check=True, **kw)


class Deploy:
    def __init__(self, a):
        self.a = a
        self.key = os.path.expanduser(a.key)
        self.host = f"{a.user}@{a.ip}"
        self.db_pw = secrets.token_hex(16)

    def ssh(self, script):
        run(["ssh", "-i", self.key, *SSH_OPT, self.host, script])

    def push(self, local, remote="/tmp/"):
        run(["scp", "-q", "-i", self.key, *SSH_OPT, local,
             f"{self.host}:{remote}"])

    # ── base: пакеты, swap, тюнинг под 1 GB RAM ────────────────────────
    def step_base(self):
        self.ssh("""set -e
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  nginx php8.3-fpm php8.3-mysql php8.3-curl php8.3-gd php8.3-xml php8.3-mbstring \
  php8.3-zip php8.3-intl mariadb-server python3-venv python3-pip unzip zstd libaio1t64 \
  libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core
swapon --show | grep -q swapfile || { sudo fallocate -l 2G /swapfile &&
  sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile &&
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab; }
printf '[mysqld]\\ninnodb_buffer_pool_size=128M\\nmax_connections=40\\n' |
  sudo tee /etc/mysql/mariadb.conf.d/60-lowmem.cnf >/dev/null
sudo sed -i 's/^pm.max_children.*/pm.max_children = 4/' /etc/php/8.3/fpm/pool.d/www.conf
sudo systemctl restart mariadb php8.3-fpm""")

    # ── upload: артефакты архива на сервер ─────────────────────────────
    def step_upload(self):
        for f in ART:
            self.push(os.path.join(self.a.archive, f))
        wh = os.path.join(self.a.archive, "wp-harden.conf")
        if os.path.exists(wh):
            self.push(wh)
        dc = os.path.join(self.a.archive, "DEPLOY_COMMIT")
        if os.path.exists(dc):
            self.push(dc)

    # ── flask: код + .env + wallet + instant client + venv + systemd ───
    def step_flask(self):
        self.ssh("""set -e
sudo rm -rf /home/ubuntu/artgranit
tar -xzf /tmp/code.tar.gz -C /home/ubuntu
chmod 600 /home/ubuntu/artgranit/.env
[ -f /tmp/DEPLOY_COMMIT ] && cp /tmp/DEPLOY_COMMIT /home/ubuntu/artgranit/
sudo rm -rf /home/ubuntu/oracle_wallets /opt/oracle
sudo tar -xzf /tmp/wallets.tar.gz -C /home/ubuntu
sudo chown -R ubuntu /home/ubuntu/oracle_wallets
sudo tar -xzf /tmp/ic.tar.gz -C /opt
IC=$(ls -d /opt/oracle/instantclient_* | head -1)
echo $IC | sudo tee /etc/ld.so.conf.d/oracle-instantclient.conf >/dev/null
sudo ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1
sudo ldconfig
cd /home/ubuntu/artgranit && python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
sudo cp /tmp/artgranit.service /etc/systemd/system/artgranit.service
sudo systemctl daemon-reload && sudo systemctl enable artgranit""")

    # ── wp: файлы + база + НОВЫЙ пароль в wp-config и .env Flask ──────
    def step_wp(self):
        self.ssh(f"""set -e
sudo rm -rf /var/www/officeplus /tmp/wpx && mkdir /tmp/wpx
tar -xzf /tmp/wp_files.tar.gz -C /tmp/wpx
sudo mv /tmp/wpx/officeplus /var/www/officeplus
DB=$(sudo php -r 'include "/var/www/officeplus/wp-config.php"; echo DB_NAME;')
DBU=$(sudo php -r 'include "/var/www/officeplus/wp-config.php"; echo DB_USER;')
sudo mysql -e "CREATE DATABASE IF NOT EXISTS $DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci;
  CREATE USER IF NOT EXISTS '$DBU'@'localhost' IDENTIFIED BY '{self.db_pw}';
  ALTER USER '$DBU'@'localhost' IDENTIFIED BY '{self.db_pw}';
  GRANT ALL PRIVILEGES ON $DB.* TO '$DBU'@'localhost'; FLUSH PRIVILEGES;"
zcat /tmp/wp_db.sql.gz | sudo mysql --default-character-set=utf8mb4 --database=$DB
sudo php -r '$f="/var/www/officeplus/wp-config.php"; $c=file_get_contents($f);
  $c=preg_replace("/define\\(\\s*.DB_PASSWORD.[^)]*\\);/",
    "define( \\x27DB_PASSWORD\\x27, \\x27{self.db_pw}\\x27 );", $c, 1);
  file_put_contents($f, $c);'
# Flask .env: модуль соц-аналитики пишет в ту же базу WP
sed -i 's/^WP_DB_PASSWORD=.*/WP_DB_PASSWORD={self.db_pw}/' /home/ubuntu/artgranit/.env
sudo chown -R www-data:www-data /var/www/officeplus
sudo chmod 640 /var/www/officeplus/wp-config.php
which wp >/dev/null || {{ curl -so /tmp/wpcli https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar &&
  sudo mv /tmp/wpcli /usr/local/bin/wp && sudo chmod +x /usr/local/bin/wp; }}
sudo rm -rf /tmp/wpx""")

    # ── nginx: конфиг из архива (правка домена при необходимости) ──────
    def step_nginx(self):
        self.ssh(f"""set -e
sudo cp /tmp/nginx_site.conf /etc/nginx/sites-available/officeplus
[ -f /tmp/wp-harden.conf ] && sudo cp /tmp/wp-harden.conf /etc/nginx/snippets/wp-harden.conf
# сертификата на новой машине ещё нет — временно оставляем только :80
sudo sed -i '/ssl_certificate\\|listen 443\\|ssl_dhparam\\|include.*letsencrypt/d' \
  /etc/nginx/sites-available/officeplus
grep -q 'listen 80' /etc/nginx/sites-available/officeplus ||
  sudo sed -i '0,/server {{/s//server {{\\n    listen 80;/' /etc/nginx/sites-available/officeplus
# лимит для wp-login (нужен снипету wp-harden)
grep -q zone=wplogin /etc/nginx/nginx.conf ||
  sudo sed -i '/http {{/a\\\\tlimit_req_zone $binary_remote_addr zone=wplogin:10m rate=15r/m;' /etc/nginx/nginx.conf
sudo ln -sf /etc/nginx/sites-available/officeplus /etc/nginx/sites-enabled/officeplus
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo systemctl restart artgranit""")
        if self.a.domain != "officeplus.md":
            d = self.a.domain
            self.ssh(f"""set -e
sudo sed -i 's/officeplus\\.md/{d}/g' /etc/nginx/sites-available/officeplus
sudo php -r '$f="/var/www/officeplus/wp-config.php"; $c=file_get_contents($f);
  $c=str_replace("officeplus.md", "{d}", $c); file_put_contents($f, $c);'
sudo -u www-data wp --path=/var/www/officeplus search-replace \
  "https://officeplus.md" "https://{d}" --all-tables --quiet || true
sudo nginx -t && sudo systemctl reload nginx""")

    # ── harden: fail2ban + автообновления (nginx-снипет уже из архива) ─
    def step_harden(self):
        self.ssh("""set -e
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q fail2ban unattended-upgrades >/dev/null
printf '[Definition]\\nfailregex = ^<HOST> .* "POST /wp-login\\\\.php\\n' |
  sudo tee /etc/fail2ban/filter.d/wp-login.conf >/dev/null
printf '[DEFAULT]\\nbantime = 1h\\nfindtime = 10m\\n[sshd]\\nenabled = true\\n[wp-login]\\nenabled = true\\nfilter = wp-login\\nlogpath = /var/log/nginx/access.log\\nmaxretry = 8\\nport = http,https\\n' |
  sudo tee /etc/fail2ban/jail.local >/dev/null
sudo systemctl enable --now fail2ban && sudo systemctl restart fail2ban""")

    # ── check: живость всех слоёв ──────────────────────────────────────
    def step_check(self):
        d = self.a.domain
        self.ssh(f"""set -e
sleep 6
echo "MariaDB: $(sudo mysql -e 'SELECT 1' >/dev/null 2>&1 && echo OK || echo FAIL)"
echo "Flask:   $(curl -s -o /dev/null -w %{{http_code}} http://127.0.0.1:8000/login)  (нужно 200)"
echo "Health:  $(curl -s http://127.0.0.1:8000/api/biro26/health | head -c 120)"
echo "WP:      $(curl -s -o /dev/null -w %{{http_code}} -H 'Host: {d}' http://127.0.0.1/wp-json/)  (нужно 200)"
echo "Shop:    $(curl -s -o /dev/null -w %{{http_code}} -H 'Host: {d}' http://127.0.0.1/cos)  (нужно 200)" """)
        print(f"""
==== РАЗВЁРНУТО ====
1. Проверить по IP: curl -H 'Host: {d}' http://{self.a.ip}/
2. DNS (nic.md): A-записи {d} и www.{d} -> {self.a.ip}
3. Когда DNS обновится — шаг tls:
   python3 deploy_archive.py --archive {self.a.archive} --ip {self.a.ip} --key {self.a.key} tls
Пароль MySQL WordPress: сгенерирован заново, лежит только в wp-config.php
и в .env Flask на новом сервере (в архиве остался старый).""")

    # ── tls: Let's Encrypt (запускать ПОСЛЕ переключения DNS) ──────────
    def step_tls(self):
        d = self.a.domain
        self.ssh(f"""set -e
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q certbot python3-certbot-nginx >/dev/null
sudo certbot --nginx -d {d} -d www.{d} --non-interactive --agree-tos \
  -m admin@{d} --redirect
sudo nginx -t && sudo systemctl reload nginx
echo "HTTPS: $(curl -s -o /dev/null -w %{{http_code}} https://{d}/cos)" """)

    STEPS = ("base", "upload", "flask", "wp", "nginx", "harden", "check")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--archive", required=True, help="папка из make_archive.py")
    ap.add_argument("--ip", required=True, help="IP нового сервера")
    ap.add_argument("--key", required=True, help="SSH-ключ нового сервера")
    ap.add_argument("--user", default="ubuntu")
    ap.add_argument("--domain", default="officeplus.md")
    ap.add_argument("steps", nargs="*", help="подмножество шагов (по умолчанию все, кроме tls)")
    a = ap.parse_args()

    a.archive = os.path.abspath(os.path.expanduser(a.archive))
    missing = [f for f in ART if not os.path.exists(os.path.join(a.archive, f))]
    if missing:
        sys.exit(f"В архиве не хватает: {', '.join(missing)}")
    if not os.path.exists(os.path.expanduser(a.key)):
        sys.exit(f"SSH-ключ не найден: {a.key}")

    d = Deploy(a)
    names = a.steps or list(Deploy.STEPS)
    for n in names:
        fn = getattr(d, f"step_{n}", None)
        if fn is None:
            sys.exit(f"Неизвестный шаг: {n} (есть: {', '.join(Deploy.STEPS)}, tls)")
        print(f"\n===== {n} =====")
        fn()


if __name__ == "__main__":
    main()

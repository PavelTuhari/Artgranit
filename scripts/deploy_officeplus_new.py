#!/usr/bin/env python3
"""Разворачивает НОВЫЙ экземпляр officeplus.md на чистом Ubuntu 24.04
(Oracle Always Free, http://92.5.130.1/docs/ECOMMERCE-WEB-SERVER.md).

Что ставит: nginx + PHP-FPM + MariaDB + WordPress (вычищенная копия основного
officeplus.md) + Flask artgranit (магазин /UNA.md/... + красивые URL) +
Oracle Instant Client. Источник артефактов — nufarul (92.5.3.187), где уже
лежат: WP-файлы /var/www/officeplus.main, дамп officeplus_wp_main_backup.sql.gz,
рабочий .env, wallet и instant client. Запускать с машины, у которой есть
SSH-ключи к ОБОИМ серверам:

    python3 scripts/deploy_officeplus_new.py            # всё
    python3 scripts/deploy_officeplus_new.py wp nginx   # только шаги

После успеха: перенастроить A-запись officeplus.md на NEW_IP через nic.md,
затем на новом сервере: certbot --nginx -d officeplus.md -d www.officeplus.md
"""
import os, secrets, subprocess, sys, tempfile

NEW_IP  = os.environ.get("NEW_IP",  "92.5.130.1")
NEW_KEY = os.environ.get("NEW_KEY", "/home/pt/grok/.ssh-keys/oracle-ecommerce-web")
SRC_IP  = os.environ.get("SRC_IP",  "92.5.3.187")            # nufarul (артефакты)
SRC_KEY = os.environ.get("SRC_KEY", os.path.expanduser("~/.ssh/artgranit-oci.key"))
REPO    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAIN  = "officeplus.md"
DB_PW   = secrets.token_hex(16)

SSH_OPT = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10"]
def run(cmd, **kw):
    print("+", " ".join(cmd[:6]), "…" if len(cmd) > 6 else "")
    subprocess.run(cmd, check=True, **kw)
def new(script):   run(["ssh", "-i", NEW_KEY, *SSH_OPT, f"ubuntu@{NEW_IP}", script])
def src(script):   run(["ssh", "-i", SRC_KEY, *SSH_OPT, f"ubuntu@{SRC_IP}", script])
def push(local, remote): run(["scp", "-i", NEW_KEY, *SSH_OPT, local, f"ubuntu@{NEW_IP}:{remote}"])
def pull(remote, local): run(["scp", "-i", SRC_KEY, *SSH_OPT, f"ubuntu@{SRC_IP}:{remote}", local])

TMP = tempfile.mkdtemp(prefix="opnew_")

def step_base():
    """Пакеты + 2G swap (у машины всего 1 GB RAM) + лёгкий тюнинг БД/PHP."""
    new("""set -e
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  nginx php8.3-fpm php8.3-mysql php8.3-curl php8.3-gd php8.3-xml php8.3-mbstring \
  php8.3-zip php8.3-intl mariadb-server python3-venv python3-pip unzip zstd libaio1t64
swapon --show | grep -q swapfile || { sudo fallocate -l 2G /swapfile &&
  sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile &&
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab; }
printf '[mysqld]\\ninnodb_buffer_pool_size=128M\\nmax_connections=40\\n' |
  sudo tee /etc/mysql/mariadb.conf.d/60-lowmem.cnf >/dev/null
sudo sed -i 's/^pm.max_children.*/pm.max_children = 4/' /etc/php/8.3/fpm/pool.d/www.conf
sudo systemctl restart mariadb php8.3-fpm""")

def step_wp():
    """WordPress: файлы + БД с nufarul, URL -> https://officeplus.md."""
    src("sudo tar -C /var/www -czf /tmp/wpmain.tar.gz officeplus.main && sudo chown ubuntu /tmp/wpmain.tar.gz")
    pull("/tmp/wpmain.tar.gz", f"{TMP}/wpmain.tar.gz")
    pull("/home/ubuntu/officeplus_wp_main_backup.sql.gz", f"{TMP}/wp.sql.gz")
    src("rm -f /tmp/wpmain.tar.gz")
    push(f"{TMP}/wpmain.tar.gz", "/tmp/"); push(f"{TMP}/wp.sql.gz", "/tmp/")
    new(f"""set -e
sudo rm -rf /var/www/officeplus /tmp/wpx && mkdir /tmp/wpx
tar -xzf /tmp/wpmain.tar.gz -C /tmp/wpx
sudo mv /tmp/wpx/officeplus.main /var/www/officeplus
sudo mysql -e "CREATE DATABASE IF NOT EXISTS officeplus_wp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_520_ci;
  CREATE USER IF NOT EXISTS 'officeplus_wp'@'localhost' IDENTIFIED BY '{DB_PW}';
  ALTER USER 'officeplus_wp'@'localhost' IDENTIFIED BY '{DB_PW}';
  GRANT ALL PRIVILEGES ON officeplus_wp.* TO 'officeplus_wp'@'localhost'; FLUSH PRIVILEGES;"
zcat /tmp/wp.sql.gz | sudo mysql --default-character-set=utf8mb4 --database=officeplus_wp
sudo php -r '$f="/var/www/officeplus/wp-config.php"; $c=file_get_contents($f);
  foreach (["DB_NAME"=>"officeplus_wp","DB_USER"=>"officeplus_wp","DB_PASSWORD"=>"{DB_PW}","DB_HOST"=>"localhost"] as $k=>$v)
    $c=preg_replace("/define\\(\\s*.".$k.".[^)]*\\);/","define( \\x27".$k."\\x27, \\x27".$v."\\x27 );",$c,1);
  $c=preg_replace("~define\\(.WP_HOME.[^)]*\\);~","define(\\x27WP_HOME\\x27, \\x27https://{DOMAIN}\\x27);",$c);
  $c=preg_replace("~define\\(.WP_SITEURL.[^)]*\\);~","define(\\x27WP_SITEURL\\x27, \\x27https://{DOMAIN}\\x27);",$c);
  file_put_contents($f,$c);'
sudo chown -R www-data:www-data /var/www/officeplus && sudo chmod 640 /var/www/officeplus/wp-config.php
which wp >/dev/null || {{ curl -so /tmp/wp https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar &&
  sudo mv /tmp/wp /usr/local/bin/wp && sudo chmod +x /usr/local/bin/wp; }}
sudo -u www-data wp --path=/var/www/officeplus search-replace \
  "https://nufarul.eminescu.md/UNA.md/orasldev/biro26-wp" "https://{DOMAIN}" --all-tables --quiet || true
rm -f /tmp/wpmain.tar.gz /tmp/wp.sql.gz && sudo rm -rf /tmp/wpx""")

def step_flask():
    """Flask artgranit: код из локального git + venv + .env/wallet/instantclient с nufarul."""
    run(["git", "-C", REPO, "archive", "-o", f"{TMP}/code.tar.gz", "HEAD"])
    pull("/home/ubuntu/artgranit/.env", f"{TMP}/env")
    src("sudo tar -C /home/ubuntu -czf /tmp/wallets.tar.gz oracle_wallets && "
        "sudo tar -C /opt -czf /tmp/ic.tar.gz oracle && sudo chown ubuntu /tmp/wallets.tar.gz /tmp/ic.tar.gz")
    pull("/tmp/wallets.tar.gz", f"{TMP}/wallets.tar.gz"); pull("/tmp/ic.tar.gz", f"{TMP}/ic.tar.gz")
    src("rm -f /tmp/wallets.tar.gz /tmp/ic.tar.gz")
    for f in ("code.tar.gz", "env", "wallets.tar.gz", "ic.tar.gz"):
        push(f"{TMP}/{f}", "/tmp/")
    new(f"""set -e
mkdir -p /home/ubuntu/artgranit && tar -xzf /tmp/code.tar.gz -C /home/ubuntu/artgranit
cp /tmp/env /home/ubuntu/artgranit/.env && chmod 600 /home/ubuntu/artgranit/.env
sudo tar -xzf /tmp/wallets.tar.gz -C /home/ubuntu && sudo chown -R ubuntu /home/ubuntu/oracle_wallets
sudo tar -xzf /tmp/ic.tar.gz -C /opt
# Ubuntu 24.04: instant client требует ldconfig-запись и libaio.so.1 (пакет t64)
echo /opt/oracle/instantclient_19_28 | sudo tee /etc/ld.so.conf.d/oracle-instantclient.conf >/dev/null
sudo ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1
sudo ldconfig
# инстансные отличия нового дома: WP-контент читаем локально (тот же сервер)
sed -i "s|^BIRO26_SHOP_WP_API=.*|BIRO26_SHOP_WP_API=https://{DOMAIN}/wp-json|" /home/ubuntu/artgranit/.env
grep -q "^BIRO26_CREDIT_HIDE_ORGS=" /home/ubuntu/artgranit/.env ||
  echo 'BIRO26_CREDIT_HIDE_ORGS="MAIB Credit de consum"' >> /home/ubuntu/artgranit/.env
cd /home/ubuntu/artgranit && python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
sudo tee /etc/systemd/system/artgranit.service >/dev/null <<'UNIT'
[Unit]
Description=Artgranit Flask (officeplus.md)
After=network.target mariadb.service
[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/artgranit
EnvironmentFile=/home/ubuntu/artgranit/.env
Environment=ENVIRONMENT=REMOTE PORT=8000
ExecStart=/home/ubuntu/artgranit/venv/bin/python3 app.py
Restart=always
[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now artgranit
rm -f /tmp/code.tar.gz /tmp/env /tmp/wallets.tar.gz /tmp/ic.tar.gz""")

# красивые URL витрины (как в Hestia-хуке nginx.conf_biro26 на старом officeplus)
PRETTY_PAGES = "despre-noi|contacte|livrare|retur-produse|termeni-si-conditii|politica-de-confidentialitate|credite"
NGINX = f"""server {{
    listen 80 default_server;
    server_name {DOMAIN} www.{DOMAIN} _;
    root /var/www/officeplus;
    index index.php;
    client_max_body_size 32M;

    location /UNA.md/ {{ proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr; proxy_set_header X-Forwarded-Proto $scheme; }}
    location /api/    {{ proxy_pass http://127.0.0.1:8000; proxy_set_header Host $host; }}
    location /static/ {{ proxy_pass http://127.0.0.1:8000; }}
    location = /biro26-shop {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-shop$is_args$args; }}
    location = /biro26-backoffice {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-backoffice$is_args$args; }}
    # витрина: красивые URL -> Flask biro26-site
    location = /cos      {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/cart$is_args$args; }}
    location = /cont     {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/account$is_args$args; }}
    location = /catalog  {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/catalog$is_args$args; }}
    location = /favorite {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/favorites$is_args$args; }}
    location = /compara  {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/compare$is_args$args; }}
    location = /branduri {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/brands$is_args$args; }}
    location ~ ^/produs/(\\d+)$ {{ proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/product/$1$is_args$args; }}
    location ~ ^/({PRETTY_PAGES})$ {{
        proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/biro26-site/page/$1$is_args$args; }}

    location / {{ try_files $uri $uri/ /index.php?$args; }}
    location ~ \\.php$ {{ include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock; }}
}}"""

def step_nginx():
    with open(f"{TMP}/site.conf", "w") as f: f.write(NGINX)
    push(f"{TMP}/site.conf", "/tmp/site.conf")
    new("""set -e
sudo mv /tmp/site.conf /etc/nginx/sites-available/officeplus
sudo ln -sf /etc/nginx/sites-available/officeplus /etc/nginx/sites-enabled/officeplus
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx""")

def step_check():
    new(f"""set -e
sleep 6
echo "WP:    $(curl -s -o /dev/null -w %{{http_code}} -H 'Host: {DOMAIN}' http://127.0.0.1/)"
echo "Flask: $(curl -s -o /dev/null -w %{{http_code}} http://127.0.0.1:8000/login)"
echo "Shop:  $(curl -s -o /dev/null -w %{{http_code}} -H 'Host: {DOMAIN}' http://127.0.0.1/cos)" """)
    print(f"""
==== ГОТОВО ====
1. Проверить в браузере: http://{NEW_IP}/  (Host-заголовок {DOMAIN} — через /etc/hosts)
2. nic.md: A-запись {DOMAIN} и www -> {NEW_IP}
3. После DNS: ssh на новый сервер и
   sudo apt-get install -y certbot python3-certbot-nginx && sudo certbot --nginx -d {DOMAIN} -d www.{DOMAIN}
Пароль БД WordPress записан только в wp-config.php на новом сервере.""")

STEPS = {"base": step_base, "wp": step_wp, "flask": step_flask,
         "nginx": step_nginx, "check": step_check}

if __name__ == "__main__":
    names = sys.argv[1:] or list(STEPS)
    for n in names:
        print(f"\n===== {n} ====="); STEPS[n]()

#!/usr/bin/env python3
"""Шаг 1. Полный ЛОКАЛЬНЫЙ архив проекта officeplus.md с живого сервера.

Полностью автономный скрипт: только python3 + ssh/scp в PATH, никаких
зависимостей от репозитория. Забирает с боевого сервера ВСЁ, что нужно для
разворачивания на чистой машине:

    code.tar.gz        Flask-приложение /home/ubuntu/artgranit (без venv)
                       вместе с .env (секреты! архив держать под chmod 700)
    wallets.tar.gz     Oracle wallet'ы /home/ubuntu/oracle_wallets
    ic.tar.gz          Oracle Instant Client /opt/oracle
    wp_files.tar.gz    WordPress /var/www/officeplus
    wp_db.sql.gz       дамп MySQL-базы officeplus_wp
    nginx_site.conf    /etc/nginx/sites-available/officeplus
    wp-harden.conf     /etc/nginx/snippets/wp-harden.conf (если есть)
    artgranit.service  systemd-юнит Flask
    MANIFEST.json      источник, дата, коммит, размеры, sha256

Запуск:
    python3 make_archive.py --src-ip 92.5.130.1 \
        --src-key ~/Keys/oracle-ecommerce-web --out ./archives

Результат — папка ./archives/officeplus_YYYYMMDD_HHMM/ + сводка на экран.
Разворачивание: deploy_archive.py (шаг 2), документация: README.md.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

SSH_OPT = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15"]


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd[:8]), "…" if len(cmd) > 8 else "")
    return subprocess.run(cmd, check=True, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src-ip", default=os.environ.get("OP_SRC_IP", "92.5.130.1"))
    ap.add_argument("--src-key", default=os.environ.get(
        "OP_SRC_KEY", os.path.expanduser("~/Keys/oracle-ecommerce-web")))
    ap.add_argument("--src-user", default="ubuntu")
    ap.add_argument("--out", default="./archives")
    a = ap.parse_args()

    key = os.path.expanduser(a.src_key)
    if not os.path.exists(key):
        sys.exit(f"SSH-ключ не найден: {key}")
    host = f"{a.src_user}@{a.src_ip}"

    def ssh(script):
        return run(["ssh", "-i", key, *SSH_OPT, host, script])

    def pull(remote, local):
        run(["scp", "-q", "-i", key, *SSH_OPT, f"{host}:{remote}", local])

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out = os.path.abspath(os.path.join(a.out, f"officeplus_{stamp}"))
    os.makedirs(out, exist_ok=True)
    os.chmod(out, 0o700)                     # в архиве секреты (.env, wallet)

    print(f"\n=== Архив officeplus с {a.src_ip} -> {out} ===\n")

    # ── 1. собираем артефакты НА сервере (во временные файлы) ──────────
    ssh("""set -e
T=/tmp/op_arch; rm -rf $T; mkdir -p $T
# Flask: код + .env, без venv/кэшей (venv пересобирается при деплое)
sudo tar -C /home/ubuntu -czf $T/code.tar.gz \
    --exclude=artgranit/venv --exclude=artgranit/__pycache__ \
    --exclude='artgranit/**/__pycache__' --exclude=artgranit/backups artgranit
# Oracle: wallet + instant client
sudo tar -C /home/ubuntu -czf $T/wallets.tar.gz oracle_wallets
sudo tar -C /opt -czf $T/ic.tar.gz oracle
# WordPress: файлы + дамп базы (имя базы читаем из wp-config.php)
sudo tar -C /var/www -czf $T/wp_files.tar.gz officeplus
DB=$(sudo php -r 'include "/var/www/officeplus/wp-config.php"; echo DB_NAME;')
sudo mysqldump --single-transaction --quick --default-character-set=utf8mb4 \
    "$DB" | gzip > $T/wp_db.sql.gz
# конфигурация: nginx + systemd
sudo cp /etc/nginx/sites-available/officeplus $T/nginx_site.conf
sudo cp /etc/nginx/snippets/wp-harden.conf $T/wp-harden.conf 2>/dev/null || true
sudo cp /etc/systemd/system/artgranit.service $T/artgranit.service
cat /home/ubuntu/artgranit/DEPLOY_COMMIT 2>/dev/null > $T/DEPLOY_COMMIT || true
sudo chown -R $(whoami) $T""")

    # ── 2. забираем к себе ─────────────────────────────────────────────
    files = ["code.tar.gz", "wallets.tar.gz", "ic.tar.gz", "wp_files.tar.gz",
             "wp_db.sql.gz", "nginx_site.conf", "artgranit.service"]
    optional = ["wp-harden.conf", "DEPLOY_COMMIT"]
    for f in files:
        pull(f"/tmp/op_arch/{f}", os.path.join(out, f))
    for f in optional:
        try:
            pull(f"/tmp/op_arch/{f}", os.path.join(out, f))
        except subprocess.CalledProcessError:
            print(f"  (нет {f} — пропущено)")
    ssh("rm -rf /tmp/op_arch")

    # ── 3. манифест: размеры + sha256 ──────────────────────────────────
    manifest = {"source_ip": a.src_ip, "created": stamp,
                "commit": None, "files": {}}
    cpath = os.path.join(out, "DEPLOY_COMMIT")
    if os.path.exists(cpath):
        manifest["commit"] = open(cpath).read().strip()
    total = 0
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        if f == "MANIFEST.json" or not os.path.isfile(p):
            continue
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        size = os.path.getsize(p)
        total += size
        manifest["files"][f] = {"size": size, "sha256": h.hexdigest()}
    with open(os.path.join(out, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n=== ГОТОВО: {out} ===")
    for f, m in manifest["files"].items():
        print(f"  {f:<22} {m['size'] / 1048576:8.1f} MB")
    print(f"  {'ИТОГО':<22} {total / 1048576:8.1f} MB"
          f"   коммит: {manifest['commit'] or '—'}")
    print("\nВ архиве секреты (.env, wallet, дамп БД) — не выкладывать,"
          "\nхранить с правами 700. Дальше: python3 deploy_archive.py --help")
    return out


if __name__ == "__main__":
    main()

# Миграция officeplus.md: архив → новый сервер

Автономный комплект для полного переноса проекта officeplus.md (Flask-магазин
Biro26 + WordPress + Oracle-клиент) на чистый сервер. Ничего из репозитория не
импортирует — нужен только `python3` и `ssh`/`scp` в PATH.

| Файл | Назначение |
|---|---|
| `make_archive.py` | шаг 1 — полный локальный архив с боевого сервера |
| `deploy_archive.py` | шаг 2 — разворачивание архива на новый сервер |
| `wizard.py` | GUI-мастер ‹Назад›/‹Далее›, проводит весь процесс |
| `README.md` | этот документ |

## Что переносится

Архив (папка `archives/officeplus_YYYYMMDD_HHMM/`) содержит **всё** для
автономного разворачивания:

| Артефакт | Откуда на боевом | Что внутри |
|---|---|---|
| `code.tar.gz` | `/home/ubuntu/artgranit` | Flask-приложение + `.env` (без venv — пересобирается) |
| `wallets.tar.gz` | `/home/ubuntu/oracle_wallets` | Oracle wallet (подключение к БД OfficePlus 11g/ADB) |
| `ic.tar.gz` | `/opt/oracle` | Oracle Instant Client (thick-режим python-oracledb) |
| `wp_files.tar.gz` | `/var/www/officeplus` | файлы WordPress с плагинами (в т.ч. Social Analytics) |
| `wp_db.sql.gz` | MySQL `officeplus_wp` | дамп базы WordPress (+ таблицы `wp_op_social_*`) |
| `nginx_site.conf` | `/etc/nginx/sites-available/officeplus` | вся маршрутизация: WP на корне, Flask на `/UNA.md/`, `/api/`, красивые URL витрины |
| `wp-harden.conf` | `/etc/nginx/snippets/` | защита WP (deny xmlrpc, uploads/*.php, rate-limit wp-login) |
| `artgranit.service` | `/etc/systemd/system/` | systemd-юнит Flask |
| `MANIFEST.json` | — | источник, дата, коммит, размеры, sha256 |

> **Архив содержит секреты** (`.env`, wallet, дамп БД). Папка создаётся с
> правами 700; не выкладывать, не коммитить, передавать только по защищённым
> каналам.

## Требования

- **Машина оператора**: macOS/Linux, `python3` ≥ 3.9, `ssh`/`scp`.
  Для GUI — tkinter (`python3 -m tkinter` должен открыть окошко).
- **Боевой сервер** (источник): SSH-ключ пользователя `ubuntu` с sudo.
  Сервер не изменяется — только чтение.
- **Новый сервер**: чистый Ubuntu 24.04, ≥1 GB RAM (Oracle Always Free
  подходит — скрипт сам добавляет 2G swap и тюнит MariaDB/PHP под малую
  память), открытые порты 22/80/443, SSH-ключ `ubuntu` с sudo.
- **DNS**: доступ к A-записям домена (nic.md) — для финального переключения.

## Быстрый путь (GUI)

```bash
python3 tools/officeplus_migration/wizard.py
```

Мастер: Введение → Параметры → Архив → Проверка архива → Разворачивание →
Проверка/DNS → TLS. Параметры запоминаются в `migration.json`.

## Тот же путь руками (CLI)

### 1. Архив

```bash
python3 make_archive.py --src-ip 92.5.130.1 \
    --src-key ~/Keys/oracle-ecommerce-web --out ./archives
```

Итог ~200–400 МБ. Проверка целостности: `MANIFEST.json` (sha256 каждого файла).

### 2. Разворачивание

```bash
python3 deploy_archive.py \
    --archive ./archives/officeplus_20260815_1200 \
    --ip <НОВЫЙ_IP> --key ~/.ssh/new-server.key
```

Шаги (идут по порядку, можно перечислить подмножество, повторный запуск
безопасен):

| Шаг | Что делает |
|---|---|
| `base` | apt-пакеты (nginx, php8.3-fpm, mariadb, python3-venv, libpango для WeasyPrint), 2G swap, тюнинг под 1 GB RAM |
| `upload` | заливка артефактов архива в `/tmp` сервера |
| `flask` | код + `.env` + wallet + instant client (ldconfig, libaio.so.1 → t64), venv c `requirements.txt`, systemd-юнит |
| `wp` | файлы WP + база; **новый** пароль MySQL → `wp-config.php` и `WP_DB_PASSWORD` в `.env` Flask; wp-cli |
| `nginx` | конфиг из архива (SSL-строки временно вырезаются — сертификата ещё нет), снипет wp-harden, limit_req-зона |
| `harden` | fail2ban (sshd + wp-login), unattended-upgrades |
| `check` | живость: MariaDB, Flask `/login`, `/api/biro26/health` (коммит!), WP `/wp-json/`, витрина `/cos` |

### 3. DNS и TLS

1. Проверить по IP: `curl -H 'Host: officeplus.md' http://<НОВЫЙ_IP>/cos` → 200.
2. nic.md: A-записи `officeplus.md` и `www` → новый IP.
3. Когда DNS обновится:

```bash
python3 deploy_archive.py --archive ... --ip ... --key ... tls
```

`tls` ставит certbot, выпускает сертификат с редиректом HTTP→HTTPS; продление
автоматическое (systemd timer certbot).

4. Старый сервер гасить только после успешного `tls` и ручной проверки
   `https://officeplus.md/cos`, `/login`, `/api/biro26/health`.

## Проверка после миграции (чек-лист)

- [ ] `https://<домен>/` — главная витрины (WP-страницы тоже открываются);
- [ ] `https://<домен>/cos`, `/catalog`, `/produs/<COD>` — 200;
- [ ] `https://<домен>/login` — вход в бэк-офис (Flask, не wp-login!);
- [ ] `https://<домен>/api/biro26/health` — `ok: true`, коммит совпадает с
      `MANIFEST.json`;
- [ ] `https://<домен>/wp-admin/` — админка WP, меню Social Analytics на месте;
- [ ] заказ-тест: положить товар в корзину, сформировать счёт;
- [ ] `journalctl -u artgranit -n 50` — без ошибок Oracle (wallet виден).

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Flask 500, в логе `DPI-1047` | instant client не виден: проверить `/etc/ld.so.conf.d/oracle-instantclient.conf` и симлинк `libaio.so.1` (шаг `flask` делает оба) |
| `/login` открывает wp-login.php | затёрт nginx-конфиг: в архивном есть `location = /login` → Flask; повторить шаг `nginx` |
| WP «Error establishing a database connection» | пароль в `wp-config.php` ≠ MySQL: повторить шаг `wp` (он выставляет заново) |
| Картинки товаров не грузятся | это Flask `/static/` и `/api/biro26/img` — проверить `systemctl status artgranit` |
| certbot: challenge failed | DNS ещё не указывает на новый IP — подождать и повторить `tls` |

## Замечания

- Пароль MySQL WordPress **генерируется заново** при каждом деплое и живёт
  только на новом сервере (wp-config.php + `.env`); из архива старый пароль
  нигде не используется.
- Отчётный sidecar (jsreport, node ≥ 22) в комплект не входит: на контуре
  officeplus PDF-отчёты ходят через WeasyPrint (ставится шагом `base`,
  libpango). Если нужен jsreport — см. `docs/Biro26/PROJECT_BIRO26.md`.
- Скрипты предполагают пользователя `ubuntu` с sudo без пароля (стандарт
  облачных образов Ubuntu). Другой пользователь: `--user`/`--src-user`.

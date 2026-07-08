# BIRO26 — Руководство по миграции на другой хостинг (для ИИ и людей)

> Цель: перенести модуль **Biro26** (часть Flask-платформы Artgranit) на любой новый
> Linux-хост с нуля, без доступа к старому серверу. Все команды готовы к копированию.
> Язык команд: bash (Ubuntu 22.04/24.04). Проверено на текущем проде
> `https://nufarul.eminescu.md/` (Ubuntu, systemd + nginx + Let's Encrypt).

---

## 1. Что такое Biro26 (минимальный контекст)

| Что | Значение |
|---|---|
| Тип | Модуль Flask-платформы Artgranit (один процесс `app.py` на всё) |
| Назначение | Работа с ERP OfficePlus: прайс-листы по периодам, товары/остатки, импорт, публичный магазин с саморегистрацией клиентов и счетами на оплату |
| БД модуля | **Oracle 11g** `officeplus @ orange.una.md:4024/cloudbd.world` (внешняя ERP-база, НЕ мигрирует — к ней только подключаемся) |
| Ключевая особенность | Oracle 11g требует **thick mode** → нужен Oracle **Instant Client** на хосте; thick-инициализация изолирована в подпроцессе-воркере (`models/biro26_worker.py`), основной Flask остаётся thin |
| UI-маршруты | `/UNA.md/orasldev/biro26` (лаунчер), `/UNA.md/orasldev/biro26-backoffice` (backoffice, 8 вкладок), `/UNA.md/orasldev/biro26-shop` (публичный магазин) |
| API | ~67 маршрутов `/api/biro26/...` (backoffice — за сессионной auth; `/api/biro26/shop/*` — публичные) |

### Архитектура подключения к Oracle (важно понять до миграции)

```
Flask (thin oracledb, платформенная ADB-база через wallet)
  └─ per-request subprocess: models/biro26_worker.py
       └─ oracledb.init_oracle_client(lib_dir=BIRO26_INSTANT_CLIENT)  ← ТОЛЬКО здесь thick
       └─ connect(officeplus / BIRO26_DB_DSN)
```

Контракт воркера: JSON `{success, columns, data, rowcount, message}`;
методы `execute_query / execute_dml / execute_script (атомарно в одной сессии) /
call_proc (DBMS_OUTPUT)`. **Никогда не вызывать `init_oracle_client` в основном
процессе** — это whole-process переключение, сломает thin-подключение платформы.

---

## 2. Инвентарь файлов модуля

```
app.py                                  # маршруты biro26 (искать "biro26")
config.py                               # секция BIRO26_* (строки ~105-118)
controllers/biro26_controller.py
models/biro26_db.py                     # клиент подпроцесс-воркера
models/biro26_worker.py                 # ЕДИНСТВЕННОЕ место thick-init
models/biro26_oracle_store.py           # весь SQL-слой
models/biro26_sources.py                # источники-SELECT (guard)
models/biro26_ai.py                     # AI-помощник импорта
templates/biro26/backoffice.html        # backoffice (монолит, i18n ru/ro/en)
templates/biro26/shop.html              # публичный магазин (фасетные фильтры)
static/biro26/backoffice-tabs.js
sql/biro26/01_biro26_app_tables.sql     # YBIRO_MAP_PROFILE и пр.
sql/biro26/02_biro26_sources.sql        # YBIRO_SRC_DEF
sql/biro26/03_biro26_stock_tables.sql   # YBIRO_STOCK_CALC(+_ITEM), GTT
sql/biro26/04_y_ai_biro26.sql           # YBIRO_CLIENT + пакет y_ai_BIRO26
deploy_biro26_app_tables.py             # идемпотентные DDL-деплойеры
deploy_biro26_sources.py
deploy_biro26_stock_tables.py
deploy_biro26_shop.py
tests/test_biro26.py                    # 56 unit-тестов (mock-БД, без сети)
docs/Biro26/                            # README_BIRO26.html, DEV_MARFA_STOC.md, TZ
```

Объекты в схеме `OFFICEPLUS` (создаются деплойерами, уже существуют в ERP-базе —
при миграции хостинга их создавать заново НЕ нужно): таблицы `YBIRO_*`,
секвенции/триггеры к ним, пакет `y_ai_BIRO26` (счета на оплату SYSFID=12280,
цены по периодам через `VTPR1D_PERPRLIST`).

---

## 3. Переменные окружения (`.env` в корне проекта)

```bash
# --- платформа Artgranit (основная ADB-база через wallet) ---
DB_USER=ADMIN
DB_PASSWORD=<секрет>
WALLET_DIR=/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q   # АБСОЛЮТНЫЙ путь, ВНЕ каталога деплоя
DEFAULT_USERNAME=ADMIN
DEFAULT_PASSWORD=<секрет>            # логин веб-интерфейса
ENVIRONMENT=REMOTE
PORT=8000                            # слушает только 127.0.0.1

# --- модуль Biro26 (ERP OfficePlus, Oracle 11g) ---
BIRO26_DB_USER=officeplus
BIRO26_DB_PASSWORD=<секрет>          # только в .env, никогда в коде/репо
BIRO26_DB_DSN=orange.una.md:4024/cloudbd.world
BIRO26_INSTANT_CLIENT=/opt/oracle/instantclient_19_28   # путь на НОВОМ хосте
# опционально: BIRO26_NLS_LANGUAGE=ENGLISH, BIRO26_NLS_TERRITORY=AMERICA
```

Секреты переносить вручную (из старого `.env` или менеджера секретов) —
в git их нет. Wallet платформы тоже вне git и вне deploy-архива.

---

## 4. Пошаговая миграция на новый хост

### 4.1 Система и Python

```bash
sudo apt update && sudo apt install -y python3.12-venv python3-pip nginx unzip libaio1t64 || sudo apt install -y libaio1
# libaio обязателен для Instant Client (на 24.04 пакет называется libaio1t64)
sudo ln -sf /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 2>/dev/null || true
```

### 4.2 Oracle Instant Client (обязателен: 11g → thick mode)

```bash
sudo mkdir -p /opt/oracle && cd /opt/oracle
# Basic (Lite недостаточно, если нужны все NLS) x86_64; версия 19c или 23c Free
wget https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linuxx64.zip
sudo unzip -o instantclient-basic-linuxx64.zip
ls -d /opt/oracle/instantclient_*        # запомнить точный путь → в .env BIRO26_INSTANT_CLIENT
```

Замечания по версии клиента:
- Linux 19c и 23c подключаются к 11.2 нормально;
- на macOS сборка 23.3 давала `ORA-28041` против этой базы — работала 23.26;
  если увидите ORA-28041/ORA-3134, попробуйте другую мажорную версию клиента.

### 4.3 Код и venv

```bash
sudo mkdir -p /home/ubuntu/artgranit && sudo chown $USER /home/ubuntu/artgranit
cd /home/ubuntu/artgranit
git clone https://github.com/PavelTuhari/Artgranit.git .   # или tar-архив со старого хоста
python3 -m venv venv
./venv/bin/pip install -r requirements.txt                  # ключевое: Flask, oracledb>=2.0
```

При переносе tar-архивом исключить: `backups/`, `venv*/`, `.git/`,
`AccountingDemoXcode/`, `*.pyc`. Wallet НЕ класть в архив.

### 4.4 Wallet платформы и .env

```bash
sudo mkdir -p /home/ubuntu/oracle_wallets
# скопировать каталог wallet_* со старого хоста (scp) или из бэкапа секретов
scp -r old-host:/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q /home/ubuntu/oracle_wallets/
nano /home/ubuntu/artgranit/.env         # заполнить по разделу 3 (пути нового хоста!)
```

### 4.5 Смоук-тест Oracle ДО настройки сервисов

```bash
cd /home/ubuntu/artgranit
./venv/bin/python -c "
from models.biro26_db import Biro26DB
r = Biro26DB().execute_query('SELECT COUNT(*) FROM TMS_UNIVERS WHERE ROWNUM<=1')
print(r.get('message') or 'BIRO26 DB OK')"
# ожидание: BIRO26 DB OK. Ошибки:
#  DPI-1047  -> неверный BIRO26_INSTANT_CLIENT или нет libaio
#  ORA-28041 -> сменить версию Instant Client
#  ORA-12170/12541 -> нет сетевого доступа к orange.una.md:4024 (открыть firewall/NAT!)
```

> **Сетевой pre-flight**: новый хост обязан достучаться до `orange.una.md:4024`:
> `nc -zv orange.una.md 4024`. Если ERP-база за VPN — сначала VPN.

### 4.6 DDL модуля (только если объектов YBIRO_* ещё нет в officeplus)

База officeplus — общая ERP; при обычной смене хостинга объекты уже существуют.
Проверка и (идемпотентный) деплой:

```bash
./venv/bin/python -c "
from models.biro26_db import Biro26DB
r = Biro26DB().execute_query(\"SELECT object_name,status FROM user_objects WHERE object_name LIKE 'YBIRO%' OR object_name='Y_AI_BIRO26'\")
print(r['data'])"
# если пусто/не хватает — выполнить по порядку:
./venv/bin/python deploy_biro26_app_tables.py
./venv/bin/python deploy_biro26_sources.py
./venv/bin/python deploy_biro26_stock_tables.py
./venv/bin/python deploy_biro26_shop.py          # YBIRO_CLIENT + пакет y_ai_BIRO26
```

### 4.7 systemd

```bash
sudo tee /etc/systemd/system/artgranit.service >/dev/null <<'EOF'
[Unit]
Description=Artgranit Flask (incl. Biro26)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/artgranit
EnvironmentFile=/home/ubuntu/artgranit/.env
ExecStart=/home/ubuntu/artgranit/venv/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now artgranit
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login   # → 200
```

**Перезапуск — только `sudo systemctl restart artgranit`** (никогда pkill+nohup:
процесс уйдёт из-под systemd и не поднимется после ребута).

### 4.7a jsReport (печатные формы корзины: счёт на оплату + заказ)

Отдельный Node.js-сервис `reports/` (порт `127.0.0.1:5488`); Flask ходит в него
по `JSREPORT_URL` (по умолчанию `http://127.0.0.1:5488`). Шаблоны Handlebars —
в `reports/templates/` (репозиторий), store jsReport не используется.

```bash
# Node 22+ (jsreport >=4.10 требует >=22.18) + зависимости Chromium (Ubuntu 24.04: имена с t64)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs
sudo apt-get install -y libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
  libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 \
  libpango-1.0-0 libcairo2 libasound2t64 fonts-dejavu-core
# при <1.5 GB RAM обязателен swap 2GB (см. free -m; fallocate -l 2G /swapfile ...)

cd /home/ubuntu/artgranit/reports && npm install --no-audit --no-fund

sudo tee /etc/systemd/system/jsreport.service >/dev/null <<'EOF'
[Unit]
Description=jsReport service (Artgranit reports sidecar)
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/artgranit/reports
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5
Environment=NODE_ENV=production
MemoryHigh=450M
MemoryMax=600M

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now jsreport
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5488/   # → 200 (старт ~20-30 c)
```

Второй движок **pdfme** работает в том же сервисе (`POST /pdfme/generate`,
без Chromium); активный движок per-форма — `reports/templates/engines.json`,
переключается в админке шаблонов (`/UNA.md/orasldev/biro26-report-templates`),
визуальный редактор — `/UNA.md/orasldev/biro26-pdfme-designer`.

Реквизиты продавца на формах — env `BIRO26_FIRM_*` (см. `config.py`), НДС —
`BIRO26_TVA_RATE` (включён в цену, по умолчанию 20). Проверка после миграции:
`GET /api/biro26/shop/report/invoice/<cod>` с сессией клиента → `application/pdf`
(первый рендер ~20 с — холодный старт Chromium). Если jsreport лежит, счёт всё
равно создаётся; API вернёт `report service unavailable`.

### 4.8 nginx + SSL

```bash
DOMAIN=your.new.domain
sudo tee /etc/nginx/sites-available/$DOMAIN >/dev/null <<EOF
server {
    listen 80; server_name $DOMAIN;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header Upgrade \$http_upgrade;      # WebSocket
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        client_max_body_size 16M;
    }
}
EOF
sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d $DOMAIN          # HTTPS + автопродление (таймер certbot)
```

### 4.9 Чек-лист верификации после миграции

```bash
D=https://your.new.domain
curl -s -o /dev/null -w 'login: %{http_code}\n'      $D/login                                  # 200
curl -s -o /dev/null -w 'backoffice: %{http_code}\n' $D/UNA.md/orasldev/biro26-backoffice      # 200/302
curl -s -o /dev/null -w 'shop: %{http_code}\n'       $D/UNA.md/orasldev/biro26-shop            # 200
curl -s "$D/api/biro26/shop/products?limit=1" | head -c 120                                    # success:true + товар
curl -s "$D/api/biro26/shop/tree"   | head -c 80                                               # success:true
curl -s "$D/api/biro26/shop/brands" | head -c 80                                               # success:true
# функционально: регистрация клиента в магазине -> корзина -> "Создать счёт на оплату"
# -> проверить документ: SELECT * FROM VMDB_DOCS_WORK WHERE COD=<cod>;
```

Юнит-тесты (без сети, mock-БД): `./venv/bin/python -m pytest tests/test_biro26.py -q` → 56 passed.

---

## 5. Обновление кода на уже мигрированном хосте (штатный цикл)

```bash
# с машины разработчика: только изменённые файлы, .env и wallet не трогаются
tar czf - app.py controllers/biro26_controller.py models/biro26_oracle_store.py \
  templates/biro26/ static/biro26/ sql/biro26/ \
  | ssh -i <key> ubuntu@<host> "cd /home/ubuntu/artgranit && tar xzf - \
      && sudo systemctl restart artgranit \
      && curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login"
# если менялась Oracle-схема: дополнительно выполнить нужный deploy_biro26_*.py
```

## 6. Диагностика

| Симптом | Причина / действие |
|---|---|
| `DPI-1047 Cannot locate Oracle Client` | Неверный `BIRO26_INSTANT_CLIENT`, нет libaio, клиент другой разрядности |
| `ORA-28041` при connect | Несовместимая версия Instant Client с 11g — сменить версию |
| `ORA-12170 / 12541` | Нет сети до `orange.una.md:4024` (firewall, VPN, security-list облака) |
| `worker timeout after N s` | Сеть до ERP медленная/висит; проверить `nc -zv`, увеличить таймаут в `models/biro26_db.py` |
| 502 на домене | Flask упал: `sudo systemctl status artgranit`, `journalctl -u artgranit -n 100` |
| Пакет INVALID | `SELECT text FROM user_errors WHERE name='Y_AI_BIRO26' ORDER BY sequence;` затем повторить `deploy_biro26_shop.py` |
| Грид «висит» на первой странице | См. правило: поисковые предикаты только как pre-resolved `u.COD IN (...)`, не OR/EXISTS в тяжёлом join |

## 7. Правила, которые нельзя нарушать (из CLAUDE.md проекта)

1. Действующий продакшен-домен не ломать; после любого изменения runtime —
   `curl -I https://<домен>/login` → 200.
2. `init_oracle_client` — только в `models/biro26_worker.py`.
3. Wallet и `.env` — вне git и вне deploy-архивов; `WALLET_DIR` — абсолютный путь.
4. Пароль officeplus — только в `.env`.
5. Все новые Oracle-объекты модуля — с префиксом `YBIRO_`/пакет `y_ai_BIRO26`,
   нормализованные таблицы, DDL-файл в `sql/biro26/` + идемпотентный деплойер.
6. Перезапуск только через systemd.

---
*Файл: `docs/Biro26/MIGRATION_BIRO26.md`. Актуален на 2026-07-07
(коммиты по PR #12/#13: цены по периодам, публичный магазин, фасетные фильтры).*

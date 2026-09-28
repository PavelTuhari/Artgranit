# DEPLOY: https://nufarul.eminescu.md/myloyalwalletcard (сервер 92.5.3.187)

Развёрнуто 2026-08-03. **Рабочий адрес: `https://nufarul.eminescu.md/myloyalwalletcard`** —
размещено путём на существующем HTTPS-домене (свой поддомен ждёт DNS, см. ниже).
Приложение собрано с `basePath: /myloyalwalletcard` (env `NEXT_BASE_PATH` при сборке).
Сервер тот же, что Artgranit (`/home/ubuntu/artgranit`, порт 8000) — его контур не тронут;
в конфиг nufarul добавлен ТОЛЬКО отдельный `location /myloyalwalletcard` (бэкап: `~/nginx_nufarul.bak.*`),
после правки: nufarul /login → 200, artgranit:8000 → 200.

## Топология

```
Интернет ──▶ nginx :80/:443 ──▶ 127.0.0.1:3010  Next.js standalone (systemd: myloyalwallet)
                                        │
                                        └──▶ 127.0.0.1:3306  MariaDB 10.11, БД loyalty_platform
```

| Компонент | Значение |
|---|---|
| Приложение | `/home/ubuntu/myloyalwalletcard` (standalone-сборка, `node server.js`) |
| Systemd unit | `/etc/systemd/system/myloyalwallet.service` (User=ubuntu, PORT=3010, MemoryMax=400M, Restart=always) |
| Env (внутри unit) | `DATABASE_URL=mysql://loyalty:loyalty123@127.0.0.1:3306/loyalty_platform`, `AUTH_SECRET`, `NEXT_PUBLIC_BASE_URL=https://myloyalwalletcard.eminescu.md` |
| Nginx | `/etc/nginx/sites-available/myloyalwalletcard.eminescu.md` → proxy 3010 |
| БД | `loyalty_platform`, пользователь `loyalty`/`loyalty123` (localhost), данные перенесены дампом с Mac |
| Node на сервере | v22 (уже стоял — «работающее ядро» переиспользовано, ничего не устанавливалось) |
| SSH | `ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187` (из `Artgranit/.env`) |

## Свой поддомен (опционально) — ждёт DNS

Авторитетные NS (`alfa.dns.md`/`beta.dns.md`) **не знают** поддомен — Let's Encrypt получил NXDOMAIN.
Нужно в панели DNS зоны `eminescu.md` добавить запись:

```
myloyalwalletcard.eminescu.md.  A  92.5.3.187
```

После появления записи (проверка: `dig +short myloyalwalletcard.eminescu.md @8.8.8.8`) выполнить на сервере:

```bash
sudo certbot --nginx -d myloyalwalletcard.eminescu.md --non-interactive --agree-tos -m ptuhari@gmail.com --redirect
```

До этого сайт работает по основному адресу `https://nufarul.eminescu.md/myloyalwalletcard`
(nginx-сайт myloyalwalletcard.eminescu.md оставлен — заработает сразу после появления DNS,
но потребует пересборки без basePath либо редиректа / → /myloyalwalletcard).

## Проверка / управление

```bash
SSH='ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187'
$SSH 'systemctl status myloyalwallet --no-pager | head -5'
$SSH 'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3010/api/health'   # → 200
$SSH 'sudo journalctl -u myloyalwallet -n 50 --no-pager'                            # логи
$SSH 'sudo systemctl restart myloyalwallet'                                         # рестарт
```

## Как деплоилось (первичный полный деплой)

1. Локально: `output: "standalone"` в next.config.ts, `binaryTargets = ["native","debian-openssl-3.0.x"]` в schema.prisma, `npx next build`.
2. Бандл: `.next/standalone` + `.next/static` + `public` + schema → tar.gz **43 MB** → scp.
3. БД: `mysqldump` локальной `loyalty_platform` (16 KB gz) → импорт в MariaDB сервера, создание пользователя.
4. systemd unit + `enable --now`, nginx site + reload.
5. Отдельно дослан linux-движок Prisma (`libquery_engine-debian-openssl-3.0.x.so.node`) — на macOS его нет в standalone.

**Обновления так больше не делаем** — см. `SYNC_MINIMAL_TRAFFIC.md`: типовой апдейт уезжает rsync-ом за 1–3 MB.

## Откат

```bash
# приложение хранит только текущую версию; перед рискованным апдейтом:
$SSH 'cp -a /home/ubuntu/myloyalwalletcard /home/ubuntu/myloyalwalletcard.prev'
# откат:
$SSH 'sudo systemctl stop myloyalwallet && rm -rf /home/ubuntu/myloyalwalletcard \
  && mv /home/ubuntu/myloyalwalletcard.prev /home/ubuntu/myloyalwalletcard \
  && sudo systemctl start myloyalwallet'
# БД: перед миграциями схемы
$SSH 'sudo mysqldump --no-tablespaces loyalty_platform | gzip > /home/ubuntu/mlwc_db_$(date +%Y%m%d_%H%M%S).sql.gz'
```

## Архивы

- Исходники: `MyLoyalWalletCard/MyLoyalWalletCard_deploy_YYYYMMDD_HHMMSS.tar.gz` (без node_modules/.next, ~300 KB)
- Правило сервера (из CLAUDE.md Artgranit) действует и здесь: после ЛЮБОЙ операции на сервере —
  `curl -I` по соседним сервисам (artgranit:8000, nufarul-конфиг не трогать).

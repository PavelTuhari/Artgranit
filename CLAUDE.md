# CLAUDE.md

Этот файл фиксирует обязательные инженерные правила для AI-агентов и разработчиков, которые добавляют или изменяют модули в проекте Artgranit.

## Главный принцип

Новые модули должны сразу проектироваться как Oracle-first и normalized-first.

Это означает:

1. бизнес-данные модуля хранятся в Oracle;
2. схема данных нормализована;
3. у модуля есть собственный префикс Oracle-объектов;
4. код, dashboards, docs и deploy обновляются согласованно.

## Критический production-инвариант

`https://nufarul.eminescu.md/` нельзя ломать.

Для любого AI-агента и разработчика это правило обязательное:

1. Не менять backend port, `systemd` unit, `WorkingDirectory`, virtualenv, `.env`, `nginx` `proxy_pass`, `server_name` или SSL-конфиг по отдельности, если это может уронить `https://nufarul.eminescu.md/`.
2. Любые изменения remote runtime или deploy-контура считаются незавершёнными, пока не подтверждено:
   `curl -I https://nufarul.eminescu.md/login`
3. Если домен начал отдавать `502`, `504`, `403`, неверный сертификат или перестал открываться после чьих-то правок, первая задача агента: восстановить `https://nufarul.eminescu.md/`, а не продолжать разработку.
4. Если в `/home/ubuntu/artgranit` уже работает другая модель или другой runtime-контур, нельзя “поверх” переключать порт или путь запуска без проверки live-домена.
5. Production URL `https://nufarul.eminescu.md/` важнее локальных экспериментов, временных рефакторингов и новых модулей.

## Что запрещено

Нельзя повторять следующие паттерны:

1. `APP_RUNTIME_KV`, `MODULE_RUNTIME_KV` и любые generic key-value таблицы для primary state;
2. `APP_EVENT_LOG` как общий контейнер для разных доменных данных;
3. хранение заказов, материалов, настроек, вариантов, статусов и других сущностей модуля в одном JSON blob;
4. использование `data/*.json`, `data/*.jsonl` или SQLite как authoritative storage;
5. добавление модуля без DDL, object prefix и документации.

## Обязательный шаблон для нового модуля

При создании нового модуля нужно сделать все пункты ниже.

### 1. Oracle-модель данных

1. Выбрать короткий префикс модуля, например `DECOR`, `NUF`, `CRED`.
2. Создать нормализованные таблицы по сущностям.
3. Разделить master-data, settings, documents, document items, metrics, statuses и logs.
4. Если нужен event log, сделать отдельную append-only таблицу модуля.

Примеры правильного подхода:

1. `DECOR_ORDERS` + `DECOR_ORDER_ITEMS`
2. `DECOR_SETTINGS` + дочерние таблицы значений
3. `CRED_EVENT_LOG` как отдельный event log

### 2. DDL и deploy

1. Добавить SQL-файл в `sql/`.
2. Включить этот файл в порядок выполнения в `deploy_oracle_objects.py`.
3. Проверить, что `deploy_to_remote.sh` недостаточно для новых Oracle-объектов: он переносит код, но по умолчанию не запускает DDL.
4. Если релиз модуля меняет Oracle-схему, отдельно выполнить `python deploy_oracle_objects.py` или remote deploy с `DEPLOY_ORACLE_ON_REMOTE=1`.

### 2a. Oracle wallet на remote

1. Oracle wallet не считать частью application source tree.
2. На remote wallet должен храниться вне каталога деплоя, например в `/home/ubuntu/oracle_wallets/...`.
3. В remote `.env` `WALLET_DIR` должен быть абсолютным путём.
4. Нельзя полагаться на то, что wallet приедет на сервер вместе с обычным deploy архива кода.
5. Если по историческим причинам wallet лежит внутри проекта относительным путём, deploy обязан сохранить и восстановить его до миграции на внешний путь.

### 3. Backend и storage

1. Не добавлять новый модуль через local-file storage как временное решение.
2. Если нужен storage helper, он должен работать с нормализованными таблицами Oracle.
3. Публичный API storage-слоя может возвращать nested dict для совместимости UI, но persistence под ним должна оставаться нормализованной.
4. Если раньше существовал файл-источник для bootstrap, он может использоваться только для одноразовой миграции/seed, а не как постоянное хранилище.

### 4. UI и маршруты

1. Все UI-маршруты должны жить под `/UNA.md/orasldev/...`.
2. Нужно добавить admin/operator/viewer маршруты в `app.py` и связанные templates/static assets.
3. Если модуль попадает в dashboards, обновить `dashboards/dashboard_*.json` и документацию в `docs/dashboards/`.
4. Нельзя оставлять устаревшие dashboard queries, которые смотрят на generic runtime tables.

### 5. Документация

Каждый новый модуль обязан иметь:

1. описание Oracle-объектов и их префикса;
2. описание UI-маршрутов;
3. описание API;
4. инструкцию локального запуска;
5. инструкцию remote deploy;
6. checklist верификации после релиза.

Минимум нужно обновить:

1. `README.md`
2. профильный файл в `docs/dashboards/` или `docs/`
3. при необходимости `docs/PROJECT_DOCUMENTATION.html` или генератор этой документации

## Checklist перед завершением задачи

Перед тем как считать модуль готовым, проверить:

1. в коде нет SQLite/file-based authoritative state;
2. в коде нет generic runtime-table names вроде `APP_RUNTIME_KV`;
3. Oracle-объекты модуля реально существуют и видны в `USER_OBJECTS`;
4. dashboards и docs используют актуальные названия таблиц;
5. локальный запуск работает;
6. remote deploy обновляет код без потери `.env`, а remote wallet остаётся доступным по `WALLET_DIR`;
7. после deploy рабочий URL находится под `/login` и `/UNA.md/orasldev/...`, а не под абстрактным `/UNA.md/`.

## Отдельные правила для Artgranit

1. DECOR уже переведен на нормализованные `DECOR_*` таблицы. Не возвращать его к KV/blob storage.
2. Кредитный лог хранится в `CRED_EVENT_LOG`. Это event log, а не общий state store.
3. `deploy_to_remote.sh` разворачивает код в `/home/ubuntu/artgranit`.
4. Production Oracle wallet хранится вне каталога деплоя: `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`.
5. Remote root URL может редиректить на `/login`; это нормальное поведение. Рабочий модульный URL: `/UNA.md/orasldev/...`.

## Production infrastructure — точная конфигурация сервера

Зафиксировано по состоянию на 2026-04. Менять эти параметры можно только синхронно, с проверкой `https://nufarul.eminescu.md/` после каждого изменения.

### Flask / systemd

| Параметр | Значение |
|---|---|
| Сервис | `/etc/systemd/system/artgranit.service` |
| User | `ubuntu` |
| WorkingDirectory | `/home/ubuntu/artgranit` |
| ExecStart | `/home/ubuntu/artgranit/venv/bin/python3 app.py` |
| EnvironmentFile | `/home/ubuntu/artgranit/.env` |
| PORT | `8000` (только localhost: `127.0.0.1:8000`) |
| ENVIRONMENT | `REMOTE` |
| Python venv | `/home/ubuntu/artgranit/venv/` (Python 3.12) |

Перезапускать приложение только через:
```bash
sudo systemctl restart artgranit
```

Проверить статус:
```bash
sudo systemctl status artgranit
journalctl -u artgranit -f
```

**Нельзя** перезапускать через `pkill` + `nohup` — это уводит процесс из-под systemd, и при следующем restart сервера приложение не поднимется.

### Nginx

Конфиг: `/etc/nginx/sites-enabled/` (домен `nufarul.eminescu.md`)

- HTTP (80) → редирект 301 на HTTPS (кроме `.well-known/acme-challenge/`)
- HTTPS (443) → `proxy_pass http://127.0.0.1:8000`
- WebSocket поддержка: `Upgrade`, `Connection: upgrade`, `proxy_read_timeout 86400`
- `client_max_body_size 16M`
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options

Перезапустить nginx после изменений:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### SSL

- Провайдер: Let's Encrypt (certbot)
- Сертификат: `/etc/letsencrypt/live/nufarul.eminescu.md/fullchain.pem`
- Ключ: `/etc/letsencrypt/live/nufarul.eminescu.md/privkey.pem`
- Автопродление: certbot systemd timer + cron (`0 */12 * * *`)
- Продление не требует ручного вмешательства, пока сервер доступен по HTTP для ACME-challenge

Проверить сертификат:
```bash
certbot certificates
```

### Oracle Wallet

- Путь: `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`
- В `.env`: `WALLET_DIR=/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`
- Wallet **не входит** в deploy-архив и не должен туда попадать

### Проверка production после любых изменений

```bash
# 1. Flask слушает
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login  # → 200

# 2. Домен отвечает через nginx + SSL
curl -I https://nufarul.eminescu.md/login  # → HTTP/2 200

# 3. Статус сервиса
sudo systemctl status artgranit --no-pager
```

## Если нужно быстро принять решение

Используй этот приоритет:

1. normalized Oracle tables;
2. explicit module prefix;
3. separate DDL deploy;
4. synced docs and dashboards;
5. verified local and remote routes.

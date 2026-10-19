# Восстановление инфраструктурных панелей TBControl — 02.09.2026

## Что случилось

Проверка по правилу №2 CLAUDE.md показала (см. [INDEX.md](INDEX.md), раздел 7):
код сервисов Zabbix через mTLS, Proxmox и сертификатов **затёрт** другой
сессией и в git не попал. В ADB остались таблицы `TBC_SERVICES` (36 строк),
`TBC_PVE_OBJECTS` (58), `TBC_CERTS` (3), представления `V_TBC_*_STATS`,
источники `zbx-svc-unisim` / `pve-proxmox3` с mTLS-колонками и события
`source in ('zabbix_svc','proxmox')`. Маршрут `/api/tbc/services` в `app.py`
остался и падал с `AttributeError` (500).

Поиск по всем веткам и worktree (`git log --all -S`) ничего не дал —
восстановлено **заново**, схема снята с `USER_TAB_COLUMNS` / `USER_CONSTRAINTS` /
`USER_VIEWS`, формат событий — с уцелевших строк `TBC_EVENTS`.

## Что сделано (по правилу №2: логика — отдельными файлами)

| Файл | Назначение |
|---|---|
| `models/tbc_mtls.py` | mTLS-транспорт к шлюзу: ключ из Keychain → временный файл 0600, `MtlsClient`, `/health`, секреты `keychain:<svc>/<acct>`, общий upsert событий `sync_events()` |
| `models/tbc_services.py` | Zabbix JSON-RPC → `TBC_SERVICES`; правила `classify_kind`, `service_status`; события `zabbix_svc`; секция AI-досье `service` |
| `models/tbc_proxmox.py` | PVE API → `TBC_PVE_OBJECTS`; правило `pve_health`; события `proxmox`; секция AI-досье `pve` |
| `models/tbc_certs.py` | TLS-рукопожатие → `TBC_CERTS`; статусы OK/EXPIRING/EXPIRED/ERROR; события `certs`; CRUD доменов |
| `controllers/tbc_infra_routes.py` | Blueprint: `GET/POST /api/tbc/proxmox[/sync]`, `GET/POST /api/tbc/certs`, `POST /api/tbc/certs/check`, `DELETE /api/tbc/certs/<id>` |
| `controllers/tbcontrol_controller.py` | **только вызовы в одну строку**: `get_services`, `sync_services`, `get_proxmox`, `sync_proxmox`, `get_certs`, `save_cert`, `delete_cert`, `check_certs`; виды источников `zabbix_svc`/`proxmox` в `save_source`/`test_source`; ветки `service`/`pve` в `generate_dossier`; очистка `TBC_SERVICES`/`TBC_PVE_OBJECTS` в `delete_source` |
| `app.py` | одна строка `app.register_blueprint(tbc_infra_bp)`; старые маршруты `/api/tbc/services*` не тронуты |
| `static/tbcontrol/tbc_infra.js` | панели «Сервисы Zabbix», «Proxmox», «Сертификаты»; подключается отдельным `<script>` |
| `templates/tbcontrol.html` | разметка трёх панелей, раздел меню «Инфраструктура», поля mTLS в модалке источника |
| `sql/79b_tbc_services_mtls.sql` | mTLS-колонки `TBC_SOURCES`, `CHK_TBC_SRC_KIND` с `zabbix_svc`/`proxmox`, `TBC_SERVICES` + views + seed источника |
| `sql/79c_tbc_dossier_types.sql` | `CHK_TBC_DSR_SRC`: + `service`, `cassa`, `store`, `pve` |
| `sql/79d_tbc_proxmox.sql` | `TBC_PVE_OBJECTS` + `V_TBC_PVE_STATS` + seed источника |
| `sql/79e_tbc_certs.sql` | `TBC_CERTS` + `V_TBC_CERTS_STATS` + 3 домена |
| `deploy_oracle_objects.py` | зарегистрированы `79_…79e_` (79 тоже не был в списке) |
| `tests/test_tbcontrol_infra.py` | 20 тестов без Oracle/сети: правила, DDL, «одна строка в контроллере», маршруты |
| `docs/TBControl/MTLS_SOURCE.md` | паспорт шлюза, ключей и синхронизации |

Объекты в ADB **уже существуют** — DDL 79b–79e нужны для новой БД и как
документация; повторный прогон на ADB даст ошибки «уже существует», это
ожидаемо (установщик продолжает).

## Что выяснилось по дороге

1. Шлюз отдаёт `/proxmox/` уже как `/api2/json/` — первый вариант кода
   дублировал префикс и получал `401 No ticket`.
2. PVE 4.4 в `/nodes` не отдаёт поле `status` — нода определяется по `uptime`;
   иначе синхронизация «теряла» все 57 дочерних объектов.
3. Приватный ключ действительно только в Keychain (`tbc-zabbix-client-key` /
   `tbc-zabbix-mtls`), файла `client.key` на диске нет.

## Как проверить

```bash
venv/bin/python -m pytest tests/test_tbcontrol_infra.py -q       # 20 passed
curl -s http://localhost:3003/api/tbc/services | head -c 120      # {"success": true, ...}
curl -s 'http://localhost:3003/api/tbc/proxmox?health=CRIT' | head -c 120
curl -s http://localhost:3003/api/tbc/certs | head -c 120
```

Живой прогон 02.09.2026: Zabbix 3.4.15 — 37 хостов, 2 PROBLEM; Proxmox 4.4-1 —
58 объектов (1 нода, 35 VM, 16 LXC, 6 хранилищ), 2 CRIT; сертификаты — 3 OK,
ближайший истекает через 33 дня.

Страховка от повторной потери:

```bash
grep -rn "tbc_services\|tbc_proxmox\|tbc_certs" --include=*.py --include=*.html --include=*.js . | head
```

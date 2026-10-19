# mTLS-источники: сервисы Zabbix и Proxmox через шлюз 192.168.0.148

**Восстановлено 02.09.2026** (первая версия утеряна, см. [INFRA_RESTORE_20260902.md](INFRA_RESTORE_20260902.md)).

## Зачем шлюз

Zabbix `unisim-soft.com` (3.4.15) и Proxmox VE 4.4 (PROXMOX3, `192.168.0.149:8006`)
живут в LAN и не имеют своей защиты уровня «только этот компьютер». Между ними
и TBControl стоит nginx на `192.168.0.148:8443` с обязательным клиентским
сертификатом (mTLS): без валидного сертификата шлюз отвечает `400`, с ним —
проксирует.

| Локация шлюза (`/etc/nginx/conf.d/tbc-zabbix-mtls.conf`) | Куда | В TBControl |
|---|---|---|
| `/api_jsonrpc.php` | Zabbix JSON-RPC | источник `zbx-svc-unisim`, `API_URL = https://192.168.0.148:8443/api_jsonrpc.php` |
| `/proxmox/` | `https://192.168.0.149:8006/api2/json/` | источник `pve-proxmox3`, `API_URL = https://192.168.0.148:8443/proxmox` |
| `/health` | 200 при валидном сертификате | `MtlsClient.health()` в «🔌 Проверить связь» |

**Важно про пути Proxmox:** шлюз уже подставляет `/api2/json`, поэтому
`…/proxmox/access/ticket` → 200, а `…/proxmox/api2/json/access/ticket` → 401
«No ticket» (проверено 02.09.2026). Код строит пути от `API_URL` напрямую.

## Где лежат ключи

| Что | Где | В `TBC_SOURCES` |
|---|---|---|
| Клиентский сертификат | `/Users/pt/Keys/tbc-zabbix-mtls/client.crt` | `CERT_PATH` |
| CA шлюза | `/Users/pt/Keys/tbc-zabbix-mtls/ca.crt` | `CA_PATH` (проверка сервера) |
| Отпечаток клиента (SHA-256) | — | `CERT_FINGERPRINT` |
| **Приватный ключ** | **только macOS Keychain**: `security find-generic-password -s tbc-zabbix-client-key -a tbc-zabbix-mtls` | `KEY_KEYCHAIN_SVC` / `KEY_KEYCHAIN_ACC` |
| Пароль Zabbix `Admin` | `API_SECRET` | — |
| Пароль Proxmox `root@pam` | `API_SECRET` — строка **или** ссылка `keychain:<service>/<account>` | — |

Ключ на диске проекта не хранится: `models/tbc_mtls.py` читает его из
Keychain на время процесса, кладёт во временный файл `0600` в каталоге
`tbc-mtls-*` и удаляет при выходе. На Linux (nufarul) Keychain нет — там
задаётся `TBC_MTLS_KEY_PATH=/путь/к/client.key` в окружении; без него источник
отвечает понятной ошибкой, а не 500.

Секрет формата `keychain:proxmox3-ssh/root` читается той же командой
`security` и в Oracle не попадает.

## Что делает синхронизация

### Сервисы Zabbix (`models/tbc_services.py` → `TBC_SERVICES`)

1. `apiinfo.version`, `user.login` (для 3.x — параметр `user`).
2. `host.get` с группами, интерфейсами, шаблонами и доступностью агента.
3. `trigger.get value=1` — активные проблемы, группируются по хосту.
4. Тип сервиса по словам в имени/группах/шаблонах: `db` (oracle, mysql, standby…),
   `mail`, `network` (mikrotik, router…), `web` (apache, nginx, домены), иначе `server`.
5. Статус: `DISABLED` (хост выключен) · `PROBLEM` (High/Disaster) ·
   `WARN` (любая проблема или агент недоступен) · `OK`.
6. Upsert по `(SOURCE_CODE, ZBX_HOSTID)`, пропавшие хосты удаляются.
7. События `source='zabbix_svc'`, corr `svc-<source>-<hostid>`: только для
   `PROBLEM`, с приоритетом худшего триггера; ушедшие из PROBLEM закрываются.

### Proxmox (`models/tbc_proxmox.py` → `TBC_PVE_OBJECTS`)

1. `POST /access/ticket` → cookie `PVEAuthCookie`.
2. `/nodes`, для живой ноды `/nodes/<n>/status` (PVE 4.4 в `/nodes` не отдаёт
   `status` — нода считается online по `uptime`), `/qemu`, `/lxc`, `/storage`.
3. HEALTH по порогам: диск 85/95 %, CPU 75/90 %, RAM 90/97 %; нода не online → CRIT.
   Остановленная VM — не проблема (половина машин выключена намеренно).
4. Upsert по `(SOURCE_CODE, OBJ_TYPE, OBJ_ID)`, пропавшие объекты удаляются.
5. События `source='proxmox'`, corr `pve-<type>-<id>`: CRIT → P2, нода offline → P1.

## Проверка

```bash
# шлюз жив (без сертификата — 400, это норма)
curl -sk -o /dev/null -w '%{http_code}\n' https://192.168.0.148:8443/health

# из проекта (нужен VPN93 и Keychain этого Mac)
venv/bin/python -c "
from models import tbc_mtls, tbc_services, tbc_proxmox
print(tbc_services.test_source(tbc_mtls.source_row('zbx-svc-unisim')))
print(tbc_proxmox.test_source(tbc_mtls.source_row('pve-proxmox3')))"
# → {'success': True, 'version': '3.4.15', 'gateway': 'OK', 'hosts': 37, ...}
# → {'success': True, 'version': '4.4-1',  'gateway': 'OK', 'nodes': 1, ...}

curl -s http://localhost:3003/api/tbc/services | head -c 200   # "success": true
```

Типовые ошибки: `Шлюз /health: HTTP 400` — сертификат не принят (проверить
`CERT_PATH`, отпечаток, срок); `Keychain: ключ … не найден` — нет записи в
связке ключей этого пользователя; `Proxmox: неверный логин/пароль (401)` —
`API_SECRET`; `401 No ticket` — в `API_URL` лишний `/api2/json`.

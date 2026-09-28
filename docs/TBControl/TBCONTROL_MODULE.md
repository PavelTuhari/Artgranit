# TBControl — модуль эксплуатации Front Office, POS, Self-Service и Android

Реализация целевой архитектуры из ТЗ [TECHNICAL-OPS.md](TECHNICAL-OPS.md) в движке Artgranit.
Главный принцип: **мониторим не компьютер, а способность магазина выполнять бизнес-операции**
(«Can the store sell?»).

Интерфейс выполнен в стилистике NOC-консолей Cisco (DNA Center / Prime) и Unify OpenScape:
тёмная тема, левая навигация по доменам, health-плитки магазинов, приоритеты P1–P4.

## Oracle-объекты (префикс `TBC_`)

DDL: `sql/70_tbc_tables.sql`, представления: `sql/71_tbc_views.sql`,
демо-данные: `sql/72_tbc_demo_data.sql`. Все три файла включены в
`deploy_oracle_objects.py`.

### Справочники

| Таблица | Содержимое |
|---|---|
| `TBC_REF_DEVICE_TYPES` | POS, SCO, AND, SRV, NET, PRN |
| `TBC_REF_SEVERITIES` | P1–P4 (раздел 23 ТЗ) с цветами для UI |
| `TBC_REF_CHANNELS` | Release channels: DEV / TEST / PILOT / PRODUCTION (раздел 31) |
| `TBC_REF_SUPPORT_GROUPS` | customer_it, developer, service_desk, management (раздел 36) |
| `TBC_REF_SERVICES` | Модель «Everything is a service»: network, pos, sco, android, store_app, payment, fiscal, inventory, sync, api, database (раздел 3.1) |

### Master data и операционные таблицы

| Таблица | Назначение |
|---|---|
| `TBC_STORES` | Магазины: код `MD-CHS-001`, maintenance window (раздел 33) |
| `TBC_DEVICES` | Технический паспорт устройства (раздел 9): serial, asset, ОС, IP/MAC, владелец, support group, criticality + текущие метрики (CPU/RAM/Disk, для Android — battery/storage/pending ops), `LAST_SEEN`/`LAST_SYNC` |
| `TBC_APPLICATIONS` | Реестр приложений: Expected Version/Build, release channel, Health API URL (разделы 19, 30) |
| `TBC_DEVICE_APPS` | Установленные версии: Current vs Expected, статус OK/OUTDATED/FAILED/UNKNOWN |
| `TBC_HEALTH_CHECKS` | Append-only результаты диагностики компонентов (разделы 16, 39–40) |
| `TBC_EVENTS` | События P1–P4: сервис, correlation_id, `PARENT_EVENT_ID` для dependency-модели (root cause → suppressed, разделы 28–29) |
| `TBC_INCIDENTS` | Инциденты `INC-YYYY-NNNNN`: lifecycle new→assigned→diagnosing→resolving→verification→closed, SLA deadline, RCA-поля (root/tech cause, business impact, resolution, corrective/preventive action — раздел 57) |
| `TBC_CHANGES` | Изменения `CHG-YYYY-NNNN`: приложение, версия, rollback plan, deployment window, validation (раздел 55) |
| `TBC_CHANGE_STORES` | Магазины в scope изменения |
| `TBC_DEPLOY_CHECKS` | Deployment verification: process/version/health/database/api/sync/peripheral/business (раздел 32) |
| `TBC_SLA_TARGETS` | Целевые и фактические SLA по сервисам (раздел 51) |
| `TBC_EVENT_LOG` | Append-only аудит действий пользователей модуля (раздел 38) |

### Monitoring / Processing / AI (разделы 72–75 ТЗ, DDL `sql/73_tbc_processing.sql`, демо `74_tbc_processing_demo.sql`)

| Таблица | Назначение |
|---|---|
| `TBC_METRIC_SAMPLES` | Append-only time series телеметрии касс: `SCOPE` hw (касса-компьютер) / app (Front Office), метрики cpu/ram/disk/battery и app_latency/tx_count/app_errors. Источник — heartbeat агентов |
| `TBC_NODES` | Узлы обработки: промежуточные серверы магазинов (1..N на магазин), центральный сервер, бэк-офис. Три уровня контроля: HW (CPU/RAM/Disk), приложение обмена (версия/статус), БД (`DB_ENGINE`: oracle/sqlite/mssql/mysql/postgres + версия/статус/размер/соединения) |
| `TBC_FLOWS` | Потоки обмена: касса (SQLite) → сервер магазина → центральный → бэк-офис. Статусы OK/LAGGING/STALLED/FAIL, lag в минутах, накопленные pending-строки, последняя ошибка |
| `TBC_FLOW_LOG` | Append-only журнал батчей (отправлено/принято/статус/ошибка) |
| `TBC_AI_DOSSIERS` | MD-досье сбоев для внешних AI-провайдеров: CLOB + per-документ `ACCESS_TOKEN`, счётчик прочтений, статус new/sent/analyzed/resolved |

### Представления

`V_TBC_DEVICES`, `V_TBC_STORE_HEALTH` (агрегированный STORE_HEALTH =
OK/DEGRADED/CRITICAL по правилам раздела 20), `V_TBC_VERSIONS`,
`V_TBC_EVENTS`, `V_TBC_INCIDENTS`, `V_TBC_CHANGES`, `V_TBC_DASHBOARD_STATS`,
`V_TBC_NODES`, `V_TBC_FLOWS`, `V_TBC_PROC_STATS`.

## UI-маршруты

| Маршрут | Описание |
|---|---|
| `/UNA.md/orasldev/tbcontrol` | SPA operations-центра (требует логин). Панели: Обзор сети (Executive dashboard, раздел 34), Магазины, Устройства (фильтры POS/SCO/Android + деталка с паспортом, софтом и диагностикой), Приложения, Версии ПО, Изменения/Deploy, События, Инциденты, SLA, Журнал аудита |

## API (`/api/tbc/*`)

| Endpoint | Метод | Назначение |
|---|---|---|
| `/stats`, `/store-health`, `/refs` | GET | Дашборд, health магазинов, справочники |
| `/stores`, `/stores/<id>` | GET/POST/PUT/DELETE | CRUD магазинов |
| `/devices`, `/devices/<id>` | GET/POST/PUT/DELETE | CRUD устройств (фильтры store_id/device_type/status) |
| `/devices/<id>/diagnostics` | POST | Диагностический workflow по типу устройства (раздел 39), результат — в `TBC_HEALTH_CHECKS` + JSON-отчёт (раздел 40) |
| `/agent/heartbeat` | POST | **Приём heartbeat от агентов** (Zabbix Agent 2 / Android Monitoring Agent, разделы 7–8). Автоrегистрация нового устройства по коду (раздел 44), обновление метрик, сверка версии ПО с ожидаемой |
| `/applications`, `/applications/<id>` | GET/POST/PUT/DELETE | Реестр приложений; смена Expected Version пересчитывает статусы установок |
| `/versions` | GET | Распределение версий (фильтры app_id, status=OUTDATED) |
| `/events` | GET/POST | События (фильтры status=active/suppressed/resolved, severity, store_id) |
| `/events/<id>/ack`, `/resolve` | POST | Workflow события; resolve root cause автоматически закрывает suppressed-потомков |
| `/events/<id>/incident` | POST | Событие → инцидент: группа назначается по границе ответственности Customer IT / Developer (раздел 64), SLA-дедлайн по приоритету |
| `/incidents`, `/incidents/<id>` | GET/PUT | Инциденты, lifecycle + RCA |
| `/changes`, `/changes/<id>` | GET/POST | Изменения; деталка — scope и verification checks |
| `/changes/<id>/deploy` | POST | Deployment на целевые устройства + автоматическая verification; `DEPLOYMENT = SUCCESS/FAILED`; успешный PRODUCTION-deploy обновляет Expected Version |
| `/changes/<id>/rollback` | POST | Откат на rollback-версию |
| `/sla`, `/sla/<id>` | GET/PUT | SLA по сервисам |
| `/audit` | GET | Журнал аудита |
| `/init-demo` | POST | Создание TBC_*-объектов и загрузка демо-данных |
| `/monitor/overview` | GET | Сводка по кассам: NOW + агрегаты за сегодня и 7 дней, HW и APP раздельно (фильтры store_id, device_type) |
| `/monitor/series/<device_id>` | GET | Временные ряды: `scope=hw\|app`, `from`/`to` (произвольный период), `bucket=hour\|day` |
| `/proc/stats` | GET | Сводка Processing-центра (потоки по статусам, pending, узлы, сбои батчей за 24ч) |
| `/nodes` | GET/POST | Узлы обработки (фильтр node_type) |
| `/nodes/heartbeat` | POST | Heartbeat узла: HW + статус приложения + статус/размер/соединения БД |
| `/flows` | GET | Потоки (фильтр status=problems/OK/…, store_id) |
| `/flows/<id>/log` | GET | Журнал батчей потока |
| `/flows/<id>/report` | POST | Отчёт агента о батче: OK/FAIL/PARTIAL → пересчёт статуса потока по правилам 73.2 |
| `/flows/<id>/retry` | POST | Ручной повтор передачи накопленного pending |
| `/ai/dossiers` | GET | Список AI-досье |
| `/ai/dossiers/generate` | POST | Генерация досье: `{source_type: event\|incident\|flow\|node\|device, ref_id}` |
| `/ai/dossiers/<id>` | PUT | Статус досье (analyzed/resolved) |
| `/ai/dossier/<code>.md` | GET | **Выдача MD внешнему AI**: `?token=<ACCESS_TOKEN>` без сессии (или из UI с сессией); text/markdown |

### AI-досье (раздел 74 ТЗ)

Досье генерируется автоматически при создании инцидента из P1/P2-события и
вручную кнопкой 🤖 у события/инцидента/потока. Содержимое: контекст сбоя,
паспорт устройства/узла, метрики NOW + телеметрия 24ч, health checks,
версии ПО, потоки обмена с журналом батчей, STORE_HEALTH магазина, открытые
события и инструкция для AI-агента (порядок диагностики + whitelist-действия
через API). Секреты и credentials в документ не включаются — сервисный
токен для активных действий выдаётся отдельно через Secret Store.

### Формат heartbeat (раздел 8 ТЗ)

```json
{
  "device_id": "MD-CHS-001-AND-01",
  "status": "OK",
  "application": "storeapp_android",
  "version": "5.12.3",
  "battery": 87,
  "storage_free_mb": 32100,
  "network": true,
  "last_sync": "2026-08-08T00:01:12Z"
}
```

Неизвестный `device_id` автоматически регистрируется: магазин и тип
извлекаются из кода (`MD-CHS-001` + `AND`). Ответ содержит
`registered: true/false` и `version_status: OK/OUTDATED`.

## Локальный запуск

```bash
cd /Users/pt/Projects.AI/Artgranit
venv/bin/python app.py
# http://localhost:3003/UNA.md/orasldev/tbcontrol
```

Первичная инициализация схемы: кнопка «⚙ Инициализация» в top-bar модуля
или `python deploy_oracle_objects.py` (файлы 70–72 в порядке выполнения).

## Remote deploy

Стандартный контур nufarul: `./deploy_to_remote.sh` (код) + Oracle DDL отдельно —
`DEPLOY_ORACLE_ON_REMOTE=1` либо ручной `python deploy_oracle_objects.py` на сервере.
После деплоя обязательно:

```bash
curl -I https://nufarul.eminescu.md/login   # → HTTP/2 200
```

## Checklist верификации после релиза

1. `SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'TBC_%'` — 45+ объектов (17 таблиц, 15 триггеров, 13 sequences) + 7 `V_TBC_*` views.
2. `/UNA.md/orasldev/tbcontrol` открывается после логина, дашборд показывает магазины.
3. `POST /api/tbc/agent/heartbeat` с новым `device_id` регистрирует устройство.
4. Resolve P1-события закрывает suppressed-потомков.
5. `POST /api/tbc/changes/<id>/deploy` даёт `DEPLOYMENT = SUCCESS` и заполняет `TBC_DEPLOY_CHECKS`.
6. Журнал аудита пишется (`TBC_EVENT_LOG`).

## Соответствие ТЗ и ограничения текущей версии

Модуль реализует управляющий контур платформы (inventory, версии, события,
инциденты, изменения, SLA, диагностика, heartbeat-API). Zabbix остаётся
внешним источником телеметрии: интеграция предполагается через
`POST /api/tbc/agent/heartbeat` и `POST /api/tbc/events` (webhook из Zabbix
actions). Диагностика и deployment verification в текущей версии —
симуляция на стороне сервера (реальные проверки выполняют агенты на
устройствах). Observability-stack (логи/трейсы) — вне scope модуля
(раздел 42 ТЗ).

# TBControl — полная документация системы

**TBControl** — операционный центр (Operations Center) торговой сети:
мониторинг, диагностика и сопровождение магазинов, POS/SCO-касс,
Android-устройств, софта Front Office и цепочки обмена данными от кассы до
бэк-офиса. Принцип: **«мониторим не компьютер, а способность магазина
продавать»**. Интерфейс — NOC-консоль в стилистике Cisco DNA / Unify.

## Живые ссылки (production)

| Что | URL |
|---|---|
| 🖥️ **Рабочая панель** | [https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol) |
| 🎞 **Презентация** (слайды с live-кнопками) | [https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol/presentation](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol/presentation) |
| 📖 **Эта документация онлайн** | [https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol/docs](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol/docs) |

Прямые ссылки на панели (deep-link по `#`): [дашборд](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#dashboard) ·
[мониторинг касс](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#monitor) ·
[processing](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#processing) ·
[события](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#events) ·
[инциденты](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#incidents) ·
[отчёт «Динамика»](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#report) ·
[AI-досье](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#dossiers) ·
[инвайты](https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol#invites).
Локально — то же на `http://localhost:3003`. Доступ без пароля — по хэш-инвайту (`?h=…`, раздел 4).

- **Oracle:** префиксы `TBC_*` (мониторинг/операции) и `INV_*` (инвайты), общая ADB обоих контуров
- **Презентация (файл):** [presentation.html](presentation.html)

---

## 1. Карта документации (все MD-файлы)

| Документ | Что внутри |
|---|---|
| [TECHNICAL-OPS.md](TECHNICAL-OPS.md) | **ТЗ / целевая архитектура** (75 разделов): Zabbix-платформа, business-first мониторинг, инвентарь и идентификация устройств (§9–10), приоритеты P1–P4 и корреляция (§23–29), версии ПО и deployment verification (§30–32), Service Desk и границы ответственности (§35–36), диагностика (§39–40), SLA (§51), change management и RCA (§55–57), авторемедиация и её запреты (§61–62), Monitoring Center (§72), Processing Center (§73), AI-досье (§74) |
| [TBCONTROL_MODULE.md](TBCONTROL_MODULE.md) | **Справочник реализации**: все таблицы `TBC_*` и представления `V_TBC_*`, полный перечень API `/api/tbc/*`, формат heartbeat, AI-досье, локальный запуск, remote deploy, checklist верификации релиза |
| [SCENARIOS.md](SCENARIOS.md) | **10 кейсов полезности** на демо-сети франшизы (Bonus / Super Bonus / Local / Local Expres / Foxi, 11 магазинов) + эмулятор и подключение реального Zabbix |
| [PRESENTATION_GOOGLE_LM.md](PRESENTATION_GOOGLE_LM.md) | Исходник для генерации презентации в Google NotebookLM: позиционирование, архитектура, сценарии, структура 13 слайдов |
| [INDEX.md](INDEX.md) | этот документ — сводный вход |

Смежные документы проекта:

- [../../README.md](../../README.md) — раздел «TBControl» в общем README движка Artgranit;
- `/Users/pt/cursorsprojects/UnisimProxm/Proxmox/zabbix/README.md` — паспорт реального Zabbix 3.4.15 (zabbix34, LXC на PROXMOX3), учётки, хосты, изменения от 2026-08-12;
- CLAUDE.md проекта — инженерные правила (Oracle-first, normalized-first, деплой).

## 2. Состав системы

| Блок | Панели UI | Данные |
|---|---|---|
| Мониторинг сети | Обзор (Executive, STORE_HEALTH-плитки), Мониторинг касс (HW/APP-контуры: сейчас · день · неделя · период), Магазины, Устройства (паспорт §9 ТЗ + диагностика) | `TBC_STORES`, `TBC_DEVICES`, `TBC_METRIC_SAMPLES`, `TBC_HEALTH_CHECKS` |
| Софт | Приложения (Expected Version, каналы DEV→TEST→PILOT→PRODUCTION), Версии ПО (OK/OUTDATED/FAILED), Изменения/Deploy (verification + rollback) | `TBC_APPLICATIONS`, `TBC_DEVICE_APPS`, `TBC_CHANGES`, `TBC_DEPLOY_CHECKS` |
| Processing | Processing центр: потоки POS (SQLite) → серверы магазина (1..N) → центральный → бэк-офис; узлы с контролем HW+приложение+БД (oracle/sqlite/mssql/mysql/postgres) | `TBC_NODES`, `TBC_FLOWS`, `TBC_FLOW_LOG` |
| Эксплуатация | События (корреляция root→suppressed), Инциденты (lifecycle + RCA), Отчёт «Динамика» (события по дням, **очереди на кассах**, действия персонала с фиксацией ненужных перезагрузок, обращения в поддержку/банки/MEV/электросети/ISP со временем реакции, климат/UPS), SLA, Журнал аудита | `TBC_EVENTS`, `TBC_INCIDENTS`, `TBC_ACTIONS`, `TBC_SUPPORT_TICKETS`, `TBC_ENV_SAMPLES`, `TBC_SLA_TARGETS`, `TBC_EVENT_LOG` |
| AI | AI-досье сбоев: MD-документ со всем контекстом, выдача внешнему AI по секретному токену | `TBC_AI_DOSSIERS` |
| Источники событий | 🧪 Эмулятор 10 сценариев по кругу / реальный **Zabbix 3.x–7.x** (user.login или API-token; trigger.get / problem.get) | `tbc_emulator.py`, `TBC_SETTINGS` |
| Администрирование | 🔗 Инвайты: ссылки `…?h=<hash>` с автологином | `INV_LINKS` |

## 3. Примеры кейсов (отдельно)

Полные описания — в [SCENARIOS.md](SCENARIOS.md). Кратко:

1. **Отключение света, магазин на UPS** — телеметрия батареи в реальном времени (100→36%), остаток минут работы, заявка в Premier Energy; диспетчер решает: генератор или ждать.
2. **Свет пропал, касса без UPS погасла** — видно, какие кассы не защищены; аргумент для дооснащения.
3. **Авария интернет-провайдера** — root cause «канал ISP down», банковский POS и MEV-очередь автоматически suppressed; банк отвечает «проблема у вас», тикет провайдеру. Персонал не дёргает лишние службы.
4. **Сбой процессинга банка при живом интернете** — кассир трижды зря перезагрузил кассу (зафиксировано как «ненужные перезагрузки»), банк подтвердил сбой за 8 минут; база для обучения персонала и претензий банку.
5. **Деградация MEV (SFS)** — фискализация по всей сети, offline-очереди чеков, тикет в SFS; отличается от «MEV не работает в одном магазине из-за интернета».
6. **Жара +38°C** — перегрев серверной магазина 26→34°C с троттлингом, просадки сети до 198V, связка с центральной серверной (30°C при UPS-нагрузке 78%).
7. **Мороз −18°C** — регламент прогрева оборудования, климат-телеметрия отрицательных диапазонов.
8. **Очереди на кассах** — сломанный SCO немедленно виден как рост очереди (max 9 человек) с подсветкой магазина.
9. **Задержки техподдержки** — время первой реакции по каждому адресату; задержка 247 минут подсвечена красным.
10. **AI-досье** — полный контекст любого сбоя для внешнего LLM по токен-ссылке, whitelist-действия для авторемедиации.

Реальный кейс интеграции: подключён боевой **Zabbix 3.4.15** сети Unisim — 18 активных проблем (cloudbd `/mnt/md3` < 3% — P1, диски PROXMOX3, «Oracle Wine: Stores OFFLINE», SSL) стали событиями TBControl; «шумовые» триггеры (Vetropack Standby, почта garileauto.md, SSL tnme.md) отключены навсегда через Zabbix API, и коннектор автоматически закрыл их события.

## 4. Хэш-инвайты (автологин по ссылке)

Панель **«🔗 Инвайты»** (раздел Администрирование) создаёт ссылки вида:

```text
https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol?h=43hhjghj34g5jh345hj
```

Механика: таблица `INV_LINKS` хранит связку **hash → модуль (target path) +
логин/пароль**. `before_request`-хук при заходе с `?h=<hash>` проверяет
инвайт (активен, не истёк, лимит использований не исчерпан), выполняет
автологин этими кредами и redirect'ом убирает хэш из адресной строки.

- срок действия (`EXPIRES_AT`) и лимит использований (`MAX_USES`) — опционально;
- учёт использований (`USES_COUNT`, `LAST_USED_AT`), пауза/включение/удаление;
- пароль наружу через API не отдаётся; управление — только авторизованным;
- DDL: `sql/78_invite_links.sql`; API: `GET/POST /api/tbc/invites`, `PUT/DELETE /api/tbc/invites/<id>`.

## 5. Файлы системы

| Слой | Файлы |
|---|---|
| Oracle DDL | `sql/70_tbc_tables.sql` … `sql/77_tbc_settings.sql`, `sql/78_invite_links.sql` (все в `deploy_oracle_objects.py` и в init-demo модуля) |
| Backend | `controllers/tbcontrol_controller.py`, маршруты в `app.py` (`/api/tbc/*`, before_request инвайтов) |
| UI | `templates/tbcontrol.html` (монолитный SPA, без внешних библиотек) |
| Эмулятор/Zabbix | `tbc_emulator.py` (TBCEmulator, ZabbixConnector, EmulatorRuntime) |
| Docs | `docs/TBControl/*.md`, `docs/TBControl/presentation.html` |

## 6. Запуск и деплой

```bash
# локально
venv/bin/python app.py           # http://localhost:3003/UNA.md/orasldev/tbcontrol

# Oracle-объекты (или кнопка «⚙ Инициализация» в UI)
venv/bin/python deploy_oracle_objects.py

# эмулятор сценариев из CLI
venv/bin/python tbc_emulator.py --interval 60

# подключение реального Zabbix 3.x из CLI
venv/bin/python tbc_emulator.py --mode zabbix \
  --zabbix-url http://192.168.0.110/zabbix/api_jsonrpc.php \
  --zabbix-user Admin --zabbix-password '...'

# remote deploy (контур nufarul) + обязательные проверки
./deploy_to_remote.sh
curl -I https://nufarul.eminescu.md/login          # → HTTP/2 200
```

Особенность: Zabbix живёт в LAN `192.168.0.0/24` — коннектор запускается с
локального инстанса; production видит все события через общую Oracle ADB.

---

## 6. Мониторинг инфраструктуры: cloudbd, PROXMOX3, OTRS (09.2026)

| Документ | Что внутри |
|---|---|
| [CLOUDBD_TEMP_MONITOR.md](CLOUDBD_TEMP_MONITOR.md) | **Перегрев CPU cloudbd/PROXMOX3**: диагностика («перезагрузки» не было — uptime 60 дн), сбор t° через coretemp → zabbix-агент, items `cpu.temp[1|2]`, триггеры >52℃ (average) / ≥60℃ (disaster), алерты в Telegram; end-to-end проверка на реальном превышении. Скрипты: [cloudbd_temp/](cloudbd_temp/) |
| [../OTRS/MAIL_QUEUE_DIAGNOSIS.md](../OTRS/MAIL_QUEUE_DIAGNOSIS.md) | **Дневные отчёты OTRS не доходили**: переполнение буфера `varchar2(4000)` в `send_email_api_php`, утечка HTTP-дескрипторов, отсутствие повторов; исправление в OTRS/TICKETS/GARABTA/VALORENERGY; скан 143 схем `cloudbd` |
| [MOBILE_APP_TZ.md](MOBILE_APP_TZ.md) | **ТЗ мобильного приложения** (iPhone): весь контур на одном экране, режим «привлечения внимания» при потере связи с Zabbix и при выходе за температурные режимы |
| `ios/TBControlMobile/` | Исходники iOS-приложения по ТЗ (SwiftUI, xcodegen) — см. README там же |

## 7. Состояние кода после 01.09.2026 — что утеряно

Проверка по правилу №2 CLAUDE.md показала: часть работы предыдущих сессий
**затёрта и не восстанавливается** (ни в git, ни на проде, ни в транскриптах):

| Утеряно | Что осталось |
|---|---|
| `models/zabbix_svc.py` (mTLS-источник сервисов Zabbix unisim-soft.com) | таблица `TBC_SERVICES` в ADB |
| `models/proxmox_svc.py` (источник Proxmox под сертификатом) | таблица `TBC_PVE_OBJECTS`, события `source=proxmox` в `TBC_EVENTS` |
| `sql/79b…79e_*.sql` (mTLS-колонки, типы досье, Proxmox, `TBC_CERTS`) | таблица `TBC_CERTS` в ADB |
| методы контроллера `get_services/sync_services/sync_proxmox/get_proxmox/get_certs/check_certs` | маршрут `/api/tbc/services` в `app.py` остался и отдаёт **500** |
| панели `services/proxmox` в `templates/tbcontrol.html`, `docs/TBControl/MTLS_SOURCE.md` | — |

Работающими остались: источники `emulator`/`zabbix`/`unisim_cassa`, Cassa
Monitor, AI-досье, инвайты, отчёты. Восстанавливать — заново и **только
изолированными файлами** (`models/tbc_*.py` + вызов в одну строку), как велит
правило №2.

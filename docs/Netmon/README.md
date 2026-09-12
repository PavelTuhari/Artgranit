# Мониторинг офиса: сеть и Telegram (`netmon`)

Изолированный модуль Artgranit: инвентарь устройств офисной сети, постановка
их на мониторинг Zabbix и наглядная витрина Telegram-каналов, в которые
Zabbix шлёт уведомления.

| Что | Где |
|---|---|
| URL | `/UNA.md/orasldev/netmon` |
| Пакет | `modules/netmon/` |
| Oracle-префикс | `NMON_` (DDL — `modules/netmon/sql/`, установщик — `modules/netmon/scripts/netmon_deploy.py`) |
| Тесты | `tests/test_netmon.py` (20 тестов, включая изоляцию) |
| Ветка / worktree | `feat/netmon` / `../Artgranit-netmon` |
| Внешние системы | Zabbix 3.4 `192.168.0.110` (JSON-RPC), Telegram Bot API |

**Полное описание системы мониторинга** — [MONITORING_SYSTEM.md](MONITORING_SYSTEM.md).
**Акт тестирования** — [TEST_REPORT.html](TEST_REPORT.html).

## Быстрый старт

```bash
cd /Users/pt/Projects.AI/Artgranit-netmon
python modules/netmon/scripts/netmon_deploy.py            # схема NMON_ в Oracle
python modules/netmon/scripts/netmon_zabbix_sync.py --scan  # что есть в сети
python modules/netmon/scripts/netmon_zabbix_sync.py --apply # завести недостающие
python -m pytest tests/test_netmon.py -q
```

Нужен туннель **VPN93** (подсеть `192.168.0.*`) и пароль Zabbix в Keychain:
`security find-generic-password -a Admin -s zabbix-web -w`.

## Журнал изменений

- **12.09.2026 — создание модуля.** Скан `192.168.0.0/24` нашёл 52 живых
  устройства, из них 38 не было в Zabbix — заведены в группу
  «Office Auto-Discovered» с шаблоном ICMP Ping, покрытие доведено до 100 %.
  Найдено 2 Telegram-канала, загружена лента из 1251 сообщения за 30 дней.
  Панель: сводка, устройства, каналы, лента. 20 тестов зелёные.
  Проверка: `pytest tests/test_netmon.py`; `git diff --name-only main HEAD` —
  только пути модуля.

- **12.09.2026 — план миграции Zabbix.** Обследована действующая система:
  Zabbix 3.4.15 на CentOS 7.9 / MariaDB 5.5 / PHP 5.6 (все сняты с поддержки),
  1,5 ГБ БД, 77 хостов, 2 734 элемента, 72 из них сломаны. Подготовлен
  [ZABBIX_MIGRATION_PLAN.md](ZABBIX_MIGRATION_PLAN.md) — переезд на Zabbix 8.0 LTS
  в новую KVM-ВМ на PROXMOX3, без простоя мониторинга. Добавлен инструмент
  `netmon_zabbix_export.py`; снята первая полная выгрузка конфигурации
  (53 шаблона, 75 хостов, 752 объекта, XML проверен разбором).

- **12.09.2026 — паспорта Proxmox и инструкция по миграции.** Решение владельца:
  историю сохраняем, база переносится целиком (Zabbix 8.0 поддерживает прямой
  апгрейд с 2.0 — цепочка версий не нужна). Добавлены разделы панели «Обзор Zabbix»
  (75 хостов, 1638 элементов, активные проблемы) и «Proxmox: машины» (51 гость,
  включая 31 выключенный, паспорт в один клик). Собрана пошаговая
  [MIGRATION_GUIDE.html](MIGRATION_GUIDE.html) — 23 шага с проверками.
  Найдено: в описаниях 18 ВМ хранятся пароли открытым текстом — на панель
  и в базу они не попадают.

---

## Развёртывание на боевом контуре

Модуль работает на двух контурах, и они **видят разное**:

| Контур | Адрес | Что показывает |
|---|---|---|
| Боевой (облако OCI) | https://nufarul.eminescu.md/UNA.md/orasldev/netmon | данные из Oracle: устройства, паспорта машин Proxmox, оборудование, домены, реестр доступов |
| Локальный (рабочая машина) | http://127.0.0.1:3013/UNA.md/orasldev/netmon | то же **плюс живой опрос**: Zabbix, Proxmox, розетки, синхронизация |

Причина различия: сеть офиса `192.168.0.0/24` доступна только через VPN93,
а боевой сервер стоит в облаке и в неё не попадает. Поэтому на боевом
контуре разделы «Обзор Zabbix» и управление розетками останутся пустыми —
это не поломка, а физическое ограничение. Кнопки синхронизации там тоже
работать не будут: их место — на рабочей машине.

Отдельно: раздел «Доступы» на боевом контуре показывает **прочерк** в
столбце статуса вместо «нет». Keychain существует только на macOS; сказать
«записи нет», не имея возможности проверить, было бы неправдой.

### Как выкатывать

Модуль изолированный, ядро подключает его само — общий код не трогается.
Точечный патч (у владельца слабый интернет, полный архив не гоняем):

```bash
cd /Users/pt/Projects.AI/Artgranit-netmon
COPYFILE_DISABLE=1 tar -czf /tmp/netmon.tar.gz \
  --exclude='__pycache__' --exclude='.DS_Store' --exclude='photos' --exclude='screenshots' \
  modules/netmon docs/Netmon tests/test_netmon.py
scp -i ~/.ssh/artgranit-oci.key /tmp/netmon.tar.gz ubuntu@92.5.3.187:/tmp/
ssh -i ~/.ssh/artgranit-oci.key ubuntu@92.5.3.187 \
  'cd /home/ubuntu/artgranit && tar -xzf /tmp/netmon.tar.gz && rm -f /tmp/netmon.tar.gz \
   && sudo systemctl restart artgranit'
curl -I https://nufarul.eminescu.md/login    # обязательная проверка: HTTP/2 200
```

Таблицы `NMON_*` ставить на боевом контуре **не нужно**: база Oracle общая
для обоих контуров, схема уже развёрнута.

Выкачено 12.09.2026, проверено: страница отдаёт 200, разделы «Устройства»
(44), «Оборудование» (11), «Proxmox» (51), «Домены» (5) работают.

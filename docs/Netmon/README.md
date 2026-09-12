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

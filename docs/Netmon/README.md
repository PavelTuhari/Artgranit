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

## Где модуль работает, а где нет

**Решение владельца 28.09.2026:** панель — только на рабочей машине
администратора и на сервере мониторинга во внутренней сети. На публичных
серверах её нет.

| Где | Адрес | Состояние |
|---|---|---|
| Рабочая машина | http://127.0.0.1:3013/UNA.md/orasldev/netmon | включено |
| Сервер мониторинга, внутренняя сеть | `192.168.0.110` (только через VPN) | включается флагом при установке |
| nufarul.eminescu.md и прочие публичные | — | **выключено, 404** |

Причина: модуль показывает устройство офисной сети, реестр доступов к
серверам и умеет выдавать ключи OpenVPN. Одного логина портала для этого
мало.

Как устроено (подробно — докстринг `modules/netmon/__init__.py`):

1. **Флаг `NETMON_ENABLED=1` в `.env`.** Без него ядро получает пустой
   blueprint — маршруты не импортируются, нет ни страницы, ни API.
   `.env` в архив деплоя не входит, поэтому модуль не включится на сервере
   случайно — деплоем, копированием каталога или чужой веткой.
2. **Сеть источника** (`routes._only_from_inside`, на весь blueprint):
   `127.0.0.0/8`, `::1`, `192.168.0.0/24`, `10.8.0.0/24`. Остальным — 404,
   а не 403: снаружи не видно даже того, что модуль существует.
   Переопределяется `NETMON_ALLOWED_NETS`.

Оговорка. На выключенном сервере в карте модулей и боковом меню остаётся
пункт «Мониторинг офиса», ведущий в 404: общий реестр
(`models/module_registry.py`) намеренно показывает модуль, у которого есть
манифест, но нет маршрутов, — чтобы отвалившийся модуль не исчезал молча.
Убрать пункт можно только правкой общего реестра, а правило №1 запрещает
трогать общий код в работе над модулем. Войти через этот пункт нельзя.

### Код на nufarul

Код модуля на nufarul лежит — его приносит общий деплой всего дерева, — но
выключен флагом. Обновлять его там нужно только затем, чтобы туда не
приехала версия без флага. Точечный патч:

```bash
cd /Users/pt/Projects.AI/Artgranit-netmon
COPYFILE_DISABLE=1 tar -czf /tmp/netmon.tar.gz \
  --exclude='__pycache__' --exclude='.DS_Store' --exclude='photos' --exclude='screenshots' \
  modules/netmon docs/Netmon tests/test_netmon.py
scp -i ~/.ssh/artgranit-oci.key /tmp/netmon.tar.gz ubuntu@92.5.3.187:/tmp/
ssh -i ~/.ssh/artgranit-oci.key ubuntu@92.5.3.187 \
  'cd /home/ubuntu/artgranit && tar -xzf /tmp/netmon.tar.gz && rm -f /tmp/netmon.tar.gz \
   && sudo systemctl restart artgranit'
curl -I https://nufarul.eminescu.md/login                                   # HTTP/2 200
curl -s -o /dev/null -w '%{http_code}\n' https://nufarul.eminescu.md/UNA.md/orasldev/netmon   # 404
```

Таблицы `NMON_*` живут в общей базе Oracle и остаются там: локальная
панель работает с ними же.

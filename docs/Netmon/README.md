# Мониторинг офиса: сеть и Telegram (`netmon`)

Изолированный модуль Artgranit поверх общего ядра. Создан `scripts/new_module.py`.

| Что | Где |
|---|---|
| URL | `/UNA.md/orasldev/netmon` |
| Пакет | `modules/netmon/` |
| Oracle-префикс | `NMON_` (DDL в `modules/netmon/sql/`, установщик `modules/netmon/scripts/netmon_deploy.py`) |
| Тесты | `tests/test_netmon.py` (изоляция + правила) |
| Ветка / worktree | `feat/netmon` / `../Artgranit-netmon` |

## Журнал изменений

- **создание каркаса** — worktree, ветка, пакет, тесты изоляции, документация.
  Проверка: `pytest tests/test_netmon.py`; `git diff --name-only main HEAD` — только свои пути.

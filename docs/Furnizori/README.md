# Работа с поставщиками (`furnizori`)

Изолированный модуль Artgranit поверх общего ядра. Создан `scripts/new_module.py`.

| Что | Где |
|---|---|
| URL | `/UNA.md/orasldev/furnizori` |
| Пакет | `modules/furnizori/` |
| Oracle-префикс | `FRZ_` (DDL в `modules/furnizori/sql/`, установщик `modules/furnizori/scripts/furnizori_deploy.py`) |
| Тесты | `tests/test_furnizori.py` (изоляция + правила) |
| Ветка / worktree | `feat/furnizori` / `../Artgranit-furnizori` |

## Журнал изменений

- **создание каркаса** — worktree, ветка, пакет, тесты изоляции, документация.
  Проверка: `pytest tests/test_furnizori.py`; `git diff --name-only main HEAD` — только свои пути.

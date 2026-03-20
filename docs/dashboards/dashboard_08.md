# Dashboard 08: Colass — Catalog + Estimator

## Назначение

Встроенный дашборд для модуля `cls` в Shell:
- каталог работ/ресурсов (F3/F5)
- сметчик с добавлением позиций и итогами

## Виджеты

1. `colass_catalog_embed`
- Тип: `embed`
- URL: `/UNA.md/orasldev/colass-catalog`
- Описание: дерево работ, поиск, нормы расхода

2. `colass_estimator_embed`
- Тип: `embed`
- URL: `/UNA.md/orasldev/colass-estimator`
- Описание: создание/правка сметы, totals по категориям

3. `documentation_08`
- Тип: `documentation`
- Dashboard ID: `08`

## Связанные маршруты

- `/UNA.md/orasldev/colass-catalog`
- `/UNA.md/orasldev/colass-estimator`
- `/api/colass/*`

## Источник данных

- Oracle schema `CLS_*`
- Демо-данные из F3/F5 (`sql/26_colass_demo_data.sql`)

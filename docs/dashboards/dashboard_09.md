# Dashboard 09: DECOR — Веранда / Стеклянная крыша

## Назначение

Shell-дашборд для проекта `DECOR`, чтобы проект открывался сразу в рабочих окнах DECOR, а не через кредитные дашборды `04/05`.

Включает:
- оператор приёма заказов (расчёт сметы + оформление лида/заказа),
- админку DECOR (материалы, коэффициенты, заказы, отчёт),
- HTML-материалы ТЗ проекта.

## Виджеты

1. `decor_operator_embed`
- Тип: `embed`
- URL: `/UNA.md/orasldev/decor-operator`

2. `decor_admin_embed`
- Тип: `embed`
- URL: `/UNA.md/orasldev/decor-admin`

3. `decor_docs_embed`
- Тип: `embed`
- URL: `/UNA.md/orasldev/docs/decor/`

4. `documentation_09`
- Тип: `documentation`
- Dashboard ID: `09`

## Связанные маршруты

- `/UNA.md/orasldev/decor-operator`
- `/UNA.md/orasldev/decor-admin`
- `/UNA.md/orasldev/decor-operator/document/<order_id>`
- `/UNA.md/orasldev/docs/decor/`
- `/api/decor-operator/*`
- `/api/decor-admin/*`

## Данные

- MVP fallback: `data/decor_store.json`
- Перспектива: Oracle-таблицы `DEC_*` (при следующем этапе)

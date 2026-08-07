# EasyCredit — рабочая интеграция через Request_v3

Статус на 2026-08-07: **заявки проходят.** Первая успешная —
`URN 001185129`, статус `Currently At Shop`.

## Какой сервис использовать

`Request_v3`. Не `eShopRequest_*` — это семейство **не для партнёрских
аккаунтов** (отвечает `Invalid Product or Product Not Found` при любых
параметрах). И не `Request_v4` — он дополнительно требует `ShopID`, тогда как
v3 выбирает магазин **автоматически по `Login`**.

Путь, которым это выяснялось:

| Что вызывали | Ответ |
|---|---|
| `eShopRequest_V5` / `_V4` | `Invalid Product or Product Not Found` — тупик, сервис не для партнёров |
| `Request_v4` без `ShopID` | `Process Failed! (Missing Shop!)` |
| `Request_v4` с `ShopID` 1 / 2 / 892 | `Process Failed! (Invalid Shop for User MTadmin)` |
| **`Request_v3`, Product 54** | **`OK`, URN выдан** |

## Обязательные поля Request_v3 (12)

`Login`, `Password`, `Product`, `UIN`, `ApDateOfBirth`, `ApFirstName`,
`ApLastName`, `CaMobile`, `GoodsName`, `CreditAmount`, `NumberOfInstallments`,
`FirstInstallmentDate`.

Все они собираются в форме корзины. `FirstInstallmentDate` считается как
сегодня + N дней (по умолчанию 31 — поле `FirstPaymentAfter` продукта).
Дополнительно отправляются `ApFatherName` и `GoodsPrice`, если известны.

## Продукт и сроки (среда TEST)

Магазину доступен **только продукт 54**, сроки **6–11 месяцев**,
суммы 100 – 80 000 лей. Проверено: 5 и 12 месяцев отклоняются
(`Invalid Product [54 / 591]`), 6 и 11 — принимаются.

Продукты 55 и 56 из `ECM_ShopProducts` **не наши** — на них приходит
`Invalid Product`.

Отсюда следствие для бэк-офиса: пакеты в `TMS_CREDITE_PLAN` со сроком вне
6–11 месяцев (например «Special 0% / 4 luni») для EasyCredit работать не
будут. Витрина об этом честно предупреждает, но лучше согласовать список.

## Настройки (бэк-офис → Provideri API)

| Параметр | Значение в TEST |
|---|---|
| `api_user` / `api_password` | `MTadmin` / пароль |
| `basic_user` / `basic_password` | `partener.ecredit.md` / пароль (HTTP Basic) |
| `product_id` | `54` |
| `first_installment_days` | `31` |

`ShopID` не нужен. Для PRODUCTION запросить у EasyCredit свой `Product`
и проверить сроки.

**Осторожно при сохранении настроек:** пустое значение НЕсекретного параметра
затирает сохранённое (правило «пусто = не менять» действует только для
секретов). Отправлять форму нужно со всеми заполненными полями.

## Обработка отказов

Технические коды кредитора заменяются понятным текстом:

- `Invalid Product` → «EasyCredit nu acceptă N rate pentru produsul
  configurat. Termene disponibile: 6-11 luni» (сроки берутся у **нашего**
  продукта, не из всего каталога);
- `There is already a loan ... with same UIN, Amount, Product` → «Există deja
  o cerere identică» — повтор той же суммы тем же клиентом отклоняется;
- незаполненные поля ловятся до отправки, чтобы не получать 422 с
  техническими именами полей.

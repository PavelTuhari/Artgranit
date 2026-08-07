# EasyCredit TEST — «Invalid Product or Product Not Found»

Диагностика от 2026-08-02. Кратко: **наша сторона исчерпана, нужен ответ
EasyCredit.** Учётная запись `MTadmin` в среде TEST не привязана к магазину,
поэтому процедура `InsertEShopRequest` не находит продукт.

## Что видно из их же API

| Операция | Результат |
|---|---|
| `ECM_ShopProducts` | **OK** — отдаёт 3 продукта (54, 55, 56) |
| `ECM_Shops` | **`Invalid User Name / Password - 50000`** — с теми же логином и паролем |
| `eShopRequest_V5` | `From SQL Exeqution dbo.InsertEShopRequest/130/Invalid Product or Product Not Found - 50000` |
| `eShopRequest_V4` | `From SQL Exeqution Invalid Product or Product Not Found - 50000` |
| `eShopGetRequests` | **OK** — 48 заявок, созданных пользователем `MTadmin`, с `ProductID` 54 и 56 |

Ключевое противоречие: список продуктов магазина отдаётся, а список магазинов
для того же пользователя — нет. Заявки раньше создавались успешно (48 штук,
`CreatedUser: MTadmin`), сейчас не создаются ни одна.

## Что проверено с нашей стороны (всё исключено)

- `ProductId` = 54, 55, 56, а также `ProductGroupID` 41002 и `ProductClassID`
  51018 — одинаковая ошибка;
- вообще без `ProductId` — та же ошибка;
- срок 6, 12, 13 месяцев — каждый в своём продукте по их же каталогу;
- сумма целым числом и с копейками; повтор точной суммы ранее успешной
  заявки (14999 при продукте 54) — та же ошибка;
- версии `eShopRequest_V5` и `V4` — обе упираются в тот же продукт, хотя идут
  через **разные** хранимые процедуры (`InsertEShopRequest` и
  `InsertEShopRequest_V2`).

Последнее и доказывает, что дело не в теле запроса: две независимые процедуры
не находят продукт для этого пользователя.

## Что просить у EasyCredit

> Contul `MTadmin` (partener `partener.ecredit.md`) în mediul **TEST**:
> `ECM_ShopProducts` întoarce corect produsele 54 / 55 / 56, dar `ECM_Shops`
> răspunde `Invalid User Name / Password`, iar `eShopRequest_V5` și `_V4`
> răspund `Invalid Product or Product Not Found` pentru orice ProductId și
> orice număr de rate. Anterior, cu același cont, s-au creat 48 de cereri
> (vizibile în `eShopGetRequests`, ProductID 54 și 56).
> Vă rugăm să verificați **legătura contului cu magazinul (shop)** în TEST și
> produsele active pe acel magazin.

## Отдельно: сроки рассрочки в бэк-офисе

Каталог EasyCredit в TEST предлагает только **6–11, 12 и 13–18** месяцев.
Пакет «Special 0% / 4 luni» в `TMS_CREDITE_PLAN` ни одному продукту не
соответствует — заявка на 4 месяца не может быть принята в принципе.

Витрина теперь говорит об этом прямо («EasyCredit nu oferă 4 rate. Termene
disponibile: 6-11, 12, 13-18 luni»), но правильнее убрать или отключить этот
пакет в `/UNA.md/orasldev/biro26-credit-admin`, чтобы клиент не выбирал срок,
который заведомо не пройдёт. Для боевой среды список продуктов будет свой —
проверить его тем же вызовом `ECM_ShopProducts` после переключения на
`PRODUCTION`.

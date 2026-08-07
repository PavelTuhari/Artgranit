# EasyCredit — партнёрский аккаунт: нужен ShopID

Уточнение владельца 2026-08-07: **семейство `eShopRequest_*` не для
партнёров.** Для нашего аккаунта правильный сервис — **`Request_v4`**.
Код переведён на него.

## Как менялась ошибка по мере уточнения

| Что вызывали | Ответ |
|---|---|
| `eShopRequest_V5` / `_V4` | `Invalid Product or Product Not Found - 50000` — тупик, сервис не для партнёров |
| `Request_v4` без `ShopID` | `Process Failed! (Missing Shop!)` |
| `Request_v4` с `ShopID` 1 / 2 / 892 | `Process Failed! (Invalid Shop for User MTadmin)` |

Последняя формулировка и есть ответ: сервис выбран верно, не хватает
**идентификатора магазина, закреплённого за пользователем `MTadmin`**.

## Что уже сделано в коде

- `submit` переведён на `Request_v4` (`integrations/easycredit_rest.py`);
- обязательные поля: `ProductID`, `UIN`, `CreditAmount`,
  `NumberOfInstallments`, `FirstInstallmentDate` (считается как сегодня + N
  дней, по умолчанию 31);
- данные заявителя наконец передаются: `ApFirstName`, `ApLastName`,
  `ApFatherName`, `ApDateOfBirth`, `CaMobile`, `GoodsName`, `GoodsPrice` —
  раньше, на `eShopRequest_V5`, к кредитору уходил только телефон;
- `ShopID`, `ProductID` и `first_installment_days` вынесены в настройки
  провайдера (бэк-офис → **Provideri API**), потому что их назначает
  EasyCredit и вывести их из API нельзя;
- пока они не заполнены, оператор видит понятный текст, а не код кредитора.

## Что просить у EasyCredit

> Contul `MTadmin` (partener `partener.ecredit.md`), mediul **TEST**.
> Folosim serviciul `Request_v4`. Fără `ShopID` primim
> `Process Failed! (Missing Shop!)`, iar cu ShopID 1 / 2 / 892 —
> `Process Failed! (Invalid Shop for User MTadmin)`.
>
> Vă rugăm să ne comunicați pentru contul `MTadmin`:
> 1. **ShopID**-ul magazinului nostru;
> 2. **ProductID**-urile valide pentru acest magazin (cu intervalele de rate
>    și sume);
> 3. aceleași valori pentru mediul **PRODUCTION**.

## Отдельно: сроки рассрочки в бэк-офисе

`ECM_ShopProducts` (без `ShopGroupID`) отдаёт продукты 54 / 55 / 56 со сроками
**6–11, 12 и 13–18** месяцев. Наш ли это каталог — вопрос открытый, он входит
в список к EasyCredit выше. Но если да, то пакет «Special 0% / 4 luni» в
`TMS_CREDITE_PLAN` ни одному продукту не соответствует, и заявка на 4 месяца
не пройдёт никогда.

Сроки в `/UNA.md/orasldev/biro26-credit-admin` нужно согласовать с тем
списком продуктов, который EasyCredit подтвердит для нашего `ShopID`. Для
боевой среды набор будет свой — запросить отдельно.

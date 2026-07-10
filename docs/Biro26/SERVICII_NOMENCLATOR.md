# Biro26 — Услуги в номенклатуре и корзине: универсальные функции PL/SQL

> Как была добавлена группа **Servicii** с позицией **«Servicii de transport»
> (150 MDL во всех трёх ценовых колонках)**, и как теми же универсальными
> функциями добавлять любые новые узлы/подузлы дерева товаров, позиции и цены.
> БД: `OFFICEPLUS @ orange.una.md:4024/cloudbd.world`; пакет: `y_ai_BIRO26`
> (`sql/biro26/04_y_ai_biro26.sql`, деплой — `deploy_biro26_shop.py`).

---

## 1. Универсальная функция: позиция + узел дерева + цены

**Ключевой факт о дереве:** дерево Marfă/Stoc (и фасет «Categorii» магазина)
— это производная от различных значений `GRUPA → CATEGORIE` в `BIRO26_GOODS`.
Отдельной таблицы узлов нет, поэтому **новый узел/подузел появляется
автоматически, как только первая позиция его использует**. Одна функция
покрывает оба случая:

```sql
-- RO/EN: создаёт TMS_UNIVERS (TIP='P') + BIRO26_GOODS (узел дерева)
--        + период цены в прайс-листе (PRETV/PRETV1/PRETV2); returns COD
FUNCTION y_ai_BIRO26.add_product(
  p_denumirea IN VARCHAR2,            -- название позиции (обязателно)
  p_grupa     IN VARCHAR2,            -- узел дерева (обязательно; новый = новый узел)
  p_categorie IN VARCHAR2 DEFAULT NULL,  -- подузел (новый = новый подузел)
  p_retail    IN NUMBER   DEFAULT NULL,  -- PRETV  (розница)
  p_angro     IN NUMBER   DEFAULT NULL,  -- PRETV1 (опт; NULL -> = retail)
  p_online    IN NUMBER   DEFAULT NULL,  -- PRETV2 (онлайн; NULL -> = retail)
  p_um        IN VARCHAR2 DEFAULT 'buc.',
  p_brand     IN VARCHAR2 DEFAULT NULL,
  p_data      IN DATE     DEFAULT TRUNC(SYSDATE)  -- начало ценового периода
) RETURN NUMBER;
```

Что делает по шагам:
1. `TMS_UNIVERS`: новый `COD` из `ID_TMS_UNIVERS`, `TIP='P'`, `GR1='TVR'`,
   `CACCESS='11100'` — позиция видна во всех гридах модуля;
2. `BIRO26_GOODS`: строка с `GRUPA`/`CATEGORIE` (это и есть «создание узла»),
   feed-ценами и `UNIT`;
3. `set_price(...)`: период в `TPR1D_PERPRLIST` (CODPRICE=1 «BIRO») через
   нативный INSTEAD OF-триггер — цены живут по правилам периодов
   (дробление/слияние, см. README раздел 12).

Ошибки: `-20263` — не заданы название или группа.

## 2. Настройки модуля: YBIRO_SETTINGS

Нормализованная таблица настроек (`skey PK, sval, descr, updated_at`) +
универсальные хелперы пакета:

```sql
PROCEDURE y_ai_BIRO26.set_setting(p_key, p_val, p_descr DEFAULT NULL);  -- upsert
FUNCTION  y_ai_BIRO26.get_setting(p_key) RETURN VARCHAR2;
```

Настройка документа/корзины про группу услуг:

| skey | sval | смысл |
|---|---|---|
| `SHOP_SERVICES_GRUPA` | `Servicii` | какая GRUPA предлагается опционально в корзине магазина |

## 3. Как была создана группа Servicii + транспортная услуга

Выполнено (идемпотентно — перед запуском проверяется существование):

```sql
DECLARE v NUMBER;
BEGIN
  v := y_ai_BIRO26.add_product(
         p_denumirea => 'Servicii de transport',
         p_grupa     => 'Servicii',        -- новый узел дерева
         p_categorie => 'Transport',       -- новый подузел
         p_retail    => 150,               -- 150 MDL ...
         p_angro     => 150,               -- ... во всех
         p_online    => 150,               -- ... трёх колонках
         p_um        => 'serv.');
  y_ai_BIRO26.set_setting('SHOP_SERVICES_GRUPA', 'Servicii',
    'optional services group in the shop cart');
END;
/
```

Результат в БД (проверено):
- `TMS_UNIVERS`: COD **288561**, «Servicii de transport», TIP='P', UM='serv.';
- `BIRO26_GOODS`: GRUPA='Servicii', CATEGORIE='Transport', 150/150/150 —
  узел «Servicii → Transport (1)» сразу виден в дереве Marfă/Stoc и в
  фасете «Categorii» магазина;
- `TPR1D_PERPRLIST`: период 09.07.2026 → 31.12.3000, PRETV=PRETV1=PRETV2=150;
- `YBIRO_SETTINGS`: SHOP_SERVICES_GRUPA='Servicii'.

## 4. Корзина магазина: опциональные услуги → счёт

- Публичный endpoint **`GET /api/biro26/shop/services`** возвращает позиции
  группы из `SHOP_SERVICES_GRUPA` с действующей ценой прайс-листа (на сегодня).
- В модалке корзины (`/UNA.md/orasldev/biro26-shop`) под таблицей товаров —
  блок **«Servicii opționale · Дополнительные услуги»** с чекбоксами
  (название + цена).
- При «Создать счёт на оплату» отмеченные услуги добавляются к товарам и
  попадают строками в тот же документ (`y_ai_BIRO26.create_invoice/add_line`,
  виден в `VMDB_DOCS_WORK` / `VMDB_ST201M` / `VMDB_ST201D`).
- Цена услуги, как и товаров, берётся **на сервере** из прайс-листа —
  клиент повлиять на неё не может.

## 5. Как добавить ещё услугу / узел (памятка)

```sql
-- ещё услуга в существующий узел:
SELECT y_ai_BIRO26.add_product('Servicii de livrare la etaj',
       'Servicii', 'Transport', 200, 200, 200, 'serv.') FROM dual;  -- (в PL/SQL блоке)

-- совершенно новый узел + подузел одним вызовом:
--   add_product('Montaj mobilier', 'Servicii', 'Montaj', 300, ...)
-- сменить группу услуг корзины:
--   y_ai_BIRO26.set_setting('SHOP_SERVICES_GRUPA', 'AltaGrupa');
```

Изменение цены услуги дальше — штатно через периоды
(`y_ai_BIRO26.set_price`, вкладка Marfă/Stoc или Listă de prețuri);
удаление периодов — `del_price` (правила слияния — README, раздел 12).


## 6. Транспорт тур-ретур: тарифная сетка по дистанции (обновление)

Структура (создана универсальными функциями `add_product` + новая таблица):

- **Подгруппа «Servicii de transport per tur»** (фикс за рейс): 0–25 км → 150 MDL
  (COD 288561, бывший «Servicii de transport», переименован), 26–50 км → 250 MDL (289179);
- **Подгруппа «Servicii de transport per km»** (за км, кол-во строки счёта = км):
  51–100 км → 6 MDL/km (289180), 101–200 км → 5.50 MDL/km (289181),
  свыше 200 км → 5.00 MDL/km (289182).

Все цены — в прайс-листе (периодные, все три колонки). Диапазоны — в новой таблице:

```sql
TMS_MPT_DISTANTE (cod PK -> TMS_UNIVERS.COD, km_min, km_max NULL=∞, tarif_mode 'TUR'|'KM')
```

**Корзина магазина:** блок «🚚 Transport tur-retur (obligatoriu)» — поле «Distanța (km)»
обязательно; тариф подбирается автоматически и показывается живым расчётом; без
дистанции счёт не создаётся. **Сервер сам добавляет** строку транспорта по
`distance_km` (TUR → qty 1, KM → qty = км), присланные клиентом транспортные строки
отбрасываются (анти-манипуляция); цена — из прайс-листа. Публичный API:
`GET /api/biro26/shop/transport` (сетка); `POST /shop/invoice` требует `distance_km`.
Из «Servicii opționale» тарифные позиции исключены.

Изменить тариф: цены — штатно через периоды (`set_price`); диапазоны — UPDATE
`TMS_MPT_DISTANTE`; новый диапазон = `add_product` + INSERT в `TMS_MPT_DISTANTE`.


## 7. Логистические центры (TMS_MPT_CENTRE_LOG)

Транспорт тур-ретур считается **от логистического центра**; дистанция в корзине —
«Distanța de la centru (km)». Справочник:

```sql
TMS_MPT_CENTRE_LOG (id PK, denumire UNIQUE, activ '1'/'0', nrord)
-- (1,'mun. Balti','1')  (2,'Cahul','0')  (3,'Comrat','0')  (4,'Chisinau','0')
```

Сейчас активен только **mun. Bălți**; Cahul/Comrat/Chișinău заведены неактивными —
включить: `UPDATE TMS_MPT_CENTRE_LOG SET activ='1' WHERE denumire='Cahul';`
(в корзине автоматически появится выбор центра, когда активных станет >1).
Имена в БД — ASCII (charset CL8MSWIN1251 не содержит румынских диакритик).

- Публичный API: `GET /api/biro26/shop/logistics` — только активные центры.
- В корзине: один активный → фиксированная подпись центра; несколько → select;
  `POST /shop/invoice` принимает `center_id` (неактивный/неизвестный id
  подменяется первым активным).
- В строке счёта транспорт получает суффикс « din <центр>»
  (напр. «Servicii de transport tur-retur 25-50 km din mun. Balti»).

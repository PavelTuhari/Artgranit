# Инструкция разработчика — интерфейс «Marfă / Stoc» (Biro26)

**Файл-владелец UI:** вкладка `products` в `templates/biro26/backoffice.html` + JS в `static/biro26/backoffice-tabs.js` (секция `TAB 6 — PRODUCT + STOCK GRID`).
**Маршрут страницы:** `/UNA.md/orasldev/biro26-backoffice` (вкладка «Marfă / Stoc»).
**Актуально на:** 2026-07-03 (после PR #5/#6).

---

## 1. Что это

Грид «товар + остатки» по всем товарам справочника (`TMS_UNIVERS`, `TIP='P'`, ~78k строк), колонки повторяют легаси-Excel-экспорт Windows-приложения: фото, артикул, **штрихкод**, наименование, таможенная группа (GRUPA), товарная группа (CATEGORIE), ед.изм., кол-во, закупка без/с НДС, онлайн-цена, розница, производитель, ставка НДС.

Слева — **дерево групп** GRUPA (12) → CATEGORIE (~605) со счётчиками; клик по узлу фильтрует грид. Сверху — поиск (название/артикул/штрихкод), фильтр по бренду, сброс фильтров и **константа остатков**. Грид подгружается **инфинит-скроллом** порциями по 100 строк. Клик по названию/SC открывает **карточку товара** (фото, все штрихкоды, поля `TMS_UNIVERS`+`TMS_MPT`).

---

## 2. Слои и поток данных

```
браузер (backoffice-tabs.js)
  → GET /api/biro26/products*            (app.py, auth-guard _b26)
  → Biro26Controller.get_products_stock  (controllers/biro26_controller.py — тонкий разбор request.args)
  → Biro26Store.get_products_stock       (models/biro26_oracle_store.py — весь SQL)
  → Biro26DB().execute_query             (models/biro26_db.py — subprocess-клиент)
  → models/biro26_worker.py              (отдельный процесс, thick-режим Instant Client)
  → officeplus @ orange.una.md:4024/cloudbd.world (Oracle 11g)
```

**Незыблемое правило:** `init_oracle_client` (thick) существует ТОЛЬКО в `biro26_worker.py`. Основной Flask-процесс остаётся thin — иначе ломается cloud-подключение production (`nufarul.eminescu.md`). Каждый вызов `Biro26DB` = отдельный subprocess = отдельная Oracle-сессия (см. §6 про остатки).

---

## 3. Таблицы-источники

| Объект | Роль в гриде |
|---|---|
| `TMS_UNIVERS` (TIP='P') | базовая строка: COD, CODVECHI, DENUMIREA, NAMERUS, UM |
| `BIRO26_GOODS` | GRUPA, CATEGORIE, BRAND, цены ANGRO/IONLINE/RETAIL1 (join по `COD_UNIVERS=COD`, **дедуплицирован** — см. §4) |
| `VMS_MPT_TVR` (view над `TMS_MPT_TVR`) | картинка `IE_LINKADRES` (наполняется `import_images()`, MERGE из фида) |
| `TMS_MPT_BARCODE (COD, BARCODE)` | штрихкоды: первый EAN + количество в грид, все — в карточку; участвует в поиске. Наполняется `import_barcodes.py` + пакетными `import_barcodes/import_barcodes_positional` (см. `IMPORT_TMS_UNIVERS.md` §9В/9В.1) |
| `YBIRO_STOCK_CALC` / `YBIRO_STOCK_CALC_ITEM` | реальный остаток `REAL_CANT` из последнего расчёта `UN$SOLD.GET_SOLDT` (вкладка «Stoc (calcul)») |

---

## 4. API и ключевой SQL

Все ответы — `{success, data?, error?}`; деньги/количества — числа, строки грида — dict с ключами в **нижнем регистре** (`_rows()` в store).

| Эндпоинт | Параметры | Возвращает |
|---|---|---|
| `GET /api/biro26/products` | `search, brand, grupa, categorie, gr1, limit(=200), offset(=0)` | строки грида: `cod, codvechi, denumirea, namerus, um, grupa, categorie, brand, angro, ionline, retail1, angro_fara_tva, image, real_cant, barcode, bc_cnt` |
| `GET /api/biro26/products/tree` | — | `[{grupa, categorie, cnt}]` (~768 строк, одним запросом; дерево строится на клиенте) |
| `GET /api/biro26/products/brands` | — | `[{brand, cnt}]` (8 шт.) |
| `GET /api/biro26/univers/<cod>` | — | карточка: `univers`, `mpt`, `photo_url`, `ie_linkadres`, **`barcodes[]`** |

Реализация — `Biro26Store.get_products_stock()` (`models/biro26_oracle_store.py:678`). Особенности, которые НЕЛЬЗЯ «упростить» обратно:

1. **Oracle 11g: нет `OFFSET/FETCH` и `IDENTITY`.** Пагинация только через хелпер `_page(inner, limit, offset)` (обёртка `ROWNUM`); внутренний SELECT обязан иметь `ORDER BY`. Хелпер `_rows()` срезает служебную колонку `rn`.
2. **Дедуп фида.** В `BIRO26_GOODS` ~11 товаров имеют повторные строки → join делается через `ROW_NUMBER() OVER (PARTITION BY g0.COD_UNIVERS ORDER BY g0.ID) = 1`, иначе товары дублируются в выдаче.
3. **Штрихкоды в грид** — агрегатным LEFT JOIN `(SELECT COD, MIN(BARCODE) BARCODE, COUNT(*) BC_CNT FROM TMS_MPT_BARCODE GROUP BY COD)` (до 11 EAN на товар).
4. **Поиск — только через предвычисленный набор ключей:**
   ```sql
   AND u.COD IN (
     SELECT COD FROM TMS_UNIVERS WHERE TIP='P' AND (имя/артикул LIKE :s)
     UNION
     SELECT COD FROM TMS_MPT_BARCODE WHERE BARCODE LIKE :s)
   ```
   ⚠️ Форма `... OR EXISTS(SELECT 1 FROM TMS_MPT_BARCODE ...)` внутри основного джойна давала **~300 секунд** (таймаут воркера): Oracle исполнял тяжёлый джойн (вью `VMS_MPT_TVR` с коррелированными подзапросами + `ROW_NUMBER`-дедуп) построчно. IN/UNION даёт ~3с. Закреплено тестом `test_get_products_stock_barcode_column_and_search` (запрещает `OR EXISTS`). Любой новый поисковый критерий добавляйте **внутрь IN-подзапроса**, не в WHERE основного джойна.
5. Только bind-переменные (`:s`, `:brand`, ...). Никакой конкатенации пользовательского ввода.

---

## 5. Frontend: состояние, элементы, функции

Все ID/функции — `static/biro26/backoffice-tabs.js`, разметка — `panel-products` в шаблоне. Диспетчер вкладки (инлайн-скрипт шаблона, `showTab`):
```js
if (id === 'products'){ loadStockConst(); loadProductBrandsFilter(); loadProductTree(); loadProductsStock(true); }
```

### Состояние
```js
const prodState = { offset, limit: 100, hasMore, loading, rows: [] };  // инфинит-скролл
let   prodTreeData = null;      // кэш /products/tree: [{grupa, categorie, cnt}]
let   prodScrollBound = false;  // scroll-листенер вешается один раз
```
Выбранный узел дерева хранится в **hidden-инпутах** `#prod-grupa` / `#prod-categorie` — их читает `loadProductsStock()`, поэтому дерево и грид не связаны напрямую.

### Элементы
| ID | Что это |
|---|---|
| `prod-search` | поиск (placeholder `search_bc_ph`: название/артикул/штрихкод), debounce 350мс |
| `prod-brand` | select бренда (грузится 1 раз, `dataset.loaded`) |
| `prod-grupa`, `prod-categorie` | hidden, выставляются деревом |
| `prod-tree` | контейнер дерева (левая карточка) |
| `prod-const` | константа остатков (localStorage `biro26_stock_const`) |
| `prod-table-wrap` | скролл-контейнер (на нём инфинит-скролл) |
| `prod-body`, `prod-count`, `prod-more-row`, `prod-end-row` | tbody, счётчик, индикаторы «грузим ещё»/«конец» |

### Функции (строки актуальны на дату документа)
| Функция | Роль |
|---|---|
| `loadProductsStock(reset)` :864 | единственная точка загрузки. `reset=true` — новый фильтр/поиск (offset=0, очистка), `reset=false` — следующая порция скролла. Собирает query из search/brand/grupa/categorie + limit/offset. `hasMore = batch.length === limit` |
| `bindProductsScroll()` :850 | scroll-листенер: за 200px до низа → `loadProductsStock(false)` |
| `productRowHtml(p)` :912 | HTML одной строки (14 колонок). Кол-во: `real_cant`, если есть и ≠0, иначе константа (курсив, muted). Штрихкод: `p.barcode` + бейдж `+N` при `bc_cnt>1`. Клик по названию → `showItemCard(cod)` |
| `loadProductTree()` :785 / `renderProductTree()` :795 | фасет грузится один раз, дерево перерисовывается целиком при каждом клике; раскрыта только выбранная GRUPA (▸/▾), выбранный узел подсвечен |
| `selectTreeNode(grupa, categorie)` :834 | пишет hidden-инпуты → `renderProductTree()` + `loadProductsStock(true)`. `('','')` = «Все товары» |
| `clearProductFilters()` :841 | сброс поиска/бренда/дерева + перезагрузка |
| `loadStockConst()` / `onStockConstChange()` :748/:755 | константа: чтение из localStorage / сохранение + **клиентская** перерисовка уже загруженных `prodState.rows` без re-fetch |
| `showItemCard(cod)` :422 | модалка `#modal-item`: фото (лайтбокс), `barcodesHtml()` — чипы всех EAN, поля TMS_UNIVERS/TMS_MPT |
| `barcodesHtml(list)` :448 | общий блок чипов штрихкодов (используется и в карточке Nomenclator) |

### i18n
Ключи в трёх блоках `I18N.{ru,ro,en}` инлайн-скрипта шаблона: `tab_products, prod_title, prod_tree_title, prod_tree_all, col_barcode, search_bc_ph, card_barcodes, prod_const_label, prod_col_* , prod_clear_filters, prod_loading_more, prod_end_of_list`. **Новый ключ добавляется во все три языка**, текст вешается через `data-i18n` / `data-i18n-ph`.

---

## 6. Остатки (`REAL_CANT`) и константа

- Реальный остаток берётся из **последнего** расчёта: подзапрос по `YBIRO_STOCK_CALC_ITEM` с `calc_id = (SELECT id FROM YBIRO_STOCK_CALC WHERE is_latest='1')`. Расчёт запускается на вкладке «Stoc (calcul)» (`POST /api/biro26/stock/calculate` → `UN$SOLD.GET_SOLDT`).
- `GET_SOLDT` создаёт **сессионную GTT**, а каждый вызов воркера — новая сессия, поэтому расчёт+перенос в постоянные таблицы выполняются **одним** `execute_script` (одна сессия). Не разбивать на отдельные вызовы. Индекс на GTT не создавать (`ORA-14452`) — индекс уже есть на `YBIRO_STOCK_CALC_ITEM(sc)`.
- Пока в `TMDB_CM` нет проводок по счетам `217 2165 2114` (Фаза 2 ТЗ не реализована), `real_cant = NULL` у всех — грид показывает константу (умолч. 1000, поле `#prod-const`), как в исходном Excel. Подмена — чисто визуальная, на клиенте.

---

## 7. Как расширять

**Добавить колонку в грид** — 4 места, по порядку:
1. `Biro26Store.get_products_stock`: колонка/join во внутреннем SELECT (у join'ов — только агрегированные/дедуплицированные подзапросы, иначе поплывёт кардинальность);
2. `<th data-i18n="...">` в `panel-products` + **colspan** во всех `emptyRow(..., 14, ...)` и в загрузочной строке шаблона (сейчас 14);
3. ячейка в `productRowHtml()` — тот же порядок, что и `<th>`;
4. i18n-ключ ×3 языка. Тест формы SQL — в `tests/test_biro26.py`.

**Добавить фильтр:** параметр в store (bind!) → `Biro26Controller.get_products_stock` (`request.args`) → UI-контрол + строчка `qs.set(...)` в `loadProductsStock` → сброс в `clearProductFilters`. Если фильтр текстовый по «содержит» — см. §4 п.4 (в IN-подзапрос).

**Изменить размер порции:** `prodState.limit` (клиент) — сервер принимает любой `limit`.

---

## 8. Тесты и верификация

- Unit (mock-DB, без Oracle): `./venv/bin/python -m pytest tests/test_biro26.py -q` — тесты формы SQL: `test_get_products_stock_*`, `test_get_product_tree_*`, `test_get_product_brands_*`, `test_get_univers_card_includes_barcodes`.
- Живой smoke: `./venv/bin/python test_biro26_smoke.py`.
- Синтаксис JS: `node -c static/biro26/backoffice-tabs.js`; рендер: `render_template('biro26/backoffice.html')` под `app.app_context()`.
- **Перф-чек после любых правок SQL грида:** поиск с фильтром обязан укладываться в секунды (см. §4 п.4); таймаут воркера — 300с (`BIRO26_WORKER_TIMEOUT`).

**Деплой на прод:** tar по ssh изменённых файлов в `/home/ubuntu/artgranit` → `sudo systemctl restart artgranit` → проверить `https://nufarul.eminescu.md/login` = 200 (инвариант) и сам эндпоинт. Instant Client на сервере: `/opt/oracle/instantclient_19_28` (`BIRO26_INSTANT_CLIENT` в remote `.env`).

## 9. Связанные документы
- `docs/Biro26/README_BIRO26.html` — обзор модуля (маршруты, все эндпоинты, деплой).
- `/Users/pt/Projects.AI/BIRO26/IMPORT_TMS_UNIVERS.md` §9В/9В.1 — методика импорта штрихкодов.
- `docs/superpowers/specs/2026-06-28-biro26-module-design.md` — архитектура модуля (subprocess-воркер, 11g).

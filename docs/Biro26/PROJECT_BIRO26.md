# BIRO26 (OfficePlus) — документация проекта

> Модуль Flask-платформы **Artgranit** для работы с ERP OfficePlus: импорт
> номенклатуры, товары/остатки/варианты, цены по периодам, публичный
> интернет-магазин с саморегистрацией клиентов, счета на оплату в ERP,
> печатные формы (2 PDF-движка), вложения к документам, уведомления.
> Отображаемое имя настраивается одной переменной — по умолчанию **OfficePlus**.
>
> Прод: `https://nufarul.eminescu.md/` · Актуально на 2026-07-09 (PR #2–#23).

---

## 1. Обзор

| | |
|---|---|
| Платформа | Flask (один процесс `app.py`), деплой `/home/ubuntu/artgranit`, systemd `artgranit`, nginx+SSL |
| БД модуля | **Oracle 11g** `officeplus @ orange.una.md:4024/cloudbd.world` (внешняя ERP; модуль к ней подключается, ничего не мигрирует) |
| Сайдкар отчётов | Node.js ≥22.18, `reports/`, `127.0.0.1:5488`, systemd `jsreport` (движки jsReport и pdfme) |
| Брендинг | `BIRO26_APP_NAME` в config/.env (по умолчанию `OfficePlus`) — заголовки/шапки всех страниц |
| Тесты | `tests/test_biro26.py` — 56 unit-тестов на mock-БД (без сети) |

## 2. Архитектура

```
Браузер ──► nginx (443) ──► Flask app.py (127.0.0.1:8000, thin oracledb → ADB платформы)
                              │
                              ├─ per-request subprocess: models/biro26_worker.py
                              │    └ init_oracle_client(BIRO26_INSTANT_CLIENT)  ← ТОЛЬКО здесь thick
                              │    └ officeplus @ Oracle 11g (ERP)
                              │
                              └─ HTTP → reports/ (Node, 127.0.0.1:5488)
                                   ├ jsReport: POST /api/report      (Handlebars + chrome-pdf)
                                   └ pdfme:    POST /pdfme/generate  (JSON-шаблон + pdf-lib, без Chromium)
```

Ключевые инварианты:
- `init_oracle_client` — **только** в `biro26_worker.py` (thick — переключение
  всего процесса; в основном Flask сломал бы thin-подключение платформы);
- контракт воркера: JSON `{success, columns, data, rowcount, message}`;
  методы `execute_query / execute_dml / execute_script` (атомарно, одна
  сессия/транзакция) / `call_proc` (DBMS_OUTPUT); бинарные параметры —
  `{"__b64__": ...}` → bytes с биндом `DB_TYPE_BLOB`;
- Oracle 11g: без OFFSET/FETCH (пагинация ROWNUM `_page()`), без IDENTITY
  (sequence+trigger), только bind-переменные;
- пароли/секреты — только в `.env` (никогда в коде, репозитории или БД).

## 3. Интерфейсы (все под auth платформы, кроме магазина)

| URL | Что это |
|---|---|
| `/UNA.md/orasldev/biro26` (`-admin`) | Лаунчер модуля (карточки всех разделов) |
| `/UNA.md/orasldev/biro26-backoffice` | Backoffice, 8 вкладок, i18n RU/RO/EN |
| `/UNA.md/orasldev/biro26-shop` | **Публичный** магазин для физлиц |
| `/UNA.md/orasldev/biro26-report-templates` | Админка шаблонов печатных форм + выбор движка |
| `/UNA.md/orasldev/biro26-pdfme-designer` | Визуальный drag&drop редактор pdfme-шаблонов |
| `/UNA.md/orasldev/biro26-notify-settings` | Настройки уведомлений (email/TG/WhatsApp) |
| `/UNA.md/orasldev/biro26-tz`, `-docs` | ТЗ и HTML-документация модуля |

### Вкладки backoffice
Sursă (feed BIRO26_GOODS) · Nomenclator (TMS_UNIVERS/TMS_MPT, карточка с
вариантами) · Grupe/Furnizori · **Listă de prețuri** (бесконечный скролл,
inline-правка цен) · Mapare/Setări (профили `g_*`) · **Import wizard**
(источник = любой SELECT, AI-подсказка маппинга) · **Marfă/Stoc**
(BI-грид: дерево групп, фасеты, поиск вкл. штрихкоды, бесконечный скролл,
цены на дату, история цен, правка товара/дерева, корзина) · Stoc (calcul)
(остатки `UN$SOLD.GET_SOLDT`, константа-плейсхолдер).

## 4. Функциональные блоки

### 4.1 Цены по периодам (как в нативном OfficePlus)
Источник цен — `TPR1D_PERPRLIST` (CODPRICE=1 «BIRO»), период = строка
[DATASTART, DATAEND]. Изменение цены **дробит** период на выбранную дату
(нативный INSTEAD OF-триггер), удаление строки **сливает** соседние периоды
(диапазон без разрывов), последнюю строку удалить нельзя (ORA-20261).
Грид Marfă/Stoc показывает цены **на дату** (`price_date`, по умолчанию
сегодня); внизу — панель «Istoric prețuri» по клику на строку товара.
Колонки: PRETV=retail, PRETV1=angro, PRETV2=online.

### 4.2 Варианты товаров (`BIRO26_VARIANTS`)
Семьи master/detail (78 227 строк, 10 288 мультивариантных групп); группа =
`MASTER_COD`, цена — одна на группу. В карточке товара — редактируемый блок
«Variante» (правка VARIANT синхронно обновляет `TMS_MPT_BARCODE.COMENT`);
в магазине у товаров с семьёй >1 — селектор характеристики, в корзину идёт
COD выбранного варианта. Подробно: `BIRO26_VARIANTS_IMPLEMENTATION.md`.

### 4.3 Публичный магазин
Каталог = грид Marfă/Stoc (поиск, Amazon-фасеты: дерево групп, диапазон
цены, чипы), саморегистрация клиентов (`YBIRO_CLIENT`, pbkdf2; организация
в `TMS_UNIVERS` TIP='O'), корзина в localStorage, **опциональные услуги**
(группа из настройки `SHOP_SERVICES_GRUPA`), кнопка «Создать счёт на
оплату». Цены — всегда серверные (из прайс-листа), клиент подменить не может.

### 4.4 Счета на оплату в ERP (пакет `y_ai_BIRO26`)
`create_invoice` + `add_line` создают нативный документ (TMDB_DOCS
SYSFID=12280, **AT2=2** — без проверки рабочего периода; проводка через
VMDB_ST201M; строки через VMDB_ST201D; XNRDOC для видимости). Документ виден
штатно: `VMDB_DOCS_WORK WHERE COD=:COD` / `VMDB_ST201M` / `VMDB_ST201D`.
Прочие универсальные функции пакета: `register_client`, `set_price` /
`del_price` / `price_on` (периоды), **`add_product`** (позиция + узел/подузел
дерева + цены одной функцией), `set_setting`/`get_setting` (YBIRO_SETTINGS).

### 4.5 Печатные формы — два движка на выбор
«Cont de plată / Счёт-фактура» и «Comanda cumpărătorului» (по образцам 1С,
с логотипом заказчика `reports/templates/logo.jpg`, суммой прописью
по-румынски). Движок — **per-форма**, переключается в админке шаблонов
(`engines.json`): **jsReport** (`biro26_*.hbs`, HTML/CSS+Chromium) или
**pdfme** (`pdfme_*.json`, pdf-lib, легче/быстрее, редактируется визуально
в Designer). Каждый сгенерированный PDF **прикрепляется к документу** в
`VMDB_DOCS_OLE` (замена, не дубликат; best effort).

### 4.6 Уведомления
При создании счёта — email (SMTP из .env) / Telegram (Bot API) / WhatsApp
(CallMeBot) по включённым каналам; настройки в админке (`YBIRO_SETTINGS`,
ключи `NOTIFY_*`), отправка fire-and-forget (фоновый поток).

### 4.7 Импорт
Мастер импорта: источник — файл-feed или **любой SELECT** (`YBIRO_SRC_DEF`,
guard только-SELECT), просмотр колонок/сэмпла, AI-подсказка маппинга,
профили (`YBIRO_MAP_PROFILE/PARAM`, параметры `g_*` пакета
`YBIRO_IMPORT_MARFA`): validate → prepare → assign-keys → import в
TMS_UNIVERS/TMS_MPT; группы/даты/цены прайс-листа; линки картинок — в
`TMS_MPT_TVR.IE_LINKADRES`; откат прайс-листа.

## 5. Объекты БД (схема OFFICEPLUS)

**Пакеты**: `Y_AI_BIRO26` (см. 4.4), `YBIRO_IMPORT_MARFA` (импорт, `g_*`).

**Таблицы модуля** (нормализованные, префиксы YBIRO_/BIRO26_):
`BIRO26_GOODS` (feed; GRUPA/CATEGORIE = дерево), `BIRO26_VARIANTS`,
`BIRO26_BARCODES*`, `BIRO26_DETAIL/MASTER` (staging вариантов),
`YBIRO_CLIENT` (+SEQ, клиенты магазина), `YBIRO_SETTINGS` (настройки),
`YBIRO_MAP_PROFILE/PARAM` (+SEQ), `YBIRO_SRC_DEF` (+SEQ),
`YBIRO_STOCK_CALC/_ITEM` (+SEQ, снимки остатков), `YBIRO_*_GTT` (временные),
`YBIRO_DUP_*_BAK` / `YBIRO_SYSGR*_BAK` (бэкапы чисток).

**Нативные объекты ERP, которые модуль использует** (не менять!):
`TMS_UNIVERS`, `TMS_MPT(+_TVR/_BARCODE)`, `TPR1D_PERPRLIST`/`VTPR1D_PERPRLIST`
(+INSTEAD OF-триггеры периодов), `VPR*`-вьюхи прайса, `TMDB_DOCS`,
`VMDB_ST201M/D`, `VMDB_DOCS_WORK`, `VMDB_DOCS_OLE`/`TMDB_DOCS_OLE`,
`XNRDOC`, `UN$SOLD.GET_SOLDT`, секвенции `ID_TMS_UNIVERS`/`ID_TMDB_DOCS`/`ID_TMDB_CM`.

DDL: `sql/biro26/01..04*.sql`; идемпотентные деплойеры `deploy_biro26_*.py`.

## 6. API (76 маршрутов `/api/biro26/...`)

**Публичные** (`/shop/*`): `register, login, logout, me` (сессия клиента) ·
`products` (каталог: search/grupa/categorie/brand-мульти/price_min/max/
price_date/limit/offset) · `tree`, `brands`, `services`, `variants?cod=` ·
`invoice` (POST items → `{cod,nrset}`) · `report/<invoice|order>/<cod>`
(PDF; клиент — только свои документы).

**За auth** (сессия платформы): source/goods/univers/suppliers/groups/
categories (импорт и словарь) · mapping/profiles · prices (+dates/import/
rollback) · products (+`<cod>`, tree rename/move, price, price-history,
price/delete, brands, categories) · univers/`<cod>`/variants, variants/`<cod>` ·
stock (calculate/latest/items) · sources (+AI) · report-templates
(+`<name>`, preview), report-engines · notify-settings, notify-test ·
connection/test.

Формат ответов: `{success, data | error}`; ошибки БД не маскируются.

## 7. Эксплуатация

### Локальный запуск
```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python app.py                 # Flask :3003 (локальный порт)
cd reports && node server.js             # сайдкар :5488 (Node ≥22.18)
./venv/bin/python -m pytest tests/test_biro26.py -q   # 56 тестов
```
Локальный Instant Client: `/Users/pt/lib/instantclient_23_26` (НЕ ~/Downloads
— блокируется macOS TCC; см. SETUP.md внутри клиента).

### Деплой (штатный цикл)
feature-ветка → PR → merge → tar изменённых файлов по ssh
(`~/.ssh/artgranit-oci.key`, `ubuntu@92.5.3.187:/home/ubuntu/artgranit`) →
`sudo systemctl restart artgranit` (и `jsreport`, если менялся `reports/`;
новые npm-пакеты — `npm install` на сервере) → проверка. Oracle-схема
меняется отдельно деплойерами. **Перезапуск только через systemd** (не
pkill+nohup). `.env` и wallet деплоем не трогаются.

### Проверка после любого изменения (обязательный инвариант)
```bash
curl -I https://nufarul.eminescu.md/login                      # HTTP/2 200
curl -s https://nufarul.eminescu.md/api/biro26/shop/products?limit=1 | head -c 60
systemctl is-active artgranit jsreport                          # на сервере
```

### Сервер (детали)
956 MB RAM + 2 GB swap; `jsreport.service` c MemoryHigh=450M/MemoryMax=600M;
первый chrome-pdf рендер ~20 c (холодный старт), pdfme — без Chromium.
Полная процедура переноса на новый хост: **MIGRATION_BIRO26.md**
(https://nufarul.eminescu.md/static/biro26/MIGRATION_BIRO26.md).

## 8. Уроки производительности (не повторять ошибок)

1. Поисковые/фильтровые предикаты — только как pre-resolved
   `u.COD IN (SELECT ...)`, не OR/EXISTS внутри тяжёлого join (было 300 с).
2. Тяжёлые join'ы (view картинок, остатки, штрихкоды, варианты) — только
   **поверх страницы** ≤200 строк, фильтры и ORDER BY — в дешёвом ядре
   (иначе фильтр по группе терял ROWNUM-stopkey: 166 с → 2.6 с).
3. Быстрые клики по фильтрам в UI — нумеровать запросы, рендерить только
   последний (иначе устаревший ответ перетирает новый).
4. `TO_NUMBER` над VARCHAR-колонками feed — только под
   `REGEXP_LIKE`-guard (ORA-01722 на грязных данных).
5. BLOB >32KB через bind — только с `setinputsizes(DB_TYPE_BLOB)` (ORA-01461).

## 9. Индекс документов

| Файл | Содержание |
|---|---|
| `README_BIRO26.html` | Полный справочник модуля (разделы 1–14: БД, маршруты, магазин, цены, варианты, отчёты, уведомления) |
| `PROJECT_BIRO26.md` | этот документ — сводная картина проекта |
| `MIGRATION_BIRO26.md` | перенос на другой хостинг (для ИИ, команды copy-paste) |
| `SERVICII_NOMENCLATOR.md` | услуги, универсальный `add_product`, настройки |
| `DEV_MARFA_STOC.md` | руководство разработчика по вкладке Marfă/Stoc |
| `TZ_BIRO26_App.md` | исходное ТЗ |
| `/Users/pt/Projects.AI/BIRO26/BIRO26_VARIANTS_IMPLEMENTATION.md` | модель вариантов |
| `CLAUDE.md` (корень) | обязательные инженерные правила платформы |

Онлайн-копии: `https://nufarul.eminescu.md/static/biro26/MIGRATION_BIRO26.md`,
`.../static/biro26/PROJECT_BIRO26.md`.

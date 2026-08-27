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

## Microinvest + документы клиента (2026-08-09)

**Кредитор Microinvest** (acord de parteneriat nr. 554/2026, без API).
Тарифы заведены в `TMS_CREDITE_ORG`/`TMS_CREDITE_PLAN` (org 4, наценка к
СТАНДАРТНОЙ цене; `TRANSPORT_MARKUP_PCT=0` — надбавка магазина уже в плане):

| План | Месяцы | Наценка | Годовая | Сумма |
|---|---|---|---|---|
| 0% 4 luni plus | 4 | 16% (6 комиссия + 10 магазин) | 0 | 1 000–500 000 |
| 0% 6 luni plus | 6 | 18% (8 + 10) | 0 | 1 000–500 000 |
| Standard 6-48 luni | 7–48 | 5% | 39% | 1 000–500 000 |

Standard начинается с 7 месяцев намеренно: на 6 месяцах он всегда дороже
плана «0% 6 luni plus», две одинаковые плитки «6 rate» только путали бы.

**Документы клиента** — новая таблица `TMS_MUNC_ADDFILES` (BLOB, 1:N к
`TMS_UNIVERS`) + журнал доступа `TMS_MUNC_ADDFILES_LOG`. DDL:
`sql/80_tms_munc_addfiles.sql`. Модель: `models/biro26_client_files.py`.

* Кабинет `/cont` → «Documentele mele»: загрузка buletin față/verso и прочих
  (JPG/PNG/PDF, до 8 МБ), просмотр, удаление (физическое).
* API: `GET|POST /api/biro26/shop/my-files`, `GET|DELETE …/my-files/<id>`;
  оператор работает с чужим досье через `?cod=<univers_cod>`.
* Бэк-офис `/biro26-clients` → кнопка «📎 acte» открывает досье клиента.
* Заявка на кредит от авторизованного клиента **автоматически прикладывает
  сканы к e-mail-уведомлению** оператору (у Microinvest нет API — заявку
  подаёт оператор). Код клиента берётся ТОЛЬКО из сессии.

⚠ Транспорт BLOB: воркер отдаёт двоичные LOB как `{"__b64__": …}` — текстовые
BLOB (описания товаров) по-прежнему приходят строкой. Без этого сканы
портились при чтении.

Аудит GDPR/безопасности: `docs/Biro26/AUDIT_GDPR_SECURITATE.html`
(риски R1–R7 и план действий; часть мер уже применена — cookie
HttpOnly/SameSite/Secure, лимит тела запроса 12 МБ).

## Обновление цен только по Артикулам (2026-08-10)

Опция **`YBIRO_SETTINGS.PRICE_UPDATE_BY_ARTICLE`**, по умолчанию **включена** (`'1'`).

Смысл: цена из источника попадает на товар, только если **АРТИКУЛ товара в ERP**
(`TMS_UNIVERS.CODVECHI`) совпадает с полем «Articol» строки источника. Строки без
совпадения по артикулу пропускаются — отсутствующий или неверный артикул больше
не может изменить цену чужой позиции.

* Oracle: `YBIRO_Import_Marfa.import_prices(..., p_only_articol IN NUMBER DEFAULT 1)`
  добавляет к JOIN условие `UPPER(TRIM(tu.codvechi)) = UPPER(TRIM(g.<articol>))`;
  `import_all` передаёт флаг дальше. `p_only_articol => 0` — прежнее поведение
  (по назначенному ключу). В отчёт (`say`) добавлена пометка, каким способом шёл импорт.
* Python: `Biro26Store.import_prices(..., only_articol=None)` — при `None` берёт
  значение настройки; `price_by_article()` / `set_price_by_article()`.
* API: `GET|PUT /api/biro26/prices/by-article` (`{"on": true|false}`);
  `POST /api/biro26/prices/import` принимает `only_articol`.
* Бэк-офис, вкладка «Цены»: галочка **«Doar în baza Articolelor» / «Только по
  Артикулам» / «By Articles only»** рядом с кнопкой импорта — состояние
  подгружается из настройки и сохраняется сразу при переключении.

### Полная анкета заявки в кредитных документах (2026-08-10)

Раньше часть анкеты (цель, доход, работодатель, данные документа) склеивалась
текстом в `CLIENT_ADDRESS`. Теперь каждое поле — своя колонка в
`TMS_CREDITE_REQ` (DDL: `sql/81_credite_req_anketa.sql`):
`CLIENT_COD, EMAIL, IDNP, BIRTH_DATE, ACT_SERIE, ACT_DATA, ACT_OFICIU,
LOCALITATE, SCOP, VENIT, ALTE_RATE, ANGAJATOR, ACORD_MKT`.

* API: `GET /api/biro26/credite-docs/anketa/<req_id>` — вся анкета + **подписанные
  ссылки на сканы буletin** (`Biro26Credit.request_anketa`).
* Страница `/UNA.md/orasldev/biro26-credite-docs`: под гридом документов —
  блок **«Ancheta cererii de credit»** с кнопкой **«📋 Copiază datele»**
  (копирует всё в буфер «поле: значение» — вставляется в заявку банка) и
  ссылками на копии документов.
* Полный IDNP хранится в заявке (нужен банку); в публичных местах
  по-прежнему используется `IDNP_MASKED`.

### Регистрация клиента оператором + Contragenti (date.gov.md), 2026-08-11

Страница `/UNA.md/orasldev/biro26-clients` получила форму **«Client nou»**
(минимум: денумире + тип физ/юр; опционально IDNO, телефон, e-mail, адрес).
API: `POST /api/biro26/shop-clients` → `Biro26Journal.client_quick_add` —
клиент попадает в ТЕ ЖЕ таблицы, что и регистрация с сайта
(`y_ai_BIRO26.register_client` → `TMS_UNIVERS` + `YBIRO_CLIENT`).

**Кнопка «🏛 Date.gov.md»** — необязательная интеграция с локальной утилитой
`Contragenti` (`/Users/pt/Projects.AI/DATE.gov/Contragenti`, `company_search.py`):

* утилита работает **на компьютере оператора** (`http://127.0.0.1:9393`,
  CORS `*`), поэтому её вызывает сам браузер бэк-офиса — серверу она не видна;
* при открытии страницы идёт `GET /health`: если утилита не запущена, кнопка
  притушена и подсказывает это, работа продолжается вручную;
* по клику — `GET /pick?q=<IDNO или название>&lang=ro&timeout=300&format=xml`:
  открывается окно утилиты, оператор выбирает компанию и нажимает «Вернуть
  контрагента», из XML заполняются **denumire, IDNO, adresa**, тип → «juridică»;
  показывается дата регистрации и предупреждение, если компания ликвидирована;
* если браузер блокирует вызов `http://127.0.0.1` со страницы HTTPS (Chrome
  разрешает localhost, некоторые браузеры — нет), выводится ссылка
  «Deschideți Contragenti într-o filă nouă» (`format=html`) для ручного копирования;
* адрес утилиты меняется в localStorage: `contragenti_base` (по умолчанию
  `http://127.0.0.1:9393`).

#### Доработки Contragenti (2026-08-11)

1. **Возврат данных в вызывающую систему.** У `/pick` появился параметр
   `return_to=<URL>`: после выбора компании утилита делает **302 обратно**
   в систему-инициатор с данными в query (`status, idno, denumire, adresa,
   inregistrare, forma_juridica, lichidata, administratori, state`).
   Раньше при переходе из браузера возвращалась HTML-карточка, и поток
   останавливался на странице утилиты. **Демо-режим сохранён** как отдельный:
   `format=html`. Статусы: `ok` / `cancelled` / `timeout`; `state` возвращается
   без изменений (корреляция запроса).
2. **Страница возврата** `/UNA.md/orasldev/biro26-gov-return` принимает данные
   из query и передаёт их окну бэк-офиса через `postMessage` (проверяется
   `origin` и `state`), после чего закрывается.
3. **Скачивание утилиты.** Копия лежит в `tools/contragenti/`; маршрут
   `/UNA.md/orasldev/biro26-contragenti.zip` собирает архив на лету (доступен
   только авторизованному оператору). Если `GET /health` не отвечает, на
   странице «Клиенты» сразу появляется ссылка «⤓ Descarcă utilitarul».

Порядок работы кнопки «🏛 Date.gov.md»: `fetch` (быстро, Chrome) → при
блокировке `http://127.0.0.1` со страницы HTTPS — окно с `return_to`
(данные всё равно возвращаются) → если и окно закрыто, работа вручную.

### MAIB Checkout — PRODUCTION (2026-08-11)

Контур **officeplus.md** переведён на боевой MAIB Checkout
(`https://api.maibmerchants.md`), банк подтвердил соответствие сайта.

* `YBIRO_SETTINGS`: `PAY_MAIB_PROJECT_ID` = боевой ClientId,
  `PAY_MAIB_SANDBOX` = `0`, `PAY_MERCHANT_NAME` = `OfficePlus` (убрано «DEMO»).
* Секреты (`ClientSecret`, `SignatureKey`) — ТОЛЬКО в `/home/ubuntu/artgranit/.env`
  на 92.5.130.1 (`BIRO26_MAIB_PROJECT_SECRET`, `BIRO26_MAIB_SIGNATURE_KEY`,
  chmod 600). В репозиторий и в Oracle секреты не попадают. Резервная копия
  прежнего `.env` — рядом (`.env.bak.<timestamp>`).
* Проверено вживую: токен от боевого API получен; тестовый checkout создан —
  `https://checkout.maib.md/…` (списаний нет).
* Callback/success/fail идут на `notify_public_base` = `https://officeplus.md`.

⚠ `YBIRO_SETTINGS` общий для обоих контуров: копия nufarul тоже увидит боевой
ClientId, но БЕЗ секрета в своём `.env` — оплата там просто не инициируется.
Реальные списания с тестовой копии невозможны.

### Liber Card — размещение логотипов

Партнёрская рассрочка — **6 плат��жей** (активный пакет «Liber Card / 6 rate»,
0%, до 50 000 лей). На главной добавлен баннер «Cumpără în 6 rate fără dobândă»
(синий maib, ведёт в корзину). Официальные файлы логотипов кладутся в
`static/biro26/pay/libercard.svg` — после этого логотип появляется сам и в
подвале, и на баннере (backend отдаёт список существующих файлов через
`window.PAY_LOGOS`). Пока файла нет — баннер показывается без логотипа,
в подвале остаётся текстовый бейдж.

### Единая цена в рассрочку (2026-08-12)

Расхождение на карточке товара («Preț ofertă în rate: 239,77» против
«Preț în rate: 246,03» при цене 208,50) возникло из-за **двух источников**
одного и того же числа:

* бейдж под ценой считался по настройке `RATE_LIBER_PCT` (была 15% — от
  старого пакета «Liber Card / 3 rate», 5% + 10%);
* блок кредита считался по РЕАЛЬНОМУ активному пакету «Liber Card / 6 rate»
  (8% + 10% = 18%).

После того как 06.08 оставили только 6 платежей, настройка осталась прежней.
Исправлено: `_biro26_site_ctx()` берёт процент из **самого дешёвого активного
пакета Liber Card** (`markup_pct` плана + `transport_markup_pct` организации);
`RATE_LIBER_PCT` остаётся лишь резервом, если офферы недоступны. Теперь при
любом изменении тарифов в кредит-админке бейдж меняется автоматически и
всегда совпадает с модалкой оплаты.

### Витрина и бэк-офис: бренд, артикул, «Produsul zilei» (2026-08-13)

Четыре правки по замечаниям владельца — версия приложения `2026.08.13`.

**1. Бренд-посредник убран с карточки товара.** В `BIRO26_GOODS` содержимое
двух колонок не соответствует их именам: `BRAND` хранит **посредника**
(Crafti, Birovits, Biblion — оптовиков, через которых закупаемся), а
`FURNIZOR` — **настоящую марку** товара (DELI, STANGER, OfficeSpace).
Строка `Cod:` на карточке товара (`site_product.html`) показывала `BRAND`,
то есть посредника. Теперь в ней только артикул и штрих-код.

**2. Штрих-код и артикул на карточках каталога.** `cardHtml()` в
`static/biro26/site.js` печатает `CODVECHI · BARCODE` под названием
(стиль `.product-code` в `landing/styles.css`). Данные уже приходили в
ответе `/api/biro26/shop/products` — новых запросов к Oracle не добавилось.

**3. Колонки BRAND / FURNIZOR в гриде «Sursă mărfuri».** Из-за того же
перекоса в источнике под заголовком BRAND был виден посредник. В
`backoffice-tabs.js` ячейки и оба фильтра поменяны местами: селект «Brand»
читает и фильтрует по колонке `FURNIZOR`, селект «Furnizor» — по `BRAND`.
Имена колонок в Oracle и в API **не менялись** (их использует импорт), правка
только на уровне отображения.

**4. «Produsul zilei» управляется вручную.** Backend (`YBIRO_SITE_DEAL`,
`Biro26Site.deal_save`) существовал, но страница
`/UNA.md/orasldev/biro26-site-admin` требовала знать COD наизусть и не была
никуда прилинкована. Добавлены: поиск товара по названию/артикулу/штрих-коду
с подстановкой COD и превью выбранной позиции, а также плитка «Vitrina ·
Pagina principală» на хабе Biro26. Пустой/выключенный override = товар дня
выбирается автоматически (детерминированно по дню).

**Побочно исправлен `UX_TMS_WEBAPPVERS_CUR`.** Уникальный индекс был создан
как `(APP_CODE, CASE WHEN IS_CURRENT='1' THEN '1' END)`. Oracle пропускает
запись индекса, только когда **все** колонки ключа NULL, поэтому пара
`('site', NULL)` допускалась лишь один раз — вторая по счёту архивная версия
падала с `ORA-00001`, и `scripts/set_app_version.py` не мог обновить номер.
Индекс пересоздан как `CASE WHEN IS_CURRENT='1' THEN APP_CODE END`
(`sql/biro26/18_tms_webappvers.sql`); демоушен + вставка выполняются одним
PL/SQL-блоком.

### «Preț în rate» — один источник, и дерево каталога (2026-08-14)

**Цена в рассрочку снова расходилась** (телевизор 19.999 лей: бейдж
«Preț ofertă în rate: 23.598,82», блок кредита «Preț în rate: 20.998,95»).
Причин две, обе устранены:

* бейдж считался по **одному** проценту (`liber_pct`, самый дешёвый пакет
  Liber Card = 18%) и **не проверял лимиты суммы** пакета;
* блок кредита брал **минимум по всем** пакетам, и им оказывался
  «Microinvest / Standard 6-48 luni» — наценка всего 5%, но **39% годовых**.
  Клиент видел 20.998,95 лей и не платил столько никогда: с процентами выходит
  дороже всех остальных вариантов.

Правило теперь одно: **одним числом можно описать только беспроцентный
пакет** (`annual_pct = 0` и `monthly_fee_pct = 0`) — там финансируемая цена и
есть всё, что платит клиент. Хелпер `_biro26_rate_plans()` (app.py) отдаёт
список таких пакетов с их лимитами (`{p: эффективная наценка, mn, mx}`),
шаблон кладёт его в `window.RATE_PLANS`, а `rateBest(price)` в
`static/biro26/site.js` берёт минимальную подходящую по сумме цену. Этой
функцией пользуются **все четыре места**: карточки каталога, бейдж под ценой,
заголовок блока кредита на карточке товара и старая витрина `shop.html`
(включая её модалку заявки). `RATE_LIBER_PCT` / `RATE_LIBER_MIN` остались
резервом, если офферы недоступны.

Контрольные значения на текущих тарифах: 19.999 → **22.998,85** (EasyCredit
0%, 5%+10%); 208,50 → **246,03** (Liber Card 18%, EasyCredit не проходит по
минимуму 1.000); 100 → 118,00.

**Дерево каталога: стрелка не закрывала группу.** Открытость считалась как
`OPEN.has(g) || F.grupa === g`, поэтому у группы, по которой идёт фильтрация,
`toggleGrp` убирал её из `OPEN`, а второе условие тут же открывало обратно.
Теперь состояние держит **только** множество `OPEN`; группа из deep-link
добавляется в него при инициализации, `pickGrupa`/`pickCat` — при выборе.

**Хлебные крошки** на `/catalog` показывают путь:
`Pagina principală › Catalog › Rechizite de birou › Ascutitoare`. Названия
переводятся из дерева (`grupa_ru` / `cat_ru`), «Catalog» сбрасывает фильтры,
группа возвращает к группе целиком. Перерисовываются вместе с сайдбаром, в
том числе при переключении языка (`onLangChange`).

### Атрибуция соцсетей → WordPress + плагин Social Analytics (2026-08-14)

Контур «как в лучших e-commerce» (WooCommerce Order Attribution / Matomo):

**1. Захват — ядро сайта** (`models/biro26_social.py` + хуки в `app.py`).
На каждой GET-странице витрины (`biro26-site`, `biro26-1shop`, `biro26-shop`)
ловятся клик-ID всех платформ: `fbclid` (Meta), `gclid`/`gbraid`/`wbraid`
(Google Ads), `ttclid` (TikTok), `twclid` (X), `msclkid` (Bing), `yclid`
(Яндекс), `li_fat_id` (LinkedIn), `igshid`/`igsh` (Instagram), `ScCid`
(Snapchat), `epik` (Pinterest), `mc_eid` (Mailchimp) — плюс все `utm_*` и
классификация по referrer (organic из facebook/instagram/t.me/vk/ok/tiktok/
youtube/google/yandex...). `fbclid` + referrer instagram = канал Instagram.

**2. Cookie атрибуции** — first-party, 90 дней (стандарт Meta/Google):
`op_vid` (анонимный ID посетителя) и `op_attr` (первое и последнее касание —
канал, utm_source, кампания, время). IP хранится только как короткий
солёный SHA-256 (без персональных данных).

**3. Хранение — в WordPress**, как будто WP стоит на приёме внешнего
трафика: таблицы `wp_op_social_visit` (атрибутированные визиты) и
`wp_op_social_conv` (конверсии) в MySQL `officeplus_wp`. Пишет Flask через
pymysql **асинхронно** (очередь + daemon-поток, fail-silent): если MySQL
недоступен — сайт не замедляется и не падает. Креды в `.env`
(`WP_DB_NAME/USER/PASSWORD/HOST`, извлечены из `wp-config.php` на сервере,
в репозиторий не попадают).

**4. Конверсии** пишутся на четырёх точках: `/api/biro26/shop/invoice`
(счёт из корзины), `/api/biro26/b2b/order`, `/api/biro26/shop/credit/apply`
(анкета Microinvest) и `/api/biro26/shop/credit/request` — с first/last
каналом, кампанией, суммой и номером документа; без атрибуции канал
`direct` (базовая линия для сравнения).

**5. Анализ — WP-плагин `officeplus-social-analytics`** (активирован на
обоих контурах, меню «Social Analytics» в админке WP + виджет на Dashboard):
по каналам — клики, посетители, конверсии, конверсия %, сумма; топ-кампании
по `utm_campaign`; последние конверсии. Периоды 7/30/90/365 дней.
Активация плагина сама создаёт таблицы (dbDelta), Flask-сторона делает то
же через `CREATE TABLE IF NOT EXISTS` — кто первый.

**6. Гигиена URL**: после захвата `site.js` убирает трекинг-параметры из
адресной строки (`history.replaceState`), функциональные (`grupa`, `q`...)
не трогаются — ссылка при копировании чистая.

Развёрнуто на обоих контурах: officeplus (WP `/var/www/officeplus`) и
nufarul (WP `/var/www/wpuna/.../biro26-wp`). Проверено сквозняком: заход с
реальным fbclid из Facebook → строка в `wp_op_social_visit` (канал
facebook), `utm_source=tg` → telegram, `gclid` → google-ads; cookie
корректно читается обратно при конверсии (экранирование Werkzeug учтено).
Тестовые строки удалены. `pymysql` добавлен в `requirements.txt`.

### Рассинхрон деплоя, картинки impreso, health (2026-08-15)

По заданию импорт-команды (`docs/Biro26/TASK_WEB_DEPLOY_SI_IMAGINI_IMPRESO.md`).

**Причина рассинхрона** — точечные патчи: на officeplus уезжал список файлов,
который поддерживался вручную, и `app.py` оказался из одного коммита, а
`controllers/biro26_controller.py` — из другого (`pt/sources` давал 500 вместо
401, `/api/biro26/img` — 404). **Деплой переведён на полное дерево**: `git
archive HEAD` (29,5 МБ, только отслеживаемые файлы) распаковывается поверх
`/home/ubuntu/artgranit` на обоих контурах — venv/.env/wallet не тронуты,
выборочных списков больше нет. Рядом кладётся файл `DEPLOY_COMMIT`.

**`GET /api/biro26/health`** (публичный): `commit` (из `DEPLOY_COMMIT`, локально
из git), `started_at`, `routes`, `missing_controller_refs` — список ссылок
`Biro26Controller.<метод>` из app.py, которых нет в контроллере. Тот же
smoke-тест выполняется при старте приложения и пишет предупреждение в
journalctl — рассинхрон виден при загрузке, а не 500-й в проде.

**Заглушки «нет изображения»** (просьба §3): в `models/biro26_imgproxy.py`
добавлены `STUB_MARKERS` (`noimage`, `no-image`, `no_image`, `placeholder`,
`default.jpg`) и `is_stub()`; `proxy_url()` превращает такие URL в `NULL` —
защита работает во всех трёх местах подстановки в `biro26_oracle_store.py`.

**`/api/biro26/site/config` ускорен с ~5 с до ~0,2 с**: каждая интерогация шла
через thick-подпроцесс Oracle (~1 с+), а config() делает 3–4. Введён кеш всей
конфигурации (60 с) со **stale-while-revalidate** (протухший ответ отдаётся
мгновенно, обновление в фоне) и прогревом при старте приложения; любой save в
site-admin инвалидирует кеш немедленно.

Проверено на бою (оба контура, commit `0200874`): pt/sources → 401; img-прокси
→ 200 image/jpeg; SSRF-тесты (evil.example.com, 127.0.0.1) → 400; в выдаче
products 191/200 картинок impreso идут через `/api/biro26/img?u=`, чужие
HTTPS (papirus.md) не тронуты, stub'ов нет; полный обход 74 GET-маршрутов —
только штатные 401/200.

## Доступ к базе: пул долгоживущих воркеров (требование)

Правило для каждого модуля, который ходит в ERP, — и для каждой новой задачи,
где такая система проектируется:

1. **Никаких процессов на запрос.** Обращения к Oracle идут через
   `models/biro26_db.py` — пул долгоживущих воркеров (`--serve`). Запуск
   процесса на каждую интерогацию стоил ~1,7 с и был главной причиной
   медленного ответа сайта (замер 26.08.2026).
2. **Чтения** переиспользуют удержанное соединение: они не трогают
   состояние сессии. **Записи** (dml/plsql/script) всегда получают свежее
   соединение — они выставляют контекст сессии (`SET_ENV`: период,
   пользователь), и он не имеет права утекать в следующие запросы.
3. **Один `execute_script` — одна транзакция.** На это опирается запись
   документов в ERP; ломать нельзя.
4. **Таймаут убивает процесс** — сессия Oracle падает и откатывается.
   Это страховка от чужих блокировок, её нельзя заменять «мягким» ожиданием.
5. Выключатель на случай беды: `BIRO26_WORKER_POOL=0` возвращает старый
   транспорт (процесс на запрос). `BIRO26_WORKER_POOL_SIZE` — размер пула.

Ориентиры скорости после перехода: чтение ~0,16 с, запись ~1,1 с,
тестовый прогон 4,6 с. Если новый код снова показывает секунды на чтение —
что-то пошло мимо пула.

## Проекты — папки, и никто никому ничего не затирает (требование)

Правило для всего, что добавляется в портал:

1. **Модуль — это папка `modules/<ключ>/`.** Ядро находит её само, ничего
   дописывать в общий код не нужно. Отсюда и главное свойство: выкладка
   одной ветки не может унести чужие маршруты — они лежат в чужой папке.
2. **Никаких маршрутов в общем `app.py`.** Проверено на своей шкуре:
   27.08.2026 контур переставили на другую ветку, где `robots.txt` и
   `sitemap.xml` в `app.py` не было, — публичный сайт остался с 404 по
   обоим адресам. Теперь они в `modules/seo/`.
3. **Адреса в корне сайта** (`/robots.txt`, `/sitemap.xml`) объявляются
   списком `root_paths` в `module.json`. Ядро подключает их без префикса и
   **отвергает** попытку занять адрес, который уже держит другой модуль:
   молча перекрыть чужое невозможно. Кто что занял — видно в манифесте.
4. **Общие файлы трогает только тот, кто обязан.** Если правка кажется
   неизбежной в `app.py` — сначала проверить, не решается ли она папкой.
5. **Слияние веток не должно решать, чьи маршруты выживут.** Если ответ на
   вопрос «а что будет при выкладке другой ветки» — «пропадёт», значит
   место выбрано неверно.

Проверить, что модуль подключился: `/api/biro26/health` и отчёт ядра —
там видно `loaded`, `skipped`, `failed` с причинами.

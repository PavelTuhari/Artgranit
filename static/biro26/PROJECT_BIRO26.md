# BIRO26 (OfficePlus) — документация проекта

> Модуль Flask-платформы **Artgranit** для работы с ERP OfficePlus: импорт
> номенклатуры, товары/остатки/варианты, цены по периодам, публичный
> интернет-магазин с саморегистрацией клиентов, счета на оплату в ERP,
> **онлайн-оплата (MAIB / MIA)**, печатные формы (2 PDF-движка), вложения
> к документам, уведомления (email/Telegram/WhatsApp + PDF).
> Отображаемое имя настраивается одной переменной — по умолчанию **OfficePlus**.
>
> Прод: `https://nufarul.eminescu.md/` и `https://officeplus.md/` ·
> Актуально на 2026-07-13 (PR #2–#40).

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
| `/UNA.md/orasldev/biro26-notify-settings` | Setări: уведомления (email/TG/WhatsApp) · **платежи MAIB/MIA** · товаров на странице |
| `/UNA.md/orasldev/biro26-import-pt` | Импорт файлов BIRO26PT (dry-run → commit, картинки из URL, авто-цены) |
| `/UNA.md/orasldev/biro26-translations` | **Traduceri**: словарь группировки RU/EN — ручная правка, CSV export/import, 🤖 автоперевод (OCI Multi-Translate) |
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
При создании счёта (и при успешной онлайн-оплате) — email (SMTP из .env) /
Telegram (Bot API) / WhatsApp по включённым каналам; настройки в админке
(`YBIRO_SETTINGS`, ключи `NOTIFY_*`), отправка fire-and-forget (фоновый
поток). В сообщение включается **подписанная публичная ссылка на PDF**
(HMAC по `kind:cod`, доступ только к этому документу; ключ =
`BIRO26_API_TOKEN`). WhatsApp — два режима (`NOTIFY_WA_MODE`):
`callmebot` (бесплатно, текст + ссылка на PDF) или `cloud`
(**WhatsApp Cloud API**, Meta — PDF приходит документом-вложением;
нужны `NOTIFY_WA_CLOUD_TOKEN` / `NOTIFY_WA_CLOUD_PHONE_ID` /
`NOTIFY_WA_CLOUD_TO`). Для ссылок обязателен `NOTIFY_PUBLIC_BASE`
(публичный URL сайта, напр. `https://officeplus.md`).

### 4.6a Онлайн-оплата (MAIB e-commerce / MIA instant payments)
Оплата «контулуй де плата» прямо из корзины магазина. Референс-интеграция:
`github.com/Unisim-Soft-Com/Telegram-Bots/unisim_BileteGaraAutoBTA`.
Код: `models/biro26_pay.py`; журнал — таблица **`YBIRO_PAYMENTS`**
(DOC_COD, METHOD, ORDER_ID `BIRO26-<doc>-<ts>`, PAY_ID, AMOUNT,
STATUS PENDING→PAID/FAILED, RRN). Успешная оплата шлёт уведомление 4.6.

**MIA** (метод по умолчанию; QMoney `api.qiwi.md`): `v1/auth`
(apiKey+apiSecret) → `qr/create-qr-dynamic` (IBAN мерчанта, сумма
документа, validSeconds 900) → в корзине показывается QR (base64) +
ссылка; UI опрашивает `qr/get-qr-extension-status` каждые 5 с до
подтверждения; дополнительно принимаем `callbackEchoUrl`.

**Achitare prin CREDITARE (rate)** — организации кредитования и их пакеты
**динамические** (таблицы `YBIRO_CREDIT_ORG` / `YBIRO_CREDIT_PLAN`, админка
`/UNA.md/orasldev/biro26-credit-admin`): режим `manual` (условия задаются в
админке) или `api` (сохраняется API_URL партнёра; адаптер per-организация).
**Метод расчёта цен при кредите**: цена каждой строки счёта увеличивается на
«комиссию магазина» пакета (`MARKUP_PCT` — пакеты EasyCredit 0%: 4л/6%,
6л/7.8%, 10л/12%, 12л/13.8%, 15л/16.8%, 24л/23.4%; Shop 12%/3–36л:
1.55%/мес + 25 lei); рата = финансируемое/мес + фин.×(годовая/12) +
фин.×комиссия_мес; сумма финансирования 1 000–100 000 MDL (проверяется).
В корзине — «Metodă de achitare: Credit/rate» с живой симуляцией
(орг+пакет+луны+аванс, рата, total); в окне товара — бейдж «💳 În rate de la
X lei/lună». Выбор сохраняется на документе (`YBIRO_DOC_META.CREDIT_*`).
Расчёт эстимативный — финальную оферту даёт организация. Публичные API:
`GET /shop/credit/offers`, `POST /shop/credit/calc`. Источник условий:
`TaskDezvoltare/1 credite` (tabelul EASYCREDIT).

**MIA transfer la telefon (pers. fizică)** — ручной метод, работает
**параллельно** с остальными: кнопка «📲 Transfer MIA la telefon» показывает
инструкцию (перевод MIA из банковского приложения на номер из настроек,
сумма документа, в комментарии — `order_id`); платёж пишется в журнал
PENDING и **подтверждается оператором вручную** после получения перевода.

**MAIB** (карта; `api.maibmerchants.md/v1`): `generate-token`
(projectId+projectSecret) → `pay` (amount/currency MDL/clientIp/orderId/
okUrl/failUrl/callbackUrl) → редирект покупателя на `payUrl`. Возврат и
callback приходят на `/api/biro26/pay/maib-callback`; статус **всегда
перепроверяется сервером через `pay-info/<payId>`** (status OK + RRN) —
параметрам из URL не доверяем. Возможен `refund` (в референс-классе).

**Настройки** (админка → Setări, карточка «💳 Plăți online»):

| Настройка | Где хранится | Ключ |
|---|---|---|
| Вкл/выкл | YBIRO_SETTINGS | `PAY_ENABLED` (0/1; поставляется выключенным) |
| Метод по умолчанию | YBIRO_SETTINGS | `PAY_METHOD` = `mia` \| `maib` \| `both` |
| Название продавца | YBIRO_SETTINGS | `PAY_MERCHANT_NAME` |
| MAIB Project ID | YBIRO_SETTINGS | `PAY_MAIB_PROJECT_ID` |
| **MAIB Project Secret** | **.env** | `BIRO26_MAIB_PROJECT_SECRET` |
| MIA apiKey | YBIRO_SETTINGS | `PAY_MIA_API_KEY` |
| **MIA apiSecret** | **.env** | `BIRO26_MIA_API_SECRET` |
| MIA IBAN мерчанта | YBIRO_SETTINGS | `PAY_MIA_IBAN` |
| MIA transfer на телефон — вкл | YBIRO_SETTINGS | `PAY_MIA_P2P_ENABLED` (0/1, параллельно) |
| MIA transfer — номер телефона | YBIRO_SETTINGS | `PAY_MIA_P2P_PHONE` |
| База callback-URL | YBIRO_SETTINGS | `NOTIFY_PUBLIC_BASE` (общая с 4.6) |

Секреты вводятся в той же карточке админки, но пишутся **только в .env**
(паттерн SMTP: пустое поле = не менять; применяются без рестарта).
Метод показывается в магазине только когда включён `PAY_ENABLED` **и**
заполнены его креды (ID/key в настройках + секрет в .env).
Чек-лист включения: ввести креды в админке → флаг «Activat» → кнопки
оплаты появляются в корзине после создания счёта (без рестарта).

### 4.7 Импорт
Мастер импорта: источник — файл-feed или **любой SELECT** (`YBIRO_SRC_DEF`,
guard только-SELECT), просмотр колонок/сэмпла, AI-подсказка маппинга,
профили (`YBIRO_MAP_PROFILE/PARAM`, параметры `g_*` пакета
`YBIRO_IMPORT_MARFA`): validate → prepare → assign-keys → import в
TMS_UNIVERS/TMS_MPT; группы/даты/цены прайс-листа; линки картинок — в
`TMS_MPT_TVR.IE_LINKADRES`; откат прайс-листа.

### 4.8 Multilingv RO/RU/EN — standard simplu (funcțional WordPress)

**Principiul**: traducerea în 3 limbi este un **standard simplu**, realizat prin
funcționalul **standard WordPress** (pagini obișnuite), în paralel cu mecanismul
custom al magazinului de vânzări accesibil prin iframe — **gestionat sincron cu
setările WordPress**. Fără plugin-uri multilingve (Polylang/WPML nu sunt necesare).

**Cum e construit**:
1. **Conținutul** trăiește în WordPress ca pagini standard cu **sufix de slug**:
   `<slug>` = română (implicit), `<slug>-ru` = rusă, `<slug>-en` = engleză.
   Există deja toate 7×3: despre-noi, contacte, livrare, retur-produse,
   termeni-si-conditii, politica-de-confidentialitate, metode-de-plata.
2. **Magazinul (iframe)**: comutatorul RO·RU·EN din bara de sus scrie limba în
   `localStorage.biro26_lang`; meniul se traduce (dicționar `NAV_TR` în
   `shop.html`), iar paginile informative se încarcă prin WP REST cu slug-ul
   sufixat (`?info=<slug>&lang=ru`); lipsa traducerii → fallback RO automat.
3. **Subsolul (footer WP)**: un mic script în blocul custom al primei pagini
   (pagina 6, backup: `static/biro26/wp_page6_shop_canonical.html`) citește
   aceeași `biro26_lang` (aceeași origine) și traduce etichetele + linkurile
   subsolului către paginile `-ru/-en`; reacționează live la comutare
   (evenimentul `storage`). Numele/produsele: RO din `TMS_UNIVERS.DENUMIREA`,
   RU din `NAMERUS` (rând secundar în card).

**Gruparea catalogului (grupa/categorie)** — tradusă după principiul
una-shops (`unisimNginx/una-shops-translations-guide`): traducerile sunt
**DATE editabile**, nu cod — dicționarul Oracle **`YBIRO_GRP_I18N`**
(KIND `grupa`/`categorie`, cheia = textul RO, coloane NAME_RU/NAME_EN,
fallback automat pe română). Toate cele 13 grupe sunt traduse RU+EN;
categoriile (~607) se adaugă treptat, tot ca date:
```sql
INSERT INTO YBIRO_GRP_I18N (KIND, NAME_RO, NAME_RU, NAME_EN)
VALUES ('categorie', 'Hartie printer', 'Бумага для принтера', 'Printer paper');
-- кириллица — ТОЛЬКО через python-oracledb (CL8MSWIN1251!)
```
Arborele din magazin (`/shop/tree`) livrează numele traduse; filtrarea
folosește în continuare cheile RO (nimic nu se strică fără traducere).
**Administrare**: pagina `/UNA.md/orasldev/biro26-translations` —
editare manuală inline, export/import CSV și **traducere automată**
(butonul «Tradu tot ce lipsește»): rândurile netraduse pleacă CSV la
serviciul **OCI Multi-Translate** (`BIRO26_TRANSLATE_API_URL`, cheia în
.env `BIRO26_TRANSLATE_API_KEY`; doc: 130.61.111.57/TRANSLATE_API_FOR_AI.md),
progresul se urmărește live (job resumabil — I18N_LAST_JOB), iar la
final rezultatul se importă automat în dicționar.

**📘 Instrucțiune pentru client — cum traduceți mai departe (numai WP admin)**:
1. Intrați în WordPress → **Pagini**. Găsiți pagina română (ex. `Livrare`).
2. **Adăugați o pagină nouă**: titlul în limba țintă (ex. «Доставка»),
   conținutul tradus, iar la **Slug** (Setări pagină → URL) puneți slug-ul
   românesc + sufix: `livrare-ru` (rusă) sau `livrare-en` (engleză). Publicați.
3. Gata — magazinul și subsolul o preiau **automat** (fără deploy, fără setări);
   dacă traducerea lipsește, vizitatorul vede automat varianta română.
4. Modificarea unei traduceri = editați pagina respectivă ca pe oricare alta.
5. Adăugarea unui punct NOU de meniu: cereți adăugarea în `BIRO26_SHOP_NAV`
   (.env) + o linie în dicționarul de traduceri; paginile le creați tot ca la
   pașii 1–2.

## 5. Объекты БД (схема OFFICEPLUS)

**Пакеты**: `Y_AI_BIRO26` (см. 4.4), `YBIRO_IMPORT_MARFA` (импорт, `g_*`).

**Таблицы модуля** (нормализованные, префиксы YBIRO_/BIRO26_):
`BIRO26_GOODS` (feed; GRUPA/CATEGORIE = дерево), `BIRO26_VARIANTS`,
`BIRO26_BARCODES*`, `BIRO26_DETAIL/MASTER` (staging вариантов),
`YBIRO_CLIENT` (+SEQ, клиенты магазина; c 07.2026 + ADDRESS/IDNO/IS_COMPANY —
обязательные поля регистрации), `YBIRO_SETTINGS` (настройки),
`YBIRO_MAP_PROFILE/PARAM` (+SEQ), `YBIRO_SRC_DEF` (+SEQ),
`YBIRO_STOCK_CALC/_ITEM` (+SEQ, снимки остатков),
`YBIRO_PROD_INFO` / `YBIRO_PROD_COMMENTS` (+SEQ — описание товара и
комментарии клиентов для большого окна товара),
**`YBIRO_PAYMENTS`** (+SEQ — журнал онлайн-платежей MAIB/MIA, см. 4.6a),
`YBIRO_*_GTT` (временные), `YBIRO_DUP_*_BAK` / `YBIRO_SYSGR*_BAK` (бэкапы чисток).

**Нативные объекты ERP, которые модуль использует** (не менять!):
`TMS_UNIVERS`, `TMS_MPT(+_TVR/_BARCODE)`, `TPR1D_PERPRLIST`/`VTPR1D_PERPRLIST`
(+INSTEAD OF-триггеры периодов), `VPR*`-вьюхи прайса, `TMDB_DOCS`,
`VMDB_ST201M/D`, `VMDB_DOCS_WORK`, `VMDB_DOCS_OLE`/`TMDB_DOCS_OLE`,
`XNRDOC`, `UN$SOLD.GET_SOLDT`, секвенции `ID_TMS_UNIVERS`/`ID_TMDB_DOCS`/`ID_TMDB_CM`.

DDL: `sql/biro26/01..07*.sql` (05 — описание/комментарии товара; 06 — поля
регистрации клиента; 07 — журнал платежей); идемпотентные деплойеры
`deploy_biro26_*.py`.

## 6. API (97 маршрутов `/api/biro26/...`)

**Публичные** (`/shop/*`): `register` (обязательные поля: имя, адрес
доставки, email, телефон; +IDNO для юрлиц), `login, logout, me` (сессия
клиента) · `products` (каталог: search/grupa/categorie/brand-мульти/
price_min/max/price_date/limit/offset/`with_count=1` — total для
нумерованной пагинации) · `tree`, `brands`, `services`, `variants?cod=` ·
`product/<cod>` (описание+комментарии), `product/<cod>/comment` (POST,
клиентская сессия) · `invoice` (POST items → `{cod,nrset}`) ·
`report/<invoice|order>/<cod>` (PDF; клиент — свои документы; также
`?sig=` — подписанная ссылка из уведомлений и `X-API-Key` — machine API) ·
**платежи**: `pay/methods` (активные методы), `pay/<mia|maib>` (POST
`{cod}`, сессия клиента → QR/base64 или `pay_url`), `pay/mia-status?order=`.

**Для внешних приложений** (auth: заголовок `X-API-Key` = `BIRO26_API_TOKEN`):
`GET /api/biro26/docs?client=<имя|код|#nr>&limit=` — список документов клиента
(номер в hashtag-форме `#338` — тот, что виден в любом нативном приложении,
дата, клиент, сумма, внутренний COD) · `GET /api/biro26/report-by-nr/
<invoice|order>/%23338` — **PDF по НОМЕРУ документа** (hashtag; также `?sig=`
HMAC-хэш для ссылок без токена) · `GET /api/biro26/doc/<cod>` — JSON.
Демо внешнего приложения: `scripts/biro26_docs_demo.py` (stdlib, CLI+интерактив).
Прикрепление PDF в `VMDB_DOCS_OLE` — фоновое (не блокирует ответ, даже если
нативный клиент держит OLE-строку заблокированной).

**Callback-и платежей** (публичные, верифицируются через API банка):
`/api/biro26/pay/maib-callback` (ok/fail/callback от MAIB → pay-info),
`/api/biro26/pay/mia-callback` (echo от MIA → status API).

**За auth** (сессия платформы): source/goods/univers/suppliers/groups/
categories (импорт и словарь) · mapping/profiles · prices (+dates/import/
rollback) · products (+`<cod>`, tree rename/move, price, price-history,
price/delete, brands, categories) · univers/`<cod>`/variants, variants/`<cod>` ·
product-desc/`<cod>` (PUT), product-comment/`<id>` (DELETE) ·
stock (calculate/latest/items) · sources (+AI) · report-templates
(+`<name>`, preview), report-engines · notify-settings, notify-test ·
**pay-settings** (GET/PUT — карточка «Plăți online», секреты → .env) ·
shop-settings (GET/PUT — товаров на странице `SHOP_PAGE_SIZE`) ·
pt/* (импорт BIRO26PT: upload/analyze/preview/commit/remap) ·
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

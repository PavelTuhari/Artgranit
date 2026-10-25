# Набор готового контента — посты, письма, описания

*17.10.2026 · тексты под каналы из `STRATEGIA_PROMOVARE.md`; цифры — из `PROSPECT_ARTGRANIT.md`. Всё можно публиковать как есть, заменив `{…}`.*

---

## A. Заказчики

### A1. Facebook / Instagram (RO) — пост с видео 45 с

> **Magazin online care știe ce aveți pe raft chiar acum.**
> La officeplus.md prețul, stocul și comanda vin direct din evidența firmei — fără
> export «o dată pe zi», fără introducere dublă. Comanda de pe site devine document
> în contabilitate în aceeași secundă.
> Aveți deja evidența pe Oracle / UNA.md? Magazinul se pornește în 3 zile, pe baza
> dumneavoastră. Rate, e-Factura, chat-asistent și cabinet client — incluse.
> 📞 +373 620 07 211 · demo pe datele dvs. — gratuit.
> #magazinonline #ERP #Moldova #eFactura #Balti

### A2. Facebook (RU) — e-Factura

> **Входящие накладные из e-Factura — в учёт за 5 минут, не за полдня.**
> Загружаете XML с портала SFS — система сама находит поставщика по IDNO, товары по
> точному совпадению, заводит новые карточки со штрихкодом и ценой по вашему правилу,
> создаёт документ прихода. 47 накладных, 352 позиции — одной кнопкой.
> Работает прямо в вашей базе UNA.md. Покажем на ваших накладных.
> 📞 +373 620 07 211

### A3. LinkedIn (RO) — от имени владельца

> Am pus pe site un lucru simplu: **prețul în rate lîngă prețul obișnuit**.
> EasyCredit, Iute, Microinvest, MAIB — pachetele vin din ERP, adaosul e același pe
> vitrină, în coș și în factură (am învățat asta după un incident, cînd clientul vedea
> un preț și plătea altul — acum e verificat de 4 teste).
> Asta e Artgranit: 21 de module peste Oracle/UNA.md, fiecare într-un folder al lui.
> Dacă aveți evidență pe Oracle și vreți magazin, cabinet client sau e-Factura —
> scrieți-mi, facem demo pe baza dvs. într-o zi.

### A4. Письмо клиентам UNA.md (RU)

**Тема:** Ваша учётная система уже умеет интернет-магазин — покажем за один день

Здравствуйте, {Имя}!

Вы ведёте учёт в UNA.md на Oracle. Это значит, что у вас уже есть всё для
интернет-магазина: товары, цены, остатки, клиенты. Не хватает только витрины.

Artgranit ставит её **поверх вашей базы**: заказ с сайта сразу становится документом
в учёте, остатки на сайте — те же, что на складе, рассрочка считается по вашим
пакетам, входящие накладные e-Factura импортируются сами.

Живой пример — магазин OfficePlus (Бэлць, 200 000 товаров), демо: https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site

Предлагаю демо на ваших данных: подключение занимает один день, ничего в вашей
базе не меняется. Удобно {дата}? Ответьте на письмо или позвоните: +373 620 07 211.

С уважением, {Имя}, GRECU OFFICE GROUP SRL

### A5. Google Ads — объявления (RO / RU)

| Заголовок 1 | Заголовок 2 | Описание |
|---|---|---|
| Magazin online pe baza ERP | Stoc și prețuri în timp real | Comanda de pe site = document în evidență. Pornire în 3 zile. Demo gratuit pe datele dvs. |
| Import e-Factura automat | Facturile SFS → evidență | Furnizor după IDNO, mărfuri după denumire, document de intrare gata. Oracle / UNA.md. |
| Интернет-магазин на вашей ERP | Остатки и цены — живые | Заказ с сайта сразу в учёте. Рассрочка на витрине. Запуск за 3 дня. Демо бесплатно. |

Ключевые слова: `magazin online integrat contabilitate`, `import e-factura`, `magazin
online rate`, `интернет-магазин ERP Молдова`, `импорт e-factura`, `сайт для 1С UNA`.

---

## B. Разработчики

### B1. Статья 1 — Habr (RU) / dev.to (EN): план

**Заголовок RU:** «Модуль — это папка: как мы перестали добавлять модули правкой app.py и
получили 0 конфликтов слияния при 10 параллельных ИИ-сессиях»
**Title EN:** "A module is a folder: how a Flask+Oracle portal went from one 9 000-line
app.py to 21 self-registering modules with zero merge conflicts"

1. Боль: 13 модулей, 9 000 строк в `app.py`, каждый модуль = конфликт.
2. Контракт: `modules/<ключ>/__init__.py` экспортирует `blueprint` с именем = ключ; адрес ставит ядро.
3. Ядро запрещает сильнее, чем проверяет: `app.add_url_rule` и `register_blueprint` отключены на время импорта модуля (код).
4. Меню собирается из `url_map` — страница не может быть «невидимой».
5. Тесты изоляции: общий `app.py` не упоминает модуль; общий установщик DDL не тронут.
6. `new_module.py`: worktree + ветка + каркас + тесты + docs + push одной командой.
7. Что это дало с ИИ-агентами: правило №3 (коммит и push каждого шага) и worktree на задачу — после потери кода mTLS-шлюза (дата, разбор).
8. Ссылка на шаблон модуля (GitHub), на документацию ядра.

### B2. Telegram-канал — формат «инцидент → правило» (примеры)

> **Ловушка DDL.** Файл модуля SDA пережил четыре круга ревью и не ставился вовсе:
> `/` стоял только ПОСЛЕ триггера, разделитель режет по `/`, и каждый блок выходил как
> `CREATE INDEX; CREATE TABLE; … END;` — один PL/SQL-оператор, ORA-00911.
> Правило: `/` ставить и ДО, и ПОСЛЕ каждого PL/SQL-блока, установщик один раз прогнать
> вживую. `--dry-run` не доказывает, что схема встанет.

> **TRANSLATE с диакритикой.** База в CL8MSWIN1251: литерал `'ăâîșț'` долетает как
> `aai?s?t`, и `TRANSLATE` превращает «Agrafe» в « grafe». В SQL не транслитерируем —
> нормализуем в Python той же функцией, что и импортёр. Теперь это проверяет тест.

> **Штрихкод есть, а в документе — нет.** У карточки два места: `TMS_MPT_BARCODE`
> (вторичные) и `TMS_MPT.STRIH1_CODPRODUCER` (основной); документ 1209 читает только
> основной. 126 330 карточек имели код в таблице и пустой основной. Заполнили, конвейер
> теперь делает это сам.

### B3. GitHub README шаблона (EN) — первый абзац

> **artgranit-module-template** — the smallest module that the Artgranit core accepts:
> a `blueprint` named after the folder, routes without a prefix (the core mounts it under
> `/UNA.md/orasldev/<key>`), `rules.py` with DB-free logic, `sql/` with its own DDL
> installer, `module.json` for the menu, and two isolation tests that fail if you touch
> shared code. Run `python scripts/new_module.py mykey "My module"` and you get a
> worktree, a branch, the scaffold, tests and the first push.

### B4. YouTube — сценарий «Модуль за 10 минут» (0:00–10:00)

0:00 что такое портал и карта системы (179 страниц, меню само) · 1:00 `new_module.py demo "Demo"` · 2:30 маршрут + шаблон · 4:00 `rules.py` и тест без базы · 5:30 DDL с префиксом и свой установщик · 7:00 тесты изоляции падают, если тронуть `app.py` · 8:30 модуль появился в меню и на карте · 9:30 коммит, push, документ в `docs/`.

---

## C. Oracle

### C1. Письмо партнёр-менеджеру OPN (EN)

**Subject:** ISV reference: modular Flask platform on Oracle 11g + Autonomous DB 23ai (Moldova retail)

Hello {Name},

GRECU OFFICE GROUP SRL (Bălți, Moldova) runs **Artgranit** — a modular web platform on
top of an Oracle-based ERP (UNA.md): e-commerce storefront with 200 000 SKUs, customer
cabinet, instalment credit, SFS e-invoicing, CRM, production floor and infrastructure
monitoring — 30 modules, 179 pages, 1355 automated tests.

What may interest Oracle: the same application works against a legacy **Oracle 11.2**
ERP schema (CL8MSWIN1251, thick client in an isolated worker) and **Autonomous Database
23ai on OCI** (thin, wallet) — a live migration path for SMB ERP customers without a
rewrite. All module data is in normalized Oracle tables with per-module prefixes; DDL is
deployed separately from code.

We would like to join Oracle PartnerNetwork (Build track), publish a joint success story
and list a BYOL image on OCI Marketplace. Live system: https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site ·
developer documentation: https://nufarul.eminescu.md/UNA.md/orasldev/docs/

Could we schedule a 30-minute call?

Best regards, {Name}, {role} · +373 620 07 211

### C2. Кейс (success story) — структура, 2 страницы EN

1. **Customer:** OfficePlus (GRECU OFFICE GROUP SRL), office supplies retail & wholesale, Bălți, Moldova.
2. **Challenge:** ERP on Oracle 11g since 2013; needed storefront, customer cabinet, credit, e-invoicing — without a second database and nightly syncs.
3. **Solution:** Artgranit modular platform; Oracle-first data model; 30 modules; Autonomous DB 23ai for new modules and analytics; OCI Compute.
4. **Results:** storefront live on the ERP database; e-Factura inbound in minutes; instalment price on every product; 1355 tests; 0 merge conflicts with parallel AI-agent development.
5. **Why Oracle:** one data model, two generations of the database, python-oracledb thin+thick, wallet security, OCI Free Tier for demo.
6. **Quote** + architecture diagram + numbers table.

### C3. Заявка на доклад (RoOUG / Developer Live) — abstract

> **"One app, two Oracles: serving a 2013 ERP and Autonomous DB 23ai from the same Flask
> process."** How a modular portal keeps a legacy 11g schema (CL8MSWIN1251, instead-of
> triggers, A$ configuration trees) and a modern Autonomous Database in one codebase:
> thick client in a subprocess worker, per-module prefixes and separate DDL, isolation
> tests, and the engineering rules we wrote after real incidents (DDL delimiters,
> diacritics in TRANSLATE, multi-row INSERT into views). With live code.

---

## D. Общие элементы

### D1. Описание компании (bio, 300 знаков) — RO / RU / EN

- **RO:** Artgranit — platformă web de module peste Oracle și UNA.md: magazin online, cabinet client, rate, e-Factura, CRM, producție, monitorizare — direct pe baza dvs. 30 module, 179 pagini, 1355 teste. GRECU OFFICE GROUP SRL, Bălți.
- **RU:** Artgranit — веб-платформа модулей над Oracle и UNA.md: магазин, кабинет, рассрочка, e-Factura, CRM, производство, мониторинг — прямо на вашей базе. 30 модулей, 179 страниц, 1355 тестов. GRECU OFFICE GROUP SRL, Бэлць.
- **EN:** Artgranit — modular web platform on Oracle & the UNA.md ERP: storefront, customer cabinet, instalment credit, e-invoicing, CRM, production, monitoring — straight on your database. 30 modules, 179 pages, 1355 tests. Bălți, Moldova.

### D2. Хештеги

`#Artgranit #UNAmd #Oracle #AutonomousDatabase #OCI #Flask #Python #ERP #eFactura #magazinonline #Moldova #Romania #AIagents #ClaudeCode`

### D3. UTM-схема

`?utm_source={facebook|instagram|linkedin|google|telegram|habr|devto|email|oracle}&utm_medium={paid|organic|email|partner}&utm_campaign={clienti|dev|oracle}-{тема}` — считается в SEOForge и в `op_attr` (только с согласием на Marketing).

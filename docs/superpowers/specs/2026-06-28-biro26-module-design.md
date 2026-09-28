# Biro26 — Дизайн модуля (фазы 1–5)

**Дата:** 2026-06-28 · **Версия:** 1.0
**ТЗ:** `docs/Biro26/TZ_BIRO26_App.md`
**Источники бизнес-логики:** `/Users/pt/Projects.AI/BIRO26/` (`YBIRO_Import_Marfa.pkg.sql`, `IMPORT_TMS_UNIVERS.md`)
**Целевая СУБД модуля:** `officeplus@//orange.una.md:4024/cloudbd.world` (отдельная от Artgranit wallet-БД)

---

## 1. Решения по объёму (зафиксировано с заказчиком)

- **Объём этой итерации:** этапы ТЗ **1–5** (полный импорт цен).
- **Состояние БД officeplus:** все объекты (`BIRO26_GOODS`, `TMS_*`, `VPR*`, пакет `YBIRO_Import_Marfa`) **уже существуют**. Приложение строится поверх них.
- **Интеграция:** в существующий Flask `app.py`, по образцу модуля AEI (`controllers/aei_controller.py`, `models/aei_oracle_store.py`, `templates/aei/`, маршруты `/UNA.md/orasldev/aei*`).
- **Хранение профилей маппинга:** в officeplus, нормализовано, префикс `YBIRO_` (подтверждено).
- **Пароль officeplus:** в `.env`, как существующий `DB_PASSWORD` (подтверждено).

### Явно вне объёма (последующие фазы)
- Фаза 6: таблица `YBIRO_IMPORT_LOG`, просмотрщик логов, перевод пакета на autonomous-tx логирование. Временно: захват `DBMS_OUTPUT` для отчётов.
- Фаза 7: единая кнопка `import_all` + отчёты (отдельные шаги вместе уже дают полный импорт).
- Фаза 8: приходы/продажи (`TMDB_*`).

---

## 2. Архитектура

Новый модуль монтируется в `app.py` так же, как AEI, но работает со **вторым, отдельным** Oracle-подключением к officeplus, независимым от Artgranit wallet-БД.

```
templates/biro26_admin.html        — лендинг/лаунчер (как aei_admin.html)
templates/biro26/backoffice.html   — основной трёхъязычный UI с вкладками
controllers/biro26_controller.py   — тонкие обработчики (@staticmethod), {success,data?,error?}
models/biro26_oracle_store.py      — Biro26Store: запросы + вызовы пакета YBIRO_*
models/biro26_db.py                — Biro26DB: подключение к officeplus (НОВЫЙ слой)
sql/biro26/01_biro26_app_tables.sql— единственный НОВЫЙ DDL (профили маппинга), на officeplus
docs/Biro26/README_BIRO26.html     — документация модуля (по образцу README_AEI.html)
```

**Маршруты** (по конвенции AEI):
- UI: `/UNA.md/orasldev/biro26`, `/UNA.md/orasldev/biro26-tz`, `/UNA.md/orasldev/biro26-docs`
- API: `/api/biro26/*` (см. §6)

### Принцип изоляции
- `biro26_db.py` — единственное место, знающее как подключиться к officeplus. Возвращает тот же контракт, что `DatabaseModel` (`{success, columns, data, rowcount, message}`).
- `biro26_oracle_store.py` — единственное место с SQL/вызовами пакета. UI и контроллер не содержат SQL.
- `biro26_controller.py` — разбор HTTP-запроса, валидация входа, делегирование в store.

---

## 3. Слой подключения (subprocess-воркер — главное отличие от остальных модулей)

> **ВАЖНО (уточнено по факту, 2026-06-28):** officeplus — это **Oracle 11g (11.2.0.4)**, charset **CL8MSWIN1251**. python-oracledb может работать с 11g **только в thick-режиме** (Instant Client; thin даёт `DPY-3010`). Thick — переключатель уровня **всего процесса**, и его включение **ломает** существующее thin+wallet подключение основного приложения к Oracle Cloud (проверено: `ORA-12506`), от которого зависит production `nufarul.eminescu.md`. Поэтому Biro26 **не** подключается в основном процессе.

- **Изоляция через subprocess-воркер.** `models/biro26_worker.py` — отдельный короткоживущий процесс: включает thick (`init_oracle_client`), подключается к officeplus, выполняет запрос/DML/PLSQL/script, печатает JSON в stdout. Обмен JSON через stdin/stdout. Основной Flask остаётся **thin** — cloud/production не затрагивается.
- **`models/biro26_db.py` (`Biro26DB`)** — в основном процессе; на каждый вызов запускает воркер через `subprocess.run([sys.executable, worker])`, парсит JSON. Контракт совпадает с `DatabaseModel`:
  - `execute_query(sql, params) -> {success, columns, data, rowcount, message}`
  - `execute_dml(sql, params) -> {success, rowcount, message}` (commit в воркере)
  - `call_proc(plsql, params, capture_output=False) -> {success, output_lines[], message}` — `plsql` — полный блок; `g_*` пакета ставятся в **том же** блоке (session state).
  - `execute_script([{sql,params,kind}]) -> {success, results[], message}` — несколько операторов в **одной** транзакции (атомарные multi-statement, напр. создание профиля).
  - `test_connection() -> {success, version, error}`.
- **NLS** в воркере после connect: `NLS_LANGUAGE='ENGLISH' NLS_TERRITORY='AMERICA' NLS_NUMERIC_CHARACTERS='. '` (детерминированный парсинг цен; нейтрализует `en_MD`/`ORA-12705`).
- **Charset:** thick-клиент отдаёт данные в UTF-8 (Cyrillic `NAMERUS` читается корректно). Данные ERP практически без диакритики (RO без диакритик + RU кириллица). Запись в officeplus — в пределах CL8MSWIN1251.
- **Особенности Oracle 11g для всего SQL модуля:** нет `FETCH FIRST/OFFSET` — пагинация только через `ROWNUM` (паттерн: `SELECT * FROM (SELECT a.*, ROWNUM rn FROM (<inner ORDER BY> ) a WHERE ROWNUM<=:hi) WHERE rn>:lo`).
- **Конфигурация** в `config.py`/`.env`: `BIRO26_DB_USER=officeplus`, `BIRO26_DB_PASSWORD` (только в `.env`), `BIRO26_DB_DSN=orange.una.md:4024/cloudbd.world`, `BIRO26_NLS_*`, `BIRO26_INSTANT_CLIENT=/Users/pt/Downloads/instantclient_23_26` (сборка `23_26` работает; `23_3` даёт `ORA-28041`). Видны/тестируются во вкладке «Настройки».
- **Deploy на сервер (позже):** потребуется Instant Client на Linux-сервере + сетевой доступ к `orange.una.md:4024`; основной thin-контур не меняется. Пока модуль — локальный.

---

## 4. Бизнес-логика: вызываем пакет, не дублируем SQL

Все изменения справочника/прайса проходят через пакет `YBIRO_Import_Marfa` (уже в officeplus), который соблюдает триггеры `TMS_*` (запрет удаления → архив). Перед каждым вызовом store устанавливает переменные пакета `g_*` из **активного профиля маппинга** (anonymous PL/SQL block: `BEGIN YBIRO_Import_Marfa.g_codprice := :v; ...; YBIRO_Import_Marfa.import_prices(...); END;`, всё в одной сессии/вызове, т.к. package state живёт в пределах сессии).

Прямой записью пишем только:
- правки прайс-грида (`PRETV*` через INSTEAD-OF триггер представления `VTPR1D_PERPRLIST`);
- переименование/слияние групп (`VPR01M_GROUPS`).

### Единственный новый DDL (нет в officeplus) — профили маппинга
Нормализованно, префикс `YBIRO_`:
```sql
CREATE TABLE YBIRO_MAP_PROFILE (
  id          NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  name        VARCHAR2(60) NOT NULL,        -- RO: nume profil / EN: profile name
  codprice    NUMBER,                        -- RO: lista de preturi / EN: price list code
  is_default  VARCHAR2(1) DEFAULT '0',       -- '1' = profil implicit / default profile
  created_at  TIMESTAMP DEFAULT SYSTIMESTAMP,
  created_by  VARCHAR2(60) DEFAULT USER,
  CONSTRAINT  uq_ybiro_map_profile_name UNIQUE (name)
);
CREATE TABLE YBIRO_MAP_PARAM (
  profile_id  NUMBER NOT NULL REFERENCES YBIRO_MAP_PROFILE(id),
  param_name  VARCHAR2(30) NOT NULL,         -- имя переменной пакета g_* (без префикса g_)
  param_value VARCHAR2(200),
  CONSTRAINT  pk_ybiro_map_param PRIMARY KEY (profile_id, param_name)
);
```
Запускается отдельно против officeplus (`sqlplus officeplus/officeplus26@orange.una.md:4024/cloudbd.world @sql/biro26/01_biro26_app_tables.sql`). Не входит в `deploy_oracle_objects.py` (та БД — wallet-БД Artgranit). Сид: один профиль `default` со значениями из шапки пакета (§4 ТЗ).

Перечень управляемых параметров (имена `g_*` из пакета): `tbl_goods, col_key, col_id, col_brand, col_articol, col_denumire, col_angro, col_ionline, col_retail, seq_key, codprice, um, gr1, tip, caccess, codtva, date_start, date_end, group_type, empty_brand, len_codvechi, len_denumire, isarhiv_arc, isarhiv_lock, confus_max_cyr`.

---

## 5. Функционал по вкладкам (фазы 1–5)

### Вкладка «Настройки / Маппинг» (этап 1)
- Параметры подключения (host/service/user, NLS) + кнопка «Проверить подключение».
- Список именованных профилей маппинга; форма «целевое поле ← источник/константа» с типом и правилом (обрезка/парсинг) по таблицам ТЗ §4.1–4.2.
- Чтение/запись `g_*` как профиля; выбор активного профиля.
- Валидация: длины (`len_codvechi=20`, `len_denumire=160`), NOT NULL (`caccess`), конвертируемость числовых.

### Вкладка «Источник» (BIRO26_GOODS, этап 2)
- Грид с фильтром/поиском: `ID, ARTICOL, DENUMIRE, BRAND, FURNIZOR, ANGRO, IONLINE, RETAIL1, STOC, COD_UNIVERS`.
- `validate_input` → отчёт (пустые имена, длинные ARTICOL/DENUMIRE, пустой бренд, нет ключа, непарсируемые цены) через захват DBMS_OUTPUT.
- `prepare_input` (нормализация: пустой бренд → маркер, TRIM).
- `assign_keys` (заполнение COD_UNIVERS из секвенции).
- Статус строки: новая / уже в справочнике / конфликт артикула (вычисляется запросом сопоставления с `TMS_UNIVERS`).

### Вкладка «Справочник» (TMS_UNIVERS + TMS_MPT, этап 3)
- Грид товаров `TIP='P'` с фильтрами `GR1`, бренд, архив (`ISARHIV`).
- Карточка товара: поля `TMS_UNIVERS` + связанная `TMS_MPT` (цены, счета, ШК, единицы), двуязычные `DENUMIREA`/`NAMERUS`.
- `import_univers` (идемпотентно по `COD = COD_UNIVERS`).
- Вместо удаления — `archive_univers` (значение `ISARHIV`; '2' блокируется триггером — UI это учитывает).
- `fix_denumirea_confusables` (кириллические обманки → латиница, только на строках с ≤ N кириллических символов).

### Вкладка «Группы / Поставщики» (этап 4)
- `VPR01M_GROUPS`: просмотр/редактирование (`CODPRICE, CODGRP, GRPNAME`); `import_groups` (нумерация продолжается с максимума); слияние групп (перенос цен + удаление пустой).
- `TMS_ORG`: справочник поставщиков (реквизиты, банки, счета `TMS_ORG_ACCOUNTS`); сопоставление `BIRO26_GOODS.FURNIZOR` ↔ код организации; отчёты «товары по поставщику», «поставщики по группе».
- Дерево категорий `TMS_SYSGRP/TMS_SYSGRPH` — только чтение.

### Вкладка «Прайс-лист» (этап 5)
- Цепочка: группы → `import_dates` (период, открытый конец 01.01.3000) → `import_prices` (дедуп по `SC`, при дубле артикула — макс. розница; запись через INSTEAD-OF; `PRETV/PRETV1/PRETV2 ← RETAIL1/ANGRO/IONLINE`).
- Грид цен с фильтром `CODPRICE/CODGRP/период`, редактирование `PRETV*`.
- `rollback_pricelist(p_codprice)` (цены → даты → группы, полностью обратимо).
- Учитывать PK `(CODPRICE, CODGRP, SC, DATASTART)` и отсутствие уникальности `CODVECHI`.

### Трёхъязычность (RU/RO/EN)
- Inline-словари ресурсов в шаблоне с переключением на лету (самодостаточный подход, как в шаблонах AEI).
- Данные: `DENUMIREA` (RO) — основное, `NAMERUS` (RU); отображение по выбранному языку с фолбэком RO→RU→EN.
- Код БД (если потребуются правки) — только RO + EN (правило проекта).

---

## 6. API (контракт)

Все ответы: `{success: bool, data?, error?}`. Деструктивные операции требуют подтверждения в UI.

| Метод/маршрут | Действие |
|---|---|
| `GET  /api/biro26/connection/test` | проверка подключения к officeplus |
| `GET/POST /api/biro26/mapping/profiles` | список / создание профиля |
| `GET/PUT /api/biro26/mapping/profiles/<id>` | чтение / изменение значений `g_*` |
| `POST /api/biro26/mapping/profiles/<id>/activate` | сделать активным |
| `GET  /api/biro26/goods` | грид BIRO26_GOODS (фильтры, пагинация) + статус строки |
| `POST /api/biro26/goods/validate` | `validate_input` (отчёт) |
| `POST /api/biro26/goods/prepare` | `prepare_input` |
| `POST /api/biro26/goods/assign-keys` | `assign_keys` |
| `GET  /api/biro26/univers` | грид TMS_UNIVERS (TIP='P', фильтры) |
| `GET  /api/biro26/univers/<cod>` | карточка (TMS_UNIVERS + TMS_MPT) |
| `POST /api/biro26/univers/import` | `import_univers` |
| `POST /api/biro26/univers/<cod>/archive` | `archive_univers` |
| `POST /api/biro26/univers/fix-confusables` | `fix_denumirea_confusables` |
| `GET/PUT /api/biro26/groups` | VPR01M_GROUPS просмотр/редакт |
| `POST /api/biro26/groups/import` | `import_groups` |
| `POST /api/biro26/groups/merge` | слияние групп |
| `GET  /api/biro26/categories` | дерево TMS_SYSGRP* (read-only) |
| `GET  /api/biro26/suppliers` | TMS_ORG + счета |
| `GET/POST /api/biro26/suppliers/mapping` | FURNIZOR ↔ TMS_ORG |
| `GET  /api/biro26/suppliers/reports` | отчёты по поставщикам |
| `GET  /api/biro26/prices` | грид VTPR1D_PERPRLIST (фильтры) |
| `PUT  /api/biro26/prices` | правка PRETV* |
| `POST /api/biro26/prices/import-dates` | `import_dates` |
| `POST /api/biro26/prices/import` | `import_prices` |
| `POST /api/biro26/prices/rollback` | `rollback_pricelist` |

---

## 7. Нефункциональные требования

- **Идемпотентность:** повторный запуск шага не плодит дублей (логика в пакете, `NOT EXISTS`).
- **Целостность:** не обходим триггеры; удаление товара — только архив.
- **Безопасность:** только bind-переменные; пароль officeplus — в `.env`, не в коде; деструктивные действия (import/rollback/archive/merge) — с подтверждением в UI, т.к. пишем в живую ERP-БД.
- **Производительность:** массовые операции — set-based внутри пакета (импорт ~78k цен ≈ 8 c). Гриды — пагинация на стороне БД.
- **Конфигурируемость:** маппинг/константы — через профили (`g_*`), без перекомпиляции.

---

## 8. Риски и допущения

- **Пишем в чужую ERP-БД (officeplus).** Снижение риска: все мутации через пакет YBIRO (соблюдает триггеры); деструктив с подтверждением; `rollback_pricelist` обратим.
- **Сетевая доступность** `orange.una.md:4024` из среды запуска — проверяется кнопкой «Проверить подключение» на первом шаге.
- **Состояние объектов officeplus** принято «всё есть» со слов заказчика; первый шаг плана — smoke-проверка наличия (`USER_OBJECTS`/`ALL_OBJECTS`) и существования процедур пакета, чтобы провалиться рано и понятно.
- **package state в пределах сессии:** установка `g_*` и вызов процедуры выполняются в одном PL/SQL-блоке/одной сессии коннекта.
- **Логирование (фаза 6)** временно через `DBMS_OUTPUT`; полноценный лог-просмотрщик — отдельная итерация.

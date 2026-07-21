# Спецификация веб-интерфейса для `BIRO26PT_importData`

> Документ для ИИ, создающего веб-приложение поверх PL/SQL-пакета
> `BIRO26PT_importData` (Oracle `OFFICEPLUS`). Цель интерфейса — принять от
> пользователя **группу файлов** или **zip-архив папки** с файлами прайса/остатков/
> штрихкодов неизвестной структуры, показать, **как система их поняла**, и по
> подтверждению выполнить импорт в боевую БД.

---

## 1. Что уже готово в БД (не переизобретать)

| Объект | Роль |
|---|---|
| `biro26pt_loader.py` | Python-загрузчик: xlsx/csv → «сырой» staging (`BIRO26PT_RAW/HEADER/FILE`) |
| `BIRO26PT_importData` (PL/SQL) | Детекция колонок (3 стратегии) + импорт (позиции/цены/ШК) |
| `BIRO26PT_MAP` | Результат детекции: `logical_field → cNN` на каждый `load_id` |
| `BIRO26PT_STG` | Проекция файла в «goods»-форму + `status` (NEW/EXISTING/AMBIGUOUS/NOARTICOL) |
| `BIRO26PT_LOG` | Журнал детекции/импорта |

Полное описание алгоритма — в `BIRO26PT_IMPORTDATA.md` и в функции
`BIRO26PT_importData.algo_md` (возвращает Markdown RO+EN).

**Веб-интерфейс НЕ содержит бизнес-логики импорта** — он только: принимает файлы,
запускает загрузчик, вызывает процедуры пакета, читает таблицы результата и
рисует их. Вся логика остаётся в БД (по требованию проекта).

---

## 2. Поток работы (2 фазы: анализ → подтверждение)

```
[1] Пользователь загружает: N файлов (xlsx/csv) ИЛИ 1 zip-архив
        │
[2] Backend: если zip → распаковать во временную папку (только *.xlsx,*.xls,*.csv)
        │
[3] Backend: запустить biro26pt_loader.py <папка>  → строки в BIRO26PT_RAW/HEADER/FILE
        │     (loader печатает: load_id / file / rows / cols — распарсить stdout)
        │
[4] Backend: для каждого нового load_id вызвать DRY-RUN:
        BEGIN BIRO26PT_importData.import_file(:load_id, :grupa, :codprice, p_commit => FALSE); END;
        │
[5] Backend: прочитать из БД детекцию + классификацию (SQL ниже) → вернуть на фронт
        │
[6] Фронт показывает по каждому файлу: маппинг колонок + счётчики (NEW/EXISTING/…)
        │     Пользователь при желании правит группу/цену-код, подтверждает.
        │
[7] По кнопке «Импортировать»: тот же вызов с p_commit => TRUE
        │
[8] Backend читает итоговые счётчики из BIRO26PT_LOG / прод-таблиц → отчёт
```

**Важно:** фаза DRY-RUN ничего не пишет в продакшен — безопасно вызывать всегда.
Реальная запись — только `p_commit => TRUE` (кнопка с подтверждением).

---

## 3. Приём файлов

- Принимать: `multipart/form-data` с несколькими файлами **или** одним `.zip`.
- Расширения-белый-список: `.xlsx .xls .csv .zip`. Внутри zip — те же (рекурсивно,
  но игнорировать вложенные zip, `__MACOSX`, файлы с `~$`).
- Zip распаковывать в изолированную временную папку (защита от path traversal:
  отбрасывать записи с `..` и абсолютными путями).
- Лимит размера — конфиг (напр. 50 МБ). Каждая загрузка = отдельная папка
  `uploads/<session_uuid>/`.

---

## 4. Запуск загрузчика (backend → shell)

```bash
# Окружение (macOS-хост проекта). Instant Client 23 обязателен.
export DYLD_LIBRARY_PATH=/Users/pt/Downloads/instantclient_23_26
python3 biro26pt_loader.py "/abs/path/uploads/<session_uuid>"
```

- Загрузчик подключается к БД сам (`officeplus/officeplus26@//orange.una.md:4024/cloudbd.world`)
  и присваивает `load_id` инкрементально (max+1). **Верните stdout** — там строки
  `load_id=<n> file='<name>' sheet='<s>' rows=<r> cols=<c>`, из них backend узнаёт
  список `load_id` для этой сессии.
- ⚠️ **Charset БД — `CL8MSWIN1251`.** Загрузчик через `python-oracledb` конвертирует
  Unicode→win1251 корректно. Не вставляйте кириллицу в служебные таблицы через
  SQLcl/сырой SQL — байты испортятся.
- Альтернатива: backend может реализовать загрузку сам (тот же INSERT в
  `BIRO26PT_RAW/HEADER/FILE`), но проще вызвать готовый скрипт.

---

## 5. Вызов PL/SQL из backend

Подключение (any Oracle driver — node `oracledb`, python `oracledb`, JDBC):

```
user=officeplus  password=officeplus26
dsn=orange.una.md:4024/cloudbd.world
```

⚠️ Локаль хоста `en_MD` вызывает `ORA-12705` при логине через thick-клиент.
Для JVM/SQLcl задавать `-Duser.language=en -Duser.country=US`. Для python/node
`oracledb` в thin-режиме проблемы нет.

**Dry-run (анализ):**
```sql
BEGIN BIRO26PT_importData.import_file(
        p_load_id  => :load_id,
        p_grupa    => :grupa,      -- напр. 'Hartie colorata'; NULL → 'IMPORT PT'
        p_codprice => :codprice,   -- напр. 1
        p_commit   => FALSE); END;
```
**Импорт (запись):** тот же вызов с `p_commit => TRUE`.
**Все файлы разом:** `BIRO26PT_importData.import_folder(:grupa, :codprice, :commit)`.

Процедуры печатают отчёт в `DBMS_OUTPUT`, но backend'у **удобнее читать таблицы
результата напрямую** (ниже) — это чистые данные для UI, без парсинга текста.

---

## 6. SQL, которые backend выполняет для UI

### 6.1 Маппинг колонок (что система поняла)
```sql
SELECT m.col_idx,
       'c'||m.col_idx        AS phys_col,
       m.logical_field,
       m.strategy,                       -- HEADER / CONTENT / LAYOUT
       h.header_text
FROM   biro26pt_map m
LEFT   JOIN biro26pt_header h
       ON h.load_id = m.load_id AND h.col_idx = m.col_idx
WHERE  m.load_id = :load_id
ORDER  BY m.col_idx;
```

### 6.2 Счётчики классификации (карточки статуса)
```sql
SELECT status, COUNT(*) cnt
FROM   biro26pt_stg
WHERE  load_id = :load_id
GROUP  BY status;          -- NEW / EXISTING / AMBIGUOUS / NOARTICOL
```

### 6.3 Сколько существующих товаров получат новую цену
```sql
SELECT COUNT(*) price_changed
FROM   biro26pt_stg s
WHERE  s.load_id = :load_id AND s.status='EXISTING' AND s.retail1 IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM vtpr1d_perprlist p
     WHERE p.sc = s.cod_univers AND p.codprice = :codprice
       AND NVL(p.pretv,-1) <> NVL(YBIRO_Import_Marfa.parse_price(s.retail1),-2)
       AND p.datastart = (SELECT MAX(p2.datastart) FROM vtpr1d_perprlist p2
                           WHERE p2.sc=p.sc AND p2.codprice=:codprice));
```

### 6.4 Превью строк (таблица на фронте, пагинация)
```sql
SELECT row_no, status, articol, denumire, grupa,
       angro, ionline, retail1, barcode
FROM   biro26pt_stg
WHERE  load_id = :load_id
ORDER  BY row_no
OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY;
```
> Замечание: `ONLINE`, `RETAIL` — зарезервированные слова Oracle; в БД поля
> называются `IONLINE`, `RETAIL1`. В алиасах не использовать голое `online`.

### 6.5 Журнал импорта (после commit)
```sql
SELECT phase, logical_field, strategy, note, ts
FROM   biro26pt_log
WHERE  load_id = :load_id
ORDER  BY log_id;
```

### 6.6 Описание алгоритма для страницы «Справка»
```sql
SELECT BIRO26PT_importData.algo_md FROM dual;   -- Markdown RO+EN
```

### 6.7 Фильтр «produse noi» (новые товары)
«PRODUSE NOI» — **виртуальный** признак, а не узел дерева: это флаг `MATGR1=1`.
Товары, помеченные при импорте, доступны фронту одним запросом:
```sql
SELECT * FROM vms_mpt WHERE matgr1 = 1;   -- v.cod = TMS_UNIVERS.COD
```
Маркер ставит `import_file`/`import_folder`: `p_mark_all_new=TRUE` (по умолчанию) —
все товары файла; `FALSE` — только новые позиции. Новым позициям также
**генерируется EAN-13** (префикс `20`), и они помещаются в **свои реальные узлы дерева
по `GRUPA`** (`ensure_group` находит узел по имени; физический узел «PRODUSE NOI» не
создаётся). Цены обновляются по правилу **«не понижать»** (новый период только если цена
в файле выше); дата вступления — `p_date` (по умолчанию дата загрузки).

---

## 7. Рекомендуемые REST-эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/uploads` | Приём файлов/zip → распаковка → loader → возвращает `session_id` + список `{load_id, file, rows, cols}` |
| `POST` | `/api/analyze` | Тело `{load_ids[], grupa, codprice}` → dry-run по каждому → возвращает маппинг + счётчики (§6.1–6.4) |
| `GET`  | `/api/preview/:load_id?offset&limit` | Превью строк (§6.4) |
| `POST` | `/api/commit` | Тело `{load_ids[], grupa, codprice}` → `p_commit=TRUE` → итоговый отчёт (§6.5 + дельты прод-таблиц) |
| `GET`  | `/api/help` | `algo_md` (§6.6) |

Каждый ответ — JSON. Ошибки Oracle пробрасывать как `{error, ora_code, message}`.

---

## 8. UX-подсказки для фронта

1. **Экран загрузки:** drag-and-drop нескольких файлов или zip; после загрузки —
   список файлов с `rows/cols`.
2. **Экран анализа (по каждому файлу):**
   - «Как поняты колонки»: таблица `header_text → logical_field` с бейджем стратегии
     (`HEADER`=зелёный/уверенно, `CONTENT`=жёлтый, `LAYOUT`=синий). Дать
     пользователю **переопределить** маппинг вручную (см. §9) — опционально.
   - 4 карточки-счётчика: Новых / Существующих (из них N с новой ценой) /
     Неоднозначных / Без артикула.
   - Кнопка «Показать строки» → превью-таблица со статусом построчно
     (подсветить AMBIGUOUS/NOARTICOL — они будут пропущены).
   - Поля ввода: **Группа** (`grupa`) и **Код прайса** (`codprice`, по умолч. 1).
3. **Подтверждение импорта:** явная кнопка с итогом «Будет создано X товаров,
   обновлено Y цен, пропущено Z». Только после явного клика — `/api/commit`.
4. **Экран результата:** реальные дельты (создано в `TMS_UNIVERS`/`TMS_MPT`,
   вставлено цен в `VTPR1D_PERPRLIST`), ссылка на журнал.

---

## 9. (Опционально) Ручное переопределение маппинга

Если пользователь хочет поправить, какая колонка чем является, backend может до
`build_stg` перезаписать `BIRO26PT_MAP` для этого `load_id`:
```sql
DELETE FROM biro26pt_map WHERE load_id=:load_id AND logical_field=:field;
INSERT INTO biro26pt_map(load_id,logical_field,col_idx,strategy,confidence)
VALUES(:load_id,:field,:col_idx,'MANUAL',1);
```
затем повторить dry-run. Т.е. интерфейс может стать «полуавтоматическим»: система
предлагает — человек корректирует — импорт.

Также можно **пополнять словарь** `BIRO26PT_COLMAP` (новые синонимы заголовков) —
тогда следующие файлы того же поставщика распознаются автоматически. Кириллицу
добавлять через `python-oracledb` (charset win1251).

---

## 10. Безопасность и эксплуатация

- **Двухфазность** (dry-run → commit) — обязательна в UI; не давать «импорт в один клик».
- Пакет идемпотентен: повторный commit того же файла не создаёт дублей
  (`NOT EXISTS` по коду/периоду/ШК).
- Удалений нет: цены — новыми периодами (история), товары — только добавляются.
- Откат цен по прайсу: `BEGIN YBIRO_Import_Marfa.rollback_pricelist(:codprice); END;`.
- Учётные данные БД — только на backend (никогда на фронте). Загруженные файлы и
  временные папки чистить после обработки.
- Доступ к интерфейсу — за аутентификацией (запись в боевой ERP).

---

## 11. Стек (рекомендация, не обязательно)

- Backend: **Node.js + `oracledb` (thin)** или **Python FastAPI + `oracledb`**.
  Thin-режим избавляет от `ORA-12705`/Instant Client. Для запуска `biro26pt_loader.py`
  всё же нужен Instant Client на хосте загрузчика (или переписать загрузку на thin).
- Zip: `adm-zip` (node) / `zipfile` (python).
- Frontend: любой SPA (React/Vue) — таблицы, карточки-счётчики, две кнопки.

---

## 12. Проверенный факт (batch-3)

На `Set_data_import/3/Price nou.xlsx` (407 строк, русские заголовки, 4 цены, без ШК):
детекция целиком по именам колонок; импорт с `p_commit=TRUE` создал **94 товара**
(+ 94 карточки) и **373 цены** (перевод существующих на новый период = обновление,
новым — первая цена). Пример: `ZM80-B` — новый период с retail 75.5 вместо 80.

Связанные документы: `BIRO26PT_IMPORTDATA.md`, `IMPORT_TMS_UNIVERS.md`,
`USING_GROUPED_RESULTS_FOR_PROD_DB.md`.

---

## 13. Инструкция пользователя + доступ из GUI

**Инструкция для оператора** (пошагово, как загружать данные) — `INSTRUCTIUNE_INCARCARE_DATE.md`
и HTML-версия `import_reguli.html`. Обе развёрнуты в `static/biro26/`, то есть доступны по HTTP:
- `https://nufarul.eminescu.md/static/biro26/import_reguli.html`
- `https://officeplus.md/static/biro26/import_reguli.html`

**Что добавить в GUI (страница Import / asistent):**
- Ссылка **«📖 Instrucțiune»** → `/static/biro26/import_reguli.html` (открыть инструкцию).
- На шаге **Analizează** показывать распознавание новых колонок: `GRUPA`, `CATEGORIE`, `PRODUCER`
  (furnizor) — с бейджем стратегии (HEADER/CONTENT).
- В отчёте импорта показывать: сколько записано в `BIRO26_GOODS` (дерево/магазин), сколько
  привязано к furnizor, сколько изображений.
- Кнопка **«Corectează prețuri din feed»** (опционально) — точечное выравнивание списка цен
  `TPR1D_PERPRLIST` из `BIRO26_GOODS` для выбранного furnizor (см. §9.15 в `GHID_IMPORT_ALTE_SCHEME.md`).

**Новые логические поля** (детекция): `GRUPA` (грр. товара), `CATEG` (подкатегория),
`FURNIZOR` (поставщик/производитель) — в дополнение к `ARTICOL/DENUMIRE/ANGRO/ONLINE/RETAIL/BARCODE/VAT/URL`.
Пакет `do_writes` пишет и в `BIRO26_GOODS` (источник дерева/магазина), и в список цен, и ставит
`DEP_PRODUCER`, и создаёт узлы дерева по `GRUPA > CATEGORIE`.

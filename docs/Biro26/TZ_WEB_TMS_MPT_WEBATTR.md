# ТЗ для веб-команды: адаптация под `TMS_MPT_WEBATTR`

> ✅ **СТАТУС: РЕАЛИЗОВАНО 2026-07-26** на обеих системах (officeplus.md + shop1.officeplus.md).
> Задача 1 (показ): `get_products_stock()` — `LEFT JOIN tms_mpt_webattr` (в сетке `DENUM_FULL`,
> VARCHAR2-копия); `product_info(cod, lang)` читает BLOB с откатом lang→RO→YBIRO_PROD_INFO;
> worker: `oracledb.defaults.fetch_lobs = False` (BLOB→bytes→UTF-8 — диакритика доходит).
> Задача 2 (поиск): запрос нормализуется `cp1251_safe()`, ищет и по `DENUMIRE_FULL_RO/RU`
> + `DBMS_LOB.INSTR` по `DESCRIERE_NON_DIACR_RO`. Проверено: «carti» = «cărți» = 1114 позиций.
> Задача 3 (редактирование): backoffice-карточка — блок «Atribute web» с вкладками RO/RU/EN
> (Denumire completă + Descriere), API `GET/PUT /api/biro26/webattr/<cod>`; запись ТОЛЬКО в BLOB
> (`{"__b64__"}` → bytes → `DB_TYPE_BLOB`, мимо charset-конверсии), `lang` — белый список.
> Проверено: `Ștampilă pătrată` → BLOB точный, `DENUMIRE_FULL_*` = `Stampila patrata` (триггер).
> Задача 4 (импорт): loader задеплоен на оба контура; `LOGICAL_FIELDS` +=
> `DENUM_FULL, DESCRIERE, GRUPA, CATEG, FURNIZOR` (видны и переназначаются в «Analizează»);
> в отчёте импорта — строка «atribute web scrise (TMS_MPT_WEBATTR): N».
> Задача 5 (индексация) — не делалась (опциональная).
> Магазин/PDP передают `?lang=` и показывают `denum_full` + описание с диакритикой.

> **Кому:** команда/ИИ, сопровождающая `Artgranit` (back-office `biro26-backoffice`, магазин `shop`,
> мастер импорта `import_pt`).
> **От кого:** сторона импорта данных (пакет `BIRO26PT_importData`).
> **Статус БД:** все объекты созданы и заполнены в продакшене; данные set 8 загружены (30 004 товара).
> **Что требуется от вас:** адаптировать интерфейсы и алгоритмы под новую таблицу.

---

## 1. Что изменилось и почему (обязательно к прочтению)

База `OFFICEPLUS` — **`CL8MSWIN1251`, однобайтовая**. Любая румынская диакритика или типографский
знак, записанный в **текстовую** колонку, молча превращается в `?`:
`Cărți educaționale` → `C?r?i educa?ionale`.

Раньше мы это лечили транслитерацией (`ș`→`s`) — данные спасены, но **диакритика теряется**.
Для описаний товара это неприемлемо (витрина магазина).

**Решение:** оригинал хранится в **BLOB** — Oracle никогда не перекодирует байты BLOB, поэтому
UTF-8 текст выживает при любой кодировке БД. Параллельно **триггер** автоматически создаёт
текстовые копии **без диакритики** — для поиска и индексации.

```
запись:  текст UTF-8 ──► BLOB (байты нетронуты)
                          │  триггер TMS_MPT_WEBATTR_BIU
                          ▼
чтение:  BLOB ──► показ с диакритикой        (витрина, карточка)
         CLOB/VARCHAR2 ──► поиск/индекс      («carti» находит «cărți»)
```

---

## 2. Структура таблицы

`TMS_MPT_WEBATTR` — сателлит 1:1 к `TMS_UNIVERS` (`COD` = **PK и FK**, как у `TMS_MPT`).

| Колонка | Тип | Кто пишет | Назначение |
|---|---|---|---|
| `COD` | NUMBER PK+FK | импорт/приложение | = `TMS_UNIVERS.COD` |
| `DESCRIERE_RO` / `_RU` / `_EN` | **BLOB** | **вы (редактирование)** | описание/характеристики, **оригинал UTF-8** |
| `DENUMIRE_FULL_BLOB_RO` / `_RU` / `_EN` | **BLOB** | **вы (редактирование)** | полное название, **оригинал UTF-8** |
| `DESCRIERE_NON_DIACR_RO` / `_RU` / `_EN` | CLOB | **триггер** | копия без диакритики (поиск, вектор-индекс) |
| `DENUMIRE_FULL_RO` / `_RU` / `_EN` | VARCHAR2(4000) | **триггер** | копия без диакритики (поиск, индекс) |
| `SRC`, `LOAD_ID`, `UPDATED_AT` | | импорт/триггер | источник и прослеживаемость |

> ⛔ **Главное правило:** приложение пишет **только BLOB-колонки**. Поля `*_NON_DIACR_*` и
> `DENUMIRE_FULL_RO/RU/EN` **не трогать** — их перезаписывает триггер при каждом изменении BLOB.
> Запись в них вручную будет потеряна.

Текущее наполнение: **30 004** строки, из них **19 702** с описанием (RO — из файлов поставщиков;
RU/EN пока пустые, заполняются вами через редактирование/перевод).

---

## 3. Задача 1 — Чтение и показ (магазин + карточка товара)

### 3.1 Правило
Показывать пользователю **BLOB** (там диакритика). Текстовые копии — **только** для поиска.

### 3.2 SQL
```sql
SELECT u.cod, u.denumirea,
       w.descriere_ro, w.descriere_ru, w.descriere_en,                     -- BLOB
       w.denumire_full_blob_ro, w.denumire_full_blob_ru, w.denumire_full_blob_en
FROM   tms_univers u
LEFT   JOIN tms_mpt_webattr w ON w.cod = u.cod
WHERE  u.cod = :cod;
```

### 3.3 Python (декодирование BLOB)
```python
def blob_text(v):
    """BLOB -> str. python-oracledb отдаёт LOB-объект или bytes."""
    if v is None:
        return None
    data = v.read() if hasattr(v, "read") else v
    return data.decode("utf-8", "replace")

descr = blob_text(row["DESCRIERE_RO"])   # 'Caiet cu spiră A4+ 80 foi pătrățele'
```

### 3.4 Выбор языка
Порядок отката: запрошенный язык → RO (базовый) → пусто.
```python
def pick(row, lang, base):          # base='DESCRIERE' | 'DENUMIRE_FULL_BLOB'
    for L in (lang.upper(), "RO"):
        v = blob_text(row.get(f"{base}_{L}"))
        if v:
            return v
    return None
```

### 3.5 Где применить
- **Магазин** (`shop.html`, `/api/biro26/shop/products`, карточка товара) — выводить описание под названием.
- **Back-office → Marfă / Stoc** — колонка/тултип с описанием; в карточке товара — блок «Descriere».
- Учтите: `get_products_stock()` (`models/biro26_oracle_store.py:682`) сейчас не читает `webattr` —
  добавьте `LEFT JOIN tms_mpt_webattr w ON w.cod = u.cod`. Для сетки достаточно текстовой копии
  `w.denumire_full_ro` (быстро, без LOB); BLOB тянуть **только** в карточке товара.

---

## 4. Задача 2 — Поиск

Искать по текстовым копиям **без диакритики** и так же нормализовать поисковый запрос —
тогда «carti», «cărți» и «CARTI» дают один результат.

```sql
SELECT cod FROM tms_mpt_webattr
WHERE UPPER(denumire_full_ro) LIKE UPPER('%' || :q_norm || '%')
   OR DBMS_LOB.INSTR(UPPER(descriere_non_diacr_ro), UPPER(:q_norm)) > 0;
```

Нормализация запроса на стороне приложения — **уже есть готовая функция**: `cp1251_safe()` в
`models/biro26pt_loader.py`. Импортируйте её, не пишите свою:
```python
from models.biro26pt_loader import cp1251_safe
q_norm = cp1251_safe(user_query)     # 'cărți' -> 'carti'
```

---

## 5. Задача 3 — Редактирование (back-office)

### 5.1 UI
В карточке товара — блок «Атрибуты веб» с **вкладками языков RO / RU / EN**, в каждой два поля:
- **Descriere** (многострочное, до ~2000 симв.),
- **Denumire completă** (одна строка, до ~4000 симв.).

Показывать пометку: *«Diacriticele se păstrează integral»* — оператор может свободно писать `ăâîșț`.

### 5.2 Запись — только BLOB
```python
def save_webattr(cod, lang, descr, full):
    L = lang.upper()                       # 'RO' | 'RU' | 'EN'
    if L not in ("RO", "RU", "EN"):
        raise ValueError("lang")
    db.execute_dml(
        f"""MERGE INTO tms_mpt_webattr t
            USING (SELECT :cod AS cod FROM dual) s ON (t.cod = s.cod)
            WHEN MATCHED THEN UPDATE SET
                 t.descriere_{L}            = :d,
                 t.denumire_full_blob_{L}   = :f
            WHEN NOT MATCHED THEN
                 INSERT (cod, descriere_{L}, denumire_full_blob_{L}, src)
                 VALUES (:cod, :d, :f, 'BACKOFFICE')""",
        {"cod": cod,
         "d": descr.encode("utf-8") if descr else None,
         "f": full.encode("utf-8")  if full  else None})
```
Имя языковой колонки подставляется в SQL — **валидируйте `lang` по белому списку** (как выше),
никаких значений от клиента напрямую.

### 5.3 Ожидаемое поведение
После сохранения `DESCRIERE_NON_DIACR_*` и `DENUMIRE_FULL_*` заполнятся сами. Проверить:
```sql
SELECT denumire_full_ro FROM tms_mpt_webattr WHERE cod = :cod;  -- уже без диакритики
```

---

## 6. Задача 4 — Мастер импорта (`import_pt`)

### 6.1 Что уже сделано на стороне БД/загрузчика (менять не нужно)
- Пакет распознаёт два новых логических поля: **`DESCRIERE`** и **`DENUM_FULL`**
  (синонимы заголовков RO/RU/EN уже в `BIRO26PT_COLMAP`).
- `models/biro26pt_loader.py` **уже обновлён** (в `main` ветке): сохраняет оригинальные UTF-8
  байты в staging `BIRO26PT_RAW_BLOB` — но **только** для ячеек, где транслитерация что-то
  изменила (экономно: 45 509 ячеек на set 8).
- `do_writes` берёт оригинал из `BIRO26PT_RAW_BLOB` и пишет в `TMS_MPT_WEBATTR` (BLOB).

### 6.2 Что нужно сделать вам
1. **Подтянуть `main`** и задеплоить `models/biro26pt_loader.py` (иначе GUI-импорт продолжит
   грузить без оригиналов, и описания приедут без диакритики).
2. **Показать новые поля в шаге «Analizează»** — добавить `DESCRIERE` и `DENUM_FULL` в список
   логических полей: `models/biro26pt_store.py:36`, константа `LOGICAL_FIELDS`
   (сейчас: `ARTICOL, DENUMIRE, ANGRO, ONLINE, RETAIL, VAT, BARCODE, URL, IGNORE` — добавьте
   `GRUPA, CATEG, FURNIZOR, DESCRIERE, DENUM_FULL`; они уже детектируются пакетом, но в UI
   не отображаются и их нельзя переназначить вручную).
3. **В отчёте импорта** показывать строку «atribute web scrise (TMS_MPT_WEBATTR): N» —
   она уже приходит в `DBMS_OUTPUT`/журнале, просто выведите её в сводке.

### 6.3 Проверка после деплоя
```sql
-- при следующем импорте через GUI: оригиналы должны попадать в staging
SELECT COUNT(*) FROM biro26pt_raw_blob WHERE load_id = :N;   -- > 0, если в файле есть диакритика
```

---

## 7. Задача 5 (опционально) — Индексация и поиск «по смыслу»

Поля `DESCRIERE_NON_DIACR_*` (CLOB) сделаны именно под индексацию — они чистый ASCII/кириллица
без диакритики. Возможные шаги (на ваше усмотрение):
- Oracle Text: `CREATE INDEX ... ON tms_mpt_webattr(descriere_non_diacr_ro) INDEXTYPE IS CTXSYS.CONTEXT;`
- Векторный поиск: эмбеддинги считать по `DESCRIERE_NON_DIACR_*`, хранить рядом.

Требование одно: **не менять** эти поля вручную — они производные.

---

## 8. Критерии приёмки

| # | Проверка | Ожидаемо |
|---|---|---|
| 1 | Карточка товара в магазине | Описание видно **с диакритикой**: `Caiet cu spiră A4+ 80 foi pătrățele` |
| 2 | Поиск «carti» | Находит товары с `cărți` |
| 3 | Поиск «cărți» | Находит те же товары (запрос нормализуется) |
| 4 | Редактирование: сохранить `Ștampilă pătrată` | В `DESCRIERE_RO` (BLOB) — точный текст; в `DENUMIRE_FULL_RO` — `Stampila patrata` |
| 5 | Повторное открытие карточки | Показывает **оригинал**, а не транслитерацию |
| 6 | Импорт файла с диакритикой через GUI | `BIRO26PT_RAW_BLOB` непусто; описания в БД с диакритикой |
| 7 | Шаг «Analizează» | Колонки `DESCRIERE` / `CATEGORIE` / `PRODUCER` видны в списке маппинга |
| 8 | Языки | RU/EN, если пустые, откатываются на RO (не пустой экран) |

---

## 9. Подводные камни (проверено на практике)

1. **Не пишите в текстовые копии** — перезапишет триггер.
2. **BLOB в сетке — дорого.** Для списков используйте `DENUMIRE_FULL_RO` (VARCHAR2), BLOB — только в карточке.
3. **`COUNT(clob_column)` не работает** (`ORA-00932`) — считайте через
   `SUM(CASE WHEN c IS NOT NULL THEN 1 ELSE 0 END)`.
4. **`LIKE` по CLOB** — используйте `DBMS_LOB.INSTR`, так надёжнее и быстрее.
5. **Пустая строка внутри `CREATE TABLE`** в SQLcl обрывает команду — если будете применять DDL
   скриптом, ставьте `SET SQLBLANKLINES ON`.
6. **Валидируйте `lang`** белым списком: имя колонки подставляется в SQL.
7. `DESCRIERE_RU/EN` сейчас пустые — UI должен корректно показывать пустое состояние
   и предлагать заполнить/перевести.

---

## 10. Готовые объекты в БД (уже развёрнуты)

| Объект | Назначение |
|---|---|
| `TMS_MPT_WEBATTR` | таблица (16 колонок) |
| `TMS_MPT_WEBATTR_BIU` | триггер: BLOB → текстовые копии |
| `YBIRO_TEXT_UTIL` | `blob_to_nclob`, `strip_diacritics`, `blob_to_plain`, `nclob_to_blob` |
| `BIRO26PT_RAW_BLOB` | staging оригиналов при импорте |
| `Y_AI_WEBATTR_V1_BAK` | бэкап предыдущей версии таблицы (30 004) |

Полезно: `YBIRO_TEXT_UTIL.blob_to_plain(:blob)` — если нужно получить «чистый» текст на лету,
не читая BLOB в приложение.

---

## 11. Связанные документы

- `GHID_IMPORT_ALTE_SCHEME.md` §3.4 — модель «мастер + сателлиты», архитектура BLOB
- `BIRO26PT_WEB_INTERFACE_SPEC.md` §15 — SQL для показа/поиска/записи
- `DIACRITICE_SI_SERVICII.md` §3b — когда BLOB, а когда транслитерация
- `TMS_MPT_WEBATTR.tab.sql`, `YBIRO_TEXT_UTIL.pkg.sql` — DDL (в `sql/biro26/`)

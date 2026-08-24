# SEOForge Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать в бэкофисе Artgranit модуль `seoforge` — Oracle-контур `YSEO_*` и web-интерфейс для сайтов, кампаний, плана/факта бюджета и ROI по каналам.

**Architecture:** Oracle-first. Данные и инварианты (лимит бюджета, приведение валют, журнал) живут в таблицах `YSEO_*`, вьюшках `VSEO_*` и пакетах `PK_SEO_*` облачной базы бэкофиса. Python — тонкий: чистый модуль разбора CSV, хранилище поверх `DatabaseModel`, контроллер-маршрутизатор, одностраничный SPA-шаблон с панелями.

**Tech Stack:** Oracle (облачная БД бэкофиса, wallet/thin через `models/database.py`), Python 3.12 + Flask, pytest, ванильный JS в шаблоне (как в `templates/digi_marketing.html`).

**Спека:** `docs/superpowers/specs/2026-08-24-seoforge-backoffice-design.md`

## Global Constraints

- Префикс всех Oracle-объектов модуля — `YSEO_` (таблицы, последовательности, триггеры), `VSEO_` (вьюшки), `PK_SEO_` (пакеты).
- Комментарии в SQL и тексты исключений — строго в формате `RO: <text> / EN: <text>`. Русского в коде БД нет.
- Идентификаторы — английские.
- Первичные ключи выдаются последовательностями `YSEO_*_SEQ` через триггеры `BEFORE INSERT`. `IDENTITY` и `DEFAULT seq.NEXTVAL` не используются.
- Удалений нет: справочные сущности архивируются `ISARHIV = 1`.
- `execute_query` из `models/database.py` **не коммитит** — коммит делает вызывающий через `db.connection.commit()`.
- UI-маршруты живут под `/UNA.md/orasldev/seoforge`, охрана `AuthController.is_authenticated()`.
- Тесты гоняются без живой базы: `./venv/bin/python -m pytest tests/ -q`.
- Ветка работы — `feature/seoforge-module`. Боевой сервер не трогаем; `deploy_to_remote.sh` не запускаем.

## Файловая структура

| Файл | Ответственность |
|---|---|
| `sql/113_yseo_tables.sql` | таблицы, последовательности, триггеры-нумераторы, триггер контроля перерасхода |
| `sql/114_yseo_views.sql` | `VSEO_SITE`, `VSEO_CAMPAIGN`, `VSEO_BUDGET_PLANFACT`, `VSEO_CHANNEL_ROI` |
| `sql/115_yseo_package.sql` | `PK_SEO_UTIL`, `PK_SEO_BUDGET` (спецификации и тела) |
| `sql/116_yseo_dict_seed.sql` | наполнение `YSEO_DICT`, `YSEO_SETUP` |
| `deploy_oracle_objects.py` | четыре файла в порядок выполнения |
| `models/seo_csv.py` | чистые функции: период, `EXT_ID`, разбор и валидация CSV. Без Oracle, без Flask |
| `models/seo_oracle_store.py` | CRUD и выборки поверх `DatabaseModel` |
| `controllers/seo_controller.py` | валидация ввода, маппинг ошибок в HTTP-коды, оркестрация импорта |
| `app.py` | регистрация страницы и JSON-API |
| `templates/seoforge.html` | SPA: семь панелей |
| `modules/seoforge/module.json` | манифест меню |
| `docs/SEOForge/*.md`, `docs/SEOForge/docs.json` | документация модуля |
| `tests/test_seoforge.py` | юнит-тесты: DDL-инварианты, CSV, хранилище, контроллер |
| `scripts/seoforge_smoke.py` | живой smoke по инвариантам контура после установки DDL |

Разделение `seo_csv.py` / `seo_oracle_store.py` / `seo_controller.py` намеренное: разбор CSV — чистая логика, её тестируем без моков; хранилище знает про SQL, но не про HTTP; контроллер знает про HTTP, но не про SQL.

---

### Task 1: Таблицы контура

**Files:**
- Create: `sql/113_yseo_tables.sql`
- Test: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: ничего
- Produces: таблицы `YSEO_DICT`, `YSEO_SITE`, `YSEO_PLATFORM`, `YSEO_CAMPAIGN`, `YSEO_BUDGET_PLAN`, `YSEO_SPEND_FACT`, `YSEO_METRICS_FACT`, `YSEO_IMPORT`, `YSEO_FX_RATE`, `YSEO_SETUP`, `YSEO_XREF`, `YSEO_EVENT_LOG`; последовательности `YSEO_<TABLE>_SEQ`; триггеры `TRG_YSEO_<TABLE>_ID`, `TRG_YSEO_SPEND_BUDGET`.

Живой базы в тестах нет, поэтому DDL проверяется разбором файла: это ловит ровно те ошибки, которые дороже всего стоят — забытый индекс по FK, потерянный префикс, русский комментарий, отсутствие `ISARHIV` у справочника.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_seoforge.py
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(ROOT, "sql")

def _sql(name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
        return fh.read()

EXPECTED_TABLES = [
    "YSEO_DICT", "YSEO_SITE", "YSEO_PLATFORM", "YSEO_CAMPAIGN",
    "YSEO_BUDGET_PLAN", "YSEO_SPEND_FACT", "YSEO_METRICS_FACT",
    "YSEO_IMPORT", "YSEO_FX_RATE", "YSEO_SETUP", "YSEO_XREF",
    "YSEO_EVENT_LOG",
]

def test_tables_ddl_declares_every_table():
    ddl = _sql("113_yseo_tables.sql").upper()
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table}" in ddl, table

def test_tables_ddl_has_no_russian_comments():
    ddl = _sql("113_yseo_tables.sql")
    for line in ddl.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or "COMMENT ON" in stripped.upper():
            assert not re.search(r"[а-яА-ЯёЁ]", stripped), stripped

def test_every_foreign_key_column_has_an_index():
    ddl = _sql("113_yseo_tables.sql").upper()
    fk_cols = set(re.findall(r"FOREIGN KEY \(([A-Z0-9_]+)\)", ddl))
    indexed = set()
    for cols in re.findall(r"CREATE INDEX [A-Z0-9_]+ ON [A-Z0-9_]+ \(([^)]+)\)", ddl):
        indexed.add(cols.split(",")[0].strip())
    for col in fk_cols:
        assert col in indexed, f"FK {col} without index"

def test_dictionaries_carry_isarhiv():
    ddl = _sql("113_yseo_tables.sql").upper()
    for table in ("YSEO_SITE", "YSEO_PLATFORM", "YSEO_CAMPAIGN", "YSEO_DICT"):
        block = ddl.split(f"CREATE TABLE {table} (")[1].split(");")[0]
        assert "ISARHIV" in block, table

def test_every_table_has_sequence_and_id_trigger():
    ddl = _sql("113_yseo_tables.sql").upper()
    # Таблицы с натуральным составным PK нумератор не получают.
    natural_pk = {"YSEO_DICT", "YSEO_FX_RATE", "YSEO_SETUP"}
    for table in EXPECTED_TABLES:
        if table in natural_pk:
            continue
        assert f"CREATE SEQUENCE {table}_SEQ" in ddl, table
        assert f"{table}_SEQ.NEXTVAL" in ddl, table
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — `FileNotFoundError: sql/113_yseo_tables.sql`

- [ ] **Step 3: Написать DDL**

Файл открывается шапкой:

```sql
-- =====================================================================
-- RO: Modulul SEOForge - conturul de promovare SEO in baza back-office.
-- EN: SEOForge module - SEO promotion contour in the back-office database.
--
-- RO: Sursa cerintelor - docs/superpowers/specs/2026-08-24-seoforge-backoffice-design.md
-- EN: Requirements source - docs/superpowers/specs/2026-08-24-seoforge-backoffice-design.md
-- =====================================================================
```

Состав таблиц — раздел 3.1 спеки, без отступлений. Для каждой таблицы:
`CREATE TABLE`, ограничения (`PK`, `UK`, `CHECK`, `FK`), `CREATE INDEX` по
каждой FK-колонке, `CREATE SEQUENCE <TABLE>_SEQ START WITH 1 INCREMENT BY 1 NOCACHE`,
триггер-нумератор:

```sql
CREATE OR REPLACE TRIGGER TRG_YSEO_SITE_ID
BEFORE INSERT ON YSEO_SITE FOR EACH ROW
WHEN (NEW.COD IS NULL)
BEGIN
  :NEW.COD := YSEO_SITE_SEQ.NEXTVAL;
END;
/
```

Триггер контроля перерасхода ставится последним и опирается на пакет из Task 3:

```sql
CREATE OR REPLACE TRIGGER TRG_YSEO_SPEND_BUDGET
BEFORE INSERT OR UPDATE ON YSEO_SPEND_FACT FOR EACH ROW
DECLARE
  v_rest  NUMBER;
  v_mode  VARCHAR2(20);
  v_mdl   NUMBER;
BEGIN
  :NEW.PERIOD := PK_SEO_UTIL.PERIOD_OF(:NEW.SPEND_DATE);
  v_mdl  := PK_SEO_UTIL.TO_MDL(:NEW.SUMA, :NEW.VALUTA, :NEW.SPEND_DATE);
  :NEW.SUMA_MDL := v_mdl;
  v_mode := PK_SEO_UTIL.GET_SETUP('BUDGET_OVERRUN_MODE');
  v_rest := PK_SEO_BUDGET.CHECK_LIMIT(:NEW.PERIOD, :NEW.ARTICLE_COD1,
                                      :NEW.CHANNEL_COD1, :NEW.SITE_COD, v_mdl);
  IF v_rest < 0 THEN
    IF v_mode = 'BLOCK' THEN
      RAISE_APPLICATION_ERROR(-20101,
        'RO: Cheltuiala depaseste bugetul planificat pentru perioada. / '
        || 'EN: Spend exceeds the planned budget for the period.');
    END IF;
    :NEW.IS_OVERBUDGET := 1;
  ELSE
    :NEW.IS_OVERBUDGET := 0;
  END IF;
END;
/
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add sql/113_yseo_tables.sql tests/test_seoforge.py
git commit -m "feat(seoforge): таблицы контура YSEO_*"
```

---

### Task 2: Вьюшки

**Files:**
- Create: `sql/114_yseo_views.sql`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: таблицы из Task 1, `PK_SEO_UTIL.TO_MDL` из Task 3
- Produces: `VSEO_SITE`, `VSEO_CAMPAIGN`, `VSEO_BUDGET_PLANFACT`, `VSEO_CHANNEL_ROI`

- [ ] **Step 1: Написать падающий тест**

```python
EXPECTED_VIEWS = ["VSEO_SITE", "VSEO_CAMPAIGN", "VSEO_BUDGET_PLANFACT", "VSEO_CHANNEL_ROI"]

def test_views_ddl_declares_every_view():
    ddl = _sql("114_yseo_views.sql").upper()
    for view in EXPECTED_VIEWS:
        assert f"CREATE OR REPLACE VIEW {view}" in ddl, view

def test_roi_view_guards_division_by_zero():
    ddl = _sql("114_yseo_views.sql").upper()
    block = ddl.split("CREATE OR REPLACE VIEW VSEO_CHANNEL_ROI")[1]
    # ROI, CPC и CPA делят на расход и клики — оба могут быть нулём.
    assert block.count("NULLIF(") >= 3

def test_views_ddl_has_no_russian_comments():
    for line in _sql("114_yseo_views.sql").splitlines():
        if line.strip().startswith("--"):
            assert not re.search(r"[а-яА-ЯёЁ]", line), line
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — файл `114_yseo_views.sql` не найден

- [ ] **Step 3: Написать вьюшки**

`VSEO_BUDGET_PLANFACT` — полное внешнее соединение плана и факта, чтобы
в сетку попали и незапланированные расходы, и неизрасходованный план:

```sql
CREATE OR REPLACE VIEW VSEO_BUDGET_PLANFACT AS
SELECT COALESCE(p.PERIOD, f.PERIOD)                 AS PERIOD,
       COALESCE(p.ARTICLE_COD1, f.ARTICLE_COD1)     AS ARTICLE_COD1,
       COALESCE(p.CHANNEL_COD1, f.CHANNEL_COD1)     AS CHANNEL_COD1,
       COALESCE(p.SITE_COD, f.SITE_COD)             AS SITE_COD,
       NVL(p.PLAN_SUMA, 0)                          AS PLAN_SUMA,
       NVL(f.FACT_SUMA, 0)                          AS FACT_SUMA,
       NVL(p.PLAN_SUMA, 0) - NVL(f.FACT_SUMA, 0)    AS REST_SUMA,
       ROUND(NVL(f.FACT_SUMA, 0) * 100
             / NULLIF(p.PLAN_SUMA, 0), 2)           AS DONE_PCT
FROM   (SELECT PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD,
               SUM(PK_SEO_UTIL.TO_MDL(PLAN_SUMA, VALUTA, NULL)) AS PLAN_SUMA
        FROM   YSEO_BUDGET_PLAN
        GROUP  BY PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD) p
FULL OUTER JOIN
       (SELECT PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD,
               SUM(SUMA_MDL) AS FACT_SUMA
        FROM   YSEO_SPEND_FACT
        GROUP  BY PERIOD, ARTICLE_COD1, CHANNEL_COD1, SITE_COD) f
ON     p.PERIOD = f.PERIOD AND p.ARTICLE_COD1 = f.ARTICLE_COD1
   AND NVL(p.CHANNEL_COD1, -1) = NVL(f.CHANNEL_COD1, -1)
   AND NVL(p.SITE_COD, -1) = NVL(f.SITE_COD, -1);
```

`VSEO_CHANNEL_ROI` считает по каналу и периоду: `SUM(SUMA_MDL)`, `SUM(CLICKS)`,
`SUM(IMPRESSIONS)`, `SUM(CONVERSIONS)`, `SUM(REVENUE)`, и производные
`ROI = (REVENUE - SPEND) / NULLIF(SPEND, 0)`, `CPC = SPEND / NULLIF(CLICKS, 0)`,
`CPA = SPEND / NULLIF(CONVERSIONS, 0)`.

`VSEO_SITE` — сайт, число незаархивированных активных кампаний, расход
текущего периода, отклонение от плана. `VSEO_CAMPAIGN` — кампания плюс
план, факт и остаток.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add sql/114_yseo_views.sql tests/test_seoforge.py
git commit -m "feat(seoforge): вьюшки VSEO_* (план/факт, ROI по каналам)"
```

---

### Task 3: Пакеты

**Files:**
- Create: `sql/115_yseo_package.sql`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: таблицы из Task 1
- Produces:
  - `PK_SEO_UTIL.PERIOD_OF(p_date DATE) RETURN VARCHAR2` — `YYYY-MM`
  - `PK_SEO_UTIL.TO_MDL(p_suma NUMBER, p_valuta VARCHAR2, p_date DATE) RETURN NUMBER`
  - `PK_SEO_UTIL.GET_SETUP(p_code VARCHAR2) RETURN VARCHAR2`
  - `PK_SEO_UTIL.LOG_EVENT(p_action, p_entity_type, p_entity_cod, p_details, p_username)`
  - `PK_SEO_BUDGET.PLAN_UPSERT(p_period, p_article, p_channel, p_site, p_suma, p_valuta, p_note, p_username)`
  - `PK_SEO_BUDGET.CHECK_LIMIT(p_period, p_article, p_channel, p_site, p_add_suma) RETURN NUMBER` — остаток плана после добавления суммы; отрицательное значение означает перерасход
  - `PK_SEO_BUDGET.RECALC_OVERBUDGET(p_period VARCHAR2)`

- [ ] **Step 1: Написать падающий тест**

```python
def test_packages_declare_expected_routines():
    ddl = _sql("115_yseo_package.sql").upper()
    for routine in ("PERIOD_OF", "TO_MDL", "GET_SETUP", "LOG_EVENT",
                    "PLAN_UPSERT", "CHECK_LIMIT", "RECALC_OVERBUDGET"):
        assert routine in ddl, routine

def test_packages_have_spec_and_body():
    ddl = _sql("115_yseo_package.sql").upper()
    for pkg in ("PK_SEO_UTIL", "PK_SEO_BUDGET"):
        assert f"CREATE OR REPLACE PACKAGE {pkg}" in ddl, pkg
        assert f"CREATE OR REPLACE PACKAGE BODY {pkg}" in ddl, pkg

def test_business_errors_are_bilingual():
    ddl = _sql("115_yseo_package.sql")
    raises = re.findall(r"RAISE_APPLICATION_ERROR\s*\(\s*-\d+\s*,(.*?)\);", ddl, re.S)
    assert raises, "пакеты обязаны иметь хотя бы одно бизнес-исключение"
    for body in raises:
        assert "RO:" in body and "EN:" in body, body

def test_packages_have_no_russian_comments():
    for line in _sql("115_yseo_package.sql").splitlines():
        if line.strip().startswith("--"):
            assert not re.search(r"[а-яА-ЯёЁ]", line), line
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — файл `115_yseo_package.sql` не найден

- [ ] **Step 3: Написать пакеты**

`TO_MDL` берёт курс на ближайшую дату не позже переданной; если валюта
совпадает с `BASE_CURRENCY`, курс равен единице; если курса нет — исключение
`-20102` с двуязычным текстом (молчаливая единица исказила бы все суммы).
`p_date IS NULL` означает «последний известный курс» — так вьюшка плана
считает без привязки к дате.

`CHECK_LIMIT` возвращает `plan - fact - p_add_suma` по ключу
`(период, статья, канал, сайт)`; отсутствие строки плана трактуется как
нулевой план.

`PLAN_UPSERT` делает `MERGE` по естественному ключу и пишет событие
через `LOG_EVENT`.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add sql/115_yseo_package.sql tests/test_seoforge.py
git commit -m "feat(seoforge): пакеты PK_SEO_UTIL и PK_SEO_BUDGET"
```

---

### Task 4: Справочники и регистрация в деплое

**Files:**
- Create: `sql/116_yseo_dict_seed.sql`
- Modify: `deploy_oracle_objects.py`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: таблицы из Task 1
- Produces: разделы `YSEO_DICT` (`CHANNEL`, `ARTICLE`, `PROMO_TYPE`, `FORMAT`, `BUYUNIT`, `METRIC`), параметры `YSEO_SETUP` (`BASE_CURRENCY = MDL`, `BUDGET_OVERRUN_MODE = WARN`)

- [ ] **Step 1: Написать падающий тест**

```python
def test_seed_covers_every_dictionary_section():
    seed = _sql("116_yseo_dict_seed.sql").upper()
    for section in ("CHANNEL", "ARTICLE", "PROMO_TYPE", "FORMAT", "BUYUNIT", "METRIC"):
        assert f"'{section}'" in seed, section

def test_seed_is_idempotent():
    # Повторный прогон установки не должен ронять деплой на дублях.
    seed = _sql("116_yseo_dict_seed.sql").upper()
    assert seed.count("MERGE INTO") >= 2
    assert "INSERT INTO YSEO_DICT" not in seed

def test_seed_declares_default_settings():
    seed = _sql("116_yseo_dict_seed.sql").upper()
    assert "BASE_CURRENCY" in seed and "'MDL'" in seed
    assert "BUDGET_OVERRUN_MODE" in seed

def test_deploy_registers_yseo_files_in_order():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    order = [src.index(f'"{name}"') for name in (
        "113_yseo_tables.sql", "114_yseo_views.sql",
        "115_yseo_package.sql", "116_yseo_dict_seed.sql")]
    assert order == sorted(order), "файлы контура должны идти в порядке зависимостей"
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — файл `116_yseo_dict_seed.sql` не найден

- [ ] **Step 3: Написать seed и зарегистрировать файлы**

Наполнение через `MERGE INTO … USING DUAL … WHEN NOT MATCHED THEN INSERT`,
чтобы повторный деплой не падал. Каналы — из §4.2.6 и §5 ТЗ: `GOOGLE_ORGANIC`,
`FACEBOOK`, `INSTAGRAM`, `LINKEDIN`, `TIKTOK`, `YOUTUBE`, `TELEGRAM`,
`POINT_MD`, `999_MD`, `CATALOGS`, `EMAIL`, `GOOGLE_ADS`, `META_ADS`.

В `deploy_oracle_objects.py` четыре файла добавляются в конец списка
`sql_files` в порядке `113 → 114 → 115 → 116`.

Порядок установки требует внимания: триггер из `113` ссылается на пакеты
из `115`, поэтому после первого прогона `113` триггер остаётся невалидным
и компилируется при установке `115`. Это штатное поведение Oracle
(`CREATE OR REPLACE TRIGGER` с обращением к ещё не созданному пакету
компилируется с ошибкой, но перекомпилируется автоматически при первом
использовании после появления пакета). В самом конце `116` ставится
`ALTER TRIGGER TRG_YSEO_SPEND_BUDGET COMPILE;`, чтобы деплой заканчивался
валидной схемой, а не отложенной перекомпиляцией.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add sql/116_yseo_dict_seed.sql deploy_oracle_objects.py tests/test_seoforge.py
git commit -m "feat(seoforge): справочники контура и регистрация DDL в деплое"
```

---

### Task 5: Чистая логика CSV

**Files:**
- Create: `models/seo_csv.py`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: ничего (чистый модуль: без Oracle, без Flask)
- Produces:
  - `period_of(day: date | str) -> str` — `YYYY-MM`
  - `make_ext_id(source: str, day: str, campaign: str, channel: str, extra: str = "") -> str` — детерминированный hex-хеш длиной 32
  - `SPEND_COLUMNS: tuple[str, ...]`, `METRICS_COLUMNS: tuple[str, ...]`
  - `parse_spend_csv(text: str) -> ParseResult`
  - `parse_metrics_csv(text: str) -> ParseResult`
  - `ParseResult` — `dataclass` с полями `rows: list[dict]`, `errors: list[dict]`, `columns: list[str]`

- [ ] **Step 1: Написать падающие тесты**

```python
from models.seo_csv import (period_of, make_ext_id, parse_spend_csv,
                            parse_metrics_csv, SPEND_COLUMNS)

def test_period_of_formats_year_month():
    assert period_of("2026-08-25") == "2026-08"
    import datetime
    assert period_of(datetime.date(2026, 1, 3)) == "2026-01"

def test_period_of_rejects_garbage():
    import pytest
    with pytest.raises(ValueError):
        period_of("25.08.2026 maybe")

def test_make_ext_id_is_deterministic_and_sensitive():
    a = make_ext_id("google_ads", "2026-08-25", "back_to_school", "GOOGLE_ADS")
    b = make_ext_id("google_ads", "2026-08-25", "back_to_school", "GOOGLE_ADS")
    c = make_ext_id("google_ads", "2026-08-26", "back_to_school", "GOOGLE_ADS")
    assert a == b and a != c
    assert len(a) == 32 and all(ch in "0123456789abcdef" for ch in a)

def _spend_csv(*rows):
    head = ";".join(SPEND_COLUMNS)
    return "\n".join([head, *rows])

def test_parse_spend_csv_reads_a_good_row():
    text = _spend_csv("officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-25;1250.50;MDL;300;15000;12;8400;")
    res = parse_spend_csv(text)
    assert res.errors == []
    assert len(res.rows) == 1
    row = res.rows[0]
    assert row["site"] == "officeplus.md"
    assert row["suma"] == 1250.50
    assert row["clicks"] == 300
    assert row["period"] == "2026-08"
    assert len(row["ext_id"]) == 32

def test_parse_spend_csv_reports_bad_number_without_dropping_other_rows():
    text = _spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-25;не число;MDL;300;15000;12;8400;",
        "officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-26;10;MDL;1;2;0;0;",
    )
    res = parse_spend_csv(text)
    assert len(res.rows) == 1
    assert len(res.errors) == 1
    assert res.errors[0]["line"] == 2
    assert "SUMA" in res.errors[0]["message"].upper()

def test_parse_spend_csv_requires_mandatory_columns():
    res = parse_spend_csv("site;suma\nofficeplus.md;10")
    assert res.rows == []
    assert res.errors and "SPEND_DATE" in res.errors[0]["message"].upper()

def test_parse_spend_csv_rejects_negative_amount():
    text = _spend_csv("officeplus.md;GOOGLE_ADS;ADS;c;2026-08-25;-5;MDL;0;0;0;0;")
    res = parse_spend_csv(text)
    assert res.rows == [] and len(res.errors) == 1

def test_parse_spend_csv_accepts_comma_decimal_and_tab_separator():
    head = "\t".join(SPEND_COLUMNS)
    text = head + "\n" + "officeplus.md\tGOOGLE_ADS\tADS\tc\t2026-08-25\t1250,50\tMDL\t0\t0\t0\t0\t"
    res = parse_spend_csv(text)
    assert res.errors == [] and res.rows[0]["suma"] == 1250.50

def test_parse_spend_csv_keeps_supplied_ext_id():
    text = _spend_csv("officeplus.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;0;0;0;0;campaign-42-day-1")
    res = parse_spend_csv(text)
    assert res.rows[0]["ext_id"] == "campaign-42-day-1"

def test_parse_metrics_csv_reads_a_good_row():
    from models.seo_csv import METRICS_COLUMNS
    text = ";".join(METRICS_COLUMNS) + "\n" + "una.md;POSITION_AVG;GOOGLE_ORGANIC;2026-08-25;7.4;gsc;"
    res = parse_metrics_csv(text)
    assert res.errors == [] and res.rows[0]["value"] == 7.4
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — `ModuleNotFoundError: models.seo_csv`

- [ ] **Step 3: Реализовать модуль**

Разделитель определяется по первой строке (`;`, `\t`, `,` — что чаще).
Числа принимают и точку, и запятую как десятичный разделитель. Пустая
необязательная числовая ячейка даёт `0`, пустая обязательная — ошибку.
Ошибка строки не прерывает разбор: строка попадает в `errors`
с номером и текстом, остальные читаются дальше. `ext_id` из файла
используется как есть, иначе собирается `make_ext_id`.

Колонки расхода: `site`, `channel`, `article`, `campaign`, `spend_date`,
`suma`, `valuta`, `clicks`, `impressions`, `conversions`, `revenue`, `ext_id`.
Колонки метрик: `site`, `metric`, `channel`, `fact_date`, `value`, `source`, `ext_id`.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add models/seo_csv.py tests/test_seoforge.py
git commit -m "feat(seoforge): разбор и валидация CSV расходов и метрик"
```

---

### Task 6: Хранилище

**Files:**
- Create: `models/seo_oracle_store.py`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: `models.database.DatabaseModel`, `models.seo_csv`
- Produces (все методы возвращают `{"success": bool, "data": ..., "message": str}`):
  - `list_sites(include_archived=False)`, `save_site(payload, username)`, `archive_site(cod, username)`
  - `list_platforms(...)`, `save_platform(...)`, `archive_platform(...)`
  - `list_dict(section)`, `save_dict(section, payload, username)`
  - `list_fx()`, `save_fx(valuta, rate_date, rate, username)`
  - `list_campaigns(site_cod=None)`, `save_campaign(payload, username)`, `set_campaign_status(cod, status, username)`
  - `plan_upsert(payload, username)`, `planfact(period=None, site_cod=None)`
  - `list_spend(period=None, site_cod=None)`, `add_spend(payload, username)`
  - `list_metrics(period=None, site_cod=None)`, `add_metrics(payload, username)`
  - `import_commit(kind, file_name, rows, username)` → `{"import_cod", "loaded", "skipped"}`
  - `existing_ext_ids(kind, ext_ids)` → `set[str]`
  - `roi(period_from=None, period_to=None, site_cod=None)`
  - `get_settings()`, `save_settings(values, username)`, `list_events(limit=200)`

- [ ] **Step 1: Написать падающие тесты**

```python
from unittest.mock import patch, MagicMock
from models import seo_oracle_store as store

def _db(query_results=None, dml_ok=True):
    """Мок DatabaseModel: возвращает подготовленные ответы execute_query."""
    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    results = list(query_results or [])
    def _exec(sql, params=None):
        if results:
            return results.pop(0)
        return {"success": dml_ok, "data": [], "columns": [], "rowcount": 1,
                "message": "" if dml_ok else "ORA-00001: unique constraint"}
    db.execute_query.side_effect = _exec
    return db

def test_list_sites_maps_rows_to_dicts():
    rows = {"success": True, "columns": ["COD", "DOMAIN"], "data": [[1, "una.md"]],
            "rowcount": 1, "message": ""}
    with patch.object(store, "DatabaseModel", return_value=_db([rows])):
        res = store.list_sites()
    assert res["success"] is True
    assert res["data"] == [{"cod": 1, "domain": "una.md"}]

def test_list_sites_hides_archived_by_default():
    captured = {}
    db = _db([{"success": True, "columns": [], "data": [], "rowcount": 0, "message": ""}])
    def _exec(sql, params=None):
        captured["sql"] = sql
        return {"success": True, "columns": [], "data": [], "rowcount": 0, "message": ""}
    db.execute_query.side_effect = _exec
    with patch.object(store, "DatabaseModel", return_value=db):
        store.list_sites()
    assert "ISARHIV = 0" in captured["sql"].upper()

def test_save_site_commits():
    db = _db()
    with patch.object(store, "DatabaseModel", return_value=db):
        res = store.save_site({"domain": "una.md", "locales": "ru,ro"}, "pt")
    assert res["success"] is True
    db.connection.commit.assert_called_once()

def test_failed_dml_does_not_commit():
    db = _db(dml_ok=False)
    with patch.object(store, "DatabaseModel", return_value=db):
        res = store.save_site({"domain": "una.md", "locales": "ru"}, "pt")
    assert res["success"] is False
    db.connection.commit.assert_not_called()

def test_archive_site_sets_flag_and_never_deletes():
    captured = []
    db = _db()
    db.execute_query.side_effect = lambda sql, params=None: (
        captured.append(sql),
        {"success": True, "columns": [], "data": [], "rowcount": 1, "message": ""})[1]
    with patch.object(store, "DatabaseModel", return_value=db):
        store.archive_site(1, "pt")
    joined = " ".join(captured).upper()
    assert "ISARHIV = 1" in joined and "DELETE" not in joined

def test_existing_ext_ids_returns_a_set():
    rows = {"success": True, "columns": ["EXT_ID"], "data": [["a"], ["b"]],
            "rowcount": 2, "message": ""}
    with patch.object(store, "DatabaseModel", return_value=_db([rows])):
        assert store.existing_ext_ids("SPEND", ["a", "b", "c"]) == {"a", "b"}

def test_existing_ext_ids_without_input_does_not_touch_the_database():
    db = _db()
    with patch.object(store, "DatabaseModel", return_value=db):
        assert store.existing_ext_ids("SPEND", []) == set()
    db.execute_query.assert_not_called()

def test_import_commit_counts_loaded_and_skipped():
    seq = [
        {"success": True, "columns": ["COD"], "data": [[7]], "rowcount": 1, "message": ""},   # партия
        {"success": True, "columns": ["EXT_ID"], "data": [["dup"]], "rowcount": 1, "message": ""},  # дубли
    ]
    with patch.object(store, "DatabaseModel", return_value=_db(seq)):
        res = store.import_commit("SPEND", "ads.csv",
                                  [{"ext_id": "dup"}, {"ext_id": "new"}], "pt")
    assert res["data"]["loaded"] == 1
    assert res["data"]["skipped"] == 1
    assert res["data"]["import_cod"] == 7
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — `ModuleNotFoundError: models.seo_oracle_store`

- [ ] **Step 3: Реализовать хранилище**

Общий каркас — как в `controllers/digi_marketing_controller.py`: помощник
`_rows(result)` приводит `columns` + `data` к списку словарей с ключами
в нижнем регистре; `_run(sql, params, commit)` открывает `DatabaseModel`,
выполняет запрос, коммитит только при успехе.

Все параметры — именованные bind-переменные, конкатенации значений в SQL нет.
Выборки читают вьюшки `VSEO_*`, записи идут в таблицы либо через пакеты
(`PK_SEO_BUDGET.PLAN_UPSERT`). Каждая запись сопровождается
`PK_SEO_UTIL.LOG_EVENT` в той же транзакции.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add models/seo_oracle_store.py tests/test_seoforge.py
git commit -m "feat(seoforge): хранилище модуля поверх контура YSEO_*"
```

---

### Task 7: Контроллер

**Files:**
- Create: `controllers/seo_controller.py`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: `models.seo_oracle_store`, `models.seo_csv`
- Produces: класс `SeoController` со статическими методами, каждый возвращает
  `(payload: dict, http_status: int)`:
  - `sites()`, `save_site(payload)`, `archive_site(cod)`
  - `platforms()`, `save_platform(payload)`, `archive_platform(cod)`
  - `dictionary(section)`, `save_dictionary(section, payload)`
  - `fx()`, `save_fx(payload)`
  - `campaigns(site_cod)`, `save_campaign(payload)`, `set_campaign_status(cod, status)`
  - `plan_save(payload)`, `planfact(period, site_cod)`
  - `spend(period, site_cod)`, `add_spend(payload)`
  - `metrics(period, site_cod)`, `add_metrics(payload)`
  - `import_preview(kind, file_name, text)`, `import_commit(kind, file_name, text)`
  - `roi(period_from, period_to, site_cod)`
  - `settings()`, `save_settings(payload)`, `events()`
- `SeoController.error_status(message: str) -> int` — маппинг сообщения Oracle в HTTP-код

- [ ] **Step 1: Написать падающие тесты**

```python
from controllers.seo_controller import SeoController

def test_business_error_becomes_409():
    msg = ("ORA-20101: RO: Cheltuiala depaseste bugetul planificat. / "
           "EN: Spend exceeds the planned budget.")
    assert SeoController.error_status(msg) == 409

def test_unique_constraint_becomes_409():
    assert SeoController.error_status("ORA-00001: unique constraint violated") == 409

def test_unknown_error_becomes_500():
    assert SeoController.error_status("ORA-03113: end-of-file on communication") == 500

def test_save_site_rejects_empty_domain_before_touching_the_database():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.save_site({"domain": "  "})
    assert status == 400
    assert payload["success"] is False
    st.save_site.assert_not_called()

def test_save_campaign_rejects_reversed_dates():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.save_campaign(
            {"camp_code": "c1", "site_cod": 1, "date_start": "2026-09-01",
             "date_end": "2026-08-01", "promo_type_cod1": 1})
    assert status == 400
    st.save_campaign.assert_not_called()

def test_import_preview_never_writes():
    text = "site;channel;article;campaign;spend_date;suma;valuta;clicks;impressions;conversions;revenue;ext_id\n" \
           "una.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;1;2;0;0;"
    with patch.object(SeoController, "_store") as st:
        st.existing_ext_ids.return_value = set()
        payload, status = SeoController.import_preview("SPEND", "ads.csv", text)
    assert status == 200
    assert payload["data"]["rows"][0]["site"] == "una.md"
    st.import_commit.assert_not_called()

def test_import_preview_marks_duplicates():
    text = "site;channel;article;campaign;spend_date;suma;valuta;clicks;impressions;conversions;revenue;ext_id\n" \
           "una.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;1;2;0;0;fixed-id"
    with patch.object(SeoController, "_store") as st:
        st.existing_ext_ids.return_value = {"fixed-id"}
        payload, status = SeoController.import_preview("SPEND", "ads.csv", text)
    assert payload["data"]["duplicates"] == ["fixed-id"]
    assert payload["data"]["rows"][0]["is_duplicate"] is True

def test_import_commit_refuses_a_file_with_only_errors():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.import_commit("SPEND", "bad.csv", "site;suma\nx;1")
    assert status == 400
    st.import_commit.assert_not_called()

def test_unknown_import_kind_is_rejected():
    payload, status = SeoController.import_preview("PAYROLL", "x.csv", "a;b")
    assert status == 400
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — `ModuleNotFoundError: controllers.seo_controller`

- [ ] **Step 3: Реализовать контроллер**

`_store` — ссылка на модуль хранилища, вынесена атрибутом класса, чтобы
тесты могли её подменить. Валидация ввода происходит до обращения к базе:
пустые обязательные поля, перевёрнутые даты, отрицательные суммы,
неизвестный `kind` импорта. `error_status` разбирает сообщение: `ORA-20xxx`
и `ORA-00001` → `409`, всё остальное → `500`. Имя пользователя берётся
из `flask.session` с запасным значением `system`, как в соседних контроллерах.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Коммит**

```bash
git add controllers/seo_controller.py tests/test_seoforge.py
git commit -m "feat(seoforge): контроллер модуля, валидация и маппинг ошибок"
```

---

### Task 8: Маршруты, интерфейс, манифест

**Files:**
- Modify: `app.py`
- Create: `templates/seoforge.html`
- Create: `modules/seoforge/module.json`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: `controllers.seo_controller.SeoController`
- Produces: страница `/UNA.md/orasldev/seoforge` и JSON-API `/UNA.md/orasldev/seoforge/api/…`

- [ ] **Step 1: Написать падающие тесты**

```python
import json

def test_module_manifest_is_valid_and_trilingual():
    path = os.path.join(ROOT, "modules", "seoforge", "module.json")
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert set(manifest["title"]) >= {"ru", "ro", "en"}
    assert manifest["url"] == "/UNA.md/orasldev/seoforge"
    assert manifest["sql_prefix"] == "YSEO_"

def test_app_registers_the_page_and_the_api():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "'/UNA.md/orasldev/seoforge'" in src
    assert "/UNA.md/orasldev/seoforge/api/sites" in src
    assert "SeoController" in src

def test_every_page_route_is_guarded_by_authentication():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    block = src.split("SEOForge")[1].split("\n@app.route")[0]
    assert "AuthController.is_authenticated()" in block

def test_template_declares_every_panel():
    with open(os.path.join(ROOT, "templates", "seoforge.html"), encoding="utf-8") as fh:
        html = fh.read()
    for panel in ("portfolio", "sites", "campaigns", "budget", "facts", "roi", "refs"):
        assert f'id="panel-{panel}"' in html, panel
        assert f"data-panel=\"{panel}\"" in html, panel
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — манифест и шаблон не найдены

- [ ] **Step 3: Написать маршруты, шаблон и манифест**

Маршруты добавляются в `app.py` отдельным блоком с шапкой
`# ========== SEOForge Routes ==========`, по образцу блока DIGI SM.
Страница отдаёт `render_template('seoforge.html')` после проверки
`AuthController.is_authenticated()`. Каждый API-маршрут вызывает метод
контроллера и возвращает `jsonify(payload), status`.

Шаблон повторяет структуру `templates/digi_marketing.html`: боковая
навигация `div.nav-item[data-panel]`, панели `div.panel#panel-<key>`,
функция `showPanel(name)`. Данные тянутся `fetch` с тех же адресов.
Импорт — форма с выбором файла, кнопка «Предпросмотр» рисует таблицу
разобранных строк, ошибок и дублей, кнопка «Загрузить» становится
доступной только после успешного предпросмотра.

Манифест:

```json
{
  "title": {
    "ru": "SEOForge — AI-SEO продвижение",
    "ro": "SEOForge — promovare AI-SEO",
    "en": "SEOForge — AI-SEO promotion"
  },
  "icon": "🚀",
  "order": 115,
  "url": "/UNA.md/orasldev/seoforge",
  "sql_prefix": "YSEO_",
  "descr": "Сайты, кампании, бюджет план/факт, ROI по каналам",
  "docs": "SEOForge",
  "pages": {
    "seoforge": {"ru": "SEOForge", "ro": "SEOForge", "en": "SEOForge"}
  }
}
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: PASS

- [ ] **Step 5: Проверить, что приложение импортируется**

Run: `./venv/bin/python -c "import app; print(len(list(app.app.url_map.iter_rules())))"`
Expected: число маршрутов печатается без исключения

- [ ] **Step 6: Коммит**

```bash
git add app.py templates/seoforge.html modules/seoforge/module.json tests/test_seoforge.py
git commit -m "feat(seoforge): страница модуля, JSON-API и манифест меню"
```

---

### Task 9: Живой smoke и документация

**Files:**
- Create: `scripts/seoforge_smoke.py`
- Create: `docs/SEOForge/README.md`, `docs/SEOForge/DATA_MODEL.md`, `docs/SEOForge/CSV_FORMAT.md`, `docs/SEOForge/docs.json`
- Modify: `tests/test_seoforge.py`

**Interfaces:**
- Consumes: `models.seo_oracle_store`, установленный контур
- Produces: скрипт проверки инвариантов; документация модуля

- [ ] **Step 1: Написать падающие тесты**

```python
def test_docs_registry_lists_every_document():
    docs_dir = os.path.join(ROOT, "docs", "SEOForge")
    with open(os.path.join(docs_dir, "docs.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    listed = {item["file"] for item in registry["docs"]}
    on_disk = {n for n in os.listdir(docs_dir) if n.endswith(".md")}
    assert on_disk == listed

def test_csv_format_doc_matches_the_parser():
    from models.seo_csv import SPEND_COLUMNS, METRICS_COLUMNS
    with open(os.path.join(ROOT, "docs", "SEOForge", "CSV_FORMAT.md"), encoding="utf-8") as fh:
        text = fh.read()
    for col in SPEND_COLUMNS + METRICS_COLUMNS:
        assert col in text, col

def test_smoke_script_covers_every_declared_invariant():
    with open(os.path.join(ROOT, "scripts", "seoforge_smoke.py"), encoding="utf-8") as fh:
        src = fh.read()
    for check in ("check_plan_and_spend", "check_overrun_blocked",
                  "check_overrun_warned", "check_import_dedup",
                  "check_archive_not_delete", "check_views"):
        assert f"def {check}" in src, check
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `./venv/bin/python -m pytest tests/test_seoforge.py -q`
Expected: FAIL — документация и скрипт не найдены

- [ ] **Step 3: Написать smoke и документацию**

`scripts/seoforge_smoke.py` — шесть функций-проверок из §8 спеки, каждая
печатает `OK` или `FAIL` с пояснением; работа идёт на служебном сайте
с доменом `smoke.invalid`, который в конце архивируется. Скрипт требует
явного `--yes`, чтобы случайный запуск не насорил в базе.

`docs/SEOForge/README.md` — назначение модуля, что вошло в v1 и что отложено.
`DATA_MODEL.md` — таблицы, вьюшки, пакеты, инварианты.
`CSV_FORMAT.md` — колонки обоих импортов, правила `EXT_ID`, примеры файлов.
`docs.json` — реестр для `models/doc_registry.py`.

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `./venv/bin/python -m pytest tests/ -q`
Expected: PASS — весь набор тестов проекта

- [ ] **Step 5: Коммит**

```bash
git add scripts/seoforge_smoke.py docs/SEOForge tests/test_seoforge.py
git commit -m "docs(seoforge): документация модуля и живой smoke контура"
```

---

## Что остаётся после плана

Установка контура в облачную базу (`python deploy_oracle_objects.py`) и прогон
`scripts/seoforge_smoke.py --yes` — отдельный шаг, требующий рабочего wallet.
Пока он не сделан, инварианты пакетов проверены только чтением кода.
Выкатка на боевой сервер в этот план не входит.

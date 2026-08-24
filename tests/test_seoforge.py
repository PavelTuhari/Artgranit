"""SEOForge module — unit tests (no live Oracle).

Контур YSEO_* ставится в облачную базу бэкофиса, но тесты не должны требовать
ни wallet, ни сети. Поэтому DDL проверяется разбором файлов (это ловит ровно
те ошибки, которые дороже всего стоят: забытый индекс по FK, потерянный
префикс, русский комментарий в коде БД), а Python-слой — моками поверх
DatabaseModel, как в tests/test_biro26.py.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


# ── Task 1: таблицы контура ──────────────────────────────────────────

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
    natural_pk = {"YSEO_FX_RATE", "YSEO_SETUP"}
    for table in EXPECTED_TABLES:
        if table in natural_pk:
            continue
        assert f"CREATE SEQUENCE {table}_SEQ" in ddl, table
        assert f"{table}_SEQ.NEXTVAL" in ddl, table


def test_spend_fact_is_guarded_by_the_budget_trigger():
    ddl = _sql("113_yseo_tables.sql").upper()
    assert "CREATE OR REPLACE TRIGGER TRG_YSEO_SPEND_BUDGET" in ddl
    block = ddl.split("TRG_YSEO_SPEND_BUDGET")[1]
    assert "PK_SEO_BUDGET.ENFORCE_KEYS" in block


def test_budget_trigger_is_compound_to_avoid_mutating_table():
    # Проверка лимита читает саму YSEO_SPEND_FACT: построчный триггер
    # упал бы с ORA-04091. Сбор ключей в BEFORE EACH ROW, проверка —
    # один раз в AFTER STATEMENT.
    ddl = _sql("113_yseo_tables.sql").upper()
    block = ddl.split("CREATE OR REPLACE TRIGGER TRG_YSEO_SPEND_BUDGET")[1]
    assert "COMPOUND TRIGGER" in block
    assert "BEFORE EACH ROW" in block
    assert "AFTER STATEMENT" in block


def test_fact_tables_deduplicate_by_ext_id():
    ddl = _sql("113_yseo_tables.sql").upper()
    for table in ("YSEO_SPEND_FACT", "YSEO_METRICS_FACT"):
        block = ddl.split(f"CREATE TABLE {table} (")[1].split(");")[0]
        assert "EXT_ID" in block, table
        assert re.search(r"UNIQUE \(EXT_ID\)", block), table


# ── Task 2: вьюшки ───────────────────────────────────────────────────

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


def test_planfact_view_keeps_unplanned_spend():
    # Расход по статье без плана обязан попасть в сетку, иначе перерасход
    # молча исчезнет из отчёта.
    ddl = _sql("114_yseo_views.sql").upper()
    block = ddl.split("CREATE OR REPLACE VIEW VSEO_BUDGET_PLANFACT")[1].split(";")[0]
    assert "FULL OUTER JOIN" in block


def test_views_ddl_has_no_russian_comments():
    for line in _sql("114_yseo_views.sql").splitlines():
        if line.strip().startswith("--"):
            assert not re.search(r"[а-яА-ЯёЁ]", line), line


# ── Task 3: пакеты ───────────────────────────────────────────────────

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


def test_missing_fx_rate_is_an_error_not_a_silent_one():
    # Молчаливая единица вместо курса исказила бы все суммы отчётов.
    body = _sql("115_yseo_package.sql").upper().split("FUNCTION TO_MDL")[-1]
    assert "RAISE_APPLICATION_ERROR" in body


def test_packages_have_no_russian_comments():
    for line in _sql("115_yseo_package.sql").splitlines():
        if line.strip().startswith("--"):
            assert not re.search(r"[а-яА-ЯёЁ]", line), line

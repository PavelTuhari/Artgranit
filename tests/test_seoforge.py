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


# ── Task 4: справочники и деплой ─────────────────────────────────────

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


def test_seed_recompiles_the_budget_trigger():
    # Триггер из 113 ссылается на пакеты из 115 и до их установки невалиден.
    seed = _sql("116_yseo_dict_seed.sql").upper()
    assert "ALTER TRIGGER TRG_YSEO_SPEND_BUDGET COMPILE" in seed


def test_deploy_registers_yseo_files_in_order():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    order = [src.index(f'"{name}"') for name in (
        "113_yseo_tables.sql", "114_yseo_views.sql",
        "115_yseo_package.sql", "116_yseo_dict_seed.sql")]
    assert order == sorted(order), "файлы контура должны идти в порядке зависимостей"


def test_sql_comments_never_contain_a_semicolon_or_a_quote():
    # deploy_oracle_objects.py режет скрипт по ';' и отслеживает кавычки,
    # НЕ вырезая комментарии: точка с запятой или апостроф внутри '--'
    # разрывает команду пополам и валит установку.
    for name in ("113_yseo_tables.sql", "114_yseo_views.sql",
                 "115_yseo_package.sql", "116_yseo_dict_seed.sql"):
        for no, line in enumerate(_sql(name).splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith("--"):
                continue
            assert ";" not in stripped, f"{name}:{no} {stripped}"
            assert "'" not in stripped and '"' not in stripped, f"{name}:{no} {stripped}"


# ── Task 5: разбор CSV ───────────────────────────────────────────────

import datetime

import pytest

from models.seo_csv import (METRICS_COLUMNS, SPEND_COLUMNS, make_ext_id,
                            parse_metrics_csv, parse_spend_csv, period_of)


def test_period_of_formats_year_month():
    assert period_of("2026-08-25") == "2026-08"
    assert period_of(datetime.date(2026, 1, 3)) == "2026-01"


def test_period_of_rejects_garbage():
    with pytest.raises(ValueError):
        period_of("25.08.2026 maybe")


def test_make_ext_id_is_deterministic_and_sensitive():
    a = make_ext_id("google_ads", "2026-08-25", "back_to_school", "GOOGLE_ADS")
    b = make_ext_id("google_ads", "2026-08-25", "back_to_school", "GOOGLE_ADS")
    c = make_ext_id("google_ads", "2026-08-26", "back_to_school", "GOOGLE_ADS")
    assert a == b and a != c
    assert len(a) == 32 and all(ch in "0123456789abcdef" for ch in a)


def _spend_csv(*rows):
    return "\n".join([";".join(SPEND_COLUMNS), *rows])


def test_parse_spend_csv_reads_a_good_row():
    res = parse_spend_csv(_spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-25;1250.50;MDL;300;15000;12;8400;"))
    assert res.errors == []
    assert len(res.rows) == 1
    row = res.rows[0]
    assert row["site"] == "officeplus.md"
    assert row["suma"] == 1250.50
    assert row["clicks"] == 300
    assert row["period"] == "2026-08"
    assert len(row["ext_id"]) == 32


def test_parse_spend_csv_reports_bad_number_without_dropping_other_rows():
    res = parse_spend_csv(_spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-25;не число;MDL;300;15000;12;8400;",
        "officeplus.md;GOOGLE_ADS;ADS;back_to_school;2026-08-26;10;MDL;1;2;0;0;",
    ))
    assert len(res.rows) == 1
    assert len(res.errors) == 1
    assert res.errors[0]["line"] == 2
    assert "SUMA" in res.errors[0]["message"].upper()


def test_parse_spend_csv_requires_mandatory_columns():
    res = parse_spend_csv("site;suma\nofficeplus.md;10")
    assert res.rows == []
    assert res.errors and "SPEND_DATE" in res.errors[0]["message"].upper()


def test_parse_spend_csv_rejects_negative_amount():
    res = parse_spend_csv(_spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;c;2026-08-25;-5;MDL;0;0;0;0;"))
    assert res.rows == [] and len(res.errors) == 1


def test_parse_spend_csv_accepts_comma_decimal_and_tab_separator():
    text = ("\t".join(SPEND_COLUMNS) + "\n"
            + "officeplus.md\tGOOGLE_ADS\tADS\tc\t2026-08-25\t1250,50\tMDL\t0\t0\t0\t0\t")
    res = parse_spend_csv(text)
    assert res.errors == [] and res.rows[0]["suma"] == 1250.50


def test_parse_spend_csv_keeps_supplied_ext_id():
    res = parse_spend_csv(_spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;0;0;0;0;campaign-42-day-1"))
    assert res.rows[0]["ext_id"] == "campaign-42-day-1"


def test_parse_spend_csv_ignores_blank_lines_and_bom():
    text = "﻿" + _spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;0;0;0;0;", "", "   ")
    res = parse_spend_csv(text)
    assert res.errors == [] and len(res.rows) == 1


def test_parse_spend_csv_rejects_a_bad_date():
    res = parse_spend_csv(_spend_csv(
        "officeplus.md;GOOGLE_ADS;ADS;c;25/08/2026;10;MDL;0;0;0;0;"))
    assert res.rows == []
    assert "SPEND_DATE" in res.errors[0]["message"].upper()


def test_parse_metrics_csv_reads_a_good_row():
    text = ";".join(METRICS_COLUMNS) + "\n" + \
        "una.md;POSITION_AVG;GOOGLE_ORGANIC;2026-08-25;7.4;gsc;"
    res = parse_metrics_csv(text)
    assert res.errors == [] and res.rows[0]["value"] == 7.4
    assert res.rows[0]["period"] == "2026-08"


def test_parse_metrics_csv_allows_negative_values():
    # Дельта позиции или изменение трафика бывают отрицательными.
    text = ";".join(METRICS_COLUMNS) + "\n" + "una.md;CTR;;2026-08-25;-1.5;gsc;"
    res = parse_metrics_csv(text)
    assert res.errors == [] and res.rows[0]["value"] == -1.5


def test_empty_file_is_an_error_not_an_empty_success():
    res = parse_spend_csv("")
    assert res.rows == [] and res.errors

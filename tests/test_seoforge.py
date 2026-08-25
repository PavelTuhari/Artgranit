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
MODULE_DIR = os.path.join(ROOT, "modules", "seoforge")
SQL_DIR = os.path.join(MODULE_DIR, "sql")


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


def test_erp_installer_keeps_dependency_order():
    # Не по номерам, а по зависимостям: вьюшки VSEO_BUDGET_PLANFACT и
    # VSEO_SITE вызывают PK_SEO_UTIL.TO_MDL, поэтому пакеты (115) обязаны
    # ставиться раньше вьюшек (114) — иначе вьюшки не компилируются.
    from modules.seoforge.scripts.seoforge_deploy_erp import FILES
    assert list(FILES) == ["113_yseo_tables.sql", "115_yseo_package.sql",
                           "114_yseo_views.sql", "116_yseo_dict_seed.sql"]


def test_shared_deploy_script_is_untouched_by_the_module():
    # Контур ставится своим установщиком в ERP. Общий скрипт облачной базы
    # модуль не трогает вовсе — ни файлами, ни комментариями.
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "yseo" not in src.lower()
    assert "seoforge" not in src.lower()


def test_store_uses_the_erp_transport_only():
    # Thick-режим включается на весь процесс: если хранилище возьмёт
    # DatabaseModel, модуль полезет в облачную базу, где контура больше нет.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "Biro26DB" in src
    assert "DatabaseModel" not in src


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

from modules.seoforge.csv_format import (METRICS_COLUMNS, SPEND_COLUMNS, make_ext_id,
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


# ── Task 6: хранилище ────────────────────────────────────────────────

from unittest.mock import MagicMock, patch

from modules.seoforge import store


def _ok(columns=None, data=None, rowcount=1):
    return {"success": True, "columns": columns or [], "data": data or [],
            "rowcount": rowcount, "message": ""}


def _db(query_results=None, script_ok=True, script_results=None):
    """Мок Biro26DB: контур живёт в ERP, туда ходят через воркер.

    Постоянного соединения нет: чтения — execute_query, записи — один
    execute_script на всю операцию.
    """
    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    results = list(query_results or [])
    db.captured = []

    def _query(sql, params=None):
        db.captured.append(sql)
        return results.pop(0) if results else _ok()

    def _script(statements):
        db.captured.extend(st["sql"] for st in statements)
        db.script_calls.append(statements)
        if script_ok:
            return {"success": True,
                    "results": script_results or [{"rowcount": 1}
                                                  for _ in statements],
                    "message": ""}
        return {"success": False, "results": [],
                "message": "ORA-00001: unique constraint violated"}

    db.script_calls = []
    db.execute_query.side_effect = _query
    db.execute_script.side_effect = _script
    return db


def test_list_sites_maps_rows_to_dicts():
    rows = _ok(["COD", "DOMAIN"], [[1, "una.md"]])
    with patch.object(store, "Biro26DB", return_value=_db([rows])):
        res = store.list_sites()
    assert res["success"] is True
    assert res["data"] == [{"cod": 1, "domain": "una.md"}]


def test_list_sites_hides_archived_by_default():
    db = _db([_ok()])
    with patch.object(store, "Biro26DB", return_value=db):
        store.list_sites()
    assert "ISARHIV = 0" in db.captured[0].upper()


def test_list_sites_can_include_archived():
    db = _db([_ok()])
    with patch.object(store, "Biro26DB", return_value=db):
        store.list_sites(include_archived=True)
    assert "ISARHIV = 0" not in db.captured[0].upper()


def test_write_goes_through_a_single_transaction():
    # Воркер коммитит скрипт целиком: две команды в двух вызовах означали
    # бы две транзакции и запись в журнал, пережившую откат операции.
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.save_site({"domain": "una.md", "locales": "ru,ro"}, "pt")
    assert res["success"] is True
    assert len(db.script_calls) == 1
    assert db.execute_query.call_count == 0


def test_failed_write_reports_the_oracle_message():
    db = _db(script_ok=False)
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.save_site({"domain": "una.md", "locales": "ru"}, "pt")
    assert res["success"] is False
    assert "ORA-00001" in res["message"]


def test_archive_site_sets_flag_and_never_deletes():
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        store.archive_site(1, "pt")
    joined = " ".join(db.captured).upper()
    assert "ISARHIV = 1" in joined and "DELETE" not in joined


def test_every_write_leaves_a_journal_entry_in_the_same_script():
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        store.save_site({"domain": "una.md", "locales": "ru"}, "pt")
    statements = db.script_calls[0]
    assert any("LOG_EVENT" in st["sql"].upper() for st in statements)


def test_existing_ext_ids_returns_a_set():
    rows = _ok(["EXT_ID"], [["a"], ["b"]], 2)
    with patch.object(store, "Biro26DB", return_value=_db([rows])):
        assert store.existing_ext_ids("SPEND", ["a", "b", "c"]) == {"a", "b"}


def test_existing_ext_ids_without_input_does_not_touch_the_database():
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        assert store.existing_ext_ids("SPEND", []) == set()
    db.execute_query.assert_not_called()


def test_existing_ext_ids_splits_long_lists():
    # В IN нельзя больше 1000 элементов, а выгрузка за месяц бывает длиннее.
    db = _db([_ok(["EXT_ID"], [], 0), _ok(["EXT_ID"], [], 0)])
    with patch.object(store, "Biro26DB", return_value=db):
        store.existing_ext_ids("SPEND", [f"k{i}" for i in range(1500)])
    assert len(db.captured) == 2


def test_existing_ext_ids_rejects_an_unknown_kind():
    with pytest.raises(ValueError):
        store.existing_ext_ids("PAYROLL", ["a"])


def test_import_commit_counts_loaded_and_skipped():
    seq = [
        _ok(["EXT_ID"], [["dup"]], 1),   # уже загруженные ext_id
        _ok(["COD"], [[7]], 1),          # номер будущей партии
    ]
    with patch.object(store, "Biro26DB", return_value=_db(seq)):
        res = store.import_commit(
            "SPEND", "ads.csv",
            [{"ext_id": "dup", "site": "una.md"}, {"ext_id": "new", "site": "una.md"}],
            "pt")
    assert res["success"] is True
    assert res["data"]["loaded"] == 1
    assert res["data"]["skipped"] == 1
    assert res["data"]["import_cod"] == 7


def test_import_commit_writes_batch_and_rows_in_one_transaction():
    seq = [_ok(["EXT_ID"], [], 0), _ok(["COD"], [[9]], 1)]
    db = _db(seq)
    with patch.object(store, "Biro26DB", return_value=db):
        store.import_commit("SPEND", "ads.csv",
                            [{"ext_id": "a"}, {"ext_id": "b"}], "pt")
    assert len(db.script_calls) == 1
    statements = db.script_calls[0]
    # партия + две строки + журнал
    assert len(statements) == 4
    assert "YSEO_IMPORT" in statements[0]["sql"].upper()


def test_import_commit_with_only_duplicates_writes_nothing_new():
    seq = [_ok(["EXT_ID"], [["dup"]], 1), _ok(["COD"], [[8]], 1)]
    with patch.object(store, "Biro26DB", return_value=_db(seq)):
        res = store.import_commit("SPEND", "ads.csv",
                                  [{"ext_id": "dup", "site": "una.md"}], "pt")
    assert res["data"]["loaded"] == 0 and res["data"]["skipped"] == 1


def test_manual_fact_does_not_depend_on_the_import_sequence():
    # Ручной ввод идёт той же командой, что и импорт. Если бы номер партии
    # брался через CURRVAL, в сессии без импорта был бы ORA-08002.
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        store.add_spend({"ext_id": "manual-1", "site": "una.md"}, "pt")
    joined = " ".join(db.captured).upper()
    assert "CURRVAL" not in joined


def test_plan_upsert_goes_through_the_package_not_raw_sql():
    # Лимит бюджета и журнал живут в PK_SEO_BUDGET: прямой INSERT обошёл бы их.
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        store.plan_upsert({"period": "2026-08", "article_cod1": 201,
                           "channel_cod1": 102, "site_cod": 1,
                           "plan_suma": 1000}, "pt")
    assert any("PK_SEO_BUDGET.PLAN_UPSERT" in sql.upper() for sql in db.captured)


def test_queries_use_bind_variables_only():
    # Конкатенация значений в SQL — путь к инъекции; выбираем только связывание.
    db = _db([_ok()])
    with patch.object(store, "Biro26DB", return_value=db):
        store.planfact(period="2026-08'; DROP TABLE YSEO_SITE--", site_cod=1)
    assert "DROP TABLE" not in " ".join(db.captured).upper()


# ── Task 7: контроллер ───────────────────────────────────────────────

from modules.seoforge.controller import SeoController


def test_business_error_becomes_409():
    msg = ("ORA-20101: RO: Cheltuiala depaseste bugetul planificat. / "
           "EN: Spend exceeds the planned budget.")
    assert SeoController.error_status(msg) == 409


def test_unique_constraint_becomes_409():
    assert SeoController.error_status("ORA-00001: unique constraint violated") == 409


def test_unknown_error_becomes_500():
    assert SeoController.error_status("ORA-03113: end-of-file on communication") == 500


def test_business_message_reaches_the_user_verbatim():
    msg = "ORA-20102: RO: Lipseste cursul valutar pentru EUR. / EN: Missing rate."
    with patch.object(SeoController, "_store") as st:
        st.save_fx.return_value = {"success": False, "data": None, "message": msg}
        payload, status = SeoController.save_fx(
            {"valuta": "EUR", "rate_date": "2026-08-01", "rate": 19.5})
    assert status == 409
    assert "Lipseste cursul valutar" in payload["message"]


def test_infrastructure_error_is_not_leaked_to_the_user():
    with patch.object(SeoController, "_store") as st:
        st.sites.return_value = None
        st.list_sites.return_value = {
            "success": False, "data": None,
            "message": "ORA-12541: TNS:no listener at host db-internal:1521"}
        payload, status = SeoController.sites()
    assert status == 500
    assert "db-internal" not in payload["message"]


def test_save_site_rejects_empty_domain_before_touching_the_database():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.save_site({"domain": "  "})
    assert status == 400
    assert payload["success"] is False
    st.save_site.assert_not_called()


def test_save_site_requires_locales():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.save_site({"domain": "una.md"})
    assert status == 400
    st.save_site.assert_not_called()


def test_save_campaign_rejects_reversed_dates():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.save_campaign(
            {"camp_code": "c1", "site_cod": 1, "date_start": "2026-09-01",
             "date_end": "2026-08-01", "promo_type_cod1": 1})
    assert status == 400
    st.save_campaign.assert_not_called()


def test_campaign_status_must_be_known():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.set_campaign_status(1, "MAYBE")
    assert status == 400
    st.set_campaign_status.assert_not_called()


def test_plan_save_rejects_a_bad_period():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.plan_save(
            {"period": "август", "article_cod1": 201, "plan_suma": 10})
    assert status == 400
    st.plan_upsert.assert_not_called()


_SPEND_HEADER = ("site;channel;article;campaign;spend_date;suma;valuta;"
                 "clicks;impressions;conversions;revenue;ext_id")


def test_import_preview_never_writes():
    text = _SPEND_HEADER + "\nuna.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;1;2;0;0;"
    with patch.object(SeoController, "_store") as st:
        st.existing_ext_ids.return_value = set()
        payload, status = SeoController.import_preview("SPEND", "ads.csv", text)
    assert status == 200
    assert payload["data"]["rows"][0]["site"] == "una.md"
    st.import_commit.assert_not_called()


def test_import_preview_marks_duplicates():
    text = _SPEND_HEADER + "\nuna.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;1;2;0;0;fixed-id"
    with patch.object(SeoController, "_store") as st:
        st.existing_ext_ids.return_value = {"fixed-id"}
        payload, status = SeoController.import_preview("SPEND", "ads.csv", text)
    assert payload["data"]["duplicates"] == ["fixed-id"]
    assert payload["data"]["rows"][0]["is_duplicate"] is True


def test_import_preview_returns_parse_errors_with_line_numbers():
    text = _SPEND_HEADER + "\nuna.md;GOOGLE_ADS;ADS;c;2026-08-25;мусор;MDL;1;2;0;0;"
    with patch.object(SeoController, "_store") as st:
        st.existing_ext_ids.return_value = set()
        payload, status = SeoController.import_preview("SPEND", "ads.csv", text)
    assert status == 200
    assert payload["data"]["errors"][0]["line"] == 2


def test_import_commit_refuses_a_file_with_only_errors():
    with patch.object(SeoController, "_store") as st:
        payload, status = SeoController.import_commit("SPEND", "bad.csv",
                                                      "site;suma\nx;1")
    assert status == 400
    st.import_commit.assert_not_called()


def test_import_commit_passes_only_valid_rows_to_the_store():
    text = (_SPEND_HEADER
            + "\nuna.md;GOOGLE_ADS;ADS;c;2026-08-25;10;MDL;1;2;0;0;"
            + "\nuna.md;GOOGLE_ADS;ADS;c;2026-08-26;мусор;MDL;1;2;0;0;")
    with patch.object(SeoController, "_store") as st:
        st.import_commit.return_value = {
            "success": True, "data": {"import_cod": 1, "loaded": 1, "skipped": 0},
            "message": ""}
        payload, status = SeoController.import_commit("SPEND", "ads.csv", text)
    assert status == 200
    passed_rows = st.import_commit.call_args[0][2]
    assert len(passed_rows) == 1
    assert payload["data"]["errors"][0]["line"] == 3


def test_unknown_import_kind_is_rejected():
    payload, status = SeoController.import_preview("PAYROLL", "x.csv", "a;b")
    assert status == 400


# ── Task 8: маршруты, интерфейс, манифест ────────────────────────────

import json


def test_module_manifest_is_valid_and_trilingual():
    path = os.path.join(ROOT, "modules", "seoforge", "module.json")
    with open(path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert set(manifest["title"]) >= {"ru", "ro", "en"}
    assert manifest["url"] == "/UNA.md/orasldev/seoforge"
    assert manifest["sql_prefix"] == "YSEO_"


def test_module_leaves_nothing_in_the_shared_app():
    # Ради этого и делалось ядро: модуль не должен присутствовать в общем
    # файле ни строкой, иначе каждый новый модуль — конфликт слияния.
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "seoforge" not in src.lower()
    assert "SeoController" not in src


def test_module_is_picked_up_by_the_core():
    from core.module_loader import module_keys
    assert "seoforge" in module_keys()
    assert os.path.isfile(os.path.join(MODULE_DIR, "__init__.py"))

    from modules.seoforge import blueprint
    assert blueprint.name == "seoforge"


def test_routes_are_declared_without_the_module_prefix():
    # Префикс ставит ядро. Если модуль пропишет его сам, он сможет
    # промахнуться мимо своей области.
    with open(os.path.join(MODULE_DIR, "routes.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "@blueprint.route" in src
    assert "/UNA.md/orasldev" not in src.replace(
        "Адреса здесь записаны БЕЗ префикса `/UNA.md/orasldev/seoforge`", "")


def test_every_seoforge_route_is_guarded_by_authentication():
    # Обработчик модуля — функция с @blueprint.route; каждая обязана либо
    # сама звать is_authenticated, либо пройти через общий _guard.
    import ast

    with open(os.path.join(MODULE_DIR, "routes.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    handlers = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and any(_is_route(dec) for dec in node.decorator_list)]
    assert len(handlers) >= 20, f"маршрутов найдено {len(handlers)}"

    for node in handlers:
        called = {n.func.attr for n in ast.walk(node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        called |= {n.func.id for n in ast.walk(node)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "is_authenticated" in called or "_guard" in called, node.name


def _is_route(decorator):
    import ast
    func = decorator.func if isinstance(decorator, ast.Call) else decorator
    return isinstance(func, ast.Attribute) and func.attr == "route"


def test_template_declares_every_panel():
    with open(os.path.join(MODULE_DIR, "templates", "seoforge.html"), encoding="utf-8") as fh:
        html = fh.read()
    for panel in ("portfolio", "sites", "campaigns", "budget", "facts",
                  "roi", "refs"):
        assert f'id="panel-{panel}"' in html, panel
        assert f'data-panel="{panel}"' in html, panel


def test_template_commit_button_waits_for_a_preview():
    # Загрузка без предпросмотра — прямой путь к мусору в базе.
    with open(os.path.join(MODULE_DIR, "templates", "seoforge.html"), encoding="utf-8") as fh:
        html = fh.read()
    assert "importCommitBtn" in html and "disabled" in html


# ── Task 9: документация и живой smoke ───────────────────────────────

def test_docs_registry_lists_every_document():
    # Формат реестра — как в docs/Planograms/docs.json: ключ = имя файла.
    docs_dir = os.path.join(ROOT, "docs", "SEOForge")
    with open(os.path.join(docs_dir, "docs.json"), encoding="utf-8") as fh:
        registry = json.load(fh)
    on_disk = {n for n in os.listdir(docs_dir) if n.endswith(".md")}
    assert on_disk == set(registry)
    for name, item in registry.items():
        assert item.get("slug") and item.get("title"), name


def test_csv_format_doc_matches_the_parser():
    from modules.seoforge.csv_format import METRICS_COLUMNS, SPEND_COLUMNS
    with open(os.path.join(ROOT, "docs", "SEOForge", "CSV_FORMAT.md"),
              encoding="utf-8") as fh:
        text = fh.read()
    for col in SPEND_COLUMNS + METRICS_COLUMNS:
        assert col in text, col


def test_data_model_doc_lists_every_table():
    with open(os.path.join(ROOT, "docs", "SEOForge", "DATA_MODEL.md"),
              encoding="utf-8") as fh:
        text = fh.read()
    for table_name in EXPECTED_TABLES:
        assert table_name in text, table_name


def test_smoke_script_covers_every_declared_invariant():
    with open(os.path.join(MODULE_DIR, "scripts", "seoforge_smoke.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    for check in ("check_plan_and_spend", "check_overrun_blocked",
                  "check_overrun_warned", "check_import_dedup",
                  "check_archive_not_delete", "check_views"):
        assert f"def {check}" in src, check


def test_smoke_script_requires_explicit_confirmation():
    # Скрипт пишет в базу: случайный запуск не должен ничего создавать.
    with open(os.path.join(MODULE_DIR, "scripts", "seoforge_smoke.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    assert "--yes" in src


def test_compound_trigger_has_no_return_statement():
    # PLS-00678: RETURN внутри compound trigger запрещён. Ловится только
    # компиляцией в живой базе, поэтому правило закреплено тестом.
    ddl = _sql("113_yseo_tables.sql").upper()
    block = ddl.split("CREATE OR REPLACE TRIGGER TRG_YSEO_SPEND_BUDGET")[1]
    assert not re.search(r"\bRETURN\s*;", block)


def test_una_interface_doc_records_the_verified_facts():
    # Документ заменяет таблицу предположений ТЗ: если он потеряет
    # проверенные имена объектов, кусок C снова поедет на догадках.
    with open(os.path.join(ROOT, "docs", "SEOForge", "UNA_INTERFACE.md"),
              encoding="utf-8") as fh:
        text = fh.read()
    for fact in ("ID_TMDB_DOCS.NEXTVAL", "TRIG_BFINS_TMDB_DOCS",
                 "TMDB_DOCS_TRLOG", "TRG_DOCS_COLOR", "PARAM_USERID",
                 "setDoc_GFC", "setDoc_Correct", "YSEO_XREF"):
        assert fact in text, fact


def test_erp_config_installer_reserves_a_documented_range():
    # Диапазон DB ID = SYSFID: если он разъедется с документацией,
    # журнал перестанет видеть свои же документы.
    from modules.seoforge.scripts.seoforge_erp_config import DBID_FROM, DBID_TO, DOCUMENTS
    assert (DBID_FROM, DBID_TO) == (60000, 60099)
    for _section, _name, dbid, _src in DOCUMENTS:
        assert DBID_FROM <= dbid <= DBID_TO, dbid

    with open(os.path.join(ROOT, "docs", "SEOForge", "UNA_INTERFACE.md"),
              encoding="utf-8") as fh:
        text = fh.read()
    assert f"{DBID_FROM}..{DBID_TO}" in text
    for _section, name, _dbid, _src in DOCUMENTS:
        assert name in text, name


def test_erp_config_documents_are_copies_of_real_documents():
    # Набор свойств документа руками не собрать: копируем работающий.
    from modules.seoforge.scripts.seoforge_erp_config import DOCUMENTS
    for _section, _name, _dbid, src in DOCUMENTS:
        assert src.startswith("2:"), src

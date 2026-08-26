"""Autopark module -- unit tests (no live Oracle, no wallet).

DDL is verified by parsing sql/120_flt_tables.sql: that catches the errors
that cost the most on this project -- a forgotten index on a foreign key,
a NOCACHE sequence deadlocking under parallel inserts, a missing '/'
gluing a trigger to the surrounding DDL. The Python layer (rules.py) is
pure -- no DB import at all -- and is tested with plain dict/list fixtures.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_DIR = os.path.join(ROOT, "modules", "autopark")
SQL_DIR = os.path.join(MODULE_DIR, "sql")


def _sql(name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
        return fh.read()


# Tables with a surrogate NUMBER(12) ID -- each must carry its own
# SEQ_<table>/TRG_<table>_BI pair (see modules/sda/sql/117_sda_tables.sql
# for the pattern this copies).
ID_TABLES = [
    "FLT_STATIONS", "FLT_STATION_TANKS", "FLT_LOAD_POINTS", "FLT_END_POINTS",
    "FLT_TRUCKS", "FLT_DRIVERS", "FLT_DISTANCES", "FLT_TRIPS",
    "FLT_TRIP_STOPS", "FLT_TRIP_STOP_ITEMS", "FLT_DELIVERIES",
    "FLT_STATION_STOCK", "FLT_EVENT_LOG",
]

# Reference/natural-key tables and the settings singleton -- no surrogate
# ID, no sequence, no trigger.
NO_ID_TABLES = [
    "FLT_PRODUCTS", "FLT_TRUCK_PRODUCTS", "FLT_REF_TRIP_TYPES",
    "FLT_REF_TRIP_STATUS", "FLT_SETTINGS",
]

ALL_TABLES = ID_TABLES + NO_ID_TABLES


# -- Task 1: schema (120_flt_tables.sql) --------------------------------

def test_ddl_declares_every_table():
    ddl = _sql("120_flt_tables.sql").upper()
    for table in ALL_TABLES:
        assert f"CREATE TABLE {table}" in ddl, table


def test_ddl_has_no_semicolons_in_comments():
    # Splitters (deploy_oracle_objects.py's own, and this module's copy of
    # it) cut statements on ';' without understanding SQL comments -- a
    # ';' inside a '--' comment breaks the split (project-wide rule).
    for line in _sql("120_flt_tables.sql").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            assert ";" not in stripped, stripped


def test_every_id_table_has_a_sequence_and_trigger():
    ddl = _sql("120_flt_tables.sql").upper()
    for table in ID_TABLES:
        assert f"CREATE SEQUENCE SEQ_{table}" in ddl, table
        assert f"CREATE OR REPLACE TRIGGER TRG_{table}_BI" in ddl, table


def test_no_id_tables_carry_no_sequence_or_trigger():
    # Natural-key reference tables and the FLT_SETTINGS singleton don't
    # need a surrogate key -- adding one would just be KV-style bloat.
    ddl = _sql("120_flt_tables.sql").upper()
    for table in NO_ID_TABLES:
        assert f"CREATE SEQUENCE SEQ_{table}" not in ddl, table
        assert f"CREATE OR REPLACE TRIGGER TRG_{table}_BI" not in ddl, table


def test_every_sequence_uses_cache_20():
    # A NOCACHE sequence deadlocked (ORA-12860) under parallel
    # INSERT...SELECT for the PECO module on this same ADB (26.08.2026).
    ddl = _sql("120_flt_tables.sql").upper()
    for seq in re.findall(r"CREATE SEQUENCE (SEQ_[A-Z0-9_]+)", ddl):
        # Grab the single line the CREATE SEQUENCE statement is written on.
        line = next(l for l in ddl.splitlines() if f"CREATE SEQUENCE {seq}" in l)
        assert "CACHE 20" in line, line
        assert "NOCACHE" not in line, line


def test_every_trigger_is_fenced_by_slash_before_and_after():
    # Missing the leading '/' glues the trigger to the preceding
    # CREATE TABLE/INDEX/SEQUENCE into a single PL/SQL block that
    # cursor.execute() rejects -- this broke the SDA module's installer
    # on 25.08.2026. Checked by requiring a lone '/' line immediately
    # before every CREATE OR REPLACE TRIGGER, and one right after its
    # closing END;.
    text = _sql("120_flt_tables.sql")
    lines = text.splitlines()
    trigger_line_idxs = [i for i, l in enumerate(lines)
                         if l.strip().upper().startswith("CREATE OR REPLACE TRIGGER")]
    assert len(trigger_line_idxs) == len(ID_TABLES)
    for idx in trigger_line_idxs:
        assert lines[idx - 1].strip() == "/", \
            f"no lone '/' before trigger at line {idx + 1}: {lines[idx]!r}"
        # The trigger body is a single line ending in END;  -- '/' follows.
        end_idx = idx + 1
        assert lines[end_idx].strip().upper().startswith("BEGIN") or \
            "END;" in lines[end_idx].upper()
        assert lines[end_idx + 1].strip() == "/", \
            f"no lone '/' after trigger at line {end_idx + 2}"


def test_every_foreign_key_column_has_an_index():
    ddl = _sql("120_flt_tables.sql").upper()

    indexed_by_table = {}
    for table, cols in re.findall(
        r"CREATE (?:UNIQUE )?INDEX [A-Z0-9_]+ ON ([A-Z0-9_]+) \(([^)]+)\)", ddl
    ):
        indexed_by_table.setdefault(table, set()).add(cols.split(",")[0].strip())

    for table, body in re.findall(
        r"CREATE TABLE ([A-Z0-9_]+) \((.*?)\n\);", ddl, re.DOTALL
    ):
        fk_cols = re.findall(r"FOREIGN KEY \(([A-Z0-9_]+)\)", body)
        for col in fk_cols:
            assert col in indexed_by_table.get(table, set()), \
                f"{table}.{col} is a FK but has no index on {table} starting with it"


def test_distances_from_and_to_kind_are_constrained():
    ddl = _sql("120_flt_tables.sql").upper()
    assert "FROM_KIND IN ('LOAD','STATION','END')" in ddl
    assert "TO_KIND IN ('LOAD','STATION','END')" in ddl


def test_distances_matrix_is_unique_per_leg():
    ddl = _sql("120_flt_tables.sql").upper()
    assert "UNIQUE (FROM_KIND, FROM_ID, TO_KIND, TO_ID)" in ddl


def test_settings_is_a_singleton_with_named_columns_not_a_kv_blob():
    # CLAUDE.md forbids APP_RUNTIME_KV-style generic key-value tables.
    ddl = _sql("120_flt_tables.sql").upper()
    settings = ddl[ddl.index("CREATE TABLE FLT_SETTINGS"):]
    settings = settings[:settings.index(";")]
    assert "CHECK (ID = 1)" in settings
    for col in ("RATE_PER_KM", "TRIP_BONUS", "SAFETY_DAYS",
                "KM_DEVIATION_LIMIT", "FUEL_DEVIATION_PCT"):
        assert col in settings, col


def test_trip_types_reference_carries_pays_bonus_flag():
    ddl = _sql("120_flt_tables.sql").upper()
    assert "CREATE TABLE FLT_REF_TRIP_TYPES" in ddl
    assert "PAYS_BONUS" in ddl


def test_event_log_has_no_foreign_keys():
    # Append-only journal -- never a shared/generic container, and not
    # coupled to other tables by FK (CLAUDE.md event-log convention).
    ddl = _sql("120_flt_tables.sql").upper()
    log = ddl[ddl.index("CREATE TABLE FLT_EVENT_LOG"):]
    log = log[:log.index(";")]
    assert "FOREIGN KEY" not in log


def test_deploy_script_installs_all_flt_files_in_order():
    from modules.autopark.scripts.autopark_deploy import FILES
    assert FILES == (
        "120_flt_tables.sql", "121_flt_views.sql", "122_flt_seed.sql",
        "123_flt_prices.sql", "124_flt_gps.sql",
    )


def test_module_installer_only_imports_functions_that_exist_on_the_shared_script():
    import deploy_oracle_objects as shared
    for name in ("_sql_blocks", "_is_plsql_block", "_split_ddl_dml",
                 "_is_comment_only"):
        assert hasattr(shared, name), name


def test_ddl_splits_into_one_isolated_block_per_trigger():
    import deploy_oracle_objects as shared

    text = _sql("120_flt_tables.sql")
    blocks = shared._sql_blocks(text)

    plsql_blocks = 0
    for block in blocks:
        if shared._is_comment_only(block):
            continue
        if shared._is_plsql_block(block):
            plsql_blocks += 1
            creates = re.findall(r"(?im)^\s*CREATE\s+(\S+)", block)
            assert creates == ["OR"], (
                "PL/SQL block is not isolated to its own trigger -- it "
                f"also contains: {block[:200]!r}")
            continue
        for stmt in shared._split_ddl_dml(block):
            stmt = stmt.strip()
            if not stmt or shared._is_comment_only(stmt):
                continue
            creates = len(re.findall(r"(?mi)^\s*(--.*\n)*CREATE\s", "\n" + stmt))
            assert creates <= 1, (
                "non-PL/SQL statement still glues together more than one "
                f"CREATE: {stmt[:120]!r}")

    assert plsql_blocks == len(ID_TABLES)


# -- Task 2: views (121_flt_views.sql) ----------------------------------

def test_views_file_declares_all_three_views():
    ddl = _sql("121_flt_views.sql").upper()
    for view in ("V_FLT_STOCK_DAYS", "V_FLT_TRIP_PAY", "V_FLT_TRIP_CONTROL"):
        assert f"CREATE OR REPLACE VIEW {view}" in ddl, view


def test_stock_days_view_guards_division_by_zero():
    ddl = _sql("121_flt_views.sql").upper()
    view = ddl[ddl.index("CREATE OR REPLACE VIEW V_FLT_STOCK_DAYS"):]
    assert "NVL(L.AVG_DAILY_SALES_L, 0) > 0" in view


def test_trip_pay_view_excludes_bonus_for_draft_and_import():
    ddl = _sql("121_flt_views.sql").upper()
    view = ddl[ddl.index("CREATE OR REPLACE VIEW V_FLT_TRIP_PAY"):]
    assert "TT.PAYS_BONUS = 1" in view
    assert "T.STATUS_CODE <> 'DRAFT'" in view


def test_trip_control_view_computes_km_deviation_and_norm_fuel():
    ddl = _sql("121_flt_views.sql").upper()
    view = ddl[ddl.index("CREATE OR REPLACE VIEW V_FLT_TRIP_CONTROL"):]
    assert "(T.FACT_KM - T.NORM_KM)" in view
    assert "T.NORM_KM * TR.NORM_L_PER_100KM / 100" in view


def test_trips_table_has_fact_fuel_l_column():
    ddl = _sql("120_flt_tables.sql").upper()
    trips = ddl[ddl.index("CREATE TABLE FLT_TRIPS"):]
    trips = trips[:trips.index(");")]
    assert "FACT_FUEL_L" in trips


def test_trip_control_view_reports_fact_fuel_and_deviation():
    ddl = _sql("121_flt_views.sql").upper()
    view = ddl[ddl.index("CREATE OR REPLACE VIEW V_FLT_TRIP_CONTROL"):]
    assert "T.FACT_FUEL_L" in view
    assert "FUEL_DEVIATION" in view
    assert "OVER_FUEL_LIMIT" in view
    assert "CFG.FUEL_DEVIATION_PCT" in view


def test_trip_control_view_guards_fuel_division_by_zero():
    # Тот же урок, что в V_FLT_STOCK_DAYS: не делить на NORM_FUEL_L=0
    # напрямую -- проверка на 0 должна стоять раньше деления в CASE.
    ddl = _sql("121_flt_views.sql").upper()
    view = ddl[ddl.index("CREATE OR REPLACE VIEW V_FLT_TRIP_CONTROL"):]
    assert "NVL(T.NORM_KM * TR.NORM_L_PER_100KM / 100, 0) = 0" in view


# -- Task 3: seed (122_flt_seed.sql) ------------------------------------

def test_seed_is_idempotent_merge_statements_only():
    seed = _sql("122_flt_seed.sql").upper()
    # No plain INSERT INTO anywhere -- every seed write goes through MERGE
    # so re-running the installer never duplicates reference rows.
    assert "INSERT INTO" not in seed
    assert seed.count("MERGE INTO") >= 6


def test_seed_covers_products_types_status_settings_points():
    seed = _sql("122_flt_seed.sql").upper()
    for token in ("'A92'", "'A95'", "'A98'", "'DIESEL'",
                  "'DOMESTIC'", "'IMPORT'",
                  "'DRAFT'", "'APPROVED'", "'DONE'",
                  "'KIS'", "'MSPD'", "'CONST'", "'BAZA'"):
        assert token in seed, token


def test_seed_marks_constanta_as_foreign():
    seed = _sql("122_flt_seed.sql")
    line = next(l for l in seed.splitlines() if "'CONST'" in l)
    assert re.search(r",\s*1\s*FROM DUAL", line), line


# -- Task 4: pure rules (rules.py) --------------------------------------

from modules.autopark import rules  # noqa: E402


def test_norm_route_km_sums_the_legs():
    assert rules.norm_route_km([10, 20.5, 5]) == 35.5


def test_norm_route_km_raises_on_a_missing_leg():
    try:
        rules.norm_route_km([10, None, 5])
    except ValueError as exc:
        assert "матрице" in str(exc)
    else:
        raise AssertionError("expected ValueError for a missing distance")


def test_route_legs_builds_the_full_chain_in_order():
    matrix = {
        ("LOAD", "KIS", "STATION", "orgeev"): 100,
        ("STATION", "orgeev", "STATION", "beltsy"): 40,
        ("STATION", "beltsy", "END", "BAZA"): 150,
    }
    legs = rules.route_legs("KIS", ["orgeev", "beltsy"], "BAZA",
                            lambda fk, fi, tk, ti: matrix.get((fk, fi, tk, ti)))
    assert [l["km"] for l in legs] == [100, 40, 150]
    assert legs[0]["from_kind"] == "LOAD" and legs[0]["to_kind"] == "STATION"
    assert legs[-1]["to_kind"] == "END"


def test_trip_pay_domestic_gets_km_and_bonus():
    assert rules.trip_pay(100, "DOMESTIC", 2.75, 600) == 100 * 2.75 + 600


def test_trip_pay_import_gets_only_km():
    assert rules.trip_pay(100, "IMPORT", 2.75, 600) == 100 * 2.75


def test_payroll_matches_the_tor_formula():
    trips = [
        {"status": "APPROVED", "type": "DOMESTIC", "norm_km": 100},
        {"status": "DONE", "type": "DOMESTIC", "norm_km": 50},
        {"status": "APPROVED", "type": "IMPORT", "norm_km": 300},
    ]
    result = rules.payroll(trips, rate=2.75, bonus=600)
    assert result["domestic_count"] == 2
    assert result["import_count"] == 1
    assert result["total_norm_km"] == 450
    assert result["km_pay"] == 450 * 2.75
    assert result["trip_pay"] == 2 * 600
    assert result["total"] == 450 * 2.75 + 2 * 600


def test_payroll_excludes_draft_trips():
    trips = [
        {"status": "DRAFT", "type": "DOMESTIC", "norm_km": 1000},
        {"status": "APPROVED", "type": "DOMESTIC", "norm_km": 100},
    ]
    result = rules.payroll(trips, rate=2.75, bonus=600)
    assert result["domestic_count"] == 1
    assert result["total_norm_km"] == 100


def test_fuel_norm_l():
    assert rules.fuel_norm_l(200, 30) == 60


def test_fuel_deviation_flags_over_limit():
    deviation, over = rules.fuel_deviation(fact_l=70, norm_l=60, limit_pct=5)
    assert deviation == 10
    assert over is True


def test_fuel_deviation_within_limit_is_not_flagged():
    deviation, over = rules.fuel_deviation(fact_l=61, norm_l=60, limit_pct=5)
    assert over is False


def test_fuel_deviation_guards_zero_norm():
    deviation, over = rules.fuel_deviation(fact_l=5, norm_l=0, limit_pct=5)
    assert deviation == 5
    assert over is True
    deviation, over = rules.fuel_deviation(fact_l=0, norm_l=0, limit_pct=5)
    assert over is False


def test_km_deviation_flags_over_limit():
    deviation, over = rules.km_deviation(fact_km=220, norm_km=200, limit_km=15)
    assert deviation == 20
    assert over is True


def test_stock_days_is_none_for_zero_sales():
    assert rules.stock_days(current_l=500, avg_daily_sales_l=0) is None
    assert rules.stock_days(current_l=500, avg_daily_sales_l=None) is None


def test_stock_days_divides_current_by_average():
    assert rules.stock_days(current_l=600, avg_daily_sales_l=100) == 6


def test_min_stock_l_is_average_times_safety_days():
    assert rules.min_stock_l(avg_daily_sales_l=100, safety_days=6) == 600


def test_need_volume_does_not_exceed_free_tank_space():
    # Huge shortfall (raw need = 600 + 9000 - 500 - 0 = 9100), but the
    # tank only has 500 L of free room left -- the order must be capped
    # there, not at the raw shortfall.
    need = rules.need_volume_l(
        current_l=500, min_stock_l=600, forecast_sales_l=9000,
        in_transit_l=0, tank_capacity_l=1000)
    assert need == 500  # capped at free space, not at the raw shortfall


def test_need_volume_accounts_for_stock_already_in_transit():
    need = rules.need_volume_l(
        current_l=200, min_stock_l=600, forecast_sales_l=100,
        in_transit_l=500, tank_capacity_l=10000)
    # raw need = 600 + 100 - 200 - 500 = 0
    assert need == 0


def test_classify_trip_domestic_when_nothing_is_foreign():
    assert rules.classify_trip(False, False) == "DOMESTIC"


def test_classify_trip_import_when_load_point_is_foreign():
    # Chisinau -> Constanta -> Chisinau is IMPORT (ToR pt. 10), driven by
    # the loading point being abroad, not by any station's own attribute.
    assert rules.classify_trip(True, False) == "IMPORT"


def test_classify_trip_import_when_end_point_is_foreign():
    assert rules.classify_trip(False, True) == "IMPORT"


def test_plan_trips_never_exceeds_truck_capacity_or_sections():
    needs = [
        {"station_id": "s1", "product_code": "A95", "need_l": 3000, "days_left": 1},
        {"station_id": "s2", "product_code": "DIESEL", "need_l": 4000, "days_left": 2},
        {"station_id": "s3", "product_code": "A92", "need_l": 5000, "days_left": 3},
    ]
    trucks = [{"id": "T1", "capacity_l": 6000, "sections_cnt": 2}]
    matrix = {
        ("LOAD", "KIS", "STATION", "s1"): 50,
        ("LOAD", "KIS", "STATION", "s2"): 80,
        ("LOAD", "KIS", "STATION", "s3"): 120,
        ("STATION", "s1", "STATION", "s2"): 30,
        ("STATION", "s2", "STATION", "s1"): 30,
    }
    plan = rules.plan_trips(needs, trucks, lambda fk, fi, tk, ti: matrix.get((fk, fi, tk, ti)), "KIS")
    assert len(plan) == 1
    trip = plan[0]
    total_volume = sum(item["volume"] for stop in trip["stops"] for item in stop["items"])
    assert total_volume <= 6000
    n_items = sum(len(stop["items"]) for stop in trip["stops"])
    assert n_items <= 2  # sections_cnt


def test_plan_trips_nearest_neighbor_order_on_three_stations():
    # Load point at KIS; s2 is closest, then s3 is closest to s2, s1 is
    # farthest of all -- nearest-neighbor should visit s2, s3, s1 in
    # that order rather than the input order (s1, s2, s3).
    needs = [
        {"station_id": "s1", "product_code": "A95", "need_l": 100, "days_left": 1},
        {"station_id": "s2", "product_code": "A95", "need_l": 100, "days_left": 1},
        {"station_id": "s3", "product_code": "A95", "need_l": 100, "days_left": 1},
    ]
    trucks = [{"id": "T1", "capacity_l": 10000, "sections_cnt": 3}]
    matrix = {
        ("LOAD", "KIS", "STATION", "s1"): 500,
        ("LOAD", "KIS", "STATION", "s2"): 10,
        ("LOAD", "KIS", "STATION", "s3"): 200,
        ("STATION", "s2", "STATION", "s1"): 400,
        ("STATION", "s2", "STATION", "s3"): 20,
        ("STATION", "s3", "STATION", "s1"): 50,
        ("STATION", "s1", "STATION", "s3"): 50,
        ("STATION", "s1", "STATION", "s2"): 400,
        ("STATION", "s3", "STATION", "s2"): 20,
    }
    plan = rules.plan_trips(needs, trucks, lambda fk, fi, tk, ti: matrix.get((fk, fi, tk, ti)), "KIS")
    order = [stop["station_id"] for stop in plan[0]["stops"]]
    assert order == ["s2", "s3", "s1"]


# -- Task 5: core connects the module, and the shared code stays clean --

def test_blueprint_name_matches_module_key():
    from modules.autopark import blueprint
    assert blueprint.name == "autopark"


def test_core_module_loader_connects_autopark():
    from flask import Flask

    from core.module_loader import load_module

    app = Flask(__name__)
    app.secret_key = "test"
    loaded = load_module(app, "autopark")
    assert loaded, (
        "load_module(app, 'autopark') returned a falsy value -- the "
        "module failed to load")
    assert any(rule.endpoint.startswith("autopark.")
               for rule in app.url_map.iter_rules())


# Trigram-safe leak signatures: "autopark"/"FLT_" as bare substrings would
# false-positive on unrelated words, so match specific, unambiguous tokens.
AUTOPARK_LEAK_SIGNATURES = ("modules.autopark", "modules/autopark",
                            "flt_products", "flt_trips", "orasldev/autopark")


def _leak_signatures_found(src: str) -> list:
    lowered = src.lower()
    return [sig for sig in AUTOPARK_LEAK_SIGNATURES if sig in lowered]


def test_module_leaves_nothing_in_the_shared_app():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert not _leak_signatures_found(src)


def test_shared_deploy_script_is_untouched_by_the_module():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert not _leak_signatures_found(src)


# -- Task 2: store.py, controller.py, routes.py (no live Oracle) --------

from unittest.mock import MagicMock, patch  # noqa: E402


def _db_returning(*results):
    """Мок DatabaseModel: каждый вызов execute_query отдаёт свой результат."""
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.execute_query = MagicMock(side_effect=list(results))
    return db


def _ok(columns, data, rowcount=None):
    return {"success": True, "columns": columns, "data": data,
            "rowcount": rowcount if rowcount is not None else len(data),
            "message": ""}


def _currval_row(value):
    return _ok(["ID"], [[value]])


# -- store: atomicity, rowcount guards, NO_PARALLEL regression ----------

def test_create_trip_makes_exactly_one_commit():
    from modules.autopark.store import AutoparkStore
    db = _db_returning(
        _ok([], [], rowcount=1),   # INSERT FLT_TRIPS
        _currval_row(501),         # SEQ_FLT_TRIPS.CURRVAL
        _ok([], [], rowcount=1),   # INSERT FLT_TRIP_STOPS
        _currval_row(601),         # SEQ_FLT_TRIP_STOPS.CURRVAL
        _ok([], [], rowcount=1),   # INSERT FLT_TRIP_STOP_ITEMS
        _ok([], [], rowcount=1),  # UPDATE FLT_DELIVERIES (delivery 77)
    )
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.create_trip(
            {"trip_date": "2026-08-01", "truck_id": 1, "driver_id": 2,
             "type_code": "DOMESTIC", "load_point_id": 10,
             "end_point_id": 20, "norm_km": 123.4, "delivery_ids": [77]},
            [{"station_id": 30,
              "items": [{"product_code": "A95", "volume_l": 500}]}])
    assert res["success"] is True
    assert res["data"]["trip_id"] == 501
    assert db.connection.commit.call_count == 1


def test_create_trip_rolls_back_conceptually_when_a_delivery_vanishes():
    # Последний шаг (привязка накладной) не находит строку -- ошибка, и
    # commit НЕ должен быть вызван: транзакция ещё не подтверждена.
    from modules.autopark.store import AutoparkStore
    db = _db_returning(
        _ok([], [], rowcount=1),
        _currval_row(501),
        _ok([], [], rowcount=1),
        _currval_row(601),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=0),  # UPDATE FLT_DELIVERIES -- строка исчезла
    )
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.create_trip(
            {"trip_date": "2026-08-01", "truck_id": 1, "driver_id": 2,
             "type_code": "DOMESTIC", "load_point_id": 10,
             "end_point_id": 20, "norm_km": 100, "delivery_ids": [999]},
            [{"station_id": 30,
              "items": [{"product_code": "A95", "volume_l": 500}]}])
    assert res["success"] is False
    assert db.connection.commit.call_count == 0


def test_approve_trip_zero_rowcount_is_an_error():
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.approve_trip(999, "logist")
    assert res["success"] is False
    assert db.connection.commit.call_count == 0


def test_set_trip_fact_zero_rowcount_is_an_error():
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.set_trip_fact(999, 100, 60)
    assert res["success"] is False


def test_set_trip_fact_writes_fact_fuel_l_param():
    # Регресс задачи 3: FACT_FUEL_L должен уйти в UPDATE, а не потеряться
    # на пути от controller к store.
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok([], [], rowcount=1))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.set_trip_fact(501, 100, 60, fact_fuel_l=42.5)
    assert res["success"] is True
    assert res["data"]["fact_fuel_l"] == 42.5
    call_args = db.execute_query.call_args
    sql, params = call_args[0][0], call_args[0][1]
    assert "FACT_FUEL_L" in sql.upper()
    assert params["fact_fuel_l"] == 42.5


def test_set_trip_fact_fuel_defaults_to_none_when_not_supplied():
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok([], [], rowcount=1))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.set_trip_fact(501, 100, 60)
    assert res["success"] is True
    assert res["data"]["fact_fuel_l"] is None


def test_controller_trip_set_fact_passes_through_fact_fuel_l():
    from modules.autopark.controller import AutoparkController
    with patch("modules.autopark.controller.AutoparkStore.set_trip_fact",
               return_value={"success": True, "data": {}, "message": ""}) as mocked:
        res = AutoparkController.trip_set_fact(
            {"trip_id": 501, "fact_km": 120, "fact_minutes": 90,
             "fact_fuel_l": 33.3})
    assert res["success"] is True
    mocked.assert_called_once_with(501, 120.0, 90, 33.3)


def test_controller_trip_set_fact_rejects_negative_fuel():
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.trip_set_fact(
        {"trip_id": 501, "fact_km": 120, "fact_minutes": 90,
         "fact_fuel_l": -5})
    assert res["success"] is False


def test_truck_summary_query_avoids_double_counting_fuel_via_subqueries():
    # Урок этой задачи: суммировать FACT_FUEL_L/NORM_FUEL_L на уровне
    # FLT_TRIPS ПОСЛЕ join'а с FLT_TRIP_STOP_ITEMS размножило бы расход на
    # число остановок/продуктов рейса. Запрос обязан агрегировать расход
    # рейса и объём по остановкам в раздельных подзапросах.
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok(
        ["TRUCK_ID", "PLATE", "TRIP_CNT", "TOTAL_VOLUME_L", "NORM_FUEL_L",
         "FACT_FUEL_L"],
        [[1, "AB123", 2, 40000.0, 300.0, 305.0]]))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        res = AutoparkStore.truck_summary("2026-08-01", "2026-08-31")
    assert res["success"] is True
    sql = db.execute_query.call_args[0][0].upper()
    assert sql.count("LEFT JOIN (") == 2
    assert "FLT_TRIP_STOP_ITEMS" in sql
    assert res["data"][0]["fact_fuel_l"] == 305.0


def test_log_event_swallows_sql_failure_and_never_raises():
    from modules.autopark.store import AutoparkStore
    db = MagicMock()
    db.__enter__ = MagicMock(return_value=db)
    db.__exit__ = MagicMock(return_value=False)
    db.execute_query = MagicMock(side_effect=RuntimeError("boom"))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        AutoparkStore.log_event("X", "REF", 1, "details", "tester")
    # Никакого исключения наружу и никакого commit при ошибке.
    assert db.connection.commit.call_count == 0


def test_trip_pay_report_filters_draft_at_the_store_layer():
    # ТЗ п.6: DRAFT-рейс не основание для начисления. Это правило должно
    # жить в store (единый источник правды для любого вызывающего кода),
    # а не полагаться на то, что controller не забудет отфильтровать.
    from modules.autopark.store import AutoparkStore
    db = _db_returning(_ok(["TRIP_ID"], []))
    with patch("modules.autopark.store.DatabaseModel", return_value=db):
        AutoparkStore.trip_pay_report("2026-01-01", "2026-01-31")
    sql = db.execute_query.call_args[0][0]
    assert "STATUS_CODE <> 'DRAFT'" in sql.upper() or \
           "STATUS_CODE <> 'DRAFT'" in sql


def test_no_insert_select_nextval_without_no_parallel_hint():
    # Регресс на урок PECO (ORA-12860, 26.08.2026): любой INSERT...SELECT
    # с явным NEXTVAL в тексте вызывающего кода обязан нести хинт
    # /*+ NO_PARALLEL */. Сегодня в store.py такого паттерна нет (каждый
    # INSERT — одна строка, ID назначает BI-триггер таблицы), поэтому тест
    # проходит "вхолостую", но ловит регресс, если кто-то добавит батч-
    # вставку с NEXTVAL и забудет про хинт.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read().upper()
    for match in re.finditer(r"INSERT INTO[\s\S]{0,400}?SELECT[\s\S]{0,400}?"
                             r"(?:NEXTVAL|;|$)", src):
        stmt = match.group(0)
        if "NEXTVAL" in stmt:
            assert "NO_PARALLEL" in stmt, stmt[:200]


# -- controller: validation, matrix-gap naming, classification warning --

def test_distance_set_rejects_a_non_numeric_km():
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.distance_set({
        "from_kind": "load", "from_id": 1, "to_kind": "station", "to_id": 2,
        "km": "abc"})
    assert res["success"] is False
    assert "числом" in res["message"]


def test_distance_set_rejects_an_unknown_kind():
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.distance_set({
        "from_kind": "GARAGE", "from_id": 1, "to_kind": "STATION",
        "to_id": 2, "km": 10})
    assert res["success"] is False
    assert "from_kind" in res["message"]


def test_require_date_converts_string_to_date_object():
    # Регресс сквозной проверки задачи 3: голая строка 'YYYY-MM-DD',
    # отправленная в BETWEEN на живом Oracle без TO_DATE, падает с
    # ORA-01861 (NLS_DATE_FORMAT этой ADB не 'YYYY-MM-DD'). Парсинг в
    # date() должен случиться в контроллере ДО передачи в store.
    from datetime import date as date_cls
    from modules.autopark.controller import _require_date
    result = _require_date("2026-08-20", "date_from")
    assert result == date_cls(2026, 8, 20)
    assert isinstance(result, date_cls)


def test_require_date_rejects_bad_format():
    from modules.autopark.controller import _require_date, AutoparkValidationError
    try:
        _require_date("20/08/2026", "date_from")
        assert False, "должно было поднять AutoparkValidationError"
    except AutoparkValidationError:
        pass


def test_delivery_list_passes_date_objects_to_store_not_raw_strings():
    from datetime import date as date_cls
    from modules.autopark.controller import AutoparkController
    with patch("modules.autopark.controller.AutoparkStore.list_deliveries",
               return_value={"success": True, "data": [], "message": ""}) as mocked:
        res = AutoparkController.delivery_list(
            {"date_from": "2026-08-01", "date_to": "2026-08-31"})
    assert res["success"] is True
    args = mocked.call_args[0]
    assert args[0] == date_cls(2026, 8, 1)
    assert args[1] == date_cls(2026, 8, 31)


def test_trip_autoform_parses_and_rejects_bad_dates():
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.trip_autoform("not-a-date", "2026-08-31")
    assert res["success"] is False


def test_supply_plan_in_transit_lookup_uses_date_objects_not_strings():
    # Раньше supply_plan подставлял литералы "0001-01-01"/"9999-12-31"
    # прямо строками -- тот же ORA-01861 на BETWEEN, просто маскировался
    # тем, что ошибка in_transit тихо игнорируется (см. controller.py).
    from datetime import date as date_cls
    from modules.autopark.controller import AutoparkController
    settings_ok = {"success": True, "data": {"safety_days": 6}, "message": ""}
    stock_ok = {"success": True, "data": [], "message": ""}
    stations_ok = {"success": True, "data": [], "message": ""}
    with patch("modules.autopark.controller.AutoparkStore.get_settings",
               return_value=settings_ok), \
         patch("modules.autopark.controller.AutoparkStore.stock_days_report",
               return_value=stock_ok), \
         patch("modules.autopark.controller.AutoparkStore.list_stations",
               return_value=stations_ok), \
         patch("modules.autopark.controller.AutoparkStore.list_deliveries",
               return_value={"success": True, "data": [], "message": ""}) as mocked:
        AutoparkController.supply_plan()
    args = mocked.call_args[0]
    assert isinstance(args[0], date_cls)
    assert isinstance(args[1], date_cls)


def test_truck_upsert_rejects_zero_capacity():
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.truck_upsert({
        "plate": "ABC123", "capacity_l": 0, "sections_cnt": 2,
        "norm_l_per_100km": 30})
    assert res["success"] is False
    assert "вместимость" in res["message"].lower()


def test_trip_create_manual_names_the_missing_leg():
    from modules.autopark.controller import AutoparkController
    payload = {
        "trip_date": "2026-08-01", "truck_id": 1, "driver_id": 2,
        "load_point_id": 10, "end_point_id": 20,
        "stations": [{"station_id": 30,
                     "items": [{"product_code": "A95", "volume_l": 100}]}],
    }
    with patch.object(AutoparkController, "_load_point_is_foreign",
                      return_value=False), \
         patch("modules.autopark.controller.AutoparkStore.distance_lookup_fn",
              return_value=lambda *a: None):
        res = AutoparkController.trip_create_manual(payload)
    assert res["success"] is False
    assert "матрице" in res["message"]


def test_trip_create_manual_warns_on_contradicting_trip_type():
    from modules.autopark.controller import AutoparkController
    payload = {
        "trip_date": "2026-08-01", "truck_id": 1, "driver_id": 2,
        "load_point_id": 10, "end_point_id": 20, "type_code": "IMPORT",
        "stations": [{"station_id": 30,
                     "items": [{"product_code": "A95", "volume_l": 100}]}],
    }
    matrix = {
        ("LOAD", 10, "STATION", 30): 50,
        ("STATION", 30, "END", 20): 60,
    }
    lookup = lambda fk, fi, tk, ti: matrix.get((fk, fi, tk, ti))  # noqa: E731
    with patch.object(AutoparkController, "_load_point_is_foreign",
                      return_value=False), \
         patch("modules.autopark.controller.AutoparkStore.distance_lookup_fn",
              return_value=lookup), \
         patch("modules.autopark.controller.AutoparkStore.create_trip",
              return_value={"success": True,
                           "data": {"trip_id": 1, "norm_km": 110},
                           "message": ""}), \
         patch("modules.autopark.controller.AutoparkStore.log_event"):
        res = AutoparkController.trip_create_manual(payload)
    assert res["success"] is True
    assert res.get("warnings"), "expected a warning for the type mismatch"
    assert "IMPORT" in res["warnings"][0]


def test_trip_create_manual_matches_computed_type_without_a_warning():
    from modules.autopark.controller import AutoparkController
    payload = {
        "trip_date": "2026-08-01", "truck_id": 1, "driver_id": 2,
        "load_point_id": 10, "end_point_id": 20,
        "stations": [{"station_id": 30,
                     "items": [{"product_code": "A95", "volume_l": 100}]}],
    }
    matrix = {
        ("LOAD", 10, "STATION", 30): 50,
        ("STATION", 30, "END", 20): 60,
    }
    lookup = lambda fk, fi, tk, ti: matrix.get((fk, fi, tk, ti))  # noqa: E731
    with patch.object(AutoparkController, "_load_point_is_foreign",
                      return_value=False), \
         patch("modules.autopark.controller.AutoparkStore.distance_lookup_fn",
              return_value=lookup), \
         patch("modules.autopark.controller.AutoparkStore.create_trip",
              return_value={"success": True,
                           "data": {"trip_id": 1, "norm_km": 110},
                           "message": ""}), \
         patch("modules.autopark.controller.AutoparkStore.log_event"):
        res = AutoparkController.trip_create_manual(payload)
    assert res["success"] is True
    assert not res.get("warnings")


# -- routes: every documented address is declared ------------------------

def test_routes_declare_every_documented_api_endpoint():
    from flask import Flask

    from core.module_loader import load_module

    app = Flask(__name__)
    app.secret_key = "test"
    loaded = load_module(app, "autopark")
    assert loaded
    rules = {r.rule for r in app.url_map.iter_rules()}
    prefix = "/UNA.md/orasldev/autopark"
    for suffix in (
        "/api/refs", "/api/station", "/api/truck", "/api/driver",
        "/api/distance", "/api/settings", "/api/delivery", "/api/trips",
        "/api/trip", "/api/trip/autoform", "/api/trip/approve",
        "/api/trip/fact", "/api/stock", "/api/supply-plan",
        "/api/report/payroll", "/api/report/control", "/api/report/drivers",
        "/api/report/trucks", "/api/report/stations",
        "/api/report/management",
    ):
        assert prefix + suffix in rules, suffix
    assert prefix in rules or prefix + "/" in rules


# -- Task 4: fuel prices (123_flt_prices.sql + store/routes/generator) ----

def test_prices_ddl_declares_table_and_unique_constraint():
    ddl = _sql("123_flt_prices.sql").upper()
    assert "CREATE TABLE FLT_FUEL_PRICES" in ddl
    assert "UNIQUE (PRICE_DATE, PRODUCT_CODE)" in ddl
    assert "CHECK (SOURCE IN ('ANRE','MODEL'))" in ddl
    assert "CHECK (PRICE_LEI > 0)" in ddl


def test_prices_ddl_has_no_semicolons_in_comments():
    for line in _sql("123_flt_prices.sql").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            assert ";" not in stripped, stripped


def test_prices_ddl_trigger_is_fenced_by_slashes_before_and_after():
    text = _sql("123_flt_prices.sql")
    idx = text.index("CREATE OR REPLACE TRIGGER TRG_FLT_FUEL_PRICES_BI")
    before = text[:idx].rstrip()
    assert before.endswith("/"), "missing leading '/' before the trigger block"
    after = text[idx:]
    end_idx = after.index("END;") + len("END;")
    after_trigger = after[end_idx:].lstrip()
    assert after_trigger.startswith("/"), "missing trailing '/' after the trigger block"


def test_store_declares_list_and_upsert_fuel_prices():
    from modules.autopark.store import AutoparkStore
    assert hasattr(AutoparkStore, "list_fuel_prices")
    assert hasattr(AutoparkStore, "upsert_fuel_prices")


def test_controller_declares_fuel_prices_wrapper():
    from modules.autopark.controller import AutoparkController
    assert hasattr(AutoparkController, "fuel_prices")


def test_fuel_prices_route_is_declared():
    from flask import Flask

    from core.module_loader import load_module

    app = Flask(__name__)
    app.secret_key = "test"
    loaded = load_module(app, "autopark")
    assert loaded
    rules_set = {r.rule for r in app.url_map.iter_rules()}
    assert "/UNA.md/orasldev/autopark/api/fuel-prices" in rules_set


def test_price_generator_produces_jumps_over_three_percent():
    from modules.autopark.scripts.autopark_prices import build_all_rows
    rows, jump_days = build_all_rows()
    assert len(jump_days) > 0, "expected at least one day-to-day change > 3%"
    assert rows


def test_price_generator_labels_unretrieved_products_as_model():
    from modules.autopark.scripts.autopark_prices import REAL_ANRE, PRODUCTS
    # A92/A98 have no retrievable public ANRE archive -- must not be
    # silently reported as real regulator data.
    for product in ("A92", "A98"):
        assert product not in REAL_ANRE
    assert set(PRODUCTS) == {"A92", "A95", "A98", "DIESEL"}


def test_history_generator_caps_route_length_and_import_cadence():
    from modules.autopark.scripts.autopark_history import build_import_trip_dates
    dates = build_import_trip_dates()
    # ~1 import trip per month over a ~24-month horizon.
    assert 18 <= len(dates) <= 30


# -- Task 4 fix: dashboard keys, chart date sorting, ANRE/MODEL seam -----

def test_station_supply_report_selects_current_and_min_stock():
    src = open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8").read()
    idx = src.index("def station_supply_report")
    body = src[idx:idx + 1200]
    assert "s.CURRENT_L" in body
    assert "s.MIN_STOCK_L" in body


def test_price_changes_are_sorted_by_real_timestamp_in_template():
    html = open(os.path.join(MODULE_DIR, "templates", "autopark.html"),
                encoding="utf-8").read()
    assert "function dateTime(v)" in html
    assert "dateTime(b.price_date) - dateTime(a.price_date)" in html
    # the old lexicographic string comparison must be gone
    assert "a.price_date < b.price_date" not in html


def test_template_has_fmt_date_helper_used_for_trip_and_delivery_dates():
    html = open(os.path.join(MODULE_DIR, "templates", "autopark.html"),
                encoding="utf-8").read()
    assert "function fmtDate(v)" in html
    assert "fmtDate(t.trip_date)" in html
    assert "fmtDate(d.deliv_date)" in html
    assert "fmtDate(r.price_date)" in html


def test_calibration_keeps_anchor_boundary_change_under_five_percent():
    from datetime import timedelta

    from modules.autopark.scripts.autopark_prices import REAL_ANRE, build_all_rows
    rows, _jumps = build_all_rows()
    by_prod = {}
    for r in rows:
        by_prod.setdefault(r["product_code"], {})[r["price_date"]] = r["price_lei"]
    for product, anchors in REAL_ANRE.items():
        series = by_prod[product]
        for d in anchors:
            for neighbor in (d - timedelta(days=1), d + timedelta(days=1)):
                if neighbor in series and series[neighbor]:
                    pct = abs(series[d] - series[neighbor]) / series[neighbor] * 100
                    assert pct < 5, (product, d, neighbor, pct)


def test_calibrate_to_anchors_leaves_products_without_anchors_untouched():
    from datetime import date

    from modules.autopark.scripts.autopark_prices import calibrate_to_anchors
    series = {date(2025, 1, 1): 24.0, date(2025, 1, 2): 24.5}
    assert calibrate_to_anchors(series, {}) == series


# -- Task 5: GPS layer (124_flt_gps.sql + gps.py + store/controller/routes) --

def test_gps_ddl_declares_alters_and_new_tables():
    ddl = _sql("124_flt_gps.sql").upper()
    assert "ALTER TABLE FLT_STATIONS ADD" in ddl
    assert "ALTER TABLE FLT_LOAD_POINTS ADD" in ddl
    assert "ALTER TABLE FLT_END_POINTS ADD" in ddl
    assert "CREATE TABLE FLT_GPS_PROVIDERS" in ddl
    assert "CREATE TABLE FLT_GPS_TRACKS" in ddl
    assert "CHECK (KIND IN ('SIM','HTTP_PUSH','HTTP_PULL'))" in ddl
    assert "CACHE 20" in ddl


def test_gps_ddl_has_composite_index_on_trip_and_ts():
    ddl = _sql("124_flt_gps.sql").upper()
    assert "CREATE INDEX IX_FLT_GPS_TRACKS_TRIP_TS ON FLT_GPS_TRACKS (TRIP_ID, TS)" in ddl


def test_gps_ddl_has_no_semicolons_in_comments():
    for line in _sql("124_flt_gps.sql").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            assert ";" not in stripped, stripped


def test_gps_ddl_triggers_are_fenced_by_slashes_before_and_after():
    text = _sql("124_flt_gps.sql")
    for trigger_name in ("TRG_FLT_GPS_PROVIDERS_BI", "TRG_FLT_GPS_TRACKS_BI"):
        idx = text.index(f"CREATE OR REPLACE TRIGGER {trigger_name}")
        before = text[:idx].rstrip()
        assert before.endswith("/"), f"missing leading '/' before {trigger_name}"
        after = text[idx:]
        end_idx = after.index("END;") + len("END;")
        after_trigger = after[end_idx:].lstrip()
        assert after_trigger.startswith("/"), f"missing trailing '/' after {trigger_name}"


def test_deploy_installer_ignores_ora_01430_column_already_exists():
    # ALTER TABLE ... ADD on an already-migrated schema raises ORA-01430
    # ("column being added already exists") on a repeat run of file 124 --
    # this must be in the installer's tolerated-not-an-error list, same as
    # the existing 120-123 idempotency guarantee (see autopark_deploy.py
    # docstring / sql/124_flt_gps.sql header comment).
    src = open(os.path.join(MODULE_DIR, "scripts", "autopark_deploy.py"),
              encoding="utf-8").read()
    idx = src.index("if any(code in message for code in")
    assert "ORA-01430" in src[idx:idx + 300]


def test_haversine_km_chisinau_to_balti_matches_known_distance():
    from modules.autopark.gps import haversine_km
    # Chisinau ~47.0105/28.8638, Balti ~47.7614/27.9297 -- straight-line
    # distance is well documented as ~110 km.
    km = haversine_km(47.0105, 28.8638, 47.7614, 27.9297)
    assert abs(km - 110) < 10


def test_haversine_km_same_point_is_zero():
    from modules.autopark.gps import haversine_km
    assert haversine_km(47.0, 28.8, 47.0, 28.8) == 0.0


def test_track_length_km_sums_consecutive_legs():
    from modules.autopark.gps import haversine_km, track_length_km
    points = [{"lat": 47.0, "lon": 28.8}, {"lat": 47.4, "lon": 28.8},
             {"lat": 47.8, "lon": 28.8}]
    expected = (haversine_km(47.0, 28.8, 47.4, 28.8)
               + haversine_km(47.4, 28.8, 47.8, 28.8))
    assert abs(track_length_km(points) - expected) < 1e-9


def test_track_length_km_single_point_is_zero():
    from modules.autopark.gps import track_length_km
    assert track_length_km([{"lat": 47.0, "lon": 28.8}]) == 0.0


def test_interpolate_route_position_before_departure_is_start():
    from datetime import datetime, timedelta

    from modules.autopark.gps import interpolate_route, position_at
    geo_points = [
        {"kind": "LOAD", "id": 1, "lat": 47.0, "lon": 28.8},
        {"kind": "STATION", "id": 2, "lat": 47.4, "lon": 28.8},
        {"kind": "END", "id": 3, "lat": 47.8, "lon": 28.8},
    ]
    depart_ts = datetime(2026, 8, 26, 8, 0)
    profile = interpolate_route(geo_points, depart_ts, 55.0, 25.0)
    pos = position_at(profile, depart_ts - timedelta(hours=1))
    assert pos["started"] is False
    assert pos["lat"] == 47.0 and pos["lon"] == 28.8


def test_interpolate_route_position_after_finish_is_end():
    from datetime import datetime, timedelta

    from modules.autopark.gps import interpolate_route, position_at
    geo_points = [
        {"kind": "LOAD", "id": 1, "lat": 47.0, "lon": 28.8},
        {"kind": "STATION", "id": 2, "lat": 47.4, "lon": 28.8},
        {"kind": "END", "id": 3, "lat": 47.8, "lon": 28.8},
    ]
    depart_ts = datetime(2026, 8, 26, 8, 0)
    profile = interpolate_route(geo_points, depart_ts, 55.0, 25.0)
    pos = position_at(profile, profile[-1]["ts"] + timedelta(days=1))
    assert pos["finished"] is True
    assert pos["lat"] == 47.8 and pos["lon"] == 28.8


def test_interpolate_route_profile_timestamps_are_monotonic():
    from datetime import datetime

    from modules.autopark.gps import interpolate_route
    geo_points = [
        {"kind": "LOAD", "id": 1, "lat": 47.0, "lon": 28.8},
        {"kind": "STATION", "id": 2, "lat": 47.2, "lon": 28.7},
        {"kind": "STATION", "id": 3, "lat": 47.5, "lon": 28.6},
        {"kind": "END", "id": 4, "lat": 47.0, "lon": 28.85},
    ]
    profile = interpolate_route(geo_points, datetime(2026, 8, 26, 8, 0), 55.0, 25.0)
    for a, b in zip(profile, profile[1:]):
        assert b["ts"] >= a["ts"]


def test_interpolate_route_rejects_non_positive_speed():
    from datetime import datetime

    from modules.autopark.gps import interpolate_route
    geo_points = [{"kind": "LOAD", "id": 1, "lat": 47.0, "lon": 28.8},
                 {"kind": "END", "id": 2, "lat": 47.5, "lon": 28.8}]
    try:
        interpolate_route(geo_points, datetime(2026, 8, 26, 8, 0), 0, 10)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_position_at_empty_profile_is_none():
    from modules.autopark.gps import position_at
    assert position_at([], object()) is None


def test_normalize_points_discards_garbage_and_reports_reasons():
    from modules.autopark.gps import normalize_points
    payload = {"track": [
        {"ts": "2026-08-26T08:00:00", "lat": 47.0, "lon": 28.8, "speed": 50},
        {"ts": "2026-08-26T08:05:00", "lat": "not-a-number", "lon": 28.8},
        {"lat": 47.1, "lon": 28.8},                     # missing ts
        {"ts": "2026-08-26T08:10:00", "lat": 999, "lon": 28.8},  # out of range
        "not-a-dict",
    ]}
    points, reasons = normalize_points("SIM", payload)
    assert len(points) == 1
    assert points[0]["lat"] == 47.0
    assert len(reasons) == 4


def test_normalize_points_accepts_device_key_as_alias_for_track():
    from modules.autopark.gps import normalize_points
    payload = {"device": [{"ts": "2026-08-26T08:00:00", "lat": 47.0, "lon": 28.8}]}
    points, reasons = normalize_points("SIM", payload)
    assert len(points) == 1
    assert not reasons


def test_normalize_points_rejects_unknown_provider_kind():
    from modules.autopark.gps import normalize_points
    points, reasons = normalize_points("CARRIER_PIGEON", {"track": []})
    assert points == []
    assert reasons


def test_normalize_points_missing_track_and_device_is_reported():
    from modules.autopark.gps import normalize_points
    points, reasons = normalize_points("SIM", {})
    assert points == []
    assert reasons


def test_store_declares_gps_layer_methods():
    from modules.autopark.store import AutoparkStore
    for name in ("list_geo_points", "insert_track_points", "get_track",
                "apply_track_fact", "active_trips_today",
                "get_gps_provider", "trip_geo_points", "get_trip_header"):
        assert hasattr(AutoparkStore, name), name


def test_controller_declares_gps_layer_methods():
    from modules.autopark.controller import AutoparkController
    for name in ("gps_geo", "gps_ingest", "gps_positions", "gps_track",
                "gps_replay"):
        assert hasattr(AutoparkController, name), name


def test_gps_routes_are_declared():
    from flask import Flask

    from core.module_loader import load_module

    app = Flask(__name__)
    app.secret_key = "test"
    loaded = load_module(app, "autopark")
    assert loaded
    rules_set = {r.rule for r in app.url_map.iter_rules()}
    prefix = "/UNA.md/orasldev/autopark"
    for suffix in ("/api/gps/positions", "/api/gps/track", "/api/gps/ingest",
                  "/api/gps/replay", "/api/gps/geo"):
        assert prefix + suffix in rules_set, suffix


def test_apply_track_fact_short_track_is_rejected(monkeypatch):
    from modules.autopark.store import AutoparkStore

    monkeypatch.setattr(AutoparkStore, "get_track",
                        staticmethod(lambda trip_id: {"success": True,
                                                      "data": [{"lat": 47.0,
                                                               "lon": 28.8}]}))
    res = AutoparkStore.apply_track_fact(123)
    assert res["success"] is False
    assert "точек" in res["message"]


def test_apply_track_fact_propagates_get_track_failure(monkeypatch):
    from modules.autopark.store import AutoparkStore

    monkeypatch.setattr(AutoparkStore, "get_track",
                        staticmethod(lambda trip_id: {"success": False,
                                                      "data": None,
                                                      "message": "boom"}))
    res = AutoparkStore.apply_track_fact(123)
    assert res["success"] is False
    assert res["message"] == "boom"


def test_gps_replay_refuses_draft_trip(monkeypatch):
    from modules.autopark.controller import AutoparkController
    from modules.autopark.store import AutoparkStore

    monkeypatch.setattr(
        AutoparkStore, "trip_geo_points",
        staticmethod(lambda trip_id: {"success": True, "data": {
            "trip": {"id": trip_id, "status_code": "DRAFT", "norm_km": 100,
                    "trip_date": __import__("datetime").datetime(2026, 1, 1)},
            "geo_points": [{"kind": "LOAD", "id": 1, "lat": 47.0, "lon": 28.8},
                          {"kind": "END", "id": 2, "lat": 47.5, "lon": 28.8}],
        }}))
    res = AutoparkController.gps_replay({"trip_id": 1})
    assert res["success"] is False
    assert "DRAFT" in res["message"]


def test_gps_ingest_validates_provider_and_points(monkeypatch):
    from modules.autopark.controller import AutoparkController
    res = AutoparkController.gps_ingest({"trip_id": 1, "points": []})
    assert res["success"] is False
    res2 = AutoparkController.gps_ingest({"provider": "SIM", "trip_id": 1})
    assert res2["success"] is False

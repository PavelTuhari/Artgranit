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


def test_deploy_script_installs_all_three_flt_files_in_order():
    from modules.autopark.scripts.autopark_deploy import FILES
    assert FILES == (
        "120_flt_tables.sql", "121_flt_views.sql", "122_flt_seed.sql",
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

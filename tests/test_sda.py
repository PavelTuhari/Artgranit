"""SDA module — unit tests (no live Oracle, no wallet).

DDL is verified by parsing sql/117_sda_tables.sql: that catches the errors
that cost the most — a forgotten index on a foreign key, a lost prefix,
a Cyrillic comment shipped into the database. The Python layer is tested
with mocks over DatabaseModel, as in tests/test_biro26.py.
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
    "SDA_PARTIC", "SDA_PARTIC_ROL", "SDA_UNIT", "SDA_RETURN_POINT",
    "SDA_RVM", "SDA_PACK", "SDA_PACK_SKU", "SDA_TARIFF",
    "SDA_TARIFF_LINE", "SDA_EVENT_LOG",
]


# -- Task 1: schema ---------------------------------------------------

def test_ddl_declares_every_table():
    ddl = _sql("117_sda_tables.sql").upper()
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table}" in ddl, table


def test_ddl_has_no_cyrillic():
    ddl = _sql("117_sda_tables.sql")
    assert not re.search(r"[Ѐ-ӿ]", ddl), "Cyrillic found in DDL"


def test_every_foreign_key_column_has_an_index():
    ddl = _sql("117_sda_tables.sql").upper()

    # Index every table's first-column position: {table: {first_col, ...}}.
    indexed_by_table = {}
    for table, cols in re.findall(
        r"CREATE (?:UNIQUE )?INDEX [A-Z0-9_]+ ON ([A-Z0-9_]+) \(([^)]+)\)", ddl
    ):
        indexed_by_table.setdefault(table, set()).add(cols.split(",")[0].strip())

    # Parse each CREATE TABLE <name> ( ... ); block and collect its FK columns.
    for table, body in re.findall(
        r"CREATE TABLE ([A-Z0-9_]+) \((.*?)\n\);", ddl, re.DOTALL
    ):
        fk_cols = re.findall(r"FOREIGN KEY \(([A-Z0-9_]+)\)", body)
        for col in fk_cols:
            assert col in indexed_by_table.get(table, set()), \
                f"{table}.{col} is a FK but has no index on {table} starting with it"


def test_every_table_has_a_sequence_and_trigger():
    ddl = _sql("117_sda_tables.sql").upper()
    for table in EXPECTED_TABLES:
        assert f"CREATE SEQUENCE SEQ_{table}" in ddl, table
        assert f"CREATE OR REPLACE TRIGGER TRG_{table}_BI" in ddl, table


def test_partic_carries_the_declared_sales_volumes():
    ddl = _sql("117_sda_tables.sql").upper()
    partic = ddl[ddl.index("CREATE TABLE SDA_PARTIC "):]
    partic = partic[:partic.index(";")]
    for col in ("VANDUT_AN_ANT", "ESTIMARE_AN"):
        assert col in partic, col


def test_unit_carries_surface_and_regime():
    ddl = _sql("117_sda_tables.sql").upper()
    unit = ddl[ddl.index("CREATE TABLE SDA_UNIT"):]
    unit = unit[:unit.index(";")]
    for col in ("SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV",
                "DATA_EVALUARE", "COD_ERP"):
        assert col in unit, col


def test_return_point_distance_is_capped_at_150():
    ddl = _sql("117_sda_tables.sql").upper()
    assert "DISTANTA_M" in ddl
    assert re.search(r"DISTANTA_M\s*(<=|BETWEEN 0 AND)\s*150", ddl), \
        "no CHECK enforcing the 150 m limit from pct. 85"


def test_pack_registry_holds_tariff_categories():
    ddl = _sql("117_sda_tables.sql").upper()
    pack = ddl[ddl.index("CREATE TABLE SDA_PACK"):]
    pack = pack[:pack.index(";")]
    for col in ("EAN", "MATERIAL", "REUTILIZABIL", "VOLUM_L",
                "GREUTATE_G", "CAT_ADMIN", "CAT_GEST"):
        assert col in pack, col


def test_ean_is_unique():
    ddl = _sql("117_sda_tables.sql").upper()
    assert re.search(r"CREATE UNIQUE INDEX [A-Z0-9_]+ ON SDA_PACK \(EAN\)", ddl) \
        or "EAN VARCHAR2(20) NOT NULL UNIQUE" in ddl, "EAN must be unique"


def test_tariff_line_reutilizabil_is_constrained():
    ddl = _sql("117_sda_tables.sql").upper()
    assert "CONSTRAINT CK_SDA_TL_REUT CHECK (REUTILIZABIL IS NULL OR REUTILIZABIL IN ('D','N'))" in ddl


def test_pack_tariff_categories_are_constrained():
    ddl = _sql("117_sda_tables.sql").upper()
    assert "CONSTRAINT CK_SDA_PACK_CATADM CHECK (CAT_ADMIN IS NULL OR CAT_ADMIN IN ('A','B','C','D','E','F','G'))" in ddl
    assert "CONSTRAINT CK_SDA_PACK_CATGES CHECK (CAT_GEST IS NULL OR CAT_GEST IN ('A','B','C','D','E'))" in ddl


def test_tariff_line_categorie_is_constrained():
    ddl = _sql("117_sda_tables.sql").upper()
    assert "CONSTRAINT CK_SDA_TL_CAT CHECK (CATEGORIE IN ('A','B','C','D','E','F','G','*'))" in ddl


def test_deploy_script_installs_the_sda_ddl():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert '"117_sda_tables.sql"' in src


# -- Task 2: pure rules ------------------------------------------------

from models import sda_rules  # noqa: E402


def test_small_shop_falls_under_the_exception():
    regim, motiv = sda_rules.classify_regime(85.0, "MAGAZIN")
    assert regim == "B_EXCEPTIE_APL"
    assert "100" in motiv


def test_shop_exactly_at_the_threshold_still_falls_under_the_exception():
    # pct. 93 says "nu depaseste 100 m2" - 100 is inside the exception.
    regim, _ = sda_rules.classify_regime(100.0, "MAGAZIN")
    assert regim == "B_EXCEPTIE_APL"


def test_large_shop_needs_its_own_return_point():
    regim, motiv = sda_rules.classify_regime(240.0, "MAGAZIN")
    assert regim == "A_PUNCT_PROPRIU"
    assert "240" in motiv


def test_kiosk_uses_the_150_threshold():
    assert sda_rules.classify_regime(140.0, "CHIOSC")[0] == "B_EXCEPTIE_APL"
    assert sda_rules.classify_regime(160.0, "CHIOSC")[0] == "A_PUNCT_PROPRIU"


def test_petrol_station_and_market_stall_use_the_special_threshold():
    for tip in ("BENZINARIE", "TARABA", "ALIMENTATIE_PUBLICA"):
        assert sda_rules.classify_regime(149.0, tip)[0] == "B_EXCEPTIE_APL", tip


def test_horeca_wins_over_surface():
    regim, motiv = sda_rules.classify_regime(400.0, "ALIMENTATIE_PUBLICA", is_horeca=True)
    assert regim == "C_HORECA"
    assert "HoReCa" in motiv


def test_unknown_surface_gives_no_regime_and_says_why():
    regim, motiv = sda_rules.classify_regime(None, "MAGAZIN")
    assert regim is None
    assert "suprafa" in motiv.lower()


def test_admin_categories_cover_the_seven_cases():
    assert sda_rules.admin_category("PLASTIC", "TRANSPARENT", "N", 1.5) == "a"
    assert sda_rules.admin_category("PLASTIC", "VERDE", "N", 1.5) == "b"
    assert sda_rules.admin_category("PLASTIC", "ROSU", "N", 1.5) == "c"
    assert sda_rules.admin_category("PLASTIC", "TRANSPARENT", "D", 1.5) == "d"
    assert sda_rules.admin_category("METAL", None, "N", 0.33) == "e"
    assert sda_rules.admin_category("STICLA", None, "N", 0.75) == "f"
    assert sda_rules.admin_category("STICLA", None, "N", 0.5) == "g"


def test_oxygen_barrier_beats_colour():
    # A barrier moves the packaging to category d whatever its colour.
    assert sda_rules.admin_category("PLASTIC", "VERDE", "D", 1.0) == "d"


def test_gest_categories_split_plastic_at_one_litre_and_glass_at_half():
    assert sda_rules.gest_category("PLASTIC", 1.0) == "a"
    assert sda_rules.gest_category("PLASTIC", 1.5) == "b"
    assert sda_rules.gest_category("METAL", 0.5) == "c"
    assert sda_rules.gest_category("STICLA", 0.75) == "d"
    assert sda_rules.gest_category("STICLA", 0.5) == "e"

# -- Task 3: tariff periods -------------------------------------------

from datetime import date  # noqa: E402


def _p(tid, tip, start, end=None):
    return {"tariff_id": tid, "tip": tip, "data_start": start, "data_end": end}


def test_clean_consecutive_periods_are_valid():
    problems = sda_rules.validate_periods([
        _p(1, "DEPOZIT", date(2027, 1, 25), date(2027, 6, 30)),
        _p(2, "DEPOZIT", date(2027, 7, 1), None),
    ])
    assert problems == []


def test_overlapping_periods_are_reported():
    problems = sda_rules.validate_periods([
        _p(1, "DEPOZIT", date(2027, 1, 25), date(2027, 7, 31)),
        _p(2, "DEPOZIT", date(2027, 7, 1), None),
    ])
    assert len(problems) == 1
    assert "suprapun" in problems[0].lower()


def test_gap_between_periods_is_reported():
    problems = sda_rules.validate_periods([
        _p(1, "DEPOZIT", date(2027, 1, 25), date(2027, 6, 30)),
        _p(2, "DEPOZIT", date(2027, 8, 1), None),
    ])
    assert len(problems) == 1
    assert "gol" in problems[0].lower()


def test_different_tariff_types_do_not_collide():
    problems = sda_rules.validate_periods([
        _p(1, "DEPOZIT", date(2027, 1, 25), None),
        _p(2, "ADMIN", date(2027, 1, 25), None),
    ])
    assert problems == []


def test_pick_value_matches_the_exact_category():
    lines = [
        {"categorie": "a", "metoda": None, "reutilizabil": None, "valoare_lei": 0.11},
        {"categorie": "e", "metoda": None, "reutilizabil": None, "valoare_lei": 0.09},
    ]
    assert sda_rules.pick_value(lines, "e") == 0.09


def test_pick_value_distinguishes_manual_from_automatic():
    lines = [
        {"categorie": "a", "metoda": "MANUAL", "reutilizabil": None, "valoare_lei": 0.20},
        {"categorie": "a", "metoda": "AUTOMAT", "reutilizabil": None, "valoare_lei": 0.35},
    ]
    assert sda_rules.pick_value(lines, "a", metoda="AUTOMAT") == 0.35


def test_pick_value_falls_back_to_the_wildcard_category():
    lines = [{"categorie": "*", "metoda": None, "reutilizabil": None, "valoare_lei": 1.0}]
    assert sda_rules.pick_value(lines, "f") == 1.0


def test_pick_value_returns_none_when_nothing_matches():
    lines = [{"categorie": "a", "metoda": None, "reutilizabil": None, "valoare_lei": 0.11}]
    assert sda_rules.pick_value(lines, "f") is None


def test_pick_value_distinguishes_reusable_from_single_use():
    lines = [
        {"categorie": "a", "metoda": None, "reutilizabil": "D", "valoare_lei": 0.50},
        {"categorie": "a", "metoda": None, "reutilizabil": "N", "valoare_lei": 0.11},
    ]
    assert sda_rules.pick_value(lines, "a", reutilizabil="D") == 0.50
    assert sda_rules.pick_value(lines, "a", reutilizabil="N") == 0.11


def test_pick_value_without_reutilizabil_does_not_match_a_specific_line():
    lines = [{"categorie": "a", "metoda": None, "reutilizabil": "D", "valoare_lei": 0.50}]
    assert sda_rules.pick_value(lines, "a") is None


def test_pick_value_null_reutilizabil_line_matches_either_caller_value():
    lines = [{"categorie": "a", "metoda": None, "reutilizabil": None, "valoare_lei": 0.20}]
    assert sda_rules.pick_value(lines, "a", reutilizabil="D") == 0.20
    assert sda_rules.pick_value(lines, "a", reutilizabil="N") == 0.20


def test_gap_hidden_by_a_wider_covering_period_is_not_reported():
    problems = sda_rules.validate_periods([
        _p(1, "DEPOZIT", date(2027, 1, 1), date(2027, 4, 1)),
        _p(2, "DEPOZIT", date(2027, 1, 2), date(2027, 1, 3)),
        _p(3, "DEPOZIT", date(2027, 3, 1), date(2027, 5, 1)),
    ])
    assert not any("gol" in p.lower() for p in problems)
    assert any("suprapun" in p.lower() for p in problems)


# -- Task 4: store ----------------------------------------------------

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


def test_list_units_maps_rows_to_dicts():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["UNIT_ID", "DENUMIRE", "REGIM"],
                           [[1, "Magazin 12", "B_EXCEPTIE_APL"]]))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.list_units()
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Magazin 12"


def test_saving_a_unit_recomputes_its_regime():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin 12", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    params = db.execute_query.call_args_list[0][0][1]
    assert params["regim"] == "B_EXCEPTIE_APL"
    assert "100" in params["regim_motiv"]


def test_saving_a_unit_without_surface_leaves_the_regime_empty():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        SDAStore.save_unit({"partic_id": 1, "denumire": "X",
                            "tip_amplasament": "MAGAZIN"}, "tester")
    params = db.execute_query.call_args_list[0][0][1]
    assert params["regim"] is None


def test_compliance_map_counts_units_without_a_regime_separately():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["REGIM", "N"],
                           [["B_EXCEPTIE_APL", 65], ["A_PUNCT_PROPRIU", 17],
                            [None, 3]]))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.compliance_map()
    assert res["data"]["total"] == 85
    assert res["data"]["by_regime"]["B_EXCEPTIE_APL"] == 65
    assert res["data"]["unknown"] == 3


def test_reclassify_all_keeps_horeca_units_horeca():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM"],
            [[1, 500, "MAGAZIN", "C_HORECA"]]),
        _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    assert res["data"]["changed"] == 0


def test_reclassify_all_updates_units_whose_regime_no_longer_matches_surface():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    assert res["data"]["changed"] == 1
    update_params = db.execute_query.call_args_list[1][0][1]
    assert update_params["regim"] == "A_PUNCT_PROPRIU"
    assert update_params["unit_id"] == 7


def test_store_reports_failure_instead_of_raising():
    from models.sda_oracle_store import SDAStore
    db = _db_returning({"success": False, "columns": [], "data": [],
                        "rowcount": 0, "message": "ORA-00942"})
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.list_units()
    assert res["success"] is False
    assert "ORA-00942" in res["message"]


# -- Task 5: registry -------------------------------------------------

def test_saving_a_pack_derives_both_tariff_categories():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        SDAStore.save_pack({"ean": "4840012345678", "material": "STICLA",
                            "volum_l": 0.75, "greutate_g": 380}, "tester")
    params = db.execute_query.call_args_list[0][0][1]
    assert params["cat_admin"] == "f"
    assert params["cat_gest"] == "d"


def test_deposit_for_a_known_ean_uses_the_current_tariff():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [["*", None, None, 1.0]]),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 1.0
    assert res["data"]["pack_id"] == 7


def test_unknown_ean_never_silently_returns_zero_deposit():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["PACK_ID"], []))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("0000000000000")
    assert res["success"] is False
    assert "registru" in res["message"].lower()


def test_known_ean_without_a_tariff_period_is_an_error_not_a_zero():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"], []),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is False
    assert "tarif" in res["message"].lower()


def test_overlapping_tariff_periods_pick_the_later_starting_one():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        # Мок отдаёт данные в порядке ORDER BY DATA_START DESC, TARIFF_ID DESC:
        # более поздний период (2.0 lei) идёт первым.
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [["*", None, None, 2.0], ["*", None, None, 1.0]]),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 2.0
    tariff_sql = db.execute_query.call_args_list[1][0][0]
    assert "ORDER BY T.DATA_START DESC, T.TARIFF_ID DESC" in tariff_sql


def test_saving_a_unit_with_id_zero_updates_instead_of_inserting():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"unit_id": 0, "partic_id": 1, "denumire": "Magazin 0",
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("UPDATE SDA_UNIT")


def test_saving_a_pack_with_id_zero_updates_instead_of_inserting():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack(
            {"pack_id": 0, "ean": "4840012345678", "material": "STICLA",
             "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("UPDATE SDA_PACK")


# -- Task 6: controller and routes ------------------------------------

def test_controller_rejects_a_unit_without_a_name():
    from controllers.sda_controller import SDAController
    res = SDAController.save_unit({"partic_id": 1}, "tester")
    assert res["success"] is False
    assert "denumire" in res["message"].lower()


def test_controller_rejects_a_pack_without_an_ean():
    from controllers.sda_controller import SDAController
    res = SDAController.save_pack({"material": "STICLA", "volum_l": 0.5,
                                   "greutate_g": 300}, "tester")
    assert res["success"] is False
    assert "ean" in res["message"].lower()


def test_controller_rejects_a_volume_outside_the_legal_range():
    from controllers.sda_controller import SDAController
    res = SDAController.save_pack({"ean": "484", "material": "PLASTIC",
                                   "volum_l": 5, "greutate_g": 40}, "tester")
    assert res["success"] is False
    assert "3" in res["message"]


def test_deposit_endpoint_requires_an_ean():
    from controllers.sda_controller import SDAController
    res = SDAController.get_deposit({})
    assert res["success"] is False


def test_app_registers_every_sda_api_route():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    for route in ("/api/sda/units", "/api/sda/units/reclassify",
                  "/api/sda/compliance", "/api/sda/packs", "/api/sda/deposit"):
        assert f"'{route}'" in src or f'"{route}"' in src, route

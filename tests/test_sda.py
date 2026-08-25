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
SQL_DIR = os.path.join(ROOT, "modules", "sda", "sql")


def _sql(name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
        return fh.read()


MODULE_DIR = os.path.join(ROOT, "modules", "sda")


def _sda_test_client():
    """A Flask app with only the sda blueprint registered — no live Oracle,
    no wallet, no need to import the whole app.py (see test_seoforge.py's
    approach for the same problem)."""
    from flask import Flask

    from core.module_loader import load_module

    app = Flask(__name__)
    app.secret_key = "test"
    load_module(app, "sda")
    return app.test_client()


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

from modules.sda import rules as sda_rules  # noqa: E402


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


def _currval(new_id=101):
    """Mock pentru rezultatul SELECT SEQ_*.CURRVAL FROM DUAL de dupa un INSERT."""
    return _ok(["CURRVAL"], [[new_id]])


def test_list_units_maps_rows_to_dicts():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["UNIT_ID", "DENUMIRE", "REGIM"],
                           [[1, "Magazin 12", "B_EXCEPTIE_APL"]]))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.list_units()
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Magazin 12"


def test_saving_a_unit_recomputes_its_regime():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin 12", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    params = db.execute_query.call_args_list[0][0][1]
    assert params["regim"] == "B_EXCEPTIE_APL"
    assert "100" in params["regim_motiv"]


def test_saving_a_unit_without_surface_leaves_the_regime_empty():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        SDAStore.save_unit({"partic_id": 1, "denumire": "X",
                            "tip_amplasament": "MAGAZIN"}, "tester")
    params = db.execute_query.call_args_list[0][0][1]
    assert params["regim"] is None


def test_compliance_map_counts_units_without_a_regime_separately():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["REGIM", "N"],
                           [["B_EXCEPTIE_APL", 65], ["A_PUNCT_PROPRIU", 17],
                            [None, 3]]))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.compliance_map()
    assert res["data"]["total"] == 85
    assert res["data"]["by_regime"]["B_EXCEPTIE_APL"] == 65
    assert res["data"]["unknown"] == 3


def test_reclassify_all_keeps_horeca_units_horeca():
    from modules.sda.store import SDAStore
    # REGIM_MOTIV este parte a comparației: reclasificarea rescrie și motivul,
    # deci „nimic nu s-a schimbat" înseamnă regim ȘI motiv identice.
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[1, 500, "ALIMENTATIE_PUBLICA", "C_HORECA",
              "Unitate HoReCa: predare directa catre Administrator"]]),
        _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    assert res["data"]["changed"] == 0


def test_reclassify_all_updates_units_whose_regime_no_longer_matches_surface():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    assert res["data"]["changed"] == 1
    update_params = db.execute_query.call_args_list[1][0][1]
    assert update_params["regim"] == "A_PUNCT_PROPRIU"
    assert update_params["unit_id"] == 7


def test_store_reports_failure_instead_of_raising():
    from modules.sda.store import SDAStore
    db = _db_returning({"success": False, "columns": [], "data": [],
                        "rowcount": 0, "message": "ORA-00942"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.list_units()
    assert res["success"] is False
    assert "ORA-00942" in res["message"]


# -- Task 5: registry -------------------------------------------------

def test_saving_a_pack_derives_both_tariff_categories():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        SDAStore.save_pack({"ean": "4840012345678", "material": "STICLA",
                            "volum_l": 0.75, "greutate_g": 380}, "tester")
    params = db.execute_query.call_args_list[0][0][1]
    assert params["cat_admin"] == "f"
    assert params["cat_gest"] == "d"


def test_deposit_for_a_known_ean_uses_the_current_tariff():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [["*", None, None, 1.0]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 1.0
    assert res["data"]["pack_id"] == 7


def test_unknown_ean_never_silently_returns_zero_deposit():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["PACK_ID"], []))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("0000000000000")
    assert res["success"] is False
    assert "registru" in res["message"].lower()


def test_known_ean_without_a_tariff_period_is_an_error_not_a_zero():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"], []),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is False
    assert "tarif" in res["message"].lower()


def test_overlapping_tariff_periods_pick_the_later_starting_one():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        # Мок отдаёт данные в порядке ORDER BY DATA_START DESC, TARIFF_ID DESC:
        # более поздний период (2.0 lei) идёт первым.
        _ok(["CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [["*", None, None, 2.0], ["*", None, None, 1.0]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 2.0
    tariff_sql = db.execute_query.call_args_list[1][0][0]
    assert "ORDER BY T.DATA_START DESC, T.TARIFF_ID DESC" in tariff_sql


def test_saving_a_unit_with_id_zero_updates_instead_of_inserting():
    from modules.sda.store import SDAStore
    # Prima interogare este citirea regimului curent (HoReCa nu are coloană
    # proprie); ce contează aici este că unit_id == 0 duce la UPDATE, nu INSERT.
    db = _db_returning(_ok(["REGIM"], [["B_EXCEPTIE_APL"]]),
                       _ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"unit_id": 0, "partic_id": 1, "denumire": "Magazin 0",
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    statements = [c[0][0].strip() for c in db.execute_query.call_args_list]
    assert any(x.startswith("UPDATE SDA_UNIT") for x in statements)
    assert not any(x.startswith("INSERT INTO SDA_UNIT") for x in statements)


def test_saving_a_pack_with_id_zero_updates_instead_of_inserting():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack(
            {"pack_id": 0, "ean": "4840012345678", "material": "STICLA",
             "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("UPDATE SDA_PACK")


# -- Task 6: controller and routes ------------------------------------

def test_controller_rejects_a_unit_without_a_name():
    from modules.sda.controller import SDAController
    res = SDAController.save_unit({"partic_id": 1}, "tester")
    assert res["success"] is False
    assert "denumire" in res["message"].lower()


def test_controller_rejects_a_pack_without_an_ean():
    from modules.sda.controller import SDAController
    res = SDAController.save_pack({"material": "STICLA", "volum_l": 0.5,
                                   "greutate_g": 300}, "tester")
    assert res["success"] is False
    assert "ean" in res["message"].lower()


def test_controller_rejects_a_volume_outside_the_legal_range():
    from modules.sda.controller import SDAController
    res = SDAController.save_pack({"ean": "484", "material": "PLASTIC",
                                   "volum_l": 5, "greutate_g": 40}, "tester")
    assert res["success"] is False
    assert "3" in res["message"]


def test_deposit_endpoint_requires_an_ean():
    from modules.sda.controller import SDAController
    res = SDAController.get_deposit({})
    assert res["success"] is False


def test_app_registers_every_sda_api_route():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    for route in ("/api/sda/units", "/api/sda/units/reclassify",
                  "/api/sda/compliance", "/api/sda/packs", "/api/sda/deposit"):
        assert f"'{route}'" in src or f'"{route}"' in src, route


def test_get_units_rejects_a_non_numeric_partic_id():
    from modules.sda.controller import SDAController
    res = SDAController.get_units({"partic_id": "abc"})
    assert res["success"] is False
    assert res["data"] is None
    assert "partic_id" in res["message"]


def test_get_compliance_rejects_a_non_numeric_partic_id():
    from modules.sda.controller import SDAController
    res = SDAController.get_compliance({"partic_id": "abc"})
    assert res["success"] is False
    assert res["data"] is None
    assert "partic_id" in res["message"]


def test_get_units_with_no_partic_id_still_lists_everything():
    from modules.sda.controller import SDAController
    db = _db_returning(_ok(["UNIT_ID", "DENUMIRE", "REGIM"],
                           [[1, "Magazin 12", "B_EXCEPTIE_APL"]]))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAController.get_units({})
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Magazin 12"


def test_get_units_with_a_string_partic_id_reaches_the_store_as_int():
    from modules.sda.controller import SDAController
    from modules.sda.store import SDAStore
    with patch.object(SDAStore, "list_units", return_value=_ok([], [])) as mock_list:
        SDAController.get_units({"partic_id": "7"})
    args, _kwargs = mock_list.call_args
    assert args[0] == 7
    assert isinstance(args[0], int)


def test_get_compliance_with_a_string_partic_id_reaches_the_store_as_int():
    from modules.sda.controller import SDAController
    from modules.sda.store import SDAStore
    with patch.object(SDAStore, "compliance_map",
                       return_value={"success": True, "data": {}, "message": ""}) as mock_map:
        SDAController.get_compliance({"partic_id": "7"})
    args, _kwargs = mock_map.call_args
    assert args[0] == 7
    assert isinstance(args[0], int)

# -- Task 7: interface ------------------------------------------------

def _template(name):
    with open(os.path.join(ROOT, "modules", "sda", "templates", name), encoding="utf-8") as fh:
        return fh.read()


def test_console_template_declares_the_three_panels():
    html = _template("sda.html")
    for panel in ("panel-harta", "panel-retea", "panel-registru"):
        assert f'id="{panel}"' in html, panel


def test_console_template_calls_the_real_api_routes():
    html = _template("sda.html")
    for route in ("/api/sda/compliance", "/api/sda/units", "/api/sda/packs"):
        assert route in html, route


def test_console_route_is_registered():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "/UNA.md/orasldev/sda-console" in src


def test_module_manifest_lists_the_console_page():
    import json
    with open(os.path.join(ROOT, "modules", "sda", "module.json"),
              encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert "pages" in manifest
    assert "/UNA.md/orasldev/sda-console" in manifest["pages"]

# -- Task 8: dossier --------------------------------------------------

def test_dossier_carries_all_eight_blocks_of_pct_78():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003600000000", "Rogob SRL", "Ion Popescu", "+373...",
              "office@example.md", 412000, 430000]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin 12", "str. Test 1", 85, "MAGAZIN", "B_EXCEPTIE_APL"]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"],
            [[1, 1, "str. Test 1", "08-20", "MANUAL"]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["success"] is True
    d = res["data"]
    assert d["vandut_an_anterior"] == 412000
    for block in ("identificare", "contact", "unitati", "punct_preluare",
                  "modalitate_preluare", "vandut_an_anterior",
                  "estimare_an_curent", "exceptii"):
        assert block in d, block


def test_dossier_flags_units_that_still_have_no_regime():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin fara suprafata", "str. X", None, "MAGAZIN", None]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["incomplet"] == 1


# -- Final review: fixes for the blocking findings ---------------------

# 1. Fără commit, python-oracledb face rollback la închiderea conexiunii:
#    fiecare scriere a modulului s-ar fi pierdut în tăcere.

def test_log_commits_its_journal_entry():
    # SDAStore.log() a fost cod mort (l-am sters): singurul apelant era
    # aceasta suita de teste. Reancoram acelasi comportament — o scriere in
    # jurnal (in acest caz cea din save_partic) trebuie sa fie comisa — prin
    # save_partic, calea reala prin care apare o intrare de jurnal.
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is True
    assert db.connection.commit.called


def test_saving_a_unit_commits_the_transaction():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin 12", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


def test_saving_a_pack_commits_the_transaction():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack({"ean": "4840012345678", "material": "STICLA",
                                  "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


def test_reclassify_all_commits_the_batch():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL", "vechi"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["data"]["changed"] == 1
    # O dată pentru lot, o dată pentru intrarea de jurnal scrisă de SDAStore.log.
    assert db.connection.commit.called


def test_saving_a_participant_commits_the_transaction():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


# 2. Participanți: fără ei nicio unitate nu poate exista (PARTIC_ID NOT NULL).

def test_list_partic_maps_rows_to_dicts():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["PARTIC_ID", "IDNO", "DENUMIRE"],
                           [[1, "1003600000000", "Rogob SRL"]]))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.list_partic()
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Rogob SRL"


def test_saving_a_new_participant_inserts_with_bind_variables():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        SDAStore.save_partic({"idno": "1003600000000", "denumire": "Rogob SRL",
                              "stare": "activ"}, "tester")
    sql, params = db.execute_query.call_args_list[0][0]
    assert sql.strip().startswith("INSERT INTO SDA_PARTIC")
    assert "'" not in sql.replace("''", "")
    assert params["stare"] == "ACTIV"
    assert "partic_id" not in params


def test_updating_a_missing_participant_is_reported_not_silently_ok():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic({"partic_id": 42, "idno": "100",
                                    "denumire": "X"}, "tester")
    assert res["success"] is False
    assert "42" in res["message"]
    db.connection.commit.assert_not_called()


def test_saving_a_participant_with_id_zero_updates_instead_of_inserting():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic({"partic_id": 0, "idno": "100",
                                    "denumire": "X"}, "tester")
    assert res["success"] is True
    assert db.execute_query.call_args_list[0][0][0].strip().startswith(
        "UPDATE SDA_PARTIC")


def test_controller_rejects_a_participant_without_a_name():
    from modules.sda.controller import SDAController
    res = SDAController.save_partic({"idno": "1003"}, "tester")
    assert res["success"] is False
    assert "denumire" in res["message"].lower()


def test_controller_rejects_a_participant_without_an_idno():
    from modules.sda.controller import SDAController
    res = SDAController.save_partic({"denumire": "Rogob SRL"}, "tester")
    assert res["success"] is False
    assert "idno" in res["message"].lower()


def test_controller_rejects_a_unit_without_a_participant():
    from modules.sda.controller import SDAController
    res = SDAController.save_unit({"denumire": "Magazin 12"}, "tester")
    assert res["success"] is False
    assert "participant" in res["message"].lower()


def test_app_registers_the_participant_api_route():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "'/api/sda/partic'" in src or '"/api/sda/partic"' in src


def test_console_template_declares_the_participants_panel():
    html = _template("sda.html")
    assert 'id="panel-participanti"' in html
    assert "/api/sda/partic" in html
    # Unitatea se leagă de un participant existent, nu de un ID scris de mână.
    assert '<select id="u_partic_id"' in html


# 3. HoReCa supraviețuiește doar în REGIM: editarea nu are voie s-o piardă.

def test_editing_a_horeca_unit_without_the_flag_keeps_it_horeca():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["REGIM"], [["C_HORECA"]]),
                       _ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"unit_id": 5, "partic_id": 1, "denumire": "Bistro",
             "suprafata_mp": 40, "tip_amplasament": "ALIMENTATIE_PUBLICA"},
            "tester")
    assert res["data"]["regim"] == "C_HORECA"
    update_params = db.execute_query.call_args_list[1][0][1]
    assert update_params["regim"] == "C_HORECA"


def test_console_template_offers_the_horeca_checkbox():
    html = _template("sda.html")
    assert 'id="u_is_horeca"' in html
    assert "HoReCa" in html


# 4. Regimul NULL trebuie să poată fi creat și păstrat din consolă.

def test_console_template_does_not_force_a_surface():
    html = _template("sda.html")
    field = html[html.index('id="u_suprafata_mp"'):]
    field = field[:field.index(">")]
    assert "required" not in field


def test_console_template_shows_the_reason_when_the_regime_is_null():
    html = _template("sda.html")
    assert "unitRegimMotiv" in html
    assert "nestabilit" in html


# 5. O interogare eșuată nu are voie să arate ca „nu există date".

def test_dossier_reports_a_failing_unit_query_instead_of_an_empty_filing():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-00942"},
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["success"] is False
    assert "ORA-00942" in res["message"]


def test_dossier_with_an_incomplete_unit_may_not_be_filed():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin fara suprafata", "str. X", None, "MAGAZIN", None]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["poate_fi_depus"] is False
    # Fără puncte de preluare modalitatea este necunoscută, nu „MANUAL".
    assert res["data"]["modalitate_preluare"] == []


def test_dossier_without_incomplete_units_may_be_filed():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin 12", "str. X", 85, "MAGAZIN", "B_EXCEPTIE_APL"]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"],
            [[1, 1, "str. X", "08-20", "MANUAL"]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["poate_fi_depus"] is True


# 6. Un UPDATE care nu a nimerit niciun rând nu este un succes.

def test_updating_a_missing_unit_is_reported_not_silently_ok():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok(["REGIM"], []), _ok([], [], rowcount=0))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit({"unit_id": 99, "partic_id": 1,
                                  "denumire": "Sters", "suprafata_mp": 50},
                                 "tester")
    assert res["success"] is False
    assert "99" in res["message"]
    db.connection.commit.assert_not_called()


def test_updating_a_missing_pack_is_reported_not_silently_ok():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack({"pack_id": 99, "ean": "484",
                                  "material": "STICLA", "volum_l": 0.5,
                                  "greutate_g": 300}, "tester")
    assert res["success"] is False
    assert "99" in res["message"]
    db.connection.commit.assert_not_called()


# 7. Întâi perioada, apoi categoria în interiorul ei.

def test_a_newer_wildcard_beats_an_older_exact_category():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        # Perioada nouă (TARIFF_ID 2) publică doar '*'; cea veche are un 'f'
        # exact. Fără limitarea la perioada câștigătoare, 'f' ar învinge.
        _ok(["TARIFF_ID", "CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [[2, "*", None, None, 2.00], [1, "f", None, None, 1.00]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 2.00


# 8. Restul.

def test_reclassify_rewrites_a_unit_whose_reason_went_stale():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 85, "MAGAZIN", "B_EXCEPTIE_APL", "motiv vechi, suprafata 70 m2"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["data"]["changed"] == 1
    assert "85" in db.execute_query.call_args_list[1][0][1]["regim_motiv"]


def test_parse_partic_id_is_annotated_as_optional():
    import inspect
    from modules.sda import controller as sda_controller
    sig = inspect.signature(sda_controller._parse_partic_id)
    assert "Optional" in str(sig.return_annotation)


def test_console_template_requires_a_positive_weight():
    html = _template("sda.html")
    field = html[html.index('id="p_greutate_g"'):]
    field = field[:field.index(">")]
    assert "required" in field
    assert 'min="0.01"' in field


def test_an_unknown_placement_type_falls_to_the_stricter_threshold():
    """Un tip necunoscut de amplasament primește pragul de 100 m², nu 150.

    Aceasta este alegerea conservatoare: o unitate nouă ajunge la
    „punct propriu de returnare", nu la scutire. O refactorizare care ar
    inversa valoarea implicită ar declara scutite magazine de 120 m².
    """
    from modules.sda import rules as sda_rules
    assert sda_rules.prag_pentru("SUPERMARKET_VIITOR") == 100.0
    assert sda_rules.prag_pentru("") == 100.0
    assert sda_rules.prag_pentru(None) == 100.0
    regim, _motiv = sda_rules.classify_regime(120, "SUPERMARKET_VIITOR")
    assert regim == "A_PUNCT_PROPRIU"


# -- Second review round: fixes for the eight findings ----------------

# 1. Cimpurile numerice ale participantului nu au voie sa provoace o
#    exceptie necaptata la un fel scris de mana.

def test_controller_rejects_a_non_numeric_sales_volume():
    from modules.sda.controller import SDAController
    res = SDAController.save_partic(
        {"idno": "1", "denumire": "X", "vandut_an_ant": "12.5"}, "tester")
    assert res["success"] is False
    assert "vandut" in res["message"].lower()


def test_controller_rejects_a_non_numeric_estimate():
    from modules.sda.controller import SDAController
    res = SDAController.save_partic(
        {"idno": "1", "denumire": "X", "estimare_an": "abc"}, "tester")
    assert res["success"] is False
    assert "estimare" in res["message"].lower()


def test_controller_accepts_an_absent_sales_volume_as_not_declared():
    from modules.sda.controller import SDAController
    from unittest.mock import patch as _patch
    with _patch("modules.sda.controller.SDAStore.save_partic",
                return_value={"success": True, "data": {}, "message": ""}):
        res = SDAController.save_partic({"idno": "1", "denumire": "X"}, "tester")
    assert res["success"] is True


# 2. reclassify_all nu are voie sa contorizeze sau sa comita un UPDATE esuat.

def test_reclassify_all_reports_a_failing_update_and_does_not_commit():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL", "vechi"]]),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-00001"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is False
    assert "ORA-00001" in res["message"]
    db.connection.commit.assert_not_called()


# 3. O intrare de jurnal esuata nu are voie sa lase scrierea de business
#    sa se comita oricum.

def test_saving_a_unit_does_not_commit_when_the_journal_insert_fails():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok([], [], rowcount=1),
        _currval(),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-01461"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin 12", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is False
    db.connection.commit.assert_not_called()


def test_saving_a_pack_does_not_commit_when_the_journal_insert_fails():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok([], [], rowcount=1),
        _currval(),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-01461"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack({"ean": "4840012345678", "material": "STICLA",
                                  "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is False
    db.connection.commit.assert_not_called()


def test_saving_a_participant_does_not_commit_when_the_journal_insert_fails():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok([], [], rowcount=1),
        _currval(),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-01461"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is False
    db.connection.commit.assert_not_called()


# 4. O unitate A_PUNCT_PROPRIU fara niciun punct de preluare declarat nu
#    poate fi depusa, chiar daca dosarul e altfel "complet".

def test_dossier_with_own_point_regime_and_no_declared_point_may_not_be_filed():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin 500mp", "str. X", 500, "MAGAZIN", "A_PUNCT_PROPRIU"]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["incomplet"] == 0
    assert res["data"]["modalitate_preluare"] == []
    assert res["data"]["poate_fi_depus"] is False


def test_dossier_with_own_point_regime_and_a_declared_point_may_be_filed():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin 500mp", "str. X", 500, "MAGAZIN", "A_PUNCT_PROPRIU"]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"],
            [[1, 1, "str. X", "08-20", "AUTOMAT"]]),
    )
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["poate_fi_depus"] is True


# 5. GET /api/sda/partic returneaza date personale, deci trebuie sa fie
#    protejat la fel ca ruta POST.

def test_app_requires_authentication_on_the_participant_read_route():
    import app as flask_app
    client = flask_app.app.test_client()
    resp = client.get("/api/sda/partic")
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


# 6. O unitate legata de un participant inexistent trebuie sa primeasca
#    un mesaj tradus, nu un ORA brut.

def test_saving_a_unit_with_an_unknown_participant_gets_a_readable_message():
    from modules.sda.store import SDAStore
    db = _db_returning(
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-02291: integrity constraint violated - parent key not found"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 999999, "denumire": "Magazin", "suprafata_mp": 50,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is False
    assert "nu exista" in res["message"].lower()
    assert "ORA-02291" not in res["message"]
    db.connection.commit.assert_not_called()


# 7. Un id gol de forma "" trebuie tratat ca absent, la fel ca None; 0
#    ramane un id real.

def test_empty_string_unit_id_is_treated_as_absent():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"unit_id": "", "partic_id": 1, "denumire": "Magazin 12",
             "suprafata_mp": 85, "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("INSERT INTO SDA_UNIT")


def test_empty_string_pack_id_is_treated_as_absent():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack(
            {"pack_id": "", "ean": "4840012345678", "material": "STICLA",
             "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("INSERT INTO SDA_PACK")


def test_empty_string_partic_id_is_treated_as_absent():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"partic_id": "", "idno": "1003600000000", "denumire": "Rogob SRL"},
            "tester")
    assert res["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert sql.strip().startswith("INSERT INTO SDA_PARTIC")


# -- Third review round: fixes for gate-3 findings ---------------------

# 1. Vezi mai sus (test_app_requires_authentication_on_the_participant_read_route)
#    — verifica acum comportamentul real prin test_client, nu o felie de sursa.

# 2. log() trebuie sa raporteze esecul, iar reclassify_all trebuie sa scrie
#    intrarea de jurnal pe ACEEASI conexiune, inainte de commit-ul lotului.

def test_log_reports_failure_instead_of_returning_none():
    # SDAStore.log() a fost cod mort (l-am sters): singurul apelant era
    # aceasta suita de teste. Reancoram acelasi comportament — o scriere in
    # jurnal esuata trebuie raportata, nu inghitita — prin save_partic,
    # calea reala prin care apare o intrare de jurnal.
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok([], [], rowcount=1), _currval(),
        {"success": False, "columns": [], "data": [],
         "rowcount": 0, "message": "ORA-00001"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is False
    assert "ORA-00001" in res["message"]
    db.connection.commit.assert_not_called()


def test_reclassify_all_does_not_commit_when_the_journal_insert_fails():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL", "vechi"]]),
        _ok([], [], rowcount=1),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-00001"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is False
    assert "ORA-00001" in res["message"]
    db.connection.commit.assert_not_called()


def test_reclassify_all_writes_the_journal_entry_on_the_batch_connection():
    """Jurnalul se scrie prin acelasi db.execute_query cat timp with-block-ul
    e deschis, nu printr-o conexiune separata (SDAStore.log)."""
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL", "vechi"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db) as dm:
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    # o singura instantiere de DatabaseModel pentru list_units + una pentru
    # lotul cu update-uri si jurnal: jurnalul nu deschide o a treia.
    assert dm.call_count == 2
    journal_sql = db.execute_query.call_args_list[2][0][0]
    assert "SDA_EVENT_LOG" in journal_sql
    assert db.connection.commit.call_count == 1


# 3. Un dosar de inregistrare nu poate conta un punct de returnare care nu
#    mai e activ la data de referinta a dosarului.

def test_dossier_ignores_a_return_point_that_has_expired():
    from modules.sda.store import SDAStore
    from datetime import date as _date
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin 500mp", "str. X", 500, "MAGAZIN", "A_PUNCT_PROPRIU"]]),
        # Punctul are ACTIV_PANA in trecut: filtrul din SQL nu l-ar mai
        # intoarce pe date reale, dar mock-ul nu executa WHERE — il tratam
        # ca deja-exclus, exact cum ar face Oracle.
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1, on_date=_date(2026, 1, 1))
    assert res["data"]["poate_fi_depus"] is False
    assert res["data"]["punct_preluare"] == []


def test_dossier_passes_the_reference_date_as_a_bind_parameter():
    from modules.sda.store import SDAStore
    from datetime import date as _date
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"], []),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []))
    ref = _date(2026, 3, 15)
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        SDAStore.registration_dossier(1, on_date=ref)
    points_call = db.execute_query.call_args_list[2]
    sql, params = points_call[0]
    assert "ACTIV_PANA" in sql and "ACTIV_DIN" in sql
    assert params["d"] == ref


# 4. Truncherea la 1000 de caractere trebuie ancorata cu un test, nu doar
#    presupusa functionala.

def test_log_truncates_an_overlong_detail_before_binding_it():
    # SDAStore.log() a fost cod mort (l-am sters): singurul apelant era
    # aceasta suita de teste. Reancoram acelasi comportament — trunchierea
    # detaliului la 1000 de caractere — prin save_partic.
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(),
                       _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "X" * 2000}, "tester")
    assert res["success"] is True
    bound = db.execute_query.call_args_list[2][0][1]["detalii"]
    assert len(bound) == 1000


def test_save_partic_truncates_the_journal_detail():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(), _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "X" * 2000}, "tester")
    assert res["success"] is True
    bound = db.execute_query.call_args_list[2][0][1]["detalii"]
    assert len(bound) <= 1000


# 5. Doua rute noi (units, compliance) trebuie sa ceara autentificare, la
#    fel ca partic si dossier.

def test_app_requires_authentication_on_the_units_read_route():
    import app as flask_app
    client = flask_app.app.test_client()
    resp = client.get("/api/sda/units")
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_app_requires_authentication_on_the_compliance_read_route():
    import app as flask_app
    client = flask_app.app.test_client()
    resp = client.get("/api/sda/compliance")
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_app_leaves_packs_and_deposit_open_without_authentication():
    import app as flask_app
    client = flask_app.app.test_client()
    resp = client.get("/api/sda/packs")
    assert resp.status_code != 401
    resp = client.get("/api/sda/deposit?ean=0000000000000")
    assert resp.status_code != 401


# 6. modules/sda/store.py:484 foloseste .get(...) ca restul accesarilor,
#    iar controllerul respinge un float JSON netreg (12.5) la fel ca stringul.

def test_controller_rejects_a_json_float_sales_volume():
    from modules.sda.controller import SDAController
    res = SDAController.save_partic(
        {"idno": "1", "denumire": "X", "vandut_an_ant": 12.5}, "tester")
    assert res["success"] is False
    assert "vandut" in res["message"].lower()


def test_controller_accepts_a_json_whole_number_float_sales_volume():
    from modules.sda.controller import SDAController
    from unittest.mock import patch as _patch
    with _patch("modules.sda.controller.SDAStore.save_partic",
                return_value={"success": True, "data": {}, "message": ""}):
        res = SDAController.save_partic(
            {"idno": "1", "denumire": "X", "vandut_an_ant": 12.0}, "tester")
    assert res["success"] is True


# -- Fourth review round: fixes for the final findings -----------------

# 1. HoReCa nu este disponibil decat pentru ALIMENTATIE_PUBLICA: controlorul
#    respinge orice incercare de a-l marca pentru un alt tip de amplasament,
#    altfel reclassify_all l-ar citi inapoi din REGIM si l-ar perpetua.

def test_controller_rejects_horeca_flag_for_a_regular_shop():
    from modules.sda.controller import SDAController
    res = SDAController.save_unit(
        {"partic_id": 1, "denumire": "Magazin mare", "suprafata_mp": 500,
         "tip_amplasament": "MAGAZIN", "is_horeca": True}, "tester")
    assert res["success"] is False
    assert "horeca" in res["message"].lower()
    assert "alimentatie" in res["message"].lower()


def test_controller_accepts_horeca_flag_for_alimentatie_publica():
    from modules.sda.controller import SDAController
    from unittest.mock import patch as _patch
    with _patch("modules.sda.controller.SDAStore.save_unit",
                return_value={"success": True, "data": {}, "message": ""}):
        res = SDAController.save_unit(
            {"partic_id": 1, "denumire": "Bistro", "suprafata_mp": 40,
             "tip_amplasament": "ALIMENTATIE_PUBLICA", "is_horeca": True},
            "tester")
    assert res["success"] is True


# 2. Intrarea de jurnal trebuie sa primeasca ENTITATE_ID nenul la creare,
#    citit inapoi prin SEQ_*.CURRVAL pe aceeasi conexiune, imediat dupa
#    INSERT-ul principal.

def test_saving_a_new_unit_writes_a_non_null_entitate_id_to_the_journal():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(555),
                       _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin nou", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    currval_sql = db.execute_query.call_args_list[1][0][0]
    assert "SEQ_SDA_UNIT.CURRVAL" in currval_sql
    journal_params = db.execute_query.call_args_list[2][0][1]
    assert journal_params["entitate_id"] == 555
    assert res["data"]["unit_id"] == 555


def test_saving_a_new_pack_writes_a_non_null_entitate_id_to_the_journal():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(777),
                       _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack(
            {"ean": "4840012345678", "material": "STICLA", "volum_l": 0.75,
             "greutate_g": 380}, "tester")
    assert res["success"] is True
    currval_sql = db.execute_query.call_args_list[1][0][0]
    assert "SEQ_SDA_PACK.CURRVAL" in currval_sql
    journal_params = db.execute_query.call_args_list[2][0][1]
    assert journal_params["entitate_id"] == 777
    assert res["data"]["pack_id"] == 777


def test_saving_a_new_participant_writes_a_non_null_entitate_id_to_the_journal():
    from modules.sda.store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _currval(333),
                       _ok([], [], rowcount=1))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is True
    currval_sql = db.execute_query.call_args_list[1][0][0]
    assert "SEQ_SDA_PARTIC.CURRVAL" in currval_sql
    journal_params = db.execute_query.call_args_list[2][0][1]
    assert journal_params["entitate_id"] == 333
    assert res["data"]["partic_id"] == 333


# 3. reclassify_all nu are voie sa scrie in jurnal si sa comita atunci cand
#    nimic nu s-a schimbat.

def test_reclassify_all_skips_journal_and_commit_when_nothing_changed():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 85, "MAGAZIN", "B_EXCEPTIE_APL",
              "Suprafata 85 m2 nu depaseste pragul de 100 m2"]]))
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["success"] is True
    assert res["data"]["changed"] == 0
    # Un singur apel: cel care a listat unitatile. Niciun UPDATE, niciun
    # INSERT in jurnal, deci niciun commit.
    assert db.execute_query.call_count == 1
    db.connection.commit.assert_not_called()


# 5. O interogare esuata pentru tariful de depozit trebuie raportata cu
#    mesajul real al driverului, nu tratata tacut ca "niciun tarif".

def test_deposit_reports_a_failing_tariff_query_instead_of_no_tariff():
    from modules.sda.store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-00942"})
    with patch("modules.sda.store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is False
    assert "ORA-00942" in res["message"]


# 6. controller.save_unit foloseste _parse_partic_id, la fel ca restul
#    controlorului, in loc sa verifice doar prezenta.

def test_controller_rejects_a_non_numeric_partic_id_on_save_unit():
    from modules.sda.controller import SDAController
    res = SDAController.save_unit(
        {"partic_id": "abc", "denumire": "Magazin"}, "tester")
    assert res["success"] is False
    assert "partic_id" in res["message"]


# 7. Consola trebuie sa redirectioneze la /login pe 401, nu sa arate
#    banner-ul rusesc de autorizare pe o pagina fara sesiune.

def test_console_template_redirects_to_login_on_401():
    html = _template("sda.html")
    for marker in ("loadCompliance", "loadUnits", "fetchPartic"):
        section = html[html.index(f"async function {marker}"):]
        section = section[:section.index("\n}\n")]
        assert "status === 401" in section
        assert "/login" in section


# 8. Bifa HoReCa nu are voie sa fie oferita in interfata pentru un tip de
#    amplasament diferit de ALIMENTATIE_PUBLICA.

def test_console_template_disables_horeca_checkbox_outside_alimentatie_publica():
    html = _template("sda.html")
    assert "syncHorecaCheckbox" in html
    assert "ALIMENTATIE_PUBLICA" in html[html.index("function syncHorecaCheckbox"):]

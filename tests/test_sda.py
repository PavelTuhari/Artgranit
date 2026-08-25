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
    # REGIM_MOTIV este parte a comparației: reclasificarea rescrie și motivul,
    # deci „nimic nu s-a schimbat" înseamnă regim ȘI motiv identice.
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[1, 500, "MAGAZIN", "C_HORECA",
              "Unitate HoReCa: predare directa catre Administrator"]]),
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
    # Prima interogare este citirea regimului curent (HoReCa nu are coloană
    # proprie); ce contează aici este că unit_id == 0 duce la UPDATE, nu INSERT.
    db = _db_returning(_ok(["REGIM"], [["B_EXCEPTIE_APL"]]),
                       _ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"unit_id": 0, "partic_id": 1, "denumire": "Magazin 0",
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    statements = [c[0][0].strip() for c in db.execute_query.call_args_list]
    assert any(x.startswith("UPDATE SDA_UNIT") for x in statements)
    assert not any(x.startswith("INSERT INTO SDA_UNIT") for x in statements)


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


def test_get_units_rejects_a_non_numeric_partic_id():
    from controllers.sda_controller import SDAController
    res = SDAController.get_units({"partic_id": "abc"})
    assert res["success"] is False
    assert res["data"] is None
    assert "partic_id" in res["message"]


def test_get_compliance_rejects_a_non_numeric_partic_id():
    from controllers.sda_controller import SDAController
    res = SDAController.get_compliance({"partic_id": "abc"})
    assert res["success"] is False
    assert res["data"] is None
    assert "partic_id" in res["message"]


def test_get_units_with_no_partic_id_still_lists_everything():
    from controllers.sda_controller import SDAController
    db = _db_returning(_ok(["UNIT_ID", "DENUMIRE", "REGIM"],
                           [[1, "Magazin 12", "B_EXCEPTIE_APL"]]))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAController.get_units({})
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Magazin 12"


def test_get_units_with_a_string_partic_id_reaches_the_store_as_int():
    from controllers.sda_controller import SDAController
    from models.sda_oracle_store import SDAStore
    with patch.object(SDAStore, "list_units", return_value=_ok([], [])) as mock_list:
        SDAController.get_units({"partic_id": "7"})
    args, _kwargs = mock_list.call_args
    assert args[0] == 7
    assert isinstance(args[0], int)


def test_get_compliance_with_a_string_partic_id_reaches_the_store_as_int():
    from controllers.sda_controller import SDAController
    from models.sda_oracle_store import SDAStore
    with patch.object(SDAStore, "compliance_map",
                       return_value={"success": True, "data": {}, "message": ""}) as mock_map:
        SDAController.get_compliance({"partic_id": "7"})
    args, _kwargs = mock_map.call_args
    assert args[0] == 7
    assert isinstance(args[0], int)

# -- Task 7: interface ------------------------------------------------

def _template(name):
    with open(os.path.join(ROOT, "templates", name), encoding="utf-8") as fh:
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
    from models.sda_oracle_store import SDAStore
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
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["success"] is True
    d = res["data"]
    assert d["vandut_an_anterior"] == 412000
    for block in ("identificare", "contact", "unitati", "punct_preluare",
                  "modalitate_preluare", "vandut_an_anterior",
                  "estimare_an_curent", "exceptii"):
        assert block in d, block


def test_dossier_flags_units_that_still_have_no_regime():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin fara suprafata", "str. X", None, "MAGAZIN", None]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["incomplet"] == 1


# -- Final review: fixes for the blocking findings ---------------------

# 1. Fără commit, python-oracledb face rollback la închiderea conexiunii:
#    fiecare scriere a modulului s-ar fi pierdut în tăcere.

def test_log_commits_its_journal_entry():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        SDAStore.log("TEST", "SDA_UNIT", 1, "detalii", "tester")
    assert db.connection.commit.called


def test_saving_a_unit_commits_the_transaction():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit(
            {"partic_id": 1, "denumire": "Magazin 12", "suprafata_mp": 85,
             "tip_amplasament": "MAGAZIN"}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


def test_saving_a_pack_commits_the_transaction():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack({"ean": "4840012345678", "material": "STICLA",
                                  "volum_l": 0.75, "greutate_g": 380}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


def test_reclassify_all_commits_the_batch():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 500, "MAGAZIN", "B_EXCEPTIE_APL", "vechi"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["data"]["changed"] == 1
    # O dată pentru lot, o dată pentru intrarea de jurnal scrisă de SDAStore.log.
    assert db.connection.commit.called


def test_saving_a_participant_commits_the_transaction():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic(
            {"idno": "1003600000000", "denumire": "Rogob SRL"}, "tester")
    assert res["success"] is True
    assert db.connection.commit.call_count == 1


# 2. Participanți: fără ei nicio unitate nu poate exista (PARTIC_ID NOT NULL).

def test_list_partic_maps_rows_to_dicts():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["PARTIC_ID", "IDNO", "DENUMIRE"],
                           [[1, "1003600000000", "Rogob SRL"]]))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.list_partic()
    assert res["success"] is True
    assert res["data"][0]["denumire"] == "Rogob SRL"


def test_saving_a_new_participant_inserts_with_bind_variables():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        SDAStore.save_partic({"idno": "1003600000000", "denumire": "Rogob SRL",
                              "stare": "activ"}, "tester")
    sql, params = db.execute_query.call_args_list[0][0]
    assert sql.strip().startswith("INSERT INTO SDA_PARTIC")
    assert "'" not in sql.replace("''", "")
    assert params["stare"] == "ACTIV"
    assert "partic_id" not in params


def test_updating_a_missing_participant_is_reported_not_silently_ok():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic({"partic_id": 42, "idno": "100",
                                    "denumire": "X"}, "tester")
    assert res["success"] is False
    assert "42" in res["message"]
    db.connection.commit.assert_not_called()


def test_saving_a_participant_with_id_zero_updates_instead_of_inserting():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_partic({"partic_id": 0, "idno": "100",
                                    "denumire": "X"}, "tester")
    assert res["success"] is True
    assert db.execute_query.call_args_list[0][0][0].strip().startswith(
        "UPDATE SDA_PARTIC")


def test_controller_rejects_a_participant_without_a_name():
    from controllers.sda_controller import SDAController
    res = SDAController.save_partic({"idno": "1003"}, "tester")
    assert res["success"] is False
    assert "denumire" in res["message"].lower()


def test_controller_rejects_a_participant_without_an_idno():
    from controllers.sda_controller import SDAController
    res = SDAController.save_partic({"denumire": "Rogob SRL"}, "tester")
    assert res["success"] is False
    assert "idno" in res["message"].lower()


def test_controller_rejects_a_unit_without_a_participant():
    from controllers.sda_controller import SDAController
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
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["REGIM"], [["C_HORECA"]]),
                       _ok([], [], rowcount=1), _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
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
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        {"success": False, "columns": [], "data": [], "rowcount": 0,
         "message": "ORA-00942"},
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["success"] is False
    assert "ORA-00942" in res["message"]


def test_dossier_with_an_incomplete_unit_may_not_be_filed():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PARTIC_ID", "IDNO", "DENUMIRE", "CONTACT_NUME", "CONTACT_TEL",
             "CONTACT_EMAIL", "VANDUT_AN_ANT", "ESTIMARE_AN"],
            [[1, "1003", "Rogob SRL", "", "", "", None, None]]),
        _ok(["UNIT_ID", "DENUMIRE", "ADRESA", "SUPRAFATA_MP",
             "TIP_AMPLASAMENT", "REGIM"],
            [[1, "Magazin fara suprafata", "str. X", None, "MAGAZIN", None]]),
        _ok(["POINT_ID", "UNIT_ID", "ADRESA", "ORAR", "TIP"], []),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["poate_fi_depus"] is False
    # Fără puncte de preluare modalitatea este necunoscută, nu „MANUAL".
    assert res["data"]["modalitate_preluare"] == []


def test_dossier_without_incomplete_units_may_be_filed():
    from models.sda_oracle_store import SDAStore
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
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.registration_dossier(1)
    assert res["data"]["poate_fi_depus"] is True


# 6. Un UPDATE care nu a nimerit niciun rând nu este un succes.

def test_updating_a_missing_unit_is_reported_not_silently_ok():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok(["REGIM"], []), _ok([], [], rowcount=0))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_unit({"unit_id": 99, "partic_id": 1,
                                  "denumire": "Sters", "suprafata_mp": 50},
                                 "tester")
    assert res["success"] is False
    assert "99" in res["message"]
    db.connection.commit.assert_not_called()


def test_updating_a_missing_pack_is_reported_not_silently_ok():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(_ok([], [], rowcount=0))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.save_pack({"pack_id": 99, "ean": "484",
                                  "material": "STICLA", "volum_l": 0.5,
                                  "greutate_g": 300}, "tester")
    assert res["success"] is False
    assert "99" in res["message"]
    db.connection.commit.assert_not_called()


# 7. Întâi perioada, apoi categoria în interiorul ei.

def test_a_newer_wildcard_beats_an_older_exact_category():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["PACK_ID", "EAN", "CAT_ADMIN", "REUTILIZABIL"],
            [[7, "4840012345678", "f", "N"]]),
        # Perioada nouă (TARIFF_ID 2) publică doar '*'; cea veche are un 'f'
        # exact. Fără limitarea la perioada câștigătoare, 'f' ar învinge.
        _ok(["TARIFF_ID", "CATEGORIE", "METODA", "REUTILIZABIL", "VALOARE_LEI"],
            [[2, "*", None, None, 2.00], [1, "f", None, None, 1.00]]),
    )
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.deposit_for_ean("4840012345678")
    assert res["success"] is True
    assert res["data"]["valoare_lei"] == 2.00


# 8. Restul.

def test_reclassify_rewrites_a_unit_whose_reason_went_stale():
    from models.sda_oracle_store import SDAStore
    db = _db_returning(
        _ok(["UNIT_ID", "SUPRAFATA_MP", "TIP_AMPLASAMENT", "REGIM", "REGIM_MOTIV"],
            [[7, 85, "MAGAZIN", "B_EXCEPTIE_APL", "motiv vechi, suprafata 70 m2"]]),
        _ok([], [], rowcount=1),
        _ok([], [], rowcount=1))
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.reclassify_all("tester")
    assert res["data"]["changed"] == 1
    assert "85" in db.execute_query.call_args_list[1][0][1]["regim_motiv"]


def test_parse_partic_id_is_annotated_as_optional():
    import inspect
    from controllers import sda_controller
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
    from models import sda_rules
    assert sda_rules.prag_pentru("SUPERMARKET_VIITOR") == 100.0
    assert sda_rules.prag_pentru("") == 100.0
    assert sda_rules.prag_pentru(None) == 100.0
    regim, _motiv = sda_rules.classify_regime(120, "SUPERMARKET_VIITOR")
    assert regim == "A_PUNCT_PROPRIU"

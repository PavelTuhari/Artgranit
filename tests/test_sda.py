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

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


def test_deploy_script_installs_the_sda_ddl():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert '"117_sda_tables.sql"' in src

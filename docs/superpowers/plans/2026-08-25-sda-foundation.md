# SDA Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation of the SDA module — participants, units with automatic regime classification, the SD packaging registry, and period-versioned tariffs — so the client gets a working compliance map and a generated registration dossier.

**Architecture:** Normalized Oracle tables with prefix `SDA_` in the platform's cloud ADB, reached through `models.database.DatabaseModel` (thin mode), the same as AEI and Planograms. Pure business rules (regime thresholds, tariff category derivation, tariff lookup) live in `models/sda_rules.py` with no database dependency, so they are testable without a wallet. The storage layer `models/sda_oracle_store.py` knows SQL and nothing about HTTP; the controller knows HTTP and nothing about SQL. EAN data from the client's ERP (Oracle 11g OfficePlus) is read through the existing `models/biro26_db.py` worker and never written to.

**Tech Stack:** Python 3.12, Flask, Oracle (ADB for `SDA_*`, OfficePlus 11g read-only for nomenclature), python-oracledb thin, vanilla JS SPA template, pytest.

## Global Constraints

- Oracle prefix for every object of this module: `SDA_`. No generic runtime tables, no KV, no JSON blob as primary state.
- SQL comments and `COMMENT ON` text: **English only**. Cyrillic in DDL is rejected by the test suite (same rule as `sql/113_yseo_tables.sql`).
- Every FOREIGN KEY column gets its own index — enforced by test.
- Oracle 11g compatibility is NOT required for `SDA_*` (they live in the ADB), but the OfficePlus reads through `biro26_db` must stay 11g-safe: no `OFFSET/FETCH`, no `IDENTITY`, bind variables only.
- New tables use sequence + `BEFORE INSERT` trigger for identifiers, matching existing modules.
- All UI routes live under `/UNA.md/orasldev/sda…`. API routes under `/api/sda/…`.
- Store layer returns `{"success": bool, "data": ..., "message": str}`.
- Tests must run with no network and no wallet: DDL is verified by parsing the `.sql` files, Python by mocking `DatabaseModel`.
- Tariff values (deposit, administration, management) are never constants in code — always rows in `SDA_TARIFF_LINE` with a validity period.
- Do not touch `deploy_to_remote.sh`, the production venv, or the systemd unit.

---

### Task 1: DDL for the SDA schema

**Files:**
- Create: `sql/117_sda_tables.sql`
- Modify: `deploy_oracle_objects.py` (the `order` list, after `"112_plg_i18n_algos.sql"`)
- Test: `tests/test_sda.py`

**Interfaces:**
- Consumes: nothing.
- Produces: tables `SDA_PARTIC`, `SDA_PARTIC_ROL`, `SDA_UNIT`, `SDA_RETURN_POINT`, `SDA_RVM`, `SDA_PACK`, `SDA_PACK_SKU`, `SDA_TARIFF`, `SDA_TARIFF_LINE`, `SDA_EVENT_LOG`. Later tasks read and write these column names exactly as declared here.

- [ ] **Step 1: Write the failing test**

Create `tests/test_sda.py`:

```python
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
    fk_cols = set(re.findall(r"FOREIGN KEY \(([A-Z0-9_]+)\)", ddl))
    indexed = set()
    for cols in re.findall(r"CREATE INDEX [A-Z0-9_]+ ON [A-Z0-9_]+ \(([^)]+)\)", ddl):
        indexed.add(cols.split(",")[0].strip())
    for col in fk_cols:
        assert col in indexed, f"FK {col} without index"


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q`
Expected: FAIL — `FileNotFoundError: sql/117_sda_tables.sql`

- [ ] **Step 3: Write the DDL**

Create `sql/117_sda_tables.sql`. Structure for every table: `CREATE TABLE`, then its sequence, then its `BEFORE INSERT` trigger, then its indexes. Full content:

```sql
-- SDA module: deposit return system for beverage packaging (Moldova).
-- Legal basis: Law 209/2016 art. 54^1-54^4, DRS implementing regulation.
-- Prefix: SDA_. Target database: platform cloud ADB.

CREATE TABLE SDA_PARTIC (
  PARTIC_ID      NUMBER(12)      NOT NULL,
  IDNO           VARCHAR2(20)    NOT NULL,
  DENUMIRE       VARCHAR2(200)   NOT NULL,
  DATA_INREG     DATE,
  NR_CONTRACT    VARCHAR2(60),
  DATA_CONTRACT  DATE,
  CONTACT_NUME   VARCHAR2(120),
  CONTACT_TEL    VARCHAR2(40),
  CONTACT_EMAIL  VARCHAR2(120),
  STARE          VARCHAR2(20)    DEFAULT 'ACTIV' NOT NULL,
  -- Blocks 6 and 7 of the registration notification (pct. 78): units of
  -- SD packaging sold last year and forecast for the current year.
  VANDUT_AN_ANT  NUMBER(14),
  ESTIMARE_AN    NUMBER(14),
  CREATED_AT     DATE            DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_SDA_PARTIC PRIMARY KEY (PARTIC_ID),
  CONSTRAINT CK_SDA_PARTIC_STARE CHECK (STARE IN ('ACTIV','SUSPENDAT','INCHIS'))
);
CREATE SEQUENCE SEQ_SDA_PARTIC START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_PARTIC_BI BEFORE INSERT ON SDA_PARTIC FOR EACH ROW
BEGIN IF :NEW.PARTIC_ID IS NULL THEN SELECT SEQ_SDA_PARTIC.NEXTVAL INTO :NEW.PARTIC_ID FROM DUAL; END IF; END;
/
CREATE UNIQUE INDEX UX_SDA_PARTIC_IDNO ON SDA_PARTIC (IDNO);

-- One economic operator may hold several roles at once (regulation pct. 83).
CREATE TABLE SDA_PARTIC_ROL (
  ROL_ID     NUMBER(12)   NOT NULL,
  PARTIC_ID  NUMBER(12)   NOT NULL,
  ROL        VARCHAR2(10) NOT NULL,
  ACTIV_DIN  DATE         DEFAULT SYSDATE NOT NULL,
  ACTIV_PANA DATE,
  CONSTRAINT PK_SDA_PARTIC_ROL PRIMARY KEY (ROL_ID),
  CONSTRAINT FK_SDA_PARTIC_ROL_P FOREIGN KEY (PARTIC_ID) REFERENCES SDA_PARTIC (PARTIC_ID),
  CONSTRAINT CK_SDA_PARTIC_ROL CHECK (ROL IN ('PROD','COM','HORECA','DISTR','APL','ADMIN'))
);
CREATE SEQUENCE SEQ_SDA_PARTIC_ROL START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_PARTIC_ROL_BI BEFORE INSERT ON SDA_PARTIC_ROL FOR EACH ROW
BEGIN IF :NEW.ROL_ID IS NULL THEN SELECT SEQ_SDA_PARTIC_ROL.NEXTVAL INTO :NEW.ROL_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_PARTIC_ROL_P ON SDA_PARTIC_ROL (PARTIC_ID);

-- Retail units. SUPRAFATA_MP and TIP_AMPLASAMENT decide REGIM (pct. 93, 97).
CREATE TABLE SDA_UNIT (
  UNIT_ID          NUMBER(12)     NOT NULL,
  PARTIC_ID        NUMBER(12)     NOT NULL,
  COD_ERP          VARCHAR2(40),
  DENUMIRE         VARCHAR2(200)  NOT NULL,
  ADRESA           VARCHAR2(300),
  LOCALITATE       VARCHAR2(120),
  RAION            VARCHAR2(120),
  SUPRAFATA_MP     NUMBER(10,2),
  TIP_AMPLASAMENT  VARCHAR2(24)   DEFAULT 'MAGAZIN' NOT NULL,
  REGIM            VARCHAR2(20),
  REGIM_MOTIV      VARCHAR2(300),
  DATA_EVALUARE    DATE,
  CREATED_AT       DATE           DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_SDA_UNIT PRIMARY KEY (UNIT_ID),
  CONSTRAINT FK_SDA_UNIT_P FOREIGN KEY (PARTIC_ID) REFERENCES SDA_PARTIC (PARTIC_ID),
  CONSTRAINT CK_SDA_UNIT_TIP CHECK (TIP_AMPLASAMENT IN
    ('MAGAZIN','TARABA','CHIOSC','BENZINARIE','ALIMENTATIE_PUBLICA')),
  CONSTRAINT CK_SDA_UNIT_REGIM CHECK (REGIM IN
    ('A_PUNCT_PROPRIU','B_EXCEPTIE_APL','C_HORECA')),
  CONSTRAINT CK_SDA_UNIT_SUPRAF CHECK (SUPRAFATA_MP IS NULL OR SUPRAFATA_MP > 0)
);
CREATE SEQUENCE SEQ_SDA_UNIT START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_UNIT_BI BEFORE INSERT ON SDA_UNIT FOR EACH ROW
BEGIN IF :NEW.UNIT_ID IS NULL THEN SELECT SEQ_SDA_UNIT.NEXTVAL INTO :NEW.UNIT_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_UNIT_P ON SDA_UNIT (PARTIC_ID);
CREATE INDEX IX_SDA_UNIT_REGIM ON SDA_UNIT (REGIM);

-- Return points. The 150 m limit and the opening hours come from pct. 85.
CREATE TABLE SDA_RETURN_POINT (
  POINT_ID            NUMBER(12)    NOT NULL,
  UNIT_ID             NUMBER(12)    NOT NULL,
  TIP                 VARCHAR2(10)  DEFAULT 'MANUAL' NOT NULL,
  ADRESA              VARCHAR2(300),
  DISTANTA_M          NUMBER(6)     DEFAULT 0 NOT NULL,
  ORAR                VARCHAR2(200),
  PARTENER_APL        VARCHAR2(200),
  RESPONSABIL_NUME    VARCHAR2(120),
  RESPONSABIL_CONTACT VARCHAR2(120),
  ACTIV_DIN           DATE,
  ACTIV_PANA          DATE,
  CONSTRAINT PK_SDA_RETURN_POINT PRIMARY KEY (POINT_ID),
  CONSTRAINT FK_SDA_RETURN_POINT_U FOREIGN KEY (UNIT_ID) REFERENCES SDA_UNIT (UNIT_ID),
  CONSTRAINT CK_SDA_RP_TIP CHECK (TIP IN ('MANUAL','AUTOMAT','MIXT')),
  CONSTRAINT CK_SDA_RP_DIST CHECK (DISTANTA_M BETWEEN 0 AND 150)
);
CREATE SEQUENCE SEQ_SDA_RETURN_POINT START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_RETURN_POINT_BI BEFORE INSERT ON SDA_RETURN_POINT FOR EACH ROW
BEGIN IF :NEW.POINT_ID IS NULL THEN SELECT SEQ_SDA_RETURN_POINT.NEXTVAL INTO :NEW.POINT_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_RETURN_POINT_U ON SDA_RETURN_POINT (UNIT_ID);

-- Reverse vending machines. PROPRIETAR affects the management tariff (pct. 14.14 j).
CREATE TABLE SDA_RVM (
  RVM_ID          NUMBER(12)    NOT NULL,
  POINT_ID        NUMBER(12)    NOT NULL,
  MODEL           VARCHAR2(120),
  SERIA           VARCHAR2(60),
  PROPRIETAR      VARCHAR2(20)  DEFAULT 'COMERCIANT' NOT NULL,
  DATA_INSTALARE  DATE,
  STARE           VARCHAR2(20)  DEFAULT 'ACTIV' NOT NULL,
  ULTIM_HEARTBEAT DATE,
  CONSTRAINT PK_SDA_RVM PRIMARY KEY (RVM_ID),
  CONSTRAINT FK_SDA_RVM_PT FOREIGN KEY (POINT_ID) REFERENCES SDA_RETURN_POINT (POINT_ID),
  CONSTRAINT CK_SDA_RVM_PROP CHECK (PROPRIETAR IN ('COMERCIANT','ADMINISTRATOR')),
  CONSTRAINT CK_SDA_RVM_STARE CHECK (STARE IN ('ACTIV','DEFECT','DEMONTAT'))
);
CREATE SEQUENCE SEQ_SDA_RVM START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_RVM_BI BEFORE INSERT ON SDA_RVM FOR EACH ROW
BEGIN IF :NEW.RVM_ID IS NULL THEN SELECT SEQ_SDA_RVM.NEXTVAL INTO :NEW.RVM_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_RVM_PT ON SDA_RVM (POINT_ID);

-- Registry of SD packaging (pct. 14.12). EAN is the key of the whole module.
CREATE TABLE SDA_PACK (
  PACK_ID       NUMBER(12)    NOT NULL,
  EAN           VARCHAR2(20)  NOT NULL,
  DENUMIRE      VARCHAR2(200),
  PRODUCATOR    VARCHAR2(200),
  MATERIAL      VARCHAR2(10)  NOT NULL,
  CULOARE       VARCHAR2(20),
  BARIERA_O2    CHAR(1)       DEFAULT 'N' NOT NULL,
  REUTILIZABIL  CHAR(1)       DEFAULT 'N' NOT NULL,
  VOLUM_L       NUMBER(6,3)   NOT NULL,
  GREUTATE_G    NUMBER(8,2)   NOT NULL,
  CAT_ADMIN     CHAR(1),
  CAT_GEST      CHAR(1),
  SURSA         VARCHAR2(20)  DEFAULT 'MANUAL' NOT NULL,
  ACTIV_DIN     DATE,
  ACTIV_PANA    DATE,
  CREATED_AT    DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_SDA_PACK PRIMARY KEY (PACK_ID),
  CONSTRAINT CK_SDA_PACK_MAT CHECK (MATERIAL IN ('PLASTIC','STICLA','METAL')),
  CONSTRAINT CK_SDA_PACK_REUT CHECK (REUTILIZABIL IN ('D','N')),
  CONSTRAINT CK_SDA_PACK_BAR CHECK (BARIERA_O2 IN ('D','N')),
  CONSTRAINT CK_SDA_PACK_SURSA CHECK (SURSA IN ('MANUAL','ADMIN_REGISTRU','IMPORT')),
  CONSTRAINT CK_SDA_PACK_VOL CHECK (VOLUM_L >= 0.1 AND VOLUM_L <= 3),
  CONSTRAINT CK_SDA_PACK_GREU CHECK (GREUTATE_G > 0)
);
CREATE SEQUENCE SEQ_SDA_PACK START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_PACK_BI BEFORE INSERT ON SDA_PACK FOR EACH ROW
BEGIN IF :NEW.PACK_ID IS NULL THEN SELECT SEQ_SDA_PACK.NEXTVAL INTO :NEW.PACK_ID FROM DUAL; END IF; END;
/
CREATE UNIQUE INDEX UX_SDA_PACK_EAN ON SDA_PACK (EAN);

-- Bridge to the ERP nomenclature. COD_MPT is the OfficePlus item code.
CREATE TABLE SDA_PACK_SKU (
  SKU_ID     NUMBER(12)    NOT NULL,
  PACK_ID    NUMBER(12)    NOT NULL,
  COD_MPT    VARCHAR2(40)  NOT NULL,
  EAN_SURSA  VARCHAR2(20),
  CREATED_AT DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_SDA_PACK_SKU PRIMARY KEY (SKU_ID),
  CONSTRAINT FK_SDA_PACK_SKU_P FOREIGN KEY (PACK_ID) REFERENCES SDA_PACK (PACK_ID)
);
CREATE SEQUENCE SEQ_SDA_PACK_SKU START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_PACK_SKU_BI BEFORE INSERT ON SDA_PACK_SKU FOR EACH ROW
BEGIN IF :NEW.SKU_ID IS NULL THEN SELECT SEQ_SDA_PACK_SKU.NEXTVAL INTO :NEW.SKU_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_PACK_SKU_P ON SDA_PACK_SKU (PACK_ID);
CREATE INDEX IX_SDA_PACK_SKU_COD ON SDA_PACK_SKU (COD_MPT);

-- Tariff periods. The law fixes none of these values: they arrive by
-- ministerial order and by the Administrator's financing scheme.
CREATE TABLE SDA_TARIFF (
  TARIFF_ID     NUMBER(12)    NOT NULL,
  TIP           VARCHAR2(10)  NOT NULL,
  DATA_START    DATE          NOT NULL,
  DATA_END      DATE,
  ACT_NORMATIV  VARCHAR2(200),
  OBS           VARCHAR2(400),
  CREATED_AT    DATE          DEFAULT SYSDATE NOT NULL,
  CONSTRAINT PK_SDA_TARIFF PRIMARY KEY (TARIFF_ID),
  CONSTRAINT CK_SDA_TARIFF_TIP CHECK (TIP IN ('DEPOZIT','ADMIN','GESTIUNE')),
  CONSTRAINT CK_SDA_TARIFF_PER CHECK (DATA_END IS NULL OR DATA_END >= DATA_START)
);
CREATE SEQUENCE SEQ_SDA_TARIFF START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_TARIFF_BI BEFORE INSERT ON SDA_TARIFF FOR EACH ROW
BEGIN IF :NEW.TARIFF_ID IS NULL THEN SELECT SEQ_SDA_TARIFF.NEXTVAL INTO :NEW.TARIFF_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_TARIFF_TIP ON SDA_TARIFF (TIP, DATA_START);

CREATE TABLE SDA_TARIFF_LINE (
  LINE_ID      NUMBER(12)   NOT NULL,
  TARIFF_ID    NUMBER(12)   NOT NULL,
  CATEGORIE    VARCHAR2(2)  DEFAULT '*' NOT NULL,
  METODA       VARCHAR2(10),
  REUTILIZABIL CHAR(1),
  VALOARE_LEI  NUMBER(10,4) NOT NULL,
  CONSTRAINT PK_SDA_TARIFF_LINE PRIMARY KEY (LINE_ID),
  CONSTRAINT FK_SDA_TARIFF_LINE_T FOREIGN KEY (TARIFF_ID) REFERENCES SDA_TARIFF (TARIFF_ID),
  CONSTRAINT CK_SDA_TL_METODA CHECK (METODA IS NULL OR METODA IN ('MANUAL','AUTOMAT')),
  CONSTRAINT CK_SDA_TL_VAL CHECK (VALOARE_LEI >= 0)
);
CREATE SEQUENCE SEQ_SDA_TARIFF_LINE START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_TARIFF_LINE_BI BEFORE INSERT ON SDA_TARIFF_LINE FOR EACH ROW
BEGIN IF :NEW.LINE_ID IS NULL THEN SELECT SEQ_SDA_TARIFF_LINE.NEXTVAL INTO :NEW.LINE_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_TARIFF_LINE_T ON SDA_TARIFF_LINE (TARIFF_ID);

-- Append-only journal of the module. Never a shared container.
CREATE TABLE SDA_EVENT_LOG (
  EVENT_ID    NUMBER(12)     NOT NULL,
  EVENT_DATE  DATE           DEFAULT SYSDATE NOT NULL,
  TIP         VARCHAR2(40)   NOT NULL,
  ENTITATE    VARCHAR2(40),
  ENTITATE_ID NUMBER(12),
  UTILIZATOR  VARCHAR2(120),
  DETALII     VARCHAR2(1000),
  CONSTRAINT PK_SDA_EVENT_LOG PRIMARY KEY (EVENT_ID)
);
CREATE SEQUENCE SEQ_SDA_EVENT_LOG START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE OR REPLACE TRIGGER TRG_SDA_EVENT_LOG_BI BEFORE INSERT ON SDA_EVENT_LOG FOR EACH ROW
BEGIN IF :NEW.EVENT_ID IS NULL THEN SELECT SEQ_SDA_EVENT_LOG.NEXTVAL INTO :NEW.EVENT_ID FROM DUAL; END IF; END;
/
CREATE INDEX IX_SDA_EVENT_LOG_D ON SDA_EVENT_LOG (EVENT_DATE);
```

- [ ] **Step 4: Register the file in the deploy script**

In `deploy_oracle_objects.py`, add `"117_sda_tables.sql",` to the `order` list immediately after `"112_plg_i18n_algos.sql",` (before the SEOForge comment block).

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 9 tests.

- [ ] **Step 6: Commit**

```bash
git add sql/117_sda_tables.sql deploy_oracle_objects.py tests/test_sda.py
git commit -m "feat(sda): схема SDA_* — участники, сеть, реестр упаковки, тарифы"
```

---

### Task 2: Regime classification and tariff categories (pure rules)

**Files:**
- Create: `models/sda_rules.py`
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: nothing from Task 1 at runtime — this module has no database import.
- Produces:
  - `classify_regime(suprafata_mp: float | None, tip_amplasament: str, is_horeca: bool = False) -> tuple[str | None, str]` returning `(regim, motiv)` where `regim` is `'A_PUNCT_PROPRIU'`, `'B_EXCEPTIE_APL'`, `'C_HORECA'` or `None`.
  - `admin_category(material: str, culoare: str | None, bariera_o2: str, volum_l: float) -> str` returning one of `'a'…'g'`.
  - `gest_category(material: str, volum_l: float) -> str` returning one of `'a'…'e'`.
  - `PRAG_STANDARD_MP = 100.0`, `PRAG_SPECIAL_MP = 150.0`, `TIPURI_PRAG_SPECIAL = frozenset(...)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "regime or categor or threshold or barrier or horeca or surface or kiosk or petrol"`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.sda_rules'`

- [ ] **Step 3: Write the implementation**

Create `models/sda_rules.py`:

```python
"""SDA — чистые правила модуля: порог площади и тарифные категории.

Здесь нет ни базы, ни HTTP, ни настроек. Это сделано намеренно: порог
освобождения магазина решает, нужен ли сети пункт возврата, и такую
величину нельзя проверять только через живую базу.

Пороги: 100 м² для обычного магазина, 150 м² для тарабы на рынке,
киоска, заправки и заведения общественного питания (пункты 93 и 97
регламента). Граница включительна: «suprafață care nu depășește 100 m²»
означает, что ровно 100 попадают в исключение.
"""
from __future__ import annotations

from typing import Optional, Tuple

PRAG_STANDARD_MP = 100.0
PRAG_SPECIAL_MP = 150.0

TIPURI_PRAG_SPECIAL = frozenset({
    "TARABA", "CHIOSC", "BENZINARIE", "ALIMENTATIE_PUBLICA",
})

REGIM_PROPRIU = "A_PUNCT_PROPRIU"
REGIM_EXCEPTIE = "B_EXCEPTIE_APL"
REGIM_HORECA = "C_HORECA"

CULORI_SIMPLE = frozenset({"ALBASTRU", "VERDE", "MARO"})


def prag_pentru(tip_amplasament: str) -> float:
    """Порог площади для этого типа точки."""
    return (PRAG_SPECIAL_MP
            if (tip_amplasament or "").upper() in TIPURI_PRAG_SPECIAL
            else PRAG_STANDARD_MP)


def classify_regime(suprafata_mp: Optional[float],
                    tip_amplasament: str,
                    is_horeca: bool = False) -> Tuple[Optional[str], str]:
    """Режим точки и человекочитаемое обоснование.

    Возвращает (regim, motiv). Без площади режим не назначается: молча
    подставить один из двух — значит однажды подставить неверный.
    """
    if is_horeca:
        return REGIM_HORECA, "Unitate HoReCa: predare directa catre Administrator"

    if suprafata_mp is None:
        return None, "Suprafata comerciala nu este cunoscuta - inventar necesar"

    prag = prag_pentru(tip_amplasament)
    if suprafata_mp <= prag:
        return REGIM_EXCEPTIE, (
            f"Suprafata {suprafata_mp:g} m2 nu depaseste pragul de {prag:g} m2"
        )
    return REGIM_PROPRIU, (
        f"Suprafata {suprafata_mp:g} m2 depaseste pragul de {prag:g} m2"
    )


def admin_category(material: str, culoare: Optional[str],
                   bariera_o2: str, volum_l: float) -> str:
    """Категория тарифа администрирования, a..g (пункт 14.13)."""
    material = (material or "").upper()
    if material == "METAL":
        return "e"
    if material == "STICLA":
        return "f" if volum_l > 0.5 else "g"

    # Пластик. Барьер по кислороду перекрывает цвет.
    if (bariera_o2 or "N").upper() == "D":
        return "d"
    culoare = (culoare or "").upper()
    if culoare == "TRANSPARENT":
        return "a"
    if culoare in CULORI_SIMPLE:
        return "b"
    return "c"


def gest_category(material: str, volum_l: float) -> str:
    """Категория тарифа обработки, a..e (пункт 14.14)."""
    material = (material or "").upper()
    if material == "METAL":
        return "c"
    if material == "STICLA":
        return "d" if volum_l > 0.5 else "e"
    return "a" if volum_l <= 1.0 else "b"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 18 tests.

- [ ] **Step 5: Commit**

```bash
git add models/sda_rules.py tests/test_sda.py
git commit -m "feat(sda): порог площади и тарифные категории отдельным чистым модулем"
```

---

### Task 3: Tariff lookup with period validation

**Files:**
- Modify: `models/sda_rules.py`
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: `models.sda_rules` from Task 2.
- Produces:
  - `validate_periods(periods: list[dict]) -> list[str]` — returns a list of human-readable problems; empty list means valid. Each period is `{"tariff_id": int, "tip": str, "data_start": date, "data_end": date | None}`.
  - `pick_value(lines: list[dict], categorie: str, metoda: str | None = None, reutilizabil: str | None = None) -> float | None` — chooses the matching line from one tariff period. Each line is `{"categorie": str, "metoda": str | None, "reutilizabil": str | None, "valoare_lei": float}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "period or pick_value"`
Expected: FAIL — `AttributeError: module 'models.sda_rules' has no attribute 'validate_periods'`

- [ ] **Step 3: Write the implementation**

Append to `models/sda_rules.py`:

```python
# ── периоды тарифов ──────────────────────────────────────────────────
#
# Тарифы живут периодами, как цены в OfficePlus. Дыра в периодах — это
# день, за который систему нечем посчитать; наложение — день, за который
# посчитать можно двумя способами. Обе ошибки видны только на границе,
# поэтому их ищет отдельная проверка, а не глаз оператора.

from datetime import timedelta   # noqa: E402  (рядом с использованием)


def validate_periods(periods):
    """Список проблем в наборе периодов. Пустой список — всё в порядке."""
    problems = []
    by_type = {}
    for p in periods:
        by_type.setdefault(p["tip"], []).append(p)

    for tip, group in by_type.items():
        group = sorted(group, key=lambda p: p["data_start"])
        for prev, curr in zip(group, group[1:]):
            if prev["data_end"] is None:
                problems.append(
                    f"{tip}: perioada {prev['tariff_id']} este deschisa si "
                    f"se suprapune cu perioada {curr['tariff_id']}")
                continue
            if prev["data_end"] >= curr["data_start"]:
                problems.append(
                    f"{tip}: perioadele {prev['tariff_id']} si "
                    f"{curr['tariff_id']} se suprapun")
            elif prev["data_end"] + timedelta(days=1) < curr["data_start"]:
                problems.append(
                    f"{tip}: gol intre perioadele {prev['tariff_id']} si "
                    f"{curr['tariff_id']}")
    return problems


def pick_value(lines, categorie, metoda=None, reutilizabil=None):
    """Значение тарифа для категории. None — если строки нет.

    Точное совпадение важнее подстановочной категории `*`: последняя
    нужна для депозита, у которого категорий нет вовсе.
    """
    def matches(line, cat):
        if line.get("categorie") != cat:
            return False
        if line.get("metoda") is not None and metoda is not None \
                and line["metoda"] != metoda:
            return False
        if line.get("reutilizabil") is not None and reutilizabil is not None \
                and line["reutilizabil"] != reutilizabil:
            return False
        if line.get("metoda") is not None and metoda is None:
            return False
        return True

    for cat in (categorie, "*"):
        for line in lines:
            if matches(line, cat):
                return line["valoare_lei"]
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 26 tests.

- [ ] **Step 5: Commit**

```bash
git add models/sda_rules.py tests/test_sda.py
git commit -m "feat(sda): периоды тарифов — проверка стыков и выбор значения"
```

---

### Task 4: Oracle store for participants, units and the compliance map

**Files:**
- Create: `models/sda_oracle_store.py`
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: tables from Task 1, `classify_regime` from Task 2.
- Produces class `SDAStore` with static methods:
  - `list_units(partic_id: int | None = None, regim: str | None = None) -> dict`
  - `save_unit(payload: dict, username: str) -> dict` — inserts when `payload` has no `unit_id`, updates otherwise; always recomputes `REGIM`, `REGIM_MOTIV`, `DATA_EVALUARE`.
  - `reclassify_all(username: str) -> dict` — recomputes the regime of every unit, returns `{"changed": int}` in `data`.
  - `compliance_map(partic_id: int | None = None) -> dict` — returns `{"total": int, "by_regime": {...}, "unknown": int}`.
  - `log(tip: str, entitate: str, entitate_id, detalii: str, username: str) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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


def test_store_reports_failure_instead_of_raising():
    from models.sda_oracle_store import SDAStore
    db = _db_returning({"success": False, "columns": [], "data": [],
                        "rowcount": 0, "message": "ORA-00942"})
    with patch("models.sda_oracle_store.DatabaseModel", return_value=db):
        res = SDAStore.list_units()
    assert res["success"] is False
    assert "ORA-00942" in res["message"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "units or regime or compliance or failure"`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.sda_oracle_store'`

- [ ] **Step 3: Write the implementation**

Create `models/sda_oracle_store.py`:

```python
"""SDA — хранилище модуля поверх таблиц SDA_* в облачной базе портала.

Слой знает про SQL и ничего не знает про HTTP. Наружу отдаёт контракт
портала: {"success": bool, "data": ..., "message": str}.

Режим точки здесь не принимают на веру из формы: он всегда считается
заново функцией sda_rules.classify_regime и сохраняется вместе с датой
оценки. Иначе оператор однажды впишет «исключение» магазину в 300 м²,
и это всплывёт при проверке, а не при вводе.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel
from models import sda_rules


def _rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


class SDAStore:
    """Все обращения к Oracle для модуля SDA."""

    # ── журнал ──────────────────────────────────────────────────────

    @staticmethod
    def log(tip: str, entitate: str, entitate_id, detalii: str,
            username: str) -> None:
        with DatabaseModel() as db:
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES (:tip, :entitate, :entitate_id, "
                ":utilizator, :detalii)",
                {"tip": tip, "entitate": entitate, "entitate_id": entitate_id,
                 "utilizator": username, "detalii": (detalii or "")[:1000]})

    # ── сеть ────────────────────────────────────────────────────────

    @staticmethod
    def list_units(partic_id: Optional[int] = None,
                   regim: Optional[str] = None) -> Dict[str, Any]:
        sql = ("SELECT UNIT_ID, PARTIC_ID, COD_ERP, DENUMIRE, ADRESA, "
               "LOCALITATE, RAION, SUPRAFATA_MP, TIP_AMPLASAMENT, REGIM, "
               "REGIM_MOTIV, DATA_EVALUARE FROM SDA_UNIT WHERE 1=1")
        params: Dict[str, Any] = {}
        if partic_id is not None:
            sql += " AND PARTIC_ID = :partic_id"
            params["partic_id"] = partic_id
        if regim:
            sql += " AND REGIM = :regim"
            params["regim"] = regim
        sql += " ORDER BY DENUMIRE"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la citirea unitatilor")
        return _done(_rows(r))

    @staticmethod
    def save_unit(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        suprafata = payload.get("suprafata_mp")
        suprafata = float(suprafata) if suprafata not in (None, "") else None
        tip = (payload.get("tip_amplasament") or "MAGAZIN").upper()
        regim, motiv = sda_rules.classify_regime(
            suprafata, tip, bool(payload.get("is_horeca")))

        params = {
            "unit_id": payload.get("unit_id"),
            "partic_id": payload.get("partic_id"),
            "cod_erp": payload.get("cod_erp"),
            "denumire": payload.get("denumire"),
            "adresa": payload.get("adresa"),
            "localitate": payload.get("localitate"),
            "raion": payload.get("raion"),
            "suprafata_mp": suprafata,
            "tip_amplasament": tip,
            "regim": regim,
            "regim_motiv": motiv,
            "data_evaluare": date.today(),
        }

        if payload.get("unit_id"):
            sql = ("UPDATE SDA_UNIT SET COD_ERP = :cod_erp, "
                   "DENUMIRE = :denumire, ADRESA = :adresa, "
                   "LOCALITATE = :localitate, RAION = :raion, "
                   "SUPRAFATA_MP = :suprafata_mp, "
                   "TIP_AMPLASAMENT = :tip_amplasament, REGIM = :regim, "
                   "REGIM_MOTIV = :regim_motiv, "
                   "DATA_EVALUARE = :data_evaluare, PARTIC_ID = :partic_id "
                   "WHERE UNIT_ID = :unit_id")
        else:
            params.pop("unit_id")
            sql = ("INSERT INTO SDA_UNIT (PARTIC_ID, COD_ERP, DENUMIRE, "
                   "ADRESA, LOCALITATE, RAION, SUPRAFATA_MP, "
                   "TIP_AMPLASAMENT, REGIM, REGIM_MOTIV, DATA_EVALUARE) "
                   "VALUES (:partic_id, :cod_erp, :denumire, :adresa, "
                   ":localitate, :raion, :suprafata_mp, :tip_amplasament, "
                   ":regim, :regim_motiv, :data_evaluare)")

        with DatabaseModel() as db:
            r = db.execute_query(sql, params)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la salvarea unitatii")
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('UNIT_SAVE', 'SDA_UNIT', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": payload.get("unit_id"),
                 "utilizator": username,
                 "detalii": f"{payload.get('denumire')} -> {regim or 'FARA REGIM'}"})
        return _done({"regim": regim, "regim_motiv": motiv})

    @staticmethod
    def reclassify_all(username: str) -> Dict[str, Any]:
        listed = SDAStore.list_units()
        if not listed["success"]:
            return listed
        changed = 0
        for unit in listed["data"]:
            regim, motiv = sda_rules.classify_regime(
                unit.get("suprafata_mp"), unit.get("tip_amplasament") or "MAGAZIN")
            if regim == unit.get("regim"):
                continue
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE SDA_UNIT SET REGIM = :regim, "
                    "REGIM_MOTIV = :regim_motiv, DATA_EVALUARE = :data_evaluare "
                    "WHERE UNIT_ID = :unit_id",
                    {"regim": regim, "regim_motiv": motiv,
                     "data_evaluare": date.today(), "unit_id": unit["unit_id"]})
            changed += 1
        SDAStore.log("RECLASSIFY", "SDA_UNIT", None,
                     f"reclasificate {changed} unitati", username)
        return _done({"changed": changed})

    @staticmethod
    def compliance_map(partic_id: Optional[int] = None) -> Dict[str, Any]:
        sql = ("SELECT REGIM, COUNT(*) AS N FROM SDA_UNIT WHERE 1=1")
        params: Dict[str, Any] = {}
        if partic_id is not None:
            sql += " AND PARTIC_ID = :partic_id"
            params["partic_id"] = partic_id
        sql += " GROUP BY REGIM"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la harta de conformitate")

        by_regime: Dict[str, int] = {}
        unknown = 0
        total = 0
        for row in _rows(r):
            n = int(row["n"])
            total += n
            if row["regim"]:
                by_regime[row["regim"]] = n
            else:
                unknown += n
        return _done({"total": total, "by_regime": by_regime, "unknown": unknown})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 31 tests.

- [ ] **Step 5: Commit**

```bash
git add models/sda_oracle_store.py tests/test_sda.py
git commit -m "feat(sda): хранилище сети — режим точки считается, а не вводится"
```

---

### Task 5: Packaging registry store and ERP beverage gap report

**Files:**
- Modify: `models/sda_oracle_store.py`
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: `SDAStore` from Task 4, `admin_category` / `gest_category` from Task 2.
- Produces on `SDAStore`:
  - `list_packs(search: str | None = None) -> dict`
  - `save_pack(payload: dict, username: str) -> dict` — always recomputes `CAT_ADMIN` and `CAT_GEST`.
  - `deposit_for_ean(ean: str, on_date: date | None = None) -> dict` — returns `{"ean", "pack_id", "valoare_lei"}` or `success=False` when the EAN is unknown.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "pack or deposit or ean"`
Expected: FAIL — `AttributeError: type object 'SDAStore' has no attribute 'save_pack'`

- [ ] **Step 3: Write the implementation**

Append these methods inside `class SDAStore` in `models/sda_oracle_store.py`:

```python
    # ── реестр упаковки ─────────────────────────────────────────────

    @staticmethod
    def list_packs(search: Optional[str] = None) -> Dict[str, Any]:
        sql = ("SELECT PACK_ID, EAN, DENUMIRE, PRODUCATOR, MATERIAL, CULOARE, "
               "BARIERA_O2, REUTILIZABIL, VOLUM_L, GREUTATE_G, CAT_ADMIN, "
               "CAT_GEST, SURSA FROM SDA_PACK WHERE 1=1")
        params: Dict[str, Any] = {}
        if search:
            sql += " AND (UPPER(DENUMIRE) LIKE :q OR EAN LIKE :q)"
            params["q"] = f"%{search.upper()}%"
        sql += " ORDER BY DENUMIRE"

        with DatabaseModel() as db:
            r = db.execute_query(sql, params or None)
        if not r.get("success"):
            return _fail(r.get("message") or "Eroare la citirea registrului")
        return _done(_rows(r))

    @staticmethod
    def save_pack(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        material = (payload.get("material") or "").upper()
        volum = float(payload.get("volum_l") or 0)
        params = {
            "pack_id": payload.get("pack_id"),
            "ean": payload.get("ean"),
            "denumire": payload.get("denumire"),
            "producator": payload.get("producator"),
            "material": material,
            "culoare": (payload.get("culoare") or None),
            "bariera_o2": (payload.get("bariera_o2") or "N").upper(),
            "reutilizabil": (payload.get("reutilizabil") or "N").upper(),
            "volum_l": volum,
            "greutate_g": float(payload.get("greutate_g") or 0),
            "cat_admin": sda_rules.admin_category(
                material, payload.get("culoare"),
                (payload.get("bariera_o2") or "N"), volum),
            "cat_gest": sda_rules.gest_category(material, volum),
            "sursa": (payload.get("sursa") or "MANUAL").upper(),
        }

        if payload.get("pack_id"):
            sql = ("UPDATE SDA_PACK SET EAN = :ean, DENUMIRE = :denumire, "
                   "PRODUCATOR = :producator, MATERIAL = :material, "
                   "CULOARE = :culoare, BARIERA_O2 = :bariera_o2, "
                   "REUTILIZABIL = :reutilizabil, VOLUM_L = :volum_l, "
                   "GREUTATE_G = :greutate_g, CAT_ADMIN = :cat_admin, "
                   "CAT_GEST = :cat_gest, SURSA = :sursa "
                   "WHERE PACK_ID = :pack_id")
        else:
            params.pop("pack_id")
            sql = ("INSERT INTO SDA_PACK (EAN, DENUMIRE, PRODUCATOR, MATERIAL, "
                   "CULOARE, BARIERA_O2, REUTILIZABIL, VOLUM_L, GREUTATE_G, "
                   "CAT_ADMIN, CAT_GEST, SURSA) VALUES (:ean, :denumire, "
                   ":producator, :material, :culoare, :bariera_o2, "
                   ":reutilizabil, :volum_l, :greutate_g, :cat_admin, "
                   ":cat_gest, :sursa)")

        with DatabaseModel() as db:
            r = db.execute_query(sql, params)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la salvarea ambalajului")
            db.execute_query(
                "INSERT INTO SDA_EVENT_LOG (TIP, ENTITATE, ENTITATE_ID, "
                "UTILIZATOR, DETALII) VALUES ('PACK_SAVE', 'SDA_PACK', "
                ":entitate_id, :utilizator, :detalii)",
                {"entitate_id": payload.get("pack_id"), "utilizator": username,
                 "detalii": f"{params['ean']} {params['cat_admin']}/{params['cat_gest']}"})
        return _done({"cat_admin": params["cat_admin"],
                      "cat_gest": params["cat_gest"]})

    @staticmethod
    def deposit_for_ean(ean: str, on_date: Optional[date] = None) -> Dict[str, Any]:
        """Величина депозита для штрихкода на дату.

        Неизвестный EAN — это ошибка, а не ноль. Молчаливый ноль означал бы,
        что сеть недобирает депозит и обнаруживает это при сверке.
        """
        on_date = on_date or date.today()
        with DatabaseModel() as db:
            r = db.execute_query(
                "SELECT PACK_ID, EAN, CAT_ADMIN, REUTILIZABIL FROM SDA_PACK "
                "WHERE EAN = :ean", {"ean": ean})
            packs = _rows(r)
            if not r.get("success"):
                return _fail(r.get("message") or "Eroare la citirea registrului")
            if not packs:
                return _fail(f"EAN {ean} nu exista in registrul ambalajelor SD")

            t = db.execute_query(
                "SELECT L.CATEGORIE, L.METODA, L.REUTILIZABIL, L.VALOARE_LEI "
                "FROM SDA_TARIFF T JOIN SDA_TARIFF_LINE L "
                "ON L.TARIFF_ID = T.TARIFF_ID "
                "WHERE T.TIP = 'DEPOZIT' AND T.DATA_START <= :d "
                "AND (T.DATA_END IS NULL OR T.DATA_END >= :d)",
                {"d": on_date})
            lines = _rows(t)

        if not lines:
            return _fail("Nu exista tarif de depozit valabil la data ceruta")

        pack = packs[0]
        value = sda_rules.pick_value(
            [{"categorie": l["categorie"], "metoda": l["metoda"],
              "reutilizabil": l["reutilizabil"], "valoare_lei": l["valoare_lei"]}
             for l in lines],
            pack.get("cat_admin") or "*",
            reutilizabil=pack.get("reutilizabil"))
        if value is None:
            return _fail("Nu exista tarif de depozit pentru aceasta categorie")
        return _done({"ean": pack["ean"], "pack_id": pack["pack_id"],
                      "valoare_lei": float(value)})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 35 tests.

- [ ] **Step 5: Commit**

```bash
git add models/sda_oracle_store.py tests/test_sda.py
git commit -m "feat(sda): реестр упаковки и депозит по EAN без молчаливого нуля"
```

---

### Task 6: Controller and HTTP API

**Files:**
- Create: `controllers/sda_controller.py`
- Modify: `app.py` (add API routes next to the SDA docs routes added earlier)
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: `SDAStore` from Tasks 4–5.
- Produces class `SDAController` with static methods `get_units(args)`, `save_unit(data, username)`, `reclassify(username)`, `get_compliance(args)`, `get_packs(args)`, `save_pack(data, username)`, `get_deposit(args)`. Each returns a plain dict ready for `jsonify`.
- Produces routes: `GET /api/sda/units`, `POST /api/sda/units`, `POST /api/sda/units/reclassify`, `GET /api/sda/compliance`, `GET /api/sda/packs`, `POST /api/sda/packs`, `GET /api/sda/deposit`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "controller or endpoint or api_route"`
Expected: FAIL — `ModuleNotFoundError: No module named 'controllers.sda_controller'`

- [ ] **Step 3: Write the controller**

Create `controllers/sda_controller.py`:

```python
"""SDA — контроллер модуля: HTTP наверху, хранилище внизу.

Проверки формы живут здесь, а не в хранилище: в базу не должна уезжать
запись, про которую заранее известно, что она не пройдёт CHECK. Границы
объёма 0,1–3 л взяты из пункта 14.1 регламента и продублированы в DDL —
пользователю нужна внятная фраза, базе нужен запрет.
"""
from __future__ import annotations

from typing import Any, Dict

from models.sda_oracle_store import SDAStore

VOLUM_MIN_L = 0.1
VOLUM_MAX_L = 3.0


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


class SDAController:
    """Тонкий слой между Flask и SDAStore."""

    # ── сеть ────────────────────────────────────────────────────────

    @staticmethod
    def get_units(args) -> Dict[str, Any]:
        partic_id = args.get("partic_id")
        return SDAStore.list_units(
            int(partic_id) if partic_id else None, args.get("regim") or None)

    @staticmethod
    def save_unit(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("denumire") or "").strip():
            return _fail("Denumirea unitatii este obligatorie")
        suprafata = data.get("suprafata_mp")
        if suprafata not in (None, ""):
            try:
                if float(suprafata) <= 0:
                    return _fail("Suprafata trebuie sa fie mai mare ca zero")
            except (TypeError, ValueError):
                return _fail("Suprafata trebuie sa fie un numar")
        return SDAStore.save_unit(data, username)

    @staticmethod
    def reclassify(username: str) -> Dict[str, Any]:
        return SDAStore.reclassify_all(username)

    @staticmethod
    def get_compliance(args) -> Dict[str, Any]:
        partic_id = args.get("partic_id")
        return SDAStore.compliance_map(int(partic_id) if partic_id else None)

    # ── реестр ──────────────────────────────────────────────────────

    @staticmethod
    def get_packs(args) -> Dict[str, Any]:
        return SDAStore.list_packs(args.get("q") or None)

    @staticmethod
    def save_pack(data: Dict[str, Any], username: str) -> Dict[str, Any]:
        if not (data.get("ean") or "").strip():
            return _fail("Codul EAN este obligatoriu")
        if (data.get("material") or "").upper() not in ("PLASTIC", "STICLA", "METAL"):
            return _fail("Materialul trebuie sa fie PLASTIC, STICLA sau METAL")
        try:
            volum = float(data.get("volum_l"))
        except (TypeError, ValueError):
            return _fail("Volumul trebuie sa fie un numar")
        if not (VOLUM_MIN_L <= volum <= VOLUM_MAX_L):
            return _fail(
                f"Volumul trebuie sa fie intre {VOLUM_MIN_L} si {VOLUM_MAX_L} litri")
        try:
            if float(data.get("greutate_g")) <= 0:
                return _fail("Greutatea trebuie sa fie mai mare ca zero")
        except (TypeError, ValueError):
            return _fail("Greutatea trebuie sa fie un numar")
        return SDAStore.save_pack(data, username)

    @staticmethod
    def get_deposit(args) -> Dict[str, Any]:
        ean = args.get("ean")
        if not ean:
            return _fail("Parametrul ean este obligatoriu")
        return SDAStore.deposit_for_ean(ean)
```

- [ ] **Step 4: Add the routes to app.py**

In `app.py`, immediately after the block `# --- Модуль SDA: документация и презентация ---` and before `# --- Язык, словарь, справочники ---`, insert:

```python
# --- Модуль SDA: API ---
#
# Чтение открыто вместе с хабом модуля; запись требует входа, как
# в остальных модулях портала.

from controllers.sda_controller import SDAController   # noqa: E402


def _sda_user():
    return session.get('username') or 'anonim'


@app.route('/api/sda/units', methods=['GET'])
def api_sda_units():
    return jsonify(SDAController.get_units(request.args))


@app.route('/api/sda/units', methods=['POST'])
def api_sda_units_save():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.save_unit(request.get_json() or {}, _sda_user()))


@app.route('/api/sda/units/reclassify', methods=['POST'])
def api_sda_units_reclassify():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.reclassify(_sda_user()))


@app.route('/api/sda/compliance', methods=['GET'])
def api_sda_compliance():
    return jsonify(SDAController.get_compliance(request.args))


@app.route('/api/sda/packs', methods=['GET'])
def api_sda_packs():
    return jsonify(SDAController.get_packs(request.args))


@app.route('/api/sda/packs', methods=['POST'])
def api_sda_packs_save():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.save_pack(request.get_json() or {}, _sda_user()))


@app.route('/api/sda/deposit', methods=['GET'])
def api_sda_deposit():
    return jsonify(SDAController.get_deposit(request.args))
```

Before running, confirm `session` is already imported in `app.py` (`from flask import ... session ...`). If it is not, add it to that import line rather than importing Flask again.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 40 tests.

- [ ] **Step 6: Verify the app still imports**

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add controllers/sda_controller.py app.py tests/test_sda.py
git commit -m "feat(sda): контроллер и API сети, реестра и депозита"
```

---

### Task 7: Operator interface — compliance map, network, registry

**Files:**
- Create: `templates/sda.html`
- Modify: `app.py` (route `/UNA.md/orasldev/sda-console`)
- Modify: `modules/sda/module.json` (add the `pages` block)
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: the API routes from Task 6.
- Produces: route `sda_console` rendering `templates/sda.html`, with three panels whose ids are `panel-harta`, `panel-retea`, `panel-registru` (picked up automatically by the SPA navigation convention).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "console or manifest"`
Expected: FAIL — `FileNotFoundError: templates/sda.html`

- [ ] **Step 3: Write the template**

Create `templates/sda.html` as a self-contained page (the project uses monolithic templates, no base template). It must contain: a left navigation with three items bound to the panels; `panel-harta` showing the counts from `/api/sda/compliance` as three labelled bars plus the "fără regim" count; `panel-retea` showing a table of units from `/api/sda/units` with an edit form posting to the same route and a "Reclasifică" button posting to `/api/sda/units/reclassify`; `panel-registru` showing the packaging registry from `/api/sda/packs` with a form posting to it, displaying the derived `cat_admin` / `cat_gest` read-only.

Key behaviours the JavaScript must implement:

```javascript
async function loadCompliance() {
  const r = await fetch('/api/sda/compliance').then(x => x.json());
  if (!r.success) { showError(r.message); return; }
  const d = r.data, total = d.total || 0;
  const rows = [
    ['B_EXCEPTIE_APL', 'Excepție — parteneriat APL'],
    ['A_PUNCT_PROPRIU', 'Punct propriu de returnare'],
    ['C_HORECA', 'HoReCa'],
  ];
  document.getElementById('harta-bars').innerHTML = rows.map(([key, label]) => {
    const n = d.by_regime[key] || 0;
    const pct = total ? Math.round(n * 100 / total) : 0;
    return `<div class="bar"><span>${label}</span>
      <span class="track"><span class="fill ${key}" style="width:${pct}%"></span></span>
      <span class="n">${n}</span></div>`;
  }).join('');
  // Unitățile fără regim sunt anunțate separat: ele nu sunt o categorie,
  // ci munca rămasă de făcut înainte de depunerea dosarului.
  document.getElementById('harta-unknown').textContent = d.unknown
    ? `${d.unknown} unități fără suprafață declarată — inventar necesar`
    : 'Toate unitățile au regim stabilit';
}
```

The unit form must send `suprafata_mp` and `tip_amplasament` and then display the returned `regim` and `regim_motiv` so the operator sees why the system classified it that way — never let the operator type the regime directly.

- [ ] **Step 4: Add the route to app.py**

In `app.py`, next to `sda_docs_index`, add:

```python
@app.route('/UNA.md/orasldev/sda-console')
def sda_console():
    """Консоль модуля: карта соответствия, сеть, реестр упаковки."""
    if not AuthController.is_authenticated():
        return redirect(url_for('login'))
    return render_template('sda.html', page_title='SDA — consola modulului')
```

- [ ] **Step 5: Extend the module manifest**

Replace `modules/sda/module.json` with:

```json
{
  "title": {"ru": "SDA — залоговая система упаковки", "ro": "SDA — Sistemul de depozit pentru ambalaje", "en": "DRS — packaging deposit system"},
  "icon": "♻️",
  "order": 45,
  "url": "/UNA.md/orasldev/sda",
  "docs": "docs/SDA",
  "sql_prefix": "SDA_",
  "descr": "Регистр упаковки, сеть и режимы точек возврата, депозит на кассе, талоны, сдача администратору, взаиморасчёты и отчётность",
  "pages": {
    "/UNA.md/orasldev/sda": {"ru": "Документация", "ro": "Documentație", "en": "Documentation"},
    "/UNA.md/orasldev/sda-console": {"ru": "Консоль модуля", "ro": "Consola modulului", "en": "Module console"},
    "/UNA.md/orasldev/sda/presentation": {"ru": "Досье для клиента", "ro": "Dosar de prezentare", "en": "Client dossier"}
  }
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 44 tests.

- [ ] **Step 7: Commit**

```bash
git add templates/sda.html app.py modules/sda/module.json tests/test_sda.py
git commit -m "feat(sda): консоль модуля — карта соответствия, сеть, реестр"
```

---

### Task 8: Registration dossier export and documentation sync

**Files:**
- Modify: `models/sda_oracle_store.py`, `controllers/sda_controller.py`, `app.py`
- Modify: `docs/SDA/SPEC_SDA.md`, `README.md`
- Test: `tests/test_sda.py` (append)

**Interfaces:**
- Consumes: everything above.
- Produces `SDAStore.registration_dossier(partic_id: int) -> dict` returning the eight blocks required by pct. 78, and route `GET /api/sda/dossier?partic_id=N`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_sda.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_sda.py -q -k "dossier"`
Expected: FAIL — `AttributeError: type object 'SDAStore' has no attribute 'registration_dossier'`

- [ ] **Step 3: Write the implementation**

Append to `class SDAStore`:

```python
    # ── досье регистрации (пункт 78) ────────────────────────────────

    @staticmethod
    def registration_dossier(partic_id: int) -> Dict[str, Any]:
        """Восемь блоков уведомления о регистрации у Администратора.

        Блок «unitati» несёт площадь каждой точки: именно он решает,
        нужен ли сети собственный пункт возврата. Точки без площади
        считаются отдельно — досье с ними подавать нельзя.
        """
        with DatabaseModel() as db:
            p = db.execute_query(
                "SELECT PARTIC_ID, IDNO, DENUMIRE, CONTACT_NUME, CONTACT_TEL, "
                "CONTACT_EMAIL, VANDUT_AN_ANT, ESTIMARE_AN FROM SDA_PARTIC "
                "WHERE PARTIC_ID = :partic_id",
                {"partic_id": partic_id})
            partics = _rows(p)
            if not partics:
                return _fail(f"Participantul {partic_id} nu exista")

            u = db.execute_query(
                "SELECT UNIT_ID, DENUMIRE, ADRESA, SUPRAFATA_MP, "
                "TIP_AMPLASAMENT, REGIM FROM SDA_UNIT "
                "WHERE PARTIC_ID = :partic_id ORDER BY DENUMIRE",
                {"partic_id": partic_id})
            units = _rows(u)

            r = db.execute_query(
                "SELECT PT.POINT_ID, PT.UNIT_ID, PT.ADRESA, PT.ORAR, PT.TIP "
                "FROM SDA_RETURN_POINT PT JOIN SDA_UNIT UN "
                "ON UN.UNIT_ID = PT.UNIT_ID WHERE UN.PARTIC_ID = :partic_id",
                {"partic_id": partic_id})
            points = _rows(r)

        partic = partics[0]
        incomplet = sum(1 for x in units if not x.get("regim"))
        metode = sorted({x["tip"] for x in points}) or ["MANUAL"]

        return _done({
            "identificare": {"idno": partic["idno"], "denumire": partic["denumire"]},
            "contact": {"nume": partic.get("contact_nume"),
                        "telefon": partic.get("contact_tel"),
                        "email": partic.get("contact_email")},
            "unitati": units,
            "punct_preluare": points,
            "modalitate_preluare": metode,
            "vandut_an_anterior": partic.get("vandut_an_ant"),
            "estimare_an_curent": partic.get("estimare_an"),
            "exceptii": [x for x in units if x.get("regim") == "B_EXCEPTIE_APL"],
            "incomplet": incomplet,
        })
```

Add to `SDAController`:

```python
    @staticmethod
    def get_dossier(args) -> Dict[str, Any]:
        partic_id = args.get("partic_id")
        if not partic_id:
            return _fail("Parametrul partic_id este obligatoriu")
        return SDAStore.registration_dossier(int(partic_id))
```

Add to `app.py` next to the other SDA API routes:

```python
@app.route('/api/sda/dossier', methods=['GET'])
def api_sda_dossier():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return jsonify(SDAController.get_dossier(request.args))
```

- [ ] **Step 4: Run the whole suite**

Run: `python -m pytest tests/test_sda.py -q`
Expected: PASS, 46 tests.

- [ ] **Step 5: Update the documentation**

In `docs/SDA/SPEC_SDA.md`, section 7 "Etape de implementare", mark etapele 1–3 as delivered and record the two decisions this plan locked in: `SDA_*` live in the platform ADB (not in the client's ERP), and the OfficePlus nomenclature is read-only through `biro26_db`.

In `README.md`, add SDA to the module list next to the other modules, with its route and SQL prefix.

- [ ] **Step 6: Commit**

```bash
git add models/sda_oracle_store.py controllers/sda_controller.py app.py \
        docs/SDA/SPEC_SDA.md README.md tests/test_sda.py
git commit -m "feat(sda): досье регистрации по пункту 78 и синхронизация документации"
```

---

## Deployment (after all tasks pass)

The `SDA_*` objects are NOT created by a code deploy. Install them separately:

```bash
python deploy_oracle_objects.py --only 117_sda
```

Then verify they exist:

```sql
SELECT OBJECT_NAME, OBJECT_TYPE FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'SDA_%' ORDER BY 1;
```

Ship the code to nufarul as a targeted patch (`controllers/ models/ templates/ app.py` as one consistent set — never `app.py` alone), then:

```bash
sudo systemctl restart artgranit && sleep 8
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login
curl -I https://nufarul.eminescu.md/login
```

"""Biro26 module — unit tests (mocked; no live Oracle).

Biro26 reaches the Oracle 11g OfficePlus ERP through a thick-mode subprocess
worker. These tests mock the subprocess transport (and the worker's pure helpers)
so they run without a database or Instant Client.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from models.biro26_db import Biro26DB
from models import biro26_worker


# ── worker pure helpers ─────────────────────────────────────────────

def test_worker_nls_statements():
    joined = " ".join(biro26_worker._nls_statements()).upper()
    assert "NLS_LANGUAGE" in joined and "ENGLISH" in joined
    assert "NLS_TERRITORY" in joined and "AMERICA" in joined
    assert "NLS_NUMERIC_CHARACTERS" in joined


def test_worker_cell_makes_numbers_and_dates_json_safe():
    import decimal, datetime
    assert biro26_worker._cell(decimal.Decimal("12.00")) == 12  # integer-valued -> int
    assert biro26_worker._cell(decimal.Decimal("12.50")) == 12.5
    assert biro26_worker._cell(datetime.date(2026, 1, 1)) == "2026-01-01"
    assert biro26_worker._cell("plain") == "plain"


# ── client transport (subprocess mocked) ────────────────────────────

def _fake_proc(payload: dict, returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = json.dumps(payload)
    m.stderr = stderr
    return m


def test_execute_query_parses_worker_json():
    payload = {"success": True, "columns": ["ID", "NAME"],
               "data": [[1, "a"], [2, "b"]], "rowcount": 2}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)) as mrun:
        r = Biro26DB().execute_query("SELECT 1 FROM dual", {"x": 1})
    assert r["success"] and r["columns"] == ["ID", "NAME"]
    assert r["data"] == [(1, "a"), (2, "b")]  # rows normalized to tuples
    # request shape sent to worker
    sent = json.loads(mrun.call_args.kwargs["input"])
    assert sent["op"] == "query" and sent["params"] == {"x": 1}


def test_call_proc_returns_output_lines():
    payload = {"success": True, "output_lines": ["RO: ok / EN: ok"]}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)):
        r = Biro26DB().call_proc("BEGIN NULL; END;", capture_output=True)
    assert r["success"] and r["output_lines"] == ["RO: ok / EN: ok"]


def test_worker_nonzero_exit_is_error():
    bad = MagicMock(); bad.returncode = 1; bad.stdout = ""; bad.stderr = "boom"
    with patch("models.biro26_db.subprocess.run", return_value=bad):
        r = Biro26DB().execute_query("SELECT 1 FROM dual")
    assert r["success"] is False and "boom" in r["message"]


def test_test_connection_maps_version():
    payload = {"success": True, "version": "Oracle Database 11g"}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)):
        r = Biro26DB().test_connection()
    assert r["success"] and "11g" in r["version"]


# ── store: mapping profiles + g_* builder ───────────────────────────

from models.biro26_oracle_store import Biro26Store, G_PARAMS, build_gset_block, _page


def test_g_params_complete():
    assert len(G_PARAMS) == 25
    assert "codprice" in G_PARAMS and "len_denumire" in G_PARAMS


def test_build_gset_block_numbers_strings_dates():
    block = build_gset_block({"codprice": "5", "um": "buc.", "len_denumire": "160",
                              "date_start": "2026-01-01", "bogus": "x"})
    assert "g_codprice := 5" in block            # numeric unquoted
    assert "g_um := 'buc.'" in block             # string quoted
    assert "g_len_denumire := 160" in block
    assert "g_date_start := DATE '2026-01-01'" in block
    assert "bogus" not in block                  # unknown param ignored


def test_page_uses_rownum_not_fetch():
    sql = _page("SELECT id FROM t ORDER BY id", limit=10, offset=20)
    assert "ROWNUM <= 30" in sql and "rn > 20" in sql
    assert "FETCH" not in sql.upper()


class _FakeBiro26DB:
    """Stand-in for Biro26DB in store unit tests."""
    def __init__(self, rows=None, cols=None):
        self._rows = rows or []
        self._cols = cols or []
        self.last_sql = None
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute_query(self, sql, params=None):
        self.last_sql = sql
        return {"success": True, "data": self._rows, "columns": self._cols,
                "rowcount": len(self._rows), "message": ""}
    def execute_dml(self, sql, params=None):
        self.last_sql = sql
        return {"success": True, "rowcount": 1, "message": ""}
    def execute_script(self, statements):
        self.last_sql = statements
        return {"success": True, "results": [{"data": [[42]], "columns": ["ID"]}], "message": ""}
    def call_proc(self, plsql, params=None, capture_output=False):
        self.last_sql = plsql
        return {"success": True, "output_lines": ["RO: ok / EN: ok"], "message": ""}


def test_get_profiles_ok():
    cols = ["ID", "NAME", "CODPRICE", "IS_DEFAULT", "CREATED_AT", "CREATED_BY"]
    rows = [(1, "default", 1, "1", "28.06.2026 10:00", "OFFICEPLUS")]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_profiles()
    assert r["success"] and r["data"][0]["name"] == "default"


def test_create_profile_returns_new_id():
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB()):
        r = Biro26Store.create_profile("feed2", 5, {"codprice": "5", "um": "buc."})
    assert r["success"] and r["data"]["id"] == 42


# ── store: source feed ──────────────────────────────────────────────

def test_get_goods_returns_rows_and_status():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1","STOC","COD_UNIVERS","ROW_STATUS"]
    rows = [(1,"A1","Name","BR","F",10,9,12,5,1001,"IN_DICT")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_goods(limit=50, offset=0)
    assert r["success"] and r["data"][0]["row_status"] == "IN_DICT"
    assert "ROWNUM" in fake.last_sql and "FETCH" not in fake.last_sql.upper()


def test_get_goods_status_filter():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1","STOC","COD_UNIVERS","ROW_STATUS"]
    rows = [(1,"A1","N","B","F",1,1,1,1,1,"NEW"),(2,"A2","M","B","F",1,1,1,1,None,"CONFLICT")]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_goods(status="CONFLICT")
    assert [d["id"] for d in r["data"]] == [2]


def test_validate_input_captures_output():
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB()):
        r = Biro26Store.validate_input()
    assert r["success"] and r["output"] == ["RO: ok / EN: ok"]


# ── store: dictionary ───────────────────────────────────────────────

def test_get_univers_filters_tip_p():
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","GR1","UM","ISARHIV"]
    rows = [(1001,"A1","Nume","Имя","TVR","buc.",None)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_univers(arhiv="active")
    assert r["success"] and r["data"][0]["namerus"] == "Имя"
    assert "TIP='P'" in fake.last_sql and "ROWNUM" in fake.last_sql


def test_archive_univers_value_two_still_calls_pkg():
    # store does not guard '2' (controller does); ensure it builds the call
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.archive_univers("1")
    assert r["success"] and "archive_univers" in fake.last_sql


def test_fix_confusables_single_cod():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.fix_denumirea_confusables(1001)
    assert r["success"] and "p_cod => 1001" in fake.last_sql

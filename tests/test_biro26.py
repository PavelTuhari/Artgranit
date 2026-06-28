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

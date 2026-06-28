"""Biro26 module — unit tests (mocked Oracle)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from models.biro26_db import Biro26DB


def test_nls_alter_statements_built():
    db = Biro26DB()
    stmts = db._nls_statements()
    joined = " ".join(stmts).upper()
    assert "NLS_LANGUAGE" in joined and "ENGLISH" in joined
    assert "NLS_TERRITORY" in joined and "AMERICA" in joined
    assert "NLS_NUMERIC_CHARACTERS" in joined


def test_connect_uses_dsn_and_runs_nls():
    fake_conn = MagicMock()
    fake_cur = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = fake_cur
    with patch("models.biro26_db.oracledb.connect", return_value=fake_conn) as mconn:
        with Biro26DB() as db:
            assert db.connection is fake_conn
        kwargs = mconn.call_args.kwargs
        assert kwargs["user"] == "officeplus"
        assert "cloudbd.world" in kwargs["dsn"]
        assert any("ALTER SESSION" in str(c.args[0]).upper()
                   for c in fake_cur.execute.call_args_list)

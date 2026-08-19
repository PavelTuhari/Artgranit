"""PECO module — unit tests (Oracle fully mocked)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from models.peco_oracle_store import PecoStore, _norm_rows


def _fake_db(query_result):
    """Context manager yielding a db whose execute_query returns query_result."""
    db = MagicMock()
    db.execute_query.return_value = query_result
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm, db


def test_norm_rows_lowercases_columns():
    r = {"success": True, "columns": ["ID", "GRADE_CODE"], "data": [(1, "A95")]}
    assert _norm_rows(r) == [{"id": 1, "grade_code": "A95"}]


def test_norm_rows_empty_on_failure():
    assert _norm_rows({"success": False, "columns": [], "data": []}) == []


def test_current_price_returns_open_ended_row():
    cm, db = _fake_db({"success": True, "columns": ["PRICE"], "data": [(23.90,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.current_price(1, "A95")
    assert r["success"] is True
    assert r["price"] == 23.90
    sql = db.execute_query.call_args[0][0]
    assert "VALID_TO IS NULL" in sql  # действующая цена, а не любая


def test_current_price_missing_is_not_success():
    cm, _ = _fake_db({"success": True, "columns": ["PRICE"], "data": []})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.current_price(1, "A95")
    assert r["success"] is False


def test_set_price_closes_previous_then_inserts():
    cm, db = _fake_db({"success": True, "columns": [], "data": []})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.set_price(1, "A95", 24.50)
    assert r["success"] is True
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("UPDATE PECO_PRICES" in s for s in statements)
    assert any("INSERT INTO PECO_PRICES" in s for s in statements)
    db.connection.commit.assert_called_once()


def test_store_never_raises_on_db_error():
    cm = MagicMock()
    cm.__enter__.side_effect = Exception("ORA-12541")
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.list_stations()
    assert r["success"] is False and "ORA-12541" in r["error"]

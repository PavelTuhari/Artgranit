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


def _failing_db(message="ORA-00001: unique constraint violated"):
    """db, чей execute_query сообщает об ошибке флагом, а не исключением —
    именно так ведёт себя models.database.execute_query."""
    db = MagicMock()
    db.execute_query.return_value = {"success": False, "message": message,
                                     "columns": [], "data": [], "rowcount": 0}
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm, db


def test_set_price_does_not_commit_when_sql_fails():
    """Неудавшийся UPDATE не должен доезжать до commit и возвращать success."""
    cm, db = _failing_db()
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.set_price(1, "A95", 24.50)
    assert r["success"] is False
    db.connection.commit.assert_not_called()


def test_log_event_reports_sql_failure():
    cm, db = _failing_db()
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.log_event("TEST", station_id=1)
    assert r["success"] is False
    db.connection.commit.assert_not_called()


def test_reads_report_failure_instead_of_empty_list():
    """Сломанный SELECT — это ошибка, а не 'данных нет'."""
    cm, _ = _failing_db("ORA-00942: table or view does not exist")
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        assert PecoStore.list_grades()["success"] is False
        assert PecoStore.list_stations()["success"] is False
        assert PecoStore.list_nozzles(1)["success"] is False


def test_current_price_failure_is_not_reported_as_missing_price():
    cm, _ = _failing_db("ORA-00942: table or view does not exist")
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.current_price(1, "A95")
    assert r["success"] is False
    assert "действующей цены" not in r.get("error", "")


def test_open_shift_creates_meter_rows_from_nozzles():
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(77,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.open_shift(station_id=1, employee_id=5)
    assert r["success"] is True and r["shift_id"] == 77
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("INSERT INTO PECO_SHIFTS" in s for s in statements)
    # показания открытия берутся из текущих счётчиков пистолетов
    assert any("INSERT INTO PECO_SHIFT_METERS" in s for s in statements)
    assert any("METER_TOTAL" in s for s in statements)
    db.connection.commit.assert_called_once()


def test_open_shift_snapshots_tank_volumes():
    """Без снимка остатка на открытие tank_variance посчитать не из чего."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(77,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        PecoStore.open_shift(station_id=1, employee_id=5)
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("INSERT INTO PECO_SHIFT_TANKS" in s for s in statements)
    assert any("CURRENT_L" in s for s in statements)


def test_get_shift_tanks_returns_ledger_columns():
    cm, db = _fake_db({
        "success": True,
        "columns": ["TANK_ID", "GRADE_CODE", "VOLUME_OPEN_L", "DELIVERED_L", "DIP_CLOSE_L"],
        "data": [(11, "A95", 12000.0, 5000.0, 15950.0)],
    })
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.get_shift_tanks(77)
    assert r["success"] is True
    assert r["items"][0]["volume_open_l"] == 12000.0
    assert r["items"][0]["delivered_l"] == 5000.0


def test_count_unresolved_txn_covers_both_open_states():
    cm, db = _fake_db({"success": True, "columns": ["C"], "data": [(3,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.count_unresolved_txn(77)
    assert r["success"] is True and r["count"] == 3
    sql = db.execute_query.call_args[0][0]
    assert "DISPENSING" in sql and "AWAITING_PAY" in sql


def test_shift_paid_liters_separates_cash_from_mia():
    cm, db = _fake_db({
        "success": True,
        "columns": ["LITERS", "CASH_AMT", "MIA_AMT"],
        "data": [(120.5, 2400.00, 900.00)],
    })
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.shift_paid_liters(77)
    assert r["liters"] == 120.5
    assert r["cash"] == 2400.00
    assert r["mia"] == 900.00
    sql = db.execute_query.call_args[0][0]
    assert "'CASH'" in sql and "'MIA_QR'" in sql


def test_finalize_shift_writes_all_three_variances():
    cm, db = _fake_db({"success": True, "columns": [], "data": []})
    totals = {"cash_declared": 2390.0, "cash_expected": 2400.0,
              "cash_variance": -10.0, "liter_variance": 0.4,
              "tank_variance": -1.2}
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.finalize_shift(77, employee_id=5, status="DISPUTED", totals=totals)
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    for col in ("CASH_VARIANCE", "LITER_VARIANCE", "TANK_VARIANCE", "STATUS_CODE"):
        assert col in sql
    db.connection.commit.assert_called_once()

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


def test_list_prices_returns_only_active_rows():
    """Менеджер меняет цены и между сменами, поэтому цены нужны отдельно
    от pump_state, который требует открытую смену."""
    cm, db = _fake_db({"success": True,
                       "columns": ["GRADE_CODE", "PRICE", "VALID_FROM", "GRADE_NAME"],
                       "data": [("A95", 23.90, None, "Бензин А-95")]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.list_prices(1)
    assert r["success"] is True
    assert r["items"][0]["grade_code"] == "A95"
    sql = db.execute_query.call_args[0][0]
    assert "VALID_TO IS NULL" in sql


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


from models import peco_shift


def test_meter_delta_sums_closed_nozzles_only():
    meters = [
        {"nozzle_id": 1, "meter_open": 1000.0, "meter_close": 1120.5},
        {"nozzle_id": 2, "meter_open": 500.0,  "meter_close": 560.0},
        {"nozzle_id": 3, "meter_open": 200.0,  "meter_close": None},  # не снят
    ]
    assert peco_shift.meter_delta(meters) == 180.5


def test_liter_variance_is_meter_minus_paid():
    """Топливо вышло из пистолета, но не оплачено — это и есть недостача."""
    meters = [{"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0}]
    v = peco_shift.compute_variances(meters, txn_liters=98.0,
                                     cash_declared=0.0, cash_expected=0.0)
    assert v["meter_delta"] == 100.0
    assert v["liter_variance"] == 2.0


def test_cash_variance_is_declared_minus_expected():
    v = peco_shift.compute_variances([], txn_liters=0.0,
                                     cash_declared=2390.0, cash_expected=2400.0)
    assert v["cash_variance"] == -10.0  # недостача кассы


def test_variances_are_rounded_to_three_decimals():
    meters = [{"nozzle_id": 1, "meter_open": 0.0, "meter_close": 10.0}]
    v = peco_shift.compute_variances(meters, txn_liters=9.9999,
                                     cash_declared=0.0, cash_expected=0.0)
    assert v["liter_variance"] == 0.0


def test_tank_variances_computes_per_tank_not_per_station():
    """У станции до четырёх резервуаров; утечка в одном не должна
    растворяться в сумме по станции."""
    tank_rows = [
        {"tank_id": 11, "grade_code": "A95", "volume_open_l": 12000.0, "delivered_l": 5000.0},
        {"tank_id": 12, "grade_code": "DIESEL", "volume_open_l": 8000.0, "delivered_l": 0.0},
    ]
    meters = [
        {"nozzle_id": 1, "tank_id": 11, "meter_open": 0.0, "meter_close": 1000.0},
        {"nozzle_id": 2, "tank_id": 12, "meter_open": 0.0, "meter_close": 500.0},
    ]
    dips = {11: 15950.0, 12: 7500.0}
    rows = peco_shift.tank_variances(tank_rows, meters, dips)
    by_id = {r["tank_id"]: r for r in rows}
    # 12000 + 5000 - 1000 = 16000, замер 15950 -> -50
    assert by_id[11]["tank_variance"] == -50.0
    # 8000 + 0 - 500 = 7500, замер 7500 -> 0
    assert by_id[12]["tank_variance"] == 0.0


def test_tank_variance_is_none_when_that_tank_has_no_dip():
    tank_rows = [{"tank_id": 11, "grade_code": "A95",
                  "volume_open_l": 100.0, "delivered_l": 0.0}]
    rows = peco_shift.tank_variances(tank_rows, [], {})
    assert rows[0]["tank_variance"] is None


def test_tank_variances_only_counts_meters_of_that_tank():
    """Счётчик чужого резервуара не должен уменьшать чужой остаток."""
    tank_rows = [{"tank_id": 11, "grade_code": "A95",
                  "volume_open_l": 1000.0, "delivered_l": 0.0}]
    meters = [
        {"nozzle_id": 1, "tank_id": 11, "meter_open": 0.0, "meter_close": 100.0},
        {"nozzle_id": 2, "tank_id": 99, "meter_open": 0.0, "meter_close": 400.0},
    ]
    rows = peco_shift.tank_variances(tank_rows, meters, {11: 900.0})
    assert rows[0]["tank_variance"] == 0.0


def test_status_is_closed_within_tolerance():
    v = {"liter_variance": 0.2, "cash_variance": 0.5, "tank_variance": None}
    assert peco_shift.exceeds_tolerance(v) is False


def test_status_is_disputed_when_liters_exceed_tolerance():
    v = {"liter_variance": 3.0, "cash_variance": 0.0, "tank_variance": None}
    assert peco_shift.exceeds_tolerance(v) is True


def test_status_is_disputed_on_negative_cash_beyond_tolerance():
    """Излишек тоже расхождение — проверяется модуль, а не знак."""
    v = {"liter_variance": 0.0, "cash_variance": -25.0, "tank_variance": None}
    assert peco_shift.exceeds_tolerance(v) is True


def test_tank_leak_and_overage_do_not_cancel():
    """Утечка в одном резервуаре и излишек в другом не должны погасить
    друг друга: сумма по станции дала бы ноль и чистую смену."""
    rows = [
        {"tank_id": 11, "tank_variance": -200.0},
        {"tank_id": 12, "tank_variance": 200.0},
    ]
    assert peco_shift.tank_variances_exceed(rows) is True


def test_tank_variances_exceed_ignores_tanks_without_a_dip():
    rows = [{"tank_id": 11, "tank_variance": None}]
    assert peco_shift.tank_variances_exceed(rows) is False


def test_tank_variances_exceed_is_false_within_tolerance():
    rows = [{"tank_id": 11, "tank_variance": 10.0},
            {"tank_id": 12, "tank_variance": -10.0}]
    assert peco_shift.tank_variances_exceed(rows) is False


def test_tank_tolerance_is_looser_than_meter_tolerance():
    """Замер метрштоком грубее счётчика; равный допуск сделал бы
    DISPUTED статусом каждой смены."""
    assert peco_shift.TOLERANCE_TANK_LITERS > peco_shift.TOLERANCE_LITERS


def test_exceeds_tolerance_flags_a_tank_leak():
    v = {"liter_variance": 0.0, "cash_variance": 0.0, "tank_variance": -200.0}
    assert peco_shift.exceeds_tolerance(v) is True


def test_missing_measurement_is_not_treated_as_clean():
    """Отсутствие замера — не доказательство отсутствия расхождения."""
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": None, "cash_variance": 0.0, "tank_variance": None}) is True
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": 0.0, "cash_variance": None, "tank_variance": None}) is True


def test_tolerance_boundary_is_inclusive():
    """Ровно на допуске — ещё чисто; чуть больше — уже расхождение."""
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": 0.5, "cash_variance": 0.0, "tank_variance": None}) is False
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": 0.501, "cash_variance": 0.0, "tank_variance": None}) is True
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": 0.6, "cash_variance": 0.0, "tank_variance": None}) is True
    assert peco_shift.exceeds_tolerance(
        {"liter_variance": 0.0, "cash_variance": 1.0, "tank_variance": None}) is False


def test_variance_maths_accepts_oracle_decimals():
    """Oracle отдаёт числа как Decimal — расчёт не должен на этом падать."""
    from decimal import Decimal
    meters = [{"nozzle_id": 1, "tank_id": 11,
               "meter_open": Decimal("0.000"), "meter_close": Decimal("100.000")}]
    v = peco_shift.compute_variances(meters, txn_liters=Decimal("98.000"),
                                     cash_declared=Decimal("0.00"),
                                     cash_expected=Decimal("0.00"))
    assert v["liter_variance"] == 2.0

    rows = [{"tank_id": 11, "grade_code": "A95",
             "volume_open_l": Decimal("12000.000"),
             "delivered_l": Decimal("0.000")}]
    out = peco_shift.tank_variances(rows, meters, {11: Decimal("11900.000")})
    assert out[0]["tank_variance"] == 0.0


def test_tank_variances_skips_nozzles_without_a_closing_reading():
    """Неснятое показание не должно считаться нулевым расходом."""
    rows = [{"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 1000.0, "delivered_l": 0.0}]
    meters = [{"nozzle_id": 1, "tank_id": 11, "meter_open": 0.0, "meter_close": None}]
    out = peco_shift.tank_variances(rows, meters, {11: 1000.0})
    assert out[0]["tank_variance"] == 0.0


def test_tank_variances_output_carries_grade_and_dip():
    rows = [{"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 100.0, "delivered_l": 0.0}]
    out = peco_shift.tank_variances(rows, [], {11: 95.0})
    assert out[0]["grade_code"] == "A95"
    assert out[0]["dip_close_l"] == 95.0


def test_open_shift_refuses_when_one_is_already_open():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": True, "shift": {"id": 42}}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is False
    assert "уже открыта" in r["error"]
    store.open_shift.assert_not_called()


def test_open_shift_creates_when_none_open():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": False, "error": "Нет открытой смены"}
        store.open_shift.return_value = {"success": True, "shift_id": 43}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is True and r["shift_id"] == 43
    store.log_event.assert_called_once()


def test_close_shift_blocked_by_unresolved_transactions():
    """Смена не закрывается, пока налив идёт или ждёт оплаты — ничего
    не должно исчезать молча."""
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 2}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=100.0)
    assert r["success"] is False
    assert r["unresolved"] == 2
    store.finalize_shift.assert_not_called()


def test_close_shift_computes_and_persists_variances():
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 100.0, "cash": 2400.0, "mia": 500.0}
        store.get_shift_tanks.return_value = {"success": True, "items": []}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=2400.0)
    assert r["success"] is True
    assert r["status"] == "CLOSED"
    assert r["variances"]["liter_variance"] == 0.0
    assert r["variances"]["cash_variance"] == 0.0
    # ожидаемая наличность — только CASH, без MIA QR
    totals = store.finalize_shift.call_args.kwargs["totals"]
    assert totals["cash_expected"] == 2400.0


def test_close_shift_reads_tank_ledger_from_store_not_caller():
    """Остаток на открытие и приход читаются из PECO_SHIFT_TANKS.
    Иначе оператор подогнал бы расхождение под ноль, объявив удобные цифры."""
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "tank_id": 11, "meter_open": 0.0, "meter_close": 1000.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 1000.0, "cash": 0.0, "mia": 0.0}
        store.get_shift_tanks.return_value = {"success": True, "items": [
            {"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 12000.0, "delivered_l": 5000.0},
        ]}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0,
                                   dips={11: 15800.0})
    # 12000 + 5000 - 1000 = 16000; замер 15800 -> -200
    assert r["variances"]["tank_variance"] == -200.0
    store.save_tank_close.assert_called_once()
    assert r["status"] == "DISPUTED"   # 200 л выходит за допуск по резервуару


def test_close_shift_does_not_let_tanks_cancel_each_other():
    """Утечка в одном резервуаре и излишек в другом дают в сумме ноль.
    Смена всё равно обязана уйти в DISPUTED."""
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": []}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 0.0, "cash": 0.0, "mia": 0.0}
        store.get_shift_tanks.return_value = {"success": True, "items": [
            {"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 1000.0, "delivered_l": 0.0},
            {"tank_id": 12, "grade_code": "DIESEL",
             "volume_open_l": 1000.0, "delivered_l": 0.0},
        ]}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0,
                                   dips={11: 800.0, 12: 1200.0})
    assert r["variances"]["tank_variance"] == 0.0   # сумма действительно ноль
    assert r["status"] == "DISPUTED"                # но по резервуарам — нет


def test_close_shift_marks_disputed_on_shortfall():
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "meter_open": 0.0, "meter_close": 100.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 90.0, "cash": 2000.0, "mia": 0.0}
        store.get_shift_tanks.return_value = {"success": True, "items": []}
        store.finalize_shift.return_value = {"success": True}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=2000.0)
    assert r["status"] == "DISPUTED"
    assert r["variances"]["liter_variance"] == 10.0


# ------------------------------------------------------------------
# Final review fix: reconciliation must not be opt-in (Critical 1)
# ------------------------------------------------------------------


def test_close_shift_refuses_when_a_nozzle_has_no_closing_meter():
    """Пистолет без снятого показания — это спущенное топливо без следа,
    а не законный ноль: смена не имеет права закрыться, пока показание
    не снято со ВСЕХ пистолетов."""
    with patch("models.peco_shift.PecoStore") as store:
        store.count_unresolved_txn.return_value = {"success": True, "count": 0}
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "nozzle_code": "N-A95",
             "meter_open": 0.0, "meter_close": 100.0},
            {"nozzle_id": 2, "nozzle_code": "N-DIESEL",
             "meter_open": 0.0, "meter_close": None},
        ]}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0)
    assert r["success"] is False
    assert r["missing_meters"] == [2]
    assert "N-DIESEL" in r["error"]
    store.mark_shift_closing.assert_not_called()
    store.finalize_shift.assert_not_called()


def test_close_shift_forces_disputed_when_a_tank_has_no_dip():
    """Отсутствие метрштока — недостаток данных, а не доказательство
    чистой смены (тот же принцип, что и None в exceeds_tolerance).
    liter_variance и cash_variance в допуске, но резервуар не обмерен —
    смена обязана уйти в DISPUTED, а не закрыться CLOSED."""
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        store.get_shift_meters.return_value = {"success": True, "items": [
            {"nozzle_id": 1, "tank_id": 11, "meter_open": 0.0, "meter_close": 100.0},
        ]}
        store.shift_paid_liters.return_value = {
            "success": True, "liters": 100.0, "cash": 0.0, "mia": 0.0}
        store.get_shift_tanks.return_value = {"success": True, "items": [
            {"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 1000.0, "delivered_l": 0.0},
        ]}
        # dips не передан вовсе -> у резервуара 11 нет замера на закрытие
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0)
    assert r["success"] is True
    assert r["status"] == "DISPUTED"
    assert r["unmeasured_tanks"] == [11]
    store.save_tank_close.assert_not_called()  # нечего писать без замера


# ------------------------------------------------------------------
# Task 8 fix-pass 1: error-path findings
# ------------------------------------------------------------------


def _close_mocks(store):
    """Общая заглушка успешного закрытия смены."""
    store.count_unresolved_txn.return_value = {"success": True, "count": 0}
    store.mark_shift_closing.return_value = {"success": True}
    store.get_shift_meters.return_value = {"success": True, "items": []}
    store.shift_paid_liters.return_value = {
        "success": True, "liters": 0.0, "cash": 0.0, "mia": 0.0}
    store.get_shift_tanks.return_value = {"success": True, "items": []}
    store.save_tank_close.return_value = {"success": True}
    store.finalize_shift.return_value = {"success": True}
    store.log_event.return_value = {"success": True}


def test_close_shift_fails_when_a_tank_write_fails():
    """Смена не должна закрываться успешно, если расхождение по резервуару
    не сохранилось: итог по станции остался бы без данных о том, ГДЕ недостача."""
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        store.get_shift_tanks.return_value = {"success": True, "items": [
            {"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 100.0, "delivered_l": 0.0}]}
        store.save_tank_close.return_value = {"success": False, "error": "ORA-00001"}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0,
                                   dips={11: 50.0})
    assert r["success"] is False
    store.finalize_shift.assert_not_called()


def test_close_shift_fails_when_tank_ledger_cannot_be_read():
    """Сбой чтения реестра — это ошибка, а не 'расхождений по резервуарам нет'."""
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        store.get_shift_tanks.return_value = {"success": False,
                                              "error": "ORA-00942"}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0)
    assert r["success"] is False
    store.finalize_shift.assert_not_called()


def test_close_shift_marks_closing_before_writing_measurements():
    """Пока идёт закрытие, смена не должна выглядеть обычной открытой."""
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        peco_shift.close_shift(77, employee_id=5, cash_declared=0.0)
    store.mark_shift_closing.assert_called_once_with(77)


def test_close_shift_returns_per_tank_detail():
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        store.get_shift_tanks.return_value = {"success": True, "items": [
            {"tank_id": 11, "grade_code": "A95",
             "volume_open_l": 100.0, "delivered_l": 0.0}]}
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0,
                                   dips={11: 90.0})
    assert r["tanks"][0]["tank_id"] == 11
    assert r["tanks"][0]["tank_variance"] == -10.0


def test_close_shift_reports_dips_for_unknown_tanks():
    """Замер по резервуару, которого нет в реестре смены, не должен
    исчезать молча."""
    with patch("models.peco_shift.PecoStore") as store:
        _close_mocks(store)
        r = peco_shift.close_shift(77, employee_id=5, cash_declared=0.0,
                                   dips={99: 5000.0})
    assert r["ignored_dips"] == [99]


def test_open_shift_maps_index_violation_to_domain_error():
    """Гонка двух открытий: оператор должен увидеть доменную ошибку,
    а не текст ORA."""
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": False, "error": "нет"}
        store.open_shift.return_value = {
            "success": False,
            "error": "ORA-00001: unique constraint (X.UX_PECO_SHIFTS_ACTIVE) violated"}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is False
    assert "ORA-" not in r["error"]
    assert "уже открыта" in r["error"]


def test_open_shift_rejects_a_null_shift_id():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_open_shift.return_value = {"success": False, "error": "нет"}
        store.open_shift.return_value = {"success": True, "shift_id": None}
        r = peco_shift.open_shift(station_id=1, employee_id=5)
    assert r["success"] is False


def test_save_tank_close_rejects_a_zero_row_update():
    """UPDATE, не задевший ни одной строки, означает отсутствие строки
    реестра — это ошибка, а не успех."""
    db = MagicMock()
    db.execute_query.return_value = {"success": True, "columns": [], "data": [],
                                     "rowcount": 0}
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.save_tank_close(77, 11, 100.0, -5.0)
    assert r["success"] is False


# ------------------------------------------------------------------
# Task 8 fix-pass 2: mark_shift_closing retry-idempotency
# ------------------------------------------------------------------


def _rowcount_db(rowcount):
    db = MagicMock()
    db.execute_query.return_value = {"success": True, "columns": [], "data": [],
                                     "rowcount": rowcount}
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm, db


def test_mark_shift_closing_accepts_a_shift_already_closing():
    """Повторное закрытие после сбоя обязано пройти: иначе смена,
    упавшая на finalize, застревает в CLOSING навсегда, и станция
    не может ни закрыть её, ни открыть новую."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.mark_shift_closing(77)
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    assert "'OPEN'" in sql and "'CLOSING'" in sql


def test_mark_shift_closing_rejects_an_already_closed_shift():
    cm, _ = _rowcount_db(0)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.mark_shift_closing(77)
    assert r["success"] is False


# ------------------------------------------------------------------
# Final review fix: measured dip must correct the register (Critical 2)
# ------------------------------------------------------------------


def test_save_tank_close_writes_current_l_and_dip_row_in_one_transaction():
    """Замер на закрытие обязан переписывать PECO_TANKS.CURRENT_L и
    оставлять след в PECO_TANK_DIPS в ТОЙ ЖЕ транзакции, что и реестр
    смены. Иначе один неучтённый слив «утекает» заново на каждой
    следующей смене, и DISPUTED перестаёт что-либо значить."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.save_tank_close(77, 11, 15800.0, -200.0, employee_id=5)
    assert r["success"] is True
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    assert any("UPDATE PECO_TANKS" in s and "CURRENT_L" in s for s in statements)
    assert any("INSERT INTO PECO_TANK_DIPS" in s and "'CLOSE'" in s
              for s in statements)
    db.connection.commit.assert_called_once()


# ------------------------------------------------------------------
# Final review fix: save_meter_close guards (Critical 5)
# ------------------------------------------------------------------


def test_save_meter_close_refuses_a_nozzle_outside_the_shift():
    """Ноль строк по (SHIFT_ID, NOZZLE_ID) — это либо чужой пистолет, либо
    уже закрытая смена. Ни то, ни другое не должно тихо вернуть success,
    иначе первый UPDATE открывает путь второму — station-scoped, но не
    существующему для этой смены — перезаписать чужой тотализатор."""
    cm, db = _rowcount_db(0)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.save_meter_close(12, 900, 5000.0)
    assert r["success"] is False
    db.connection.commit.assert_not_called()


def test_save_meter_close_nozzle_update_is_station_scoped_and_forward_only():
    """Второй UPDATE обязан быть ограничен станцией этой смены и не давать
    тотализатору идти назад — без этого запрос с чужим nozzle_id молча
    перезаписывает тотализатор ЧУЖОЙ станции."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.save_meter_close(12, 3, 5000.0)
    assert r["success"] is True
    statements = [c[0][0] for c in db.execute_query.call_args_list]
    nozzle_sql = next(s for s in statements if "UPDATE PECO_NOZZLES" in s)
    assert "STATION_ID = (SELECT STATION_ID FROM PECO_SHIFTS" in nozzle_sql
    assert "METER_TOTAL <= :meter_close" in nozzle_sql
    shift_sql = next(s for s in statements if "UPDATE PECO_SHIFT_METERS" in s)
    assert "STATUS_CODE IN ('OPEN','CLOSING')" in shift_sql
    db.connection.commit.assert_called_once()


def test_hash_pin_is_stable_for_the_same_salt():
    salt = "a" * 32
    h = peco_shift.hash_pin("1234", salt)
    assert h == peco_shift.hash_pin("1234", salt)
    assert "1234" not in h
    assert len(h) == 64


def test_same_pin_with_different_salts_gives_different_hashes():
    """Соль на сотрудника: одинаковый PIN у двоих не даёт одинаковый хеш,
    иначе четырёхзначный PIN вскрывается одной радужной таблицей."""
    assert peco_shift.hash_pin("1234", "a" * 32) != peco_shift.hash_pin("1234", "b" * 32)


def test_new_salt_is_random_and_hex():
    s1, s2 = peco_shift.new_salt(), peco_shift.new_salt()
    assert s1 != s2
    assert len(s1) == 32
    int(s1, 16)  # бросит ValueError, если не hex


def test_verify_pin_accepts_correct_and_rejects_wrong():
    salt = peco_shift.new_salt()
    h = peco_shift.hash_pin("1234", salt)
    assert peco_shift.verify_pin("1234", salt, h) is True
    assert peco_shift.verify_pin("9999", salt, h) is False


def test_verify_pin_rejects_placeholder_seed_values():
    """Демо-строки из сида не должны случайно проходить проверку."""
    assert peco_shift.verify_pin("1234", "NO_SALT_SET", "NO_PIN_SET") is False


def _mgr(role="MANAGER", pin="1234", station_id=1):
    salt = peco_shift.new_salt()
    return {"id": 9, "station_id": station_id, "role_code": role, "pin_salt": salt,
            "pin_hash": peco_shift.hash_pin(pin, salt)}


def test_approve_disputed_rejects_non_manager():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {
            "success": True, "employee": _mgr(role="ATTENDANT")}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="1234")
    assert r["success"] is False
    store.approve_shift.assert_not_called()


def test_approve_disputed_rejects_wrong_pin():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": _mgr()}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="9999")
    assert r["success"] is False
    store.approve_shift.assert_not_called()


def test_approve_disputed_accepts_manager_with_correct_pin():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": _mgr()}
        store.approve_shift.return_value = {"success": True}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="1234")
    assert r["success"] is True
    store.approve_shift.assert_called_once_with(77, 9, 1)
    store.log_event.assert_called_once()


# ------------------------------------------------------------------
# Task 9 fix-pass 1: approve_shift authorization gaps
# ------------------------------------------------------------------


def test_hash_pin_is_actually_pbkdf2_not_a_bare_digest():
    """Известный вектор: подмена PBKDF2 на sha256(salt+pin) не должна
    пройти тесты. Четырёхзначный PIN — это 10 000 вариантов, и голый
    дайджест такого пространства разворачивается таблицей мгновенно."""
    import hashlib
    salt = "a" * 32
    expected = hashlib.pbkdf2_hmac(
        "sha256", b"1234", salt.encode(), peco_shift._PIN_ITERATIONS).hex()
    assert peco_shift.hash_pin("1234", salt) == expected
    assert peco_shift.hash_pin("1234", salt) != hashlib.sha256(
        (salt + "1234").encode()).hexdigest()


def test_pin_iterations_meet_current_guidance():
    assert peco_shift._PIN_ITERATIONS >= 600_000


def test_approve_shift_scopes_the_update_to_disputed_and_station():
    """Условия авторизации обязаны быть в WHERE: проверка в Python
    оставила бы окно между проверкой и обновлением."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.approve_shift(77, 9, 1)
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    assert "DISPUTED" in sql
    assert "STATION_ID" in sql


def test_approve_shift_rejects_a_zero_row_update():
    """Ноль затронутых строк — смены нет, она не DISPUTED, либо чужая станция."""
    cm, _ = _rowcount_db(0)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.approve_shift(77, 9, 1)
    assert r["success"] is False


def test_manager_cannot_approve_a_shift_at_another_station():
    """Менеджер станции 3 не должен подписывать расхождение станции 41."""
    salt = peco_shift.new_salt()
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": {
            "id": 9, "station_id": 3, "role_code": "MANAGER",
            "pin_salt": salt, "pin_hash": peco_shift.hash_pin("1234", salt)}}
        store.approve_shift.return_value = {
            "success": False,
            "error": "Смена не найдена, не в статусе расхождения или относится к другой станции"}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="1234")
    assert r["success"] is False
    # станция менеджера обязана дойти до запроса
    assert store.approve_shift.call_args[0][2] == 3


def test_admin_may_approve_network_wide():
    salt = peco_shift.new_salt()
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": {
            "id": 1, "station_id": None, "role_code": "ADMIN",
            "pin_salt": salt, "pin_hash": peco_shift.hash_pin("1234", salt)}}
        store.approve_shift.return_value = {"success": True}
        store.log_event.return_value = {"success": True}
        r = peco_shift.approve_disputed(77, manager_id=1, pin="1234")
    assert r["success"] is True
    assert store.approve_shift.call_args[0][2] is None


def test_approval_errors_do_not_reveal_which_check_failed():
    """Разные сообщения выдавали бы, существует ли сотрудник и менеджер ли он."""
    salt = peco_shift.new_salt()
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": {
            "id": 5, "station_id": 1, "role_code": "ATTENDANT",
            "pin_salt": salt, "pin_hash": peco_shift.hash_pin("1234", salt)}}
        not_manager = peco_shift.approve_disputed(77, 5, "1234")
        store.get_employee_credentials.return_value = {"success": True, "employee": {
            "id": 9, "station_id": 1, "role_code": "MANAGER",
            "pin_salt": salt, "pin_hash": peco_shift.hash_pin("1234", salt)}}
        wrong_pin = peco_shift.approve_disputed(77, 9, "9999")
    assert not_manager["error"] == wrong_pin["error"]


def test_get_employee_does_not_expose_credentials():
    """Хеш и соль не должны уезжать наружу с обычным чтением сотрудника."""
    cm, _ = _fake_db({"success": True,
                      "columns": ["ID", "STATION_ID", "FULL_NAME", "ROLE_CODE"],
                      "data": [(9, 1, "Тест", "MANAGER")]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.get_employee(9)
    assert r["success"] is True
    assert "pin_hash" not in r["employee"]
    assert "pin_salt" not in r["employee"]


def test_approval_reports_a_lost_audit_record():
    salt = peco_shift.new_salt()
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee_credentials.return_value = {"success": True, "employee": {
            "id": 9, "station_id": 1, "role_code": "MANAGER",
            "pin_salt": salt, "pin_hash": peco_shift.hash_pin("1234", salt)}}
        store.approve_shift.return_value = {"success": True}
        store.log_event.return_value = {"success": False, "error": "ORA-00942"}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="1234")
    assert r["success"] is True
    assert "audit_warning" in r


from models import peco_txn


def test_legal_transitions_follow_the_state_machine():
    assert peco_txn.can_transition("AUTHORIZED", "DISPENSING") is True
    assert peco_txn.can_transition("DISPENSING", "AWAITING_PAY") is True
    assert peco_txn.can_transition("AWAITING_PAY", "PAID") is True
    assert peco_txn.can_transition("DISPENSING", "VOIDED") is True
    assert peco_txn.can_transition("AUTHORIZED", "VOIDED") is True


def test_illegal_transitions_are_refused():
    assert peco_txn.can_transition("AUTHORIZED", "PAID") is False   # без налива
    assert peco_txn.can_transition("PAID", "DISPENSING") is False   # оплачено — финал
    assert peco_txn.can_transition("VOIDED", "PAID") is False
    assert peco_txn.can_transition("PAID", "VOIDED") is False


def test_self_service_settles_immediately_attendant_waits_for_cashier():
    assert peco_txn.next_status_after_dispense(is_self_service=True) == "PAID"
    assert peco_txn.next_status_after_dispense(is_self_service=False) == "AWAITING_PAY"


def test_liters_come_from_the_meter_not_from_input():
    assert peco_txn.liters_from_meter(1000.0, 1042.375) == 42.375


def test_liters_from_meter_refuses_backwards_reading():
    assert peco_txn.liters_from_meter(1000.0, 999.0) == 0.0


def test_amount_rounds_half_up_to_two_decimals():
    assert peco_txn.compute_amount(10.0, 23.90) == 239.00
    assert peco_txn.compute_amount(1.005, 10.0) == 10.05


def test_mia_settlement_requires_a_reference():
    r = peco_txn.validate_settlement("AWAITING_PAY", "MIA_QR", None)
    assert r["ok"] is False
    assert "MIA" in r["error"]


def test_cash_settlement_needs_no_reference():
    assert peco_txn.validate_settlement("AWAITING_PAY", "CASH", None)["ok"] is True


def test_cannot_settle_a_voided_transaction():
    r = peco_txn.validate_settlement("VOIDED", "CASH", None)
    assert r["ok"] is False


# ------------------------------------------------------------------
# Task 10 fix-pass 1: meter rollover documentation
# ------------------------------------------------------------------


def test_meter_rollover_is_not_reconstructed():
    """Переполнение счётчика намеренно НЕ восстанавливается: чтобы вычислить
    оборот, пришлось бы предполагать максимум счётчика, а ошибка в этом
    предположении зачислила бы неотпущенное топливо. Литры остаются в
    meter_delta смены и всплывают при закрытии как неоплаченные."""
    assert peco_txn.liters_from_meter(999999.000, 12.000) == 0.0


def test_equal_readings_dispense_nothing():
    assert peco_txn.liters_from_meter(1000.0, 1000.0) == 0.0


# ------------------------------------------------------------------
# Task 11: транзакции — авторизация, налив, оплата, аннулирование
# ------------------------------------------------------------------


def test_authorize_uses_current_price_and_opens_at_authorized():
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": True, "price": 23.90}
        store.insert_txn.return_value = {"success": True, "txn_id": 500}
        store.log_event.return_value = {"success": True}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=1000.0,
                               is_self_service=True, mia_ref="MIA-1")
    assert r["success"] is True and r["txn_id"] == 500
    assert store.insert_txn.call_args.kwargs["price"] == 23.90


def test_authorize_refuses_without_a_current_price():
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": False, "error": "Нет цены"}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=1000.0,
                               is_self_service=True)
    assert r["success"] is False
    store.insert_txn.assert_not_called()


def test_finish_dispense_computes_liters_and_amount_from_meter():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "DISPENSING", "meter_start": 1000.0,
            "price": 23.90, "is_self_service": 0, "nozzle_id": 3}}
        store.update_txn_status.return_value = {"success": True}
        r = peco_txn.finish_dispense(500, meter_end=1010.0)
    assert r["success"] is True
    assert r["liters"] == 10.0
    assert r["amount"] == 239.00
    assert r["status"] == "AWAITING_PAY"   # отпуск сотрудником ждёт кассы


def test_finish_dispense_self_service_goes_straight_to_paid():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 501, "status_code": "DISPENSING", "meter_start": 0.0,
            "price": 20.0, "is_self_service": 1, "nozzle_id": 3}}
        store.update_txn_status.return_value = {"success": True}
        r = peco_txn.finish_dispense(501, meter_end=5.0)
    assert r["status"] == "PAID"


def test_settle_refuses_mia_without_reference():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "AWAITING_PAY"}}
        r = peco_txn.settle(500, pay_method="MIA_QR", mia_ref=None)
    assert r["success"] is False
    store.update_txn_status.assert_not_called()


def test_settle_marks_paid_with_method():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "AWAITING_PAY", "liters": 10.0}}
        store.update_txn_status.return_value = {"success": True}
        store.log_event.return_value = {"success": True}
        r = peco_txn.settle(500, pay_method="CASH")
    assert r["success"] is True
    assert store.update_txn_status.call_args[0][1] == "PAID"


def test_void_is_refused_on_a_paid_transaction():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "PAID"}}
        r = peco_txn.void(500, reason="ошибка оператора")
    assert r["success"] is False
    store.update_txn_status.assert_not_called()


# ------------------------------------------------------------------
# Task 11 fix-pass 1: guarded status update, dropped log_event results,
# null txn_id, unreferenced self-service, backwards meter, shift not open,
# settling a still-running dispense
# ------------------------------------------------------------------


def test_update_txn_status_guards_on_expected_state():
    """Ожидаемый статус обязан быть в WHERE: проверка в Python оставляет
    окно, в котором второй оператор перезапишет уже оплаченную продажу."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.update_txn_status(500, "PAID", expected_status="AWAITING_PAY")
    assert r["success"] is True
    sql = db.execute_query.call_args_list[0][0][0]
    assert "STATUS_CODE = :expected_status" in sql


def test_update_txn_status_reports_a_lost_race():
    cm, _ = _rowcount_db(0)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.update_txn_status(500, "PAID", expected_status="AWAITING_PAY")
    assert r["success"] is False


def test_update_txn_status_rejects_an_unknown_field():
    cm, _ = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        try:
            PecoStore.update_txn_status(500, "PAID", pay_metod="CASH")
        except ValueError as e:
            assert "pay_metod" in str(e)
        else:
            raise AssertionError("опечатка в имени поля должна быть ошибкой")


def test_insert_txn_takes_station_from_the_open_shift_only():
    """Станция берётся из смены, а не от вызывающего, и только у ОТКРЫТОЙ смены:
    иначе колонка отпускала бы топливо на уже закрывающуюся смену."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(500,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        PecoStore.insert_txn(77, 3, "A95", 23.90, 1000.0, False)
    sql = db.execute_query.call_args_list[0][0][0]
    assert "FROM PECO_SHIFTS" in sql
    assert "'OPEN'" in sql


def test_meter_total_never_moves_backwards():
    """Счётчик не должен уезжать назад: с него берётся показание открытия
    следующей смены."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        PecoStore.update_txn_status(500, "PAID", expected_status="DISPENSING",
                                    meter_end=1010.0)
    meter_sql = [c[0][0] for c in db.execute_query.call_args_list
                 if "PECO_NOZZLES" in c[0][0]][0]
    assert "METER_TOTAL <= :meter_end" in meter_sql


def test_update_txn_status_draws_the_tank_down_in_the_same_transaction():
    """Списание резервуара обязано идти тем же UPDATE/commit, что и смена
    статуса — раздельный commit (как предлагал черновик задачи) оставляет
    окно, где продажа записана, а расход резервуара — нет, и tank_variance
    на закрытии смены расходится безвозвратно."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.update_txn_status(500, "PAID", expected_status="DISPENSING",
                                        meter_end=1010.0, liters=40.0, amount=800.0)
    assert r["success"] is True
    tank_sql_calls = [c[0][0] for c in db.execute_query.call_args_list
                      if "PECO_TANKS" in c[0][0]]
    assert len(tank_sql_calls) == 1
    tank_sql = tank_sql_calls[0]
    assert "CURRENT_L = CURRENT_L - :liters" in tank_sql
    assert "PECO_NOZZLES" in tank_sql and "PECO_TXN" in tank_sql
    assert db.connection.commit.call_count == 1


def test_update_txn_status_does_not_credit_the_tank_with_zero_liters():
    """Обратный или переполнившийся счётчик даёт liters=0 — такой отпуск
    не должен ничего списывать с резервуара."""
    cm, db = _rowcount_db(1)
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.update_txn_status(500, "VOIDED", expected_status="DISPENSING",
                                        meter_end=990.0, liters=0.0, amount=0.0)
    assert r["success"] is True
    tank_sql_calls = [c[0][0] for c in db.execute_query.call_args_list
                      if "PECO_TANKS" in c[0][0]]
    assert tank_sql_calls == []


def test_self_service_requires_a_mia_reference():
    """Продажа самообслуживания без ссылки предавторизации не сверяется
    с отчётом эквайера."""
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": True, "price": 23.90}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=0.0,
                               is_self_service=True)
    assert r["success"] is False
    store.insert_txn.assert_not_called()


def test_self_service_stores_the_mia_reference():
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": True, "price": 23.90}
        store.insert_txn.return_value = {"success": True, "txn_id": 500}
        store.log_event.return_value = {"success": True}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=0.0,
                               is_self_service=True, mia_ref="MIA-1")
    assert r["success"] is True
    assert store.insert_txn.call_args.kwargs["mia_ref"] == "MIA-1"


def test_authorize_rejects_a_null_txn_id():
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": True, "price": 23.90}
        store.insert_txn.return_value = {"success": True, "txn_id": None}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=0.0,
                               is_self_service=False)
    assert r["success"] is False


def test_cannot_settle_a_dispense_still_running():
    """Оплатить ещё идущий налив значит продать топливо за ноль:
    PAID терминален, и finish_dispense после этого уже не пройдёт."""
    assert peco_txn.validate_settlement("DISPENSING", "CASH", None)["ok"] is False


def test_cannot_settle_a_transaction_without_liters():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "AWAITING_PAY", "liters": 0.0}}
        r = peco_txn.settle(500, pay_method="CASH")
    assert r["success"] is False
    store.update_txn_status.assert_not_called()


def test_money_path_events_carry_the_shift():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "AWAITING_PAY", "liters": 10.0,
            "shift_id": 77}}
        store.update_txn_status.return_value = {"success": True}
        store.log_event.return_value = {"success": True}
        peco_txn.settle(500, pay_method="CASH")
    assert store.log_event.call_args.kwargs.get("shift_id") == 77


def test_settle_reports_a_lost_audit_record():
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 500, "status_code": "AWAITING_PAY", "liters": 10.0,
            "shift_id": 77}}
        store.update_txn_status.return_value = {"success": True}
        store.log_event.return_value = {"success": False, "error": "ORA-00942"}
        r = peco_txn.settle(500, pay_method="CASH")
    assert r["success"] is True
    assert "audit_warning" in r


from models import peco_inventory


def test_shortfall_is_positive_when_less_arrived_than_documented():
    assert peco_inventory.shortfall(5000.0, 4980.0) == 20.0
    assert peco_inventory.shortfall(5000.0, 5000.0) == 0.0
    assert peco_inventory.shortfall(5000.0, 5010.0) == -10.0  # излишек


def test_receive_delivery_writes_header_and_all_items():
    """Task 12 fix pass 1: приход теперь применяется одним вызовом
    apply_delivery (одна транзакция), а не отдельными вызовами store per
    item — тест переписан на новую границу, но проверяет то же самое:
    все строки уходят в store, резервуар зачисляется ФАКТИЧЕСКИ принятым
    объёмом (не документальным), и это же значение попадает в реестр
    открытой смены, потому что store читает liters_recv из тех же items."""
    items = [
        {"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
         "liters_recv": 4980.0, "dip_before": 3000.0, "dip_after": 7980.0},
        {"tank_id": 2, "grade_code": "DIESEL", "liters_doc": 3000.0,
         "liters_recv": 3000.0, "dip_before": 2000.0, "dip_after": 5000.0},
    ]
    with patch("models.peco_inventory.PecoStore") as store:
        store.apply_delivery.return_value = {"success": True, "delivery_id": 9}
        store.log_event.return_value = {"success": True}
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-77",
            items=items, employee_id=5)
    assert r["success"] is True
    assert r["delivery_id"] == 9
    store.apply_delivery.assert_called_once()
    call_kwargs = store.apply_delivery.call_args.kwargs
    # обе строки прихода уходят в store одним вызовом, вместе с их
    # ФАКТИЧЕСКИ принятыми объёмами (liters_recv), которыми store
    # зачислит и резервуар, и реестр открытой смены
    assert call_kwargs["items"] == items
    recv = [it["liters_recv"] for it in call_kwargs["items"]]
    assert recv == [4980.0, 3000.0]
    assert call_kwargs["station_id"] == 1
    assert call_kwargs["waybill_no"] == "WB-77"
    assert call_kwargs["employee_id"] == 5


def test_receive_delivery_reports_total_shortfall():
    items = [{"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
              "liters_recv": 4980.0}]
    with patch("models.peco_inventory.PecoStore") as store:
        store.apply_delivery.return_value = {"success": True, "delivery_id": 9}
        store.log_event.return_value = {"success": True}
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-78",
            items=items, employee_id=5)
    assert r["total_shortfall"] == 20.0


def test_receive_delivery_refuses_empty_item_list():
    with patch("models.peco_inventory.PecoStore") as store:
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-79",
            items=[], employee_id=5)
    assert r["success"] is False
    store.apply_delivery.assert_not_called()


# ------------------------------------------------------------------
# Task 12 fix pass 1: приход одной транзакцией + раздельные недостачи
# ------------------------------------------------------------------


def test_delivery_is_applied_in_one_transaction():
    """Приход обязан быть одной транзакцией: иначе сбой на середине оставит
    резервуары пополненными по накладной, которую не довели до конца, а
    уникальность накладной не даст повторить приём начисто."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(9,)],
                       "rowcount": 1})
    items = [{"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
              "liters_recv": 4980.0},
             {"tank_id": 2, "grade_code": "DIESEL", "liters_doc": 3000.0,
              "liters_recv": 3000.0}]
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.apply_delivery(1, "Petrom", "WB-1", items, 5)
    assert r["success"] is True
    # весь приём — один commit, а не по одному на каждое утверждение
    assert db.connection.commit.call_count == 1


def test_failed_delivery_commits_nothing():
    cm, db = _failing_db("ORA-00001")
    items = [{"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
              "liters_recv": 4980.0}]
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.apply_delivery(1, "Petrom", "WB-2", items, 5)
    assert r["success"] is False
    db.connection.commit.assert_not_called()


def test_tank_is_credited_with_received_not_documented_litres():
    """Зачесть документальные литры значит записать недостачу как топливо,
    которое есть; позже она всплывёт как необъяснимая утечка."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(9,)],
                       "rowcount": 1})
    items = [{"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
              "liters_recv": 4980.0}]
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        PecoStore.apply_delivery(1, "Petrom", "WB-3", items, 5)
    binds = [c[0][1] for c in db.execute_query.call_args_list
             if len(c[0]) > 1 and isinstance(c[0][1], dict)]
    credited = [b.get("liters") for b in binds if "liters" in b]
    assert 4980.0 in credited
    assert 5000.0 not in credited


def test_receive_delivery_reports_each_tank_shortfall_separately():
    """Чистая сумма скрыла бы недостачу в одном резервуаре за излишком
    в другом."""
    items = [
        {"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
         "liters_recv": 4980.0},
        {"tank_id": 2, "grade_code": "DIESEL", "liters_doc": 3000.0,
         "liters_recv": 3020.0},
    ]
    with patch("models.peco_inventory.PecoStore") as store:
        store.apply_delivery.return_value = {"success": True, "delivery_id": 9}
        store.log_event.return_value = {"success": True}
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-4",
            items=items, employee_id=5)
    assert r["total_shortfall"] == 0.0          # взаимно погасились
    assert len(r["shortfalls"]) == 2            # но каждый виден отдельно
    by_tank = {s["tank_id"]: s["shortfall"] for s in r["shortfalls"]}
    assert by_tank[1] == 20.0
    assert by_tank[2] == -20.0


def test_receive_delivery_propagates_a_store_failure():
    with patch("models.peco_inventory.PecoStore") as store:
        store.apply_delivery.return_value = {"success": False, "error": "ORA-00001"}
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-5",
            items=[{"tank_id": 1, "grade_code": "A95",
                    "liters_doc": 10.0, "liters_recv": 10.0}],
            employee_id=5)
    assert r["success"] is False
    store.log_event.assert_not_called()


from controllers.peco_controller import PecoController


def test_pump_state_requires_an_open_shift():
    with patch("controllers.peco_controller.PecoStore") as store:
        store.get_open_shift.return_value = {"success": False,
                                             "error": "Нет открытой смены"}
        r = PecoController.pump_state(station_id=1)
    assert r["success"] is False
    assert "смен" in r["error"].lower()


def test_pump_state_returns_nozzles_with_current_prices():
    with patch("controllers.peco_controller.PecoStore") as store:
        store.get_open_shift.return_value = {"success": True, "shift": {"id": 77}}
        store.list_nozzles.return_value = {"success": True, "items": [
            {"id": 3, "code": "N-A95", "grade_code": "A95", "meter_total": 1000.0,
             "pump_code": "P-1", "self_service": 1, "tank_id": 11},
        ]}
        store.list_grades.return_value = {"success": True, "items": [
            {"code": "A95", "name": "Бензин А-95", "color": "#2563eb"}]}
        store.current_price.return_value = {"success": True, "price": 23.90}
        r = PecoController.pump_state(station_id=1)
    assert r["success"] is True
    assert r["shift_id"] == 77
    assert r["prices"]["A95"] == 23.90
    assert r["nozzles"][0]["code"] == "N-A95"


def test_authorize_rejects_missing_fields():
    r = PecoController.authorize({"station_id": 1})
    assert r["success"] is False
    assert "nozzle_id" in r["error"]


def test_pay_passes_mia_reference_through():
    with patch("controllers.peco_controller.peco_txn") as txn:
        txn.settle.return_value = {"success": True, "status": "PAID"}
        r = PecoController.pay({"txn_id": 500, "pay_method": "MIA_QR",
                                "mia_ref": "MIA-ABC-1"})
    assert r["success"] is True
    txn.settle.assert_called_once_with(500, pay_method="MIA_QR",
                                       mia_ref="MIA-ABC-1")


def test_shift_close_forwards_declared_cash():
    with patch("controllers.peco_controller.peco_shift") as shift:
        shift.close_shift.return_value = {"success": True, "status": "CLOSED",
                                          "variances": {}}
        r = PecoController.shift_close({"shift_id": 77, "employee_id": 5,
                                        "cash_declared": 2400.0})
    assert r["success"] is True
    assert shift.close_shift.call_args.kwargs["cash_declared"] == 2400.0


def test_authorize_forwards_the_mia_reference():
    """Без ссылки предавторизации модель отказывает в отпуске, а MIA-итог
    смены нечем сверить с эквайером."""
    with patch("controllers.peco_controller.peco_txn") as txn:
        txn.authorize.return_value = {"success": True, "txn_id": 500}
        PecoController.authorize({
            "station_id": 1, "shift_id": 77, "nozzle_id": 3,
            "grade_code": "A95", "meter_start": 0.0,
            "is_self_service": True, "mia_ref": "MIA-7"})
    assert txn.authorize.call_args.kwargs["mia_ref"] == "MIA-7"


def test_controller_rejects_a_non_numeric_field_cleanly():
    """Мусор в запросе — ошибка запроса, а не 500."""
    r = PecoController.shift_close({"shift_id": "abc", "employee_id": 5,
                                    "cash_declared": 0.0})
    assert r["success"] is False
    assert "shift_id" in r["error"]


def test_controller_rejects_malformed_dips():
    r = PecoController.shift_close({"shift_id": 77, "employee_id": 5,
                                    "cash_declared": 0.0,
                                    "dips": {"x": "abc"}})
    assert r["success"] is False


def test_controller_rejects_a_dips_value_that_is_not_a_mapping():
    r = PecoController.shift_close({"shift_id": 77, "employee_id": 5,
                                    "cash_declared": 0.0,
                                    "dips": [1, 2, 3]})
    assert r["success"] is False


def test_controller_rejects_infinity():
    """float('1e999') не бросает исключение, а тихо даёт inf, который
    прошёл бы всю арифметику сверки и испортил расхождения смены.

    Модель замокана намеренно: без этого тест проходил бы из-за
    недоступной базы, а не из-за проверки на бесконечность."""
    with patch("controllers.peco_controller.peco_shift") as shift:
        shift.close_shift.return_value = {"success": True, "status": "CLOSED",
                                          "variances": {}}
        r = PecoController.shift_close({"shift_id": 77, "employee_id": 5,
                                        "cash_declared": "1e999"})
    assert r["success"] is False
    assert "cash_declared" in r["error"]
    shift.close_shift.assert_not_called()


def test_an_empty_till_can_still_close_a_shift():
    """Ноль наличных — законное значение, а не отсутствующее поле."""
    with patch("controllers.peco_controller.peco_shift") as shift:
        shift.close_shift.return_value = {"success": True, "status": "CLOSED",
                                          "variances": {}}
        r = PecoController.shift_close({"shift_id": 77, "employee_id": 5,
                                        "cash_declared": 0.0})
    assert r["success"] is True
    assert shift.close_shift.call_args.kwargs["cash_declared"] == 0.0


def test_default_station_is_one_cheap_query():
    """Опрос состояния колонки — самый горячий маршрут; выбирать станцию
    обходом всех 46 станций с остатками там нельзя."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(1,)]})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.default_station_id()
    assert r["success"] is True and r["station_id"] == 1
    assert db.execute_query.call_count == 1


def test_default_station_reports_when_none_are_active():
    cm, _ = _fake_db({"success": True, "columns": ["ID"], "data": []})
    with patch("models.peco_oracle_store.DatabaseModel", return_value=cm):
        r = PecoStore.default_station_id()
    assert r["success"] is False

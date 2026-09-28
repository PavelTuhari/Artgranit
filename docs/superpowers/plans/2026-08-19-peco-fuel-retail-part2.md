# PECO Fuel Retail ERP — Implementation Plan, Part 2 (Tasks 9–14)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
>
> **Read Part 1 first:** `docs/superpowers/plans/2026-08-19-peco-fuel-retail.md` — it holds the Global Constraints, file structure, and Tasks 1–8. Every constraint there applies here.

**Covers:** Task 9 (manager approval), Stage D (dispense state machine), Stage E (inventory), Task 14 (controller).

---

### Task 9: Manager approval of a disputed shift

**Files:**
- Modify: `models/peco_shift.py` (append)
- Modify: `models/peco_oracle_store.py` (append two methods to `PecoStore`)
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore.log_event`.
- Produces:
  - `PecoStore.get_employee(employee_id: int) -> dict` → `{"success": bool, "employee": {"id", "full_name", "role_code", "pin_hash", "station_id"}}`
  - `PecoStore.approve_shift(shift_id: int, employee_id: int) -> dict`
  - `peco_shift.approve_disputed(shift_id: int, manager_id: int, pin: str) -> dict`
  - `peco_shift.hash_pin(pin: str) -> str` — SHA-256 hex

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
def test_hash_pin_is_stable_and_not_plaintext():
    h = peco_shift.hash_pin("1234")
    assert h == peco_shift.hash_pin("1234")
    assert "1234" not in h
    assert len(h) == 64


def test_approve_disputed_rejects_non_manager():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee.return_value = {"success": True, "employee": {
            "id": 5, "role_code": "ATTENDANT",
            "pin_hash": peco_shift.hash_pin("1234")}}
        r = peco_shift.approve_disputed(77, manager_id=5, pin="1234")
    assert r["success"] is False
    assert "менеджер" in r["error"].lower()
    store.approve_shift.assert_not_called()


def test_approve_disputed_rejects_wrong_pin():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee.return_value = {"success": True, "employee": {
            "id": 9, "role_code": "MANAGER",
            "pin_hash": peco_shift.hash_pin("1234")}}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="9999")
    assert r["success"] is False
    store.approve_shift.assert_not_called()


def test_approve_disputed_accepts_manager_with_correct_pin():
    with patch("models.peco_shift.PecoStore") as store:
        store.get_employee.return_value = {"success": True, "employee": {
            "id": 9, "role_code": "MANAGER",
            "pin_hash": peco_shift.hash_pin("1234")}}
        store.approve_shift.return_value = {"success": True}
        r = peco_shift.approve_disputed(77, manager_id=9, pin="1234")
    assert r["success"] is True
    store.approve_shift.assert_called_once_with(77, 9)
    store.log_event.assert_called_once()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "pin or approve"`
Expected: FAIL — `AttributeError: module 'models.peco_shift' has no attribute 'hash_pin'`

- [ ] **Step 3: Add the store methods**

Append inside `class PecoStore` in `models/peco_oracle_store.py`:

```python
    @staticmethod
    def get_employee(employee_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_HASH
                         FROM PECO_EMPLOYEES
                        WHERE ID = :employee_id AND ACTIVE = 1""",
                    {"employee_id": employee_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Сотрудник не найден"}
                return {"success": True, "employee": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def approve_shift(shift_id: int, employee_id: int) -> Dict[str, Any]:
        """Подтверждение расхождения менеджером. Статус остаётся DISPUTED —
        расхождение не стирается, оно принимается под ответственность."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_SHIFTS SET APPROVED_BY = :employee_id
                        WHERE ID = :shift_id""",
                    {"shift_id": shift_id, "employee_id": employee_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Add the approval logic**

At the top of `models/peco_shift.py`, add below the existing imports:

```python
import hashlib
```

Append to the end of `models/peco_shift.py`:

```python
def hash_pin(pin: str) -> str:
    """SHA-256 от PIN. PIN в открытом виде не хранится и не логируется."""
    return hashlib.sha256(str(pin).encode("utf-8")).hexdigest()


def approve_disputed(shift_id: int, manager_id: int, pin: str) -> Dict[str, Any]:
    """Подтверждение смены с расхождением. Требует роль MANAGER или ADMIN.

    Расхождение при этом не обнуляется: статус остаётся DISPUTED, а в
    APPROVED_BY фиксируется, кто принял его под ответственность.
    """
    emp_r = PecoStore.get_employee(manager_id)
    if not emp_r.get("success"):
        return emp_r
    emp = emp_r["employee"]

    if emp.get("role_code") not in ("MANAGER", "ADMIN"):
        return {"success": False,
                "error": "Подтвердить расхождение может только менеджер"}

    if emp.get("pin_hash") != hash_pin(pin):
        return {"success": False, "error": "Неверный PIN"}

    saved = PecoStore.approve_shift(shift_id, manager_id)
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "SHIFT_APPROVED",
        shift_id=shift_id,
        entity_type="SHIFT",
        entity_id=shift_id,
        employee_id=manager_id,
    )
    return {"success": True}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 28 passed

- [ ] **Step 6: Commit**

```bash
git add models/peco_shift.py models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: подтверждение расхождения менеджером по PIN"
```

---

## Stage D — Dispense State Machine

### Task 10: Transition rules (pure functions)

**Files:**
- Create: `models/peco_txn.py`
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: nothing (pure).
- Produces:
  - `TRANSITIONS: dict[str, set[str]]`
  - `can_transition(current: str, target: str) -> bool`
  - `next_status_after_dispense(is_self_service: bool) -> str` — `"PAID"` path for self-service (pre-authorized), `"AWAITING_PAY"` for attendant
  - `compute_amount(liters: float, price: float) -> float` — rounds to 2 decimals, half-up
  - `liters_from_meter(meter_start: float, meter_end: float) -> float`
  - `validate_settlement(status: str, pay_method: str, mia_ref: str | None) -> dict` → `{"ok": bool, "error": str}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "transition or dispense or liters or amount or settlement"`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.peco_txn'`

- [ ] **Step 3: Write the module**

Create `models/peco_txn.py`:

```python
"""PECO: конечный автомат отпуска топлива.

Один автомат обслуживает оба режима — самообслуживание и отпуск
сотрудником. Различие сводится к флагу IS_SELF_SERVICE и к тому, кто
авторизовал операцию; отдельной ветки в коде для этого нет.

    AUTHORIZED -> DISPENSING -> AWAITING_PAY -> PAID
                       |              |
                       v              v
                    VOIDED         VOIDED

Функции этого модуля чистые: к базе не обращаются.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Set

TRANSITIONS: Dict[str, Set[str]] = {
    "AUTHORIZED":   {"DISPENSING", "VOIDED"},
    "DISPENSING":   {"AWAITING_PAY", "PAID", "VOIDED"},
    "AWAITING_PAY": {"PAID", "VOIDED"},
    "PAID":         set(),   # финальное состояние
    "VOIDED":       set(),   # финальное состояние
}

# Способы оплаты, требующие внешней ссылки на платёж
_REF_REQUIRED = {"MIA_QR"}

_SETTLEABLE = {"DISPENSING", "AWAITING_PAY"}


def can_transition(current: str, target: str) -> bool:
    """Разрешён ли переход. Неизвестный статус трактуется как запрет."""
    return target in TRANSITIONS.get(current, set())


def next_status_after_dispense(is_self_service: bool) -> str:
    """Самообслуживание предавторизовано по MIA QR — закрывается сразу
    при возврате пистолета. Отпуск сотрудником ждёт кассира."""
    return "PAID" if is_self_service else "AWAITING_PAY"


def liters_from_meter(meter_start: float, meter_end: float) -> float:
    """Литры считаются по счётчику, а не по вводу оператора.

    Показание назад означает сбой или подмену: возвращаем 0, чтобы
    отрицательный объём не попал в сверку и не замаскировал недостачу.
    """
    delta = float(meter_end) - float(meter_start)
    return round(delta, 3) if delta > 0 else 0.0


def compute_amount(liters: float, price: float) -> float:
    """Сумма к оплате, округление половины вверх до копейки."""
    value = Decimal(str(liters)) * Decimal(str(price))
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def validate_settlement(status: str, pay_method: str,
                        mia_ref: Optional[str]) -> Dict[str, Any]:
    """Можно ли закрыть транзакцию указанным способом оплаты."""
    if status not in _SETTLEABLE:
        return {"ok": False,
                "error": f"Нельзя оплатить транзакцию в статусе {status}"}
    if pay_method in _REF_REQUIRED and not mia_ref:
        return {"ok": False, "error": "Не указана ссылка платежа MIA"}
    return {"ok": True, "error": ""}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 37 passed

- [ ] **Step 5: Commit**

```bash
git add models/peco_txn.py tests/test_peco.py
git commit -m "PECO: конечный автомат отпуска топлива (чистые функции + тесты)"
```

---

### Task 11: Transaction persistence and settlement

**Files:**
- Modify: `models/peco_oracle_store.py` (append to `PecoStore`)
- Modify: `models/peco_txn.py` (append orchestration)
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore`, `can_transition`, `liters_from_meter`, `compute_amount`, `validate_settlement`, `next_status_after_dispense`.
- Produces:
  - `PecoStore.insert_txn(shift_id, nozzle_id, grade_code, price, meter_start, is_self_service, authorized_by) -> dict` → `{"success": True, "txn_id": int}`
  - `PecoStore.get_txn(txn_id: int) -> dict` → `{"success": bool, "txn": {...}}`
  - `PecoStore.update_txn_status(txn_id, status, **fields) -> dict`
  - `peco_txn.authorize(shift_id, nozzle_id, grade_code, station_id, meter_start, is_self_service, employee_id=None) -> dict`
  - `peco_txn.finish_dispense(txn_id: int, meter_end: float) -> dict`
  - `peco_txn.settle(txn_id: int, pay_method: str, mia_ref: str | None = None) -> dict`
  - `peco_txn.void(txn_id: int, reason: str) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
def test_authorize_uses_current_price_and_opens_at_authorized():
    with patch("models.peco_txn.PecoStore") as store:
        store.current_price.return_value = {"success": True, "price": 23.90}
        store.insert_txn.return_value = {"success": True, "txn_id": 500}
        r = peco_txn.authorize(shift_id=77, nozzle_id=3, grade_code="A95",
                               station_id=1, meter_start=1000.0,
                               is_self_service=True)
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
            "id": 500, "status_code": "AWAITING_PAY"}}
        store.update_txn_status.return_value = {"success": True}
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "authorize or finish_dispense or settle or void"`
Expected: FAIL — `AttributeError: module 'models.peco_txn' has no attribute 'authorize'`

- [ ] **Step 3: Add the store methods**

Append inside `class PecoStore` in `models/peco_oracle_store.py`:

```python
    # ---------------- транзакции ----------------

    @staticmethod
    def insert_txn(shift_id: int, nozzle_id: int, grade_code: str,
                   price: float, meter_start: float,
                   is_self_service: bool,
                   authorized_by: Optional[int] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_TXN
                              (ID, SHIFT_ID, NOZZLE_ID, GRADE_CODE, STATUS_CODE,
                               PRICE, METER_START, IS_SELF_SERVICE, AUTHORIZED_BY)
                       VALUES (PECO_TXN_SEQ.NEXTVAL, :shift_id, :nozzle_id,
                               :grade_code, 'AUTHORIZED', :price, :meter_start,
                               :is_self_service, :authorized_by)""",
                    {
                        "shift_id": shift_id,
                        "nozzle_id": nozzle_id,
                        "grade_code": grade_code,
                        "price": price,
                        "meter_start": meter_start,
                        "is_self_service": 1 if is_self_service else 0,
                        "authorized_by": authorized_by,
                    },
                )
                r = db.execute_query(
                    "SELECT PECO_TXN_SEQ.CURRVAL AS ID FROM dual"
                )
                db.connection.commit()
                rows = _norm_rows(r)
                return {"success": True,
                        "txn_id": int(rows[0]["id"]) if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_txn(txn_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT ID, SHIFT_ID, NOZZLE_ID, GRADE_CODE, STATUS_CODE,
                              LITERS, PRICE, AMOUNT, PAY_METHOD, IS_SELF_SERVICE,
                              MIA_REF, METER_START, METER_END
                         FROM PECO_TXN WHERE ID = :txn_id""",
                    {"txn_id": txn_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Транзакция не найдена"}
                return {"success": True, "txn": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_txn_status(txn_id: int, status: str,
                          **fields: Any) -> Dict[str, Any]:
        """Обновляет статус и переданные поля. Имена полей проверяются по
        белому списку — в SQL не попадает ничего из внешнего ввода."""
        allowed = {"liters", "amount", "pay_method", "mia_ref", "meter_end"}
        sets = ["STATUS_CODE = :status"]
        params: Dict[str, Any] = {"txn_id": txn_id, "status": status}

        for key, value in fields.items():
            if key not in allowed:
                continue
            sets.append(f"{key.upper()} = :{key}")
            params[key] = value

        if status == "PAID":
            sets.append("PAID_AT = SYSTIMESTAMP")

        try:
            with DatabaseModel() as db:
                db.execute_query(
                    f"UPDATE PECO_TXN SET {', '.join(sets)} WHERE ID = :txn_id",
                    params,
                )
                # тотализатор пистолета двигается вместе с завершённым наливом
                if "meter_end" in params and params["meter_end"] is not None:
                    db.execute_query(
                        """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_end
                            WHERE ID = (SELECT NOZZLE_ID FROM PECO_TXN
                                         WHERE ID = :txn_id)""",
                        {"meter_end": params["meter_end"], "txn_id": txn_id},
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Add the orchestration to `models/peco_txn.py`**

At the top of `models/peco_txn.py`, add below the `typing` import:

```python
from models.peco_oracle_store import PecoStore
```

Append to the end of `models/peco_txn.py`:

```python
# ------------------------------------------------------------------
# Оркестрация
# ------------------------------------------------------------------


def authorize(shift_id: int, nozzle_id: int, grade_code: str,
              station_id: int, meter_start: float, is_self_service: bool,
              employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Авторизует налив по действующей цене.

    Цена фиксируется в транзакции: смена цены посреди смены не должна
    переписывать то, что клиент уже заплатил.
    """
    price_r = PecoStore.current_price(station_id, grade_code)
    if not price_r.get("success"):
        return price_r

    created = PecoStore.insert_txn(
        shift_id=shift_id,
        nozzle_id=nozzle_id,
        grade_code=grade_code,
        price=price_r["price"],
        meter_start=meter_start,
        is_self_service=is_self_service,
        authorized_by=employee_id,
    )
    if not created.get("success"):
        return created

    PecoStore.log_event(
        "TXN_AUTHORIZED", station_id=station_id, shift_id=shift_id,
        entity_type="TXN", entity_id=created["txn_id"], employee_id=employee_id,
        payload={"grade": grade_code, "price": price_r["price"]},
    )
    return {"success": True, "txn_id": created["txn_id"],
            "price": price_r["price"]}


def start_dispense(txn_id: int) -> Dict[str, Any]:
    """AUTHORIZED -> DISPENSING."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]
    if not can_transition(current, "DISPENSING"):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> DISPENSING"}
    saved = PecoStore.update_txn_status(txn_id, "DISPENSING")
    if not saved.get("success"):
        return saved
    return {"success": True, "status": "DISPENSING"}


def finish_dispense(txn_id: int, meter_end: float) -> Dict[str, Any]:
    """Завершает налив: литры и сумма считаются по счётчику."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    txn = txn_r["txn"]
    current = txn["status_code"]

    is_self = bool(int(txn.get("is_self_service") or 0))
    target = next_status_after_dispense(is_self)

    if not can_transition(current, target):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> {target}"}

    liters = liters_from_meter(float(txn["meter_start"]), meter_end)
    amount = compute_amount(liters, float(txn["price"]))

    fields: Dict[str, Any] = {"liters": liters, "amount": amount,
                              "meter_end": meter_end}
    if target == "PAID":
        # самообслуживание предавторизовано по MIA QR
        fields["pay_method"] = "MIA_QR"

    saved = PecoStore.update_txn_status(txn_id, target, **fields)
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_DISPENSED", entity_type="TXN", entity_id=txn_id,
        payload={"liters": liters, "amount": amount, "status": target},
    )
    return {"success": True, "status": target, "liters": liters,
            "amount": amount}


def settle(txn_id: int, pay_method: str,
           mia_ref: Optional[str] = None) -> Dict[str, Any]:
    """Закрывает транзакцию оплатой на кассе или по MIA QR."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]

    check = validate_settlement(current, pay_method, mia_ref)
    if not check["ok"]:
        return {"success": False, "error": check["error"]}

    if not can_transition(current, "PAID"):
        return {"success": False,
                "error": f"Недопустимый переход {current} -> PAID"}

    saved = PecoStore.update_txn_status(
        txn_id, "PAID", pay_method=pay_method, mia_ref=mia_ref
    )
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_PAID", entity_type="TXN", entity_id=txn_id,
        payload={"pay_method": pay_method},
    )
    return {"success": True, "status": "PAID"}


def void(txn_id: int, reason: str) -> Dict[str, Any]:
    """Аннулирует незавершённую транзакцию. Оплаченную аннулировать нельзя."""
    txn_r = PecoStore.get_txn(txn_id)
    if not txn_r.get("success"):
        return txn_r
    current = txn_r["txn"]["status_code"]

    if not can_transition(current, "VOIDED"):
        return {"success": False,
                "error": f"Нельзя аннулировать транзакцию в статусе {current}"}

    saved = PecoStore.update_txn_status(txn_id, "VOIDED")
    if not saved.get("success"):
        return saved

    PecoStore.log_event(
        "TXN_VOIDED", entity_type="TXN", entity_id=txn_id,
        payload={"reason": reason},
    )
    return {"success": True, "status": "VOIDED"}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 44 passed

- [ ] **Step 6: Commit**

```bash
git add models/peco_txn.py models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: транзакции — авторизация, налив, оплата, аннулирование"
```

---

## Stage E — Inventory

### Task 12: Delivery intake

**Files:**
- Create: `models/peco_inventory.py`
- Modify: `models/peco_oracle_store.py` (append)
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore`.
- Produces:
  - `PecoStore.insert_delivery(station_id, supplier, waybill_no, driver_name, vehicle_no) -> dict` → `{"success": True, "delivery_id": int}`
  - `PecoStore.insert_delivery_item(delivery_id, tank_id, grade_code, liters_doc, liters_recv, temperature_c, dip_before, dip_after) -> dict`
  - `PecoStore.add_tank_volume(tank_id: int, liters: float) -> dict`
  - `PecoStore.accept_delivery(delivery_id: int, employee_id: int) -> dict`
  - `peco_inventory.shortfall(liters_doc: float, liters_recv: float) -> float`
  - `peco_inventory.receive_delivery(station_id, supplier, waybill_no, items, employee_id, driver_name=None, vehicle_no=None) -> dict`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
from models import peco_inventory


def test_shortfall_is_positive_when_less_arrived_than_documented():
    assert peco_inventory.shortfall(5000.0, 4980.0) == 20.0
    assert peco_inventory.shortfall(5000.0, 5000.0) == 0.0
    assert peco_inventory.shortfall(5000.0, 5010.0) == -10.0  # излишек


def test_receive_delivery_writes_header_and_all_items():
    items = [
        {"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
         "liters_recv": 4980.0, "dip_before": 3000.0, "dip_after": 7980.0},
        {"tank_id": 2, "grade_code": "DIESEL", "liters_doc": 3000.0,
         "liters_recv": 3000.0, "dip_before": 2000.0, "dip_after": 5000.0},
    ]
    with patch("models.peco_inventory.PecoStore") as store:
        store.insert_delivery.return_value = {"success": True, "delivery_id": 9}
        store.insert_delivery_item.return_value = {"success": True}
        store.add_tank_volume.return_value = {"success": True}
        store.accept_delivery.return_value = {"success": True}
        r = peco_inventory.receive_delivery(
            station_id=1, supplier="Petrom", waybill_no="WB-77",
            items=items, employee_id=5)
    assert r["success"] is True
    assert r["delivery_id"] == 9
    assert store.insert_delivery_item.call_count == 2
    # остаток растёт на ФАКТИЧЕСКИ принятый объём, не на документальный
    added = [c.kwargs["liters"] for c in store.add_tank_volume.call_args_list]
    assert added == [4980.0, 3000.0]


def test_receive_delivery_reports_total_shortfall():
    items = [{"tank_id": 1, "grade_code": "A95", "liters_doc": 5000.0,
              "liters_recv": 4980.0}]
    with patch("models.peco_inventory.PecoStore") as store:
        store.insert_delivery.return_value = {"success": True, "delivery_id": 9}
        store.insert_delivery_item.return_value = {"success": True}
        store.add_tank_volume.return_value = {"success": True}
        store.accept_delivery.return_value = {"success": True}
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
    store.insert_delivery.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "shortfall or receive_delivery"`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.peco_inventory'`

- [ ] **Step 3: Add the store methods**

Append inside `class PecoStore` in `models/peco_oracle_store.py`:

```python
    # ---------------- приход цистерн ----------------

    @staticmethod
    def insert_delivery(station_id: int, supplier: str, waybill_no: str,
                        driver_name: Optional[str] = None,
                        vehicle_no: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_DELIVERIES
                              (ID, STATION_ID, SUPPLIER, WAYBILL_NO,
                               DRIVER_NAME, VEHICLE_NO)
                       VALUES (PECO_DELIVERIES_SEQ.NEXTVAL, :station_id,
                               :supplier, :waybill_no, :driver_name,
                               :vehicle_no)""",
                    {"station_id": station_id, "supplier": supplier,
                     "waybill_no": waybill_no, "driver_name": driver_name,
                     "vehicle_no": vehicle_no},
                )
                r = db.execute_query(
                    "SELECT PECO_DELIVERIES_SEQ.CURRVAL AS ID FROM dual"
                )
                db.connection.commit()
                rows = _norm_rows(r)
                return {"success": True,
                        "delivery_id": int(rows[0]["id"]) if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def insert_delivery_item(delivery_id: int, tank_id: int, grade_code: str,
                             liters_doc: float, liters_recv: float,
                             temperature_c: Optional[float] = None,
                             dip_before: Optional[float] = None,
                             dip_after: Optional[float] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_DELIVERY_ITEMS
                              (ID, DELIVERY_ID, TANK_ID, GRADE_CODE,
                               LITERS_DOC, LITERS_RECV, TEMPERATURE_C,
                               DIP_BEFORE_L, DIP_AFTER_L)
                       VALUES (PECO_DELIVERY_ITEMS_SEQ.NEXTVAL, :delivery_id,
                               :tank_id, :grade_code, :liters_doc, :liters_recv,
                               :temperature_c, :dip_before, :dip_after)""",
                    {"delivery_id": delivery_id, "tank_id": tank_id,
                     "grade_code": grade_code, "liters_doc": liters_doc,
                     "liters_recv": liters_recv, "temperature_c": temperature_c,
                     "dip_before": dip_before, "dip_after": dip_after},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def add_tank_volume(tank_id: int, liters: float) -> Dict[str, Any]:
        """Прибавляет к остатку резервуара. Отрицательное значение — расход."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_TANKS
                          SET CURRENT_L = CURRENT_L + :liters
                        WHERE ID = :tank_id""",
                    {"tank_id": tank_id, "liters": liters},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def accept_delivery(delivery_id: int, employee_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_DELIVERIES
                          SET ACCEPTED_AT = SYSTIMESTAMP,
                              ACCEPTED_BY = :employee_id
                        WHERE ID = :delivery_id""",
                    {"delivery_id": delivery_id, "employee_id": employee_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def insert_tank_dip(tank_id: int, measured_l: float, dip_kind: str,
                        shift_id: Optional[int] = None,
                        employee_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_TANK_DIPS
                              (ID, TANK_ID, SHIFT_ID, MEASURED_L,
                               MEASURED_BY, DIP_KIND)
                       VALUES (PECO_TANK_DIPS_SEQ.NEXTVAL, :tank_id, :shift_id,
                               :measured_l, :employee_id, :dip_kind)""",
                    {"tank_id": tank_id, "shift_id": shift_id,
                     "measured_l": measured_l, "employee_id": employee_id,
                     "dip_kind": dip_kind},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_tank_levels(station_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT TANK_ID, TANK_CODE, GRADE_CODE, GRADE_NAME,
                              CAPACITY_L, CURRENT_L, MIN_ALARM_L,
                              FILL_PCT, IS_LOW
                         FROM V_PECO_TANK_LEVELS
                        WHERE STATION_ID = :station_id
                        ORDER BY GRADE_CODE""",
                    {"station_id": station_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Write `models/peco_inventory.py`**

```python
"""PECO: складской контур — приход цистерн, замеры, остатки резервуаров.

Реестр резервуара ведётся по формуле
    остаток = предыдущий остаток + принято − отпущено по счётчику
с периодической корректировкой ручными замерами (PECO_TANK_DIPS).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.peco_oracle_store import PecoStore


def shortfall(liters_doc: float, liters_recv: float) -> float:
    """Недолив: положительное значение = приняли меньше, чем по накладной."""
    return round(float(liters_doc) - float(liters_recv), 3)


def receive_delivery(
    station_id: int,
    supplier: str,
    waybill_no: str,
    items: List[Dict[str, Any]],
    employee_id: int,
    driver_name: Optional[str] = None,
    vehicle_no: Optional[str] = None,
) -> Dict[str, Any]:
    """Принимает цистерну: шапка + строки по резервуарам.

    Остаток резервуара растёт на ФАКТИЧЕСКИ принятый объём, а не на
    документальный: иначе недолив осел бы в учёте как наличное топливо
    и всплыл позже как необъяснимая утечка.
    """
    if not items:
        return {"success": False, "error": "Не указано ни одной строки прихода"}

    header = PecoStore.insert_delivery(
        station_id=station_id, supplier=supplier, waybill_no=waybill_no,
        driver_name=driver_name, vehicle_no=vehicle_no,
    )
    if not header.get("success"):
        return header
    delivery_id = header["delivery_id"]

    total_shortfall = 0.0
    for it in items:
        liters_doc = float(it.get("liters_doc") or 0.0)
        liters_recv = float(it.get("liters_recv") or 0.0)
        total_shortfall += shortfall(liters_doc, liters_recv)

        saved = PecoStore.insert_delivery_item(
            delivery_id=delivery_id,
            tank_id=it["tank_id"],
            grade_code=it["grade_code"],
            liters_doc=liters_doc,
            liters_recv=liters_recv,
            temperature_c=it.get("temperature_c"),
            dip_before=it.get("dip_before"),
            dip_after=it.get("dip_after"),
        )
        if not saved.get("success"):
            return saved

        added = PecoStore.add_tank_volume(tank_id=it["tank_id"],
                                          liters=liters_recv)
        if not added.get("success"):
            return added

        if it.get("dip_after") is not None:
            PecoStore.insert_tank_dip(
                tank_id=it["tank_id"], measured_l=float(it["dip_after"]),
                dip_kind="DELIVERY", employee_id=employee_id,
            )

    accepted = PecoStore.accept_delivery(delivery_id, employee_id)
    if not accepted.get("success"):
        return accepted

    PecoStore.log_event(
        "DELIVERY_RECEIVED", station_id=station_id, entity_type="DELIVERY",
        entity_id=delivery_id, employee_id=employee_id,
        payload={"waybill": waybill_no, "items": len(items),
                 "shortfall": round(total_shortfall, 3)},
    )
    return {"success": True, "delivery_id": delivery_id,
            "total_shortfall": round(total_shortfall, 3)}


def record_dip(tank_id: int, measured_l: float, dip_kind: str,
               shift_id: Optional[int] = None,
               employee_id: Optional[int] = None) -> Dict[str, Any]:
    """Фиксирует ручной замер уровня."""
    if dip_kind not in ("OPEN", "CLOSE", "DELIVERY", "CONTROL"):
        return {"success": False, "error": f"Неизвестный тип замера: {dip_kind}"}
    return PecoStore.insert_tank_dip(
        tank_id=tank_id, measured_l=measured_l, dip_kind=dip_kind,
        shift_id=shift_id, employee_id=employee_id,
    )


def tank_levels(station_id: int) -> Dict[str, Any]:
    """Остатки резервуаров станции с признаком низкого уровня."""
    return PecoStore.list_tank_levels(station_id)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 48 passed

- [ ] **Step 6: Commit**

```bash
git add models/peco_inventory.py models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: приём цистерн, замеры, остатки резервуаров"
```

---

### Task 13: Dispensing draws down the tank

The tank ledger must fall when fuel leaves the nozzle, not only when a delivery arrives. Without this, `tank_variance` is meaningless.

**Files:**
- Modify: `models/peco_txn.py` (`finish_dispense`)
- Modify: `models/peco_oracle_store.py` (`get_txn` returns `tank_id`)
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore.add_tank_volume` from Task 12.
- Produces: no new signatures — `finish_dispense` gains the side effect of decrementing the tank.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_peco.py`:

```python
def test_finish_dispense_draws_the_tank_down():
    """Отпуск через пистолет должен уменьшать остаток резервуара, иначе
    tank_variance теряет смысл."""
    with patch("models.peco_txn.PecoStore") as store:
        store.get_txn.return_value = {"success": True, "txn": {
            "id": 502, "status_code": "DISPENSING", "meter_start": 0.0,
            "price": 20.0, "is_self_service": 0, "nozzle_id": 3,
            "tank_id": 11}}
        store.update_txn_status.return_value = {"success": True}
        store.add_tank_volume.return_value = {"success": True}
        r = peco_txn.finish_dispense(502, meter_end=40.0)
    assert r["success"] is True
    store.add_tank_volume.assert_called_once_with(tank_id=11, liters=-40.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_peco.py -v -k "draws_the_tank_down"`
Expected: FAIL — `AssertionError: Expected 'add_tank_volume' to be called once. Called 0 times.`

- [ ] **Step 3: Make `get_txn` return the tank**

In `models/peco_oracle_store.py`, replace the SQL inside `get_txn` with:

```python
                    """SELECT t.ID, t.SHIFT_ID, t.NOZZLE_ID, t.GRADE_CODE,
                              t.STATUS_CODE, t.LITERS, t.PRICE, t.AMOUNT,
                              t.PAY_METHOD, t.IS_SELF_SERVICE, t.MIA_REF,
                              t.METER_START, t.METER_END, n.TANK_ID
                         FROM PECO_TXN t
                         JOIN PECO_NOZZLES n ON n.ID = t.NOZZLE_ID
                        WHERE t.ID = :txn_id""",
```

- [ ] **Step 4: Draw down the tank in `finish_dispense`**

In `models/peco_txn.py`, inside `finish_dispense`, insert directly after the `if not saved.get("success"): return saved` block and before the `PecoStore.log_event(...)` call:

```python
    # Топливо физически покинуло резервуар — реестр должен это отразить,
    # иначе tank_variance при закрытии смены ничего не значит.
    tank_id = txn.get("tank_id")
    if tank_id and liters > 0:
        PecoStore.add_tank_volume(tank_id=tank_id, liters=-liters)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 49 passed

- [ ] **Step 6: Commit**

```bash
git add models/peco_txn.py models/peco_oracle_store.py tests/test_peco.py
git commit -m "PECO: отпуск топлива списывает остаток резервуара"
```

---

## Stage F — Controller

### Task 14: PECO controller

**Files:**
- Create: `controllers/peco_controller.py`
- Modify: `tests/test_peco.py`

**Interfaces:**
- Consumes: `PecoStore`, `peco_shift`, `peco_txn`, `peco_inventory`.
- Produces `PecoController` with static methods, each returning a JSON-serializable dict:
  - `pump_state(station_id: int) -> dict` → `{"success", "station_id", "shift_id", "nozzles": [...], "prices": {grade: price}}`
  - `authorize(payload: dict) -> dict`
  - `finish(payload: dict) -> dict`
  - `pay(payload: dict) -> dict`
  - `shift_open(payload: dict) -> dict`
  - `shift_close(payload: dict) -> dict`
  - `shift_approve(payload: dict) -> dict`
  - `delivery_receive(payload: dict) -> dict`
  - `admin_overview() -> dict` → `{"success", "stations": [...], "low_tanks": [...]}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_peco.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_peco.py -v -k "pump_state or authorize_rejects or pay_passes or shift_close_forwards"`
Expected: FAIL — `ModuleNotFoundError: No module named 'controllers.peco_controller'`

- [ ] **Step 3: Write the controller**

Create `controllers/peco_controller.py`:

```python
"""Контроллер модуля PECO — розничная продажа топлива в сети АЗС.

Спецификация: docs/superpowers/specs/2026-08-19-peco-fuel-retail-design.md
Oracle-объекты: префикс PECO_ (sql/100_peco_tables.sql ... 104_peco_demo_data.sql).

Слой отвечает только за приём запроса, проверку полей и формирование
ответа. Бизнес-правила живут в models/peco_shift.py, models/peco_txn.py
и models/peco_inventory.py.
"""
import os
import sys
from typing import Any, Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.peco_oracle_store import PecoStore
from models import peco_shift, peco_txn, peco_inventory


def _require(payload: Dict[str, Any], *names: str) -> Optional[str]:
    """Возвращает имя первого отсутствующего поля или None."""
    for n in names:
        if payload.get(n) in (None, ""):
            return n
    return None


class PecoController:
    """Маршрутная логика фронт-офиса, консоли смены и бэк-офиса."""

    # ---------------- фронт-офис колонки ----------------

    @staticmethod
    def pump_state(station_id: int) -> Dict[str, Any]:
        """Состояние станции для экрана колонки: смена, пистолеты, цены."""
        shift_r = PecoStore.get_open_shift(station_id)
        if not shift_r.get("success"):
            return {"success": False,
                    "error": "Нет открытой смены — отпуск невозможен"}

        nozzles_r = PecoStore.list_nozzles(station_id)
        if not nozzles_r.get("success"):
            return nozzles_r

        grades_r = PecoStore.list_grades()
        grades = grades_r.get("items", []) if grades_r.get("success") else []

        prices: Dict[str, float] = {}
        for g in grades:
            p = PecoStore.current_price(station_id, g["code"])
            if p.get("success"):
                prices[g["code"]] = p["price"]

        return {
            "success": True,
            "station_id": station_id,
            "shift_id": shift_r["shift"]["id"],
            "nozzles": nozzles_r["items"],
            "grades": grades,
            "prices": prices,
        }

    @staticmethod
    def authorize(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "shift_id", "nozzle_id",
                           "grade_code", "meter_start")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}

        return peco_txn.authorize(
            shift_id=int(payload["shift_id"]),
            nozzle_id=int(payload["nozzle_id"]),
            grade_code=payload["grade_code"],
            station_id=int(payload["station_id"]),
            meter_start=float(payload["meter_start"]),
            is_self_service=bool(payload.get("is_self_service")),
            employee_id=payload.get("employee_id"),
        )

    @staticmethod
    def start(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.start_dispense(int(payload["txn_id"]))

    @staticmethod
    def finish(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "meter_end")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.finish_dispense(int(payload["txn_id"]),
                                        float(payload["meter_end"]))

    @staticmethod
    def pay(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id", "pay_method")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.settle(
            int(payload["txn_id"]),
            pay_method=payload["pay_method"],
            mia_ref=payload.get("mia_ref"),
        )

    @staticmethod
    def void(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "txn_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_txn.void(int(payload["txn_id"]),
                             reason=payload.get("reason") or "не указана")

    # ---------------- консоль смены ----------------

    @staticmethod
    def shift_open(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.open_shift(int(payload["station_id"]),
                                     int(payload["employee_id"]))

    @staticmethod
    def shift_meters(shift_id: int) -> Dict[str, Any]:
        return PecoStore.get_shift_meters(shift_id)

    @staticmethod
    def shift_save_meter(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "shift_id", "nozzle_id", "meter_close")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return PecoStore.save_meter_close(
            int(payload["shift_id"]), int(payload["nozzle_id"]),
            float(payload["meter_close"]),
        )

    @staticmethod
    def shift_close(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "shift_id", "employee_id", "cash_declared")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.close_shift(
            int(payload["shift_id"]),
            employee_id=int(payload["employee_id"]),
            cash_declared=float(payload["cash_declared"]),
            tank_readings=payload.get("tank_readings"),
        )

    @staticmethod
    def shift_approve(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "shift_id", "manager_id", "pin")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return peco_shift.approve_disputed(
            int(payload["shift_id"]), int(payload["manager_id"]),
            str(payload["pin"]),
        )

    # ---------------- склад ----------------

    @staticmethod
    def delivery_receive(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "supplier", "waybill_no",
                           "employee_id")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        items: List[Dict[str, Any]] = payload.get("items") or []
        return peco_inventory.receive_delivery(
            station_id=int(payload["station_id"]),
            supplier=payload["supplier"],
            waybill_no=payload["waybill_no"],
            items=items,
            employee_id=int(payload["employee_id"]),
            driver_name=payload.get("driver_name"),
            vehicle_no=payload.get("vehicle_no"),
        )

    @staticmethod
    def tank_levels(station_id: int) -> Dict[str, Any]:
        return peco_inventory.tank_levels(station_id)

    # ---------------- бэк-офис ----------------

    @staticmethod
    def admin_overview() -> Dict[str, Any]:
        """Сводка по сети: станции и резервуары с низким уровнем."""
        stations_r = PecoStore.list_stations()
        if not stations_r.get("success"):
            return stations_r

        low: List[Dict[str, Any]] = []
        for st in stations_r["items"]:
            levels = PecoStore.list_tank_levels(st["id"])
            if not levels.get("success"):
                continue
            for t in levels["items"]:
                if int(t.get("is_low") or 0) == 1:
                    low.append(dict(t, station_name=st["name"]))

        return {"success": True, "stations": stations_r["items"],
                "low_tanks": low}

    @staticmethod
    def set_price(payload: Dict[str, Any]) -> Dict[str, Any]:
        missing = _require(payload, "station_id", "grade_code", "price")
        if missing:
            return {"success": False, "error": f"Не указано поле: {missing}"}
        return PecoStore.set_price(int(payload["station_id"]),
                                   payload["grade_code"],
                                   float(payload["price"]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_peco.py -v`
Expected: PASS — 54 passed

- [ ] **Step 5: Commit**

```bash
git add controllers/peco_controller.py tests/test_peco.py
git commit -m "PECO: контроллер фронт-офиса, консоли смены и бэк-офиса"
```

---

**Continues in Part 3:** `docs/superpowers/plans/2026-08-19-peco-fuel-retail-part3.md` — Task 15 (routes in `app.py`), Stage G (Tasks 16–18, templates), Stage H (Tasks 19–20, `docs/PECO/TZ.html` and module documentation).

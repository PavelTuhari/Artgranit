"""PECO module Oracle store — все операции с таблицами PECO_*.

Только persistence. Бизнес-правила живут в models/peco_shift.py,
models/peco_txn.py и models/peco_inventory.py.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel


def _norm_rows(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    """{success, columns, data} -> список словарей с ключами в нижнем регистре."""
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


class PecoStore:
    """CRUD по справочникам, мастер-данным и ценам PECO."""

    # ---------------- справочники ----------------

    @staticmethod
    def list_grades() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT CODE, NAME, COLOR, DENSITY
                         FROM PECO_REF_FUEL_GRADES
                        ORDER BY SORT_ORDER"""
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- мастер-данные ----------------

    @staticmethod
    def list_stations(active_only: bool = True) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT ID, CODE, NAME, ADDRESS, REGION, ACTIVE
                           FROM PECO_STATIONS"""
                if active_only:
                    sql += " WHERE ACTIVE = 1"
                sql += " ORDER BY CODE"
                r = db.execute_query(sql)
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_nozzles(station_id: int) -> Dict[str, Any]:
        """Активные пистолеты станции с колонкой, резервуаром и счётчиком."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT n.ID, n.CODE, n.GRADE_CODE, n.METER_TOTAL,
                              n.TANK_ID, p.ID AS PUMP_ID, p.CODE AS PUMP_CODE,
                              p.SELF_SERVICE
                         FROM PECO_NOZZLES n
                         JOIN PECO_PUMPS p ON p.ID = n.PUMP_ID
                        WHERE p.STATION_ID = :station_id
                          AND n.ACTIVE = 1 AND p.ACTIVE = 1
                        ORDER BY p.CODE, n.CODE""",
                    {"station_id": station_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- цены ----------------

    @staticmethod
    def current_price(station_id: int, grade_code: str) -> Dict[str, Any]:
        """Действующая цена = строка с VALID_TO IS NULL."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT PRICE FROM PECO_PRICES
                        WHERE STATION_ID = :station_id
                          AND GRADE_CODE = :grade_code
                          AND VALID_TO IS NULL""",
                    {"station_id": station_id, "grade_code": grade_code},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False,
                            "error": f"Нет действующей цены: {grade_code}"}
                return {"success": True, "price": float(rows[0]["price"])}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_price(station_id: int, grade_code: str, price: float) -> Dict[str, Any]:
        """Закрывает предыдущую цену и вставляет новую. In-place не обновляем:
        транзакции хранят цену проведения, история должна оставаться верной."""
        params = {"station_id": station_id, "grade_code": grade_code}
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE PECO_PRICES SET VALID_TO = SYSTIMESTAMP
                        WHERE STATION_ID = :station_id
                          AND GRADE_CODE = :grade_code
                          AND VALID_TO IS NULL""",
                    params,
                )
                db.execute_query(
                    """INSERT INTO PECO_PRICES
                              (ID, STATION_ID, GRADE_CODE, PRICE)
                       VALUES (PECO_PRICES_SEQ.NEXTVAL, :station_id,
                               :grade_code, :price)""",
                    dict(params, price=price),
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- журнал событий ----------------

    @staticmethod
    def log_event(
        event_type: str,
        station_id: Optional[int] = None,
        shift_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        employee_id: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append-only запись в PECO_EVENT_LOG."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO PECO_EVENT_LOG
                              (ID, STATION_ID, SHIFT_ID, EVENT_TYPE,
                               ENTITY_TYPE, ENTITY_ID, EMPLOYEE_ID, PAYLOAD)
                       VALUES (PECO_EVENT_LOG_SEQ.NEXTVAL, :station_id, :shift_id,
                               :event_type, :entity_type, :entity_id,
                               :employee_id, :payload)""",
                    {
                        "station_id": station_id,
                        "shift_id": shift_id,
                        "event_type": event_type,
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "employee_id": employee_id,
                        "payload": json.dumps(payload or {}, ensure_ascii=False)[:2000],
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

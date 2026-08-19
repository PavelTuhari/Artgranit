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


class PecoSqlError(Exception):
    """Ошибка SQL, о которой execute_query сообщает флагом, а не исключением."""


def _run(db, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Выполняет запрос и бросает исключение, если он не удался.

    models.database.execute_query не бросает исключений: об ошибке SQL он
    сообщает полем success. Без этой обёртки неудавшийся DML молча
    доезжал бы до commit(), и вызывающий получал бы success=True на
    операции, которая не выполнилась.
    """
    r = db.execute_query(sql, params) if params else db.execute_query(sql)
    if not r.get("success"):
        raise PecoSqlError(r.get("message") or "SQL error")
    return r


class PecoStore:
    """CRUD по справочникам, мастер-данным и ценам PECO."""

    # ---------------- справочники ----------------

    @staticmethod
    def list_grades() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db,
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
                r = _run(db, sql)
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_nozzles(station_id: int) -> Dict[str, Any]:
        """Активные пистолеты станции с колонкой, резервуаром и счётчиком."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
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
                r = _run(db,
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
                _run(db,
                    """UPDATE PECO_PRICES SET VALID_TO = SYSTIMESTAMP
                        WHERE STATION_ID = :station_id
                          AND GRADE_CODE = :grade_code
                          AND VALID_TO IS NULL""",
                    params,
                )
                _run(db,
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
                _run(db, 
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

    # ---------------- смены ----------------

    @staticmethod
    def open_shift(station_id: int, employee_id: int) -> Dict[str, Any]:
        """Создаёт смену и строки показаний по всем активным пистолетам.

        Показание открытия = текущий тотализатор пистолета. Это связывает
        новую смену с закрывающими показаниями предыдущей и не даёт
        разорвать цепочку незаметно.
        """
        try:
            with DatabaseModel() as db:
                _run(db,
                    """INSERT INTO PECO_SHIFTS
                              (ID, STATION_ID, STATUS_CODE, OPENED_BY)
                       VALUES (PECO_SHIFTS_SEQ.NEXTVAL, :station_id, 'OPEN',
                               :employee_id)""",
                    {"station_id": station_id, "employee_id": employee_id},
                )
                r = _run(db,
                    "SELECT PECO_SHIFTS_SEQ.CURRVAL AS ID FROM dual"
                )
                rows = _norm_rows(r)
                shift_id = int(rows[0]["id"]) if rows else None

                # STATION_ID у PECO_SHIFT_METERS NOT NULL и участвует в составном
                # FK на PECO_NOZZLES (ID, STATION_ID) — без него строка не свяжет
                # смену и пистолет с одной и той же станцией.
                _run(db,
                    """INSERT INTO PECO_SHIFT_METERS
                              (ID, SHIFT_ID, NOZZLE_ID, STATION_ID, METER_OPEN)
                       SELECT PECO_SHIFT_METERS_SEQ.NEXTVAL, :shift_id,
                              n.ID, n.STATION_ID, n.METER_TOTAL
                         FROM PECO_NOZZLES n
                         JOIN PECO_PUMPS p ON p.ID = n.PUMP_ID
                        WHERE p.STATION_ID = :station_id
                          AND n.ACTIVE = 1 AND p.ACTIVE = 1""",
                    {"shift_id": shift_id, "station_id": station_id},
                )

                # Снимок остатков резервуаров на момент открытия. Без него
                # tank_variance при закрытии не из чего вычислять:
                # PECO_TANKS.CURRENT_L — это текущий счётчик, а не снимок.
                _run(db,
                    """INSERT INTO PECO_SHIFT_TANKS
                              (ID, SHIFT_ID, TANK_ID, STATION_ID,
                               VOLUME_OPEN_L, DELIVERED_L)
                       SELECT PECO_SHIFT_TANKS_SEQ.NEXTVAL, :shift_id,
                              t.ID, t.STATION_ID, t.CURRENT_L, 0
                         FROM PECO_TANKS t
                        WHERE t.STATION_ID = :station_id AND t.ACTIVE = 1""",
                    {"shift_id": shift_id, "station_id": station_id},
                )
                db.connection.commit()
                return {"success": True, "shift_id": shift_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_open_shift(station_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID, STATION_ID, STATUS_CODE, OPENED_AT, OPENED_BY
                         FROM PECO_SHIFTS
                        WHERE STATION_ID = :station_id
                          AND STATUS_CODE IN ('OPEN', 'CLOSING')
                        ORDER BY OPENED_AT DESC
                        FETCH FIRST 1 ROWS ONLY""",
                    {"station_id": station_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Нет открытой смены"}
                return {"success": True, "shift": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_shift_meters(shift_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT sm.NOZZLE_ID, sm.METER_OPEN, sm.METER_CLOSE,
                              n.CODE AS NOZZLE_CODE, n.GRADE_CODE, n.TANK_ID
                         FROM PECO_SHIFT_METERS sm
                         JOIN PECO_NOZZLES n ON n.ID = sm.NOZZLE_ID
                        WHERE sm.SHIFT_ID = :shift_id
                        ORDER BY n.CODE""",
                    {"shift_id": shift_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_shift_tanks(shift_id: int) -> Dict[str, Any]:
        """Реестр резервуаров смены: остаток на открытие, приход, замер."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT st.TANK_ID, t.GRADE_CODE, st.VOLUME_OPEN_L,
                              st.DELIVERED_L, st.DIP_CLOSE_L, st.TANK_VARIANCE,
                              t.CODE AS TANK_CODE
                         FROM PECO_SHIFT_TANKS st
                         JOIN PECO_TANKS t ON t.ID = st.TANK_ID
                        WHERE st.SHIFT_ID = :shift_id
                        ORDER BY t.GRADE_CODE""",
                    {"shift_id": shift_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_tank_close(shift_id: int, tank_id: int, dip_close_l: float,
                        tank_variance: Optional[float] = None) -> Dict[str, Any]:
        """Записывает замер на закрытие и расхождение по конкретному резервуару."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """UPDATE PECO_SHIFT_TANKS
                          SET DIP_CLOSE_L   = :dip_close_l,
                              TANK_VARIANCE = :tank_variance
                        WHERE SHIFT_ID = :shift_id AND TANK_ID = :tank_id""",
                    {"shift_id": shift_id, "tank_id": tank_id,
                     "dip_close_l": dip_close_l, "tank_variance": tank_variance},
                )
                # rowcount == 0 значит, что для этой пары (SHIFT_ID, TANK_ID)
                # нет строки в PECO_SHIFT_TANKS: UPDATE ничего не задел, но
                # execute_query всё равно вернул success. Без этой проверки
                # расхождение по резервуару молча исчезает без единой ошибки.
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Нет строки реестра резервуара для этой смены"}
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def mark_shift_closing(shift_id: int) -> Dict[str, Any]:
        """Переводит смену в CLOSING перед записью замеров.

        Между началом закрытия и finalize_shift смена не должна выглядеть
        обычной открытой: иначе после сбоя в реестре резервуаров окажется
        замер на закрытие, а колонки продолжат отпускать топливо.

        Переход в CLOSING обязан быть идемпотентным: если close_shift упадёт
        на finalize_shift, смена остаётся в CLOSING, и оператор должен иметь
        возможность повторить попытку закрытия без раскрытия смены. Поэтому
        WHERE принимает и OPEN, и CLOSING. Отвергаются только уже CLOSED или
        DISPUTED — те, что нельзя переоткрыть.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """UPDATE PECO_SHIFTS SET STATUS_CODE = 'CLOSING'
                        WHERE ID = :shift_id AND STATUS_CODE IN ('OPEN', 'CLOSING')""",
                    {"shift_id": shift_id},
                )
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Смена уже закрыта"}
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_meter_close(shift_id: int, nozzle_id: int,
                         meter_close: float) -> Dict[str, Any]:
        """Записывает закрывающее показание и синхронно двигает тотализатор."""
        try:
            with DatabaseModel() as db:
                _run(db,
                    """UPDATE PECO_SHIFT_METERS SET METER_CLOSE = :meter_close
                        WHERE SHIFT_ID = :shift_id AND NOZZLE_ID = :nozzle_id""",
                    {"shift_id": shift_id, "nozzle_id": nozzle_id,
                     "meter_close": meter_close},
                )
                _run(db,
                    """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_close
                        WHERE ID = :nozzle_id""",
                    {"nozzle_id": nozzle_id, "meter_close": meter_close},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_paid_liters(shift_id: int) -> Dict[str, Any]:
        """Литры и деньги по оплаченным транзакциям смены.

        Наличные и MIA QR разделены: MIA не попадает в кассовую сверку,
        иначе cash_variance теряет смысл.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT NVL(SUM(LITERS), 0) AS LITERS,
                              NVL(SUM(CASE WHEN PAY_METHOD = 'CASH'
                                           THEN AMOUNT ELSE 0 END), 0) AS CASH_AMT,
                              NVL(SUM(CASE WHEN PAY_METHOD = 'MIA_QR'
                                           THEN AMOUNT ELSE 0 END), 0) AS MIA_AMT
                         FROM PECO_TXN
                        WHERE SHIFT_ID = :shift_id AND STATUS_CODE = 'PAID'""",
                    {"shift_id": shift_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": True, "liters": 0.0, "cash": 0.0, "mia": 0.0}
                row = rows[0]
                return {
                    "success": True,
                    "liters": float(row["liters"]),
                    "cash": float(row["cash_amt"]),
                    "mia": float(row["mia_amt"]),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def count_unresolved_txn(shift_id: int) -> Dict[str, Any]:
        """Транзакции, мешающие закрыть смену: налив идёт или ждёт оплаты."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT COUNT(*) AS C FROM PECO_TXN
                        WHERE SHIFT_ID = :shift_id
                          AND STATUS_CODE IN ('DISPENSING', 'AWAITING_PAY')""",
                    {"shift_id": shift_id},
                )
                rows = _norm_rows(r)
                return {"success": True, "count": int(rows[0]["c"]) if rows else 0}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def finalize_shift(shift_id: int, employee_id: int, status: str,
                       totals: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                _run(db,
                    """UPDATE PECO_SHIFTS
                          SET STATUS_CODE    = :status,
                              CLOSED_AT      = SYSTIMESTAMP,
                              CLOSED_BY      = :employee_id,
                              CASH_DECLARED  = :cash_declared,
                              CASH_EXPECTED  = :cash_expected,
                              CASH_VARIANCE  = :cash_variance,
                              LITER_VARIANCE = :liter_variance,
                              TANK_VARIANCE  = :tank_variance
                        WHERE ID = :shift_id""",
                    {
                        "shift_id": shift_id,
                        "employee_id": employee_id,
                        "status": status,
                        "cash_declared": totals.get("cash_declared"),
                        "cash_expected": totals.get("cash_expected"),
                        "cash_variance": totals.get("cash_variance"),
                        "liter_variance": totals.get("liter_variance"),
                        "tank_variance": totals.get("tank_variance"),
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_employee(employee_id: int) -> Dict[str, Any]:
        """Публичные данные сотрудника. PIN_SALT и PIN_HASH сюда не входят —
        см. get_employee_credentials для пути, который их использует."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID, STATION_ID, FULL_NAME, ROLE_CODE
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
    def get_employee_credentials(employee_id: int) -> Dict[str, Any]:
        """Данные сотрудника вместе с PIN_SALT/PIN_HASH для проверки PIN.

        Результат этого метода не должен сериализоваться и уходить клиенту
        ни в каком виде — он только для сравнения хеша внутри approve_disputed.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID, STATION_ID, ROLE_CODE, PIN_SALT, PIN_HASH
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
    def approve_shift(shift_id: int, employee_id: int,
                      station_id: Optional[int]) -> Dict[str, Any]:
        """Подтверждение расхождения менеджером. Статус остаётся DISPUTED —
        расхождение не стирается, оно принимается под ответственность."""
        try:
            with DatabaseModel() as db:
                # Все три условия авторизации — существование смены, статус
                # DISPUTED и своя станция менеджера — намеренно живут в одном
                # атомарном UPDATE, а не в отдельных проверках в Python до
                # него. Проверка-потом-обновление оставила бы окно гонки
                # между чтением и записью, и вдобавок разные ошибки на
                # разных условиях сказали бы атакующему, какое из них не
                # выполнено (существует ли смена, в каком она статусе, на
                # какой станции). :station_id IS NULL пропускает проверку
                # станции для ADMIN, у которого STATION_ID в БД NULL и кто
                # действует по всей сети.
                r = _run(db,
                    """UPDATE PECO_SHIFTS SET APPROVED_BY = :employee_id
                        WHERE ID = :shift_id
                          AND STATUS_CODE = 'DISPUTED'
                          AND (:station_id IS NULL OR STATION_ID = :station_id)""",
                    {"shift_id": shift_id, "employee_id": employee_id,
                     "station_id": station_id},
                )
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Смена не найдена, не в статусе расхождения "
                                     "или относится к другой станции"}
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- транзакции ----------------

    @staticmethod
    def insert_txn(shift_id: int, nozzle_id: int, grade_code: str,
                   price: float, meter_start: float,
                   is_self_service: bool,
                   authorized_by: Optional[int] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                # STATION_ID берётся подзапросом из самой смены, а не
                # принимается параметром: PECO_TXN.STATION_ID NOT NULL и
                # участвует в составном FK на PECO_SHIFTS (ID, STATION_ID) —
                # значение обязано совпасть со станцией смены, иначе
                # транзакция может привязать пистолет одной станции к
                # смене другой. Подзапрос гарантирует совпадение и сразу
                # проваливает INSERT (NOT NULL), если SHIFT_ID не существует.
                _run(db,
                    """INSERT INTO PECO_TXN
                              (ID, SHIFT_ID, NOZZLE_ID, STATION_ID, GRADE_CODE,
                               STATUS_CODE, PRICE, METER_START, IS_SELF_SERVICE,
                               AUTHORIZED_BY)
                       VALUES (PECO_TXN_SEQ.NEXTVAL, :shift_id, :nozzle_id,
                               (SELECT STATION_ID FROM PECO_SHIFTS
                                 WHERE ID = :shift_id),
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
                r = _run(db,
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
                r = _run(db,
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
        """Обновляет статус и переданные поля.

        Имена полей проверяются по фиксированному белому списку `allowed` —
        в SQL не попадает ничего из внешнего ввода. Вызывающая сторона —
        только код этого модуля (peco_txn.py передаёт заранее известные
        ключи), но белый список остаётся обязательным барьером на случай,
        если в будущем сюда прокинут словарь из запроса.
        """
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
                r = _run(db,
                    f"UPDATE PECO_TXN SET {', '.join(sets)} WHERE ID = :txn_id",
                    params,
                )
                # rowcount == 0 значит, что транзакции с таким ID нет: без
                # этой проверки авторизация/оплата/аннулирование молча
                # "проходят", хотя ни одна строка не изменилась — тот же
                # класс ошибки, что уже находили в save_tank_close и
                # mark_shift_closing.
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Транзакция не найдена"}
                # тотализатор пистолета двигается вместе с завершённым наливом
                if "meter_end" in params and params["meter_end"] is not None:
                    _run(db,
                        """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_end
                            WHERE ID = (SELECT NOZZLE_ID FROM PECO_TXN
                                         WHERE ID = :txn_id)""",
                        {"meter_end": params["meter_end"], "txn_id": txn_id},
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

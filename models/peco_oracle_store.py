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
    def list_prices(station_id: int) -> Dict[str, Any]:
        """Действующие цены станции — по одной на вид топлива.

        Отдельно от pump_state: там цены отдаются только при открытой смене,
        а менеджер меняет цены и между сменами.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT p.GRADE_CODE, p.PRICE, p.VALID_FROM,
                              g.NAME AS GRADE_NAME
                         FROM PECO_PRICES p
                         JOIN PECO_REF_FUEL_GRADES g ON g.CODE = p.GRADE_CODE
                        WHERE p.STATION_ID = :station_id
                          AND p.VALID_TO IS NULL
                        ORDER BY g.SORT_ORDER""",
                    {"station_id": station_id})
                return {"success": True, "items": _norm_rows(r)}
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
                #
                # NO_PARALLEL обязателен на каждом INSERT...SELECT, который
                # берёт ключ из NOCACHE-последовательности PECO_*: Oracle ADB
                # сам распараллеливает такие запросы, а слейвы параллельного
                # запроса сериализуются на NEXTVAL NOCACHE-последовательности
                # и блокируют друг друга — deadlock ORA-12801/ORA-12860.
                # Без хинта open_shift падает так на КАЖДОМ вызове. Тот же
                # хинт нужен на любом другом INSERT...SELECT с NEXTVAL этой
                # формы (ниже — PECO_SHIFT_TANKS, PECO_TANK_DIPS,
                # PECO_DELIVERY_ITEMS); INSERT...VALUES это не касается.
                _run(db,
                    """INSERT /*+ NO_PARALLEL */ INTO PECO_SHIFT_METERS
                              (ID, SHIFT_ID, NOZZLE_ID, STATION_ID, METER_OPEN)
                       SELECT /*+ NO_PARALLEL */ PECO_SHIFT_METERS_SEQ.NEXTVAL, :shift_id,
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
                    """INSERT /*+ NO_PARALLEL */ INTO PECO_SHIFT_TANKS
                              (ID, SHIFT_ID, TANK_ID, STATION_ID,
                               VOLUME_OPEN_L, DELIVERED_L)
                       SELECT /*+ NO_PARALLEL */ PECO_SHIFT_TANKS_SEQ.NEXTVAL, :shift_id,
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
    def default_station_id() -> Dict[str, Any]:
        """Первая активная станция — для запросов без явного station_id.

        Отдельный лёгкий запрос вместо admin_overview: тот обходит все
        станции и читает остатки каждой (около 47 запросов), а этот вызов
        стоит на самом горячем маршруте — опросе состояния колонки.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID FROM PECO_STATIONS
                        WHERE ACTIVE = 1 ORDER BY CODE
                        FETCH FIRST 1 ROWS ONLY""")
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Нет активных станций"}
                return {"success": True, "station_id": int(rows[0]["id"])}
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
                        tank_variance: Optional[float] = None,
                        employee_id: Optional[int] = None) -> Dict[str, Any]:
        """Записывает замер на закрытие и расхождение по конкретному резервуару.

        Замер метрштоком — физическое измерение, и он обязан стать новым
        действующим остатком резервуара (PECO_TANKS.CURRENT_L), а не только
        лечь в реестр смены. Иначе CURRENT_L продолжает вестись только по
        счётчикам и приходу; если он разошёлся с физикой (например, слив без
        транзакции), это расхождение никогда не исчезает само и заново
        отражается на КАЖДОЙ следующей смене — DISPUTED перестаёт что-либо
        значить, потому что нет способа отличить новую утечку от старой,
        которую уже видели и не исправили. Обновление регистра и запись
        замера в PECO_TANK_DIPS (DIP_KIND='CLOSE') идут в ОДНОЙ транзакции
        с UPDATE реестра смены: замер обязан либо целиком применяться, либо
        не применяться вовсе.
        """
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

                # Замер становится действующим остатком: следующая смена
                # откроется от него (VOLUME_OPEN_L = CURRENT_L), а не от
                # старого значения, которое разошлось со счётчиками.
                _run(db,
                    """UPDATE PECO_TANKS SET CURRENT_L = :dip_close_l
                        WHERE ID = :tank_id""",
                    {"tank_id": tank_id, "dip_close_l": dip_close_l},
                )

                _run(db,
                    """INSERT /*+ NO_PARALLEL */ INTO PECO_TANK_DIPS
                              (ID, TANK_ID, STATION_ID, SHIFT_ID, MEASURED_L,
                               MEASURED_BY, DIP_KIND)
                       SELECT /*+ NO_PARALLEL */ PECO_TANK_DIPS_SEQ.NEXTVAL, :tank_id, t.STATION_ID,
                              :shift_id, :dip_close_l, :employee_id, 'CLOSE'
                         FROM PECO_TANKS t
                        WHERE t.ID = :tank_id""",
                    {"tank_id": tank_id, "shift_id": shift_id,
                     "dip_close_l": dip_close_l, "employee_id": employee_id},
                )

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
        """Записывает закрывающее показание и синхронно двигает тотализатор.

        METER_CLOSE становится METER_OPEN следующей смены — это самое
        аудит-критичное число модуля, и запись обязана быть защищена не
        слабее прочих мутаций реестра смены:

        1. UPDATE PECO_SHIFT_METERS ограничен И сменой (SHIFT_ID), И тем,
           что смена ещё OPEN/CLOSING. Без второго условия показание можно
           переписать ПОСЛЕ финализации смены, не пересчитав LITER_VARIANCE
           — аудированная цифра стала бы редактируемой задним числом.
        2. UPDATE PECO_NOZZLES ограничен станцией этой смены и не даёт
           тотализатору пойти назад (тот же приём, что и в
           update_txn_status выше). Без этого чужой nozzle_id из другого
           запроса молча перезаписывает тотализатор ЧУЖОЙ станции.

        rowcount не проверяется на втором UPDATE: отказ сдвинуть счётчик
        назад — это ожидаемый исход (показание уже сохранено выше), а не
        ошибка.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """UPDATE PECO_SHIFT_METERS SET METER_CLOSE = :meter_close
                        WHERE SHIFT_ID = :shift_id AND NOZZLE_ID = :nozzle_id
                          AND EXISTS (SELECT 1 FROM PECO_SHIFTS s
                                       WHERE s.ID = :shift_id
                                         AND s.STATUS_CODE IN ('OPEN','CLOSING'))""",
                    {"shift_id": shift_id, "nozzle_id": nozzle_id,
                     "meter_close": meter_close},
                )
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Пистолет не относится к этой смене, "
                                     "либо смена уже закрыта"}

                _run(db,
                    """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_close
                        WHERE ID = :nozzle_id
                          AND METER_TOTAL <= :meter_close
                          AND STATION_ID = (SELECT STATION_ID FROM PECO_SHIFTS
                                              WHERE ID = :shift_id)""",
                    {"nozzle_id": nozzle_id, "meter_close": meter_close,
                     "shift_id": shift_id},
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
                   authorized_by: Optional[int] = None,
                   mia_ref: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                # STATION_ID берётся подзапросом из самой смены, а не
                # принимается параметром: PECO_TXN.STATION_ID NOT NULL и
                # участвует в составном FK на PECO_SHIFTS (ID, STATION_ID) —
                # значение обязано совпасть со станцией смены, иначе
                # транзакция может привязать пистолет одной станции к
                # смене другой. Подзапрос дополнительно требует
                # STATUS_CODE = 'OPEN': смена в CLOSING/CLOSED/DISPUTED не
                # даст строку, и NOT NULL провалит INSERT — иначе можно
                # было бы авторизовать налив против смены, которая уже
                # закрывается, что и должен предотвращать mark_shift_closing.
                _run(db,
                    """INSERT INTO PECO_TXN
                              (ID, SHIFT_ID, NOZZLE_ID, STATION_ID, GRADE_CODE,
                               STATUS_CODE, PRICE, METER_START, IS_SELF_SERVICE,
                               AUTHORIZED_BY, MIA_REF)
                       VALUES (PECO_TXN_SEQ.NEXTVAL, :shift_id, :nozzle_id,
                               (SELECT STATION_ID FROM PECO_SHIFTS
                                 WHERE ID = :shift_id AND STATUS_CODE = 'OPEN'),
                               :grade_code, 'AUTHORIZED', :price, :meter_start,
                               :is_self_service, :authorized_by, :mia_ref)""",
                    {
                        "shift_id": shift_id,
                        "nozzle_id": nozzle_id,
                        "grade_code": grade_code,
                        "price": price,
                        "meter_start": meter_start,
                        "is_self_service": 1 if is_self_service else 0,
                        "authorized_by": authorized_by,
                        "mia_ref": mia_ref,
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
            # ORA-01400 здесь означает, что подзапрос STATION_ID не вернул
            # строку — смена не существует или не в статусе OPEN. Домены
            # ошибки должны говорить об этом прямо, а не отдавать сырой
            # текст Oracle оператору у колонки.
            if "ORA-01400" in str(e):
                return {"success": False,
                        "error": "Смена не открыта — отпуск невозможен"}
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_txn(txn_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID, SHIFT_ID, STATION_ID, NOZZLE_ID, GRADE_CODE,
                              STATUS_CODE, LITERS, PRICE, AMOUNT, PAY_METHOD,
                              IS_SELF_SERVICE, MIA_REF, METER_START, METER_END
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
                          expected_status: Optional[str] = None,
                          **fields: Any) -> Dict[str, Any]:
        """Обновляет статус и переданные поля.

        Имена полей проверяются по фиксированному белому списку `allowed` —
        в SQL не попадает ничего из внешнего ввода. Вызывающая сторона —
        только код этого модуля (peco_txn.py передаёт заранее известные
        ключи), но белый список остаётся обязательным барьером на случай,
        если в будущем сюда прокинут словарь из запроса. Неизвестный ключ —
        это опечатка вызывающего (например, pay_metod вместо pay_method),
        и она обязана падать явной ошибкой, а не молча терять поле.

        `expected_status`, если передан, обязан попасть в WHERE, а не
        проверяться отдельным чтением в Python до этого вызова: peco_txn.py
        читает текущий статус через get_txn на одном соединении, а этот
        UPDATE выполняется на другом — между ними есть окно, в котором
        второй оператор (например, кассир вместо того, кто аннулирует)
        успевает провести свой переход первым. Проверка в Python этого
        не видит и просто перезаписывает уже оплаченную строку. Условие в
        WHERE делает гонку невозможной: если статус успел измениться,
        обновится ноль строк, и это будет замечено проверкой rowcount ниже.
        """
        allowed = {"liters", "amount", "pay_method", "mia_ref", "meter_end"}
        sets = ["STATUS_CODE = :status"]
        params: Dict[str, Any] = {"txn_id": txn_id, "status": status}

        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(
                    f"update_txn_status: неизвестное поле {key!r}")
            sets.append(f"{key.upper()} = :{key}")
            params[key] = value

        if status == "PAID":
            sets.append("PAID_AT = SYSTIMESTAMP")

        where = "WHERE ID = :txn_id"
        if expected_status is not None:
            where += " AND STATUS_CODE = :expected_status"
            params["expected_status"] = expected_status

        try:
            with DatabaseModel() as db:
                r = _run(db,
                    f"UPDATE PECO_TXN SET {', '.join(sets)} {where}",
                    params,
                )
                # rowcount == 0 значит либо что транзакции с таким ID нет,
                # либо (когда передан expected_status) что статус успел
                # измениться другим оператором между чтением и записью —
                # тот же класс ошибки, что уже находили в save_tank_close и
                # mark_shift_closing.
                if r.get("rowcount", 0) == 0:
                    if expected_status is not None:
                        return {"success": False,
                                "error": "Статус транзакции изменился "
                                         "другим оператором"}
                    return {"success": False,
                            "error": "Транзакция не найдена"}
                # тотализатор пистолета двигается вместе с завершённым наливом.
                # METER_TOTAL <= :meter_end не даёт счётчику уехать назад:
                # с него берётся показание открытия следующей смены, и
                # откат сломал бы meter_delta и этой, и следующей смены.
                # Ноль строк здесь — ожидаемый отказ сдвинуть счётчик назад,
                # а не ошибка: транзакция с нулевыми литрами уже сохранена
                # выше, откат счётчика лишь не проводится.
                if "meter_end" in params and params["meter_end"] is not None:
                    _run(db,
                        """UPDATE PECO_NOZZLES SET METER_TOTAL = :meter_end
                            WHERE ID = (SELECT NOZZLE_ID FROM PECO_TXN
                                         WHERE ID = :txn_id)
                              AND METER_TOTAL <= :meter_end""",
                        {"meter_end": params["meter_end"], "txn_id": txn_id},
                    )
                # Топливо физически покинуло резервуар — списание обязано
                # закоммититься вместе со сменой статуса и сдвигом
                # тотализатора, а не отдельным вызовом add_tank_volume после
                # этого метода (как предлагал черновик задачи). Отдельный
                # commit — это Critical-дефект, найденный на Task 12: успешная
                # смена статуса с последующим неудавшимся списанием оставляет
                # продажу в реестре без соответствующего расхода резервуара,
                # tank_variance на закрытии смены расходится безвозвратно, и
                # безопасного повтора нет — второй прогон либо спишет литры
                # дважды, либо будет отвергнут guard'ом терминального статуса.
                # rowcount == 0 здесь не проверяется: PECO_NOZZLES.TANK_ID
                # NOT NULL и participates в составном FK на PECO_TANKS
                # (ID, STATION_ID) — строка резервуара гарантирована схемой,
                # а сам txn_id уже подтверждён проверкой rowcount выше по
                # основному UPDATE.
                if "liters" in params and params["liters"] and params["liters"] > 0:
                    _run(db,
                        """UPDATE PECO_TANKS SET CURRENT_L = CURRENT_L - :liters
                            WHERE ID = (SELECT n.TANK_ID FROM PECO_TXN t
                                          JOIN PECO_NOZZLES n ON n.ID = t.NOZZLE_ID
                                         WHERE t.ID = :txn_id)""",
                        {"liters": params["liters"], "txn_id": txn_id},
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- приход цистерн ----------------
    #
    # insert_delivery / insert_delivery_item / add_tank_volume /
    # add_shift_tank_delivered были ранней (многотранзакционной) версией
    # приёма цистерны и вызваны здесь же apply_delivery ниже: сбой на
    # середине оставлял резервуары зачисленными по недооформленной
    # накладной, а повторная попытка иногда начисляла топливо дважды.
    # apply_delivery делает то же самое одной транзакцией; отдельные методы
    # удалены как не имеющие вызывающих вне тестов.

    @staticmethod
    def apply_delivery(station_id: int, supplier: str, waybill_no: str,
                       items: List[Dict[str, Any]],
                       employee_id: int,
                       driver_name: Optional[str] = None,
                       vehicle_no: Optional[str] = None) -> Dict[str, Any]:
        """Приход цистерны целиком — одна транзакция, один commit.

        Раньше шапка, каждая строка, зачисление резервуара, реестр смены и
        замер коммитились отдельно. Сбой на середине оставлял резервуары
        зачисленными по накладной, которую не довели до конца, а уникальный
        индекс (STATION_ID, WAYBILL_NO) не давал повторить приём под той же
        накладной. Оператор, оформивший новую накладную и повторно
        отправивший весь список строк, начислял уже зачисленное топливо
        второй раз — фактически несуществующее топливо оседало в остатках.
        Поэтому всё пишется на одном соединении через _run и коммитится
        один раз в самом конце: любая ошибка бросает исключение раньше
        commit, и Oracle откатывает всю транзакцию целиком при закрытии
        соединения.
        """
        try:
            with DatabaseModel() as db:
                _run(db,
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
                r = _run(db,
                    "SELECT PECO_DELIVERIES_SEQ.CURRVAL AS ID FROM dual"
                )
                rows = _norm_rows(r)
                delivery_id = int(rows[0]["id"]) if rows else None

                for it in items:
                    tank_id = it["tank_id"]
                    grade_code = it["grade_code"]
                    liters_doc = float(it.get("liters_doc") or 0.0)
                    liters_recv = float(it.get("liters_recv") or 0.0)

                    item_r = _run(db,
                        """INSERT /*+ NO_PARALLEL */ INTO PECO_DELIVERY_ITEMS
                                  (ID, DELIVERY_ID, TANK_ID, STATION_ID, GRADE_CODE,
                                   LITERS_DOC, LITERS_RECV, TEMPERATURE_C,
                                   DIP_BEFORE_L, DIP_AFTER_L)
                           SELECT /*+ NO_PARALLEL */ PECO_DELIVERY_ITEMS_SEQ.NEXTVAL, :delivery_id,
                                  :tank_id, d.STATION_ID, :grade_code,
                                  :liters_doc, :liters_recv, :temperature_c,
                                  :dip_before, :dip_after
                             FROM PECO_DELIVERIES d
                            WHERE d.ID = :delivery_id""",
                        {"delivery_id": delivery_id, "tank_id": tank_id,
                         "grade_code": grade_code, "liters_doc": liters_doc,
                         "liters_recv": liters_recv,
                         "temperature_c": it.get("temperature_c"),
                         "dip_before": it.get("dip_before"),
                         "dip_after": it.get("dip_after")},
                    )
                    if item_r.get("rowcount", 0) == 0:
                        return {"success": False,
                                "error": "Приход с таким ID не найден"}

                    # Резервуар зачисляется ФАКТИЧЕСКИ принятым объёмом, не
                    # документальным: иначе недолив осел бы в учёте как
                    # наличное топливо.
                    tank_r = _run(db,
                        """UPDATE PECO_TANKS
                              SET CURRENT_L = CURRENT_L + :liters
                            WHERE ID = :tank_id""",
                        {"tank_id": tank_id, "liters": liters_recv},
                    )
                    if tank_r.get("rowcount", 0) == 0:
                        return {"success": False,
                                "error": "Резервуар с таким ID не найден"}

                    # Ноль строк здесь — норма: приём вне открытой смены,
                    # обновление просто ничего не находит. Настоящая ошибка
                    # SQL всё равно уйдёт исключением через _run и остановит
                    # всю транзакцию.
                    #
                    # Подзапрос смены ограничен ТОЛЬКО STATUS_CODE = 'OPEN'
                    # (не 'CLOSING'): close_shift читает реестр резервуаров
                    # и тут же считает TANK_VARIANCE от прочитанных чисел.
                    # Если бы приход мог присоединиться к уже закрывающейся
                    # смене, DELIVERED_L сдвинулся бы ПОСЛЕ того, как
                    # расхождение уже посчитано и сохранено, и сохранённый
                    # TANK_VARIANCE перестал бы соответствовать данным в
                    # PECO_SHIFT_TANKS — расхождение стало бы
                    # самопротиворечивым и невоспроизводимым.
                    _run(db,
                        """UPDATE PECO_SHIFT_TANKS
                              SET DELIVERED_L = DELIVERED_L + :liters
                            WHERE TANK_ID = :tank_id
                              AND SHIFT_ID = (SELECT ID FROM PECO_SHIFTS
                                               WHERE STATION_ID = :station_id
                                                 AND STATUS_CODE = 'OPEN')""",
                        {"tank_id": tank_id, "station_id": station_id,
                         "liters": liters_recv},
                    )

                    if it.get("dip_after") is not None:
                        dip_r = _run(db,
                            """INSERT /*+ NO_PARALLEL */ INTO PECO_TANK_DIPS
                                      (ID, TANK_ID, STATION_ID, SHIFT_ID, MEASURED_L,
                                       MEASURED_BY, DIP_KIND)
                               SELECT /*+ NO_PARALLEL */ PECO_TANK_DIPS_SEQ.NEXTVAL, :tank_id,
                                      t.STATION_ID, NULL, :measured_l,
                                      :employee_id, 'DELIVERY'
                                 FROM PECO_TANKS t
                                WHERE t.ID = :tank_id""",
                            {"tank_id": tank_id,
                             "measured_l": float(it["dip_after"]),
                             "employee_id": employee_id},
                        )
                        if dip_r.get("rowcount", 0) == 0:
                            return {"success": False,
                                    "error": "Резервуар с таким ID не найден"}

                accept_r = _run(db,
                    """UPDATE PECO_DELIVERIES
                          SET ACCEPTED_AT = SYSTIMESTAMP,
                              ACCEPTED_BY = :employee_id
                        WHERE ID = :delivery_id""",
                    {"delivery_id": delivery_id, "employee_id": employee_id},
                )
                if accept_r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Приход с таким ID не найден"}

                db.connection.commit()
                return {"success": True, "delivery_id": delivery_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def insert_tank_dip(tank_id: int, measured_l: float, dip_kind: str,
                        shift_id: Optional[int] = None,
                        employee_id: Optional[int] = None) -> Dict[str, Any]:
        """STATION_ID у замера NOT NULL и участвует в составном FK на
        PECO_TANKS (ID, STATION_ID). Берём его подзапросом из PECO_TANKS по
        tank_id, а не из параметра вызывающего кода — резервуар уже привязан
        к правильной станции, доверять чужому значению не нужно.
        """
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """INSERT /*+ NO_PARALLEL */ INTO PECO_TANK_DIPS
                              (ID, TANK_ID, STATION_ID, SHIFT_ID, MEASURED_L,
                               MEASURED_BY, DIP_KIND)
                       SELECT /*+ NO_PARALLEL */ PECO_TANK_DIPS_SEQ.NEXTVAL, :tank_id, t.STATION_ID,
                              :shift_id, :measured_l, :employee_id, :dip_kind
                         FROM PECO_TANKS t
                        WHERE t.ID = :tank_id""",
                    {"tank_id": tank_id, "shift_id": shift_id,
                     "measured_l": measured_l, "employee_id": employee_id,
                     "dip_kind": dip_kind},
                )
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Резервуар с таким ID не найден"}
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def list_tank_levels(station_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = _run(db,
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

    # ---------------- сотрудники / PIN ----------------

    @staticmethod
    def list_employees(station_id: Optional[int] = None) -> Dict[str, Any]:
        """Сотрудники сети (или одной станции) без PIN_HASH/PIN_SALT.

        HAS_PIN считается прямо в SQL по значению-заглушке 'NO_PIN_SET',
        которым засеваются демо-сотрудники до того, как им назначен
        реальный PIN. Сами PIN_HASH/PIN_SALT в SELECT не входят —
        см. get_employee_credentials для пути, где они действительно нужны."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT ID, STATION_ID, FULL_NAME, ROLE_CODE, ACTIVE,
                              CASE WHEN PIN_HASH = 'NO_PIN_SET' THEN 0 ELSE 1 END AS HAS_PIN
                         FROM PECO_EMPLOYEES
                        WHERE (:station_id IS NULL OR STATION_ID = :station_id)
                        ORDER BY FULL_NAME""",
                    {"station_id": station_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_employee_pin(employee_id: int, pin_salt: str, pin_hash: str) -> Dict[str, Any]:
        """Записывает соль и хеш PIN сотрудника. Сам PIN сюда не попадает —
        вызывающий (peco_shift.hash_pin) обязан посчитать хеш заранее."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """UPDATE PECO_EMPLOYEES
                          SET PIN_SALT = :pin_salt, PIN_HASH = :pin_hash
                        WHERE ID = :employee_id AND ACTIVE = 1""",
                    {"employee_id": employee_id, "pin_salt": pin_salt,
                     "pin_hash": pin_hash},
                )
                if r.get("rowcount", 0) == 0:
                    return {"success": False,
                            "error": "Сотрудник не найден или неактивен"}
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- смены: сводка и расхождения ----------------

    @staticmethod
    def list_disputed_shifts(station_id: Optional[int] = None) -> Dict[str, Any]:
        """Смены со статусом DISPUTED из V_PECO_VARIANCE.

        Представление не отдаёт APPROVED_BY (см. sql/103_peco_views.sql),
        поэтому статус подтверждения читается прямым JOIN на PECO_SHIFTS —
        без этого бэк-офис не может отличить расхождение, уже принятое
        менеджером под ответственность, от того, что всё ещё ждёт PIN."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT v.SHIFT_ID, v.STATION_ID, v.STATION_NAME,
                              v.CLOSED_AT, v.LITER_VARIANCE, v.CASH_VARIANCE,
                              v.TANK_VARIANCE, v.CLOSED_BY_NAME,
                              CASE WHEN sh.APPROVED_BY IS NOT NULL THEN 1 ELSE 0 END AS IS_APPROVED
                         FROM V_PECO_VARIANCE v
                         JOIN PECO_SHIFTS sh ON sh.ID = v.SHIFT_ID
                        WHERE v.STATUS_CODE = 'DISPUTED'
                          AND (:station_id IS NULL OR v.STATION_ID = :station_id)
                        ORDER BY v.CLOSED_AT DESC""",
                    {"station_id": station_id},
                )
                return {"success": True, "items": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shift_summary(shift_id: int) -> Dict[str, Any]:
        """Одна строка V_PECO_SHIFT_SUMMARY по номеру смены."""
        try:
            with DatabaseModel() as db:
                r = _run(db,
                    """SELECT SHIFT_ID, STATION_ID, STATION_NAME, STATUS_CODE,
                              OPENED_AT, CLOSED_AT, METER_DELTA, TXN_LITERS,
                              CASH_AMOUNT, MIA_AMOUNT, OPEN_TXN_COUNT,
                              CASH_DECLARED, CASH_EXPECTED, CASH_VARIANCE,
                              LITER_VARIANCE, TANK_VARIANCE
                         FROM V_PECO_SHIFT_SUMMARY
                        WHERE SHIFT_ID = :shift_id""",
                    {"shift_id": shift_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Смена не найдена"}
                return {"success": True, "summary": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

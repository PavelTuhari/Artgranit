"""
Контур снабжения топливом: карта АЗС, автозаказ, нефтебаза, рейсы, GPS.

Раздел живёт внутри модуля «Планограммы» (маршрут `#fuel`), но работает
с таблицами PECO: розничная часть сети АЗС уже описана там, и дублировать
станции с резервуарами в PLG_* было бы ровно тем, что запрещает CLAUDE.md.

Oracle-объекты: sql/106_peco_supply.sql, sql/107_peco_supply_views.sql
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel
from models.peco_autoorder import DEFAULTS, FuelAutoOrder
from models.peco_gps import PecoGps

LANGS = ('ru', 'ro', 'en')


def _rows(res) -> List[Dict[str, Any]]:
    if not res or not res.get('success'):
        return []
    cols = [c.lower() for c in (res.get('columns') or [])]
    return [dict(zip(cols, r)) for r in (res.get('data') or [])]


def _localize(rows: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    suffixes = tuple('_' + c for c in LANGS)
    out = []
    for row in rows:
        bases = {k[:-3] for k in row if k.endswith(suffixes)}
        new = dict(row)
        for base in bases:
            new[base] = row.get(base + '_' + lang) or row.get(base + '_ru')
        out.append(new)
    return out


class PecoSupplyController:
    """Станции на карте, автозаказ топлива, нефтебаза, рейсы, телеметрия."""

    # ==================== Карта станций ====================

    @staticmethod
    def stations(lang: str = 'ru') -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                data = _rows(db.execute_query(
                    "SELECT * FROM V_PECO_STATION_SUPPLY ORDER BY REGION, STATION_CODE"))
                depots = _rows(db.execute_query(
                    "SELECT ID, CODE, NAME, ADDRESS, LAT, LON, LOAD_BAYS "
                    "FROM PECO_DEPOTS WHERE ACTIVE = 1 ORDER BY ID"))
            _ = lang
            return {'success': True, 'data': data, 'depots': depots,
                    'without_geo': sum(1 for r in data if not r.get('has_geo'))}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def save_geo(station_id: int, payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """
        Сохранение координат станции: перетащили маркер либо нашли по адресу.

        Границы Молдовы проверяются намеренно: промах геокодера по
        неполному адресу уносит точку в другую страну, и на карте это
        замечают не сразу, а вот маршрут бензовоза ломается сразу.
        """
        try:
            lat = float(payload.get('lat'))
            lon = float(payload.get('lon'))
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Нужны числовые lat и lon', 'status': 400}
        if not (45.4 <= lat <= 48.5) or not (26.6 <= lon <= 30.2):
            return {'success': False, 'status': 400,
                    'error': f'Координаты вне Молдовы ({lat:.4f}, {lon:.4f}) — '
                             'проверьте адрес или поставьте точку вручную'}
        source = payload.get('source') if payload.get('source') in \
            ('manual', 'geocode', 'import') else 'manual'
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PECO_STATIONS SET LAT = :p_lat, LON = :p_lon, "
                    "GEO_SOURCE = :p_src, GEO_AT = SYSTIMESTAMP, "
                    "ACCESS_NOTE = NVL(:p_note, ACCESS_NOTE), "
                    "ROUTE_ZONE = NVL(:p_zone, ROUTE_ZONE) WHERE ID = :p_id",
                    {'p_lat': round(lat, 6), 'p_lon': round(lon, 6), 'p_src': source,
                     'p_note': (payload.get('access_note') or None),
                     'p_zone': (payload.get('route_zone') or None), 'p_id': station_id})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                db.connection.commit()
                db.execute_query(
                    "INSERT INTO PECO_EVENT_LOG (STATION_ID, EVENT_TYPE, ENTITY_TYPE, "
                    "ENTITY_ID, PAYLOAD) VALUES (:p_st, 'station_geo', 'station', :p_st2, :p_p)",
                    {'p_st': station_id, 'p_st2': station_id,
                     'p_p': f'lat={lat} lon={lon} source={source} by={username}'})
                db.connection.commit()
            return {'success': True, 'lat': round(lat, 6), 'lon': round(lon, 6)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Резервуары и автозаказ ====================

    @staticmethod
    def tanks(station_id: Optional[int] = None) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PECO_TANK_SUPPLY"
        params: Dict[str, Any] = {}
        if station_id:
            sql += " WHERE STATION_ID = :p_st"
            params['p_st'] = station_id
        sql += " ORDER BY NVL(DAYS_TO_DRY, 999), STATION_CODE, GRADE_CODE"
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _rows(db.execute_query(sql, params))}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def params() -> Dict[str, Any]:
        return {'success': True, 'data': dict(DEFAULTS)}

    @staticmethod
    def run_autoorder(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        numeric = {}
        for k in DEFAULTS:
            if payload.get(k) is not None:
                try:
                    numeric[k] = float(payload[k])
                except (TypeError, ValueError):
                    return {'success': False, 'status': 400,
                            'error': f'Параметр {k} должен быть числом'}
        return FuelAutoOrder.run(numeric, username)

    @staticmethod
    def runs(limit: int = 15) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _rows(db.execute_query(
                    "SELECT ID, DEPOT_ID, STATUS, STAGE, PROGRESS_PCT, STATION_COUNT, "
                    "ORDER_COUNT, LITERS_TOTAL, DRY_RISK_CNT, DURATION_SEC, MESSAGE, "
                    "USERNAME, STARTED_AT, FINISHED_AT FROM PECO_ORDER_RUNS "
                    "ORDER BY ID DESC FETCH FIRST :p_l ROWS ONLY", {'p_l': limit}))}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def orders(lang: str, status: Optional[str] = None,
               run_id: Optional[int] = None) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PECO_FUEL_ORDERS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if status:
            sql += " AND STATUS = :p_st"
            params['p_st'] = status
        if run_id:
            sql += " AND RUN_ID = :p_run"
            params['p_run'] = run_id
        sql += " ORDER BY NVL(MIN_DAYS_TO_DRY, 99), CREATED_AT DESC"
        try:
            with DatabaseModel() as db:
                data = _localize(_rows(db.execute_query(sql, params)), lang)
                items = _rows(db.execute_query(
                    "SELECT * FROM V_PECO_FUEL_ORDER_ITEMS ORDER BY ORDER_ID, GRADE_CODE"))
            by_order: Dict[int, List[Dict[str, Any]]] = {}
            for it in items:
                by_order.setdefault(int(it['order_id']), []).append(it)
            for o in data:
                o['items'] = by_order.get(int(o['id']), [])
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def adjust_item(item_id: int, payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """
        Правка объёма налива логистом. Ограничение то же, что у алгоритма:
        больше свободной ёмкости залить нельзя — это не «предупреждение»,
        а физика, поэтому сервер такую правку отклоняет.
        """
        try:
            liters = float(payload.get('liters'))
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Нужно число литров', 'status': 400}
        if liters < 0:
            return {'success': False, 'error': 'Объём не может быть отрицательным',
                    'status': 400}
        try:
            with DatabaseModel() as db:
                cur = _rows(db.execute_query(
                    "SELECT i.ID, i.ORDER_ID, i.ULLAGE_L, o.STATUS FROM PECO_FUEL_ORDER_ITEMS i "
                    "JOIN PECO_FUEL_ORDERS o ON o.ID = i.ORDER_ID WHERE i.ID = :p_id",
                    {'p_id': item_id}))
                if not cur:
                    return {'success': False, 'error': 'Строка не найдена', 'status': 404}
                row = cur[0]
                if row['status'] not in ('draft', 'approved'):
                    return {'success': False, 'status': 409,
                            'error': 'Заказ уже в рейсе — правка невозможна'}
                ullage = float(row.get('ullage_l') or 0)
                if liters > ullage + 0.5:
                    return {'success': False, 'status': 409,
                            'error': f'Больше свободной ёмкости ({ullage:.0f} л) залить нельзя'}
                db.execute_query(
                    "UPDATE PECO_FUEL_ORDER_ITEMS SET LITERS_ORDER = :p_l, "
                    "ADJ_REASON = NVL(:p_r, ADJ_REASON) WHERE ID = :p_id",
                    {'p_l': liters, 'p_r': (payload.get('reason') or None)[:30]
                     if payload.get('reason') else None, 'p_id': item_id})
                db.execute_query(
                    "UPDATE PECO_FUEL_ORDERS o SET LITERS_TOTAL = "
                    "(SELECT NVL(SUM(LITERS_ORDER), 0) FROM PECO_FUEL_ORDER_ITEMS i "
                    "  WHERE i.ORDER_ID = o.ID) WHERE o.ID = :p_o",
                    {'p_o': int(row['order_id'])})
                db.connection.commit()
            _ = username
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def set_order_status(order_id: int, status: str, username: str) -> Dict[str, Any]:
        if status not in ('draft', 'approved', 'cancelled'):
            return {'success': False, 'error': 'Недопустимый статус', 'status': 400}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PECO_FUEL_ORDERS SET STATUS = :p_s, "
                    "APPROVED_BY = CASE WHEN :p_s2 = 'approved' THEN :p_u ELSE APPROVED_BY END, "
                    "APPROVED_AT = CASE WHEN :p_s3 = 'approved' THEN SYSTIMESTAMP ELSE APPROVED_AT END "
                    "WHERE ID = :p_id AND STATUS IN ('draft','approved')",
                    {'p_s': status, 'p_s2': status, 'p_s3': status, 'p_u': username,
                     'p_id': order_id})
                if not r.get('rowcount'):
                    return {'success': False, 'status': 409,
                            'error': 'Заказ уже в рейсе или доставлен'}
                db.connection.commit()
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def approve_all(run_id: Optional[int], username: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = ("UPDATE PECO_FUEL_ORDERS SET STATUS = 'approved', APPROVED_BY = :p_u, "
                       "APPROVED_AT = SYSTIMESTAMP WHERE STATUS = 'draft'")
                params: Dict[str, Any] = {'p_u': username}
                if run_id:
                    sql += " AND RUN_ID = :p_run"
                    params['p_run'] = run_id
                r = db.execute_query(sql, params)
                db.connection.commit()
            return {'success': True, 'approved': r.get('rowcount', 0)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Нефтебаза и импорт ====================

    @staticmethod
    def depot(lang: str, import_lead_days: float = 9.0) -> Dict[str, Any]:
        res = FuelAutoOrder.depot_requirement(import_lead_days)
        if not res.get('success'):
            return res
        try:
            with DatabaseModel() as db:
                suppliers = _localize(_rows(db.execute_query(
                    "SELECT s.ID, s.CODE, s.NAME, s.SOURCE_CODE, s.COUNTRY, s.INCOTERMS, "
                    "s.LEAD_DAYS, s.MIN_LOT_L, s.PRICE_PER_L, s.CURRENCY, s.ACTIVE, "
                    "src.NAME_RU AS SOURCE_NAME_RU, src.NAME_RO AS SOURCE_NAME_RO, "
                    "src.NAME_EN AS SOURCE_NAME_EN, src.IS_IMPORT "
                    "FROM PECO_FUEL_SUPPLIERS s "
                    "JOIN PECO_REF_SUPPLY_SOURCES src ON src.CODE = s.SOURCE_CODE "
                    "WHERE s.ACTIVE = 1 ORDER BY src.SORT_ORDER, s.NAME")), lang)
            res['suppliers'] = suppliers
            return res
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Рейсы и телеметрия ====================

    @staticmethod
    def plan_trips(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        return FuelAutoOrder.plan_trips(payload.get('run_id'), username,
                                        int(payload.get('max_stations') or 3))

    @staticmethod
    def trips(lang: str, status: Optional[str] = None) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PECO_TRIPS"
        params: Dict[str, Any] = {}
        if status:
            sql += " WHERE STATUS = :p_st"
            params['p_st'] = status
        sql += " ORDER BY ID DESC"
        try:
            with DatabaseModel() as db:
                data = _rows(db.execute_query(sql, params))
                stops = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PECO_TRIP_STOPS ORDER BY TRIP_ID, STOP_NO")), lang)
                trucks = _rows(db.execute_query(
                    "SELECT * FROM V_PECO_TRUCKS ORDER BY PLATE_NO"))
            by_trip: Dict[int, List[Dict[str, Any]]] = {}
            for s in stops:
                by_trip.setdefault(int(s['trip_id']), []).append(s)
            for t in data:
                t['stops'] = by_trip.get(int(t['id']), [])
            return {'success': True, 'data': data, 'trucks': trucks}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def set_trip_status(trip_id: int, status: str, username: str) -> Dict[str, Any]:
        if status not in ('planned', 'loading', 'en_route', 'done', 'cancelled'):
            return {'success': False, 'error': 'Недопустимый статус', 'status': 400}
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE PECO_TRIPS SET STATUS = :p_s, "
                    "ACT_DEPART = CASE WHEN :p_s2 = 'en_route' AND ACT_DEPART IS NULL "
                    "  THEN SYSTIMESTAMP ELSE ACT_DEPART END, "
                    "ACT_RETURN = CASE WHEN :p_s3 = 'done' THEN SYSTIMESTAMP ELSE ACT_RETURN END "
                    "WHERE ID = :p_id", {'p_s': status, 'p_s2': status, 'p_s3': status,
                                         'p_id': trip_id})
                if status == 'done':
                    db.execute_query(
                        "UPDATE PECO_FUEL_ORDERS SET STATUS = 'delivered' "
                        "WHERE TRIP_ID = :p_tr AND STATUS = 'planned'", {'p_tr': trip_id})
                db.connection.commit()
            _ = username
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def gps_events(lang: str, status: Optional[str] = 'new',
                   limit: int = 100) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PECO_GPS_EVENTS"
        params: Dict[str, Any] = {}
        if status:
            sql += " WHERE STATUS = :p_st"
            params['p_st'] = status
        sql += " ORDER BY TS DESC FETCH FIRST :p_l ROWS ONLY"
        params['p_l'] = limit
        try:
            with DatabaseModel() as db:
                return {'success': True,
                        'data': _localize(_rows(db.execute_query(sql, params)), lang)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def track(trip_id: int) -> Dict[str, Any]:
        return PecoGps.track(trip_id)

    @staticmethod
    def analyze(trip_id: Optional[int] = None) -> Dict[str, Any]:
        return PecoGps.analyze(trip_id)

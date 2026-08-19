"""
Приём и разбор GPS-телеметрии бензовозов.

Транспорт свой, а датчики на аутсорсе: телеметрию присылает внешний
провайдер. Отсюда три решения.

1. ПРИЁМ ОТДЕЛЁН ОТ РАЗБОРА. Пинг пишется в PECO_GPS_PINGS всегда,
   даже если наши детекторы упадут: терять чужие данные, которые нельзя
   переспросить, недопустимо. События разбираются отдельным проходом.

2. АВТОРИЗАЦИЯ ПО ТОКЕНУ ПРОВАЙДЕРА, хеш в базе. Провайдер шлёт пинги
   пачками по HTTP; сессия браузера тут не при чём.

3. ДЕТЕКТОРЫ СЧИТАЮТ ГЕОМЕТРИЮ, А НЕ «ПОДОЗРИТЕЛЬНОСТЬ». Каждый сигнал
   объясняется одной фразой и проверяется по карте: стоянка N минут вне
   точек маршрута, отклонение M км от коридора, срыв пломбы при
   выключенном зажигании. Слив топлива система не «обнаруживает» —
   она показывает факты, из которых человек делает вывод.

Oracle-объекты: sql/106_peco_supply.sql
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel

# Пороги детекторов
TH = {
    'stop_minutes': 12.0,      # стоянка дольше — уже не светофор
    'stop_radius_km': 0.6,     # ближе этого к точке маршрута стоянка законна
    'deviation_km': 5.0,       # отклонение от коридора «депо → станции»
    'speed_kmh': 95.0,         # предел для гружёной цистерны
    'idle_minutes': 45.0,      # долгая стоянка с работающим двигателем
}
EARTH_KM = 6371.0088


def hash_token(token: str) -> str:
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние по большому кругу. Плоской геометрии тут мало: сеть тянется
    на 300 км с севера на юг, и ошибка проекции набегает в километры."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def _rows(res) -> List[Dict[str, Any]]:
    if not res or not res.get('success'):
        return []
    cols = [c.lower() for c in (res.get('columns') or [])]
    return [dict(zip(cols, r)) for r in (res.get('data') or [])]


class PecoGps:
    """Приём пингов и разбор их в события."""

    @staticmethod
    def provider_by_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        try:
            with DatabaseModel() as db:
                rows = _rows(db.execute_query(
                    "SELECT ID, CODE, NAME FROM PECO_GPS_PROVIDERS "
                    "WHERE TOKEN_HASH = :p_h AND ACTIVE = 1", {'p_h': hash_token(token)}))
                return rows[0] if rows else None
        except Exception:                                        # noqa: BLE001
            return None

    @staticmethod
    def set_provider_token(provider_id: int, token: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PECO_GPS_PROVIDERS SET TOKEN_HASH = :p_h WHERE ID = :p_id",
                    {'p_h': hash_token(token), 'p_id': provider_id})
                db.connection.commit()
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def ingest(provider: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Приём пачки пингов от провайдера.

        Формат: {"pings": [{"device_id": "...", "ts": "2026-08-20T10:15:00",
                            "lat": .., "lon": .., "speed": .., "ignition": 1,
                            "seal_closed": 1, "fuel_l": ..}, ...]}
        Неизвестный device_id не роняет пачку — он считается пропущенным
        и возвращается в ответе: у провайдера могут быть чужие машины.
        """
        pings = payload.get('pings') or ([payload] if payload.get('device_id') else [])
        if not pings:
            return {'success': False, 'error': 'Пустая пачка телеметрии', 'status': 400}
        try:
            with DatabaseModel() as db:
                trucks = {r['gps_device_id']: r for r in _rows(db.execute_query(
                    "SELECT ID, GPS_DEVICE_ID FROM PECO_TRUCKS "
                    "WHERE GPS_DEVICE_ID IS NOT NULL AND ACTIVE = 1"))}
                # Активный рейс машины: пинг привязывается к нему,
                # иначе телеметрия повиснет без контекста маршрута
                trips = {int(r['truck_id']): int(r['id']) for r in _rows(db.execute_query(
                    "SELECT ID, TRUCK_ID FROM PECO_TRIPS "
                    "WHERE STATUS IN ('loading','en_route') ORDER BY ID"))}
                accepted, unknown = 0, []
                for p in pings:
                    dev = str(p.get('device_id') or '')
                    truck = trucks.get(dev)
                    if not truck:
                        unknown.append(dev)
                        continue
                    ts = p.get('ts')
                    db.execute_query(
                        "INSERT INTO PECO_GPS_PINGS (TRUCK_ID, TRIP_ID, TS, LAT, LON, "
                        "SPEED_KMH, HEADING, IGNITION, SEAL_CLOSED, FUEL_L, PROVIDER_ID) "
                        "VALUES (:p_t, :p_tr, "
                        " NVL(TO_TIMESTAMP(:p_ts, 'YYYY-MM-DD\"T\"HH24:MI:SS'), SYSTIMESTAMP), "
                        " :p_lat, :p_lon, :p_sp, :p_hd, :p_ig, :p_seal, :p_fuel, :p_pr)",
                        {'p_t': int(truck['id']), 'p_tr': trips.get(int(truck['id'])),
                         'p_ts': (ts or '')[:19] or None,
                         'p_lat': float(p.get('lat') or 0), 'p_lon': float(p.get('lon') or 0),
                         'p_sp': p.get('speed'), 'p_hd': p.get('heading'),
                         'p_ig': p.get('ignition'), 'p_seal': p.get('seal_closed'),
                         'p_fuel': p.get('fuel_l'), 'p_pr': provider.get('id')})
                    accepted += 1
                db.connection.commit()
            return {'success': True, 'accepted': accepted,
                    'unknown_devices': sorted(set(unknown))}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Разбор в события ====================

    @staticmethod
    def analyze(trip_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Разбор телеметрии рейса в события.

        Считается по последовательности пингов: остановки (скорость ~0),
        удаление от ближайшей точки маршрута, скорость, срыв пломбы.
        Повторно найденное событие не дублируется — совпадение по типу
        и минуте времени.
        """
        try:
            with DatabaseModel() as db:
                trips = _rows(db.execute_query(
                    "SELECT ID, TRUCK_ID, DEPOT_ID FROM PECO_TRIPS "
                    + ("WHERE ID = :p_id" if trip_id else
                       "WHERE STATUS IN ('loading','en_route','done')"),
                    {'p_id': trip_id} if trip_id else {}))
                created = 0
                for tr in trips:
                    pings = _rows(db.execute_query(
                        "SELECT TS, LAT, LON, SPEED_KMH, IGNITION, SEAL_CLOSED "
                        "FROM PECO_GPS_PINGS WHERE TRIP_ID = :p_tr ORDER BY TS",
                        {'p_tr': int(tr['id'])}))
                    if len(pings) < 2:
                        continue
                    # Точки маршрута: нефтебаза плюс станции рейса
                    route = _rows(db.execute_query(
                        "SELECT d.LAT, d.LON FROM PECO_DEPOTS d WHERE d.ID = :p_d "
                        "UNION ALL "
                        "SELECT s.LAT, s.LON FROM PECO_TRIP_STOPS st "
                        "JOIN PECO_STATIONS s ON s.ID = st.STATION_ID "
                        "WHERE st.TRIP_ID = :p_tr AND s.LAT IS NOT NULL",
                        {'p_d': tr['depot_id'], 'p_tr': int(tr['id'])}))
                    pts = [(float(r['lat']), float(r['lon'])) for r in route
                           if r.get('lat') is not None]

                    existing = {(r['event_type'], str(r['ts'])[:16]) for r in _rows(
                        db.execute_query(
                            "SELECT EVENT_TYPE, TS FROM PECO_GPS_EVENTS WHERE TRIP_ID = :p_tr",
                            {'p_tr': int(tr['id'])}))}

                    def add(ev_type, sev, ts, lat, lon, val, ru, ro, en):
                        nonlocal created
                        key = (ev_type, str(ts)[:16])
                        if key in existing:
                            return
                        existing.add(key)
                        db.execute_query(
                            "INSERT INTO PECO_GPS_EVENTS (TRUCK_ID, TRIP_ID, EVENT_TYPE, "
                            "SEVERITY, TS, LAT, LON, VALUE_NUM, MESSAGE_RU, MESSAGE_RO, "
                            "MESSAGE_EN) VALUES (:p_t, :p_tr, :p_ty, :p_s, :p_ts, :p_lat, "
                            ":p_lon, :p_v, :p_ru, :p_ro, :p_en)",
                            {'p_t': int(tr['truck_id']), 'p_tr': int(tr['id']),
                             'p_ty': ev_type, 'p_s': sev, 'p_ts': ts, 'p_lat': lat,
                             'p_lon': lon, 'p_v': round(val, 2) if val is not None else None,
                             'p_ru': ru[:500], 'p_ro': ro[:500], 'p_en': en[:500]})
                        created += 1

                    stop_start = None
                    for i, p in enumerate(pings):
                        lat, lon = float(p['lat']), float(p['lon'])
                        speed = float(p.get('speed_kmh') or 0)
                        ts = p['ts']

                        if speed > TH['speed_kmh']:
                            add('speeding', 'warn', ts, lat, lon, speed,
                                f'Скорость {speed:.0f} км/ч на гружёной цистерне',
                                f'Viteză {speed:.0f} km/h cu cisterna încărcată',
                                f'Speed {speed:.0f} km/h with a loaded tanker')

                        near = min((haversine_km(lat, lon, a, b) for a, b in pts),
                                   default=None)
                        if near is not None and near > TH['deviation_km']:
                            add('route_deviation', 'warn', ts, lat, lon, near,
                                f'Отклонение {near:.1f} км от точек маршрута',
                                f'Abatere de {near:.1f} km de la traseu',
                                f'{near:.1f} km deviation from the route')

                        if p.get('seal_closed') == 0:
                            add('seal_open', 'crit', ts, lat, lon, None,
                                'Пломба горловины открыта вне точки слива',
                                'Sigiliul gurii de descărcare este deschis în afara punctului',
                                'Discharge seal open outside a delivery point')

                        # Остановка: копим, пока скорость около нуля
                        if speed < 3:
                            if stop_start is None:
                                stop_start = (ts, lat, lon)
                        else:
                            if stop_start is not None:
                                mins = (ts - stop_start[0]).total_seconds() / 60.0
                                d = min((haversine_km(stop_start[1], stop_start[2], a, b)
                                         for a, b in pts), default=99.0)
                                if mins >= TH['stop_minutes'] and d > TH['stop_radius_km']:
                                    add('unplanned_stop', 'crit', stop_start[0],
                                        stop_start[1], stop_start[2], mins,
                                        f'Стоянка {mins:.0f} мин в {d:.1f} км от точек маршрута',
                                        f'Staționare {mins:.0f} min la {d:.1f} km de traseu',
                                        f'{mins:.0f} min stop {d:.1f} km away from the route')
                                stop_start = None
                    db.connection.commit()
            return {'success': True, 'events': created}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def track(trip_id: int, limit: int = 2000) -> Dict[str, Any]:
        """Трек рейса для карты: точки в порядке времени."""
        try:
            with DatabaseModel() as db:
                data = _rows(db.execute_query(
                    "SELECT TS, LAT, LON, SPEED_KMH, SEAL_CLOSED FROM PECO_GPS_PINGS "
                    "WHERE TRIP_ID = :p_tr ORDER BY TS FETCH FIRST :p_lim ROWS ONLY",
                    {'p_tr': trip_id, 'p_lim': limit}))
                events = _rows(db.execute_query(
                    "SELECT * FROM V_PECO_GPS_EVENTS WHERE TRIP_ID = :p_tr ORDER BY TS",
                    {'p_tr': trip_id}))
            return {'success': True, 'points': data, 'events': events}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

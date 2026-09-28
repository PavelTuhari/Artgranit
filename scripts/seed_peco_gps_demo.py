#!/usr/bin/env python3
"""
Демо-трек рейса бензовоза: телеметрия от «внешнего провайдера».

Трек строится по реальным точкам маршрута (нефтебаза → станции рейса)
с шагом в пять минут. В один из перегонов намеренно вставлена стоянка
в стороне от маршрута со срывом пломбы — именно этот сценарий контур
и должен показывать, иначе проверить детекторы не на чем.

Запуск: python3 scripts/seed_peco_gps_demo.py [--trip ID] [--clean]
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel
from models.peco_gps import PecoGps


def rows(res):
    if not res or not res.get('success'):
        return []
    cols = [c.lower() for c in (res.get('columns') or [])]
    return [dict(zip(cols, r)) for r in (res.get('data') or [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trip', type=int, help='ID рейса (по умолчанию первый в пути)')
    ap.add_argument('--clean', action='store_true', help='удалить прежние пинги и события')
    args = ap.parse_args()

    with DatabaseModel() as db:
        if args.clean:
            db.execute_query('DELETE FROM PECO_GPS_EVENTS')
            db.connection.commit()
            db.execute_query('DELETE FROM PECO_GPS_PINGS')
            db.connection.commit()
            print('телеметрия очищена')

        sql = "SELECT ID, TRUCK_ID, DEPOT_ID FROM PECO_TRIPS"
        params = {}
        if args.trip:
            sql += " WHERE ID = :p_id"
            params['p_id'] = args.trip
        else:
            sql += " WHERE STATUS IN ('en_route','loading','planned') ORDER BY ID"
        trips = rows(db.execute_query(sql, params))
        if not trips:
            print('нет подходящего рейса'); return
        trip = trips[0]

        depot = rows(db.execute_query(
            "SELECT LAT, LON FROM PECO_DEPOTS WHERE ID = :p", {'p': trip['depot_id']}))
        stops = rows(db.execute_query(
            "SELECT DISTINCT s.LAT, s.LON, st.STOP_NO FROM PECO_TRIP_STOPS st "
            "JOIN PECO_STATIONS s ON s.ID = st.STATION_ID "
            "WHERE st.TRIP_ID = :p AND s.LAT IS NOT NULL ORDER BY st.STOP_NO",
            {'p': trip['id']}))
        if not depot or not stops:
            print('у рейса нет координат маршрута'); return

        route = [(float(depot[0]['lat']), float(depot[0]['lon']))]
        route += [(float(s['lat']), float(s['lon'])) for s in stops]

        pings, ts = [], datetime.now() - timedelta(hours=3)
        for leg in range(len(route) - 1):
            a, b = route[leg], route[leg + 1]
            steps = 14
            for i in range(steps + 1):
                lat = a[0] + (b[0] - a[0]) * i / steps
                lon = a[1] + (b[1] - a[1]) * i / steps
                speed = 0 if i in (0, steps) else 62
                pings.append({'device_id': None, 'ts': ts, 'lat': lat, 'lon': lon,
                              'speed': speed, 'ignition': 1, 'seal': 1})
                ts += timedelta(minutes=5)
                # На первом перегоне — стоянка в стороне от маршрута со срывом
                # пломбы: сценарий, ради которого контур и строился
                if leg == 0 and i == 7:
                    off_lat = lat + 0.075
                    off_lon = lon + 0.055
                    for k in range(6):
                        pings.append({'device_id': None, 'ts': ts, 'lat': off_lat,
                                      'lon': off_lon, 'speed': 0, 'ignition': 0,
                                      'seal': 0 if k >= 2 else 1})
                        ts += timedelta(minutes=6)

        device = rows(db.execute_query(
            "SELECT GPS_DEVICE_ID FROM PECO_TRUCKS WHERE ID = :p", {'p': trip['truck_id']}))
        dev_id = device[0]['gps_device_id'] if device else None
        if not dev_id:
            print('у бензовоза нет GPS-устройства'); return

        cur = db.connection.cursor()
        cur.executemany(
            "INSERT INTO PECO_GPS_PINGS (TRUCK_ID, TRIP_ID, TS, LAT, LON, SPEED_KMH, "
            "IGNITION, SEAL_CLOSED, PROVIDER_ID) VALUES (:1, :2, :3, :4, :5, :6, :7, :8, "
            "(SELECT MIN(ID) FROM PECO_GPS_PROVIDERS))",
            [(int(trip['truck_id']), int(trip['id']), p['ts'], round(p['lat'], 6),
              round(p['lon'], 6), p['speed'], p['ignition'], p['seal']) for p in pings])
        db.connection.commit()
        print(f"рейс {trip['id']}: пингов {len(pings)}")

    res = PecoGps.analyze(trips[0]['id'])
    print('событий найдено:', res.get('events'), res.get('error', ''))
    with DatabaseModel() as db:
        for r in rows(db.execute_query(
                "SELECT EVENT_TYPE, SEVERITY, MESSAGE_RU FROM V_PECO_GPS_EVENTS "
                "WHERE TRIP_ID = :p ORDER BY TS", {'p': trips[0]['id']}))[:8]:
            print(f"  [{r['severity']:4}] {r['event_type']:16} {r['message_ru']}")


if __name__ == '__main__':
    main()

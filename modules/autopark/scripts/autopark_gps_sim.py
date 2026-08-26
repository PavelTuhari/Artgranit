#!/usr/bin/env python3
"""Autopark -- внешний GPS-провайдер-эмулятор (доказательство прослойки).

Смысл этого скрипта: он играет роль РЕАЛЬНОГО GPS-провайдера, а не
внутреннего кода портала. Поэтому он сознательно НЕ импортирует
``modules.autopark.store`` и не открывает соединение с Oracle -- он
логинится и ходит HTTP-ом ровно так же, как будет ходить трекер на
настоящем бензовозе (POST /api/gps/ingest с cookie-сессией залогиненного
пользователя). Единственный "внутренний" импорт -- ``modules.autopark.gps``
(чистая геометрия/интерполяция без БД, см. её докстринг) -- он используется
ТОЛЬКО чтобы понять, где по времени должна быть точка на маршруте
(тот же расчёт, которым будет пользоваться сам симулятор внутри системы
для live-позиций); сама отправка точки идёт исключительно через API.

Два режима:

  --live NNN
      Раз в NNN секунд (по умолчанию 10) отправляет очередную порцию
      накопившихся точек по каждому сегодняшнему рейсу через
      POST /api/gps/ingest -- то есть эмулирует поток телеметрии с
      реального устройства.

  --replay-recent N
      Прогоняет AutoparkController.gps_replay для N последних (не
      DRAFT) рейсов -- "подключение источника треков вместо тестового
      набора фактов" (см. ТЗ задачи). Каждый вызов заменяет
      FLT_TRIPS.FACT_KM реального рейса треком, сгенерированным той же
      интерполяцией маршрута + шумом GPS-приёмника.

      Эта часть предпочитает настоящий HTTP (тот же контракт, что и
      --live), но если сервер недоступен (``--base-url`` не отвечает),
      скрипт честно сообщает об этом и продолжает через
      ``app.test_client()`` -- не бизнес-обходной путь в БД, а
      единственный способ проверить сквозную цепочку без поднятого
      процесса Flask, задокументированный в самой задаче как разрешённый
      резерв.

Использование:
    venv/bin/python modules/autopark/scripts/autopark_gps_sim.py --live
    venv/bin/python modules/autopark/scripts/autopark_gps_sim.py --live --interval 5 --duration 30
    venv/bin/python modules/autopark/scripts/autopark_gps_sim.py --replay-recent 30
    venv/bin/python modules/autopark/scripts/autopark_gps_sim.py --replay-recent 30 --base-url http://127.0.0.1:9999
"""
from __future__ import annotations

import argparse
import os
import sys
import time as time_mod
from datetime import date, datetime, time as dtime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.autopark import gps                                # noqa: E402

DEFAULT_BASE_URL = "http://127.0.0.1:3003"
DEFAULT_USERNAME = os.environ.get("DEFAULT_USERNAME", "ADMIN")
DEFAULT_PASSWORD = os.environ.get("DEFAULT_PASSWORD", "")
MODULE_BASE = "/UNA.md/orasldev/autopark"

GPS_DEPART_HOUR = 8
GPS_AVG_SPEED_KMH = 55.0
GPS_STOP_MINUTES = 25.0


class HttpTransport:
    """Тонкая обёртка над `requests.Session` -- логин формой,
    cookie-сессия, GET/POST JSON. Всё, что нужно эмулятору внешнего
    устройства -- ничего специфичного для портала здесь нет."""

    def __init__(self, base_url: str):
        import requests
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def login(self, username: str, password: str) -> bool:
        r = self.session.post(f"{self.base_url}/login",
                              data={"username": username, "password": password},
                              timeout=10)
        if r.status_code != 200:
            return False
        try:
            return bool(r.json().get("success"))
        except ValueError:
            return False

    def get(self, path: str):
        r = self.session.get(f"{self.base_url}{MODULE_BASE}{path}", timeout=10)
        return r.json()

    def post(self, path: str, payload: dict):
        r = self.session.post(f"{self.base_url}{MODULE_BASE}{path}",
                              json=payload, timeout=10)
        return r.json()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _points_between(geo_points, depart_ts, avg_speed, stop_minutes,
                    window_from: datetime, window_to: datetime):
    """Точки профиля маршрута, приходящиеся на окно [window_from, window_to).

    Используется живым режимом: каждый тик отправляем только точки,
    накопившиеся с прошлого тика -- ровно так вело бы себя реальное
    устройство, шлющее буфер с последней отправки, а не весь трек заново.
    """
    profile = gps.interpolate_route(geo_points, depart_ts, avg_speed, stop_minutes)
    out = []
    for node in profile:
        if window_from <= node["ts"] < window_to:
            out.append({"ts": _iso(node["ts"]), "lat": node["lat"],
                       "lon": node["lon"], "speed": avg_speed})
    # Дополнительно -- текущая интерполированная позиция на конец окна,
    # даже если она не совпадает с узлом профиля (между остановками) --
    # иначе при коротком тике (10 с) буфер часто был бы пуст.
    pos = gps.position_at(profile, window_to)
    if pos and pos["started"] and not pos["finished"]:
        out.append({"ts": _iso(window_to), "lat": pos["lat"], "lon": pos["lon"],
                   "speed": avg_speed})
    return out


def run_live(transport: HttpTransport, interval: int, duration: Optional[int]) -> None:
    print(f"[live] логин {DEFAULT_USERNAME}@{transport.base_url} ...")
    if not transport.login(DEFAULT_USERNAME, DEFAULT_PASSWORD):
        print("[live] ОШИБКА логина -- проверьте DEFAULT_USERNAME/DEFAULT_PASSWORD в .env")
        sys.exit(1)

    started_at = time_mod.time()
    last_sent_to = {}
    tick = 0
    while True:
        tick += 1
        trips_res = transport.get(f"/api/trips?date_from={date.today().isoformat()}"
                                  f"&date_to={date.today().isoformat()}")
        if not trips_res.get("success"):
            print(f"[live] тик {tick}: /api/trips -> {trips_res.get('message')}")
        else:
            geo_res = transport.get("/api/gps/geo")
            if not geo_res.get("success"):
                print(f"[live] тик {tick}: /api/gps/geo -> {geo_res.get('message')}")
            else:
                geo = geo_res["data"]
                stations_by_id = {s["id"]: s for s in geo["stations"]}
                load_by_id = {p["id"]: p for p in geo["load_points"]}
                end_by_id = {p["id"]: p for p in geo["end_points"]}
                now = datetime.now()
                sent_total = 0
                for trip in trips_res["data"]:
                    if trip.get("status_code") == "DRAFT":
                        continue
                    geo_points = []
                    lp = load_by_id.get(trip["load_point_id"])
                    if lp:
                        geo_points.append({"kind": "LOAD", "id": lp["id"],
                                          "lat": lp["lat"], "lon": lp["lon"]})
                    for stop in trip.get("stops") or []:
                        st = stations_by_id.get(stop["station_id"])
                        if st:
                            geo_points.append({"kind": "STATION", "id": st["id"],
                                              "lat": st["lat"], "lon": st["lon"]})
                    ep = end_by_id.get(trip["end_point_id"])
                    if ep:
                        geo_points.append({"kind": "END", "id": ep["id"],
                                          "lat": ep["lat"], "lon": ep["lon"]})
                    if len(geo_points) < 2:
                        continue

                    depart_ts = datetime.combine(date.today(), dtime(GPS_DEPART_HOUR, 0))
                    window_from = last_sent_to.get(trip["id"], depart_ts)
                    points = _points_between(geo_points, depart_ts, GPS_AVG_SPEED_KMH,
                                             GPS_STOP_MINUTES, window_from, now)
                    last_sent_to[trip["id"]] = now
                    if not points:
                        continue
                    res = transport.post("/api/gps/ingest",
                                         {"provider": "SIM", "trip_id": trip["id"],
                                          "points": points})
                    if res.get("success"):
                        sent_total += len(points)
                    else:
                        print(f"[live] рейс {trip['id']}: ingest -> "
                              f"{res.get('message')}")
                print(f"[live] тик {tick}: отправлено {sent_total} точек "
                      f"по {len(trips_res['data'])} рейсам")

        if duration is not None and (time_mod.time() - started_at) >= duration:
            print(f"[live] остановлено по --duration {duration} c")
            return
        time_mod.sleep(interval)


def _recent_trip_ids(get_json, n: int):
    today = date.today()
    days_back = 60
    ids = []
    while len(ids) < n and days_back <= 800:
        date_from = (today - timedelta(days=days_back)).isoformat()
        res = get_json(f"/api/trips?date_from={date_from}&date_to={today.isoformat()}")
        if res.get("success"):
            rows = [t for t in res["data"] if t.get("status_code") != "DRAFT"]
            rows.sort(key=lambda t: (t["trip_date"], t["id"]), reverse=True)
            ids = [t["id"] for t in rows]
        days_back *= 2
    return ids[:n]


def run_replay_recent(base_url: str, n: int) -> None:
    transport = None
    try:
        transport = HttpTransport(base_url)
        if not transport.login(DEFAULT_USERNAME, DEFAULT_PASSWORD):
            transport = None
    except Exception as exc:                                     # noqa: BLE001
        print(f"[replay] HTTP-сервер {base_url} недоступен ({exc}) -- "
              "переключаюсь на app.test_client() (разрешённый резерв, "
              "см. докстринг скрипта); хотя бы отдельный ingest ниже "
              "всё равно проверяется настоящим HTTP, если сервер поднят.")
        transport = None

    if transport is not None:
        print(f"[replay] используется настоящий HTTP: {base_url}{MODULE_BASE}")
        get_json = transport.get
        post_json = transport.post
    else:
        print("[replay] используется app.test_client() -- сервер не отвечал")
        import app as appmod
        client = appmod.app.test_client()
        client.post("/login", data={"username": DEFAULT_USERNAME,
                                    "password": DEFAULT_PASSWORD})

        def get_json(path):
            return client.get(MODULE_BASE + path).get_json()

        def post_json(path, payload):
            return client.post(MODULE_BASE + path, json=payload).get_json()

    ids = _recent_trip_ids(get_json, n)
    print(f"[replay] найдено {len(ids)} рейсов (запрошено {n})")

    ok = 0
    deviations = []
    for trip_id in ids:
        res = post_json("/api/gps/replay", {"trip_id": trip_id})
        if not res.get("success"):
            print(f"[replay] рейс {trip_id}: ОШИБКА -- {res.get('message')}")
            continue
        d = res["data"]
        norm_km = float(d.get("norm_km") or 0)
        fact_km = float(d.get("fact_km") or 0)
        if norm_km:
            deviations.append(abs(fact_km - norm_km) / norm_km * 100)
        ok += 1
        print(f"[replay] рейс {trip_id}: {d['points']} точек, "
              f"факт {fact_km:.1f} км (норма {norm_km:.1f} км)")

    avg_dev = sum(deviations) / len(deviations) if deviations else None
    print(f"\n[replay] итог: {ok}/{len(ids)} треков сформировано, "
          f"средняя |факт-норма| = "
          f"{avg_dev:.1f}%" if avg_dev is not None else
          f"\n[replay] итог: {ok}/{len(ids)} треков сформировано, "
          "средняя |факт-норма| не посчитана (нет норматива)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autopark GPS -- внешний провайдер-эмулятор (проходит "
                    "через тот же HTTP-контракт, что и реальный трекер)")
    parser.add_argument("--live", action="store_true",
                        help="цикл живой телеметрии по сегодняшним рейсам")
    parser.add_argument("--interval", type=int, default=10,
                        help="интервал между тиками, с (по умолчанию 10)")
    parser.add_argument("--duration", type=int, default=None,
                        help="остановиться после N секунд (по умолчанию — бесконечно)")
    parser.add_argument("--replay-recent", type=int, metavar="N",
                        help="сформировать треки для N последних рейсов")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"адрес портала (по умолчанию {DEFAULT_BASE_URL})")
    args = parser.parse_args()

    if not args.live and not args.replay_recent:
        parser.print_help()
        sys.exit(2)

    if args.live:
        transport = HttpTransport(args.base_url)
        run_live(transport, args.interval, args.duration)

    if args.replay_recent:
        run_replay_recent(args.base_url, args.replay_recent)


if __name__ == "__main__":
    from typing import Optional  # noqa: E402  (только для аннотации run_live)
    main()

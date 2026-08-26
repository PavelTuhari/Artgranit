"""Autopark — прослойка между GPS-провайдером и системой (Bemol).

Ни одного импорта БД — весь модуль работает с простыми числами/dict/list,
которые ему передаёт вызывающий код (store.py/controller.py). Это
позволяет тестировать геометрию и интерполяцию маршрута без wallet и без
Oracle — см. tests/test_autopark.py.

Идея прослойки: у симулятора (SIM) и у будущего реального провайдера
(HTTP_PUSH/HTTP_PULL, FLT_GPS_PROVIDERS.KIND) один и тот же вход —
``normalize_points(provider_kind, payload)``. Контроллер и БД ничего не
знают о том, кто именно прислал точки: симулятор дергает ровно тот же
``POST /api/gps/ingest``, каким будет пользоваться реальный трекер на
бензовозе. Замена тестового набора GPS-фактов на реальный источник —
это переключение ``FLT_GPS_PROVIDERS.ACTIVE``/появление второй строки
регистра, а не переписывание кода.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

EARTH_RADIUS_KM = 6371.0088

# Provider kinds a real integration can use, mirrors
# FLT_GPS_PROVIDERS.KIND CHECK IN ('SIM','HTTP_PUSH','HTTP_PULL').
NORMALIZED_KINDS = ("SIM", "HTTP_PUSH", "HTTP_PULL")


# -- Геометрия -----------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние по прямой (большому кругу) между двумя точками, км.

    Формула гаверсинуса — стандартная оценка расстояния по сфере,
    достаточная для сверки GPS-трека с нормативным пробегом по дорогам
    (реальный путь всегда длиннее прямой, это ожидаемо и не ошибка).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def track_length_km(points: Sequence[Dict[str, Any]]) -> float:
    """Длина ломаной по последовательным точкам трека (сумма прямых).

    ``points`` — список ``{"lat", "lon", ...}`` в хронологическом
    порядке (порядок вызывающий код обеспечивает сам — здесь только
    суммирование соседних пар, без сортировки по ts). Меньше двух точек
    — длина 0, а не ошибка: одна точка — это ещё не трек.
    """
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += haversine_km(float(a["lat"]), float(a["lon"]),
                              float(b["lat"]), float(b["lon"]))
    return total


# -- Нормализация сырого payload провайдера -------------------------------

def normalize_points(provider_kind: str,
                     payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Сырой payload провайдера -> список точек {ts, lat, lon, speed_kmh}.

    Единый формат для SIM и generic HTTP_PUSH (ТЗ задачи): JSON вида
    ``{"device"|"track": [{"ts", "lat", "lon", "speed"?}, ...]}`` — ключ
    верхнего уровня может называться и "device", и "track" (оба
    встречаются у реальных трекеров под разными терминами одного и того
    же массива точек). Невалидные точки не поднимают исключение — они
    отбрасываются, а причина отбрасывания попадает в список ``reasons``
    (второй элемент кортежа), чтобы вызывающий код мог залогировать, что
    именно провайдер прислал плохого.

    ``provider_kind`` сегодня не меняет разбор (SIM и HTTP_PUSH несут
    один и тот же формат), но параметр остаётся в сигнатуре — второй
    реальный формат (например HTTP_PULL с другой схемой полей) подключится
    веткой здесь же, не меняя вызывающий код.
    """
    reasons: List[str] = []
    if provider_kind not in NORMALIZED_KINDS:
        return [], [f"неизвестный тип провайдера: {provider_kind}"]

    raw_points = payload.get("track")
    if raw_points is None:
        raw_points = payload.get("device")
    if raw_points is None:
        return [], ["payload не содержит ни 'track', ни 'device'"]
    if not isinstance(raw_points, list):
        return [], ["'track'/'device' должен быть списком точек"]

    out: List[Dict[str, Any]] = []
    for i, raw in enumerate(raw_points):
        if not isinstance(raw, dict):
            reasons.append(f"точка #{i}: не объект")
            continue
        ts = raw.get("ts")
        if not ts:
            reasons.append(f"точка #{i}: отсутствует ts")
            continue
        # Провайдер шлёт ts JSON-строкой ("2026-08-26T08:00:00" и т.п.);
        # Oracle DATE-колонка (FLT_GPS_TRACKS.TS) требует настоящий
        # python-объект datetime как bind, а не голую строку -- то же
        # ORA-01861 "literal does not match format string", что уже
        # ловили с date_from/date_to в controller._require_date. Разбор
        # здесь, а не в store, чтобы store никогда не видел строку.
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                reasons.append(f"точка #{i}: ts не разбирается как ISO-дата: {ts!r}")
                continue
        elif not isinstance(ts, datetime):
            reasons.append(f"точка #{i}: ts должен быть строкой или datetime")
            continue
        try:
            lat = float(raw.get("lat"))
            lon = float(raw.get("lon"))
        except (TypeError, ValueError):
            reasons.append(f"точка #{i}: lat/lon не число")
            continue
        if not (-90.0 <= lat <= 90.0):
            reasons.append(f"точка #{i}: lat вне диапазона [-90, 90]: {lat}")
            continue
        if not (-180.0 <= lon <= 180.0):
            reasons.append(f"точка #{i}: lon вне диапазона [-180, 180]: {lon}")
            continue
        speed = raw.get("speed", raw.get("speed_kmh"))
        if speed is not None:
            try:
                speed = float(speed)
            except (TypeError, ValueError):
                reasons.append(f"точка #{i}: speed не число — точка принята без скорости")
                speed = None
        out.append({"ts": ts, "lat": lat, "lon": lon, "speed_kmh": speed})
    return out, reasons


# -- Временной профиль маршрута (ядро live-симуляции и replay) -----------

GeoLookup = Callable[[str, Any], Optional[Tuple[float, float]]]


def interpolate_route(
    geo_points: Sequence[Dict[str, Any]],
    depart_ts,
    avg_speed_kmh: float,
    stop_minutes: float,
) -> List[Dict[str, Any]]:
    """Строит временной профиль движения по ломаной маршрута.

    ``geo_points`` — точки маршрута В ПОРЯДКЕ СЛЕДОВАНИЯ, каждая
    ``{"kind": "LOAD"|"STATION"|"END", "id", "lat", "lon"}``. Между
    соседними точками движение равномерное со скоростью
    ``avg_speed_kmh``; на каждой точке кроме первой и последней —
    остановка (стоянка/слив) длиной ``stop_minutes`` минут (реальный
    случай — только АЗС, но функция не завязана на конкретный "kind":
    стоянка ставится на любой промежуточной точке, отбор какие точки
    промежуточные делает вызывающий код через состав ``geo_points``).

    Возвращает список опорных узлов профиля
    ``{"ts": datetime, "lat", "lon", "kind", "id", "leg_km"}`` —
    "leg_km" на узле прибытия — длина только что пройденного участка (на
    первом узле, где ещё нечего проходить, 0.0. :func:`position_at`
    линейно интерполирует МЕЖДУ этими узлами по времени, включая паузы
    стоянки, где позиция не меняется.

    ``avg_speed_kmh <= 0`` — ошибка данных (деление на 0/движение назад
    во времени бессмысленно), поднимается ValueError, а не тихий
    провал куда-то в отрицательную длительность.
    """
    if avg_speed_kmh <= 0:
        raise ValueError("средняя скорость должна быть больше нуля")
    if not geo_points:
        return []

    profile: List[Dict[str, Any]] = []
    ts = depart_ts
    first = geo_points[0]
    profile.append({"ts": ts, "lat": first["lat"], "lon": first["lon"],
                     "kind": first.get("kind"), "id": first.get("id"),
                     "leg_km": 0.0})

    last = len(geo_points) - 1
    for i in range(1, len(geo_points)):
        prev = geo_points[i - 1]
        cur = geo_points[i]
        leg_km = haversine_km(prev["lat"], prev["lon"], cur["lat"], cur["lon"])
        travel_hours = leg_km / avg_speed_kmh
        ts = ts + timedelta(hours=travel_hours)
        profile.append({"ts": ts, "lat": cur["lat"], "lon": cur["lon"],
                         "kind": cur.get("kind"), "id": cur.get("id"),
                         "leg_km": leg_km})
        if i != last and stop_minutes:
            ts = ts + timedelta(minutes=stop_minutes)
            profile.append({"ts": ts, "lat": cur["lat"], "lon": cur["lon"],
                             "kind": cur.get("kind"), "id": cur.get("id"),
                             "leg_km": 0.0})
    return profile


def position_at(profile: Sequence[Dict[str, Any]], ts) -> Optional[Dict[str, Any]]:
    """Позиция бензовоза в момент ``ts`` по профилю :func:`interpolate_route`.

    До выезда (``ts`` раньше первого узла) — позиция старта, ``started``
    = False. После финиша (``ts`` позже последнего узла) — позиция
    финиша, ``finished`` = True. Между двумя узлами — линейная
    интерполяция координат по доле прошедшего времени; внутри интервала
    стоянки (соседние узлы с одинаковыми координатами) интерполяция
    вырождается в "стоим на месте", что и требуется. Пустой профиль —
    None (маршрут не построен, позиции не существует).
    """
    if not profile:
        return None
    if ts <= profile[0]["ts"]:
        p = profile[0]
        return {"lat": p["lat"], "lon": p["lon"], "started": False,
               "finished": False}
    last = profile[-1]
    if ts >= last["ts"]:
        return {"lat": last["lat"], "lon": last["lon"], "started": True,
               "finished": True}

    for a, b in zip(profile, profile[1:]):
        if a["ts"] <= ts <= b["ts"]:
            span = (b["ts"] - a["ts"]).total_seconds()
            frac = 0.0 if span <= 0 else (ts - a["ts"]).total_seconds() / span
            lat = a["lat"] + (b["lat"] - a["lat"]) * frac
            lon = a["lon"] + (b["lon"] - a["lon"]) * frac
            return {"lat": lat, "lon": lon, "started": True, "finished": False}
    # Не должно достигаться при отсортированном по времени профиле, но на
    # всякий случай — последняя известная точка, а не исключение.
    return {"lat": last["lat"], "lon": last["lon"], "started": True,
           "finished": True}

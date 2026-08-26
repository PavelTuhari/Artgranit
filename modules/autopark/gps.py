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


# -- Дорожный коэффициент (replay -- см. GPS_INTEGRATION.md) -------------
#
# interpolate_route строит ЛОМАНУЮ ПО ПРЯМЫМ между точками маршрута --
# это годится для отображения (карта условная, без реальных дорог), но
# длина такой прямой систематически КОРОЧЕ дорожного норматива NORM_KM
# (дорога всегда петляет). Записывать FACT_KM как haversine-сумму прямых
# точек означало бы, что реплеенные рейсы выглядят "телепортацией"
# бензовоза -- расхождение около -39% на реальных данных (см.
# .superpowers/sdd/autopark-task5-gps.md, находка координатора
# 26.08.2026). Функции ниже не меняют интерфейс interpolate_route/
# position_at (те остаются чистой геометрией прямых для отрисовки) --
# они пост-обрабатывают уже построенный профиль, вставляя между каждой
# парой соседних узлов точку излома так, чтобы СУММА haversine-отрезков
# приблизилась к заданной дорожной длине. Профиль остаётся кусочно-
# прямым (два коротких прямых отрезка на каждом участке вместо одного) --
# для условной карты это по-прежнему "почти прямая", а записываемая
# длина -- уже дорожная.

def _equirect_xy(lat: float, lon: float, ref_lat: float) -> Tuple[float, float]:
    """Градусы -> локальные км (эквиректангулярная проекция вокруг
    ``ref_lat``). Годится только на региональном масштабе (Молдова,
    сотни км) -- нужна исключительно чтобы найти точку излома
    перпендикулярно линии участка, итоговая длина всё равно считается
    обратно через haversine_km, а не через эту проекцию."""
    x = lon * 111.320 * math.cos(math.radians(ref_lat))
    y = lat * 110.574
    return x, y


def _equirect_lonlat(x: float, y: float, ref_lat: float) -> Tuple[float, float]:
    lat = y / 110.574
    lon = x / (111.320 * math.cos(math.radians(ref_lat)) or 1e-9)
    return lat, lon


def road_leg_midpoint(lat1: float, lon1: float, lat2: float, lon2: float,
                      target_km: float, sign: float = 1.0) -> Tuple[float, float]:
    """Точка излома A-M-B такая, что haversine(A,M) + haversine(M,B) ~=
    ``target_km`` (плоская аппроксимация, см. модульный докстринг выше).

    Если ``target_km`` меньше или равно прямому расстоянию A-B, излом не
    нужен -- геометрического смысла в отрицательном/нулевом ``h`` нет,
    возвращается настоящая середина без смещения (сумма отрезков тогда
    просто равна прямой, короче цели -- вызывающий код (:func:`road_scaled_track`)
    это компенсирует перераспределением через коэффициент, а не эта
    функция в одиночку).
    """
    ref_lat = (lat1 + lat2) / 2.0
    x1, y1 = _equirect_xy(lat1, lon1, ref_lat)
    x2, y2 = _equirect_xy(lat2, lon2, ref_lat)
    dx, dy = x2 - x1, y2 - y1
    straight = math.hypot(dx, dy)
    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    if straight <= 0 or target_km <= straight:
        return _equirect_lonlat(mx, my, ref_lat)
    half = straight / 2.0
    h = math.sqrt(max(0.0, (target_km / 2.0) ** 2 - half ** 2))
    ux, uy = -dy / straight, dx / straight
    px, py = mx + ux * h * sign, my + uy * h * sign
    return _equirect_lonlat(px, py, ref_lat)


def road_scaled_track(profile: Sequence[Dict[str, Any]], target_km: float,
                      correction_passes: int = 2) -> List[Dict[str, Any]]:
    """Вставляет точку излома между каждой парой соседних узлов профиля
    (:func:`interpolate_route`) так, чтобы суммарная haversine-длина
    получившейся ломаной была близка к ``target_km`` -- дорожному
    нормативу с шумом (см. модульный докстринг выше и
    docs/Autopark/GPS_INTEGRATION.md, раздел "дорожный коэффициент").

    Узлы-остановки (``leg_km`` отсутствует или 0 -- стоим на месте, см.
    :func:`interpolate_route`) не получают излома: добавлять зигзаг там,
    где бензовоз не двигался, было бы неправдоподобно.

    ``correction_passes`` — плоская проекция вносит небольшую погрешность
    (участки в сотни км на широте Молдовы), поэтому после первого
    прохода фактическая длина сверяется через :func:`track_length_km` и
    коэффициент уточняется пропорционально -- пары проходов достаточно,
    чтобы сойтись к цели с точностью на уровне долей процента.
    """
    legs = [n for n in profile if (n.get("leg_km") or 0) > 0]
    straight_total = sum(n["leg_km"] for n in legs)
    if not legs or straight_total <= 0 or target_km <= 0:
        return list(profile)

    factor = target_km / straight_total
    out: List[Dict[str, Any]] = []
    for _pass in range(max(1, correction_passes)):
        out = []
        if profile:
            out.append(dict(profile[0]))
        sign = 1.0
        for prev, cur in zip(profile, profile[1:]):
            if (cur.get("leg_km") or 0) <= 0:
                out.append(dict(cur))
                continue
            leg_target = cur["leg_km"] * factor
            mid_lat, mid_lon = road_leg_midpoint(
                prev["lat"], prev["lon"], cur["lat"], cur["lon"],
                leg_target, sign)
            sign = -sign  # чередуем сторону излома -- лёгкий зигзаг, не петля
            mid_ts = prev["ts"] + (cur["ts"] - prev["ts"]) / 2
            out.append({"ts": mid_ts, "lat": mid_lat, "lon": mid_lon,
                       "kind": None, "id": None, "leg_km": None})
            out.append(dict(cur))
        achieved = track_length_km(out)
        if achieved <= 0:
            break
        factor *= target_km / achieved
    return out


def road_target_km(norm_km: float, km_deviation_limit: Optional[float] = None,
                   overage_probability: float = 0.04,
                   noise_pct: float = 0.03,
                   rng: Optional[Any] = None) -> float:
    """Целевая дорожная длина трека для replay: норматив + реалистичный
    шум, и в редких случаях -- заведомое превышение лимита отклонения
    (см. docs/Autopark/GPS_INTEGRATION.md, "дорожный коэффициент").

    Та же пропорция (~``overage_probability``), что генератор истории
    (modules/autopark/scripts/autopark_history.py) закладывает для
    контрольных отчётов -- иначе реплеенные рейсы выглядели бы
    исключением на фоне общей статистики отклонений по пробегу.
    ``rng`` — внедряемый источник случайности (по умолчанию модуль
    ``random``), только чтобы тесты (если понадобятся) могли
    зафиксировать сид, а не потому что вызывающему коду это нужно.
    """
    import random as _random
    rng = rng or _random
    norm_km = float(norm_km or 0)
    if km_deviation_limit and rng.random() < overage_probability:
        extra = float(km_deviation_limit) * (1.0 + rng.uniform(0.1, 0.6))
        sign = rng.choice((-1.0, 1.0))
        return max(0.0, norm_km + sign * extra)
    return max(0.0, norm_km * (1.0 + rng.uniform(-noise_pct, noise_pct)))


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

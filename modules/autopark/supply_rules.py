"""Autopark — распределение топлива по АЗС: чистые правила расчёта.

Реализует ТЗ заказчика от 18.09.2026 «Автоматизация формирования
потребности, заказа и доставки топлива на АЗС» (docx —
`docs/Planograms/Bemol2/`, конспект — `docs/Autopark/SPEC_SUPPLY_2026-09-18.md`).

Файл отдельный от `rules.py` намеренно: там правила зарплаты и пробега по
первому ТЗ, здесь — контур распределения по второму. Ни одного импорта БД,
поэтому весь алгоритм проверяется без wallet и без Oracle
(`tests/test_autopark_supply.py`).

Четыре вещи, которые отличают этот расчёт от обычного автозаказа и ради
которых он написан заново, а не настройкой существующего:

1. ПОТОЛОК — НЕ ВМЕСТИМОСТЬ, А ДОПУСТИМЫЙ ЗАЛИВ (п.4.1).
   Резервуар на 20 000 л с остатком 7 200 л принимает 12 800 л, и ни
   литром больше. Плюс то, что уже едет к этой АЗС (п.5): иначе один и
   тот же объём попадёт в две заявки и вторая машина приедет к полному
   резервуару.

2. ОТСЕК СЛИВАЕТСЯ ЦЕЛИКОМ (п.4.2).
   Оставить топливо в отсеке нельзя технически. Поэтому объём поставки —
   это не «сколько нужно», а сумма выбранных отсеков: задача подбора
   подмножества, а не деления вместимости на число секций.

3. ПОТОЛОК ЗАПАСА В ДНЯХ, НО НЕ ЦЕНОЙ СРЫВА ПОСТАВКИ (п.4.2 примечание).
   Обычно на АЗС держат не больше 7 дней запаса. Но есть станции, где
   даже самый маленький отсек продаётся дольше недели — там ограничение
   в днях физически невыполнимо, и правильный ответ не «не везём», а
   «везём минимальный отсек и говорим об этом вслух». Отсюда предупреждение
   `cover_exceeded` вместо отказа, и ручной override дней на резервуар.

4. ОДНА ЦИСТЕРНА — ОДНО СЕМЕЙСТВО ТОПЛИВА (п.6).
   «Дизель и бензин в одну цистерну не грузятся». А92/А95/А98 в одном
   рейсе допустимы — это одно семейство и один терминал погрузки,
   поэтому ограничение живёт на уровне `fuel_group`, а не марки.

Разгрузка идёт с крайнего хвостового отсека (п.4.2 примечание), поэтому
первая по маршруту АЗС получает хвостовые отсеки — порядок назначения
отсеков здесь не косметика, а то, в каком виде рейс физически выполним.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

DistLookup = Callable[[str, object, str, object], Optional[float]]


def _truck_groups(truck: Dict) -> Sequence[str]:
    """Семейства топлива, которые цистерне разрешено возить.

    Поддерживаются обе формы записи: список ``fuel_groups`` и единичное
    ``fuel_group`` — вторая осталась в тестах и в коде, написанном до
    того, как выяснилось, что одна цистерна возит и бензин, и дизель
    (в разных рейсах).
    """
    groups = truck.get("fuel_groups")
    if groups:
        return list(groups)
    return [truck.get("fuel_group") or "PETROL"]

# Предупреждения строки плана — коды, а не тексты: подписи живут в UI и
# в отчётах, а сравнивать в тестах и в SQL удобнее код.
WARN_COVER_EXCEEDED = "cover_exceeded"      # запас превысит допустимые дни
WARN_NO_ROOM = "no_room"                    # свободного объёма меньше отсека
WARN_NO_SECTION = "no_section"              # свободных отсеков не осталось
WARN_PARTIAL = "partial_section"            # отсек сливается не полностью
WARN_UNDERFILL = "underfill"                # завезли меньше целевого запаса


# ── потребность одного резервуара ────────────────────────────────────

def allowed_volume_l(max_fill_l: float, current_l: float,
                     in_transit_l: float = 0.0) -> float:
    """Максимально допустимый объём поставки (ТЗ п.4.1 + п.5).

    Считается от МАКСИМАЛЬНО ДОПУСТИМОГО объёма резервуара, а не от
    паспортной вместимости: в неё заливать нельзя, и разница между этими
    двумя числами — это как раз то, из-за чего резервуар переливают.

    Топливо в пути вычитается наравне с остатком: оно физически займёт
    место к моменту приезда следующей машины.
    """
    return max(0.0, float(max_fill_l) - float(current_l) - float(in_transit_l))


def days_to_min(current_l: float, min_stock_l: float, avg_daily_l: float,
                in_transit_l: float = 0.0) -> Optional[float]:
    """Через сколько суток остаток упадёт до минимального (ТЗ п.3, п.7).

    ``None`` — когда реализации нет: делить на ноль нельзя, а «бесконечный
    запас» и «нет данных о продажах» для планировщика одно и то же —
    станция не срочная. Отрицательное значение означает, что минимум уже
    пробит, и такую АЗС планировщик обслуживает первой.
    """
    if not avg_daily_l:
        return None
    return (float(current_l) + float(in_transit_l) - float(min_stock_l)) / float(avg_daily_l)


def target_volume_l(current_l: float, min_stock_l: float, avg_daily_l: float,
                    max_cover_days: float, max_fill_l: float,
                    in_transit_l: float = 0.0) -> float:
    """Желаемый объём поставки до потолка запаса в днях (ТЗ п.4.2).

    Целевой уровень — «минимальный остаток плюс продажи за допустимое
    число дней», но не выше допустимого залива резервуара: у части АЗС
    резервуар физически не вмещает недельный запас, и тогда потолок
    задаёт железо, а не политика.

    Возвращает желаемый объём ДОБОРА (сколько привезти), а не уровень.
    """
    desired_level = float(min_stock_l) + float(avg_daily_l) * float(max_cover_days)
    desired_level = min(desired_level, float(max_fill_l))
    return max(0.0, desired_level - float(current_l) - float(in_transit_l))


def cover_days_after(current_l: float, min_stock_l: float, avg_daily_l: float,
                     delivered_l: float, in_transit_l: float = 0.0) -> Optional[float]:
    """Сколько дней запаса останется после поставки (ТЗ п.7, колонка плана)."""
    if not avg_daily_l:
        return None
    return (float(current_l) + float(in_transit_l) + float(delivered_l)
            - float(min_stock_l)) / float(avg_daily_l)


# ── подбор отсеков ────────────────────────────────────────────────────

def pick_sections(sections: Sequence[Dict], target_l: float,
                  allowed_l: float) -> Tuple[List[Dict], List[str]]:
    """Подбор отсеков под потребность одной АЗС (ТЗ п.4.2, п.6).

    ``sections`` — доступные (ещё не занятые) отсеки в порядке разгрузки,
    хвостовой первым: ``[{"id", "seq_no", "volume_l"}, ...]``.

    Правила, в порядке жёсткости:

    1. сумма выбранных отсеков НИКОГДА не превышает ``allowed_l`` — это
       перелив резервуара, физический запрет;
    2. из допустимых комбинаций берётся та, что ближе всего снизу к
       ``target_l`` — потолок запаса в днях соблюдён;
    3. если ни одна комбинация не укладывается в ``target_l``, но
       минимальный отсек проходит по ``allowed_l`` — берётся он, и
       возвращается предупреждение ``cover_exceeded``: на такой АЗС
       любой завоз превышает недельный запас, и отказ от поставки был бы
       хуже превышения (ТЗ п.4.2, примечание про мелкие станции);
    4. если и минимальный отсек не влезает — поставки нет, предупреждение
       ``no_room``.

    Полный перебор подмножеств: у бензовоза 4-6 отсеков, 2^6 = 64
    варианта — точный ответ дешевле любой эвристики.
    """
    warnings: List[str] = []
    usable = [s for s in sections if float(s["volume_l"]) > 0]
    if not usable:
        return [], [WARN_NO_SECTION]
    if allowed_l <= 0:
        return [], [WARN_NO_ROOM]

    n = len(usable)
    best_subset: List[Dict] = []
    best_sum = 0.0
    fallback_subset: List[Dict] = []
    fallback_sum: Optional[float] = None

    for mask in range(1, 1 << n):
        subset = [usable[i] for i in range(n) if mask & (1 << i)]
        total = sum(float(s["volume_l"]) for s in subset)
        if total > allowed_l + 1e-6:
            continue                      # перелив — вариант недопустим
        if total <= target_l + 1e-6:
            # Ближе к цели снизу; при равном объёме предпочитаем набор из
            # отсеков, что ближе к хвосту (меньшие индексы) — их всё равно
            # разгружать первыми.
            if total > best_sum + 1e-9:
                best_sum, best_subset = total, subset
        elif fallback_sum is None or total < fallback_sum:
            fallback_sum, fallback_subset = total, subset

    if best_subset:
        return best_subset, warnings
    if fallback_subset:
        # Ни один отсек не укладывается в потолок запаса — но станция
        # нуждается, и оставить её без поставки нельзя.
        return fallback_subset, [WARN_COVER_EXCEEDED]
    return [], [WARN_NO_ROOM]


# ── маршрут ──────────────────────────────────────────────────────────

def route_order(load_point, station_ids: Sequence, dist_lookup: DistLookup) -> List:
    """Порядок объезда АЗС методом ближайшего соседа от пункта погрузки.

    Эвристика, а не оптимум (это задача коммивояжёра). АЗС, для которой
    расстояние не заведено в матрице, не выбрасывается из рейса, а
    дописывается в конец: поставку всё равно нужно выполнить, а дыра в
    справочнике — повод показать предупреждение, а не потерять станцию.
    """
    remaining = list(station_ids)
    order: List = []
    kind, point = "LOAD", load_point
    while remaining:
        best_i, best_km = None, None
        for i, sid in enumerate(remaining):
            km = dist_lookup(kind, point, "STATION", sid)
            if km is None:
                continue
            if best_km is None or km < best_km:
                best_i, best_km = i, km
        if best_i is None:
            best_i = 0
        chosen = remaining.pop(best_i)
        order.append(chosen)
        kind, point = "STATION", chosen
    return order


def route_km(start_point, load_point, stations_seq: Sequence, end_point,
             dist_lookup: DistLookup) -> Tuple[Optional[float], List[Dict]]:
    """Нормативный пробег рейса целиком (ТЗ автопарка, «Расчёт нормативного пробега»).

    Цепочка: стоянка → пункт загрузки → АЗС₁ → … → АЗСₙ → стоянка.
    Первый участок (стоянка → пункт загрузки) в первой версии модуля
    отсутствовал, и норматив — а с ним и зарплата — занижался на дорогу
    от стоянки до терминала.

    Возвращает ``(км, участки)``. Если хотя бы один участок не заведён в
    матрице, км = ``None``: подставлять ноль вместо неизвестного
    расстояния значит молча недоплатить водителю.
    """
    stops: List[Tuple[str, object]] = []
    if start_point is not None:
        stops.append(("END", start_point))
    stops.append(("LOAD", load_point))
    stops.extend(("STATION", s) for s in stations_seq)
    if end_point is not None:
        stops.append(("END", end_point))

    legs: List[Dict] = []
    total = 0.0
    complete = True
    for (fk, fi), (tk, ti) in zip(stops, stops[1:]):
        km = dist_lookup(fk, fi, tk, ti)
        legs.append({"from_kind": fk, "from_id": fi,
                     "to_kind": tk, "to_id": ti, "km": km})
        if km is None:
            complete = False
        else:
            total += float(km)
    return (total if complete else None), legs


# ── сборка плана ─────────────────────────────────────────────────────

def build_needs(tanks: Sequence[Dict], default_cover_days: float,
                horizon_days: float = 0.0) -> List[Dict]:
    """Строки потребности по резервуарам (ТЗ п.3, п.7).

    ``tanks`` — состояние резервуаров (``V_FLT_TANK_STATE``):
    ``{"tank_id", "station_id", "product_code", "fuel_group", "current_l",
    "avg_daily_l", "min_stock_l", "max_fill_l", "max_cover_days",
    "in_transit_l"}``.

    ``horizon_days`` — на сколько суток вперёд смотрим: резервуар попадает
    в план, если минимальный остаток будет пробит в пределах горизонта.
    Ноль означает «только те, что уже ниже минимума».

    Возвращает ВСЕ резервуары, которым нужна поставка, отсортированные по
    срочности. Резервуар, где ехать некуда (нет свободного объёма),
    остаётся в списке с предупреждением: логист должен видеть, что
    станция голодает и почему поставка невозможна, а не гадать, куда она
    пропала из плана.
    """
    needs: List[Dict] = []
    for t in tanks:
        avg_daily = float(t.get("avg_daily_l") or 0)
        current = float(t.get("current_l") or 0)
        in_transit = float(t.get("in_transit_l") or 0)
        min_stock = float(t.get("min_stock_l") or 0)
        max_fill = float(t.get("max_fill_l") or 0)
        cover_days = t.get("max_cover_days")
        cover_days = float(cover_days) if cover_days not in (None, "") else float(default_cover_days)

        left = days_to_min(current, min_stock, avg_daily, in_transit)
        if left is not None and left > horizon_days:
            continue
        if left is None and current + in_transit >= min_stock:
            # Продаж нет и минимум не пробит — поставка не нужна.
            continue

        allowed = allowed_volume_l(max_fill, current, in_transit)
        target = target_volume_l(current, min_stock, avg_daily, cover_days,
                                 max_fill, in_transit)
        needs.append({
            "tank_id": t.get("tank_id"),
            "station_id": t.get("station_id"),
            "product_code": t.get("product_code"),
            "fuel_group": t.get("fuel_group") or "PETROL",
            "current_l": current,
            "avg_daily_l": avg_daily,
            "min_stock_l": min_stock,
            "max_fill_l": max_fill,
            "in_transit_l": in_transit,
            "max_cover_days": cover_days,
            "days_to_min": left,
            "allowed_l": allowed,
            "target_l": min(target, allowed),
            "planned_l": 0.0,
            "warnings": [] if allowed > 0 else [WARN_NO_ROOM],
        })

    needs.sort(key=lambda n: (n["days_to_min"] if n["days_to_min"] is not None
                              else float("inf")))
    return needs


def _assign_truck(truck: Dict, group_needs: List[Dict], load_point,
                  dist_lookup: DistLookup, max_stations: int) -> Optional[Dict]:
    """Набивает один бензовоз под потребности одной группы АЗС.

    Отсеки назначаются в порядке разгрузки — с хвостового (ТЗ п.4.2), то
    есть первая по маршруту АЗС получает хвост цистерны. Поэтому сначала
    определяется порядок объезда, и только потом отсеки раздаются
    станциям по этому порядку.
    """
    sections = sorted((s for s in truck.get("sections", [])
                       if float(s.get("volume_l") or 0) > 0),
                      key=lambda s: -int(s["seq_no"]))          # хвост первым
    if not sections:
        return None

    pending = [n for n in group_needs
               if n["allowed_l"] > 0 and n["target_l"] + n["planned_l"] >= 0
               and n["planned_l"] < n["allowed_l"]]
    if not pending:
        return None

    # Кого вообще берём в рейс: самые срочные, но не больше допустимого
    # числа АЗС в одном рейсе (ТЗ п.6 — обычно от 2 до 4).
    chosen_stations: List = []
    for n in pending:
        if n["station_id"] in chosen_stations:
            continue
        if len(chosen_stations) >= max_stations:
            break
        chosen_stations.append(n["station_id"])
    if not chosen_stations:
        return None

    order = route_order(load_point, chosen_stations, dist_lookup)

    free_sections = list(sections)
    loads: List[Dict] = []
    unload_seq = 0
    for station_id in order:
        used_at_station: List[Dict] = []
        for need in [n for n in pending if n["station_id"] == station_id]:
            if not free_sections:
                break
            remaining_allowed = need["allowed_l"] - need["planned_l"]
            remaining_target = max(0.0, need["target_l"] - need["planned_l"])
            if remaining_allowed <= 0:
                continue
            picked, warns = pick_sections(free_sections, remaining_target,
                                          remaining_allowed)
            # Предупреждения «нет места» и «нет отсека» относятся к
            # потребности ЦЕЛИКОМ, а не к очередной попытке добрать.
            # Первая версия вешала no_room на строку, куда уже
            # запланировали 6 250 л: в плане это читалось как «поставки
            # нет», хотя машина едет. Пока по строке ничего не
            # запланировано — предупреждение честное, дальше это просто
            # недовоз, неизбежный при сливе отсеками целиком.
            if need["planned_l"] <= 0:
                for w in warns:
                    if w not in need["warnings"]:
                        need["warnings"].append(w)
            if not picked:
                continue
            for sec in picked:
                unload_seq += 1
                loads.append({
                    "section_id": sec["id"],
                    "section_no": sec["seq_no"],
                    "station_id": station_id,
                    "product_code": need["product_code"],
                    "volume_l": float(sec["volume_l"]),
                    "unload_seq": unload_seq,
                    "need": need,
                })
                need["planned_l"] += float(sec["volume_l"])
            used_at_station.extend(picked)
            picked_ids = {s["id"] for s in picked}
            free_sections = [s for s in free_sections if s["id"] not in picked_ids]

        # Физика слива: отсеки опорожняются от хвоста к кабине, поэтому
        # следующей АЗС достаются только отсеки ПЕРЕД теми, что уже
        # отданы этой. Пропустить отсек можно (он поедет пустым), а
        # вернуться к нему после переднего — нельзя. Без этого среза
        # план выглядел бы исполнимым на бумаге, а на площадке водителю
        # пришлось бы сливать средний отсек раньше хвостового.
        if used_at_station:
            frontmost = min(int(s["seq_no"]) for s in used_at_station)
            free_sections = [s for s in free_sections
                             if int(s["seq_no"]) < frontmost]

    if not loads:
        return None

    visited = list(dict.fromkeys(l["station_id"] for l in loads))
    est_km = 0.0
    kind, point = "LOAD", load_point
    for sid in visited:
        km = dist_lookup(kind, point, "STATION", sid)
        est_km += float(km or 0)
        kind, point = "STATION", sid

    return {
        "truck_id": truck.get("id"),
        "plate": truck.get("plate"),
        "fuel_group": truck.get("fuel_group"),
        "load_point_id": load_point,
        "stations": visited,
        "loads": loads,
        "volume_l": sum(l["volume_l"] for l in loads),
        "est_km": est_km,
        "sections_used": len(loads),
        "sections_total": len(sections),
    }


def build_plan(tanks: Sequence[Dict], trucks: Sequence[Dict],
               groups: Sequence[Dict], settings: Dict,
               dist_lookup: DistLookup, load_point_by_group: Dict = None) -> Dict:
    """Полный план распределения топлива (ТЗ п.3 — п.7).

    ``groups`` — географические группы АЗС: ``{"id", "code", "name",
    "station_ids": [...], "load_point_id": <опционально>}``. Станции вне
    групп обслуживаются собственными одиночными рейсами — молча выпасть
    из плана они не могут.

    ``trucks`` — бензовозы с реальными отсеками: ``{"id", "plate",
    "fuel_group", "sections": [{"id", "seq_no", "volume_l"}]}``.
    ``fuel_group`` жёстко разделяет парк: бензиновая цистерна не получит
    дизельную потребность (ТЗ п.6).

    Возвращает ``{"needs": [...], "trips": [...]}`` — плоские списки,
    готовые к записи в ``FLT_SUPPLY_NEEDS`` / ``FLT_SUPPLY_TRIPS`` /
    ``FLT_SUPPLY_LOADS``, без единого обращения к БД.
    """
    cover_days = float(settings.get("max_cover_days") or 7)
    horizon = float(settings.get("plan_horizon_days") or 0)
    max_stations = int(settings.get("group_max_stations") or 4)
    default_load_point = settings.get("load_point_id")
    load_point_by_group = load_point_by_group or {}

    needs = build_needs(tanks, cover_days, horizon)

    # Станция → группа. Одна станция может входить в несколько групп
    # (бензиновый круг и дизельный) — берём первую подходящую по семейству.
    group_of: Dict[object, Dict] = {}
    for g in groups:
        for sid in g.get("station_ids", []):
            group_of.setdefault(sid, g)

    trips: List[Dict] = []
    used_trucks: set = set()
    for fuel_group in ("PETROL", "DIESEL"):
        family_needs = [n for n in needs if n["fuel_group"] == fuel_group]
        if not family_needs:
            continue
        # Цистерна годится, если ей разрешено это семейство. Одна цистерна
        # обслуживает один рейс за расчёт: в двух местах одновременно она
        # не бывает, и план, где она бензин и дизель везёт одним заездом,
        # нарушал бы п.6.
        family_trucks = [t for t in trucks
                         if t["id"] not in used_trucks
                         and fuel_group in _truck_groups(t)]
        if not family_trucks:
            continue

        # Раскладываем потребности по группам: своя группа, либо
        # одиночная псевдогруппа на станцию.
        buckets: Dict[object, List[Dict]] = {}
        bucket_meta: Dict[object, Dict] = {}
        for need in family_needs:
            g = group_of.get(need["station_id"])
            key = ("G", g["id"]) if g else ("S", need["station_id"])
            buckets.setdefault(key, []).append(need)
            bucket_meta.setdefault(key, g or {"id": None, "code": None,
                                              "name": None})

        # Срочные группы первыми — бензовозов всегда меньше, чем желающих.
        ordered_keys = sorted(
            buckets,
            key=lambda k: min((n["days_to_min"] if n["days_to_min"] is not None
                               else float("inf")) for n in buckets[k]))

        available = list(family_trucks)
        for key in ordered_keys:
            if not available:
                break
            group_needs = buckets[key]
            meta = bucket_meta[key]
            load_point = (load_point_by_group.get(meta.get("id"))
                          or meta.get("load_point_id") or default_load_point)
            if load_point is None:
                continue
            while available:
                truck = available[0]
                trip = _assign_truck(truck, group_needs, load_point,
                                     dist_lookup, max_stations)
                if trip is None:
                    break
                available.pop(0)
                used_trucks.add(truck["id"])
                trip["fuel_group"] = fuel_group
                trip["group_id"] = meta.get("id")
                trip["group_name"] = meta.get("name")
                trip["seq_no"] = len(trips) + 1
                trips.append(trip)
                if all(n["planned_l"] >= n["target_l"] - 1e-6
                       for n in group_needs):
                    break

    # Итоговые поля строки плана: покрытие после поставки и признак
    # «запланировано меньше, чем нужно».
    for n in needs:
        n["cover_days_after"] = cover_days_after(
            n["current_l"], n["min_stock_l"], n["avg_daily_l"],
            n["planned_l"], n["in_transit_l"])
        if n["planned_l"] <= 0:
            if not n["warnings"]:
                n["warnings"].append(WARN_NO_SECTION)
        elif n["planned_l"] < n["target_l"] - 1e-6:
            if WARN_UNDERFILL not in n["warnings"]:
                n["warnings"].append(WARN_UNDERFILL)

    return {"needs": needs, "trips": trips}


# ── проверка ручной правки (ТЗ п.7) ──────────────────────────────────

def validate_loads(loads: Sequence[Dict], tank_state: Dict,
                   sections: Dict) -> List[Dict]:
    """Перепроверка плана после ручного изменения (ТЗ п.7).

    ТЗ требует ровно двух проверок — перелив резервуара и физическая
    возможность распределить объём по отсекам. Обе жёсткие: ошибка
    запрещает сохранение, предупреждение только подсвечивается.

    ``tank_state`` — ``{(station_id, product_code): {"allowed_l", ...}}``;
    ``sections`` — ``{section_id: {"volume_l", "truck_id"}}``.
    """
    problems: List[Dict] = []
    by_tank: Dict[Tuple, float] = {}
    seen_sections: Dict[object, int] = {}

    for idx, load in enumerate(loads):
        key = (load.get("station_id"), load.get("product_code"))
        volume = float(load.get("volume_l") or 0)
        by_tank[key] = by_tank.get(key, 0.0) + volume

        section = sections.get(load.get("section_id"))
        if section is None:
            problems.append({"level": "error", "row": idx,
                             "code": "unknown_section",
                             "message": "Отсек не найден в справочнике цистерны"})
            continue
        seen_sections[load["section_id"]] = seen_sections.get(load["section_id"], 0) + 1
        section_volume = float(section.get("volume_l") or 0)
        if volume > section_volume + 1e-6:
            problems.append({
                "level": "error", "row": idx, "code": "over_section",
                "message": f"В отсек №{section.get('seq_no', '?')} нельзя залить "
                           f"{volume:.0f} л: его объём {section_volume:.0f} л"})
        elif volume < section_volume - 1e-6:
            problems.append({
                "level": "warning", "row": idx, "code": WARN_PARTIAL,
                "message": f"Отсек №{section.get('seq_no', '?')} сливается не "
                           f"полностью ({volume:.0f} из {section_volume:.0f} л)"})

    for section_id, count in seen_sections.items():
        if count > 1:
            problems.append({"level": "error", "row": None,
                             "code": "section_reused",
                             "message": f"Отсек {section_id} назначен {count} раза "
                                        "— один отсек обслуживает одну выдачу"})

    for (station_id, product_code), volume in by_tank.items():
        state = tank_state.get((station_id, product_code))
        if state is None:
            problems.append({"level": "error", "row": None, "code": "unknown_tank",
                             "message": f"Резервуар {product_code} на АЗС "
                                        f"{station_id} не найден"})
            continue
        allowed = float(state.get("allowed_l") or 0)
        if volume > allowed + 1e-6:
            problems.append({
                "level": "error", "row": None, "code": "overfill",
                "message": f"Перелив резервуара {product_code} на АЗС "
                           f"{station_id}: {volume:.0f} л при допустимых "
                           f"{allowed:.0f} л"})

    fuel_groups = {load.get("fuel_group") for load in loads
                   if load.get("fuel_group")}
    if len(fuel_groups) > 1:
        problems.append({"level": "error", "row": None, "code": "mixed_fuel",
                         "message": "Бензин и дизель в одной цистерне "
                                    "не перевозятся"})
    return problems


# ── экономика перевозки (ТЗ автопарка, «Отчёт для руководства») ───────

def transport_economics(trips: Sequence[Dict], rate_per_km: float,
                        fuel_price_lei: float,
                        km_limit: float = 0.0) -> Dict:
    """Экономика перевозки за период: во что обошёлся литр и где потери.

    ``trips`` — рейсы периода:
    ``{"norm_km", "fact_km", "norm_fuel_l", "fact_fuel_l", "volume_l",
    "capacity_l", "pay"}``.

    Что здесь считается и, главное, чего НЕ считается:

    * **Стоимость перевозки литра** — только зарплатная часть плюс
      стоимость перерасходованного дизеля. Амортизация, ремонт, страховка
      и зарплата диспетчера в модуле не учитываются: у него нет таких
      данных, и подмешивать в цифру оценку «на глаз» хуже, чем показать
      честную неполную.
    * **Экономический эффект от оптимизации маршрутов** — это не
      «сэкономленные деньги», а СТОИМОСТЬ ЛИШНЕГО: сверхнормативный
      пробег по ставке водителя плюс перерасход топлива по его цене.
      Именно эта сумма перестанет тратиться, если убрать отклонения,
      поэтому она и есть верхняя граница эффекта. Выдавать её за уже
      полученную экономию нельзя.
    * **Средняя загрузка** — перевезённый объём к суммарной вместимости
      задействованных цистерн. Ниже 100 % это норма, а не потеря: отсек
      сливается целиком, и подогнать загрузку под потолок физически
      невозможно.
    """
    norm_km = sum(float(t.get("norm_km") or 0) for t in trips)
    fact_km = sum(float(t.get("fact_km") or 0) for t in trips)
    volume = sum(float(t.get("volume_l") or 0) for t in trips)
    capacity = sum(float(t.get("capacity_l") or 0) for t in trips)
    pay = sum(float(t.get("pay") or 0) for t in trips)

    norm_fuel = sum(float(t.get("norm_fuel_l") or 0) for t in trips)
    measured = [t for t in trips if t.get("fact_fuel_l") is not None]
    fact_fuel = sum(float(t["fact_fuel_l"]) for t in measured)

    # Перерасход и перепробег считаются ПОРЕЙСОВО, а не по итогам периода.
    # На сумме рейс, проехавший меньше норматива, гасит тот, что проехал
    # больше, и отчёт показывает ноль лишнего пробега при двух рейсах с
    # отклонениями — ровно это и было на первом прогоне по живым данным.
    fuel_over_l = sum(max(0.0, float(t["fact_fuel_l"]) - float(t.get("norm_fuel_l") or 0))
                      for t in measured)
    extra_km = sum(max(0.0, float(t["fact_km"]) - float(t.get("norm_km") or 0))
                   for t in trips if t.get("fact_km") is not None)
    over_limit_trips = sum(
        1 for t in trips
        if t.get("fact_km") is not None
        and abs(float(t["fact_km"]) - float(t.get("norm_km") or 0)) > km_limit)

    extra_km_cost = extra_km * float(rate_per_km or 0)
    fuel_over_cost = fuel_over_l * float(fuel_price_lei or 0)

    return {
        "trips": len(trips),
        "norm_km": round(norm_km, 1),
        "fact_km": round(fact_km, 1),
        "extra_km": round(extra_km, 1),
        "volume_l": round(volume, 1),
        "avg_load_pct": round(100.0 * volume / capacity, 1) if capacity else None,
        "pay_total": round(pay, 2),
        "fuel_norm_l": round(norm_fuel, 1),
        "fuel_fact_l": round(fact_fuel, 1),
        "fuel_over_l": round(fuel_over_l, 1),
        "cost_per_liter": round((pay + fuel_over_cost) / volume, 4) if volume else None,
        "extra_km_cost": round(extra_km_cost, 2),
        "fuel_over_cost": round(fuel_over_cost, 2),
        "optimization_effect": round(extra_km_cost + fuel_over_cost, 2),
        "deviation_trips": over_limit_trips,
    }


def driver_rating(drivers: Sequence[Dict]) -> List[Dict]:
    """Рейтинг водителей по соблюдению маршрута (ТЗ, «Сводный отчёт»).

    Метрика — перепробег в процентах к нормативу, а не в километрах:
    иначе водитель дальних импортных рейсов всегда хуже того, кто возит
    по городу. Водитель без фактического пробега в рейтинг не попадает —
    сравнивать его не с чем.
    """
    rated = []
    for d in drivers:
        norm = float(d.get("total_norm_km") or 0)
        fact = float(d.get("total_fact_km") or 0)
        if norm <= 0 or fact <= 0:
            continue
        rated.append({
            "driver_id": d.get("driver_id"),
            "full_name": d.get("full_name"),
            "norm_km": round(norm, 1),
            "fact_km": round(fact, 1),
            "extra_km": round(fact - norm, 1),
            "extra_pct": round((fact - norm) / norm * 100, 2),
            "domestic_cnt": d.get("domestic_cnt"),
            "import_cnt": d.get("import_cnt"),
            "pay": d.get("total_pay"),
        })
    rated.sort(key=lambda r: r["extra_pct"])
    for i, row in enumerate(rated, 1):
        row["rank"] = i
    return rated

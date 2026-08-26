"""Autopark — чистые бизнес-правила (модуль Bemol: автопарк бензовозов).

Ни одного импорта БД: все функции работают с простыми dict/list, которые
им передаёт вызывающий код (store.py/controller.py в следующей задаче).
Это позволяет тестировать расчёт зарплаты, контроль пробега и планирование
поставок без wallet и без Oracle — см. tests/test_autopark.py.

Формулы соответствуют ТЗ клиента (docs/Autopark/SPEC_AUTOPARK.md либо
исходный файл ТЗ):

    п.8  — нормативный пробег = сумма участков маршрута;
    п.9  — отклонение = фактический пробег − нормативный пробег;
    п.10 — зарплата = (нормативный пробег × 2.75) + (внутренние рейсы × 600),
           импортные рейсы бонус не получают;
    п.12 — нормативный расход = нормативный пробег × норма / 100;
    п.7  — минимальный запас = среднесуточная реализация × 6 дней,
           запас в днях = текущий остаток / среднесуточная реализация.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

DistLookup = Callable[[str, object, str, object], Optional[float]]


# -- Нормативный пробег и маршрут --------------------------------------

def norm_route_km(legs: Sequence[Optional[float]]) -> float:
    """Сумма участков маршрута (ТЗ п.8).

    ``legs`` — список расстояний в км по каждому участку, в порядке
    следования маршрута. Если хотя бы один участок не найден в матрице
    расстояний (None), пробег посчитать нельзя — это ошибка данных, а не
    нулевой километраж, поэтому функция поднимает ValueError, а не
    подставляет 0.
    """
    for i, km in enumerate(legs):
        if km is None:
            raise ValueError(
                f"расстояние не заведено в матрице для участка #{i + 1} "
                "маршрута — норматив посчитать нельзя")
    return sum(legs)


def route_legs(
    load_point,
    stations_seq: Sequence,
    end_point,
    dist_lookup: DistLookup,
) -> List[Dict]:
    """Строит участки маршрута: пункт загрузки → АЗС1 → АЗС2 → … → конечный пункт.

    ``stations_seq`` — идентификаторы АЗС в порядке фактического
    обслуживания (ТЗ п.5: маршрут хранится в последовательности
    обслуживания, а не в произвольном порядке).

    ``dist_lookup(from_kind, from_id, to_kind, to_id) -> km|None`` —
    функция поиска расстояния в матрице (обычно тонкая обёртка над
    FLT_DISTANCES). Возвращает список участков вида
    ``{"from_kind", "from_id", "to_kind", "to_id", "km"}`` — километраж
    может быть ``None``, если участок не заведён; сложить их в норматив
    берётся на себя :func:`norm_route_km`, здесь мы только собираем сами
    участки.
    """
    stops = [("LOAD", load_point)] + [("STATION", s) for s in stations_seq] + \
        [("END", end_point)]
    legs = []
    for (from_kind, from_id), (to_kind, to_id) in zip(stops, stops[1:]):
        km = dist_lookup(from_kind, from_id, to_kind, to_id)
        legs.append({
            "from_kind": from_kind, "from_id": from_id,
            "to_kind": to_kind, "to_id": to_id,
            "km": km,
        })
    return legs


# -- Зарплата водителя --------------------------------------------------

def trip_pay(norm_km: float, trip_type: str, rate_per_km: float,
             trip_bonus: float) -> float:
    """Оплата одного рейса (ТЗ п.10).

    Оплата за километраж начисляется всегда. Доплата 600 леев за рейс —
    только для внутреннего рейса (``trip_type == "DOMESTIC"``); импортные
    рейсы (в том числе Кишинёв–Констанца–Кишинёв) доплату не получают —
    это прямое исключение из ТЗ, а не побочный эффект округления.
    """
    pay = norm_km * rate_per_km
    if trip_type == "DOMESTIC":
        pay += trip_bonus
    return pay


def payroll(trips: Sequence[Dict], rate: float, bonus: float) -> Dict:
    """Свод зарплаты по водителю за период (ТЗ п.6, п.10, п.11).

    ``trips`` — рейсы одного водителя за период, каждый в виде
    ``{"status": "DRAFT"|"APPROVED"|"DONE", "type": "DOMESTIC"|"IMPORT",
    "norm_km": float}``.

    DRAFT-рейсы в расчёт НЕ включаются: основанием для зарплаты становится
    только утверждённый логистом рейс (ТЗ п.6) — черновик мог ещё
    измениться и посчитать его было бы преждевременно.
    """
    counted = [t for t in trips if t.get("status") != "DRAFT"]
    domestic = [t for t in counted if t.get("type") == "DOMESTIC"]
    import_trips = [t for t in counted if t.get("type") == "IMPORT"]

    total_norm_km = sum(t.get("norm_km") or 0 for t in counted)
    km_pay = total_norm_km * rate
    trip_pay_sum = len(domestic) * bonus

    return {
        "domestic_count": len(domestic),
        "import_count": len(import_trips),
        "total_norm_km": total_norm_km,
        "km_pay": km_pay,
        "trip_pay": trip_pay_sum,
        "total": km_pay + trip_pay_sum,
    }


# -- Расход топлива и контроль пробега ----------------------------------

def fuel_norm_l(norm_km: float, norm_per_100km: float) -> float:
    """Нормативный расход ДТ на рейс (ТЗ п.12)."""
    return norm_km * norm_per_100km / 100


def fuel_deviation(fact_l: float, norm_l: float,
                    limit_pct: float) -> Tuple[float, bool]:
    """Отклонение фактического расхода топлива от нормы (ТЗ п.12).

    При ``norm_l == 0`` процент отклонения не определён (деление на 0);
    отклонением в этом случае считается сам фактический расход, а
    превышением — любой положительный факт при нулевой норме.
    """
    deviation = fact_l - norm_l
    if norm_l == 0:
        return deviation, fact_l > 0
    pct = abs(deviation) / norm_l * 100
    return deviation, pct > limit_pct


def km_deviation(fact_km: float, norm_km: float,
                 limit_km: float) -> Tuple[float, bool]:
    """Отклонение фактического пробега от норматива (ТЗ п.9)."""
    deviation = fact_km - norm_km
    return deviation, abs(deviation) > limit_km


# -- Планирование поставок на АЗС ---------------------------------------

def stock_days(current_l: float, avg_daily_sales_l: float) -> Optional[float]:
    """Запас в днях реализации (ТЗ п.7). None при нулевой/неизвестной реализации."""
    if not avg_daily_sales_l:
        return None
    return current_l / avg_daily_sales_l


def min_stock_l(avg_daily_sales_l: float, safety_days: float) -> float:
    """Минимальный страховой запас (ТЗ п.7): среднесуточная реализация × дни."""
    return avg_daily_sales_l * safety_days


def need_volume_l(current_l: float, min_stock_l: float,
                   forecast_sales_l: float, in_transit_l: float,
                   tank_capacity_l: float) -> float:
    """Объём поставки, который нужно заказать (ТЗ п.7).

    Потребность = сколько не хватает, чтобы после прогнозируемой
    реализации до следующей поставки остаток не опустился ниже
    минимального страхового запаса, за вычетом того, что уже в пути::

        need = max(0, min_stock_l + forecast_sales_l - current_l - in_transit_l)

    Заказать больше свободного места в резервуаре нельзя, поэтому итог
    ограничен сверху свободной вместимостью (вместимость минус то, что уже
    есть и что уже везётся)::

        free_space = max(0, tank_capacity_l - current_l - in_transit_l)
        result = min(need, free_space)
    """
    need = max(0.0, min_stock_l + forecast_sales_l - current_l - in_transit_l)
    free_space = max(0.0, tank_capacity_l - current_l - in_transit_l)
    return min(need, free_space)


def classify_trip(load_point_is_foreign: bool,
                   end_point_is_foreign: bool = False) -> str:
    """Тип рейса по географии пунктов маршрута (ТЗ п.10).

    Если пункт загрузки или конечный пункт находится за рубежом (например
    Констанца) — рейс импортный, иначе внутренний. Кишинёв–Констанца–
    Кишинёв — импорт именно по этому правилу, а не по признаку самой АЗС.
    """
    return "IMPORT" if (load_point_is_foreign or end_point_is_foreign) else "DOMESTIC"


def _nearest_neighbor_order(load_point, station_ids: Sequence,
                             dist_lookup: DistLookup) -> List:
    """Порядок обхода АЗС жадным методом ближайшего соседа.

    Эвристика: на каждом шаге едем в ближайшую из ещё не посещённых АЗС от
    текущей точки. Не гарантирует глобальный минимум пробега (это была бы
    задача коммивояжёра), но даёт разумный порядок без переборных
    вычислений. Если расстояние до какой-то АЗС не найдено в матрице ни
    от одной уже посещённой точки, она добавляется в конец в порядке
    поступления — молча пропустить АЗС нельзя, поставку всё равно нужно
    выполнить.
    """
    remaining = list(station_ids)
    order = []
    current_kind, current_id = "LOAD", load_point
    while remaining:
        best_idx = None
        best_km = None
        for idx, sid in enumerate(remaining):
            km = dist_lookup(current_kind, current_id, "STATION", sid)
            if km is None:
                continue
            if best_km is None or km < best_km:
                best_km = km
                best_idx = idx
        if best_idx is None:
            # Ни для одной оставшейся АЗС расстояние не заведено — берём
            # первую по порядку поступления, чтобы не потерять её из плана.
            best_idx = 0
        chosen = remaining.pop(best_idx)
        order.append(chosen)
        current_kind, current_id = "STATION", chosen
    return order


def plan_trips(needs: Sequence[Dict], trucks: Sequence[Dict],
               dist_lookup: DistLookup, load_point) -> List[Dict]:
    """Жадное планирование рейсов под рассчитанную потребность АЗС (ТЗ п.7).

    Это эвристика, а не оптимум: планирование рейсов с ограничениями по
    вместимости, секциям и минимизацией пробега — NP-трудная задача
    объединённой упаковки и маршрутизации (bin packing + VRP). Функция
    жадно набивает бензовозы по срочности потребности и обходит АЗС
    ближайшим соседом — этого достаточно для первой очереди автоматизации,
    но не заменяет полноценный оптимизатор маршрутов.

    ``needs`` — список потребностей, каждая
    ``{"station_id", "product_code", "need_l", "days_left"}``.
    Сортируются по возрастанию ``days_left`` — наиболее срочные
    обслуживаются первыми доступными бензовозами.

    ``trucks`` — список бензовозов в порядке использования, каждый
    ``{"id", "capacity_l", "sections_cnt", "products": [...] (опционально)}``.
    Одна секция вмещает один продукт одной АЗС; объём секции =
    ``capacity_l / sections_cnt``. Объём в секцию берётся как
    ``min(потребность, свободный объём секции)`` — секции не округляются
    вверх, недогруз в последней секции — нормальное поведение.

    Возвращает список предложений рейсов:
    ``{"truck": <id бензовоза>, "stops": [{"station_id", "items": [{"product", "volume"}]}],
    "est_km": <оценка пробега>}``.
    """
    remaining = [dict(n) for n in needs]
    remaining.sort(key=lambda n: n.get("days_left") if n.get("days_left") is not None
                   else float("inf"))

    trips = []
    for truck in trucks:
        capacity = truck["capacity_l"]
        sections = truck.get("sections_cnt", 1) or 1
        section_cap = capacity / sections
        allowed = truck.get("products")

        loaded = []
        sections_used = 0
        for need in remaining:
            if sections_used >= sections:
                break
            if need.get("need_l", 0) <= 0:
                continue
            if allowed is not None and need["product_code"] not in allowed:
                continue
            volume = min(need["need_l"], section_cap)
            if volume <= 0:
                continue
            loaded.append({
                "station_id": need["station_id"],
                "product": need["product_code"],
                "volume": volume,
            })
            need["need_l"] -= volume
            sections_used += 1

        if not loaded:
            continue

        station_ids = list(dict.fromkeys(item["station_id"] for item in loaded))
        visiting_order = _nearest_neighbor_order(load_point, station_ids, dist_lookup)

        stops = []
        est_km = 0.0
        current_kind, current_id = "LOAD", load_point
        for station_id in visiting_order:
            km = dist_lookup(current_kind, current_id, "STATION", station_id)
            if km is None:
                raise ValueError(
                    f"расстояние не заведено в матрице: "
                    f"{current_kind}:{current_id} -> STATION:{station_id}")
            est_km += km
            items = [it for it in loaded if it["station_id"] == station_id]
            stops.append({
                "station_id": station_id,
                "items": [{"product": it["product"], "volume": it["volume"]}
                          for it in items],
            })
            current_kind, current_id = "STATION", station_id

        trips.append({"truck": truck.get("id"), "stops": stops, "est_km": est_km})

    return trips

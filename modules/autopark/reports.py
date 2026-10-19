"""Autopark — пакет отчётности (ТЗ Bemol §14) поверх store/controller.

Шесть отчётов, единый контракт результата:

    {"title": str, "period": str,
     "columns": [str, ...],
     "rows": [[...], ...],        # каждая строка ровно len(columns)
     "totals": [...] | [],        # строка итогов той же ширины или пусто
     "notes": [str, ...]}         # допущения/пояснения (может быть пуст)

Слой не открывает соединений и не знает SQL: все данные приходят из
AutoparkStore/AutoparkController — теми же методами, которыми пользуется
UI. Ошибку нижнего слоя отчёт не глотает и не маскирует пустой таблицей:
поднимается AutoparkReportError, чтобы выгрузка (xlsx/pdf/бот) явно
упала, а не отдала руководству пустой отчёт как «нет данных».

Зафиксированные допущения (проверяются тестами и повторены в notes):
  * «экономический эффект» (§14, отчёт руководству) — оценка
    (факт. пробег − норм. пробег) × ставка за км (2.75): положительное
    значение — переплаченные леи за необоснованный пробег, отрицательное
    — экономия против норматива. Стоимость топлива в оценку не входит.
  * «стоимость перевозки 1 л» — только зарплатная часть (как в
    management_report контроллера), закупочной цены топлива у модуля нет.
  * ценовой отчёт: «влияние на стоимость нормативного расхода ДТ» =
    Σ по рейсам (норм. км × норма л/100км автомобиля / 100 × цена DIESEL
    на дату рейса, forward-fill от последнего решения ANRE).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from modules.autopark.store import AutoparkStore

Report = Dict[str, Any]


class AutoparkReportError(Exception):
    """Нижний слой не отдал данные — отчёт строить не из чего."""


def _get(res: Dict[str, Any], label: str) -> Any:
    if not res.get("success"):
        raise AutoparkReportError(f"{label}: {res.get('message')}")
    return res.get("data")


def _period(date_from: date, date_to: date) -> str:
    return f"{date_from.isoformat()} — {date_to.isoformat()}"


def _num(value: Any, digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _report(title: str, date_from: date, date_to: date, columns: List[str],
            rows: List[List[Any]], totals: List[Any],
            notes: Optional[List[str]] = None) -> Report:
    return {"title": title, "period": _period(date_from, date_to),
            "columns": columns, "rows": rows, "totals": totals,
            "notes": notes or []}


def _non_draft_trips(date_from: date, date_to: date) -> List[Dict[str, Any]]:
    trips = _get(AutoparkStore.list_trips(date_from, date_to), "Рейсы")
    return [t for t in trips if t.get("status_code") != "DRAFT"]


# ── 1. По водителю ──────────────────────────────────────────────────────

def report_driver(date_from: date, date_to: date) -> Report:
    """Рейсы, пробег, зарплата и отклонения по каждому водителю (ТЗ §14)."""
    settings = _get(AutoparkStore.get_settings(), "Настройки")
    km_limit = float(settings.get("km_deviation_limit") or 0)
    drivers = _get(AutoparkStore.driver_summary(date_from, date_to),
                   "Свод по водителям")

    dev_cnt: Dict[Any, int] = {}
    for t in _non_draft_trips(date_from, date_to):
        if t.get("fact_km") is None or t.get("norm_km") is None:
            continue
        if abs(float(t["fact_km"]) - float(t["norm_km"])) > km_limit:
            dev_cnt[t["driver_id"]] = dev_cnt.get(t["driver_id"], 0) + 1

    rows = []
    for d in drivers:
        norm_km = float(d.get("total_norm_km") or 0)
        fact_km = float(d.get("total_fact_km") or 0)
        rows.append([
            d["full_name"],
            int(d.get("domestic_cnt") or 0),
            int(d.get("import_cnt") or 0),
            _num(norm_km), _num(fact_km), _num(fact_km - norm_km),
            _num(d.get("total_pay")),
            dev_cnt.get(d["driver_id"], 0),
        ])
    totals = ["ИТОГО",
              sum(r[1] for r in rows), sum(r[2] for r in rows),
              _num(sum(r[3] for r in rows)), _num(sum(r[4] for r in rows)),
              _num(sum(r[5] for r in rows)), _num(sum(r[6] for r in rows)),
              sum(r[7] for r in rows)]
    return _report(
        "Отчёт по водителям", date_from, date_to,
        ["Водитель", "Внутр. рейсы", "Импортные рейсы", "Норм. км",
         "Факт. км", "Отклонение, км", "Зарплата, леев",
         "Рейсов сверх лимита"],
        rows, totals if rows else [],
        [f"Лимит отклонения по пробегу: {km_limit:g} км на рейс "
         "(FLT_SETTINGS.KM_DEVIATION_LIMIT); черновики (DRAFT) не входят."])


# ── 2. По автомобилю ────────────────────────────────────────────────────

def report_truck(date_from: date, date_to: date) -> Report:
    """Рейсы, перевезённый объём, норм./факт. расход ДТ по автомобилю."""
    trucks = _get(AutoparkStore.truck_summary(date_from, date_to),
                  "Свод по автомобилям")
    rows = []
    for t in trucks:
        if not int(t.get("trip_cnt") or 0):
            continue  # автомобиль без рейсов в периоде не раздувает отчёт
        norm_l = float(t.get("norm_fuel_l") or 0)
        fact_l = (float(t["fact_fuel_l"])
                  if t.get("fact_fuel_l") is not None else None)
        rows.append([
            t["plate"],
            int(t.get("trip_cnt") or 0),
            _num(t.get("total_volume_l")),
            _num(norm_l), _num(fact_l),
            _num(fact_l - norm_l) if fact_l is not None else None,
        ])
    totals = ["ИТОГО", sum(r[1] for r in rows),
              _num(sum(r[2] or 0 for r in rows)),
              _num(sum(r[3] or 0 for r in rows)),
              _num(sum(r[4] for r in rows if r[4] is not None)),
              _num(sum(r[5] for r in rows if r[5] is not None))]
    return _report(
        "Отчёт по автомобилям", date_from, date_to,
        ["Автомобиль", "Рейсов", "Перевезено, л", "Норм. расход ДТ, л",
         "Факт. расход ДТ, л", "Перерасход, л"],
        rows, totals if rows else [],
        ["Пустой факт. расход — у рейсов автомобиля нет заправочной "
         "телеметрии (FACT_FUEL_L IS NULL); это не нулевой расход."])


# ── 3. По АЗС ───────────────────────────────────────────────────────────

def report_station(date_from: date, date_to: date) -> Report:
    """Расчётная потребность vs фактические поставки по АЗС/продукту."""
    data = _get(AutoparkStore.station_supply_report(date_from, date_to),
                "Свод по АЗС")
    rows = []
    for r in data:
        current_l = float(r.get("current_l") or 0)
        min_stock = float(r.get("min_stock_l") or 0)
        need_l = max(0.0, min_stock - current_l)
        deliv_l = float(r.get("deliv_volume_l") or 0)
        rows.append([
            r["station_code"], r["station_name"], r["product_code"],
            _num(current_l), _num(min_stock),
            _num(r.get("stock_days")), _num(need_l),
            int(r.get("deliv_cnt") or 0), _num(deliv_l),
            _num(deliv_l - need_l),
        ])
    totals = ["ИТОГО", "", "",
              _num(sum(r[3] for r in rows)), _num(sum(r[4] for r in rows)),
              None, _num(sum(r[6] for r in rows)),
              sum(r[7] for r in rows), _num(sum(r[8] for r in rows)),
              _num(sum(r[9] for r in rows))]
    return _report(
        "Отчёт по АЗС (потребность и поставки)", date_from, date_to,
        ["Код АЗС", "АЗС", "Продукт", "Остаток, л", "Мин. запас, л",
         "Запас, дней", "Расч. потребность, л", "Поставок",
         "Поставлено, л", "Отклонение, л"],
        rows, totals if rows else [],
        ["Расчётная потребность здесь — дефицит до минимального "
         "страхового запаса на ТЕКУЩУЮ дату (max(0, мин.запас − остаток)); "
         "полная формула планирования (прогноз реализации, объём в пути, "
         "вместимость) — в supply_plan (ТЗ §7)."])


# ── 4. Сводный ──────────────────────────────────────────────────────────

def report_summary(date_from: date, date_to: date) -> Report:
    """Общая зарплата/пробег/перерасход + рейтинг водителей (ТЗ §14).

    Рейтинг — по эффективности маршрутов: |факт − норма| / норма,
    по возрастанию (чем меньше относительное отклонение, тем выше место).
    Водитель без факта пробега (GPS не покрыл ни одного рейса) идёт в
    конец списка — сравнивать его не с чем.
    """
    drivers = _get(AutoparkStore.driver_summary(date_from, date_to),
                   "Свод по водителям")
    control = _get(AutoparkStore.trip_control_report(date_from, date_to),
                   "Контроль рейсов")

    scored = []
    for d in drivers:
        norm_km = float(d.get("total_norm_km") or 0)
        fact_km = float(d.get("total_fact_km") or 0)
        eff = (abs(fact_km - norm_km) / norm_km * 100
               if norm_km and fact_km else None)
        scored.append((eff, d, norm_km, fact_km))
    scored.sort(key=lambda x: x[0] if x[0] is not None else float("inf"))

    rows = []
    for rank, (eff, d, norm_km, fact_km) in enumerate(scored, start=1):
        rows.append([rank, d["full_name"],
                     int(d.get("domestic_cnt") or 0),
                     int(d.get("import_cnt") or 0),
                     _num(norm_km), _num(fact_km),
                     _num(eff), _num(d.get("total_pay"))])

    over_fuel = sum(float(r["fuel_deviation"]) for r in control
                    if r.get("fuel_deviation") is not None
                    and float(r["fuel_deviation"]) > 0)
    totals = ["", "ИТОГО", sum(r[2] for r in rows), sum(r[3] for r in rows),
              _num(sum(r[4] for r in rows)), _num(sum(r[5] for r in rows)),
              None, _num(sum(r[7] for r in rows))]
    return _report(
        "Сводный отчёт (рейтинг водителей)", date_from, date_to,
        ["Место", "Водитель", "Внутр. рейсы", "Импортные рейсы",
         "Норм. км", "Факт. км", "|Откл.|/норма, %", "Зарплата, леев"],
        rows, totals if rows else [],
        [f"Суммарный перерасход ДТ за период: {over_fuel:.2f} л "
         "(сумма положительных отклонений факт − норматив по рейсам).",
         "Рейтинг: |факт − норма| / норма, по возрастанию; водители без "
         "фактического пробега — в конце списка."])


# ── 5. Для руководства ──────────────────────────────────────────────────

def report_management(date_from: date, date_to: date) -> Report:
    """Ключевые показатели периода одним листом (ТЗ §14)."""
    from modules.autopark.controller import AutoparkController
    data = _get(AutoparkController.management_report(
        {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}),
        "Сводка руководству")
    settings = _get(AutoparkStore.get_settings(), "Настройки")
    rate = float(settings.get("rate_per_km") or 0)

    total_norm = float(data.get("total_norm_km") or 0)
    total_fact = float(data.get("total_fact_km") or 0)
    effect = (total_fact - total_norm) * rate

    rows = [
        ["Рейсов выполнено", data.get("total_trip_cnt"), ""],
        ["Перевезено топлива, л", _num(data.get("total_volume_l")), ""],
        ["Нормативный пробег, км", _num(total_norm), ""],
        ["Фактический пробег (GPS), км", _num(total_fact), ""],
        ["Фонд оплаты, леев", _num(data.get("total_pay")), ""],
        ["Стоимость перевозки 1 л, леев", _num(data.get("cost_per_liter"), 4),
         "только зарплатная часть"],
        ["Средняя загрузка бензовозов, %", _num(data.get("avg_loading_pct")),
         "объём / (рейсы × вместимость)"],
        ["Рейсов с превышением по пробегу", data.get("km_deviation_cnt"), ""],
        ["Рейсов с перерасходом ДТ", data.get("fuel_deviation_cnt"), ""],
        ["Экономический эффект, леев", _num(effect),
         "(факт − норм. пробег) × %.2f; >0 — переплата, <0 — экономия"
         % rate],
    ]
    return _report(
        "Отчёт для руководства", date_from, date_to,
        ["Показатель", "Значение", "Комментарий"], rows, [],
        ["Экономический эффект — оценка по зарплатной ставке за км "
         f"({rate:g} лея): переплаченные (или сэкономленные) леи за "
         "разницу фактического и нормативного пробега; стоимость "
         "топлива в оценку не входит (ТЗ §14, допущение)."])


# ── 6. Ценовой (ANRE) ───────────────────────────────────────────────────

def report_prices(date_from: date, date_to: date) -> Report:
    """Динамика предельных цен ANRE + влияние на стоимость норм. расхода."""
    prices = _get(AutoparkStore.list_fuel_prices(date_from, date_to),
                  "Цены на топливо")
    series: Dict[str, List[Dict[str, Any]]] = {}
    for p in prices:
        series.setdefault(p["product_code"], []).append(p)

    rows = []
    for product in sorted(series):
        pts = sorted(series[product], key=lambda p: _as_date(p["price_date"]))
        values = [float(p["price_lei"]) for p in pts]
        changes = sum(1 for a, b in zip(values, values[1:]) if a != b)
        first, last = values[0], values[-1]
        rows.append([
            product, len(pts), changes,
            _num(first), _num(last),
            _num(min(values)), _num(max(values)),
            _num(sum(values) / len(values)),
            _num((last - first) / first * 100) if first else None,
        ])

    # Влияние на парк: норм. литры ДТ каждого рейса × цена DIESEL на дату
    # рейса (цена решения действует до следующего — forward-fill).
    notes = []
    diesel = sorted(series.get("DIESEL", []),
                    key=lambda p: _as_date(p["price_date"]))
    diesel_series = [(_as_date(p["price_date"]), float(p["price_lei"]))
                     for p in diesel]

    def price_at(day: Optional[date]) -> Optional[float]:
        best = None
        for d, v in diesel_series:
            if d is None or day is None or d > day:
                break
            best = v
        return best

    trucks = _get(AutoparkStore.list_trucks(), "Автомобили")
    norm_by_truck = {t["id"]: float(t["norm_l_per_100km"] or 0)
                     for t in trucks}
    norm_liters = 0.0
    norm_cost = 0.0
    unpriced = 0
    for t in _non_draft_trips(date_from, date_to):
        liters = (float(t.get("norm_km") or 0)
                  * norm_by_truck.get(t["truck_id"], 0) / 100)
        norm_liters += liters
        price = price_at(_as_date(t.get("trip_date")))
        if price is None:
            unpriced += 1
            continue
        norm_cost += liters * price
    notes.append(f"Нормативный расход ДТ парка за период: "
                 f"{norm_liters:.1f} л; его стоимость по ценам ANRE на "
                 f"дату каждого рейса: {norm_cost:.2f} леев.")
    if unpriced:
        notes.append(f"Для {unpriced} рейсов не нашлось цены DIESEL на "
                     "дату рейса — они вошли в литры, но не в стоимость.")
    notes.append("«Изменений» — число смен уровня цены внутри периода "
                 "(решение ANRE действует до следующего, ряд в "
                 "FLT_FUEL_PRICES — ступенчатый, forward-fill).")
    return _report(
        "Ценовой отчёт (ANRE)", date_from, date_to,
        ["Продукт", "Дней с ценой", "Изменений", "Цена на начало",
         "Цена на конец", "Мин", "Макс", "Средняя", "Изменение, %"],
        rows, [], notes)


# ── Реестр для CLI/бота ────────────────────────────────────────────────

REPORTS: Dict[str, Callable[[date, date], Report]] = {
    "driver": report_driver,
    "truck": report_truck,
    "station": report_station,
    "summary": report_summary,
    "management": report_management,
    "prices": report_prices,
}

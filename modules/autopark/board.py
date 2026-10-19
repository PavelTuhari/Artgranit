"""Autopark — сводка для первого лица и совета директоров.

Отдельный слой, а не ещё один отчёт: у руководителя другой вопрос. Логист
спрашивает «что везти завтра», закупщик — «чем закрыть дефицит»,
бухгалтер — «сколько начислить». Первое лицо спрашивает три вещи:

    1. Сеть под контролем или где-то вот-вот встанет колонка?
    2. Во что обходится логистика и где мы теряем деньги?
    3. Что даст автоматизация в цифрах, а не в обещаниях?

Поэтому здесь не таблицы, а короткие ответы с оценкой «хорошо / внимание
/ плохо» и одной фразой, объясняющей, что делать. Ни одного термина,
которого нет в обычной управленческой речи: «запас в днях», «стоимость
доставки литра», «перерасход».

Расчёты чистые (без БД) живут в supply_rules.transport_economics и
periods; здесь — только сборка и пороги.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from modules.autopark import board_store
from modules.autopark import supply_rules as rules

# Пороги светофора. Вынесены сюда, а не спрятаны в формулах: их придётся
# обсуждать с заказчиком, и искать их нужно в одном месте.
DRY_RISK_DAYS = 1.0        # меньше суток запаса — красный
LOW_STOCK_DAYS = 2.0       # меньше двух суток — жёлтый
DEVIATION_PCT_WARN = 3.0   # перепробег к нормативу, % — жёлтый
DEVIATION_PCT_BAD = 7.0    # то же, красный


def _level(value: Optional[float], warn: float, bad: float,
           higher_is_worse: bool = True) -> str:
    if value is None:
        return "unknown"
    if higher_is_worse:
        if value >= bad:
            return "bad"
        if value >= warn:
            return "warn"
        return "good"
    if value <= bad:
        return "bad"
    if value <= warn:
        return "warn"
    return "good"


def network_status(tanks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Первый вопрос руководителя: где сеть может встать.

    Считаются не «резервуары ниже минимума» (это язык логиста), а
    станции: колонка стоит не по резервуару, а по АЗС.
    """
    risky, low, ok = set(), set(), set()
    worst: Optional[Dict[str, Any]] = None
    for tank in tanks:
        days = tank.get("days_to_min")
        station = tank.get("station_code")
        if days is None:
            continue
        if days < DRY_RISK_DAYS:
            risky.add(station)
        elif days < LOW_STOCK_DAYS:
            low.add(station)
        else:
            ok.add(station)
        if worst is None or days < worst["days"]:
            worst = {"days": days, "station": station,
                     "product": tank.get("product_code")}
    low -= risky
    ok -= risky | low
    total = len(risky | low | ok)
    return {
        "stations_total": total,
        "stations_risky": len(risky),
        "stations_low": len(low),
        "stations_ok": len(ok),
        "worst": worst,
        "level": "bad" if risky else ("warn" if low else "good"),
        "headline": ("Сеть под контролем" if not risky and not low else
                     (f"Требуют завоза сегодня: {len(risky)} АЗС" if risky
                      else f"Близко к минимуму: {len(low)} АЗС")),
    }


def money(economics: Dict[str, Any], fuel_price: Optional[float]) -> Dict[str, Any]:
    """Второй вопрос: сколько стоит логистика и где потери."""
    volume = float(economics.get("volume_l") or 0)
    pay = float(economics.get("pay_total") or 0)
    effect = float(economics.get("optimization_effect") or 0)
    cost_per_liter = economics.get("cost_per_liter")
    extra_km = float(economics.get("extra_km") or 0)
    norm_km = float(economics.get("norm_km") or 0)
    extra_pct = (extra_km / norm_km * 100) if norm_km else None
    return {
        "volume_l": volume,
        "pay_total": pay,
        "cost_per_liter": cost_per_liter,
        "fuel_price": fuel_price,
        "cost_share_pct": (round(cost_per_liter / fuel_price * 100, 2)
                           if cost_per_liter and fuel_price else None),
        "extra_km": extra_km,
        "extra_pct": round(extra_pct, 2) if extra_pct is not None else None,
        "fuel_over_l": economics.get("fuel_over_l"),
        "loss_total": effect,
        "level": _level(extra_pct, DEVIATION_PCT_WARN, DEVIATION_PCT_BAD),
        # Формулировка зависит от того, тревожная цифра или рабочая.
        # «Лишний пробег 218 км — 3 547 лей» рядом с зелёным индикатором
        # читается как противоречие, хотя 0,8% отклонения — норма для
        # живой логистики. Руководителю нужен один вывод, а не два.
        "headline": (
            "Отклонений по пробегу и топливу нет" if effect <= 0 else
            (f"Лишний пробег {extra_km:,.0f} км — это {effect:,.0f} лей"
             .replace(",", " ")
             if _level(extra_pct, DEVIATION_PCT_WARN, DEVIATION_PCT_BAD) != "good"
             else f"Отклонения в норме: {extra_pct:.1f}% сверх норматива "
                  f"({effect:,.0f} лей)".replace(",", " "))),
    }


def automation_effect(plans: List[Dict[str, Any]], trips: int,
                      manual_minutes_per_trip: int = 25) -> Dict[str, Any]:
    """Третий вопрос: что дала автоматизация.

    Считается ровно то, что можно подтвердить данными системы: сколько
    рейсов собрано расчётом вместо ручного планирования и сколько это
    рабочего времени логиста. Норматив ручного планирования (25 минут на
    рейс: обзвон АЗС, сверка остатков, раскладка по отсекам) — оценка
    заказчика, она вынесена в параметр и подписана как оценка, а не
    выдана за измерение.
    """
    planned_trips = sum(int(p.get("trips_cnt") or 0) for p in plans)
    planned_volume = sum(float(p.get("volume_l") or 0) for p in plans)
    hours = planned_trips * manual_minutes_per_trip / 60.0
    return {
        "plans": len(plans),
        "planned_trips": planned_trips,
        "planned_volume_l": planned_volume,
        "trips_total": trips,
        "auto_share_pct": (round(100.0 * planned_trips / trips, 1)
                           if trips else None),
        "saved_hours": round(hours, 1),
        "manual_minutes_per_trip": manual_minutes_per_trip,
        "headline": (f"Расчётом собрано рейсов: {planned_trips}"
                     if planned_trips else "Плановые рейсы ещё не создавались"),
    }


def build(date_from: date, date_to: date) -> Dict[str, Any]:
    """Сводка целиком. Каждый блок — ответ на один вопрос руководителя.

    Данные берутся ОДНИМ подключением (board_store.fetch_all): семь
    отдельных соединений с облачной ADB стоили 3,8 секунды на экран,
    который руководитель открывает первым.
    """
    raw = board_store.fetch_all(date_from, date_to)
    if not raw.get("success"):
        return raw
    data = raw["data"]

    tanks = data["tanks"]
    rate_row = data.get("rate") or {}
    settings = data.get("settings") or {}
    rate = float(rate_row.get("rate_per_km") or settings.get("rate_per_km") or 0)
    fuel_price = data.get("fuel_price")
    km_limit = float(settings.get("km_deviation_limit") or 0)

    economics = rules.transport_economics(data["trips"], rate,
                                          fuel_price or 0, km_limit)
    plans = data["plans"]
    rating = rules.driver_rating(data["drivers"])

    status = network_status(tanks)
    cash = money(economics, fuel_price)
    effect = automation_effect(plans, economics.get("trips") or 0)

    # Что делать — по одной фразе на блок. Руководителю нужен не список
    # метрик, а понимание, требуется ли его вмешательство.
    actions: List[str] = []
    if status["level"] == "bad":
        worst = status.get("worst") or {}
        actions.append(f"Сегодня завезти на {status['stations_risky']} АЗС; "
                       f"критичнее всего {worst.get('station')} "
                       f"({worst.get('product')})")
    if cash["level"] != "good" and cash["loss_total"]:
        actions.append(f"Разобрать отклонения по маршрутам: "
                       f"{cash['loss_total']:,.0f} лей за период"
                       .replace(",", " "))
    if rating and rating[-1]["extra_pct"] > DEVIATION_PCT_WARN:
        actions.append(f"Проверить маршруты водителя {rating[-1]['full_name']}: "
                       f"перепробег {rating[-1]['extra_pct']:.1f}%")
    if not actions:
        actions.append("Вмешательство не требуется")

    return {"success": True, "message": "", "data": {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "network": status,
        "money": cash,
        "automation": effect,
        "rating_best": rating[0] if rating else None,
        "rating_worst": rating[-1] if len(rating) > 1 else None,
        "rate_per_km": rate,
        "actions": actions,
    }}

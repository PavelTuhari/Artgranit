"""
Прогнозирование заказов для модуля «Планограммы».

Четыре алгоритма, каждый настраивается через модель (PLG_FCT_MODELS):

  sma           скользящее / взвешенное скользящее среднее
  ses           простое экспоненциальное сглаживание (Brown)
  holt_winters  тройное экспоненциальное сглаживание: уровень + тренд + сезонность
  promo_reg     базовая линия по дням без акций × promo-uplift × индекс трафика зоны
  fresh         скоропортящийся товар: медианный недельный профиль + заказ
                по критическому отношению newsvendor и календарю маршрута
                (через распределительный центр либо прямой поставкой)

Режимы прогона:
  forecast  прогноз вперёд от последней даты истории (QTY_ACTUAL не заполняется);
  backtest  origin отодвигается на горизонт назад, прогноз сравнивается
            с фактом — так считаются MAPE / MAE / RMSE / bias и модели
            сравниваются между собой на одних и тех же данных.

Прогноз превращается в заказ:
  safety_stock = z(service_level) × sigma(остатков модели) × sqrt(lead_time)
  order_qty    = max(0, спрос за (lead_time + horizon) + safety_stock − остаток)
  и округляется вверх до кратности короба (ORDER_MULTIPLE).

Oracle-объекты: sql/85_plg_forecast.sql
"""
from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseConnection

BATCH = 10000

# Квантили нормального распределения для типовых уровней сервиса
Z_TABLE = [(50, 0.00), (75, 0.674), (80, 0.842), (85, 1.036), (90, 1.282),
           (92, 1.405), (95, 1.645), (96, 1.751), (97, 1.881), (98, 2.054),
           (99, 2.326), (99.5, 2.576), (99.9, 3.090)]


def z_score(service_level: float) -> float:
    """Линейная интерполяция по таблице квантилей — без внешних зависимостей."""
    sl = max(50.0, min(99.9, float(service_level or 95)))
    for i in range(1, len(Z_TABLE)):
        lo_sl, lo_z = Z_TABLE[i - 1]
        hi_sl, hi_z = Z_TABLE[i]
        if sl <= hi_sl:
            if hi_sl == lo_sl:
                return hi_z
            k = (sl - lo_sl) / (hi_sl - lo_sl)
            return lo_z + k * (hi_z - lo_z)
    return Z_TABLE[-1][1]


class ForecastCancelled(Exception):
    """Прогон остановлен оператором."""


# ==================== Алгоритмы ====================

def forecast_sma(series: Sequence[float], horizon: int, params: Dict) -> List[float]:
    """
    Скользящее среднее. weighted=1 → линейные веса (свежие дни тяжелее).
    Прогноз плоский: одно и то же значение на весь горизонт — модель
    не знает ни тренда, ни сезонности, и это её честное поведение.
    """
    window = max(1, int(params.get('window') or 14))
    tail = list(series[-window:]) or [0.0]
    if params.get('weighted'):
        weights = list(range(1, len(tail) + 1))
        value = sum(v * w for v, w in zip(tail, weights)) / sum(weights)
    else:
        value = sum(tail) / len(tail)
    return [max(0.0, value)] * horizon


def forecast_ses(series: Sequence[float], horizon: int, params: Dict) -> List[float]:
    """Простое экспоненциальное сглаживание: level = a·y + (1−a)·level."""
    alpha = float(params.get('alpha') or 0.3)
    alpha = min(0.95, max(0.01, alpha))
    if not series:
        return [0.0] * horizon
    level = float(series[0])
    for y in series[1:]:
        level = alpha * float(y) + (1 - alpha) * level
    return [max(0.0, level)] * horizon


def forecast_holt_winters(series: Sequence[float], horizon: int, params: Dict) -> List[float]:
    """
    Тройное экспоненциальное сглаживание с аддитивной сезонностью.
    При damped=1 тренд затухает (phi=0.95) — иначе на длинном горизонте
    линейный тренд уводит прогноз в неправдоподобные значения.
    """
    alpha = min(0.95, max(0.01, float(params.get('alpha') or 0.3)))
    beta = min(0.95, max(0.0, float(params.get('beta') or 0.1)))
    gamma = min(0.95, max(0.0, float(params.get('gamma') or 0.2)))
    season = max(2, int(params.get('season') or 7))
    phi = 0.95 if params.get('damped') else 1.0

    n = len(series)
    if n < season * 2:
        # Истории не хватает на два полных периода — откатываемся на SES
        return forecast_ses(series, horizon, {'alpha': alpha})

    data = [float(v) for v in series]
    # Инициализация: уровень и тренд по первым двум периодам, сезонность — отклонения
    first = sum(data[:season]) / season
    second = sum(data[season:season * 2]) / season
    level = first
    trend = (second - first) / season
    seasonal = [data[i] - first for i in range(season)]

    for i, y in enumerate(data):
        idx = i % season
        last_level = level
        level = alpha * (y - seasonal[idx]) + (1 - alpha) * (level + phi * trend)
        trend = beta * (level - last_level) + (1 - beta) * phi * trend
        seasonal[idx] = gamma * (y - level) + (1 - gamma) * seasonal[idx]

    out = []
    damp_sum = 0.0
    for h in range(1, horizon + 1):
        damp_sum += phi ** h
        idx = (n + h - 1) % season
        out.append(max(0.0, level + damp_sum * trend + seasonal[idx]))
    return out


def forecast_promo_reg(series: Sequence[float], horizon: int, params: Dict,
                       ctx: Optional[Dict] = None) -> List[float]:
    """
    Базовая линия строится ТОЛЬКО по дням без акций, чтобы промо-всплески
    не задирали «нормальный» уровень спроса. Дальше базовая линия множится
    на недельный профиль, исторический promo-uplift этого SKU (если на дату
    прогноза запланирована акция) и индекс проходимости зоны выкладки.
    """
    ctx = ctx or {}
    window = max(14, int(params.get('baseline_window') or 56))
    uplift_cap = float(params.get('uplift_cap') or 3.5)
    promo_flags = ctx.get('promo_flags') or []          # 1/0 по каждому дню истории
    weekdays = ctx.get('weekdays') or []                # день недели для каждой точки
    future_promo = ctx.get('future_promo') or []        # 1/0 на каждый день горизонта
    future_weekdays = ctx.get('future_weekdays') or []
    traffic_index = float(ctx.get('traffic_index') or 1.0) if params.get('use_traffic') else 1.0

    data = [float(v) for v in series][-window:]
    flags = list(promo_flags)[-window:]
    wds = list(weekdays)[-window:]
    if not data:
        return [0.0] * horizon

    base_points = [v for v, f in zip(data, flags)] if len(flags) != len(data) else \
                  [v for v, f in zip(data, flags) if not f]
    if not base_points:
        base_points = data
    base = sum(base_points) / len(base_points)

    # Недельный профиль по не-промо дням
    profile = {}
    if len(wds) == len(data):
        buckets: Dict[int, List[float]] = {}
        for v, f, wd in zip(data, flags, wds):
            if f:
                continue
            buckets.setdefault(int(wd), []).append(v)
        for wd, vals in buckets.items():
            profile[wd] = (sum(vals) / len(vals)) / base if base > 0 else 1.0

    # Исторический promo-uplift этого SKU
    promo_points = [v for v, f in zip(data, flags) if f] if len(flags) == len(data) else []
    if promo_points and base > 0:
        uplift = min(uplift_cap, max(1.0, (sum(promo_points) / len(promo_points)) / base))
    else:
        uplift = 1.0

    out = []
    for h in range(horizon):
        k = profile.get(int(future_weekdays[h]), 1.0) if h < len(future_weekdays) and profile else 1.0
        promo_k = uplift if (params.get('use_promo') and h < len(future_promo) and future_promo[h]) else 1.0
        out.append(max(0.0, base * k * promo_k * traffic_index))
    return out


def forecast_fresh(series: Sequence[float], horizon: int, params: Dict,
                   ctx: Optional[Dict] = None) -> List[float]:
    """
    Спрос на скоропортящийся товар.

    Отличий от сухого ассортимента три, и все три здесь учтены.

    1. Уровень спроса на фреш меняется быстрее, поэтому окно короткое (35 дней
       против 56 у promo_reg), а вместо среднего берётся МЕДИАНА: одна суббота
       с завозом на банкет не должна поднять профиль всей недели.
    2. Недельный профиль у фреша выражен сильнее, чем сезонность года: хлеб и
       мясо в пятницу-субботу расходятся кратно сильнее вторника. Профиль
       считается по каждому дню недели отдельно.
    3. Свежий уровень последних дней важнее старой истории (погода, стройка
       рядом, ушедший конкурент). Поправка ограничена коридором ±30 %:
       без ограничения одна неделя аномалии ломает заказ на всю следующую.
    """
    ctx = ctx or {}
    window = max(14, int(params.get('window') or 35))
    lvl_window = max(3, int(params.get('level_window') or 7))
    uplift_cap = float(params.get('uplift_cap') or 3.0)

    data = [float(v) for v in series][-window:]
    if not data:
        return [0.0] * horizon
    flags = list(ctx.get('promo_flags') or [])[-window:]
    wds = list(ctx.get('weekdays') or [])[-window:]
    future_promo = ctx.get('future_promo') or []
    future_weekdays = ctx.get('future_weekdays') or []

    def median(values: Sequence[float]) -> float:
        s = sorted(values)
        n = len(s)
        if not n:
            return 0.0
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

    # База — медиана дней без акций
    plain = [v for v, f in zip(data, flags) if not f] if len(flags) == len(data) else list(data)
    if not plain:
        plain = list(data)
    base = median(plain)
    if base <= 0:
        base = median(data)

    # Недельный профиль: коэффициент к базе по каждому дню недели
    profile: Dict[int, float] = {}
    if len(wds) == len(data) and base > 0:
        buckets: Dict[int, List[float]] = {}
        for v, wd, f in zip(data, wds, flags if len(flags) == len(data) else [0] * len(data)):
            if f:
                continue
            buckets.setdefault(int(wd), []).append(v)
        for wd, vals in buckets.items():
            if len(vals) >= 2:
                # Коридор оставлен широким: у пекарни суббота реально вдвое выше вторника
                profile[wd] = min(2.5, max(0.35, median(vals) / base))

    # Поправка на свежий уровень: последние дни против ожидания профиля
    level_k = 1.0
    if len(data) >= lvl_window and base > 0:
        recent = data[-lvl_window:]
        recent_wds = wds[-lvl_window:] if len(wds) == len(data) else []
        expected = sum(base * profile.get(int(wd), 1.0) for wd in recent_wds) if recent_wds \
            else base * lvl_window
        if expected > 0:
            level_k = min(1.30, max(0.70, sum(recent) / expected))

    # Промо-аплифт этого SKU по фактической истории
    promo_points = [v for v, f in zip(data, flags) if f] if len(flags) == len(data) else []
    uplift = 1.0
    if promo_points and base > 0:
        uplift = min(uplift_cap, max(1.0, median(promo_points) / base))

    out = []
    for h in range(horizon):
        k = profile.get(int(future_weekdays[h]), 1.0) if h < len(future_weekdays) else 1.0
        promo_k = uplift if (params.get('use_promo') and h < len(future_promo)
                             and future_promo[h]) else 1.0
        out.append(max(0.0, base * k * level_k * promo_k))
    return out


ALGORITHMS = {
    'sma': forecast_sma,
    'ses': forecast_ses,
    'holt_winters': forecast_holt_winters,
    'promo_reg': forecast_promo_reg,
    'fresh': forecast_fresh,
}


def run_algorithm(algorithm: str, series: Sequence[float], horizon: int,
                  params: Dict, ctx: Optional[Dict] = None) -> List[float]:
    fn = ALGORITHMS.get(algorithm)
    if not fn:
        raise ValueError(f"Неизвестный алгоритм прогноза: {algorithm}")
    if algorithm in ('promo_reg', 'fresh'):
        return fn(series, horizon, params, ctx)
    return fn(series, horizon, params)


# ==================== Заказ фреш: календарь и экономика ====================
#
# Отдельный слой поверх прогноза: спрос предсказывается одинаково, а вот
# превращение прогноза в заказ у фреша принципиально другое.

def _norm_cdf(x: float) -> float:
    """Φ(x) через erf — стандартной библиотеки хватает, зависимостей не надо."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def z_from_probability(p: float) -> float:
    """
    Обратная функция нормального распределения (Acklam, рациональное
    приближение). Нужна там, где уровень сервиса не задан оператором,
    а ВЫЧИСЛЕН из экономики — как критическое отношение newsvendor.
    """
    p = min(0.999999, max(0.000001, float(p)))
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _calendar_days(mask: Optional[str]) -> List[int]:
    """'1111100' → [0,1,2,3,4]. Понедельник первый, как в date.weekday()."""
    mask = (mask or '1111111').strip()
    if len(mask) != 7 or set(mask) - {'0', '1'}:
        return list(range(7))
    days = [i for i, ch in enumerate(mask) if ch == '1']
    return days or list(range(7))


def delivery_schedule(origin: date, route: Dict, ahead: int = 21) -> Tuple[Optional[date], Optional[date]]:
    """
    Ближайшая и следующая за ней даты поставки по календарю маршрута.

    Считаем честно по календарю, а не «плечо в днях»: у рыбы поставки
    по понедельникам, средам и пятницам, и разрыв выходного (пятница → понедельник)
    втрое больше буднего. Именно этот разрыв определяет, сколько товара нужно
    заказать, — усреднённое «раз в 2.3 дня» даёт систематический недозаказ
    перед выходными и перезаказ в середине недели.
    """
    order_days = set(_calendar_days(route.get('order_days')))
    delivery_days = set(_calendar_days(route.get('delivery_days')))
    lead = float(route.get('lead_time_days') or 1)

    found: List[date] = []
    for offset in range(0, ahead + 1):
        day = origin + timedelta(days=offset)
        if day.weekday() not in order_days and offset == 0:
            continue
        # Заказ, размещённый сегодня, приезжает не раньше чем через lead дней
        earliest = origin + timedelta(days=int(math.ceil(lead)))
        if day < earliest:
            continue
        if day.weekday() in delivery_days:
            found.append(day)
            if len(found) >= 2:
                break
    if not found:
        return None, None
    return found[0], (found[1] if len(found) > 1 else None)


def fresh_order(daily_forecast: Sequence[float], origin: date, route: Dict,
                economics: Dict, params: Dict) -> Dict[str, Any]:
    """
    Заказ скоропортящегося товара.

    Логика, по шагам:

    1. По календарю маршрута находим ближайшую поставку d1 и следующую d2.
       Партия должна прокормить полку от d1 до d2 — это и есть окно защиты.
    2. Спрос на окне берём из прогноза (он уже дневной и с профилем недели),
       а не из среднего: разрыв выходного считается по фактическим дням.
    3. Уровень сервиса НЕ задаётся оператором. Он вычисляется из экономики:
         Cu = цена − себестоимость          (теряем, если не хватило)
         Co = себестоимость − возврат уценкой (теряем, если списали)
         CR = Cu / (Cu + Co)
       У молока с наценкой 26 % и полным списанием CR ≈ 0.79, у пекарни
       с наценкой 42 % и уценкой 10 % — CR ≈ 0.85. Это и есть ответ на вопрос
       «сколько держать на полке»: не «97 % по регламенту», а столько, сколько
       выгодно именно по этому товару.
    4. Ограничение сроком годности. Если остаточный срок на полке короче окна
       защиты, партия физически не доживёт до следующей поставки — заказ
       режется по сроку и помечается shelf_limited. Это не ошибка расчёта,
       а сигнал категорийному менеджеру: маршрут или график не годятся.
    5. Презентационный минимум: полка фреша не должна выглядеть пустой даже
       при слабом спросе, иначе падают и продажи соседних позиций.
    6. Ожидаемое списание считается функцией потерь нормального распределения
       E[max(0, S − D)] — чтобы рекомендация показывала свою цену, а не только
       количество.
    """
    horizon = len(daily_forecast)
    d1, d2 = delivery_schedule(origin, route)
    if not d1:
        return {'order': 0.0, 'coverage': 0.0, 'waste': 0.0, 'shelf_limited': 0,
                'next_delivery': None, 'safety': 0.0, 'reason': 'no_delivery_day'}

    # Окно защиты: от ближайшей поставки до следующей. Если следующей в горизонте
    # нет, берём типовой интервал по календарю поставок.
    if d2:
        window_days = max(1, (d2 - d1).days)
    else:
        per_week = len(_calendar_days(route.get('delivery_days')))
        window_days = max(1, round(7 / max(1, per_week)))

    def demand_between(day_from: date, days: int) -> float:
        total = 0.0
        for i in range(days):
            idx = (day_from - origin).days + i - 1
            if 0 <= idx < horizon:
                total += float(daily_forecast[idx])
            elif horizon:
                total += sum(daily_forecast) / horizon   # за горизонтом — средний день
        return total

    # Остаточный срок годности на полке
    shelf_life = float(economics.get('shelf_life_days') or 0)
    receipt_pct = float(route.get('receipt_shelf_pct')
                        or economics.get('receipt_shelf_pct') or 80)
    transit = float(route.get('transit_days') or 0)
    usable_days = max(0.5, shelf_life * receipt_pct / 100.0 - transit) if shelf_life else 999.0

    coverage_days = float(window_days)
    shelf_limited = 0
    if usable_days < coverage_days:
        coverage_days = usable_days
        shelf_limited = 1

    mu = demand_between(d1, int(math.ceil(coverage_days)))
    # Спрос до прихода партии закрывается текущим остатком, а не заказом
    mu_until_arrival = demand_between(origin + timedelta(days=1), max(0, (d1 - origin).days))

    # Критическое отношение.
    #
    # Классический newsvendor предполагает, что остаток в конце периода
    # обесценивается полностью. Для фреша это верно только когда срок годности
    # сопоставим с интервалом поставки: булка, не проданная сегодня, завтра
    # уценка. Молоко со сроком девять дней при ежедневном завозе спокойно
    # доживает до следующего дня, и списывать на него полную стоимость нельзя —
    # иначе модель систематически недозаказывает длинный фреш.
    #
    # Поэтому стоимость перезаказа умножается на долю партии, реально рискующую
    # испортиться: отношение окна поставки к остаточному сроку годности.
    price = float(economics.get('price') or 0)
    cost = float(economics.get('cost') or 0) or price * 0.72
    salvage = cost * float(economics.get('salvage_pct') or 0) / 100.0
    perish_share = min(1.0, coverage_days / max(0.5, usable_days))
    waste_cost = (cost * float(params.get('waste_cost_pct') or 100) / 100.0 - salvage) * perish_share
    # Упущенная продажа стоит дороже своей маржи: покупатель уходит за товаром
    # в другую сеть и уносит всю корзину. Коэффициент настраивается.
    lost_factor = float(params.get('lost_sale_factor') or 1.5)
    cu = max(0.01, (price - cost) * lost_factor)
    co = max(0.01, waste_cost)
    cr = cu / (cu + co)
    cr = min(float(params.get('max_cr') or 0.97), max(float(params.get('min_cr') or 0.70), cr))
    z = z_from_probability(cr)

    sigma_daily = float(economics.get('sigma') or 0)
    sigma = sigma_daily * math.sqrt(max(1.0, coverage_days))
    safety = z * sigma

    target = mu + safety
    if params.get('use_presentation'):
        target = max(target, float(economics.get('presentation_min') or 0))

    stock = float(economics.get('stock_on_hand') or 0)
    order = target - max(0.0, stock - mu_until_arrival)
    order = max(0.0, order)

    # Минимальная партия: округляем вверх, только если заказ уже близок к ней.
    # Иначе минималка сама по себе создаёт списание — а именно с ним боремся.
    moq = float(route.get('min_order_qty') or 0)
    if moq > 0 and 0 < order < moq:
        order = moq if order >= moq / 2 else 0.0

    step = float(economics.get('round_step') or 0) or 0
    pack = float(economics.get('pack') or 1)
    if order > 0:
        if pack > 1:
            order = math.ceil(order / pack) * pack
        elif step > 0:
            order = math.ceil(order / step) * step

    # Ожидаемое списание: сколько из партии не успеет продаться за usable_days
    sell_days = min(usable_days, coverage_days) if shelf_life else coverage_days
    mu_sell = demand_between(d1, int(math.ceil(sell_days))) if sell_days > 0 else mu
    sigma_sell = sigma_daily * math.sqrt(max(1.0, sell_days))
    available = order + max(0.0, stock - mu_until_arrival)
    if sigma_sell > 0:
        k = (available - mu_sell) / sigma_sell
        waste = (available - mu_sell) * _norm_cdf(k) + sigma_sell * _norm_pdf(k)
    else:
        waste = max(0.0, available - mu_sell)

    return {
        'order': round(order, 3),
        'coverage': round(coverage_days, 2),
        'waste': round(max(0.0, waste), 3),
        'shelf_limited': shelf_limited,
        'next_delivery': d1,
        'safety': round(safety, 3),
        'critical_ratio': round(cr, 4),
        'reason': 'ok',
    }


# ==================== Движок прогонов ====================

class ForecastEngine:
    """Один экземпляр = один прогон прогноза."""

    _active: Dict[int, "ForecastEngine"] = {}
    _lock = threading.Lock()

    def __init__(self, run_id: int, model: Dict, dataset_id: Optional[int],
                 store_id: Optional[int], mode: str):
        self.run_id = run_id
        self.model = model
        self.dataset_id = dataset_id
        self.store_id = store_id
        self.mode = mode
        self.cancelled = False
        self.conn = None
        self._t0 = time.time()
        self.series_count = 0
        self.skipped = 0
        self.order_sum = 0.0
        self._abs_err: List[float] = []
        self._pct_err: List[float] = []
        self._sq_err: List[float] = []
        self._signed: List[float] = []

    # ---------- запуск ----------

    @staticmethod
    def launch(model_id: int, dataset_id: Optional[int], store_id: Optional[int],
               mode: str, username: str) -> Dict[str, Any]:
        mode = mode if mode in ('forecast', 'backtest') else 'forecast'
        conn = DatabaseConnection.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT ID, CODE, ALGORITHM, PARAMS_JSON, HORIZON_DAYS, SERVICE_LEVEL, "
                "LEAD_TIME_DAYS, ROUND_TO_PACK FROM PLG_FCT_MODELS WHERE ID = :p_id",
                {"p_id": int(model_id)})
            row = cur.fetchone()
            if not row:
                return {"success": False, "error": "Модель прогноза не найдена"}
            try:
                params = json.loads(row[3] or '{}')
            except (ValueError, TypeError):
                params = {}
            model = {"id": int(row[0]), "code": row[1], "algorithm": row[2], "params": params,
                     "horizon": int(row[4] or 7), "service_level": float(row[5] or 95),
                     "lead_time": int(row[6] or 2), "round_to_pack": int(row[7] or 1)}

            run_var = cur.var(int)
            cur.execute(
                "INSERT INTO PLG_FCT_RUNS (MODEL_ID, DATASET_ID, STORE_ID, RUN_MODE, "
                "HORIZON_DAYS, STATUS, STAGE, USERNAME) "
                "VALUES (:p_m, :p_ds, :p_st, :p_mode, :p_h, 'running', 'init', :p_user) "
                "RETURNING ID INTO :p_id",
                {"p_m": model["id"], "p_ds": dataset_id, "p_st": store_id, "p_mode": mode,
                 "p_h": model["horizon"], "p_user": username[:150], "p_id": run_var})
            conn.commit()
            run_id = int(run_var.getvalue()[0])
        finally:
            conn.close()

        engine = ForecastEngine(run_id, model, dataset_id, store_id, mode)
        with ForecastEngine._lock:
            ForecastEngine._active[run_id] = engine
        threading.Thread(target=engine._run, name=f"plg-forecast-{run_id}", daemon=True).start()
        return {"success": True, "run_id": run_id, "mode": mode, "model": model["code"]}

    @staticmethod
    def cancel(run_id: int) -> Dict[str, Any]:
        with ForecastEngine._lock:
            engine = ForecastEngine._active.get(int(run_id))
        if not engine:
            return {"success": False, "error": "Прогон не найден среди активных"}
        engine.cancelled = True
        return {"success": True}

    # ---------- служебное ----------

    def _check_cancel(self):
        if self.cancelled:
            raise ForecastCancelled()

    def _fetch(self, sql: str, params: Optional[Dict] = None) -> List[Tuple]:
        cur = self.conn.cursor()
        cur.execute(sql, params or {})
        return cur.fetchall()

    def _progress(self, stage: str, pct: int):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE PLG_FCT_RUNS SET STAGE = :p_stage, PROGRESS_PCT = :p_pct, "
                "SERIES_COUNT = :p_n WHERE ID = :p_id",
                {"p_stage": stage[:60], "p_pct": max(0, min(100, int(pct))),
                 "p_n": self.series_count, "p_id": self.run_id})
            self.conn.commit()
        except Exception:
            pass

    def _finish(self, status: str, message: str = "", origin: Optional[date] = None):
        mape = (sum(self._pct_err) / len(self._pct_err) * 100) if self._pct_err else None
        mae = (sum(self._abs_err) / len(self._abs_err)) if self._abs_err else None
        rmse = math.sqrt(sum(self._sq_err) / len(self._sq_err)) if self._sq_err else None
        denom = sum(abs(x) for x in self._signed)
        bias = (sum(self._signed) / denom * 100) if denom else None
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE PLG_FCT_RUNS SET STATUS = :p_status, PROGRESS_PCT = :p_pct, "
                "SERIES_COUNT = :p_n, SKIPPED_COUNT = :p_skip, ORIGIN_DATE = :p_origin, "
                "MAPE = :p_mape, MAE = :p_mae, RMSE = :p_rmse, BIAS_PCT = :p_bias, "
                "ORDER_QTY_SUM = :p_order, DURATION_SEC = :p_dur, MESSAGE = :p_msg, "
                "FINISHED_AT = SYSTIMESTAMP WHERE ID = :p_id",
                {"p_status": status, "p_pct": 100 if status == 'done' else None,
                 "p_n": self.series_count, "p_skip": self.skipped, "p_origin": origin,
                 "p_mape": round(mape, 4) if mape is not None else None,
                 "p_mae": round(mae, 4) if mae is not None else None,
                 "p_rmse": round(rmse, 4) if rmse is not None else None,
                 "p_bias": round(bias, 4) if bias is not None else None,
                 "p_order": round(self.order_sum, 3),
                 "p_dur": round(time.time() - self._t0, 1),
                 "p_msg": (message or "")[:2000], "p_id": self.run_id})
            self.conn.commit()
        except Exception:
            pass

    # ---------- основной цикл ----------

    def _run(self):
        try:
            self.conn = DatabaseConnection.get_connection()
        except Exception:
            with ForecastEngine._lock:
                ForecastEngine._active.pop(self.run_id, None)
            return
        origin = None
        try:
            origin = self._execute()
            msg = f"Рядов посчитано: {self.series_count}, пропущено: {self.skipped}"
            if self.series_count == 0 and self.skipped:
                # Частый случай: истории меньше, чем требует алгоритм. Без явного
                # объяснения прогон выглядит как успешный, но пустой.
                min_history = self._fetch(
                    "SELECT MIN_HISTORY FROM PLG_FCT_ALGORITHMS WHERE CODE = :p_c",
                    {"p_c": self.model['algorithm']})
                need = min_history[0][0] if min_history else '?'
                msg += (f". Ни один ряд не прошёл порог истории: алгоритму "
                        f"{self.model['algorithm']} нужно минимум {need} дней продаж")
            self._finish('done', msg, origin)
        except ForecastCancelled:
            self._finish('cancelled', 'Прогон остановлен оператором', origin)
        except Exception as e:
            import traceback
            self._finish('failed', f"{e}\n{traceback.format_exc()[:1500]}", origin)
        finally:
            try:
                self.conn.close()
            except Exception:
                pass
            with ForecastEngine._lock:
                ForecastEngine._active.pop(self.run_id, None)

    def _stores(self) -> List[int]:
        if self.store_id:
            return [int(self.store_id)]
        if self.dataset_id:
            return [int(r[0]) for r in self._fetch(
                "SELECT ID FROM PLG_STORES WHERE DATASET_ID = :p_ds ORDER BY ID",
                {"p_ds": self.dataset_id})]
        return [int(r[0]) for r in self._fetch("SELECT ID FROM PLG_STORES ORDER BY ID")]

    def _execute(self) -> Optional[date]:
        algorithm = self.model['algorithm']
        params = self.model['params']
        horizon = self.model['horizon']
        lead = self.model['lead_time']
        z = z_score(self.model['service_level'])
        exclude_oos = bool(params.get('exclude_oos', 1))

        min_history = int(self._fetch(
            "SELECT MIN_HISTORY FROM PLG_FCT_ALGORITHMS WHERE CODE = :p_c",
            {"p_c": algorithm})[0][0] or 28)

        stores = self._stores()
        if not stores:
            # Пустой набор — это не «успешный прогон на нуле рядов»:
            # оператор должен увидеть причину, а не зелёный статус.
            raise ValueError("В выбранном срезе нет магазинов: "
                             "сначала сгенерируйте набор данных")

        # Последняя дата истории по выбранному срезу. Список магазинов уже
        # получен из БД (числа), поэтому подстановка в IN безопасна.
        in_list = ",".join(str(int(s)) for s in stores)
        row = self._fetch(
            f"SELECT MAX(SALES_DATE) FROM PLG_SALES_DAILY WHERE STORE_ID IN ({in_list})")
        last_date = row[0][0] if row and row[0][0] else None
        if not last_date:
            raise ValueError("Нет истории продаж: сначала сгенерируйте набор данных")
        last_date = last_date.date() if hasattr(last_date, 'date') else last_date

        # backtest: прячем последние horizon дней и прогнозируем их
        origin = last_date - timedelta(days=horizon) if self.mode == 'backtest' else last_date
        history_needed = max(min_history, int(params.get('baseline_window') or 0),
                             int(params.get('window') or 0) * 2,
                             int(params.get('season') or 0) * 3, 60)
        history_from = origin - timedelta(days=history_needed)

        result_sql = ("INSERT INTO PLG_FCT_RESULTS (ID, RUN_ID, STORE_ID, PRODUCT_ID, FCT_DATE, "
                      "QTY_FORECAST, QTY_ACTUAL, ABS_ERROR, SAFETY_STOCK, STOCK_ON_HAND, ORDER_QTY, "
                      "ROUTE, COVERAGE_DAYS, WASTE_FORECAST, SHELF_LIMITED, NEXT_DELIVERY) "
                      "VALUES (PLG_FCT_RESULTS_SEQ.NEXTVAL, :1, :2, :3, :4, :5, :6, :7, :8, :9, :10, "
                      ":11, :12, :13, :14, :15)")
        buffer: List[Tuple] = []

        for si, store_id in enumerate(stores):
            self._check_cancel()
            self._progress(f"store {store_id}", int(si / len(stores) * 100))

            # Индекс проходимости зоны для promo_reg.
            #
            # Индекс — это ИЗМЕНЕНИЕ трафика зоны (последняя неделя против всего
            # окна истории), а не его абсолютный уровень. Абсолютный уровень уже
            # «зашит» в базовую линию SKU, и умножение на него double-count'ит:
            # категории с большим трафиком держат и больше SKU, поэтому средний
            # по товарам индекс уезжает выше единицы и прогноз systematically завышается.
            traffic_by_cat: Dict[int, float] = {}
            if algorithm == 'promo_reg' and params.get('use_traffic'):
                for (cid, recent, overall) in self._fetch(
                        "SELECT z.CATEGORY_ID, "
                        "  AVG(CASE WHEN t.METRIC_DATE > :p_recent THEN t.TRAFFIC_PCT END), "
                        "  AVG(t.TRAFFIC_PCT) "
                        "FROM PLG_ZONES z JOIN PLG_ZONE_TRAFFIC t ON t.ZONE_ID = z.ID "
                        "WHERE z.STORE_ID = :p_st AND z.CATEGORY_ID IS NOT NULL "
                        "AND t.METRIC_DATE <= :p_origin GROUP BY z.CATEGORY_ID",
                        {"p_st": store_id, "p_recent": origin - timedelta(days=7),
                         "p_origin": origin}):
                    if not recent or not overall:
                        continue
                    # Ограничение: трафик — вспомогательный сигнал, а не главный
                    traffic_by_cat[int(cid)] = min(1.25, max(0.80, float(recent) / float(overall)))

            # Плановые акции на горизонте (по SKU)
            future_promo: Dict[int, set] = {}
            if algorithm == 'promo_reg' and params.get('use_promo'):
                for (prod_id, d_from, d_to) in self._fetch(
                        "SELECT pp.PRODUCT_ID, pr.DATE_FROM, pr.DATE_TO FROM PLG_PROMOS pr "
                        "JOIN PLG_PROMO_PRODUCTS pp ON pp.PROMO_ID = pr.ID "
                        "WHERE pr.STORE_ID = :p_st AND pr.STATUS <> 'cancelled' "
                        "AND pr.DATE_TO >= :p_from", {"p_st": store_id, "p_from": origin}):
                    d = d_from.date() if hasattr(d_from, 'date') else d_from
                    end = d_to.date() if hasattr(d_to, 'date') else d_to
                    bucket = future_promo.setdefault(int(prod_id), set())
                    while d <= end:
                        bucket.add(d.toordinal())
                        d += timedelta(days=1)

            rows = self._fetch(
                "SELECT sd.PRODUCT_ID, sd.SALES_DATE, sd.QTY, NVL(sd.IS_OOS,0), "
                "CASE WHEN sd.PROMO_ID IS NULL THEN 0 ELSE 1 END, sd.STOCK_END "
                "FROM PLG_SALES_DAILY sd WHERE sd.STORE_ID = :p_st "
                "AND sd.SALES_DATE BETWEEN :p_from AND :p_to "
                "ORDER BY sd.PRODUCT_ID, sd.SALES_DATE",
                {"p_st": store_id, "p_from": history_from, "p_to": origin})
            if not rows:
                continue

            actuals: Dict[Tuple[int, int], float] = {}
            if self.mode == 'backtest':
                for (prod_id, d, qty) in self._fetch(
                        "SELECT PRODUCT_ID, SALES_DATE, QTY FROM PLG_SALES_DAILY "
                        "WHERE STORE_ID = :p_st AND SALES_DATE > :p_from AND SALES_DATE <= :p_to",
                        {"p_st": store_id, "p_from": origin, "p_to": last_date}):
                    dd = d.date() if hasattr(d, 'date') else d
                    actuals[(int(prod_id), dd.toordinal())] = float(qty or 0)

            meta = {int(r[0]): r for r in self._fetch(
                "SELECT p.ID, NVL(p.ORDER_MULTIPLE,1), NVL(p.LEAD_TIME_DAYS,:p_lead), p.CATEGORY_ID "
                "FROM PLG_PRODUCTS p WHERE p.ID IN "
                "(SELECT DISTINCT PRODUCT_ID FROM PLG_SALES_DAILY WHERE STORE_ID = :p_st)",
                {"p_lead": lead, "p_st": store_id})}

            # Фреш: маршрут поставки, профиль категории и экономика SKU.
            # Читается один раз на магазин — на 400 SKU это 3 запроса вместо 1200.
            fresh_routes, fresh_profiles, fresh_econ = {}, {}, {}
            if algorithm == 'fresh':
                want = params.get('route') or 'auto'
                for (cat_id, route, lead_d, transit, odays, ddays, moq, receipt) in self._fetch(
                        "SELECT CATEGORY_ID, ROUTE, LEAD_TIME_DAYS, TRANSIT_DAYS, ORDER_DAYS, "
                        "DELIVERY_DAYS, MIN_ORDER_QTY, RECEIPT_SHELF_PCT FROM PLG_FRESH_ROUTES "
                        "WHERE STORE_ID = :p_st AND IS_ACTIVE = 1 ORDER BY PRIORITY, ID",
                        {"p_st": store_id}):
                    if want in ('dc', 'direct') and route != want:
                        continue
                    fresh_routes[int(cat_id) if cat_id else None] = {
                        'route': route, 'lead_time_days': float(lead_d or 1),
                        'transit_days': float(transit or 0), 'order_days': odays,
                        'delivery_days': ddays, 'min_order_qty': float(moq or 0),
                        'receipt_shelf_pct': float(receipt) if receipt is not None else None,
                    }
                for (cat_id, shelf, receipt, present, salvage, step) in self._fetch(
                        "SELECT CATEGORY_ID, SHELF_LIFE_DAYS, RECEIPT_SHELF_PCT, PRESENTATION_MIN, "
                        "SALVAGE_PCT, ROUND_STEP FROM PLG_FRESH_PROFILES WHERE IS_ACTIVE = 1"):
                    fresh_profiles[int(cat_id)] = {
                        'shelf_life_days': float(shelf or 0),
                        'receipt_shelf_pct': float(receipt or 80),
                        'presentation_min': float(present or 0),
                        'salvage_pct': float(salvage or 0),
                        'round_step': float(step or 0),
                    }
                for (pid, price, cost, shelf, salvage) in self._fetch(
                        "SELECT p.ID, p.PRICE, p.COST_PRICE, p.SHELF_LIFE_DAYS, p.SALVAGE_PCT "
                        "FROM PLG_PRODUCTS p WHERE NVL(p.IS_FRESH,0) = 1 AND p.ID IN "
                        "(SELECT DISTINCT PRODUCT_ID FROM PLG_SALES_DAILY WHERE STORE_ID = :p_st)",
                        {"p_st": store_id}):
                    fresh_econ[int(pid)] = {
                        'price': float(price or 0), 'cost': float(cost or 0),
                        'shelf_life_days': float(shelf or 0),
                        'salvage_pct': float(salvage) if salvage is not None else None,
                    }

            # Группируем строки в ряды по SKU
            current_pid = None
            series: List[float] = []
            promo_flags: List[int] = []
            weekdays: List[int] = []
            stock_on_hand = 0.0

            def flush():
                nonlocal series, promo_flags, weekdays, stock_on_hand, buffer
                if current_pid is None:
                    return
                if len(series) < min_history:
                    self.skipped += 1
                    return
                if algorithm == 'fresh' and current_pid not in fresh_econ:
                    # Модель фреша не должна выдавать рекомендации по бакалее:
                    # прогон остаётся честным — сухой ассортимент считают другие модели.
                    self.skipped += 1
                    return
                m = meta.get(current_pid)
                pack = int(m[1]) if m else 1
                sku_lead = int(m[2]) if m else lead
                cat_id = int(m[3]) if m and m[3] else None

                clean = series
                if exclude_oos:
                    # Дни out-of-stock — не спрос, а его отсутствие: заменяем медианой,
                    # иначе модель систематически занижает уровень.
                    ordered = sorted(v for v in series if v > 0) or [0.0]
                    median = ordered[len(ordered) // 2]
                    clean = [v if not oos else median for v, oos in zip(series, oos_flags)]

                future_days = [origin + timedelta(days=h + 1) for h in range(horizon)]
                ctx = {
                    'promo_flags': promo_flags,
                    'weekdays': weekdays,
                    'future_promo': [1 if (current_pid in future_promo and
                                           d.toordinal() in future_promo[current_pid]) else 0
                                     for d in future_days],
                    'future_weekdays': [d.weekday() for d in future_days],
                    'traffic_index': traffic_by_cat.get(cat_id, 1.0) if cat_id else 1.0,
                }
                fct = run_algorithm(algorithm, clean, horizon, params, ctx)

                # sigma остатков модели на истории (in-sample, скользящее среднее как опора)
                if len(clean) >= 7:
                    mean_val = sum(clean[-28:]) / len(clean[-28:])
                    var = sum((v - mean_val) ** 2 for v in clean[-28:]) / len(clean[-28:])
                    sigma = math.sqrt(var)
                else:
                    sigma = 0.0
                safety = z * sigma * math.sqrt(max(1, sku_lead))

                route_code = coverage = waste_qty = next_delivery = None
                shelf_limited = 0

                if algorithm == 'fresh' and current_pid in fresh_econ:
                    # Фреш считается по календарю маршрута и экономике списаний,
                    # а не по «горизонт + плечо»: см. fresh_order().
                    econ = dict(fresh_profiles.get(cat_id, {}))
                    econ.update({k: v for k, v in fresh_econ[current_pid].items()
                                 if v not in (None, 0) or k == 'cost'})
                    econ.update({'sigma': sigma, 'stock_on_hand': stock_on_hand,
                                 'pack': pack if self.model['round_to_pack'] else 1})
                    route = fresh_routes.get(cat_id) or fresh_routes.get(None)
                    if route:
                        res = fresh_order(fct, origin, route, econ, params)
                        order = res['order']
                        safety = res['safety']
                        route_code = route['route']
                        coverage = res['coverage']
                        waste_qty = res['waste']
                        shelf_limited = res['shelf_limited']
                        next_delivery = res['next_delivery']
                    else:
                        # Маршрута нет — заказ не выдумываем: пустая рекомендация
                        # честнее, чем посчитанная по несуществующему графику.
                        order = 0.0
                        self.skipped += 1
                else:
                    horizon_demand = sum(fct)
                    lead_demand = (horizon_demand / horizon) * sku_lead if horizon else 0.0
                    need = horizon_demand + lead_demand + safety - stock_on_hand
                    order = max(0.0, need)
                    if self.model['round_to_pack'] and pack > 1 and order > 0:
                        order = math.ceil(order / pack) * pack
                self.order_sum += order

                for h, d in enumerate(future_days):
                    actual = actuals.get((current_pid, d.toordinal())) if self.mode == 'backtest' else None
                    abs_err = None
                    if actual is not None:
                        abs_err = abs(fct[h] - actual)
                        self._abs_err.append(abs_err)
                        self._sq_err.append(abs_err ** 2)
                        self._signed.append(fct[h] - actual)
                        if actual > 0.5:   # MAPE не определён на околонулевом факте
                            self._pct_err.append(abs_err / actual)
                    buffer.append((self.run_id, int(store_id), int(current_pid), d,
                                   round(fct[h], 3),
                                   round(actual, 3) if actual is not None else None,
                                   round(abs_err, 3) if abs_err is not None else None,
                                   round(safety, 3), round(stock_on_hand, 3),
                                   round(order, 3) if h == 0 else 0.0,
                                   route_code if h == 0 else None,
                                   coverage if h == 0 else None,
                                   round(waste_qty, 3) if (h == 0 and waste_qty is not None) else None,
                                   shelf_limited if h == 0 else 0,
                                   next_delivery if h == 0 else None))
                self.series_count += 1

            oos_flags: List[int] = []
            for (prod_id, d, qty, oos, promo, stock) in rows:
                pid = int(prod_id)
                if pid != current_pid:
                    flush()
                    self._check_cancel()
                    if len(buffer) >= BATCH:
                        self._write(result_sql, buffer)
                        buffer = []
                    current_pid = pid
                    series, promo_flags, weekdays, oos_flags = [], [], [], []
                dd = d.date() if hasattr(d, 'date') else d
                series.append(float(qty or 0))
                promo_flags.append(int(promo or 0))
                oos_flags.append(int(oos or 0))
                weekdays.append(dd.weekday())
                stock_on_hand = float(stock or 0)
            flush()

            if buffer:
                self._write(result_sql, buffer)
                buffer = []

        if buffer:
            self._write(result_sql, buffer)
        return origin

    def _write(self, sql: str, rows: List[Tuple]):
        if not rows:
            return
        cur = self.conn.cursor()
        for i in range(0, len(rows), BATCH):
            self._check_cancel()
            cur.executemany(sql, rows[i:i + BATCH])
            self.conn.commit()

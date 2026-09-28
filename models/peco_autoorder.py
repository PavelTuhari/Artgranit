"""
Автозаказ топлива для сети АЗС.

Чем автозаказ топлива отличается от товарного — три вещи, и каждая
меняет формулу, а не только константы.

1. ОГРАНИЧЕНИЕ СВЕРХУ — СВОБОДНАЯ ЁМКОСТЬ, А НЕ СРОК ГОДНОСТИ.
   Товар можно заказать «с запасом» и сложить на складе. Топливо —
   нельзя: резервуар физически вмещает столько, сколько вмещает,
   и заливать под горловину запрещено (температурное расширение,
   потолок 95 % от паспортной ёмкости). Причём считать надо свободную
   ёмкость НЕ СЕЙЧАС, а НА МОМЕНТ ПРИХОДА бензовоза: пока он едет,
   станция продолжает продавать, и места становится больше.

2. КРАТНОСТЬ — СЕКЦИЯ ЦИСТЕРНЫ, А НЕ КОРОБ.
   Заказ округляется не «вверх до кратности», а подбирается КОМБИНАЦИЕЙ
   секций: 6000 + 5000 = 11 000 л. Одна секция — один вид топлива:
   остаток А-95 в секции с дизелем делает несортовыми обе партии.
   Поэтому округление всегда ВНИЗ по свободной ёмкости — перелив
   означает остановленный слив и возврат остатка на нефтебазу.

3. СТОКАУТ СТОИТ НЕ МАРЖИ С ЛИТРА, А ПРОСТОЯ СТАНЦИИ.
   Сухой бак уводит клиента к конкуренту вместе с кофе и мойкой.
   Поэтому уровень сервиса здесь высокий по умолчанию (99 %),
   а «риск сухого бака» — отдельный флаг, а не следствие расчёта.

Двухэшелонная схема снабжения:

    импорт ──▶ НЕФТЕБАЗА ──▶ АЗС
    (плечо 9-14 дней)  (плечо 0.5-1 день)

Заказы АЗС агрегируются в потребность нефтебазы; когда её запаса
не хватает на плечо импорта, поднимается сигнал на импортную закупку.

Oracle-объекты: sql/106_peco_supply.sql, sql/107_peco_supply_views.sql
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel
from models import peco_forecast, peco_plan, peco_sourcing

# Параметры по умолчанию. Вынесены в один словарь: их придётся крутить
# под конкретную сеть, и искать их нужно в одном месте.
DEFAULTS = {
    'max_fill_pct': 95.0,     # потолок налива, % ёмкости (температурное расширение)
    'target_fill_pct': 92.0,  # до какого уровня доливаем, когда уже едем
    'trigger_days': 3.0,      # ниже скольких суток покрытия — пора заказывать
    'service_level': 99.0,    # уровень сервиса для страхового запаса
    'lead_days': 1.0,         # плечо от заявки до слива (нефтебаза)
    'review_days': 1.0,       # как часто вообще можем приехать
    'min_drop_l': 2000.0,     # меньше этого объёма ехать невыгодно
    'max_cover_days': 21.0,   # потолок запаса: сверх него деньги заморожены,
                              # а топливо (особенно А-98 с присадками) стареет
    'recent_weight': 0.35,    # вес свежей недели против месяца в оценке спроса
}

# Квантили нормального распределения: те же, что в товарном прогнозе
_Z = [(50, 0.0), (80, 0.842), (90, 1.282), (95, 1.645), (97, 1.881),
      (98, 2.054), (99, 2.326), (99.5, 2.576), (99.9, 3.090)]


def z_score(service_level: float) -> float:
    sl = max(50.0, min(99.9, float(service_level or 99)))
    for i in range(1, len(_Z)):
        lo_sl, lo_z = _Z[i - 1]
        hi_sl, hi_z = _Z[i]
        if sl <= hi_sl:
            if hi_sl == lo_sl:
                return hi_z
            k = (sl - lo_sl) / (hi_sl - lo_sl)
            return lo_z + k * (hi_z - lo_z)
    return _Z[-1][1]


def best_compartment_fill(target_l: float, ullage_l: float,
                          compartments: List[float],
                          min_drop_l: float = 0.0) -> Tuple[float, List[float]]:
    """
    Подбор комбинации секций под потребность.

    Правило: сумма секций не должна превышать свободную ёмкость (перелив
    физически невозможен), и при этом быть как можно ближе к потребности
    СНИЗУ. Если ни одна комбинация не помещается — возвращается ноль:
    ехать некуда, бак и так почти полный.

    Секций у бензовоза 3-5, поэтому полный перебор подмножеств (2^5 = 32)
    дешевле и точнее любой жадной эвристики.
    """
    limit = min(target_l, ullage_l)
    if limit <= 0 or not compartments:
        return 0.0, []
    n = len(compartments)
    best_sum, best_set = 0.0, []
    for mask in range(1, 1 << n):
        total = 0.0
        used = []
        for i in range(n):
            if mask & (1 << i):
                total += compartments[i]
                used.append(compartments[i])
        if total <= limit + 1e-6 and total > best_sum:
            best_sum, best_set = total, used
    if best_sum < min_drop_l:
        return 0.0, []
    return best_sum, sorted(best_set, reverse=True)


def _sum_days(daily: List[float], days: float) -> float:
    """
    Спрос за дробное число суток по посуточному прогнозу.

    Плечо развозки — половина суток, и округление в любую сторону стоит
    денег: вверх — раздутый заказ на половину оборота сети, вниз —
    недолив. Поэтому последний день берётся пропорционально, а если
    горизонт прогноза короче запрошенного окна, продлевается последним
    значением, а не нулём.
    """
    if not daily or days <= 0:
        return 0.0
    total, full = 0.0, int(days)
    for i in range(full):
        total += daily[i] if i < len(daily) else daily[-1]
    frac = days - full
    if frac > 1e-9:
        total += (daily[full] if full < len(daily) else daily[-1]) * frac
    return total


def calc_tank_order(tank: Dict[str, Any], params: Dict[str, Any],
                    compartments: List[float]) -> Dict[str, Any]:
    """
    Расчёт по одному резервуару.

    tank ожидает ключи: capacity_l, current_l, min_alarm_l, avg_l_28,
    avg_l_7, sigma_l (может отсутствовать).
    """
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (params or {}).items() if v is not None})

    capacity = float(tank.get('capacity_l') or 0)
    current = float(tank.get('current_l') or 0)
    min_alarm = float(tank.get('min_alarm_l') or 0)
    avg28 = float(tank.get('avg_l_28') or 0)
    avg7 = float(tank.get('avg_l_7') or avg28)
    sigma = float(tank.get('sigma_l') or (avg28 * 0.15))

    lead = float(p['lead_days'])
    review = float(p['review_days'])

    # Спрос: месяц как основа, свежая неделя как поправка. Полностью
    # переходить на неделю нельзя — одна аномальная неделя (ремонт дороги,
    # конкурент закрылся) сдвинет заказ по всей сети.
    w = float(p['recent_weight'])
    daily = avg28 * (1 - w) + avg7 * w if avg28 > 0 else avg7

    # Если подан прогноз (theta / croston_sba / conformal / gbt), спрос
    # на окно берётся из него, а не из плоского среднего. Разница не
    # косметическая: среднее не знает про день недели, а бензин в пятницу
    # уходит на треть быстрее вторника, и заказ, посчитанный «в среднем»,
    # в пятницу недоливает, а во вторник морозит деньги.
    forecast = tank.get('forecast') or {}
    fdaily = forecast.get('daily') or []
    algorithm = forecast.get('algorithm')
    if fdaily:
        window = max(1e-9, lead + review)
        lead_demand = _sum_days(fdaily, lead)
        window_demand = _sum_days(fdaily, window)
        daily = window_demand / window
    else:
        lead_demand = daily * lead
        window_demand = daily * (lead + review)
    max_fill = capacity * float(p['max_fill_pct']) / 100.0
    # Целевой уровень ограничен ДВАЖДЫ: физически (процент ёмкости)
    # и экономически (потолок покрытия в сутках). Без второго ограничения
    # медленный грейд заливается под крышку: у А-98 с оборотом 330 л/сут
    # полный резервуар на 27 тысяч — это запас на два с половиной месяца,
    # то есть замороженные деньги и стареющее топливо.
    target_level = capacity * float(p['target_fill_pct']) / 100.0
    if daily > 0:
        target_level = min(target_level,
                           min_alarm + daily * float(p['max_cover_days']))

    # Сколько останется к приходу бензовоза
    level_at_arrival = max(0.0, current - lead_demand)
    ullage = max(0.0, max_fill - level_at_arrival)

    # Ниже аварийного остатка «дней до сухого бака» не бывает: это уже ноль,
    # а факт провала показывается отдельным признаком
    below_alarm = 1 if current <= min_alarm else 0
    days_to_dry = (max(0.0, current - min_alarm) / daily) if daily > 0 else None

    # Страховой запас: у conformal он эмпирический (квантиль реальных
    # ошибок на истории), у остальных — нормальная аппроксимация.
    # Подменять эмпирический на нормальный нельзя: у топлива хвост
    # распределения толще нормального, и на 99 % это видно в литрах.
    fc_safety = float(forecast.get('safety_l') or 0)
    if fc_safety > 0:
        safety = fc_safety
    else:
        z = z_score(p['service_level'])
        safety = z * sigma * math.sqrt(max(1.0, lead + review))

    # Нужно долить до целевого уровня, но не ниже страхового покрытия
    need_by_target = max(0.0, target_level - level_at_arrival)
    need_by_safety = max(0.0, (window_demand + safety + min_alarm) - level_at_arrival)
    need = max(need_by_target, need_by_safety) if daily > 0 else need_by_target
    need = min(need, ullage)

    # Пора ли вообще ехать
    trigger = float(p['trigger_days'])
    must_go = (days_to_dry is not None and days_to_dry <= trigger) or current <= min_alarm
    if not must_go:
        return {'liters': 0.0, 'combo': [], 'ullage_l': round(ullage, 1),
                'daily_rate_l': round(daily, 2),
                'algorithm': algorithm, 'safety_l': round(safety, 1),
                'days_to_dry': round(days_to_dry, 2) if days_to_dry is not None else None,
                'cover_after_d': round(days_to_dry, 2) if days_to_dry is not None else None,
                'is_below_alarm': below_alarm, 'is_dry_risk': 0, 'reason': 'not_due'}

    liters, combo = best_compartment_fill(need, ullage, compartments,
                                          float(p['min_drop_l']))
    after = level_at_arrival + liters
    cover_after = ((after - min_alarm) / daily) if daily > 0 else None

    return {
        'liters': round(liters, 1),
        'combo': combo,
        'ullage_l': round(ullage, 1),
        'daily_rate_l': round(daily, 2),
        'algorithm': algorithm,
        'safety_l': round(safety, 1),
        'days_to_dry': round(days_to_dry, 2) if days_to_dry is not None else None,
        'cover_after_d': round(cover_after, 2) if cover_after is not None else None,
        'is_below_alarm': below_alarm,
        # Риск сухого бака: топливо кончится раньше, чем приедет машина
        'is_dry_risk': 1 if (below_alarm or
                             (days_to_dry is not None and days_to_dry <= lead + 0.5)) else 0,
        'reason': 'ok' if liters > 0 else 'no_room',
    }


class FuelAutoOrder:
    """Прогон автозаказа по сети: считает, пишет заказы, сводит потребность депо."""

    @staticmethod
    def _rows(res) -> List[Dict[str, Any]]:
        if not res or not res.get('success'):
            return []
        cols = [c.lower() for c in (res.get('columns') or [])]
        return [dict(zip(cols, r)) for r in (res.get('data') or [])]

    @staticmethod
    def run(params: Optional[Dict[str, Any]] = None,
            username: str = 'system') -> Dict[str, Any]:
        """
        Синхронный прогон: 184 резервуара считаются за секунды, фоновый
        поток здесь только усложнил бы отладку и статус-поллинг.
        """
        p = dict(DEFAULTS)
        params = dict(params or {})
        algorithm = params.pop('algorithm', None) or None
        if algorithm and algorithm not in peco_forecast.ALGORITHMS:
            return {'success': False, 'status': 400,
                    'error': f'Неизвестный алгоритм прогноза: {algorithm}'}
        money_rate = float(params.pop('money_rate', peco_plan.DEFAULT_MONEY_RATE) or 0)
        p.update({k: v for k, v in params.items() if v is not None})
        started = datetime.now()
        plan_cost = None
        try:
            with DatabaseModel() as db:
                depot = FuelAutoOrder._rows(db.execute_query(
                    "SELECT ID, NAME FROM PECO_DEPOTS WHERE ACTIVE = 1 ORDER BY ID"))
                depot_id = depot[0]['id'] if depot else None

                db.execute_query(
                    "INSERT INTO PECO_ORDER_RUNS (DEPOT_ID, STATUS, STAGE, PARAMS_JSON, USERNAME) "
                    "VALUES (:p_d, 'running', 'start', :p_p, :p_u)",
                    {'p_d': depot_id, 'p_p': json.dumps(p, ensure_ascii=False)[:2000],
                     'p_u': username})
                db.connection.commit()
                run_id = FuelAutoOrder._rows(db.execute_query(
                    "SELECT MAX(ID) AS ID FROM PECO_ORDER_RUNS"))[0]['id']

                # Секции всего парка: множество доступных объёмов налива
                comps = [float(r['volume_l']) for r in FuelAutoOrder._rows(db.execute_query(
                    "SELECT DISTINCT VOLUME_L FROM PECO_TRUCK_COMPARTMENTS "
                    "WHERE ACTIVE = 1 ORDER BY VOLUME_L"))]
                if not comps:
                    comps = [5000.0, 6000.0, 8000.0]

                # Разброс суточного отпуска нужен для страхового запаса
                sigma_by_tank = {int(r['tank_id']): float(r['sigma_l'] or 0)
                                 for r in FuelAutoOrder._rows(db.execute_query(
                                     "SELECT TANK_ID, ROUND(STDDEV(LITERS), 3) AS SIGMA_L "
                                     "FROM PECO_TANK_DAILY "
                                     "WHERE SALE_DATE > (SELECT MAX(SALE_DATE) - 28 FROM PECO_TANK_DAILY) "
                                     "GROUP BY TANK_ID"))}

                tanks = FuelAutoOrder._rows(db.execute_query(
                    "SELECT TANK_ID, STATION_ID, STATION_CODE, STATION_NAME, TANK_CODE, "
                    "GRADE_CODE, CAPACITY_L, CURRENT_L, MIN_ALARM_L, AVG_L_28, AVG_L_7 "
                    "FROM V_PECO_TANK_SUPPLY ORDER BY STATION_ID, GRADE_CODE"))

                # История отпуска под выбранный алгоритм прогноза.
                # Поднимается ОДНИМ запросом на всю сеть: 184 бака по
                # запросу каждый — это 184 round-trip до Oracle в Ирландии,
                # то есть минуты вместо секунд.
                horizon = max(3, int(math.ceil(float(p['lead_days']) +
                                               float(p['review_days']))) + 1)
                hist = {}
                if algorithm:
                    peco_plan.load_min_history(db)
                    hist = peco_plan.load_tank_history(db, peco_plan.HISTORY_DAYS)

                by_station: Dict[int, List[Dict[str, Any]]] = {}
                dry_risk = 0
                fc_used = 0
                for t in tanks:
                    t['sigma_l'] = sigma_by_tank.get(int(t['tank_id']))
                    if algorithm:
                        h = hist.get(int(t['tank_id']))
                        # У conformal своя параметризация: покрытие долей
                        # единицы и окно защиты в сутках — это плечо плюс
                        # период между завозами, а не горизонт прогноза
                        fparams = {'coverage': float(p['service_level']) / 100.0,
                                   'protect_days': float(p['lead_days']) + float(p['review_days'])}
                        f = peco_plan.forecast_tank(h, algorithm, horizon, fparams) if h else None
                        if f:
                            f['algorithm'] = algorithm
                            t['forecast'] = f
                            fc_used += 1
                    res = calc_tank_order(t, p, comps)
                    if res['liters'] <= 0:
                        if res['is_dry_risk']:
                            dry_risk += 1
                        continue
                    dry_risk += res['is_dry_risk']
                    by_station.setdefault(int(t['station_id']), []).append((t, res))

                orders, liters_total = 0, 0.0
                need_by = date.today() + timedelta(days=int(math.ceil(p['lead_days'])))
                for station_id, items in by_station.items():
                    station_liters = sum(r['liters'] for _t, r in items)
                    db.execute_query(
                        "INSERT INTO PECO_FUEL_ORDERS (RUN_ID, STATION_ID, SOURCE_CODE, "
                        "DEPOT_ID, STATUS, NEED_BY, LITERS_TOTAL, CREATED_BY) "
                        "VALUES (:p_r, :p_s, 'depot', :p_d, 'draft', :p_n, :p_l, :p_u)",
                        {'p_r': run_id, 'p_s': station_id, 'p_d': depot_id,
                         'p_n': need_by, 'p_l': round(station_liters, 3), 'p_u': username})
                    order_id = FuelAutoOrder._rows(db.execute_query(
                        "SELECT MAX(ID) AS ID FROM PECO_FUEL_ORDERS WHERE RUN_ID = :p_r "
                        "AND STATION_ID = :p_s", {'p_r': run_id, 'p_s': station_id}))[0]['id']
                    for t, r in items:
                        db.execute_query(
                            "INSERT INTO PECO_FUEL_ORDER_ITEMS (ORDER_ID, STATION_ID, TANK_ID, "
                            "GRADE_CODE, LITERS_MODEL, LITERS_ORDER, CURRENT_L, ULLAGE_L, "
                            "DAILY_RATE_L, DAYS_TO_DRY, COVER_AFTER_D, IS_DRY_RISK, "
                            "ALGORITHM, FORECAST_DAILY_L, SAFETY_L) "
                            "VALUES (:p_o, :p_s, :p_t, :p_g, :p_lm, :p_lo, :p_cur, :p_ul, "
                            ":p_dr, :p_dd, :p_ca, :p_risk, :p_alg, :p_fd, :p_sf)",
                            {'p_o': order_id, 'p_s': station_id, 'p_t': int(t['tank_id']),
                             'p_g': t['grade_code'], 'p_lm': r['liters'], 'p_lo': r['liters'],
                             'p_cur': t['current_l'], 'p_ul': r['ullage_l'],
                             'p_dr': r['daily_rate_l'], 'p_dd': r['days_to_dry'],
                             'p_ca': r['cover_after_d'], 'p_risk': r['is_dry_risk'],
                             'p_alg': r.get('algorithm'),
                             'p_fd': r.get('daily_rate_l') if r.get('algorithm') else None,
                             'p_sf': r.get('safety_l')})
                    orders += 1
                    liters_total += station_liters

                db.connection.commit()

                # Выбор пути снабжения: чем именно закрывать каждую строку.
                # Считается ПОСЛЕ записи строк, потому что оптимизатору
                # нужны итоговые литры (после подбора секций), а не
                # «сколько хотелось».
                plan_cost = None
                try:
                    dem = peco_plan.station_demands(db, run_id)
                    src = peco_plan.load_paths(db, 'distribution')
                    dist = peco_sourcing.solve_distribution(dem, src, money_rate)
                    if dist.get('success'):
                        for a in dist['allocations']:
                            key = a['key']
                            a['item_id'] = int(key.split(':')[1]) if key.startswith('item:') else None
                        peco_plan.apply_plan_to_items(db, dist['allocations'])
                        plan_cost = dist.get('total_cost')
                        uncovered = len(dist.get('uncovered') or [])
                except Exception as pe:                          # noqa: BLE001
                    # Заказ важнее его себестоимости: если путей ещё нет
                    # или справочник цен пуст, заказ остаётся валидным,
                    # просто без выбранного пути
                    uncovered = 0
                    plan_note = str(pe)[:200]

                db.execute_query(
                    "UPDATE PECO_ORDER_RUNS SET ALGORITHM = :p_alg, MONEY_RATE = :p_mr, "
                    "PLAN_COST = :p_pc WHERE ID = :p_id",
                    {'p_alg': algorithm, 'p_mr': money_rate, 'p_pc': plan_cost,
                     'p_id': run_id})

                db.execute_query(
                    "UPDATE PECO_ORDER_RUNS SET STATUS = 'done', STAGE = 'finished', "
                    "PROGRESS_PCT = 100, STATION_COUNT = :p_st, ORDER_COUNT = :p_o, "
                    "LITERS_TOTAL = :p_l, DRY_RISK_CNT = :p_dry, FINISHED_AT = SYSTIMESTAMP, "
                    "DURATION_SEC = :p_dur, MESSAGE = :p_m WHERE ID = :p_id",
                    {'p_st': len(by_station), 'p_o': orders, 'p_l': round(liters_total, 3),
                     'p_dry': dry_risk, 'p_dur': int((datetime.now() - started).total_seconds()),
                     'p_m': f'Заказов: {orders}, литров: {round(liters_total)}, '
                            f'риск сухого бака: {dry_risk}',
                     'p_id': run_id})
                db.connection.commit()
            return {'success': True, 'run_id': run_id, 'orders': orders,
                    'liters': round(liters_total, 1), 'dry_risk': dry_risk,
                    'stations': len(by_station), 'algorithm': algorithm,
                    'forecasted_tanks': fc_used, 'plan_cost': plan_cost,
                    'money_rate': money_rate}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Второй эшелон: потребность нефтебазы ====================

    @staticmethod
    def depot_requirement(import_lead_days: float = 9.0) -> Dict[str, Any]:
        """
        Хватит ли запаса нефтебазы на плечо импорта.

        Считается по видам топлива: суточная потребность всей сети против
        доступного (сверх неснижаемого) остатка базы. Если покрытия меньше
        плеча импорта плюс запас — нужно размещать импортную закупку
        СЕЙЧАС, а не когда база опустеет: судно/состав идёт две недели.
        """
        try:
            with DatabaseModel() as db:
                rows = FuelAutoOrder._rows(db.execute_query(
                    "SELECT DEPOT_ID, DEPOT_NAME, GRADE_CODE, GRADE_NAME, GRADE_COLOR, "
                    "CAPACITY_L, CURRENT_L, MIN_STOCK_L, FILL_PCT, NET_DAILY_L, DAYS_COVER_NET "
                    "FROM V_PECO_DEPOT_STOCK ORDER BY GRADE_CODE"))
            out = []
            for r in rows:
                cover = float(r.get('days_cover_net') or 0)
                daily = float(r.get('net_daily_l') or 0)
                # Сколько нужно завезти, чтобы дожить до следующего импорта с запасом
                horizon = import_lead_days * 1.5
                deficit = max(0.0, daily * horizon -
                              (float(r['current_l']) - float(r['min_stock_l'])))
                free = float(r['capacity_l']) * 0.95 - float(r['current_l'])
                r['deficit_l'] = round(min(deficit, max(0.0, free)), 1)
                r['import_due'] = 1 if cover and cover < import_lead_days else 0
                out.append(r)
            return {'success': True, 'data': out, 'import_lead_days': import_lead_days}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Планирование рейсов ====================

    @staticmethod
    def plan_trips(run_id: Optional[int] = None, username: str = 'system',
                   max_stations: int = 3) -> Dict[str, Any]:
        """
        Раскладка утверждённых заказов по бензовозам.

        Правило одно и жёсткое: одна секция — один вид топлива и один
        резервуар. Но строка заказа при этом МОЖЕТ занимать несколько
        секций: автозаказ подбирает объём как сумму секций (8000 + 8000 +
        7000 = 23 000 л), и физически это три отдельных слива.
        Поэтому на каждую задействованную секцию заводится своя остановка —
        так же, как это происходит на площадке.

        Первая версия искала ОДНУ секцию, вмещающую строку целиком,
        и молча пропускала всё, что больше самой большой секции:
        из 42 заказов в рейс попадали три.

        Станции берутся по возрастанию покрытия — сначала те, где ближе
        сухой бак. Больше max_stations точек в рейс не ставим: бензовоз
        физически не успевает объехать больше за смену.
        """
        try:
            with DatabaseModel() as db:
                sql = ("SELECT i.ID AS ITEM_ID, i.ORDER_ID, o.STATION_ID, s.NAME AS STATION_NAME, "
                       "i.GRADE_CODE, i.LITERS_ORDER, i.DAYS_TO_DRY, o.DEPOT_ID "
                       "FROM PECO_FUEL_ORDER_ITEMS i "
                       "JOIN PECO_FUEL_ORDERS o ON o.ID = i.ORDER_ID "
                       "JOIN PECO_STATIONS s ON s.ID = o.STATION_ID "
                       "WHERE o.STATUS = 'approved' AND o.TRIP_ID IS NULL")
                params: Dict[str, Any] = {}
                if run_id:
                    sql += " AND o.RUN_ID = :p_run"
                    params['p_run'] = run_id
                sql += " ORDER BY NVL(i.DAYS_TO_DRY, 99), i.LITERS_ORDER DESC"
                items = FuelAutoOrder._rows(db.execute_query(sql, params))
                if not items:
                    return {'success': False, 'error': 'Нет утверждённых заказов без рейса',
                            'status': 409}

                trucks = FuelAutoOrder._rows(db.execute_query(
                    "SELECT t.ID, t.PLATE_NO, t.DEPOT_ID, t.DRIVER_NAME FROM PECO_TRUCKS t "
                    "WHERE t.ACTIVE = 1 ORDER BY t.CAPACITY_L DESC"))
                if not trucks:
                    return {'success': False, 'error': 'Нет активных бензовозов', 'status': 409}

                comps_by_truck: Dict[int, List[Dict[str, Any]]] = {}
                for c in FuelAutoOrder._rows(db.execute_query(
                        "SELECT ID, TRUCK_ID, COMP_NO, VOLUME_L FROM PECO_TRUCK_COMPARTMENTS "
                        "WHERE ACTIVE = 1 ORDER BY TRUCK_ID, VOLUME_L DESC")):
                    comps_by_truck.setdefault(int(c['truck_id']), []).append(c)

                trips_created, stops_created, assigned = 0, 0, set()
                depart = datetime.now() + timedelta(hours=2)

                for truck in trucks:
                    free = sorted(comps_by_truck.get(int(truck['id']), []),
                                  key=lambda c: -float(c['volume_l']))
                    if not free:
                        continue
                    # План загрузки: (строка заказа, список секций под неё)
                    load: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
                    stations: set = set()
                    for it in items:
                        if it['item_id'] in assigned or not free:
                            continue
                        if (it['station_id'] not in stations
                                and len(stations) >= max_stations):
                            continue
                        need = float(it['liters_order'] or 0)
                        taken: List[Dict[str, Any]] = []
                        rest = need
                        for c in list(free):
                            vol = float(c['volume_l'])
                            if vol <= rest + 1e-6:
                                taken.append(c)
                                free.remove(c)
                                rest -= vol
                                if rest <= 1e-6:
                                    break
                        if rest > 1e-6:
                            # Целиком не набралось — возвращаем секции в парк,
                            # частичный завоз резервуара не планируем
                            free.extend(taken)
                            free.sort(key=lambda c: -float(c['volume_l']))
                            continue
                        assigned.add(it['item_id'])
                        stations.add(it['station_id'])
                        load.append((it, taken))
                    if not load:
                        continue

                    depot_id = load[0][0]['depot_id'] or truck['depot_id']
                    db.execute_query(
                        "INSERT INTO PECO_TRIPS (DEPOT_ID, TRUCK_ID, DRIVER_NAME, STATUS, "
                        "PLAN_DEPART, LITERS_TOTAL, STOPS_COUNT, CREATED_BY) "
                        "VALUES (:p_d, :p_t, :p_dr, 'planned', :p_dep, :p_l, :p_s, :p_u)",
                        {'p_d': depot_id, 'p_t': int(truck['id']),
                         'p_dr': truck.get('driver_name'), 'p_dep': depart,
                         'p_l': round(sum(float(i['liters_order']) for i, _c in load), 3),
                         'p_s': len(stations), 'p_u': username})
                    trip_id = FuelAutoOrder._rows(db.execute_query(
                        "SELECT MAX(ID) AS ID FROM PECO_TRIPS WHERE TRUCK_ID = :p_t",
                        {'p_t': int(truck['id'])}))[0]['id']

                    stop_no = 0
                    eta = depart + timedelta(minutes=45)
                    for it, comps in load:
                        for c in comps:
                            stop_no += 1
                            db.execute_query(
                                "INSERT INTO PECO_TRIP_STOPS (TRIP_ID, STOP_NO, STATION_ID, "
                                "ORDER_ID, COMP_ID, GRADE_CODE, LITERS_PLAN, PLAN_ARRIVE) "
                                "VALUES (:p_tr, :p_no, :p_st, :p_o, :p_c, :p_g, :p_l, :p_eta)",
                                {'p_tr': trip_id, 'p_no': stop_no,
                                 'p_st': int(it['station_id']), 'p_o': int(it['order_id']),
                                 'p_c': int(c['id']), 'p_g': it['grade_code'],
                                 'p_l': float(c['volume_l']), 'p_eta': eta})
                            stops_created += 1
                        db.execute_query(
                            "UPDATE PECO_FUEL_ORDERS SET TRIP_ID = :p_tr, STATUS = 'planned' "
                            "WHERE ID = :p_o", {'p_tr': trip_id, 'p_o': int(it['order_id'])})
                        eta += timedelta(minutes=50)
                    trips_created += 1
                    depart += timedelta(minutes=40)   # разнос выездов по наливным постам

                db.connection.commit()
            return {'success': True, 'trips': trips_created, 'stops': stops_created,
                    'items_assigned': len(assigned),
                    'items_left': len(items) - len(assigned)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

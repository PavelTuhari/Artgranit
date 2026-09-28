"""
Связка «прогноз → потребность → путь снабжения» для топлива.

Здесь три вещи, которых нет ни в `peco_forecast`, ни в `peco_sourcing`:
оба модуля намеренно ничего не знают про Oracle и работают с чистыми
списками чисел. Этот файл — единственное место, где они встречаются
с базой:

1. история отпуска по резервуарам → ряды для алгоритмов прогноза;
2. таблица `PECO_SUPPLY_PATHS` → источники для потока минимальной
   стоимости (импорт / рынок ↔ своя или чужая нефтебаза ↔ АЗС);
3. результат оптимизатора → обратно в строки заказа (путь и цена литра).

Oracle-объекты: sql/110_peco_algorithms.sql, sql/111_peco_paths_demo.sql
"""
from __future__ import annotations

import math
import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel
from models import peco_forecast as fc
from models import peco_sourcing as srcng

HISTORY_DAYS = 120        # сколько истории поднимаем под прогноз
DEFAULT_ALGORITHM = 'theta'
DEFAULT_MONEY_RATE = 0.14  # годовая стоимость денег для landed cost


def _rows(res) -> List[Dict[str, Any]]:
    if not res or not res.get('success'):
        return []
    cols = [c.lower() for c in (res.get('columns') or [])]
    return [dict(zip(cols, r)) for r in (res.get('data') or [])]


# ==================== История отпуска ====================


def load_tank_history(db, days: int = HISTORY_DAYS,
                      grade_code: Optional[str] = None) -> Dict[int, Dict[str, Any]]:
    """
    Ряды суточного отпуска по резервуарам.

    Ряд строится по КАЛЕНДАРЮ, а не по строкам таблицы: пропущенный день
    в `PECO_TANK_DAILY` означает «данных нет», а не «продали ноль», и если
    сдвинуть ряд на день, недельный профиль (пятница против вторника)
    развалится. Дырки закрываются медианой резервуара — консервативно
    и не тянет прогноз ни вверх, ни вниз.
    """
    sql = ("SELECT TANK_ID, SALE_DATE, LITERS FROM PECO_TANK_DAILY "
           "WHERE SALE_DATE > (SELECT MAX(SALE_DATE) - :p_d FROM PECO_TANK_DAILY)")
    params: Dict[str, Any] = {'p_d': days}
    if grade_code:
        sql += " AND GRADE_CODE = :p_g"
        params['p_g'] = grade_code
    sql += " ORDER BY TANK_ID, SALE_DATE"

    raw = _rows(db.execute_query(sql, params))
    by_tank: Dict[int, Dict[date, float]] = {}
    all_dates: List[date] = []
    for r in raw:
        d = r['sale_date']
        d = d.date() if hasattr(d, 'date') else d
        by_tank.setdefault(int(r['tank_id']), {})[d] = float(r['liters'] or 0)
        all_dates.append(d)
    if not all_dates:
        return {}
    last = max(all_dates)

    out: Dict[int, Dict[str, Any]] = {}
    for tank_id, dmap in by_tank.items():
        first = min(dmap)
        vals = sorted(dmap.values())
        med = vals[len(vals) // 2] if vals else 0.0
        series, weekdays = [], []
        cur = first
        while cur <= last:
            series.append(dmap.get(cur, med))
            weekdays.append(cur.weekday())
            cur += timedelta(days=1)
        out[tank_id] = {'series': series, 'weekdays': weekdays, 'last_date': last}
    return out


def future_weekdays(last_day: date, horizon: int) -> List[int]:
    return [(last_day + timedelta(days=i + 1)).weekday() for i in range(horizon)]


def sum_days(daily: Sequence[float], days: float) -> float:
    """
    Спрос за дробное число суток.

    Плечо развозки — 0.5 дня, а прогноз посуточный. Округлять вверх
    нельзя (заказ раздувается на половину суточного оборота сети),
    округлять вниз тоже (недоливаем), поэтому последний день берётся
    пропорционально.
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


def forecast_tank(hist: Dict[str, Any], algorithm: str, horizon: int,
                  params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Прогноз по одному резервуару. None — если истории меньше минимума
    алгоритма: в этом случае вызывающий код честно откатывается на
    среднюю за 28 дней, а не подставляет выдуманный ряд.
    """
    series = hist.get('series') or []
    if len(series) < ALGO_MIN_HISTORY.get(algorithm, 28):
        return None
    try:
        return fc.run_forecast(algorithm, series, hist['weekdays'], horizon,
                               future_weekdays(hist['last_date'], horizon), params)
    except Exception:                                            # noqa: BLE001
        return None


# Минимум истории. Значение живёт в реестре `PECO_FCT_ALGORITHMS` — это
# то же число, которое видит пользователь в карточке алгоритма. Здесь
# только КЭШ на время процесса: ходить в Oracle на каждый из 184 баков
# нельзя, а расходиться с тем, что показано в интерфейсе, — тем более.
# Словарь ниже — запасной вариант на случай, когда реестр ещё не развёрнут.
_MIN_HISTORY_FALLBACK = {'theta': 28, 'croston_sba': 21, 'conformal': 35, 'gbt': 45}
ALGO_MIN_HISTORY = dict(_MIN_HISTORY_FALLBACK)
_min_history_loaded = False


def load_min_history(db) -> Dict[str, int]:
    global _min_history_loaded
    if _min_history_loaded:
        return ALGO_MIN_HISTORY
    rows = _rows(db.execute_query(
        "SELECT CODE, MIN_HISTORY FROM PECO_FCT_ALGORITHMS WHERE IS_ACTIVE = 1"))
    for r in rows:
        if r.get('min_history'):
            ALGO_MIN_HISTORY[r['code']] = int(r['min_history'])
    _min_history_loaded = bool(rows)
    return ALGO_MIN_HISTORY


# ==================== Пути снабжения ====================


def load_paths(db, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    """Пути из Oracle в том виде, в каком их ждёт оптимизатор потока."""
    sql = "SELECT * FROM V_PECO_SUPPLY_PATHS WHERE IS_ACTIVE = 1"
    params: Dict[str, Any] = {}
    if kind:
        sql += " AND KIND = :p_k"
        params['p_k'] = kind
    sql += " ORDER BY KIND, COST_PER_L_BASE"
    out = []
    for r in _rows(db.execute_query(sql, params)):
        out.append({
            'code': r['code'], 'kind': r['kind'], 'source_code': r['source_code'],
            'grade_code': r.get('grade_code'),
            'depot_id': int(r['depot_id']) if r.get('depot_id') else None,
            'depot_name': r.get('depot_name'),
            'depot_is_own': int(r.get('depot_is_own') or 0),
            'station_id': int(r['station_id']) if r.get('station_id') else None,
            # Для развозки целевая точка — станция, для пополнения — база
            'target_id': (int(r['station_id']) if r.get('station_id')
                          else (int(r['depot_id']) if r['kind'] == 'replenishment'
                                and r.get('depot_id') else None)),
            'lead_days': float(r.get('lead_days') or 0),
            'price_per_l': float(r.get('price_per_l') or 0),
            'transport_per_l': float(r.get('transport_per_l') or 0),
            'handling_per_l': float(r.get('handling_per_l') or 0),
            'duty_per_l': float(r.get('duty_per_l') or 0),
            'available_l': float(r.get('available_l') or 0),
            'min_lot_l': float(r.get('min_lot_l') or 0),
            'name_ru': r.get('name_ru'), 'name_ro': r.get('name_ro'),
            'name_en': r.get('name_en'), 'is_import': int(r.get('is_import') or 0),
        })
    return out


def station_demands(db, run_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Потребности станций из строк автозаказа (draft/approved)."""
    sql = ("SELECT i.ID, i.ORDER_ID, i.STATION_ID, i.TANK_ID, i.GRADE_CODE, "
           "i.LITERS_ORDER, i.DAYS_TO_DRY, o.RUN_ID "
           "FROM PECO_FUEL_ORDER_ITEMS i JOIN PECO_FUEL_ORDERS o ON o.ID = i.ORDER_ID "
           "WHERE o.STATUS IN ('draft','approved') AND i.LITERS_ORDER > 0")
    params: Dict[str, Any] = {}
    if run_id:
        sql += " AND o.RUN_ID = :p_r"
        params['p_r'] = run_id
    out = []
    for r in _rows(db.execute_query(sql, params)):
        out.append({
            'key': f"item:{int(r['id'])}", 'item_id': int(r['id']),
            'order_id': int(r['order_id']), 'target_id': int(r['station_id']),
            'grade_code': r['grade_code'],
            'liters': float(r['liters_order'] or 0),
            'days_to_dry': float(r['days_to_dry']) if r.get('days_to_dry') is not None else None,
        })
    return out


def depot_demands(db, import_lead_days: float = 9.0) -> List[Dict[str, Any]]:
    """
    Потребности НЕФТЕБАЗ (второй эшелон): дефицит покрытия сети
    на горизонте плеча закупки, ограниченный свободной ёмкостью базы.
    """
    rows = _rows(db.execute_query(
        "SELECT DEPOT_ID, DEPOT_NAME, GRADE_CODE, CAPACITY_L, CURRENT_L, MIN_STOCK_L, "
        "NET_DAILY_L, DAYS_COVER_NET FROM V_PECO_DEPOT_STOCK ORDER BY DEPOT_ID, GRADE_CODE"))
    out = []
    for r in rows:
        daily = float(r.get('net_daily_l') or 0)
        cover = float(r.get('days_cover_net') or 0)
        cap95 = float(r['capacity_l'] or 0) * 0.95
        current = float(r['current_l'] or 0)
        min_stock = float(r['min_stock_l'] or 0)
        avail = current - min_stock

        # Свободная ёмкость считается ДВАЖДЫ и по-разному — это тот же
        # принцип, что и для резервуара АЗС (см. peco_autoorder, п.1).
        # Срочная закупка приезжает через двое суток, к этому моменту
        # база отгрузит немного. Импорт идёт девять суток, и к его приходу
        # места заметно больше. Считать импорт по сегодняшней ёмкости —
        # значит не заказывать его почти никогда: база редко бывает пустой.
        free_now = max(0.0, cap95 - current)
        level_at_import = max(min_stock, current - daily * import_lead_days)
        free_at_import = max(0.0, cap95 - level_at_import)

        deficit = max(0.0, daily * import_lead_days * 1.5 - avail)
        if deficit < 1000:
            continue

        # Потребность базы разделяется на СРОЧНУЮ и БАЗОВУЮ, и это не
        # формальность. Единой строкой «нужно 738 тысяч литров к сроку
        # покрытия» весь объём уходил на внутренний рынок: импорт с плечом
        # девять дней не успевал ни к какому сроку и проигрывал всегда,
        # хотя дешевле на полтора лея с литра. В жизни закупщик делит:
        # доживить сеть до прихода импорта покупает на рынке, а основной
        # объём заказывает импортом заранее.
        urgent = min(deficit, free_now, max(0.0, daily * import_lead_days - avail))
        base = min(deficit - urgent, max(0.0, free_at_import - urgent))
        key = f"depot:{int(r['depot_id'])}:{r['grade_code']}"
        common = {'target_id': int(r['depot_id']), 'depot_name': r.get('depot_name'),
                  'grade_code': r['grade_code'], 'capacity_l': float(r['capacity_l'] or 0)}
        if urgent >= 1000:
            out.append(dict(common, key=key + ':urgent', liters=round(urgent, 1),
                            part='urgent',
                            # Срок — собственное покрытие базы: столько
                            # она проживёт без завоза
                            days_to_dry=round(cover, 2) if cover else None))
        if base >= 1000:
            out.append(dict(common, key=key + ':base', liters=round(base, 1),
                            part='base',
                            # У базового объёма срока нет: его и заказывают
                            # заранее, чтобы приехал к моменту, когда
                            # срочная закупка закончится
                            days_to_dry=None))
    return out


# ==================== План снабжения целиком ====================


def build_plan(run_id: Optional[int] = None, money_rate: float = DEFAULT_MONEY_RATE,
               import_lead_days: float = 9.0) -> Dict[str, Any]:
    try:
        with DatabaseModel() as db:
            if not run_id:
                # По умолчанию — ПОСЛЕДНИЙ прогон, а не «все черновики
                # разом»: незакрытые заказы прошлых прогонов дублируют
                # потребность тех же баков, и сумма плана раздувается
                # кратно числу прогонов.
                last = _rows(db.execute_query(
                    "SELECT MAX(RUN_ID) AS RUN_ID FROM PECO_FUEL_ORDERS "
                    "WHERE STATUS IN ('draft','approved')"))
                run_id = int(last[0]['run_id']) if last and last[0].get('run_id') else None
            dem = station_demands(db, run_id)
            dist_src = load_paths(db, 'distribution')
            dep_need = depot_demands(db, import_lead_days)
            repl_src = load_paths(db, 'replenishment')
        plan = srcng.solve_supply_plan(dem, dist_src, dep_need, repl_src, money_rate)
        # Литры и стоимость понятны только вместе с адресом: подшиваем имена
        by_key = {d['key']: d for d in dem}
        by_dep = {d['key']: d for d in dep_need}
        for a in (plan.get('distribution') or {}).get('allocations', []):
            src = by_key.get(a['key'])
            if src:
                a['item_id'] = src.get('item_id')
                a['order_id'] = src.get('order_id')
        for a in (plan.get('replenishment') or {}).get('allocations', []):
            src = by_dep.get(a['key'])
            if src:
                a['depot_name'] = src.get('depot_name')
        plan['money_rate'] = money_rate
        plan['run_id'] = run_id
        return plan
    except Exception as e:                                       # noqa: BLE001
        return {'success': False, 'error': str(e)}


def apply_plan_to_items(db, allocations: List[Dict[str, Any]]) -> int:
    """
    Путь и цена литра — обратно в строку заказа.

    Строка может закрываться НЕСКОЛЬКИМИ путями (не хватило остатка своей
    базы — добор с рынка), поэтому в строке фиксируется путь с наибольшим
    объёмом, а цена литра — средневзвешенная по всем путям строки.
    Иначе отчёт «во что обошёлся завоз» врал бы на смешанных строках.
    """
    agg: Dict[int, Dict[str, Any]] = {}
    for a in allocations:
        item_id = a.get('item_id')
        if not item_id:
            continue
        cur = agg.setdefault(int(item_id), {'liters': 0.0, 'amount': 0.0,
                                            'best_l': 0.0, 'path': None})
        cur['liters'] += float(a['liters'])
        cur['amount'] += float(a['amount'])
        if float(a['liters']) > cur['best_l']:
            cur['best_l'] = float(a['liters'])
            cur['path'] = a['path_code']
    n = 0
    for item_id, v in agg.items():
        cpl = (v['amount'] / v['liters']) if v['liters'] > 0 else None
        db.execute_query(
            "UPDATE PECO_FUEL_ORDER_ITEMS SET PATH_CODE = :p_p, COST_PER_L = :p_c "
            "WHERE ID = :p_id",
            {'p_p': v['path'], 'p_c': round(cpl, 4) if cpl else None, 'p_id': item_id})
        n += 1
    return n


def explain_demand(station_id: int, grade_code: str, liters: float,
                   days_to_dry: Optional[float] = None,
                   money_rate: float = DEFAULT_MONEY_RATE) -> Dict[str, Any]:
    """Разбор одной потребности по всем путям — «почему выбрано именно это»."""
    try:
        with DatabaseModel() as db:
            paths = [p for p in load_paths(db, 'distribution')
                     if not p.get('station_id') or p['station_id'] == int(station_id)]
        dem = {'key': 'ask', 'target_id': int(station_id), 'grade_code': grade_code,
               'liters': float(liters or 0), 'days_to_dry': days_to_dry}
        return {'success': True, 'demand': dem,
                'data': srcng.compare_paths(dem, paths, money_rate)}
    except Exception as e:                                       # noqa: BLE001
        return {'success': False, 'error': str(e)}


# ==================== Backtest алгоритмов ====================


def run_backtests(algorithms: Optional[List[str]] = None, horizon: int = 3,
                  folds: int = 8, grade_code: Optional[str] = None,
                  max_tanks: int = 40, username: str = 'system') -> Dict[str, Any]:
    """
    Сравнение алгоритмов на реальной истории отпуска.

    Считается ошибка НАКОПЛЕННОГО спроса за горизонт: заказ закрывает
    окно до следующего завоза целиком, и промах понедельника, погашенный
    вторником, для бака безразличен. Результат ложится в
    `PECO_FCT_BACKTESTS` — иначе выбор алгоритма остаётся спором,
    а не измерением.
    """
    from datetime import datetime
    algos = algorithms or list(fc.ALGO_ORDER)
    started = datetime.now()
    try:
        with DatabaseModel() as db:
            load_min_history(db)
            hist = load_tank_history(db, HISTORY_DAYS, grade_code)
            tank_ids = sorted(hist)[:max_tanks]
            results = []
            for algo in algos:
                errs, pcts, signed, sq, used = [], [], [], [], 0
                for tid in tank_ids:
                    h = hist[tid]
                    if len(h['series']) < ALGO_MIN_HISTORY.get(algo, 28) + horizon:
                        continue
                    r = fc.backtest(algo, h['series'], h['weekdays'], horizon, folds)
                    if not r.get('success') or r.get('mape') is None:
                        continue
                    used += 1
                    errs.append(float(r['mae']))
                    pcts.append(float(r['mape']))
                    signed.append(float(r['bias_pct']))
                    # RMSE усредняем по квадратам, а не по корням: среднее
                    # корней меньше корня среднего и приукрашивает разброс
                    sq.append(float(r['rmse']) ** 2)
                if not used:
                    continue
                mae = sum(errs) / used
                mape = sum(pcts) / used
                bias = sum(signed) / used
                rmse = math.sqrt(sum(sq) / used)
                db.execute_query(
                    "INSERT INTO PECO_FCT_BACKTESTS (ALGORITHM, GRADE_CODE, HORIZON, FOLDS, "
                    "TANK_COUNT, MAPE, MAE, RMSE, BIAS_PCT, DURATION_SEC, USERNAME) "
                    "VALUES (:p_a, :p_g, :p_h, :p_f, :p_t, :p_mp, :p_ma, :p_rm, :p_b, :p_d, :p_u)",
                    {'p_a': algo, 'p_g': grade_code, 'p_h': horizon, 'p_f': folds,
                     'p_t': used, 'p_mp': round(mape, 4), 'p_ma': round(mae, 4),
                     'p_rm': round(rmse, 4), 'p_b': round(bias, 4),
                     'p_d': int((datetime.now() - started).total_seconds()),
                     'p_u': username})
                results.append({'algorithm': algo, 'tanks': used, 'mape': round(mape, 2),
                                'mae': round(mae, 1), 'rmse': round(rmse, 1),
                                'bias_pct': round(bias, 2)})
            db.connection.commit()
        results.sort(key=lambda x: x['mape'])
        return {'success': True, 'data': results, 'horizon': horizon, 'folds': folds,
                'grade_code': grade_code,
                'best': results[0]['algorithm'] if results else None,
                'duration_sec': int((datetime.now() - started).total_seconds())}
    except Exception as e:                                       # noqa: BLE001
        return {'success': False, 'error': str(e)}

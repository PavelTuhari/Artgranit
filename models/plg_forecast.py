"""
Прогнозирование заказов для модуля «Планограммы».

Четыре алгоритма, каждый настраивается через модель (PLG_FCT_MODELS):

  sma           скользящее / взвешенное скользящее среднее
  ses           простое экспоненциальное сглаживание (Brown)
  holt_winters  тройное экспоненциальное сглаживание: уровень + тренд + сезонность
  promo_reg     базовая линия по дням без акций × promo-uplift × индекс трафика зоны

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
    if algorithm == 'promo_reg':
        return fn(series, horizon, params, ctx)
    return fn(series, horizon, params)


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
                      "QTY_FORECAST, QTY_ACTUAL, ABS_ERROR, SAFETY_STOCK, STOCK_ON_HAND, ORDER_QTY) "
                      "VALUES (PLG_FCT_RESULTS_SEQ.NEXTVAL, :1, :2, :3, :4, :5, :6, :7, :8, :9, :10)")
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
                                   round(order, 3) if h == 0 else 0.0))
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

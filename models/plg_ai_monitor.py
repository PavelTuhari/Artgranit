"""
ИИ-мониторинг продаж модуля «Планограммы».

Один прогон делает две вещи:

  1. Считает ПРИЗНАКИ по каждой паре «магазин × SKU» — витрину данных
     (PLG_AI_FEATURES), которая выгружается наружу для обучения моделей
     и одновременно объясняет человеку поведение товара.
  2. Прогоняет ДЕТЕКТОРЫ по этим признакам и пишет сигналы (PLG_AI_SIGNALS):
     риск out-of-stock, всплеск, провал, риск списаний фреша, дрейф смещения
     модели прогноза, мёртвый запас.

Про честность термина «ИИ». Детекторы здесь — статистика, а не нейросеть:
z-оценки против недельной базы, покрытие остатком, пороги. Это сделано
намеренно: сигнал, который нельзя объяснить одной фразой, оператор глушит
через неделю. Витрина признаков — это как раз мост к настоящему ML:
на ней обучаются модели из дорожной карты (см. AUTO_ORDER_GUIDE.md),
а детекторы задают базовую линию, которую ML обязан бить, чтобы жить.

Oracle-объекты: sql/96_plg_ai_monitor.sql
"""
from __future__ import annotations

import math
import os
import sys
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseConnection

BATCH = 5000
WINDOW = 28          # окно признаков, дней
RECENT = 7           # окно «свежего уровня»

# Пороги детекторов. Вынесены в константы, а не размазаны по коду:
# их придётся крутить под сеть, и искать их нужно в одном месте.
TH = {
    'oos_cover_crit': 1.0,    # покрытие остатком меньше суток — crit
    'oos_cover_warn': 2.0,    # меньше двух суток — warn
    'spike_z': 2.5,           # всплеск: z-оценка последнего дня против базы дня недели
    'spike_min_qty': 5.0,     # и не меньше 5 единиц — иначе шум на малых числах
    'drop_ratio': 0.3,        # провал: последний день < 30 % базы
    'drop_min_base': 3.0,     # база не меньше 3 единиц в день
    'waste_over_target': 1.5, # списание фреша в 1.5 раза выше цели категории
    'bias_warn': 8.0,         # |смещение| модели, %
    'bias_crit': 15.0,
    'dead_days': 21,          # нет продаж столько дней при остатке > 0
}


class MonitorCancelled(Exception):
    """Прогон остановлен оператором."""


def _squash(value: float, scale: float) -> float:
    """
    x / (x + scale) — мягкая нормировка в [0, 1).

    Выбрана вместо min-max: у неё нет зависимости от выборки (вектор SKU
    не меняется от того, какие ещё товары попали в прогон), а хвосты
    сжимаются плавно — «продажи 500/день» и «продажи 900/день» дают
    близкие координаты, что для СРАВНЕНИЯ ПОВЕДЕНИЯ и нужно.
    """
    v = max(0.0, float(value))
    return v / (v + scale)


def behavior_vector(avg7: float, mean28: float, med28: float, sigma: float,
                    cv: float, trend: float, weekend_lift: float,
                    promo_uplift: float, oos_days: int, cover: float,
                    waste_pct: Optional[float], is_fresh: int) -> str:
    """
    Вектор поведения SKU: 12 нормированных координат для колонки VECTOR.

    Состав подобран так, чтобы близость векторов означала «товары живут
    одинаково»: уровень спроса, стабильность, тренд, недельный рисунок,
    реакция на промо, доступность, запас, списания. Цена сюда не входит
    сознательно — дорогой и дешёвый товар могут вести себя одинаково,
    и для прогноза новинки по аналогам это ценнее ценового соседства.
    """
    coords = [
        _squash(avg7, 10.0),                       # уровень спроса, свежий
        _squash(mean28, 10.0),                     # уровень спроса, месяц
        _squash(med28, 10.0),                      # медианный уровень
        _squash(sigma, 5.0),                       # разброс
        min(1.0, cv / 2.0),                        # коэффициент вариации
        max(0.0, min(1.0, 0.5 + trend / 200.0)),   # тренд: −100%…+100% → 0…1
        max(0.0, min(1.0, weekend_lift / 3.0)),    # подъём выходных
        max(0.0, min(1.0, (promo_uplift - 1.0) / 3.0)),  # промо-аплифт
        min(1.0, oos_days / float(WINDOW)),        # доля дней OOS
        _squash(cover, 7.0),                       # покрытие остатком
        min(1.0, (waste_pct or 0.0) / 20.0),       # ожидаемое списание
        float(is_fresh),                           # фреш-флаг
    ]
    return '[' + ','.join(f'{c:.5f}' for c in coords) + ']'


def _median(vals: List[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if not n:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


class AiMonitorEngine:
    """Один экземпляр = один прогон мониторинга."""

    _active: Dict[int, 'AiMonitorEngine'] = {}

    def __init__(self, run_id: int, dataset_id: Optional[int],
                 store_id: Optional[int], username: str):
        self.run_id = run_id
        self.dataset_id = dataset_id
        self.store_id = store_id
        self.username = username
        self.cancelled = False
        self.signal_count = 0
        self.feature_count = 0
        self.conn = None

    # ==================== Запуск и жизненный цикл ====================

    @staticmethod
    def launch(dataset_id: Optional[int], store_id: Optional[int],
               username: str) -> Dict[str, Any]:
        conn = DatabaseConnection.get_connection()
        try:
            cur = conn.cursor()
            out = cur.var(int)
            cur.execute(
                "INSERT INTO PLG_AI_RUNS (DATASET_ID, STORE_ID, USERNAME) "
                "VALUES (:p_ds, :p_st, :p_user) RETURNING ID INTO :p_id",
                {'p_ds': dataset_id, 'p_st': store_id, 'p_user': username, 'p_id': out})
            run_id = int(out.getvalue()[0])
            conn.commit()
        finally:
            conn.close()
        engine = AiMonitorEngine(run_id, dataset_id, store_id, username)
        AiMonitorEngine._active[run_id] = engine
        threading.Thread(target=engine._run, daemon=True,
                         name=f'plg-ai-monitor-{run_id}').start()
        return {'success': True, 'run_id': run_id}

    @staticmethod
    def cancel(run_id: int) -> Dict[str, Any]:
        engine = AiMonitorEngine._active.get(run_id)
        if engine:
            engine.cancelled = True
            return {'success': True}
        return {'success': False, 'error': 'Прогон не активен'}

    def _check_cancel(self):
        if self.cancelled:
            raise MonitorCancelled()

    def _fetch(self, sql: str, params: Optional[Dict] = None) -> List[Tuple]:
        cur = self.conn.cursor()
        cur.execute(sql, params or {})
        return cur.fetchall()

    def _progress(self, stage: str, pct: int):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE PLG_AI_RUNS SET STAGE = :p_stage, PROGRESS_PCT = :p_pct "
            "WHERE ID = :p_id",
            {'p_stage': stage[:60], 'p_pct': pct, 'p_id': self.run_id})
        self.conn.commit()

    def _finish(self, status: str, message: str = ''):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE PLG_AI_RUNS SET STATUS = :p_st, PROGRESS_PCT = "
            "CASE WHEN :p_st2 = 'done' THEN 100 ELSE PROGRESS_PCT END, "
            "SIGNAL_COUNT = :p_sig, FEATURE_COUNT = :p_feat, "
            "DURATION_SEC = ROUND((CAST(SYSTIMESTAMP AS DATE) - CAST(STARTED_AT AS DATE)) * 86400), "
            "MESSAGE = :p_msg, FINISHED_AT = SYSTIMESTAMP WHERE ID = :p_id",
            {'p_st': status, 'p_st2': status, 'p_sig': self.signal_count,
             'p_feat': self.feature_count, 'p_msg': message[:2000], 'p_id': self.run_id})
        self.conn.commit()

    def _run(self):
        start = time.time()
        try:
            self.conn = DatabaseConnection.get_connection()
            self._execute()
            self._finish('done',
                         f'Признаков: {self.feature_count}, сигналов: {self.signal_count}')
        except MonitorCancelled:
            self._finish('cancelled', 'Остановлено оператором')
        except Exception as e:                                   # noqa: BLE001
            try:
                self._finish('failed', str(e))
            except Exception:                                    # noqa: BLE001
                pass
        finally:
            AiMonitorEngine._active.pop(self.run_id, None)
            if self.conn:
                self.conn.close()
            _ = time.time() - start

    # ==================== Основной расчёт ====================

    def _stores(self) -> List[int]:
        if self.store_id:
            return [int(self.store_id)]
        sql = "SELECT ID FROM PLG_STORES"
        if self.dataset_id:
            sql += " WHERE DATASET_ID = :p_ds"
            return [int(r[0]) for r in self._fetch(sql, {'p_ds': self.dataset_id})]
        return [int(r[0]) for r in self._fetch(sql)]

    def _execute(self):
        stores = self._stores()
        if not stores:
            raise ValueError('В выбранном срезе нет магазинов')

        row = self._fetch(
            "SELECT MAX(SALES_DATE) FROM PLG_SALES_DAILY WHERE STORE_ID IN (%s)"
            % ','.join(str(s) for s in stores))
        last_date = row[0][0] if row and row[0][0] else None
        if not last_date:
            raise ValueError('Нет истории продаж: сначала сгенерируйте набор данных')
        last_date = last_date.date() if hasattr(last_date, 'date') else last_date
        date_from = last_date - timedelta(days=WINDOW - 1)

        # Смещение моделей по последнему backtest — один запрос на весь прогон
        bias_by_model = {}
        for (code, bias) in self._fetch(
                "SELECT m.CODE, r.BIAS_PCT FROM PLG_FCT_RUNS r "
                "JOIN PLG_FCT_MODELS m ON m.ID = r.MODEL_ID "
                "WHERE r.RUN_MODE = 'backtest' AND r.STATUS = 'done' "
                "AND r.BIAS_PCT IS NOT NULL "
                "AND r.STARTED_AT = (SELECT MAX(r2.STARTED_AT) FROM PLG_FCT_RUNS r2 "
                "  WHERE r2.MODEL_ID = r.MODEL_ID AND r2.RUN_MODE = 'backtest' "
                "  AND r2.STATUS = 'done')"):
            bias_by_model[code] = float(bias)

        # Ожидаемое списание фреша из последних фреш-прогонов
        waste_by_key: Dict[Tuple[int, int], float] = {}
        for (st, pid, order_qty, waste) in self._fetch(
                "SELECT res.STORE_ID, res.PRODUCT_ID, res.ORDER_QTY, res.WASTE_FORECAST "
                "FROM PLG_FCT_RESULTS res WHERE res.WASTE_FORECAST IS NOT NULL "
                "AND res.ORDER_QTY > 0 AND res.RUN_ID IN ("
                "  SELECT MAX(r.ID) FROM PLG_FCT_RUNS r "
                "  JOIN PLG_FCT_MODELS m ON m.ID = r.MODEL_ID "
                "  WHERE m.ALGORITHM = 'fresh' AND r.STATUS = 'done' "
                "  AND r.RUN_MODE = 'forecast' GROUP BY r.MODEL_ID)"):
            waste_by_key[(int(st), int(pid))] = float(waste) / float(order_qty) * 100

        waste_target = {}
        for (cid, target) in self._fetch(
                "SELECT CATEGORY_ID, WASTE_TARGET_PCT FROM PLG_FRESH_PROFILES "
                "WHERE IS_ACTIVE = 1"):
            waste_target[int(cid)] = float(target or 3)

        feat_sql = (
            "INSERT INTO PLG_AI_FEATURES (RUN_ID, STORE_ID, PRODUCT_ID, SNAPSHOT_DATE, "
            "AVG_QTY_7, AVG_QTY_28, MEDIAN_QTY_28, SIGMA_28, CV, TREND_PCT, WEEKEND_LIFT, "
            "PROMO_UPLIFT, PROMO_DAYS_28, OOS_DAYS_28, STOCK_END, STOCK_COVER_DAYS, "
            "WASTE_PCT, FORECAST_BIAS, PRICE, MARGIN_PCT, ABC_CLASS, XYZ_CLASS, IS_FRESH, "
            "EMB) "
            "VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13, :14, :15, "
            ":16, :17, :18, :19, :20, :21, :22, :23, :24)")
        sig_sql = (
            "INSERT INTO PLG_AI_SIGNALS (RUN_ID, SIGNAL_TYPE, SEVERITY, STORE_ID, "
            "PRODUCT_ID, CATEGORY_ID, METRIC_VALUE, BASELINE_VALUE, DELTA_PCT, "
            "MESSAGE_RU, MESSAGE_RO, MESSAGE_EN, ACTION_HINT) "
            "VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9, :10, :11, :12, :13)")

        # Смещение модели — сигнал уровня сети, один на модель, не на SKU
        for code, bias in bias_by_model.items():
            if abs(bias) < TH['bias_warn']:
                continue
            sev = 'crit' if abs(bias) >= TH['bias_crit'] else 'warn'
            direction_ru = 'завышает' if bias > 0 else 'занижает'
            direction_ro = 'supraestimează' if bias > 0 else 'subestimează'
            direction_en = 'over-forecasts' if bias > 0 else 'under-forecasts'
            cur = self.conn.cursor()
            cur.execute(sig_sql, (
                self.run_id, 'bias_drift', sev, stores[0], None, None,
                round(bias, 2), 0, round(bias, 2),
                f'Модель {code} системно {direction_ru} спрос на {abs(bias):.1f}% — пересмотрите параметры',
                f'Modelul {code} {direction_ro} sistematic cererea cu {abs(bias):.1f}%',
                f'Model {code} systematically {direction_en} demand by {abs(bias):.1f}%',
                'forecast'))
            self.signal_count += 1
        self.conn.commit()

        feat_buf: List[Tuple] = []
        sig_buf: List[Tuple] = []

        for si, store_id in enumerate(stores):
            self._check_cancel()
            self._progress(f'store {store_id}', int(si / len(stores) * 100))

            meta = {int(r[0]): (r[1], float(r[2] or 0), float(r[3] or 0), r[4],
                                int(r[5] or 0), int(r[6] or 0))
                    for r in self._fetch(
                        "SELECT p.ID, p.ABC_CLASS, p.PRICE, p.COST_PRICE, p.CATEGORY_ID, "
                        "NVL(p.IS_FRESH,0), NVL(p.ORDER_MULTIPLE,1) FROM PLG_PRODUCTS p "
                        "WHERE p.ID IN (SELECT DISTINCT PRODUCT_ID FROM PLG_SALES_DAILY "
                        "WHERE STORE_ID = :p_st)", {'p_st': store_id})}

            rows = self._fetch(
                "SELECT PRODUCT_ID, SALES_DATE, NVL(QTY,0), NVL(IS_OOS,0), "
                "CASE WHEN PROMO_ID IS NULL THEN 0 ELSE 1 END, STOCK_END "
                "FROM PLG_SALES_DAILY WHERE STORE_ID = :p_st "
                "AND SALES_DATE BETWEEN :p_from AND :p_to "
                "ORDER BY PRODUCT_ID, SALES_DATE",
                {'p_st': store_id, 'p_from': date_from, 'p_to': last_date})

            series: Dict[int, List[Tuple[date, float, int, int, float]]] = {}
            for (pid, d, qty, oos, promo, stock) in rows:
                dd = d.date() if hasattr(d, 'date') else d
                series.setdefault(int(pid), []).append(
                    (dd, float(qty), int(oos), int(promo), float(stock or 0)))

            for pid, hist in series.items():
                self._check_cancel()
                if len(hist) < RECENT:
                    continue
                qtys = [h[1] for h in hist]
                mean28 = sum(qtys) / len(qtys)
                med28 = _median(qtys)
                var = sum((v - mean28) ** 2 for v in qtys) / len(qtys)
                sigma = math.sqrt(var)
                cv = sigma / mean28 if mean28 > 0 else 0.0
                avg7 = sum(qtys[-RECENT:]) / RECENT
                trend = (avg7 / mean28 - 1) * 100 if mean28 > 0 else 0.0

                wk = [h[1] for h in hist if h[0].weekday() >= 5]
                wd = [h[1] for h in hist if h[0].weekday() < 5]
                weekend_lift = (sum(wk) / len(wk)) / (sum(wd) / len(wd)) \
                    if wk and wd and sum(wd) > 0 else 1.0

                promo_q = [h[1] for h in hist if h[3]]
                plain_q = [h[1] for h in hist if not h[3]]
                promo_uplift = (_median(promo_q) / _median(plain_q)) \
                    if promo_q and plain_q and _median(plain_q) > 0 else 1.0

                oos_days = sum(1 for h in hist if h[2])
                stock_end = hist[-1][4]
                cover = stock_end / avg7 if avg7 > 0 else 99.0

                abc, price, cost, cat_id, is_fresh, _pack = meta.get(
                    pid, (None, 0.0, 0.0, None, 0, 1))
                margin = (price - cost) / price * 100 if price and cost else None
                xyz = 'X' if cv < 0.35 else ('Y' if cv < 0.8 else 'Z')
                waste_pct = waste_by_key.get((store_id, pid))
                bias = None   # смещение уровня сети хранится в сигналах, не в признаке SKU

                feat_buf.append((
                    self.run_id, store_id, pid, last_date,
                    round(avg7, 3), round(mean28, 3), round(med28, 3), round(sigma, 3),
                    round(cv, 4), round(trend, 2), round(weekend_lift, 4),
                    round(promo_uplift, 4), sum(1 for h in hist if h[3]), oos_days,
                    round(stock_end, 3), round(min(cover, 99.0), 2),
                    round(waste_pct, 3) if waste_pct is not None else None,
                    bias, price or None,
                    round(margin, 2) if margin is not None else None,
                    abc, xyz, is_fresh,
                    behavior_vector(avg7, mean28, med28, sigma, cv, trend,
                                    weekend_lift, promo_uplift, oos_days, cover,
                                    waste_pct, is_fresh)))
                self.feature_count += 1

                # ---------- Детекторы ----------
                name_key = (store_id, pid, cat_id)

                # Риск out-of-stock: остаток не покрывает спрос до завтра
                if avg7 > 0.3 and cover < TH['oos_cover_warn'] and not hist[-1][2]:
                    sev = 'crit' if cover < TH['oos_cover_crit'] else 'warn'
                    sig_buf.append((self.run_id, 'oos_risk', sev, store_id, pid, cat_id,
                                    round(stock_end, 2), round(avg7, 2),
                                    round((cover - 1) * 100, 1),
                                    f'Остатка {stock_end:.0f} ед. хватит на {cover:.1f} дн. при спросе {avg7:.1f}/день',
                                    f'Stocul de {stock_end:.0f} un. ajunge pentru {cover:.1f} zile la cererea {avg7:.1f}/zi',
                                    f'Stock of {stock_end:.0f} covers {cover:.1f} days at {avg7:.1f}/day demand',
                                    'forecast'))

                # Всплеск и провал: последний день против базы этого дня недели
                last_day, last_qty = hist[-1][0], hist[-1][1]
                same_dow = [h[1] for h in hist[:-1] if h[0].weekday() == last_day.weekday()
                            and not h[2]]
                if len(same_dow) >= 2:
                    base = _median(same_dow)
                    s_dow = math.sqrt(sum((v - base) ** 2 for v in same_dow) / len(same_dow))
                    # Двойной порог: и статистический (z), и практический (×1.6).
                    # На медленных SKU сигма меньше единицы, и «5 против 4»
                    # проходит по z-оценке, оставаясь бытовым шумом.
                    if (s_dow > 0 and last_qty > base + TH['spike_z'] * s_dow
                            and last_qty >= max(TH['spike_min_qty'], base * 1.6)
                            and not hist[-1][3]):
                        delta = (last_qty / base - 1) * 100 if base > 0 else 100.0
                        sig_buf.append((self.run_id, 'spike', 'info', store_id, pid, cat_id,
                                        round(last_qty, 2), round(base, 2), round(delta, 1),
                                        f'Продажи {last_qty:.0f} против обычных {base:.0f} для этого дня недели — без акции',
                                        f'Vânzări {last_qty:.0f} față de {base:.0f} obișnuite pentru această zi — fără promoție',
                                        f'Sales {last_qty:.0f} vs usual {base:.0f} for this weekday — no promo running',
                                        'analytics'))
                    elif (base >= TH['drop_min_base'] and last_qty < base * TH['drop_ratio']
                          and not hist[-1][2]):
                        delta = (last_qty / base - 1) * 100
                        sig_buf.append((self.run_id, 'drop', 'warn', store_id, pid, cat_id,
                                        round(last_qty, 2), round(base, 2), round(delta, 1),
                                        f'Продажи упали до {last_qty:.0f} при базе {base:.0f} — товар есть, спроса нет: проверьте выкладку и цену',
                                        f'Vânzările au scăzut la {last_qty:.0f} față de {base:.0f} — marfa există, cererea nu: verificați expunerea și prețul',
                                        f'Sales dropped to {last_qty:.0f} vs base {base:.0f} — stock present, demand gone: check facing and price',
                                        'storemap'))

                # Риск списаний фреша: прогнозное списание выше цели категории
                if waste_pct is not None and cat_id in waste_target:
                    target = waste_target[cat_id]
                    if waste_pct > target * TH['waste_over_target']:
                        sig_buf.append((self.run_id, 'waste_risk', 'warn', store_id, pid,
                                        cat_id, round(waste_pct, 2), target,
                                        round(waste_pct - target, 2),
                                        f'Ожидаемое списание {waste_pct:.1f}% при цели {target:.1f}% — пересмотрите фейсинги или график поставки',
                                        f'Rebut estimat {waste_pct:.1f}% față de ținta {target:.1f}% — revizuiți expunerea sau graficul',
                                        f'Expected waste {waste_pct:.1f}% vs {target:.1f}% target — revisit facings or the delivery schedule',
                                        'fresh'))

                # Мёртвый запас: остаток есть, продаж нет
                tail = [h for h in hist if h[0] > last_date - timedelta(days=TH['dead_days'])]
                if (stock_end > 0 and tail and all(h[1] == 0 for h in tail)
                        and len(tail) >= TH['dead_days'] - 2):
                    sig_buf.append((self.run_id, 'dead_stock', 'warn', store_id, pid, cat_id,
                                    round(stock_end, 2), 0, None,
                                    f'{TH["dead_days"]} дней без продаж при остатке {stock_end:.0f} ед. — кандидат на уценку или вывод',
                                    f'{TH["dead_days"]} zile fără vânzări cu stoc {stock_end:.0f} — candidat la reducere sau delistare',
                                    f'{TH["dead_days"]} days without sales with {stock_end:.0f} on hand — markdown or delist candidate',
                                    'products'))
                _ = name_key

                if len(feat_buf) >= BATCH:
                    self._write(feat_sql, feat_buf); feat_buf = []
                if len(sig_buf) >= BATCH:
                    self._write(sig_sql, sig_buf); sig_buf = []

        self._write(feat_sql, feat_buf)
        self._write(sig_sql, sig_buf)
        self._vector_outliers(stores, sig_sql)

    def _vector_outliers(self, stores: List[int], sig_sql: str):
        """
        Векторный детектор: выброс среди соседей по категории.

        Расстояния считает БАЗА (VECTOR_DISTANCE по колонке VECTOR из 26ai),
        а не Python: среднее косинусное расстояние каждого SKU до товаров
        своей категории в том же магазине. SKU, чьё расстояние выше
        медианы категории на 2.5 межквартильных размаха, — аномалия
        сочетания признаков, даже если каждый признак по отдельности
        в норме и пороговые детекторы молчат.
        """
        self._progress('vector outliers', 96)
        sig_buf: List[Tuple] = []
        for store_id in stores:
            self._check_cancel()
            rows = self._fetch(
                "SELECT f1.PRODUCT_ID, p1.CATEGORY_ID, "
                "AVG(VECTOR_DISTANCE(f1.EMB, f2.EMB, COSINE)) AS D, COUNT(*) AS N "
                "FROM PLG_AI_FEATURES f1 "
                "JOIN PLG_PRODUCTS p1 ON p1.ID = f1.PRODUCT_ID "
                "JOIN PLG_PRODUCTS p2 ON p2.CATEGORY_ID = p1.CATEGORY_ID "
                "JOIN PLG_AI_FEATURES f2 ON f2.PRODUCT_ID = p2.ID "
                " AND f2.RUN_ID = f1.RUN_ID AND f2.STORE_ID = f1.STORE_ID "
                " AND f2.PRODUCT_ID <> f1.PRODUCT_ID "
                "WHERE f1.RUN_ID = :p_run AND f1.STORE_ID = :p_st "
                " AND f1.EMB IS NOT NULL AND f2.EMB IS NOT NULL "
                "GROUP BY f1.PRODUCT_ID, p1.CATEGORY_ID HAVING COUNT(*) >= 5",
                {'p_run': self.run_id, 'p_st': store_id})
            by_cat: Dict[int, List[Tuple[int, float]]] = {}
            for (pid, cat_id, d, _n) in rows:
                by_cat.setdefault(int(cat_id or 0), []).append((int(pid), float(d)))
            for cat_id, items in by_cat.items():
                dists = sorted(d for _, d in items)
                if len(dists) < 8:
                    continue
                q1 = dists[len(dists) // 4]
                q3 = dists[3 * len(dists) // 4]
                med = dists[len(dists) // 2]
                iqr = max(q3 - q1, 0.005)
                threshold = med + 2.5 * iqr
                for pid, d in items:
                    if d <= threshold or d < 0.03:
                        continue
                    delta = (d / med - 1) * 100 if med > 0 else 100.0
                    sig_buf.append((
                        self.run_id, 'peer_outlier', 'warn', store_id, pid,
                        cat_id or None, round(d, 4), round(med, 4), round(delta, 1),
                        'Поведение товара выбивается из категории: векторное расстояние '
                        f'{d:.3f} при типичном {med:.3f} — проверьте карточку и историю',
                        'Comportamentul produsului iese din tiparul categoriei: distanța '
                        f'vectorială {d:.3f} față de {med:.3f} tipic',
                        f'Product behaviour deviates from its category: vector distance '
                        f'{d:.3f} vs the typical {med:.3f}',
                        'aimonitor'))
        self._write(sig_sql, sig_buf)

    def _write(self, sql: str, rows: List[Tuple]):
        if not rows:
            return
        cur = self.conn.cursor()
        cur.executemany(sql, rows)
        self.conn.commit()
        if 'PLG_AI_SIGNALS' in sql:
            self.signal_count += len(rows)

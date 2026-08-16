"""
ИИ-мониторинг, корректировка автозаказа и заказы импорта.

Три контура в одном контроллере, потому что они обслуживают один сценарий
закупщика: мониторинг показывает проблему → корректировка автозаказа её
закрывает → пакет документов уходит поставщику (внутреннему или импортному).

Oracle-объекты: sql/96_plg_ai_monitor.sql, sql/97_plg_import.sql
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel
from models.plg_ai_monitor import AiMonitorEngine

LANGS = ('ru', 'ro', 'en')


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result or not result.get('success'):
        return []
    cols = [c.lower() for c in (result.get('columns') or [])]
    return [dict(zip(cols, row)) for row in (result.get('data') or [])]


def _localize(rows: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    suffixes = tuple('_' + code for code in LANGS)
    out = []
    for row in rows:
        bases = {k[:-3] for k in row if k.endswith(suffixes)}
        new = dict(row)
        for base in bases:
            new[base] = row.get(base + '_' + lang) or row.get(base + '_ru')
        out.append(new)
    return out


class PlgAiController:
    """Мониторинг, корректировки, импорт."""

    # ==================== ИИ-мониторинг ====================

    @staticmethod
    def start_monitor(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        try:
            return AiMonitorEngine.launch(payload.get('dataset_id'),
                                          payload.get('store_id'), username)
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def monitor_runs(limit: int = 20) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                data = _rows(db.execute_query(
                    "SELECT ID, DATASET_ID, STORE_ID, STATUS, STAGE, PROGRESS_PCT, "
                    "SIGNAL_COUNT, FEATURE_COUNT, DURATION_SEC, MESSAGE, USERNAME, "
                    "STARTED_AT, FINISHED_AT FROM PLG_AI_RUNS "
                    "ORDER BY ID DESC FETCH FIRST :p_lim ROWS ONLY", {'p_lim': limit}))
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _last_monitor_run(db: DatabaseModel) -> Optional[int]:
        rows = _rows(db.execute_query(
            "SELECT MAX(ID) AS ID FROM PLG_AI_RUNS WHERE STATUS = 'done'"))
        return rows[0].get('id') if rows else None

    @staticmethod
    def signals(lang: str, store_id: Optional[int] = None,
                signal_type: Optional[str] = None,
                run_id: Optional[int] = None, limit: int = 300) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                if not run_id:
                    run_id = PlgAiController._last_monitor_run(db)
                if not run_id:
                    return {'success': True, 'data': [], 'run_id': None, 'summary': []}
                sql = "SELECT * FROM V_PLG_AI_SIGNALS WHERE RUN_ID = :p_run"
                params: Dict[str, Any] = {'p_run': run_id}
                if store_id:
                    sql += " AND STORE_ID = :p_st"
                    params['p_st'] = store_id
                if signal_type:
                    sql += " AND SIGNAL_TYPE = :p_type"
                    params['p_type'] = signal_type
                sql += (" ORDER BY CASE SEVERITY WHEN 'crit' THEN 0 WHEN 'warn' THEN 1 "
                        "ELSE 2 END, ID DESC FETCH FIRST :p_lim ROWS ONLY")
                params['p_lim'] = limit
                data = _localize(_rows(db.execute_query(sql, params)), lang)
                summary = _rows(db.execute_query(
                    "SELECT SIGNAL_TYPE, SEVERITY, COUNT(*) AS CNT FROM PLG_AI_SIGNALS "
                    "WHERE RUN_ID = :p_run" +
                    (" AND STORE_ID = :p_st" if store_id else "") +
                    " GROUP BY SIGNAL_TYPE, SEVERITY",
                    {k: v for k, v in params.items() if k in ('p_run', 'p_st')}))
            return {'success': True, 'data': data, 'run_id': run_id, 'summary': summary}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def ack_signal(signal_id: int, username: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PLG_AI_SIGNALS SET STATUS = 'ack', ACK_BY = :p_by, "
                    "ACK_AT = SYSTIMESTAMP WHERE ID = :p_id AND STATUS = 'new'",
                    {'p_by': username, 'p_id': signal_id})
                db.connection.commit()
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def features(lang: str, store_id: Optional[int] = None,
                 run_id: Optional[int] = None, limit: int = 500) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                if not run_id:
                    run_id = PlgAiController._last_monitor_run(db)
                if not run_id:
                    return {'success': True, 'data': [], 'run_id': None}
                sql = "SELECT * FROM V_PLG_AI_FEATURES WHERE RUN_ID = :p_run"
                params: Dict[str, Any] = {'p_run': run_id}
                if store_id:
                    sql += " AND STORE_ID = :p_st"
                    params['p_st'] = store_id
                sql += " ORDER BY AVG_QTY_28 DESC FETCH FIRST :p_lim ROWS ONLY"
                params['p_lim'] = limit
                data = _localize(_rows(db.execute_query(sql, params)), lang)
                total = _rows(db.execute_query(
                    "SELECT COUNT(*) AS CNT FROM PLG_AI_FEATURES WHERE RUN_ID = :p_run",
                    {'p_run': run_id}))
            return {'success': True, 'data': data, 'run_id': run_id,
                    'total': total[0]['cnt'] if total else 0}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def export_features(fmt: str = 'csv', run_id: Optional[int] = None,
                        store_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Выгрузка витрины признаков целиком — «массив данных» для обучения.
        CSV для аналитиков и Excel, JSON для пайплайнов ML.
        """
        try:
            with DatabaseModel() as db:
                if not run_id:
                    run_id = PlgAiController._last_monitor_run(db)
                if not run_id:
                    return {'success': False, 'error': 'Прогонов мониторинга ещё не было',
                            'status': 404}
                sql = ("SELECT RUN_ID, SNAPSHOT_DATE, STORE_CODE, PRODUCT_CODE, "
                       "PRODUCT_NAME_RU, CATEGORY_CODE, AVG_QTY_7, AVG_QTY_28, "
                       "MEDIAN_QTY_28, SIGMA_28, CV, TREND_PCT, WEEKEND_LIFT, "
                       "PROMO_UPLIFT, PROMO_DAYS_28, OOS_DAYS_28, STOCK_END, "
                       "STOCK_COVER_DAYS, WASTE_PCT, PRICE, MARGIN_PCT, ABC_CLASS, "
                       "XYZ_CLASS, IS_FRESH FROM V_PLG_AI_FEATURES WHERE RUN_ID = :p_run")
                params: Dict[str, Any] = {'p_run': run_id}
                if store_id:
                    sql += " AND STORE_ID = :p_st"
                    params['p_st'] = store_id
                res = db.execute_query(sql + " ORDER BY STORE_CODE, PRODUCT_CODE", params)
                cols = [c.lower() for c in (res.get('columns') or [])]
                rows = res.get('data') or []
            if fmt == 'json':
                payload = json.dumps([dict(zip(cols, r)) for r in rows],
                                     ensure_ascii=False, default=str)
                return {'success': True, 'content': payload,
                        'mimetype': 'application/json; charset=utf-8',
                        'filename': f'plg_features_run{run_id}.json'}
            buf = io.StringIO()
            w = csv.writer(buf, delimiter=';')   # ; — чтобы Excel с русской локалью открыл сразу
            w.writerow(cols)
            for r in rows:
                w.writerow(['' if v is None else v for v in r])
            return {'success': True, 'content': buf.getvalue(),
                    'mimetype': 'text/csv; charset=utf-8',
                    'filename': f'plg_features_run{run_id}.csv'}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Корректировка автозаказа ====================

    @staticmethod
    def order_runs(lang: str) -> Dict[str, Any]:
        """Свежие завершённые прогоны прогноза — селектор экрана автозаказа."""
        try:
            with DatabaseModel() as db:
                data = _localize(_rows(db.execute_query(
                    "SELECT r.ID, r.MODEL_ID, m.CODE AS MODEL_CODE, m.ALGORITHM, "
                    "m.NAME_RU AS MODEL_NAME_RU, m.NAME_RO AS MODEL_NAME_RO, "
                    "m.NAME_EN AS MODEL_NAME_EN, r.ORIGIN_DATE, r.SERIES_COUNT, "
                    "r.ORDER_QTY_SUM, r.STARTED_AT FROM PLG_FCT_RUNS r "
                    "JOIN PLG_FCT_MODELS m ON m.ID = r.MODEL_ID "
                    "WHERE r.STATUS = 'done' AND r.RUN_MODE = 'forecast' "
                    "ORDER BY r.ID DESC FETCH FIRST 15 ROWS ONLY")), lang)
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def order_proposal(lang: str, run_id: Optional[int],
                       store_id: Optional[int]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                if not run_id:
                    rows = _rows(db.execute_query(
                        "SELECT MAX(ID) AS ID FROM PLG_FCT_RUNS "
                        "WHERE STATUS = 'done' AND RUN_MODE = 'forecast'"))
                    run_id = rows[0].get('id') if rows else None
                if not run_id:
                    return {'success': True, 'data': [], 'run_id': None}
                sql = "SELECT * FROM V_PLG_ORDER_ADJUSTED WHERE RUN_ID = :p_run"
                params: Dict[str, Any] = {'p_run': run_id}
                if store_id:
                    sql += " AND STORE_ID = :p_st"
                    params['p_st'] = store_id
                sql += " ORDER BY IS_ADJUSTED DESC, AMOUNT_FINAL DESC NULLS LAST"
                data = _localize(_rows(db.execute_query(sql, params)), lang)
            adjusted = sum(1 for r in data if r.get('is_adjusted'))
            total = sum(float(r.get('amount_final') or 0) for r in data)
            return {'success': True, 'data': data, 'run_id': run_id,
                    'adjusted_count': adjusted, 'total_amount': round(total, 2)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def adjust_order(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """
        Правка количества «на лету». Рекомендация модели фиксируется в
        QTY_ORIGINAL в момент правки: потом по паре (модель, человек)
        считается, где машина системно ошибается.
        """
        run_id = payload.get('run_id')
        store_id = payload.get('store_id')
        product_id = payload.get('product_id')
        qty = payload.get('qty')
        if not all([run_id, store_id, product_id]) or qty is None:
            return {'success': False, 'error': 'Нужны run_id, store_id, product_id, qty',
                    'status': 400}
        reason = payload.get('reason') if payload.get('reason') in \
            ('manual', 'promo', 'event', 'supply', 'quality', 'other') else 'manual'
        try:
            with DatabaseModel() as db:
                orig = _rows(db.execute_query(
                    "SELECT ORDER_QTY FROM V_PLG_ORDER_PROPOSAL WHERE RUN_ID = :p_r "
                    "AND STORE_ID = :p_s AND PRODUCT_ID = :p_p",
                    {'p_r': run_id, 'p_s': store_id, 'p_p': product_id}))
                qty_model = float(orig[0]['order_qty'] or 0) if orig else None
                r = db.execute_query(
                    "MERGE INTO PLG_ORDER_ADJUSTMENTS t USING (SELECT :p_r AS RUN_ID, "
                    ":p_s AS STORE_ID, :p_p AS PRODUCT_ID FROM DUAL) src "
                    "ON (t.RUN_ID = src.RUN_ID AND t.STORE_ID = src.STORE_ID "
                    "AND t.PRODUCT_ID = src.PRODUCT_ID) "
                    "WHEN MATCHED THEN UPDATE SET QTY_ADJUSTED = :p_q, REASON = :p_reason, "
                    "NOTE = :p_note, STATUS = 'active', USERNAME = :p_user "
                    "WHEN NOT MATCHED THEN INSERT (RUN_ID, STORE_ID, PRODUCT_ID, "
                    "QTY_ORIGINAL, QTY_ADJUSTED, REASON, NOTE, USERNAME) "
                    "VALUES (:p_r2, :p_s2, :p_p2, :p_orig, :p_q2, :p_reason2, :p_note2, :p_user2)",
                    {'p_r': run_id, 'p_s': store_id, 'p_p': product_id,
                     'p_q': float(qty), 'p_reason': reason,
                     'p_note': (payload.get('note') or '')[:600], 'p_user': username,
                     'p_r2': run_id, 'p_s2': store_id, 'p_p2': product_id,
                     'p_orig': qty_model, 'p_q2': float(qty), 'p_reason2': reason,
                     'p_note2': (payload.get('note') or '')[:600], 'p_user2': username})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                db.connection.commit()
            return {'success': True, 'qty_model': qty_model}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def reset_adjustment(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE PLG_ORDER_ADJUSTMENTS SET STATUS = 'cancelled' "
                    "WHERE RUN_ID = :p_r AND STORE_ID = :p_s AND PRODUCT_ID = :p_p",
                    {'p_r': payload.get('run_id'), 'p_s': payload.get('store_id'),
                     'p_p': payload.get('product_id')})
                db.connection.commit()
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def order_package(lang: str, run_id: int, store_id: Optional[int]) -> Dict[str, Any]:
        """
        Пакет документов заказа: позиции с учётом корректировок,
        сгруппированные по поставщикам, — данные для печатной формы.
        """
        res = PlgAiController.order_proposal(lang, run_id, store_id)
        if not res.get('success'):
            return res
        by_sup: Dict[str, Dict[str, Any]] = {}
        for row in res['data']:
            if float(row.get('qty_final') or 0) <= 0:
                continue
            key = row.get('supplier_name') or '—'
            g = by_sup.setdefault(key, {'supplier': key, 'items': [], 'amount': 0.0})
            g['items'].append(row)
            g['amount'] += float(row.get('amount_final') or 0)
        groups = sorted(by_sup.values(), key=lambda g: -g['amount'])
        return {'success': True, 'run_id': res.get('run_id'), 'groups': groups,
                'total_amount': res.get('total_amount'),
                'adjusted_count': res.get('adjusted_count')}

    # ==================== Заказы импорта ====================

    @staticmethod
    def import_orders(lang: str, status: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_PLG_IMPORT_ORDERS"
                params: Dict[str, Any] = {}
                if status:
                    sql += " WHERE STATUS = :p_status"
                    params['p_status'] = status
                sql += " ORDER BY CREATED_AT DESC"
                data = _localize(_rows(db.execute_query(sql, params)), lang)
                stages = _localize(_rows(db.execute_query(
                    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, SORT_ORDER, IS_CUSTOMS, "
                    "TYPICAL_DAYS FROM PLG_REF_IMP_STAGES ORDER BY SORT_ORDER")), lang)
            return {'success': True, 'data': data, 'stages': stages}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def import_order(lang: str, order_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                head = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_IMPORT_ORDERS WHERE ID = :p_id",
                    {'p_id': order_id})), lang)
                if not head:
                    return {'success': False, 'error': 'Заказ не найден', 'status': 404}
                items = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_IMPORT_ITEMS WHERE ORDER_ID = :p_id "
                    "ORDER BY SORT_ORDER, ID", {'p_id': order_id})), lang)
                stages = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_IMPORT_STAGES WHERE ORDER_ID = :p_id "
                    "ORDER BY SORT_ORDER", {'p_id': order_id})), lang)
                docs = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_IMPORT_DOCS WHERE ORDER_ID = :p_id "
                    "ORDER BY SORT_ORDER", {'p_id': order_id})), lang)
            data = head[0]
            data.update({'items': items, 'stages': stages, 'docs': docs})
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def create_import(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """
        Новый заказ импорта. Вместе с заказом сразу создаются план этапов
        (по типовым длительностям справочника) и упреждающий чек-лист
        документов с дедлайнами от плановой даты границы — в этом весь смысл:
        о сертификате соответствия нужно вспомнить за неделю до границы,
        а не на посту.
        """
        try:
            etd = payload.get('etd')
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO PLG_IMPORT_ORDERS (SUPPLIER_ID, DC_ID, STORE_ID, COUNTRY, "
                    "INCOTERMS, TRANSPORT, CURRENCY, DUTY_PCT, STATUS, ETD, CUSTOMS_POST, "
                    "BROKER, NOTES, CREATED_BY) VALUES (:p_sup, :p_dc, :p_store, :p_country, "
                    ":p_inc, :p_tr, :p_cur, :p_duty, 'draft', "
                    "TO_DATE(:p_etd, 'YYYY-MM-DD'), :p_post, :p_broker, :p_notes, :p_by)",
                    {'p_sup': payload.get('supplier_id'), 'p_dc': payload.get('dc_id'),
                     'p_store': payload.get('store_id'),
                     'p_country': (payload.get('country') or '')[:5],
                     'p_inc': (payload.get('incoterms') or 'FCA')[:10],
                     'p_tr': payload.get('transport') if payload.get('transport') in
                             ('truck', 'sea', 'air', 'rail') else 'truck',
                     'p_cur': (payload.get('currency') or 'EUR')[:5],
                     'p_duty': payload.get('duty_pct'),
                     'p_etd': etd, 'p_post': (payload.get('customs_post') or '')[:150],
                     'p_broker': (payload.get('broker') or '')[:200],
                     'p_notes': (payload.get('notes') or '')[:1000], 'p_by': username})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                oid = _rows(db.execute_query(
                    "SELECT MAX(ID) AS ID FROM PLG_IMPORT_ORDERS WHERE CREATED_BY = :p_by",
                    {'p_by': username}))[0]['id']

                # План этапов от даты отгрузки (или от сегодня)
                db.execute_query(
                    "INSERT INTO PLG_IMPORT_STAGE_LOG (ORDER_ID, STAGE_CODE, PLANNED_DATE, USERNAME) "
                    "SELECT :p_id, s.CODE, "
                    "  NVL(TO_DATE(:p_etd, 'YYYY-MM-DD'), SYSDATE) + "
                    "  (SELECT SUM(s2.TYPICAL_DAYS) FROM PLG_REF_IMP_STAGES s2 "
                    "    WHERE s2.SORT_ORDER <= s.SORT_ORDER) - "
                    "  (SELECT SUM(s3.TYPICAL_DAYS) FROM PLG_REF_IMP_STAGES s3 "
                    "    WHERE s3.SORT_ORDER <= (SELECT SORT_ORDER FROM PLG_REF_IMP_STAGES "
                    "      WHERE CODE = 'shipment')), "
                    ":p_user FROM PLG_REF_IMP_STAGES s",
                    {'p_id': oid, 'p_etd': etd, 'p_user': username})

                # Упреждающий чек-лист: дедлайн = плановая граница − LEAD_DAYS
                db.execute_query(
                    "INSERT INTO PLG_IMPORT_DOCS (ORDER_ID, DOC_CODE, STATUS, DUE_DATE) "
                    "SELECT :p_id, d.CODE, 'pending', "
                    "  (SELECT PLANNED_DATE FROM PLG_IMPORT_STAGE_LOG "
                    "    WHERE ORDER_ID = :p_id2 AND STAGE_CODE = 'border') - d.LEAD_DAYS "
                    "FROM PLG_REF_IMP_DOCS d",
                    {'p_id': oid, 'p_id2': oid})

                # ETA = плановая дата доставки
                db.execute_query(
                    "UPDATE PLG_IMPORT_ORDERS SET ETA = (SELECT PLANNED_DATE "
                    "FROM PLG_IMPORT_STAGE_LOG WHERE ORDER_ID = :p_id "
                    "AND STAGE_CODE = 'delivered') WHERE ID = :p_id2",
                    {'p_id': oid, 'p_id2': oid})

                for i, it in enumerate(payload.get('items') or []):
                    db.execute_query(
                        "INSERT INTO PLG_IMPORT_ITEMS (ORDER_ID, PRODUCT_ID, DESCR, HS_CODE, "
                        "ORIGIN, QTY, UOM, PRICE, SORT_ORDER) VALUES (:p_o, :p_p, :p_d, "
                        ":p_hs, :p_or, :p_q, :p_u, :p_pr, :p_i)",
                        {'p_o': oid, 'p_p': it.get('product_id'),
                         'p_d': (it.get('descr') or '')[:300] or None,
                         'p_hs': (it.get('hs_code') or '')[:12] or None,
                         'p_or': (it.get('origin') or '')[:5] or None,
                         'p_q': float(it.get('qty') or 0),
                         'p_u': (it.get('uom') or 'pcs')[:20],
                         'p_pr': it.get('price'), 'p_i': i})
                db.execute_query(
                    "UPDATE PLG_IMPORT_ORDERS SET AMOUNT = (SELECT NVL(SUM(QTY*PRICE),0) "
                    "FROM PLG_IMPORT_ITEMS WHERE ORDER_ID = :p_id) WHERE ID = :p_id2",
                    {'p_id': oid, 'p_id2': oid})
                db.connection.commit()
            return {'success': True, 'id': oid}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def advance_stage(order_id: int, payload: Dict[str, Any],
                      username: str) -> Dict[str, Any]:
        """
        Отметка фактического прохождения этапа. Задержка = факт − план,
        причина обязательна, если задержка положительная: «просто так»
        дни на таможне не теряются, и статистика причин — главное, ради
        чего ведётся журнал.
        """
        stage = payload.get('stage_code')
        actual = payload.get('actual_date')   # YYYY-MM-DD, по умолчанию сегодня
        reason = payload.get('delay_reason')
        try:
            with DatabaseModel() as db:
                row = _rows(db.execute_query(
                    "SELECT PLANNED_DATE FROM PLG_IMPORT_STAGE_LOG "
                    "WHERE ORDER_ID = :p_o AND STAGE_CODE = :p_s",
                    {'p_o': order_id, 'p_s': stage}))
                if not row:
                    return {'success': False, 'error': 'Этап не в плане заказа', 'status': 404}
                r = db.execute_query(
                    "UPDATE PLG_IMPORT_STAGE_LOG SET "
                    "ACTUAL_DATE = NVL(TO_DATE(:p_d, 'YYYY-MM-DD'), TRUNC(SYSDATE)), "
                    "DELAY_DAYS = GREATEST(0, ROUND(NVL(TO_DATE(:p_d2, 'YYYY-MM-DD'), "
                    "  TRUNC(SYSDATE)) - PLANNED_DATE)), "
                    "DELAY_REASON = :p_reason, NOTE = :p_note, USERNAME = :p_user "
                    "WHERE ORDER_ID = :p_o AND STAGE_CODE = :p_s",
                    {'p_d': actual, 'p_d2': actual,
                     'p_reason': reason if reason in
                     ('docs', 'customs', 'logistics', 'supplier', 'payment', 'other') else None,
                     'p_note': (payload.get('note') or '')[:600], 'p_user': username,
                     'p_o': order_id, 'p_s': stage})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                delay = _rows(db.execute_query(
                    "SELECT DELAY_DAYS FROM PLG_IMPORT_STAGE_LOG "
                    "WHERE ORDER_ID = :p_o AND STAGE_CODE = :p_s",
                    {'p_o': order_id, 'p_s': stage}))
                if delay and float(delay[0]['delay_days'] or 0) > 0 and not reason:
                    db.connection.rollback()
                    return {'success': False, 'status': 409,
                            'error': 'Этап пройден с задержкой — укажите причину '
                                     '(документы / таможня / логистика / поставщик / оплата)'}
                db.execute_query(
                    "UPDATE PLG_IMPORT_ORDERS SET STATUS = :p_s, "
                    "TOTAL_DELAY_DAYS = (SELECT NVL(SUM(DELAY_DAYS),0) "
                    "FROM PLG_IMPORT_STAGE_LOG WHERE ORDER_ID = :p_o) "
                    "WHERE ID = :p_o2",
                    {'p_s': stage, 'p_o': order_id, 'p_o2': order_id})
                db.connection.commit()
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def set_import_doc(order_id: int, doc_id: int, payload: Dict[str, Any],
                       username: str) -> Dict[str, Any]:
        status = payload.get('status')
        if status not in ('pending', 'in_progress', 'ready', 'approved', 'rejected'):
            return {'success': False, 'error': 'Некорректный статус', 'status': 400}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PLG_IMPORT_DOCS SET STATUS = :p_st, "
                    "READY_DATE = CASE WHEN :p_st2 IN ('ready','approved') "
                    "  THEN NVL(READY_DATE, TRUNC(SYSDATE)) ELSE NULL END, "
                    "RESPONSIBLE = NVL(:p_resp, RESPONSIBLE), NOTE = NVL(:p_note, NOTE) "
                    "WHERE ID = :p_id AND ORDER_ID = :p_o",
                    {'p_st': status, 'p_st2': status,
                     'p_resp': (payload.get('responsible') or '')[:150] or None,
                     'p_note': (payload.get('note') or '')[:600] or None,
                     'p_id': doc_id, 'p_o': order_id})
                db.connection.commit()
                _ = username
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def import_delay_stats(lang: str) -> Dict[str, Any]:
        """Где теряются дни: по этапам и по причинам, за все заказы."""
        try:
            with DatabaseModel() as db:
                by_stage = _localize(_rows(db.execute_query(
                    "SELECT l.STAGE_CODE, rs.NAME_RU AS STAGE_NAME_RU, "
                    "rs.NAME_RO AS STAGE_NAME_RO, rs.NAME_EN AS STAGE_NAME_EN, "
                    "rs.SORT_ORDER, COUNT(*) AS PASSES, SUM(l.DELAY_DAYS) AS DELAY_DAYS "
                    "FROM PLG_IMPORT_STAGE_LOG l "
                    "JOIN PLG_REF_IMP_STAGES rs ON rs.CODE = l.STAGE_CODE "
                    "WHERE l.ACTUAL_DATE IS NOT NULL "
                    "GROUP BY l.STAGE_CODE, rs.NAME_RU, rs.NAME_RO, rs.NAME_EN, "
                    "rs.SORT_ORDER ORDER BY rs.SORT_ORDER")), lang)
                by_reason = _rows(db.execute_query(
                    "SELECT DELAY_REASON, COUNT(*) AS CNT, SUM(DELAY_DAYS) AS DELAY_DAYS "
                    "FROM PLG_IMPORT_STAGE_LOG WHERE DELAY_DAYS > 0 "
                    "GROUP BY DELAY_REASON ORDER BY 3 DESC"))
            return {'success': True, 'by_stage': by_stage, 'by_reason': by_reason}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

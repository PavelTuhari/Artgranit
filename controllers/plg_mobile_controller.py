"""
Мобильное приложение модуля «Планограммы»: API устройства и голосовой заказ.

Контур авторизации отличается от остального модуля и это сделано намеренно.

Веб-часть работает по сессии браузера. Мобильное приложение так работать
не может: сессия живёт до закрытия браузера, а телефон менеджера лежит
в кармане халата весь день и не должен переспрашивать пароль у полки.
Поэтому здесь — токен устройства:

  1. Администратор заводит устройство в бэк-офисе и получает КОД СОПРЯЖЕНИЯ
     (шесть символов, живёт сутки, одноразовый).
  2. Приложение обменивает код на постоянный токен.
  3. В базе лежит SHA-256 токена. Утечка дампа не даёт доступа к устройствам.
  4. Токен отзывается администратором в один клик — устройство мгновенно
     теряет доступ, пароль менеджера при этом менять не нужно.

Голосовая команда никогда не создаёт отправленный заказ: только черновик,
который менеджер подтверждает на экране. Ошибка распознавания не должна
превращаться в машину товара — см. models/plg_voice.py.

Oracle-объекты: sql/94_plg_mobile.sql
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import secrets
import string
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel
from models.plg_voice import ProductMatcher, parse_order

LANGS = ('ru', 'ro', 'en')
PAIR_ALPHABET = string.ascii_uppercase.replace('O', '').replace('I', '') + '23456789'


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or '').encode('utf-8')).hexdigest()


def _rows(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not result or not result.get('success'):
        return []
    cols = [c.lower() for c in (result.get('columns') or [])]
    return [dict(zip(cols, row)) for row in (result.get('data') or [])]


def _localize(rows: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    """Схлопывает поля <base>_ru/_ro/_en в <base> по выбранному языку."""
    suffixes = tuple('_' + code for code in LANGS)
    out = []
    for row in rows:
        bases = {k[:-3] for k in row if k.endswith(suffixes)}
        new = dict(row)
        for base in bases:
            new[base] = row.get(base + '_' + lang) or row.get(base + '_ru')
        out.append(new)
    return out


class PlgMobileController:
    """Устройства, голосовой разбор и заказы из торгового зала."""

    # ==================== Сопряжение и авторизация ====================

    @staticmethod
    def _new_pair_code() -> str:
        rnd = random.SystemRandom()
        return ''.join(rnd.choice(PAIR_ALPHABET) for _ in range(6))

    @staticmethod
    def create_device(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Заводит устройство и выдаёт код сопряжения. Токена ещё нет."""
        store_id = payload.get('store_id')
        if not store_id:
            return {'success': False, 'error': 'Не указан магазин'}
        code = PlgMobileController._new_pair_code()
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO PLG_MOBILE_DEVICES (STORE_ID, PAIR_CODE, USERNAME, DISPLAY_NAME, "
                    "ROLE_CODE, LANG, ORDER_LIMIT, STATUS, CREATED_BY) "
                    "VALUES (:p_st, :p_code, :p_user, :p_name, :p_role, :p_lang, :p_limit, "
                    "'pending', :p_by)",
                    {'p_st': int(store_id), 'p_code': code,
                     'p_user': (payload.get('username') or '')[:150],
                     'p_name': (payload.get('display_name') or 'Устройство')[:200],
                     'p_role': payload.get('role_code') or 'manager',
                     'p_lang': payload.get('lang') if payload.get('lang') in LANGS else 'ru',
                     'p_limit': float(payload.get('order_limit') or 0),
                     'p_by': username})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
            return {'success': True, 'pair_code': code}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def pair(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Обмен кода сопряжения на постоянный токен устройства."""
        code = (payload.get('pair_code') or '').strip().upper()
        if not code:
            return {'success': False, 'error': 'Не указан код сопряжения', 'status': 400}
        token = secrets.token_urlsafe(32)
        try:
            with DatabaseModel() as db:
                rows = _rows(db.execute_query(
                    "SELECT ID, STORE_ID, LANG, STATUS, TOKEN_HASH FROM PLG_MOBILE_DEVICES "
                    "WHERE PAIR_CODE = :p_code", {'p_code': code}))
                if not rows:
                    return {'success': False, 'error': 'Код не найден', 'status': 404}
                dev = rows[0]
                if dev.get('status') == 'revoked':
                    return {'success': False, 'error': 'Устройство отозвано', 'status': 403}
                if dev.get('token_hash'):
                    # Код одноразовый: повторное сопряжение — это либо ошибка,
                    # либо чужая попытка. Второй раз тот же код не работает.
                    return {'success': False, 'error': 'Код уже использован', 'status': 409}
                r = db.execute_query(
                    "UPDATE PLG_MOBILE_DEVICES SET TOKEN_HASH = :p_hash, STATUS = 'active', "
                    "PAIR_CODE = NULL, PAIRED_AT = SYSTIMESTAMP, LAST_SEEN = SYSTIMESTAMP, "
                    "PLATFORM = :p_plat, APP_VERSION = :p_ver WHERE ID = :p_id",
                    {'p_hash': _hash_token(token), 'p_id': dev['id'],
                     'p_plat': (payload.get('platform') or '')[:20],
                     'p_ver': (payload.get('app_version') or '')[:20]})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
            return {'success': True, 'token': token, 'device_id': dev['id'],
                    'store_id': dev['store_id'], 'lang': dev.get('lang') or 'ru'}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def device_by_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
        """Устройство по токену. None = доступа нет."""
        if not token:
            return None
        try:
            with DatabaseModel() as db:
                rows = _rows(db.execute_query(
                    "SELECT d.ID, d.STORE_ID, d.USERNAME, d.DISPLAY_NAME, d.ROLE_CODE, d.LANG, "
                    "d.STATUS, d.ORDER_LIMIT, s.CODE AS STORE_CODE, s.NAME_RU AS STORE_NAME_RU, "
                    "s.NAME_RO AS STORE_NAME_RO, s.NAME_EN AS STORE_NAME_EN "
                    "FROM PLG_MOBILE_DEVICES d JOIN PLG_STORES s ON s.ID = d.STORE_ID "
                    "WHERE d.TOKEN_HASH = :p_hash", {'p_hash': _hash_token(token)}))
                if not rows or rows[0].get('status') != 'active':
                    return None
                db.execute_query(
                    "UPDATE PLG_MOBILE_DEVICES SET LAST_SEEN = SYSTIMESTAMP WHERE ID = :p_id",
                    {'p_id': rows[0]['id']})
                return rows[0]
        except Exception:                                        # noqa: BLE001
            return None

    @staticmethod
    def session(device: Dict[str, Any]) -> Dict[str, Any]:
        lang = device.get('lang') or 'ru'
        info = _localize([device], lang)[0]
        return {'success': True, 'data': {
            'device_id': info['id'], 'display_name': info.get('display_name'),
            'role': info.get('role_code'), 'lang': lang,
            'store': {'id': info['store_id'], 'code': info.get('store_code'),
                      'name': info.get('store_name')},
            'order_limit': float(info.get('order_limit') or 0),
        }}

    @staticmethod
    def list_devices(store_id: Optional[int], lang: str) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PLG_MOBILE_DEVICES"
        params: Dict[str, Any] = {}
        if store_id:
            sql += " WHERE STORE_ID = :p_st"
            params['p_st'] = store_id
        sql += " ORDER BY STORE_CODE, DISPLAY_NAME"
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _localize(_rows(db.execute_query(sql, params)), lang)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def revoke_device(device_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PLG_MOBILE_DEVICES SET STATUS = 'revoked', TOKEN_HASH = NULL "
                    "WHERE ID = :p_id", {'p_id': device_id})
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Каталог магазина ====================

    @staticmethod
    def _catalog(store_id: int, lang: str, limit: int = 4000) -> List[Dict[str, Any]]:
        """Ассортимент магазина для сопоставления и подсказок в приложении."""
        with DatabaseModel() as db:
            rows = _rows(db.execute_query(
                "SELECT p.ID, p.CODE, p.NAME_RU, p.NAME_RO, p.NAME_EN, p.BARCODE, p.UOM, "
                "p.PRICE, NVL(p.ORDER_MULTIPLE,1) AS ORDER_MULTIPLE, p.CATEGORY_ID, "
                "NVL(p.IS_FRESH,0) AS IS_FRESH "
                "FROM PLG_PRODUCTS p WHERE p.STATUS = 'active' AND p.ID IN "
                "(SELECT DISTINCT PRODUCT_ID FROM PLG_SALES_DAILY WHERE STORE_ID = :p_st) "
                "AND ROWNUM <= :p_lim ORDER BY p.NAME_RU",
                {'p_st': store_id, 'p_lim': limit}))
        if not rows:
            # Магазин без истории продаж (новый) — берём весь активный каталог
            with DatabaseModel() as db:
                rows = _rows(db.execute_query(
                    "SELECT p.ID, p.CODE, p.NAME_RU, p.NAME_RO, p.NAME_EN, p.BARCODE, p.UOM, "
                    "p.PRICE, NVL(p.ORDER_MULTIPLE,1) AS ORDER_MULTIPLE, p.CATEGORY_ID, "
                    "NVL(p.IS_FRESH,0) AS IS_FRESH FROM PLG_PRODUCTS p "
                    "WHERE p.STATUS = 'active' AND ROWNUM <= :p_lim ORDER BY p.NAME_RU",
                    {'p_lim': limit}))
        return _localize(rows, lang)

    @staticmethod
    def catalog(store_id: int, lang: str, query: str = '', limit: int = 50) -> Dict[str, Any]:
        try:
            items = PlgMobileController._catalog(store_id, lang)
            if query:
                matcher = PlgMobileController._matcher(items, lang)
                best, score, options = matcher.match(query)
                ids = [o['id'] for o in options] or ([best['id']] if best else [])
                by_id = {i['id']: i for i in items}
                items = [dict(by_id[i], score=next((o['score'] for o in options if o['id'] == i), score))
                         for i in ids if i in by_id]
            return {'success': True, 'data': items[:limit], 'total': len(items)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _matcher(items: List[Dict[str, Any]], lang: str) -> ProductMatcher:
        with DatabaseModel() as db:
            syn = _rows(db.execute_query(
                "SELECT PRODUCT_ID, CATEGORY_ID, PHRASE, WEIGHT FROM PLG_VOICE_SYNONYMS "
                "WHERE LANG = :p_lang", {'p_lang': lang}))
        return ProductMatcher(items, syn, lang)

    # ==================== Голосовой заказ ====================

    @staticmethod
    def voice(device: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Фраза из приложения → разбор → черновик заказа.

        Ответ всегда содержит разбор целиком, включая непонятые позиции:
        приложение показывает их отдельным списком и просит уточнить.
        """
        text = (payload.get('text') or '').strip()
        if not text:
            return {'success': False, 'error': 'Пустая фраза', 'status': 400}
        lang = payload.get('lang') if payload.get('lang') in LANGS else (device.get('lang') or 'ru')
        store_id = int(device['store_id'])
        try:
            items = PlgMobileController._catalog(store_id, lang)
            parsed = parse_order(text, lang, PlgMobileController._matcher(items, lang))

            order_id = payload.get('order_id')
            order: Optional[Dict[str, Any]] = None
            if parsed['intent'] in ('add', 'set', 'remove') and parsed['items']:
                order = PlgMobileController._apply_to_draft(
                    device, store_id, lang, parsed, order_id, payload.get('zone_id'))
            elif parsed['intent'] == 'submit' and order_id:
                PlgMobileController.submit_order(device, int(order_id))
                order = PlgMobileController.get_order(device, int(order_id)).get('data')
            elif parsed['intent'] == 'cancel' and order_id:
                PlgMobileController.cancel_order(device, int(order_id))
                order = PlgMobileController.get_order(device, int(order_id)).get('data')

            PlgMobileController._log_voice(device, store_id, lang, text, parsed,
                                           order.get('id') if order else order_id,
                                           payload)
            return {'success': True, 'data': {'parsed': parsed, 'order': order}}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _log_voice(device: Dict[str, Any], store_id: int, lang: str, text: str,
                   parsed: Dict[str, Any], order_id: Optional[int],
                   payload: Dict[str, Any]) -> None:
        """
        Журнал распознавания. Пишется всегда, в том числе на непонятые фразы —
        именно они показывают, каких синонимов не хватает словарю.
        """
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO PLG_VOICE_LOG (DEVICE_ID, STORE_ID, ORDER_ID, LANG, RAW_TEXT, "
                    "INTENT, PARSED_JSON, ITEM_COUNT, MATCHED, UNMATCHED, CONFIDENCE, ASR_CONF, "
                    "DURATION_MS, USERNAME) VALUES (:p_dev, :p_st, :p_ord, :p_lang, :p_text, "
                    ":p_intent, :p_json, :p_cnt, :p_ok, :p_bad, :p_conf, :p_asr, :p_dur, :p_user)",
                    {'p_dev': device.get('id'), 'p_st': store_id, 'p_ord': order_id,
                     'p_lang': lang, 'p_text': text[:2000], 'p_intent': parsed.get('intent'),
                     'p_json': json.dumps(parsed, ensure_ascii=False),
                     'p_cnt': len(parsed.get('items') or []),
                     'p_ok': parsed.get('matched') or 0, 'p_bad': parsed.get('unmatched') or 0,
                     'p_conf': parsed.get('confidence'),
                     'p_asr': payload.get('asr_conf'), 'p_dur': payload.get('duration_ms'),
                     'p_user': device.get('username') or device.get('display_name')})
        except Exception:                                        # noqa: BLE001
            pass   # журнал не должен ронять заказ

    @staticmethod
    def _apply_to_draft(device: Dict[str, Any], store_id: int, lang: str,
                        parsed: Dict[str, Any], order_id: Optional[int],
                        zone_id: Optional[int]) -> Dict[str, Any]:
        with DatabaseModel() as db:
            oid = None
            if order_id:
                rows = _rows(db.execute_query(
                    "SELECT ID FROM PLG_MOBILE_ORDERS WHERE ID = :p_id AND STORE_ID = :p_st "
                    "AND STATUS = 'draft'", {'p_id': int(order_id), 'p_st': store_id}))
                oid = rows[0]['id'] if rows else None
            if not oid:
                db.execute_query(
                    "INSERT INTO PLG_MOBILE_ORDERS (STORE_ID, DEVICE_ID, ZONE_ID, SOURCE, STATUS, "
                    "LANG, CREATED_BY) VALUES (:p_st, :p_dev, :p_zone, 'voice', 'draft', :p_lang, :p_by)",
                    {'p_st': store_id, 'p_dev': device.get('id'),
                     'p_zone': int(zone_id) if zone_id else None, 'p_lang': lang,
                     'p_by': device.get('username') or device.get('display_name')})
                oid = _rows(db.execute_query(
                    "SELECT MAX(ID) AS ID FROM PLG_MOBILE_ORDERS WHERE STORE_ID = :p_st "
                    "AND DEVICE_ID = :p_dev", {'p_st': store_id, 'p_dev': device.get('id')}))[0]['id']

            intent = parsed['intent']
            for item in parsed['items']:
                pid = item.get('product_id')
                if intent == 'remove' and pid:
                    db.execute_query(
                        "UPDATE PLG_MOBILE_ORDER_ITEMS SET STATUS = 'removed' "
                        "WHERE ORDER_ID = :p_o AND PRODUCT_ID = :p_p",
                        {'p_o': oid, 'p_p': pid})
                    continue
                if intent == 'set' and pid:
                    upd = db.execute_query(
                        "UPDATE PLG_MOBILE_ORDER_ITEMS SET QTY = :p_q, STATUS = 'ok' "
                        "WHERE ORDER_ID = :p_o AND PRODUCT_ID = :p_p AND STATUS <> 'removed'",
                        {'p_q': item['qty'], 'p_o': oid, 'p_p': pid})
                    if upd.get('rowcount'):
                        continue
                db.execute_query(
                    "INSERT INTO PLG_MOBILE_ORDER_ITEMS (ORDER_ID, PRODUCT_ID, QTY, UOM, PACK_QTY, "
                    "PRICE, SOURCE_TEXT, MATCH_NAME, CONFIDENCE, STATUS) "
                    "SELECT :p_o, :p_p, :p_q, :p_u, :p_pack, "
                    "  (SELECT PRICE FROM PLG_PRODUCTS WHERE ID = :p_p2), "
                    "  :p_src, :p_name, :p_conf, :p_status FROM DUAL",
                    {'p_o': oid, 'p_p': pid, 'p_q': item['qty'],
                     'p_u': (item.get('uom') or 'pcs')[:20],
                     'p_pack': item.get('pack_qty'), 'p_p2': pid,
                     'p_src': (item.get('source_text') or '')[:600],
                     'p_name': (item.get('match_name') or '')[:300] or None,
                     'p_conf': item.get('confidence'), 'p_status': item.get('status') or 'ok'})
            PlgMobileController._recalc(db, oid)
        return PlgMobileController.get_order(device, oid).get('data')

    @staticmethod
    def _recalc(db: DatabaseModel, order_id: int) -> None:
        db.execute_query(
            "UPDATE PLG_MOBILE_ORDERS o SET "
            "  ITEM_COUNT = (SELECT COUNT(*) FROM PLG_MOBILE_ORDER_ITEMS i "
            "                 WHERE i.ORDER_ID = o.ID AND i.STATUS <> 'removed'), "
            "  TOTAL_QTY  = (SELECT NVL(SUM(i.QTY),0) FROM PLG_MOBILE_ORDER_ITEMS i "
            "                 WHERE i.ORDER_ID = o.ID AND i.STATUS <> 'removed'), "
            "  TOTAL_AMOUNT = (SELECT NVL(SUM(i.QTY * NVL(i.PRICE,0)),0) FROM PLG_MOBILE_ORDER_ITEMS i "
            "                 WHERE i.ORDER_ID = o.ID AND i.STATUS <> 'removed') "
            "WHERE o.ID = :p_id", {'p_id': order_id})

    # ==================== Заказы ====================

    @staticmethod
    def create_order(device: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ручной заказ из приложения (без голоса) — тот же черновик."""
        lang = payload.get('lang') if payload.get('lang') in LANGS else (device.get('lang') or 'ru')
        parsed = {'intent': 'add', 'items': []}
        for it in (payload.get('items') or []):
            if not it.get('product_id'):
                continue
            parsed['items'].append({
                'product_id': int(it['product_id']), 'qty': float(it.get('qty') or 1),
                'uom': it.get('uom') or 'pcs', 'pack_qty': it.get('pack_qty'),
                'source_text': it.get('source_text') or '', 'match_name': it.get('name'),
                'confidence': 100.0, 'status': 'ok'})
        if not parsed['items']:
            return {'success': False, 'error': 'Нет позиций', 'status': 400}
        try:
            data = PlgMobileController._apply_to_draft(
                device, int(device['store_id']), lang, parsed,
                payload.get('order_id'), payload.get('zone_id'))
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def list_orders(device: Dict[str, Any], status: Optional[str] = None) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PLG_MOBILE_ORDERS WHERE STORE_ID = :p_st"
        params: Dict[str, Any] = {'p_st': int(device['store_id'])}
        if status:
            sql += " AND STATUS = :p_status"
            params['p_status'] = status
        sql += " ORDER BY CREATED_AT DESC"
        lang = device.get('lang') or 'ru'
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _localize(_rows(db.execute_query(sql, params)), lang)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_order(device: Dict[str, Any], order_id: int) -> Dict[str, Any]:
        lang = device.get('lang') or 'ru'
        try:
            with DatabaseModel() as db:
                head = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_MOBILE_ORDERS WHERE ID = :p_id AND STORE_ID = :p_st",
                    {'p_id': order_id, 'p_st': int(device['store_id'])})), lang)
                if not head:
                    return {'success': False, 'error': 'Заказ не найден', 'status': 404}
                items = _localize(_rows(db.execute_query(
                    "SELECT * FROM V_PLG_MOBILE_ORDER_ITEMS WHERE ORDER_ID = :p_id "
                    "AND STATUS <> 'removed' ORDER BY ID", {'p_id': order_id})), lang)
            data = head[0]
            data['items'] = items
            return {'success': True, 'data': data}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def update_item(device: Dict[str, Any], order_id: int, item_id: int,
                    payload: Dict[str, Any]) -> Dict[str, Any]:
        """Уточнение позиции руками: количество и/или выбранный товар."""
        try:
            with DatabaseModel() as db:
                own = _rows(db.execute_query(
                    "SELECT ID FROM PLG_MOBILE_ORDERS WHERE ID = :p_id AND STORE_ID = :p_st "
                    "AND STATUS = 'draft'",
                    {'p_id': order_id, 'p_st': int(device['store_id'])}))
                if not own:
                    return {'success': False, 'error': 'Черновик не найден', 'status': 404}
                sets, params = [], {'p_item': item_id, 'p_order': order_id}
                if payload.get('qty') is not None:
                    sets.append("QTY = :p_qty")
                    params['p_qty'] = float(payload['qty'])
                if payload.get('product_id'):
                    sets.append("PRODUCT_ID = :p_prod")
                    sets.append("PRICE = (SELECT PRICE FROM PLG_PRODUCTS WHERE ID = :p_prod2)")
                    sets.append("STATUS = 'ok'")
                    sets.append("CONFIDENCE = 100")
                    params['p_prod'] = int(payload['product_id'])
                    params['p_prod2'] = int(payload['product_id'])
                if not sets:
                    return {'success': False, 'error': 'Нечего менять', 'status': 400}
                r = db.execute_query(
                    f"UPDATE PLG_MOBILE_ORDER_ITEMS SET {', '.join(sets)} "
                    "WHERE ID = :p_item AND ORDER_ID = :p_order", params)
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                PlgMobileController._learn_synonym(db, item_id, payload.get('product_id'),
                                                   device.get('lang') or 'ru')
                PlgMobileController._recalc(db, order_id)
            return PlgMobileController.get_order(device, order_id)
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _learn_synonym(db: DatabaseModel, item_id: int, product_id: Optional[int],
                       lang: str) -> None:
        """
        Если менеджер вручную выбрал товар для непонятой фразы — запоминаем эту
        фразу как синоним. Словарь пополняется работой, а не отдельным проектом
        по его наполнению: «помидоры» становятся «Томатами» после первого раза.
        """
        if not product_id:
            return
        try:
            rows = _rows(db.execute_query(
                "SELECT SOURCE_TEXT FROM PLG_MOBILE_ORDER_ITEMS WHERE ID = :p_id",
                {'p_id': item_id}))
            phrase = (rows[0].get('source_text') if rows else '') or ''
            from models.plg_voice import normalize, NUMBER_WORDS, UNITS
            words = [w for w in normalize(phrase).split()
                     if w not in NUMBER_WORDS.get(lang, {}) and w not in UNITS.get(lang, {})
                     and not w.replace('.', '').isdigit()]
            phrase = ' '.join(words).strip()
            if len(phrase) < 3:
                return
            db.execute_query(
                "INSERT INTO PLG_VOICE_SYNONYMS (PRODUCT_ID, LANG, PHRASE, SOURCE, CREATED_BY) "
                "SELECT :p_p, :p_l, :p_ph, 'learned', 'voice' FROM DUAL WHERE NOT EXISTS "
                "(SELECT 1 FROM PLG_VOICE_SYNONYMS WHERE LANG = :p_l2 AND PHRASE = :p_ph2 "
                " AND PRODUCT_ID = :p_p2)",
                {'p_p': int(product_id), 'p_l': lang, 'p_ph': phrase[:200],
                 'p_l2': lang, 'p_ph2': phrase[:200], 'p_p2': int(product_id)})
        except Exception:                                        # noqa: BLE001
            pass

    @staticmethod
    def remove_item(device: Dict[str, Any], order_id: int, item_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE PLG_MOBILE_ORDER_ITEMS SET STATUS = 'removed' WHERE ID = :p_i "
                    "AND ORDER_ID IN (SELECT ID FROM PLG_MOBILE_ORDERS WHERE ID = :p_o "
                    "AND STORE_ID = :p_st AND STATUS = 'draft')",
                    {'p_i': item_id, 'p_o': order_id, 'p_st': int(device['store_id'])})
                PlgMobileController._recalc(db, order_id)
            return PlgMobileController.get_order(device, order_id)
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def submit_order(device: Dict[str, Any], order_id: int) -> Dict[str, Any]:
        """
        Отправка черновика. Три проверки, каждая закрывает свой способ
        отправить в закупку мусор.
        """
        try:
            cur = PlgMobileController.get_order(device, order_id)
            if not cur.get('success'):
                return cur
            data = cur['data']
            if data.get('status') != 'draft':
                return {'success': False, 'error': 'Заказ уже отправлен', 'status': 409}
            items = data.get('items') or []
            if not items:
                return {'success': False, 'error': 'В заказе нет позиций', 'status': 400}
            problems = [i for i in items if i.get('status') in ('unmatched', 'ambiguous')
                        or not i.get('product_id')]
            if problems:
                return {'success': False, 'status': 409,
                        'error': 'Есть нераспознанные позиции — уточните товар',
                        'items': [i.get('id') for i in problems]}
            limit = float(device.get('order_limit') or 0)
            if limit and float(data.get('total_amount') or 0) > limit:
                return {'success': False, 'status': 403,
                        'error': f"Сумма заказа выше лимита устройства ({limit:.0f})"}
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PLG_MOBILE_ORDERS SET STATUS = 'submitted', "
                    "SUBMITTED_AT = SYSTIMESTAMP WHERE ID = :p_id AND STATUS = 'draft'",
                    {'p_id': order_id})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
            return PlgMobileController.get_order(device, order_id)
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel_order(device: Dict[str, Any], order_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE PLG_MOBILE_ORDERS SET STATUS = 'cancelled' WHERE ID = :p_id "
                    "AND STORE_ID = :p_st AND STATUS = 'draft'",
                    {'p_id': order_id, 'p_st': int(device['store_id'])})
            return PlgMobileController.get_order(device, order_id)
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    # ==================== Бэк-офис: приёмка заказов из зала ====================

    @staticmethod
    def review_order(order_id: int, decision: str, note: str, username: str) -> Dict[str, Any]:
        if decision not in ('accepted', 'rejected'):
            return {'success': False, 'error': 'Некорректное решение', 'status': 400}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "UPDATE PLG_MOBILE_ORDERS SET STATUS = :p_st, REVIEWED_BY = :p_by, "
                    "REVIEW_NOTE = :p_note, REVIEWED_AT = SYSTIMESTAMP "
                    "WHERE ID = :p_id AND STATUS = 'submitted'",
                    {'p_st': decision, 'p_by': username, 'p_note': (note or '')[:1000],
                     'p_id': order_id})
                if not r.get('success'):
                    return {'success': False, 'error': r.get('message')}
                if not r.get('rowcount'):
                    return {'success': False, 'error': 'Заказ не в статусе «отправлен»',
                            'status': 409}
            return {'success': True}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def office_orders(store_id: Optional[int], status: Optional[str], lang: str) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PLG_MOBILE_ORDERS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if store_id:
            sql += " AND STORE_ID = :p_st"
            params['p_st'] = store_id
        if status:
            sql += " AND STATUS = :p_status"
            params['p_status'] = status
        sql += " ORDER BY CREATED_AT DESC"
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _localize(_rows(db.execute_query(sql, params)), lang)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def voice_log(store_id: Optional[int], lang: str, limit: int = 200) -> Dict[str, Any]:
        sql = "SELECT * FROM V_PLG_VOICE_LOG WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if store_id:
            sql += " AND STORE_ID = :p_st"
            params['p_st'] = store_id
        sql += " ORDER BY CREATED_AT DESC FETCH FIRST :p_lim ROWS ONLY"
        params['p_lim'] = limit
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _localize(_rows(db.execute_query(sql, params)), lang)}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def synonyms(lang: Optional[str] = None) -> Dict[str, Any]:
        sql = ("SELECT s.ID, s.PRODUCT_ID, p.NAME_RU AS PRODUCT_NAME, s.CATEGORY_ID, "
               "c.NAME_RU AS CATEGORY_NAME, s.LANG, s.PHRASE, s.WEIGHT, s.HIT_COUNT, "
               "s.SOURCE, s.CREATED_BY, s.CREATED_AT FROM PLG_VOICE_SYNONYMS s "
               "LEFT JOIN PLG_PRODUCTS p ON p.ID = s.PRODUCT_ID "
               "LEFT JOIN PLG_CATEGORIES c ON c.ID = s.CATEGORY_ID")
        params: Dict[str, Any] = {}
        if lang:
            sql += " WHERE s.LANG = :p_lang"
            params['p_lang'] = lang
        sql += " ORDER BY s.LANG, s.PHRASE"
        try:
            with DatabaseModel() as db:
                return {'success': True, 'data': _rows(db.execute_query(sql, params))}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def save_synonym(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        from models.plg_voice import normalize
        phrase = normalize(payload.get('phrase') or '')
        if len(phrase) < 2:
            return {'success': False, 'error': 'Слишком короткая фраза', 'status': 400}
        if not payload.get('product_id') and not payload.get('category_id'):
            return {'success': False, 'error': 'Нужен товар или категория', 'status': 400}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO PLG_VOICE_SYNONYMS (PRODUCT_ID, CATEGORY_ID, LANG, PHRASE, "
                    "WEIGHT, SOURCE, CREATED_BY) VALUES (:p_p, :p_c, :p_l, :p_ph, :p_w, "
                    "'manual', :p_by)",
                    {'p_p': payload.get('product_id'), 'p_c': payload.get('category_id'),
                     'p_l': payload.get('lang') if payload.get('lang') in LANGS else 'ru',
                     'p_ph': phrase[:200], 'p_w': float(payload.get('weight') or 1),
                     'p_by': username})
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

    @staticmethod
    def delete_synonym(syn_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query("DELETE FROM PLG_VOICE_SYNONYMS WHERE ID = :p_id",
                                     {'p_id': syn_id})
                return {'success': bool(r.get('success')), 'error': r.get('message')}
        except Exception as e:                                   # noqa: BLE001
            return {'success': False, 'error': str(e)}

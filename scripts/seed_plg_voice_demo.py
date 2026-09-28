#!/usr/bin/env python3
"""
Демо-данные голосового контура: устройства и заказы из торгового зала.

Нужны, чтобы раздел «Заказы из зала» и методичка показывали работу системы
на осмысленных фразах, а не на тестовом мусоре. Фразы намеренно разные
по сложности: от простой до такой, где часть позиций не распознаётся —
именно этот случай важно показать честно.

Запуск: python3 scripts/seed_plg_voice_demo.py [--store CODE] [--reset]
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel
from controllers.plg_mobile_controller import PlgMobileController as C

DEVICES = [
    {'display_name': 'iPhone · зав. секцией фреш', 'username': 'ivanov',
     'lang': 'ru', 'order_limit': 20000, 'platform': 'ios', 'app_version': '1.2.0'},
    {'display_name': 'Android · мерчандайзер зала', 'username': 'popescu',
     'lang': 'ro', 'order_limit': 8000, 'platform': 'android', 'app_version': '1.2.0'},
]

# Фразы подобраны под реальный ассортимент набора: точные названия берём
# из каталога магазина, чтобы демонстрация не зависела от случайных совпадений.
PHRASES = [
    ('ru', 'закажи пять ящиков {p0}'),
    ('ru', 'добавь {p1} двенадцать штук и {p2} десять килограмм'),
    ('ru', 'нужно три {p3}'),
    ('ro', 'comanda doua lazi de {p4}'),
    ('ru', 'закажи два ящика свежей зелени с грядки'),   # намеренно не распознаётся
]


def catalog_names(store_id: int, need: int = 6):
    """
    Берём товары, чьё короткое имя встречается в каталоге ОДИН раз.

    Иначе демонстрация показывает не работу системы, а её беспомощность:
    в наборе четыре позиции «Бананы Cricova» разной фасовки, и фраза
    «закажи пять ящиков бананов Cricova» честно уходит в «уточните» —
    для витрины это выглядит как сбой, хотя поведение верное.
    """
    items = C._catalog(store_id, 'ru')
    counts = {}
    for i in items:
        counts[i['name'].split(',')[0].strip()] = counts.get(i['name'].split(',')[0].strip(), 0) + 1
    out, seen_cat = [], set()
    for i in items:
        short = i['name'].split(',')[0].strip()
        if counts[short] != 1 or not i.get('is_fresh'):
            continue
        if i.get('category_id') in seen_cat and len(seen_cat) < 4:
            continue
        seen_cat.add(i.get('category_id'))
        out.append(short)
        if len(out) >= need:
            break
    return out or [i['name'].split(',')[0] for i in items[:need]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--store', help='код магазина (по умолчанию первый набора)')
    ap.add_argument('--reset', action='store_true', help='удалить прежние демо-заказы')
    args = ap.parse_args()

    with DatabaseModel() as db:
        sql = "SELECT ID, CODE, NAME_RU FROM PLG_STORES"
        params = {}
        if args.store:
            sql += " WHERE CODE = :p_c"
            params['p_c'] = args.store
        sql += " ORDER BY ID"
        rows = db.execute_query(sql, params)['data']
        if not rows:
            print('магазин не найден'); return
        store_id, code, name = rows[0]
        if args.reset:
            db.execute_query(
                "DELETE FROM PLG_VOICE_LOG WHERE STORE_ID = :p_s", {'p_s': store_id})
            db.execute_query(
                "DELETE FROM PLG_MOBILE_ORDERS WHERE STORE_ID = :p_s", {'p_s': store_id})
            db.execute_query(
                "DELETE FROM PLG_MOBILE_DEVICES WHERE STORE_ID = :p_s", {'p_s': store_id})
            db.connection.commit()
            print('прежние демо-данные удалены')
    print(f'магазин {code} — {name}')

    names = catalog_names(store_id)
    tokens = {f'p{i}': names[i] if i < len(names) else 'товар' for i in range(6)}

    devices = []
    for d in DEVICES:
        r = C.create_device(dict(d, store_id=store_id), 'system')
        if not r.get('success'):
            print('  устройство:', r.get('error')); continue
        p = C.pair({'pair_code': r['pair_code'], 'platform': d['platform'],
                    'app_version': d['app_version']})
        if not p.get('success'):
            print('  сопряжение:', p.get('error')); continue
        devices.append((d, p['token']))
        print(f"  устройство «{d['display_name']}» сопряжено")

    if not devices:
        return

    order_ids = []
    for i, (lang, tpl) in enumerate(PHRASES):
        d, token = devices[i % len(devices)]
        device = C.device_by_token(token)
        text = tpl.format(**tokens)
        res = C.voice(device, {'text': text, 'lang': lang, 'asr_conf': 88 + i,
                               'duration_ms': 1400 + i * 220})
        parsed = res.get('data', {}).get('parsed', {}) if res.get('success') else {}
        order = res.get('data', {}).get('order') if res.get('success') else None
        print(f"  «{text[:52]}…» → {parsed.get('intent')}, "
              f"распознано {parsed.get('matched')}/{len(parsed.get('items') or [])}")
        if order:
            order_ids.append((order['id'], device))

    # Часть заказов доводим до отправки, один оставляем черновиком,
    # один принимаем — чтобы в разделе были видны все состояния.
    for n, (oid, device) in enumerate(order_ids):
        cur = C.get_order(device, oid).get('data') or {}
        if any(it.get('status') != 'ok' for it in cur.get('items', [])):
            continue                       # с нераспознанным оставляем черновиком
        if n % 3 == 2:
            continue
        C.submit_order(device, oid)
        if n % 3 == 0:
            C.review_order(oid, 'accepted', 'проверено категорийным менеджером', 'system')
    print(f'создано заказов: {len(order_ids)}')


if __name__ == '__main__':
    main()

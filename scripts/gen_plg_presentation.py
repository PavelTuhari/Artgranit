#!/usr/bin/env python3
"""
Дорабатывает презентацию модуля «Планограммы»:

  1. вставляет слайды со схемами бизнес-процессов (BPMN, кликабельные фигуры);
  2. добавляет на КАЖДЫЙ слайд панель живых ссылок в работающую систему;
  3. перенумеровывает слайды.

Схемы рисуются из той же спецификации, что и draw.io-версия
(scripts/gen_plg_processes.py), поэтому презентация и бэк-офис не разъезжаются.

Запуск: python3 scripts/gen_plg_presentation.py
"""
from __future__ import annotations

import os
import re
import sys
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

from gen_plg_processes import PROCESSES, SIZE  # noqa: E402

DECK = os.path.join(ROOT, 'docs', 'Planograms', 'presentation.html')
MODULE = '/UNA.md/orasldev/planograms'

FILL = {
    'task':    ('#1e3a5f', '#3b82f6', '#e8eef7'),
    'task2':   ('#14532d', '#22c55e', '#e8eef7'),
    'task3':   ('#4a2c0a', '#f59e0b', '#e8eef7'),
    'gateway': ('#3f2d0b', '#f59e0b', '#fde68a'),
    'start':   ('#14532d', '#22c55e', '#dcfce7'),
    'end':     ('#4c1414', '#ef4444', '#fee2e2'),
}


def border_point(box, tx, ty):
    x, y, w, h = box
    cx, cy = x + w / 2, y + h / 2
    dx, dy = tx - cx, ty - cy
    if not dx and not dy:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else 1e9
    sy = (h / 2) / abs(dy) if dy else 1e9
    k = min(sx, sy)
    return cx + dx * k, cy + dy * k


def wrap(text, max_chars):
    words, lines, cur = str(text).split(' '), [], ''
    for w in words:
        if len((cur + ' ' + w).strip()) > max_chars:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return lines


def render_bpmn(proc, scale=1.0, font=12):
    """Рисует схему процесса в SVG. Узлы со ссылкой оборачиваются в <a>."""
    nodes = {n[0]: n for n in proc['nodes']}
    boxes = {}
    for nid, label, kind, x, y, link in proc['nodes']:
        w, h = SIZE[kind]
        boxes[nid] = (x, y, w, h)

    xs = [b[0] for b in boxes.values()] + [b[0] + b[2] for b in boxes.values()]
    ys = [b[1] for b in boxes.values()] + [b[1] + b[3] for b in boxes.values()]
    pad = 22
    minx, miny = min(xs) - pad, min(ys) - pad
    W, H = max(xs) - minx + pad, max(ys) - miny + pad

    p = [f'<defs><marker id="bpa{proc["code"]}" markerWidth="9" markerHeight="9" refX="8" '
         f'refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#64748b"/></marker></defs>']

    for e in proc['edges']:
        eid, src, dst = e[0], e[1], e[2]
        label = e[3] if len(e) > 3 else ''
        a, b = boxes[src], boxes[dst]
        ac = (a[0] + a[2] / 2, a[1] + a[3] / 2)
        bc = (b[0] + b[2] / 2, b[1] + b[3] / 2)
        sx, sy = border_point(a, *bc)
        tx, ty = border_point(b, *ac)
        if abs(bc[0] - ac[0]) >= abs(bc[1] - ac[1]):
            m = (sx + tx) / 2
            d = f'M {sx} {sy} L {m} {sy} L {m} {ty} L {tx} {ty}'
        else:
            m = (sy + ty) / 2
            d = f'M {sx} {sy} L {sx} {m} L {tx} {m} L {tx} {ty}'
        p.append(f'<path d="{d}" fill="none" stroke="#64748b" stroke-width="1.6" '
                 f'marker-end="url(#bpa{proc["code"]})"/>')
        if label:
            lx, ly = (sx + tx) / 2, (sy + ty) / 2
            p.append(f'<rect x="{lx - len(label) * 3.2 - 5}" y="{ly - 9}" '
                     f'width="{len(label) * 6.4 + 10}" height="15" rx="3" fill="#111827" opacity=".93"/>')
            p.append(f'<text x="{lx}" y="{ly + 2}" text-anchor="middle" fill="#94a3b8" '
                     f'font-size="10">{escape(label)}</text>')

    for nid, label, kind, x, y, link in proc['nodes']:
        w, h = SIZE[kind]
        fill, stroke, fc = FILL[kind]
        sw = 3 if kind == 'end' else 1.6
        if kind == 'gateway':
            cx, cy = x + w / 2, y + h / 2
            shape = (f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        elif kind in ('start', 'end'):
            shape = (f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        else:
            shape = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
        fs = 10 if kind in ('gateway', 'start', 'end') else font
        lines = wrap(label, max(7, int(w / (fs * 0.52))))[:4]
        top = y + h / 2 - (len(lines) - 1) * (fs * 0.58) + 1
        text = ''.join(
            f'<text x="{x + w / 2}" y="{top + i * (fs + 2)}" text-anchor="middle" '
            f'fill="{fc}" font-size="{fs}" font-weight="500">{escape(ln)}</text>'
            for i, ln in enumerate(lines))
        g = f'<g>{shape}{text}</g>'
        p.append(f'<a href="{escape(link)}" target="_blank"><title>{escape(label)} — открыть раздел</title>{g}</a>'
                 if link else g)

    return (f'<svg viewBox="{minx} {miny} {W} {H}" width="100%" class="bpm" '
            f'style="display:block">{"".join(p)}</svg>')


# ==================== Живые ссылки по слайдам ====================
# Ключ — номер слайда в исходной колоде (до вставки новых).
LIVE = {
    1: [('Открыть работающую систему', f'{MODULE}#overview', ''),
        ('Документация модуля', f'{MODULE}/docs', 'blue')],
    2: [('Как это выглядит сейчас: реестр планограмм', f'{MODULE}#plglist', ''),
        ('График завоза', f'{MODULE}#logistics', 'blue')],
    3: [('Выкладка', f'{MODULE}#storemap', ''),
        ('Заказ', f'{MODULE}#forecast', 'blue'),
        ('Завоз', f'{MODULE}#logistics', 'blue'),
        ('Рынок', f'{MODULE}#competitors', 'blue')],
    4: [('Открыть карту зала с живой проходимостью', f'{MODULE}#storemap', ''),
        ('Сводка дня', f'{MODULE}#overview', 'blue')],
    5: [('Реестр планограмм со статусами', f'{MODULE}#plglist', ''),
        ('История изменений', f'{MODULE}#history', 'blue')],
    6: [('Конфигуратор моделей прогноза', f'{MODULE}#forecast', '')],
    7: [('Прогоны backtest с метриками', f'{MODULE}#forecast', ''),
        ('Аналитика спроса', f'{MODULE}#analytics', 'blue')],
    8: [('Рекомендуемый заказ', f'{MODULE}#forecast', ''),
        ('Карточки товаров', f'{MODULE}#products', 'blue')],
    9: [('Открыть диаграмму Ганта', f'{MODULE}#logistics', ''),
        ('Задачи мерчандайзинга', f'{MODULE}#tasks', 'blue')],
    10: [('Граф связей с поставщиками', f'{MODULE}#suppliers', ''),
         ('Акции и промо', f'{MODULE}#promos', 'blue')],
    11: [('Ценовой индекс конкурентов', f'{MODULE}#competitors', ''),
         ('Ассортимент и цены', f'{MODULE}#products', 'blue')],
    12: [('Бенчмарк рынков стран', f'{MODULE}#markets', ''),
         ('Оборудование зала', f'{MODULE}#equipment', 'blue')],
    13: [('Генератор тестовых данных', f'{MODULE}#testdata', ''),
         ('Наборы и журнал прогонов', f'{MODULE}#testdata', 'blue')],
    14: [('Открыть систему', f'{MODULE}#overview', ''),
         ('Схемы бизнес-процессов', f'{MODULE}#processes', 'blue'),
         ('Документация', f'{MODULE}/docs', 'blue')],
}


def livebar(links, hint=''):
    items = ''.join(
        f'<a class="live {cls}" href="{href}" target="_blank" rel="noopener">{escape(text)}</a>'
        for text, href, cls in links)
    tail = f'<span class="hint">{escape(hint)}</span>' if hint else ''
    return f'<div class="foot"><div class="livebar">{items}{tail}</div></div>'


def process_slides():
    """Три слайда: карта процессов и две развёрнутые схемы."""
    tiles = ''.join(f"""
      <a class="doc-tile" href="{MODULE}#processes" target="_blank" rel="noopener">
        <div class="n">{p['sort']}</div>
        <div>
          <h3>{escape(p['ru'])}</h3>
          <p>{escape(p['dru'][:118])}…</p>
        </div>
      </a>""" for p in PROCESSES)

    s_map = f"""
<!-- BPMN: карта процессов -->
<section class="slide">
  <div class="kicker">Бизнес-процессы</div>
  <h2>Пять процессов, которые закрывает модуль</h2>
  <p>Схемы описаны в нотации BPMN и хранятся в формате draw.io — тот же файл
     открывается в diagrams.net. Каждая фигура на схеме кликабельна и ведёт
     в соответствующий раздел работающей системы.</p>
  <div class="proc-grid">{tiles}</div>
  <div class="card accent" style="margin-top:18px">
    <h3>Почему это не «картинка в презентации»</h3>
    <p>Схемы лежат в Oracle и редактируются в бэк-офисе: их можно выгрузить
       в .drawio, изменить в diagrams.net и загрузить обратно. Ссылки на разделы
       живут внутри схемы как штатные гиперссылки draw.io.</p>
  </div>
  {livebar([('Раздел «Бизнес-процессы» в системе', f'{MODULE}#processes', ''),
            ('Документация', f'{MODULE}/docs', 'blue')],
           'клик по любой фигуре на следующих слайдах открывает раздел системы')}
  <div class="num">X</div>
</section>"""

    def slide(proc, kicker, extra):
        return f"""
<!-- BPMN: {proc['code']} -->
<section class="slide">
  <div class="kicker">{kicker}</div>
  <h2>{escape(proc['ru'])}</h2>
  <p>{escape(proc['dru'])}</p>
  <div class="viz" style="padding:10px">{render_bpmn(proc)}</div>
  <div class="legend">
    <div><i style="background:#22c55e"></i>событие</div>
    <div><i style="background:#3b82f6"></i>задача</div>
    <div><i style="background:#f59e0b"></i>шлюз / решение</div>
    <div><i style="background:#ef4444"></i>завершение</div>
    <div style="margin-left:auto">{extra}</div>
  </div>
  {livebar([(t, h, c) for t, h, c in extra_links[proc['code']]],
           'фигуры схемы кликабельны')}
  <div class="num">X</div>
</section>"""

    global extra_links
    extra_links = {
        'planogram-change': [('Реестр планограмм', f'{MODULE}#plglist', ''),
                             ('Карта зала', f'{MODULE}#storemap', 'blue'),
                             ('История изменений', f'{MODULE}#history', 'blue')],
        'order-forecast': [('Модели прогноза', f'{MODULE}#forecast', ''),
                           ('Аналитика спроса', f'{MODULE}#analytics', 'blue'),
                           ('Акции', f'{MODULE}#promos', 'blue')],
        'inbound-delivery': [('Диаграмма Ганта', f'{MODULE}#logistics', ''),
                             ('Поставщики', f'{MODULE}#suppliers', 'blue')],
    }
    by_code = {p['code']: p for p in PROCESSES}
    return (s_map
            + slide(by_code['planogram-change'], 'Процесс · выкладка', 'клик по фигуре → раздел системы')
            + slide(by_code['order-forecast'], 'Процесс · заказ', 'клик по фигуре → раздел системы')
            + slide(by_code['inbound-delivery'], 'Процесс · завоз', 'клик по фигуре → раздел системы'))


def main():
    with open(DECK, encoding='utf-8') as f:
        deck = f.read()

    # --- стили плиток процессов
    if '.proc-grid' not in deck:
        deck = deck.replace('.steps{ counter-reset:s; }', """.proc-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:12px; }
.doc-tile{ display:flex; gap:14px; background:var(--panel); border:1px solid var(--border);
  border-radius:11px; padding:14px 16px; text-decoration:none; color:inherit;
  border-left:3px solid var(--accent); transition:background .15s; }
.doc-tile:hover{ background:var(--panel2); }
.doc-tile .n{ width:28px; height:28px; border-radius:8px; background:var(--accent); color:#fff;
  display:flex; align-items:center; justify-content:center; font-weight:800; font-size:14px; flex-shrink:0; }
.doc-tile h3{ font-size:15px; margin-bottom:4px; }
.doc-tile p{ font-size:12.5px; color:var(--muted); margin:0; line-height:1.45; }
.steps{ counter-reset:s; }""", 1)

    # --- живые ссылки на каждый исходный слайд
    slides = re.findall(r'<section class="slide.*?</section>', deck, re.S)
    for i, sl in enumerate(slides, start=1):
        links = LIVE.get(i)
        if not links:
            continue
        bar = livebar(links)
        if '<div class="foot">' in sl:
            new_sl = re.sub(r'<div class="foot">.*?</div>\s*(?=<div class="num">)',
                            bar.replace('<div class="foot">', '<div class="foot">', 1) + '\n  ',
                            sl, count=1, flags=re.S)
            # сохраняем прежний текст подвала как подсказку
            old_foot = re.search(r'<div class="foot">(.*?)</div>\s*<div class="num">', sl, re.S)
            if old_foot and 'ПОКАЗАТЬ ВЖИВУЮ' in old_foot.group(1):
                hint = re.sub(r'<[^>]+>', '', old_foot.group(1)).strip()
                hint = hint.replace('ПОКАЗАТЬ ВЖИВУЮ', '').strip(' · ')
                new_sl = new_sl.replace('</div></div>\n  <div class="num">',
                                        f'<span class="hint">{escape(hint)}</span></div></div>\n  <div class="num">')
        else:
            new_sl = sl.replace('<div class="num">', bar + '\n  <div class="num">', 1)
        deck = deck.replace(sl, new_sl, 1)

    # --- вставляем слайды процессов после третьего
    slides = re.findall(r'<section class="slide.*?</section>', deck, re.S)
    third = slides[2]
    deck = deck.replace(third, third + '\n' + process_slides(), 1)

    # --- перенумерация
    n = [0]

    def renum(m):
        n[0] += 1
        return f'<div class="num">{n[0]}</div>'

    deck = re.sub(r'<div class="num">[^<]*</div>', renum, deck)

    with open(DECK, 'w', encoding='utf-8') as f:
        f.write(deck)

    total = len(re.findall(r'<section class="slide', deck))
    live = len(re.findall(r'class="live', deck))
    bpmn = len(re.findall(r'class="bpm"', deck))
    print(f'слайдов: {total}, живых ссылок: {live}, BPMN-схем: {bpmn}')


if __name__ == '__main__':
    main()

"""
Выбор источника топлива: любые комбинации импорт / внутренний рынок ↔
своя или чужая нефтебаза ↔ заправка.

Задача, которую решает модуль. Один и тот же литр А-95 на станции
в Кагуле может приехать четырьмя разными путями:

    импорт (Румыния) → своя нефтебаза → АЗС
    импорт (Греция)  → чужая нефтебаза (хранение по тарифу) → АЗС
    внутренний рынок → своя нефтебаза → АЗС
    внутренний рынок → напрямую на АЗС (без перевалки)

У путей разная цена литра, разное плечо, разная минимальная партия
и разные ограничения по объёму. Выбирать «самый дешёвый» построчно
нельзя: дешёвый импорт имеет плечо 9-14 дней и не спасёт станцию,
у которой топливо кончится завтра, а ёмкость своей нефтебазы конечна
и достаётся тем, кому она нужнее.

Поэтому здесь честная ОПТИМИЗАЦИЯ, а не эвристика: задача сводится
к потоку минимальной стоимости в сети

    источники → (нефтебазы) → потребности станций

и решается алгоритмом последовательных кратчайших путей с потенциалами
Джонсона. Граф маленький (единицы источников, единицы баз, сотни
потребностей), поэтому точное решение считается за миллисекунды —
эвристика тут не нужна и не оправдана.

Что входит в стоимость литра (landed cost):
  цена поставщика + транспорт + перевалка на базе (своя дешевле чужой)
  + акциз и пошлина для импорта + стоимость денег за время плеча.

Жёсткие ограничения (не штрафы, а именно запреты):
  * путь с плечом длиннее, чем осталось до сухого бака, недопустим;
  * объём сверх свободной ёмкости резервуара недопустим;
  * запас нефтебазы и её суточная пропускная способность конечны.

Oracle-объекты: sql/110_peco_algorithms.sql
"""
from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional, Tuple

INF = float('inf')


class MinCostFlow:
    """
    Поток минимальной стоимости: последовательные кратчайшие пути
    с потенциалами Джонсона (Дейкстра на неотрицательных сведённых весах).

    Реализация на списках смежности с рёбрами-парами: обратное ребро
    хранится рядом, что даёт отмену уже отправленного потока — без неё
    жадный проход застревает в локальном оптимуме.
    """

    def __init__(self, n: int):
        self.n = n
        self.graph: List[List[List[float]]] = [[] for _ in range(n)]
        # ребро: [to, capacity, cost, index_of_reverse]

    def add_edge(self, u: int, v: int, cap: float, cost: float) -> None:
        self.graph[u].append([v, cap, cost, len(self.graph[v])])
        self.graph[v].append([u, 0.0, -cost, len(self.graph[u]) - 1])

    def flow(self, s: int, t: int, want: float = INF) -> Tuple[float, float]:
        """Возвращает (пропущенный поток, суммарная стоимость)."""
        n = self.n
        res_flow, res_cost = 0.0, 0.0
        pot = [0.0] * n                      # потенциалы: держим веса неотрицательными
        while want > 1e-9:
            dist = [INF] * n
            prev_v = [-1] * n
            prev_e = [-1] * n
            dist[s] = 0.0
            pq = [(0.0, s)]
            while pq:
                d, v = heapq.heappop(pq)
                if d > dist[v] + 1e-12:
                    continue
                for i, e in enumerate(self.graph[v]):
                    to, cap, cost, _rev = e
                    if cap <= 1e-9:
                        continue
                    nd = d + cost + pot[v] - pot[int(to)]
                    if nd < dist[int(to)] - 1e-12:
                        dist[int(to)] = nd
                        prev_v[int(to)] = v
                        prev_e[int(to)] = i
                        heapq.heappush(pq, (nd, int(to)))
            if dist[t] == INF:
                break                        # больше путей нет
            for v in range(n):
                if dist[v] < INF:
                    pot[v] += dist[v]
            # Узкое место найденного пути
            d = want
            v = t
            while v != s:
                d = min(d, self.graph[prev_v[v]][prev_e[v]][1])
                v = prev_v[v]
            v = t
            while v != s:
                e = self.graph[prev_v[v]][prev_e[v]]
                e[1] -= d
                self.graph[int(e[0])][int(e[3])][1] += d
                v = prev_v[v]
            res_flow += d
            res_cost += d * pot[t]
            want -= d
        return res_flow, res_cost


def landed_cost_per_l(path: Dict[str, Any], money_rate_year: float = 0.14) -> float:
    """
    Полная стоимость литра по пути: не только цена поставщика.

    Стоимость денег добавлена намеренно. Импортная партия на 400 тысяч
    литров с плечом 14 дней замораживает оборотные средства на две недели,
    и при ставке 14 % годовых это заметная величина — сравнивать импорт
    с внутренним рынком без неё нечестно.
    """
    price = float(path.get('price_per_l') or 0)
    transport = float(path.get('transport_per_l') or 0)
    handling = float(path.get('handling_per_l') or 0)
    duty = float(path.get('duty_per_l') or 0)
    lead = float(path.get('lead_days') or 0)
    money = price * money_rate_year * (lead / 365.0)
    return round(price + transport + handling + duty + money, 5)


def solve_sourcing(demands: List[Dict[str, Any]], paths: List[Dict[str, Any]],
                   depots: Optional[List[Dict[str, Any]]] = None,
                   money_rate_year: float = 0.14) -> Dict[str, Any]:
    """
    Распределение потребностей станций по путям снабжения.

    demands: [{'key', 'station_id', 'grade_code', 'liters', 'days_to_dry'}]
    paths:   [{'code', 'source_code', 'grade_code', 'depot_id'|None,
               'station_id'|None, 'lead_days', 'price_per_l',
               'transport_per_l', 'handling_per_l', 'duty_per_l',
               'available_l', 'min_lot_l'}]
    depots:  [{'id', 'grade_code', 'available_l', 'throughput_l_day'}]

    Устройство сети:

        исток ──▶ путь ──▶ [нефтебаза] ──▶ потребность ──▶ сток

    Нефтебаза — это УЗКОЕ МЕСТО, а не строка прайса: пути, идущие через
    неё, конкурируют за один и тот же ограниченный объём (остаток плюс
    суточная пропускная способность налива). Ограничение навешено на
    ребро «вход базы → выход базы», поэтому оптимизатор сам решает, кому
    из станций достанется дефицитный ресурс — по стоимости и срочности.

    Про атрибуцию. Литры в резервуаре базы обезличены: если базу питают
    два импортных контракта, сказать, «чей» литр уехал на конкретную
    станцию, нельзя — и притворяться, что можно, было бы враньём.
    Поэтому результат двухслойный:
      allocations   — что получила станция и каким маршрутом (через какую базу);
      replenishment — чем при этом пополнялась сама база.
    """
    if not demands:
        return {'success': True, 'allocations': [], 'replenishment': [],
                'uncovered': [], 'total_liters': 0.0, 'total_cost': 0.0}
    if not paths:
        return {'success': False, 'error': 'Не задано ни одного пути снабжения'}

    depots = depots or []
    dep_index: Dict[Tuple[int, str], int] = {}
    for d in depots:
        dep_index[(int(d['id']), str(d['grade_code']))] = len(dep_index)

    P, D, N = len(paths), len(dep_index), len(demands)
    src = 0
    p_node = lambda i: 1 + i
    din = lambda k: 1 + P + k
    dout = lambda k: 1 + P + D + k
    d_node = lambda j: 1 + P + 2 * D + j
    sink = 1 + P + 2 * D + N
    mcf = MinCostFlow(sink + 1)

    # Пропускная способность базы: остаток сверх неснижаемого плюс то,
    # что она физически успеет налить за сутки
    for (did, grade), k in dep_index.items():
        d = next(x for x in depots
                 if int(x['id']) == did and str(x['grade_code']) == grade)
        cap = max(0.0, min(float(d.get('available_l') or 0),
                           float(d.get('throughput_l_day') or INF)))
        mcf.add_edge(din(k), dout(k), cap, 0.0)

    for i, p in enumerate(paths):
        avail = max(0.0, float(p.get('available_l') or 0))
        if avail > 0:
            mcf.add_edge(src, p_node(i), avail, 0.0)

    # Рёбра «путь → база» с полной стоимостью литра на этом пути
    path_to_depot: Dict[int, int] = {}
    for i, p in enumerate(paths):
        if not p.get('depot_id'):
            continue
        key = (int(p['depot_id']), str(p.get('grade_code') or ''))
        if key not in dep_index:
            continue
        k = dep_index[key]
        path_to_depot[i] = k
        mcf.add_edge(p_node(i), din(k), max(0.0, float(p.get('available_l') or 0)),
                     landed_cost_per_l(p, money_rate_year))

    reasons: Dict[str, str] = {}
    depot_edge_ref: Dict[Tuple[int, int], Tuple[int, int]] = {}
    direct_edge_ref: Dict[Tuple[int, int], Tuple[int, int]] = {}

    for j, dem in enumerate(demands):
        need = float(dem['liters'])
        if need <= 0:
            continue
        mcf.add_edge(d_node(j), sink, need, 0.0)
        served = False
        for i, p in enumerate(paths):
            if p.get('grade_code') and p['grade_code'] != dem['grade_code']:
                continue
            if p.get('station_id') and int(p['station_id']) != int(dem['station_id']):
                continue
            dtd = dem.get('days_to_dry')
            if dtd is not None and float(p.get('lead_days') or 0) > float(dtd) + 1e-9:
                # Путь не успевает физически: это запрет, а не штраф
                reasons.setdefault(dem['key'], 'lead_too_long')
                continue
            if float(p.get('available_l') or 0) <= 0:
                continue
            if i in path_to_depot:
                k = path_to_depot[i]
                # Ребро «выход базы → потребность» заводим один раз на пару
                if (k, j) not in depot_edge_ref:
                    depot_edge_ref[(k, j)] = (dout(k), len(mcf.graph[dout(k)]))
                    mcf.add_edge(dout(k), d_node(j), need, 0.0)
                served = True
            else:
                direct_edge_ref[(i, j)] = (p_node(i), len(mcf.graph[p_node(i)]))
                mcf.add_edge(p_node(i), d_node(j), min(need, float(p['available_l'])),
                             landed_cost_per_l(p, money_rate_year))
                served = True
        if not served:
            reasons.setdefault(dem['key'], 'no_path')

    total_need = sum(float(d['liters']) for d in demands if float(d['liters']) > 0)
    flow, cost = mcf.flow(src, sink, total_need)

    def sent(u: int, idx: int) -> float:
        """Сколько ушло по ребру: столько же вернулось в обратное."""
        e = mcf.graph[u][idx]
        return mcf.graph[int(e[0])][int(e[3])][1]

    depot_by_index = {k: (did, grade) for (did, grade), k in dep_index.items()}
    allocations: List[Dict[str, Any]] = []
    covered: Dict[str, float] = {}

    for (k, j), (u, idx) in depot_edge_ref.items():
        vol = sent(u, idx)
        if vol <= 1e-9:
            continue
        dem = demands[j]
        did, grade = depot_by_index[k]
        dep = next((x for x in depots if int(x['id']) == did
                    and str(x['grade_code']) == grade), {})
        allocations.append({
            'key': dem['key'], 'station_id': dem['station_id'],
            'grade_code': dem['grade_code'], 'via': 'depot',
            'depot_id': did, 'depot_name': dep.get('name'),
            'path_code': None, 'source_code': 'depot',
            'liters': round(vol, 1),
        })
        covered[dem['key']] = covered.get(dem['key'], 0.0) + vol

    for (i, j), (u, idx) in direct_edge_ref.items():
        vol = sent(u, idx)
        if vol <= 1e-9:
            continue
        dem, p = demands[j], paths[i]
        cpl = landed_cost_per_l(p, money_rate_year)
        allocations.append({
            'key': dem['key'], 'station_id': dem['station_id'],
            'grade_code': dem['grade_code'], 'via': 'direct',
            'depot_id': None, 'depot_name': None,
            'path_code': p['code'], 'source_code': p.get('source_code'),
            'liters': round(vol, 1), 'lead_days': p.get('lead_days'),
            'cost_per_l': cpl, 'amount': round(vol * cpl, 2),
        })
        covered[dem['key']] = covered.get(dem['key'], 0.0) + vol

    # Чем пополнялась сама база
    replenishment: List[Dict[str, Any]] = []
    for i, k in path_to_depot.items():
        for idx, e in enumerate(mcf.graph[p_node(i)]):
            if int(e[0]) != din(k):
                continue
            vol = sent(p_node(i), idx)
            if vol <= 1e-9:
                continue
            p = paths[i]
            cpl = landed_cost_per_l(p, money_rate_year)
            did, grade = depot_by_index[k]
            replenishment.append({
                'depot_id': did, 'grade_code': grade, 'path_code': p['code'],
                'source_code': p.get('source_code'), 'liters': round(vol, 1),
                'lead_days': p.get('lead_days'), 'cost_per_l': cpl,
                'amount': round(vol * cpl, 2),
            })

    uncovered = []
    for dem in demands:
        need = float(dem['liters'])
        got = covered.get(dem['key'], 0.0)
        if need - got > 1.0:
            uncovered.append({'key': dem['key'], 'station_id': dem['station_id'],
                              'grade_code': dem['grade_code'],
                              'need_l': round(need, 1), 'covered_l': round(got, 1),
                              'reason': reasons.get(dem['key'], 'no_capacity')})

    return {'success': True, 'allocations': allocations,
            'replenishment': replenishment, 'uncovered': uncovered,
            'total_liters': round(flow, 1), 'total_cost': round(cost, 2),
            'avg_cost_per_l': round(cost / flow, 4) if flow > 0 else None,
            'demands': len(demands)}


def compare_paths(dem: Dict[str, Any], paths: List[Dict[str, Any]],
                  money_rate_year: float = 0.14) -> List[Dict[str, Any]]:
    """
    Разбор одной потребности по всем путям — «почему выбрано именно это».

    Оптимизатор возвращает решение, а закупщику нужно объяснение.
    Здесь каждый путь показан со своей стоимостью и причиной, по которой
    он не подошёл, если не подошёл.
    """
    out = []
    for p in paths:
        if p.get('grade_code') and p['grade_code'] != dem.get('grade_code'):
            continue
        reason = None
        dtd = dem.get('days_to_dry')
        if dtd is not None and float(p.get('lead_days') or 0) > float(dtd) + 1e-9:
            reason = 'не успевает по плечу'
        elif float(p.get('available_l') or 0) <= 0:
            reason = 'нет доступного объёма'
        elif float(p.get('min_lot_l') or 0) > float(dem.get('liters') or 0):
            reason = 'партия меньше минимальной'
        out.append({
            'path_code': p['code'], 'source_code': p.get('source_code'),
            'depot_id': p.get('depot_id'), 'lead_days': p.get('lead_days'),
            'cost_per_l': landed_cost_per_l(p, money_rate_year),
            'available_l': p.get('available_l'),
            'blocked_reason': reason, 'is_feasible': reason is None,
        })
    return sorted(out, key=lambda x: (not x['is_feasible'], x['cost_per_l']))

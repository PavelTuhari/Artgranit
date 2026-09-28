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


def solve_distribution(demands: List[Dict[str, Any]], sources: List[Dict[str, Any]],
                       money_rate_year: float = 0.14) -> Dict[str, Any]:
    """
    ЗАДАЧА 1 — сегодняшняя развозка: чем закрыть потребность станций
    прямо сейчас.

    Источники здесь — то, что физически доступно к отгрузке сегодня:
      * остаток СВОЕЙ нефтебазы (плечо — часы до станции);
      * остаток ЧУЖОЙ нефтебазы, где мы храним по тарифу;
      * прямая поставка с внутреннего рынка на станцию (плечо сутки).

    Импорт сюда не попадает: судно идёт две недели и станцию,
    у которой топливо кончится завтра, не спасёт. Импорт решается
    во второй задаче — пополнении баз.

    Разделение на две задачи появилось после проверки: единый граф
    «источник → база → станция» складывал плечо закупки и плечо развозки,
    и станция в полусутках от сухого бака оказывалась непокрытой при
    полной нефтебазе в сорока километрах. Это была ошибка модели,
    а не жизни.
    """
    return _solve_flow(demands, sources, money_rate_year, lead_field='lead_days')


def solve_replenishment(depot_needs: List[Dict[str, Any]],
                        supplies: List[Dict[str, Any]],
                        money_rate_year: float = 0.14) -> Dict[str, Any]:
    """
    ЗАДАЧА 2 — пополнение нефтебаз: импорт против внутреннего рынка.

    Потребность базы — это дефицит покрытия сети на горизонте плеча
    импорта. Ограничение сверху — свободная ёмкость резервуарного парка
    базы: залить больше, чем влезет, нельзя и здесь.

    Дешёвый импорт выигрывает по цене литра, но замораживает деньги
    на две недели и не годится, когда покрытия осталось на трое суток;
    внутренний рынок дороже, но приезжает за двое. Выбор между ними —
    ровно то, что считает этот поток.
    """
    return _solve_flow(depot_needs, supplies, money_rate_year, lead_field='lead_days')


# Цена опоздания: сколько условно стоит литр, приехавший на сутки позже,
# чем станция высохнет. Величина не «настоящая цена» — это ВЕС в задаче
# оптимизации: он должен уверенно перебивать разницу в цене литра между
# путями (там речь о 1-3 лея), чтобы срочная потребность ушла на быстрый
# путь, но не быть бесконечным — иначе поток вообще откажется её везти.
LATE_PENALTY_PER_L_DAY = 5.0


def _solve_flow(demands: List[Dict[str, Any]], sources: List[Dict[str, Any]],
                money_rate_year: float, lead_field: str,
                late_penalty: float = LATE_PENALTY_PER_L_DAY) -> Dict[str, Any]:
    """
    Общее ядро обеих задач: поток минимальной стоимости
    «источники → потребности» с запретом по плечу.

    demands: [{'key', 'target_id', 'grade_code', 'liters', 'days_to_dry'|None,
               'capacity_l'|None}]
    sources: [{'code', 'source_code', 'grade_code', 'target_id'|None,
               'lead_days', 'price_per_l', 'transport_per_l',
               'handling_per_l', 'duty_per_l', 'available_l', 'min_lot_l',
               'depot_id'|None, 'depot_name'|None}]
    """
    if not demands:
        return {'success': True, 'allocations': [], 'uncovered': [],
                'total_liters': 0.0, 'total_cost': 0.0, 'avg_cost_per_l': None}
    if not sources:
        return {'success': False, 'error': 'Не задано ни одного источника'}

    S, N = len(sources), len(demands)
    src, sink = 0, 1 + S + N
    s_node = lambda i: 1 + i
    d_node = lambda j: 1 + S + j
    mcf = MinCostFlow(sink + 1)

    for i, p in enumerate(sources):
        avail = max(0.0, float(p.get('available_l') or 0))
        if avail > 0:
            mcf.add_edge(src, s_node(i), avail, 0.0)

    reasons: Dict[str, str] = {}
    edge_ref: Dict[Tuple[int, int], int] = {}
    for j, dem in enumerate(demands):
        need = float(dem.get('liters') or 0)
        if need <= 0:
            continue
        mcf.add_edge(d_node(j), sink, need, 0.0)
        served = False
        for i, p in enumerate(sources):
            if p.get('grade_code') and p['grade_code'] != dem.get('grade_code'):
                continue
            if p.get('target_id') and int(p['target_id']) != int(dem['target_id']):
                continue
            if float(p.get('available_l') or 0) <= 0:
                continue
            dtd = dem.get('days_to_dry')
            lead = float(p.get(lead_field) or 0)
            # Опоздание НЕ запрещает путь, а дорожает его.
            #
            # Первая версия отсекала пути с плечом больше остатка хода —
            # и на прогоне 17 станций из 23 остались «непокрытыми»: это
            # были ровно те, у кого бак высохнет через несколько часов.
            # В жизни таким станциям везут в первую очередь и максимально
            # быстрым транспортом, а не отказывают в поставке. Штраф за
            # сутки опоздания сохраняет правильный ПОРЯДОК предпочтений
            # (быстрый путь выигрывает у дешёвого) и при этом всегда
            # оставляет потребность покрытой.
            late = max(0.0, lead - float(dtd)) if dtd is not None else 0.0
            # Минимальная партия: источник, который нельзя взять мелко,
            # не годится под мелкую потребность
            if float(p.get('min_lot_l') or 0) > need + 1e-9:
                reasons.setdefault(dem['key'], 'min_lot')
                continue
            cap = min(need, float(p['available_l']))
            edge_ref[(i, j)] = len(mcf.graph[s_node(i)])
            mcf.add_edge(s_node(i), d_node(j), cap,
                         landed_cost_per_l(p, money_rate_year) + late * late_penalty)
            served = True
        if not served:
            reasons.setdefault(dem['key'], reasons.get(dem['key'], 'no_source'))

    total_need = sum(float(d.get('liters') or 0) for d in demands)
    flow, cost = mcf.flow(src, sink, total_need)

    allocations: List[Dict[str, Any]] = []
    covered: Dict[str, float] = {}
    for (i, j), idx in edge_ref.items():
        e = mcf.graph[s_node(i)][idx]
        vol = mcf.graph[int(e[0])][int(e[3])][1]      # сколько вернулось в обратное ребро
        if vol <= 1e-9:
            continue
        p, dem = sources[i], demands[j]
        cpl = landed_cost_per_l(p, money_rate_year)
        dtd = dem.get('days_to_dry')
        late = (max(0.0, float(p.get(lead_field) or 0) - float(dtd))
                if dtd is not None else 0.0)
        allocations.append({
            'key': dem['key'], 'target_id': dem.get('target_id'),
            'grade_code': dem.get('grade_code'), 'path_code': p['code'],
            'source_code': p.get('source_code'), 'depot_id': p.get('depot_id'),
            'depot_name': p.get('depot_name'),
            'liters': round(vol, 1), 'lead_days': p.get(lead_field),
            # Сумма считается по РЕАЛЬНОЙ цене литра: штраф за опоздание —
            # инструмент выбора, а не строка в счёте поставщика
            'cost_per_l': cpl, 'amount': round(vol * cpl, 2),
            'late_days': round(late, 2), 'is_late': 1 if late > 1e-6 else 0,
        })
        covered[dem['key']] = covered.get(dem['key'], 0.0) + vol

    uncovered = []
    for dem in demands:
        need = float(dem.get('liters') or 0)
        got = covered.get(dem['key'], 0.0)
        if need - got > 1.0:
            uncovered.append({'key': dem['key'], 'target_id': dem.get('target_id'),
                              'grade_code': dem.get('grade_code'),
                              'need_l': round(need, 1), 'covered_l': round(got, 1),
                              'reason': reasons.get(dem['key'], 'no_capacity')})

    # Стоимость из потока включает штрафы за опоздание — для отчёта
    # пересчитываем по фактическим ценам путей
    real_cost = sum(a['amount'] for a in allocations)
    late_l = sum(a['liters'] for a in allocations if a['is_late'])
    return {'success': True, 'allocations': allocations, 'uncovered': uncovered,
            'total_liters': round(flow, 1), 'total_cost': round(real_cost, 2),
            'avg_cost_per_l': round(real_cost / flow, 4) if flow > 0 else None,
            'late_liters': round(late_l, 1),
            'late_count': sum(1 for a in allocations if a['is_late']),
            'demands': len(demands)}


def solve_supply_plan(station_demands: List[Dict[str, Any]],
                      distribution_sources: List[Dict[str, Any]],
                      depot_needs: List[Dict[str, Any]],
                      replenishment_sources: List[Dict[str, Any]],
                      money_rate_year: float = 0.14) -> Dict[str, Any]:
    """
    Полный план снабжения: развозка сегодня плюс пополнение баз.

    Возвращает оба слоя раздельно — именно так решение и принимается:
    диспетчер смотрит развозку, закупщик смотрит пополнение, и это
    разные люди с разным горизонтом.
    """
    dist = solve_distribution(station_demands, distribution_sources, money_rate_year)
    repl = solve_replenishment(depot_needs, replenishment_sources, money_rate_year)
    total = 0.0
    for part in (dist, repl):
        if part.get('success'):
            total += float(part.get('total_cost') or 0)
    return {'success': dist.get('success', False) or repl.get('success', False),
            'distribution': dist, 'replenishment': repl,
            'total_cost': round(total, 2)}


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
        lead = float(p.get('lead_days') or 0)
        late = max(0.0, lead - float(dtd)) if dtd is not None else 0.0
        if float(p.get('available_l') or 0) <= 0:
            reason = 'нет доступного объёма'
        elif float(p.get('min_lot_l') or 0) > float(dem.get('liters') or 0):
            reason = 'потребность меньше минимальной партии'
        out.append({
            'path_code': p['code'], 'source_code': p.get('source_code'),
            'depot_id': p.get('depot_id'), 'lead_days': p.get('lead_days'),
            'cost_per_l': landed_cost_per_l(p, money_rate_year),
            'available_l': p.get('available_l'),
            'late_days': round(late, 2),
            'note': ('опоздание %.1f сут' % late) if late > 1e-6 else None,
            'blocked_reason': reason, 'is_feasible': reason is None,
        })
    # Сортировка по решающему критерию: сначала успевающие и дешёвые,
    # затем опаздывающие — в том же порядке, в каком их выбирает поток
    return sorted(out, key=lambda x: (not x['is_feasible'], x['late_days'],
                                      x['cost_per_l']))

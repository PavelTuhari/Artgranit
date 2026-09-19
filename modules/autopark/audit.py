"""Autopark — аудиторский движок контура (концепт отчёта Big-4/KPMG).

Зачем отдельный слой. Приёмка по ролям (`scripts/autopark_role_test.py`)
отвечает на вопрос «работает ли функция». Аудит отвечает на другой:
«можно ли доверять числу, которое система выдала бухгалтеру и
руководству». Это разные вопросы, и второй нельзя закрыть прогоном UI:
нужен независимый пересчёт по всей популяции документов и вывод о том,
какие контроли эффективны, а какие — нет.

Модуль ЧИСТЫЙ: ни одного импорта БД, ни одного SQL. На вход — снимок
популяции (контракт `audit_data.population()`), на выход — структура
аудиторского отчёта. Поэтому движок тестируется без wallet и одинаково
работает на боевых данных Oracle и на сгенерированном наборе.

Методика (в терминах, принятых в отчётах Big-4):

  * **Контроль** — правило, которое должно не допускать ошибку. У каждого
    два измерения: дизайн (описан ли контроль так, что теоретически
    предотвращает риск) и операционная эффективность (срабатывает ли он
    на реальных данных).
  * **Тест по существу (substantive)** — независимый пересчёт: аудитор
    считает величину сам и сравнивает с тем, что в системе.
  * **Полная популяция (D&A)** — там, где данные машинные, тестируется
    100 % документов, а не выборка. Выборка остаётся только для того,
    что в данных не видно (наличие подписи на путевом листе).
  * **Отклонение (exception)** — единичное несовпадение. Находка
    (finding) появляется тогда, когда отклонения складываются в вывод.

Важное ограничение, которое повторяется в самом отчёте: аудит проверяет
внутреннюю непротиворечивость системы и соответствие её же правилам.
Он НЕ подтверждает, что в систему ввели правду о физическом мире — что
бензовоз действительно проехал этот маршрут, а в резервуар действительно
слили эти литры. Это предмет инвентаризации и сверки с GPS/Petrol Expert,
а не расчёта.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence

# ── Шкалы ───────────────────────────────────────────────────────────────

SEV_HIGH = "Высокий"
SEV_MED = "Средний"
SEV_LOW = "Низкий"
SEVERITIES = (SEV_HIGH, SEV_MED, SEV_LOW)

RATE_OK = "Эффективен"
RATE_WARN = "Требует улучшения"
RATE_BAD = "Неэффективен"
#: Отдельная оценка вместо «эффективен» там, где тестировать нечего.
#: Ноль отклонений из нуля объектов — не доказательство работы контроля,
#: а отсутствие доказательства. Смешивать эти два случая нельзя: именно
#: так контрольная среда и выглядит здоровой на бумаге.
RATE_NA = "Не тестировался"
RATINGS = (RATE_OK, RATE_WARN, RATE_BAD, RATE_NA)

#: Порог отклонения при пересчёте денег: лей. Меньше — округление.
MONEY_TOL = 0.01
#: Порог отклонения при пересчёте литров.
LITRE_TOL = 0.5

#: Доля отклонений, выше которой контроль признаётся неэффективным.
BAD_RATE = 0.05
#: Доля отклонений, выше которой контроль требует улучшения.
WARN_RATE = 0.0

#: Денежное влияние, выше которого находка поднимается до «Высокий», лей.
HIGH_IMPACT_LEI = 50_000.0
MED_IMPACT_LEI = 5_000.0

#: Минимальная популяция, на которой доля отклонений вообще что-то значит.
#: «Одно отклонение из одного проверенного объекта» — это 100 %, и по
#: шкале частоты такая находка уезжает в «высокий». На боевых данных
#: именно так и вышло: приёмка была зафиксирована ровно у одной позиции,
#: она разошлась с отгрузкой, и контур получил находку высшей значимости
#: на популяции из одного документа. Вывод о ЧАСТОТЕ на таком объёме
#: недопустим; вывод о ДЕНЬГАХ — допустим, деньги не зависят от объёма
#: выборки, поэтому денежный порог продолжает работать без оглядки сюда.
MIN_RATE_POPULATION = 30


class AuditInputError(Exception):
    """Популяция не соответствует контракту — аудит строить не из чего."""


# ── Вспомогательное ─────────────────────────────────────────────────────

def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) >= 10:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _f(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rate_on(rate_periods: Sequence[Dict], day: Optional[date],
             fallback: Dict) -> Dict:
    """Ставка, действующая на дату рейса.

    Именно «на дату рейса», а не текущая: если ставку подняли с сентября,
    августовские рейсы обязаны остаться на старой. Проверка этого — один
    из контролей (FLT-C-07), поэтому резолвер живёт здесь, а не берётся
    из `periods.py`: аудитор считает независимо от проверяемого кода.
    """
    if day is None:
        return fallback
    best = None
    for period in rate_periods:
        vf = _as_date(period.get("valid_from"))
        vt = _as_date(period.get("valid_to"))
        if vf is not None and vf > day:
            continue
        if vt is not None and vt < day:
            continue
        if best is None or (vf or date.min) > (_as_date(best.get("valid_from")) or date.min):
            best = period
    return best or fallback


def _pct(part: int, whole: int) -> float:
    return round(part / whole * 100, 2) if whole else 0.0


def _severity(rate_pct: float, impact_lei: float, tested: int = 10 ** 9) -> str:
    """Значимость из двух измеренных величин — с оговоркой про объём.

    Доля отклонений повышает значимость только тогда, когда проверено
    достаточно объектов, чтобы о доле вообще можно было говорить
    (`MIN_RATE_POPULATION`). Денежная оценка действует всегда.
    """
    rate_counts = tested >= MIN_RATE_POPULATION
    if impact_lei >= HIGH_IMPACT_LEI or (rate_counts and rate_pct >= BAD_RATE * 100):
        return SEV_HIGH
    if impact_lei >= MED_IMPACT_LEI or (rate_counts and rate_pct >= 1.0):
        return SEV_MED
    return SEV_LOW


def _effectiveness(exceptions: int, tested: int) -> str:
    if tested == 0:
        return RATE_NA
    rate = exceptions / tested
    if rate > BAD_RATE:
        return RATE_BAD
    if rate > WARN_RATE:
        return RATE_WARN
    return RATE_OK


def sample_indexes(population_size: int, sample_size: int, seed: str) -> List[int]:
    """Воспроизводимая выборка без random: аудит обязан повторяться.

    `random.sample` дал бы разный результат на разных версиях Python и
    рассыпал бы повторяемость акта. Здесь порядок задаёт SHA-256 от
    (seed, индекс) — одинаковый на любой машине и в любом году.
    """
    if sample_size >= population_size:
        return list(range(population_size))
    keyed = sorted(
        range(population_size),
        key=lambda i: hashlib.sha256(f"{seed}:{i}".encode()).hexdigest(),
    )
    return sorted(keyed[:sample_size])


def attribute_sample_size(population: int, frequency: str) -> int:
    """Объём выборки для контроля, который не виден в данных.

    Шкала attribute sampling, принятая в практике Big-4 при ожидаемом
    нулевом уровне отклонений и 90 % доверии: частота срабатывания
    контроля определяет объём, а не размер популяции (популяция влияет
    только как верхняя граница).
    """
    table = {"daily": 25, "weekly": 5, "monthly": 2, "quarterly": 2,
             "multiple": 40, "annual": 1}
    return min(population, table.get(frequency, 25))


# ══ Тесты по существу ═══════════════════════════════════════════════════
#
# Каждый тест возвращает единый контракт:
#   {"id", "title", "objective", "procedure", "scope", "tested",
#    "exceptions", "impact_lei", "columns", "rows"}
# где rows — ТОЛЬКО отклонения (по ним аудитор смотрит расшифровку),
# а tested — размер проверенной популяции.


def _test(tid: str, title: str, objective: str, procedure: str, scope: str,
          tested: int, columns: List[str], rows: List[List[Any]],
          impact_lei: float = 0.0) -> Dict[str, Any]:
    return {"id": tid, "title": title, "objective": objective,
            "procedure": procedure, "scope": scope, "tested": tested,
            "exceptions": len(rows), "impact_lei": round(impact_lei, 2),
            "columns": columns, "rows": rows,
            "rate_pct": _pct(len(rows), tested),
            "result": (RATE_NA if tested == 0
                       else "Без отклонений" if not rows else "Отклонения")}


def test_payroll_recompute(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-01. Независимый пересчёт зарплаты по 100 % утверждённых рейсов."""
    settings = pop["settings"]
    fallback = {"rate_per_km": settings.get("rate_per_km"),
                "trip_bonus": settings.get("trip_bonus")}
    drivers = {d["id"]: d["full_name"] for d in pop["drivers"]}
    rows: List[List[Any]] = []
    impact = 0.0
    tested = 0
    for trip in pop["trips"]:
        if trip.get("status_code") == "DRAFT":
            continue
        if trip.get("pay_stored") is None:
            continue
        tested += 1
        day = _as_date(trip.get("trip_date"))
        rate = _rate_on(pop.get("rate_periods") or [], day, fallback)
        expected = _f(trip.get("norm_km")) * _f(rate.get("rate_per_km"))
        if trip.get("type_code") == "DOMESTIC":
            expected += _f(rate.get("trip_bonus"))
        diff = _f(trip.get("pay_stored")) - expected
        if abs(diff) > MONEY_TOL:
            impact += abs(diff)
            rows.append([trip["id"], day.isoformat() if day else "",
                         drivers.get(trip.get("driver_id"), "—"),
                         trip.get("type_code"),
                         round(_f(trip.get("norm_km")), 1),
                         round(_f(rate.get("rate_per_km")), 2),
                         round(expected, 2),
                         round(_f(trip.get("pay_stored")), 2),
                         round(diff, 2)])
    return _test(
        "T-01", "Пересчёт заработной платы водителей",
        "Начисление соответствует нормативному пробегу и ставке, "
        "действовавшей на дату рейса.",
        "Пересчёт: норм. км × ставка(дата рейса) + доплата за внутренний "
        "рейс. Сравнение с начислением в системе, допуск 0,01 лея.",
        "100 % рейсов периода со статусом не «черновик»",
        tested,
        ["Рейс", "Дата", "Водитель", "Тип", "Норм. км", "Ставка",
         "Пересчёт аудитора, лей", "В системе, лей", "Расхождение, лей"],
        rows, impact)


def test_rate_period_integrity(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-02. Смена ставки не переписывает закрытые периоды."""
    periods = sorted(
        (p for p in (pop.get("rate_periods") or [])
         if _as_date(p.get("valid_from")) is not None),
        key=lambda p: _as_date(p["valid_from"]))
    rows: List[List[Any]] = []
    tested = max(len(periods) - 1, 0)
    for prev, cur in zip(periods, periods[1:]):
        prev_to = _as_date(prev.get("valid_to"))
        cur_from = _as_date(cur["valid_from"])
        if prev_to is None:
            rows.append([prev.get("id"), cur.get("id"),
                         str(_as_date(prev["valid_from"])), "не закрыт",
                         str(cur_from), "Предыдущий период остался открытым — "
                         "две ставки действуют на одну дату"])
        elif prev_to >= cur_from:
            rows.append([prev.get("id"), cur.get("id"),
                         str(_as_date(prev["valid_from"])), str(prev_to),
                         str(cur_from), "Пересечение периодов действия ставки"])
    return _test(
        "T-02", "Целостность периодов действия ставки",
        "На любую дату действует ровно одна ставка; изменение ставки не "
        "меняет уже начисленное за прошлый период.",
        "Сортировка периодов по дате начала, проверка смежности: "
        "предыдущий закрыт строго до начала следующего.",
        "100 % периодов действия ставки", tested,
        ["Период A", "Период B", "A действует с", "A действует по",
         "B действует с", "Характер отклонения"], rows)


def test_section_integrity(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-03. Слив отсеками целиком (требование ТЗ 18.09.2026)."""
    sections: Dict[Any, float] = {}
    for truck in pop["trucks"]:
        for sec in truck.get("sections") or []:
            sections[sec["id"]] = _f(sec.get("volume_l"))
    rows: List[List[Any]] = []
    tested = 0
    for item in pop["trip_items"]:
        sid = item.get("section_id")
        if sid is None or sid not in sections:
            continue
        tested += 1
        planned = _f(item.get("planned_l"))
        volume = sections[sid]
        if abs(planned - volume) > LITRE_TOL:
            rows.append([item.get("trip_id"), item.get("station_code"),
                         item.get("product_code"), sid, round(volume, 1),
                         round(planned, 1), round(planned - volume, 1)])
    return _test(
        "T-03", "Слив отсеками целиком",
        "Отсек бензовоза сливается на АЗС полностью: частичный слив ТЗ "
        "запрещает (нет поверенного средства измерения остатка в отсеке).",
        "Сверка планового объёма каждой позиции с паспортным объёмом "
        "назначенного отсека, допуск 0,5 л.",
        "100 % позиций рейсов с назначенным отсеком", tested,
        ["Рейс", "АЗС", "Продукт", "Отсек", "Объём отсека, л",
         "В позиции, л", "Расхождение, л"], rows)


def test_overfill(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-04. Приёмка не превышает ёмкость резервуара.

    Тест сознательно разделён на два случая, и это не придирка к форме.
    Для поставки, которая ещё не выполнена, свободная ёмкость известна:
    остаток в резервуаре — сегодняшний, и проверять надо именно его. Для
    уже исполненной поставки сегодняшний остаток ничего не говорит: между
    той датой и сегодня АЗС продавала топливо, а состояния резервуара на
    момент слива контур не хранит. Сравнивать историческую приёмку с
    текущим остатком — значит штамповать отклонения там, где их нет.
    Поэтому по истории проверяется абсолютная граница: одна поставка
    физически не может превысить допустимый налив резервуара.
    """
    tanks = {t["id"]: t for t in pop["tanks"]}
    pending_status = {"PLANNED", "LOAD_REQ", "LOADED", "IN_TRANSIT"}
    trip_status = {t["id"]: t.get("status_code") for t in pop["trips"]}
    rows: List[List[Any]] = []
    tested = 0
    for item in pop["trip_items"]:
        tank = tanks.get(item.get("tank_id"))
        if tank is None:
            continue
        accepted = item.get("accepted_l")
        if accepted is None:
            accepted = item.get("planned_l")
        if accepted is None:
            continue
        tested += 1
        pending = trip_status.get(item.get("trip_id")) in pending_status
        if pending:
            limit = _f(tank.get("max_fill_l")) - _f(tank.get("current_l"))
            basis = "свободная ёмкость на сегодня"
        else:
            limit = _f(tank.get("max_fill_l"))
            basis = "допустимый налив резервуара"
        if _f(accepted) - limit > LITRE_TOL:
            rows.append([item.get("trip_id"), item.get("station_code"),
                         item.get("product_code"), basis,
                         round(_f(tank.get("max_fill_l")), 0),
                         round(_f(tank.get("current_l")), 0),
                         round(limit, 0), round(_f(accepted), 0),
                         round(_f(accepted) - limit, 0)])
    return _test(
        "T-04", "Контроль переполнения резервуара",
        "Приёмка не может превысить допустимый налив резервуара, а для "
        "ещё не выполненной поставки — свободную ёмкость на сегодня.",
        "Для запланированных поставок: приёмка против (допустимый налив − "
        "остаток). Для исполненных: приёмка против допустимого налива "
        "(состояние резервуара на дату слива контур не хранит). "
        "Допуск 0,5 л.",
        "100 % позиций с зафиксированным объёмом", tested,
        ["Рейс", "АЗС", "Продукт", "База сравнения", "Допустимый налив, л",
         "Остаток, л", "Предел, л", "Принято, л", "Превышение, л"], rows)


def test_delivery_reconciliation(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-05. Сверка «загружено → по документам → принято»."""
    price = _f((pop.get("prices") or {}).get("DIESEL"), 0.0)
    rows: List[List[Any]] = []
    tested = 0
    impact = 0.0
    limit = _f(pop["settings"].get("loss_tolerance_l"), 50.0)
    for item in pop["trip_items"]:
        loaded = item.get("loaded_l")
        accepted = item.get("accepted_l")
        if loaded is None or accepted is None:
            continue
        tested += 1
        loss = _f(loaded) - _f(accepted)
        if abs(loss) > limit:
            impact += abs(loss) * price
            rows.append([item.get("trip_id"), item.get("station_code"),
                         item.get("product_code"), round(_f(loaded), 0),
                         round(_f(item.get("doc_l") or loaded), 0),
                         round(_f(accepted), 0), round(loss, 0),
                         round(abs(loss) * price, 2)])
    return _test(
        "T-05", "Сверка отгрузки и приёмки",
        "Расхождение между налитым на нефтебазе и принятым на АЗС не "
        "превышает технологического допуска.",
        f"Разница «загружено − принято» по каждой позиции против допуска "
        f"{limit:.0f} л; денежная оценка по цене ДТ.",
        "100 % позиций с зафиксированными отгрузкой и приёмкой", tested,
        ["Рейс", "АЗС", "Продукт", "Загружено, л", "По документам, л",
         "Принято, л", "Потери, л", "Оценка, лей"], rows, impact)


def test_km_deviation(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-06. Превышение фактического пробега над нормативным."""
    limit = _f(pop["settings"].get("km_deviation_limit"), 5.0)
    rate = _f(pop["settings"].get("rate_per_km"), 0.0)
    drivers = {d["id"]: d["full_name"] for d in pop["drivers"]}
    rows: List[List[Any]] = []
    tested = 0
    impact = 0.0
    for trip in pop["trips"]:
        norm = trip.get("norm_km")
        fact = trip.get("fact_km")
        if norm is None or fact is None or _f(norm) <= 0:
            continue
        tested += 1
        dev = (_f(fact) - _f(norm)) / _f(norm) * 100
        if dev > limit:
            extra = (_f(fact) - _f(norm)) * rate
            impact += extra
            rows.append([trip["id"],
                         (_as_date(trip.get("trip_date")) or date.min).isoformat(),
                         drivers.get(trip.get("driver_id"), "—"),
                         round(_f(norm), 1), round(_f(fact), 1),
                         round(dev, 2), round(extra, 2)])
    return _test(
        "T-06", "Необоснованный пробег",
        "Фактический пробег не превышает нормативный более чем на "
        f"{limit:.0f} %.",
        "Расчёт отклонения по каждому рейсу с фактом GPS; денежная "
        "оценка лишних километров по действующей ставке.",
        "100 % рейсов с зафиксированным фактическим пробегом", tested,
        ["Рейс", "Дата", "Водитель", "Норматив, км", "Факт, км",
         "Отклонение, %", "Оценка, лей"], rows, impact)


def test_fuel_deviation(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-07. Перерасход дизельного топлива против нормы автомобиля."""
    limit = _f(pop["settings"].get("fuel_deviation_limit"), 5.0)
    price = _f((pop.get("prices") or {}).get("DIESEL"), 0.0)
    trucks = {t["id"]: t for t in pop["trucks"]}
    rows: List[List[Any]] = []
    tested = 0
    impact = 0.0
    for trip in pop["trips"]:
        truck = trucks.get(trip.get("truck_id"))
        fact_l = trip.get("fact_fuel_l")
        if truck is None or fact_l is None:
            continue
        norm_l = _f(trip.get("norm_km")) * _f(truck.get("norm_l_per_100km")) / 100
        if norm_l <= 0:
            continue
        tested += 1
        dev = (_f(fact_l) - norm_l) / norm_l * 100
        if dev > limit:
            impact += (_f(fact_l) - norm_l) * price
            rows.append([trip["id"],
                         (_as_date(trip.get("trip_date")) or date.min).isoformat(),
                         truck.get("plate"), round(norm_l, 1),
                         round(_f(fact_l), 1), round(dev, 2),
                         round((_f(fact_l) - norm_l) * price, 2)])
    return _test(
        "T-07", "Перерасход топлива бензовозом",
        f"Фактический расход ДТ не превышает норму автомобиля более чем "
        f"на {limit:.0f} %.",
        "Норма рейса = норм. км × норма л/100 км автомобиля; сравнение с "
        "фактической заправкой, денежная оценка по цене ДТ.",
        "100 % рейсов с зафиксированной заправкой", tested,
        ["Рейс", "Дата", "Автомобиль", "Норма, л", "Факт, л",
         "Отклонение, %", "Оценка, лей"], rows, impact)


def test_completeness(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-08. Полнота: у каждого утверждённого рейса есть груз и начисление."""
    items_by_trip: Dict[Any, int] = {}
    for item in pop["trip_items"]:
        items_by_trip[item.get("trip_id")] = items_by_trip.get(item.get("trip_id"), 0) + 1
    rows: List[List[Any]] = []
    tested = 0
    for trip in pop["trips"]:
        if trip.get("status_code") == "DRAFT":
            continue
        tested += 1
        problems = []
        if items_by_trip.get(trip["id"], 0) == 0:
            problems.append("нет ни одной позиции груза")
        if trip.get("pay_stored") is None:
            problems.append("нет начисления зарплаты")
        if trip.get("norm_km") is None or _f(trip.get("norm_km")) <= 0:
            problems.append("не рассчитан нормативный пробег")
        if problems:
            rows.append([trip["id"],
                         (_as_date(trip.get("trip_date")) or date.min).isoformat(),
                         trip.get("status_code"),
                         items_by_trip.get(trip["id"], 0),
                         "; ".join(problems)])
    return _test(
        "T-08", "Полнота учёта рейса",
        "Утверждённый рейс содержит груз, нормативный пробег и начисление "
        "— иначе он не может быть основанием ни для зарплаты, ни для "
        "списания топлива.",
        "Проверка наличия связанных записей у каждого рейса не в статусе "
        "«черновик».",
        "100 % рейсов периода со статусом не «черновик»", tested,
        ["Рейс", "Дата", "Статус", "Позиций груза", "Чего не хватает"], rows)


VALID_FLOW = ["PLANNED", "LOAD_REQ", "LOADED", "IN_TRANSIT", "DELIVERED",
              "APPROVED", "DONE"]


def test_status_sequence(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-09. Рейс не перепрыгивает через обязательные стадии."""
    order = {code: i for i, code in enumerate(VALID_FLOW)}
    rows: List[List[Any]] = []
    tested = 0
    for trip in pop["trips"]:
        history = trip.get("status_history") or []
        if not history:
            continue
        tested += 1
        prev = None
        for entry in history:
            code = entry.get("status_code") if isinstance(entry, dict) else entry
            if code not in order:
                rows.append([trip["id"], str(prev), str(code),
                             "Неизвестный статус"])
                break
            if prev is not None and order[code] < order[prev]:
                rows.append([trip["id"], prev, code,
                             "Возврат назад по цепочке исполнения"])
                break
            if prev is not None and order[code] - order[prev] > 1:
                rows.append([trip["id"], prev, code,
                             "Пропущена обязательная стадия"])
                break
            prev = code
    return _test(
        "T-09", "Хронология исполнения рейса",
        "Статусы меняются строго по цепочке: заявка → загрузка → в пути → "
        "доставлено → утверждено. Пропуск стадии означает, что документ "
        "оформлен задним числом.",
        "Проверка последовательности записей журнала статусов каждого "
        "рейса против эталонной цепочки.",
        "100 % рейсов с журналом статусов", tested,
        ["Рейс", "Из статуса", "В статус", "Характер отклонения"], rows)


def test_segregation_of_duties(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-10. Тот, кто создал рейс, его не утверждает."""
    rows: List[List[Any]] = []
    tested = 0
    for trip in pop["trips"]:
        created = trip.get("created_by")
        approved = trip.get("approved_by")
        if not created or not approved:
            continue
        tested += 1
        if str(created).strip().lower() == str(approved).strip().lower():
            rows.append([trip["id"],
                         (_as_date(trip.get("trip_date")) or date.min).isoformat(),
                         created, approved,
                         round(_f(trip.get("pay_stored")), 2)])
    return _test(
        "T-10", "Разделение полномочий",
        "Создание рейса и его утверждение выполняют разные сотрудники: "
        "утверждённый рейс — основание для начисления зарплаты.",
        "Сравнение автора и утвердившего по каждому утверждённому рейсу.",
        "100 % утверждённых рейсов с заполненными автором и утвердившим",
        tested,
        ["Рейс", "Дата", "Создал", "Утвердил", "Начислено, лей"], rows)


def test_duplicates(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-11. Один и тот же рейс не учтён дважды.

    Первая версия считала отклонением любые два рейса одного бензовоза
    за день. На сгенерированном наборе это работало — там машина выходит
    на линию раз в сутки, — а на боевых данных дало две ложные находки:
    бензовоз вполне может сделать за день два коротких внутренних рейса,
    и это нормальная работа, а не двойной учёт.

    Признаком двойного учёта считается то, что им и является: повтор
    номера путевого листа либо ПОЛНОСТЬЮ совпадающий документ — тот же
    бензовоз, тот же день, тот же водитель и тот же нормативный пробег.
    Два разных рейса одной машины так не совпадают.
    """
    seen_doc: Dict[Any, Any] = {}
    seen_same: Dict[Any, Any] = {}
    rows: List[List[Any]] = []
    tested = 0
    for trip in sorted(pop["trips"], key=lambda t: (
            _as_date(t.get("trip_date")) or date.min, t["id"])):
        if trip.get("status_code") == "DRAFT":
            continue
        tested += 1
        day = _as_date(trip.get("trip_date"))
        doc = trip.get("waybill_no")
        if doc:
            if doc in seen_doc:
                rows.append([trip["id"], day.isoformat() if day else "",
                             f"путевой лист {doc}", seen_doc[doc],
                             "Дубль номера путевого листа"])
                continue
            seen_doc[doc] = trip["id"]
        key = (trip.get("truck_id"), day, trip.get("driver_id"),
               round(_f(trip.get("norm_km")), 1))
        if key in seen_same:
            rows.append([trip["id"], day.isoformat() if day else "",
                         "бензовоз + дата + водитель + норматив",
                         seen_same[key],
                         "Полностью совпадающий документ"])
        else:
            seen_same[key] = trip["id"]
    return _test(
        "T-11", "Дублирование документов",
        "Один и тот же рейс не может быть учтён дважды — ни через второй "
        "путевой лист, ни через полностью повторённый документ.",
        "Поиск повторов по номеру путевого листа и по полному совпадению "
        "реквизитов (бензовоз, дата, водитель, нормативный пробег) по "
        "всей популяции рейсов. Два разных рейса одной машины за день "
        "отклонением не считаются.",
        "100 % рейсов периода со статусом не «черновик»", tested,
        ["Рейс", "Дата", "Ключ повтора", "Первый рейс с тем же ключом",
         "Характер отклонения"], rows)


def test_master_data(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-12. Непротиворечивость справочников (основа всех расчётов)."""
    rows: List[List[Any]] = []
    tested = 0
    for tank in pop["tanks"]:
        tested += 1
        cap = _f(tank.get("capacity_l"))
        mx = _f(tank.get("max_fill_l"))
        mn = _f(tank.get("min_stock_l"))
        cur = _f(tank.get("current_l"))
        problems = []
        if cap > 0 and mx > cap:
            problems.append(f"допустимый налив {mx:.0f} л больше паспортной "
                            f"ёмкости {cap:.0f} л")
        if mn > mx > 0:
            problems.append("страховой запас выше допустимого налива")
        if cur > cap > 0:
            problems.append(f"остаток {cur:.0f} л выше ёмкости {cap:.0f} л")
        if problems:
            rows.append([tank.get("station_code"), tank.get("product_code"),
                         round(cap, 0), round(mx, 0), round(mn, 0),
                         round(cur, 0), "; ".join(problems)])
    for truck in pop["trucks"]:
        tested += 1
        cap = _f(truck.get("capacity_l"))
        secs = sum(_f(s.get("volume_l")) for s in truck.get("sections") or [])
        if secs > 0 and abs(secs - cap) > LITRE_TOL:
            rows.append([truck.get("plate"), "—", round(cap, 0),
                         round(secs, 0), 0, 0,
                         f"сумма отсеков {secs:.0f} л не равна ёмкости "
                         f"цистерны {cap:.0f} л"])
    return _test(
        "T-12", "Непротиворечивость справочников",
        "Паспортные величины резервуаров и бензовозов не противоречат друг "
        "другу: на них опираются все последующие расчёты.",
        "Проверка неравенств: налив ≤ ёмкость, страховой запас ≤ налив, "
        "остаток ≤ ёмкость, сумма отсеков = ёмкость цистерны.",
        "100 % резервуаров и бензовозов", tested,
        ["Объект", "Продукт", "Ёмкость, л", "Допустимый налив, л",
         "Страховой запас, л", "Остаток, л", "Характер отклонения"], rows)


def test_dry_risk(pop: Dict[str, Any]) -> Dict[str, Any]:
    """T-13. Риск сухого бака: запас ниже страхового без покрытия рейсом."""
    covered = set()
    for item in pop["trip_items"]:
        trip = item.get("trip_id")
        covered.add((item.get("station_code"), item.get("product_code")))
    rows: List[List[Any]] = []
    tested = 0
    for tank in pop["tanks"]:
        tested += 1
        cur = _f(tank.get("current_l"))
        mn = _f(tank.get("min_stock_l"))
        avg = _f(tank.get("avg_daily_l"))
        if cur >= mn:
            continue
        key = (tank.get("station_code"), tank.get("product_code"))
        days = round((cur - mn) / avg, 2) if avg > 0 else None
        rows.append([tank.get("station_code"), tank.get("product_code"),
                     round(cur, 0), round(mn, 0), round(avg, 0),
                     days if days is not None else "—",
                     "покрыт рейсом" if key in covered else "НЕ ПОКРЫТ"])
    return _test(
        "T-13", "Покрытие страхового запаса",
        "Резервуар с остатком ниже страхового запаса включён в план "
        "завоза: иначе АЗС останавливает продажу.",
        "Сопоставление резервуаров ниже страхового запаса с позициями "
        "запланированных рейсов.",
        "100 % резервуаров сети", tested,
        ["АЗС", "Продукт", "Остаток, л", "Страховой запас, л",
         "Продажи, л/сут", "Дней до нуля", "Статус"], rows)


TESTS = (test_payroll_recompute, test_rate_period_integrity,
         test_section_integrity, test_overfill, test_delivery_reconciliation,
         test_km_deviation, test_fuel_deviation, test_completeness,
         test_status_sequence, test_segregation_of_duties, test_duplicates,
         test_master_data, test_dry_risk)


# ══ Контроли ════════════════════════════════════════════════════════════
#
# Контроль — то, что ДОЛЖНО не допустить ошибку. Тест — то, чем аудитор
# убеждается, что контроль сработал. Связь «контроль → тест» задана явно,
# чтобы в отчёте нельзя было объявить контроль эффективным без теста.

CONTROL_SPECS: List[Dict[str, Any]] = [
    {"id": "FLT-C-01", "domain": "Расчёты с персоналом",
     "title": "Автоматический расчёт зарплаты по нормативу",
     "objective": "Зарплата водителя рассчитывается системой по нормативному "
                  "пробегу и не вводится вручную.",
     "type": "Автоматический", "frequency": "multiple",
     "design": "Эффективен",
     "design_note": "Начисление формируется представлением V_FLT_TRIP_PAY; "
                    "поля для ручного ввода суммы в интерфейсе нет.",
     "tests": ["T-01"]},
    {"id": "FLT-C-02", "domain": "Расчёты с персоналом",
     "title": "Ставка применяется по дате рейса",
     "objective": "Изменение ставки не переписывает начисления закрытых "
                  "периодов.",
     "type": "Автоматический", "frequency": "monthly",
     "design": "Эффективен",
     "design_note": "Ставки хранятся периодами (FLT_RATE_PERIODS), резолвер "
                    "выбирает период по TRIP_DATE, а не по SYSDATE.",
     "tests": ["T-02", "T-01"]},
    {"id": "FLT-C-03", "domain": "Операции: отгрузка и приёмка",
     "title": "Слив отсеками целиком",
     "objective": "Плановый объём позиции равен паспортному объёму отсека.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Подбор отсеков — точное перечисление подмножеств "
                    "(supply_rules.pick_sections), частичный объём "
                    "сформировать нельзя.",
     "tests": ["T-03"]},
    {"id": "FLT-C-04", "domain": "Операции: отгрузка и приёмка",
     "title": "Запрет переполнения резервуара",
     "objective": "Приёмка не превышает свободную ёмкость резервуара.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Валидация на сервере (supply_rules.validate_loads); "
                    "проверка выполняется до сохранения факта.",
     "tests": ["T-04"]},
    {"id": "FLT-C-05", "domain": "Операции: отгрузка и приёмка",
     "title": "Сверка отгруженного и принятого",
     "objective": "Расхождение выявляется и фиксируется по каждой поставке.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Карточка исполнения показывает три величины (загружено "
                    "/ по документам / принято) и подсвечивает разницу.",
     "tests": ["T-05"]},
    {"id": "FLT-C-06", "domain": "Контроль затрат",
     "title": "Контроль необоснованного пробега",
     "objective": "Превышение факта над нормативом выявляется и оценивается "
                  "в деньгах.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Порог отклонения — настройка заказчика "
                    "(KM_DEVIATION_LIMIT), факт приходит из GPS-прослойки.",
     "tests": ["T-06"]},
    {"id": "FLT-C-07", "domain": "Контроль затрат",
     "title": "Контроль расхода топлива бензовозом",
     "objective": "Перерасход против нормы автомобиля выявляется.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Норма хранится в карточке автомобиля "
                    "(NORM_L_PER_100KM), расчёт нормы рейса автоматический.",
     "tests": ["T-07"]},
    {"id": "FLT-C-08", "domain": "Полнота и достоверность учёта",
     "title": "Полнота реквизитов рейса",
     "objective": "Утверждённый рейс содержит груз, норматив и начисление.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Утверждение недоступно для рейса без позиций; "
                    "нормативный пробег считается при сохранении маршрута.",
     "tests": ["T-08"]},
    {"id": "FLT-C-09", "domain": "Полнота и достоверность учёта",
     "title": "Цепочка статусов исполнения",
     "objective": "Документ нельзя оформить задним числом, пропустив стадии.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Требует улучшения",
     "design_note": "Порядок задан справочником REF_TRIP_STATUS.SORT_NO, но "
                    "запрет обратного перехода реализован в контроллере, а "
                    "не ограничением БД — прямая правка таблицы его обойдёт.",
     "tests": ["T-09"]},
    {"id": "FLT-C-10", "domain": "Доступ и полномочия",
     "title": "Разделение полномочий «создал / утвердил»",
     "objective": "Одно лицо не создаёт и не утверждает один и тот же рейс.",
     "type": "Ручной", "frequency": "daily",
     "design": "Требует улучшения",
     "design_note": "Роли в системе разделены, но техническая блокировка "
                    "самоутверждения не включена: контроль держится на "
                    "распределении учётных записей.",
     "tests": ["T-10"]},
    {"id": "FLT-C-11", "domain": "Полнота и достоверность учёта",
     "title": "Защита от двойного учёта",
     "objective": "Рейс и путевой лист не учитываются дважды.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Один бензовоз используется в плане один раз; номер "
                    "путевого листа уникален.",
     "tests": ["T-11"]},
    {"id": "FLT-C-12", "domain": "Справочные данные",
     "title": "Непротиворечивость справочников",
     "objective": "Паспортные величины не противоречат друг другу.",
     "type": "Автоматический", "frequency": "monthly",
     "design": "Эффективен",
     "design_note": "Формы настроек отклоняют налив выше ёмкости и сумму "
                    "отсеков, не равную цистерне.",
     "tests": ["T-12"]},
    {"id": "FLT-C-13", "domain": "Непрерывность операций",
     "title": "Покрытие страхового запаса планом завоза",
     "objective": "АЗС не останавливает продажу из-за отсутствия топлива.",
     "type": "Автоматический", "frequency": "daily",
     "design": "Эффективен",
     "design_note": "Планирование сортирует потребности по дням до "
                    "страхового запаса; сводка руководителя показывает риск.",
     "tests": ["T-13"]},
]


def _build_controls(tests_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    controls = []
    for spec in CONTROL_SPECS:
        linked = [tests_by_id[t] for t in spec["tests"] if t in tests_by_id]
        tested = sum(t["tested"] for t in linked)
        exceptions = sum(t["exceptions"] for t in linked)
        impact = sum(t["impact_lei"] for t in linked)
        operating = _effectiveness(exceptions, tested)
        # Дизайн-дефект не может дать итоговую оценку выше «требует
        # улучшения»: контроль, который легко обойти, нельзя признать
        # эффективным только потому, что в периоде его никто не обходил.
        if operating == RATE_NA:
            overall = RATE_NA
        elif spec["design"] != "Эффективен" and operating == RATE_OK:
            overall = RATE_WARN
        else:
            overall = operating
        controls.append({
            **{k: v for k, v in spec.items() if k != "tests"},
            "test_ids": spec["tests"],
            "tested": tested, "exceptions": exceptions,
            "rate_pct": _pct(exceptions, tested),
            "impact_lei": round(impact, 2),
            "operating": operating, "rating": overall,
            "sample": attribute_sample_size(tested, spec["frequency"])
            if spec["type"] == "Ручной" else tested,
            "coverage": ("Реквизит отсутствует в данных" if tested == 0
                         else "Выборка" if spec["type"] == "Ручной"
                         else "100 % популяции"),
        })
    return controls


# ══ Находки ═════════════════════════════════════════════════════════════

#: Рекомендация и риск для каждого теста. Держим здесь, а не в тексте
#: отчёта: находка обязана нести и последствие, и что с ним делать.
FINDING_TEXT: Dict[str, Dict[str, str]] = {
    "T-01": {"risk": "Начисление, не соответствующее нормативу, попадает в "
                     "расчётную ведомость и в себестоимость литра.",
             "rec": "Заблокировать сохранение рейса, у которого начисление "
                    "отличается от расчётного, и вывести расхождение в "
                    "журнал для разбора."},
    "T-02": {"risk": "Две ставки на одну дату означают, что сумма зарплаты "
                     "зависит от порядка выборки — воспроизвести начисление "
                     "прошлого месяца невозможно.",
             "rec": "Закрывать предыдущий период автоматически при вводе "
                    "новой ставки и запретить сохранение пересекающихся "
                    "периодов на уровне БД."},
    "T-03": {"risk": "Частичный слив нечем измерить: остаток в отсеке "
                     "становится неучтённым топливом.",
             "rec": "Оставить подбор отсеков только автоматическим, ручное "
                    "изменение объёма позиции запретить."},
    "T-04": {"risk": "Перелив резервуара — пролив продукта, экологический "
                     "инцидент и прямые потери.",
             "rec": "Держать проверку на сервере (не в форме) и логировать "
                    "каждую попытку превышения."},
    "T-05": {"risk": "Систематическая недостача при приёмке — признак "
                     "потерь продукта или недолива на нефтебазе.",
             "rec": "Ввести разбор каждой недостачи выше допуска с "
                    "обязательным комментарием и сверкой с нефтебазой."},
    "T-06": {"risk": "Лишние километры оплачиваются водителю и не создают "
                     "поставки.",
             "rec": "Требовать обоснование при утверждении рейса с "
                    "отклонением выше порога."},
    "T-07": {"risk": "Перерасход топлива бензовозом — прямой убыток и "
                     "возможный слив на сторону.",
             "rec": "Сверять заправки бензовозов с топливными картами и "
                    "разбирать рейсы с отклонением выше порога."},
    "T-08": {"risk": "Неполный рейс не может служить основанием для "
                     "начисления и списания, но участвует в отчётности.",
             "rec": "Запретить утверждение рейса без позиций груза и "
                    "рассчитанного норматива."},
    "T-09": {"risk": "Оформление задним числом скрывает простои и "
                     "фактические сроки доставки.",
             "rec": "Перенести проверку порядка статусов в ограничение "
                    "базы данных (триггер), чтобы её нельзя было обойти "
                    "прямой правкой таблицы."},
    "T-10": {"risk": "Самоутверждение рейса снимает единственный контроль "
                     "над основанием для начисления зарплаты.",
             "rec": "Включить техническую блокировку: утвердить рейс может "
                    "только учётная запись, отличная от создавшей."},
    "T-11": {"risk": "Двойной учёт рейса удваивает и зарплату, и списание "
                     "топлива.",
             "rec": "Добавить уникальный ключ на номер путевого листа и "
                    "предупреждение при повторной постановке бензовоза."},
    "T-12": {"risk": "Ошибка в справочнике тиражируется во все расчёты "
                     "периода и обнаруживается только при инвентаризации.",
             "rec": "Проверять неравенства при сохранении карточки и "
                    "ежемесячно прогонять контроль справочников."},
    "T-13": {"risk": "Остановка продажи на АЗС из-за отсутствия топлива — "
                     "потерянная выручка и репутационный ущерб.",
             "rec": "Включить резервуары ниже страхового запаса в план "
                    "завоза принудительно, с уведомлением логисту."},
}


def _build_findings(tests: Sequence[Dict[str, Any]],
                    controls: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_test_control: Dict[str, str] = {}
    for ctl in controls:
        for tid in ctl["test_ids"]:
            by_test_control.setdefault(tid, ctl["id"])

    findings = []
    seq = 0
    for test in tests:
        if test["exceptions"] == 0:
            continue
        seq += 1
        text = FINDING_TEXT.get(test["id"], {})
        severity = _severity(test["rate_pct"], test["impact_lei"],
                             test["tested"])
        thin = test["tested"] < MIN_RATE_POPULATION
        findings.append({
            "id": f"F-{seq:02d}",
            "severity": severity,
            "control_id": by_test_control.get(test["id"], "—"),
            "test_id": test["id"],
            "title": test["title"],
            "observation": (
                f"При проверке {test['tested']} объектов ({test['scope']}) "
                f"выявлено {test['exceptions']} отклонений "
                f"({test['rate_pct']:.2f} %)."
                + (f" Денежная оценка: {test['impact_lei']:,.2f} лея."
                   .replace(",", " ") if test["impact_lei"] else "")
                + (f" Популяции ({test['tested']}) недостаточно для вывода "
                   f"о частоте: значимость определена только денежной "
                   f"оценкой." if thin else "")),
            "thin_population": thin,
            "risk": text.get("risk", ""),
            "recommendation": text.get("rec", ""),
            "exceptions": test["exceptions"],
            "tested": test["tested"],
            "rate_pct": test["rate_pct"],
            "impact_lei": test["impact_lei"],
        })
    order = {SEV_HIGH: 0, SEV_MED: 1, SEV_LOW: 2}
    findings.sort(key=lambda f: (order[f["severity"]], -f["impact_lei"]))
    for i, f in enumerate(findings, 1):
        f["id"] = f"F-{i:02d}"
    return findings


# ══ Карта рисков ════════════════════════════════════════════════════════

def _heat_map(findings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Вероятность × влияние по шкале 1–5 для каждой находки.

    Вероятность выводится из доли отклонений (как часто контроль не
    срабатывал), влияние — из денежной оценки. Обе величины считаются из
    результата тестирования, а не назначаются экспертно: иначе карта
    рисков превращается в картинку.
    """
    def likelihood(rate: float, tested: int) -> int:
        # На популяции меньше порога о частоте судить нельзя: ставим
        # минимальную вероятность, иначе «1 из 1» уезжает в верхний ряд
        # карты и вытесняет оттуда настоящие риски.
        if tested < MIN_RATE_POPULATION:
            return 1
        for bound, score in ((10.0, 5), (5.0, 4), (1.0, 3), (0.1, 2)):
            if rate >= bound:
                return score
        return 1

    def impact(lei: float, exceptions: int) -> int:
        for bound, score in ((HIGH_IMPACT_LEI, 5), (MED_IMPACT_LEI, 4),
                             (500.0, 3), (1.0, 2)):
            if lei >= bound:
                return score
        return 2 if exceptions > 5 else 1

    cells = []
    for f in findings:
        cells.append({
            "id": f["id"], "title": f["title"], "severity": f["severity"],
            "likelihood": likelihood(f["rate_pct"], f["tested"]),
            "impact": impact(f["impact_lei"], f["exceptions"]),
        })
    return cells


# ══ Заключение ══════════════════════════════════════════════════════════

OPINIONS = [
    ("Существенных недостатков не выявлено",
     "Контрольная среда контура признана эффективной: тесты по существу "
     "не выявили отклонений, влияющих на достоверность расчётов."),
    ("Удовлетворительно с замечаниями",
     "Контрольная среда в целом эффективна. Выявленные отклонения носят "
     "локальный характер и не искажают расчёт зарплаты и объёмов "
     "поставок по периоду в целом."),
    ("Требуются улучшения",
     "Отдельные контроли не обеспечивают предотвращение ошибок: "
     "выявлены отклонения средней значимости, требующие устранения до "
     "перевода контура в промышленную эксплуатацию."),
    ("Контрольная среда неэффективна",
     "Выявлены отклонения высокой значимости: числа, которые контур "
     "выдаёт бухгалтерии и руководству, не могут использоваться без "
     "ручной перепроверки до устранения находок."),
]


def _opinion(findings: Sequence[Dict[str, Any]],
             controls: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    high = sum(1 for f in findings if f["severity"] == SEV_HIGH)
    med = sum(1 for f in findings if f["severity"] == SEV_MED)
    low = sum(1 for f in findings if f["severity"] == SEV_LOW)
    if high:
        idx = 3
    elif med:
        idx = 2
    elif low:
        idx = 1
    else:
        idx = 0
    title, text = OPINIONS[idx]
    return {"level": idx, "title": title, "text": text,
            "high": high, "medium": med, "low": low,
            "controls_ok": sum(1 for c in controls if c["rating"] == RATE_OK),
            "controls_warn": sum(1 for c in controls if c["rating"] == RATE_WARN),
            "controls_bad": sum(1 for c in controls if c["rating"] == RATE_BAD),
            "controls_na": sum(1 for c in controls if c["rating"] == RATE_NA),
            "controls_total": len(controls)}


SCOPE = [
    "Расчёт заработной платы водителей бензовозов по нормативному пробегу "
    "(ТЗ «Автоматизация расчёта расходов автопарка» от 18.09.2026).",
    "Планирование потребности АЗС в топливе, формирование и исполнение "
    "рейсов (ТЗ «Автоматизация распределения топлива» от 18.09.2026).",
    "Контроль фактического пробега и расхода дизельного топлива "
    "бензовозами.",
    "Настройки контура, действующие по периодам: ставка за километр, "
    "лимиты резервуаров, состав отсеков и групп АЗС.",
]

METHODOLOGY = [
    "Тестирование полной популяции (data & analytics): каждый документ "
    "периода пересчитан независимо, выборочный метод применён только там, "
    "где контроль не отражён в данных.",
    "Пересчёт выполнен отдельной реализацией формул (modules/autopark/"
    "audit.py), не использующей проверяемый код расчёта, — совпадение "
    "результата не может быть следствием общей ошибки.",
    "Оценка контроля даётся по двум измерениям: дизайн (предотвращает ли "
    "правило ошибку в принципе) и операционная эффективность (срабатывало "
    "ли оно на данных периода).",
    "Контроль с дефектом дизайна не получает оценку выше «требует "
    "улучшения», даже если отклонений в периоде не обнаружено.",
    "Значимость находки определяется долей отклонений и денежной оценкой, "
    "а не экспертным суждением.",
]

LIMITATIONS = [
    "Аудит проверяет внутреннюю непротиворечивость системы и соответствие "
    "её собственным правилам. Он не подтверждает достоверность исходных "
    "данных: что бензовоз физически проехал маршрут, а в резервуар "
    "фактически поступили литры.",
    "Фактический пробег и расход топлива принимаются в том виде, в каком "
    "их передаёт GPS-прослойка; независимая сверка с показаниями "
    "провайдера в объём работы не входила.",
    "Остатки в резервуарах приняты по данным контура. Сверка с Petrol "
    "Expert и инвентаризацией не проводилась — интеграция не подключена.",
    "Заключение относится к периоду и набору данных, указанным на "
    "титульном листе, и не распространяется на последующие изменения "
    "конфигурации.",
]


def run_audit(pop: Dict[str, Any], *, seed: str = "BEMOL-2026") -> Dict[str, Any]:
    """Полный проход: тесты → контроли → находки → заключение."""
    for key in ("settings", "trips", "trip_items", "tanks", "trucks", "drivers"):
        if key not in pop:
            raise AuditInputError(f"в популяции нет раздела «{key}»")

    tests = [fn(pop) for fn in TESTS]
    tests_by_id = {t["id"]: t for t in tests}
    controls = _build_controls(tests_by_id)
    findings = _build_findings(tests, controls)
    opinion = _opinion(findings, controls)

    manual = [c for c in controls if c["type"] == "Ручной"]
    sample_rows = []
    trips_non_draft = [t for t in pop["trips"] if t.get("status_code") != "DRAFT"]
    for ctl in manual:
        idxs = sample_indexes(len(trips_non_draft), ctl["sample"],
                              f"{seed}:{ctl['id']}")
        for n, i in enumerate(idxs, 1):
            trip = trips_non_draft[i]
            sample_rows.append([
                ctl["id"], n, trip["id"],
                (_as_date(trip.get("trip_date")) or date.min).isoformat(),
                trip.get("waybill_no") or "—",
                trip.get("created_by") or "—", trip.get("approved_by") or "—",
                "Отклонение" if str(trip.get("created_by") or "").lower()
                == str(trip.get("approved_by") or "").lower() else "Без отклонений",
            ])

    total_tested = sum(t["tested"] for t in tests)
    total_exceptions = sum(t["exceptions"] for t in tests)
    return {
        "entity": pop.get("entity", "—"),
        "period": pop.get("period", {}),
        "data_label": pop.get("data_label", ""),
        "scope": SCOPE,
        "methodology": METHODOLOGY,
        "limitations": LIMITATIONS,
        "tests": tests,
        "controls": controls,
        "findings": findings,
        "opinion": opinion,
        "heat_map": _heat_map(findings),
        "sample": {
            "columns": ["Контроль", "№", "Рейс", "Дата", "Путевой лист",
                        "Создал", "Утвердил", "Результат"],
            "rows": sample_rows,
            "seed": seed,
        },
        "facts": {
            "trips": len(pop["trips"]),
            "trips_tested": len(trips_non_draft),
            "items": len(pop["trip_items"]),
            "stations": len(pop.get("stations") or []),
            "tanks": len(pop["tanks"]),
            "trucks": len(pop["trucks"]),
            "drivers": len(pop["drivers"]),
            "total_tested": total_tested,
            "total_exceptions": total_exceptions,
            "exception_rate_pct": _pct(total_exceptions, total_tested),
            "impact_lei": round(sum(t["impact_lei"] for t in tests), 2),
        },
    }

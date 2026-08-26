"""Autopark — контроллер модуля: HTTP наверху, хранилище внизу.

Стиль — как в других модулях проекта (см. modules/sda/controller.py):
валидация формы живёт здесь, а не в store — в базу не должна уезжать
запись, про которую заранее известно, что она не пройдёт CHECK. Каждый
публичный метод ловит всё сам и возвращает
{"success": bool, "data": ..., "message": str, ["warnings": [...]]} —
исключение наружу не выпускается.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from modules.autopark import rules
from modules.autopark.store import AutoparkStore

VALID_KINDS = ("LOAD", "STATION", "END")
VALID_TRIP_TYPES = ("DOMESTIC", "IMPORT")


class AutoparkValidationError(Exception):
    """Ошибка проверки формы — превращается в {"success": False, ...}."""


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _as_int(raw: Any, label: str) -> int:
    if raw in (None, ""):
        raise AutoparkValidationError(f"{label} обязателен")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise AutoparkValidationError(f"{label} должен быть целым числом")


def _as_float(raw: Any, label: str) -> float:
    if raw in (None, ""):
        raise AutoparkValidationError(f"{label} обязателен")
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise AutoparkValidationError(f"{label} должен быть числом")


def _as_optional_float(raw: Any, label: str) -> Optional[float]:
    if raw in (None, ""):
        return None
    return _as_float(raw, label)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AutoparkValidationError(message)


class AutoparkController:
    """Тонкий слой между Flask и AutoparkStore/rules."""

    # ── справочники ──────────────────────────────────────────────────

    @staticmethod
    def refs() -> Dict[str, Any]:
        """Все справочники одним ответом — так их запрашивает UI (/api/refs)."""
        results = {
            "products": AutoparkStore.list_products(),
            "stations": AutoparkStore.list_stations(),
            "load_points": AutoparkStore.list_load_points(),
            "end_points": AutoparkStore.list_end_points(),
            "trucks": AutoparkStore.list_trucks(),
            "drivers": AutoparkStore.list_drivers(),
            "distances": AutoparkStore.list_distances(),
            "settings": AutoparkStore.get_settings(),
        }
        failed = {k: v["message"] for k, v in results.items()
                 if not v.get("success")}
        if failed:
            return _fail("; ".join(f"{k}: {m}" for k, m in failed.items()))
        return {"success": True, "message": "",
               "data": {k: v["data"] for k, v in results.items()}}

    @staticmethod
    def station_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _require(bool((payload.get("code") or "").strip()),
                     "Код АЗС обязателен")
            _require(bool((payload.get("name") or "").strip()),
                     "Наименование АЗС обязательно")
            for tank in (payload.get("tanks") or []):
                cap = _as_float(tank.get("capacity_l"), "Вместимость резервуара")
                _require(cap > 0, "Вместимость резервуара должна быть больше нуля")
                _require(bool(tank.get("product_code")),
                         "Продукт резервуара обязателен")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.upsert_station(payload)

    @staticmethod
    def truck_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _require(bool((payload.get("plate") or "").strip()),
                     "Госномер обязателен")
            capacity = _as_float(payload.get("capacity_l"), "Вместимость бензовоза")
            _require(capacity > 0, "Вместимость бензовоза должна быть больше нуля")
            sections = _as_int(payload.get("sections_cnt") or 1,
                               "Количество секций")
            _require(sections > 0, "Количество секций должно быть больше нуля")
            norm = _as_float(payload.get("norm_l_per_100km"),
                             "Норма расхода топлива")
            _require(norm > 0, "Норма расхода топлива должна быть больше нуля")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.upsert_truck(payload)

    @staticmethod
    def driver_upsert(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _require(bool((payload.get("full_name") or "").strip()),
                     "ФИО водителя обязательно")
            _require(bool((payload.get("tab_no") or "").strip()),
                     "Табельный номер обязателен")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.upsert_driver(payload)

    # ── матрица расстояний ──────────────────────────────────────────

    @staticmethod
    def distance_list() -> Dict[str, Any]:
        return AutoparkStore.list_distances()

    @staticmethod
    def distance_set(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from_kind = (payload.get("from_kind") or "").upper()
            to_kind = (payload.get("to_kind") or "").upper()
            _require(from_kind in VALID_KINDS,
                     f"from_kind должен быть одним из {VALID_KINDS}")
            _require(to_kind in VALID_KINDS,
                     f"to_kind должен быть одним из {VALID_KINDS}")
            _require(payload.get("from_id") not in (None, ""), "from_id обязателен")
            _require(payload.get("to_id") not in (None, ""), "to_id обязателен")
            km = _as_float(payload.get("km"), "Расстояние (км)")
            _require(km >= 0, "Расстояние не может быть отрицательным")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.set_distance(from_kind, payload.get("from_id"),
                                         to_kind, payload.get("to_id"), km)

    # ── настройки ────────────────────────────────────────────────────

    @staticmethod
    def settings_get() -> Dict[str, Any]:
        return AutoparkStore.get_settings()

    @staticmethod
    def settings_update(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rate = _as_float(payload.get("rate_per_km"), "Ставка за км")
            _require(rate >= 0, "Ставка за км не может быть отрицательной")
            bonus = _as_float(payload.get("trip_bonus"), "Доплата за рейс")
            _require(bonus >= 0, "Доплата за рейс не может быть отрицательной")
            safety_days = _as_float(payload.get("safety_days"), "Страховой запас (дни)")
            _require(safety_days >= 0, "Страховой запас не может быть отрицательным")
            km_limit = _as_float(payload.get("km_deviation_limit"),
                                 "Лимит отклонения по пробегу")
            _require(km_limit >= 0, "Лимит отклонения не может быть отрицательным")
            fuel_pct = _as_float(payload.get("fuel_deviation_pct"),
                                 "Лимит отклонения по топливу (%)")
            _require(fuel_pct >= 0, "Лимит отклонения по топливу не может быть отрицательным")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.update_settings(payload)

    # ── поставки ─────────────────────────────────────────────────────

    @staticmethod
    def delivery_add(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            _require(bool(payload.get("deliv_date")), "Дата поставки обязательна")
            _require(bool(payload.get("product_code")), "Вид нефтепродукта обязателен")
            volume = _as_float(payload.get("volume_l"), "Объём поставки")
            _require(volume > 0, "Объём поставки должен быть больше нуля")
            for label in ("load_point_id", "station_id", "truck_id", "driver_id"):
                _require(payload.get(label) not in (None, ""),
                         f"Поле {label} обязательно")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        res = AutoparkStore.insert_delivery(payload)
        if res.get("success"):
            AutoparkStore.log_event("DELIVERY_ADD", "FLT_DELIVERIES",
                                    res["data"]["id"],
                                    f"{payload.get('product_code')} "
                                    f"{payload.get('volume_l')} L",
                                    payload.get("_username") or "system")
        return res

    @staticmethod
    def delivery_list(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        unassigned_only = str(args.get("unassigned_only") or "").lower() in (
            "1", "true", "yes")
        return AutoparkStore.list_deliveries(date_from, date_to, unassigned_only)

    # ── рейсы ────────────────────────────────────────────────────────

    @staticmethod
    def _load_point_is_foreign(load_point_id) -> Optional[bool]:
        lp = AutoparkStore.list_load_points()
        if not lp.get("success"):
            return None
        for row in lp["data"]:
            if row["id"] == load_point_id:
                return bool(row.get("is_foreign"))
        return None

    @staticmethod
    def trip_create_manual(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ручное формирование рейса логистом (ТЗ п.6, вариант 2).

        Тип рейса определяется автоматически через rules.classify_trip по
        признаку IS_FOREIGN пункта загрузки (конечные пункты в схеме не
        несут собственного признака "за рубежом" — единственный сегодня
        конечный пункт BAZA внутренний, поэтому end_point_is_foreign
        всегда передаётся как False; это осознанное ограничение первой
        очереди, а не забытый случай). Ручной type_code в payload
        допускается, но при расхождении с классификацией — это не отказ,
        а предупреждение в ответе (ТЗ п.13: "ошибочная классификация").
        """
        try:
            trip_date = payload.get("trip_date")
            _require(bool(trip_date), "Дата рейса обязательна")
            truck_id = _as_int(payload.get("truck_id"), "Автомобиль")
            driver_id = _as_int(payload.get("driver_id"), "Водитель")
            load_point_id = _as_int(payload.get("load_point_id"), "Пункт загрузки")
            end_point_id = _as_int(payload.get("end_point_id"), "Конечный пункт")
            stations = payload.get("stations") or []
            _require(bool(stations), "Маршрут должен включать хотя бы одну АЗС")
            for st in stations:
                _require(st.get("station_id") not in (None, ""),
                         "У каждой остановки должна быть указана АЗС")
                for item in (st.get("items") or []):
                    vol = _as_float(item.get("volume_l"), "Объём слива на АЗС")
                    _require(vol > 0, "Объём слива на АЗС должен быть больше нуля")
        except AutoparkValidationError as exc:
            return _fail(str(exc))

        load_is_foreign = AutoparkController._load_point_is_foreign(load_point_id)
        if load_is_foreign is None:
            return _fail(f"Пункт загрузки {load_point_id} не найден")
        computed_type = rules.classify_trip(load_is_foreign, False)

        warnings: List[str] = []
        manual_type = (payload.get("type_code") or "").upper() or None
        if manual_type and manual_type not in VALID_TRIP_TYPES:
            return _fail(f"type_code должен быть одним из {VALID_TRIP_TYPES}")
        if manual_type and manual_type != computed_type:
            warnings.append(
                f"Указанный тип рейса {manual_type} расходится с "
                f"автоматической классификацией по географии ({computed_type}) "
                "— проверьте маршрут (ТЗ п.13)")
        type_code = manual_type or computed_type

        dist_lookup = AutoparkStore.distance_lookup_fn()
        station_ids = [st["station_id"] for st in stations]
        legs = rules.route_legs(load_point_id, station_ids, end_point_id, dist_lookup)
        try:
            norm_km = rules.norm_route_km([leg["km"] for leg in legs])
        except ValueError as exc:
            return _fail(str(exc))

        store_stops = [{"station_id": st["station_id"],
                        "items": [{"product_code": it["product_code"],
                                  "volume_l": it["volume_l"]}
                                 for it in (st.get("items") or [])]}
                      for st in stations]

        res = AutoparkStore.create_trip({
            "trip_date": trip_date, "truck_id": truck_id,
            "driver_id": driver_id, "type_code": type_code,
            "load_point_id": load_point_id, "end_point_id": end_point_id,
            "source": "MANUAL", "norm_km": norm_km,
            "delivery_ids": payload.get("delivery_ids") or [],
        }, store_stops)
        if res.get("success"):
            AutoparkStore.log_event("TRIP_CREATE_MANUAL", "FLT_TRIPS",
                                    res["data"]["trip_id"],
                                    f"{type_code} {norm_km} km",
                                    payload.get("_username") or "system")
            res = dict(res)
            if warnings:
                res["warnings"] = warnings
        return res

    @staticmethod
    def trip_autoform(date_from, date_to) -> Dict[str, Any]:
        """Автоматическое формирование рейсов из непривязанных накладных
        (ТЗ п.6, вариант 1): группировка по (дата, авто, водитель, пункт
        загрузки), внутри группы — обход АЗС жадным ближайшим соседом.
        """
        try:
            date_from = _require_date(date_from, "date_from")
            date_to = _require_date(date_to, "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        deliv = AutoparkStore.list_deliveries(date_from, date_to, unassigned_only=True)
        if not deliv.get("success"):
            return deliv

        end_points = AutoparkStore.list_end_points()
        if not end_points.get("success") or not end_points["data"]:
            return _fail("Не заведён ни один конечный пункт маршрута")
        # Первая очередь: единственный сконфигурированный конечный пункт
        # используется по умолчанию для всех автосформированных рейсов —
        # выбор конечного пункта логистом вручную не входит в вариант 1
        # ТЗ (см. docstring класса).
        end_point_id = end_points["data"][0]["id"]

        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for d in deliv["data"]:
            key = (d["deliv_date"], d["truck_id"], d["driver_id"], d["load_point_id"])
            groups.setdefault(key, []).append(d)

        dist_lookup = AutoparkStore.distance_lookup_fn()
        created = []
        skipped = []
        for (trip_date, truck_id, driver_id, load_point_id), deliveries in groups.items():
            load_is_foreign = AutoparkController._load_point_is_foreign(load_point_id)
            if load_is_foreign is None:
                skipped.append({"key": str((trip_date, truck_id, driver_id,
                                            load_point_id)),
                                "reason": f"Пункт загрузки {load_point_id} не найден"})
                continue
            type_code = rules.classify_trip(load_is_foreign, False)

            station_ids = list(dict.fromkeys(d["station_id"] for d in deliveries))
            try:
                # rules.py не выставляет наружу обход соседей отдельной
                # публичной функцией (только внутри plan_trips) — берём
                # приватный хелпер модуля напрямую, а не переизобретаем
                # тот же жадный алгоритм здесь.
                ordered = rules._nearest_neighbor_order(
                    load_point_id, station_ids, dist_lookup)
            except Exception as exc:  # noqa: BLE001
                skipped.append({"key": str((trip_date, truck_id, driver_id,
                                            load_point_id)),
                                "reason": str(exc)})
                continue

            stops = []
            for station_id in ordered:
                items_by_product: Dict[str, float] = {}
                for d in deliveries:
                    if d["station_id"] != station_id:
                        continue
                    items_by_product[d["product_code"]] = (
                        items_by_product.get(d["product_code"], 0)
                        + float(d["volume_l"]))
                stops.append({"station_id": station_id,
                             "items": [{"product_code": p, "volume_l": v}
                                      for p, v in items_by_product.items()]})

            legs = rules.route_legs(load_point_id, ordered, end_point_id, dist_lookup)
            try:
                norm_km = rules.norm_route_km([leg["km"] for leg in legs])
            except ValueError as exc:
                skipped.append({"key": str((trip_date, truck_id, driver_id,
                                            load_point_id)),
                                "reason": str(exc)})
                continue

            delivery_ids = [d["id"] for d in deliveries]
            res = AutoparkStore.create_trip({
                "trip_date": trip_date, "truck_id": truck_id,
                "driver_id": driver_id, "type_code": type_code,
                "load_point_id": load_point_id, "end_point_id": end_point_id,
                "source": "AUTO", "norm_km": norm_km,
                "delivery_ids": delivery_ids,
            }, stops)
            if not res.get("success"):
                skipped.append({"key": str((trip_date, truck_id, driver_id,
                                            load_point_id)),
                                "reason": res.get("message")})
                continue
            AutoparkStore.log_event("TRIP_CREATE_AUTO", "FLT_TRIPS",
                                    res["data"]["trip_id"],
                                    f"{type_code} {norm_km} km, "
                                    f"{len(delivery_ids)} deliveries",
                                    "auto")
            created.append(res["data"])

        return {"success": True, "message": "",
               "data": {"created": len(created), "trips": created,
                        "skipped": skipped}}

    @staticmethod
    def trip_list(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        driver_id = args.get("driver_id")
        driver_id = int(driver_id) if driver_id not in (None, "") else None
        return AutoparkStore.list_trips(date_from, date_to, driver_id)

    @staticmethod
    def trip_approve(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        try:
            trip_id = _as_int(payload.get("trip_id"), "trip_id")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        res = AutoparkStore.approve_trip(trip_id, username)
        if res.get("success"):
            AutoparkStore.log_event("TRIP_APPROVE", "FLT_TRIPS", trip_id,
                                    "approved", username)
        return res

    @staticmethod
    def trip_set_fact(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            trip_id = _as_int(payload.get("trip_id"), "trip_id")
            fact_km = _as_float(payload.get("fact_km"), "Фактический пробег")
            _require(fact_km >= 0, "Фактический пробег не может быть отрицательным")
            fact_minutes = _as_int(payload.get("fact_minutes"), "Фактическое время (мин)")
            _require(fact_minutes >= 0, "Фактическое время не может быть отрицательным")
            fact_fuel_l = _as_optional_float(payload.get("fact_fuel_l"),
                                             "Фактический расход ДТ")
            if fact_fuel_l is not None:
                _require(fact_fuel_l >= 0,
                         "Фактический расход ДТ не может быть отрицательным")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.set_trip_fact(trip_id, fact_km, fact_minutes,
                                           fact_fuel_l)

    # ── учёт АЗС ─────────────────────────────────────────────────────

    @staticmethod
    def stock_upload(payload: Dict[str, Any]) -> Dict[str, Any]:
        rows = payload.get("rows") or []
        try:
            _require(bool(rows), "Список строк учёта не может быть пустым")
            for row in rows:
                for label in ("station_id", "product_code", "stock_date",
                             "open_l", "close_l"):
                    _require(row.get(label) not in (None, ""),
                             f"Поле {label} обязательно в каждой строке")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.upsert_station_stock(rows)

    # ── планирование поставок ────────────────────────────────────────

    @staticmethod
    def supply_plan() -> Dict[str, Any]:
        """Предложение рейсов под рассчитанную потребность АЗС (ТЗ п.7).

        Ничего не пишет в БД — только план-предложение, который логист
        либо утвердит вручную (trip_create_manual), либо отклонит.
        """
        settings_res = AutoparkStore.get_settings()
        if not settings_res.get("success"):
            return settings_res
        settings = settings_res["data"]

        stock_res = AutoparkStore.stock_days_report()
        if not stock_res.get("success"):
            return stock_res

        stations_res = AutoparkStore.list_stations()
        if not stations_res.get("success"):
            return stations_res
        capacity_by_key = {}
        for st in stations_res["data"]:
            for tank in st.get("tanks", []):
                capacity_by_key[(st["id"], tank["product_code"])] = tank["capacity_l"]

        # В пути = объём непривязанных к рейсу накладных на эту АЗС и
        # продукт (ещё не доставлено физически, но уже отгружено).
        # Диапазон дат -- настоящие date(), не строки: BETWEEN на живом
        # Oracle падает с ORA-01861 на голой строке (см. _require_date).
        in_transit_res = AutoparkStore.list_deliveries(
            date(1, 1, 1), date(9999, 12, 31), unassigned_only=True)
        in_transit_by_key: Dict[tuple, float] = {}
        if in_transit_res.get("success"):
            for d in in_transit_res["data"]:
                key = (d["station_id"], d["product_code"])
                in_transit_by_key[key] = (in_transit_by_key.get(key, 0)
                                          + float(d["volume_l"]))

        needs = []
        for row in stock_res["data"]:
            avg_daily = float(row.get("avg_daily_sales_l") or 0)
            current_l = float(row.get("current_l") or 0)
            min_stock = float(row.get("min_stock_l") or 0)
            capacity = capacity_by_key.get((row["station_id"], row["product_code"]))
            if capacity is None:
                continue
            # Прогноз реализации до следующей поставки — на глубину
            # страхового периода настроек (первая очередь: без отдельного
            # прогноза продаж используем тот же среднесуточный темп).
            forecast_sales = avg_daily * float(settings.get("safety_days") or 0)
            in_transit = in_transit_by_key.get(
                (row["station_id"], row["product_code"]), 0)
            need = rules.need_volume_l(current_l, min_stock, forecast_sales,
                                       in_transit, capacity)
            if need <= 0:
                continue
            needs.append({"station_id": row["station_id"],
                         "product_code": row["product_code"],
                         "need_l": need,
                         "days_left": row.get("stock_days")})

        if not needs:
            return {"success": True, "message": "", "data": {"trips": []}}

        trucks_res = AutoparkStore.list_trucks()
        if not trucks_res.get("success"):
            return trucks_res
        trucks = [{"id": t["id"], "capacity_l": float(t["capacity_l"]),
                  "sections_cnt": t.get("sections_cnt") or 1,
                  "products": t.get("products") or None}
                 for t in trucks_res["data"] if t.get("active")]

        load_points_res = AutoparkStore.list_load_points()
        if not load_points_res.get("success"):
            return load_points_res
        # Точка отгрузки для плана поставок — первый внутренний (не
        # зарубежный) пункт загрузки; первая очередь не поддерживает
        # выбор конкретного пункта отгрузки для автопланирования.
        domestic_points = [p for p in load_points_res["data"]
                          if not p.get("is_foreign")]
        if not domestic_points:
            return _fail("Не заведён ни один внутренний пункт загрузки")
        load_point_id = domestic_points[0]["id"]

        dist_lookup = AutoparkStore.distance_lookup_fn()
        try:
            proposals = rules.plan_trips(needs, trucks, dist_lookup, load_point_id)
        except ValueError as exc:
            return _fail(str(exc))
        return {"success": True, "message": "",
               "data": {"trips": proposals, "load_point_id": load_point_id}}

    # ── отчёты ───────────────────────────────────────────────────────

    @staticmethod
    def payroll_report(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        driver_id = args.get("driver_id")
        driver_id = int(driver_id) if driver_id not in (None, "") else None
        return AutoparkStore.trip_pay_report(date_from, date_to, driver_id)

    @staticmethod
    def control_report(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.trip_control_report(date_from, date_to)

    @staticmethod
    def driver_report(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.driver_summary(date_from, date_to)

    @staticmethod
    def truck_report(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.truck_summary(date_from, date_to)

    @staticmethod
    def station_report(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        return AutoparkStore.station_supply_report(date_from, date_to)

    @staticmethod
    def fuel_prices(args) -> Dict[str, Any]:
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))
        product = args.get("product") or None
        return AutoparkStore.list_fuel_prices(date_from, date_to, product)

    @staticmethod
    def management_report(args) -> Dict[str, Any]:
        """Сводка руководству (ТЗ п.14).

        Допущение, зафиксированное явно (проверяется тестом): "стоимость
        перевозки 1 литра топлива" считается только по зарплатной части
        (сумма TOTAL_PAY / суммарный перевезённый объём) — стоимость
        самого топлива в расчёт не входит, у модуля нет источника данных
        о закупочной цене нефтепродукта на литр. Средняя загрузка
        бензовозов = перевезённый объём / (число рейсов × вместимость
        задействованных бензовозов).
        """
        try:
            date_from = _require_date(args.get("date_from"), "date_from")
            date_to = _require_date(args.get("date_to"), "date_to")
        except AutoparkValidationError as exc:
            return _fail(str(exc))

        payroll = AutoparkStore.trip_pay_report(date_from, date_to)
        if not payroll.get("success"):
            return payroll
        control = AutoparkStore.trip_control_report(date_from, date_to)
        if not control.get("success"):
            return control
        trucks = AutoparkStore.truck_summary(date_from, date_to)
        if not trucks.get("success"):
            return trucks

        total_pay = sum(float(r["total_pay"]) for r in payroll["data"])
        total_norm_km = sum(float(r["norm_km"] or 0) for r in payroll["data"])
        total_fact_km = sum(float(r["fact_km"] or 0) for r in control["data"])
        over_limit_cnt = sum(1 for r in control["data"] if r.get("over_km_limit"))
        fuel_over_limit_cnt = sum(1 for r in control["data"]
                                  if r.get("over_fuel_limit"))

        total_volume = sum(float(t["total_volume_l"]) for t in trucks["data"])
        total_trip_cnt = sum(int(t["trip_cnt"]) for t in trucks["data"])
        trucks_res = AutoparkStore.list_trucks()
        capacities = {t["id"]: float(t["capacity_l"])
                     for t in trucks_res.get("data") or []}
        total_capacity_trips = sum(
            int(t["trip_cnt"]) * capacities.get(t["truck_id"], 0)
            for t in trucks["data"])

        cost_per_liter = (total_pay / total_volume) if total_volume else None
        avg_loading_pct = (100.0 * total_volume / total_capacity_trips
                          if total_capacity_trips else None)

        return {"success": True, "message": "", "data": {
            "total_pay": total_pay,
            "total_norm_km": total_norm_km,
            "total_fact_km": total_fact_km,
            "total_volume_l": total_volume,
            "total_trip_cnt": total_trip_cnt,
            "cost_per_liter": cost_per_liter,
            "avg_loading_pct": avg_loading_pct,
            "km_deviation_cnt": over_limit_cnt,
            "fuel_deviation_cnt": fuel_over_limit_cnt,
        }}


def _require_date(raw: Any, label: str) -> date:
    """Строку 'YYYY-MM-DD' (из query string/JSON) -- в объект date.

    Критично: store.py биндит date_from/date_to напрямую в
    ``DATE_COLUMN BETWEEN :date_from AND :date_to`` без явного TO_DATE.
    Если передать туда голую строку, Oracle пытается неявно привести её
    по СВОЕМУ дефолтному NLS_DATE_FORMAT сессии (у этой ADB он не
    'YYYY-MM-DD') и падает с ORA-01861 "literal does not match format
    string" -- воспроизведено на живом контуре при сквозной проверке
    задачи 3 (все report/list-эндпоинты возвращали success=False).
    python-oracledb передаёt объект ``datetime.date`` как настоящий
    Oracle DATE bind без всякого NLS-форматирования, поэтому парсинг
    должен случиться здесь, ДО передачи в store, а не полагаться на
    неявное приведение в SQL.
    """
    if not raw:
        raise AutoparkValidationError(f"Параметр {label} обязателен")
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        raise AutoparkValidationError(
            f"Параметр {label} должен быть датой в формате YYYY-MM-DD")

"""Autopark — контроллер контура распределения топлива (ТЗ от 18.09.2026).

Тонкий слой: разбирает форму, зовёт правила (`supply_rules.py`) и
хранилище (`supply_store.py`), возвращает `{"success", "data", "message"}`.
Ни одного SQL и ни одной формулы — они живут в своих файлах.

Разделение ответственности по ТЗ:
  расчёт потребности и подбор отсеков  -> supply_rules.build_plan
  сохранение расчёта и его исполнение  -> supply_store.SupplyStore
  проверки ручной правки (п.7)          -> supply_rules.validate_loads
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from modules.autopark import supply_rules as rules
from modules.autopark.store import AutoparkStore
from modules.autopark.supply_store import SupplyStore


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def _as_float(raw: Any, label: str) -> Optional[float]:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается число, получено {raw!r}")


def _as_int(raw: Any, label: str) -> Optional[int]:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается целое число, получено {raw!r}")


def _as_date(raw: Any, label: str) -> date:
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается дата в формате ГГГГ-ММ-ДД")


class SupplyController:
    """Потребность, план, отсеки, исполнение поставки."""

    # ── справочные данные контура ───────────────────────────────────

    @staticmethod
    def tank_state() -> Dict[str, Any]:
        return SupplyStore.tank_state()

    @staticmethod
    def tank_limits_save(tank_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            tank_id = _as_int(tank_id, "Резервуар")
            data = {
                "max_fill_l": _as_float(payload.get("max_fill_l"), "Допустимый залив"),
                "min_stock_l": _as_float(payload.get("min_stock_l"), "Минимальный остаток"),
                "max_cover_days": _as_float(payload.get("max_cover_days"), "Запас, дней"),
                "ext_code": (payload.get("ext_code") or None),
            }
        except ValueError as exc:
            return _fail(str(exc))
        if tank_id is None:
            return _fail("Не указан резервуар")
        if data["max_fill_l"] is not None and data["max_fill_l"] <= 0:
            return _fail("Допустимый залив должен быть больше нуля")
        if data["max_cover_days"] is not None and data["max_cover_days"] <= 0:
            return _fail("Допустимый запас в днях должен быть больше нуля")
        return SupplyStore.save_tank_limits(tank_id, data)

    @staticmethod
    def stock_push(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Приём остатков из Petrol Expert (ТЗ п.2).

        Формат пакета намеренно простой: список
        ``{"station_code"|"tank_id", "product_code", "current_l"}`` — под
        него подстраивается выгрузка внешней системы, а не наоборот.
        """
        rows = payload.get("rows") or payload.get("data") or []
        if not isinstance(rows, list):
            return _fail("Ожидается список остатков в поле rows")
        clean: List[Dict[str, Any]] = []
        for i, row in enumerate(rows, 1):
            try:
                current = _as_float(row.get("current_l"), f"Строка {i}: остаток")
            except ValueError as exc:
                return _fail(str(exc))
            if current is None or current < 0:
                return _fail(f"Строка {i}: остаток должен быть неотрицательным числом")
            clean.append({"tank_id": row.get("tank_id"),
                          "station_code": row.get("station_code"),
                          "ext_code": row.get("ext_code"),
                          "product_code": row.get("product_code"),
                          "current_l": current})
        source = payload.get("source") or "PETROL_EXPERT"
        if source not in ("PETROL_EXPERT", "MANUAL", "UNA"):
            return _fail("Неизвестный источник остатков")
        return SupplyStore.push_stock(clean, source)

    @staticmethod
    def sections_list(truck_id: Any = None) -> Dict[str, Any]:
        try:
            truck_id = _as_int(truck_id, "Цистерна")
        except ValueError as exc:
            return _fail(str(exc))
        return SupplyStore.list_sections(truck_id)

    @staticmethod
    def sections_save(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Отсеки цистерны (ТЗ п.6: бензин 5 отсеков, дизель 4)."""
        try:
            truck_id = _as_int(payload.get("truck_id"), "Цистерна")
        except ValueError as exc:
            return _fail(str(exc))
        if truck_id is None:
            return _fail("Не указана цистерна")
        raw = payload.get("sections") or []
        if not raw:
            return _fail("Нужен хотя бы один отсек")
        sections: List[Dict[str, Any]] = []
        for i, sec in enumerate(raw, 1):
            try:
                volume = _as_float(sec.get("volume_l"), f"Отсек {i}: объём")
            except ValueError as exc:
                return _fail(str(exc))
            if not volume or volume <= 0:
                return _fail(f"Отсек {i}: объём должен быть больше нуля")
            sections.append({"seq_no": i, "volume_l": volume})

        trucks = AutoparkStore.list_trucks()
        if trucks.get("success"):
            truck = next((t for t in trucks["data"] if t["id"] == truck_id), None)
            if truck:
                total = sum(s["volume_l"] for s in sections)
                if total > float(truck["capacity_l"]) + 1e-6:
                    return _fail(f"Сумма отсеков {total:.0f} л больше вместимости "
                                 f"цистерны {float(truck['capacity_l']):.0f} л")
        return SupplyStore.save_sections(truck_id, sections)

    @staticmethod
    def groups_list() -> Dict[str, Any]:
        return SupplyStore.list_groups()

    @staticmethod
    def group_save(payload: Dict[str, Any]) -> Dict[str, Any]:
        code = (payload.get("code") or "").strip()
        name = (payload.get("name") or "").strip()
        if not code or not name:
            return _fail("Нужны код и наименование группы")
        station_ids = payload.get("station_ids") or []
        if not isinstance(station_ids, list):
            return _fail("station_ids должен быть списком")
        try:
            station_ids = [_as_int(s, "АЗС") for s in station_ids]
        except ValueError as exc:
            return _fail(str(exc))
        return SupplyStore.save_group({"id": payload.get("id"), "code": code,
                                       "name": name, "active": payload.get("active", True),
                                       "station_ids": station_ids})

    # ── расчёт плана ────────────────────────────────────────────────

    @staticmethod
    def _truck_catalog() -> Dict[str, Any]:
        """Бензовозы с их реальными отсеками и допустимыми семействами топлива.

        Цистерна, которой разрешены и бензин, и дизель, — это НЕ ошибка
        справочника: ТЗ п.6 запрещает смешивать топливо в одном РЕЙСЕ, а
        не приписывает цистерну к виду топлива навсегда. Поэтому здесь
        перечисляются допустимые семейства, а выбор одного из них делает
        планировщик на каждый рейс.

        Первая версия жёстко назначала каждой цистерне одно семейство — и
        на живом парке, где всем трём цистернам разрешено и то и другое,
        весь парк стал «бензиновым», а дизельные АЗС не обслуживались
        вообще.
        """
        trucks_res = AutoparkStore.list_trucks()
        if not trucks_res.get("success"):
            return trucks_res
        sections_res = SupplyStore.list_sections()
        if not sections_res.get("success"):
            return sections_res
        by_truck: Dict[Any, List[Dict[str, Any]]] = {}
        for sec in sections_res["data"]:
            by_truck.setdefault(sec["truck_id"], []).append(
                {"id": sec["id"], "seq_no": sec["seq_no"],
                 "volume_l": float(sec["volume_l"])})

        warnings: List[str] = []
        trucks: List[Dict[str, Any]] = []
        for t in trucks_res["data"]:
            if not t.get("active"):
                continue
            products = t.get("products") or []
            groups = set()
            if "DIESEL" in products:
                groups.add("DIESEL")
            if any(p != "DIESEL" for p in products):
                groups.add("PETROL")
            if not groups:
                # Продукты не заведены -- считаем, что цистерна возит всё:
                # исключить её из плана молча значило бы потерять машину.
                groups = {"PETROL", "DIESEL"}
                warnings.append(f"Цистерне {t.get('plate')} не заданы разрешённые "
                                "продукты — она доступна для любого топлива")
            sections = by_truck.get(t["id"]) or []
            if not sections:
                warnings.append(f"У цистерны {t.get('plate')} не заведены отсеки — "
                                "в планирование она не попадёт")
                continue
            trucks.append({"id": t["id"], "plate": t.get("plate"),
                           "fuel_groups": sorted(groups), "sections": sections})
        return _done({"trucks": trucks, "warnings": warnings})

    @staticmethod
    def plan_build(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        """Расчёт плана распределения (ТЗ п.3 — п.7) и его сохранение."""
        settings_res = SupplyStore.supply_settings()
        if not settings_res.get("success"):
            return settings_res
        settings = dict(settings_res["data"])

        try:
            override = {
                "max_cover_days": _as_float(payload.get("max_cover_days"), "Запас, дней"),
                "plan_horizon_days": _as_float(payload.get("horizon_days"), "Горизонт"),
                "group_max_stations": _as_int(payload.get("group_max_stations"),
                                              "АЗС в рейсе"),
            }
        except ValueError as exc:
            return _fail(str(exc))
        settings.update({k: v for k, v in override.items() if v is not None})

        tanks_res = SupplyStore.tank_state()
        if not tanks_res.get("success"):
            return tanks_res
        tanks = tanks_res["data"]
        if not tanks:
            return _fail("Не заведён ни один резервуар АЗС")

        catalog = SupplyController._truck_catalog()
        if not catalog.get("success"):
            return catalog
        trucks = catalog["data"]["trucks"]
        warnings = list(catalog["data"]["warnings"])
        if not trucks:
            return _fail("Нет ни одной цистерны с заведёнными отсеками — "
                         "планировать нечем")

        groups_res = SupplyStore.list_groups()
        groups = [g for g in (groups_res.get("data") or []) if g.get("active")]

        load_points_res = AutoparkStore.list_load_points()
        if not load_points_res.get("success"):
            return load_points_res
        load_point_id = payload.get("load_point_id")
        if load_point_id is None:
            domestic = [p for p in load_points_res["data"] if not p.get("is_foreign")]
            if not domestic:
                return _fail("Не заведён ни один внутренний пункт загрузки")
            load_point_id = domestic[0]["id"]
        settings["load_point_id"] = load_point_id

        dist_lookup = AutoparkStore.distance_lookup_fn()
        plan = rules.build_plan(tanks, trucks, groups, settings, dist_lookup)

        if not plan["needs"]:
            return _done({"plan_id": None, "needs": [], "trips": [],
                          "warnings": warnings},
                         "Потребности нет: на всех АЗС запаса хватает")

        saved = SupplyStore.save_plan(plan, settings, username)
        if not saved.get("success"):
            return saved
        AutoparkStore.log_event("SUPPLY_PLAN", "PLAN", saved["data"]["plan_id"],
                                f"needs={len(plan['needs'])} trips={len(plan['trips'])}",
                                username)
        return _done({"plan_id": saved["data"]["plan_id"],
                      "needs": plan["needs"], "trips": plan["trips"],
                      "warnings": warnings},
                     f"План {saved['data']['plan_id']}: потребностей "
                     f"{len(plan['needs'])}, рейсов {len(plan['trips'])}")

    @staticmethod
    def plans_list(limit: Any = 20) -> Dict[str, Any]:
        try:
            limit = _as_int(limit, "Количество") or 20
        except ValueError as exc:
            return _fail(str(exc))
        return SupplyStore.list_plans(min(limit, 100))

    @staticmethod
    def plan_get(plan_id: Any) -> Dict[str, Any]:
        try:
            plan_id = _as_int(plan_id, "План")
        except ValueError as exc:
            return _fail(str(exc))
        if plan_id is None:
            return _fail("Не указан план")
        return SupplyStore.get_plan(plan_id)

    # ── ручная правка и перепроверка (ТЗ п.7) ───────────────────────

    @staticmethod
    def plan_validate(plan_id: Any) -> Dict[str, Any]:
        """Перепроверка ограничений после ручного изменения плана.

        ТЗ требует ровно двух проверок: недопустимость перелива резервуара
        и физическая возможность распределить объём по отсекам. Ошибка
        блокирует утверждение, предупреждение только подсвечивается.
        """
        try:
            plan_id = _as_int(plan_id, "План")
        except ValueError as exc:
            return _fail(str(exc))
        ctx = SupplyStore.plan_context(plan_id)
        if not ctx.get("success"):
            return ctx
        loads = ctx["data"]["loads"]
        sections = {s["id"]: {"volume_l": float(s["volume_l"]),
                              "seq_no": s["seq_no"], "truck_id": s["truck_id"]}
                    for s in ctx["data"]["sections"]}
        # ALLOWED_L во view уже вычтено «в пути», а сохранённый план как
        # раз и есть часть этого «в пути» после утверждения. До утверждения
        # он в ALLOWED_L не входит, поэтому сравниваем как есть.
        tanks = {(t["station_id"], t["product_code"]):
                 {"allowed_l": float(t["allowed_l"] or 0)}
                 for t in ctx["data"]["tanks"]}

        problems: List[Dict[str, Any]] = []
        by_trip: Dict[Any, List[Dict[str, Any]]] = {}
        for load in loads:
            by_trip.setdefault(load["supply_trip_id"], []).append(load)
        for trip_loads in by_trip.values():
            problems.extend(rules.validate_loads(trip_loads, tanks, sections))
        # Перелив считается по всему плану, а не по одному рейсу: две
        # машины к одной АЗС переливают её так же, как одна.
        problems.extend([p for p in rules.validate_loads(loads, tanks, sections)
                         if p["code"] == "overfill"])

        seen = set()
        unique: List[Dict[str, Any]] = []
        for p in problems:
            key = (p["code"], p.get("row"), p["message"])
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        errors = [p for p in unique if p["level"] == "error"]
        return _done({"problems": unique, "errors": len(errors),
                      "warnings": len(unique) - len(errors),
                      "can_confirm": not errors})

    @staticmethod
    def load_update(load_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            load_id = _as_int(load_id, "Строка плана")
            volume = _as_float(payload.get("volume_l"), "Объём")
        except ValueError as exc:
            return _fail(str(exc))
        if load_id is None:
            return _fail("Не указана строка плана")
        if volume is None or volume <= 0:
            return _fail("Объём должен быть больше нуля")
        saved = SupplyStore.update_load(load_id, volume)
        if not saved.get("success"):
            return saved
        plan_id = payload.get("plan_id")
        if plan_id:
            check = SupplyController.plan_validate(plan_id)
            if check.get("success"):
                saved["data"]["validation"] = check["data"]
        return saved

    @staticmethod
    def load_delete(load_id: Any) -> Dict[str, Any]:
        try:
            load_id = _as_int(load_id, "Строка плана")
        except ValueError as exc:
            return _fail(str(exc))
        return SupplyStore.delete_load(load_id)

    # ── утверждение плана -> рейсы (ТЗ п.9) ─────────────────────────

    @staticmethod
    def plan_confirm(plan_id: Any, payload: Dict[str, Any], username: str
                     ) -> Dict[str, Any]:
        """Превращает утверждённый план в рейсы со статусом «запланировано».

        Водитель выбирается вручную (ТЗ автопарка: «оставить место занести
        водителя вручную»), стоянка — точка старта и финиша норматива.
        """
        try:
            plan_id = _as_int(plan_id, "План")
            start_point_id = _as_int(payload.get("start_point_id"), "Стоянка")
            end_point_id = _as_int(payload.get("end_point_id"), "Конечный пункт")
        except ValueError as exc:
            return _fail(str(exc))
        if plan_id is None:
            return _fail("Не указан план")

        drivers_raw = payload.get("drivers") or {}
        if not isinstance(drivers_raw, dict) or not drivers_raw:
            return _fail("Не выбран водитель ни для одной цистерны")
        try:
            driver_by_truck = {int(k): int(v) for k, v in drivers_raw.items()}
        except (TypeError, ValueError):
            return _fail("Список водителей должен быть вида {цистерна: водитель}")

        check = SupplyController.plan_validate(plan_id)
        if not check.get("success"):
            return check
        if not check["data"]["can_confirm"]:
            return _fail("План нарушает ограничения — исправьте ошибки перед "
                         "утверждением")

        plan = SupplyStore.get_plan(plan_id)
        if not plan.get("success"):
            return plan

        if end_point_id is None or start_point_id is None:
            points = AutoparkStore.list_end_points()
            if points.get("success") and points["data"]:
                default_point = points["data"][0]["id"]
                start_point_id = start_point_id or default_point
                end_point_id = end_point_id or default_point

        dist_lookup = AutoparkStore.distance_lookup_fn()
        norm_km: Dict[int, Optional[float]] = {}
        missing: List[str] = []
        for trip in plan["data"]["trips"]:
            stations = list(dict.fromkeys(l["station_id"] for l in trip["loads"]))
            km, legs = rules.route_km(start_point_id, trip["load_point_id"],
                                      stations, end_point_id, dist_lookup)
            norm_km[trip["id"]] = km
            if km is None:
                gaps = [f"{l['from_kind']}:{l['from_id']} → {l['to_kind']}:{l['to_id']}"
                        for l in legs if l["km"] is None]
                missing.append(f"рейс {trip['seq_no']} ({trip.get('plate')}): "
                               + ", ".join(gaps))

        created = SupplyStore.confirm_plan(plan_id, driver_by_truck, end_point_id,
                                           start_point_id, norm_km, username)
        if not created.get("success"):
            return created
        AutoparkStore.log_event("SUPPLY_CONFIRM", "PLAN", plan_id,
                                f"trips={len(created['data']['trips'])}", username)
        message = f"Создано рейсов: {len(created['data']['trips'])}"
        if missing:
            # Норматив не посчитан -- рейс создан, но зарплата по нему не
            # начислится, пока не заполнена матрица расстояний. Молчать об
            # этом нельзя: водитель узнает о недоплате позже всех.
            message += ". Нет расстояний в матрице: " + "; ".join(missing)
        return _done(created["data"], message)

    # ── исполнение (ТЗ п.9) ─────────────────────────────────────────

    @staticmethod
    def trip_status(trip_id: Any, payload: Dict[str, Any], username: str
                    ) -> Dict[str, Any]:
        try:
            trip_id = _as_int(trip_id, "Рейс")
        except ValueError as exc:
            return _fail(str(exc))
        status = (payload.get("status_code") or "").strip().upper()
        if not status:
            return _fail("Не указан статус")
        res = SupplyStore.set_trip_status(trip_id, status)
        if res.get("success"):
            AutoparkStore.log_event("TRIP_STATUS", "TRIP", trip_id,
                                    f"{res['data'].get('previous')} -> {status}",
                                    username)
        return res

    @staticmethod
    def item_fact(item_id: Any, payload: Dict[str, Any], username: str
                  ) -> Dict[str, Any]:
        try:
            item_id = _as_int(item_id, "Позиция")
            data = {"loaded_l": _as_float(payload.get("loaded_l"), "Загружено"),
                    "doc_l": _as_float(payload.get("doc_l"), "По документу"),
                    "accepted_l": _as_float(payload.get("accepted_l"), "Принято АЗС")}
        except ValueError as exc:
            return _fail(str(exc))
        if item_id is None:
            return _fail("Не указана позиция")
        if all(v is None for v in data.values()):
            return _fail("Нечего сохранять: не заполнен ни один объём")
        for label, value in data.items():
            if value is not None and value < 0:
                return _fail("Объём не может быть отрицательным")
        res = SupplyStore.set_item_fact(item_id, data)
        if res.get("success"):
            AutoparkStore.log_event("TRIP_ITEM_FACT", "ITEM", item_id,
                                    str(data), username)
        return res

    @staticmethod
    def execution(args) -> Dict[str, Any]:
        try:
            date_from = _as_date(args.get("date_from"), "date_from")
            date_to = _as_date(args.get("date_to"), "date_to")
        except ValueError as exc:
            return _fail(str(exc))
        only_diff = str(args.get("only_discrepancies") or "").lower() in ("1", "true", "yes")
        return SupplyStore.execution_report(date_from, date_to, only_diff)

    # ── настройки контура ───────────────────────────────────────────

    @staticmethod
    def settings_get() -> Dict[str, Any]:
        return SupplyStore.supply_settings()

    @staticmethod
    def settings_update(payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            data = {
                "max_cover_days": _as_float(payload.get("max_cover_days"), "Запас, дней"),
                "plan_horizon_days": _as_int(payload.get("plan_horizon_days"), "Горизонт"),
                "group_min_stations": _as_int(payload.get("group_min_stations"), "АЗС минимум"),
                "group_max_stations": _as_int(payload.get("group_max_stations"), "АЗС максимум"),
                "volume_diff_pct": _as_float(payload.get("volume_diff_pct"), "Порог расхождения"),
            }
        except ValueError as exc:
            return _fail(str(exc))
        if data["max_cover_days"] is not None and data["max_cover_days"] <= 0:
            return _fail("Допустимый запас в днях должен быть больше нуля")
        if (data["group_min_stations"] is not None
                and data["group_max_stations"] is not None
                and data["group_min_stations"] > data["group_max_stations"]):
            return _fail("Минимум АЗС в рейсе не может быть больше максимума")
        return SupplyStore.update_supply_settings(data)


    # ── отчёт для руководства (ТЗ автопарка) ────────────────────────

    @staticmethod
    def management(args) -> Dict[str, Any]:
        """Экономика перевозки и рейтинг водителей за период.

        Отвечает на вопросы «Отчёта для руководства» второго ТЗ:
        пробег по автомобилям, стоимость перевозки литра, средняя
        загрузка бензовозов, перерасход топлива, число выявленных
        отклонений и экономический эффект от оптимизации маршрутов.
        """
        try:
            date_from = _as_date(args.get("date_from"), "date_from")
            date_to = _as_date(args.get("date_to"), "date_to")
        except ValueError as exc:
            return _fail(str(exc))

        trips_res = SupplyStore.trips_economics(date_from, date_to)
        if not trips_res.get("success"):
            return trips_res
        settings_res = SupplyStore.supply_settings()
        if not settings_res.get("success"):
            return settings_res
        settings = settings_res["data"]

        price_res = SupplyStore.diesel_price(date_to)
        price_row = price_res.get("data") or {}
        fuel_price = float(price_row.get("price_lei") or 0)

        base_settings = AutoparkStore.get_settings()
        km_limit = float((base_settings.get("data") or {}).get("km_deviation_limit") or 0)

        economics = rules.transport_economics(
            trips_res["data"], float(settings.get("rate_per_km") or 0),
            fuel_price, km_limit)
        economics["fuel_price_lei"] = fuel_price or None
        economics["rate_per_km"] = float(settings.get("rate_per_km") or 0)

        drivers_res = AutoparkStore.driver_summary(date_from, date_to)
        rating = rules.driver_rating(drivers_res.get("data") or [])

        trucks_res = AutoparkStore.truck_summary(date_from, date_to)
        return _done({"economics": economics, "drivers": rating,
                      "trucks": trucks_res.get("data") or []})

"""Autopark — контроллер настроек по периодам (админка заказчика).

Задача слоя: не пустить в базу настройку, которая сделает расчёт
неоднозначным или физически невыполнимым. Проверок три вида:

1. **Формат** — числа числами, даты датами;
2. **Период** — нет пересечений по одному объекту (`periods.validate_period`);
3. **Смысл** — сумма отсеков не больше цистерны, минимальный остаток не
   больше допустимого залива, размер группы в разумных границах.

Третий вид важнее первых двух: перекрытие периодов ломает отчёт, а
минимальный остаток выше допустимого залива ломает планирование — такая
АЗС будет вечно «ниже минимума» и вечно «нет свободного объёма».
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from modules.autopark import periods as per
from modules.autopark.periods_store import PeriodsStore, SPECS
from modules.autopark.store import AutoparkStore

KINDS = tuple(SPECS)


def _fail(message: str) -> Dict[str, Any]:
    return {"success": False, "data": None, "message": message}


def _done(data: Any = None, message: str = "") -> Dict[str, Any]:
    return {"success": True, "data": data, "message": message}


def _as_date(raw: Any, label: str, required: bool = True) -> Optional[date]:
    if raw in (None, ""):
        if required:
            raise ValueError(f"{label}: не указана дата")
        return None
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается дата в формате ГГГГ-ММ-ДД")


def _as_float(raw: Any, label: str) -> Optional[float]:
    if raw in (None, ""):
        return None
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается число")


def _as_int(raw: Any, label: str) -> Optional[int]:
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{label}: ожидается целое число")


class PeriodsController:
    """CRUD настроек, действующих в периоде."""

    @staticmethod
    def list(kind: str, owner_id: Any = None) -> Dict[str, Any]:
        if kind not in KINDS:
            return _fail(f"Неизвестный вид настройки: {kind}")
        try:
            owner_id = _as_int(owner_id, "Объект")
        except ValueError as exc:
            return _fail(str(exc))
        res = PeriodsStore.list(kind, owner_id)
        if res.get("success"):
            for row in res["data"]:
                row["period_label"] = per.describe(row)
        return res

    @staticmethod
    def save(kind: str, payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        if kind not in KINDS:
            return _fail(f"Неизвестный вид настройки: {kind}")
        try:
            valid_from = _as_date(payload.get("valid_from"), "Действует с")
            valid_to = _as_date(payload.get("valid_to"), "Действует по", required=False)
        except ValueError as exc:
            return _fail(str(exc))

        data: Dict[str, Any] = {"id": _as_int(payload.get("id"), "Период"),
                                "valid_from": valid_from, "valid_to": valid_to}
        try:
            if kind == "rates":
                data["rate_per_km"] = _as_float(payload.get("rate_per_km"), "Ставка за км")
                data["trip_bonus"] = _as_float(payload.get("trip_bonus"), "Доплата за рейс") or 0
                data["note"] = (payload.get("note") or None)
                if data["rate_per_km"] is None or data["rate_per_km"] < 0:
                    return _fail("Ставка за километр должна быть неотрицательным числом")
            elif kind == "params":
                data["max_cover_days"] = _as_float(payload.get("max_cover_days"), "Запас, дней")
                data["plan_horizon_days"] = _as_int(payload.get("plan_horizon_days"), "Горизонт")
                data["group_min_stations"] = _as_int(payload.get("group_min_stations"), "АЗС минимум")
                data["group_max_stations"] = _as_int(payload.get("group_max_stations"), "АЗС максимум")
                data["volume_diff_pct"] = _as_float(payload.get("volume_diff_pct"), "Порог расхождения")
                data["note"] = (payload.get("note") or None)
                if not data["max_cover_days"] or data["max_cover_days"] <= 0:
                    return _fail("Допустимый запас в днях должен быть больше нуля")
                if (data["group_min_stations"] or 0) > (data["group_max_stations"] or 0):
                    return _fail("Минимум АЗС в рейсе не может быть больше максимума")
            else:  # tank_limits
                data["tank_id"] = _as_int(payload.get("tank_id"), "Резервуар")
                data["min_stock_l"] = _as_float(payload.get("min_stock_l"), "Минимальный остаток")
                data["max_fill_l"] = _as_float(payload.get("max_fill_l"), "Допустимый залив")
                data["max_cover_days"] = _as_float(payload.get("max_cover_days"), "Запас, дней")
                data["note"] = (payload.get("note") or None)
                if data["tank_id"] is None:
                    return _fail("Не указан резервуар")
                check = PeriodsController._check_tank_limits(data)
                if check:
                    return _fail(check)
        except ValueError as exc:
            return _fail(str(exc))

        owner_id = data.get("tank_id")
        existing = PeriodsStore.list(kind, owner_id)
        if not existing.get("success"):
            return existing

        # Порядок здесь принципиален. Сначала вычисляем, какие открытые
        # периоды новый закроет, и проверяем пересечения УЖЕ С УЧЁТОМ
        # этого закрытия. Наоборот не работает: «с 1 октября ставка 4
        # лея» всегда пересекается с бессрочным сентябрьским периодом,
        # и первая версия честно отклоняла ровно тот сценарий, ради
        # которого всё это написано.
        closing = (per.close_open_period(existing["data"], valid_from)
                   if not data.get("id") else [])
        closed_ids = {c["id"]: c["valid_to"] for c in closing}
        adjusted = [dict(row, valid_to=closed_ids.get(row.get("id"), row.get("valid_to")))
                    for row in existing["data"]]
        errors = per.validate_period(data, adjusted)
        if errors:
            return _fail(errors[0])
        res = PeriodsStore.save(kind, data, username, closing)
        if res.get("success"):
            AutoparkStore.log_event("PERIOD_SAVE", kind.upper(), res["data"]["id"],
                                    per.describe(data), username)
            if closing:
                res["message"] = ("Сохранено. Предыдущий период закрыт "
                                  f"{closing[0]['valid_to']:%d.%m.%Y}")
        return res

    @staticmethod
    def _check_tank_limits(data: Dict[str, Any]) -> Optional[str]:
        """Смысловые проверки лимитов резервуара."""
        tanks = AutoparkStore.list_stations()
        capacity = None
        if tanks.get("success"):
            for st in tanks["data"]:
                for tank in st.get("tanks", []):
                    if tank.get("id") == data["tank_id"]:
                        capacity = float(tank.get("capacity_l") or 0)
        if capacity and data.get("max_fill_l") and data["max_fill_l"] > capacity:
            return (f"Допустимый залив {data['max_fill_l']:.0f} л больше "
                    f"паспортной вместимости резервуара {capacity:.0f} л")
        if (data.get("min_stock_l") is not None and data.get("max_fill_l") is not None
                and data["min_stock_l"] >= data["max_fill_l"]):
            return ("Минимальный остаток не может быть больше допустимого залива — "
                    "такая АЗС навсегда останется «ниже минимума»")
        for key, label in (("min_stock_l", "Минимальный остаток"),
                           ("max_fill_l", "Допустимый залив"),
                           ("max_cover_days", "Запас, дней")):
            value = data.get(key)
            if value is not None and value < 0:
                return f"{label}: значение не может быть отрицательным"
        return None

    @staticmethod
    def delete(kind: str, row_id: Any, username: str) -> Dict[str, Any]:
        if kind not in KINDS:
            return _fail(f"Неизвестный вид настройки: {kind}")
        try:
            row_id = _as_int(row_id, "Период")
        except ValueError as exc:
            return _fail(str(exc))
        res = PeriodsStore.delete(kind, row_id)
        if res.get("success"):
            AutoparkStore.log_event("PERIOD_DELETE", kind.upper(), row_id, "", username)
        return res

    # ── отсеки цистерн ──────────────────────────────────────────────

    @staticmethod
    def sections(truck_id: Any = None) -> Dict[str, Any]:
        try:
            truck_id = _as_int(truck_id, "Цистерна")
        except ValueError as exc:
            return _fail(str(exc))
        res = PeriodsStore.sections(truck_id)
        if res.get("success"):
            for row in res["data"]:
                row["period_label"] = per.describe(row)
        return res

    @staticmethod
    def save_sections(payload: Dict[str, Any], username: str) -> Dict[str, Any]:
        try:
            truck_id = _as_int(payload.get("truck_id"), "Цистерна")
            valid_from = _as_date(payload.get("valid_from"), "Действует с", required=False)
            valid_to = _as_date(payload.get("valid_to"), "Действует по", required=False)
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
        res = PeriodsStore.save_sections(truck_id, sections, valid_from, valid_to)
        if res.get("success"):
            AutoparkStore.log_event("SECTIONS_SAVE", "TRUCK", truck_id,
                                    f"{len(sections)} отсеков, "
                                    + per.describe({"valid_from": valid_from,
                                                    "valid_to": valid_to}), username)
            if valid_from:
                res["message"] = ("Новая конфигурация отсеков действует "
                                  + per.describe({"valid_from": valid_from,
                                                  "valid_to": valid_to})
                                  + ". Прежняя сохранена в истории")
        return res

    # ── группы АЗС ──────────────────────────────────────────────────

    @staticmethod
    def groups() -> Dict[str, Any]:
        res = PeriodsStore.groups()
        if res.get("success"):
            for g in res["data"]:
                for item in g.get("items", []):
                    item["period_label"] = per.describe(item)
        return res

    @staticmethod
    def save_group_period(group_id: Any, payload: Dict[str, Any],
                          username: str) -> Dict[str, Any]:
        try:
            group_id = _as_int(group_id, "Группа")
            valid_from = _as_date(payload.get("valid_from"), "Действует с", required=False)
            valid_to = _as_date(payload.get("valid_to"), "Действует по", required=False)
            station_ids = [_as_int(s, "АЗС") for s in (payload.get("station_ids") or [])]
        except ValueError as exc:
            return _fail(str(exc))
        if group_id is None:
            return _fail("Не указана группа")
        if not station_ids:
            return _fail("В группе должна быть хотя бы одна АЗС")

        params = PeriodsStore.effective_params(valid_from or date.today())
        limits = (params.get("data") or {}).get("params") or {}
        max_stations = int(limits.get("group_max_stations") or 4)
        if len(station_ids) > max_stations * 2:
            # Группа -- это география, а не весь список сети: рейс всё
            # равно обслужит не больше group_max_stations АЗС, но запас
            # на выбор нужен, поэтому предел мягкий, а не равен максимуму.
            return _fail(f"В группе {len(station_ids)} АЗС при максимуме "
                         f"{max_stations} в рейсе — это не география, а весь список")
        res = PeriodsStore.save_group_period(group_id, station_ids, valid_from, valid_to)
        if res.get("success"):
            AutoparkStore.log_event("GROUP_PERIOD", "GROUP", group_id,
                                    f"{len(station_ids)} АЗС, "
                                    + per.describe({"valid_from": valid_from,
                                                    "valid_to": valid_to}), username)
        return res

    # ── что действует на дату ───────────────────────────────────────

    @staticmethod
    def effective(args) -> Dict[str, Any]:
        try:
            on_date = _as_date(args.get("date"), "Дата", required=False) or date.today()
        except ValueError as exc:
            return _fail(str(exc))
        res = PeriodsStore.effective_params(on_date)
        if res.get("success"):
            res["data"]["date"] = on_date.isoformat()
            for key in ("params", "rate"):
                if res["data"].get(key):
                    res["data"][key]["period_label"] = per.describe(res["data"][key])
        return res

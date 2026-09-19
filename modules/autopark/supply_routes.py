"""Autopark — HTTP-маршруты контура распределения топлива (ТЗ 18.09.2026).

Отдельный файл от `routes.py` по правилу №2 проекта: свой код — в свой
файл, в общем остаётся одна строка импорта. Адреса без префикса
`/UNA.md/orasldev/autopark` — его подставляет ядро при регистрации
blueprint'а.

Всё закрыто входом: это данные логиста и бухгалтера, а не публичный
справочник. Исключение по смыслу — приём остатков из Petrol Expert
(`/api/supply/stock`): туда ходит не человек, а внешняя система, но
и она ходит с сессией, потому что отдельного контура токенов у модуля
пока нет — это осознанное ограничение первой очереди, а не недосмотр.
"""
from flask import jsonify, request, session

from controllers.auth_controller import AuthController
from modules.autopark import blueprint
from modules.autopark.supply_controller import SupplyController


def _username() -> str:
    return session.get("username") or "anonim"


def _guard():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется авторизация"}), 401
    return None


# ── состояние резервуаров и справочники контура ──────────────────────

@blueprint.route("/api/supply/tanks", methods=["GET"])
def api_supply_tanks():
    return _guard() or jsonify(SupplyController.tank_state())


@blueprint.route("/api/supply/tanks/<int:tank_id>", methods=["POST"])
def api_supply_tank_save(tank_id):
    return _guard() or jsonify(
        SupplyController.tank_limits_save(tank_id, request.get_json(silent=True) or {}))


@blueprint.route("/api/supply/stock", methods=["POST"])
def api_supply_stock():
    """Приём фактических остатков (Petrol Expert, ТЗ п.2)."""
    return _guard() or jsonify(
        SupplyController.stock_push(request.get_json(silent=True) or {}))


@blueprint.route("/api/supply/sections", methods=["GET"])
def api_supply_sections():
    return _guard() or jsonify(
        SupplyController.sections_list(request.args.get("truck_id")))


@blueprint.route("/api/supply/sections", methods=["POST"])
def api_supply_sections_save():
    return _guard() or jsonify(
        SupplyController.sections_save(request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/supply/groups", methods=["GET"])
def api_supply_groups():
    return _guard() or jsonify(SupplyController.groups_list())


@blueprint.route("/api/supply/groups", methods=["POST"])
def api_supply_group_save():
    return _guard() or jsonify(
        SupplyController.group_save(request.get_json(silent=True) or {}))


# ── план распределения ───────────────────────────────────────────────

@blueprint.route("/api/supply/plan", methods=["POST"])
def api_supply_plan_build():
    return _guard() or jsonify(
        SupplyController.plan_build(request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/supply/plans", methods=["GET"])
def api_supply_plans():
    return _guard() or jsonify(SupplyController.plans_list(request.args.get("limit")))


@blueprint.route("/api/supply/plans/<int:plan_id>", methods=["GET"])
def api_supply_plan_get(plan_id):
    return _guard() or jsonify(SupplyController.plan_get(plan_id))


@blueprint.route("/api/supply/plans/<int:plan_id>/validate", methods=["GET"])
def api_supply_plan_validate(plan_id):
    return _guard() or jsonify(SupplyController.plan_validate(plan_id))


@blueprint.route("/api/supply/plans/<int:plan_id>/confirm", methods=["POST"])
def api_supply_plan_confirm(plan_id):
    return _guard() or jsonify(SupplyController.plan_confirm(
        plan_id, request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/supply/loads/<int:load_id>", methods=["POST"])
def api_supply_load_update(load_id):
    return _guard() or jsonify(
        SupplyController.load_update(load_id, request.get_json(silent=True) or {}))


@blueprint.route("/api/supply/loads/<int:load_id>/delete", methods=["POST"])
def api_supply_load_delete(load_id):
    return _guard() or jsonify(SupplyController.load_delete(load_id))


# ── исполнение поставки ──────────────────────────────────────────────

@blueprint.route("/api/supply/trips/<int:trip_id>/status", methods=["POST"])
def api_supply_trip_status(trip_id):
    return _guard() or jsonify(SupplyController.trip_status(
        trip_id, request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/supply/items/<int:item_id>/fact", methods=["POST"])
def api_supply_item_fact(item_id):
    return _guard() or jsonify(SupplyController.item_fact(
        item_id, request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/supply/execution", methods=["GET"])
def api_supply_execution():
    return _guard() or jsonify(SupplyController.execution(request.args))


# ── настройки контура ────────────────────────────────────────────────

@blueprint.route("/api/supply/settings", methods=["GET"])
def api_supply_settings():
    return _guard() or jsonify(SupplyController.settings_get())


@blueprint.route("/api/supply/settings", methods=["POST"])
def api_supply_settings_save():
    return _guard() or jsonify(
        SupplyController.settings_update(request.get_json(silent=True) or {}))


@blueprint.route("/api/supply/management", methods=["GET"])
def api_supply_management():
    """Отчёт для руководства: экономика перевозки и рейтинг водителей."""
    return _guard() or jsonify(SupplyController.management(request.args))


# ── настройки по периодам (админка заказчика) ────────────────────────
#
# Всё, что ТЗ оставляло «на потом» — минимальный остаток, допустимый
# залив, потолок запаса в днях, ставка водителя, отсеки цистерн, состав
# групп АЗС — заказчик правит здесь сам, и правит НА ПЕРИОД.

from modules.autopark.periods_controller import PeriodsController  # noqa: E402


@blueprint.route("/api/periods/<kind>", methods=["GET"])
def api_periods_list(kind):
    return _guard() or jsonify(
        PeriodsController.list(kind, request.args.get("owner_id")))


@blueprint.route("/api/periods/<kind>", methods=["POST"])
def api_periods_save(kind):
    return _guard() or jsonify(
        PeriodsController.save(kind, request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/periods/<kind>/<int:row_id>/delete", methods=["POST"])
def api_periods_delete(kind, row_id):
    return _guard() or jsonify(PeriodsController.delete(kind, row_id, _username()))


@blueprint.route("/api/periods-effective", methods=["GET"])
def api_periods_effective():
    """Что действует на дату — ставка и параметры планирования."""
    return _guard() or jsonify(PeriodsController.effective(request.args))


@blueprint.route("/api/sections-periods", methods=["GET"])
def api_sections_periods():
    return _guard() or jsonify(PeriodsController.sections(request.args.get("truck_id")))


@blueprint.route("/api/sections-periods", methods=["POST"])
def api_sections_periods_save():
    return _guard() or jsonify(
        PeriodsController.save_sections(request.get_json(silent=True) or {}, _username()))


@blueprint.route("/api/group-periods", methods=["GET"])
def api_group_periods():
    return _guard() or jsonify(PeriodsController.groups())


@blueprint.route("/api/group-periods/<int:group_id>", methods=["POST"])
def api_group_period_save(group_id):
    return _guard() or jsonify(PeriodsController.save_group_period(
        group_id, request.get_json(silent=True) or {}, _username()))


# ── сводка первого лица ──────────────────────────────────────────────

from datetime import date, datetime, timedelta  # noqa: E402

from modules.autopark import board as board_view  # noqa: E402


@blueprint.route("/api/board", methods=["GET"])
def api_board():
    """Три ответа руководителю: сеть, деньги, эффект автоматизации."""
    guard = _guard()
    if guard:
        return guard

    def _date(raw, default):
        if not raw:
            return default
        try:
            return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
        except ValueError:
            return default

    date_to = _date(request.args.get("date_to"), date.today())
    date_from = _date(request.args.get("date_from"), date_to - timedelta(days=30))
    return jsonify(board_view.build(date_from, date_to))

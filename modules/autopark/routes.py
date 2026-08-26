"""Маршруты модуля Autopark.

Адреса здесь записаны БЕЗ префикса `/UNA.md/orasldev/autopark` — его
подставляет ядро при регистрации blueprint'а (см. modules/sda/routes.py
для образца того же приёма).

Страница '' / '/' — консоль модуля, закрыта входом (как modules/sda
'/console'). Весь /api/... — тоже за входом: это данные логиста/бухгалтера
по зарплате и рейсам, не публичный справочник.
"""
from flask import jsonify, redirect, render_template, request, session, url_for

from controllers.auth_controller import AuthController
from modules.autopark import blueprint
from modules.autopark.controller import AutoparkController


def _username() -> str:
    return session.get("username") or "anonim"


def _unauthorized():
    return jsonify({"success": False, "message": "Требуется авторизация"}), 401


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    return render_template("autopark.html", page_title="Autopark — автопарк бензовозов")


# ── справочники ──────────────────────────────────────────────────────

@blueprint.route("/api/refs", methods=["GET"])
def api_refs():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.refs())


@blueprint.route("/api/station", methods=["POST"])
def api_station_save():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.station_upsert(request.get_json(silent=True) or {}))


@blueprint.route("/api/truck", methods=["POST"])
def api_truck_save():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.truck_upsert(request.get_json(silent=True) or {}))


@blueprint.route("/api/driver", methods=["POST"])
def api_driver_save():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.driver_upsert(request.get_json(silent=True) or {}))


# ── матрица расстояний ───────────────────────────────────────────────

@blueprint.route("/api/distance", methods=["GET"])
def api_distance_list():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.distance_list())


@blueprint.route("/api/distance", methods=["POST"])
def api_distance_set():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.distance_set(request.get_json(silent=True) or {}))


# ── настройки ────────────────────────────────────────────────────────

@blueprint.route("/api/settings", methods=["GET"])
def api_settings_get():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.settings_get())


@blueprint.route("/api/settings", methods=["POST"])
def api_settings_update():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.settings_update(request.get_json(silent=True) or {}))


# ── поставки ─────────────────────────────────────────────────────────

@blueprint.route("/api/delivery", methods=["GET"])
def api_delivery_list():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.delivery_list(request.args))


@blueprint.route("/api/delivery", methods=["POST"])
def api_delivery_add():
    if not AuthController.is_authenticated():
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    payload["_username"] = _username()
    return jsonify(AutoparkController.delivery_add(payload))


# ── рейсы ────────────────────────────────────────────────────────────

@blueprint.route("/api/trips", methods=["GET"])
def api_trips_list():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.trip_list(request.args))


@blueprint.route("/api/trip", methods=["POST"])
def api_trip_create():
    if not AuthController.is_authenticated():
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    payload["_username"] = _username()
    return jsonify(AutoparkController.trip_create_manual(payload))


@blueprint.route("/api/trip/autoform", methods=["POST"])
def api_trip_autoform():
    if not AuthController.is_authenticated():
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    return jsonify(AutoparkController.trip_autoform(
        payload.get("date_from"), payload.get("date_to")))


@blueprint.route("/api/trip/approve", methods=["POST"])
def api_trip_approve():
    if not AuthController.is_authenticated():
        return _unauthorized()
    payload = request.get_json(silent=True) or {}
    return jsonify(AutoparkController.trip_approve(payload, _username()))


@blueprint.route("/api/trip/fact", methods=["POST"])
def api_trip_fact():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.trip_set_fact(request.get_json(silent=True) or {}))


# ── учёт АЗС ─────────────────────────────────────────────────────────

@blueprint.route("/api/stock", methods=["POST"])
def api_stock_upload():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.stock_upload(request.get_json(silent=True) or {}))


# ── планирование поставок ─────────────────────────────────────────────

@blueprint.route("/api/supply-plan", methods=["GET"])
def api_supply_plan():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.supply_plan())


# ── отчёты ───────────────────────────────────────────────────────────

@blueprint.route("/api/report/payroll", methods=["GET"])
def api_report_payroll():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.payroll_report(request.args))


@blueprint.route("/api/report/control", methods=["GET"])
def api_report_control():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.control_report(request.args))


@blueprint.route("/api/report/drivers", methods=["GET"])
def api_report_drivers():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.driver_report(request.args))


@blueprint.route("/api/report/trucks", methods=["GET"])
def api_report_trucks():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.truck_report(request.args))


@blueprint.route("/api/report/stations", methods=["GET"])
def api_report_stations():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.station_report(request.args))


@blueprint.route("/api/report/management", methods=["GET"])
def api_report_management():
    if not AuthController.is_authenticated():
        return _unauthorized()
    return jsonify(AutoparkController.management_report(request.args))

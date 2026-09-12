"""Маршруты модуля Мониторинг офиса: сеть и Telegram.

Адреса БЕЗ префикса /UNA.md/orasldev/netmon — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
from flask import jsonify, redirect, render_template, request, session, url_for

from controllers.auth_controller import AuthController
from modules.netmon import blueprint
from modules.netmon.controller import NetmonController


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход в систему"}), 401


def _reply(reply):
    payload, status = reply
    return jsonify(payload), status


def _int(name, default=None):
    v = request.args.get(name)
    try:
        return int(v) if v else default
    except (TypeError, ValueError):
        return default


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    return render_template("netmon.html")


@blueprint.route("/api/status")
def api_status():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.status())


@blueprint.route("/api/overview")
def api_overview():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.overview())


@blueprint.route("/api/devices")
def api_devices():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.devices(
        kind=request.args.get("kind"),
        only_missing=request.args.get("missing") == "1"))


@blueprint.route("/api/channels")
def api_channels():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.channels())


@blueprint.route("/api/alerts")
def api_alerts():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.alerts(
        limit=_int("limit", 100), channel_id=_int("channel"),
        severity=request.args.get("severity")))


@blueprint.route("/api/sync/channels", methods=["POST"])
def api_sync_channels():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_channels())


@blueprint.route("/api/sync/alerts", methods=["POST"])
def api_sync_alerts():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_alerts(days=_int("days", 30)))


@blueprint.route("/api/sync/devices", methods=["POST"])
def api_sync_devices():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_devices(run_by=session.get("username", "system")))


@blueprint.route("/api/sync/all", methods=["POST"])
def api_sync_all():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_all(run_by=session.get("username", "system")))


@blueprint.route("/api/zabbix")
def api_zabbix():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.zabbix_overview())


@blueprint.route("/api/pve")
def api_pve():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.pve_guests(
        status=request.args.get("status"),
        decision=request.args.get("decision"),
        risk=request.args.get("risk")))


@blueprint.route("/api/pve/<int:vmid>")
def api_pve_guest(vmid):
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.pve_guest(vmid))


@blueprint.route("/api/sync/pve", methods=["POST"])
def api_sync_pve():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_pve())


@blueprint.route("/api/assets")
def api_assets():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.assets())


@blueprint.route("/api/vault")
def api_vault():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.vault())


@blueprint.route("/api/sync/assets", methods=["POST"])
def api_sync_assets():
    if (g := _guard()) is not None:
        return g
    return _reply(NetmonController.sync_assets())

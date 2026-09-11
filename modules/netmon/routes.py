"""Маршруты модуля Мониторинг офиса: сеть и Telegram.

Адреса БЕЗ префикса /UNA.md/orasldev/netmon — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.netmon import blueprint
from modules.netmon.controller import NetmonController


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход в систему"}), 401


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
    payload, status = NetmonController.status()
    return jsonify(payload), status

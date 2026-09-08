"""Маршруты модуля Работа с поставщиками.

Адреса БЕЗ префикса /UNA.md/orasldev/furnizori — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.furnizori import blueprint
from modules.furnizori.controller import FurnizoriController


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход в систему"}), 401


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    return render_template("furnizori.html")


@blueprint.route("/api/status")
def api_status():
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.status()
    return jsonify(payload), status

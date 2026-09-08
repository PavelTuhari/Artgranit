"""Маршруты модуля Работа с поставщиками.

Адреса БЕЗ префикса /UNA.md/orasldev/furnizori — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
from flask import Response, jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.furnizori import blueprint, rules, store
from modules.furnizori.controller import FurnizoriController


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "message": "Требуется вход в систему"}), 401


def _user():
    try:
        return AuthController.get_current_user()
    except Exception:  # noqa: BLE001 — имя пользователя не критично для записи
        return None


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


@blueprint.route("/api/reference")
def api_reference():
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.reference()
    return jsonify(payload), status


# --------------------------------------------------------------- письма

@blueprint.route("/api/letters", methods=["GET"])
def api_letters():
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.letters(request.args.get("status"))
    return jsonify(payload), status


@blueprint.route("/api/letters", methods=["POST"])
def api_letter_create():
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.create(request.get_json(silent=True) or {}, _user())
    return jsonify(payload), status


@blueprint.route("/api/letters/<int:letter_id>", methods=["PATCH"])
def api_letter_update(letter_id):
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.update(letter_id, request.get_json(silent=True) or {})
    return jsonify(payload), status


@blueprint.route("/api/letters/<int:letter_id>", methods=["DELETE"])
def api_letter_delete(letter_id):
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.remove(letter_id)
    return jsonify(payload), status


# ------------------------------------------------------------- вложения

@blueprint.route("/api/letters/<int:letter_id>/files", methods=["GET"])
def api_files(letter_id):
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.files(letter_id)
    return jsonify(payload), status


@blueprint.route("/api/letters/<int:letter_id>/files", methods=["POST"])
def api_file_upload(letter_id):
    if (g := _guard()) is not None:
        return g
    f = request.files.get("file")
    if f is None:
        return jsonify({"success": False, "message": "Файл не передан"}), 400
    payload, status = FurnizoriController.upload(letter_id, f.filename, f.read(), _user())
    return jsonify(payload), status


@blueprint.route("/api/files/<int:file_id>", methods=["DELETE"])
def api_file_delete(file_id):
    if (g := _guard()) is not None:
        return g
    payload, status = FurnizoriController.drop_file(file_id)
    return jsonify(payload), status


@blueprint.route("/api/files/<int:file_id>/download")
def api_file_download(file_id):
    if (g := _guard()) is not None:
        return g
    got = store.read_file(file_id)
    if got is None:
        return jsonify({"success": False, "message": "Файл не найден"}), 404
    name, mime, blob = got
    # attachment + nosniff: файл поставщика никогда не должен исполниться
    # как страница в сессии оператора
    return Response(blob, mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="{rules.safe_filename(name)}"',
        "X-Content-Type-Options": "nosniff",
    })

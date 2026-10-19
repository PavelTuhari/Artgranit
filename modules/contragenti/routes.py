"""Rutele puntii Contragenti — fara prefix; prefixul (…/contragenti) il pune nucleul."""
from __future__ import annotations

from flask import jsonify, redirect, render_template, request, session, url_for

from controllers.auth_controller import AuthController

from modules.contragenti import blueprint
from modules.contragenti.controller import CtgController
from modules.contragenti.store import CtgStore


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "error": "login required"}), 401


def _user() -> str:
    return str(session.get("username") or session.get("user_name") or "")


@blueprint.route("/")
def journal_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=" + url_for("contragenti.journal_page"))
    return render_template("contragenti_journal.html")


@blueprint.route("/api/upsert", methods=["POST"])
def api_upsert():
    """RO: cardul de contraparte (JSON {xml} sau cimpurile) -> una.md, cu dedup si jurnal."""
    err = _guard()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    r = CtgController.upsert(body, username=_user())
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/api/log", methods=["POST"])
def api_log():
    err = _guard()
    if err:
        return err
    r = CtgController.client_event(request.get_json(silent=True) or {}, username=_user())
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/api/events")
def api_events():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": CtgStore.events(
        request.args.get("limit", 100, type=int), request.args.get("idno", ""), request.args.get("page", ""))})


@blueprint.route("/api/find")
def api_find():
    err = _guard()
    if err:
        return err
    ex = CtgStore.find_existing(request.args.get("idno", "").strip(), request.args.get("name", ""))
    return jsonify({"success": True, "data": ex})

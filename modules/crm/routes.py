"""Rutele CRM-ului — FARA prefix; prefixul (…/crm) il pune nucleul.

RO: pagina (o singura aplicatie, stil EspoCRM ca Demo CRM), API-ul JSON al
paginii si punctul de intoarcere al Contragenti (`/contragenti/callback`,
pentru modul `return_to`). Totul cere sesiunea portalului.
EN: page, JSON API and the Contragenti return_to callback.
"""
from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController

from modules.crm import blueprint
from modules.crm.controller import CrmController
from modules.crm.store import CrmStore


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "error": "login required"}), 401


@blueprint.route("/")
def app_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=" + url_for("crm.app_page"))
    return render_template("crm_app.html")


# ── clienti ──────────────────────────────────────────────────────────────
@blueprint.route("/api/clients")
def api_clients():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": CrmStore.list(
        request.args.get("preset", "all"), request.args.get("q", ""),
        request.args.get("limit", 200, type=int))})


@blueprint.route("/api/clients/<int:client_id>")
def api_client(client_id):
    err = _guard()
    if err:
        return err
    c = CrmStore.get(client_id)
    if not c:
        return jsonify({"success": False, "error": "client inexistent"}), 404
    return jsonify({"success": True, "data": c})


@blueprint.route("/api/clients/<int:client_id>", methods=["DELETE"])
def api_client_delete(client_id):
    err = _guard()
    if err:
        return err
    r = CrmStore.delete(client_id)
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/api/clients/<int:client_id>/note", methods=["POST"])
def api_client_note(client_id):
    err = _guard()
    if err:
        return err
    body = request.get_json(silent=True) or {}
    r = CrmStore.set_note(client_id, body.get("note") or "")
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/api/clients/<int:client_id>/events")
def api_client_events(client_id):
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": CrmStore.events(50, client_id)})


# ── import ───────────────────────────────────────────────────────────────
@blueprint.route("/api/import-xml", methods=["POST"])
def api_import_xml():
    """RO: corpul = XML-ul cardului (text) sau JSON {xml, src, refresh}."""
    err = _guard()
    if err:
        return err
    body = request.get_json(silent=True) if request.is_json else None
    if body:
        text, src, refresh = body.get("xml") or "", body.get("src") or "xml", bool(body.get("refresh"))
    else:
        text, src, refresh = request.get_data(as_text=True), request.args.get("src", "xml"), \
            request.args.get("refresh") == "1"
    r = CrmController.import_xml(text, src=src, refresh=refresh)
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/api/pick-url")
def api_pick_url():
    """RO: adresa `/pick` a Contragenti cu `return_to` = callback-ul nostru."""
    err = _guard()
    if err:
        return err
    q = request.args.get("q", "")
    state = request.args.get("state", "")
    ret = url_for("crm.contragenti_callback", _external=True) if request.args.get("return") == "1" else ""
    return jsonify({"success": True, "url": CrmController.pick_url(q, ret, state)})


@blueprint.route("/contragenti/callback")
def contragenti_callback():
    """RO: Contragenti (mod `return_to`) intoarce browserul aici cu
    `status=ok|cancelled|timeout&idno=…&denumire=…`. Adaugam clientul si
    trimitem inapoi in aplicatie cu mesajul pentru linia de jos."""
    if not AuthController.is_authenticated():
        return redirect("/login?next=" + url_for("crm.app_page"))
    r = CrmController.import_query(request.args.to_dict())
    if r.get("success"):
        msg = "%s:%s:%s" % (r.get("result"), r.get("id"), request.args.get("idno", ""))
    else:
        msg = "err:%s" % (r.get("error") or "")
    return redirect(url_for("crm.app_page") + "?cb=" + msg)


@blueprint.route("/launcher/<kind>")
def launcher(kind):
    """RO: scriptul de pornire a Contragenti (py / command / bat), cu limba si
    portul din setari si adresa de revenire in CRM."""
    if not AuthController.is_authenticated():
        return redirect("/login?next=" + url_for("crm.app_page"))
    from datetime import datetime
    from urllib.parse import urlparse
    from flask import Response
    from modules.crm import launcher as L
    if kind not in L.KINDS:
        return jsonify({"success": False, "error": "tip necunoscut"}), 404
    s = CrmStore.settings()
    try:
        port = int(urlparse(s.get("contragenti_url") or "").port or 9393)
    except (TypeError, ValueError):
        port = 9393
    body = L.render(kind, lang=s.get("lang") or "ro", port=port,
                    return_url=url_for("crm.app_page", _external=True),
                    generated=datetime.now().strftime("%d.%m.%Y %H:%M"))
    return Response(body, mimetype=L.KINDS[kind] + "; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=%s" % L.file_name(kind)})


# ── setari, statistici, jurnal ───────────────────────────────────────────
@blueprint.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    err = _guard()
    if err:
        return err
    if request.method == "POST":
        r = CrmStore.set_settings(request.get_json(silent=True) or {})
        if not r.get("success"):
            return jsonify(r), 400
    return jsonify({"success": True, "data": CrmStore.settings()})


@blueprint.route("/api/stats")
def api_stats():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": CrmStore.stats()})


@blueprint.route("/api/events")
def api_events():
    err = _guard()
    if err:
        return err
    return jsonify({"success": True, "data": CrmStore.events(request.args.get("limit", 50, type=int))})

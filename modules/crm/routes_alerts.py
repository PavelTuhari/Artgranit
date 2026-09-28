"""Rutele alertelor Telegram (tranzactii nefinisate si datorii).

RO: fisier separat de `routes_process.py` (regula nr. 2). Acelasi contract:
JSON, erori cu 4xx, chiriasul din sesiune. Tokenul botului nu se intoarce
niciodata catre browser — doar semnalul ca exista.
EN: Telegram alert routes: settings, preview, send now.
"""
from __future__ import annotations

from flask import g, jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController

from modules.crm import alerts as A
from modules.crm import blueprint, notify
from modules.crm.routes_process import err, with_data


@blueprint.route("/alerte/prezentare")
def alerts_deck():
    """RO: prezentarea botului de alerte (slide-uri + capturi reale). Ctrl/Cmd+P = PDF."""
    if not AuthController.is_authenticated():
        return redirect("/login?next=" + url_for("crm.alerts_deck"))
    return render_template("crm_alerts_deck.html")


@blueprint.route("/api/v2/alerts")
@with_data
def api_alerts():
    """RO: previzualizare — tot ce e deschis acum (nu doar ce nu s-a trimis)."""
    cfg = notify.get_cfg(g.crm)
    d = notify.digest(g.crm, cfg, only_new=request.args.get("new") == "1",
                      url=request.url_root.rstrip("/") + "/UNA.md/orasldev/crm/")
    return jsonify({"success": True, "data": {
        "text": d["text"], "money": d["money"], "counts": d["counts"],
        "open": [a.as_dict() for a in d["all"]], "new": len(d["alerts"]),
        # RO: lista (nu dict): jsonify sorteaza cheile si s-ar pierde ordinea dupa gravitate
        "kinds": [{"kind": k, "sev": v["sev"]} for k, v in A.KINDS.items()], "cfg": cfg}})


@blueprint.route("/api/v2/alerts/settings", methods=["GET", "POST"])
@with_data
def api_alerts_settings():
    if request.method == "POST":
        notify.save_cfg(g.crm, request.get_json(silent=True) or {})
    return jsonify({"success": True, "data": notify.get_cfg(g.crm)})


@blueprint.route("/api/v2/alerts/send", methods=["POST"])
@with_data
def api_alerts_send():
    """RO: «Trimite acum» — trimite si daca nu e nimic nou (`force`)."""
    b = request.get_json(silent=True) or {}
    r = notify.send(g.crm, only_new=not b.get("force"), force=bool(b.get("force")),
                    url=request.url_root.rstrip("/") + "/UNA.md/orasldev/crm/")
    if not r.get("success"):
        return err(r.get("error") or "eroare la trimitere", 400)
    return jsonify({"success": True, "data": r})

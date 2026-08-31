"""Rutele modulului e-Factura — trei intrari, o singura logica.

RO: adresele sint FARA prefix (nucleul monteaza totul sub
/UNA.md/orasldev/efactura). Cele trei intrari se deosebesc DOAR prin cine are
voie sa le cheme:

  * `/admin/...`  — operatorul portalului (sesiunea de back-office);
  * `/my/...`     — clientul din cabinetul site-ului, DOAR documentele lui;
  * `/api/...`    — masina-la-masina prin X-API-Key (back-office nativ),
                    acelasi antet ca la restul API-ului Biro26.

EN: three entry points, one implementation; they differ only in who may call.
"""
from __future__ import annotations

from flask import jsonify, redirect, render_template, request

from controllers.auth_controller import AuthController
from controllers.biro26_controller import Biro26Controller

from modules.efactura import blueprint
from modules.efactura.controller import EfaController
from modules.efactura.store import EfaStore


def _body():
    return request.get_json(silent=True) or {}


def _reply(r, ok=200, bad=400):
    return jsonify(r), (ok if r.get("success") else bad)


# ── 1. BACK-OFFICE (sesiunea portalului) ───────────────────────────────
def _admin_guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "error": "login required"}), 401


@blueprint.route("/")
def admin_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/efactura/")
    return render_template("efactura_admin.html")


@blueprint.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    err = _admin_guard()
    if err:
        return err
    if request.method == "POST":
        return _reply(EfaStore.set_settings(_body()))
    return jsonify({"success": True, "data": EfaStore.settings_public()})


@blueprint.route("/admin/test", methods=["POST"])
def admin_test():
    err = _admin_guard()
    if err:
        return err
    from modules.efactura.sfs import SfsClient
    r = SfsClient.from_settings().test()
    EfaStore.log(None, "test", str(r)[:600], "backoffice")
    return _reply(r, bad=502)


@blueprint.route("/admin/docs")
def admin_docs():
    err = _admin_guard()
    if err:
        return err
    return jsonify(EfaStore.doc_list(request.args.get("status", ""),
                                     request.args.get("limit", 100, type=int)))


@blueprint.route("/admin/log")
def admin_log():
    err = _admin_guard()
    if err:
        return err
    return jsonify(EfaStore.log_list(request.args.get("limit", 200, type=int)))


@blueprint.route("/admin/send/<int:doc_cod>", methods=["POST"])
def admin_send(doc_cod):
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.send(doc_cod, src="backoffice"))


@blueprint.route("/admin/preview/<int:doc_cod>")
def admin_preview(doc_cod):
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.preview_xml(doc_cod))


@blueprint.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.refresh_statuses(
        _body().get("days", 7)), bad=502)


# ── 2. CABINETUL CLIENTULUI (site) ─────────────────────────────────────
def _client_cod():
    """RO: clientul logat pe site; None daca nu e autentificat."""
    from flask import session
    c = session.get("biro26_client")
    return int(c["univers_cod"]) if c else None


@blueprint.route("/my/status/<int:doc_cod>")
def my_status(doc_cod):
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.status(doc_cod, allowed_client_cod=cc),
                  bad=403)


@blueprint.route("/my/send/<int:doc_cod>", methods=["POST"])
def my_send(doc_cod):
    """RO: clientul cere factura fiscala electronica pentru comanda LUI —
    aceeasi logica, dar limitata la documentele proprii."""
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.send(doc_cod, src="cabinet",
                                     allowed_client_cod=cc), bad=403)


@blueprint.route("/my/preview/<int:doc_cod>")
def my_preview(doc_cod):
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.preview_xml(doc_cod, allowed_client_cod=cc),
                  bad=403)


# ── 3. API INTERN (X-API-Key) pentru back-office-uri native ────────────
def _api_guard():
    """RO: acelasi mecanism ca la restul API-ului Biro26 (X-API-Key sau
    ?api_key=), ca aplicatiile native sa nu invete inca un tip de acces."""
    if Biro26Controller._api_token_ok():
        return None
    return jsonify({"success": False, "error": "invalid api key"}), 401


@blueprint.route("/api/send/<int:doc_cod>", methods=["POST"])
def api_send(doc_cod):
    err = _api_guard()
    if err:
        return err
    return _reply(EfaController.send(doc_cod, src="api"))


@blueprint.route("/api/status/<int:doc_cod>")
def api_status(doc_cod):
    err = _api_guard()
    if err:
        return err
    return _reply(EfaController.status(doc_cod))


@blueprint.route("/api/preview/<int:doc_cod>")
def api_preview(doc_cod):
    err = _api_guard()
    if err:
        return err
    return _reply(EfaController.preview_xml(doc_cod))


@blueprint.route("/api/docs")
def api_docs():
    err = _api_guard()
    if err:
        return err
    return jsonify(EfaStore.doc_list(request.args.get("status", ""),
                                     request.args.get("limit", 100, type=int)))


@blueprint.route("/api/health")
def api_health():
    err = _api_guard()
    if err:
        return err
    s = EfaStore.settings_public()
    return jsonify({"success": True, "data": {
        "configured": s.get("configured"), "mode": s.get("mode"),
        "endpoint_set": bool(s.get("endpoint"))}})

"""API-ul e-Factura pentru back-office-ul NATIV una.md — pe HTTP simplu.

RO: aplicatia nativa nu vorbeste HTTP; ea apeleaza un pachet Oracle
(`EFA_NATIVE`, vezi sql/03_efa_native.sql), care la rindul lui apeleaza
serverul web prin UTL_HTTP — exact ca «Contul de plata»
(`y_ai_BIRO26.gen_conturi`). Doua constringeri vin de acolo:

1. Oracle 11g de pe serverul ERP nu are wallet TLS (ORA-29024 la HTTPS),
   deci apelul trebuie sa mearga pe **http://**;
2. intrarea `officeplus.md` redirecteaza tot HTTP-ul la HTTPS, CU EXCEPTIA
   prefixului `/api/biro26/` (masurat 02.09.2026: `/api/biro26/...` trece,
   `/api/...` si `/UNA.md/...` primesc 301).

De aceea aceste adrese stau la radacina, sub `/api/biro26/efactura/`, si
NU sub prefixul modulului. Ele raman totusi in modul: nucleul le monteaza
prin `root_blueprint` + `root_paths` din module.json (vezi
core/module_loader.py), fara nicio linie in app.py.

Accesul: aceeasi cheie ca restul API-ului Biro26 (`X-API-Key` sau
`?api_key=`, = BIRO26_API_TOKEN din .env = YBIRO_SETTINGS.API_GEN_KEY).
Trimiterea e si pe GET, pentru ca UTL_HTTP.REQUEST face doar GET — la fel
ca `gen-docs-by-nr`; efectul e protejat de cheie.
EN: plain-HTTP machine API for the native back-office, mounted at root
through the core's root_blueprint facility.
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from controllers.biro26_controller import Biro26Controller

root_blueprint = Blueprint("efactura_root", __name__)

ROOT_PATHS = [
    "/api/biro26/efactura/health",
    "/api/biro26/efactura/send/<int:doc_cod>",
    "/api/biro26/efactura/status/<int:doc_cod>",
]


def _guard():
    if Biro26Controller._api_token_ok():
        return None
    return jsonify({"success": False, "error": "invalid api key"}), 401


def _reply(r, ok=200, bad=400):
    return jsonify(r), (ok if r.get("success") else bad)


@root_blueprint.route("/api/biro26/efactura/health")
def native_health():
    err = _guard()
    if err:
        return err
    from modules.efactura.store import EfaStore
    pub = EfaStore.settings_public()
    return jsonify({"success": True, "data": {
        "configured": pub.get("configured"), "endpoint": pub.get("endpoint"),
        "two_signers": pub.get("two_signers")}})


@root_blueprint.route("/api/biro26/efactura/send/<int:doc_cod>",
                      methods=["GET", "POST"])
def native_send(doc_cod):
    """RO: actiunea «Выгрузить в e-Factura» din una.md ajunge aici.
    `?override_date=YYYY-MM-DD` — DOAR pentru probe pe mediul de test."""
    err = _guard()
    if err:
        return err
    from modules.efactura.controller import EfaController
    body = request.get_json(silent=True) or {}
    od = request.args.get("override_date") or body.get("override_date")
    return _reply(EfaController.send(doc_cod, src="native", override_date=od))


@root_blueprint.route("/api/biro26/efactura/status/<int:doc_cod>")
def native_status(doc_cod):
    err = _guard()
    if err:
        return err
    from modules.efactura.controller import EfaController
    return _reply(EfaController.status(doc_cod))

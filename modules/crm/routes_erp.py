"""Rutele sursei reale: marfa din dictionarul ERP si contragentii OfficePlus.

RO: fisier separat (regula nr. 2). Toate cer sesiune de portal; regimul demo
si cabinetul clientului primesc 409 cu explicatie, nu date reale.
EN: routes for the real ERP source (goods search/import, client sync).
"""
from __future__ import annotations

from flask import g, jsonify, request

from modules.crm import blueprint
from modules.crm import tenant as tenant_mod
from modules.crm.routes_process import err, with_data
from modules.crm.store_erp import ErpSource


def _erp() -> ErpSource:
    return ErpSource(g.crm.t, g.crm.db)


@blueprint.route("/api/v2/erp/status")
@with_data
def api_erp_status():
    return jsonify({"success": True, "data": _erp().status()})


@blueprint.route("/api/v2/erp/goods")
@with_data
def api_erp_goods():
    """RO: cautare vie in TMS_UNIVERS (nu scrie nimic)."""
    rows = _erp().search_goods(request.args.get("q", ""),
                               limit=request.args.get("limit", 50, type=int),
                               only_active=request.args.get("all") != "1")
    return jsonify({"success": True, "data": rows, "count": len(rows)})


@blueprint.route("/api/v2/erp/items", methods=["POST"])
@with_data
def api_erp_import_item():
    """RO: aduce pozitia ERP in nomenclatorul CRM (sau o reimprospateaza)."""
    b = request.get_json(silent=True) or {}
    cods = b.get("cods") or ([b.get("cod")] if b.get("cod") else [])
    if not cods:
        raise ValueError("cod: cimp obligatoriu")
    e, out = _erp(), []
    for c in list(cods)[:100]:
        out.append(e.import_item(int(c)))
    return jsonify({"success": True, "data": out, "count": len(out)}), 201


@blueprint.route("/api/v2/erp/items/refresh", methods=["POST"])
@with_data
def api_erp_refresh():
    return jsonify({"success": True, "count": _erp().refresh_items()})


@blueprint.route("/api/v2/erp/clients/sync", methods=["POST"])
@with_data
def api_erp_sync_clients():
    return jsonify({"success": True, "data": _erp().sync_clients(),
                    "status": _erp().status()})


@blueprint.route("/api/v2/mode", methods=["GET", "POST"])
def api_mode():
    """RO: comutatorul «date reale / demo». Doar pentru portal: clientul din
    cabinet are datele lui si nu vede comutatorul."""
    t = tenant_mod.current()
    if t is None:
        return err("login required", 401)
    if t.kind == tenant_mod.CLIENT:
        return err("regimul demo e doar pentru portal", 403)
    if request.method == "POST":
        b = request.get_json(silent=True) or {}
        tenant_mod.set_demo(bool(b.get("demo")))
        t = tenant_mod.current()
    return jsonify({"success": True, "data": {"demo": t.is_demo, "tenant": t.kind,
                                              "label": t.label}})

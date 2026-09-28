"""Rutele procesului CRM — API-ul v2 al TZ (§7.4) pe blueprint-ul modulului.

RO: FARA prefix (il pune nucleul, sub cheia modulului). Contractul:
JSON UTF-8, date yyyy-mm-dd, sume cu doua zecimale, erori {error, detail,
field} cu HTTP 4xx (niciodata 200 cu text de eroare), paginare <= 500.
Chiriasul se ia din sesiune (tenant.py): portalul = OfficePlus, clientul
din cabinet = contul lui. `/cabinet` e pagina clientului.
EN: v2 process API: entities CRUD, order lines, post, convert, boards,
workspace stages, reports, lang, seed, dml-test.
"""
from __future__ import annotations

import json
import os
from functools import wraps
from typing import Any, Callable, Dict

from flask import Response, g, jsonify, redirect, render_template, request, url_for

from modules.crm import blueprint, dml_test, process, reports, seed
from modules.crm.entities import ENTITIES, as_json, entity
from modules.crm.store_process import CrmData
from modules.crm import tenant as tenant_mod

_LANG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang.json")
_LANG: Dict[str, Any] = {}


def lang_json() -> Dict[str, Any]:
    global _LANG
    if not _LANG:
        with open(_LANG_PATH, encoding="utf-8") as fh:
            _LANG = json.load(fh)
    return _LANG


def err(msg: str, code: int = 400, field: str = "", detail: str = ""):
    return jsonify({"success": False, "error": msg, "detail": detail, "field": field}), code


def with_data(fn: Callable) -> Callable:
    """RO: chiriasul din sesiune -> g.crm (CrmData); fara sesiune -> 401."""
    @wraps(fn)
    def wrapper(*a, **kw):
        t = tenant_mod.current(prefer_client=request.args.get("as") == "client")
        if t is None:
            return err("login required", 401)
        g.crm = CrmData(t)
        try:
            return fn(*a, **kw)
        except ValueError as e:                       # validare
            return err(str(e), 400, field=str(e).split(":")[0] if ":" in str(e) else "")
        except LookupError as e:
            return err(str(e), 404)
        except RuntimeError as e:                     # eroare Oracle — nu se mascheaza
            return err("eroare de baza de date", 500, detail=str(e)[:400])
    return wrapper


# ── pagina clientului (cabinet) ──────────────────────────────────────────
@blueprint.route("/cabinet")
def cabinet_page():
    """RO: CRM-ul clientului OfficePlus — cere sesiunea de client a magazinului."""
    t = tenant_mod.current(prefer_client=True)
    if t is None or t.is_office:
        return redirect("/UNA.md/orasldev/biro26-site/account")
    return render_template("crm_app.html", tenant_kind=t.kind, tenant_id=t.id, cabinet=True)


# ── meta: limbi, descrieri, versiune ─────────────────────────────────────
@blueprint.route("/api/v2/lang")
def api_lang():
    return jsonify(lang_json())


@blueprint.route("/api/v2/health")
@with_data
def api_health():
    return jsonify({"success": True, "data": {"tenant": g.crm.t.kind, "tenant_id": g.crm.t.id,
                                              "entities": list(ENTITIES), "counts": g.crm.counts()}})


@blueprint.route("/api/v2/meta")
@with_data
def api_meta():
    return jsonify({"success": True, "data": {
        "entities": {k: as_json(e) for k, e in ENTITIES.items()},
        "stages": [{"stage": s, "title": process.STAGE_TITLES[i], "hint": process.STAGE_HINTS[i],
                    "table": "deals" if s.startswith("deal_") else "orders"} for i, s in enumerate(process.STAGES)],
        "boards": {k: {"columns": process.board_columns(k), "colors": process.BOARD_COLORS[k]} for k in process.BOARDS},
        "reports": list(reports.SLUGS),
        "tenant": {"kind": g.crm.t.kind, "id": g.crm.t.id, "label": g.crm.t.label}}})


# ── CRUD generic ─────────────────────────────────────────────────────────
def _entity_or_404(key: str):
    if key not in ENTITIES:
        raise LookupError("entitate necunoscuta: %s" % key)
    return entity(key)


@blueprint.route("/api/v2/lookup/<kind>")
@with_data
def api_lookup(kind):
    k = "lookup_" + kind
    from modules.crm.entities import LOOKUP_TABLE
    if k not in LOOKUP_TABLE:
        raise LookupError("lookup necunoscut")
    return jsonify({"success": True, "data": [{"id": int(r["id"]), "name": r["d"]} for r in g.crm.lookup_pairs(k)]})


@blueprint.route("/api/v2/<key>")
@with_data
def api_list(key):
    _entity_or_404(key)
    extra, params = "", {}
    stage = request.args.get("stage")
    if stage in process.STAGES:                        # filtrul unei plite de pe tabloul de lucru
        extra, params = process.stage_where(stage)
    board, col = request.args.get("board"), request.args.get("col", type=int)
    if board in process.BOARDS and col is not None:
        extra, params = process.board_column_where(board, col, request.args.get("project_id", 0, type=int))
    pid = request.args.get("project_id", type=int)
    if pid and key in ("tasks", "orders") and not board:
        extra, params = "t.PROJECT_ID = :pid", {"pid": pid}
    cid = request.args.get("client_id", type=int)
    if cid and entity(key).field("client_id"):
        extra = (extra + " AND " if extra else "") + "t.CLIENT_ID = :cid"
        params["cid"] = cid
    rows = g.crm.list(key, q=request.args.get("q", ""), extra_where=extra, extra_params=params,
                      limit=min(request.args.get("limit", 500, type=int), 500))
    return jsonify({"success": True, "data": rows, "count": len(rows)})


@blueprint.route("/api/v2/<key>/<int:rid>")
@with_data
def api_get(key, rid):
    _entity_or_404(key)
    row = g.crm.get(key, rid)
    if not row:
        raise LookupError("inregistrare inexistenta")
    if key == "orders":
        row["lines"] = g.crm.order_lines(rid)
    if key == "projects":
        row["summary"] = g.crm.project_summary(rid)
    return jsonify({"success": True, "data": row})


@blueprint.route("/api/v2/<key>", methods=["POST"])
@with_data
def api_create(key):
    _entity_or_404(key)
    rid = g.crm.insert(key, request.get_json(silent=True) or {})
    return jsonify({"success": True, "data": g.crm.get(key, rid), "id": rid}), 201


@blueprint.route("/api/v2/<key>/<int:rid>", methods=["PUT"])
@with_data
def api_update(key, rid):
    _entity_or_404(key)
    g.crm.update(key, rid, request.get_json(silent=True) or {})
    return jsonify({"success": True, "data": g.crm.get(key, rid)})


@blueprint.route("/api/v2/<key>/<int:rid>", methods=["DELETE"])
@with_data
def api_delete(key, rid):
    _entity_or_404(key)
    g.crm.delete(key, rid)
    return jsonify({"success": True})


# ── comenzi: linii si contare ────────────────────────────────────────────
@blueprint.route("/api/v2/orders/<int:rid>/lines", methods=["POST"])
@with_data
def api_order_line_add(rid):
    b = request.get_json(silent=True) or {}
    try:
        item_id, qty, price = int(b.get("item_id") or 0), float(b.get("qty") or 1), float(b.get("price") or 0)
    except (TypeError, ValueError):
        raise ValueError("qty/price: trebuie sa fie numere")
    if item_id <= 0:
        raise ValueError("item_id: cimp obligatoriu")
    if not price:
        it = g.crm.get("items", item_id)
        price = float((it or {}).get("price") or 0)
    lid = g.crm.add_order_line(rid, item_id, qty, price)
    return jsonify({"success": True, "id": lid, "data": g.crm.get("orders", rid), "lines": g.crm.order_lines(rid)}), 201


@blueprint.route("/api/v2/orders/<int:rid>/lines/<int:lid>", methods=["DELETE"])
@with_data
def api_order_line_del(rid, lid):
    g.crm.delete_order_line(lid)
    return jsonify({"success": True, "data": g.crm.get("orders", rid), "lines": g.crm.order_lines(rid)})


@blueprint.route("/api/v2/orders/<int:rid>/post", methods=["POST"])
@with_data
def api_order_post(rid):
    msg = g.crm.post_order(rid)
    ok = msg.startswith(("списано", "оприходовано", "услуги"))
    return jsonify({"success": ok, "message": msg, "data": g.crm.get("orders", rid)}), (200 if ok else 409)


@blueprint.route("/api/v2/leads/<int:rid>/convert", methods=["POST"])
@with_data
def api_lead_convert(rid):
    msg, cid = g.crm.convert_lead(rid)
    return jsonify({"success": cid > 0, "message": msg, "client_id": cid, "data": g.crm.get("leads", rid)}), (200 if cid else 409)


@blueprint.route("/api/v2/tasks/<int:rid>/done", methods=["POST"])
@with_data
def api_task_done(rid):
    b = request.get_json(silent=True) or {}
    g.crm.set_task_done(rid, bool(b.get("done", True)))
    return jsonify({"success": True, "data": g.crm.get("tasks", rid)})


# ── tablou de lucru, doua, rapoarte ──────────────────────────────────────
@blueprint.route("/api/v2/workspace/stages")
@with_data
def api_stages():
    st = g.crm.stages()
    orders = [s for s in st if s["table"] == "orders"]
    tasks = g.crm.list("tasks", extra_where="t.DONE = 0", limit=8)
    last_orders = g.crm.list("orders", limit=8)
    return jsonify({"success": True, "data": {"stages": st, "orders_total": sum(s["count"] for s in orders),
                                              "orders_overdue": sum(s["overdue"] for s in orders),
                                              "orders_overdue_sum": sum(s["overdue_sum"] for s in orders),
                                              "next_tasks": tasks, "last_orders": last_orders}})


@blueprint.route("/api/v2/board/<kind>")
@with_data
def api_board(kind):
    if kind not in process.BOARDS:
        raise LookupError("doua necunoscuta")
    return jsonify({"success": True, "data": g.crm.board(kind, request.args.get("project_id", 0, type=int))})


@blueprint.route("/api/v2/board/<kind>/move", methods=["POST"])
@with_data
def api_board_move(kind):
    """RO: singurul punct de schimbare a etapei de pe doua (MoveBoardCard)."""
    if kind not in process.BOARDS:
        raise LookupError("doua necunoscuta")
    b = request.get_json(silent=True) or {}
    g.crm.move_card(kind, int(b.get("id") or 0), int(b.get("col", -1)))
    return jsonify({"success": True})


@blueprint.route("/api/v2/reports/<slug>")
@with_data
def api_report(slug):
    if slug not in reports.SLUGS:
        raise LookupError("raport necunoscut")
    rep = reports.build(g.crm, slug, request.args.get("lang", "ro"))
    if request.args.get("format") == "csv":
        return Response(reports.to_csv(rep), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=crm_%s.csv" % slug})
    return jsonify({"success": True, "data": rep})


# ── date demo si DML-test (TZ TEC-03) ────────────────────────────────────
@blueprint.route("/api/v2/seed", methods=["POST"])
@with_data
def api_seed():
    st = seed.run(g.crm)
    return jsonify({"success": True, "data": st, "text": seed.text(st), "counts": g.crm.counts()})


@blueprint.route("/api/v2/dml-test", methods=["POST"])
@with_data
def api_dml_test():
    # RO: testul ruleaza pe chiriasul tehnic, nu pe datele celui logat
    r = dml_test.run(CrmData(tenant_mod.Tenant(tenant_mod.CLIENT, 999999)))
    return jsonify({"success": r["ok"], "data": r})

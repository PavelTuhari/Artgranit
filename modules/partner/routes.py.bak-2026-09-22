"""Rutele modulului Partner API.

RO: adresele sint FARA prefix — nucleul le monteaza sub
/UNA.md/orasldev/partner. Adresele publice identice cu Ultra
(https://officeplus.md/api/v1/... si /api-documentation) le da nginx-ul
instantei, ca la vitrina. Contract: eshop.ultra.md/api-documentation.
EN: routes are prefix-less; the instance nginx exposes the pretty
Ultra-shaped public URLs.
"""
from __future__ import annotations

from flask import jsonify, render_template, request

from controllers.auth_controller import AuthController
from modules.partner import blueprint, rules
from modules.partner.controller import PartnerController
from modules.partner.store import PartnerStore


def _err(msg, status, errors=None):
    return jsonify(rules.error_body(msg, errors)), status


def _guarded():
    """RO: (partener, eroare) — eroarea e raspunsul gata de trimis."""
    partner = PartnerController.current_partner()
    if not partner:
        return None, _err("Unauthenticated.", 401)
    if PartnerController.throttled(partner["partner_id"]):
        return None, _err("Too many requests.", 429)
    return partner, None


def _body():
    return request.get_json(silent=True) or {}


# ── documentatia (pagina publica, in stilul Ultra) ─────────────────────
@blueprint.route("/api-documentation")
def api_documentation():
    return render_template("partner_api_docs.html")


# ── autentificare ──────────────────────────────────────────────────────
@blueprint.route("/api/auth/token", methods=["POST"])
def auth_token():
    body, status = PartnerController.auth_token(_body())
    return jsonify(body), status


@blueprint.route("/api/auth/refresh", methods=["POST"])
def auth_refresh():
    body, status = PartnerController.auth_refresh(_body())
    return jsonify(body), status


@blueprint.route("/api/auth/revoke", methods=["POST"])
def auth_revoke():
    body, status = PartnerController.auth_revoke()
    return jsonify(body), status


# ── catalog ────────────────────────────────────────────────────────────
@blueprint.route("/api/product")
def product_list():
    partner, err = _guarded()
    if err:
        return err
    r = PartnerStore.products(request.args)
    if not r.get("success"):
        return _err("Server error.", 500)
    return jsonify({
        "data": [rules.map_product(x) for x in (r.get("data") or [])],
        "total": r.get("total"),
        "limit": min(max(int(request.args.get("limit") or 100), 1), 1000),
        "offset": max(int(request.args.get("offset") or 0), 0),
    })


@blueprint.route("/api/product/batch", methods=["POST"])
def product_batch():
    partner, err = _guarded()
    if err:
        return err
    codes = _body().get("codes") or _body().get("ultra_codes") or []
    if not isinstance(codes, list) or not (1 <= len(codes) <= 1000):
        return _err("Validation failed.", 400,
                    {"codes": ["must be a list of 1..1000 codes"]})
    rows = PartnerStore.products_by_codes([str(c) for c in codes])
    return jsonify({"data": [rules.map_product(x) for x in rows]})


@blueprint.route("/api/product/<pid>")
def product_one(pid):
    partner, err = _guarded()
    if err:
        return err
    row = PartnerStore.product_one(pid)
    if not row:
        return _err("Product not found.", 404)
    return jsonify(rules.map_product(row))


@blueprint.route("/api/category")
def category_list():
    partner, err = _guarded()
    if err:
        return err
    from models.biro26_oracle_store import Biro26Store
    r = Biro26Store.get_product_tree()
    return jsonify({"data": [
        {"name": {"ro": t.get("categorie") or t.get("grupa")},
         "hierarchy": [x for x in (t.get("grupa"), t.get("categorie")) if x],
         "level": 2 if t.get("categorie") else 1,
         "products": t.get("cnt")}
        for t in (r.get("data") or [])]})


@blueprint.route("/api/brand")
def brand_list():
    partner, err = _guarded()
    if err:
        return err
    from models.biro26_oracle_store import Biro26Store
    r = Biro26Store.get_product_brands()
    return jsonify({"data": [{"name": b.get("brand"), "products": b.get("cnt")}
                             for b in (r.get("data") or [])]})


# ── stocuri ────────────────────────────────────────────────────────────
@blueprint.route("/api/quantity")
def quantity_list():
    partner, err = _guarded()
    if err:
        return err
    r = PartnerStore.products(request.args)
    if not r.get("success"):
        return _err("Server error.", 500)
    return jsonify({"data": [rules.map_quantity(x)
                             for x in (r.get("data") or [])]})


@blueprint.route("/api/quantity/batch", methods=["POST"])
def quantity_batch():
    partner, err = _guarded()
    if err:
        return err
    codes = _body().get("codes") or _body().get("ultra_codes") or []
    if not isinstance(codes, list) or not (1 <= len(codes) <= 1000):
        return _err("Validation failed.", 400,
                    {"codes": ["must be a list of 1..1000 codes"]})
    rows = PartnerStore.products_by_codes([str(c) for c in codes])
    return jsonify({"data": [rules.map_quantity(x) for x in rows]})


# ── modificari incrementale ────────────────────────────────────────────
@blueprint.route("/api/changes")
def changes():
    partner, err = _guarded()
    if err:
        return err
    since = str(request.args.get("since") or "1990-01-01T00:00:00")[:19]
    if "T" not in since:
        since += "T00:00:00"
    entity = str(request.args.get("entity") or "")
    if entity not in ("", "product", "price", "quantity"):
        return _err("Validation failed.", 400,
                    {"entity": ["must be one of: product, price, quantity"]})
    try:
        limit = int(request.args.get("limit") or 100)
    except ValueError:
        limit = 100
    return jsonify(PartnerStore.changes(since, entity, limit))


# ── comenzi ────────────────────────────────────────────────────────────
@blueprint.route("/api/order", methods=["POST"])
def order_create():
    partner, err = _guarded()
    if err:
        return err
    payload = _body()
    errors = rules.validate_order(payload)
    if errors:
        return _err("Validation failed.", 400, errors)
    r = PartnerStore.order_create(partner, payload)
    if not r.get("success"):
        return _err(str(r.get("error") or "Order failed."), 400)
    if r.get("validated"):
        return jsonify({"message": "Order is valid (not created).",
                        "items": r["items"], "total": r["total"]})
    return jsonify({"message": "Order created.",
                    "order_id": r["data"].get("cod"),
                    "order_number": r["data"].get("nrmanual")})


@blueprint.route("/api/order", methods=["GET"])
def order_list():
    partner, err = _guarded()
    if err:
        return err
    try:
        limit = int(request.args.get("limit") or 50)
    except ValueError:
        limit = 50
    r = PartnerStore.orders_list(partner, limit)
    return jsonify({"data": r.get("data") or []})


@blueprint.route("/api/health")
def health():
    partner, err = _guarded()
    if err:
        return err
    import datetime
    return jsonify({"status": "ok",
                    "time": datetime.datetime.now().isoformat(timespec="seconds"),
                    "user_email": partner["email"]})


# ── administrare (back-office, sub autentificarea portalului) ─────────
def _admin_guard():
    if AuthController.is_authenticated():
        return None
    return _err("Login required.", 401)


@blueprint.route("/")
def admin_page():
    if not AuthController.is_authenticated():
        from flask import redirect
        return redirect("/login?next=/UNA.md/orasldev/partner/")
    return render_template("partner_admin.html")


@blueprint.route("/admin/partners", methods=["GET"])
def admin_partners():
    err = _admin_guard()
    if err:
        return err
    return jsonify(PartnerStore.partner_list())


@blueprint.route("/admin/partners", methods=["POST"])
def admin_partner_save():
    err = _admin_guard()
    if err:
        return err
    r = PartnerStore.partner_save(_body())
    return jsonify(r), (200 if r.get("success") else 400)


@blueprint.route("/admin/log")
def admin_log():
    err = _admin_guard()
    if err:
        return err
    from models.biro26_oracle_store import _rows
    from models.biro26_db import Biro26DB
    rows = _rows(Biro26DB().execute_query(
        "SELECT * FROM (SELECT l.ID, TO_CHAR(l.TS,'DD.MM.YYYY HH24:MI:SS') TS, "
        "l.EVENT, l.DETAIL, p.EMAIL FROM PAPI_LOG l "
        "LEFT JOIN PAPI_PARTNER p ON p.ID = l.PARTNER_ID "
        "ORDER BY l.ID DESC) WHERE ROWNUM <= 200"))
    return jsonify({"success": True, "data": rows})


@blueprint.route("/admin/ultra/settings", methods=["GET", "POST"])
def admin_ultra_settings():
    err = _admin_guard()
    if err:
        return err
    from models.biro26_oracle_store import Biro26Store
    if request.method == "POST":
        d = _body()
        for key, setting in (("base", "PARTNER_ULTRA_BASE"),
                             ("username", "PARTNER_ULTRA_USER"),
                             ("password", "PARTNER_ULTRA_PASSWORD")):
            if d.get(key) is not None and str(d.get(key)) != "":
                Biro26Store.set_setting(setting, str(d[key])[:300])
        return jsonify({"success": True})
    return jsonify({"success": True, "data": {
        "base": Biro26Store.get_setting("PARTNER_ULTRA_BASE",
                                        "https://eshop.ultra.md/api"),
        "username": Biro26Store.get_setting("PARTNER_ULTRA_USER", ""),
        "password_set": bool(Biro26Store.get_setting("PARTNER_ULTRA_PASSWORD", "")),
        "last_sync": Biro26Store.get_setting("PARTNER_ULTRA_SINCE", ""),
    }})


@blueprint.route("/admin/ultra/test", methods=["POST"])
def admin_ultra_test():
    err = _admin_guard()
    if err:
        return err
    from modules.partner.ultra import UltraClient
    r = UltraClient.from_settings().test()
    return jsonify(r), (200 if r.get("success") else 502)


@blueprint.route("/admin/ultra/sync", methods=["POST"])
def admin_ultra_sync():
    err = _admin_guard()
    if err:
        return err
    from modules.partner.ultra import UltraClient
    full = bool(_body().get("full"))
    r = UltraClient.from_settings().sync(full=full)
    return jsonify(r), (200 if r.get("success") else 502)

"""HTTP-маршруты TexFlow."""
from __future__ import annotations

import re

from flask import (Blueprint, Response, current_app, flash, jsonify, redirect, render_template,
                   request, url_for)

from . import labels as L
from . import printing, store
from .i18n import _

bp = Blueprint("tf", __name__)


def con():
    return current_app.get_db()


def _f(name, default=0.0):
    try:
        v = request.form.get(name, "")
        return float(str(v).replace(",", ".")) if str(v).strip() else default
    except ValueError:
        return default


def _i(v):
    try:
        return int(v) if v not in (None, "") else None
    except ValueError:
        return None


# ---------------------------------------------------------------- главная

@bp.route("/")
def index():
    c = con()
    return render_template("index.html", d=store.dashboard(c), shipments=store.shipments(c)[:8])


# ---------------------------------------------------------------- поставки

@bp.route("/shipments", methods=["GET", "POST"])
def shipments():
    c = con()
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if not code:
            flash(_("Укажите номер поставки"), "err")
            return redirect(url_for("tf.shipments"))
        try:
            sid = store.create_shipment(
                c, code, request.form.get("supplier", ""), request.form.get("country", "TR"),
                request.form.get("currency", "USD"), _f("fx_rate", 1), request.form.get("arrival_date", ""),
                freight=_f("freight"), customs=_f("customs"), broker=_f("broker"),
                other_costs=_f("other_costs"), alloc_method=request.form.get("alloc_method", "value"))
        except Exception as e:  # noqa: BLE001
            flash(_("Не создано: {e}", e=e), "err")
            return redirect(url_for("tf.shipments"))
        n = _i(request.form.get("bags_count")) or 0
        for k in range(1, n + 1):
            store.ensure_bag(c, sid, str(k))
        c.commit()
        flash(_("Поставка {code} создана", code=code), "ok")
        return redirect(url_for("tf.shipment", sid=sid))
    return render_template("shipments.html", shipments=store.shipments(c))


@bp.route("/shipments/<int:sid>", methods=["GET", "POST"])
def shipment(sid):
    c = con()
    sh = store.shipment(c, sid)
    if not sh:
        return _("Поставка не найдена"), 404
    if request.method == "POST":
        store.update_shipment(c, sid, currency=request.form.get("currency", sh["currency"]).upper(),
                              fx_rate=_f("fx_rate", sh["fx_rate"]), freight=_f("freight"), customs=_f("customs"),
                              broker=_f("broker"), other_costs=_f("other_costs"),
                              alloc_method=request.form.get("alloc_method", "value"),
                              arrival_date=request.form.get("arrival_date", ""),
                              note=request.form.get("note", ""))
        store.compute_landed(c, sid)
        flash(_("Затраты сохранены, себестоимость пересчитана"), "ok")
        return redirect(url_for("tf.shipment", sid=sid))
    store.compute_landed(c, sid)          # себестоимость всегда актуальна, без кнопки «пересчитать»
    return render_template("shipment.html", sh=sh, bags=store.bags(c, sid),
                           packing=store.packing_lines(c, sid), rec=store.reconciliation(c, sid),
                           totals=store.shipment_totals(c, sid))


@bp.post("/shipments/<int:sid>/packing")
def packing_import(sid):
    c = con()
    text = request.form.get("text", "")
    f = request.files.get("file")
    if f and f.filename:
        raw = f.read()
        for enc in ("utf-8-sig", "cp1251", "cp1254", "gb18030", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    if not text.strip():
        flash(_("Пустой упаковочный лист"), "err")
        return redirect(url_for("tf.shipment", sid=sid))
    try:
        r = store.import_packing_csv(c, sid, text, replace=request.form.get("append") != "1")
    except ValueError as e:
        flash(str(e), "err")
        return redirect(url_for("tf.shipment", sid=sid))
    msg = _("Загружено строк: {lines}, мешков: {bags}", lines=r["lines"], bags=r["bags"])
    if r["unknown_categories"]:
        msg += ". " + _("Не распознаны категории: ") + ", ".join(r["unknown_categories"])
    flash(msg, "ok" if not r["unknown_categories"] else "warn")
    return redirect(url_for("tf.shipment", sid=sid))


@bp.post("/shipments/<int:sid>/bags")
def bag_add(sid):
    c = con()
    no = request.form.get("bag_no", "").strip()
    if no:
        store.ensure_bag(c, sid, no, _f("weight_kg") or None, request.form.get("desc", ""))
        c.commit()
    return redirect(url_for("tf.shipment", sid=sid))


@bp.post("/bags/<int:bag_id>/status")
def bag_status(bag_id):
    c = con()
    store.set_bag_status(c, bag_id, request.form.get("status", "done"))
    sid = c.execute("SELECT shipment_id FROM bags WHERE id = ?", (bag_id,)).fetchone()[0]
    return redirect(request.form.get("next") or url_for("tf.shipment", sid=sid))


# ---------------------------------------------------------------- разбор мешка

@bp.route("/sort/<int:sid>")
def sort(sid):
    c = con()
    sh = store.shipment(c, sid)
    if not sh:
        return _("Поставка не найдена"), 404
    bag_id = _i(request.args.get("bag"))
    pid = _i(request.args.get("product"))
    matrix = store.product_matrix(c, pid) if pid and store.product(c, pid) else None
    hint = 0.0
    if matrix:
        hint = matrix["product"]["base_cost_fx"] or store.declared_unit_price(c, sid, matrix["product"]["category_id"])
    return render_template("sort.html", sh=sh, bags=store.bags(c, sid), bag_id=bag_id, matrix=matrix,
                           families=store.color_families(c), categories=store.categories(c),
                           log=store.intake_log(c, sid, bag_id, 60), cost_hint=hint,
                           recent=store.products(c)[:12])


@bp.post("/sort/<int:sid>/product")
def sort_quick_product(sid):
    c = con()
    bag = request.form.get("bag_id") or None
    cat_id = _i(request.form.get("category_id"))
    name = request.form.get("name", "").strip()
    if not (cat_id and name):
        flash(_("Нужны название и категория"), "err")
        return redirect(url_for("tf.sort", sid=sid, bag=bag))
    cost = _f("base_cost_fx") or store.declared_unit_price(c, sid, cat_id)
    try:
        pid = store.create_product(c, name, cat_id, request.form.get("style_code", ""),
                                   store.shipment(c, sid)["supplier"] or "", cost,
                                   request.form.get("composition", ""))
    except Exception as e:  # noqa: BLE001
        flash(_("Товар не создан: {e}", e=e), "err")
        return redirect(url_for("tf.sort", sid=sid, bag=bag))
    return redirect(url_for("tf.sort", sid=sid, bag=bag, product=pid))


_CELL = re.compile(r"^q_(\d+)_(\d+)$")


@bp.post("/sort/<int:sid>/intake")
def sort_intake(sid):
    c = con()
    pid = _i(request.form.get("product_id"))
    bag_id = _i(request.form.get("bag_id"))
    grid = {}
    for k, v in request.form.items():
        m = _CELL.match(k)
        if m and str(v).strip():
            try:
                grid[(int(m.group(1)), int(m.group(2)))] = int(v)
            except ValueError:
                continue
    cost = request.form.get("unit_cost_fx", "").replace(",", ".").strip()
    if cost:
        store.update_product(c, pid, base_cost_fx=float(cost))
    n = store.add_intake(c, sid, bag_id, pid, grid, float(cost) if cost else None)
    flash(_("Принято {n} шт.", n=n) if n else _("Ничего не введено"), "ok" if n else "warn")
    if request.form.get("print") and n:
        return redirect(url_for("tf.labels", shipment=sid, bag=bag_id or "", last=1))
    return redirect(url_for("tf.sort", sid=sid, bag=bag_id or "", product=pid))


@bp.post("/sort/<int:sid>/scan")
def sort_scan(sid):
    c = con()
    data = request.get_json(silent=True) or request.form
    try:
        v = store.add_scan(c, sid, _i(data.get("bag_id")), str(data.get("code", "")), int(data.get("qty") or 1))
    except ValueError as e:
        return jsonify(success=False, error=str(e)), 404
    return jsonify(success=True, sku=v["sku"], name=v["name"], product_id=v["product_id"])


@bp.post("/intake/<int:item_id>/delete")
def intake_delete(item_id):
    c = con()
    r = c.execute("SELECT shipment_id, bag_id FROM intake_items WHERE id = ?", (item_id,)).fetchone()
    store.delete_intake(c, item_id)
    return redirect(request.form.get("next") or url_for("tf.sort", sid=r["shipment_id"], bag=r["bag_id"] or ""))


# ---------------------------------------------------------------- цены

@bp.route("/shipments/<int:sid>/pricing", methods=["GET", "POST"])
def pricing(sid):
    c = con()
    sh = store.shipment(c, sid)
    if not sh:
        return _("Поставка не найдена"), 404
    if request.method == "POST":
        overrides = {}
        for k, v in request.form.items():
            if k.startswith("price_") and v.strip():
                try:
                    overrides[int(k[6:])] = float(v.replace(",", "."))
                except ValueError:
                    pass
        n = store.apply_prices(c, sid, overrides)
        flash(_("Цены записаны в {n} карточек", n=n), "ok")
        return redirect(url_for("tf.pricing", sid=sid))
    return render_template("pricing.html", sh=sh, rows=store.price_proposal(c, sid),
                           totals=store.shipment_totals(c, sid), st=store.settings(c))


# ---------------------------------------------------------------- каталог

@bp.route("/catalog")
def catalog():
    c = con()
    return render_template("catalog.html", products=store.products(c, request.args.get("q", ""),
                                                                    _i(request.args.get("category"))),
                           categories=store.categories(c), q=request.args.get("q", ""),
                           st=store.settings(c))


@bp.route("/product/<int:pid>", methods=["GET", "POST"])
def product(pid):
    c = con()
    if not store.product(c, pid):
        return _("Товар не найден"), 404
    if request.method == "POST":
        rp = request.form.get("retail_price", "").replace(",", ".").strip()
        store.update_product(c, pid, name=request.form.get("name", ""),
                             name_ro=request.form.get("name_ro", "").strip(),
                             name_en=request.form.get("name_en", "").strip(),
                             composition=request.form.get("composition", ""),
                             composition_ro=request.form.get("composition_ro", "").strip(),
                             composition_en=request.form.get("composition_en", "").strip(),
                             description=request.form.get("description", ""),
                             season=request.form.get("season", ""), gender=request.form.get("gender", ""),
                             base_cost_fx=_f("base_cost_fx"),
                             retail_price=float(rp) if rp else None,
                             price_locked=1 if request.form.get("price_locked") else 0)
        flash(_("Карточка сохранена"), "ok")
        return redirect(url_for("tf.product", pid=pid))
    m = store.product_matrix(c, pid)
    return render_template("product.html", m=m, p=m["product"], variants=store.variants(c, pid),
                           st=store.settings(c))


@bp.route("/export/catalog.csv")
def export_catalog():
    return Response("﻿" + store.export_catalog_csv(con()), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=catalog.csv"})


@bp.route("/api/products")
def api_products():
    rows = store.products(con(), request.args.get("q", ""))[:30]
    return jsonify([{"id": r["id"], "style_code": r["style_code"], "name": r["title"],
                     "category": r["category"], "stock": r["stock"]} for r in rows])


# ---------------------------------------------------------------- этикетки

def _label_selection(c):
    a = request.values
    sid, bag, pid, vid = (_i(a.get("shipment")), _i(a.get("bag")), _i(a.get("product")), _i(a.get("variant")))
    copies = _i(a.get("copies"))
    picked = {}
    for k, v in a.items():
        if k.startswith("v_") and str(v).strip():
            picked[int(k[2:])] = _i(v) or 0
    if picked:
        return picked
    if vid:
        return {vid: copies or 1}
    if pid:
        if copies:
            return {v["id"]: copies for v in store.variants(c, pid)}
        return {v["id"]: max(v["stock"], 0) or 1 for v in store.variants(c, pid)}
    if sid:
        if a.get("last"):
            last = c.execute("SELECT MAX(created_at) FROM intake_items WHERE shipment_id = ?", (sid,)).fetchone()[0]
            rows = c.execute("SELECT variant_id, SUM(qty) q FROM intake_items WHERE shipment_id = ? AND created_at = ?"
                             " GROUP BY variant_id HAVING q > 0", (sid, last)).fetchall()
            return {r["variant_id"]: r["q"] for r in rows}
        return store.labels_for_shipment(c, sid, bag)
    return {}


@bp.route("/labels", methods=["GET", "POST"])
def labels():
    c = con()
    sel = _label_selection(c)
    items = store.label_rows(c, sel)
    action = request.values.get("action", "")
    fmt = request.values.get("fmt", "pdf_a4")
    if action:
        lay, sheet = store.layouts(c)
        st = store.settings(c)
        sheet.start_cell = _i(request.values.get("start_cell")) or 0
        if not items:
            flash(_("Нет выбранных этикеток"), "warn")
            return redirect(url_for("tf.labels", **{k: v for k, v in request.values.items() if k != "action"}))
        try:
            if fmt == "zpl":
                data, ext, mime = L.to_zpl(items, lay, st.get("zpl_font", "")).encode("utf-8"), "zpl", "text/plain"
            elif fmt == "tspl":
                data, ext, mime = L.to_tspl(items, lay, st.get("tspl_font", "")).encode("utf-8"), "tspl", "text/plain"
            elif fmt == "pdf_roll":
                data, ext, mime = L.to_pdf_roll(items, lay), "pdf", "application/pdf"
            else:
                data, ext, mime = L.to_pdf_sheet(items, sheet), "pdf", "application/pdf"
        except ValueError as e:
            flash(str(e), "err")
            return redirect(url_for("tf.labels"))
        n = sum(max(1, i.copies) for i in items)
        if action == "print":
            target = request.values.get("target") or st.get("printer_zpl" if fmt == "zpl" else "printer_tspl", "")
            try:
                msg = printing.dispatch(target, data, ext)
                store.log_label_job(c, fmt, target, n, "ok", f"{len(data)} B → {target}")  # без языка: журнал читают на любом
                flash(_("Печать: {n} этикеток — {msg}", n=n, msg=msg), "ok")
            except Exception as e:  # noqa: BLE001
                store.log_label_job(c, fmt, target, n, "error", str(e))
                flash(_("Принтер не ответил: {e}", e=e), "err")
            return redirect(url_for("tf.labels", **{k: v for k, v in request.values.items()
                                                    if k not in ("action", "target")}))
        store.log_label_job(c, fmt, "download", n)
        disp = "inline" if ext == "pdf" and action == "view" else "attachment"
        return Response(data, mimetype=mime,
                        headers={"Content-Disposition": f"{disp}; filename=labels.{ext}"})
    preview = L.to_zpl(items[:1], store.layouts(c)[0], store.settings(c).get("zpl_font", "")) if items else ""
    return render_template("labels.html", items=items, sel=sel, fmt=fmt, args=request.values,
                           shipments=store.shipments(c), st=store.settings(c), preview=preview,
                           jobs=c.execute("SELECT * FROM label_jobs ORDER BY id DESC LIMIT 10").fetchall())


# ---------------------------------------------------------------- справочники и настройки

@bp.route("/settings", methods=["GET", "POST"])
def settings():
    c = con()
    if request.method == "POST":
        keys = [k for k in store.settings(c) if k != "ean_counter"]
        vals = {k: request.form.get(k, "") for k in keys if k in request.form}
        if "sheet_border" in keys:
            vals["sheet_border"] = "1" if request.form.get("sheet_border") else "0"
        if "prices_include_vat" in keys:
            vals["prices_include_vat"] = "1" if request.form.get("prices_include_vat") else "0"
        store.save_settings(c, vals)
        flash(_("Настройки сохранены"), "ok")
        return redirect(url_for("tf.settings"))
    return render_template("settings.html", st=store.settings(c))


@bp.route("/refs", methods=["GET", "POST"])
def refs():
    c = con()
    if request.method == "POST":
        kind = request.form.get("kind")
        try:
            if kind == "color":
                store.add_color(c, int(request.form["family_id"]), request.form["code"], request.form["name"],
                                request.form.get("hex", "#cccccc"), request.form.get("name_ro", ""),
                                request.form.get("name_en", ""))
            elif kind == "size":
                store.add_size(c, int(request.form["scale_id"]), request.form["code"])
            elif kind == "category":
                store.add_category(c, request.form["code"], request.form["name"], _i(request.form.get("scale_id")),
                                   _f("markup_pct", 100), _f("duty_pct"), request.form.get("hs_code", ""),
                                   request.form.get("name_ro", ""), request.form.get("name_en", ""))
            elif kind == "category_update":
                store.update_category(c, int(request.form["id"]), _f("markup_pct", 100), _f("duty_pct"),
                                      _i(request.form.get("scale_id")))
            flash(_("Сохранено"), "ok")
        except Exception as e:  # noqa: BLE001
            flash(_("Не сохранено: {e}", e=e), "err")
        return redirect(url_for("tf.refs") + "#" + (kind or ""))
    return render_template("refs.html", families=store.color_families(c), scales=store.size_scales(c),
                           categories=store.categories(c))


@bp.route("/help")
def help_page():
    return render_template("help.html")

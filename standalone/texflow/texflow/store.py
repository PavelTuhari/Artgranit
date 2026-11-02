"""Операции над SQLite: каталог, приёмка из мешков, себестоимость, цены, этикетки."""
from __future__ import annotations

import csv
import io

from . import rules
from .i18n import _, name_sql as N
from .labels import LabelData, LabelLayout, SheetLayout


# ---------------------------------------------------------------- settings

def settings(con) -> dict:
    return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM settings")}


def setting_f(con, key: str, default: float = 0.0) -> float:
    r = con.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    try:
        return float(r["value"]) if r else default
    except ValueError:
        return default


def save_settings(con, values: dict) -> None:
    for k, v in values.items():
        con.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, str(v).strip()))
    con.commit()


# ---------------------------------------------------------------- справочники

def categories(con):
    return con.execute(f"""SELECT c.*, {N('c')} AS title, {N('s')} AS scale_name FROM categories c
                           LEFT JOIN size_scales s ON s.id = c.size_scale_id ORDER BY title""").fetchall()


def size_scales(con):
    scales = con.execute(f"SELECT *, {N()} AS title FROM size_scales ORDER BY id").fetchall()
    return [{"id": s["id"], "name": s["name"], "title": s["title"],
             "sizes": con.execute("SELECT * FROM sizes WHERE scale_id = ? ORDER BY sort",
                                  (s["id"],)).fetchall()} for s in scales]


def sizes_for_scale(con, scale_id):
    return con.execute("SELECT * FROM sizes WHERE scale_id = ? ORDER BY sort", (scale_id,)).fetchall()


def color_families(con):
    fams = con.execute(f"SELECT *, {N()} AS title FROM color_families ORDER BY sort, name").fetchall()
    return [{"id": f["id"], "name": f["name"], "title": f["title"], "hex": f["hex"],
             "colors": con.execute(f"SELECT *, {N()} AS title FROM colors WHERE family_id = ? ORDER BY code",
                                   (f["id"],)).fetchall()} for f in fams]


def add_color(con, family_id: int, code: str, name: str, hexv: str, name_ro: str = "", name_en: str = "") -> int:
    cid = con.execute("INSERT INTO colors(family_id, code, name, name_ro, name_en, hex) VALUES (?, ?, ?, ?, ?, ?)",
                      (family_id, code.strip(), name.strip(), (name_ro or "").strip(), (name_en or "").strip(),
                       hexv or "#cccccc")).lastrowid
    con.commit()
    return cid


def add_size(con, scale_id: int, code: str) -> int:
    n = con.execute("SELECT COALESCE(MAX(sort), -1) + 1 FROM sizes WHERE scale_id = ?", (scale_id,)).fetchone()[0]
    sid = con.execute("INSERT INTO sizes(scale_id, code, sort) VALUES (?, ?, ?)",
                      (scale_id, code.strip().upper(), n)).lastrowid
    con.commit()
    return sid


def update_category(con, cat_id: int, markup_pct: float, duty_pct: float, size_scale_id: int | None = None):
    con.execute("UPDATE categories SET markup_pct = ?, duty_pct = ?, size_scale_id = COALESCE(?, size_scale_id)"
                " WHERE id = ?", (markup_pct, duty_pct, size_scale_id, cat_id))
    con.commit()


def add_category(con, code, name, scale_id, markup, duty, hs="", name_ro="", name_en="") -> int:
    cid = con.execute("INSERT INTO categories(code, name, name_ro, name_en, size_scale_id, markup_pct, duty_pct,"
                      " hs_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                      (code.strip().upper(), name.strip(), (name_ro or "").strip(), (name_en or "").strip(),
                       scale_id, markup, duty, hs)).lastrowid
    con.commit()
    return cid


def supplier_id(con, name: str, country: str = "TR") -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    r = con.execute("SELECT id FROM suppliers WHERE name = ?", (name,)).fetchone()
    if r:
        return r["id"]
    return con.execute("INSERT INTO suppliers(name, country) VALUES (?, ?)", (name, country)).lastrowid


def find_category(con, text: str):
    t = (text or "").strip()
    if not t:
        return None
    return con.execute("SELECT * FROM categories WHERE UPPER(code) = UPPER(?) OR LOWER(name) = LOWER(?)"
                       " OR LOWER(name_ro) = LOWER(?) OR LOWER(name_en) = LOWER(?)", (t, t, t, t)).fetchone()


# ---------------------------------------------------------------- поставки

def create_shipment(con, code: str, supplier: str = "", country: str = "TR", currency: str = "USD",
                    fx_rate: float = 1.0, arrival_date: str = "", **costs) -> int:
    sid = con.execute(
        """INSERT INTO shipments(code, supplier_id, country, currency, fx_rate, arrival_date,
                                 freight, customs, broker, other_costs, alloc_method, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code.strip(), supplier_id(con, supplier, country), country, currency.upper(), float(fx_rate or 1),
         arrival_date, float(costs.get("freight") or 0), float(costs.get("customs") or 0),
         float(costs.get("broker") or 0), float(costs.get("other_costs") or 0),
         costs.get("alloc_method") or "value", costs.get("note") or "")).lastrowid
    con.commit()
    return sid


def update_shipment(con, sid: int, **f) -> None:
    allowed = ["code", "country", "currency", "fx_rate", "arrival_date", "freight", "customs",
               "broker", "other_costs", "alloc_method", "status", "note"]
    sets = {k: v for k, v in f.items() if k in allowed}
    if not sets:
        return
    con.execute(f"UPDATE shipments SET {', '.join(k + ' = ?' for k in sets)} WHERE id = ?",
                (*sets.values(), sid))
    con.commit()


def shipments(con):
    return con.execute("""
        SELECT sh.*, sp.name AS supplier,
               (SELECT COUNT(*) FROM bags b WHERE b.shipment_id = sh.id) AS bags,
               (SELECT COALESCE(SUM(qty), 0) FROM packing_lines p WHERE p.shipment_id = sh.id) AS declared,
               (SELECT COALESCE(SUM(qty), 0) FROM intake_items i WHERE i.shipment_id = sh.id) AS counted
        FROM shipments sh LEFT JOIN suppliers sp ON sp.id = sh.supplier_id
        ORDER BY sh.id DESC""").fetchall()


def shipment(con, sid: int):
    return con.execute("""SELECT sh.*, sp.name AS supplier FROM shipments sh
                          LEFT JOIN suppliers sp ON sp.id = sh.supplier_id WHERE sh.id = ?""", (sid,)).fetchone()


def bags(con, sid: int):
    return con.execute("""
        SELECT b.*, (SELECT COALESCE(SUM(qty), 0) FROM intake_items i WHERE i.bag_id = b.id) AS counted,
               (SELECT COALESCE(SUM(qty), 0) FROM packing_lines p
                 WHERE p.shipment_id = b.shipment_id AND p.bag_no = b.bag_no) AS declared
        FROM bags b WHERE b.shipment_id = ? ORDER BY CAST(b.bag_no AS INTEGER), b.bag_no""", (sid,)).fetchall()


def ensure_bag(con, sid: int, bag_no: str, weight_kg: float | None = None, desc: str = "") -> int:
    bag_no = str(bag_no).strip()
    r = con.execute("SELECT id FROM bags WHERE shipment_id = ? AND bag_no = ?", (sid, bag_no)).fetchone()
    if r:
        if weight_kg:
            con.execute("UPDATE bags SET weight_kg = ? WHERE id = ?", (weight_kg, r["id"]))
        return r["id"]
    return con.execute("INSERT INTO bags(shipment_id, bag_no, weight_kg, declared_desc) VALUES (?, ?, ?, ?)",
                       (sid, bag_no, weight_kg or 0, desc)).lastrowid


def set_bag_status(con, bag_id: int, status: str) -> None:
    con.execute("UPDATE bags SET status = ? WHERE id = ?", (status, bag_id))
    con.commit()


# ---------------------------------------------------------------- упаковочный лист

PACKING_ALIASES = {
    "bag_no": ["bag_no", "bag", "мешок", "№ мешка", "no", "çuval", "cuval", "sack", "sac", "nr. sac", "包"],
    "category": ["category", "категория", "cat", "kategori", "categorie", "类别"],
    "description": ["description", "описание", "desc", "товар", "açıklama", "aciklama", "descriere",
                    "denumire", "品名"],
    "qty": ["qty", "кол-во", "количество", "quantity", "pcs", "adet", "шт", "cantitate", "buc", "数量"],
    "unit_price": ["unit_price", "price", "цена", "fiyat", "preț", "pret", "单价"],
    "weight_kg": ["weight_kg", "weight", "вес", "kg", "ağırlık", "agirlik", "greutate", "重量"],
}


def _norm_header(h: str) -> str | None:
    h = (h or "").strip().lower().lstrip("﻿")
    for key, names in PACKING_ALIASES.items():
        if h in names:
            return key
    return None


def _num(v, default=0.0) -> float:
    try:
        return float(str(v).replace(" ", "").replace(",", ".")) if str(v).strip() else default
    except ValueError:
        return default


def import_packing_csv(con, sid: int, text: str, replace: bool = True) -> dict:
    """Импорт примерного упаковочного листа (CSV/; или табуляция).

    Колонки (любой порядок, рус/англ/тур/кит заголовки): мешок, категория,
    описание, кол-во, цена, вес. Мешки создаются автоматически, вес мешка —
    сумма весов строк.
    """
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        return {"lines": 0, "bags": 0, "unknown_categories": []}
    header = [_norm_header(h) for h in rows[0]]
    if "qty" not in header:
        raise ValueError(_("в упаковочном листе нет колонки количества (qty / кол-во / adet)"))
    if replace:
        con.execute("DELETE FROM packing_lines WHERE shipment_id = ?", (sid,))
    unknown, bag_w, n = set(), {}, 0
    for raw in rows[1:]:
        if not any(c.strip() for c in raw):
            continue
        rec = {header[i]: raw[i] for i in range(min(len(raw), len(header))) if header[i]}
        qty = int(_num(rec.get("qty")))
        if qty <= 0:
            continue
        cat = find_category(con, rec.get("category", ""))
        if rec.get("category") and not cat:
            unknown.add(rec["category"].strip())
        bag_no = str(rec.get("bag_no", "")).strip()
        w = _num(rec.get("weight_kg"))
        con.execute("""INSERT INTO packing_lines(shipment_id, bag_no, category_id, description, qty,
                                                 unit_price_fx, weight_kg) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sid, bag_no, cat["id"] if cat else None,
                     (rec.get("description") or rec.get("category") or "").strip(),
                     qty, _num(rec.get("unit_price")), w))
        if bag_no:
            bag_w[bag_no] = bag_w.get(bag_no, 0.0) + w
        n += 1
    for bag_no, w in bag_w.items():
        ensure_bag(con, sid, bag_no, w or None)
    con.commit()
    return {"lines": n, "bags": len(bag_w), "unknown_categories": sorted(unknown)}


def packing_lines(con, sid: int):
    return con.execute(f"""SELECT p.*, {N('c')} AS category, c.code AS category_code FROM packing_lines p
                          LEFT JOIN categories c ON c.id = p.category_id
                          WHERE p.shipment_id = ? ORDER BY p.bag_no, p.id""", (sid,)).fetchall()


def declared_unit_price(con, sid: int, category_id: int) -> float:
    """Средняя цена категории по упаковочному листу — подсказка для закупочной цены."""
    r = con.execute("""SELECT SUM(qty * unit_price_fx) / NULLIF(SUM(qty), 0) AS p FROM packing_lines
                       WHERE shipment_id = ? AND category_id = ? AND unit_price_fx > 0""",
                    (sid, category_id)).fetchone()
    return round(r["p"], 4) if r and r["p"] else 0.0


def reconciliation(con, sid: int) -> dict:
    by_cat_decl = {r["k"]: r["q"] for r in con.execute(
        f"""SELECT COALESCE({N('c')}, ? || p.description) AS k, SUM(p.qty) AS q
           FROM packing_lines p LEFT JOIN categories c ON c.id = p.category_id
           WHERE p.shipment_id = ? GROUP BY k""", (_("— без категории: "), sid))}
    by_cat_cnt = {r["k"]: r["q"] for r in con.execute(
        f"""SELECT {N('c')} AS k, SUM(i.qty) AS q FROM intake_items i
           JOIN variants v ON v.id = i.variant_id JOIN products pr ON pr.id = v.product_id
           JOIN categories c ON c.id = pr.category_id WHERE i.shipment_id = ? GROUP BY k""", (sid,))}
    by_bag_decl = {r["k"]: r["q"] for r in con.execute(
        "SELECT bag_no AS k, SUM(qty) AS q FROM packing_lines WHERE shipment_id = ? AND bag_no <> '' GROUP BY k",
        (sid,))}
    by_bag_cnt = {r["k"]: r["q"] for r in con.execute(
        """SELECT COALESCE(b.bag_no, '—') AS k, SUM(i.qty) AS q FROM intake_items i
           LEFT JOIN bags b ON b.id = i.bag_id WHERE i.shipment_id = ? GROUP BY k""", (sid,))}
    return {"by_category": rules.reconcile(by_cat_decl, by_cat_cnt),
            "by_bag": rules.reconcile(by_bag_decl, by_bag_cnt),
            "declared_total": sum(by_cat_decl.values()), "counted_total": sum(by_cat_cnt.values())}


# ---------------------------------------------------------------- товары и варианты

def next_style_code(con, category_code: str) -> str:
    r = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    while True:
        r += 1
        code = f"{category_code}{r:04d}"
        if not con.execute("SELECT 1 FROM products WHERE style_code = ?", (code,)).fetchone():
            return code


def create_product(con, name: str, category_id: int, style_code: str = "", supplier: str = "",
                   base_cost_fx: float = 0.0, composition: str = "", description: str = "",
                   season: str = "", gender: str = "") -> int:
    cat = con.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if not cat:
        raise ValueError(_("категория не найдена"))
    code = rules.sku_part(style_code) or next_style_code(con, cat["code"])
    pid = con.execute(
        """INSERT INTO products(style_code, name, category_id, supplier_id, composition, description,
                                season, gender, base_cost_fx) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (code, name.strip(), category_id, supplier_id(con, supplier), composition, description,
         season, gender, float(base_cost_fx or 0))).lastrowid
    con.commit()
    return pid


def update_product(con, pid: int, **f) -> None:
    allowed = ["name", "category_id", "composition", "description", "season", "gender",
               "base_cost_fx", "retail_price", "price_locked"]
    sets = {k: v for k, v in f.items() if k in allowed}
    if sets:
        con.execute(f"UPDATE products SET {', '.join(k + ' = ?' for k in sets)} WHERE id = ?",
                    (*sets.values(), pid))
        con.commit()


def product(con, pid: int):
    return con.execute(f"""SELECT p.*, {N('c')} AS category, c.code AS category_code, c.size_scale_id,
                                 c.markup_pct, s.name AS supplier
                          FROM products p JOIN categories c ON c.id = p.category_id
                          LEFT JOIN suppliers s ON s.id = p.supplier_id WHERE p.id = ?""", (pid,)).fetchone()


def products(con, q: str = "", category_id: int | None = None):
    sql = f"""SELECT p.*, {N('c')} AS category,
                    (SELECT COUNT(*) FROM variants v WHERE v.product_id = p.id) AS variants,
                    (SELECT COALESCE(SUM(i.qty), 0) FROM intake_items i JOIN variants v ON v.id = i.variant_id
                      WHERE v.product_id = p.id) AS stock,
                    (SELECT GROUP_CONCAT(DISTINCT co.hex) FROM variants v JOIN colors co ON co.id = v.color_id
                      WHERE v.product_id = p.id) AS swatches
             FROM products p JOIN categories c ON c.id = p.category_id WHERE 1 = 1"""
    args = []
    if q:
        sql += " AND (p.name LIKE ? OR p.style_code LIKE ? OR EXISTS (SELECT 1 FROM variants v WHERE " \
               "v.product_id = p.id AND (v.ean13 = ? OR v.sku LIKE ?)))"
        args += [f"%{q}%", f"%{q}%", q, f"%{q}%"]
    if category_id:
        sql += " AND p.category_id = ?"
        args.append(category_id)
    return con.execute(sql + " ORDER BY p.id DESC", args).fetchall()


def next_ean(con) -> str:
    prefix = settings(con).get("ean_prefix", "200")
    n = int(setting_f(con, "ean_counter", 0))
    while True:
        n += 1
        code = rules.make_ean13(prefix, n)
        if not con.execute("SELECT 1 FROM variants WHERE ean13 = ?", (code,)).fetchone():
            break
    con.execute("UPDATE settings SET value = ? WHERE key = 'ean_counter'", (str(n),))
    return code


def ensure_variant(con, pid: int, color_id: int, size_id: int) -> int:
    r = con.execute("SELECT id FROM variants WHERE product_id = ? AND color_id = ? AND size_id = ?",
                    (pid, color_id, size_id)).fetchone()
    if r:
        return r["id"]
    p = con.execute("SELECT style_code FROM products WHERE id = ?", (pid,)).fetchone()
    c = con.execute("SELECT code FROM colors WHERE id = ?", (color_id,)).fetchone()
    s = con.execute("SELECT code FROM sizes WHERE id = ?", (size_id,)).fetchone()
    if not (p and c and s):
        raise ValueError(_("товар, цвет или размер не найден"))
    return con.execute("INSERT INTO variants(product_id, color_id, size_id, sku, ean13) VALUES (?, ?, ?, ?, ?)",
                       (pid, color_id, size_id, rules.make_sku(p["style_code"], c["code"], s["code"]),
                        next_ean(con))).lastrowid


def variants(con, pid: int):
    return con.execute(f"""
        SELECT v.*, {N('co')} AS color, co.code AS color_code, co.hex, {N('cf')} AS family,
               sz.code AS size, sz.sort AS size_sort,
               (SELECT COALESCE(SUM(qty), 0) FROM intake_items i WHERE i.variant_id = v.id) AS stock
        FROM variants v JOIN colors co ON co.id = v.color_id JOIN color_families cf ON cf.id = co.family_id
        JOIN sizes sz ON sz.id = v.size_id WHERE v.product_id = ? ORDER BY co.code, sz.sort""", (pid,)).fetchall()


def variant_by_ean(con, code: str):
    return con.execute("""SELECT v.*, p.name, p.style_code, p.base_cost_fx FROM variants v
                          JOIN products p ON p.id = v.product_id WHERE v.ean13 = ? OR v.sku = ?""",
                       (code.strip(), code.strip().upper())).fetchone()


def product_matrix(con, pid: int) -> dict:
    """Матрица цвет × размер для карточки и экрана приёмки."""
    p = product(con, pid)
    sizes = sizes_for_scale(con, p["size_scale_id"]) if p["size_scale_id"] else []
    vs = variants(con, pid)
    colors, cells = {}, {}
    for v in vs:
        colors.setdefault(v["color_id"], {"id": v["color_id"], "name": v["color"], "code": v["color_code"],
                                          "hex": v["hex"], "family": v["family"]})
        cells[(v["color_id"], v["size_id"])] = v
    used = {v["size_id"] for v in vs}
    known = {s["id"] for s in sizes}
    extra = {r["size_id"]: {"id": r["size_id"], "code": r["size"]} for r in vs if r["size_id"] not in known}
    size_list = list(sizes) + list(extra.values())
    return {"product": p, "sizes": size_list, "colors": list(colors.values()), "cells": cells,
            "used_sizes": used}


# ---------------------------------------------------------------- приёмка

def add_intake(con, sid: int, bag_id: int | None, pid: int, grid: dict, unit_cost_fx: float | None = None) -> int:
    """grid: {(color_id, size_id): qty}. Создаёт недостающие варианты. Возвращает штук."""
    p = con.execute("SELECT base_cost_fx FROM products WHERE id = ?", (pid,)).fetchone()
    if not p:
        raise ValueError(_("товар не найден"))
    cost = float(unit_cost_fx if unit_cost_fx not in (None, "") else p["base_cost_fx"])
    total = 0
    for (color_id, size_id), qty in grid.items():
        qty = int(qty or 0)
        if not qty:
            continue
        vid = ensure_variant(con, pid, int(color_id), int(size_id))
        con.execute("INSERT INTO intake_items(shipment_id, bag_id, variant_id, qty, unit_cost_fx)"
                    " VALUES (?, ?, ?, ?, ?)", (sid, bag_id, vid, qty, cost))
        total += qty
    if bag_id and total:
        con.execute("UPDATE bags SET status = 'sorting' WHERE id = ? AND status = 'closed'", (bag_id,))
    con.commit()
    return total


def add_scan(con, sid: int, bag_id: int | None, code: str, qty: int = 1) -> dict:
    v = variant_by_ean(con, code)
    if not v:
        raise ValueError(_("штрихкод {code} не найден", code=code))
    con.execute("INSERT INTO intake_items(shipment_id, bag_id, variant_id, qty, unit_cost_fx) VALUES (?, ?, ?, ?, ?)",
                (sid, bag_id, v["id"], qty, v["base_cost_fx"]))
    con.commit()
    return dict(v)


def intake_log(con, sid: int, bag_id: int | None = None, limit: int = 200):
    sql = f"""SELECT i.*, v.sku, v.ean13, p.name, p.id AS product_id, {N('co')} AS color, sz.code AS size,
                    b.bag_no FROM intake_items i JOIN variants v ON v.id = i.variant_id
             JOIN products p ON p.id = v.product_id JOIN colors co ON co.id = v.color_id
             JOIN sizes sz ON sz.id = v.size_id LEFT JOIN bags b ON b.id = i.bag_id
             WHERE i.shipment_id = ?"""
    args = [sid]
    if bag_id:
        sql += " AND i.bag_id = ?"
        args.append(bag_id)
    return con.execute(sql + " ORDER BY i.id DESC LIMIT ?", (*args, limit)).fetchall()


def delete_intake(con, item_id: int) -> None:
    con.execute("DELETE FROM intake_items WHERE id = ?", (item_id,))
    con.commit()


# ---------------------------------------------------------------- себестоимость и цены

def compute_landed(con, sid: int, save: bool = True) -> list[rules.LandedResult]:
    sh = shipment(con, sid)
    items = con.execute("""
        SELECT i.id, i.qty, i.unit_cost_fx, i.bag_id, c.duty_pct,
               b.weight_kg AS bag_w,
               (SELECT SUM(qty) FROM intake_items x WHERE x.bag_id = i.bag_id AND x.qty > 0) AS bag_pcs
        FROM intake_items i JOIN variants v ON v.id = i.variant_id JOIN products p ON p.id = v.product_id
        JOIN categories c ON c.id = p.category_id LEFT JOIN bags b ON b.id = i.bag_id
        WHERE i.shipment_id = ? AND i.qty > 0""", (sid,)).fetchall()
    lines = [rules.CostLine(key=r["id"], qty=r["qty"], unit_cost_fx=r["unit_cost_fx"], duty_pct=r["duty_pct"],
                            weight_kg=(r["bag_w"] or 0) * r["qty"] / r["bag_pcs"] if r["bag_pcs"] else 0)
             for r in items]
    res = rules.allocate_landed_cost(lines, rules.ShipmentCosts(
        fx_rate=sh["fx_rate"], freight=sh["freight"], customs=sh["customs"], broker=sh["broker"],
        other=sh["other_costs"], method=sh["alloc_method"]))
    if save:
        for r in res:
            con.execute("UPDATE intake_items SET landed_unit_cost = ? WHERE id = ?", (r.landed_unit, r.key))
        con.commit()
    return res


def price_proposal(con, sid: int) -> list[dict]:
    """Средняя себестоимость каждого товара поставки и предлагаемая розничная цена."""
    compute_landed(con, sid)
    st = settings(con)
    vat = float(st.get("vat_pct", 0)) if st.get("prices_include_vat", "1") == "1" else 0.0
    rows = con.execute(f"""
        SELECT p.id, p.style_code, p.name, p.retail_price, p.price_locked, {N('c')} AS category, c.markup_pct,
               SUM(i.qty) AS qty, SUM(i.qty * i.landed_unit_cost) / SUM(i.qty) AS landed,
               SUM(i.qty * i.unit_cost_fx) / SUM(i.qty) AS cost_fx
        FROM intake_items i JOIN variants v ON v.id = i.variant_id JOIN products p ON p.id = v.product_id
        JOIN categories c ON c.id = p.category_id WHERE i.shipment_id = ? AND i.qty > 0
        GROUP BY p.id ORDER BY category, p.name""", (sid,)).fetchall()
    out = []
    for r in rows:
        calc = rules.retail_price(r["landed"] or 0, r["markup_pct"], vat,
                                  float(st.get("round_step", 10)), float(st.get("round_ending", 0.1)),
                                  float(st.get("min_markup_pct", 0)))
        out.append({**dict(r), **calc})
    return out


def apply_prices(con, sid: int, overrides: dict | None = None) -> int:
    """Записать цены в карточки. Заблокированные цены не трогаются."""
    n = 0
    overrides = overrides or {}
    for row in price_proposal(con, sid):
        if row["price_locked"]:
            continue
        price = overrides.get(row["id"], row["price"])
        con.execute("UPDATE products SET retail_price = ? WHERE id = ?", (price, row["id"]))
        n += 1
    con.execute("UPDATE shipments SET status = 'priced' WHERE id = ?", (sid,))
    con.commit()
    return n


def shipment_totals(con, sid: int) -> dict:
    sh = shipment(con, sid)
    r = con.execute("""SELECT COALESCE(SUM(qty), 0) AS pcs, COALESCE(SUM(qty * unit_cost_fx), 0) AS goods_fx,
                              COALESCE(SUM(qty * landed_unit_cost), 0) AS landed
                       FROM intake_items WHERE shipment_id = ? AND qty > 0""", (sid,)).fetchone()
    lump = sh["freight"] + sh["customs"] + sh["broker"] + sh["other_costs"]
    return {"pcs": r["pcs"], "goods_fx": round(r["goods_fx"], 2),
            "goods_local": round(r["goods_fx"] * sh["fx_rate"], 2), "lump": round(lump, 2),
            "landed": round(r["landed"], 2),
            "avg_landed": round(r["landed"] / r["pcs"], 2) if r["pcs"] else 0}


# ---------------------------------------------------------------- этикетки

def label_rows(con, variant_qty: dict) -> list[LabelData]:
    """variant_qty: {variant_id: копий}."""
    st = settings(con)
    label_lang = st.get("label_lang", "ru") if st.get("label_lang") in ("ru", "ro", "en") else "ru"
    out = []
    for vid, qty in variant_qty.items():
        if int(qty or 0) <= 0:
            continue
        r = con.execute(f"""SELECT v.ean13, v.sku, p.name, p.style_code, p.composition, p.retail_price,
                                   {N('co', label_lang)} AS color, sz.code AS size, s.country
                           FROM variants v JOIN products p ON p.id = v.product_id
                           JOIN colors co ON co.id = v.color_id JOIN sizes sz ON sz.id = v.size_id
                           LEFT JOIN suppliers s ON s.id = p.supplier_id WHERE v.id = ?""", (vid,)).fetchone()
        if r:
            out.append(LabelData(ean13=r["ean13"], sku=r["sku"], name=r["name"], color=r["color"],
                                 size=r["size"], price=r["retail_price"], currency=st.get("currency", ""),
                                 brand=st.get("brand", ""), style=r["style_code"],
                                 composition=r["composition"], origin=r["country"] or "", copies=int(qty),
                                 ref=int(vid)))
    return out


def labels_for_shipment(con, sid: int, bag_id: int | None = None) -> dict:
    """Этикеток столько, сколько штук принято (по варианту)."""
    sql = "SELECT variant_id, SUM(qty) AS q FROM intake_items WHERE shipment_id = ?"
    args = [sid]
    if bag_id:
        sql += " AND bag_id = ?"
        args.append(bag_id)
    return {r["variant_id"]: r["q"] for r in con.execute(sql + " GROUP BY variant_id HAVING q > 0", args)}


def layouts(con) -> tuple[LabelLayout, SheetLayout]:
    f = lambda k, d: setting_f(con, k, d)  # noqa: E731
    return (LabelLayout(f("label_width_mm", 58), f("label_height_mm", 40), f("label_gap_mm", 2),
                        int(f("label_dpi", 203))),
            SheetLayout(int(f("sheet_cols", 3)), int(f("sheet_rows", 8)), f("sheet_label_w_mm", 70),
                        f("sheet_label_h_mm", 37), f("sheet_margin_left_mm", 0), f("sheet_margin_top_mm", 0.5),
                        border=f("sheet_border", 1) == 1))


def log_label_job(con, fmt: str, target: str, n: int, status: str = "ok", msg: str = "") -> None:
    con.execute("INSERT INTO label_jobs(format, target, labels, status, message) VALUES (?, ?, ?, ?, ?)",
                (fmt, target, n, status, msg[:500]))
    con.commit()


# ---------------------------------------------------------------- экспорт каталога

def export_catalog_csv(con) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["style_code", "name", "category", "color_family", "color_code", "color", "size", "sku",
                "ean13", "price", "stock", "composition"])
    for r in con.execute(f"""
        SELECT p.style_code, p.name, {N('c')} AS cat, {N('cf')} AS fam, co.code AS ccode, {N('co')} AS color,
               sz.code AS size, v.sku, v.ean13, p.retail_price, p.composition,
               (SELECT COALESCE(SUM(qty), 0) FROM intake_items i WHERE i.variant_id = v.id) AS stock
        FROM variants v JOIN products p ON p.id = v.product_id JOIN categories c ON c.id = p.category_id
        JOIN colors co ON co.id = v.color_id JOIN color_families cf ON cf.id = co.family_id
        JOIN sizes sz ON sz.id = v.size_id ORDER BY p.style_code, co.code, sz.sort"""):
        w.writerow([r["style_code"], r["name"], r["cat"], r["fam"], r["ccode"], r["color"], r["size"], r["sku"],
                    r["ean13"], "" if r["retail_price"] is None else f"{r['retail_price']:.2f}", r["stock"],
                    r["composition"]])
    return buf.getvalue()


def dashboard(con) -> dict:
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    return {"products": one("SELECT COUNT(*) FROM products"),
            "variants": one("SELECT COUNT(*) FROM variants"),
            "pcs": one("SELECT COALESCE(SUM(qty), 0) FROM intake_items"),
            "open_shipments": one("SELECT COUNT(*) FROM shipments WHERE status <> 'closed'"),
            "unpriced": one("SELECT COUNT(*) FROM products WHERE retail_price IS NULL"),
            "bags_open": one("SELECT COUNT(*) FROM bags WHERE status <> 'done'")}

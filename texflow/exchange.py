"""Выгрузка и загрузка результатов: Excel (.xlsx) и CSV.

Выгрузка: каталог (варианты), цены, поставки, приёмка, упаковочный лист, сверка, предложение цен
и «полный отчёт» — одна книга Excel со всеми листами.
Загрузка: упаковочный лист, цены (правка в Excel и обратно), каталог (модели и варианты, по желанию —
сразу в приёмку поставки), результаты приёмки с другого рабочего места.

Заголовки колонок пишутся на языке интерфейса, а при загрузке понимаются на любом из трёх языков
и по техническому имени (style_code, sku, qty…), поэтому файл можно выгрузить на румынском,
поправить и загрузить на русском.
"""
from __future__ import annotations

import csv
import io
import os

from . import store
from .i18n import _, current_lang, name_sql as N

# ключ колонки → (RU, RO, EN)
COLUMNS = {
    "style_code": ("Артикул", "Articol", "Style no."),
    "name": ("Название", "Denumire", "Name"),
    "name_ro": ("Название RO", "Denumire RO", "Name RO"),
    "name_en": ("Название EN", "Denumire EN", "Name EN"),
    "category": ("Категория", "Categorie", "Category"),
    "color_family": ("Группа цвета", "Grupă culoare", "Colour group"),
    "color_code": ("Код цвета", "Cod culoare", "Colour code"),
    "color": ("Цвет", "Culoare", "Colour"),
    "size": ("Размер", "Mărime", "Size"),
    "sku": ("SKU", "SKU", "SKU"),
    "ean13": ("EAN-13", "EAN-13", "EAN-13"),
    "retail_price": ("Цена", "Preț", "Price"),
    "price_locked": ("Цена зафиксирована", "Preț blocat", "Price locked"),
    "base_cost_fx": ("Закупка (валюта)", "Achiziție (valută)", "Purchase (currency)"),
    "stock": ("Остаток", "Stoc", "Stock"),
    "qty": ("Кол-во", "Cantitate", "Qty"),
    "composition": ("Состав", "Compoziție", "Composition"),
    "shipment": ("Поставка", "Livrare", "Shipment"),
    "supplier": ("Поставщик", "Furnizor", "Supplier"),
    "country": ("Страна", "Țara", "Country"),
    "currency": ("Валюта", "Valută", "Currency"),
    "fx_rate": ("Курс", "Curs", "Rate"),
    "status": ("Статус", "Stare", "Status"),
    "bag_no": ("Мешок", "Sac", "Bag"),
    "description": ("Описание", "Descriere", "Description"),
    "unit_price": ("Цена за шт.", "Preț pe buc.", "Unit price"),
    "weight_kg": ("Вес, кг", "Greutate, kg", "Weight, kg"),
    "unit_cost_fx": ("Закупка за шт.", "Achiziție pe buc.", "Purchase per pc"),
    "landed_unit_cost": ("Себестоимость за шт.", "Cost pe buc.", "Landed cost per pc"),
    "created_at": ("Время", "Ora", "Time"),
    "declared": ("По листу", "Conform listei", "Per list"),
    "counted": ("Факт", "Fapt", "Actual"),
    "diff": ("Разница", "Diferență", "Difference"),
    "group": ("Раздел", "Secțiune", "Section"),
    "key": ("Ключ", "Cheie", "Key"),
    "markup_pct": ("Наценка %", "Adaos %", "Markup %"),
    "landed": ("Себестоимость", "Cost", "Landed cost"),
    "price": ("Предложено", "Propus", "Proposed"),
    "real_markup_pct": ("Факт. наценка %", "Adaos real %", "Actual markup %"),
    "pcs": ("Принято шт.", "Recepționat buc.", "Pieces received"),
    "goods_local": ("Товар (местн.)", "Marfă (local)", "Goods (local)"),
    "lump": ("Общие затраты", "Cheltuieli comune", "Shared costs"),
}
_LANG_IDX = {"ru": 0, "ro": 1, "en": 2}

DATASETS = {
    "catalog": ("Каталог", ["style_code", "name", "name_ro", "name_en", "category", "color_family", "color_code",
                            "color", "size", "sku", "ean13", "retail_price", "stock", "composition"]),
    "prices": ("Цены", ["style_code", "name", "category", "base_cost_fx", "retail_price", "price_locked"]),
    "shipments": ("Поставки", ["shipment", "supplier", "country", "currency", "fx_rate", "status", "pcs",
                               "goods_local", "lump", "landed"]),
    "intake": ("Приёмка", ["created_at", "shipment", "bag_no", "sku", "ean13", "name", "color", "size", "qty",
                           "unit_cost_fx", "landed_unit_cost"]),
    "packing": ("Упаковочный лист", ["shipment", "bag_no", "category", "description", "qty", "unit_price",
                                     "weight_kg"]),
    "reconciliation": ("Сверка", ["shipment", "group", "key", "declared", "counted", "diff", "status"]),
    "pricing": ("Предложение цен", ["shipment", "style_code", "name", "category", "qty", "landed", "markup_pct",
                                     "price", "real_markup_pct"]),
}


def header(key: str, lang: str | None = None) -> str:
    return COLUMNS.get(key, (key, key, key))[_LANG_IDX.get(lang or current_lang(), 0)]


def dataset_title(ds: str) -> str:
    return _(DATASETS[ds][0])


# ======================================================================= выборки

def rows(con, ds: str, sid: int | None = None) -> list[dict]:
    """Строки набора данных (ключи — технические имена колонок)."""
    if ds == "catalog":
        q = f"""SELECT p.style_code, p.name, p.name_ro, p.name_en, {N('c')} AS category, {N('cf')} AS color_family,
                       co.code AS color_code, {N('co')} AS color, sz.code AS size, v.sku, v.ean13, p.retail_price,
                       (SELECT COALESCE(SUM(qty), 0) FROM intake_items i WHERE i.variant_id = v.id) AS stock,
                       p.composition
                FROM variants v JOIN products p ON p.id = v.product_id JOIN categories c ON c.id = p.category_id
                JOIN colors co ON co.id = v.color_id JOIN color_families cf ON cf.id = co.family_id
                JOIN sizes sz ON sz.id = v.size_id"""
        args: tuple = ()
        if sid:
            q += " WHERE v.id IN (SELECT variant_id FROM intake_items WHERE shipment_id = ?)"
            args = (sid,)
        return [dict(r) for r in con.execute(q + " ORDER BY p.style_code, co.code, sz.sort", args)]
    if ds == "prices":
        return [dict(r) for r in con.execute(
            f"""SELECT p.style_code, {N('p')} AS name, {N('c')} AS category, p.base_cost_fx, p.retail_price,
                       p.price_locked FROM products p JOIN categories c ON c.id = p.category_id ORDER BY p.style_code""")]
    if ds == "shipments":
        out = []
        for s in store.shipments(con):
            if sid and s["id"] != sid:
                continue
            tot = store.shipment_totals(con, s["id"])
            out.append({"shipment": s["code"], "supplier": s["supplier"] or "", "country": s["country"],
                        "currency": s["currency"], "fx_rate": s["fx_rate"], "status": s["status"],
                        "pcs": tot["pcs"], "goods_local": tot["goods_local"], "lump": tot["lump"],
                        "landed": tot["landed"]})
        return out
    if ds == "intake":
        q = f"""SELECT i.created_at, sh.code AS shipment, COALESCE(b.bag_no, '') AS bag_no, v.sku, v.ean13,
                       {N('p')} AS name, {N('co')} AS color, sz.code AS size, i.qty, i.unit_cost_fx, i.landed_unit_cost
                FROM intake_items i JOIN shipments sh ON sh.id = i.shipment_id JOIN variants v ON v.id = i.variant_id
                JOIN products p ON p.id = v.product_id JOIN colors co ON co.id = v.color_id
                JOIN sizes sz ON sz.id = v.size_id LEFT JOIN bags b ON b.id = i.bag_id"""
        args = ()
        if sid:
            q += " WHERE i.shipment_id = ?"
            args = (sid,)
        return [dict(r) for r in con.execute(q + " ORDER BY i.id", args)]
    if ds == "packing":
        q = f"""SELECT sh.code AS shipment, p.bag_no, COALESCE({N('c')}, '') AS category, p.description, p.qty,
                       p.unit_price_fx AS unit_price, p.weight_kg
                FROM packing_lines p JOIN shipments sh ON sh.id = p.shipment_id
                LEFT JOIN categories c ON c.id = p.category_id"""
        args = ()
        if sid:
            q += " WHERE p.shipment_id = ?"
            args = (sid,)
        return [dict(r) for r in con.execute(q + " ORDER BY sh.code, p.bag_no, p.id", args)]
    if ds == "reconciliation":
        out = []
        for s in store.shipments(con):
            if sid and s["id"] != sid:
                continue
            rec = store.reconciliation(con, s["id"])
            for group, key in (("by_category", "Сверка по категориям"), ("by_bag", "Сверка по мешкам")):
                for r in rec[group]:
                    out.append({"shipment": s["code"], "group": _(key), "key": r["key"], "declared": r["declared"],
                                "counted": r["counted"], "diff": r["diff"], "status": r["status"]})
        return out
    if ds == "pricing":
        out = []
        for s in store.shipments(con):
            if sid and s["id"] != sid:
                continue
            for r in store.price_proposal(con, s["id"]):
                out.append({"shipment": s["code"], "style_code": r["style_code"], "name": r["name"],
                            "category": r["category"], "qty": r["qty"], "landed": r["landed"],
                            "markup_pct": r["markup_pct"], "price": r["price"],
                            "real_markup_pct": r["real_markup_pct"]})
        return out
    raise ValueError(f"dataset: {ds}")


# ======================================================================= запись CSV / XLSX

def to_csv(con, ds: str, sid: int | None = None) -> str:
    cols = DATASETS[ds][1]
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([header(c) for c in cols])
    for r in rows(con, ds, sid):
        w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    return "﻿" + buf.getvalue()


def _sheet(wb, title: str, cols: list[str], data: list[dict]):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    ws = wb.create_sheet(title[:31])
    ws.append([header(c) for c in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="EEEEEA")
        cell.alignment = Alignment(vertical="center")
    for r in data:
        ws.append([r.get(c) for c in cols])
    ws.freeze_panes = "A2"
    if data:
        ws.auto_filter.ref = ws.dimensions
    for i, c in enumerate(cols, 1):
        width = max([len(str(header(c)))] + [len(str(r.get(c) or "")) for r in data[:500]])
        ws.column_dimensions[get_column_letter(i)].width = min(48, max(8, width + 2))
        if c in ("ean13", "sku", "style_code", "bag_no", "color_code", "size"):
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].number_format = "@"          # не превращать EAN в 2.00000E+12
        elif c in ("retail_price", "base_cost_fx", "unit_cost_fx", "landed_unit_cost", "landed", "price",
                   "unit_price", "goods_local", "lump", "fx_rate"):
            for row in ws.iter_rows(min_row=2, min_col=i, max_col=i):
                row[0].number_format = "0.00"
    return ws


def to_xlsx(con, datasets: list[str] | None = None, sid: int | None = None) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for ds in datasets or list(DATASETS):
        _sheet(wb, dataset_title(ds), DATASETS[ds][1], rows(con, ds, sid))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export(con, ds: str, fmt: str, sid: int | None = None) -> tuple[bytes, str, str]:
    """(данные, имя файла, mime). ds = один набор или 'full' — вся книга (только xlsx)."""
    suffix = f"_{sid}" if sid else ""
    if fmt == "xlsx":
        data = to_xlsx(con, None if ds == "full" else [ds], sid)
        return data, f"texflow_{ds}{suffix}.xlsx", \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if ds == "full":
        raise ValueError(_("Полный отчёт — только в Excel"))
    return to_csv(con, ds, sid).encode("utf-8"), f"texflow_{ds}{suffix}.csv", "text/csv"


# ======================================================================= чтение файлов

def _norm(h) -> str:
    return str(h or "").strip().lower().lstrip("﻿")


def _alias_map() -> dict:
    m = {}
    for key, names in COLUMNS.items():
        for n in (key, *names):
            m.setdefault(_norm(n), key)
    for key, names in store.PACKING_ALIASES.items():
        target = {"unit_price": "unit_price", "category": "category"}.get(key, key)
        for n in names:
            m.setdefault(_norm(n), target)
    return m


def read_table(data: bytes, filename: str, sheet: str | None = None) -> list[dict]:
    """Прочитать CSV или XLSX в список словарей с техническими ключами колонок."""
    amap = _alias_map()
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".xlsx", ".xlsm"):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.worksheets[0]
        it = ws.iter_rows(values_only=True)
        try:
            head = next(it)
        except StopIteration:
            return []
        table = [list(r) for r in it]
    else:
        text = None
        for enc in ("utf-8-sig", "cp1251", "cp1254", "gb18030", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        except csv.Error:
            dialect = csv.excel
            dialect.delimiter = ";" if sample.count(";") >= sample.count(",") else ","
        all_rows = list(csv.reader(io.StringIO(text), dialect))
        if not all_rows:
            return []
        head, table = all_rows[0], all_rows[1:]
    keys = [amap.get(_norm(h)) for h in head]
    out = []
    for r in table:
        if not r or all(v in (None, "") for v in r):
            continue
        out.append({k: r[i] for i, k in enumerate(keys) if k and i < len(r)})
    return out


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _f(v, default=None):
    if v in (None, ""):
        return default
    try:
        return float(str(v).replace(" ", "").replace(",", "."))
    except ValueError:
        return default


def _b(v) -> bool:
    return _s(v).lower() in ("1", "true", "yes", "да", "da", "x", "+")


# ======================================================================= загрузка

def import_packing(con, sid: int, data: bytes, filename: str, replace: bool = True) -> dict:
    """Упаковочный лист из CSV или XLSX (те же правила, что и в веб-версии)."""
    if filename.lower().endswith((".xlsx", ".xlsm")):
        recs = read_table(data, filename)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        w.writerow(["bag_no", "category", "description", "qty", "unit_price", "weight_kg"])
        for r in recs:
            w.writerow([_s(r.get("bag_no")), _s(r.get("category")), _s(r.get("description")), _s(r.get("qty")),
                        _s(r.get("unit_price")), _s(r.get("weight_kg"))])
        text = buf.getvalue()
    else:
        text = None
        for enc in ("utf-8-sig", "cp1251", "cp1254", "gb18030", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    return store.import_packing_csv(con, sid, text, replace)


def import_prices(con, data: bytes, filename: str) -> dict:
    """Цены из файла: по артикулу обновляются цена, фиксация и закупка (что заполнено)."""
    updated, unknown, skipped = 0, [], 0
    for r in read_table(data, filename):
        code = _s(r.get("style_code")).upper()
        if not code:
            skipped += 1
            continue
        p = con.execute("SELECT id FROM products WHERE style_code = ?", (code,)).fetchone()
        if not p:
            unknown.append(code)
            continue
        fields = {}
        price = _f(r.get("retail_price") if r.get("retail_price") not in (None, "") else r.get("price"))
        if price is not None:
            fields["retail_price"] = price
        if r.get("price_locked") not in (None, ""):
            fields["price_locked"] = 1 if _b(r.get("price_locked")) else 0
        cost = _f(r.get("base_cost_fx"))
        if cost is not None:
            fields["base_cost_fx"] = cost
        if fields:
            store.update_product(con, p["id"], **fields)
            updated += 1
        else:
            skipped += 1
    return {"updated": updated, "unknown": unknown, "skipped": skipped}


def import_catalog(con, data: bytes, filename: str, sid: int | None = None, bag_id: int | None = None) -> dict:
    """Каталог: модели и варианты. Если указана поставка и в строке есть «Кол-во» — сразу в приёмку."""
    created_p, created_v, received, errors = 0, 0, 0, []
    for n, r in enumerate(read_table(data, filename), start=2):
        code = _s(r.get("style_code")).upper()
        name = _s(r.get("name"))
        cat = store.find_category(con, _s(r.get("category")))
        try:
            p = con.execute("SELECT * FROM products WHERE style_code = ?", (code,)).fetchone() if code else None
            if not p:
                if not (name and cat):
                    raise ValueError(_("нужны название и категория"))
                pid = store.create_product(con, name, cat["id"], code, base_cost_fx=_f(r.get("base_cost_fx"), 0),
                                           composition=_s(r.get("composition")))
                created_p += 1
            else:
                pid = p["id"]
            upd = {k: _s(r.get(k)) for k in ("name_ro", "name_en") if _s(r.get(k))}
            if _f(r.get("retail_price")) is not None:
                upd["retail_price"] = _f(r.get("retail_price"))
            if upd:
                store.update_product(con, pid, **upd)
            ccode, size = _s(r.get("color_code")), _s(r.get("size")).upper()
            if not (ccode and size):
                continue
            color = con.execute("SELECT id FROM colors WHERE code = ?", (ccode,)).fetchone()
            if not color:
                raise ValueError(_("нет цвета с кодом {code}", code=ccode))
            scale = con.execute("SELECT c.size_scale_id FROM products p JOIN categories c ON c.id = p.category_id "
                                "WHERE p.id = ?", (pid,)).fetchone()[0]
            sz = con.execute("SELECT id FROM sizes WHERE scale_id = ? AND code = ?", (scale, size)).fetchone()
            size_id = sz["id"] if sz else store.add_size(con, scale, size)
            existed = con.execute("SELECT 1 FROM variants WHERE product_id = ? AND color_id = ? AND size_id = ?",
                                  (pid, color["id"], size_id)).fetchone()
            store.ensure_variant(con, pid, color["id"], size_id)
            created_v += 0 if existed else 1
            qty = int(_f(r.get("qty"), 0) or 0)
            if sid and qty:
                received += store.add_intake(con, sid, bag_id, pid, {(color["id"], size_id): qty},
                                             _f(r.get("unit_cost_fx") or r.get("base_cost_fx")))
        except (ValueError, KeyError) as e:
            errors.append(f"{n}: {e}")
    con.commit()
    return {"products": created_p, "variants": created_v, "received": received, "errors": errors}


def import_intake(con, sid: int, data: bytes, filename: str) -> dict:
    """Результаты приёмки с другого рабочего места: SKU или EAN-13, кол-во, мешок."""
    added, unknown = 0, []
    for r in read_table(data, filename):
        code = _s(r.get("ean13")) or _s(r.get("sku"))
        qty = int(_f(r.get("qty"), 0) or 0)
        if not code or not qty:
            continue
        v = store.variant_by_ean(con, code)
        if not v:
            unknown.append(code)
            continue
        bag = _s(r.get("bag_no"))
        bag_id = store.ensure_bag(con, sid, bag) if bag else None
        con.execute("INSERT INTO intake_items(shipment_id, bag_id, variant_id, qty, unit_cost_fx) VALUES (?, ?, ?, ?, ?)",
                    (sid, bag_id, v["id"], qty, _f(r.get("unit_cost_fx"), v["base_cost_fx"])))
        added += qty
    con.commit()
    return {"pcs": added, "unknown": unknown}

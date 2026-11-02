"""Шаблоны этикеток (редактор) и обмен Excel / CSV — общее ядро веб- и нативной версии."""
import io
import re

import pytest

from texflow import exchange, label_templates as LT, store
from texflow.labels import LabelData


def lb(**kw):
    d = dict(ean13="2000000000015", sku="TSH0001-800-M", name="Футболка", color="Чёрный", size="M", price=189.9,
             currency="MDL", brand="SHOP", composition="хлопок", copies=2)
    d.update(kw)
    return LabelData(**d)


# ------------------------------------------------------------------ шаблоны

def test_seeded_templates_and_default(con):
    ts = LT.list_templates(con)
    assert [t["name"] for t in ts][0] == "Standard 58×40" and ts[0]["is_default"] == 1
    assert len(ts) == 3 and all(t["elements"] > 0 for t in ts)
    t = LT.load(con)
    assert (t.width_mm, t.height_mm) == (58, 40) and any(e.kind == "barcode" for e in t.elements)


def test_save_roundtrip_duplicate_default_delete(con):
    t = LT.Template("Мой 50×30", 50, 30, [LT.Element("text", "{name} {size}", x_mm=1, y_mm=1, w_mm=48, h_mm=4),
                                          LT.Element("barcode", "{sku}", "CODE128", 2, 8, 46, 12),
                                          LT.Element("line", x_mm=1, y_mm=22, w_mm=48, h_mm=0)])
    tid = LT.save(con, t)
    back = LT.load(con, tid)
    assert [e.kind for e in back.elements] == ["text", "barcode", "line"]
    assert back.elements[1].symbology == "CODE128"
    back.elements[0].text = "{brand}"
    LT.save(con, back)
    assert LT.load(con, tid).elements[0].text == "{brand}" and len(LT.load(con, tid).elements) == 3
    copy = LT.duplicate(con, tid, "Копия")
    LT.set_default(con, copy)
    assert LT.load(con).id == copy
    LT.delete(con, copy)
    assert LT.load(con).is_default          # по умолчанию назначен другой шаблон
    d = LT.to_dict(LT.load(con, tid))
    assert LT.from_dict(d).elements[1].w_mm == 46


def test_validation(con):
    with pytest.raises(ValueError):
        LT.save(con, LT.Template("", 58, 40))
    with pytest.raises(ValueError):
        LT.save(con, LT.Template("x", 5, 40))
    with pytest.raises(ValueError):
        LT.save(con, LT.Template("x", 58, 40, [LT.Element(kind="circle")]))
    for t in LT.list_templates(con)[1:]:
        LT.delete(con, t["id"])
    with pytest.raises(ValueError):
        LT.delete(con, LT.list_templates(con)[0]["id"])


def test_fill_placeholders():
    assert LT.fill("{name} · {size} · {price}", lb()) == "Футболка · M · 189.90 MDL"
    assert LT.fill("{unknown} {name}", lb()) == "{unknown} Футболка"
    assert LT.fill("{price_value}", lb(price=None)) == ""


def test_barcode_modules_match_reportlab():
    from reportlab.graphics.barcode.code128 import Code128
    assert len(LT.ean13_modules("4006381333931")) == 95
    assert LT.ean13_modules("4006381333931").startswith("1010001101")
    for s in ("TSH0001-800-M", "ABC-12 x"):
        c = Code128(s); c.validate(); c.encode(); c.decompose()
        ref = "".join(("1" if ch.isupper() else "0") * (ord(ch.upper()) - 64) for ch in c.decomposed)
        assert LT.code128_modules(s) == ref
    with pytest.raises(ValueError):
        LT.ean13_modules("123")


def test_render_all_formats(con):
    t = LT.load(con)
    z = LT.to_zpl(t, [lb(), lb(size="L", copies=1)])
    assert z.count("^XA") == 2 and "^BEN," in z and "^PQ2,0,1,N" in z and "^PW464" in z
    assert "Futbolka" in z and "Футболка" not in z
    assert "Футболка" in LT.to_zpl(t, [lb()], font="E:ARIAL.TTF")
    ts = LT.to_tspl(t, [lb()])
    assert ts.startswith("SIZE 58 mm,40 mm\r\n") and '"EAN13"' in ts and "BOX " in ts and "PRINT 1,2" in ts
    tag = LT.load(con, [x["id"] for x in LT.list_templates(con) if "CODE128" in x["name"]][0])
    assert "^BCN," in LT.to_zpl(tag, [lb()]) and '"128"' in LT.to_tspl(tag, [lb()])
    roll = LT.to_pdf_roll(t, [lb(copies=3)])
    assert roll.startswith(b"%PDF") and len(re.findall(rb"/Type\s*/Page[^s]", roll)) == 3
    sheet = LT.to_pdf_sheet(t, [lb(copies=25)])
    assert len(re.findall(rb"/Type\s*/Page[^s]", sheet)) == 2
    with pytest.raises(ValueError):
        LT.to_zpl(t, [lb(ean13="1")])


def test_layout_for_editor_preview(con):
    prims = LT.layout(LT.load(con), LT.sample_label())
    kinds = {p["type"] for p in prims}
    assert {"text", "rect", "bars"} <= kinds
    bars = [p for p in prims if p["type"] == "bars"][0]
    assert len(bars["modules"]) == 95 and bars["caption"] == "2000000000015"


def test_line_variants_zpl_tspl(con):
    t = LT.Template("L", 40, 30, [LT.Element("line", x_mm=1, y_mm=1, w_mm=30, h_mm=0),
                                  LT.Element("line", x_mm=1, y_mm=1, w_mm=0, h_mm=20),
                                  LT.Element("line", x_mm=1, y_mm=1, w_mm=20, h_mm=10)])
    z = LT.to_zpl(t, [lb()])
    assert z.count("^GB") == 2 and "^GD" in z
    assert LT.to_tspl(t, [lb()]).count("BAR ") == 3


def test_store_render_uses_template(con):
    t = LT.Template("Только SKU", 30, 20, [LT.Element("text", "{sku}", x_mm=1, y_mm=1, w_mm=28, h_mm=4)])
    tid = LT.save(con, t)
    data, ext, mime = store.render_labels(con, [lb()], "zpl", tid)
    assert ext == "zpl" and b"TSH0001-800-M" in data and b"^BEN" not in data
    data, ext, _m = store.render_labels(con, [lb()], "pdf_roll", tid)
    assert b"/MediaBox [ 0 0 85.03937 56.69291 ]" in data


# ------------------------------------------------------------------ Excel / CSV

@pytest.fixture
def demo(con):
    from texflow.demo import load_demo
    load_demo(con)
    return con


def test_export_every_dataset_csv_and_xlsx(demo):
    from openpyxl import load_workbook
    for ds in exchange.DATASETS:
        text = exchange.to_csv(demo, ds)
        assert text.startswith("﻿") and ";" in text.splitlines()[0]
    data, name, mime = exchange.export(demo, "full", "xlsx")
    wb = load_workbook(io.BytesIO(data))
    assert name == "texflow_full.xlsx" and len(wb.sheetnames) == len(exchange.DATASETS)
    cat = wb[wb.sheetnames[0]]
    assert cat["A1"].value == "Артикул" and cat.max_row > 10
    ean_col = [c.value for c in cat[1]].index("EAN-13") + 1
    assert isinstance(cat.cell(2, ean_col).value, str) and len(cat.cell(2, ean_col).value) == 13
    with pytest.raises(ValueError):
        exchange.export(demo, "full", "csv")


def test_export_headers_follow_language(demo):
    from texflow import i18n
    i18n.set_lang("ro")
    try:
        assert exchange.to_csv(demo, "prices").splitlines()[0].lstrip("﻿").startswith("Articol;Denumire")
    finally:
        i18n.set_lang("ru")


def test_prices_roundtrip_through_excel(demo):
    from openpyxl import load_workbook
    data, _n, _m = exchange.export(demo, "prices", "xlsx")
    wb = load_workbook(io.BytesIO(data))
    ws = wb.active
    head = [c.value for c in ws[1]]
    ws.cell(2, head.index("Цена") + 1).value = 777.7
    ws.cell(2, head.index("Цена зафиксирована") + 1).value = "да"
    ws.append(["NOPE0001", "x", "y", 1, 2, 0])
    buf = io.BytesIO(); wb.save(buf)
    r = exchange.import_prices(demo, buf.getvalue(), "prices.xlsx")
    assert r["updated"] == 3 and r["unknown"] == ["NOPE0001"]
    code = ws.cell(2, 1).value
    p = demo.execute("SELECT retail_price, price_locked FROM products WHERE style_code = ?", (code,)).fetchone()
    assert (p[0], p[1]) == (777.7, 1)


def test_prices_import_csv_with_romanian_headers(demo):
    csv_text = "Articol;Preț\nTSH0001;99,90\n".encode("utf-8")
    assert exchange.import_prices(demo, csv_text, "p.csv")["updated"] == 1
    assert demo.execute("SELECT retail_price FROM products WHERE style_code='TSH0001'").fetchone()[0] == 99.9


def test_catalog_import_creates_models_variants_and_intake(demo):
    sid = store.create_shipment(demo, "CN-XL", fx_rate=2.5)
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["Style no.", "Name", "Name RO", "Category", "Colour code", "Size", "Qty", "Purchase (currency)"])
    ws.append(["HD0001", "Худи", "Hanorac", "KNT", "800", "M", 5, 9.5])
    ws.append(["HD0001", "Худи", "", "KNT", "800", "L", 3, 9.5])
    ws.append(["HD0001", "Худи", "", "KNT", "999", "L", 3, 9.5])          # нет такого цвета
    ws.append(["", "Без категории", "", "", "", "", "", ""])
    ws.append(["HD0001", "Худи", "", "KNT", "800", "5XL", 1, 9.5])        # новый размер в шкале
    buf = io.BytesIO(); wb.save(buf)
    r = exchange.import_catalog(demo, buf.getvalue(), "cat.xlsx", sid)
    assert (r["products"], r["variants"], r["received"]) == (1, 3, 9)
    assert len(r["errors"]) == 2 and "999" in r["errors"][0]
    p = demo.execute("SELECT id, name_ro FROM products WHERE style_code = 'HD0001'").fetchone()
    assert p["name_ro"] == "Hanorac"
    assert demo.execute("SELECT SUM(qty) FROM intake_items WHERE shipment_id = ?", (sid,)).fetchone()[0] == 9


def test_packing_import_xlsx(demo):
    sid = store.create_shipment(demo, "TR-X")
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    ws.append(["sac", "categorie", "descriere", "cantitate", "preț", "greutate"])
    ws.append([1, "Blugi", "blugi", 40, 7.5, 20])
    ws.append([2, "TSH", "tricouri", 100, 2, 15])
    buf = io.BytesIO(); wb.save(buf)
    r = exchange.import_packing(demo, sid, buf.getvalue(), "pl.xlsx")
    assert r == {"lines": 2, "bags": 2, "unknown_categories": []}


def test_intake_results_from_other_workstation(demo):
    exported = exchange.to_csv(demo, "intake", 1).encode("utf-8")
    sid = store.create_shipment(demo, "COPY")
    r = exchange.import_intake(demo, sid, exported, "intake.csv")
    assert r["pcs"] == store.shipment_totals(demo, 1)["pcs"] and r["unknown"] == []
    assert len(store.bags(demo, sid)) == 2
    bad = "SKU;Кол-во\nNOPE;3\n".encode()
    assert exchange.import_intake(demo, sid, bad, "x.csv")["unknown"] == ["NOPE"]


def test_web_exchange_and_template_routes(client, app):
    from texflow.demo import load_demo
    with app.app_context():
        load_demo(app.get_db())
    assert client.get("/exchange").status_code == 200
    r = client.get("/export/full.xlsx")
    assert r.status_code == 200 and r.data[:2] == b"PK"
    assert client.get("/export/catalog.csv").data.startswith("﻿".encode())
    assert client.get("/export/nope.csv").status_code == 404
    assert client.get("/export/full.csv").status_code == 400
    r = client.post("/import/prices", data={"file": (io.BytesIO("Артикул;Цена\nTSH0001;55\n".encode()), "p.csv")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "Цены обновлены: 1" in r.get_data(as_text=True)
    r = client.post("/import/packing", data={}, follow_redirects=True)
    assert "Выберите файл" in r.get_data(as_text=True)
    with app.app_context():
        tid = [t["id"] for t in LT.list_templates(app.get_db()) if t["name"].startswith("Mini")][0]
    page = client.get("/labels?product=1").get_data(as_text=True)
    assert "Mini 40×30" in page
    z = client.post("/labels", data={"product": "1", "copies": "1", "fmt": "zpl", "action": "download",
                                     "template": tid}).get_data(as_text=True)
    assert "^PW320" in z                               # 40 мм при 203 dpi (round)

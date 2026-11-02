import pytest

from texflow import rules, store

PACK_RU = """мешок;категория;описание;кол-во;цена;вес
1;TSH;футболки;100;2,00;15
1;Джинсы;джинсы;20;8;10
2;XYZ;непонятное;5;1;3
"""


def cat_id(con, code):
    return con.execute("SELECT id FROM categories WHERE code = ?", (code,)).fetchone()["id"]


def size(con, cat_code, code):
    return con.execute("SELECT s.id FROM sizes s JOIN categories c ON c.size_scale_id = s.scale_id "
                       "WHERE c.code = ? AND s.code = ?", (cat_code, code)).fetchone()["id"]


def color(con, code):
    return con.execute("SELECT id FROM colors WHERE code = ?", (code,)).fetchone()["id"]


@pytest.fixture
def sid(con):
    return store.create_shipment(con, "TR-1", "Bursa Tekstil", "TR", "USD", 18, freight=900, customs=300,
                                 broker=0, other_costs=0, alloc_method="value")


def test_seed_is_idempotent(con):
    from texflow import db
    n = con.execute("SELECT COUNT(*) FROM colors").fetchone()[0]
    db.seed_reference(con)
    assert con.execute("SELECT COUNT(*) FROM colors").fetchone()[0] == n
    assert len(store.color_families(con)) >= 12
    assert {s["name"] for s in store.size_scales(con)} >= {"Буквенная", "Джинсы W", "Обувь EU"}


def test_packing_import_ru_headers(con, sid):
    r = store.import_packing_csv(con, sid, PACK_RU)
    assert r == {"lines": 3, "bags": 2, "unknown_categories": ["XYZ"]}
    bags = {b["bag_no"]: b for b in store.bags(con, sid)}
    assert bags["1"]["weight_kg"] == 25 and bags["1"]["declared"] == 120
    assert store.declared_unit_price(con, sid, cat_id(con, "TSH")) == 2.0
    # повторный импорт заменяет строки
    store.import_packing_csv(con, sid, PACK_RU)
    assert len(store.packing_lines(con, sid)) == 3


def test_packing_import_chinese_tab_and_errors(con, sid):
    text = "包\t类别\t品名\t数量\t单价\t重量\nA1\tTSH\tT-shirt\t50\t1.1\t9\n"
    assert store.import_packing_csv(con, sid, text)["lines"] == 1
    with pytest.raises(ValueError):
        store.import_packing_csv(con, sid, "a;b\n1;2\n")


def test_intake_grid_creates_variants(con, sid):
    bag = store.ensure_bag(con, sid, "1", 20)
    pid = store.create_product(con, "Футболка", cat_id(con, "TSH"), base_cost_fx=2)
    n = store.add_intake(con, sid, bag, pid, {(color(con, "800"), size(con, "TSH", "M")): 5,
                                              (color(con, "800"), size(con, "TSH", "L")): 3,
                                              (color(con, "001"), size(con, "TSH", "M")): 0})
    assert n == 8
    vs = store.variants(con, pid)
    assert len(vs) == 2
    assert all(rules.is_valid_ean13(v["ean13"]) for v in vs)
    assert {v["sku"] for v in vs} == {"TSH0001-800-M", "TSH0001-800-L"}
    # повторная приёмка того же варианта не плодит вариантов
    store.add_intake(con, sid, bag, pid, {(color(con, "800"), size(con, "TSH", "M")): 2})
    assert len(store.variants(con, pid)) == 2
    assert con.execute("SELECT status FROM bags WHERE id = ?", (bag,)).fetchone()[0] == "sorting"
    m = store.product_matrix(con, pid)
    assert len(m["colors"]) == 1 and len(m["sizes"]) == 8


def test_scan_adds_piece(con, sid):
    pid = store.create_product(con, "Джинсы", cat_id(con, "JNS"), base_cost_fx=8)
    store.add_intake(con, sid, None, pid, {(color(con, "400"), size(con, "JNS", "28")): 1})
    ean = store.variants(con, pid)[0]["ean13"]
    store.add_scan(con, sid, None, ean)
    store.add_scan(con, sid, None, store.variants(con, pid)[0]["sku"].lower())
    assert store.variants(con, pid)[0]["stock"] == 3
    with pytest.raises(ValueError):
        store.add_scan(con, sid, None, "0000000000000")


def test_landed_cost_and_prices(con, sid):
    store.import_packing_csv(con, sid, PACK_RU)
    t = store.create_product(con, "Футболка", cat_id(con, "TSH"), base_cost_fx=2)
    j = store.create_product(con, "Джинсы", cat_id(con, "JNS"), base_cost_fx=8)
    store.add_intake(con, sid, None, t, {(color(con, "800"), size(con, "TSH", "M")): 100})
    store.add_intake(con, sid, None, j, {(color(con, "400"), size(con, "JNS", "28")): 20})
    tot = store.shipment_totals(con, sid)
    store.compute_landed(con, sid)
    tot = store.shipment_totals(con, sid)
    goods = (100 * 2 + 20 * 8) * 18
    duty = goods * 0.12
    assert tot["landed"] == pytest.approx(goods + duty + 1200, abs=0.5)
    rows = {r["id"]: r for r in store.price_proposal(con, sid)}
    # футболка: 36 + 4.32 пошлина + 1200 * 3600/6480 / 100 = 6.6667 → 46.99
    assert rows[t]["landed"] == pytest.approx(46.99, abs=0.01)
    assert rows[t]["price"] == pytest.approx(rules.retail_price(46.9867, 150, 20)["price"])
    assert str(rows[t]["price"]).endswith(".9")
    # закреплённая цена не перезаписывается
    store.update_product(con, j, retail_price=999, price_locked=1)
    assert store.apply_prices(con, sid) == 1
    assert store.product(con, j)["retail_price"] == 999
    assert store.product(con, t)["retail_price"] == rows[t]["price"]
    assert store.shipment(con, sid)["status"] == "priced"


def test_weight_allocation_uses_bag_weight(con, sid):
    store.update_shipment(con, sid, alloc_method="weight", customs=0, freight=100)
    b1, b2 = store.ensure_bag(con, sid, "1", 30), store.ensure_bag(con, sid, "2", 10)
    t = store.create_product(con, "Т", cat_id(con, "TSH"), base_cost_fx=1)
    store.add_intake(con, sid, b1, t, {(color(con, "800"), size(con, "TSH", "M")): 10})
    store.add_intake(con, sid, b2, t, {(color(con, "800"), size(con, "TSH", "L")): 10})
    res = {r.key: r for r in store.compute_landed(con, sid)}
    over = sorted(r.overhead_unit for r in res.values())
    assert over == pytest.approx([2.5, 7.5])


def test_reconciliation(con, sid):
    store.import_packing_csv(con, sid, PACK_RU)
    t = store.create_product(con, "Футболка", cat_id(con, "TSH"))
    bag = store.ensure_bag(con, sid, "1")
    store.add_intake(con, sid, bag, t, {(color(con, "800"), size(con, "TSH", "M")): 97})
    rec = store.reconciliation(con, sid)
    by = {r["key"]: r for r in rec["by_category"]}
    assert by["Футболки и топы"]["status"] == "short" and by["Футболки и топы"]["diff"] == -3
    assert by["Джинсы"]["status"] == "short" and by["Джинсы"]["counted"] == 0
    assert any(k.startswith("— без категории") for k in by)
    assert {r["key"]: r["counted"] for r in rec["by_bag"]}["1"] == 97


def test_labels_and_export(con, sid):
    t = store.create_product(con, "Футболка", cat_id(con, "TSH"), base_cost_fx=2, composition="хлопок")
    store.add_intake(con, sid, None, t, {(color(con, "800"), size(con, "TSH", "M")): 4,
                                         (color(con, "001"), size(con, "TSH", "S")): 2})
    sel = store.labels_for_shipment(con, sid)
    assert sorted(sel.values()) == [2, 4]
    items = store.label_rows(con, sel)
    assert sum(i.copies for i in items) == 6 and all(i.ref for i in items)
    lay, sheet = store.layouts(con)
    assert (lay.width_mm, lay.dpi, sheet.cols, sheet.rows) == (58, 203, 3, 8)
    csv = store.export_catalog_csv(con)
    assert csv.splitlines()[0].startswith("style_code;name") and len(csv.splitlines()) == 3


def test_settings_roundtrip_and_refs(con):
    store.save_settings(con, {"round_step": "1", "brand": "ZEBRA SHOP"})
    assert store.settings(con)["round_step"] == "1"
    fam = store.color_families(con)[0]["id"]
    store.add_color(con, fam, "099", "Снежный", "#fafafa")
    scale = store.size_scales(con)[0]["id"]
    store.add_size(con, scale, "4xl")
    assert "4XL" in [s["code"] for s in store.sizes_for_scale(con, scale)]
    cid = store.add_category(con, "swm", "Купальники", scale, 140, 12)
    store.update_category(con, cid, 160, 5)
    assert con.execute("SELECT markup_pct FROM categories WHERE id = ?", (cid,)).fetchone()[0] == 160

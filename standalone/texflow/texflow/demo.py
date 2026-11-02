"""Демо-данные: одна поставка из Турции, разобранный мешок, цены."""
from . import store


def load_demo(con) -> str:
    if con.execute("SELECT 1 FROM shipments WHERE code = 'DEMO-TR-01'").fetchone():
        return "демо уже загружено"
    sid = store.create_shipment(con, "DEMO-TR-01", "Istanbul Tekstil", "TR", "USD", 17.8,
                                freight=4500, customs=1200, broker=800, alloc_method="value")
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "samples", "packing_list_tr.csv")
    with open(path, encoding="utf-8") as f:
        store.import_packing_csv(con, sid, f.read())
    bag1 = con.execute("SELECT id FROM bags WHERE shipment_id = ? AND bag_no = '1'", (sid,)).fetchone()["id"]
    bag2 = con.execute("SELECT id FROM bags WHERE shipment_id = ? AND bag_no = '2'", (sid,)).fetchone()["id"]
    cat = {r["code"]: r for r in store.categories(con)}
    col = {r["code"]: r["id"] for r in con.execute("SELECT id, code FROM colors")}

    def sz(cat_code, code):
        return con.execute("SELECT id FROM sizes WHERE scale_id = ? AND code = ?",
                           (cat[cat_code]["size_scale_id"], code)).fetchone()["id"]

    t = store.create_product(con, "Футболка базовая оверсайз", cat["TSH"]["id"], base_cost_fx=2.10,
                             composition="100% хлопок", supplier="Istanbul Tekstil")
    store.add_intake(con, sid, bag1, t, {(col["001"], sz("TSH", "S")): 12, (col["001"], sz("TSH", "M")): 18,
                                         (col["001"], sz("TSH", "L")): 10, (col["800"], sz("TSH", "S")): 10,
                                         (col["800"], sz("TSH", "M")): 20, (col["800"], sz("TSH", "L")): 14,
                                         (col["710"], sz("TSH", "M")): 16, (col["630"], sz("TSH", "S")): 12})
    b = store.create_product(con, "Блуза шифоновая", cat["SHR"]["id"], base_cost_fx=4.50,
                             composition="100% полиэстер", supplier="Istanbul Tekstil")
    store.add_intake(con, sid, bag1, b, {(col["002"], sz("SHR", "S")): 10, (col["002"], sz("SHR", "M")): 14,
                                         (col["406"], sz("SHR", "M")): 12})
    j = store.create_product(con, "Джинсы mom fit", cat["JNS"]["id"], base_cost_fx=7.80,
                             composition="98% хлопок, 2% эластан", supplier="Istanbul Tekstil")
    store.add_intake(con, sid, bag2, j, {(col["400"], sz("JNS", w)): q for w, q in
                                         [("26", 8), ("27", 10), ("28", 12), ("29", 10), ("30", 8)]})
    store.add_intake(con, sid, bag2, j, {(col["800"], sz("JNS", "27")): 6, (col["800"], sz("JNS", "28")): 6})
    store.set_bag_status(con, bag1, "done")
    n = store.apply_prices(con, sid)
    return f"демо: поставка DEMO-TR-01, {n} моделей с ценами"

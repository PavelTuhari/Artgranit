"""Встроенная тестовая база: заполнено всё — от поставщиков до журнала печати.

Пять поставок во всех статусах (закрыта, оценена, разобрана, в разборе, только что пришла),
четыре поставщика из Турции и Китая, модели во всех 12 категориях с переводами RO/EN,
приёмка с недостачей, излишком, «нет в листе» (юбки в CN-2026-10) и исправлением, ручная и заблокированная цена,
свой цвет и свой размер, свои шаблоны этикеток, журнал печати, настройки принтеров.

    python texflow_app.py --sample            # программа на тестовой базе
    python texflow_app.py --web --sample      # веб-версия на тестовой базе
    python -m texflow.sample_db путь.db       # собрать файл базы

Рабочую базу тестовая не трогает: она пишется в отдельный файл texflow_sample.db.
"""
from __future__ import annotations

import os
import sys

from . import db, label_templates as lt, store

SAMPLE_FILE = "texflow_sample.db"
MARK = "SAMPLE-DB"           # отметка в settings: база собрана этим модулем

SETTINGS = {
    "brand": "BAZAR NOVA", "currency": "MDL", "vat_pct": "20", "prices_include_vat": "1",
    "round_step": "10", "round_ending": "0.1", "min_markup_pct": "30",
    "printer_zpl": "192.168.1.50:9100", "printer_tspl": "192.168.1.51:9100",
    "label_lang": "ro", "ui_lang": "ru", "sample_db": MARK,
}

SUPPLIERS = [("Laleli Moda", "TR"), ("Istanbul Tekstil", "TR"),
             ("Guangzhou Baiyun Garments", "CN"), ("Yiwu Smart Accessories", "CN")]

# код, поставщик, страна, валюта, курс, дата, (фрахт, таможня, брокер, прочее), распределение, статус
SHIPMENTS = [
    ("TR-2026-09", "Laleli Moda", "TR", "USD", 17.6, "2026-09-12", (5200, 1400, 900, 300), "value", "closed"),
    ("TR-2026-10", "Istanbul Tekstil", "TR", "EUR", 19.4, "2026-10-08", (4500, 1200, 800, 0), "value", "priced"),
    ("CN-2026-10", "Guangzhou Baiyun Garments", "CN", "USD", 17.8, "2026-10-21", (9800, 2600, 1100, 450),
     "weight", "sorted"),
    ("CN-2026-11", "Yiwu Smart Accessories", "CN", "CNY", 2.45, "2026-11-01", (3100, 700, 500, 0), "qty", "open"),
    ("TR-2026-11", "Laleli Moda", "TR", "USD", 17.7, "2026-11-02", (4800, 1300, 900, 0), "value", "open"),
]

# мешок; категория; описание; кол-во; цена; вес — по одному листу на поставку
PACKING = {
    "TR-2026-09": """bag_no;category;description;qty;unit_price;weight_kg
1;KNT;Свитеры крупной вязки;40;7.50;22
1;TSH;Лонгсливы;60;2.40;9
2;JCK;Пальто шерстяное;20;24.00;30
2;PNT;Брюки палаццо;30;5.80;12""",
    "TR-2026-10": "@samples/packing_list_tr.csv",
    "CN-2026-10": """包;类别;品名;数量;单价;重量
A1;TSH;T-shirt kids print;80;1.10;10
A1;KID;Kids joggers;60;1.90;12
A2;SHO;Sneakers white;24;6.50;20
A2;SUI;Men suit 2 pcs;10;28.00;18
A3;DRS;Dress summer;30;3.20;8""",
    "CN-2026-11": """bag_no;category;description;qty;unit_price;weight_kg
B1;ACC;Шапки вязаные;80;6.50;6
B1;ACC;Ремни;40;9.00;7
B2;SHO;Ботинки челси;30;68.00;34""",
    "TR-2026-11": """bag_no;category;description;qty;unit_price;weight_kg
1;DRS;Платья трикотаж;50;6.40;15
1;TSH;Топы рибана;70;1.90;8
2;JNS;Джинсы straight;60;7.20;31
3;JCK;Пуховики короткие;25;19.00;27""",
}

# (поставка, мешок, кат., артикул, RU, RO, EN, состав RU/RO/EN, закупка, сезон, пол,
#  [(цвет, [(размер, шт), ...]), ...])
C_COTTON = ("100% хлопок", "100% bumbac", "100% cotton")
C_WOOL = ("70% шерсть, 30% полиамид", "70% lână, 30% poliamidă", "70% wool, 30% polyamide")
C_POLY = ("100% полиэстер", "100% poliester", "100% polyester")
C_DENIM = ("98% хлопок, 2% эластан", "98% bumbac, 2% elastan", "98% cotton, 2% elastane")
C_VISC = ("95% вискоза, 5% эластан", "95% viscoză, 5% elastan", "95% viscose, 5% elastane")
C_LEATH = ("Натуральная кожа", "Piele naturală", "Genuine leather")

MODELS = [
    ("TR-2026-09", "1", "KNT", "KNT0901", "Свитер крупной вязки", "Pulover tricotat gros", "Chunky knit sweater",
     C_WOOL, 7.50, "FW26", "women", [("002", [("S", 6), ("M", 8), ("L", 5)]), ("712", [("S", 5), ("M", 7), ("L", 6)]),
                                      ("815", [("M", 3)])]),
    ("TR-2026-09", "1", "TSH", "TSH0901", "Лонгслив базовый", "Bluză cu mânecă lungă", "Basic long sleeve tee",
     C_COTTON, 2.40, "FW26", "unisex", [("001", [("S", 8), ("M", 10), ("L", 8)]), ("800", [("S", 8), ("M", 12), ("L", 10)]),
                                        ("812", [("M", 4)])]),
    ("TR-2026-09", "2", "JCK", "JCK0901", "Пальто шерстяное прямое", "Palton drept din lână", "Straight wool coat",
     C_WOOL, 24.00, "FW26", "women", [("712", [("S", 4), ("M", 6), ("L", 4)]), ("800", [("S", 2), ("M", 3), ("L", 1)])]),
    ("TR-2026-09", "2", "PNT", "PNT0901", "Брюки палаццо", "Pantaloni palazzo", "Palazzo trousers",
     C_VISC, 5.80, "FW26", "women", [("800", [("S", 6), ("M", 8), ("L", 6)]), ("710", [("S", 4), ("M", 4), ("L", 2)])]),

    ("TR-2026-10", "1", "TSH", "TSH1001", "Футболка базовая оверсайз", "Tricou basic oversize",
     "Basic oversize T-shirt", C_COTTON, 2.10, "SS27", "women",
     [("001", [("S", 12), ("M", 18), ("L", 10)]), ("800", [("S", 10), ("M", 20), ("L", 14)]),
      ("710", [("M", 16)]), ("630", [("S", 12)])]),
    ("TR-2026-10", "1", "SHR", "SHR1001", "Блуза шифоновая", "Bluză din șifon", "Chiffon blouse",
     C_POLY, 4.50, "SS27", "women", [("002", [("S", 10), ("M", 14)]), ("406", [("M", 12)])]),
    ("TR-2026-10", "2", "JNS", "JNS1001", "Джинсы mom fit", "Blugi mom fit", "Mom fit jeans",
     C_DENIM, 7.80, "SS27", "women", [("400", [("26", 8), ("27", 10), ("28", 12), ("29", 10), ("30", 8)]),
                                      ("800", [("27", 6), ("28", 6)])]),
    ("TR-2026-10", "3", "DRS", "DRS1001", "Платье миди трикотаж", "Rochie midi tricotată", "Knit midi dress",
     C_VISC, 6.20, "SS27", "women", [("620", [("36", 5), ("38", 7), ("40", 6), ("42", 4)]),
                                     ("800", [("36", 4), ("38", 6), ("40", 5)])]),
    ("TR-2026-10", "3", "KNT", "KNT1001", "Свитер оверсайз", "Pulover oversize", "Oversize sweater",
     C_WOOL, 8.00, "SS27", "unisex", [("812", [("M", 8), ("L", 8)]), ("507", [("M", 6), ("L", 4)])]),
    ("TR-2026-10", "4", "JCK", "JCK1001", "Куртка демисезон", "Geacă de tranziție", "Transitional jacket",
     C_POLY, 14.50, "SS27", "women", [("505", [("S", 4), ("M", 6), ("L", 4)]), ("800", [("M", 6), ("L", 4)])]),
    ("TR-2026-10", "4", "ACC", "ACC1001", "Шарф кашемировый", "Fular din cașmir", "Cashmere scarf",
     C_WOOL, 1.20, "SS27", "unisex", [("712", [("ONE", 20)]), ("902", [("ONE", 18)]), ("620", [("ONE", 10)])]),

    ("CN-2026-10", "A1", "TSH", "TSH1002", "Футболка детская с принтом", "Tricou copii cu imprimeu",
     "Kids print T-shirt", C_COTTON, 1.10, "SS27", "kids", [("900", [("S", 20), ("M", 30), ("L", 20)]),
                                                         ("403", [("M", 12)])]),
    ("CN-2026-10", "A1", "KID", "KID1001", "Джоггеры детские", "Pantaloni jogger copii", "Kids joggers",
     C_COTTON, 1.90, "SS27", "kids", [("812", [("98", 6), ("104", 8), ("110", 8), ("116", 8), ("122", 6)]),
                                      ("406", [("104", 6), ("110", 8), ("116", 6)])]),
    ("CN-2026-10", "A2", "SHO", "SHO1001", "Кеды белые", "Teniși albi", "White sneakers",
     ("Текстиль, резина", "Textil, cauciuc", "Textile, rubber"), 6.50, "SS27", "unisex",
     [("001", [("37", 3), ("38", 4), ("39", 4), ("40", 4), ("41", 3), ("42", 2)])]),
    ("CN-2026-10", "A2", "SUI", "SUI1001", "Костюм мужской двойка", "Costum bărbați din două piese",
     "Men's two-piece suit", ("65% полиэстер, 35% вискоза", "65% poliester, 35% viscoză", "65% polyester, 35% viscose"),
     28.00, "SS27", "men", [("406", [("48", 2), ("50", 3), ("52", 2)]), ("815", [("50", 2), ("52", 1)])]),
    ("CN-2026-10", "A3", "SKR", "SKR1001", "Юбка плиссе", "Fustă plisată", "Pleated skirt",
     C_POLY, 3.20, "SS27", "women", [("640", [("36", 6), ("38", 8), ("40", 6)]), ("TF1", [("38", 6)])]),

    ("CN-2026-11", "B1", "ACC", "ACC1101", "Шапка вязаная", "Căciulă tricotată", "Knit beanie",
     ("100% акрил", "100% acril", "100% acrylic"), 6.50, "FW26", "unisex",
     [("800", [("ONE", 20)]), ("620", [("ONE", 14)]), ("505", [("ONE", 10)])]),
]

def _packing(code: str) -> str:
    text = PACKING[code]
    if text.startswith("@"):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, text[1:]), encoding="utf-8") as f:
            return f.read()
    return text


TF_COLOR = ("TF1", "Терракотовый меланж", "Teracotă melanj", "Terracotta marl", "#c46a4e")


def build(con) -> dict:
    """Заполнить пустую базу тестовыми данными. Возвращает счётчики."""
    db.init_db(con)
    if store.settings(con).get("sample_db") == MARK:
        return summary(con)
    if con.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]:
        raise ValueError("база не пустая: тестовые данные пишутся только в новую базу")
    store.save_settings(con, SETTINGS)
    for name, country in SUPPLIERS:
        store.supplier_id(con, name, country)

    # свой цвет и свой размер — как это делает пользователь в «Справочниках»
    fam = con.execute("SELECT id FROM color_families WHERE name_en = 'Orange'").fetchone()[0]
    store.add_color(con, fam, TF_COLOR[0], TF_COLOR[1], TF_COLOR[4], TF_COLOR[2], TF_COLOR[3])
    letters = con.execute("SELECT id FROM size_scales WHERE name_en = 'Letter'").fetchone()[0]
    store.add_size(con, letters, "4XL")

    sid = {}
    for code, sup, country, cur, rate, date, (fr, cu, br, ot), alloc, _st in SHIPMENTS:
        sid[code] = store.create_shipment(con, code, sup, country, cur, rate, date, freight=fr, customs=cu,
                                          broker=br, other_costs=ot, alloc_method=alloc,
                                          note=f"{sup}, {date}")
        store.import_packing_csv(con, sid[code], _packing(code))

    cats = {r["code"]: r for r in store.categories(con)}
    colors = {r["code"]: r["id"] for r in con.execute("SELECT id, code FROM colors")}

    def size(cat, code):
        return con.execute("SELECT id FROM sizes WHERE scale_id = ? AND code = ?",
                           (cats[cat]["size_scale_id"], code)).fetchone()["id"]

    def bag(ship, no):
        return con.execute("SELECT id FROM bags WHERE shipment_id = ? AND bag_no = ?", (sid[ship], no)).fetchone()["id"]

    pids = {}
    for ship, bag_no, cat, style, ru, ro, en, comp, cost, season, gender, grid in MODELS:
        sup = next(s[1] for s in SHIPMENTS if s[0] == ship)
        pid = store.create_product(con, ru, cats[cat]["id"], style_code=style, supplier=sup, base_cost_fx=cost,
                                   composition=comp[0], season=season, gender=gender,
                                   description=f"{en} — {season}")
        store.update_product(con, pid, name_ro=ro, name_en=en, composition_ro=comp[1], composition_en=comp[2])
        pids[style] = pid
        store.add_intake(con, sid[ship], bag(ship, bag_no), pid,
                         {(colors[c], size(cat, s)): q for c, row in grid for s, q in row})

    # повторные товары — сканером, как на столе приёмки
    v = con.execute("SELECT ean13 FROM variants WHERE sku = 'TSH1001-800-M'").fetchone()["ean13"]
    for _i in range(3):
        store.add_scan(con, sid["TR-2026-10"], bag("TR-2026-10", "1"), v)
    # пересчёт: лишние 2 шт. списаны отрицательной строкой
    vid = con.execute("SELECT id FROM variants WHERE sku = 'JNS1001-400-28'").fetchone()["id"]
    con.execute("INSERT INTO intake_items(shipment_id, bag_id, variant_id, qty, unit_cost_fx) VALUES (?, ?, ?, ?, ?)",
                (sid["TR-2026-10"], bag("TR-2026-10", "2"), vid, -2, 7.80))
    # новый размер 4XL появился в мешке
    store.add_intake(con, sid["TR-2026-09"], bag("TR-2026-09", "1"), pids["TSH0901"],
                     {(colors["800"], size("TSH", "4XL")): 3})
    con.commit()

    # статусы мешков
    for ship in ("TR-2026-09", "TR-2026-10", "CN-2026-10"):
        for b in store.bags(con, sid[ship]):
            store.set_bag_status(con, b["id"], "done")
    store.set_bag_status(con, bag("CN-2026-11", "B1"), "sorting")

    # цены: ручная цена у пальто, заблокированная — у шарфа
    store.update_product(con, pids["ACC1001"], retail_price=149.90, price_locked=1)
    store.apply_prices(con, sid["TR-2026-09"], overrides={pids["JCK0901"]: 1899.90})
    store.apply_prices(con, sid["TR-2026-10"])
    store.compute_landed(con, sid["CN-2026-10"])
    store.apply_prices(con, sid["CN-2026-10"])
    store.apply_prices(con, sid["CN-2026-11"])
    for code, *_rest, status in SHIPMENTS:
        store.update_shipment(con, sid[code], status=status)

    # шаблоны этикеток: три стандартных + два своих
    lt.seed(con)
    E = lt.Element
    lt.save(con, lt.Template("Sale 50×30", 50, 30, elements=[
        E("box", x_mm=1, y_mm=1, w_mm=48, h_mm=28, thickness=0.4),
        E("text", "SALE", x_mm=2, y_mm=2, w_mm=20, h_mm=5, font_mm=4.6, bold=True),
        E("text", "{price}", x_mm=20, y_mm=2, w_mm=28, h_mm=5, font_mm=4.6, bold=True, align="R"),
        E("text", "{name} · {size}", x_mm=2, y_mm=8, w_mm=46, h_mm=3.4, font_mm=2.8),
        E("barcode", "{ean13}", "EAN13", x_mm=8, y_mm=12.5, w_mm=34, h_mm=12),
        E("text", "{sku}", x_mm=2, y_mm=25.5, w_mm=46, h_mm=2.6, font_mm=2.2, align="C")]))
    lt.save(con, lt.Template("Kids 40×25", 40, 25, elements=[
        E("text", "{name}", x_mm=1.5, y_mm=1.2, w_mm=37, h_mm=3, font_mm=2.6, bold=True),
        E("text", "{size} cm", x_mm=1.5, y_mm=4.6, w_mm=14, h_mm=4, font_mm=3.6, bold=True),
        E("text", "{price}", x_mm=16, y_mm=4.6, w_mm=22.5, h_mm=4, font_mm=3.6, bold=True, align="R"),
        E("barcode", "{sku}", "CODE128", x_mm=2, y_mm=10, w_mm=36, h_mm=12.5)]))

    # журнал печати
    for fmt, target, n, status, msg in [
            ("zpl", "192.168.1.50:9100", 214, "ok", "TR-2026-09"),
            ("pdf_sheet", "file", 72, "ok", "TR-2026-09 A4"),
            ("tspl", "192.168.1.51:9100", 356, "ok", "TR-2026-10"),
            ("pdf_roll", "file", 40, "ok", "TR-2026-10 bag 1"),
            ("zpl", "192.168.1.50:9100", 0, "error", "timed out — принтер выключен"),
            ("zpl", "192.168.1.50:9100", 330, "ok", "CN-2026-10")]:
        store.log_label_job(con, fmt, target, n, status, msg)
    return summary(con)


def summary(con) -> dict:
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    return {"suppliers": one("SELECT COUNT(*) FROM suppliers"),
            "shipments": one("SELECT COUNT(*) FROM shipments"),
            "bags": one("SELECT COUNT(*) FROM bags"),
            "packing_lines": one("SELECT COUNT(*) FROM packing_lines"),
            "products": one("SELECT COUNT(*) FROM products"),
            "variants": one("SELECT COUNT(*) FROM variants"),
            "pieces": one("SELECT COALESCE(SUM(qty), 0) FROM intake_items"),
            "priced": one("SELECT COUNT(*) FROM products WHERE retail_price IS NOT NULL"),
            "templates": one("SELECT COUNT(*) FROM label_templates"),
            "label_jobs": one("SELECT COUNT(*) FROM label_jobs")}


def ensure(path: str, fresh: bool = False) -> str:
    """Файл тестовой базы: собрать, если его нет (или fresh=True). Возвращает путь."""
    if fresh and os.path.exists(path):
        for ext in ("", "-wal", "-shm"):
            if os.path.exists(path + ext):
                os.remove(path + ext)
    con = db.connect(path)
    try:
        build(con)
    finally:
        con.close()
    return path


def default_path() -> str:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "desktop"))
        from texflow_desktop.paths import data_dir
        return os.path.join(data_dir(), SAMPLE_FILE)
    except Exception:   # noqa: BLE001
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instance", SAMPLE_FILE)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else default_path()
    ensure(target, fresh=True)
    con = db.connect(target)
    print(target, summary(con))

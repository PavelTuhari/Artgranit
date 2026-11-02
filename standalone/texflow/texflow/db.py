"""SQLite: подключение, схема и стартовые справочники."""
from __future__ import annotations

import os
import sqlite3

SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")

DEFAULT_SETTINGS = {
    "brand": "MY STORE",
    "currency": "MDL",
    "vat_pct": "20",
    "prices_include_vat": "1",
    "round_step": "10",
    "round_ending": "0.1",
    "min_markup_pct": "30",
    "ean_prefix": "200",
    "ean_counter": "0",
    "label_width_mm": "58",
    "label_height_mm": "40",
    "label_gap_mm": "2",
    "label_dpi": "203",
    "printer_zpl": "",
    "printer_tspl": "",
    "zpl_font": "",
    "tspl_font": "",
    "sheet_cols": "3",
    "sheet_rows": "8",
    "sheet_label_w_mm": "70",
    "sheet_label_h_mm": "37",
    "sheet_margin_left_mm": "0",
    "sheet_margin_top_mm": "0.5",
    "sheet_border": "1",
    "ui_lang": "ru",
    "label_lang": "ru",
}

# шкала: (RU, RO, EN) → размеры
SIZE_SCALES = {
    ("Буквенная", "Litere", "Letter"): ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL"],
    ("Женская EU", "Damă EU", "Women EU"): ["32", "34", "36", "38", "40", "42", "44", "46", "48"],
    ("Мужская RU", "Bărbați RU", "Men RU"): ["44", "46", "48", "50", "52", "54", "56", "58"],
    ("Джинсы W", "Blugi W", "Jeans W"): ["24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "36", "38"],
    ("Детская (рост)", "Copii (înălțime)", "Kids (height)"): ["86", "92", "98", "104", "110", "116", "122", "128",
                                                             "134", "140", "152", "164"],
    ("Обувь EU", "Încălțăminte EU", "Shoes EU"): ["35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"],
    ("Единый", "Mărime unică", "One size"): ["ONE"],
}

# ((семейство RU, RO, EN), hex, [(код, (RU, RO, EN), hex)]) — группы цветов как на витрине Zara
COLOR_FAMILIES = [
    (("Белый", "Alb", "White"), "#ffffff", [
        ("001", ("Белый", "Alb", "White"), "#ffffff"),
        ("002", ("Молочный", "Lăptos", "Off-white"), "#f6f1e6"),
        ("003", ("Экрю", "Ecru", "Ecru"), "#efe6d2")]),
    (("Чёрный", "Negru", "Black"), "#111111", [
        ("800", ("Чёрный", "Negru", "Black"), "#111111"),
        ("802", ("Графит", "Grafit", "Graphite"), "#33363a")]),
    (("Серый", "Gri", "Grey"), "#9a9a9a", [
        ("810", ("Серый", "Gri", "Grey"), "#9a9a9a"),
        ("812", ("Серый меланж", "Gri melanj", "Grey marl"), "#b8b8b8"),
        ("815", ("Антрацит", "Antracit", "Anthracite"), "#4a4d50")]),
    (("Бежевый", "Bej", "Beige"), "#d9c4a3", [
        ("710", ("Бежевый", "Bej", "Beige"), "#d9c4a3"),
        ("704", ("Песочный", "Nisipiu", "Sand"), "#cdb58a"),
        ("712", ("Кэмел", "Camel", "Camel"), "#b5844f")]),
    (("Коричневый", "Maro", "Brown"), "#6b4a2f", [
        ("700", ("Коричневый", "Maro", "Brown"), "#6b4a2f"),
        ("702", ("Шоколад", "Ciocolatiu", "Chocolate"), "#4a3020")]),
    (("Синий", "Albastru", "Blue"), "#1f3a68", [
        ("401", ("Синий", "Albastru", "Blue"), "#1f4fa0"),
        ("406", ("Тёмно-синий", "Bleumarin", "Navy"), "#1b2a49"),
        ("400", ("Деним", "Denim", "Denim"), "#4a6a8f")]),
    (("Голубой", "Albastru deschis", "Light blue"), "#9cc3e6", [
        ("403", ("Голубой", "Albastru deschis", "Light blue"), "#9cc3e6"),
        ("405", ("Небесный", "Bleu ceresc", "Sky blue"), "#bcd8f0")]),
    (("Зелёный", "Verde", "Green"), "#3b6e4a", [
        ("500", ("Зелёный", "Verde", "Green"), "#3b6e4a"),
        ("505", ("Хаки", "Kaki", "Khaki"), "#7a7a4a"),
        ("507", ("Оливковый", "Oliv", "Olive"), "#6b6b3a"),
        ("510", ("Мятный", "Mentă", "Mint"), "#bfe3cf")]),
    (("Красный", "Roșu", "Red"), "#b3202a", [
        ("600", ("Красный", "Roșu", "Red"), "#b3202a"),
        ("620", ("Бордовый", "Bordo", "Burgundy"), "#6d1a26")]),
    (("Розовый", "Roz", "Pink"), "#e9a8b8", [
        ("630", ("Розовый", "Roz", "Pink"), "#e9a8b8"),
        ("640", ("Пудровый", "Roz pudră", "Powder pink"), "#e8c8c0"),
        ("645", ("Фуксия", "Fucsia", "Fuchsia"), "#c4307a")]),
    (("Фиолетовый", "Violet", "Purple"), "#6b4a8f", [
        ("650", ("Фиолетовый", "Violet", "Purple"), "#6b4a8f"),
        ("655", ("Лиловый", "Lila", "Lilac"), "#b9a3d0")]),
    (("Жёлтый", "Galben", "Yellow"), "#e8c33a", [
        ("300", ("Жёлтый", "Galben", "Yellow"), "#e8c33a"),
        ("310", ("Горчичный", "Muștar", "Mustard"), "#c49a2a")]),
    (("Оранжевый", "Portocaliu", "Orange"), "#e07a2a", [
        ("320", ("Оранжевый", "Portocaliu", "Orange"), "#e07a2a"),
        ("330", ("Терракота", "Teracotă", "Terracotta"), "#b5573a")]),
    (("Принт / Мульти", "Imprimeu / Multi", "Print / Multi"), "#cccccc", [
        ("900", ("Принт", "Imprimeu", "Print"), "#cccccc"),
        ("901", ("Полоска", "Dungi", "Stripes"), "#dddddd"),
        ("902", ("Клетка", "Carouri", "Check"), "#bbbbbb")]),
]

# (код, (RU, RO, EN), шкала RU, наценка %, пошлина %, ТН ВЭД)
CATEGORIES = [
    ("TSH", ("Футболки и топы", "Tricouri și topuri", "T-shirts & tops"), "Буквенная", 150, 12, "6109"),
    ("SHR", ("Рубашки и блузы", "Cămăși și bluze", "Shirts & blouses"), "Буквенная", 140, 12, "6205"),
    ("KNT", ("Трикотаж и свитеры", "Tricotaje și pulovere", "Knitwear & sweaters"), "Буквенная", 130, 12, "6110"),
    ("DRS", ("Платья", "Rochii", "Dresses"), "Женская EU", 140, 12, "6204"),
    ("SKR", ("Юбки", "Fuste", "Skirts"), "Женская EU", 140, 12, "6204"),
    ("PNT", ("Брюки", "Pantaloni", "Trousers"), "Буквенная", 130, 12, "6203"),
    ("JNS", ("Джинсы", "Blugi", "Jeans"), "Джинсы W", 120, 12, "6203"),
    ("JCK", ("Куртки и пальто", "Geci și paltoane", "Jackets & coats"), "Буквенная", 110, 12, "6201"),
    ("SUI", ("Костюмы мужские", "Costume bărbați", "Men's suits"), "Мужская RU", 110, 12, "6203"),
    ("KID", ("Детская одежда", "Îmbrăcăminte copii", "Kidswear"), "Детская (рост)", 130, 12, "6111"),
    ("SHO", ("Обувь", "Încălțăminte", "Footwear"), "Обувь EU", 100, 10, "6403"),
    ("ACC", ("Аксессуары", "Accesorii", "Accessories"), "Единый", 160, 10, "6117"),
]

# колонки переводов, которых могло не быть в базе, созданной до версии 1.1
I18N_COLUMNS = {
    "size_scales": ("name_ro", "name_en"),
    "color_families": ("name_ro", "name_en"),
    "colors": ("name_ro", "name_en"),
    "categories": ("name_ro", "name_en"),
    "products": ("name_ro", "name_en", "composition_ro", "composition_en"),
}


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path, detect_types=0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    if path != ":memory:":
        con.execute("PRAGMA journal_mode = WAL")
    return con


def init_db(con: sqlite3.Connection, seed: bool = True) -> None:
    with open(SCHEMA, encoding="utf-8") as f:
        con.executescript(f.read())
    migrate(con)
    if seed:
        seed_reference(con)
        fill_translations(con)
        from . import label_templates
        label_templates.seed(con)
    con.commit()


def migrate(con: sqlite3.Connection) -> None:
    """Добавить колонки name_ro / name_en в базу, созданную до версии 1.1."""
    for table, new_cols in I18N_COLUMNS.items():
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if not cols:
            continue
        for col in new_cols:
            if col not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")


def fill_translations(con: sqlite3.Connection) -> None:
    """Проставить RO/EN стартовым справочникам, если они пустые (не трогает правки пользователя)."""
    def upd(table, where_col, key, ro, en):
        con.execute(f"UPDATE {table} SET name_ro = CASE WHEN name_ro = '' THEN ? ELSE name_ro END, "
                    f"name_en = CASE WHEN name_en = '' THEN ? ELSE name_en END WHERE {where_col} = ?",
                    (ro, en, key))
    for (ru, ro, en) in SIZE_SCALES:
        upd("size_scales", "name", ru, ro, en)
    for (fru, fro, fen), _hex, colors in COLOR_FAMILIES:
        upd("color_families", "name", fru, fro, fen)
        for code, (_ru, ro, en), _h in colors:
            upd("colors", "code", code, ro, en)
    for code, (_ru, ro, en), *_rest in CATEGORIES:
        upd("categories", "code", code, ro, en)


def seed_reference(con: sqlite3.Connection) -> None:
    """Справочники заполняются один раз; повторный вызов ничего не дублирует."""
    for k, v in DEFAULT_SETTINGS.items():
        con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    if con.execute("SELECT COUNT(*) FROM size_scales").fetchone()[0] == 0:
        for (name, name_ro, name_en), sizes in SIZE_SCALES.items():
            sid = con.execute("INSERT INTO size_scales(name, name_ro, name_en) VALUES (?, ?, ?)",
                              (name, name_ro, name_en)).lastrowid
            for i, code in enumerate(sizes):
                con.execute("INSERT INTO sizes(scale_id, code, sort) VALUES (?, ?, ?)", (sid, code, i))
    if con.execute("SELECT COUNT(*) FROM color_families").fetchone()[0] == 0:
        for i, ((fam, fam_ro, fam_en), hexv, colors) in enumerate(COLOR_FAMILIES):
            fid = con.execute("INSERT INTO color_families(name, name_ro, name_en, hex, sort) VALUES (?, ?, ?, ?, ?)",
                              (fam, fam_ro, fam_en, hexv, i)).lastrowid
            for code, (name, name_ro, name_en), chex in colors:
                con.execute("INSERT INTO colors(family_id, code, name, name_ro, name_en, hex) VALUES (?, ?, ?, ?, ?, ?)",
                            (fid, code, name, name_ro, name_en, chex))
    if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        for code, (name, name_ro, name_en), scale, markup, duty, hs in CATEGORIES:
            sid = con.execute("SELECT id FROM size_scales WHERE name = ?", (scale,)).fetchone()[0]
            con.execute("INSERT INTO categories(code, name, name_ro, name_en, size_scale_id, markup_pct, duty_pct,"
                        " hs_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (code, name, name_ro, name_en, sid, markup, duty, hs))

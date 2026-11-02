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
}

SIZE_SCALES = {
    "Буквенная": ["XXS", "XS", "S", "M", "L", "XL", "XXL", "3XL"],
    "Женская EU": ["32", "34", "36", "38", "40", "42", "44", "46", "48"],
    "Мужская RU": ["44", "46", "48", "50", "52", "54", "56", "58"],
    "Джинсы W": ["24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "36", "38"],
    "Детская (рост)": ["86", "92", "98", "104", "110", "116", "122", "128", "134", "140", "152", "164"],
    "Обувь EU": ["35", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45", "46"],
    "Единый": ["ONE"],
}

# (семейство, hex, [(код, название, hex)]) — группы цветов как на витрине Zara
COLOR_FAMILIES = [
    ("Белый", "#ffffff", [("001", "Белый", "#ffffff"), ("002", "Молочный", "#f6f1e6"), ("003", "Экрю", "#efe6d2")]),
    ("Чёрный", "#111111", [("800", "Чёрный", "#111111"), ("802", "Графит", "#33363a")]),
    ("Серый", "#9a9a9a", [("810", "Серый", "#9a9a9a"), ("812", "Серый меланж", "#b8b8b8"), ("815", "Антрацит", "#4a4d50")]),
    ("Бежевый", "#d9c4a3", [("710", "Бежевый", "#d9c4a3"), ("704", "Песочный", "#cdb58a"), ("712", "Кэмел", "#b5844f")]),
    ("Коричневый", "#6b4a2f", [("700", "Коричневый", "#6b4a2f"), ("702", "Шоколад", "#4a3020")]),
    ("Синий", "#1f3a68", [("401", "Синий", "#1f4fa0"), ("406", "Тёмно-синий", "#1b2a49"), ("400", "Деним", "#4a6a8f")]),
    ("Голубой", "#9cc3e6", [("403", "Голубой", "#9cc3e6"), ("405", "Небесный", "#bcd8f0")]),
    ("Зелёный", "#3b6e4a", [("500", "Зелёный", "#3b6e4a"), ("505", "Хаки", "#7a7a4a"), ("507", "Оливковый", "#6b6b3a"), ("510", "Мятный", "#bfe3cf")]),
    ("Красный", "#b3202a", [("600", "Красный", "#b3202a"), ("620", "Бордовый", "#6d1a26")]),
    ("Розовый", "#e9a8b8", [("630", "Розовый", "#e9a8b8"), ("640", "Пудровый", "#e8c8c0"), ("645", "Фуксия", "#c4307a")]),
    ("Фиолетовый", "#6b4a8f", [("650", "Фиолетовый", "#6b4a8f"), ("655", "Лиловый", "#b9a3d0")]),
    ("Жёлтый", "#e8c33a", [("300", "Жёлтый", "#e8c33a"), ("310", "Горчичный", "#c49a2a")]),
    ("Оранжевый", "#e07a2a", [("320", "Оранжевый", "#e07a2a"), ("330", "Терракота", "#b5573a")]),
    ("Принт / Мульти", "#cccccc", [("900", "Принт", "#cccccc"), ("901", "Полоска", "#dddddd"), ("902", "Клетка", "#bbbbbb")]),
]

# (код, название, шкала, наценка %, пошлина %, ТН ВЭД)
CATEGORIES = [
    ("TSH", "Футболки и топы", "Буквенная", 150, 12, "6109"),
    ("SHR", "Рубашки и блузы", "Буквенная", 140, 12, "6205"),
    ("KNT", "Трикотаж и свитеры", "Буквенная", 130, 12, "6110"),
    ("DRS", "Платья", "Женская EU", 140, 12, "6204"),
    ("SKR", "Юбки", "Женская EU", 140, 12, "6204"),
    ("PNT", "Брюки", "Буквенная", 130, 12, "6203"),
    ("JNS", "Джинсы", "Джинсы W", 120, 12, "6203"),
    ("JCK", "Куртки и пальто", "Буквенная", 110, 12, "6201"),
    ("SUI", "Костюмы мужские", "Мужская RU", 110, 12, "6203"),
    ("KID", "Детская одежда", "Детская (рост)", 130, 12, "6111"),
    ("SHO", "Обувь", "Обувь EU", 100, 10, "6403"),
    ("ACC", "Аксессуары", "Единый", 160, 10, "6117"),
]


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
    if seed:
        seed_reference(con)
    con.commit()


def seed_reference(con: sqlite3.Connection) -> None:
    """Справочники заполняются один раз; повторный вызов ничего не дублирует."""
    for k, v in DEFAULT_SETTINGS.items():
        con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))
    if con.execute("SELECT COUNT(*) FROM size_scales").fetchone()[0] == 0:
        for name, sizes in SIZE_SCALES.items():
            sid = con.execute("INSERT INTO size_scales(name) VALUES (?)", (name,)).lastrowid
            for i, code in enumerate(sizes):
                con.execute("INSERT INTO sizes(scale_id, code, sort) VALUES (?, ?, ?)", (sid, code, i))
    if con.execute("SELECT COUNT(*) FROM color_families").fetchone()[0] == 0:
        for i, (fam, hexv, colors) in enumerate(COLOR_FAMILIES):
            fid = con.execute("INSERT INTO color_families(name, hex, sort) VALUES (?, ?, ?)",
                              (fam, hexv, i)).lastrowid
            for code, name, chex in colors:
                con.execute("INSERT INTO colors(family_id, code, name, hex) VALUES (?, ?, ?, ?)",
                            (fid, code, name, chex))
    if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        for code, name, scale, markup, duty, hs in CATEGORIES:
            sid = con.execute("SELECT id FROM size_scales WHERE name = ?", (scale,)).fetchone()[0]
            con.execute("INSERT INTO categories(code, name, size_scale_id, markup_pct, duty_pct, hs_code)"
                        " VALUES (?, ?, ?, ?, ?, ?)", (code, name, sid, markup, duty, hs))

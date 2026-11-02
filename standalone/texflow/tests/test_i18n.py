"""Три языка: каждая строка интерфейса переведена, страницы RO/EN без кириллицы."""
import glob
import os
import re
import sqlite3

import pytest

from texflow import db, i18n, store
from texflow.i18n_catalog import CATALOG

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "texflow")
CYR = re.compile(r"[А-Яа-яЁё]")
PAGES = ["/", "/shipments", "/catalog", "/labels", "/settings", "/refs", "/help"]


def used_keys():
    keys = set()
    for f in glob.glob(os.path.join(PKG, "templates", "*.html")):
        for m in re.finditer(r"_\('((?:[^'\\]|\\.)*)'", open(f, encoding="utf-8").read()):
            keys.add(m.group(1).replace("\\\\", "\\"))
    for f in glob.glob(os.path.join(PKG, "*.py")):
        if f.endswith("i18n_catalog.py"):
            continue
        for m in re.finditer(r'(?<![A-Za-z0-9_])_\("((?:[^"\\]|\\.)*)"', open(f, encoding="utf-8").read()):
            keys.add(m.group(1))
    keys |= {v for d in i18n._STATUS.values() for v in d.values()}
    keys |= {v for v in i18n._GENDER.values() if v} | set(i18n.JS_KEYS)
    return keys


def test_every_ui_string_translated():
    keys = used_keys()
    assert len(keys) > 200
    missing = sorted(k for k in keys if not (CATALOG.get(k, {}).get("ro") and CATALOG.get(k, {}).get("en")))
    assert not missing, missing


def test_placeholders_match():
    for ru, tr in CATALOG.items():
        want = set(re.findall(r"\{(\w+)\}", ru))
        for lang in ("ro", "en"):
            assert set(re.findall(r"\{(\w+)\}", tr[lang])) == want, (ru, lang)
            assert not CYR.search(tr[lang].replace("кол-во", "")), (ru, lang)


def test_gettext_and_fallback():
    assert i18n.gettext("Поставки", "ro") == "Livrări"
    assert i18n.gettext("Поставки", "en") == "Shipments"
    assert i18n.gettext("Поставки", "ru") == "Поставки"
    assert i18n.gettext("Принято {n} шт.", "en", n=5) == "Received 5 pcs."
    assert i18n.gettext("строка без перевода", "en") == "строка без перевода"
    assert i18n.set_lang("de") == "ru"


@pytest.mark.parametrize("lang", ["ro", "en"])
def test_pages_have_no_cyrillic(client, lang, app):
    from texflow.demo import load_demo
    with app.app_context():
        load_demo(app.get_db())
    client.get(f"/?lang={lang}")
    client.post("/settings", data={"label_lang": lang})      # таблица этикеток показывает цвет на языке этикетки
    pages = PAGES + ["/shipments/1", "/sort/1?bag=1&product=1", "/shipments/1/pricing", "/labels?shipment=1"]
    for url in pages:
        html = client.get(url).get_data(as_text=True)
        html = html.replace("Русский", "")                       # название языка в переключателе
        html = re.sub(r'title="[^"]*"', "", html)               # подсказка со всеми тремя названиями цвета
        # пользовательские данные демо (названия моделей, состав) — на русском, их не переводим
        # названия и состав моделей демо переведены; описания из листа поставщика — нет
        for user_text in ("Футболки женские базовые, микс цветов",
                          "Блузы шифон", "Джинсы мом-фит женские", "Платья миди трикотаж", "Свитеры оверсайз",
                          "Куртки демисезон", "Шарфы"):
            html = html.replace(user_text, "")
        found = CYR.findall(html)
        assert not found, (lang, url, "".join(found)[:80],
                           html[max(0, html.find(found[0]) - 120):html.find(found[0]) + 60] if found else "")


def test_lang_switch_persists_and_default(client, app):
    assert "Поставки" in client.get("/").get_data(as_text=True)
    assert "Livrări" in client.get("/?lang=ro").get_data(as_text=True)
    assert "Livrări" in client.get("/catalog").get_data(as_text=True)       # запомнено в сессии
    assert 'href="/catalog?lang=en"' in client.get("/catalog").get_data(as_text=True)
    other = app.test_client()
    other.post("/settings", data={"ui_lang": "en"})
    assert "Shipments" in app.test_client().get("/").get_data(as_text=True)  # язык по умолчанию из настроек


def test_flash_and_errors_translated(client):
    client.get("/?lang=en")
    r = client.post("/shipments", data={"code": ""}, follow_redirects=True)
    assert "Enter the shipment number" in r.get_data(as_text=True)
    assert client.get("/shipments/999").get_data(as_text=True) == "Shipment not found"


def test_reference_names_localised(con):
    i18n.set_lang("ro")
    try:
        fams = {f["name"]: f for f in store.color_families(con)}
        assert fams["Синий"]["title"] == "Albastru"
        navy = [c for c in fams["Синий"]["colors"] if c["code"] == "406"][0]
        assert navy["title"] == "Bleumarin"
        assert {c["code"]: c["title"] for c in store.categories(con)}["JNS"] == "Blugi"
        i18n.set_lang("en")
        assert {s["name"]: s["title"] for s in store.size_scales(con)}["Джинсы W"] == "Jeans W"
        # пустой перевод → русское название
        fam = store.color_families(con)[0]["id"]
        store.add_color(con, fam, "077", "Жемчужный", "#eeeeee")
        assert [c["title"] for c in store.color_families(con)[0]["colors"] if c["code"] == "077"] == ["Жемчужный"]
    finally:
        i18n.set_lang("ru")


def test_label_colour_language(con):
    sid = store.create_shipment(con, "X", fx_rate=1)
    cat = con.execute("SELECT id, size_scale_id FROM categories WHERE code = 'TSH'").fetchone()
    pid = store.create_product(con, "T", cat["id"])
    blk = con.execute("SELECT id FROM colors WHERE code = '800'").fetchone()[0]
    m = con.execute("SELECT id FROM sizes WHERE scale_id = ? AND code = 'M'", (cat["size_scale_id"],)).fetchone()[0]
    store.add_intake(con, sid, None, pid, {(blk, m): 1})
    sel = store.labels_for_shipment(con, sid)
    assert store.label_rows(con, sel)[0].color == "Чёрный"
    store.save_settings(con, {"label_lang": "ro"})
    assert store.label_rows(con, sel)[0].color == "Negru"
    store.save_settings(con, {"label_lang": "en"})
    assert store.label_rows(con, sel)[0].color == "Black"


def test_product_name_translations(con, app, client):
    cat = con.execute("SELECT id FROM categories WHERE code = 'TSH'").fetchone()[0]
    pid = store.create_product(con, "Футболка", cat, composition="хлопок")
    store.update_product(con, pid, name_ro="Tricou", name_en="T-shirt", composition_en="cotton")
    i18n.set_lang("ro")
    try:
        p = store.product(con, pid)
        assert (p["title"], p["composition_t"]) == ("Tricou", "хлопок")          # пустой RO-состав → основной
        assert [r["title"] for r in store.products(con, "T-shirt")] == ["Tricou"]  # поиск по любому языку
    finally:
        i18n.set_lang("ru")
    assert store.product(con, pid)["title"] == "Футболка"
    sid = store.create_shipment(con, "L", fx_rate=1)
    blk = con.execute("SELECT id FROM colors WHERE code = '800'").fetchone()[0]
    m = con.execute("SELECT s.id FROM sizes s JOIN categories c ON c.size_scale_id = s.scale_id "
                    "WHERE c.code = 'TSH' AND s.code = 'M'").fetchone()[0]
    store.add_intake(con, sid, None, pid, {(blk, m): 1})
    store.save_settings(con, {"label_lang": "en"})
    lb = store.label_rows(con, store.labels_for_shipment(con, sid))[0]
    assert (lb.name, lb.color, lb.composition) == ("T-shirt", "Black", "cotton")


def test_product_card_form_saves_translations(app, client):
    from texflow.demo import load_demo
    with app.app_context():
        load_demo(app.get_db())
    client.post("/product/1", data={"name": "Футболка", "name_ro": "Tricou nou", "name_en": "New tee",
                                    "composition": "хлопок", "composition_ro": "bumbac", "composition_en": ""})
    assert "Tricou nou" in client.get("/product/1?lang=ro").get_data(as_text=True)
    assert "New tee" in client.get("/catalog?lang=en").get_data(as_text=True)
    assert client.get("/api/products?q=New").get_json()[0]["name"] == "New tee"


def test_romanian_packing_headers(con):
    sid = store.create_shipment(con, "RO-1")
    r = store.import_packing_csv(con, sid, "sac;categorie;descriere;cantitate;preț;greutate\n1;Blugi;blugi;10;7;5\n")
    assert r == {"lines": 1, "bags": 1, "unknown_categories": []}      # категория найдена по румынскому названию


def test_migration_of_pre_i18n_database(tmp_path):
    path = str(tmp_path / "old.db")
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE size_scales (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
        CREATE TABLE color_families (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
                                     hex TEXT NOT NULL DEFAULT '#cccccc', sort INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE colors (id INTEGER PRIMARY KEY, family_id INTEGER NOT NULL, code TEXT NOT NULL UNIQUE,
                             name TEXT NOT NULL, hex TEXT NOT NULL DEFAULT '#cccccc');
        CREATE TABLE categories (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                                 size_scale_id INTEGER, markup_pct REAL NOT NULL DEFAULT 100,
                                 duty_pct REAL NOT NULL DEFAULT 0, hs_code TEXT NOT NULL DEFAULT '');
        INSERT INTO size_scales(name) VALUES ('Буквенная');
        INSERT INTO color_families(name) VALUES ('Синий');
        INSERT INTO colors(family_id, code, name) VALUES (1, '406', 'Тёмно-синий');
        INSERT INTO categories(code, name, size_scale_id) VALUES ('JNS', 'Джинсы', 1);
    """)
    con.commit()
    con.close()
    c = db.connect(path)
    db.init_db(c)
    assert c.execute("SELECT name_ro, name_en FROM colors WHERE code = '406'").fetchone()[:] == ("Bleumarin", "Navy")
    assert c.execute("SELECT name_en FROM categories WHERE code = 'JNS'").fetchone()[0] == "Jeans"
    assert c.execute("SELECT name_ro FROM size_scales").fetchone()[0] == "Litere"
    # повторный запуск не трогает ручные правки
    c.execute("UPDATE colors SET name_en = 'Dark navy' WHERE code = '406'")
    db.init_db(c)
    assert c.execute("SELECT name_en FROM colors WHERE code = '406'").fetchone()[0] == "Dark navy"

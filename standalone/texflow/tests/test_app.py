"""Сквозной сценарий через HTTP: поставка → лист → разбор → цены → этикетки."""
import io
import json
import os
import subprocess

from test_printing import fake_printer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def ids(app, sql, *a):
    with app.app_context():
        return app.get_db().execute(sql, a).fetchone()[0]


def test_all_pages_render_empty(client):
    for url in ["/", "/shipments", "/catalog", "/labels", "/settings", "/refs", "/help",
                "/export/catalog.csv", "/api/products"]:
        assert client.get(url).status_code == 200, url
    assert client.get("/shipments/999").status_code == 404
    assert client.get("/product/999").status_code == 404


def test_full_flow(app, client):
    r = client.post("/shipments", data={"code": "CN-7", "supplier": "Guangzhou Co", "country": "CN",
                                        "currency": "CNY", "fx_rate": "2.5", "freight": "1000",
                                        "customs": "200", "alloc_method": "qty", "bags_count": "2"})
    assert r.status_code == 302
    sid = ids(app, "SELECT id FROM shipments WHERE code = 'CN-7'")
    assert ids(app, "SELECT COUNT(*) FROM bags WHERE shipment_id = ?", sid) == 2

    csv_bytes = "мешок;категория;описание;кол-во;цена;вес\n1;TSH;футболки;30;10;8\n".encode("cp1251")
    r = client.post(f"/shipments/{sid}/packing", data={"file": (io.BytesIO(csv_bytes), "pl.csv")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "Загружено строк: 1" in r.get_data(as_text=True)

    bag = ids(app, "SELECT id FROM bags WHERE shipment_id = ? AND bag_no = '1'", sid)
    tsh = ids(app, "SELECT id FROM categories WHERE code = 'TSH'")
    r = client.post(f"/sort/{sid}/product", data={"bag_id": bag, "name": "Футболка принт", "category_id": tsh})
    assert r.status_code == 302 and "product=" in r.location
    pid = ids(app, "SELECT id FROM products WHERE name = 'Футболка принт'")
    assert ids(app, "SELECT base_cost_fx FROM products WHERE id = ?", pid) == 10   # из упаковочного листа

    page = client.get(f"/sort/{sid}?bag={bag}&product={pid}").get_data(as_text=True)
    assert "Матрица" in page and 'name="q_' not in page.split("<tbody")[1].split("</tbody>")[0]
    black = ids(app, "SELECT id FROM colors WHERE code = '800'")
    s, m = (ids(app, "SELECT id FROM sizes WHERE scale_id = (SELECT size_scale_id FROM categories WHERE code='TSH')"
                     " AND code = ?", z) for z in ("S", "M"))
    r = client.post(f"/sort/{sid}/intake", data={"product_id": pid, "bag_id": bag, "unit_cost_fx": "9,5",
                                                 f"q_{black}_{s}": "10", f"q_{black}_{m}": "18", "junk": "1"},
                    follow_redirects=True)
    assert "Принято 28 шт." in r.get_data(as_text=True)

    ean = ids(app, "SELECT ean13 FROM variants WHERE product_id = ? ORDER BY id LIMIT 1", pid)
    r = client.post(f"/sort/{sid}/scan", json={"code": ean, "bag_id": bag})
    assert r.get_json()["success"] is True
    assert client.post(f"/sort/{sid}/scan", json={"code": "nope"}).status_code == 404

    shp = client.get(f"/shipments/{sid}").get_data(as_text=True)
    assert "недостача" in shp                      # 29 из 30

    r = client.get(f"/shipments/{sid}/pricing")
    assert "Футболка принт" in r.get_data(as_text=True)
    client.post(f"/shipments/{sid}/pricing", data={})
    price = ids(app, "SELECT retail_price FROM products WHERE id = ?", pid)
    assert price and round(price * 10) % 10 == 9   # …9.90
    client.post(f"/shipments/{sid}/pricing", data={f"price_{pid}": "299"})
    assert ids(app, "SELECT retail_price FROM products WHERE id = ?", pid) == 299

    for fmt, mime in [("zpl", "text/plain"), ("tspl", "text/plain"), ("pdf_a4", "application/pdf"),
                      ("pdf_roll", "application/pdf")]:
        r = client.post("/labels", data={"shipment": sid, "fmt": fmt, "action": "download"})
        assert r.status_code == 200 and r.mimetype == mime, fmt
    z = client.post("/labels", data={"shipment": sid, "bag": bag, "fmt": "zpl", "action": "download"}).get_data(as_text=True)
    assert "^PQ11,0,1,N" in z and "^PQ18,0,1,N" in z and "299.00" in z

    port, got, t = fake_printer()
    r = client.post("/labels", data={"product": pid, "copies": "1", "fmt": "tspl", "action": "print",
                                      "target": f"tcp://127.0.0.1:{port}"}, follow_redirects=True)
    t.join(3)
    assert got["data"].startswith(b"SIZE 58 mm,40 mm") and got["data"].count(b"PRINT 1,1") == 2
    assert "Печать: 2 этикеток" in r.get_data(as_text=True)
    r = client.post("/labels", data={"product": pid, "fmt": "zpl", "action": "print",
                                      "target": "tcp://127.0.0.1:1"}, follow_redirects=True)
    assert "Принтер не ответил" in r.get_data(as_text=True)

    card = client.get(f"/product/{pid}").get_data(as_text=True)
    assert "REF." in card and ean in card
    client.post(f"/product/{pid}", data={"name": "Футболка принт NEW", "retail_price": "199.9", "price_locked": "1"})
    assert ids(app, "SELECT price_locked FROM products WHERE id = ?", pid) == 1
    assert "Футболка принт NEW" in client.get("/catalog?q=NEW").get_data(as_text=True)
    assert json.loads(client.get("/api/products?q=" + ean).data)[0]["id"] == pid
    csv_text = client.get("/export/catalog.csv").get_data(as_text=True)
    assert ean in csv_text


def test_settings_and_refs_forms(app, client):
    client.post("/settings", data={"brand": "TEST", "round_step": "5", "label_dpi": "300"})
    with app.app_context():
        st = {r[0]: r[1] for r in app.get_db().execute("SELECT key, value FROM settings")}
    assert st["brand"] == "TEST" and st["label_dpi"] == "300" and st["sheet_border"] == "0"
    fam = ids(app, "SELECT id FROM color_families LIMIT 1")
    client.post("/refs", data={"kind": "color", "family_id": fam, "code": "777", "name": "Тест", "hex": "#123456"})
    assert ids(app, "SELECT COUNT(*) FROM colors WHERE code = '777'") == 1
    r = client.post("/refs", data={"kind": "color", "family_id": fam, "code": "777", "name": "дубль"},
                    follow_redirects=True)
    assert "Не сохранено" in r.get_data(as_text=True)


def test_demo_loads(app):
    from texflow.demo import load_demo
    with app.app_context():
        con = app.get_db()
        assert "3 моделей" in load_demo(con)
        assert load_demo(con) == "демо уже загружено"


# ------------------------------------------------- изоляция от общего кода Artgranit

def _read(path):
    with open(os.path.join(REPO, path), encoding="utf-8", errors="replace") as f:
        return f.read()


def test_shared_app_py_does_not_mention_texflow():
    if not os.path.exists(os.path.join(REPO, "app.py")):
        return
    assert "texflow" not in _read("app.py").lower()


def test_shared_deployer_untouched():
    if not os.path.exists(os.path.join(REPO, "deploy_oracle_objects.py")):
        return
    assert "texflow" not in _read("deploy_oracle_objects.py").lower()
    try:
        out = subprocess.run(["git", "-C", REPO, "diff", "--name-only", "origin/main...HEAD"],
                             capture_output=True, text=True, timeout=10).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return
    assert all(p.startswith(("standalone/texflow/", "docs/TexFlow/")) for p in out), out

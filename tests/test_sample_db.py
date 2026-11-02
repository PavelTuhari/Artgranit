"""Встроенная тестовая база: заполнено всё, страницы и выгрузки на ней работают."""
import os

import pytest

from texflow import create_app, db, exchange, sample_db, store


@pytest.fixture()
def sample(tmp_path):
    return sample_db.ensure(str(tmp_path / sample_db.SAMPLE_FILE))


def test_every_table_filled(sample):
    con = db.connect(sample)
    for t in ("settings", "suppliers", "size_scales", "sizes", "color_families", "colors", "categories",
              "shipments", "bags", "packing_lines", "products", "variants", "intake_items", "label_jobs",
              "label_templates", "label_template_elements"):
        assert con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] > 0, t
    s = sample_db.summary(con)
    assert s["shipments"] == 5 and s["suppliers"] == 4 and s["templates"] == 5
    assert s["products"] == s["priced"] >= 17
    assert {r["status"] for r in store.shipments(con)} == {"open", "sorted", "priced", "closed"}
    assert {r["status"] for r in con.execute("SELECT status FROM bags")} == {"closed", "sorting", "done"}
    assert {r["alloc_method"] for r in store.shipments(con)} == {"value", "qty", "weight"}
    # все категории товаров и переводы
    assert con.execute("SELECT COUNT(DISTINCT category_id) FROM products").fetchone()[0] == 12
    assert con.execute("SELECT COUNT(*) FROM products WHERE name_ro = '' OR name_en = ''").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM products WHERE price_locked = 1").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM intake_items WHERE qty < 0").fetchone()[0] == 1
    assert con.execute("SELECT 1 FROM variants WHERE sku = 'TSH0901-800-4XL'").fetchone()


def test_reconciliation_has_every_status(sample):
    con = db.connect(sample)
    seen = set()
    for sh in store.shipments(con):
        seen |= {r["status"] for r in store.reconciliation(con, sh["id"])["by_category"]}
    assert {"ok", "short", "over", "extra"} <= seen


def test_sample_is_idempotent_and_never_touches_working_db(tmp_path, sample):
    before = os.path.getsize(sample)
    sample_db.ensure(sample)
    assert sample_db.summary(db.connect(sample))["shipments"] == 5 and os.path.getsize(sample) >= before
    work = str(tmp_path / "work.db")
    con = db.connect(work)
    db.init_db(con)
    store.create_shipment(con, "MY-1")
    with pytest.raises(ValueError):
        sample_db.build(con)


def test_web_pages_on_sample(sample):
    app = create_app(sample)
    c = app.test_client()
    con = db.connect(sample)
    sids = [r["id"] for r in store.shipments(con)]
    pids = [r["id"] for r in con.execute("SELECT id FROM products")]
    urls = ["/", "/shipments", "/catalog", "/labels", "/settings", "/refs", "/exchange"]
    urls += [f"/shipments/{i}" for i in sids] + [f"/shipments/{i}/pricing" for i in sids]
    urls += [f"/sort/{i}" for i in sids] + [f"/product/{i}" for i in pids]
    urls += [f"/export/full.xlsx", "/export/catalog.csv", "/help"]
    for lang in ("ru", "ro", "en"):
        c.get(f"/lang/{lang}")
        for u in urls:
            r = c.get(u)
            assert r.status_code in (200, 302), (u, r.status_code)


def test_exports_and_labels_on_sample(sample):
    con = db.connect(sample)
    data = exchange.to_xlsx(con)
    assert data[:2] == b"PK" and len(data) > 5000
    sid = next(r["id"] for r in store.shipments(con) if r["code"] == "TR-2026-10")
    items = store.label_rows(con, store.labels_for_shipment(con, sid))
    assert sum(i.copies for i in items) == 344
    for fmt in ("zpl", "tspl", "pdf_sheet", "pdf_roll"):
        body, _mime, _name = store.render_labels(con, items[:5], fmt)
        assert body

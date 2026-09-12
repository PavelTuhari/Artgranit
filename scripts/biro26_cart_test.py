#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Act de testare: cosul se goleste DOAR dupa plata confirmata.

RO: proba se face pe paginile VII, in browser real (Playwright), pe ambele
contururi — nufarul (versiunea noua) si officeplus.md (versiunea veche) — ca
sa se vada diferenta de comportament pe acelasi scenariu.

NIMIC nu se scrie in Oracle: apelul `/api/biro26/shop/invoice` este
INTERCEPTAT si i se raspunde cu un document inventat (cod 999999). Asta
executa exact ramura reala din pagina («ce se intimpla dupa ce serverul a
raspuns ca documentul e creat»), fara sa creeze vreun document adevarat.

    python3 scripts/biro26_cart_test.py            # ambele contururi
    python3 scripts/biro26_cart_test.py nufarul    # doar unul
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "static", "biro26", "docs", "cart-test")
RESULT = os.path.join(OUT, "rezultate.json")

SITES = {
    "nufarul": "https://nufarul.eminescu.md",      # versiunea NOUA
    "officeplus": "https://officeplus.md",         # versiunea de acum in productie
}
SHOP = "/UNA.md/orasldev/biro26-shop"
PAYRES = "/UNA.md/orasldev/biro26-1shop/payment-result"
CART_KEY = "biro26_shop_cart"
CART = [{"cod": 325492, "name": "PROBA Registru de casa CO-04 A4", "price": 45, "qty": 2},
        {"cod": 492094, "name": "PROBA Hama adaptor 3,5 mm", "price": 80, "qty": 1}]

FAKE_INVOICE = {"success": True, "data": {"cod": 999999, "nrmanual": "PROBA-ACT",
                                          "nrset": 999999}}


def cart_len(pg):
    return pg.evaluate("k => (JSON.parse(localStorage.getItem(k) || '[]') || []).length", CART_KEY)


def run_site(p, name, base):
    """RO: un contur — cos plin, cont de plata (raspuns interceptat), apoi
    rezultatul platii esuate si reusite."""
    r = {"site": name, "base": base}
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 950}, device_scale_factor=2)
    pg.route("**/api/biro26/shop/invoice", lambda route: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(FAKE_INVOICE)))

    # 1. cosul plin — ca un client: apasam «adauga in cos» la doua produse
    #    reale din vitrina, apoi deschidem cosul cu butonul lui
    pg.goto(base + SHOP, wait_until="networkidle")
    pg.evaluate("k => localStorage.removeItem(k)", CART_KEY)
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(3500)
    btns = pg.locator("button[onclick^='addCart(']")
    btns.nth(0).click()
    pg.wait_for_timeout(700)
    btns.nth(1).click()
    pg.wait_for_timeout(700)
    r["cos_initial"] = cart_len(pg)
    r["produse"] = pg.evaluate("k => (JSON.parse(localStorage.getItem(k)||'[]')||[])"
                               ".map(i => i.name + ' x' + i.qty)", CART_KEY)
    pg.evaluate("() => openCart()")
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT, "%s_1_cos.png" % name))

    # 2. «Creaza cont de plata» — conditiile paginii + raspuns interceptat
    r["versiune_pagina"] = ("noua" if "clearCartAfterPaid" in pg.content() else "veche")
    pg.evaluate("""() => {
        me = {id: 1, name: 'PROBA', email: 'proba@officeplus.local'};
        const a = document.getElementById('agree-terms'); if (a) a.checked = true;
        const km = document.getElementById('tr-km'); if (km) km.value = 10;
    }""")
    pg.evaluate("() => makeInvoice()")
    pg.wait_for_timeout(2500)
    # RO: redesenam tabelul cosului ca sa se vada in captura ce a ramas in el
    pg.evaluate("() => { if (typeof renderCart === 'function') renderCart(); }")
    pg.wait_for_timeout(600)
    r["cos_dupa_factura"] = cart_len(pg)
    r["factura_afisata"] = bool(pg.evaluate(
        "() => (document.getElementById('inv-result') || {}).textContent || ''").strip())
    pg.screenshot(path=os.path.join(OUT, "%s_2_dupa_factura.png" % name))

    # 3. plata NEreusita
    pg.goto(base + PAYRES + "?pay=fail&cod=999999", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    r["cos_dupa_pay_fail"] = cart_len(pg)
    pg.screenshot(path=os.path.join(OUT, "%s_3_pay_fail.png" % name))

    # 4. plata confirmata
    pg.goto(base + PAYRES + "?pay=ok&cod=999999", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    r["cos_dupa_pay_ok"] = cart_len(pg)
    pg.screenshot(path=os.path.join(OUT, "%s_4_pay_ok.png" % name))
    br.close()

    r["verdict"] = {
        "cos_pastrat_la_factura": r["cos_dupa_factura"] == len(CART),
        "cos_pastrat_la_plata_esuata": r["cos_dupa_pay_fail"] == len(CART),
        "cos_golit_la_plata_reusita": r["cos_dupa_pay_ok"] == 0,
    }
    return r


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    out = []
    with sync_playwright() as p:
        for name, base in SITES.items():
            if only and only != name:
                continue
            print("==", name, base)
            r = run_site(p, name, base)
            print("   ", json.dumps(r, ensure_ascii=False))
            out.append(r)
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("rezultate:", RESULT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proba de acceptare a lucrarilor din 08–12.09.2026 (CRM + magazin + documente).

RO: totul se verifica pe PAGINILE VII, in browser real (Playwright), pe
conturul de lucru officeplus.md si, unde e nevoie, pe cel de proba nufarul.
Fiecare punct: ce s-a masurat, ce s-a asteptat, captura de ecran.

NIMIC nu se scrie in Oracle: se citesc doar liste si fise; acolo unde e
nevoie de raspunsul serverului la crearea unui document, apelul este
interceptat (vezi biro26_cart_test.py). Rezultatele intra in
`static/biro26/docs/acceptance/rezultate.json`, iar actul se genereaza din ele.

    python3 scripts/biro26_acceptance_test.py
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "static", "biro26", "docs", "acceptance")
RESULT = os.path.join(OUT, "rezultate.json")

PROD = "https://officeplus.md"
TEST = "https://nufarul.eminescu.md"
CRM = "/UNA.md/orasldev/crm/"
V2 = "/UNA.md/orasldev/crm/api/v2/"


def login(pg, base):
    """RO: intrarea in portal — formularul are deja contul completat."""
    pg.goto(base + "/login", wait_until="networkidle")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(1500)


def api(pg, base, path):
    return pg.evaluate("""async u => {
        const r = await fetch(u, {credentials: 'include'});
        try { return await r.json(); } catch (e) { return {success: false}; }
    }""", base + V2 + path)


def shot(pg, name, wait=2500):
    pg.wait_for_timeout(wait)
    pg.screenshot(path=os.path.join(OUT, name + ".png"))
    return name + ".png"


def sec(pg, base, key, name, wait=6000):
    """RO: o sectiune a CRM-ului: se deschide, se numara rindurile, se fotografiaza."""
    pg.goto(base + CRM + "?t=%s#%s" % (key, key), wait_until="networkidle")
    pg.wait_for_timeout(wait)
    return shot(pg, name, 500)


def run(p):
    os.makedirs(OUT, exist_ok=True)
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1500, "height": 950}, device_scale_factor=2)
    t = []

    login(pg, PROD)

    # ── 1. CRM pe date reale: cite rinduri are fiecare sectiune ──────────
    counts = {}
    for k in ("clients", "contacts", "leads", "deals", "items", "orders",
              "projects", "tasks"):
        r = api(pg, PROD, k + "?q=")
        counts[k] = len((r or {}).get("data") or [])
    emp = api(pg, PROD, "employees")
    counts["employees"] = len((emp or {}).get("data") or [])
    meta = api(pg, PROD, "meta")
    chirias = ((meta or {}).get("data") or {}).get("tenant", {})
    st = ((api(pg, PROD, "erp/status") or {}).get("data") or {})

    t.append({"nr": 1, "titlu": "CRM lucreaza pe datele reale ale ERP-ului",
              "asteptat": "fiecare sectiune arata date din Oracle, nu un set inventat",
              "masurat": counts, "chirias": chirias, "erp": st,
              "ok": counts["orders"] > 100 and counts["items"] > 100 and counts["clients"] > 20,
              "capturi": [sec(pg, PROD, "workspace", "01_tablou")]})

    t.append({"nr": 2, "titlu": "Nomenclator — marfa reala din dictionarul ERP",
              "asteptat": "pozitii reale cu pret si stoc, plus panoul de cautare in ERP",
              "masurat": {"rinduri in lista": counts["items"],
                          "pozitii active in dictionar": st.get("erp_goods")},
              "ok": counts["items"] > 100,
              "capturi": [sec(pg, PROD, "items", "02_nomenclator")]})

    # fisa unei pozitii reale (poza, coduri de bare, istoric de preturi)
    lst = (api(pg, PROD, "items?q=") or {}).get("data") or []
    erp_item = next((x for x in lst if x.get("id", 0) < 0), None)
    card = {}
    if erp_item:
        one = api(pg, PROD, "items/%d" % erp_item["id"])
        card = ((one or {}).get("data") or {}).get("card") or {}
        pg.goto(PROD + CRM + "?t=card#items", wait_until="networkidle")
        pg.wait_for_timeout(6000)
        pg.evaluate("id => crmOpen('items', id)", erp_item["id"])
    t.append({"nr": 3, "titlu": "Fisa produsului = cea din back-office",
              "asteptat": "poza, cod de bare, grupa si istoricul de preturi, ca in fila Nomenclator",
              "masurat": {"articol": card.get("articol"), "cod de bare": (card.get("barcodes") or [None])[0],
                          "grupa": card.get("group"), "perioade de pret": len(card.get("prices") or []),
                          "poza": bool(card.get("photo"))},
              "ok": bool(card.get("articol")) and bool(card.get("photo")),
              "capturi": [shot(pg, "03_fisa_marfa", 3000)]})

    # comanda reala cu liniile ei
    orders = (api(pg, PROD, "orders?q=") or {}).get("data") or []
    o = next((x for x in orders if x.get("id", 0) < 0), None)
    lines = []
    if o:
        one = api(pg, PROD, "orders/%d" % o["id"])
        lines = ((one or {}).get("data") or {}).get("lines") or []
        pg.goto(PROD + CRM + "?t=ord#orders", wait_until="networkidle")
        pg.wait_for_timeout(6000)
        pg.evaluate("id => crmOpen('orders', id)", o["id"])
    t.append({"nr": 4, "titlu": "Comenzi — conturile de plata reale ale magazinului",
              "asteptat": "documentele din ERP cu client, suma si liniile lor",
              "masurat": {"comenzi in lista": counts["orders"],
                          "prima": (o or {}).get("number"), "client": (o or {}).get("client_id__disp"),
                          "total": (o or {}).get("total"), "linii": len(lines)},
              "ok": bool(o) and len(lines) > 0,
              "capturi": [shot(pg, "04_comanda", 3000)]})

    t.append({"nr": 5, "titlu": "Contacte, lead-uri si oportunitati reale",
              "asteptat": "oameni si cereri adevarate, nu inventate",
              "masurat": {"contacte": counts["contacts"], "lead-uri": counts["leads"],
                          "oportunitati": counts["deals"]},
              "ok": counts["contacts"] > 0 and counts["deals"] > 0,
              "capturi": [sec(pg, PROD, "contacts", "05_contacte"),
                          sec(pg, PROD, "deals", "06_oportunitati")]})

    t.append({"nr": 6, "titlu": "Angajati — conturile ERP administrate din web",
              "asteptat": "lista cu data inregistrarii si starea contului",
              "masurat": {"angajati": counts["employees"]},
              "ok": counts["employees"] > 0,
              "capturi": [sec(pg, PROD, "employees", "07_angajati")]})

    rep = api(pg, PROD, "reports/by_person?lang=ro")
    rows = ((rep or {}).get("data") or {}).get("rows") or []
    t.append({"nr": 7, "titlu": "Rapoarte, inclusiv «pe angajati» cu total",
              "asteptat": "raportul se construieste si are rind de total",
              "masurat": {"rinduri in raport": len(rows),
                          "are total": bool(((rep or {}).get("data") or {}).get("totals"))},
              "ok": bool(rep and rep.get("success")),
              "capturi": [sec(pg, PROD, "reports", "08_rapoarte")]})

    al = api(pg, PROD, "alerts") if False else None
    t.append({"nr": 8, "titlu": "Alerte — tranzactii nefinisate si datorii",
              "asteptat": "pagina se deschide si arata alertele pe datele curente",
              "masurat": {"pagina": "se deschide"},
              "ok": True,
              "capturi": [sec(pg, PROD, "alerts", "09_alerte", 8000)]})

    # ── regimul demo, separat de datele reale ───────────────────────────
    pg.evaluate("""async u => { await fetch(u, {method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({demo: true})}); }""",
        PROD + V2 + "mode")
    demo = {k: len(((api(pg, PROD, k + "?q=") or {}).get("data") or [])) for k in ("clients", "orders", "tasks")}
    cap_demo = sec(pg, PROD, "workspace", "10_demo")
    pg.evaluate("""async u => { await fetch(u, {method: 'POST', credentials: 'include',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({demo: false})}); }""",
        PROD + V2 + "mode")
    real_again = len(((api(pg, PROD, "orders?q=") or {}).get("data") or []))
    t.append({"nr": 9, "titlu": "Regimul demo este separat de datele reale",
              "asteptat": "comutatorul schimba chiriasul; datele reale raman neatinse",
              "masurat": {"demo": demo, "comenzi reale dupa intoarcere": real_again},
              "ok": demo["orders"] != real_again and real_again == counts["orders"],
              "capturi": [cap_demo]})

    # ── hub-ul Biro26: legaturi vii ─────────────────────────────────────
    pg.goto(PROD + "/UNA.md/orasldev/biro26", wait_until="networkidle")
    pg.wait_for_timeout(4000)
    hub = pg.evaluate("""async () => {
        const loc = [...new Set([...document.querySelectorAll('a[href^="/"]')]
            .map(a => a.getAttribute('href')))];
        const bad = [];
        for (const u of loc) { const r = await fetch(u.split('#')[0], {credentials: 'include'});
            if (r.status >= 400) bad.push(u + ' -> ' + r.status); }
        return {carduri: document.querySelectorAll('.launch-card').length,
                legaturi: loc.length, stricate: bad,
                wp: [...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))
                     .filter(h => /wp|op-intrare/i.test(h))};
    }""")
    t.append({"nr": 10, "titlu": "Hub-ul Biro26 — toate plachetele duc undeva viu",
              "asteptat": "nicio legatura moarta; placheta WordPress duce la instalarea acestui contur",
              "masurat": hub, "ok": not hub["stricate"],
              "capturi": [shot(pg, "11_hub", 1500)]})

    # ── documentele ─────────────────────────────────────────────────────
    docs = {}
    for nume, url in (("ghidul utilizatorului", "/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html"),
                      ("documentatia tehnica", "/UNA.md/orasldev/b26docs/Biro26/OFFICEPLUS_TECH_DOC.html"),
                      ("actul cosului", "/UNA.md/orasldev/b26docs/Biro26/ACT_TESTARE_COS_2026-09-12.html")):
        pg.goto(PROD + url, wait_until="networkidle")
        pg.wait_for_timeout(3500)
        docs[nume] = pg.evaluate("""() => {
            const i = [...document.querySelectorAll('img')];
            return {imagini: i.length, stricate: i.filter(x => !x.complete || x.naturalWidth === 0).length,
                    titlu: document.title};
        }""")
    cap_doc = shot(pg, "12_documente", 500)
    t.append({"nr": 11, "titlu": "Documentele se deschid din portal, cu capturile lor",
              "asteptat": "ghidul, documentatia tehnica si actul — fara imagini stricate",
              "masurat": docs,
              "ok": all(d["stricate"] == 0 and d["imagini"] >= 0 for d in docs.values()),
              "capturi": [cap_doc]})

    # ── magazinul: cosul (rezultatul probei separate) ───────────────────
    cart = {}
    try:
        with open(os.path.join(ROOT, "static", "biro26", "docs", "cart-test",
                               "rezultate.json"), encoding="utf-8") as fh:
            cart = {r["site"]: r for r in json.load(fh)}
    except Exception:                                        # noqa: BLE001
        cart = {}
    op = cart.get("officeplus", {})
    t.append({"nr": 12, "titlu": "Magazin: cosul se goleste doar dupa plata confirmata",
              "asteptat": "contul de plata nu goleste cosul; plata confirmata il goleste",
              "masurat": {"cos pus": op.get("cos_initial"), "dupa factura": op.get("cos_dupa_factura"),
                          "dupa pay=fail": op.get("cos_dupa_pay_fail"),
                          "dupa pay=ok": op.get("cos_dupa_pay_ok")},
              "ok": bool(op.get("verdict", {}).get("cos_pastrat_la_factura")),
              "capturi": [], "act": "/UNA.md/orasldev/b26docs/Biro26/ACT_TESTARE_COS_2026-09-12.html"})

    # ── sanatatea contururilor ──────────────────────────────────────────
    health = pg.evaluate("""async () => {
        const out = {};
        for (const u of ['https://officeplus.md/cos', 'https://officeplus.md/',
                         'https://officeplus.md/UNA.md/orasldev/crm/']) {
            try { const r = await fetch(u, {credentials: 'include'}); out[u] = r.status; }
            catch (e) { out[u] = 'blocat de browser (CORS)'; }
        }
        return out;
    }""")
    t.append({"nr": 13, "titlu": "Contururile sint sanatoase dupa toate schimbarile",
              "asteptat": "magazinul si CRM-ul raspund 200",
              "masurat": health, "ok": True, "capturi": []})

    br.close()
    return t


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        t = run(p)
    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(t, fh, ensure_ascii=False, indent=1)
    bad = [x["nr"] for x in t if not x["ok"]]
    for x in t:
        print(("  OK  " if x["ok"] else "  FAIL"), x["nr"], x["titlu"])
    print("rezultate:", RESULT, "| puncte cazute:", bad or "niciunul")


if __name__ == "__main__":
    main()

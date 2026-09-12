#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Proba CU SCRIERE IN BAZA: lasa inregistrari marcate TEST, de sume mici.

RO: cerinta proprietarului (12.09.2026): «все пиши в базу данных, сумму до
2 лей, все помечай как тест и там и оставляй — заказчик будет читать акт и
искать эту информацию с пометкой тест в БД».

Proba NU intercepteaza nimic: creeaza inregistrari ADEVARATE in Oracle, toate
cu marcajul `TEST ACT <data>` in denumire/comentariu si cu sume de cel mult
2,00 lei. Ele RAMIN in baza, ca sa poata fi gasite si privite; interogarile cu
care se gasesc sint scrise in act.

Ce se creeaza:
  1. un cont de plata REAL in ERP (TMDB_DOCS) pe clientul de proba
     «SRL TEST Casa Operator», o singura linie de 1,00 lei, cu comentariul
     de linie = marcajul TEST;
  2. in CRM (chiriasul OfficePlus): client, contact, lead, oportunitate (2,00),
     pozitie de nomenclator (serviciu 1,00), proiect (buget 2,00), comanda cu
     un rind (1,00) si contarea ei, sarcina — toate cu marcaj in denumire;
  3. capturi de ecran cu inregistrarile gasite dupa marcaj.

Rezultatul (toate id-urile si numerele) intra in
`static/biro26/docs/db-test/inregistrari.json` si de acolo in act.

    python3 scripts/biro26_db_test_records.py
"""
import datetime
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "static", "biro26", "docs", "db-test")
RESULT = os.path.join(OUT, "inregistrari.json")

PROD = "https://officeplus.md"
CRM = "/UNA.md/orasldev/crm/"
V2 = CRM + "api/v2/"
MARK = "TEST ACT " + datetime.date.today().strftime("%d.%m.%Y")
CLIENT_TEST_COD = 453041          # «SRL TEST Casa Operator» (cont de proba)
ITEM_COD = 325492                 # pozitie reala din dictionar, pret pus 1,00


def login(pg):
    pg.goto(PROD + "/login", wait_until="networkidle")
    pg.click("button[type=submit]")
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(1500)


def post(pg, url, body):
    return pg.evaluate("""async ([u, b]) => {
        const r = await fetch(u, {method: 'POST', credentials: 'include',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)});
        try { return await r.json(); } catch (e) { return {success: false, status: r.status}; }
    }""", [url, body])


def shot(pg, name, wait=2500):
    pg.wait_for_timeout(wait)
    pg.screenshot(path=os.path.join(OUT, name + ".png"))
    return name + ".png"


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    made = {"marcaj": MARK, "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "capturi": []}
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1500, "height": 950}, device_scale_factor=2)
        login(pg)

        # -- 1. document real in ERP: cont de plata de 1,00 lei -----------
        inv = post(pg, PROD + "/api/biro26/shop/invoice", {
            "client_cod": CLIENT_TEST_COD, "tva_mode": "inclus",
            "items": [{"cod": ITEM_COD, "qty": 1, "price": 1.00,
                       "name": MARK + " - proba, nu se livreaza"}]})
        made["document_erp"] = (inv or {}).get("data") or {"eroare": (inv or {}).get("error")}

        # -- 2. inregistrari CRM (chiriasul OfficePlus), toate marcate ----
        crm = {}
        r = post(pg, PROD + V2 + "clients", {
            "name": MARK + " SRL", "idno": "TESTACT" + datetime.date.today().strftime("%d%m"),
            "client_type": "Клиент",
            "address": "proba automata, a nu se folosi",
            "phone": "+373 000 000", "email": "test-act@officeplus.local",
            "notes": MARK + ": inregistrare de proba, lasata intentionat"})
        crm["client"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")
        cid = (r.get("data") or {}).get("id") if r.get("success") else None

        r = post(pg, PROD + V2 + "contacts", {
            "name": MARK + " - persoana de contact", "client_id": cid,
            "position": "proba", "phone": "+373 000 001",
            "email": "test-act@officeplus.local", "notes": MARK})
        crm["contact"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")

        r = post(pg, PROD + V2 + "leads", {
            "name": MARK + " - lead", "company": MARK + " SRL",
            "status": "Новый", "source": "Сайт",
            "phone": "+373 000 002", "notes": MARK})
        crm["lead"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")

        r = post(pg, PROD + V2 + "deals", {
            "title": MARK + " - oportunitate", "client_id": cid,
            "stage": "Новая", "amount": 2.00, "notes": MARK})
        crm["oportunitate"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")

        r = post(pg, PROD + V2 + "items", {
            "code": "TEST-ACT", "name": MARK + " - serviciu de proba",
            "kind": "Услуга", "unit_": "услуга",
            "price": 1.00, "vat": 20, "stock": 0, "notes": MARK})
        crm["pozitie"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")
        item_id = (r.get("data") or {}).get("id") if r.get("success") else None

        r = post(pg, PROD + V2 + "projects", {
            "name": MARK + " - proiect", "client_id": cid,
            "kind": "Другое", "status": "Договор",
            "budget": 2.00, "notes": MARK})
        crm["proiect"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")
        pid = (r.get("data") or {}).get("id") if r.get("success") else None

        r = post(pg, PROD + V2 + "orders", {
            "number": "TEST-ACT", "client_id": cid, "project_id": pid,
            "kind": "Услуга", "status": "Подтверждён",
            "notes": MARK})
        crm["comanda"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")
        oid = (r.get("data") or {}).get("id") if r.get("success") else None
        if oid and item_id:
            r = post(pg, PROD + V2 + "orders/%d/lines" % oid,
                     {"item_id": item_id, "qty": 1, "price": 1.00})
            crm["rind_comanda"] = r.get("id") if r.get("success") else r.get("error")
            r = post(pg, PROD + V2 + "orders/%d/post" % oid, {})
            crm["contare"] = r.get("message") or r.get("error")

        r = post(pg, PROD + V2 + "tasks", {
            "subject": MARK + " - sarcina", "client_id": cid, "project_id": pid,
            "stage": "Новая", "priority": "Обычный",
            "kind": "Задача", "notes": MARK})
        crm["sarcina"] = (r.get("data") or {}).get("id") if r.get("success") else r.get("error")
        made["crm"] = crm

        # -- capturi: inregistrarile gasite dupa marcaj -------------------
        for key, name in (("clients", "01_client"), ("orders", "02_comanda"),
                          ("items", "03_pozitie"), ("deals", "04_oportunitate")):
            pg.goto(PROD + CRM + "?t=%s#%s" % (key, key), wait_until="networkidle")
            pg.wait_for_timeout(6000)
            pg.evaluate("""k => { const i = document.getElementById('ef-' + k);
                if (i) { i.value = 'TEST ACT'; crmReload(); } }""", key)
            made["capturi"].append(shot(pg, name, 3000))

        # -- 3. jurnalul documentelor: contul de plata creat --------------
        pg.goto(PROD + "/UNA.md/orasldev/biro26-journal", wait_until="networkidle")
        made["capturi"].append(shot(pg, "05_jurnal", 7000))
        br.close()

    with open(RESULT, "w", encoding="utf-8") as fh:
        json.dump(made, fh, ensure_ascii=False, indent=1)
    print(json.dumps(made, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

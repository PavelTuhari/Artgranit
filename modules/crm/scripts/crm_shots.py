#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capturile pentru ghidul utilizatorului (docs/CRM/GHID_CRM.html).

RO: pornim CRM-ul local (acelasi cod si aceeasi baza Oracle ca in productie),
intram cu contul portalului si fotografiem fiecare sectiune. Imaginile stau in
`modules/crm/static/docs/` — servite de ruta `crm.static`, deci ghidul le vede
si de pe officeplus, si de pe nufarul, fara sa scriem adrese de mina.

    python3 modules/crm/scripts/crm_shots.py [http://127.0.0.1:3011]
"""
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(ROOT, "modules", "crm", "static", "docs")
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3011"
CRM = BASE + "/UNA.md/orasldev/crm/"

# RO: (fisier, hash-ul sectiunii, secunde de asteptare, selector optional)
SHOTS = [
    ("01_workspace.png", "workspace", 4, None),
    ("02_kanban.png", "kanban", 5, None),
    ("03_clienti.png", "clients", 4, None),
    ("04_nomenclator.png", "items", 5, None),
    ("05_comenzi.png", "orders", 5, None),
    ("07_proiecte.png", "projects", 4, None),
    ("08_calendar.png", "tasks", 4, None),
    ("09_rapoarte.png", "reports", 4, None),
    ("11_alerte.png", "alerts", 5, None),
    ("12_angajati.png", "employees", 5, None),
]


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 1500, "height": 950},
                         device_scale_factor=2)
        pg.goto(BASE + "/login", wait_until="networkidle")
        pg.click("button[type=submit]")
        pg.wait_for_load_state("networkidle")
        for name, sec, wait, sel in SHOTS:
            pg.goto(CRM + "#" + sec, wait_until="networkidle")
            pg.wait_for_timeout(wait * 1000)
            target = pg.locator(sel) if sel else pg
            target.screenshot(path=os.path.join(OUT, name))
            print("  ", name)
        # RO: fise deschise — se vede cum arata cardul, nu doar lista
        pg.goto(CRM + "#orders", wait_until="networkidle")
        pg.wait_for_timeout(5000)
        pg.locator("#et-orders tbody tr.r").first.click()
        pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(OUT, "06_comanda_erp.png"))
        print("   06_comanda_erp.png")
        pg.goto(CRM + "#items", wait_until="networkidle")
        pg.wait_for_timeout(5000)
        pg.locator("#et-items tbody tr.r.erp").first.click()
        pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(OUT, "10_marfa_erp.png"))
        print("   10_marfa_erp.png")
        br.close()
    print("gata:", OUT)


if __name__ == "__main__":
    main()

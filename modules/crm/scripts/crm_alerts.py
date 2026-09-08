#!/usr/bin/env python3
"""Sumarul CRM in Telegram: tranzactii nefinisate si datorii.

RO: se ruleaza din timer (systemd) in fiecare ora; trimite doar chiriasilor
a caror ora de sumar coincide si care au alertele pornite. Fara argumente
face exact asta. Pentru verificare — `--dry-run` (arata textul, nu trimite)
si `--now` (ignora ora, trimite imediat).

    python3 modules/crm/scripts/crm_alerts.py --dry-run
    python3 modules/crm/scripts/crm_alerts.py --dry-run --client 7
    python3 modules/crm/scripts/crm_alerts.py            # rulare programata
    python3 modules/crm/scripts/crm_alerts.py --now --office --force
"""
import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from modules.crm import notify  # noqa: E402
from modules.crm.store_process import CrmData  # noqa: E402
from modules.crm.tenant import CLIENT, OFFICE, Tenant  # noqa: E402

TZ = ZoneInfo("Europe/Chisinau")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="arata textul, nu trimite")
    ap.add_argument("--now", action="store_true", help="ignora ora din setari")
    ap.add_argument("--force", action="store_true", help="trimite si daca nu e nimic nou")
    ap.add_argument("--office", action="store_true", help="doar OfficePlus")
    ap.add_argument("--client", type=int, default=0, help="doar clientul cu acest id")
    ap.add_argument("--url", default=os.environ.get("CRM_ALERTS_URL", ""), help="link catre CRM in mesaj")
    a = ap.parse_args()

    if a.office or a.client:
        t = Tenant(CLIENT, a.client) if a.client else Tenant(OFFICE, 0)
        data = CrmData(t)
        if a.dry_run:
            d = notify.digest(data, only_new=not a.force, url=a.url)
            print("== %s: %d alerte noi din %d deschise ==" % (t.label, len(d["alerts"]), len(d["all"])))
            print(d["text"])
            sys.exit(0)
        r = notify.send(data, only_new=not a.force, url=a.url, force=a.force)
        print("%s: %s" % (t.label, r))
        sys.exit(0 if r.get("success") else 1)

    hour = None if a.now else datetime.now(TZ).hour
    res = notify.run_all(hour=hour, url=a.url, dry=a.dry_run)
    if not res:
        print("Niciun chirias cu alerte pornite%s." % ("" if a.now else " la ora %d" % hour))
        sys.exit(0)
    bad = 0
    for r in res:
        if a.dry_run:
            print("== %s: %d noi / %d deschise ==\n%s\n" % (r["tenant"], r.get("alerts", 0), r.get("open", 0), r.get("text", "")))
        else:
            print("%s: %s" % (r["tenant"], {k: v for k, v in r.items() if k != "text"}))
        bad += 0 if r.get("success") else 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

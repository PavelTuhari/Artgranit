#!/usr/bin/env python3
"""Datele demo ale CRM-ului (AGENTS.md §1 al prototipului: toate plitele nevide).

RO: ruleaza pe chiriasul cerut si scrie contoarele (seed.log al prototipului):
    python3 modules/crm/scripts/crm_seed.py                 # OfficePlus (office/0)
    python3 modules/crm/scripts/crm_seed.py --client 7      # clientul 7 din cabinet
Idempotent: a doua rulare nu dubleaza nimic (contoare 0).
"""
import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from modules.crm import seed  # noqa: E402
from modules.crm.store_process import CrmData  # noqa: E402
from modules.crm.tenant import CLIENT, OFFICE, Tenant  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", type=int, default=0, help="id-ul clientului (cabinet); implicit OfficePlus")
    a = ap.parse_args()
    t = Tenant(CLIENT, a.client) if a.client else Tenant(OFFICE, 0)
    data = CrmData(t)
    st = seed.run(data)
    print("Adaugat (%s): %s" % (t.label, seed.text(st)))
    c = data.counts()
    print("Total in baza (%s): clienti %d, contacte %d, leaduri %d, oferte %d, nomenclator %d, comenzi %d, "
          "linii %d, sarcini %d, proiecte %d" % (t.label, c["clients"], c["contacts"], c["leads"], c["deals"],
                                                 c["items"], c["orders"], c["order_lines"], c["tasks"], c["projects"]))
    empty = [s["stage"] for s in data.stages() if s["count"] == 0]
    print("Plite goale pe tabloul de lucru: %s" % (", ".join(empty) if empty else "niciuna"))
    sys.exit(1 if empty else 0)


if __name__ == "__main__":
    main()

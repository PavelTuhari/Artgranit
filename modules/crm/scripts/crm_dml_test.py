#!/usr/bin/env python3
"""DML-testul CRM-ului pe Oracle (INSERT→SELECT→UPDATE→SELECT→DELETE→COUNT + specific).

RO: ruleaza pe un chirias tehnic ('client', 999999) ca sa nu atinga datele
reale; lasa baza cum a gasit-o. Cod de iesire 0 = 0 FAIL.
    python3 modules/crm/scripts/crm_dml_test.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from modules.crm import dml_test  # noqa: E402
from modules.crm.store_process import CrmData  # noqa: E402
from modules.crm.tenant import CLIENT, Tenant  # noqa: E402


def main():
    r = dml_test.run(CrmData(Tenant(CLIENT, 999999)))
    print("\n".join(r["log"]))
    print("== %s: %d FAIL ==" % ("OK" if r["ok"] else "FAIL", r["fails"]))
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Muta setul demonstrativ din chiriasul OfficePlus in chiriasul 'demo'.

RO: cerinta proprietarului 10.09.2026 — in OfficePlus totul lucreaza pe
datele reale din Oracle, iar regimul demo ramine separat. Datele
demonstrative semanate pe 08.09.2026 stateau chiar in chiriasul 'office';
scriptul le muta in ('demo', 0). Reversibil: `--back`.

    python3 modules/crm/scripts/crm_demo_move.py            # raport, fara scriere
    python3 modules/crm/scripts/crm_demo_move.py --apply    # office -> demo
    python3 modules/crm/scripts/crm_demo_move.py --apply --back   # demo -> office
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from models.biro26_db import Biro26DB  # noqa: E402

# RO: tabelele cu date de lucru. CRM_ALERT_CFG NU se muta: e setarea
#     canalelor pentru OfficePlus, nu o data demonstrativa.
TABLES = ("CRM_CLIENT", "CRM_CONTACT", "CRM_LEAD", "CRM_DEAL", "CRM_ITEM",
          "CRM_ORDER", "CRM_PROJECT", "CRM_TASK", "CRM_EVENT_LOG", "CRM_ALERT_SENT")


def counts(db, kind):
    out = {}
    for t in TABLES:
        r = db.execute_query("SELECT COUNT(*) FROM %s WHERE OWNER_KIND = :k AND OWNER_ID = 0" % t,
                             {"k": kind})
        out[t] = int((r.get("data") or [[0]])[0][0] or 0)
    return out


def main():
    apply_ = "--apply" in sys.argv
    back = "--back" in sys.argv
    src, dst = ("demo", "office") if back else ("office", "demo")
    db = Biro26DB()
    before = counts(db, src)
    print("== rinduri la chiriasul '%s' ==" % src)
    for t, n in before.items():
        print("  %-18s %d" % (t, n))
    total = sum(before.values())
    if not apply_:
        print("\nfara --apply nu se scrie nimic. Ar fi mutate %d rinduri: %s -> %s" % (total, src, dst))
        return 0
    moved = 0
    for t in TABLES:
        if not before[t]:
            continue
        r = db.execute_dml("UPDATE %s SET OWNER_KIND = :d WHERE OWNER_KIND = :s AND OWNER_ID = 0" % t,
                           {"d": dst, "s": src})
        if not r.get("success"):
            print("  FAIL %s: %s" % (t, str(r.get("message"))[:200]))
            return 1
        print("  OK   %-18s %d -> %s" % (t, before[t], dst))
        moved += before[t]
    print("\nmutate %d rinduri; la '%s' au ramas: %d" % (moved, src, sum(counts(db, src).values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

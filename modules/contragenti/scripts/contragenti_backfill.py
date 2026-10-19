#!/usr/bin/env python3
"""Completarea codului fiscal la clientii deja inregistrati fara el.

RO: clientii persoane juridice ai site-ului (YBIRO_CLIENT.IS_COMPANY='1') care
au IDNO pe fisa dar nu in TMS_UNIVERS.CODVECHI / TMS_ORG.CODFISCAL (ex. COD
518172, 07.09.2026). Trece fiecare prin CtgStore.apply (aceeasi cale ca din
pagina), deci cu jurnal si cu regula «nu suprascriu ce exista».

    python modules/contragenti/scripts/contragenti_backfill.py            # doar arata
    python modules/contragenti/scripts/contragenti_backfill.py --apply    # completeaza
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)


def _env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _env()
    os.chdir(ROOT)
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    from modules.contragenti.store import CtgStore
    rows = _rows(Biro26DB().execute_query(
        "SELECT c.UNIVERS_COD, c.IDNO, c.FULL_NAME, u.CODVECHI, o.CODFISCAL FROM YBIRO_CLIENT c "
        "JOIN TMS_UNIVERS u ON u.COD = c.UNIVERS_COD LEFT JOIN TMS_ORG o ON o.COD = u.COD "
        "WHERE c.IS_COMPANY = '1' AND (u.CODVECHI IS NULL OR o.CODFISCAL IS NULL) ORDER BY c.UNIVERS_COD"))
    apply = "--apply" in sys.argv
    print("clienti juridici fara cod fiscal complet:", len(rows), "| mod:", "APPLY" if apply else "dry-run")
    for r in rows:
        idno = (r.get("idno") or "").strip()
        print(" COD %s «%s» idno=%s codvechi=%s codfiscal=%s" % (
            r["univers_cod"], r.get("full_name"), idno or "-", r.get("codvechi") or "-", r.get("codfiscal") or "-"))
        if not idno:
            if apply:
                CtgStore.log("backfill", "skip", page="backfill", idno="", univers_cod=int(r["univers_cod"]),
                             detail="fisa fara IDNO — nu am ce completa")
            continue
        from modules.contragenti import rules
        if not rules.idno_valid(idno):
            # RO: fise de test / IDNP de persoana fizica — nu ajung in CODVECHI/CODFISCAL
            print("   -> skip: IDNO nu trece cifra de control (fisa de test sau IDNP)")
            if apply:
                CtgStore.log("backfill", "skip", page="backfill", idno=idno, univers_cod=int(r["univers_cod"]),
                             detail="IDNO invalid (cifra de control) — fisa de test sau IDNP")
            continue
        if apply:
            res = CtgStore.apply({"idno": idno, "denumire": r.get("full_name") or "", "adresa": "",
                                  "administratori": "", "source": "backfill", "updated": ""},
                                 page="backfill", username="backfill")
            print("   ->", res.get("result") or res.get("error"), res.get("changes"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

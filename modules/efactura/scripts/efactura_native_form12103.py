#!/usr/bin/env python3
"""Formularul «(12103) Cumparare - incarcare pachet e-Factura» in back-office-ul nativ una.md.

RO: copia formularului din BMPUBLIC (obj 7485, sectiune 2:7:PRIHOD_TOV4) — asa
lucreaza celelalte baze de pe cloudbd (13.09.2026): documentul 12103 tine XML-ul
pachetului ca atasament OLE, «Загрузить XML» il parseaza cu
pkg_edi_xml.import_xml_package_object, iar «Сформировать документы» face
documentele de intrare. Diferentele pentru OfficePlus:
  - actiune noua «Preia din e-Factura (API)» -> EFA_INBOX.fetch_api_pr
    (facturile vin direct din SFS, fara descarcare manuala de pe portal);
  - «Сформировать документы 1209» -> EFA_INBOX.create_docs_1209 (pachetul
    vendorului din OfficePlus nu are create_docs_from_12103).
Parintele: sectiunea «Intrari» (obj 2453). Idempotent; --remove sterge tot.
EN: registers the 12103 package form (clone of BMPUBLIC's) in OFFICEPLUS A$ADM.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

PARENT = 2453                                   # «Intrari» (MARFPRIHOD)
FORM_SECTION = "2:7:PRIHOD_TOV4"
FORM_NAMES = ("(12103) Покупка - Пакетная загрузка e-Factura (API)",
              "(12103) Cumparare - pachet e-Factura (API)",
              "(12103) Purchase - e-Factura package (API)")
# (nume RU, nume RO, nume EN, sectiune, subtip, proprietati)
CHILDREN = [
    ("LoadFromFile", "LoadFromFile", "LoadFromFile", "482:4:PRIHOD_COPYDATA", 2, {
        "ACTIONTYPE": ("S", "0"), "BUTTONTEXT": ("S", "[ Incarcare fisier pe Object ]"), "ID": ("I", 1), "IDB": ("I", 1),
        "LOADFILE": ("B", "1"), "LOADFILEUNIQUE": ("B", "1"), "VISIBLE": ("B", "1"),
        "TEXTFORUSER": ("C", ("Загрузить файл на вкладку Object", "Incarcare fisier pe Object", "Load file on Object tab"))}),
    ("Preia din e-Factura (API)", "Preia din e-Factura (API)", "Fetch from e-Factura (API)", "2:26:VZ202MIACTION:0:20:5:5:5:43:43:5", 2, {
        "ACTIONTYPE": ("S", "1"), "BUTTONTEXT": ("S", "[ Preia din e-Factura ]"), "ID": ("I", 5), "IDB": ("I", None),
        "DELETEALLFCFROMCM": ("B", "0"), "DELETEFCFROMCM": ("B", "0"), "REFRESHDDOCNEED": ("B", "1"), "VISIBLE": ("B", "1"),
        "SQL1": ("M", "begin\n  EFA_INBOX.fetch_api_pr(:nrdoc);\nend;\n"),
        "TEXTFORUSER": ("C", ("Получить из e-Factura (API SFS)", "Preia din e-Factura (API SFS)", "Fetch from e-Factura (SFS API)"))}),
    ("Загрузить XML", "Incarca XML", "Import XML", "2:26:VZ202MIACTION:0:20:5:5:5:43:43:6", 2, {
        "ACTIONTYPE": ("S", "1"), "BUTTONTEXT": ("S", "[ Загрузить XML ]"), "ID": ("I", 2), "IDB": ("I", None),
        "DELETEALLFCFROMCM": ("B", "0"), "DELETEFCFROMCM": ("B", "0"), "REFRESHDDOCNEED": ("B", "1"), "VISIBLE": ("B", "1"),
        "SQL1": ("M", "begin\n  pkg_edi_xml.import_xml_package_object(:nrdoc);\nend;\n"),
        "TEXTFORUSER": ("C", ("Загрузить XML", "Import XML", "Import XML"))}),
    ("Сформировать документы 1209", "Formeaza documentele 1209", "Create 1209 documents", "2:26:VZ202MIACTION:0:20:5:5:5:43:44:0", 2, {
        "ACTIONTYPE": ("S", "1"), "BUTTONTEXT": ("S", "[ Сформировать документы ]"), "ID": ("I", 3), "IDB": ("I", None),
        "DELETEALLFCFROMCM": ("B", "0"), "DELETEFCFROMCM": ("B", "0"), "REFRESHDDOCNEED": ("B", "1"), "VISIBLE": ("B", "1"),
        "SQL1": ("M", "begin\n  EFA_INBOX.create_docs_1209(:nrdoc);\nend;\n"),
        "TEXTFORUSER": ("C", ("Сформировать документы (1209)", "Formeaza documentele (1209)", "Create documents (1209)"))}),
    ("Total1", "Total1", "Total1", "3:2:TOTAL", 5, {
        "CM_ISVERTICAL": ("B", "1"), "CM_SQL": ("M", None), "REP_ENABLED": ("B", "0"), "REP_SQL_D": ("M", None),
        "REP_SQL_H": ("M", None), "REP_SQL_M": ("M", None), "REP_TYPE": ("S", None), "SPEC_ISVERTICAL": ("B", "1"), "SPEC_SQL": ("M", None)}),
]
FORM_PROPS = {"DB ID": ("I", 12103), "DLL ID": ("I", 4000), "DOCNAME": ("S", "DG1p21"), "EONLYPRIVATE PRINTFORMS": ("S", "false"),
              "FOCUSCONTROL": ("S", "se201DtDep"), "GRIDCOUNT": ("I", 1), "GRIDHEIGHT0": ("I", 0), "HEADERPANEL": ("B", "0"),
              "MODULE": ("S", "P"), "USE IN DB": ("B", None), "USETOOLBAR": ("B", "1")}


def _env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _prop(db, obj_id, key, vtype, val):
    p = {"o": obj_id, "k": key, "n": key, "vt": vtype, "sv": None, "iv": None, "bv": None, "lv": None, "v0": None, "v1": None, "v2": None}
    if vtype == "S":
        p["sv"] = val
    elif vtype == "I":
        p["iv"] = val
    elif vtype == "B":
        p["bv"] = val
    elif vtype == "M":
        p["sv"] = val
    elif vtype == "C":
        p["v0"], p["v1"], p["v2"] = val
    db.execute_dml("INSERT INTO A$ADP (OBJ_ID, KEY, NAME, GR, VTYPE, SVALUE, IVALUE, BVALUE, VALUE0, VALUE1, VALUE2) "
                   "VALUES (:o, :k, :n, 'Общая', :vt, :sv, :iv, :bv, :v0, :v1, :v2)", p)


def main() -> int:
    _env()
    os.chdir(ROOT)
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    db = Biro26DB()
    have = _rows(db.execute_query("SELECT m.OBJ_ID FROM A$ADM m JOIN A$ADP p ON p.OBJ_ID = m.OBJ_ID "
                                  "WHERE p.KEY = 'DB ID' AND p.IVALUE = 12103 AND m.OBJ_TYPE = 1 AND m.OBJ_SUBTYPE = 0"))
    if "--remove" in sys.argv:
        if not have:
            print("formularul 12103 nu exista — nimic de sters")
            return 0
        fid = int(have[0]["obj_id"])
        db.execute_dml("DELETE FROM A$ADP WHERE OBJ_ID IN (SELECT OBJ_ID FROM A$ADM START WITH OBJ_ID = :f CONNECT BY PRIOR OBJ_ID = PARENT_ID)", {"f": fid})
        db.execute_dml("DELETE FROM A$ADM WHERE OBJ_ID IN (SELECT OBJ_ID FROM A$ADM START WITH OBJ_ID = :f CONNECT BY PRIOR OBJ_ID = PARENT_ID)", {"f": fid})
        print("sters formularul 12103, OBJ_ID", fid)
        return 0
    if have:
        print("formularul 12103 exista deja: OBJ_ID", have[0]["obj_id"])
        return 0
    fid = int(_rows(db.execute_query("SELECT A$ADM$SQ.NEXTVAL N FROM dual"))[0]["n"])
    db.execute_dml("INSERT INTO A$ADM (OBJ_ID, SYS_ID, OBJ_TYPE, OBJ_SUBTYPE, PARENT_ID, NAME0, NAME1, NAME2, SECTION, NRORD, MODIFIED) "
                   "SELECT :id, SYS_ID, 1, 0, :p, :n0, :n1, :n2, :sec, :id, SYSDATE FROM A$ADM WHERE OBJ_ID = :p",
                   {"id": fid, "p": PARENT, "n0": FORM_NAMES[0], "n1": FORM_NAMES[1], "n2": FORM_NAMES[2], "sec": FORM_SECTION})
    for k, (vt, v) in FORM_PROPS.items():
        _prop(db, fid, k, vt, v)
    for n0, n1, n2, sec, sub, props in CHILDREN:
        cid = int(_rows(db.execute_query("SELECT A$ADM$SQ.NEXTVAL N FROM dual"))[0]["n"])
        db.execute_dml("INSERT INTO A$ADM (OBJ_ID, SYS_ID, OBJ_TYPE, OBJ_SUBTYPE, PARENT_ID, NAME0, NAME1, NAME2, SECTION, NRORD, MODIFIED) "
                       "SELECT :id, SYS_ID, 1, :sub, :p, :n0, :n1, :n2, :sec, :id, SYSDATE FROM A$ADM WHERE OBJ_ID = :p",
                       {"id": cid, "sub": sub, "p": fid, "n0": n0, "n1": n1, "n2": n2, "sec": sec})
        for k, (vt, v) in props.items():
            _prop(db, cid, k, vt, v)
    print("creat formularul 12103: OBJ_ID", fid, "sub «Intrari» (%d), %d actiuni" % (PARENT, len(CHILDREN)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

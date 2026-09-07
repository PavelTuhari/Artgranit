"""Scrierea cardului in nomenclatorul una.md + jurnalul lantului (CTG_*).

RO: `apply()` e singura cale de intrare a unui card de contraparte in baza,
oricare ar fi pagina. Ordinea potrivirii (deduplicarea):
  1. TMS_UNIVERS.CODVECHI = IDNO (GR1='E')  - inregistrarea ERP «de referinta»;
  2. TMS_ORG.CODFISCAL = IDNO;
  3. YBIRO_CLIENT.IDNO = IDNO               - clientul site-ului;
  4. denumirea normalizata (rules.norm_name) printre organizatii (TIP='O').
Gasit -> REPARARE: se completeaza ce lipseste (CODVECHI, CODFISCAL, adresa,
director, IDNO pe fisa site), nimic existent nu se suprascrie cu alta valoare
(diferenta = `conflict`, in jurnal). Negasit -> client nou (client_quick_add,
ca din pagina) + aceleasi blocuri. Totul in CTG_EVENT_LOG.
EN: card upsert into TMS_UNIVERS / TMS_ORG / YBIRO_CLIENT with dedup and log.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

from modules.contragenti import rules


class CtgStore:
    # ── jurnal ───────────────────────────────────────────────────────────
    @staticmethod
    def log(step: str, result: str = "ok", *, page: str = "", username: str = "",
            q: str = "", idno: str = "", univers_cod: Optional[int] = None,
            detail: str = "", payload: Any = None) -> None:
        try:
            body = payload if isinstance(payload, str) else (
                json.dumps(payload, ensure_ascii=False) if payload is not None else None)
            Biro26DB().execute_dml(
                "INSERT INTO CTG_EVENT_LOG (USERNAME, PAGE, STEP, Q, IDNO, UNIVERS_COD, RESULT, "
                "DETAIL, PAYLOAD) VALUES (:u, :p, :s, :q, :i, :c, :r, :d, :pl)",
                {"u": (username or "")[:120], "p": (page or "")[:60], "s": step[:40],
                 "q": (q or "")[:400], "i": (idno or "")[:20] or None, "c": univers_cod,
                 "r": (result or "")[:20], "d": rules.to_db_charset(detail)[:2000],
                 "pl": rules.to_db_charset(body)[:100000] if body else None})
        except Exception:                                    # noqa: BLE001
            pass

    @staticmethod
    def events(limit: int = 100, idno: str = "", page: str = "") -> List[Dict[str, Any]]:
        where, params = [], {"l": max(1, min(int(limit), 500))}
        if idno:
            where.append("IDNO = :i"); params["i"] = idno
        if page:
            where.append("PAGE = :p"); params["p"] = page
        w = (" WHERE " + " AND ".join(where)) if where else ""
        return _rows(Biro26DB().execute_query(
            "SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI:SS') TS, USERNAME, PAGE, STEP, "
            f"Q, IDNO, UNIVERS_COD, RESULT, DETAIL FROM CTG_EVENT_LOG{w} ORDER BY ID DESC) "
            "WHERE ROWNUM <= :l", params))

    # ── potrivire ────────────────────────────────────────────────────────
    @staticmethod
    def find_existing(idno: str, name: str = "") -> Optional[Dict[str, Any]]:
        """-> {univers_cod, denumirea, codvechi, codfiscal, yb_idno, how} | None"""
        db = Biro26DB()
        sel = ("SELECT u.COD UNIVERS_COD, u.DENUMIREA, u.NAMERUS, u.CODVECHI, u.GR1, o.CODFISCAL, "
               "o.ADRESS, o.DIRECTOR, c.IDNO YB_IDNO, c.IS_COMPANY, c.UNIVERS_COD YB_COD "
               "FROM TMS_UNIVERS u LEFT JOIN TMS_ORG o ON o.COD = u.COD "
               "LEFT JOIN YBIRO_CLIENT c ON c.UNIVERS_COD = u.COD ")
        if idno:
            for how, cond in (("codvechi", "u.CODVECHI = :i AND u.GR1 = 'E'"),
                              ("codfiscal", "o.CODFISCAL = :i"),
                              ("yb_idno", "c.IDNO = :i")):
                r = _rows(db.execute_query(sel + "WHERE " + cond + " AND u.TIP = 'O' AND ROWNUM <= 1",
                                           {"i": idno}))
                if r:
                    r[0]["how"] = how
                    return r[0]
        key = rules.norm_name(name)
        if not key:
            return None
        tok = rules.name_token(name)
        cands = _rows(db.execute_query(
            sel + "WHERE u.TIP = 'O' AND (UPPER(u.DENUMIREA) LIKE :t OR UPPER(u.NAMERUS) LIKE :t) "
                  "AND ROWNUM <= 200", {"t": "%" + tok + "%"}))
        for c in cands:
            if key in (rules.norm_name(c.get("denumirea")), rules.norm_name(c.get("namerus"))):
                # RO: alta firma cu ACELASI nume dar alt IDNO deja scris -> nu e ea
                if c.get("codvechi") and idno and c["codvechi"] != idno:
                    continue
                c["how"] = "name"
                return c
        return None

    # ── scriere ──────────────────────────────────────────────────────────
    @staticmethod
    def apply(card: Dict[str, Any], *, page: str = "api", username: str = "",
              q: str = "") -> Dict[str, Any]:
        idno, name = card["idno"], card.get("denumire") or ""
        lg = dict(page=page, username=username, q=q, idno=idno)
        m = rules.map_card(card)
        CtgStore.log("card_received", "ok", detail=rules.card_summary(card), payload=card, **lg)
        if not rules.idno_valid(idno):
            CtgStore.log("idno_check", "warn", detail="IDNO nu trece cifra de control", **lg)
        ex = CtgStore.find_existing(idno, name)
        db = Biro26DB()
        changes: List[str] = []
        if ex:
            cod = int(ex["univers_cod"])
            CtgStore.log("match_found", "ok", univers_cod=cod,
                         detail="dupa %s: COD %s «%s» (codvechi=%s, codfiscal=%s, idno site=%s)" % (
                             ex["how"], cod, ex.get("denumirea"), ex.get("codvechi"),
                             ex.get("codfiscal"), ex.get("yb_idno")), **lg)
            # TMS_UNIVERS.CODVECHI
            if not ex.get("codvechi"):
                r = db.execute_dml("UPDATE TMS_UNIVERS SET CODVECHI = :i, GR1 = NVL(GR1, 'E'), "
                                   "NAMERUS = NVL(NAMERUS, :nr) WHERE COD = :c",
                                   {"i": m["univers"]["CODVECHI"], "nr": m["univers"]["NAMERUS"], "c": cod})
                if r.get("success"):
                    changes.append("TMS_UNIVERS.CODVECHI")
                else:
                    CtgStore.log("univers_update", "error", univers_cod=cod, detail=str(r.get("message"))[:500], **lg)
                    return {"success": False, "error": "TMS_UNIVERS: " + str(r.get("message"))[:300],
                            "univers_cod": cod}
            elif ex["codvechi"] != idno:
                CtgStore.log("conflict", "conflict", univers_cod=cod,
                             detail="CODVECHI existent %s != IDNO %s — nu suprascriu" % (ex["codvechi"], idno), **lg)
            # TMS_ORG
            have_org = _rows(db.execute_query("SELECT COD FROM TMS_ORG WHERE COD = :c", {"c": cod}))
            if have_org:
                # RO: UPDATE doar pe coloanele goale pentru care cardul ADUCE o valoare —
                #     un UPDATE «pe nimic» e refuzat de un trigger al bazei (ORA-20000
                #     «Access denied», vazut pe 07.09.2026 la a doua trecere pe 518172)
                fills = {col: m["org"][col] for col, cur in (("CODFISCAL", ex.get("codfiscal")),
                                                             ("ADRESS", ex.get("adress")),
                                                             ("DIRECTOR", ex.get("director")))
                         if m["org"].get(col) and not cur}
                if fills:
                    sets = ", ".join("%s = :%s" % (c, c.lower()) for c in fills)
                    r = db.execute_dml("UPDATE TMS_ORG SET " + sets + " WHERE COD = :c",
                                       dict({c.lower(): v for c, v in fills.items()}, c=cod))
                    if r.get("success"):
                        changes += ["TMS_ORG." + c for c in fills]
                    else:
                        CtgStore.log("org_update", "error", univers_cod=cod, detail=str(r.get("message"))[:500], **lg)
                if ex.get("codfiscal") and ex["codfiscal"] != idno:
                    CtgStore.log("conflict", "conflict", univers_cod=cod,
                                 detail="CODFISCAL existent %s != IDNO %s" % (ex["codfiscal"], idno), **lg)
            else:
                r = db.execute_dml("INSERT INTO TMS_ORG (COD, CODFISCAL, ADRESS, DIRECTOR) VALUES (:c, :cf, :ad, :dr)",
                                   {"c": cod, "cf": m["org"]["CODFISCAL"], "ad": m["org"]["ADRESS"],
                                    "dr": m["org"]["DIRECTOR"]})
                if r.get("success"):
                    changes.append("TMS_ORG (rind nou)")
                else:
                    CtgStore.log("org_insert", "error", univers_cod=cod, detail=str(r.get("message"))[:500], **lg)
            # YBIRO_CLIENT.IDNO
            if ex.get("yb_cod") and not ex.get("yb_idno"):
                r = db.execute_dml("UPDATE YBIRO_CLIENT SET IDNO = :i, IS_COMPANY = '1' WHERE UNIVERS_COD = :c",
                                   {"i": idno, "c": cod})
                if r.get("success"):
                    changes.append("YBIRO_CLIENT.IDNO")
            result = "repaired" if changes else "unchanged"
            CtgStore.log("apply", result, univers_cod=cod,
                         detail=("completat: " + ", ".join(changes)) if changes else "nimic de completat", **lg)
            return {"success": True, "result": result, "univers_cod": cod, "how": ex["how"],
                    "name": ex.get("denumirea"), "changes": changes}
        # ── client nou ──
        CtgStore.log("match_none", "ok", detail="nicio inregistrare dupa IDNO/denumire — creez", **lg)
        from models.biro26_journal import Biro26Journal
        r = Biro26Journal.client_quick_add(m["univers"]["DENUMIREA"] or name, is_company=True,
                                           idno=idno, address=m["org"]["ADRESS"] or "")
        if not r.get("success"):
            CtgStore.log("client_create", "error", detail=str(r.get("error"))[:500], **lg)
            return {"success": False, "error": r.get("error")}
        cod = int(r["data"]["univers_cod"])
        db.execute_dml("UPDATE TMS_UNIVERS SET CODVECHI = :i, GR1 = 'E', NAMERUS = :nr WHERE COD = :c",
                       {"i": m["univers"]["CODVECHI"], "nr": m["univers"]["NAMERUS"], "c": cod})
        ro = db.execute_dml("INSERT INTO TMS_ORG (COD, CODFISCAL, ADRESS, DIRECTOR) VALUES (:c, :cf, :ad, :dr)",
                            {"c": cod, "cf": m["org"]["CODFISCAL"], "ad": m["org"]["ADRESS"],
                             "dr": m["org"]["DIRECTOR"]})
        if not ro.get("success"):
            db.execute_dml("UPDATE TMS_ORG SET CODFISCAL = NVL(CODFISCAL, :cf), ADRESS = NVL(ADRESS, :ad), "
                           "DIRECTOR = NVL(DIRECTOR, :dr) WHERE COD = :c",
                           {"cf": m["org"]["CODFISCAL"], "ad": m["org"]["ADRESS"], "dr": m["org"]["DIRECTOR"], "c": cod})
        CtgStore.log("client_created", "created", univers_cod=cod,
                     detail="COD %s «%s»: TMS_UNIVERS.CODVECHI, TMS_ORG.CODFISCAL/ADRESS/DIRECTOR, YBIRO_CLIENT.IDNO" % (
                         cod, m["univers"]["DENUMIREA"]), **lg)
        return {"success": True, "result": "created", "univers_cod": cod, "how": "new",
                "name": m["univers"]["DENUMIREA"], "changes": ["TMS_UNIVERS", "TMS_ORG", "YBIRO_CLIENT"]}

    @staticmethod
    def verify(cod: int) -> Dict[str, Any]:
        r = _rows(Biro26DB().execute_query(
            "SELECT u.COD, u.DENUMIREA, u.CODVECHI, u.GR1, o.CODFISCAL, o.ADRESS, o.DIRECTOR, c.IDNO YB_IDNO "
            "FROM TMS_UNIVERS u LEFT JOIN TMS_ORG o ON o.COD = u.COD LEFT JOIN YBIRO_CLIENT c ON c.UNIVERS_COD = u.COD "
            "WHERE u.COD = :c", {"c": int(cod)}))
        return r[0] if r else {}

"""Biro26 — JURNAL UNIVERSAL de documente (back-office «casa cu casier»).

RO: o singura forma pentru toate documentele, dupa modelul aprobat
    (LightAccounting, docs/UI_CONCEPT.md §3): filtre + 4 butoane, antet cu
    ACTIUNI si FORME DE TIPAR, grila master si PATRU file de detaliu:

      Contari   -> VMDB_ST201D / VMDB_ST201M  (corespondenta conturilor)
      Marfuri   -> VMDB_ST201D + TMS_UNIVERS  (partea tabelara a documentului)
      Fisiere   -> VMDB_DOCS_OLE              (formularele atasate)
      LOG       -> XLOG                       (cine, cind si ce a facut)

    NIMIC nou in alta baza: se folosesc DOAR tabelele Oracle existente ale
    ERP-ului OfficePlus. Clientii inregistrati din back-office ajung in
    ACELEASI tabele ca inregistrarile din cabinetul de pe site
    (y_ai_BIRO26.register_client -> TMS_UNIVERS + YBIRO_CLIENT).

EN: universal document journal for the back office — one form for every
    document, four detail tabs, all on the EXISTING Oracle tables.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _result, _rows

SYSFID_WEB_INVOICE = 12280


class Biro26Journal:

    # ── grila master: documentele ────────────────────────────────────────

    @staticmethod
    def docs(date_from: str = "", date_to: str = "", q: str = "",
             limit: int = 200) -> Dict[str, Any]:
        """RO: lista documentelor pentru grila master. Cautarea merge dupa
        numar, cod si denumirea clientului — exact ce vede operatorul."""
        try:
            where = ["d.SYSFID = :sf"]
            p: Dict[str, Any] = {"sf": SYSFID_WEB_INVOICE,
                                 "n": max(1, min(int(limit or 200), 500))}
            if (date_from or "").strip():
                where.append("d.DATAMANUAL >= TO_DATE(:df,'YYYY-MM-DD')")
                p["df"] = date_from.strip()
            if (date_to or "").strip():
                where.append("d.DATAMANUAL < TO_DATE(:dt,'YYYY-MM-DD') + 1")
                p["dt"] = date_to.strip()
            if (q or "").strip():
                where.append("(UPPER(NVL(d.NRMANUAL,' ')) LIKE :q "
                             "OR TO_CHAR(d.COD) LIKE :q "
                             "OR UPPER(NVL(u.DENUMIREA,' ')) LIKE :q)")
                p["q"] = f"%{q.strip().upper()}%"
            sql = (
                "SELECT * FROM ("
                "SELECT d.COD, d.NRMANUAL, "
                "TO_CHAR(d.DATAMANUAL,'DD.MM.YYYY') DDATE, "
                "m.DTDEP CLIENT_COD, u.DENUMIREA CLIENT_NAME, "
                "(SELECT ROUND(SUM(l.SUMA),2) FROM VMDB_ST201D l "
                " WHERE l.NRDOC = d.COD) TOTAL, "
                "(SELECT COUNT(*) FROM VMDB_ST201D l "
                " WHERE l.NRDOC = d.COD) LINES, "
                "(SELECT COUNT(*) FROM VMDB_DOCS_OLE o "
                " WHERE o.NRDOC = d.COD) FILES, "
                "d.USERID, d.AT2 "
                "FROM TMDB_DOCS d "
                "LEFT JOIN VMDB_ST201M m ON m.NRDOC = d.COD "
                "LEFT JOIN TMS_UNIVERS u ON u.COD = m.DTDEP "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY d.COD DESC) WHERE ROWNUM <= :n")
            res = _result(Biro26DB().execute_query(sql, p))
            for r in res.get("data") or []:
                r["nr"] = ("#" + str(r["nrmanual"]).strip()
                           if (r.get("nrmanual") or "").strip()
                           else f"COD {r['cod']}")
                r["posted"] = bool(r.get("lines"))
            return res
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ── cele PATRU file de detaliu ───────────────────────────────────────

    @staticmethod
    def detail(cod: int) -> Dict[str, Any]:
        """RO: continutul celor patru file pentru documentul selectat."""
        try:
            c = int(cod)
            db = Biro26DB()
            postings = _rows(db.execute_query(
                "SELECT l.DT, l.CT, l.SUMA, l.DTSC, l.CTSC, "
                "       ud.DENUMIREA DT_NAME, uc.DENUMIREA CT_NAME "
                "FROM VMDB_ST201D l "
                "LEFT JOIN TMS_UNIVERS ud ON ud.COD = l.DTSC "
                "LEFT JOIN TMS_UNIVERS uc ON uc.COD = l.CTSC "
                "WHERE l.NRDOC = :c ORDER BY l.RROWID", {"c": c}))
            items = _rows(db.execute_query(
                "SELECT l.CTSC COD, u.CODVECHI, u.DENUMIREA, u.UM, "
                "       l.CANT, l.PRET, l.SUMA "
                "FROM VMDB_ST201D l LEFT JOIN TMS_UNIVERS u ON u.COD = l.CTSC "
                "WHERE l.NRDOC = :c ORDER BY l.RROWID", {"c": c}))
            files = _rows(db.execute_query(
                "SELECT TXTCOMMENT, PFILE, LENGTHB(OLEOBJ) BYTES "
                "FROM VMDB_DOCS_OLE WHERE NRDOC = :c", {"c": c}))
            # RO: XLOG = jurnalul nativ al ERP-ului (cine/cind/ce)
            log = _rows(db.execute_query(
                "SELECT * FROM (SELECT TO_CHAR(ITIME,'DD.MM.YYYY HH24:MI:SS') T, "
                "IEVENT, USERID, MACHINE, COMENT "
                "FROM XLOG WHERE NRREC = :c ORDER BY ITIME DESC) "
                "WHERE ROWNUM <= 100", {"c": c}))
            return {"success": True, "data": {
                "postings": postings, "items": items,
                "files": files, "log": log}}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ── clienti: cautare pentru selectorul din antet ─────────────────────

    @staticmethod
    def clients(q: str = "", limit: int = 30) -> Dict[str, Any]:
        """RO: cautarea cumparatorului pentru comanda din back-office —
        peste clientii magazinului (YBIRO_CLIENT) SI peste contragentii ERP
        (TMS_UNIVERS), ca operatorul sa gaseasca pe oricine."""
        try:
            s = (q or "").strip().upper()
            p = {"q": f"%{s}%", "n": max(1, min(int(limit or 30), 100))}
            rows = _rows(Biro26DB().execute_query(
                "SELECT * FROM ("
                "  SELECT c.UNIVERS_COD COD, NVL(c.FULL_NAME, u.DENUMIREA) NAME, "
                "         c.IS_COMPANY, c.IDNO, c.PHONE, c.EMAIL, 'shop' SRC "
                "  FROM YBIRO_CLIENT c LEFT JOIN TMS_UNIVERS u ON u.COD = c.UNIVERS_COD "
                "  WHERE :q = '%%' OR UPPER(c.FULL_NAME) LIKE :q "
                "     OR UPPER(NVL(c.EMAIL,' ')) LIKE :q OR NVL(c.PHONE,' ') LIKE :q "
                "     OR TO_CHAR(c.UNIVERS_COD) LIKE :q OR NVL(c.IDNO,' ') LIKE :q "
                "  UNION ALL "
                "  SELECT u.COD, u.DENUMIREA, NULL, NULL, NULL, NULL, 'erp' "
                "  FROM TMS_UNIVERS u "
                "  WHERE u.TIP = 2 AND UPPER(u.DENUMIREA) LIKE :q "
                "    AND NOT EXISTS (SELECT 1 FROM YBIRO_CLIENT c2 "
                "                    WHERE c2.UNIVERS_COD = u.COD) "
                ") WHERE ROWNUM <= :n", p))
            for r in rows:
                r["is_company"] = str(r.get("is_company") or "0") == "1"
            return {"success": True, "data": rows}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ── inregistrare RAPIDA din back-office ──────────────────────────────

    @staticmethod
    def client_quick_add(name: str, is_company: bool = False, idno: str = "",
                         phone: str = "", email: str = "",
                         address: str = "") -> Dict[str, Any]:
        """RO: operatorul (casierul) inregistreaza un client NOU avind minimul
        necesar — DENUMIREA si tipul (fizica / juridica). Inregistrarea intra
        in ACELEASI tabele ca cea din cabinetul clientului: contragentul in
        TMS_UNIVERS (y_ai_BIRO26.register_client) si fisa in YBIRO_CLIENT.
        E-mailul nu e obligatoriu: fara el se pune unul tehnic, iar clientul
        isi poate cere ulterior acces la cabinet.
        EN: minimal back-office client registration into the SAME tables as
        the site's own sign-up."""
        from models.biro26_oracle_store import Biro26Store
        from controllers.biro26_controller import Biro26Controller
        import secrets

        nm = (name or "").strip()
        if len(nm) < 3:
            return {"success": False, "error": "denumirea este obligatorie (min. 3 caractere)"}
        idno = (idno or "").strip()
        if is_company and idno and not re.match(r"^\d{13}$", idno):
            return {"success": False, "error": "IDNO trebuie sa aiba 13 cifre"}
        em = (email or "").strip().lower()
        if em:
            if "@" not in em:
                return {"success": False, "error": "e-mail invalid"}
            if (Biro26Store.shop_client_by_email(em) or {}).get("data"):
                return {"success": False, "error": "acest e-mail este deja inregistrat"}
        else:
            # RO/EN: e-mail tehnic — unic, nefolosibil pentru login
            em = f"bo-{secrets.token_hex(6)}@officeplus.local"
        # RO: parola aleatoare — accesul in cabinet se activeaza separat
        pwd = Biro26Controller._hash_pwd(secrets.token_urlsafe(12))
        r = Biro26Store.shop_register_client(
            em, nm, phone or "", pwd, address=address or "",
            idno=idno if is_company else "", is_company=bool(is_company))
        if r.get("success"):
            r["data"]["email"] = em
            r["data"]["name"] = nm
            r["data"]["is_company"] = bool(is_company)
        return r

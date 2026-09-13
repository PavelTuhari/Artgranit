"""Facturile PRIMITE de la parteneri — partea de CUMPARATOR a e-Facturii.

RO: drumul unei facturi de la furnizor pina in una.md:
  1. SFS: `GetInvoicesForSigning` cu ActorRole=2 (cumparator) intoarce facturile
     care asteapta decizia noastra, CU XML-ul lor; `GetAcceptedInvoices`
     (rol 2) doar lista, XML-ul se ia cu `GetInvoicesBySeriaNumber`.
  2. `parse_invoice`: XML (Document/SupplierInfo, formatul TaxInvoiceSchema)
     -> antet + pozitii; semnatura XAdES se scoate (e uriasa si inutila).
  3. EFA_IN / EFA_IN_ROW (tabelele proprii): ce am primit, ce statut are in
     SFS, ce am decis noi, potrivirea cu nomenclatorul una.md:
       - furnizorul: TMS_UNIVERS.CODVECHI = IDNO (GR1 E) sau TMS_ORG.CODFISCAL;
       - marfa: TMS_MPT_BARCODE.BARCODE (cum face PKG_EDI_XML.fill_doc_1231);
       - serviciile: regulile TMS_IMPORT_EFACTURA (TEXT1 e un LIKE Oracle
         pe denumire; PRIORITET; DT = contul, DTSC = cardul) — aceleasi
         reguli pe care le foloseste clientul Delphi.
  4. Aterizarea in TMDB_XML_FACTURA prin EFA_INBOX.land (copia XPath-urilor
     din PKG_EDI_XML.blob_to_table, care e privat): aplicatia nativa vede
     factura exact ca pe una incarcata din fisier. NRDOC e rezervat din
     ID_TMDB_DOCS. Documentul contabil (formularul de intrare) NU se creeaza
     aici — OfficePlus nu are formularul 1231 pe care il cere fill_doc_1231;
     alegerea formularului e a contabilului (vezi documentatia).
  5. Decizia in SFS: PostAcceptedInvoices / PostRejectedInvoices.
EN: buyer-side inbox: fetch, parse, match against una.md, land into the
standard flat table, accept/reject in SFS.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from modules.efactura import sfs

# ── reguli pure (fara baza) ──────────────────────────────────────────────
_SIG = re.compile(r"<Signatures>.*?</Signatures>", re.S)


def strip_signature(xml: str) -> str:
    return _SIG.sub("", xml or "")


def wrap_documents(xml: str) -> str:
    """RO: PKG_EDI_XML asteapta //Documents/Document/SupplierInfo; SFS da <Document> gol."""
    body = strip_signature(xml).strip()
    body = re.sub(r"^<\?xml[^>]*\?>\s*", "", body)
    if body.startswith("<Documents"):
        return body
    return "<Documents>" + body + "</Documents>"


def _f(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", ".")) if v not in (None, "") else None
    except ValueError:
        return None


def _date(v: Optional[str]) -> str:
    return (v or "")[:10]


def parse_invoice(xml: str) -> Dict[str, Any]:
    """RO: <Document><SupplierInfo>… -> dict (antet + rows). ValueError la XML strain."""
    text = strip_signature(xml or "").strip()
    if not text:
        raise ValueError("XML gol")
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except ET.ParseError as e:
        raise ValueError("XML invalid: %s" % e) from e
    inf = root if root.tag == "SupplierInfo" else root.find(".//SupplierInfo")
    if inf is None:
        raise ValueError("lipseste SupplierInfo (nu e o factura e-Factura)")

    def party(tag: str) -> Dict[str, Any]:
        p = inf.find(tag)
        if p is None:
            return {}
        b = p.find("BankAccount")
        return {"idno": (p.get("IDNO") or "").strip(), "title": (p.get("Title") or "").strip(),
                "address": (p.get("Address") or "").strip(), "codtva": (p.get("CodTVA") or "").strip(),
                "taxpayer_type": p.get("TaxpayerType") or "",
                "account": (b.get("Account") if b is not None else "") or "",
                "branch_title": (b.get("BranchTitle") if b is not None else "") or "",
                "branch_code": (b.get("BranchCode") if b is not None else "") or ""}

    rows: List[Dict[str, Any]] = []
    for i, r in enumerate(inf.findall("Merchandises/Row"), start=1):
        rows.append({"rown": i, "code": (r.get("Code") or "").strip(), "name": (r.get("Name") or "").strip(),
                     "um": (r.get("UnitOfMeasure") or "").strip(), "qty": _f(r.get("Quantity")),
                     "price": _f(r.get("UnitPriceWithoutTVA")), "total_no_tva": _f(r.get("TotalPriceWithoutTVA")),
                     "tva_pct": _f(r.get("TVA")), "total_tva": _f(r.get("TotalTVA")),
                     "total": _f(r.get("TotalPrice")), "barcode": (r.get("BarCode") or "").strip()})
    return {"seria": (inf.findtext("Seria") or "").strip(), "number": (inf.findtext("Number") or "").strip(),
            "issued_date": _date(inf.findtext("IssuedDate")), "delivery_date": _date(inf.findtext("DeliveryDate")),
            "document_type": inf.get("DocumentType") or "", "document_form": inf.get("DocumentForm") or "",
            "supplier": party("Supplier"), "buyer": party("Buyer"), "transporter": party("Transporter"),
            "total": _f(inf.findtext("Total")), "total_tva": _f(inf.findtext("TotalTVA")),
            "creation_motiv": (inf.findtext("CreationMotiv") or "").strip(),
            "loading_point": (inf.findtext("LoadingPoint") or "").strip(),
            "unloading_point": (inf.findtext("UnloadingPoint") or "").strip(),
            "rows": rows}


def like_to_regex(pattern: str) -> "re.Pattern[str]":
    """RO: LIKE-ul Oracle din TMS_IMPORT_EFACTURA.TEXT1 (%SERVICII%BROKER%) -> regex."""
    out = []
    for ch in pattern or "":
        out.append(".*" if ch == "%" else "." if ch == "_" else re.escape(ch))
    return re.compile("^" + "".join(out) + "$", re.I | re.S)


_TR = str.maketrans({"ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
                     "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T"})


def fold(s: Optional[str]) -> str:
    return (s or "").translate(_TR).upper().strip()


def match_rule(name: str, rules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """RO: prima regula (dupa PRIORITET) al carei TEXT1 se potriveste pe denumire."""
    key = fold(name)
    for r in rules:
        pat = r.get("text1")
        if pat and like_to_regex(fold(pat)).match(key):
            return r
    return None


def sfs_entries(raw: str) -> List[Dict[str, Any]]:
    """RO: Results/XmlInvoice sau Results/Invoice din raspunsurile SFS -> lista
    {seria, number, status, invoice_status, message, xml}."""
    out: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("XmlInvoice", "Invoice", "InvoiceResult"):
            continue
        rec = {ch.tag.split("}")[-1]: (ch.text or "") for ch in el}
        out.append({"seria": rec.get("Seria", "").strip(), "number": rec.get("Number", "").strip(),
                    "status": rec.get("Status", "").strip(), "invoice_status": rec.get("InvoiceStatus", "").strip(),
                    "message": rec.get("Message", "").strip(), "xml": rec.get("Xml", "")})
    return out


def env_of(endpoint: Optional[str]) -> str:
    return "prod" if "efactura-api.sfs.md" in (endpoint or "") else "test"


# ── baza de date ─────────────────────────────────────────────────────────
class EfaInbox:
    @staticmethod
    def _db():
        from models.biro26_db import Biro26DB
        from models.biro26_oracle_store import _rows
        return Biro26DB(), _rows

    @staticmethod
    def list(env: str = "test", limit: int = 100) -> List[Dict[str, Any]]:
        db, rows = EfaInbox._db()
        return rows(db.execute_query(
            "SELECT * FROM (SELECT i.ID, i.ENV, i.SERIA, i.NUMBER_, i.SFS_STATUS, i.SFS_QUEUE, i.SUPPLIER_IDNO, "
            "i.SUPPLIER_NAME, i.BUYER_IDNO, TO_CHAR(i.ISSUED_DATE,'DD.MM.YYYY') ISSUED_DATE, i.TOTAL, i.TOTAL_TVA, "
            "i.STATUS, i.SUPPLIER_COD, i.NRDOC, i.PKG_NRDOC, i.PKG_STATUS, i.PKG_COMMENT, i.DEST_NRDOC, i.ERR_MSG, "
            "TO_CHAR(i.FETCHED_AT,'DD.MM.YYYY HH24:MI') FETCHED_AT, "
            "(SELECT COUNT(*) FROM EFA_IN_ROW r WHERE r.IN_ID=i.ID) ROWS_CNT, "
            "(SELECT COUNT(*) FROM EFA_IN_ROW r WHERE r.IN_ID=i.ID AND r.MATCH_KIND IN ('barcode','rule')) MATCHED_CNT, "
            "u.DENUMIREA SUPPLIER_UNA FROM EFA_IN i LEFT JOIN TMS_UNIVERS u ON u.COD=i.SUPPLIER_COD "
            "WHERE i.ENV=:e ORDER BY i.ISSUED_DATE DESC, i.ID DESC) WHERE ROWNUM <= :l",
            {"e": env, "l": max(1, min(int(limit), 500))}))

    @staticmethod
    def get(in_id: int) -> Optional[Dict[str, Any]]:
        db, rows = EfaInbox._db()
        r = rows(db.execute_query(
            "SELECT i.*, TO_CHAR(i.ISSUED_DATE,'DD.MM.YYYY') ISSUED_D, TO_CHAR(i.DELIVERY_DATE,'DD.MM.YYYY') DELIVERY_D, "
            "u.DENUMIREA SUPPLIER_UNA FROM EFA_IN i LEFT JOIN TMS_UNIVERS u ON u.COD=i.SUPPLIER_COD WHERE i.ID=:id",
            {"id": int(in_id)}))
        if not r:
            return None
        rec = r[0]
        rec.pop("xml", None)
        try:
            inv = parse_invoice(EfaInbox.xml(in_id))
            rec["supplier_address"] = (inv.get("supplier") or {}).get("address", "")
            rec["buyer_name"] = (inv.get("buyer") or {}).get("title", "")
        except ValueError:
            rec["supplier_address"], rec["buyer_name"] = "", ""
        rec["rows"] = rows(db.execute_query(
            "SELECT r.*, u.DENUMIREA UNA_NAME FROM EFA_IN_ROW r LEFT JOIN TMS_UNIVERS u ON u.COD=r.MATCH_COD "
            "WHERE r.IN_ID=:id ORDER BY r.ROWN", {"id": int(in_id)}))
        return rec

    @staticmethod
    def xml(in_id: int) -> str:
        db, rows = EfaInbox._db()
        parts, off = [], 1
        while True:
            r = rows(db.execute_query("SELECT DBMS_LOB.SUBSTR(XML, 4000, :o) T FROM EFA_IN WHERE ID=:id",
                                      {"o": off, "id": int(in_id)}))
            t = (r[0]["t"] if r else None) or ""
            parts.append(t)
            if len(t) < 4000:
                break
            off += 4000
        return "".join(parts)

    @staticmethod
    def upsert(env: str, entry: Dict[str, Any], queue: str) -> Dict[str, Any]:
        """RO: o factura primita -> EFA_IN (+ pozitiile in EFA_IN_ROW), dupa (ENV, SERIA, NUMBER)."""
        db, rows = EfaInbox._db()
        xml = strip_signature(entry.get("xml") or "")
        try:
            inv = parse_invoice(xml) if xml else {}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        seria = inv.get("seria") or entry.get("seria") or ""
        number = inv.get("number") or entry.get("number") or ""
        if not number:
            return {"success": False, "error": "factura fara numar"}
        have = rows(db.execute_query("SELECT ID, STATUS FROM EFA_IN WHERE ENV=:e AND SERIA=:s AND NUMBER_=:n",
                                     {"e": env, "s": seria, "n": number}))
        sup, buy = inv.get("supplier") or {}, inv.get("buyer") or {}
        vals = {"e": env, "s": seria, "n": number, "st": int(entry["invoice_status"]) if str(entry.get("invoice_status") or "").isdigit() else None,
                "q": queue[:20], "si": sup.get("idno"), "sn": (sup.get("title") or "")[:200], "bi": buy.get("idno"),
                "idt": inv.get("issued_date") or None, "ddt": inv.get("delivery_date") or None,
                "tot": inv.get("total"), "tva": inv.get("total_tva"), "dt": (inv.get("document_type") or "")[:2] or None,
                "df": (inv.get("document_form") or "")[:2] or None}
        # RO: aparuta in GetAcceptedInvoices (rol cumparator) = decizia noastra e inregistrata
        acc = "ACCEPTED" if queue == "accepted" else None
        if have:
            iid = int(have[0]["id"])
            r = db.execute_dml(
                "UPDATE EFA_IN SET STATUS=CASE WHEN :acc IS NOT NULL AND STATUS NOT IN ('REJECTED') THEN :acc ELSE STATUS END, "
                "SFS_STATUS=:st, SFS_QUEUE=:q, SUPPLIER_IDNO=NVL(:si,SUPPLIER_IDNO), "
                "SUPPLIER_NAME=NVL(:sn,SUPPLIER_NAME), BUYER_IDNO=NVL(:bi,BUYER_IDNO), "
                "ISSUED_DATE=NVL(TO_DATE(:idt,'YYYY-MM-DD'),ISSUED_DATE), DELIVERY_DATE=NVL(TO_DATE(:ddt,'YYYY-MM-DD'),DELIVERY_DATE), "
                "TOTAL=NVL(:tot,TOTAL), TOTAL_TVA=NVL(:tva,TOTAL_TVA), DOC_TYPE=NVL(:dt,DOC_TYPE), DOC_FORM=NVL(:df,DOC_FORM), "
                "UPDATED=SYSDATE WHERE ID=:id", dict({k: v for k, v in vals.items() if k not in ("e", "s", "n")}, id=iid, acc=acc))
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            if xml:
                db.execute_dml("UPDATE EFA_IN SET XML=:x WHERE ID=:id", {"x": xml, "id": iid})
            result = "updated"
        else:
            nx = rows(db.execute_query("SELECT EFA_IN_SEQ.NEXTVAL N FROM dual"))
            iid = int(nx[0]["n"])
            r = db.execute_dml(
                "INSERT INTO EFA_IN (ID, ENV, SERIA, NUMBER_, SFS_STATUS, SFS_QUEUE, SUPPLIER_IDNO, SUPPLIER_NAME, BUYER_IDNO, "
                "ISSUED_DATE, DELIVERY_DATE, TOTAL, TOTAL_TVA, DOC_TYPE, DOC_FORM, STATUS, XML) VALUES "
                "(:id, :e, :s, :n, :st, :q, :si, :sn, :bi, TO_DATE(:idt,'YYYY-MM-DD'), TO_DATE(:ddt,'YYYY-MM-DD'), "
                ":tot, :tva, :dt, :df, :status, :x)", dict(vals, id=iid, x=xml or None, status=acc or "NEW"))
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            result = "added"
        if inv.get("rows"):
            db.execute_dml("DELETE FROM EFA_IN_ROW WHERE IN_ID=:id", {"id": iid})
            for row in inv["rows"]:
                db.execute_dml(
                    "INSERT INTO EFA_IN_ROW (IN_ID, ROWN, CODE, NAME, UM, QTY, PRICE, TOTAL_NO_TVA, TVA_PCT, TOTAL_TVA, TOTAL, BARCODE) "
                    "VALUES (:i, :r, :c, :nm, :um, :q, :p, :t0, :tp, :tt, :t, :b)",
                    {"i": iid, "r": row["rown"], "c": row["code"][:64], "nm": row["name"][:400], "um": row["um"][:20],
                     "q": row["qty"], "p": row["price"], "t0": row["total_no_tva"], "tp": row["tva_pct"],
                     "tt": row["total_tva"], "t": row["total"], "b": row["barcode"][:40] or None})
            EfaInbox.match(iid)
        return {"success": True, "result": result, "id": iid, "seria": seria, "number": number}

    @staticmethod
    def match(in_id: int) -> Dict[str, Any]:
        """RO: furnizorul dupa IDNO; pozitiile: cod de bare -> marfa, altfel regula."""
        db, rows = EfaInbox._db()
        head = rows(db.execute_query("SELECT SUPPLIER_IDNO FROM EFA_IN WHERE ID=:id", {"id": int(in_id)}))
        if not head:
            return {"success": False, "error": "factura inexistenta"}
        idno = head[0].get("supplier_idno")
        sup = rows(db.execute_query(
            "SELECT u.COD FROM TMS_UNIVERS u LEFT JOIN TMS_ORG o ON o.COD=u.COD WHERE u.TIP='O' AND "
            "(u.CODVECHI=:i OR o.CODFISCAL=:i) AND ROWNUM<=1", {"i": idno})) if idno else []
        db.execute_dml("UPDATE EFA_IN SET SUPPLIER_COD=:c WHERE ID=:id",
                       {"c": int(sup[0]["cod"]) if sup else None, "id": int(in_id)})
        rules = rows(db.execute_query(
            "SELECT i.IDN, i.DT, i.DTSC, i.TEXT1, i.TEXT2, i.PRIORITET, u.DENUMIREA CARD FROM TMS_IMPORT_EFACTURA i "
            "LEFT JOIN TMS_UNIVERS u ON u.COD=i.DTSC ORDER BY i.PRIORITET, i.IDN"))
        stats = {"barcode": 0, "rule": 0, "none": 0}
        for r in rows(db.execute_query("SELECT ID, NAME, BARCODE FROM EFA_IN_ROW WHERE IN_ID=:id ORDER BY ROWN", {"id": int(in_id)})):
            kind, cod, dt, rule_id, mname = "none", None, None, None, None
            if r.get("barcode"):
                bc = rows(db.execute_query(
                    "SELECT b.COD, u.DENUMIREA FROM TMS_MPT_BARCODE b JOIN TMS_UNIVERS u ON u.COD=b.COD WHERE b.BARCODE=:b AND ROWNUM<=1",
                    {"b": r["barcode"]}))
                if bc:
                    kind, cod, mname = "barcode", int(bc[0]["cod"]), bc[0]["denumirea"]
            if kind == "none":
                ru = match_rule(r.get("name") or "", rules)
                if ru:
                    kind, dt, rule_id = "rule", ru.get("dt"), ru.get("idn")
                    cod = int(ru["dtsc"]) if ru.get("dtsc") else None
                    mname = ru.get("card") or ru.get("text2")
            stats[kind] += 1
            db.execute_dml("UPDATE EFA_IN_ROW SET MATCH_KIND=:k, MATCH_COD=:c, MATCH_DT=:d, MATCH_RULE=:r, MATCH_NAME=:n WHERE ID=:id",
                           {"k": kind, "c": cod, "d": dt, "r": rule_id, "n": (mname or "")[:200] or None, "id": int(r["id"])})
        return {"success": True, "supplier_cod": int(sup[0]["cod"]) if sup else None, "rows": stats}

    @staticmethod
    def land(in_id: int) -> Dict[str, Any]:
        """RO: EFA_INBOX.land -> TMDB_XML_FACTURA sub un NRDOC rezervat din ID_TMDB_DOCS."""
        db, rows = EfaInbox._db()
        head = rows(db.execute_query("SELECT SERIA, NUMBER_, NRDOC FROM EFA_IN WHERE ID=:id", {"id": int(in_id)}))
        if not head:
            return {"success": False, "error": "factura inexistenta"}
        xml = EfaInbox.xml(in_id)
        if not xml.strip():
            return {"success": False, "error": "factura nu are XML (doar din lista SFS) — reia preluarea"}
        nrdoc = head[0].get("nrdoc")
        if not nrdoc:
            nrdoc = int(rows(db.execute_query("SELECT EFA_INBOX.reserve_nrdoc N FROM dual"))[0]["n"])
        fname = "EFACTURA_IN_%s_%s.xml" % (head[0].get("seria") or "", head[0].get("number_") or "")
        r = db.call_proc("BEGIN EFA_INBOX.land(:n, :x, :f); END;", {"n": int(nrdoc), "x": wrap_documents(xml), "f": fname})
        if not r.get("success"):
            db.execute_dml("UPDATE EFA_IN SET STATUS='ERROR', ERR_MSG=:m, UPDATED=SYSDATE WHERE ID=:id",
                           {"m": str(r.get("message"))[:2000], "id": int(in_id)})
            return {"success": False, "error": str(r.get("message"))[:600]}
        cnt = rows(db.execute_query("SELECT COUNT(*) N FROM TMDB_XML_FACTURA WHERE NRDOC=:n", {"n": int(nrdoc)}))[0]["n"]
        db.execute_dml("UPDATE EFA_IN SET NRDOC=:n, STATUS=CASE WHEN STATUS IN ('ACCEPTED','REJECTED') THEN STATUS ELSE 'LANDED' END, "
                       "ERR_MSG=NULL, UPDATED=SYSDATE WHERE ID=:id", {"n": int(nrdoc), "id": int(in_id)})
        return {"success": True, "nrdoc": int(nrdoc), "rows_landed": int(cnt), "file_name": fname}

    @staticmethod
    def decide(in_id: int, action: str, comment: str, api: Optional[Dict[str, Any]], src: str = "test-page") -> Dict[str, Any]:
        db, rows = EfaInbox._db()
        head = rows(db.execute_query("SELECT SERIA, NUMBER_ FROM EFA_IN WHERE ID=:id", {"id": int(in_id)}))
        if not head:
            return {"success": False, "error": "factura inexistenta"}
        c = sfs.SfsClient.from_api(api, signer=1, src=src)
        if not c.configured():
            return {"success": False, "error": "contul API lipseste"}
        pair = (head[0].get("seria") or "", head[0].get("number_") or "")
        if action == "accept":
            r = c.post_accepted([pair])
        elif action == "reject":
            r = c.post_rejected([(pair[0], pair[1], (comment or "").strip() or "Respins de cumparator")])
        else:
            return {"success": False, "error": "actiune necunoscuta"}
        # RO: DecisionResponse = Results/InvoiceResult{Number, Seria, Message, Status, TimeStamp};
        #     masurat 13.09.2026: Status 2 si Message gol = decizia inregistrata (factura a
        #     trecut din coada cumparatorului in GetAcceptedInvoices, InvoiceStatus 3)
        results = sfs_entries(r.get("raw", "")) if r.get("success") else []
        res = results[0] if results else {}
        ok = bool(r.get("success")) and str(res.get("status") or "") == "2" and not res.get("message")
        st = ("ACCEPTED" if action == "accept" else "REJECTED") if ok else None
        db.execute_dml("UPDATE EFA_IN SET STATUS=NVL(:s, STATUS), ERR_MSG=:m, UPDATED=SYSDATE WHERE ID=:id",
                       {"s": st, "m": (res.get("message") or (None if r.get("success") else str(r.get("error"))))[:2000] if (res.get("message") or not r.get("success")) else None,
                        "id": int(in_id)})
        return {"success": bool(ok), "sfs": {"status": r.get("status"), "result": res},
                "error": None if ok else (res.get("message") or r.get("error") or "SFS nu a confirmat")}


PKG_STATUS = {1: "valida", 3: "DocumentType/DocumentForm neacceptat", 4: "seria trebuie sa aiba doar litere latine mari",
              5: "numarul trebuie sa aiba doar cifre / exista deja", 6: "data facturii in afara intervalului permis",
              7: "furnizorul (IDNO) nu exista in nomenclator", 8: "subdiviziunea cumparatorului nu exista",
              9: "dublura in documente", 10: "dublura in XML", 12: "exista deja in CST3A", 13: "exista deja in alt pachet",
              14: "dublura in VINZ (seria+nr)", 15: "eroare la crearea documentului"}


def with_unloading_code(doc: str, code: Optional[str]) -> str:
    """RO: PKG_EDI_XML ia subdiviziunea cumparatorului (depozitul, VMS_UNIVERS TIP O/GR1 I) din
    SupplierInfo/UnloadingPointCode; SFS nu il trimite (doar textul UnloadingPoint), asa ca
    il completam din setarea in_dtdep — altfel vendorul da STATUS_DOC 8. Nu suprascriem unul existent."""
    if not code or "<UnloadingPointCode" in doc:
        return doc
    tag = "<UnloadingPointCode>%s</UnloadingPointCode>" % str(code).strip()
    if "<UnloadingPoint>" in doc:
        return doc.replace("<UnloadingPoint>", tag + "<UnloadingPoint>", 1)
    return doc.replace("<Total>", tag + "<Total>", 1)


def package_xml(xmls: List[str], unloading_code: Optional[str] = None) -> str:
    """RO: pachetul e-Factura ca in fisierul descarcat de pe portal: <Documents> cu N <Document>."""
    body = "".join(with_unloading_code(re.sub(r"^<\?xml[^>]*\?>\s*", "", strip_signature(x).strip()), unloading_code)
                   for x in xmls if x and x.strip())
    return '<?xml version="1.0" encoding="UTF-8"?><Documents>' + body + "</Documents>"


class EfaPackage:
    """RO: pachetul 12103 + documentele 1209 — EXACT fluxul din BMPUBLIC/FPROIECT."""

    @staticmethod
    def rows(nrdoc: int) -> List[Dict[str, Any]]:
        db, rows = EfaInbox._db()
        out = rows(db.execute_query(
            "SELECT p.NRDOC1, p.FACTURA_SERIA, p.FACTURA_NR, TO_CHAR(p.FACTURA_ISSUEDDATE,'DD.MM.YYYY') ISSUED, p.SUPPLIER_DIV, "
            "p.STATUS_DOC, p.NRDOC_DEST, p.COMMENTS, p.TOTAL, p.TOTALTVA, d.NRMANUAL DEST_NRMANUAL, "
            "(SELECT COUNT(*) FROM VMDB_ST201D l WHERE l.NRDOC = p.NRDOC_DEST) DEST_ROWS, "
            "(SELECT COUNT(*) FROM VMDB_ST201D l WHERE l.NRDOC = p.NRDOC_DEST AND l.DTSC IS NOT NULL) DEST_ROWS_MATCHED "
            "FROM TMDB_XML_PACKAGE p LEFT JOIN TMDB_DOCS d ON d.COD = p.NRDOC_DEST WHERE p.NRDOC = :n ORDER BY p.NRDOC1",
            {"n": int(nrdoc)}))
        for r in out:
            r["status_text"] = PKG_STATUS.get(int(r["status_doc"] or 0), "statut %s" % r.get("status_doc"))
        return out

    @staticmethod
    def _apply(nrdoc: int, ids: List[int]) -> None:
        """RO: rezultatul pachetului inapoi in EFA_IN (dupa seria+nr)."""
        db, rows = EfaInbox._db()
        for r in EfaPackage.rows(nrdoc):
            db.execute_dml(
                "UPDATE EFA_IN SET PKG_NRDOC=:n, PKG_NRDOC1=:n1, PKG_STATUS=:st, PKG_COMMENT=:c, DEST_NRDOC=:d, "
                "STATUS=CASE WHEN :d IS NOT NULL THEN 'IMPORTED' WHEN :st = 1 THEN STATUS ELSE 'ERROR' END, "
                "ERR_MSG=CASE WHEN :d IS NOT NULL THEN NULL ELSE ERR_MSG END, UPDATED=SYSDATE "
                "WHERE ID IN (%s) AND SERIA=:s AND NUMBER_=:nr" % ",".join(str(int(i)) for i in ids),
                {"n": int(nrdoc), "n1": r["nrdoc1"], "st": r["status_doc"], "c": (r.get("comments") or r["status_text"])[:2000],
                 "d": r.get("nrdoc_dest"), "s": r.get("factura_seria") or "", "nr": r.get("factura_nr") or ""})

    @staticmethod
    def import_invoices(ids: List[int], *, nrdoc: Optional[int] = None, create_docs: bool = True) -> Dict[str, Any]:
        """RO: 1) XML-ul pachetului din EFA_IN; 2) document 12103 nou (sau cel dat) + OLE;
        3) pkg_edi_xml.import_xml_package_object; 4) EFA_INBOX.create_docs_1209."""
        db, rows = EfaInbox._db()
        ids = [int(i) for i in ids]
        if not ids:
            return {"success": False, "error": "nicio factura aleasa"}
        xmls = [EfaInbox.xml(i) for i in ids]
        xmls = [x for x in xmls if x.strip()]
        if not xmls:
            return {"success": False, "error": "facturile nu au XML — reia preluarea"}
        from .store import EfaStore
        pkg = package_xml(xmls, EfaStore.settings().get("in_dtdep"))
        fname = "EFACTURA_API_%s.xml" % __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
        if nrdoc:
            r = db.call_proc("BEGIN EFA_INBOX.attach(:n, :x, :f); END;", {"n": int(nrdoc), "x": pkg, "f": fname})
            if not r.get("success"):
                return {"success": False, "error": "attach: " + str(r.get("message"))[:600]}
        else:
            r = db.call_proc("BEGIN :n := EFA_INBOX.new_package(:x, :f); END;", {"n": 0, "x": pkg, "f": fname})
            nrdoc = None
            if r.get("success"):
                got = rows(db.execute_query("SELECT MAX(COD) N FROM TMDB_DOCS WHERE SYSFID = 12103"))
                nrdoc = int(got[0]["n"]) if got and got[0]["n"] else None
            if not nrdoc:
                return {"success": False, "error": "new_package: " + str(r.get("message"))[:600]}
        r = db.call_proc("BEGIN EFA_INBOX.import_package(:n); END;", {"n": int(nrdoc)})
        if not r.get("success"):
            for i in ids:
                db.execute_dml("UPDATE EFA_IN SET PKG_NRDOC=:n, STATUS='ERROR', ERR_MSG=:m, UPDATED=SYSDATE WHERE ID=:id",
                               {"n": int(nrdoc), "m": str(r.get("message"))[:2000], "id": i})
            return {"success": False, "error": "import_xml_package_object: " + str(r.get("message"))[:600], "nrdoc": nrdoc}
        created = None
        if create_docs:
            rc = db.call_proc("BEGIN EFA_INBOX.create_docs_1209(:n); END;", {"n": int(nrdoc)})
            created = rc.get("success")
            if not created:
                for i in ids:
                    db.execute_dml("UPDATE EFA_IN SET ERR_MSG=:m WHERE ID=:id", {"m": str(rc.get("message"))[:2000], "id": i})
        EfaPackage._apply(nrdoc, ids)
        prows = EfaPackage.rows(nrdoc)
        return {"success": True, "nrdoc": int(nrdoc), "file_name": fname, "package": prows,
                "created_docs": [int(x["nrdoc_dest"]) for x in prows if x.get("nrdoc_dest")],
                "create_docs_ok": created}

    @staticmethod
    def fill_from_sfs(nrdoc: int, api: Optional[Dict[str, Any]] = None, src: str = "native") -> Dict[str, Any]:
        """RO: actiunea din Delphi pe pachetul 12103: aduce din SFS facturile NOI (neimportate)
        ale cumparatorului si le pune in pachet; documentele 1209 le face «Сформировать документы»."""
        c = sfs.SfsClient.from_settings(signer=1, src=src) if api is None else sfs.SfsClient.from_api(api, 1, src)
        env = env_of(c.endpoint)
        s = sync(api if api is not None else {"endpoint": c.endpoint, "username": c.username, "password": c.password}, src=src)
        if not s.get("success"):
            return s
        db, rows = EfaInbox._db()
        pend = rows(db.execute_query("SELECT ID FROM EFA_IN WHERE ENV=:e AND PKG_NRDOC IS NULL AND DEST_NRDOC IS NULL "
                                     "AND XML IS NOT NULL ORDER BY ID", {"e": env}))
        ids = [int(x["id"]) for x in pend]
        if not ids:
            return {"success": True, "nrdoc": int(nrdoc), "found": s.get("found"), "imported": 0, "message": "nicio factura noua"}
        r = EfaPackage.import_invoices(ids, nrdoc=int(nrdoc), create_docs=False)
        r["found"], r["imported"] = s.get("found"), len(ids)
        return r


def sync(api: Optional[Dict[str, Any]], src: str = "test-page") -> Dict[str, Any]:
    """RO: aduce din SFS facturile in care sintem CUMPARATOR: cozile de decizie
    (Order 1 si 2, cu XML) si cele deja acceptate (lista, apoi XML pe fiecare)."""
    c = sfs.SfsClient.from_api(api, signer=1, src=src)
    if not c.configured():
        return {"success": False, "error": "contul API lipseste"}
    env = env_of(c.endpoint)
    seen, added, updated, errors = set(), 0, 0, []
    for label, r in (("for_signing", c.get_for_signing(order=1, actor_role=sfs.ROLE_BUYER)),
                     ("for_signing_2", c.get_for_signing(order=2, actor_role=sfs.ROLE_BUYER)),
                     ("accepted", c.get_accepted(actor_role=sfs.ROLE_BUYER))):
        if not r.get("success"):
            errors.append("%s: %s" % (label, str(r.get("error"))[:200]))
            continue
        for e in sfs_entries(r.get("raw", "")):
            key = (e["seria"], e["number"])
            if key in seen or not e["number"]:
                continue
            seen.add(key)
            if not e.get("xml"):
                rx = c.get_by_seria_number(e["seria"], e["number"])
                got = sfs_entries(rx.get("raw", "")) if rx.get("success") else []
                e["xml"] = (got[0].get("xml") if got else "") or ""
            u = EfaInbox.upsert(env, e, "for_signing" if label.startswith("for") else label)
            if u.get("success"):
                added += u["result"] == "added"
                updated += u["result"] == "updated"
            else:
                errors.append("%s %s: %s" % (e["seria"], e["number"], u.get("error")))
    return {"success": True, "env": env, "found": len(seen), "added": added, "updated": updated, "errors": errors}

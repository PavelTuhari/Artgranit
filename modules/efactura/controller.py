"""Logica modulului e-Factura — UNA singura, pentru toate cele trei intrari.

RO: back-office-ul, cabinetul clientului si API-ul intern apeleaza EXACT
aceleasi functii de aici. Asa nu se poate intimpla ca butonul din admin sa
trimita altceva decit apelul din aplicatia nativa — la fel cum forma tiparita
a contului e una pentru toti.
EN: one implementation shared by the back office, the client cabinet and the
machine API — the same principle as the printed invoice form.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from models.biro26_report import Biro26Report

from modules.efactura import sfs
from modules.efactura.store import EfaStore


class EfaController:

    # ── datele facturii ────────────────────────────────────────────────
    @staticmethod
    def build_payload(doc_cod: int,
                      allowed_client_cod: Optional[int] = None
                      ) -> Dict[str, Any]:
        """RO: documentul + rechizitele vinzatorului, pregatite pentru XML.
        `allowed_client_cod` = clientul din cabinet: nu are voie sa vada
        documentul altcuiva (aceeasi regula ca la PDF-ul contului)."""
        r = Biro26Report.doc_data(int(doc_cod))
        if not r.get("success"):
            return {"success": False, "error": r.get("error", "document lipsa")}
        if (allowed_client_cod is not None
                and int(r.get("client_cod") or 0) != int(allowed_client_cod)):
            return {"success": False, "error": "forbidden"}
        raw = r["data"]
        s = EfaStore.settings()
        # RO: rechizitele VINZATORULUI le stie deja ERP-ul (blocul `firm` din
        #     care se tipareste contul) — setarile din admin doar le
        #     SUPRASCRIU, daca cineva vrea alt IDNO/IBAN. Asa nu se poate
        #     intimpla ca pe hirtie sa fie o firma si in e-Factura alta.
        # EN: seller requisites come from the ERP block the printed invoice
        #     uses; admin settings only override them.
        firm = raw.get("firm") or {}
        client = raw.get("client") or {}
        seller = {
            "idno": s.get("seller_idno") or firm.get("fiscal_code"),
            "name": s.get("seller_name") or firm.get("name"),
            "address": s.get("seller_address") or firm.get("address"),
            "iban": s.get("seller_iban") or firm.get("iban"),
            "bank_code": s.get("seller_bank_code") or firm.get("branch"),
        }
        # RO: aplatizam documentul in forma asteptata de constructorul XML
        total = float(raw.get("total") or 0)
        tva = float(raw.get("tva") or 0)
        doc = {
            "nrmanual": raw.get("nrmanual") or raw.get("cont_number"),
            "issue_date": EfaController._iso_date(raw.get("date_short")),
            "client_name": client.get("name"),
            "client_idno": client.get("fiscal_code"),
            "client_address": client.get("address"),
            "items": raw.get("items") or [],
            "total": total,
            "tva": tva,
            "total_fara_tva": round(total - tva, 2),
            "tva_rate": 20,
        }
        return {"success": True, "doc": doc, "seller": seller, "raw": raw,
                "client_cod": r.get("client_cod"), "settings": s}

    @staticmethod
    def _iso_date(dmy: Optional[str]) -> Optional[str]:
        """RO: 28.08.2026 -> 2026-08-28 (formatul cerut in XML)."""
        try:
            d, m, y = str(dmy).split(".")
            return f"{y}-{m}-{d}"
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def preview_xml(doc_cod: int,
                    allowed_client_cod: Optional[int] = None) -> Dict[str, Any]:
        """RO: XML-ul care AR pleca — se poate vedea inainte de trimitere si
        fara credentiale. Util cit timp integrarea nu e inca configurata."""
        p = EfaController.build_payload(doc_cod, allowed_client_cod)
        if not p.get("success"):
            return p
        xml = sfs.build_invoice_xml(p["doc"], p["seller"],
                                    seria=p["settings"].get("seria", ""))
        return {"success": True, "data": {"xml": xml,
                                          "doc_cod": int(doc_cod),
                                          "nrmanual": p["doc"].get("nrmanual")}}

    # ── trimiterea ─────────────────────────────────────────────────────
    @staticmethod
    def send(doc_cod: int, src: str = "backoffice",
             allowed_client_cod: Optional[int] = None) -> Dict[str, Any]:
        """RO: trimite documentul in SIA e-Factura si scrie rezultatul in
        EFA_DOC + EFA_LOG. Nu arunca exceptii spre interfata: orice esec se
        vede ca status ERROR cu mesajul de la SFS."""
        p = EfaController.build_payload(doc_cod, allowed_client_cod)
        if not p.get("success"):
            return p
        doc, s = p["doc"], p["settings"]
        idno = str(doc.get("client_idno") or "").strip()
        # RO: factura fiscala electronica are sens pentru persoane JURIDICE;
        #     pentru persoane fizice SFS nu asteapta document electronic.
        if s.get("only_companies", "1") == "1" and not idno:
            return {"success": False,
                    "error": "RO: clientul nu are IDNO (persoana fizica) — "
                             "e-Factura se emite persoanelor juridice / "
                             "EN: buyer has no IDNO"}
        xml = sfs.build_invoice_xml(doc, p["seller"], seria=s.get("seria", ""))
        EfaStore.doc_upsert(doc_cod, NRMANUAL=str(doc.get("nrmanual") or "")[:40],
                            CLIENT_COD=p.get("client_cod"),
                            CLIENT_IDNO=idno[:20] or None,
                            TOTAL=doc.get("total"), STATUS="NEW")
        client = sfs.SfsClient.from_settings()
        r = client.post_invoices(xml)
        EfaStore.log(doc_cod, "post_invoices",
                     f"src={src} xml={xml[:900]}", src)
        if not r.get("success"):
            EfaStore.doc_upsert(doc_cod, STATUS="ERROR",
                                ERR_MSG=str(r.get("error"))[:1000])
            EfaStore.log(doc_cod, "post_error", str(r.get("error"))[:1500], src)
            return {"success": False, "error": r.get("error")}
        parsed = r.get("parsed") or {}
        posted = parsed.get("TotalInvoicesPosted") or parsed.get("Status")
        err = parsed.get("ErrorMessage")
        status = "SENT" if not err else "ERROR"
        EfaStore.doc_upsert(doc_cod, STATUS=status,
                            REQUEST_ID=str(r.get("request_id"))[:80],
                            ERR_MSG=(str(err)[:1000] if err else None),
                            SENT_AT=None)
        # RO: SENT_AT se pune prin SQL (SYSDATE), nu din aplicatie
        if status == "SENT":
            from models.biro26_db import Biro26DB
            Biro26DB().execute_dml(
                "UPDATE EFA_DOC SET SENT_AT = SYSDATE WHERE DOC_COD = :c",
                {"c": int(doc_cod)})
        EfaStore.log(doc_cod, "post_reply", str(parsed)[:1500], src)
        return {"success": status == "SENT", "data": {
            "doc_cod": int(doc_cod), "status": status,
            "request_id": r.get("request_id"), "posted": posted,
            "error": err}}

    # ── statusuri ──────────────────────────────────────────────────────
    @staticmethod
    def refresh_statuses(days: int = 7) -> Dict[str, Any]:
        """RO: aduce de la SFS facturile acceptate/respinse si actualizeaza
        starile locale. Se poate chema din admin sau dintr-un cron."""
        client = sfs.SfsClient.from_settings()
        if not client.configured():
            return {"success": False, "error": "not configured"}
        # RO: `days` ramine in semnatura pentru apelanti (admin, cron), dar
        #     contractul SFS nu are filtru de date la aceste metode:
        #     GetAcceptedInvoices / GetRejectedInvoices primesc doar
        #     ActorBaseRequest (RequestId + ActorRole) — verificat in XSD.
        out = {"days_ignored": int(days)}
        for kind, fn in (("ACCEPTED", client.get_accepted),
                         ("REJECTED", client.get_rejected)):
            r = fn()
            EfaStore.log(None, f"get_{kind.lower()}", str(r.get("parsed")
                         or r.get("error"))[:1200], "backoffice")
            out[kind] = r.get("success")
        return {"success": True, "data": out}

    @staticmethod
    def status(doc_cod: int,
               allowed_client_cod: Optional[int] = None) -> Dict[str, Any]:
        """RO: starea documentului — pentru butonul din cabinet si pentru API."""
        if allowed_client_cod is not None:
            chk = EfaController.build_payload(doc_cod, allowed_client_cod)
            if not chk.get("success"):
                return chk
        st = EfaStore.doc_state(int(doc_cod))
        return {"success": True, "data": st or {"doc_cod": int(doc_cod),
                                                "status": "NEW"}}

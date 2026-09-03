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
            # RO: XSD: BankAccount@BranchTitle = denumirea bancii
            "bank_name": firm.get("bank"),
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
            # RO: banca cumparatorului — ERP-ul o stie (exportul real al SFS
            #     o are mereu); XML-ul o pune doar daca exista IBAN.
            "client_iban": client.get("iban"),
            "client_bank": client.get("bank"),
            "client_bank_code": client.get("bic"),
            "items": raw.get("items") or [],
            "total": total,
            "tva": tva,
            "total_fara_tva": round(total - tva, 2),
            # RO: cota TVA se deduce din document cind el are TVA calculat;
            #     altfel se ia din setari (`tva_rate`, implicit 20). Pe A-88
            #     ERP-ul dadea tva=0 la un total de 20.149 lei — cu 20 fix am
            #     fi raportat 3.358 lei TVA inexistent in document.
            "tva_rate": EfaController._tva_rate(total, tva, s),
        }
        return {"success": True, "doc": doc, "seller": seller, "raw": raw,
                "client_cod": r.get("client_cod"), "settings": s}

    # RO: regula SFS, primita ca raspuns real la 02.09.2026 pe patru conturi
    #     din august: «Specify the correct date for the IssuedDate element …
    #     the date can be specified 0 days before or 10 days after the
    #     current date». Adica factura se inregistreaza in e-Factura in ZIUA
    #     eliberarii (sau cu data in viitor, pina la 10 zile) — un document
    #     mai vechi nu mai poate fi trimis. Verificam INAINTE de apel, ca
    #     operatorul sa primeasca motivul in romana, nu un ERROR generic.
    DATE_WINDOW_DAYS = 10

    @staticmethod
    def date_window_error(issue_date: str,
                          override_date: Optional[str] = None) -> Optional[str]:
        """RO: None daca data e in fereastra [azi, azi+10]; altfel mesajul."""
        import datetime as _d
        day = str(override_date or issue_date or "")[:10]
        try:
            d = _d.date.fromisoformat(day)
        except ValueError:
            return "Data eliberării lipsește sau e invalidă (%s)." % day
        today = _d.date.today()
        if d < today:
            return ("Data eliberării %s e în trecut: e-Factura primește facturi "
                    "doar cu data de azi sau cu până la %d zile în viitor. "
                    "Factura trebuie transmisă în ziua eliberării."
                    % (d.strftime("%d.%m.%Y"), EfaController.DATE_WINDOW_DAYS))
        if (d - today).days > EfaController.DATE_WINDOW_DAYS:
            return ("Data eliberării %s e cu mai mult de %d zile în viitor."
                    % (d.strftime("%d.%m.%Y"), EfaController.DATE_WINDOW_DAYS))
        return None

    @staticmethod
    def _tva_rate(total: float, tva: float, settings: Dict[str, Any]) -> float:
        """RO: cota din document (tva / baza), rotunjita la cotele legale
        (20, 12, 8, 0); fara TVA in document -> setarea `tva_rate`."""
        if total and tva and total > tva:
            pct = round(tva / (total - tva) * 100)
            return float(min((20, 12, 8, 0), key=lambda k: abs(k - pct)))
        try:
            return float(settings.get("tva_rate") or 20)
        except (TypeError, ValueError):
            return 20.0

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
             allowed_client_cod: Optional[int] = None,
             override_date: Optional[str] = None) -> Dict[str, Any]:
        """RO: trimite documentul in SIA e-Factura si scrie rezultatul in
        EFA_DOC + EFA_LOG. Nu arunca exceptii spre interfata: orice esec se
        vede ca status ERROR cu mesajul de la SFS.

        `override_date` (YYYY-MM-DD) inlocuieste data eliberarii — DOAR
        pentru probe pe mediul de test cu documente vechi; in productie nu se
        da niciodata: data fiscala e cea a documentului."""
        p = EfaController.build_payload(doc_cod, allowed_client_cod)
        if not p.get("success"):
            return p
        doc, s = p["doc"], p["settings"]
        # RO: DATA FACTURII FISCALE = ziua in care se emite in e-Factura, adica
        #     ACUM. Documentul din ERP e un «CONT la plata» (comanda), nu
        #     factura fiscala — data lui ramine in ERP (EFA_DOC.NRMANUAL o
        #     leaga). SFS oricum primeste doar azi…azi+10 («Specify the
        #     correct date…»), iar pe 03.09.2026 contabilul a fost refuzat pe
        #     un cont de ieri — gresit: contul poate fi de ieri, factura se
        #     emite azi. `override_date` ramine doar pentru probe.
        import datetime as _d
        doc["issue_date"] = (str(override_date)[:10] if override_date
                             else _d.date.today().isoformat())
        doc["delivery_date"] = doc["issue_date"]
        # RO: fereastra de date a SFS — refuz clar INAINTE de apel
        werr = EfaController.date_window_error(doc.get("issue_date"))
        if werr:
            EfaStore.doc_upsert(doc_cod, NRMANUAL=str(doc.get("nrmanual") or "")[:40],
                                CLIENT_COD=p.get("client_cod"),
                                TOTAL=doc.get("total"), STATUS="ERROR",
                                ERR_MSG=werr[:1900])
            EfaStore.log(doc_cod, "date_window", werr[:1500], src)
            return {"success": False, "error": werr,
                    "data": {"doc_cod": doc_cod, "status": "ERROR"}}
        idno = str(doc.get("client_idno") or "").strip()
        # RO: factura fiscala electronica are sens pentru persoane JURIDICE;
        #     pentru persoane fizice SFS nu asteapta document electronic.
        if s.get("only_companies", "1") == "1" and not idno:
            return {"success": False,
                    "error": "RO: clientul nu are IDNO (persoana fizica) — "
                             "e-Factura se emite persoanelor juridice / "
                             "EN: buyer has no IDNO"}
        # RO: numarul nostru (A-81) merge ca Number — referinta noastra;
        #     SFS il inlocuieste cu numarul lui la semnare.
        # RO: cifra de control a IDNO-ului — refuz local, fara apel la SFS
        from modules.efactura.rules import idno_error
        ierr = idno_error(idno, "clientului")
        if ierr:
            EfaStore.doc_upsert(doc_cod, NRMANUAL=str(doc.get("nrmanual") or "")[:40],
                                CLIENT_COD=p.get("client_cod"),
                                TOTAL=doc.get("total"), STATUS="ERROR",
                                ERR_MSG=ierr[:1900])
            return {"success": False, "error": ierr,
                    "data": {"doc_cod": doc_cod, "status": "ERROR"}}
        xml = sfs.build_invoice_xml(doc, p["seller"], seria=s.get("seria", ""),
                                    number=str(doc.get("nrmanual") or ""))
        EfaStore.doc_upsert(doc_cod, NRMANUAL=str(doc.get("nrmanual") or "")[:40],
                            CLIENT_COD=p.get("client_cod"),
                            CLIENT_IDNO=idno[:20] or None,
                            TOTAL=doc.get("total"), STATUS="NEW")
        client = sfs.SfsClient.from_settings(src=src)
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
            # RO: SENT_AT prin SYSDATE si ERR_MSG golit explicit — upsert-ul
            #     nu suprascrie cu NULL, iar mesajul refuzului anterior ramine
            #     lipit de un document deja acceptat (vazut pe A-81, 02.09.2026).
            Biro26DB().execute_dml(
                "UPDATE EFA_DOC SET SENT_AT = SYSDATE, ERR_MSG = NULL "
                "WHERE DOC_COD = :c", {"c": int(doc_cod)})
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

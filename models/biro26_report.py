"""Biro26 printable reports via the jsReport sidecar (reports/, Node.js).

RO: Randare PDF pentru "cont de plata" si "comanda cumparatorului" din
    documentele create de y_ai_BIRO26 (vizibile in VMDB_DOCS_WORK /
    VMDB_ST201M / VMDB_ST201D). Sablonul Handlebars + datele se trimit
    inline la POST {JSREPORT_URL}/api/report (recipe chrome-pdf), deci nu
    depindem de store-ul jsReport.
EN: PDF rendering for the invoice ("cont de plata") and customer order
    forms of documents created by y_ai_BIRO26. The Handlebars template +
    data go inline to POST {JSREPORT_URL}/api/report (chrome-pdf recipe),
    so no jsReport store configuration is required.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

from config import Config
from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

_TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "reports", "templates")

REPORT_KINDS = {"invoice": "biro26_invoice.hbs", "order": "biro26_order.hbs"}

_RO_MONTHS = ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
              "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie"]


def _read(fname: str) -> str:
    with open(os.path.join(_TPL_DIR, fname), encoding="utf-8") as f:
        return f.read()


class Biro26Report:

    @staticmethod
    def doc_data(cod: int) -> Dict[str, Any]:
        """Collect everything the forms need for one document COD."""
        db = Biro26DB()
        head = _rows(db.execute_query(
            "SELECT d.COD, d.NRSET, TO_CHAR(d.DATAMANUAL,'DD.MM.YYYY') DDATE, "
            "TO_CHAR(d.DATAMANUAL,'DD') DD, TO_CHAR(d.DATAMANUAL,'MM') MM, "
            "TO_CHAR(d.DATAMANUAL,'YYYY') YY, m.DTDEP CLIENT_COD, "
            "u.DENUMIREA CLIENT_NAME "
            "FROM TMDB_DOCS d "
            "JOIN VMDB_ST201M m ON m.NRDOC = d.COD "
            "LEFT JOIN TMS_UNIVERS u ON u.COD = m.DTDEP "
            "WHERE d.COD = :c", {"c": int(cod)}))
        if not head:
            return {"success": False, "error": "document not found"}
        h = head[0]
        # RO: telefon/email daca clientul e din magazinul public
        # EN: phone/email when the client came from the public shop
        extra = _rows(db.execute_query(
            "SELECT phone, email FROM YBIRO_CLIENT WHERE univers_cod = :c",
            {"c": h["client_cod"]}))
        lines = _rows(db.execute_query(
            "SELECT l.CTSC, l.CANT, l.SUMA, l.PRET, u.DENUMIREA, u.UM, u.CODVECHI "
            "FROM VMDB_ST201D l LEFT JOIN TMS_UNIVERS u ON u.COD = l.CTSC "
            "WHERE l.NRDOC = :c ORDER BY l.RROWID", {"c": int(cod)}))
        items, total = [], 0.0
        for ln in lines:
            s = float(ln["suma"] or 0)
            total += s
            qty = float(ln["cant"] or 0)
            items.append({
                "name": ln["denumirea"] or f"#{ln['ctsc']}",
                "cod": ln["codvechi"] or ln["ctsc"],
                "qty": int(qty) if qty == int(qty) else qty,
                "um": ln["um"] or "buc.",
                "price": float(ln["pret"] or 0) or (s / qty if qty else 0),
                "sum": s,
            })
        rate = Config.BIRO26_TVA_RATE
        data = {
            "number": h["nrset"],
            "date_short": h["ddate"],
            "date_ro": f"{h['dd']} {_RO_MONTHS[int(h['mm'])]} {h['yy']}",
            "firm": {
                "name": Config.BIRO26_FIRM_NAME,
                "address": Config.BIRO26_FIRM_ADDRESS,
                "fiscal_code": Config.BIRO26_FIRM_FISCAL,
                "iban": Config.BIRO26_FIRM_IBAN,
                "bank": Config.BIRO26_FIRM_BANK,
                "branch": Config.BIRO26_FIRM_BRANCH,
                "phone": Config.BIRO26_FIRM_PHONE,
                "director": Config.BIRO26_FIRM_DIRECTOR,
            },
            "client": {
                "name": h["client_name"] or f"#{h['client_cod']}",
                "cod": h["client_cod"],
                "phone": (extra[0]["phone"] if extra else None),
                "email": (extra[0]["email"] if extra else None),
            },
            "items": items,
            "total": round(total, 2),
            # RO: TVA inclusa in pret / EN: VAT included in the price
            "tva": round(total * rate / (100 + rate), 2),
        }
        return {"success": True, "data": data, "client_cod": h["client_cod"]}

    @staticmethod
    def render(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """POST the template + data to jsReport; returns {'pdf': bytes}."""
        if kind not in REPORT_KINDS:
            return {"success": False, "error": f"unknown report kind: {kind}"}
        try:
            resp = requests.post(
                Config.JSREPORT_URL.rstrip("/") + "/api/report",
                json={
                    "template": {
                        "content": _read(REPORT_KINDS[kind]),
                        "engine": "handlebars",
                        "recipe": "chrome-pdf",
                        "helpers": _read("helpers.js"),
                        "chrome": {"format": "A4",
                                   "marginTop": "8mm", "marginBottom": "10mm",
                                   "marginLeft": "6mm", "marginRight": "6mm"},
                    },
                    "data": data,
                },
                timeout=90)
            if resp.status_code != 200:
                return {"success": False,
                        "error": f"jsreport HTTP {resp.status_code}: {resp.text[:300]}"}
            return {"success": True, "pdf": resp.content}
        except requests.ConnectionError:
            return {"success": False,
                    "error": "report service unavailable (jsreport not running)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def render_doc(kind: str, cod: int,
                   allowed_client_cod: Optional[int] = None) -> Dict[str, Any]:
        """Data + render in one call; when allowed_client_cod is given the
        document must belong to that client (public shop session guard)."""
        d = Biro26Report.doc_data(cod)
        if not d.get("success"):
            return d
        if allowed_client_cod is not None and int(d["client_cod"]) != int(allowed_client_cod):
            return {"success": False, "error": "document belongs to another client"}
        return Biro26Report.render(kind, d["data"])

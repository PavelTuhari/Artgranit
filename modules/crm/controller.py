"""Validarea si orchestrarea CRM-ului — intre rute si store.

RO: cele trei cai prin care intra un client, toate prin acelasi
`CrmStore.add_from_card`:
  1. XML-ul cardului (din `fetch` la Contragenti `/pick` sau `/card`, ori
     lipit/incarcat manual — echivalentul `ContragentiCRM.exe --import`);
  2. parametrii `return_to` (Contragenti redirecteaza browserul la noi);
  3. (viitor) alte surse.
EN: import paths for a counterparty card; all end in the same upsert.
"""
from __future__ import annotations

from typing import Any, Dict

from modules.crm import rules
from modules.crm.store import CrmStore


class CrmController:
    @staticmethod
    def import_xml(text: str, src: str = "xml", refresh: bool = False) -> Dict[str, Any]:
        try:
            card = rules.parse_card_xml(text)
        except ValueError as e:
            CrmStore.log("import_error", src, None, None, str(e))
            return {"success": False, "error": str(e)}
        if not rules.idno_valid(card["idno"]):
            # RO: nu refuzam — registrul e sursa; doar semnalam
            card["_idno_warning"] = "IDNO nu trece cifra de control"
        r = CrmStore.add_from_card(card, src=src, refresh=refresh)
        if r.get("success"):
            r["card"] = {k: card.get(k) for k in rules.CARD_FIELDS}
            if card.get("_idno_warning"):
                r["warning"] = card["_idno_warning"]
        return r

    @staticmethod
    def import_query(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            card = rules.card_from_query(args)
        except ValueError as e:
            return {"success": False, "error": str(e), "cancelled": True}
        return CrmStore.add_from_card(card, src="return_to")

    @staticmethod
    def pick_url(q: str, return_to: str = "", state: str = "") -> str:
        s = CrmStore.settings()
        try:
            timeout = int(s.get("pick_timeout") or 300)
        except ValueError:
            timeout = 300
        return rules.pick_url(s.get("contragenti_url"), q=q, lang=s.get("lang") or "ro",
                              return_to=return_to, state=state, timeout=timeout)

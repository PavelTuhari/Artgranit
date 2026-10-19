"""Validarea intrarilor puntii Contragenti (XML sau cimpuri) -> CtgStore.apply."""
from __future__ import annotations

from typing import Any, Dict

from modules.contragenti import rules
from modules.contragenti.store import CtgStore


class CtgController:
    @staticmethod
    def upsert(body: Dict[str, Any], *, username: str = "") -> Dict[str, Any]:
        page = (body.get("page") or "api")[:60]
        q = body.get("q") or ""
        try:
            card = rules.parse_card_xml(body["xml"]) if body.get("xml") else rules.card_from_fields(body)
        except (ValueError, KeyError) as e:
            CtgStore.log("card_invalid", "error", page=page, username=username, q=q, detail=str(e))
            return {"success": False, "error": str(e)}
        r = CtgStore.apply(card, page=page, username=username, q=q)
        if r.get("success"):
            r["card"] = {k: card.get(k) for k in ("idno", "denumire", "adresa", "inregistrare",
                                                  "forma_juridica", "lichidata", "administratori")}
            r["after"] = CtgStore.verify(r["univers_cod"])
        return r

    @staticmethod
    def client_event(body: Dict[str, Any], *, username: str = "") -> Dict[str, Any]:
        """RO: pasii din browser (health, pick_start, pick_cancel, pick_timeout, offline…)."""
        step = (body.get("step") or "").strip()[:40]
        if not step:
            return {"success": False, "error": "step lipsa"}
        CtgStore.log(step, (body.get("result") or "ok")[:20], page=(body.get("page") or "")[:60],
                     username=username, q=body.get("q") or "", idno=body.get("idno") or "",
                     detail=str(body.get("detail") or "")[:2000])
        return {"success": True}

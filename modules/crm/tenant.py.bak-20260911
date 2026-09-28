"""Chiriasul CRM-ului: OfficePlus (portal) sau un client din cabinet.

RO: cerinta din 08.09.2026 — CRM-ul e instrumentul OfficePlus SI e
disponibil fiecarui client OfficePlus din cabinetul lui. Fiecare rind
CRM_* poarta (OWNER_KIND, OWNER_ID); chiriasul se ia din sesiune:
  * utilizator al portalului (AuthController)  -> ('office', 0)
  * client autentificat in magazin (session['biro26_client']) -> ('client', id)
Nimeni nu vede rindurile altuia — conditia intra in fiecare SQL.
EN: tenant resolution from the portal / shop-client session.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from flask import session

from controllers.auth_controller import AuthController

OFFICE, CLIENT = "office", "client"


@dataclass(frozen=True)
class Tenant:
    kind: str
    id: int

    @property
    def is_office(self) -> bool:
        return self.kind == OFFICE

    def params(self, prefix: str = "") -> Dict[str, object]:
        return {prefix + "ok": self.kind, prefix + "oi": int(self.id)}

    def where(self, alias: str = "t", prefix: str = "") -> str:
        return "%s.OWNER_KIND = :%sok AND %s.OWNER_ID = :%soi" % (alias, prefix, alias, prefix)

    @property
    def label(self) -> str:
        return "OfficePlus" if self.is_office else "client #%d" % self.id


def current(prefer_client: bool = False) -> Optional[Tenant]:
    """RO: chiriasul sesiunii curente; None = nimeni autentificat.
    `prefer_client` — pagina cabinetului: un operator logat si ca client vede
    contul clientului."""
    cl = session.get("biro26_client") or {}
    cid = cl.get("id") if isinstance(cl, dict) else None
    if prefer_client and cid:
        return Tenant(CLIENT, int(cid))
    if AuthController.is_authenticated():
        return Tenant(OFFICE, 0)
    if cid:
        return Tenant(CLIENT, int(cid))
    return None

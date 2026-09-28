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

OFFICE, CLIENT, DEMO = "office", "client", "demo"

# RO: cheia din sesiune care tine regimul demonstrativ. Cerinta 10.09.2026:
#     in OfficePlus totul lucreaza pe datele reale din Oracle, iar setul
#     demonstrativ ramine separat — alt chirias, nu alt cod.
DEMO_KEY = "crm_demo"


@dataclass(frozen=True)
class Tenant:
    kind: str
    id: int

    @property
    def is_office(self) -> bool:
        return self.kind == OFFICE

    @property
    def is_demo(self) -> bool:
        return self.kind == DEMO

    @property
    def real(self) -> bool:
        """RO: datele reale din ERP se arata doar chiriasului OfficePlus."""
        return self.kind == OFFICE

    def params(self, prefix: str = "") -> Dict[str, object]:
        return {prefix + "ok": self.kind, prefix + "oi": int(self.id)}

    def where(self, alias: str = "t", prefix: str = "") -> str:
        return "%s.OWNER_KIND = :%sok AND %s.OWNER_ID = :%soi" % (alias, prefix, alias, prefix)

    @property
    def label(self) -> str:
        if self.is_office:
            return "OfficePlus"
        return "Demo" if self.is_demo else "client #%d" % self.id


def set_demo(on: bool) -> bool:
    """RO: comuta regimul demonstrativ pentru sesiunea curenta (doar portal)."""
    session[DEMO_KEY] = bool(on)
    session.modified = True
    return bool(on)


def current(prefer_client: bool = False) -> Optional[Tenant]:
    """RO: chiriasul sesiunii curente; None = nimeni autentificat.
    `prefer_client` — pagina cabinetului: un operator logat si ca client vede
    contul clientului."""
    cl = session.get("biro26_client") or {}
    cid = cl.get("id") if isinstance(cl, dict) else None
    if prefer_client and cid:
        return Tenant(CLIENT, int(cid))
    if AuthController.is_authenticated():
        return Tenant(DEMO, 0) if session.get(DEMO_KEY) else Tenant(OFFICE, 0)
    if cid:
        return Tenant(CLIENT, int(cid))
    return None

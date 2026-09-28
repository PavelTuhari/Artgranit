"""Partner API — B2B API pentru partenerii officeplus.md.

RO: functional 1-la-1 cu Ultra B2B API V1 (eshop.ultra.md/api-documentation):
autentificare cu token + refresh, catalog (product/category/brand/quantity),
modificari incrementale (/api/changes) si plasare de comenzi direct in ERP-ul
una.md (OfficePlus 11g). Acelasi contract de API, aceleasi denumiri de rute,
ca un integrator care lucreaza deja cu Ultra sa refoloseasca clientul sau.

Pachet izolat peste nucleu (core/module_loader.py): rutele traiesc sub
/UNA.md/orasldev/partner, iar adresele publice frumoase
(https://officeplus.md/api/v1/... si /api-documentation) le da nginx-ul
instantei — exact ca la vitrina (/cos, /catalog).

EN: partner-facing B2B API mirroring Ultra's dealer API contract, backed by
the una.md ERP; isolated module, pretty URLs via per-instance nginx.
"""
from flask import Blueprint

blueprint = Blueprint(
    "partner",
    __name__,
    template_folder="templates",
)

from modules.partner import routes  # noqa: E402,F401  (înregistrează rutele)

__all__ = ["blueprint"]

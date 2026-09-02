"""e-Factura — integrarea cu SIA „e-Factura” a Serviciului Fiscal de Stat.

RO: factura fiscala electronica pleaca din ERP-ul una.md in sistemul SFS prin
API-ul lor SOAP (ghidul oficial: efactura.sfs.md/Help). Modulul e disponibil
in TREI locuri, cu aceeasi logica in spate — exact ca forma tiparita a
contului:

  1. back-office (pagina modulului): setari, jurnal, buton «Trimite»;
  2. cabinetul clientului de pe site (langa PDF-ul contului);
  3. API intern (X-API-Key), pentru back-office-urile native/alternative.

Pachet izolat peste nucleu: rutele stau sub /UNA.md/orasldev/efactura,
conturul Oracle propriu are prefixul EFA_, iar codul comun nu e atins.

EN: e-invoice integration with Moldova's SFS „e-Factura” SOAP API, reachable
from the back office, the client cabinet and an internal machine API.
"""
from flask import Blueprint

blueprint = Blueprint(
    "efactura",
    __name__,
    template_folder="templates",
)

from modules.efactura import routes  # noqa: E402,F401  (înregistrează rutele)
# RO: API-ul pe HTTP simplu pentru back-office-ul nativ una.md — la radacina
#     (/api/biro26/efactura/…), montat de nucleu prin root_paths din manifest.
from modules.efactura.native_api import root_blueprint  # noqa: E402,F401

__all__ = ["blueprint", "root_blueprint"]

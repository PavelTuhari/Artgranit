"""RO: Pauza site-ului — «se efectuează lucrări tehnice, reveniți mai tîrziu».

Parametrul `SITE_PAUSE` din YBIRO_SETTINGS ('1' = pauză, '0' = site normal) oprește
magazinul public DOAR pe punctul de intrare officeplus.* (Config.BIRO26_SHOP_HOSTS).
nufarul.eminescu.md lucrează cu aceeași bază, dar are alt domeniu — nu e atins.
Pe pauză: vitrina (/, /catalog, /produs/…, /cos …) și API-ul magazinului răspund 503
cu pagina de lucrări tehnice; rămîn deschise logarea, bactoficeul /UNA.md/orasldev/…,
API-ul partenerilor și fișierele statice — de acolo se și ridică pauza.
Utilizatorii logați văd magazinul ca de obicei (ca să-l poată verifica înainte de redeschidere).

Comutatorul: /UNA.md/orasldev/sitepause/ (după logare).
Documentatie: docs/Biro26/PAUZA_SITE_2026-10-17.md
"""
from flask import Blueprint

blueprint = Blueprint("sitepause", __name__, template_folder="templates")

from modules.sitepause import routes  # noqa: E402,F401  (inregistreaza rutele si hook-ul)

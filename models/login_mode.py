"""RO: modul paginii de logare — general (Artgranit OCI) sau EXCLUSIV OfficePlus.

Exclusiv cind:
  * instalarea e dedicata (Config.LOGIN_EXCLUSIVE == 'biro26'), sau
  * cererea vine prin officeplus.una.md: nginx-ul de pe 192.168.0.148 trimite spre
    nufarul antetul X-Login-Exclusive: biro26 (27.10.2026, proprietarul: «pe
    officeplus.una.md nu trebuie pagina Artgranit OCI — doar pe nufarul»).
Pe intrarea prin antet NU se precompleteaza utilizatorul si parola implicite.
Antetul falsificat nu da acces la nimic: arata doar o forma de logare mai saraca.
Documentatie: docs/Biro26/OFFICEPLUS_UNA_PE_NUFARUL_2026-10-27.md
"""
HEADER = "X-Login-Exclusive"


def login_mode(headers, login_exclusive_setting: str):
    """-> (exclusive, prefill_defaults)

    RO: 27.10.2026 — utilizatorul si parola NU se mai precompleteaza nicaieri: pagina
    /login a nufarul arata public ADMIN si parola din .env oricui o deschidea.
    Parola a fost schimbata pe toate trei serverele in aceeasi zi.
    """
    by_header = (headers.get(HEADER) or "").strip().lower() == "biro26"
    exclusive = by_header or (login_exclusive_setting or "") == "biro26"
    return exclusive, False

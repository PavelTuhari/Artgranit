"""Contragenti — puntea dintre utilitarul date.gov.md si nomenclatorul una.md.

RO: un singur loc pentru TOATE paginile care primesc un card de contraparte
de la utilitarul local Contragenti (biro26-clients, CRM…): cardul se
descompune in TMS_UNIVERS (CODVECHI = IDNO, GR1='E'), TMS_ORG (CODFISCAL,
adresa, director) si fisa clientului de site (YBIRO_CLIENT.IDNO), cu
DEDUPLICARE: intii dupa IDNO, apoi dupa denumire — o firma deja inregistrata
fara cod fiscal (ex. COD 518172) se REPARA, nu se dubleaza. Fiecare pas al
lantului (verificare utilitar, cautare, card primit, potrivire, scriere,
eroare) se scrie in CTG_EVENT_LOG, ca algoritmul sa poata fi analizat si
corectat pe date reale (cerinta proprietarului, 07.09.2026).

Pachet izolat peste nucleu: rute sub /UNA.md/orasldev/contragenti, prefixul
Oracle CTG_, nimic in codul comun.
EN: Contragenti -> una.md bridge: card upsert with IDNO/name dedup + full
chain event log.
"""
from flask import Blueprint

blueprint = Blueprint("contragenti", __name__, template_folder="templates")

from modules.contragenti import routes  # noqa: E402,F401

__all__ = ["blueprint"]

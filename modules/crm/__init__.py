"""CRM (beta) — modul izolat Artgranit, integrat cu Contragenti.

RO: replica web a «Demo CRM» din repo-ul PavelTuhari/Contragenti
(crm_delphi/, stil EspoCRM): baza proprie de clienti, butonul «Creeaza
client» deschide Contragenti (cautarea in registrul de stat date.gov.md)
si primeste inapoi cardul XML al contrapartii, care se descompune in
tabelele CRM_* din Oracle cu deduplicare dupa IDNO.

Pachet izolat peste nucleu: rutele sub /UNA.md/orasldev/crm, conturul
Oracle propriu cu prefixul CRM_, nimic in codul comun.
EN: web CRM (beta) mirroring the Contragenti Demo CRM; counterparties come
from the Contragenti desktop tool over its local HTTP API.
"""
from flask import Blueprint

blueprint = Blueprint("crm", __name__, template_folder="templates")

from modules.crm import routes  # noqa: E402,F401  (inregistreaza rutele)

__all__ = ["blueprint"]

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

blueprint = Blueprint("crm", __name__, template_folder="templates",
                      static_folder="static", static_url_path="/static")

# RO: routes = clientii din Contragenti (beta, 05.09.2026); routes_process =
#     procesul «de la contract la bani» dupa prototip + cabinetul clientului;
#     routes_alerts = alertele Telegram (tranzactii nefinisate si datorii,
#     08.09.2026); routes_employees = conturile angajatilor peste arborele
#     ERP (10.09.2026). Fisiere separate (CLAUDE.md, regula nr. 2).
from modules.crm import (routes, routes_process, routes_alerts,  # noqa: E402,F401
                         routes_employees, routes_erp)         # (inregistreaza rutele)

__all__ = ["blueprint"]

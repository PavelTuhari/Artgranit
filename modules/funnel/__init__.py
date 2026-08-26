"""Воронка продаж — контрольная панель и автономная рассылка сводок.

RO: Palnia de vinzari a magazinului: cite comenzi s-au creat, cite s-au
    livrat, care e conversia si cecul mediu — plus un rezumat trimis
    regulat administratiei si marketingului, fara interventia nimanui.
EN: The shop's sales funnel: orders created, orders delivered, conversion
    and the average check — plus a digest sent to the administration and
    the marketing team on a schedule, with no human in the loop.

Самодостаточный пакет на ядре портала: в общем коде не оставляет ничего.
"""
from flask import Blueprint

blueprint = Blueprint(
    "funnel",
    __name__,
    template_folder="templates",
)

from modules.funnel import routes  # noqa: E402,F401  (регистрирует маршруты)

# RO: expedierea autonoma porneste odata cu modulul / EN: the autonomous
#     sender starts with the module.
from modules.funnel import digest  # noqa: E402
digest.start_scheduler()

__all__ = ["blueprint"]

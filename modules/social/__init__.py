"""Автопостинг магазина на бесплатные площадки с API.

RO: Modulul publica singur, dupa un orar, continut REAL despre magazin:
    sectiuni cu numarul de pozitii si preturi, bestselleruri din comenzi.
    Canalele sint cele gratuite cu API: Telegram, Facebook, Instagram, VK,
    OK, Google Business Profile.
EN: The module publishes real shop content on a schedule to the free
    API-driven networks.

Самодостаточный пакет на ядре портала: в общем коде не оставляет ничего.
"""
from flask import Blueprint

blueprint = Blueprint("social", __name__, template_folder="templates")

from modules.social import routes  # noqa: E402,F401  (регистрирует маршруты)

from modules.social import scheduler  # noqa: E402
scheduler.start()

__all__ = ["blueprint"]

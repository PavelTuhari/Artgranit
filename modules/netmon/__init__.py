"""Мониторинг офиса: сеть и Telegram — изолированный модуль Artgranit.

Весь код модуля лежит здесь, в modules/netmon/. В общем коде портала модуль
не оставляет ничего: ядро (core/module_loader.py) находит пакет само и
подключает под /UNA.md/orasldev/netmon. Ядру нужен ровно один объект —
`blueprint`; маршруты объявлены в routes.py и импортируются ниже.
"""
from flask import Blueprint

blueprint = Blueprint("netmon", __name__, template_folder="templates")

from modules.netmon import routes  # noqa: E402,F401  (регистрирует маршруты)

__all__ = ["blueprint"]

"""SEOForge — модуль AI-SEO продвижения.

Самодостаточный пакет: контроллер, хранилище, разбор CSV, шаблон, DDL
контура и служебные скрипты лежат здесь же. В общем коде портала модуль
не оставляет ничего — ядро (`core/module_loader.py`) находит его само,
проверяет и подключает под `/UNA.md/orasldev/seoforge`.

Ядру нужен ровно один объект — `blueprint`. Маршруты объявлены в
`routes.py` и импортируются ниже: без этого импорта blueprint остался бы
пустым.
"""
from flask import Blueprint

blueprint = Blueprint(
    "seoforge",
    __name__,
    template_folder="templates",
)

from modules.seoforge import routes  # noqa: E402,F401  (регистрирует маршруты)

__all__ = ["blueprint"]

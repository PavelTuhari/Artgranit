"""SDA — модуль залоговой системы упаковки (Sistemul de Depozit pentru Ambalaje).

Самодостаточный пакет: правила расчёта режима, хранилище, шаблоны, DDL
контура и служебные скрипты лежат здесь же. В общем коде портала модуль
не оставляет ничего — ядро (`core/module_loader.py`) находит его само,
проверяет и подключает под `/UNA.md/orasldev/sda`.

Ядру нужен ровно один объект — `blueprint`. Маршруты объявлены в
`routes.py` и импортируются ниже: без этого импорта blueprint остался бы
пустым.
"""
from flask import Blueprint

blueprint = Blueprint(
    "sda",
    __name__,
    template_folder="templates",
)

from modules.sda import routes  # noqa: E402,F401  (регистрирует маршруты)

__all__ = ["blueprint"]

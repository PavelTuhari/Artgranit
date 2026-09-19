"""Autopark — модуль автоматизации автопарка бензовозов (Bemol).

Расчёт заработной платы водителей по нормативному пробегу, контроль
маршрутов и расхода дизельного топлива, планирование поставок на АЗС —
см. ТЗ клиента (docs/Autopark).

Самодостаточный пакет: правила расчёта, хранилище, шаблоны, DDL контура и
служебные скрипты лежат здесь же. В общем коде портала модуль не оставляет
ничего — ядро (`core/module_loader.py`) находит его само, проверяет и
подключает под `/UNA.md/orasldev/autopark`.

Ядру нужен ровно один объект — `blueprint`. Маршруты объявлены в
`routes.py` и импортируются ниже: без этого импорта blueprint остался бы
пустым.
"""
from flask import Blueprint

blueprint = Blueprint(
    "autopark",
    __name__,
    template_folder="templates",
    # Свои статические файлы модуль везёт с собой: скриншоты руководства
    # пользователя лежат в static/docs/ и отдаются по адресу модуля.
    # Общий каталог static/ -- чужая территория (правило №1 проекта).
    static_folder="static",
    static_url_path="/static",
)

from modules.autopark import routes  # noqa: E402,F401  (регистрирует маршруты)
from modules.autopark import supply_routes  # noqa: E402,F401  (контур распределения топлива)
from modules.autopark import docs_routes  # noqa: E402,F401  (хаб документации модуля)

__all__ = ["blueprint"]

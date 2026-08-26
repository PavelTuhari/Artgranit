"""Маршруты модуля Autopark.

Адреса здесь записаны БЕЗ префикса `/UNA.md/orasldev/autopark` — его
подставляет ядро при регистрации blueprint'а.

Эта задача (backend, часть 1 из 3) поднимает только заглушку, чтобы ядро
могло подключить модуль и он появился в меню портала. UI, API и панель
логиста придут следующей задачей.
"""
from modules.autopark import blueprint


@blueprint.route("")
@blueprint.route("/")
def index():
    return "Autopark: интерфейс в разработке"

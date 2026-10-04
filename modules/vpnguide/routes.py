"""Маршруты модуля «Инструкция OpenVPN».

Адреса без префикса /UNA.md/orasldev/vpnguide — его подставляет ядро.
Страница одна и статичная: данных и API у модуля нет.
"""
from flask import redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.vpnguide import blueprint

# Платформы в порядке показа: ключ вкладки, подпись.
PLATFORMS = [
    ("windows", "Windows"),
    ("macos", "macOS"),
    ("iphone", "iPhone / iPad"),
    ("android", "Android"),
    ("linux", "Linux"),
]


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login", next=request.full_path))
    return render_template("vpnguide.html", platforms=PLATFORMS)

"""Модуль «Инструкция OpenVPN»: изоляция и безопасность содержимого."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# --------------------------------------------------------------- изоляция

def test_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; общий app.py о нём ничего не знает.
    assert "vpnguide" not in _read("app.py").lower()


def test_shared_deploy_script_is_untouched_by_the_module():
    assert "vpnguide" not in _read("deploy_oracle_objects.py").lower()


def test_blueprint_name_equals_module_key():
    src = _read("modules/vpnguide/__init__.py")
    assert 'Blueprint("vpnguide"' in src


# ------------------------------------------------- содержимое страницы

def test_guide_contains_no_network_addresses_or_keys():
    """Страница работает на публичном сервере — в ней не должно быть ничего,
    что помогает войти в сеть без файла профиля."""
    html = _read("modules/vpnguide/templates/vpnguide.html")
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", html), "в инструкции IP-адрес"
    assert not re.search(r":(1194|4024|8006|22)\b", html), "в инструкции порт сервера"
    for marker in ("BEGIN PRIVATE KEY", "BEGIN CERTIFICATE", "tls-crypt", "<key>",
                   "una.md", "uniacc", "192.168"):
        assert marker not in html, f"в инструкции лишнее: {marker}"


def test_guide_links_only_to_official_sources():
    html = _read("modules/vpnguide/templates/vpnguide.html")
    hosts = set(re.findall(r'href="https?://([^/"]+)', html))
    assert hosts <= {"openvpn.net", "apps.apple.com", "play.google.com"}, hosts


def test_every_platform_has_a_tab_and_a_pane():
    from modules.vpnguide.routes import PLATFORMS
    html = _read("modules/vpnguide/templates/vpnguide.html")
    for key, _ in PLATFORMS:
        assert f'id="p-{key}"' in html, f"нет раздела для {key}"


def test_page_requires_login():
    assert "is_authenticated()" in _read("modules/vpnguide/routes.py")


def test_netmon_panel_links_to_the_guide():
    html = _read("modules/netmon/templates/netmon.html")
    assert "url_for('vpnguide.index')" in html

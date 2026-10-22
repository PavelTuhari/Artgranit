"""RO: pauza site-ului officeplus.md (modules/sitepause) — reguli + izolare.
Documentatie: docs/Biro26/PAUZA_SITE_2026-10-17.md
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_DIR = os.path.join(ROOT, "modules", "sitepause")
HOSTS = ["officeplus.md", "officeplus.una.md"]


def test_only_shop_hosts_are_paused_never_nufarul():
    from modules.sitepause import rules
    assert rules.is_shop_host("officeplus.md", HOSTS)
    assert rules.is_shop_host("www.officeplus.md", HOSTS)
    assert rules.is_shop_host("officeplus.una.md:443", HOSTS)
    assert not rules.is_shop_host("nufarul.eminescu.md", HOSTS)
    assert not rules.is_shop_host("127.0.0.1:8000", HOSTS)


def test_storefront_paused_backoffice_and_login_open():
    from modules.sitepause import rules
    for p in ("/", "/catalog", "/produs/162325", "/cos", "/api/biro26/shop/products",
              "/UNA.md/orasldev/biro26-site", "/UNA.md/orasldev/biro26-site/catalog",
              "/UNA.md/orasldev/biro26-shop", "/livrare"):
        assert rules.path_is_paused(p), p
    for p in ("/login", "/logout", "/static/biro26/site.js", "/favicon.ico", "/robots.txt",
              "/UNA.md/orasldev/biro26-backoffice", "/UNA.md/orasldev/sitepause/",
              "/UNA.md/orasldev/sitepause/toggle", "/api/v1/product", "/api-documentation"):
        assert not rules.path_is_paused(p), p


def test_flag_values():
    from modules.sitepause import rules
    assert rules.flag_on("1") and rules.flag_on(" ON ") and rules.flag_on("da")
    assert not rules.flag_on("0") and not rules.flag_on("") and not rules.flag_on(None)


def test_pause_page_is_bilingual_with_contacts():
    html = open(os.path.join(MODULE_DIR, "templates", "sitepause", "pause.html"), encoding="utf-8").read()
    assert "Se efectuează lucrări tehnice" in html and "Ведутся технические работы" in html
    assert "reveniți mai tîrziu" in html.lower() and "зайдите позже" in html.lower()
    assert 'href="tel:+37362007211"' in html and 'name="robots" content="noindex"' in html


def test_hook_answers_503_and_fails_open():
    src = open(os.path.join(MODULE_DIR, "routes.py"), encoding="utf-8").read()
    assert "@blueprint.before_app_request" in src
    assert "503" in src and '"Retry-After"' in src
    assert "AuthController.is_authenticated()" in src
    # orice exceptie in pauza -> site-ul merge (nu il opreste o eroare a pauzei)
    assert "except Exception:" in src and "return None                            # nicio eroare" in src


def test_setting_lives_in_ybiro_settings_and_is_cached():
    src = open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8").read()
    assert 'KEY = "SITE_PAUSE"' in src and "get_settings_many" in src and "set_setting" in src
    assert "REFRESH_S = 20" in src and "threading.Thread" in src


def test_manifest():
    m = json.load(open(os.path.join(MODULE_DIR, "module.json"), encoding="utf-8"))
    assert set(m["title"]) >= {"ru", "ro", "en"} and m["url"] == "/UNA.md/orasldev/sitepause/"


def test_module_leaves_nothing_in_the_shared_app():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "sitepause" not in src.lower()
    assert "SITE_PAUSE" not in src


def test_shared_deploy_script_is_untouched_by_the_module():
    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "sitepause" not in src.lower()


def test_module_is_picked_up_by_the_core():
    from core.module_loader import module_keys
    assert "sitepause" in module_keys()
    from modules.sitepause import blueprint
    assert blueprint.name == "sitepause"


def test_hook_end_to_end_with_test_client(monkeypatch):
    from flask import Flask
    from modules.sitepause import blueprint, store
    from modules.sitepause import routes as r
    flag = {"on": True}
    monkeypatch.setattr(store, "state", lambda: {"on": flag["on"], "ro": "", "ru": ""})
    monkeypatch.setattr(r.AuthController, "is_authenticated", staticmethod(lambda: False))
    monkeypatch.setattr(r.Config, "BIRO26_SHOP_HOSTS", HOSTS, raising=False)
    app = Flask(__name__)
    app.register_blueprint(blueprint, url_prefix="/UNA.md/orasldev/sitepause")

    @app.route("/UNA.md/orasldev/biro26-site")
    def shop():
        return "SHOP"

    @app.route("/login")
    def login():
        return "LOGIN"

    c = app.test_client()
    resp = c.get("/UNA.md/orasldev/biro26-site", headers={"Host": "officeplus.md"})
    assert resp.status_code == 503 and "lucrări tehnice" in resp.get_data(as_text=True)
    assert resp.headers["Retry-After"] == "3600"
    assert c.get("/UNA.md/orasldev/biro26-site", headers={"Host": "nufarul.eminescu.md"}).get_data(as_text=True) == "SHOP"
    assert c.get("/login", headers={"Host": "officeplus.md"}).get_data(as_text=True) == "LOGIN"
    assert c.get("/api/biro26/shop/x", headers={"Host": "officeplus.md"}).get_json()["maintenance"] is True
    flag["on"] = False
    assert c.get("/UNA.md/orasldev/biro26-site", headers={"Host": "officeplus.md"}).get_data(as_text=True) == "SHOP"
    flag["on"] = True
    monkeypatch.setattr(r.AuthController, "is_authenticated", staticmethod(lambda: True))
    assert c.get("/UNA.md/orasldev/biro26-site", headers={"Host": "officeplus.md"}).get_data(as_text=True) == "SHOP"


def test_wp_gate_answers_204_open_and_403_paused(monkeypatch):
    from flask import Flask
    from modules.sitepause import blueprint, store
    flag = {"on": False}
    monkeypatch.setattr(store, "state", lambda: {"on": flag["on"], "ro": "", "ru": ""})
    app = Flask(__name__)
    app.register_blueprint(blueprint, url_prefix="/UNA.md/orasldev/sitepause")
    c = app.test_client()
    assert c.get("/UNA.md/orasldev/sitepause/gate").status_code == 204
    flag["on"] = True
    assert c.get("/UNA.md/orasldev/sitepause/gate").status_code == 403
    r = c.get("/UNA.md/orasldev/sitepause/page")
    assert r.status_code == 503 and "lucrări tehnice" in r.get_data(as_text=True)
    assert r.headers["Retry-After"] == "3600"


def test_wp_gate_fails_open_on_error(monkeypatch):
    from flask import Flask
    from modules.sitepause import blueprint, store

    def boom():
        raise RuntimeError("baza cazuta")
    monkeypatch.setattr(store, "state", boom)
    app = Flask(__name__)
    app.register_blueprint(blueprint, url_prefix="/UNA.md/orasldev/sitepause")
    assert app.test_client().get("/UNA.md/orasldev/sitepause/gate").status_code == 204


def test_nginx_include_targets_the_gate():
    inc = open(os.path.join(ROOT, "deploy", "officeplus", "wp-pause.inc"), encoding="utf-8").read()
    assert "location = /_op_wp_pause" in inc and "internal;" in inc
    assert "/UNA.md/orasldev/sitepause/gate" in inc and "/UNA.md/orasldev/sitepause/page" in inc

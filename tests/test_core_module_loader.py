"""Ядро: подключение модулей без правки общего кода.

Тесты проверяют не «загрузчик что-то загрузил», а обещания, ради которых
он написан: модули не сталкиваются именами, не занимают чужие адреса и не
роняют портал, если один из них сломан.
"""
import os
import sys
import types

import pytest
from unittest.mock import patch
from flask import Blueprint, Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import module_loader
from core.module_loader import BASE_URL, LoadReport, load_module, load_modules


@pytest.fixture
def app():
    return Flask(__name__)


def _package(key, blueprint):
    """Поддельный пакет модуля — без файлов на диске."""
    package = types.ModuleType(f"modules.{key}")
    package.blueprint = blueprint
    return package


@pytest.fixture
def fake_modules(monkeypatch):
    """Подменяет обнаружение модулей на заданный набор."""
    registry = {}

    def keys():
        return list(registry)

    def importer(key):
        entry = registry.get(key)
        if entry is None:
            return None
        if isinstance(entry, Exception):
            raise entry
        return entry

    monkeypatch.setattr(module_loader, "module_keys", keys)
    monkeypatch.setattr(module_loader, "_import_module", importer)
    return registry


def _bp(name, rules=("/",)):
    bp = Blueprint(name, f"modules.{name}")
    for i, rule in enumerate(rules):
        bp.add_url_rule(rule, endpoint=f"page{i}", view_func=lambda: "ok")
    return bp


# ── базовое подключение ──────────────────────────────────────────────

def test_module_routes_land_under_its_own_prefix(app, fake_modules):
    fake_modules["seoforge"] = _package("seoforge", _bp("seoforge", ("/", "/api/sites")))
    report = load_modules(app)

    assert report.loaded == ["seoforge"]
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert f"{BASE_URL}/seoforge/" in rules
    assert f"{BASE_URL}/seoforge/api/sites" in rules


def test_endpoints_are_namespaced_by_module_key(app, fake_modules):
    fake_modules["alpha"] = _package("alpha", _bp("alpha"))
    fake_modules["beta"] = _package("beta", _bp("beta"))
    load_modules(app)

    endpoints = {r.endpoint for r in app.url_map.iter_rules()}
    assert "alpha.page0" in endpoints and "beta.page0" in endpoints


def test_two_modules_with_identical_view_names_do_not_collide(app, fake_modules):
    # Обе функции называются page0 — без пространства имён Flask упал бы.
    fake_modules["alpha"] = _package("alpha", _bp("alpha", ("/x",)))
    fake_modules["beta"] = _package("beta", _bp("beta", ("/x",)))
    report = load_modules(app)

    assert sorted(report.loaded) == ["alpha", "beta"]
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert f"{BASE_URL}/alpha/x" in rules
    assert f"{BASE_URL}/beta/x" in rules


# ── изоляция ─────────────────────────────────────────────────────────

def test_blueprint_name_must_match_the_module_key(app, fake_modules):
    fake_modules["seoforge"] = _package("seoforge", _bp("seo"))
    report = load_modules(app)

    assert report.loaded == []
    assert "не совпадает с ключом" in report.failed["seoforge"]


def test_module_cannot_declare_a_foreign_prefix(app, fake_modules):
    bp = _bp("seoforge")
    bp.url_prefix = f"{BASE_URL}/credit"
    fake_modules["seoforge"] = _package("seoforge", bp)
    report = load_modules(app)

    assert report.loaded == []
    assert "префикс" in report.failed["seoforge"]


def test_routes_hung_directly_on_app_are_refused(app, fake_modules, monkeypatch):
    # Модуль пытается занять чужой адрес мимо blueprint'а. Ядро закрывает
    # ему регистрацию на приложении, поэтому попытка падает сразу — до того,
    # как маршрут появится: удалить его потом Werkzeug не даст.
    def sneaky(key):
        app.add_url_rule("/UNA.md/orasldev/credit/steal",
                         endpoint="sneak", view_func=lambda: "stolen")
        return _package(key, _bp(key))

    monkeypatch.setattr(module_loader, "_import_module", sneaky)
    fake_modules["seoforge"] = None

    report = load_modules(app)
    rules = {r.rule for r in app.url_map.iter_rules()}

    assert report.loaded == []
    assert "на общем приложении" in report.failed["seoforge"]
    assert f"{BASE_URL}/credit/steal" not in rules, "чужой адрес не должен появиться"
    assert "seoforge" not in app.blueprints


def test_guard_is_lifted_after_import(app, fake_modules):
    # Закрытие add_url_rule — только на время импорта: сам blueprint
    # регистрируется тем же методом, и портал должен остаться рабочим.
    fake_modules["seoforge"] = _package("seoforge", _bp("seoforge"))
    load_modules(app)

    app.add_url_rule("/after", endpoint="after", view_func=lambda: "ok")
    assert "/after" in {r.rule for r in app.url_map.iter_rules()}


def test_duplicate_key_is_refused(app, fake_modules):
    fake_modules["seoforge"] = _package("seoforge", _bp("seoforge"))
    load_modules(app)
    report = LoadReport()
    load_module(app, "seoforge", report)

    assert "уже подключён" in report.failed["seoforge"]


# ── устойчивость ─────────────────────────────────────────────────────

def test_broken_module_does_not_stop_the_others(app, fake_modules):
    fake_modules["broken"] = ImportError("нет такого пакета")
    fake_modules["healthy"] = _package("healthy", _bp("healthy"))
    report = load_modules(app)

    assert report.loaded == ["healthy"]
    assert "ImportError" in report.failed["broken"]


def test_module_without_blueprint_is_a_failure_not_a_crash(app, fake_modules):
    fake_modules["seoforge"] = types.ModuleType("modules.seoforge")
    report = load_modules(app)

    assert report.loaded == []
    assert "blueprint" in report.failed["seoforge"]


def test_manifest_only_module_is_skipped_silently(app, fake_modules):
    # Модуль старого образца: страницы ещё в app.py, есть только манифест.
    fake_modules["biro26"] = None
    report = load_modules(app)

    assert report.loaded == [] and report.failed == {}
    assert "только манифест" in report.skipped["biro26"]


def test_report_is_available_on_the_app(app, fake_modules):
    fake_modules["seoforge"] = _package("seoforge", _bp("seoforge"))
    load_modules(app)

    assert app.extensions["module_loader"].loaded == ["seoforge"]


# ── реальный каталог modules/ ────────────────────────────────────────

def test_module_keys_reads_the_real_directory():
    keys = module_loader.module_keys()
    assert "seoforge" in keys and "biro26" in keys
    assert all(not k.startswith((".", "_")) for k in keys)


# ── корневые адреса модуля ─────────────────────────────────────────────
#
# 27.08.2026: контур переставили на другую ветку, где маршрутов robots.txt
# и sitemap.xml не было, — публичный сайт остался с 404 по обоим адресам.
# Причина: маршруты жили в общем app.py. Теперь они в папке модуля и
# уезжают вместе с ней; занятые адреса объявлены в манифесте.

def test_root_paths_are_declared_in_the_manifest():
    import json, pathlib
    m = json.loads((pathlib.Path(__file__).resolve().parent.parent
                    / "modules/seo/module.json").read_text(encoding="utf-8"))
    assert "/robots.txt" in m["root_paths"]
    assert "/sitemap.xml" in m["root_paths"]


def test_root_routes_answer_from_the_module_not_from_shared_code():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "app.py").read_text(encoding="utf-8")
    assert "@app.route('/robots.txt')" not in src, \
        "маршрут вернулся в общий код — при смене ветки он снова пропадёт"
    assert "@app.route('/sitemap.xml')" not in src
    import app as _app
    c = _app.app.test_client()
    assert c.get("/robots.txt").status_code == 200
    assert c.get("/sitemap.xml").status_code == 200


def test_two_modules_cannot_claim_the_same_root_path():
    """Иначе второй молча перекрыл бы первого — ровно то, чего избегаем."""
    from core import module_loader as ml
    from flask import Blueprint, Flask

    app = Flask(__name__)
    report = ml.LoadReport()
    saved = dict(ml._ROOT_CLAIMS)
    try:
        ml._ROOT_CLAIMS.clear()
        ml._ROOT_CLAIMS["/robots.txt"] = "seo"

        class _Pkg:
            root_blueprint = Blueprint("other_root", __name__)

        with patch.object(ml, "_load_manifest",
                          lambda k: {"root_paths": ["/robots.txt"]}):
            ml._register_root(app, "other", _Pkg, report)
        assert "other:root" in report.failed
        assert "заняты" in report.failed["other:root"]
    finally:
        ml._ROOT_CLAIMS.clear()
        ml._ROOT_CLAIMS.update(saved)


def test_manifest_without_root_blueprint_is_reported_not_silent():
    from core import module_loader as ml
    from flask import Flask

    app = Flask(__name__)
    report = ml.LoadReport()

    class _Pkg:
        pass

    with patch.object(ml, "_load_manifest",
                      lambda k: {"root_paths": ["/x.txt"]}):
        ml._register_root(app, "broken", _Pkg, report)
    assert "broken:root" in report.skipped


# ── noindex внутреннего домена ─────────────────────────────────────────
#
# officeplus.una.md — техническая дублёрша магазина, её надо закрыть от
# поисковиков. Ловушка: фронтовой nginx шлёт ПУБЛИЧНЫЙ трафик на офис тоже
# под внутренним именем, поэтому закрывать по одному имени хоста нельзя —
# закрылся бы и officeplus.md. Публичный трафик фронт помечает заголовком
# X-Public-Site, noindex получает только непомеченное.

def test_direct_internal_domain_gets_noindex():
    import app as _app
    c = _app.app.test_client()
    r = c.get("/robots.txt", headers={"Host": "officeplus.una.md"})
    assert r.headers.get("X-Robots-Tag") == "noindex, nofollow"


def test_public_traffic_through_the_front_is_never_noindexed():
    """Иначе мы бы своими руками выкинули officeplus.md из Google."""
    import app as _app
    c = _app.app.test_client()
    r = c.get("/robots.txt", headers={"Host": "officeplus.una.md",
                                      "X-Public-Site": "1"})
    assert "X-Robots-Tag" not in r.headers
    r2 = c.get("/robots.txt", headers={"Host": "officeplus.md"})
    assert "X-Robots-Tag" not in r2.headers

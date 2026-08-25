"""Ядро: подключение модулей без правки общего кода.

Тесты проверяют не «загрузчик что-то загрузил», а обещания, ради которых
он написан: модули не сталкиваются именами, не занимают чужие адреса и не
роняют портал, если один из них сломан.
"""
import os
import sys
import types

import pytest
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

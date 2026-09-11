"""Тесты модуля netmon. Два первых — обязательные тесты изоляции (CLAUDE.md, правило №1)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_shared_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; в app.py ему делать нечего.
    src = _read("app.py")
    assert not re.search(r"\bnetmon\b", src), "app.py упоминает модуль — нарушена изоляция"


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "NMON_" not in src and "netmon" not in src.lower(), \
        "общий установщик знает о модуле — у модуля должен быть свой scripts/netmon_deploy.py"


def test_module_exports_blueprint_named_after_key():
    from modules.netmon import blueprint
    assert blueprint.name == "netmon"


def test_rules_are_pure():
    from modules.netmon import rules
    assert rules.normalize_code("  ab c ") == "AB C"

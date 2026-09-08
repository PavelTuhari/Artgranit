"""Тесты модуля furnizori. Два первых — обязательные тесты изоляции (CLAUDE.md, правило №1)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_shared_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; в app.py ему делать нечего.
    src = _read("app.py")
    assert not re.search(r"\bfurnizori\b", src), "app.py упоминает модуль — нарушена изоляция"


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "FRZ_" not in src and "furnizori" not in src.lower(), \
        "общий установщик знает о модуле — у модуля должен быть свой scripts/furnizori_deploy.py"


def test_module_exports_blueprint_named_after_key():
    from modules.furnizori import blueprint
    assert blueprint.name == "furnizori"


def test_rules_are_pure():
    from modules.furnizori import rules
    assert rules.normalize_code("  ab c ") == "AB C"

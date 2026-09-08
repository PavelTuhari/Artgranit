"""Тесты модуля furnizori. Два первых — обязательные тесты изоляции (CLAUDE.md, правило №1)."""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_shared_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; в app.py ему делать нечего.
    #
    # Ищем именно ПОДКЛЮЧЕНИЕ модуля, а не слово «furnizori»: по-румынски это
    # «поставщики», и оно давно встречается в чужом эндпоинте biro26
    # (/api/biro26/suppliers/furnizori). Голый \bfurnizori\b падал бы на чужом
    # коде, ничего не говоря про нашу изоляцию.
    src = _read("app.py")
    for bad in ("modules.furnizori", "modules/furnizori", "furnizori.routes",
                "FurnizoriController", "FRZ_"):
        assert bad not in src, f"app.py подключает модуль ({bad}) — нарушена изоляция"


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "FRZ_" not in src and "furnizori" not in src.lower(), \
        "общий установщик знает о модуле — у модуля должен быть свой scripts/furnizori_deploy.py"


def test_module_exports_blueprint_named_after_key():
    from modules.furnizori import blueprint
    assert blueprint.name == "furnizori"


# ---------------------------------------------------------------- правила

def test_rules_are_pure():
    from modules.furnizori import rules
    assert rules.normalize_code("  ab c ") == "AB C"


def test_only_known_statuses_and_types_pass():
    from modules.furnizori import rules
    assert rules.valid_status("trimis") and not rules.valid_status("ОТПРАВЛЕНО")
    assert rules.valid_tip("preturi") and not rules.valid_tip("SPAM")


@pytest.mark.parametrize("name,size,ok", [
    ("Scrisoare_ATEHNO.eml", 44839, True),
    ("Denumiri.xlsx", 13806, True),
    ("payload.html", 100, False),      # исполняемое в браузере не принимаем
    ("script.svg", 100, False),
    ("empty.eml", 0, False),
    ("huge.zip", 40 * 1024 * 1024, False),
])
def test_upload_is_filtered(name, size, ok):
    from modules.furnizori import rules
    assert (rules.check_upload(name, size) is None) is ok


def test_download_filename_cannot_forge_a_header():
    from modules.furnizori import rules
    # путь, перевод строки и кавычка обязаны исчезнуть: имя уходит в
    # Content-Disposition, и через них можно подделать заголовок ответа
    got = rules.safe_filename('../../etc/passwd"\r\nSet-Cookie: a=b')
    assert "/" not in got and '"' not in got and "\r" not in got and "\n" not in got
    assert got.startswith("passwd")

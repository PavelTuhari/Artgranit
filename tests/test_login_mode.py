"""RO: pagina de logare pe officeplus.una.md = exclusiv OfficePlus, fara parola precompletata."""
from models.login_mode import login_mode


def test_header_from_officeplus_una_gives_exclusive_without_prefill():
    assert login_mode({"X-Login-Exclusive": "biro26"}, "") == (True, False)


def test_nufarul_default_unchanged():
    assert login_mode({}, "") == (False, False)


def test_dedicated_install_exclusive_and_never_prefilled():
    assert login_mode({}, "biro26") == (True, False)


def test_login_page_never_prefills_credentials():
    for h in ({}, {"X-Login-Exclusive": "biro26"}):
        for s in ("", "biro26"):
            assert login_mode(h, s)[1] is False


def test_app_calls_the_helper_in_one_place():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8").read()
    assert src.count("login_mode(request.headers, Config.LOGIN_EXCLUSIVE)") == 1

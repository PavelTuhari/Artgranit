"""RO: pagina de logare pe officeplus.una.md = exclusiv OfficePlus, fara parola precompletata."""
from models.login_mode import login_mode


def test_header_from_officeplus_una_gives_exclusive_without_prefill():
    assert login_mode({"X-Login-Exclusive": "biro26"}, "") == (True, False)


def test_nufarul_default_unchanged():
    assert login_mode({}, "") == (False, True)


def test_dedicated_install_keeps_prefill_behaviour():
    assert login_mode({}, "biro26") == (True, True)


def test_app_calls_the_helper_in_one_place():
    import os
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8").read()
    assert src.count("login_mode(request.headers, Config.LOGIN_EXCLUSIVE)") == 1

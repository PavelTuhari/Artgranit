"""RO: consimtamintul pentru cookie-uri pe vitrina (09.10.2026).

Garantii verificate:
- nimic ne-esential nu porneste din sablon: gtag.js si JivoChat nu mai au <script src>
  direct in site_base.html, consent default = denied;
- bannerul se incarca pe toate paginile vitrinei, o singura data;
- serverul pune op_vid / op_attr doar cu acord pe «Marketing» si le goleste fara el;
- versiunea alegerii e aceeasi in JS si in Python;
- «Refuz» e la fel de vizibil ca «Accept».
Documentatie: docs/Biro26/COOKIE_CONSIMTAMINT_2026-10-09.md
"""
import os
import re
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


def test_no_tracker_loads_directly_from_template():
    src = _read("templates", "biro26", "site_base.html")
    assert "googletagmanager.com/gtag/js" not in src
    assert "code.jivosite.com/widget" not in src
    assert "gtag('consent', 'default'" in src and "analytics_storage: 'denied'" in src
    assert src.index("gtag('consent', 'default'") < src.index("gtag('config'")
    assert "window.OP_GA_ID = '{{ ga_id }}'" in src
    assert "window.OP_JIVO_ID = '{{ jivo_id }}'" in src


def test_consent_partial_included_once():
    src = _read("templates", "biro26", "site_base.html")
    assert src.count('{% include "biro26/_site_cookie_consent.html" %}') == 1
    part = _read("templates", "biro26", "_site_cookie_consent.html")
    assert re.search(r'/static/biro26/cookie-consent\.css\?v=\d{8,10}', part)
    assert re.search(r'/static/biro26/cookie-consent\.js\?v=\d{8,10}', part)


def test_trackers_started_only_from_consent_script():
    js = _read("static", "biro26", "cookie-consent.js")
    body = js[js.index("function startAnalytics"):js.index("function startFunctional")]
    assert "googletagmanager.com/gtag/js" in body
    assert "code.jivosite.com/widget/" in js[js.index("function startFunctional"):js.index("function apply")]
    assert "if (c.a) startAnalytics();" in js and "if (c.f) startFunctional();" in js
    # fara alegere -> doar bannerul, nimic pornit
    assert "if (c) apply(c, null); else { banner(); scan(); }" in js


def test_reject_as_easy_as_accept():
    js = _read("static", "biro26", "cookie-consent.js")
    banner = js[js.index("function banner"):js.index("function settings")]
    assert 'data-opcc="reject"' in banner and 'data-opcc="accept"' in banner
    css = _read("static", "biro26", "cookie-consent.css")
    assert ".opcc-accept,.opcc-reject{" in css   # acelasi stil


def test_consent_version_same_in_js_and_python():
    js = _read("static", "biro26", "cookie-consent.js")
    from models import biro26_cookie_consent as cc
    assert "var CONSENT_VERSION = '%s';" % cc.CONSENT_VERSION in js
    assert "var COOKIE = '%s';" % cc.CONSENT_COOKIE in js


def test_parse_consent_cookie():
    from models.biro26_cookie_consent import parse
    assert parse("v1.a1.f0.m1.1790000000") == {"a": True, "f": False, "m": True}
    assert parse("v0.a1.f1.m1.1") == {"a": False, "f": False, "m": False}   # versiune veche
    assert parse(None) == parse("") == parse("gunoi") == {"a": False, "f": False, "m": False}


def _req(cookies, args=None, referrer=""):
    return SimpleNamespace(cookies=cookies, args=args or {}, referrer=referrer)


def test_attribution_cookies_only_with_marketing_consent():
    from models.biro26_social import Biro26Social
    # fara alegere, vizita din reclama: nu se pune nimic
    assert Biro26Social.on_request(_req({}, {"utm_source": "facebook"})) is None
    # refuz, dar cookie-urile vechi exista -> se golesc
    r = Biro26Social.on_request(_req({"op_consent": "v1.a1.f1.m0.1", "op_vid": "x" * 32, "op_attr": "{}"}))
    assert r == {"set_cookies": {"op_vid": "", "op_attr": ""}}
    # cu acord pe marketing -> ID de vizitator nou
    r = Biro26Social.on_request(_req({"op_consent": "v1.a0.f0.m1.1"}))
    assert r and len(r["set_cookies"]["op_vid"]) == 32


def test_no_google_fonts_and_self_hosted_inter():
    src = _read("templates", "biro26", "site_base.html")
    assert "fonts.googleapis.com" not in src and "fonts.gstatic.com" not in src
    assert "/static/biro26/fonts/inter/inter.css?v=" in src
    css = _read("static", "biro26", "fonts", "inter", "inter.css")
    for sub in ("latin", "latin-ext", "cyrillic", "cyrillic-ext"):
        f = "inter-%s-wght-normal.woff2" % sub
        assert "url(%s)" % f in css
        with open(os.path.join(ROOT, "static", "biro26", "fonts", "inter", f), "rb") as fh:
            assert fh.read(4) == b"wOF2"


def test_google_map_waits_for_consent_or_click():
    home = _read("templates", "biro26", "site_home.html")
    assert "<iframe" not in home[home.index("if (d.harta)"):home.index("if (d.harta)") + 400]
    assert "m.setAttribute('data-opcc-src'" in home and "window.opConsent.scan()" in home
    js = _read("static", "biro26", "cookie-consent.js")
    scan = js[js.index("function scan"):js.index("function apply")]
    assert "if (ok) {" in scan and "opcc-ph" in scan and "frame(b, u)" in scan

"""biro26-clients: cautarea unica OfficePlus -> date.gov.md + pornirea Contragenti (05.09.2026).

RO: logica noua sta in static/biro26/clients-gov.js; in sablonul comun sint
doar apelurile (regula nr. 2). Testele nu au nevoie de Oracle.
"""
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


def test_template_calls_the_separate_file_only():
    t = _read("templates", "biro26", "clients.html")
    assert '/static/biro26/clients-gov.js' in t
    assert "govAuto(decodeURIComponent(q))" in t, "fara rezultate -> date.gov.md automat"
    assert "govOffline(msg)" in t and "biro26-contragenti.zip" not in t
    assert "async function pickFromGov(qArg)" in t
    # scriptul extern e incarcat INAINTE de scriptul paginii (load() ruleaza imediat)
    assert t.index("clients-gov.js") < t.index("async function load()")


def test_gov_js_offers_starter_for_three_os_and_falls_back():
    js = _read("static", "biro26", "clients-gov.js")
    for k in ("'command'", "'bat'", "'py'"):
        assert k in js
    assert "/UNA.md/orasldev/crm/launcher/" in js and "return=" in js
    assert "nu este disponibil" in js and "window.govAuto" in js and "window.govOffline" in js
    r = subprocess.run(["node", "--check", os.path.join(ROOT, "static", "biro26", "clients-gov.js")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_shop_clients_search_includes_idno():
    src = _read("models", "biro26_oracle_store.py")
    assert "OR IDNO LIKE :q" in src


def test_crm_launcher_accepts_portal_return_path_only():
    src = _read("modules", "crm", "routes.py")
    assert 'request.args.get("return", "")' in src and 'ret.startswith("/UNA.md/")' in src

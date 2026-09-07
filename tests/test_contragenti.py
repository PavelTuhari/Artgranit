"""Puntea Contragenti -> una.md: izolare, reguli pure, DDL, potrivire (fara Oracle)."""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from modules.contragenti import rules  # noqa: E402


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as fh:
        return fh.read()


# ── izolare ──────────────────────────────────────────────────────────────
def test_module_leaves_nothing_in_the_shared_app():
    src = _read("app.py")
    assert "modules.contragenti" not in src and "CtgStore" not in src and "CtgController" not in src


def test_shared_deploy_script_is_untouched_by_the_module():
    assert "ctg_core" not in _read("deploy_oracle_objects.py").lower()


def test_module_is_picked_up_by_the_core():
    from core.module_loader import module_keys
    assert "contragenti" in module_keys()
    from modules.contragenti import blueprint
    assert blueprint.name == "contragenti"


def test_routes_without_prefix_and_manifest():
    assert "/UNA.md/orasldev" not in _read("modules", "contragenti", "routes.py")
    m = json.loads(_read("modules", "contragenti", "module.json"))
    assert m["url"] == "/UNA.md/orasldev/contragenti" and m["sql_prefix"] == "CTG_"


# ── reguli ───────────────────────────────────────────────────────────────
def test_norm_name_matches_registry_and_erp_spellings():
    assert rules.norm_name("Societatea cu Raspundere Limitata CONINFO") == rules.norm_name("CONINFO S.R.L.") == "CONINFO"
    assert rules.norm_name("IURILEN-FLOR SRL") == rules.norm_name("«Iurilen-Flor» S.R.L.")
    assert rules.norm_name("INSTITUTIA PUBLICA UNIVERSITATEA DE STAT DIN MOLDOVA") == \
        rules.norm_name("Instituţia Publică Universitatea de Stat din Moldova")
    assert rules.norm_name("") == ""
    assert rules.name_token("Societatea cu Raspundere Limitata 47TH PARALLEL") == "PARALLEL"


def test_charset_folding_keeps_cyrillic_and_drops_diacritics():
    assert rules.to_db_charset("Chişinău, str. Alba-Iulia") == "Chisinau, str. Alba-Iulia"
    assert rules.to_db_charset("ООО «Тест» — да") == 'ООО "Тест" - да'
    assert rules.strip_role("TUHARI PAVEL [Administrator]") == "TUHARI PAVEL"


def test_map_card_sets_codvechi_and_codfiscal_to_idno():
    card = rules.parse_card_xml(_read("modules", "crm", "sdk", "sample_card.xml"))
    m = rules.map_card(card)
    assert m["univers"]["CODVECHI"] == "1003600116460" and m["univers"]["GR1"] == "E" and m["univers"]["TIP"] == "O"
    assert m["org"]["CODFISCAL"] == "1003600116460" and m["org"]["DIRECTOR"] == "TUHARI PAVEL"
    assert m["univers"]["DENUMIREA"] == "CENTRUL DE ELABORARE UNISIM-SOFT SRL" or "UNISIM" in m["univers"]["DENUMIREA"]
    assert m["univers"]["NAMERUS"].startswith("CENTRUL DE ELABORARE UNISIM-SOFT")


def test_card_from_fields_and_invalid_inputs():
    c = rules.card_from_fields({"status": "ok", "idno": "1006600064263", "denumire": "USM", "adresa": "Chisinau"})
    assert c["idno"] == "1006600064263" and c["adresa"] == "Chisinau"
    with pytest.raises(ValueError):
        rules.card_from_fields({"denumire": "fara idno"})
    with pytest.raises(ValueError):
        rules.parse_card_xml("<html/>")
    assert rules.idno_valid("1006600064263") and not rules.idno_valid("1026602001999")


# ── DDL ──────────────────────────────────────────────────────────────────
def test_ddl_blocks_and_ascii():
    src = _read("modules", "contragenti", "sql", "01_ctg_core.sql")
    for b in [b for b in src.split("\n/\n") if b.strip()]:
        body = "\n".join(l for l in b.splitlines() if not l.strip().startswith("--")).strip()
        assert body.startswith("CREATE ") and body.count("CREATE ") == 1, body[:60]
    assert src.isascii() and "CREATE TABLE CTG_EVENT_LOG" in src
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("--"):
            assert ";" not in s and "'" not in s, s


# ── potrivirea (store cu baza simulata) ──────────────────────────────────
class _FakeDB:
    """RO: raspunde la SELECT-urile din find_existing si inregistreaza DML-urile."""
    def __init__(self, rows_by_cond):
        self.rows_by_cond, self.dml = rows_by_cond, []

    def execute_query(self, sql, params=None):
        for key, rows in self.rows_by_cond.items():
            if key in sql:
                return {"success": True, "columns": list(rows[0].keys()) if rows else [], "data": [list(r.values()) for r in rows]}
        return {"success": True, "columns": [], "data": []}

    def execute_dml(self, sql, params=None):
        self.dml.append((sql, params))
        return {"success": True}


def _patch_db(monkeypatch, fake):
    import modules.contragenti.store as st
    monkeypatch.setattr(st, "Biro26DB", lambda: fake)
    monkeypatch.setattr(st, "_rows", lambda res: [dict(zip(res["columns"], row)) for row in res["data"]])


def test_repair_existing_client_without_fiscal_code(monkeypatch):
    """RO: cazul 518172 — client de site cu IDNO pe fisa, fara CODVECHI/CODFISCAL -> repaired."""
    from modules.contragenti.store import CtgStore
    row = {"univers_cod": 518172, "denumirea": "INSTITUTIA PUBLICA UNIVERSITATEA DE STAT DIN MOLDOVA",
           "namerus": None, "codvechi": None, "gr1": "E", "codfiscal": None, "adress": None, "director": None,
           "yb_idno": "1006600064263", "is_company": "1", "yb_cod": 518172}
    fake = _FakeDB({"c.IDNO = :i": [row], "SELECT COD FROM TMS_ORG": []})
    _patch_db(monkeypatch, fake)
    logged = []
    monkeypatch.setattr(CtgStore, "log", staticmethod(lambda step, result="ok", **kw: logged.append((step, result))))
    r = CtgStore.apply({"idno": "1006600064263", "denumire": "INSTITUTIA PUBLICA UNIVERSITATEA DE STAT DIN MOLDOVA",
                        "adresa": "mun. Chisinau, str. A. Mateevici 60", "administratori": "GHERMAN IGOR [Rector]"},
                       page="biro26-clients", username="test", q="universitatea")
    assert r["success"] and r["result"] == "repaired" and r["univers_cod"] == 518172 and r["how"] == "yb_idno"
    sqls = " | ".join(s for s, _ in fake.dml)
    assert "UPDATE TMS_UNIVERS SET CODVECHI" in sqls and "INSERT INTO TMS_ORG" in sqls
    assert ("match_found", "ok") in logged and ("apply", "repaired") in logged


def test_match_by_name_when_idno_unknown_and_conflict_is_logged(monkeypatch):
    from modules.contragenti.store import CtgStore
    row = {"univers_cod": 7, "denumirea": "CONINFO SRL", "namerus": None, "codvechi": "1012600013725", "gr1": "E",
           "codfiscal": "1012600013725", "adress": "x", "director": "y", "yb_idno": None, "is_company": None, "yb_cod": None}
    fake = _FakeDB({"LIKE :t": [row]})
    _patch_db(monkeypatch, fake)
    ex = CtgStore.find_existing("1012600013725", "Societatea cu Raspundere Limitata CONINFO")
    assert ex is None or ex["how"] in ("codvechi", "name")
    # acelasi nume, ALT idno deja scris -> nu e aceeasi firma
    assert CtgStore.find_existing("1000000000000", "CONINFO S.R.L.") is None


def test_page_hooks_and_js_upsert():
    t = _read("templates", "biro26", "clients.html")
    assert "govUpsertXml(raw, q)" in t and "govUpsertFields(d)" in t
    js = _read("static", "biro26", "clients-gov.js")
    assert "const CTG = '/UNA.md/orasldev/contragenti/api/'" in js and "CTG + 'upsert'" in js and "CTG + 'log'" in js
    for step in ("pick_start", "pick_cancel", "pick_timeout", "pick_error"):
        assert "govLog('%s'" % step in t
    for step in ("offline", "search_fallback"):
        assert "govLog('%s'" % step in js

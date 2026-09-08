"""Testele modulului CRM (beta) — fara Oracle, fara wallet.

RO: izolarea (regula nr. 1), regulile pure (contractul XML al Contragenti,
IDNO, return_to, preseturi), DDL-ul (slash in jurul blocurilor PL/SQL,
fara diacritice), pagina (BASE din url_for, fara adresa portalului in JS).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODULE_DIR = os.path.join(ROOT, "modules", "crm")
sys.path.insert(0, ROOT)

from modules.crm import rules  # noqa: E402


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


SAMPLE = _read("modules", "crm", "sdk", "sample_card.xml")


# ── izolare ──────────────────────────────────────────────────────────────
def test_module_leaves_nothing_in_the_shared_app():
    src = _read("app.py")
    assert "modules.crm" not in src and "CrmController" not in src and "CrmStore" not in src


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "crm_core" not in src.lower() and "CRM_CLIENT" not in src


def test_module_is_picked_up_by_the_core():
    from core.module_loader import module_keys
    assert "crm" in module_keys()
    from modules.crm import blueprint
    assert blueprint.name == "crm"


def test_routes_are_declared_without_the_module_prefix():
    src = _read("modules", "crm", "routes.py")
    assert "/UNA.md/orasldev" not in src
    assert 'url_prefix' not in src


def test_store_uses_the_erp_transport_only():
    src = _read("modules", "crm", "store.py")
    assert "Biro26DB" in src and "DatabaseModel" not in src


def test_manifest():
    m = json.loads(_read("modules", "crm", "module.json"))
    assert set(m["title"]) >= {"ro", "ru", "en"}
    assert m["url"] == "/UNA.md/orasldev/crm" and m["sql_prefix"] == "CRM_"
    assert "crm.app_page" in m["pages"]


# ── contractul XML al Contragenti (INTEGRATION.md §2) ────────────────────
def test_parse_reference_card():
    c = rules.parse_card_xml(SAMPLE)
    assert c["idno"] == "1003600116460"
    assert c["denumire"] == "CENTRUL DE ELABORARE UNISIM-SOFT S.R.L."
    assert c["inregistrare"] == "30.03.2001" and c["lichidata"] is False
    assert c["administratori"] == "TUHARI PAVEL [Administrator]"
    assert c["founders"] == [{"name": "TUHARI PAVEL", "share": 100.0}]
    assert c["debts"] == [{"nr": 1, "type": "Bugetul de stat", "sum": 0.98}]
    assert c["currency"] == "MDL" and c["source"] == "date.gov.md"
    assert c["details_text"].startswith("=== Date de baza ===")


def test_parse_card_with_empty_founders_and_debts_and_liquidated():
    xml = ('<counterparty source="date.gov.md" idno="1012600013725" updated="x">'
           '<idno>1012600013725</idno><denumire>CONINFO S.R.L.</denumire>'
           '<lichidata>Da</lichidata><founders/><debts currency="MDL"/></counterparty>')
    c = rules.parse_card_xml(xml)
    assert c["lichidata"] is True and c["founders"] == [] and c["debts"] == []
    assert c["adresa"] == "" and c["inregistrare"] == ""


def test_parse_card_rejects_garbage():
    with pytest.raises(ValueError):
        rules.parse_card_xml("")
    with pytest.raises(ValueError):
        rules.parse_card_xml("<html></html>")
    with pytest.raises(ValueError):
        rules.parse_card_xml("<counterparty><denumire>x</denumire></counterparty>")
    with pytest.raises(ValueError):
        rules.parse_card_xml("<counterparty><idno>1</idno>")


def test_idno_check_digit():
    assert rules.idno_valid("1003600116460") and rules.idno_valid("1012600013725")
    assert not rules.idno_valid("1026602001999")          # clientul fictiv din ERP
    assert not rules.idno_valid("123") and not rules.idno_valid(None)


def test_card_from_return_to_query():
    c = rules.card_from_query({"status": "ok", "state": "A", "idno": "1003600116460",
                               "denumire": "UNISIM", "adresa": "Chisinau", "lichidata": "Nu",
                               "inregistrare": "30.03.2001", "forma_juridica": "SRL",
                               "administratori": "TUHARI"})
    assert c["idno"] == "1003600116460" and c["founders"] == [] and c["lichidata"] is False
    for st in ("cancelled", "timeout", ""):
        with pytest.raises(ValueError):
            rules.card_from_query({"status": st, "idno": "1003600116460"})


def test_presets_and_pick_url():
    assert rules.preset_where("all") == "" and rules.preset_where("xyz") == ""
    assert "TRUNC(SYSDATE)" in rules.preset_where("today")
    assert "ADDRESS IS NOT NULL" in rules.preset_where("with_address")
    u = rules.pick_url("http://127.0.0.1:9393/", q="UNISIM", lang="ru",
                       return_to="https://x/UNA.md/orasldev/crm/contragenti/callback", state="s1")
    assert u.startswith("http://127.0.0.1:9393/pick?q=UNISIM&lang=ru&timeout=300&return_to=")
    assert "state=s1" in u
    assert rules.pick_url("", lang="zz").startswith("http://127.0.0.1:9393/pick?q=&lang=ro")


# ── DDL ──────────────────────────────────────────────────────────────────
def test_ddl_has_slash_around_every_block_and_is_ascii():
    src = _read("modules", "crm", "sql", "01_crm_core.sql")
    blocks = [b for b in src.split("\n/\n") if b.strip()]
    for b in blocks:
        body = "\n".join(l for l in b.splitlines() if not l.strip().startswith("--")).strip()
        assert body.startswith("CREATE "), body[:60]
        assert body.count("CREATE ") == 1, "doua comenzi intr-un bloc: " + body[:80]
    assert src.isascii(), "diacritice in DDL — baza e CL8MSWIN1251"
    for t in ("CRM_SETTING", "CRM_CLIENT", "CRM_FOUNDER", "CRM_DEBT", "CRM_EVENT_LOG"):
        assert "CREATE TABLE %s" % t in src
    assert "UQ_CRM_CLIENT_IDNO UNIQUE (IDNO)" in src
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("--"):
            assert ";" not in s and "'" not in s, s


def test_deploy_script_is_own_and_targets_crm_sql():
    src = _read("modules", "crm", "scripts", "crm_deploy.py")
    assert '"modules", "crm", "sql"' in src and "Biro26DB" in src


# ── pagina ───────────────────────────────────────────────────────────────
def test_page_uses_url_for_and_has_the_demo_crm_features():
    tpl = _read("modules", "crm", "templates", "crm_app.html")
    js = tpl.split("<script>")[1]
    assert 'url_for("crm.app_page")' in tpl and 'url_for("crm.contragenti_callback"' in tpl
    assert "/UNA.md/orasldev/crm" not in js
    for must in ("/health", "/pick?q=", "/card?idno=", "api/import-xml", "api/pick-url",
                 "DEL_ARMED", 'value="today"', 'value="with_address"', "label-state"):
        assert must in tpl, must
    assert "alert(" not in js and "confirm(" not in js, "fara ferestre modale (regula Demo CRM)"


# ── cautarea unica + scriptul de pornire (05.09.2026) ────────────────────
def test_launcher_script_all_three_kinds_are_valid_python():
    import ast
    from modules.crm import launcher as L
    for k in ("py", "command", "bat"):
        body = L.render(k, lang="ru", port=9494, return_url="https://x/UNA.md/orasldev/crm/", generated="t")
        if k == "command":
            assert body.startswith("#!/bin/bash") and "python3 - <<'PYEOF'" in body
            py = body.split("<<'PYEOF'\n", 1)[1].rsplit("\nPYEOF", 1)[0]
        elif k == "bat":
            first, rest = body.split("\r\n", 1)
            assert first.startswith('@(python -x "%~f0"') and "py -3 -x" in first
            py = rest.replace("\r\n", "\n")
        else:
            py = body
        ast.parse(py)
        assert "PORT = 9494" in py and 'LANG = "ru"' in py and "github.com/PavelTuhari/Contragenti" in py
        for os_name in ("Darwin", "Windows", "Linux"):
            assert os_name in py
    import pytest
    with pytest.raises(ValueError):
        L.render("exe")


def test_launcher_script_uses_only_the_standard_library():
    from modules.crm import launcher as L
    import re
    py = L.render("py")
    mods = set()
    for m in re.finditer(r"^(?:from|import)\s+([\w\.]+(?:\s*,\s*[\w\.]+)*)", py, re.M):
        mods |= {x.strip().split(".")[0] for x in m.group(1).split(",")}
    assert mods <= {"io", "os", "platform", "shutil", "subprocess", "sys", "time", "venv",
                    "webbrowser", "zipfile", "urllib"}, mods


def test_page_single_search_falls_back_to_date_gov_and_offers_starter():
    tpl = _read("modules", "crm", "templates", "crm_app.html")
    assert "async function searchAll" in tpl and "await createClient(q)" in tpl
    assert "n === 0 && q" in tpl, "fara rezultate in baza -> date.gov.md"
    for k in ("launcher/command", "launcher/bat", "launcher/py"):
        assert k in tpl
    assert 'id="offline-box"' in tpl and "showOffline(true)" in tpl and "cgHost()" in tpl
    routes = _read("modules", "crm", "routes.py")
    assert '"/launcher/<kind>"' in routes and "Content-Disposition" in routes


# ── procesul «de la contract la bani» (08.09.2026) — fara Oracle ─────────
from modules.crm import entities, process  # noqa: E402


def test_entities_mirror_the_prototype_schema():
    """RO: tabelele si cimpurile din TZ §9.1 / uCrmData.pas, cu numele prototipului."""
    for key in ("clients", "contacts", "leads", "deals", "items", "orders", "tasks", "projects"):
        assert key in entities.ENTITIES
    o = entities.entity("orders")
    assert [f.name for f in o.fields][:6] == ["number", "order_date", "client_id", "project_id", "kind", "status"]
    assert o.field("number").column == "DOC_NO" and o.field("total").kind == entities.READONLY
    assert entities.entity("contacts").field("position").column == "JOB_TITLE"
    t = entities.entity("tasks")
    for n in ("stage", "priority", "assignee", "plan_start", "hours_plan", "hours_fact", "depends_on", "seq"):
        assert t.field(n), n
    assert entities.ENUMS["order_status"] == ["Черновик", "Подтверждён", "В работе", "Выполнен", "Оплачен", "Отменён"]
    assert entities.ENUMS["project_status"][0] == "Тендер" and entities.ENUMS["project_status"][-1] == "Проигран"


def test_stage_conditions_are_exclusive_and_bound_not_inlined():
    """RO: 8 etape, valorile canonice doar ca binduri (CL8MSWIN1251), alias t."""
    assert len(process.STAGES) == 8
    for s in process.STAGES:
        sql, p = process.stage_where(s)
        assert "t." in sql and sql.isascii(), sql
        assert all(not v.isascii() for v in p.values() if isinstance(v, str)), p
        osql, _ = process.overdue_where(s)
        assert osql.startswith(sql)
    assert "ADVANCE,0) <= 0" in process.stage_where("await_advance")[0]
    assert "SHIP_DATE IS NULL" in process.stage_where("ready_to_ship")[0]
    assert "PAID,0) >= NVL(t.TOTAL" in process.stage_where("closed")[0]
    assert process.overdue_where("closed")[0].endswith("1=0")


def test_boards_and_single_move_point():
    for k in process.BOARDS:
        cols = process.board_columns(k)
        assert len(cols) == len(process.BOARD_COLORS[k]), k
        for i in range(len(cols)):
            sets, p = process.board_move_sql(k, i)
            assert "WHERE" not in sets and sets.isascii()
            w, _ = process.board_column_where(k, i)
            assert "t." in w
    with pytest.raises(ValueError):
        process.board_move_sql("deals", 9)
    assert process.board_move_sql("project_tasks", 4)[1]["d"] == 1        # Готово <=> done
    assert process.board_move_sql("orders", 4)[1]["s"] == "Оплачен"


def test_posting_and_conversion_rules():
    assert process.post_sign("Продажа") == -1 and process.post_sign("Производство") == 1 and process.post_sign("Услуга") == 0
    assert process.post_allowed("Выполнен") and process.post_allowed("Оплачен") and not process.post_allowed("Черновик")
    assert process.done_steps_for("Закрыт") == 11 and process.done_steps_for("Проигран") == 1
    assert process.resolve_default("today+14") > process.resolve_default("today")
    assert process.enum_ok("deal_stage", "Выиграна") and not process.enum_ok("deal_stage", "Won")


def test_lang_json_has_three_languages_with_positional_enums():
    d = json.loads(_read("modules", "crm", "lang.json"))
    for lang in ("ro", "en", "ru"):
        assert set(d[lang]["strings"]) == set(d["ro"]["strings"]), lang
        for e, v in entities.ENUMS.items():
            assert len(d[lang]["enums"][e]) == len(v), (lang, e)
        assert len(d[lang]["enums"]["stage_title"]) == 8
    assert d["ru"]["enums"]["order_kind"] == entities.ENUMS["order_kind"]


def test_process_ddl_is_ascii_multi_tenant_and_slashed():
    src = _read("modules", "crm", "sql", "02_crm_process.sql")
    assert src.isascii()
    for t in ("CRM_CONTACT", "CRM_LEAD", "CRM_DEAL", "CRM_ITEM", "CRM_PROJECT", "CRM_ORDER", "CRM_ORDER_LINE", "CRM_TASK"):
        assert "CREATE TABLE %s (" % t in src
        if t != "CRM_ORDER_LINE":
            assert "OWNER_KIND" in src.split("CREATE TABLE %s (" % t)[1].split("/")[0]
    assert "UNIQUE (OWNER_KIND, OWNER_ID, IDNO)" in src
    for line in src.splitlines():
        s = line.strip()
        if s.startswith("--"):
            assert ";" not in s and "'" not in s, s
    blocks = [b for b in src.split("\n/\n") if b.strip()]
    assert all(b.strip() for b in blocks) and src.rstrip().endswith("/")


def test_process_routes_and_cabinet_are_prefix_free():
    src = _read("modules", "crm", "routes_process.py")
    assert "/UNA.md" not in src.replace("/UNA.md/orasldev/biro26-site/account", "")
    for r in ('"/cabinet"', '"/api/v2/<key>"', '"/api/v2/orders/<int:rid>/post"', '"/api/v2/leads/<int:rid>/convert"',
              '"/api/v2/board/<kind>/move"', '"/api/v2/workspace/stages"', '"/api/v2/reports/<slug>"'):
        assert r in src, r


def test_page_has_no_modal_dialogs_and_loads_the_process_script():
    page = _read("modules", "crm", "templates", "crm_app.html")
    js = _read("modules", "crm", "static", "crm_process.js")
    for bad in ("window.alert(", "alert(", "confirm(", "prompt("):
        assert bad not in js and bad not in page, bad
    assert "crm.static" in page and "crm_process.js" in page and "CRM_CABINET" in page
    assert "draggable" in js and "board/" in js and "workspace/stages" in js

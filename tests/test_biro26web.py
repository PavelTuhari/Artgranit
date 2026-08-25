"""Бэк-офис UNA в вебе — тесты без живой базы.

Проверяется то, что легко сломать незаметно: фильтр журнала попадает
в запрос сырым SQL, строки документа зависят от семейства витрин, а
тексты Oracle не должны утекать наружу.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MODULE_DIR = os.path.join(ROOT, "modules", "biro26web")

from modules.biro26web import store
from modules.biro26web.controller import Biro26WebController
from modules.biro26web.store import is_safe_filter


def _ok(columns=None, data=None):
    return {"success": True, "columns": columns or [], "data": data or [],
            "rowcount": len(data or []), "message": ""}


def _db(results=None, fail=None):
    db = MagicMock()
    db.__enter__.return_value = db
    db.__exit__.return_value = False
    queue = list(results or [])
    db.captured = []

    def _query(sql, params=None):
        db.captured.append((sql, params or {}))
        if fail:
            return {"success": False, "columns": [], "data": [],
                    "rowcount": 0, "message": fail}
        return queue.pop(0) if queue else _ok()

    db.execute_query.side_effect = _query
    return db


# ── фильтр журнала ───────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "sysfid=201",
    "SYSFID>=5100 and SYSFID<=5135\nor sysfid=5170",
    "(SYSFID>=401 and SYSFID<=406) or (ID >= 48134 AND ID <= 48135)",
    "sysfid in (1208, 1212, 1213)",
])
def test_real_journal_filters_pass(text):
    assert is_safe_filter(text)


@pytest.mark.parametrize("text", [
    "sysfid=201 or 1=1) union select password from users--",
    "sysfid=(select max(cod) from tmdb_docs)",
    "sysfid=201; drop table tmdb_docs",
    "nrmanual='x'",
    "",
])
def test_dangerous_filters_are_refused(text):
    assert not is_safe_filter(text)


def test_unsafe_filter_never_reaches_the_database():
    # Фильтр приходит из конфигурации, но испорченная запись там не должна
    # превращаться в инъекцию в бэк-офисе.
    db = _db([_ok(["OBJ_ID", "SQLFILTER"], [[1, "sysfid=1 or 1=1--"]])])
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.documents(1)
    assert res["success"] is False
    assert "недопустимые конструкции" in res["message"]
    assert len(db.captured) == 1, "после отказа запросов быть не должно"


def test_journal_filter_is_taken_from_config_not_from_the_request():
    # В запрос уходит только числовой номер журнала.
    db = _db([
        _ok(["OBJ_ID", "SQLFILTER"], [[7, "sysfid=201"]]),
        _ok(["COD"], [[100]]),
        _ok(["SYSFID", "NAME"], []),
    ])
    with patch.object(store, "Biro26DB", return_value=db):
        store.documents(7)

    journal_sql, journal_params = db.captured[0]
    assert journal_params == {"o": 7}
    docs_sql, docs_params = db.captured[1]
    assert "sysfid=201" in docs_sql
    assert "row_limit" in docs_params


def test_date_range_uses_bind_variables():
    db = _db([
        _ok(["OBJ_ID", "SQLFILTER"], [[7, "sysfid=201"]]),
        _ok(["COD"], []),
        _ok(["SYSFID"], []),
    ])
    with patch.object(store, "Biro26DB", return_value=db):
        store.documents(7, date_from="2026-01-01", date_to="2026-12-31")

    _sql, params = db.captured[1]
    assert params["date_from"] == "2026-01-01" and params["date_to"] == "2026-12-31"


def test_journal_without_filter_returns_a_note_not_all_documents():
    # Пустой фильтр не должен превращаться в «показать все документы базы».
    db = _db([_ok(["OBJ_ID", "SQLFILTER"], [[7, None]])])
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.documents(7)
    assert res["success"] and res["data"]["rows"] == []
    assert "не задан фильтр" in res["data"]["note"]
    assert len(db.captured) == 1


# ── дерево журналов ──────────────────────────────────────────────────

def test_journals_are_grouped_and_orphans_are_kept():
    groups = _ok(["OBJ_ID", "NAME", "CAPTION"], [[10, "grp", "Касса"]])
    journals = _ok(["OBJ_ID", "PARENT_ID", "NAME", "CAPTION"],
                   [[11, 10, "j1", "Касса дн."], [12, 99, "j2", None]])
    with patch.object(store, "Biro26DB", return_value=_db([groups, journals])):
        res = store.journal_tree()

    tree = res["data"]
    assert tree[0]["title"] == "Касса"
    assert [j["obj_id"] for j in tree[0]["journals"]] == [11]
    # журнал с несуществующей группой не должен потеряться
    assert tree[-1]["title"] == "Без группы"
    assert tree[-1]["journals"][0]["title"] == "j2"


# ── строки документа ─────────────────────────────────────────────────

def test_lines_for_a_known_family_are_read_from_its_view():
    with patch.object(store, "Biro26DB", return_value=_db([_ok(["CTSC"], [[5]])])) as _:
        res = store.document_lines(100, "201")
    assert res["success"] and res["data"]["note"] is None


def test_lines_for_an_unknown_family_say_so_instead_of_showing_empty():
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.document_lines(100, "DG1p21")
    assert res["data"]["rows"] == []
    assert "не подключены" in res["data"]["note"]
    db.execute_query.assert_not_called()


# ── контроллер ───────────────────────────────────────────────────────

def test_bad_journal_id_is_rejected_before_the_database():
    with patch.object(Biro26WebController, "_store") as st:
        payload, status = Biro26WebController.documents("не число")
    assert status == 400
    st.documents.assert_not_called()


def test_bad_date_is_rejected():
    with patch.object(Biro26WebController, "_store") as st:
        payload, status = Biro26WebController.documents(7, date_from="01.01.2026")
    assert status == 400 and "YYYY-MM-DD" in payload["message"]
    st.documents.assert_not_called()


def test_reversed_date_range_is_rejected():
    with patch.object(Biro26WebController, "_store") as st:
        payload, status = Biro26WebController.documents(
            7, date_from="2026-05-01", date_to="2026-04-01")
    assert status == 400
    st.documents.assert_not_called()


def test_limit_is_capped():
    # Журнал «Все» иначе потянет десятки тысяч строк через thick-воркер.
    with patch.object(Biro26WebController, "_store") as st:
        st.documents.return_value = {"success": True, "data": {}, "message": ""}
        Biro26WebController.documents(7, limit=999999)
    assert st.documents.call_args[0][1] == 1000


def test_missing_journal_becomes_404():
    with patch.object(Biro26WebController, "_store") as st:
        st.journal.return_value = {"success": False, "data": None,
                                   "message": "журнал не найден"}
        payload, status = Biro26WebController.journal(7)
    assert status == 404


def test_oracle_text_never_reaches_the_user():
    with patch.object(Biro26WebController, "_store") as st:
        st.journal_tree.return_value = {
            "success": False, "data": None,
            "message": "ORA-12541: TNS:no listener at host db-internal:1521"}
        payload, status = Biro26WebController.journals()
    assert status == 500
    assert "db-internal" not in payload["message"]
    assert "ORA-" not in payload["message"]


def test_document_card_joins_head_lines_and_postings():
    with patch.object(Biro26WebController, "_store") as st:
        st.document.return_value = {"success": True, "message": "",
                                    "data": {"cod": 1, "docname": "201"}}
        st.document_lines.return_value = {"success": True, "message": "",
                                          "data": {"rows": [{"ctsc": 5}], "note": None}}
        st.document_postings.return_value = {"success": True, "message": "",
                                             "data": [{"cod": 9}]}
        payload, status = Biro26WebController.document(1)

    assert status == 200
    assert payload["data"]["head"]["cod"] == 1
    assert payload["data"]["lines"] == [{"ctsc": 5}]
    assert payload["data"]["postings"] == [{"cod": 9}]


# ── модуль на ядре ───────────────────────────────────────────────────

def test_module_follows_the_core_contract():
    from core.module_loader import module_keys
    assert "biro26web" in module_keys()

    from modules.biro26web import blueprint
    assert blueprint.name == "biro26web"


def test_module_leaves_nothing_in_the_shared_app():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "biro26web" not in src


def test_module_only_reads_the_accounting_database():
    # Модуль показывает боевой учёт. Любая запись здесь — это правка
    # чужих документов, и она должна появляться осознанно, а не мимоходом.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read().upper()
    for word in ("INSERT ", "UPDATE ", "DELETE ", "MERGE ", "EXECUTE_DML",
                 "EXECUTE_SCRIPT", "CALL_PROC"):
        assert word not in src, word


def test_every_route_is_guarded():
    import ast

    with open(os.path.join(MODULE_DIR, "routes.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    handlers = [n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.decorator_list
                and any(isinstance(d, ast.Call)
                        and isinstance(d.func, ast.Attribute)
                        and d.func.attr == "route" for d in n.decorator_list)]
    assert len(handlers) >= 5

    for node in handlers:
        called = {n.func.attr for n in ast.walk(node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        called |= {n.func.id for n in ast.walk(node)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "is_authenticated" in called or "_guard" in called, node.name


def test_document_list_does_not_show_a_made_up_total():
    # SUM(TMDB_CM.SUMA) равен нулю: проводки двойной записи
    # взаимопогашаются. Документ 386 — двадцать проводок, сумма 0, при
    # этом строки дают 5100. Такую «сумму» показывать нельзя.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read()
    docs = src.split("def documents(")[1].split("def document(")[0]
    assert "SUM(c.SUMA)" not in docs
    assert "COUNT(*)" in docs

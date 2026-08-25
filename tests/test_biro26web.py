"""Бэк-офис UNA в вебе — тесты без живой базы.

Проверяется то, что легко сломать незаметно: фильтр журнала попадает
в запрос сырым SQL, строки документа зависят от семейства витрин, а
тексты Oracle не должны утекать наружу.
"""
import os
import re
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


def test_line_source_is_chosen_by_document_type_then_family():
    from modules.biro26web.store import line_source
    # тип важнее семейства: под одним DG1p21 сидят 223 разных типа
    assert line_source(sysfid=49398)["source"] == "TMDB_EDL_PLDRAFTD"
    assert line_source(docname="201")["source"] == "VMDB_ST201D"
    assert line_source(sysfid=12280, docname="201")["source"] == "VMDB_ST201D"
    assert line_source(sysfid=999999, docname="DG1p21") is None


def test_line_source_registry_is_curated_not_guessed():
    # Автоопределение по NRDOC даёт ложные срабатывания: у документа 86
    # «находится» TMDB_SALAR_ABSD1 с зарплатными строками. Реестр должен
    # оставаться списком проверенных источников.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "TMDB_SALAR_ABSD1" not in src.split("# Фильтр журнала")[0].replace(
        "# «находится» TMDB_SALAR_ABSD1", "")
    assert "user_tab_columns" not in src, "поиск таблицы наугад недопустим"


def test_unmapped_type_explains_why_instead_of_showing_nothing():
    db = _db()
    with patch.object(store, "Biro26DB", return_value=db):
        res = store.document_lines(1, docname="DG1p21", sysfid=48121,
                                   type_name="Акт изменения цен")
    note = res["data"]["note"]
    assert "Акт изменения цен" in note and "не подключены" in note
    db.execute_query.assert_not_called()


# ── номенклатура ─────────────────────────────────────────────────────

def test_goods_items_always_filter_by_product_type():
    # В TMS_UNIVERS лежат и товары, и категории, и контрагенты. Без TIP='P'
    # в список номенклатуры попали бы сами категории.
    db = _db([_ok(["COD"], [])])
    with patch.object(store, "Biro26DB", return_value=db):
        store.goods_items(group1=276)
    sql, _params = db.captured[0]
    assert "u.TIP = 'P'" in sql


def test_goods_items_require_a_group_or_a_search():
    # Иначе запрос пойдёт по 208 тысячам позиций.
    with patch.object(Biro26WebController, "_store") as st:
        payload, status = Biro26WebController.goods_items()
    assert status == 400
    st.goods_items.assert_not_called()


def test_short_search_without_a_group_is_refused():
    with patch.object(Biro26WebController, "_store") as st:
        payload, status = Biro26WebController.goods_items(search="a")
    assert status == 400
    st.goods_items.assert_not_called()


def test_goods_search_uses_a_bind_variable():
    db = _db([_ok(["COD"], [])])
    with patch.object(store, "Biro26DB", return_value=db):
        store.goods_items(search="о'брайен")
    sql, params = db.captured[0]
    assert ":needle" in sql and "%О'БРАЙЕН%" in params["needle"]


def test_goods_item_not_found_is_404():
    with patch.object(Biro26WebController, "_store") as st:
        st.goods_item.return_value = {"success": False, "data": None,
                                      "message": "номенклатура не найдена"}
        _payload, status = Biro26WebController.goods_item(1)
    assert status == 404


def test_goods_items_are_capped():
    with patch.object(Biro26WebController, "_store") as st:
        st.goods_items.return_value = {"success": True, "data": [], "message": ""}
        Biro26WebController.goods_items(group1=276, limit=10**6)
    assert st.goods_items.call_args[0][3] == 1000


def test_untitled_journal_groups_are_marked_so_the_ui_can_skip_them():
    # В конфигурации шесть групп называются служебным «Journals group».
    # Печатать такой заголовок шесть раз подряд бессмысленно.
    groups = _ok(["OBJ_ID", "NAME", "CAPTION"],
                 [[10, "Journals group", None], [11, "grp", "Касса"]])
    journals = _ok(["OBJ_ID", "PARENT_ID", "NAME", "CAPTION"],
                   [[20, 10, "j1", "A"], [21, 11, "j2", "B"]])
    with patch.object(store, "Biro26DB", return_value=_db([groups, journals])):
        tree = store.journal_tree()["data"]

    assert tree[0]["titled"] is False
    assert tree[1]["titled"] is True
    # журналы безымянной группы всё равно на месте
    assert [j["obj_id"] for j in tree[0]["journals"]] == [20]


# ── запись документов ────────────────────────────────────────────────

from modules.biro26web import writer


@pytest.fixture(autouse=False)
def period(monkeypatch):
    """Рабочий период задан — как после настройки модуля.

    Заодно отключается чтение настроек из контура: тесты не ходят в базу,
    иначе каждый вызов съедал бы ответ из очереди подставного соединения.
    """
    monkeypatch.setattr(writer, "_setting", lambda code: None)
    monkeypatch.setattr(writer, "work_period", lambda: ("2026-01-01", "2026-12-31"))


def test_foreign_document_types_cannot_be_created():
    # Чужие типы имеют свои настройки проводок и свою ответственность.
    db = _db()
    with patch.object(writer, "Biro26DB", return_value=db):
        for sysfid in (1228, 12280, 201, 59999, 60100, None):
            res = writer.create_document(sysfid, "2026-08-25")
            assert res["success"] is False, sysfid
            assert "разрешённого диапазона" in res["message"]
    db.execute_query.assert_not_called()


def test_own_document_type_is_allowed():
    assert writer.is_writable(60001) and writer.is_writable(60099)
    assert not writer.is_writable(59999) and not writer.is_writable(60100)


def test_bad_date_is_refused_before_the_database():
    db = _db()
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.create_document(60001, "25.08.2026")
    assert res["success"] is False and "YYYY-MM-DD" in res["message"]
    db.execute_query.assert_not_called()


def test_document_number_comes_from_the_sequence_not_from_max(period):
    db = _db([_ok(["COD"], [[777]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.create_document(60001, "2026-08-25")
    sql, _ = db.captured[0]
    assert "ID_TMDB_DOCS.NEXTVAL" in sql
    assert "MAX(" not in sql
    assert res["data"]["cod"] == 777


def test_author_is_left_empty_when_mapping_is_not_configured(monkeypatch, period):
    # Подставить чужой USERID хуже, чем оставить пустой.
    monkeypatch.delenv("BIRO26WEB_UNA_USERID", raising=False)
    db = _db([_ok(["COD"], [[1]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.create_document(60001, "2026-08-25", username="pt")

    statements = db.execute_script.call_args[0][0]
    # период сессия задаёт всегда, а вот автора — только если он настроен
    assert not any("PARAM_USERID" in s["sql"] for s in statements)
    assert any("PARAM_PERIODBEG" in s["sql"] for s in statements)
    assert res["data"]["userid"] is None
    assert "не настроено" in res["message"]
    # имя пользователя портала при этом сохраняется в примечании
    note = [s for s in statements if "TMDB_DOCS_ADD" in s["sql"]][0]
    assert "pt" in note["params"]["note"]


def test_author_is_set_when_mapping_is_configured(monkeypatch, period):
    monkeypatch.setenv("BIRO26WEB_UNA_USERID", "42")
    db = _db([_ok(["COD"], [[1]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.create_document(60001, "2026-08-25")

    statements = db.execute_script.call_args[0][0]
    assert any("SET_ENV" in s["sql"] for s in statements)
    assert res["data"]["userid"] == 42


def test_creation_is_one_transaction(period):
    # Документ без строки TMDB_DOCS_ADD либо наоборот — мусор в учёте.
    db = _db([_ok(["COD"], [[1]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        writer.create_document(60001, "2026-08-25")
    assert db.execute_script.call_count == 1
    stmts = db.execute_script.call_args[0][0]
    assert any("NLS_DATE_FORMAT" in st["sql"] for st in stmts), \
        "формат даты должен задаваться самим модулем"


def test_posting_goes_through_un_gfc_not_direct_inserts(period):
    db = _db([_ok(["SYSFID", "ISGFC"], [[60001, 0]]),
              _ok(["ISGFC", "CM"], [[1, 4]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.post_document(500)

    stmts = db.execute_script.call_args[0][0]
    block = " ".join(st["sql"] for st in stmts).upper()
    assert "UN$GFC.SETDOC_GFC" in block and "UN$GFC.SETDOC_CORRECT" in block
    assert "INSERT" not in block
    # проведение тоже идёт в подготовленной сессии
    assert "NLS_DATE_FORMAT" in block and "PARAM_PERIODBEG" in block
    assert res["data"]["postings"] == 4


def test_foreign_document_cannot_be_posted():
    db = _db([_ok(["SYSFID", "ISGFC"], [[12280, 0]])])
    db.call_proc = MagicMock()
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.post_document(386)
    assert res["success"] is False and "чужие документы" in res["message"]
    db.call_proc.assert_not_called()


def test_already_posted_document_is_not_posted_twice():
    db = _db([_ok(["SYSFID", "ISGFC"], [[60001, 1]])])
    db.call_proc = MagicMock()
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.post_document(500)
    assert res["success"] is False and "уже проведён" in res["message"]
    db.call_proc.assert_not_called()


def test_read_layer_stays_free_of_writing():
    # Чтение и запись разнесены намеренно: store.py можно доверять без
    # чтения целиком, а writer.py короткий и читается перед тем, как
    # разрешить запись.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        assert "TMDB_DOCS (" not in fh.read()


def test_bind_names_avoid_oracle_builtins(period):
    # :uid падает с ORA-01745: UID — встроенная функция Oracle. Проверяем
    # сам запрос, а не комментарии, где эта причина и записана.
    db = _db([_ok(["COD"], [[1]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        writer.create_document(60001, "2026-08-25")

    insert = [s for s in db.execute_script.call_args[0][0]
              if "INSERT INTO TMDB_DOCS " in s["sql"]][0]
    # имена связывания целиком, а не подстрокой: ':division' содержит ':div'
    binds = set(re.findall(r":(\w+)", insert["sql"]))
    assert "uid" not in binds and "div" not in binds
    assert binds == set(insert["params"]), "связывания и параметры разошлись"


def test_accounting_rules_reach_the_user_on_write():
    # «Дата вне рабочего периода» человек исправит сам, если увидит текст.
    # Спрятать его за «ошибкой базы» значило бы оставить его в тупике.
    msg = ("ORA-20101: Redactarea documentului este interzisa: 389.\n"
           "Data documentului (25-AUG-26) inafara perioadei de lucru (-)\n"
           "ORA-06512: at \"UN4PUBLIC.MSG\", line 4")
    with patch.object(writer, "create_document",
                      return_value={"success": False, "data": None, "message": msg}):
        payload, status = Biro26WebController.create_document(
            {"sysfid": 60001, "date": "2026-08-25"})
    assert status == 409
    assert "perioadei de lucru" in payload["message"]
    assert "ORA-06512" not in payload["message"]


def test_infrastructure_errors_stay_hidden_on_write():
    with patch.object(writer, "create_document",
                      return_value={"success": False, "data": None,
                                    "message": "ORA-12541: TNS:no listener at db-internal"}):
        payload, status = Biro26WebController.create_document(
            {"sysfid": 60001, "date": "2026-08-25"})
    assert status == 500 and "db-internal" not in payload["message"]


def test_write_routes_are_guarded_too():
    import ast
    with open(os.path.join(MODULE_DIR, "routes.py"), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    writers = [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name in ("api_create_document", "api_post_document")]
    assert len(writers) == 2
    for node in writers:
        names = {n.func.id for n in ast.walk(node)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "_guard" in names, node.name


def test_own_document_types_read_lines_through_their_business_view():
    # Строки лежат в общем TMDB_CST3A — там их ждёт родной клиент.
    # VMDB_YSEO1D даёт им бизнес-имена и отбирает только свои документы.
    from modules.biro26web.store import line_source
    for sysfid in (60001, 60002):
        assert line_source(sysfid=sysfid)["source"] == "VMDB_YSEO1D"


def test_registry_documents_how_the_line_view_is_discovered():
    # Витрина строк не угадывается: она записана в SmartQuery грида
    # документа в конфигурации. Эта подсказка должна остаться в коде.
    with open(os.path.join(MODULE_DIR, "store.py"), encoding="utf-8") as fh:
        src = fh.read()
    assert "SmartQuery" in src and "tpf0" in src


def test_document_development_guide_keeps_the_verified_facts():
    # Руководство заменяет догадки проверенными фактами. Если из него
    # пропадут имена объектов, следующий разработчик снова пойдёт гадать.
    path = os.path.join(ROOT, "docs", "UNA", "DOCUMENT_DEVELOPMENT.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for fact in ("ID_TMDB_DOCS.NEXTVAL", "TMDB_CST3A", "VMDB_CST3A",
                 "ID_TMDB_CM", "SmartQuery", ":fRegistru:grCST3a",
                 "DB ID", "SYSFID", "setDoc_GFC", "A$LOB", "SDBG"):
        assert fact in text, fact


# ── дата и рабочий период ────────────────────────────────────────────

def test_session_date_format_is_set_by_us_not_inherited(period):
    # Смысл всей правки: модуль не полагается на умолчания сервера.
    stmts = writer.session_prelude()
    assert stmts[0]["sql"].startswith("ALTER SESSION SET NLS_DATE_FORMAT")
    assert writer.SESSION_DATE_FORMAT in stmts[0]["sql"]
    # значения идут ПОСЛЕ установки формата, иначе разберутся по-старому
    assert "PARAM_PERIODBEG" in stmts[1]["sql"]


def test_dates_are_converted_into_the_format_we_declared(period):
    stmts = writer.session_prelude()
    params = stmts[1]["params"]
    assert params["beg"] == "01.01.2026" and params["end"] == "31.12.2026"


def test_to_session_date_covers_every_declared_format():
    # Если формат сменят, перевод обязан остаться правильным для всех.
    original = writer.SESSION_DATE_FORMAT
    try:
        expected = {"DD.MM.YYYY": "05.03.2026", "YYYY-MM-DD": "2026-03-05",
                    "MM/DD/YYYY": "03/05/2026"}
        for fmt, want in expected.items():
            writer.SESSION_DATE_FORMAT = fmt
            assert writer.to_session_date("2026-03-05") == want, fmt
    finally:
        writer.SESSION_DATE_FORMAT = original


def test_non_iso_input_is_refused_before_it_reaches_the_session():
    for bad in ("05.03.2026", "2026/03/05", "5-3-2026", "", None):
        with pytest.raises(ValueError):
            writer.to_session_date(bad)


def test_missing_work_period_is_refused_not_invented(monkeypatch):
    # Тихо открыть период было бы обходом контроля учёта.
    monkeypatch.setattr(writer, "work_period", lambda: (None, None))
    db = _db()
    with patch.object(writer, "Biro26DB", return_value=db):
        res = writer.create_document(60001, "2026-08-25")
    assert res["success"] is False and "рабочий период не задан" in res["message"]


def test_broken_period_setting_is_refused(monkeypatch):
    monkeypatch.setattr(writer, "work_period", lambda: ("01.01.2026", "2026-12-31"))
    with pytest.raises(writer.WriteRefused):
        writer.session_prelude()
    monkeypatch.setattr(writer, "work_period", lambda: ("2026-12-31", "2026-01-01"))
    with pytest.raises(writer.WriteRefused):
        writer.session_prelude()


def test_satellite_row_is_updated_not_inserted(period):
    """Строку TMDB_DOCS_ADD заводит учётная система, а не мы.

    TRIG_AFTINS_TMDB_DOCS2 вставляет её сразу после заголовка. Наша вторая
    вставка ломалась об ORA-00001, и документ не создавался вовсе —
    транзакция одна. Примечание дописывается правкой готовой строки.
    """
    db = _db([_ok(["COD"], [[1]])])
    db.execute_script = MagicMock(return_value={"success": True, "results": [],
                                                "message": ""})
    with patch.object(writer, "Biro26DB", return_value=db):
        writer.create_document(60001, "2026-08-25", comment="проверка")

    statements = db.execute_script.call_args[0][0]
    satellite = [s for s in statements if "TMDB_DOCS_ADD" in s["sql"]]
    assert len(satellite) == 1
    assert satellite[0]["sql"].startswith("UPDATE TMDB_DOCS_ADD")
    assert "INSERT INTO TMDB_DOCS_ADD" not in " ".join(s["sql"] for s in statements)

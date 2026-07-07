"""Biro26 module — unit tests (mocked; no live Oracle).

Biro26 reaches the Oracle 11g OfficePlus ERP through a thick-mode subprocess
worker. These tests mock the subprocess transport (and the worker's pure helpers)
so they run without a database or Instant Client.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from models.biro26_db import Biro26DB
from models import biro26_worker


# ── worker pure helpers ─────────────────────────────────────────────

def test_worker_nls_statements():
    joined = " ".join(biro26_worker._nls_statements()).upper()
    assert "NLS_LANGUAGE" in joined and "ENGLISH" in joined
    assert "NLS_TERRITORY" in joined and "AMERICA" in joined
    assert "NLS_NUMERIC_CHARACTERS" in joined


def test_worker_cell_makes_numbers_and_dates_json_safe():
    import decimal, datetime
    assert biro26_worker._cell(decimal.Decimal("12.00")) == 12  # integer-valued -> int
    assert biro26_worker._cell(decimal.Decimal("12.50")) == 12.5
    assert biro26_worker._cell(datetime.date(2026, 1, 1)) == "2026-01-01"
    assert biro26_worker._cell("plain") == "plain"


# ── client transport (subprocess mocked) ────────────────────────────

def _fake_proc(payload: dict, returncode: int = 0, stderr: str = ""):
    m = MagicMock()
    m.returncode = returncode
    m.stdout = json.dumps(payload)
    m.stderr = stderr
    return m


def test_execute_query_parses_worker_json():
    payload = {"success": True, "columns": ["ID", "NAME"],
               "data": [[1, "a"], [2, "b"]], "rowcount": 2}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)) as mrun:
        r = Biro26DB().execute_query("SELECT 1 FROM dual", {"x": 1})
    assert r["success"] and r["columns"] == ["ID", "NAME"]
    assert r["data"] == [(1, "a"), (2, "b")]  # rows normalized to tuples
    # request shape sent to worker
    sent = json.loads(mrun.call_args.kwargs["input"])
    assert sent["op"] == "query" and sent["params"] == {"x": 1}


def test_call_proc_returns_output_lines():
    payload = {"success": True, "output_lines": ["RO: ok / EN: ok"]}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)):
        r = Biro26DB().call_proc("BEGIN NULL; END;", capture_output=True)
    assert r["success"] and r["output_lines"] == ["RO: ok / EN: ok"]


def test_worker_nonzero_exit_is_error():
    bad = MagicMock(); bad.returncode = 1; bad.stdout = ""; bad.stderr = "boom"
    with patch("models.biro26_db.subprocess.run", return_value=bad):
        r = Biro26DB().execute_query("SELECT 1 FROM dual")
    assert r["success"] is False and "boom" in r["message"]


def test_test_connection_maps_version():
    payload = {"success": True, "version": "Oracle Database 11g"}
    with patch("models.biro26_db.subprocess.run", return_value=_fake_proc(payload)):
        r = Biro26DB().test_connection()
    assert r["success"] and "11g" in r["version"]


# ── store: mapping profiles + g_* builder ───────────────────────────

from models.biro26_oracle_store import Biro26Store, G_PARAMS, build_gset_block, _page


def test_g_params_complete():
    assert len(G_PARAMS) == 25
    assert "codprice" in G_PARAMS and "len_denumire" in G_PARAMS


def test_build_gset_block_numbers_strings_dates():
    block = build_gset_block({"codprice": "5", "um": "buc.", "len_denumire": "160",
                              "date_start": "2026-01-01", "bogus": "x"})
    assert "g_codprice := 5" in block            # numeric unquoted
    assert "g_um := 'buc.'" in block             # string quoted
    assert "g_len_denumire := 160" in block
    assert "g_date_start := DATE '2026-01-01'" in block
    assert "bogus" not in block                  # unknown param ignored


def test_page_uses_rownum_not_fetch():
    sql = _page("SELECT id FROM t ORDER BY id", limit=10, offset=20)
    assert "ROWNUM <= 30" in sql and "rn > 20" in sql
    assert "FETCH" not in sql.upper()


class _FakeBiro26DB:
    """Stand-in for Biro26DB in store unit tests."""
    def __init__(self, rows=None, cols=None):
        self._rows = rows or []
        self._cols = cols or []
        self.last_sql = None
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute_query(self, sql, params=None):
        self.last_sql = sql
        return {"success": True, "data": self._rows, "columns": self._cols,
                "rowcount": len(self._rows), "message": ""}
    def execute_dml(self, sql, params=None):
        self.last_sql = sql
        return {"success": True, "rowcount": 1, "message": ""}
    def execute_script(self, statements):
        self.last_sql = statements
        return {"success": True, "results": [{"data": [[42]], "columns": ["ID"]}], "message": ""}
    def call_proc(self, plsql, params=None, capture_output=False):
        self.last_sql = plsql
        return {"success": True, "output_lines": ["RO: ok / EN: ok"], "message": ""}


def test_get_profiles_ok():
    cols = ["ID", "NAME", "CODPRICE", "IS_DEFAULT", "CREATED_AT", "CREATED_BY"]
    rows = [(1, "default", 1, "1", "28.06.2026 10:00", "OFFICEPLUS")]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_profiles()
    assert r["success"] and r["data"][0]["name"] == "default"


def test_create_profile_returns_new_id():
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB()):
        r = Biro26Store.create_profile("feed2", 5, {"codprice": "5", "um": "buc."})
    assert r["success"] and r["data"]["id"] == 42


# ── store: source feed ──────────────────────────────────────────────

def test_get_goods_returns_rows_and_status():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1","STOC","COD_UNIVERS","ROW_STATUS"]
    rows = [(1,"A1","Name","BR","F",10,9,12,5,1001,"IN_DICT")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_goods(limit=50, offset=0)
    assert r["success"] and r["data"][0]["row_status"] == "IN_DICT"
    assert "ROWNUM" in fake.last_sql and "FETCH" not in fake.last_sql.upper()


def test_get_goods_status_filter():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1","STOC","COD_UNIVERS","ROW_STATUS"]
    rows = [(1,"A1","N","B","F",1,1,1,1,1,"NEW"),(2,"A2","M","B","F",1,1,1,1,None,"CONFLICT")]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_goods(status="CONFLICT")
    assert [d["id"] for d in r["data"]] == [2]


def test_validate_input_captures_output():
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB()):
        r = Biro26Store.validate_input()
    assert r["success"] and r["output"] == ["RO: ok / EN: ok"]


# ── store: dictionary ───────────────────────────────────────────────

def test_get_univers_filters_tip_p():
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","GR1","UM","ISARHIV"]
    rows = [(1001,"A1","Nume","Имя","TVR","buc.",None)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_univers(arhiv="active")
    assert r["success"] and r["data"][0]["namerus"] == "Имя"
    assert "TIP='P'" in fake.last_sql and "ROWNUM" in fake.last_sql


def test_archive_univers_value_two_still_calls_pkg():
    # store does not guard '2' (controller does); ensure it builds the call
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.archive_univers("1")
    assert r["success"] and "archive_univers" in fake.last_sql


def test_fix_confusables_single_cod():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.fix_denumirea_confusables(1001)
    assert r["success"] and "p_cod => 1001" in fake.last_sql


# ── store: groups / suppliers / categories ──────────────────────────

def test_get_groups_ok():
    cols = ["CODPRICE","CODGRP","GRPNAME","TYPE_SC","GR1_SC"]
    rows = [(1,10,"Birolux","P",None)]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_groups(codprice=1)
    assert r["success"] and r["data"][0]["grpname"] == "Birolux"


def test_merge_groups_uses_script():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.merge_groups(1, 10, 20)
    assert r["success"] and isinstance(fake.last_sql, list) and len(fake.last_sql) == 2


def test_get_suppliers_joins_univers_name():
    cols = ["COD","NAME","GR1","ADRESS","BANK","CODFISCAL"]
    rows = [(160420,"S.R.L. CRAFTI BUSINESS","X","addr","bank","123")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_suppliers()
    assert r["success"] and r["data"][0]["name"].startswith("S.R.L.")
    assert "TIP='O'" in fake.last_sql


# ── store: price list ───────────────────────────────────────────────

def test_get_prices_paginated():
    cols = ["CODPRICE","CODGRP","SC","PRETV","PRETV1","PRETV2","PRETV3","DATASTART"]
    rows = [(1,10,1001,12.0,10.0,9.0,None,"01.01.2026")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_prices(codprice=1, codgrp=10)
    assert r["success"] and r["data"][0]["pretv"] == 12.0
    assert "ROWNUM" in fake.last_sql and "VTPR1D_PERPRLIST" in fake.last_sql


def test_import_prices_builds_date_args():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.import_prices(1, "2026-01-01", "3000-01-01")
    assert r["success"]
    assert "import_prices" in fake.last_sql and "DATE '2026-01-01'" in fake.last_sql


def test_rollback_pricelist_call():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.rollback_pricelist(5)
    assert r["success"] and "rollback_pricelist(p_codprice => 5)" in fake.last_sql


# ── controller ──────────────────────────────────────────────────────

from flask import Flask
from controllers.biro26_controller import Biro26Controller

_app = Flask(__name__)


def test_controller_connection_test_delegates():
    with patch("controllers.biro26_controller.Biro26Store") as S:
        S.test_connection.return_value = {"success": True, "version": "Oracle 11g"}
        r = Biro26Controller.connection_test()
    assert r["success"] and "version" in r


def test_controller_create_profile_requires_name():
    with _app.test_request_context(json={"codprice": 1, "params": {}}):
        r = Biro26Controller.create_profile()
    assert r["success"] is False and "name" in r["error"]


def test_controller_archive_blocks_value_two():
    with _app.test_request_context(json={"isarhiv": "2"}):
        r = Biro26Controller.archive_univers()
    assert r["success"] is False and "blocked" in r["error"]


def test_controller_get_goods_passes_filters():
    with patch("controllers.biro26_controller.Biro26Store") as S:
        S.get_goods.return_value = {"success": True, "data": []}
        with _app.test_request_context("/?search=pen&status=NEW&limit=10"):
            Biro26Controller.get_goods()
        kwargs = S.get_goods.call_args.kwargs
    assert kwargs["search"] == "pen" and kwargs["status"] == "NEW" and kwargs["limit"] == 10


# ── stage 1: images ─────────────────────────────────────────────────

def test_get_goods_includes_image_cols():
    cols = ["ID","ARTICOL","DENUMIRE","BRAND","FURNIZOR","ANGRO","IONLINE","RETAIL1",
            "STOC","COD_UNIVERS","PHOTO_URL","IMAGE_LINK","ROW_STATUS"]
    rows = [(1,"A1","N","B","F",1,1,1,1,1001,"http://x/p.jpg","http://x/i.jpg","IN_DICT")]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_goods(limit=10)
    assert r["success"] and r["data"][0]["photo_url"] == "http://x/p.jpg"
    assert "PHOTO_URL" in fake.last_sql and "IMAGE_LINK" in fake.last_sql


# ── stage 2: source columns/sample ──────────────────────────────────

def test_source_columns_rejects_bad_name():
    r = Biro26Store.source_columns("BIRO26_GOODS; DROP")
    assert r["success"] is False

def test_source_columns_ok():
    cols = ["ID","ARTICOL","DENUMIRE"]
    fake = _FakeBiro26DB([(1,"a","b")], cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.source_columns("BIRO26_GOODS")
    assert r["success"] and r["data"] == ["ID","ARTICOL","DENUMIRE"]


# ── stage 3: sources ────────────────────────────────────────────────
from models.biro26_sources import is_safe_select, view_name_for, Biro26Sources

def test_is_safe_select_accepts_plain_select():
    assert is_safe_select("SELECT a, b FROM t WHERE x=1")
    assert is_safe_select("  with q as (select 1 a from dual) select * from q")

def test_is_safe_select_rejects_dml_and_multi():
    assert not is_safe_select("SELECT 1; DROP TABLE t")
    assert not is_safe_select("UPDATE t SET x=1")
    assert not is_safe_select("select * from t; delete from t")
    assert not is_safe_select("")

def test_view_name_for_sanitizes():
    assert view_name_for("My Feed!") == "V_BIRO26_SRC_MY_FEED"
    assert view_name_for("abc") == "V_BIRO26_SRC_ABC"


# ── stage 3: AI helper ──────────────────────────────────────────────
from models.biro26_ai import heuristic_mapping, extract_json, suggest_mapping

def test_heuristic_mapping_matches_common_names():
    cols = ["ARTICOL","DENUMIRE","RETAIL1","ANGRO","IONLINE","BRAND","COD_UNIVERS"]
    m = heuristic_mapping(cols)
    assert m["col_articol"] == "ARTICOL"
    assert m["col_denumire"] == "DENUMIRE"
    assert m["col_retail"] == "RETAIL1"
    assert m["col_brand"] == "BRAND"
    assert m["col_key"] == "COD_UNIVERS"

def test_extract_json_from_noisy_text():
    assert extract_json('blah {"col_articol": "ART"} tail')["col_articol"] == "ART"
    assert extract_json("no json here") is None

def test_suggest_mapping_falls_back_when_ai_unavailable():
    cols = ["ART","NAME","PRICE"]
    with patch("models.biro26_ai.is_available", return_value=False):
        r = suggest_mapping(cols, [], "")
    assert r["success"] and r["source"] == "heuristic"


def test_controller_create_source_requires_select():
    with _app.test_request_context(json={"name":"x","sql":"DELETE FROM t"}):
        with patch("controllers.biro26_controller.Biro26Sources") as S:
            S.create_source.return_value = {"success": False, "error": "only a single read-only SELECT is allowed"}
            r = Biro26Controller.create_source()
    assert r["success"] is False


def test_is_safe_select_strips_comments():
    # ';' inside a comment must NOT trigger multi-statement reject
    assert is_safe_select("select /* ; */ 1 from dual")
    # forbidden keyword hidden in a comment is removed, statement still a SELECT
    assert is_safe_select("select 1 from dual -- drop table t")
    # but a real second statement is still rejected
    assert not is_safe_select("select 1 from dual; drop table t")


def test_import_images_merges_feed_links():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.import_images()
    assert r["success"] and "rows" in r
    assert "MERGE INTO TMS_MPT_TVR" in fake.last_sql and "IE_LINKADRES" in fake.last_sql


# ── store: stock balances (UN$SOLD.GET_SOLDT) ───────────────────────

class _FakeStockCalcDB(_FakeBiro26DB):
    """Like _FakeBiro26DB but remembers the execute_script statements
    separately, since calc_stock() issues a follow-up execute_query()
    that would otherwise overwrite last_sql."""
    def __init__(self, header_rows, header_cols):
        super().__init__(header_rows, header_cols)
        self.last_script = None
    def execute_script(self, statements):
        self.last_script = statements
        return super().execute_script(statements)


def _stock_header_fake():
    cols = ["ID", "ROW_COUNT", "RUN_AT"]
    rows = [(1, 0, "01.07.2026 16:53")]
    return _FakeStockCalcDB(rows, cols)


def test_calc_stock_runs_script_and_returns_header():
    fake = _stock_header_fake()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.calc_stock(data_doc="2026-07-01", dep_filter="")
    assert r["success"] and r["data"]["id"] == 1
    assert isinstance(fake.last_script, list)
    joined = " ".join(s["sql"] for s in fake.last_script)
    assert "UN$SOLD.GET_SOLDT" in joined
    assert "YBIRO_STOCK_CALC_ITEM" in joined
    assert "GROUP BY SC, NVL(DEP,0)" in joined  # aggregated to avoid PK collisions


def test_calc_stock_no_gtt_index_step():
    # Oracle blocks CREATE INDEX on a GTT right after it's populated (ORA-14452);
    # calc_stock must not attempt it.
    fake = _stock_header_fake()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        Biro26Store.calc_stock(data_doc="2026-07-01", dep_filter="")
    joined = " ".join(s["sql"] for s in fake.last_script)
    assert "CREATE INDEX" not in joined.upper()


def test_get_latest_stock_calc_ok():
    cols = ["ID","DATA_DOC","DEP_FILTER","CONT_FILTER","PFILT","ROW_COUNT","STATUS","ERR_TEXT","RUN_AT"]
    rows = [(1,"01.07.2026",None,"217 2165 2114","ACDE12",0,"OK",None,"01.07.2026 16:53")]
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeBiro26DB(rows, cols)):
        r = Biro26Store.get_latest_stock_calc()
    assert r["success"] and r["data"]["status"] == "OK"


def test_get_products_stock_joins_stock_and_image():
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","UM","TIP","GRUPA","CATEGORIE",
            "BRAND","ANGRO","IONLINE","RETAIL1","ANGRO_FARA_TVA","IMAGE","REAL_CANT"]
    rows = [(239265,"SKU: 903194","Ace gamalie 120 buc","Имя","buc.","P",
             "Table si accesorii","Accesorii pentru table","Austral",
             3.92,4.64,5.10,3.27,"http://x/p.jpg",None)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_products_stock(limit=10)
    assert r["success"] and r["data"][0]["real_cant"] is None
    assert "TIP='P'" in fake.last_sql and "YBIRO_STOCK_CALC_ITEM" in fake.last_sql
    assert "ROWNUM" in fake.last_sql and "FETCH" not in fake.last_sql.upper()


def test_get_products_stock_filters_by_brand_and_categorie():
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","UM","TIP","GRUPA","CATEGORIE",
            "BRAND","ANGRO","IONLINE","RETAIL1","ANGRO_FARA_TVA","IMAGE","REAL_CANT"]
    fake = _FakeBiro26DB([], cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        Biro26Store.get_products_stock(brand="Austral", categorie="Accesorii pentru table")
    assert "g.BRAND IN (:br0)" in fake.last_sql and "g.CATEGORIE=:categorie" in fake.last_sql


def test_get_products_stock_multi_brand_and_price_range():
    # RO/EN: shop facets — comma-separated brands + price bounds on the
    # effective (as-of) retail price expression
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","UM","TIP","GRUPA","CATEGORIE",
            "BRAND","ANGRO","IONLINE","RETAIL1","ANGRO_FARA_TVA","IMAGE","REAL_CANT"]
    fake = _FakeBiro26DB([], cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        Biro26Store.get_products_stock(brand="Austral, Biblion",
                                       price_min=50, price_max=200)
    assert "g.BRAND IN (:br0,:br1)" in fake.last_sql
    assert ">= :pmin" in fake.last_sql and "<= :pmax" in fake.last_sql
    assert "NVL(pl.PRETV" in fake.last_sql


def test_get_product_brands_scoped_to_tip_p():
    cols = ["BRAND", "CNT"]
    rows = [("Austral", 1110), ("Biblion", 29157)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_product_brands()
    assert r["success"] and r["data"][0]["brand"] == "Austral"
    assert "TIP='P'" in fake.last_sql and "GROUP BY g.BRAND" in fake.last_sql


def test_get_product_categories_scoped_to_tip_p():
    cols = ["CATEGORIE", "CNT"]
    rows = [("Abac", 13)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_product_categories()
    assert r["success"] and r["data"][0]["categorie"] == "Abac"
    assert "TIP='P'" in fake.last_sql and "GROUP BY g.CATEGORIE" in fake.last_sql


# ── store: barcodes (TMS_MPT_BARCODE) + product tree ────────────────

def test_get_univers_search_matches_barcode():
    fake = _FakeBiro26DB([], ["COD"])
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        Biro26Store.get_univers(search="4840000000022")
    assert "TMS_MPT_BARCODE" in fake.last_sql and "b.BARCODE LIKE :s" in fake.last_sql


def test_get_products_stock_barcode_column_and_search():
    cols = ["COD","CODVECHI","DENUMIREA","NAMERUS","UM","TIP","GRUPA","CATEGORIE",
            "BRAND","ANGRO","IONLINE","RETAIL1","ANGRO_FARA_TVA","IMAGE","REAL_CANT",
            "BARCODE","BC_CNT"]
    rows = [(161226,"21171","Блок","",None,"P","Rechizite","Blocuri","Crafti",
             11.04,12.15,"13.25",9.2,"http://x/p.jpg",None,"4840000000022",2)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_products_stock(search="4840000000022")
    assert r["success"] and r["data"][0]["barcode"] == "4840000000022"
    assert r["data"][0]["bc_cnt"] == 2
    assert "MIN(BARCODE)" in fake.last_sql
    # search must be a pre-resolved COD set (IN ... UNION), NOT OR/EXISTS inside
    # the heavy join — the OR form made Oracle evaluate the whole join row-by-row
    # (~300s vs ~3s live)
    assert "u.COD IN (" in fake.last_sql and "UNION" in fake.last_sql
    assert "SELECT COD FROM TMS_MPT_BARCODE WHERE BARCODE LIKE :s" in fake.last_sql
    assert "OR EXISTS" not in fake.last_sql
    # feed join must be deduplicated (a few products have duplicate feed rows)
    assert "ROW_NUMBER() OVER" in fake.last_sql and "PARTITION BY g0.COD_UNIVERS" in fake.last_sql


def test_get_products_stock_grupa_filter():
    fake = _FakeBiro26DB([], ["COD"])
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        Biro26Store.get_products_stock(grupa="Table si accesorii")
    assert "g.GRUPA=:grupa" in fake.last_sql


def test_get_product_tree_groups_by_grupa_categorie():
    cols = ["GRUPA", "CATEGORIE", "CNT"]
    rows = [("Table si accesorii", "Accesorii pentru table", 57)]
    fake = _FakeBiro26DB(rows, cols)
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.get_product_tree()
    assert r["success"] and r["data"][0]["grupa"] == "Table si accesorii"
    assert "GROUP BY g.GRUPA, g.CATEGORIE" in fake.last_sql


def test_get_univers_card_includes_barcodes():
    class _CardFake(_FakeBiro26DB):
        def execute_query(self, sql, params=None):
            self.last_sql = sql
            if "TMS_MPT_BARCODE" in sql:
                return {"success": True, "columns": ["BARCODE"],
                        "data": [("4840000000022",), ("4840070000021",)],
                        "rowcount": 2, "message": ""}
            if "FROM TMS_UNIVERS" in sql:
                return {"success": True, "columns": ["COD", "DENUMIREA"],
                        "data": [(161226, "Блок")], "rowcount": 1, "message": ""}
            return {"success": True, "columns": [], "data": [], "rowcount": 0, "message": ""}
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_CardFake()):
        r = Biro26Store.get_univers_card(161226)
    assert r["success"] and r["data"]["barcodes"] == ["4840000000022", "4840070000021"]


# ── store: product editing + tree editing ───────────────────────────

class _FakeEditDB(_FakeBiro26DB):
    def __init__(self):
        super().__init__()
        self.last_script = None
    def execute_script(self, statements):
        self.last_script = statements
        return {"success": True, "results": [], "message": ""}


def test_update_product_builds_atomic_script_with_whitelist():
    fake = _FakeEditDB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.update_product(
            161226,
            univers={"denumirea": "X", "um": "buc.", "hack": "no"},
            goods={"brand": "B", "grupa": "G", "angro": 5, "evil": "no"},
            image="http://x/p.jpg", bc_add=["123"], bc_remove=["456"])
    assert r["success"]
    sqls = " || ".join(st["sql"] for st in fake.last_script)
    assert "UPDATE TMS_UNIVERS SET" in sqls and "DENUMIREA = :denumirea" in sqls
    assert "hack" not in sqls and "evil" not in sqls          # whitelisted fields only
    assert "UPDATE BIRO26_GOODS SET" in sqls and "BRAND = :brand" in sqls
    assert "MERGE INTO TMS_MPT_TVR" in sqls                    # image upsert
    assert "INSERT INTO TMS_MPT (COD)" in sqls                 # barcode FK card
    assert "INSERT INTO TMS_MPT_BARCODE" in sqls
    assert "DELETE FROM TMS_MPT_BARCODE" in sqls


def test_update_product_nothing_to_update():
    with patch("models.biro26_oracle_store.Biro26DB", return_value=_FakeEditDB()):
        r = Biro26Store.update_product(1, univers={"bogus": "x"})
    assert r["success"] is False


def test_rename_tree_node_grupa_and_categorie():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.rename_tree_node("grupa", "Old", "New")
    assert r["success"] and "SET GRUPA = :new WHERE GRUPA = :old" in fake.last_sql
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r2 = Biro26Store.rename_tree_node("categorie", "OldC", "NewC", grupa="G")
    assert r2["success"] and "WHERE GRUPA = :g AND CATEGORIE = :old" in fake.last_sql


def test_move_tree_categorie_sql():
    fake = _FakeBiro26DB()
    with patch("models.biro26_oracle_store.Biro26DB", return_value=fake):
        r = Biro26Store.move_tree_categorie("G1", "C1", "G2")
    assert r["success"] and "SET GRUPA = :ng" in fake.last_sql
    assert "WHERE GRUPA = :g AND CATEGORIE = :c" in fake.last_sql

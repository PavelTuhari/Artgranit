"""Drumul scurt al catalogului trebuie sa dea EXACT ce dadea cel vechi.

RO: optimizarea din 01.09.2026 schimba forma interogarii (filtrele feed-ului
trec printr-un IN, paginarea se face pe TMS_UNIVERS). Daca ar schimba si
rezultatul, magazinul ar arata alte produse — de aceea testul compara
rind cu rind cele doua drumuri pe baza reala.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COMBOS = [
    dict(limit=24, offset=0),
    dict(limit=24, offset=48),
    dict(limit=24, offset=0, grupa="Supraveghere video"),
    dict(limit=12, offset=0, sort="name_desc"),
    dict(limit=5, offset=0, only_new=True),
    dict(cod=515935, limit=1),
    # RO: cu numaratoare — forma pe care o cere vitrina la fiecare pagina
    dict(limit=24, offset=0, with_count=True),
    dict(limit=24, offset=0, grupa="Supraveghere video", with_count=True),
]


class TestFastPathShape(unittest.TestCase):
    """RO: fara baza — doar regulile de aplicabilitate."""

    def test_search_and_price_go_the_old_way(self):
        from models import biro26_catalog_fast as F
        self.assertFalse(F.supports("toner", None, None, "name"))
        self.assertFalse(F.supports(None, 10.0, None, "name"))
        self.assertFalse(F.supports(None, None, 99.0, "name"))
        self.assertFalse(F.supports(None, None, None, "price_desc"))
        self.assertTrue(F.supports(None, None, None, "name"))
        self.assertTrue(F.supports("", None, None, "name_desc"))

    def test_feed_filters_use_in_subquery(self):
        """RO: filtrul pe grupa NU mai are voie sa treaca prin deduparea
        intregii tabele inainte de paginare — asta a incarcat baza."""
        from models import biro26_catalog_fast as F
        sql, total, params = F.build("1", "2026-09-01", grupa="X", limit=24)
        page = sql[sql.index("FROM (SELECT"):sql.index(") p ")]
        self.assertIn("u.COD IN (SELECT COD_UNIVERS FROM BIRO26_GOODS", page)
        self.assertNotIn("ROW_NUMBER", page)
        self.assertEqual(params["grupa"], "X")
        self.assertIn("COUNT(*)", total)


class TestFastPathEqualsOld(unittest.TestCase):
    """RO: acelasi rezultat ca drumul vechi (cere Oracle; se sare fara el)."""

    def test_same_rows(self):
        try:
            from models import biro26_catalog_fast as F
            from models.biro26_oracle_store import Biro26Store as S
            probe = S.get_products_stock(limit=1)
            if not probe.get("success"):
                self.skipTest("Oracle indisponibil: %s" % probe.get("error"))
        except Exception as e:                               # noqa: BLE001
            self.skipTest("Oracle indisponibil: %s" % e)
        real = F.supports
        try:
            for kw in COMBOS:
                F.supports = real
                new = (S.get_products_stock(**kw).get("data") or [])
                F.supports = lambda *a, **k: False
                old = (S.get_products_stock(**kw).get("data") or [])
                self.assertEqual([r.get("cod") for r in new],
                                 [r.get("cod") for r in old], str(kw))
                if kw.get("with_count"):
                    F.supports = real
                    tn = S.get_products_stock(**kw).get("total")
                    F.supports = lambda *a, **k: False
                    to = S.get_products_stock(**kw).get("total")
                    self.assertEqual(tn, to, "total difera: %s" % kw)
                    self.assertTrue(tn and tn > 0, "total gol: %s" % kw)
                for a, b in zip(new, old):
                    self.assertEqual(a, b, str(kw))
        finally:
            F.supports = real


class TestGoodsIsUnique(unittest.TestCase):
    """RO: invariantul de care depinde join-ul simplu (02.09.2026): un singur
    rind per COD_UNIVERS in BIRO26_GOODS, aparat de un index UNIC. Daca
    testul pica, cineva a scos indexul sau a incarcat duplicate pe alta cale
    — catalogul ar arata rinduri dublate."""

    def test_no_duplicates_and_unique_index(self):
        try:
            from models.biro26_db import Biro26DB
            from models.biro26_oracle_store import _rows
            db = Biro26DB()
            dup = _rows(db.execute_query(
                "SELECT COUNT(*) N FROM (SELECT COD_UNIVERS FROM BIRO26_GOODS "
                "WHERE COD_UNIVERS IS NOT NULL GROUP BY COD_UNIVERS "
                "HAVING COUNT(*) > 1)"))
            ix = _rows(db.execute_query(
                "SELECT UNIQUENESS U FROM USER_INDEXES "
                "WHERE INDEX_NAME = 'UX_BIRO26_GOODS_CODUNIV'"))
        except Exception as e:                               # noqa: BLE001
            self.skipTest("Oracle indisponibil: %s" % e)
        if not dup:
            self.skipTest("Oracle indisponibil (raspuns gol)")
        self.assertEqual(int(dup[0]["n"]), 0, "BIRO26_GOODS are din nou duplicate")
        self.assertTrue(ix and ix[0]["u"] == "UNIQUE",
                        "lipseste indexul unic UX_BIRO26_GOODS_CODUNIV")

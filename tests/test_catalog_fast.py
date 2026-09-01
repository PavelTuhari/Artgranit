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
                for a, b in zip(new, old):
                    self.assertEqual(a, b, str(kw))
        finally:
            F.supports = real

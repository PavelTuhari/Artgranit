"""Relevanta cautarii in catalog (01.10.2026): la cautare + sortarea implicita
ORDER BY-ul pune intii denumirile care incep cu termenul; fara cautare ordinea
ramine alfabetica. Fara Oracle — mock pe execute_query.
Documentatie: docs/Biro26/CAUTARE_RELEVANTA_2026-10-01.md
"""
import re
import unittest
from unittest import mock

BIND_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def _run(**kw):
    """RO: apeleaza get_products_stock, intoarce lista (sql, params) trimise."""
    from models.biro26_oracle_store import Biro26Store
    calls = []

    def fake(sql, params=None, **_):
        calls.append((sql, dict(params or {})))
        if sql.startswith("SELECT COUNT(*)"):
            return {"success": True, "columns": ["CNT"], "data": [(3,)]}
        return {"success": True, "columns": ["COD"], "data": []}

    with mock.patch("models.biro26_db.Biro26DB.execute_query", side_effect=fake), \
            mock.patch("models.biro26_oracle_store._cached",
                       side_effect=lambda k, t, producer: producer()):
        res = Biro26Store.get_products_stock(**kw)
    return res, calls


def _page_sql(calls):
    return [c for c in calls if not c[0].startswith("SELECT COUNT(*)")][-1]


def _count_sql(calls):
    return [c for c in calls if c[0].startswith("SELECT COUNT(*)")][-1]


class TestRankHelper(unittest.TestCase):
    def test_applies_only_on_search_with_default_sort(self):
        from models import biro26_search_rank as R
        self.assertTrue(R.applies("pix", "name"))
        self.assertTrue(R.applies("pix", None))
        self.assertTrue(R.applies("pix", ""))
        self.assertFalse(R.applies(None, "name"))
        self.assertFalse(R.applies("   ", "name"))
        for s in ("price_asc", "price_desc", "name_desc"):
            self.assertFalse(R.applies("pix", s))

    def test_no_new_binds(self):
        # RO: doar `:s` — bind-ul pe care filtrul de cautare il leaga deja
        #     si in pagina, si in numaratoare (si pe drumul Oracle Text)
        from models import biro26_search_rank as R
        self.assertEqual(set(BIND_RE.findall(R.ORDER_BY)), {"s"})
        self.assertTrue(R.ORDER_BY.startswith(" ORDER BY CASE"))
        self.assertTrue(R.ORDER_BY.endswith("ELSE 4 END, u.DENUMIREA, u.COD"))


class TestStoreOrdering(unittest.TestCase):
    def test_search_uses_relevance(self):
        res, calls = _run(search="pix", limit=8)
        self.assertTrue(res["success"])
        sql, params = _page_sql(calls)
        from models import biro26_search_rank as R
        self.assertIn(R.ORDER_BY, sql)
        self.assertNotIn("ORDER BY u.DENUMIREA, u.COD", sql)
        self.assertEqual(params["s"], "%pix%")

    def test_no_search_default_order_unchanged(self):
        # RO: cu pret -> drumul general (nu cel scurt), dar fara cautare
        _, calls = _run(price_min=1, limit=8)
        sql, params = _page_sql(calls)
        self.assertIn("ORDER BY u.DENUMIREA, u.COD", sql)
        self.assertNotIn("ORDER BY CASE", sql)

    def test_explicit_sorts_win_over_relevance(self):
        for sort, frag in (("price_asc", "ASC NULLS LAST, u.DENUMIREA, u.COD"),
                           ("price_desc", "DESC NULLS LAST, u.DENUMIREA, u.COD"),
                           ("name_desc", "ORDER BY u.DENUMIREA DESC, u.COD")):
            _, calls = _run(search="pix", sort=sort, limit=8)
            sql, _ = _page_sql(calls)
            self.assertIn(frag, sql, sort)
            self.assertNotIn("ORDER BY CASE", sql, sort)

    def test_binds_match_sql_exactly(self):
        # RO: capcana ORA-01036 — fiecare interogare primeste EXACT bind-urile
        #     pe care le contine; numaratoarea nu are ORDER BY-ul de relevanta.
        res, calls = _run(search="pix", limit=8, with_count=True)
        self.assertEqual(res.get("total"), 3)
        for sql, params in (_page_sql(calls), _count_sql(calls)):
            self.assertEqual(set(BIND_RE.findall(sql)), set(params), sql[:60])
        self.assertNotIn("ORDER BY CASE", _count_sql(calls)[0])


if __name__ == "__main__":
    unittest.main()

"""Doua defecte latente din fisierele comune, iesite la iveala pe 03.09.2026
pe AMBELE contururi (identice in main): pagina «Servicii» moarta (KeyError: 0)
si /api/biro26/site/config cu 500 (aliasul `time` ascuns de o variabila).
Testele sint fara Oracle — mock pe execute_query.
"""
import os
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestServicesRowsAreDicts(unittest.TestCase):
    """RO: _rows() intoarce dictionare; modelul nu are voie sa indexeze r[0]."""

    def _res(self, cols, rows):
        return {"success": True, "columns": cols, "data": rows}

    def test_list_functions(self):
        from models.biro26_services import Biro26Services as S
        cols = ["CODE", "KIND", "ORD", "NAME_RO", "NAME_RU", "NAME_EN",
                "DESCR_RO", "DESCR_RU", "DESCR_EN", "FILE_NAME"]
        rows = [("stoc", "report", 1, "Stoc", "Остатки", None, "d", None, None, "stoc.csv")]
        with mock.patch("models.biro26_db.Biro26DB.execute_query",
                        return_value=self._res(cols, rows)):
            r = S.list_functions("ru")
        self.assertTrue(r["success"])
        self.assertEqual(r["data"][0]["code"], "stoc")
        self.assertEqual(r["data"][0]["name"], "Остатки")
        self.assertEqual(r["data"][0]["descr"], "d")            # fallback RO
        self.assertEqual(r["data"][0]["count_url"], "/api/biro26/services/stoc/count")

    def test_count_and_get_sql(self):
        from models.biro26_services import Biro26Services as S
        def fake(sql, params=None, **kw):
            if "ybiro_service_functions" in sql:
                return self._res(["SRC_SQL", "FILE_NAME", "KIND"],
                                 [("SELECT 1 FROM dual", "f.csv", "report")])
            return self._res(["CNT"], [(7,)])
        with mock.patch("models.biro26_db.Biro26DB.execute_query", side_effect=fake):
            r = S.count("stoc")
        self.assertEqual(r["data"]["count"], 7)

    def test_csv_writes_values_not_column_names(self):
        from models.biro26_services import Biro26Services as S
        def fake(sql, params=None, **kw):
            if "ybiro_service_functions" in sql:
                return self._res(["SRC_SQL", "FILE_NAME", "KIND"],
                                 [("SELECT 1 FROM dual", "f", "report")])
            return self._res(["COD", "DENUMIREA"], [(1, "Toner"), (2, None)])
        with mock.patch("models.biro26_db.Biro26DB.execute_query", side_effect=fake):
            r = S.to_csv("stoc")
        self.assertTrue(r["success"], r)
        lines = r["csv"].splitlines()
        self.assertEqual(lines[0], "COD;DENUMIREA")
        self.assertEqual(lines[1], "1;Toner")
        self.assertEqual(lines[2], "2;")

    def test_no_tuple_indexing_left(self):
        src = open(os.path.join(ROOT, "models", "biro26_services.py"), encoding="utf-8").read()
        import re
        self.assertIsNone(re.search(r"\brows\[0\]\[\d\]|\br\[\d\]", src),
                          "indexare pe tuple ramasa in biro26_services.py")


class TestSiteConfigTimeAlias(unittest.TestCase):
    """RO: `_t` e aliasul modulului time in _config_load; nu se refoloseste."""

    def test_alias_not_shadowed(self):
        src = open(os.path.join(ROOT, "models", "biro26_site.py"), encoding="utf-8").read()
        self.assertNotIn("_t, _html = _wp(", src)

"""Testele modulului Partner API.

RO: intii cele DOUA teste de izolare cerute de CLAUDE.md (dupa modelul
tests/test_seoforge.py), apoi regulile pure — fara wallet Oracle.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestPartnerIsolation(unittest.TestCase):
    """RO: modulul nu lasa nimic in codul comun."""

    def test_app_py_not_touched(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertNotIn("modules.partner", src)
        self.assertNotIn("partner_api", src)
        self.assertNotIn("PAPI_", src)

    def test_common_installer_not_touched(self):
        # RO: "partners" apare legitim la planograme (PLG_) — verificam
        #     markerii PROPRII modulului, nu cuvintul generic.
        src = open(os.path.join(ROOT, "deploy_oracle_objects.py"),
                   encoding="utf-8").read()
        self.assertNotIn("PAPI", src)
        self.assertNotIn("modules/partner", src)
        self.assertNotIn("papi_core", src)


class TestPartnerRules(unittest.TestCase):

    def test_password_roundtrip(self):
        from modules.partner import rules
        h = rules.hash_password("s3cret!")
        self.assertTrue(rules.verify_password("s3cret!", h))
        self.assertFalse(rules.verify_password("wrong", h))
        self.assertFalse(rules.verify_password("s3cret!", "garbage"))

    def test_token_hash_stable(self):
        from modules.partner import rules
        t = rules.new_token()
        self.assertGreaterEqual(len(t), 50)
        self.assertEqual(rules.token_hash(t), rules.token_hash(t))
        self.assertEqual(len(rules.token_hash(t)), 64)

    def test_map_product_shape(self):
        from modules.partner import rules
        row = {"cod": 225712, "codvechi": "GA82543", "denumirea": "Test",
               "namerus": "Тест", "barcode": "4840010000029", "brand": "HP",
               "grupa": "Cartus Toner", "categorie": "Toner",
               "retail1": "95.5", "angro": 80, "avail_cant": 12,
               "image": "https://x/y.jpg", "denum_full": "desc"}
        p = rules.map_product(row)
        self.assertEqual(p["code"], "GA82543")
        self.assertEqual(p["uuid"], "225712")
        self.assertEqual(p["quantity"], 12)
        self.assertEqual(p["fixed_price"], 95.5)
        self.assertEqual(p["user_price"], 80.0)
        self.assertEqual(p["category"]["hierarchy"],
                         ["Cartus Toner", "Toner"])
        self.assertEqual(p["image_urls"], ["https://x/y.jpg"])

    def test_validate_order(self):
        from modules.partner import rules
        ok = {"delivery": "pickup", "payment": "cash",
              "products": [{"code": "X", "quantity": 1}]}
        self.assertEqual(rules.validate_order(ok), {})
        bad = {"delivery": "teleport", "payment": "gold", "products": []}
        errs = rules.validate_order(bad)
        self.assertIn("delivery", errs)
        self.assertIn("payment", errs)
        self.assertIn("products", errs)
        no_qty = {"delivery": "pickup", "payment": "cash",
                  "products": [{"code": "X", "quantity": 0}]}
        self.assertIn("products.0.quantity", rules.validate_order(no_qty))


if __name__ == "__main__":
    unittest.main()

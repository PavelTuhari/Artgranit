"""Testele modulului e-Factura: izolarea + logica pura (fara wallet Oracle)."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestEfacturaIsolation(unittest.TestCase):
    """RO: modulul nu lasa nimic in codul comun (regula nr. 1)."""

    def test_app_py_not_touched(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertNotIn("modules.efactura", src)
        self.assertNotIn("EFA_", src)

    def test_common_installer_not_touched(self):
        src = open(os.path.join(ROOT, "deploy_oracle_objects.py"),
                   encoding="utf-8").read()
        self.assertNotIn("EFA_", src)
        self.assertNotIn("modules/efactura", src)
        self.assertNotIn("efa_core", src)


class TestInvoiceXml(unittest.TestCase):

    DOC = {"nrmanual": "A-86", "client_idno": "1003600050218",
           "client_name": 'SRL "Test & Co"', "client_address": "Chisinau",
           "total": 20159.0, "total_fara_tva": 16799.17, "tva": 3359.83,
           "tva_rate": 20,
           "items": [{"cod": "GA82543", "name": "Toner <HP>", "qty": 2,
                      "um": "buc.", "price": 95.5, "sum": 191.0}]}
    SELLER = {"idno": "1004600069507", "name": "OfficePlus SRL",
              "address": "Chisinau", "iban": "MD00AG000000000000000000",
              "bank_code": "AGRNMD2X"}

    def test_xml_wellformed_and_escaped(self):
        from xml.etree import ElementTree as ET
        from modules.efactura.sfs import build_invoice_xml
        xml = build_invoice_xml(self.DOC, self.SELLER, seria="AA")
        root = ET.fromstring(xml)               # RO: trebuie sa fie XML valid
        inv = root.find("Invoice")
        self.assertEqual(inv.findtext("Number"), "A-86")
        self.assertEqual(inv.findtext("Seria"), "AA")
        self.assertEqual(inv.find("Supplier").findtext("IDNO"),
                         "1004600069507")
        self.assertEqual(inv.find("Buyer").findtext("IDNO"), "1003600050218")
        # RO: caracterele periculoase nu strica documentul
        self.assertEqual(inv.find("Buyer").findtext("Name"), 'SRL "Test & Co"')
        line = inv.find("Lines").find("InvoiceLine")
        self.assertEqual(line.findtext("ProductName"), "Toner <HP>")
        self.assertEqual(line.findtext("Amount"), "191.00")
        self.assertEqual(inv.findtext("TotalAmount"), "20159.00")

    def test_missing_numbers_do_not_break(self):
        from xml.etree import ElementTree as ET
        from modules.efactura.sfs import build_invoice_xml
        xml = build_invoice_xml({"items": [{"name": "x"}]}, {})
        ET.fromstring(xml)                      # nu arunca


class TestSfsClientGuards(unittest.TestCase):

    def test_not_configured_returns_message_not_exception(self):
        from modules.efactura.sfs import SfsClient
        c = SfsClient("", "", "")
        self.assertFalse(c.configured())
        r = c.call("PostInvoices", "<request/>")
        self.assertFalse(r["success"])
        self.assertIn("nu e configurata", r["error"])

    def test_envelope_has_ws_security(self):
        from modules.efactura.sfs import SfsClient
        c = SfsClient("https://x/y.svc", "user", "p&ss")
        env = c._envelope("PostInvoices", "<request/>")
        self.assertIn("wsse:UsernameToken", env)
        self.assertIn("<wsse:Username>user</wsse:Username>", env)
        self.assertIn("p&amp;ss", env)          # parola escapata
        from xml.etree import ElementTree as ET
        ET.fromstring(env)                      # plicul e XML valid

    def test_fault_message_extracted(self):
        from modules.efactura.sfs import SfsClient
        raw = ('<s:Envelope xmlns:s="x"><s:Body><s:Fault>'
               '<faultstring>Invalid credentials</faultstring>'
               '</s:Fault></s:Body></s:Envelope>')
        self.assertEqual(SfsClient._fault(raw), "Invalid credentials")


if __name__ == "__main__":
    unittest.main()


class TestTestInvoice(unittest.TestCase):
    """RO: plafonul probei se verifica pe SERVER — formularul poate fi ocolit."""

    BASE = {"seller": {"idno": "1026602001837", "name": "Firma mea"},
            "buyer": {"idno": "1003600050218", "name": "Client test"},
            "tva_rate": 20}

    def _p(self, qty, price, **kw):
        d = dict(self.BASE)
        d["lines"] = [{"name": "Serviciu de test", "um": "buc.",
                       "qty": qty, "price": price}]
        d.update(kw)
        return d

    def test_amount_limits(self):
        from modules.efactura import testff
        self.assertEqual(testff.validate(self._p(1, 1.00)), {})      # 1 leu
        self.assertEqual(testff.validate(self._p(1, 0.01)), {})      # un ban
        self.assertEqual(testff.validate(self._p(1, 10.00)), {})     # pragul
        self.assertIn("total", testff.validate(self._p(1, 10.01)))   # peste
        self.assertIn("total", testff.validate(self._p(1, 0)))       # zero
        self.assertIn("total", testff.validate(self._p(3, 4.00)))    # 12 lei

    def test_required_fields(self):
        from modules.efactura import testff
        d = self._p(1, 1.00)
        d["seller"] = {"name": "x"}
        self.assertIn("seller.idno", testff.validate(d))
        d = self._p(1, 1.00)
        d["lines"] = [{"name": "", "qty": 1, "price": 1}]
        self.assertIn("lines.0.name", testff.validate(d))
        d = self._p(1, 1.00)
        d["lines"] = []
        self.assertIn("lines", testff.validate(d))

    def test_build_and_xml(self):
        from xml.etree import ElementTree as ET
        from modules.efactura import testff
        p = self._p(2, 1.50, seria="TT", number="TEST-1")   # 3.00 lei
        doc = testff.build(p)
        self.assertEqual(doc["total"], 3.00)
        self.assertEqual(doc["tva"], 0.50)                  # 20% inclus
        self.assertEqual(doc["total_fara_tva"], 2.50)
        r = testff.preview(p)
        self.assertTrue(r["success"])
        inv = ET.fromstring(r["data"]["xml"]).find("Invoice")
        self.assertEqual(inv.findtext("Number"), "TEST-1")
        self.assertEqual(inv.findtext("Seria"), "TT")
        self.assertEqual(inv.find("Supplier").findtext("IDNO"),
                         "1026602001837")
        self.assertEqual(inv.findtext("TotalAmount"), "3.00")

    def test_preview_works_without_credentials(self):
        """RO: XML-ul se vede si cind integrarea nu e configurata."""
        from modules.efactura import testff
        r = testff.preview(self._p(1, 0.05))
        self.assertTrue(r["success"])
        self.assertIn("<Invoice>", r["data"]["xml"])


class TestSfsProtocolValues(unittest.TestCase):
    """RO: valorile din ghidul SFS — roluri si statut sint NUMERE."""

    def test_post_body_uses_integers(self):
        from modules.efactura import sfs
        c = sfs.SfsClient("https://x/y.svc", "u", "p")
        env = c._envelope("PostInvoices",
                          "<request><ActorRole>1</ActorRole>"
                          "<InvoicesXmlStatus>0</InvoicesXmlStatus></request>")
        self.assertIn("<ActorRole>1</ActorRole>", env)
        self.assertIn("<InvoicesXmlStatus>0</InvoicesXmlStatus>", env)
        self.assertEqual(sfs.ROLE_SUPPLIER, 1)
        self.assertEqual(sfs.XML_UNSIGNED, 0)
        self.assertEqual(sfs.SIGN_FIRST, 1)
        self.assertEqual(sfs.SIGN_SECOND, 2)


class TestTemplateJs(unittest.TestCase):
    """RO: JS-ul din sabloane trebuie sa se parseze — o ghilimea gresit
    escapata opreste TOT scriptul si pagina ramane moarta (31.08.2026)."""

    TPL = os.path.join(ROOT, "modules", "efactura", "templates")

    def _blocks(self, name):
        import re
        src = open(os.path.join(self.TPL, name), encoding="utf-8").read()
        for blk in re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
                              src, re.S):
            js = re.sub(r"\{\{[^}]*\}\}", "1", blk)
            yield re.sub(r"\{%.*?%\}", "", js, flags=re.S)

    def test_inline_js_parses(self):
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node")
        if not node:
            self.skipTest("node lipseste")
        for name in ("efactura_test.html", "efactura_admin.html"):
            for js in self._blocks(name):
                with tempfile.NamedTemporaryFile("w", suffix=".js",
                                                 delete=False) as fh:
                    fh.write(js)
                    path = fh.name
                try:
                    r = subprocess.run([node, "--check", path],
                                       capture_output=True, text=True)
                finally:
                    os.unlink(path)
                self.assertEqual(r.returncode, 0,
                                 "%s: %s" % (name, r.stderr[:300]))

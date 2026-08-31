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

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
    """RO: XML-ul urmeaza XSD-ul OFICIAL (docs/Partner/sfs/TaxInvoiceSchema.xsd).
    Prima proba reala (02.09.2026) a fost respinsa: «The 'Invoices' element is
    not declared» — radacina noastra era inventata."""

    DOC = {"nrmanual": "A-86", "client_idno": "1003600050218",
           "client_name": 'SRL "Test & Co"', "client_address": "Chisinau",
           "total": 20159.0, "total_fara_tva": 16799.17, "tva": 3359.83,
           "tva_rate": 20, "issue_date": "2026-09-02",
           "items": [{"cod": "GA82543", "name": "Toner <HP>", "qty": 2,
                      "price": 95.5, "sum": 191.0},
                     {"cod": "X1", "name": "Hirtie", "qty": 1,
                      "price": 19968.0, "sum": 19968.0}]}
    SELLER = {"idno": "1003600116460", "name": '"UNISIM-SOFT" S.R.L.',
              "address": "Alba Iulia 75/b", "iban": "MD22ML000000222442000432",
              "bank_code": "MOLDMD2X303", "bank_name": "Moldindconbank"}

    def _xml(self):
        from modules.efactura import sfs
        return sfs.build_invoice_xml(self.DOC, self.SELLER, seria="AA", number="A-86")

    def test_structure_follows_the_official_schema(self):
        from xml.etree import ElementTree as ET
        root = ET.fromstring(self._xml())
        self.assertEqual(root.tag, "Documents")
        inf = root.find("Document/SupplierInfo")
        self.assertIsNotNone(inf)
        # RO: ordinea din xs:sequence — Seria, Number, IssuedDate, DeliveryDate,
        #     Supplier, Buyer, Total, TotalTVA, Merchandises, CreationMotiv
        tags = [c.tag for c in inf]
        self.assertEqual(tags, ["Seria", "Number", "IssuedDate", "DeliveryDate",
                                "Supplier", "Buyer", "VehicleLogbook",
                                "Redirections", "Total", "TotalTVA",
                                "Merchandises", "CreationMotiv"])
        self.assertEqual(inf.findtext("Number"), "A-86")
        self.assertTrue(inf.findtext("DeliveryDate").startswith("2026-09-02T"))
        sup = inf.find("Supplier")
        self.assertEqual(sup.get("IDNO"), "1003600116460")
        self.assertEqual(sup.get("TaxpayerType"), "1")
        self.assertEqual(sup.find("BankAccount").get("Account"),
                         "MD22ML000000222442000432")
        buy = inf.find("Buyer")
        self.assertEqual(buy.get("IDNO"), "1003600050218")
        self.assertEqual(buy.get("Title"), 'SRL "Test & Co"')     # ghilimele in atribut
        rows = inf.findall("Merchandises/Row")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].get("Name"), "Toner <HP>")
        self.assertEqual(rows[0].get("TotalPrice"), "191.00")
        self.assertEqual(rows[0].get("TotalPriceWithoutTVA"), "159.17")
        self.assertEqual(rows[0].get("TotalTVA"), "31.83")
        self.assertEqual(rows[0].get("TVA"), "20")
        self.assertEqual(inf.findtext("Total"), "20159.00")
        self.assertEqual(inf.findtext("CreationMotiv"), "4")   # Livrare

    def test_validates_against_the_official_xsd(self):
        """RO: validare cu xmllint fata de XSD-ul descarcat de la SFS — proba
        locala a ceea ce mediul lor de proba ar respinge."""
        import shutil
        import subprocess
        xsd = os.path.join(ROOT, "docs", "Partner", "sfs", "TaxInvoiceSchema.xsd")
        if not shutil.which("xmllint") or not os.path.exists(xsd):
            self.skipTest("xmllint sau XSD-ul lipsesc")
        r = subprocess.run(["xmllint", "--noout", "--schema", xsd, "-"],
                           input=self._xml().encode("utf-8"),
                           capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[:800])

    def test_missing_numbers_do_not_break(self):
        from modules.efactura import sfs
        xml = sfs.build_invoice_xml({"items": [{"name": "x"}]}, {"idno": "1"})
        self.assertIn("<Documents>", xml)
        self.assertIn("<Seria></Seria><Number></Number>", xml)   # mereu prezente
        self.assertIn('TotalPrice="0.00"', xml)

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
        inf = ET.fromstring(r["data"]["xml"]).find("Document/SupplierInfo")
        self.assertEqual(inf.findtext("Number"), "TEST-1")
        self.assertEqual(inf.findtext("Seria"), "TT")
        self.assertEqual(inf.find("Supplier").get("IDNO"), "1026602001837")
        self.assertEqual(inf.findtext("Total"), "3.00")
        self.assertEqual(inf.findtext("TotalTVA"), "0.50")
        row = inf.find("Merchandises/Row")
        self.assertEqual(row.get("TotalPriceWithoutTVA"), "2.50")

    def test_preview_works_without_credentials(self):
        """RO: XML-ul se vede si cind integrarea nu e configurata."""
        from modules.efactura import testff
        r = testff.preview(self._p(1, 0.05))
        self.assertTrue(r["success"])
        self.assertIn("<Documents>", r["data"]["xml"])


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


class TestAdHocApiAccount(unittest.TestCase):
    """RO: pagina probei merge NUMAI pe contul scris in formular — nu se
    leaga de setarile vreunui magazin (31.08.2026)."""

    SAVED = {"endpoint": "https://sfs-salvat/svc", "namespace": "http://x/",
             "username": "salvat1", "password": "p-salvat1",
             "username2": "salvat2", "password2": "p-salvat2", "seria": "FT"}

    def _p(self, api):
        return {"seller": {"idno": "1003600116460", "name": "Test SRL"},
                "buyer": {"idno": "1012600013725", "name": "Client SRL"},
                "lines": [{"name": "Serviciu", "qty": 1, "price": 1.0}],
                "api": api}

    def test_form_account_is_used(self):
        from modules.efactura import sfs
        c = sfs.SfsClient.from_api({"username": "director", "password": "p1"})
        self.assertEqual((c.username, c.password), ("director", "p1"))

    def test_default_endpoint_is_sfs_test_env(self):
        """RO: implicit — mediul de PROBA al SFS (adresele din ghidul de
        integrare, verificate 31.08.2026), nu adresa din setari."""
        from modules.efactura import sfs
        c = sfs.SfsClient.from_api({"username": "u", "password": "p"})
        self.assertEqual(c.endpoint, sfs.TEST_ENDPOINT)
        self.assertEqual(sfs.ENDPOINT_TEST,
                         "https://apiefactura-pre.sfs.md/Service.svc")
        self.assertEqual(sfs.ENDPOINT_PROD,
                         "https://efactura-api.sfs.md/Service.svc")

    def test_second_signer_falls_back_to_first_of_the_form(self):
        """RO: un singur cont in formular = ambele cozi pe el; niciodata pe
        contul salvat al firmei (altfel s-ar amesteca doi oameni)."""
        from modules.efactura import sfs
        c = sfs.SfsClient.from_api({"username": "director", "password": "p1"},
                                   signer=2)
        self.assertEqual(c.username, "director")

    def test_second_signer_own_account(self):
        from modules.efactura import sfs
        c = sfs.SfsClient.from_api({"username": "u1", "password": "p1",
                                    "username2": "u2", "password2": "p2"},
                                   signer=2)
        self.assertEqual((c.username, c.password), ("u2", "p2"))

    def test_send_refuses_without_account(self):
        """RO: fara utilizator/parola — refuz clar, fara apel in retea."""
        from unittest import mock
        from modules.efactura import testff
        with mock.patch("modules.efactura.sfs.SfsClient.post_invoices") as post:
            r = testff.send(self._p({"username": "fara-parola"}))
        self.assertFalse(r["success"])
        self.assertIn("contul API", r["error"])
        post.assert_not_called()

    def test_test_page_never_reads_shop_settings(self):
        """RO: garantia decuplarii — daca EFA_SETTING ar exploda, proba
        trebuie sa mearga oricum: preview-ul si trimiterea nu-l citesc."""
        from unittest import mock
        from modules.efactura import testff

        def boom(*a, **k):
            raise AssertionError("pagina probei a citit setarile magazinului")

        with mock.patch("modules.efactura.store.EfaStore.settings",
                        side_effect=boom), \
             mock.patch("modules.efactura.store.EfaStore.log"), \
             mock.patch("modules.efactura.sfs.SfsClient.post_invoices",
                        return_value={"success": True, "parsed": {}}):
            self.assertTrue(testff.preview(self._p(None))["success"])
            self.assertTrue(testff.send(
                self._p({"username": "u", "password": "p"}))["success"])

    def test_page_template_has_no_shop_coupling(self):
        """RO: sablonul probei nu are voie sa citeasca setarile magazinului,
        datele din ERP-ul lui, nici adresa portalului scrisa cu mina."""
        src = open(os.path.join(ROOT, "modules", "efactura", "templates",
                                "efactura_test.html"), encoding="utf-8").read()
        for token in ("settings.", "firm.", "/UNA.md/orasldev/"):
            self.assertNotIn(token, src, "cuplare interzisa: %s" % token)

    def test_ping_separates_address_from_account(self):
        """RO: gazda inexistenta = problema de ADRESA, spusa asa, nu «cont
        gresit» de trei ori (31.08.2026: api-test.fisc.md nu se rezolva)."""
        from modules.efactura import testff
        r = testff.ping({"username": "u", "password": "p",
                         "endpoint": "https://nu-exista.invalid/Service.svc"})
        a = r["data"]["adresa"]
        self.assertFalse(a["ok"])
        self.assertIn("DNS", a["reply"])
        self.assertNotIn("prima_semnatura", r["data"])


class TestSoapMatchesWsdl(unittest.TestCase):
    """RO: plicul trebuie sa respecte contractul VIU al serviciului
    (`?wsdl` / `?xsd=xsd2`, citit 31.08.2026). Greselile de aici nu se vad
    la testare locala — se vad abia cind SFS refuza apelul."""

    def _c(self):
        from modules.efactura import sfs
        return sfs.SfsClient(sfs.ENDPOINT_PROD, "u", "p")

    def test_request_children_are_in_datacontract_namespace(self):
        """RO: copiii lui <request> in tempuri = WCF ii citeste ca null."""
        from modules.efactura import sfs
        body = sfs._request([("RequestId", "x"), ("ActorRole", 1)])
        self.assertIn('xmlns:a="%s"' % sfs.NS_DC, body)
        self.assertIn("<a:RequestId>x</a:RequestId>", body)
        self.assertIn("<a:ActorRole>1</a:ActorRole>", body)

    def test_post_invoices_field_order(self):
        """RO: DataContractSerializer cere intii membrii clasei de baza:
        RequestId, ActorRole, apoi InvoicesXml, InvoicesXmlStatus."""
        from unittest import mock
        c = self._c()
        with mock.patch.object(c, "call",
                               return_value={"success": True}) as call:
            c.post_invoices("<Invoice/>")
        body = call.call_args[0][1]
        pos = [body.index("<a:%s>" % f) for f in
               ("RequestId", "ActorRole", "InvoicesXml", "InvoicesXmlStatus")]
        self.assertEqual(pos, sorted(pos))

    def test_soap_action_includes_contract_name(self):
        """RO: SOAPAction e {ns}/IService/{metoda} — fara `IService` WCF
        raspunde «action not recognized»."""
        from modules.efactura import sfs
        self.assertEqual(sfs.CONTRACT, "IService")

    def test_seria_number_uses_the_array_contract(self):
        from unittest import mock
        c = self._c()
        with mock.patch.object(c, "call",
                               return_value={"success": True}) as call:
            c.get_by_seria_number("FT", "123")
        body = call.call_args[0][1]
        self.assertIn("<a:SeriaAndNumbers>", body)
        self.assertIn("<a:InvoiceIndentificator>", body)
        self.assertIn("<a:Number>123</a:Number>", body)
        self.assertIn("<a:Seria>FT</a:Seria>", body)

    def test_connection_check_uses_the_test_operation(self):
        """RO: `GetLogs` cerea `<Top>1</Top>`, cimp inexistent in contract."""
        from unittest import mock
        c = self._c()
        with mock.patch.object(c, "call",
                               return_value={"success": True}) as call:
            c.test()
        self.assertEqual(call.call_args[0][0], "Test")


class TestEgressIp(unittest.TestCase):
    """RO: SFS deschide accesul pe IP, iar apelul il face SERVERUL — deci
    verificarea trebuie sa arate adresa serverului, nu a statiei."""

    def test_ping_shows_server_ip(self):
        from unittest import mock
        from modules.efactura import testff
        testff._EGRESS.clear()
        with mock.patch("modules.efactura.testff._egress_ip",
                        return_value="203.0.113.7"), \
             mock.patch("modules.efactura.testff._reach",
                        return_value={"configured": True, "ok": False,
                                      "reply": "test"}):
            r = testff.ping({"username": "u", "password": "p"})
        self.assertEqual(r["data"]["ip_server"]["reply"][:11], "203.0.113.7")
        self.assertIn("asistenta@sfs.md", r["data"]["ip_server"]["reply"])


class TestMaskedFault(unittest.TestCase):
    """RO: portalul SFS inlocuieste orice raspuns 500 (fault SOAP) cu o pagina
    HTML, iar 403 e filtrul de IP — mesajul trebuie sa le deosebeasca
    (masurat 02.09.2026: POST gol -> 400, SOAP 1.2 -> 415, fault -> 500 HTML)."""

    def _call(self, code):
        import io
        import urllib.error
        from unittest import mock
        from modules.efactura import sfs
        c = sfs.SfsClient(sfs.ENDPOINT_TEST, "u", "p")
        err = urllib.error.HTTPError(c.endpoint, code, "x", {},
                                     io.BytesIO(b"<!DOCTYPE html><html>500</html>"))
        # RO: apelul simulat NU are voie sa scrie in jurnalul REAL (EFA_CALL)
        #     — 02.09.2026 testele lasau rinduri «u / html» in productie.
        with mock.patch("urllib.request.urlopen", side_effect=err), \
             mock.patch("modules.efactura.journal.record"):
            return c.call("Test", "<message>ping</message>")

    def test_403_means_ip(self):
        r = self._call(403)
        self.assertFalse(r["success"])
        self.assertIn("IP", r["error"])

    def test_500_means_masked_soap_fault(self):
        r = self._call(500)
        self.assertFalse(r["success"])
        self.assertIn("parola", r["error"])
        self.assertNotIn("IP-ul", r["error"])


class TestQueueParsing(unittest.TestCase):
    """RO: raspunsul REAL al cozii de semnare (02.09.2026) -> lista lizibila."""

    RAW = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
           '<GetInvoicesForSigningResponse xmlns="http://tempuri.org/">'
           '<GetInvoicesForSigningResult xmlns:a="http://schemas.datacontract.org/2004/07/AX.EFactura.Model.ApiModel"'
           ' xmlns:i="http://www.w3.org/2001/XMLSchema-instance"><a:Status>2</a:Status><a:Results>'
           '<a:XmlInvoice><a:Number/><a:Seria/><a:Status>2</a:Status><a:InvoiceStatus>0</a:InvoiceStatus>'
           '<a:Xml>&lt;Document&gt;&lt;SupplierInfo&gt;&lt;Seria /&gt;&lt;Buyer IDNO="1" Title="&amp;quot;UNISIM-SOFT&amp;quot; S.R.L."/&gt;'
           '&lt;Total&gt;1.00&lt;/Total&gt;&lt;Merchandises&gt;&lt;Row Name="Serviciu de test" TotalPrice="1.00" /&gt;'
           '&lt;/Merchandises&gt;&lt;/SupplierInfo&gt;&lt;/Document&gt;</a:Xml></a:XmlInvoice>'
           '</a:Results></GetInvoicesForSigningResult></GetInvoicesForSigningResponse></s:Body></s:Envelope>')

    def test_parses_real_reply(self):
        from modules.efactura import testff
        inv = testff.queue_invoices(self.RAW)
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["total"], "1.00")
        self.assertEqual(inv[0]["invoice_status"], "0")           # nesemnata
        self.assertEqual(inv[0]["first_row"], "Serviciu de test")
        self.assertIn("UNISIM-SOFT", inv[0]["buyer"])

    def test_empty_or_broken_reply(self):
        from modules.efactura import testff
        self.assertEqual(testff.queue_invoices(""), [])
        self.assertEqual(testff.queue_invoices("<x/>"), [])


class TestBackofficeMapping(unittest.TestCase):
    """RO: lectiile contului real A-88 (02.09.2026)."""

    def test_taxpayer_type_inferred_from_idnp(self):
        from xml.etree import ElementTree as ET
        from modules.efactura import sfs
        xml = sfs.build_invoice_xml(
            {"items": [{"name": "x", "qty": 1, "price": 1, "sum": 1}],
             "client_idno": "2003004025284", "client_name": "Persoana"},
            {"idno": "1026602001837", "name": "Firma"})
        inf = ET.fromstring(xml).find("Document/SupplierInfo")
        self.assertEqual(inf.find("Supplier").get("TaxpayerType"), "1")
        self.assertEqual(inf.find("Buyer").get("TaxpayerType"), "2")
        self.assertIsNotNone(inf.find("Buyer/BankAccount"))   # mereu prezent

    def test_tva_rate_from_document(self):
        from modules.efactura.controller import EfaController as C
        self.assertEqual(C._tva_rate(1200.0, 200.0, {}), 20.0)
        self.assertEqual(C._tva_rate(1080.0, 80.0, {}), 8.0)
        self.assertEqual(C._tva_rate(20149.0, 0.0, {"tva_rate": "20"}), 20.0)
        self.assertEqual(C._tva_rate(100.0, 0.0, {"tva_rate": "0"}), 0.0)


class TestDateWindow(unittest.TestCase):
    """RO: regula SFS (raspuns real 02.09.2026): IssuedDate intre azi si
    azi+10 zile; documentele vechi se refuza INAINTE de apel, in romana."""

    def test_window(self):
        import datetime
        from modules.efactura.controller import EfaController as C
        today = datetime.date.today()
        self.assertIsNone(C.date_window_error(today.isoformat()))
        self.assertIsNone(C.date_window_error((today + datetime.timedelta(days=10)).isoformat()))
        self.assertIn("în trecut", C.date_window_error((today - datetime.timedelta(days=1)).isoformat()))
        self.assertIn("viitor", C.date_window_error((today + datetime.timedelta(days=11)).isoformat()))
        self.assertIn("invalid", C.date_window_error(""))

    def test_override_wins(self):
        import datetime
        from modules.efactura.controller import EfaController as C
        self.assertIsNone(C.date_window_error("2026-08-19", override_date=datetime.date.today().isoformat()))


class TestNativeApiMount(unittest.TestCase):
    """RO: API-ul pentru una.md sta la radacina (/api/biro26/efactura/…) prin
    root_blueprint — singurul prefix care trece pe HTTP simplu de intrarea
    officeplus.md (Oracle 11g nu are wallet TLS). Manifestul si blueprint-ul
    trebuie sa spuna acelasi lucru, altfel nucleul refuza montarea."""

    def test_manifest_matches_blueprint(self):
        import json
        from modules import efactura
        from modules.efactura import native_api
        self.assertTrue(hasattr(efactura, "root_blueprint"))
        man = json.load(open(os.path.join(ROOT, "modules", "efactura", "module.json"),
                             encoding="utf-8"))
        self.assertEqual(sorted(man.get("root_paths") or []),
                         sorted(native_api.ROOT_PATHS))
        for p in native_api.ROOT_PATHS:
            self.assertTrue(p.startswith("/api/biro26/efactura/"), p)

    def test_no_shared_file_touched(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertNotIn("efactura", src)


class TestIdnoCheckDigit(unittest.TestCase):
    """RO: cifra de control IDNO — clientii fictivi pica local, nu la SFS."""

    def test_real_and_fake(self):
        from modules.efactura.rules import idno_valid, idno_error
        for good in ("1003600116460", "1012600013725", "1008602003648", "1007601010378"):
            self.assertTrue(idno_valid(good), good)
        self.assertFalse(idno_valid("1026602001999"))      # «SRL TEST Casa Operator»
        self.assertFalse(idno_valid("1234567890123"))
        self.assertFalse(idno_valid(""))
        self.assertIn("cifra de control", idno_error("1026602001999"))
        self.assertIsNone(idno_error("1003600116460"))

    def test_probe_rejects_bad_buyer_idno(self):
        from modules.efactura import testff
        e = testff.validate({"seller": {"idno": "1003600116460", "name": "x"},
                             "buyer": {"idno": "1026602001999", "name": "y"},
                             "lines": [{"name": "s", "qty": 1, "price": 1}]})
        self.assertIn("buyer.idno", e)

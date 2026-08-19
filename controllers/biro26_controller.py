"""Biro26 module controller — thin HTTP handlers.

All methods @staticmethod, return {success, data?/output?, error?}.
Destructive package operations (import/archive/rollback/merge/prepare/assign)
mutate the live OfficePlus ERP; the UI gates them behind confirmation.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request, session

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import Biro26Store, G_PARAMS, _rows
from models.biro26_sources import Biro26Sources
from models import biro26_ai


class Biro26Controller:

    # -- connection / mapping ----------------------------------------
    @staticmethod
    def connection_test() -> Dict[str, Any]:
        return Biro26Store.test_connection()

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        return Biro26Store.get_profiles()

    @staticmethod
    def get_profile(profile_id: int) -> Dict[str, Any]:
        return Biro26Store.get_profile(profile_id)

    @staticmethod
    def create_profile() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name"):
            return {"success": False, "error": "name is required"}
        params = {k: v for k, v in (d.get("params") or {}).items() if k in G_PARAMS}
        return Biro26Store.create_profile(d["name"], d.get("codprice", 1), params)

    @staticmethod
    def update_profile(profile_id: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        params = {k: v for k, v in (d.get("params") or {}).items() if k in G_PARAMS}
        return Biro26Store.update_profile(profile_id, params, d.get("codprice"))

    @staticmethod
    def activate_profile(profile_id: int) -> Dict[str, Any]:
        return Biro26Store.activate_profile(profile_id)

    @staticmethod
    def list_g_params() -> Dict[str, Any]:
        return {"success": True, "data": G_PARAMS}

    # -- source feed --------------------------------------------------
    @staticmethod
    def get_goods() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_goods(
            search=a.get("search"), brand=a.get("brand"),
            furnizor=a.get("furnizor"), status=a.get("status"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def goods_brands() -> Dict[str, Any]:
        return Biro26Store.goods_brands()

    @staticmethod
    def goods_count() -> Dict[str, Any]:
        return Biro26Store.goods_count()

    @staticmethod
    def validate_input() -> Dict[str, Any]:
        return Biro26Store.validate_input()

    @staticmethod
    def prepare_input() -> Dict[str, Any]:
        return Biro26Store.prepare_input()

    @staticmethod
    def assign_keys() -> Dict[str, Any]:
        return Biro26Store.assign_keys()

    # -- sources (any SELECT) ----------------------------------------
    @staticmethod
    def list_sources() -> Dict[str, Any]:
        return Biro26Sources.list_sources()

    @staticmethod
    def sample_select() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Sources.sample(d.get("sql", ""), d.get("limit", 20))

    @staticmethod
    def create_source() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name") or not d.get("sql"):
            return {"success": False, "error": "name and sql are required"}
        md = d.get("md")
        md_path = None
        if md:
            import os as _os
            sd = _os.path.join(_os.path.dirname(__file__), "..", "docs", "Biro26", "sources")
            _os.makedirs(sd, exist_ok=True)
            md_path = f"docs/Biro26/sources/{d['name']}.md"
            with open(_os.path.join(sd, f"{d['name']}.md"), "w", encoding="utf-8") as f:
                f.write(md)
        return Biro26Sources.create_source(d["name"], d["sql"], md_path)

    @staticmethod
    def ai_draft_md() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        md = biro26_ai.draft_source_md(d.get("name", "source"), s["columns"], s["data"])
        return {"success": True, "data": {"md": md, "columns": s["columns"]}}

    @staticmethod
    def ai_suggest_mapping() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        r = biro26_ai.suggest_mapping(s["columns"], s["data"], d.get("md", ""))
        r["columns"] = s["columns"]
        return r

    @staticmethod
    def source_columns() -> Dict[str, Any]:
        return Biro26Store.source_columns(request.args.get("source", "BIRO26_GOODS"))

    @staticmethod
    def source_sample() -> Dict[str, Any]:
        return Biro26Store.source_sample(
            request.args.get("source", "BIRO26_GOODS"),
            request.args.get("limit", 20, type=int))

    # -- dictionary ---------------------------------------------------
    @staticmethod
    def get_univers() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_univers(
            search=a.get("search"), gr1=a.get("gr1"), arhiv=a.get("arhiv"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_univers_card(cod: int) -> Dict[str, Any]:
        return Biro26Store.get_univers_card(cod)

    @staticmethod
    def import_univers() -> Dict[str, Any]:
        return Biro26Store.import_univers()

    @staticmethod
    def import_images() -> Dict[str, Any]:
        return Biro26Store.import_images()

    @staticmethod
    def archive_univers() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        isarhiv = str(d.get("isarhiv", "1"))
        if isarhiv == "2":
            return {"success": False, "error": "ISARHIV='2' is blocked by trigger"}
        return Biro26Store.archive_univers(isarhiv)

    @staticmethod
    def fix_confusables() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.fix_denumirea_confusables(d.get("cod"))

    # -- groups / suppliers / categories -----------------------------
    @staticmethod
    def get_groups() -> Dict[str, Any]:
        return Biro26Store.get_groups(request.args.get("codprice", 1, type=int))

    @staticmethod
    def update_group() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "codgrp", "grpname"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.update_group(d["codprice"], d["codgrp"], d["grpname"])

    @staticmethod
    def import_groups() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_groups(d.get("codprice", 1))

    @staticmethod
    def merge_groups() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "src_codgrp", "dst_codgrp"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.merge_groups(d["codprice"], d["src_codgrp"], d["dst_codgrp"])

    @staticmethod
    def get_categories() -> Dict[str, Any]:
        return Biro26Store.get_categories()

    @staticmethod
    def get_suppliers() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_suppliers(
            search=a.get("search"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_furnizori() -> Dict[str, Any]:
        return Biro26Store.get_furnizori()

    # -- price list ---------------------------------------------------
    @staticmethod
    def get_prices() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_prices(
            codprice=a.get("codprice", 1, type=int),
            codgrp=a.get("codgrp", type=int),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_pricelists() -> Dict[str, Any]:
        return Biro26Store.get_pricelists()

    @staticmethod
    def get_dates() -> Dict[str, Any]:
        return Biro26Store.get_dates(request.args.get("codprice", 1, type=int))

    @staticmethod
    def update_price() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "codgrp", "sc", "datastart"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.update_price(
            d["codprice"], d["codgrp"], d["sc"], d["datastart"],
            d.get("pretv"), d.get("pretv1"), d.get("pretv2"))

    @staticmethod
    def import_dates() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_dates(d.get("codprice", 1), d.get("data"))

    @staticmethod
    def import_prices() -> Dict[str, Any]:
        """RO: `only_articol` (implicit din setare, ACTIVA): preturile se
        reinnoiesc DOAR pentru marfurile identificate dupa ARTICOL."""
        d = request.get_json(silent=True) or {}
        oa = d.get("only_articol")
        return Biro26Store.import_prices(
            d.get("codprice", 1), d.get("date_start"), d.get("date_end"),
            only_articol=None if oa is None else bool(oa))

    @staticmethod
    def price_by_article_get() -> Dict[str, Any]:
        return {"success": True, "data": {"on": Biro26Store.price_by_article()}}

    @staticmethod
    def price_by_article_set() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        r = Biro26Store.set_price_by_article(bool(d.get("on")))
        if not r.get("success"):
            return r
        return {"success": True, "data": {"on": Biro26Store.price_by_article()}}

    @staticmethod
    def rollback_pricelist() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.rollback_pricelist(d.get("codprice", 1))

    # -- stock balances (UN$SOLD.GET_SOLDT) ---------------------------
    @staticmethod
    def calc_stock() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("data_doc"):
            return {"success": False, "error": "data_doc is required"}
        return Biro26Store.calc_stock(
            d["data_doc"], d.get("dep_filter", ""),
            d.get("cont_filter"), d.get("pfilt"))

    @staticmethod
    def get_latest_stock_calc() -> Dict[str, Any]:
        return Biro26Store.get_latest_stock_calc()

    @staticmethod
    def get_stock_items() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_stock_items(
            limit=a.get("limit", 500, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_products_stock() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_products_stock(
            search=a.get("search"), gr1=a.get("gr1"),
            brand=a.get("brand"), categorie=a.get("categorie"),
            grupa=a.get("grupa"), cod=a.get("cod", type=int),
            price_date=a.get("price_date"),
            only_new=a.get("only_new") == "1",
            price_min=a.get("price_min", type=float),
            price_max=a.get("price_max", type=float),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int),
            with_count=a.get("with_count") == "1",
            # RO: arhiva (ISARHIV=2) e vizibila DOAR pentru sesiunile
            #     backoffice — publicul (magazinul) vede mereu doar activele
            # EN: the archive view is backoffice-only; the public shop
            #     always sees active goods regardless of the parameter
            archived=(a.get("archived") == "1"
                      and bool(session.get("username")
                               or session.get("authenticated"))),
            sort=(a.get("sort") if a.get("sort") in
                  ("name", "name_desc", "price_asc", "price_desc") else "name"))

    @staticmethod
    def product_archive(cod: int) -> Dict[str, Any]:
        """RO: dezactivare/reactivare cartela (soft-delete nativ ISARHIV).
        EN: deactivate/reactivate a card (native ISARHIV soft-delete)."""
        d = request.get_json(silent=True) or {}
        return Biro26Store.set_product_archived(cod, bool(d.get("archived", True)))

    # ── shop display settings (admin: products per page, invoice start nr) ──
    @staticmethod
    def shop_settings_get() -> Dict[str, Any]:
        # RO/EN: next invoice = counter INVOICE_NR_START (package next_invoice_nr)
        next_nr = None
        max_nr = None
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT y_ai_BIRO26.next_invoice_nr AS n FROM dual"))
            if rows and rows[0].get("n") is not None:
                next_nr = int(rows[0]["n"])
        except Exception:
            next_nr = None
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT MAX(CASE WHEN REGEXP_LIKE(TRIM(NRMANUAL), '^[0-9]+$') "
                "THEN TO_NUMBER(TRIM(NRMANUAL)) END) AS m "
                "FROM TMDB_DOCS WHERE SYSFID = 12280"))
            if rows and rows[0].get("m") is not None:
                max_nr = int(rows[0]["m"])
        except Exception:
            max_nr = None
        return {"success": True, "data": {
            "shop_page_size": Biro26Store.get_setting("SHOP_PAGE_SIZE", "24"),
            # RO: filtrul dupa brand in catalogul noului site (OFF implicit)
            "brand_filter": Biro26Store.get_setting("SHOP_BRAND_FILTER", "0"),
            # RO: formatele de cont disponibile clientilor (PDF mereu;
            #     HTML/XLSX activabile aici); o singura optiune =>
            #     selectorul dispare din front-office
            "fmt_html": Biro26Store.get_setting("SHOP_FMT_HTML", "1"),
            "fmt_xlsx": Biro26Store.get_setting("SHOP_FMT_XLSX", "1"),
            # RO: coloana de pret per tip de client (retail1/ionline/angro)
            "price_fiz": Biro26Store.get_setting("SHOP_PRICE_FIZ", "retail1"),
            "price_jur": Biro26Store.get_setting("SHOP_PRICE_JUR", "ionline"),
            # RO/EN: counter = next NRMANUAL to issue (not max+1 floor)
            "invoice_nr_start": Biro26Store.get_setting("INVOICE_NR_START", "1"),
            "invoice_nr_max": max_nr,
            "invoice_nr_next": next_nr,
        }}

    @staticmethod
    def shop_settings_put() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        # products per page (optional in payload)
        if "shop_page_size" in d:
            try:
                n = int(d.get("shop_page_size") or 24)
            except (TypeError, ValueError):
                return {"success": False, "error": "shop_page_size must be a number"}
            if not 1 <= n <= 200:
                return {"success": False, "error": "shop_page_size: 1..200"}
            r = Biro26Store.set_setting("SHOP_PAGE_SIZE", str(n))
            if not r.get("success"):
                return r
        # RO: coloana de pret pentru fizice / juridice
        for key, skey in (("price_fiz", "SHOP_PRICE_FIZ"),
                          ("price_jur", "SHOP_PRICE_JUR")):
            if key in d:
                v = str(d.get(key))
                if v not in ("retail1", "ionline", "angro"):
                    return {"success": False,
                            "error": f"{key}: retail1 | ionline | angro"}
                r = Biro26Store.set_setting(skey, v)
                if not r.get("success"):
                    return r
        # RO: formatele HTML/XLSX disponibile clientilor (PDF mereu activ)
        for key, skey in (("fmt_html", "SHOP_FMT_HTML"),
                          ("fmt_xlsx", "SHOP_FMT_XLSX")):
            if key in d:
                v = "1" if str(d.get(key)) in ("1", "true", "True") else "0"
                r = Biro26Store.set_setting(skey, v)
                if not r.get("success"):
                    return r
        # RO: filtrul dupa brand in catalog (optiune, implicit oprit)
        if "brand_filter" in d:
            v = "1" if str(d.get("brand_filter")) in ("1", "true", "True") else "0"
            r = Biro26Store.set_setting("SHOP_BRAND_FILTER", v)
            if not r.get("success"):
                return r
        # invoice counter (next NRMANUAL to issue) · счётчик следующего № счёта
        if "invoice_nr_start" in d:
            try:
                start = int(str(d.get("invoice_nr_start")).strip())
            except (TypeError, ValueError):
                return {"success": False, "error": "invoice_nr_start must be a number"}
            if not 1 <= start <= 999999999:
                return {"success": False, "error": "invoice_nr_start: 1..999999999"}
            r = Biro26Store.set_setting("INVOICE_NR_START", str(start))
            if not r.get("success"):
                return r
        return Biro26Controller.shop_settings_get()

    # ── price periods on Marfă/Stoc (y_ai_BIRO26.set_price/del_price) ──
    @staticmethod
    def product_price_history() -> Dict[str, Any]:
        sc = request.args.get("sc", type=int)
        if not sc:
            return {"success": False, "error": "sc is required"}
        return Biro26Store.get_price_history(
            sc, request.args.get("codprice", 1, type=int))

    @staticmethod
    def product_price_set() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("sc") or not d.get("date"):
            return {"success": False, "error": "sc and date are required"}

        def num(k):
            v = d.get(k)
            if v in (None, ""):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return Biro26Store.set_product_price(
            int(d["sc"]), str(d["date"]), retail1=num("retail1"),
            angro=num("angro"), ionline=num("ionline"),
            codprice=int(d.get("codprice") or 1))

    # ── printable reports (jsReport sidecar): cont de plata / comanda ──
    @staticmethod
    def _api_token_ok() -> bool:
        """RO: acces masina-la-masina (una.md/desktop) prin X-API-Key.
        EN: machine-to-machine access (una.md/desktop) via the X-API-Key
        header (or ?api_key=); disabled while BIRO26_API_TOKEN is empty."""
        import hmac
        from config import Config
        tok = (request.headers.get("X-API-Key")
               or request.args.get("api_key") or "")
        return bool(Config.BIRO26_API_TOKEN) and \
            hmac.compare_digest(tok, Config.BIRO26_API_TOKEN)

    @staticmethod
    def shop_report(kind: str, cod: int) -> Dict[str, Any]:
        """PDF of an ERP document. Public shop clients may only print their
        own documents; a backoffice session or a valid API token — any."""
        from flask import session
        from models.biro26_report import Biro26Report
        if Biro26Controller._api_token_ok():
            return Biro26Report.render_doc(kind, cod)
        # RO: link semnat (HMAC pe kind:cod) — folosit de notificari
        #     (WhatsApp/Telegram/email) ca PDF-ul sa se deschida fara login;
        #     acorda acces DOAR la acest document.
        # EN: signed link (HMAC over kind:cod) — used by notifications so
        #     the PDF opens without login; grants access to this doc only.
        sig = request.args.get("sig") or ""
        if sig:
            import hmac
            from models.biro26_notify import Biro26Notify
            if hmac.compare_digest(sig, Biro26Notify.pdf_sig(kind, cod)):
                return Biro26Report.render_doc(kind, cod)
        c = session.get("biro26_client")
        if c:
            return Biro26Report.render_doc(kind, cod,
                                           allowed_client_cod=c["univers_cod"])
        if session.get("username") or session.get("authenticated"):
            return Biro26Report.render_doc(kind, cod)
        return {"success": False, "error": "login required"}

    @staticmethod
    def shop_report_html(kind: str, cod: int) -> Dict[str, Any]:
        """RO: formularul in HTML (aceeasi paza ca la PDF)."""
        from flask import session
        from models.biro26_report import Biro26Report
        if Biro26Controller._api_token_ok():
            return Biro26Report.render_doc_html(kind, cod)
        # RO/EN: link semnat (HMAC pe kind:cod) — ca la PDF (vezi shop_report)
        sig = request.args.get("sig") or ""
        if sig:
            import hmac
            from models.biro26_notify import Biro26Notify
            if hmac.compare_digest(sig, Biro26Notify.pdf_sig(kind, cod)):
                return Biro26Report.render_doc_html(kind, cod)
        c = session.get("biro26_client")
        if c:
            return Biro26Report.render_doc_html(
                kind, cod, allowed_client_cod=c["univers_cod"])
        if session.get("username") or session.get("authenticated"):
            return Biro26Report.render_doc_html(kind, cod)
        return {"success": False, "error": "login required"}

    @staticmethod
    def shop_report_xlsx(cod: int) -> Dict[str, Any]:
        """RO: echivalentul EXCEL al contului (aceeasi paza ca la PDF):
        clientii publici doar documentele proprii; backoffice/API — orice."""
        from flask import session
        from models.biro26_report import Biro26Report
        if Biro26Controller._api_token_ok():
            return Biro26Report.render_doc_xlsx(cod)
        c = session.get("biro26_client")
        if c:
            return Biro26Report.render_doc_xlsx(
                cod, allowed_client_cod=c["univers_cod"])
        if session.get("username") or session.get("authenticated"):
            return Biro26Report.render_doc_xlsx(cod)
        return {"success": False, "error": "login required"}

    @staticmethod
    def gen_docs_by_nr(nr: str) -> Dict[str, Any]:
        """RO: genereaza SI ataseaza la document (VMDB_DOCS_OLE, ecranul
        «Object» din aplicatia nativa) contul de plata + comanda
        cumparatorului, dupa NUMARUL documentului (NRMANUAL, cu sau fara #).
        Apelat din interiorul Oracle de y_ai_BIRO26.gen_conturi (UTL_HTTP)
        sau de aplicatii desktop (X-API-Key / ?api_key=).
        EN: render + attach both forms for an existing document by number."""
        if not Biro26Controller._api_token_ok():
            return {"success": False, "error": "login required"}
        from models.biro26_report import Biro26Report
        # RO: ?cod= — COD-ul INTERN al documentului, trimis de pachetul Oracle
        #     (mereu comis, spre deosebire de NRMANUAL care poate fi tocmai
        #     atribuit in tranzactia necomisa a aplicatiei native).
        # EN: ?cod= — internal document COD sent by the Oracle package.
        cod_param = (request.args.get("cod") or "").strip()
        cod = int(cod_param) if cod_param.isdigit() else Biro26Report.resolve_nr(nr)
        if not cod:
            return {"success": False, "error": f"document '{nr}' not found"}
        d = Biro26Report.doc_data(cod)
        if not d.get("success"):
            return d
        # RO: ?nr= — numarul atribuit de y_ai_BIRO26.ensure_nrmanual, inca
        #     necomis in sesiunea apelantului: formularele l-ar tipari gol.
        # EN: ?nr= — the number just assigned by the caller, still uncommitted.
        nr_over = (request.args.get("nr") or "").strip().lstrip("#")
        if nr_over and not str(d["data"].get("number") or "").strip():
            for k in ("number", "cont_number", "nrmanual"):
                d["data"][k] = nr_over
        # RO: documentul chiar nu are numar (creat de alta aplicatie) — il
        #     atribuim automat prin y_ai_BIRO26.ensure_nrmanual (aceleasi
        #     reguli ca la emiterea unui cont nou). Asteptare LIMITATA: daca
        #     documentul e deschis in alta sesiune, raspundem clar si repede.
        # EN: assign the missing number via the package (same rules), with a
        #     bounded wait so a doc opened elsewhere fails fast and clearly.
        if not str(d["data"].get("number") or "").strip():
            nr_new = Biro26Report.assign_nrmanual(cod)
            if not nr_new:
                return {"success": False, "cod": cod,
                        "error": f"documentul COD={cod} nu are NRMANUAL si nu "
                                 f"poate fi numerotat acum (este deschis in "
                                 f"alta sesiune?)"}
            for k in ("number", "cont_number", "nrmanual"):
                d["data"][k] = nr_new
        engines = Biro26Report.get_engines()["data"]
        # RO: ?formats=pdf,html,xlsx — ORICE combinatie; implicit doar PDF.
        #     Fiecare format cerut se genereaza si se ATASEAZA la document
        #     (VMDB_DOCS_OLE): PDF/HTML pentru ambele formulare, XLSX doar
        #     pentru cont (echivalentul Excel cu formule).
        # EN: any combination of formats, each attached to the document.
        fmts = [f.strip().lower() for f in
                (request.args.get("formats") or "pdf").split(",")
                if f.strip().lower() in ("pdf", "html", "xlsx")] or ["pdf"]
        out: Dict[str, Any] = {"cod": cod, "nr": d["data"].get("number"),
                               "formats": ",".join(fmts)}
        results = []
        def step(label, res_key, res, ext):
            if not res.get("success"):
                out[label] = "RENDER_ERR: " + str(res.get("error"))[:200]
                results.append(False)
                return
            att = Biro26Report.attach_pdf(cod, label.split("_")[0],
                                          res[res_key], ext=ext)
            out[label] = ("OK" if att.get("success")
                          else "ATTACH_ERR: " + str(att.get("error"))[:200])
            results.append(att.get("success") is True)
        for kind in ("invoice", "order"):
            if "pdf" in fmts:
                res = Biro26Report.render_pdf_by_engine(kind, d["data"])
                step(f"{kind}_pdf" if len(fmts) > 1 else kind,
                     "pdf", res, "pdf")
            if "html" in fmts:
                step(f"{kind}_html", "html",
                     Biro26Report.render_html(kind, d["data"]), "html")
        if "xlsx" in fmts:
            try:
                xlsx = Biro26Report._build_invoice_xlsx(d["data"])
                step("invoice_xlsx", "x", {"success": True, "x": xlsx}, "xlsx")
            except Exception as e:
                out["invoice_xlsx"] = f"RENDER_ERR: {e}"
                results.append(False)
        out["success"] = bool(results) and all(results)
        return out

    # ── online payments: MAIB e-commerce + MIA instant payments ──

    @staticmethod
    def pay_methods() -> Dict[str, Any]:
        """Public: enabled payment methods for the shop UI."""
        from models.biro26_pay import Biro26Pay
        return Biro26Pay.public_methods()

    @staticmethod
    def pay_create(method: str) -> Dict[str, Any]:
        """RO: initiaza plata contului de plata — doar clientul autentificat
        (sau backoffice). EN: start the invoice payment — logged-in only."""
        from flask import session
        from models.biro26_pay import Biro26Pay
        c = session.get("biro26_client")
        if not c and not (session.get("username") or session.get("authenticated")):
            return {"success": False, "error": "login required"}
        d = request.get_json(silent=True) or {}
        try:
            cod = int(d.get("cod") or 0)
        except (TypeError, ValueError):
            cod = 0
        if not cod:
            return {"success": False, "error": "cod is required"}
        if method == "maib":
            ip = (request.headers.get("X-Real-IP")
                  or request.remote_addr or "127.0.0.1")
            return Biro26Pay.maib_create(cod, ip, c)
        if method == "mia":
            return Biro26Pay.mia_create(cod)
        if method == "miap2p":
            return Biro26Pay.miap2p_create(cod)
        return {"success": False, "error": f"unknown method: {method}"}

    @staticmethod
    def pay_mia_check() -> Dict[str, Any]:
        from models.biro26_pay import Biro26Pay
        return Biro26Pay.mia_check(request.args.get("order") or "")

    @staticmethod
    def pay_test_create() -> Dict[str, Any]:
        """Backoffice: ad-hoc MAIB test checkout link (admin test page)."""
        from models.biro26_pay import Biro26Pay
        d = request.get_json(silent=True) or {}
        return Biro26Pay.maib_create_test(d.get("amount"),
                                          (d.get("description") or "").strip())

    @staticmethod
    def pay_list() -> Dict[str, Any]:
        from models.biro26_pay import Biro26Pay
        return Biro26Pay.payments_list(request.args.get("limit", 30, type=int))

    @staticmethod
    def pay_verify() -> Dict[str, Any]:
        """Backoffice: re-check one order's status against the bank API."""
        from models.biro26_pay import Biro26Pay
        d = request.get_json(silent=True) or {}
        order = (d.get("order") or "").strip()
        if not order:
            return {"success": False, "error": "order is required"}
        return Biro26Pay.maib_callback(order, "", "manual-check")

    @staticmethod
    def pay_refund() -> Dict[str, Any]:
        """Backoffice: refund a confirmed MAIB checkout payment."""
        from models.biro26_pay import Biro26Pay
        d = request.get_json(silent=True) or {}
        if not d.get("order"):
            return {"success": False, "error": "order is required"}
        amt = d.get("amount")
        return Biro26Pay.maib_refund(
            str(d["order"]), float(amt) if amt else None,
            (d.get("reason") or "Refund solicitat de comerciant"))

    @staticmethod
    def pay_settings_get() -> Dict[str, Any]:
        from models.biro26_pay import Biro26Pay
        return Biro26Pay.get_settings()

    @staticmethod
    def pay_settings_put() -> Dict[str, Any]:
        from models.biro26_pay import Biro26Pay
        return Biro26Pay.save_settings(request.get_json(silent=True) or {})

    # ── credit payment: orgs/plans admin + public offers/calculator ──

    @staticmethod
    def credit_offers() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.public_offers()

    @staticmethod
    def credit_calc() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        d = request.get_json(silent=True) or {}
        return Biro26Credit.calc(d.get("amount"), d.get("plan_id"),
                                 d.get("months"), d.get("avans") or 0)

    @staticmethod
    def credit_request() -> Dict[str, Any]:
        """Public: the «Solicitati un imprumut» form (bomba.md-style)."""
        from flask import session
        from models.biro26_credit import Biro26Credit
        d = request.get_json(silent=True) or {}
        # RO: codul clientului se ia DOAR din sesiune — altfel oricine ar putea
        #     cere ca la notificare sa se ataseze actele ALTUI client.
        # EN: take the client code ONLY from the session; never from the body,
        #     or anyone could have someone else's ID scans attached.
        d.pop("client_cod", None)
        c = session.get("biro26_client")
        if c:
            d["client_cod"] = c["univers_cod"]
        return Biro26Credit.request_create(d)

    @staticmethod
    def credit_apply() -> Dict[str, Any]:
        """RO: formularul complet de cerere (macheta owner): datele creditului,
        datele personale SI copiile buletinului, intr-un singur pas de trimitere.
        Se foloseste la creditorii FARA API (Microinvest): cererea + actele ajung
        la operator, care le depune mai departe la creditor.

        Solicitantul devine automat CLIENT (persoana fizica) daca nu are cont —
        asa actele au unde sa fie pastrate (TMS_MUNC_ADDFILES) si clientul le
        vede/sterge apoi in cabinet. Daca e-mailul apartine unui cont EXISTENT,
        cerem autentificarea: altfel un strain ar incarca acte in dosarul altuia.
        EN: one-shot credit application (data + ID scans); the applicant becomes
        a client so the documents have an owner; existing e-mail requires login.
        """
        import re as _re
        from flask import session
        from models.biro26_client_files import Biro26ClientFiles
        from models.biro26_credit import Biro26Credit
        from models.biro26_journal import Biro26Journal
        from models.biro26_oracle_store import Biro26Store

        f = request.form
        name = " ".join(x for x in ((f.get("nume") or "").strip(),
                                    (f.get("prenume") or "").strip()) if x).strip()
        email = (f.get("email") or "").strip().lower()
        phone = (f.get("phone") or "").strip()
        idnp = _re.sub(r"\D", "", f.get("idnp") or "")
        if not name:
            return {"success": False, "error": "Numele și prenumele sunt obligatorii"}
        if len(phone.replace(" ", "")) < 9:
            return {"success": False, "error": "Număr de telefon invalid"}
        if "@" not in email:
            return {"success": False, "error": "E-mail invalid"}
        if len(idnp) != 13:
            return {"success": False, "error": "IDNP trebuie să aibă 13 cifre"}
        if not (f.get("acord_gdpr") and f.get("acord_istoric")):
            return {"success": False,
                    "error": "Acordurile obligatorii nu au fost bifate"}

        c = session.get("biro26_client")
        if c:
            cod = int(c["univers_cod"])
        else:
            ex = (Biro26Store.shop_client_by_email(email) or {}).get("data")
            if ex:
                return {"success": False, "error": "login_required",
                        "message": "Acest e-mail are deja cont. Autentificați-vă "
                                   "în cabinet și repetați cererea."}
            reg = Biro26Journal.client_quick_add(
                name, is_company=False, phone=phone, email=email,
                address=(f.get("adresa") or "").strip())
            if not reg.get("success"):
                return reg
            cod = int(reg["data"]["univers_cod"])

        # actele de identitate (obligatorii pentru dosar)
        saved = []
        for field, kind in (("buletin_fata", "buletin_fata"),
                            ("buletin_verso", "buletin_verso")):
            up = request.files.get(field)
            if not up:
                continue
            r = Biro26ClientFiles.add(
                cod, kind, up.filename or f"{kind}.jpg", up.read(),
                mime=up.mimetype or "", who=f"cerere-credit:{email}",
                ip=request.headers.get("X-Real-IP") or request.remote_addr or "")
            if not r.get("success"):
                return r
            saved.append(kind)

        # cererea propriu-zisa (notificarea pleaca cu actele atasate)
        # RO: ancheta se salveaza pe CIMPURI (TMS_CREDITE_REQ), nu ca text —
        #     operatorul le copiaza de acolo in cererea depusa la banca.
        # EN: the application is stored field by field, not as free text.
        res = Biro26Credit.request_create({
            "plan_id": f.get("plan_id"), "months": f.get("months"),
            "qty": 1, "amount": f.get("amount"),
            "product_cod": 0,
            "product_name": (f.get("product_name") or "Cerere de credit")[:180],
            "client_name": name, "phone": phone, "idnp": idnp,
            "birth_date": f.get("data_nasterii") or "",
            "address": (f.get("adresa") or "").strip(),
            "email": email,
            "act_serie": f.get("act_serie"), "act_data": f.get("act_data"),
            "act_oficiu": f.get("act_oficiu"),
            "localitate": f.get("localitate"), "scop": f.get("scop"),
            "venit": f.get("venit"), "alte_credite": f.get("alte_credite"),
            "angajator": f.get("angajator"),
            "acord_marketing": bool(f.get("acord_marketing")),
            "client_cod": cod})
        if res.get("success"):
            res["data"]["files"] = saved
            res["data"]["client_cod"] = cod
        return res

    @staticmethod
    def credit_requests_list() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.requests_list(request.args.get("limit", 50, type=int))

    @staticmethod
    def credit_request_status(req_id: int) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        d = request.get_json(silent=True) or {}
        return Biro26Credit.request_status(req_id, d.get("status") or "PROCESSED")

    @staticmethod
    def credit_orgs() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.orgs_list()

    @staticmethod
    def credit_org_save() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.org_save(request.get_json(silent=True) or {})

    @staticmethod
    def credit_plans() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.plans_list(request.args.get("org_id", type=int))

    @staticmethod
    def credit_plan_save() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.plan_save(request.get_json(silent=True) or {})

    @staticmethod
    def credit_plan_delete(plan_id: int) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.plan_delete(plan_id)

    # ── credit: provideri API + fluxul clientului ──

    @staticmethod
    def credit_providers() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.providers_list()

    @staticmethod
    def credit_provider_save() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.provider_save(request.get_json(silent=True) or {})

    @staticmethod
    def credit_provider_test(code: str) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.provider_test(code)

    @staticmethod
    def credit_request_events(req_id: int) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.request_events(req_id)

    # RO: preapproved/submit sunt un oracol IDNP->suma preaprobata, respectiv
    #     depunerea unei cereri reale de credit — la fel ca la comanda din cos
    #     (makeInvoice), se cere clientul autentificat al magazinului.
    _AUTH_REQUIRED_ERR = ("Autentificați-vă pentru a solicita creditul · "
                          "Войдите, чтобы оформить кредит")

    @staticmethod
    def credit_api_preapproved() -> Dict[str, Any]:
        if not session.get("biro26_client"):
            return {"success": False, "error": Biro26Controller._AUTH_REQUIRED_ERR,
                    "auth_required": True}
        from models.biro26_credit import Biro26Credit
        return Biro26Controller._with_admin_debug(
            Biro26Credit.api_preapproved(request.get_json(silent=True) or {}))

    @staticmethod
    def credit_api_submit() -> Dict[str, Any]:
        if not session.get("biro26_client"):
            return {"success": False, "error": Biro26Controller._AUTH_REQUIRED_ERR,
                    "auth_required": True}
        from models.biro26_credit import Biro26Credit
        d = request.get_json(silent=True) or {}
        # RO: datele introduse se memoreaza TACIT in cabinet (daca clientul nu a
        #     oprit memorarea) — la urmatoarea cerere formularul e deja completat,
        #     iar orice modificare suprascrie valorile vechi, fara intrebari.
        # EN: silently remember the form in the cabinet unless the client
        #     switched it off; edits overwrite the stored values.
        try:
            Biro26Store.shop_credit_profile_save(
                session["biro26_client"]["univers_cod"],
                {"nnp": d.get("client_name"), "idnp": d.get("idnp"),
                 "address": d.get("address"), "phone": d.get("phone"),
                 "birth_date": d.get("birth_date")})
        except Exception:                              # noqa: BLE001
            pass
        return Biro26Controller._with_admin_debug(Biro26Credit.api_submit(d))

    @staticmethod
    def _client_is_admin() -> bool:
        """RO: clientul autentificat in magazin e marcat 'admin' in back-office?
        Doar el vede detaliile tehnice ale erorilor de creditare (vezi
        YBIRO_CLIENT.CLIENT_MARK, pagina /UNA.md/orasldev/biro26-clients)."""
        c = session.get("biro26_client") or {}
        if not c.get("univers_cod"):
            return False
        try:
            return Biro26Store.shop_client_mark(c["univers_cod"]) == "admin"
        except Exception:                              # noqa: BLE001
            return False

    @staticmethod
    def _with_admin_debug(res: Dict[str, Any]) -> Dict[str, Any]:
        """RO: la eroare, pentru clientul-admin atasam ultimele apeluri din
        jurnalul tehnic — ca sa vada cauza direct in cos, fara back-office.
        EN: on error, attach the last technical calls for admin-marked clients."""
        if res.get("success") or not Biro26Controller._client_is_admin():
            return res
        try:
            from models.biro26_credit import Biro26Credit
            ev = [e for e in (Biro26Credit.integration_log(10).get("data") or [])
                  if e.get("kind") == "credit"][:3]
        except Exception:                              # noqa: BLE001
            return res
        if not isinstance(res.get("data"), dict):
            res["data"] = {}
        res["data"]["debug"] = ev
        return res

    @staticmethod
    def credit_api_status() -> Dict[str, Any]:
        """Public: витрина проверяет статус только своей заявки (по ext_ref)."""
        from models.biro26_credit import Biro26Credit
        try:
            req_id = int(request.args.get('req_id') or 0)
        except (TypeError, ValueError):
            return {"success": False, "error": "req_id invalid"}
        if not req_id:
            return {"success": False, "error": "req_id lipsește"}
        ref = (request.args.get('ref') or "").strip()
        if not ref:
            return {"success": False, "error": "ref lipsește"}
        return Biro26Credit.api_status(req_id, ref)

    @staticmethod
    def credit_request_refresh(req_id: int) -> Dict[str, Any]:
        """RO: reinterogare status din back-office (fara verificarea referintei)."""
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.api_status(req_id)

    # ── translations management (catalog grouping RU/EN dictionary) ──

    @staticmethod
    def i18n_groups() -> Dict[str, Any]:
        from models.biro26_i18n import Biro26I18n
        return Biro26I18n.groups_list()

    @staticmethod
    def i18n_save() -> Dict[str, Any]:
        from models.biro26_i18n import Biro26I18n
        d = request.get_json(silent=True) or {}
        return Biro26I18n.save_rows(d.get("rows") or [])

    @staticmethod
    def i18n_import() -> Dict[str, Any]:
        from models.biro26_i18n import Biro26I18n
        f = request.files.get("file")
        if not f:
            return {"success": False, "error": "no file"}
        return Biro26I18n.import_csv(f.read().decode("utf-8-sig", "replace"))

    @staticmethod
    def i18n_auto_start() -> Dict[str, Any]:
        from models.biro26_i18n import Biro26I18n
        d = request.get_json(silent=True) or {}
        return Biro26I18n.auto_start(bool(d.get("only_missing", True)))

    @staticmethod
    def i18n_auto_status(job_id: str) -> Dict[str, Any]:
        from models.biro26_i18n import Biro26I18n
        return Biro26I18n.auto_status(job_id)

    # ── product description + client comments (shop window / card) ──

    @staticmethod
    def shop_product_info(cod: int) -> Dict[str, Any]:
        """Public: description + comments for the shop's product window.
        RO: ?lang=ro|ru|en — descrierea din TMS_MPT_WEBATTR (BLOB, cu
        diacritice) cu intoarcere pe RO."""
        return Biro26Store.product_info(cod, request.args.get("lang", "ro"))

    @staticmethod
    def webattr_get(cod: int) -> Dict[str, Any]:
        """Backoffice: valorile RO/RU/EN pentru editorul «Atribute web»."""
        return Biro26Store.get_webattr(cod)

    @staticmethod
    def webattr_save(cod: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.save_webattr(
            cod, d.get("lang") or "", d.get("descriere"), d.get("denum_full"))

    @staticmethod
    def shop_product_comment(cod: int) -> Dict[str, Any]:
        """RO: comentariu nou — doar clienti autentificati (sau backoffice);
        autorul se ia din sesiune, nu din request (anti-spoof).
        EN: new comment — logged-in shop clients (or backoffice) only;
        the author comes from the session, never from the request."""
        from flask import session
        d = request.get_json() or {}
        text = (d.get("txt") or "").strip()
        c = session.get("biro26_client")
        if c:
            return Biro26Store.add_product_comment(
                cod, c.get("name") or "client", c.get("univers_cod"), text)
        if session.get("username") or session.get("authenticated"):
            return Biro26Store.add_product_comment(
                cod, session.get("username") or "operator", None, text)
        return {"success": False, "error": "login required"}

    @staticmethod
    def set_product_desc(cod: int) -> Dict[str, Any]:
        d = request.get_json() or {}
        return Biro26Store.set_product_desc(cod, d.get("descriere") or "")

    @staticmethod
    def delete_product_comment(comment_id: int) -> Dict[str, Any]:
        return Biro26Store.delete_product_comment(comment_id)

    # ── external-app API: document list + PDF by document NUMBER (#NRMANUAL) ──

    @staticmethod
    def _sig_nr_ok(kind: str, nr) -> bool:
        """RO: link semnat pe NUMARUL documentului (hashtag): HMAC peste
        '<kind>-nr:<nr>'. EN: signed link keyed by the document number."""
        import hmac
        from models.biro26_notify import Biro26Notify
        sig = request.args.get("sig") or ""
        if not sig:
            return False
        try:
            n = int(str(nr).strip().lstrip("#"))
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(sig, Biro26Notify.pdf_sig(f"{kind}-nr", n))

    @staticmethod
    def docs_list() -> Dict[str, Any]:
        """RO: lista documentelor clientului pentru aplicatii externe
        (X-API-Key) sau sesiuni backoffice. EN: doc list for external apps."""
        from models.biro26_report import Biro26Report
        if not (Biro26Controller._api_token_ok()
                or session.get("username") or session.get("authenticated")):
            return {"success": False, "error": "login required"}
        return Biro26Report.docs_list(
            (request.args.get("client") or request.args.get("search") or "").strip(),
            request.args.get("limit", 50, type=int))

    @staticmethod
    def report_by_nr(kind: str, nr: str) -> Dict[str, Any]:
        """RO: PDF dupa NUMARUL documentului (#338) — numarul vizibil in
        orice aplicatie nativa. Acces: X-API-Key, ?sig= (hash HMAC) sau
        sesiune backoffice. EN: PDF by the document NUMBER (hashtag)."""
        from models.biro26_report import Biro26Report
        if not (Biro26Controller._api_token_ok()
                or Biro26Controller._sig_nr_ok(kind, nr)
                or session.get("username") or session.get("authenticated")):
            return {"success": False, "error": "login required"}
        cod = Biro26Report.resolve_nr(nr)
        if not cod:
            return {"success": False, "error": f"document {nr} not found"}
        r = Biro26Report.render_doc(kind, cod)
        if r.get("success"):
            r["cod"] = cod
        return r

    @staticmethod
    def doc_json(cod: int) -> Dict[str, Any]:
        """Document data as JSON (number, client, items, totals) for
        desktop/integration layers; API token or backoffice session."""
        from flask import session
        from models.biro26_report import Biro26Report
        if not (Biro26Controller._api_token_ok()
                or session.get("username") or session.get("authenticated")):
            return {"success": False, "error": "login required"}
        d = Biro26Report.doc_data(cod)
        if not d.get("success"):
            return d
        return {"success": True, "data": d["data"]}

    # ── BIRO26PT universal file import (spec BIRO26PT_WEB_INTERFACE_SPEC) ──
    @staticmethod
    def pt_upload() -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        files = request.files.getlist("files")
        if not files:
            return {"success": False, "error": "no files"}
        saved = Biro26PTStore.save_uploads(files)
        if not saved.get("success"):
            return saved
        run = Biro26PTStore.run_loader(saved["data"]["session"])
        if not run.get("success"):
            return run
        return {"success": True, "data": {
            "session": saved["data"]["session"],
            "files": saved["data"]["files"],
            "loads": run["data"]["loads"]}}

    @staticmethod
    def pt_analyze() -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        d = request.get_json(silent=True) or {}
        out = []
        for lid in (d.get("load_ids") or [])[:20]:
            r = Biro26PTStore.analyze(int(lid), d.get("grupa"),
                                   int(d.get("codprice") or 1),
                                   mark_all_new=d.get("mark_all_new", True),
                                   price_date=d.get("price_effective") or None,
                                   src=d.get("src") or None,
                                   algo=d.get("algo") or None)
            if not r.get("success"):
                return r
            out.append(r["data"])
        if not out:
            return {"success": False, "error": "load_ids is required"}
        return {"success": True, "data": out}

    @staticmethod
    def pt_preview(load_id: int) -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        a = request.args
        return Biro26PTStore.preview(load_id, a.get("offset", 0, type=int),
                                     a.get("limit", 50, type=int))

    @staticmethod
    def pt_commit() -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        d = request.get_json(silent=True) or {}
        out = []
        for lid in (d.get("load_ids") or [])[:20]:
            r = Biro26PTStore.commit(int(lid), d.get("grupa"),
                                   int(d.get("codprice") or 1),
                                   mark_all_new=d.get("mark_all_new", True),
                                   price_date=d.get("price_effective") or None,
                                   src=d.get("src") or None,
                                   algo=d.get("algo") or None)
            if not r.get("success"):
                return r
            out.append(r["data"])
        if not out:
            return {"success": False, "error": "load_ids is required"}
        return {"success": True, "data": out}

    @staticmethod
    def pt_remap() -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        d = request.get_json(silent=True) or {}
        if not d.get("load_id") or not d.get("field"):
            return {"success": False, "error": "load_id and field are required"}
        col = d.get("col_idx")
        return Biro26PTStore.remap(int(d["load_id"]), str(d["field"]),
                                   int(col) if col is not None and col != "" else None)

    @staticmethod
    def pt_sources() -> Dict[str, Any]:
        """RO: sursele de import pentru selectorul de algoritm din back-office.
        EN: import sources for the back-office algorithm selector."""
        from models.biro26pt_store import Biro26PTStore
        return Biro26PTStore.sources(
            active_only=(request.args.get("all") != "1"))

    @staticmethod
    def pt_algorithms() -> Dict[str, Any]:
        """RO: algoritmii de import pentru selectorul din back-office.
        EN: import algorithms for the back-office selector."""
        from models.biro26pt_store import Biro26PTStore
        return Biro26PTStore.algorithms()

    @staticmethod
    def pt_source_files(src_code: str) -> Dict[str, Any]:
        """RO: fisierele pastrate in baza pentru sursa aleasa.
        EN: the files kept in the DB for the chosen source."""
        from models.biro26pt_store import Biro26PTStore
        return Biro26PTStore.source_files(
            src_code, request.args.get("limit", 50, type=int))

    @staticmethod
    def pt_help() -> Dict[str, Any]:
        from models.biro26pt_store import Biro26PTStore
        return Biro26PTStore.algo_md()

    # ── notification settings (email / Telegram / WhatsApp) ──
    @staticmethod
    def notify_settings_get() -> Dict[str, Any]:
        from models.biro26_notify import Biro26Notify
        return Biro26Notify.get_settings()

    @staticmethod
    def notify_settings_save() -> Dict[str, Any]:
        from models.biro26_notify import Biro26Notify
        return Biro26Notify.save_settings(request.get_json(silent=True) or {})

    @staticmethod
    def notify_test() -> Dict[str, Any]:
        from models.biro26_notify import Biro26Notify
        d = request.get_json(silent=True) or {}
        return Biro26Notify.test_channel(str(d.get("channel") or ""))

    # ── report template admin (edit reports/templates/* in the browser) ──
    @staticmethod
    def report_templates_list() -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        return Biro26Report.list_templates()

    @staticmethod
    def report_template_get(name: str) -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        return Biro26Report.read_template(name)

    @staticmethod
    def report_template_save(name: str) -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        d = request.get_json(silent=True) or {}
        return Biro26Report.save_template(name, d.get("content") or "")

    @staticmethod
    def report_template_preview() -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        d = request.get_json(silent=True) or {}
        if not (d.get("content") or "").strip():
            return {"success": False, "error": "content is required"}
        cod = d.get("cod")
        return Biro26Report.preview(d["content"], int(cod) if cod else None,
                                    name=d.get("name"))

    @staticmethod
    def report_engines_get() -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        return Biro26Report.get_engines()

    @staticmethod
    def report_engines_set() -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        return Biro26Report.set_engines(request.get_json(silent=True) or {})

    # ── product variants (BIRO26_VARIANTS master/detail families) ──
    @staticmethod
    def get_variants(cod: int) -> Dict[str, Any]:
        return Biro26Store.get_variants(cod)

    @staticmethod
    def update_variant(cod: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.update_variant(
            cod, variant=d.get("variant"),
            articol=d.get("articol"), furnizor=d.get("furnizor"))

    @staticmethod
    def shop_services() -> Dict[str, Any]:
        return Biro26Store.shop_services()

    @staticmethod
    def shop_transport() -> Dict[str, Any]:
        return Biro26Store.shop_transport_tariffs()

    @staticmethod
    def shop_logistics() -> Dict[str, Any]:
        return Biro26Store.shop_logistics_centers()

    @staticmethod
    def shop_variants() -> Dict[str, Any]:
        cod = request.args.get("cod", type=int)
        if not cod:
            return {"success": False, "error": "cod is required"}
        return Biro26Store.get_variants(cod)

    @staticmethod
    def product_price_delete() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("sc") or not d.get("date"):
            return {"success": False, "error": "sc and date are required"}
        return Biro26Store.delete_price_period(
            int(d["sc"]), str(d["date"]), codprice=int(d.get("codprice") or 1))

    @staticmethod
    def get_product_tree() -> Dict[str, Any]:
        return Biro26Store.get_product_tree()

    @staticmethod
    def update_product(cod: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.update_product(
            cod, univers=d.get("univers"), goods=d.get("goods"),
            image=d.get("image"), bc_add=d.get("bc_add"), bc_remove=d.get("bc_remove"))

    @staticmethod
    def tree_rename() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("level", "old", "new"):
            if not d.get(k):
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.rename_tree_node(d["level"], d["old"], d["new"], d.get("grupa"))

    @staticmethod
    def tree_move() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("grupa", "categorie", "new_grupa"):
            if not d.get(k):
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.move_tree_categorie(d["grupa"], d["categorie"], d["new_grupa"])

    @staticmethod
    def get_product_brands() -> Dict[str, Any]:
        return Biro26Store.get_product_brands()

    @staticmethod
    def get_product_categories() -> Dict[str, Any]:
        return Biro26Store.get_product_categories()

    # -- web-shop (public page: self-registration + invoices) ---------
    # Password hashing: pbkdf2-sha256, format "pbkdf2$<salt-hex>$<hash-hex>".

    @staticmethod
    def _hash_pwd(pwd: str) -> str:
        import hashlib, os as _os, binascii
        salt = _os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, 100000)
        return "pbkdf2$" + binascii.hexlify(salt).decode() + "$" + binascii.hexlify(dk).decode()

    @staticmethod
    def _check_pwd(pwd: str, stored: str) -> bool:
        import hashlib, binascii, hmac
        try:
            _, salt_hex, hash_hex = (stored or "").split("$")
            dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(),
                                     binascii.unhexlify(salt_hex), 100000)
            return hmac.compare_digest(binascii.hexlify(dk).decode(), hash_hex)
        except Exception:
            return False

    @staticmethod
    def shop_register() -> Dict[str, Any]:
        import re
        from flask import session
        d = request.get_json(silent=True) or {}
        email = (d.get("email") or "").strip().lower()
        name = (d.get("full_name") or "").strip()
        address = (d.get("address") or "").strip()
        phone = (d.get("phone") or "").strip()
        is_company = bool(d.get("is_company"))
        idno = (d.get("idno") or "").strip()
        pwd = d.get("password") or ""
        # RO: cimpuri OBLIGATORII: Nume Prenume, adresa de livrare, e-mail,
        #     telefon; IDNO (13 cifre) pentru persoane juridice.
        # EN: MANDATORY fields: full name, delivery address, e-mail, phone;
        #     IDNO (13 digits) for legal entities.
        if not name:
            return {"success": False, "error": "Nume Prenume este obligatoriu"}
        if not address:
            return {"success": False, "error": "Adresa de livrare este obligatorie"}
        if not email or "@" not in email:
            return {"success": False, "error": "E-mail valid este obligatoriu"}
        if not phone:
            return {"success": False, "error": "Numărul de telefon este obligatoriu"}
        if is_company and not re.match(r"^\d{13}$", idno):
            return {"success": False,
                    "error": "IDNO (13 cifre) este obligatoriu pentru persoane juridice"}
        if len(pwd) < 6:
            return {"success": False, "error": "Parola: minim 6 caractere"}
        exists = Biro26Store.shop_client_by_email(email)
        if exists.get("data"):
            return {"success": False, "error": "email already registered"}
        r = Biro26Store.shop_register_client(
            email, name, phone, Biro26Controller._hash_pwd(pwd),
            address=address, idno=idno if is_company else "",
            is_company=is_company)
        if r.get("success"):
            session["biro26_client"] = {"id": r["data"]["client_id"],
                                        "univers_cod": r["data"]["univers_cod"],
                                        "email": email, "name": name}
        return r

    @staticmethod
    def shop_login() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        r = Biro26Store.shop_client_by_email(d.get("email") or "")
        c = r.get("data")
        if not c or not Biro26Controller._check_pwd(d.get("password") or "", c["pwd_hash"]):
            return {"success": False, "error": "invalid email or password"}
        session["biro26_client"] = {"id": c["id"], "univers_cod": c["univers_cod"],
                                    "email": c["email"], "name": c["full_name"]}
        return {"success": True, "data": {"name": c["full_name"], "email": c["email"]}}

    @staticmethod
    def shop_logout() -> Dict[str, Any]:
        from flask import session
        session.pop("biro26_client", None)
        return {"success": True}

    @staticmethod
    def shop_me() -> Dict[str, Any]:
        from flask import session
        c = session.get("biro26_client")
        if not c:
            return {"success": True, "data": None}
        # RO: telefonul e necesar cererii de credit din cos
        # EN: the phone feeds the cart's credit-request button
        phone, inv_fmt, is_company, idno = "", "", False, ""
        try:
            r = Biro26Store.shop_client_by_email(c["email"])
            row = r.get("data") or {}
            phone = row.get("phone") or ""
            inv_fmt = row.get("invoice_fmt") or ""
            is_company = str(row.get("is_company")) in ("1", "Y", "True")
            idno = row.get("idno") or ""
        except Exception:
            pass
        return {"success": True,
                "data": {"name": c["name"], "email": c["email"],
                         "phone": phone,
                         # RO: constanta personala — formatele contului
                         #     (implicit 'pdf' la toti)
                         "invoice_fmt": inv_fmt or "pdf",
                         # RO: tipul clientului decide COLOANA de pret
                         "is_company": is_company, "idno": idno,
                         # RO: datele formularului de credit memorate in cabinet —
                         #     cosul le precompleteaza la urmatoarea cerere
                         "credit": Biro26Store.shop_credit_profile(c["univers_cod"]),
                         "price_field": Biro26Store.client_price_field(
                             c["univers_cod"])}}

    @staticmethod
    def shop_credit_profile_set() -> Dict[str, Any]:
        """RO: butonul din cabinet — memorarea datelor de credit pornita/oprita."""
        from flask import session
        cl = session.get("biro26_client")
        if not cl:
            return {"success": False, "error": "login required"}
        d = request.get_json(silent=True) or {}
        return Biro26Store.shop_credit_profile_set_save(
            cl["univers_cod"], str(d.get("save")) in ("1", "true", "True"))

    @staticmethod
    def shop_set_client_type() -> Dict[str, Any]:
        """RO: setarea din cabinet: pers. FIZICA / JURIDICA — schimba
        automat preturile afisate si cele din conturile viitoare.
        Juridica cere IDNO (13 cifre)."""
        import re
        from flask import session
        cl = session.get("biro26_client")
        if not cl:
            return {"success": False, "error": "login required"}
        d = request.get_json(silent=True) or {}
        is_company = str(d.get("is_company")) in ("1", "true", "True")
        idno = (d.get("idno") or "").strip()
        if is_company and not re.match(r"^\d{13}$", idno):
            return {"success": False,
                    "error": "IDNO (13 cifre) este obligatoriu pentru "
                             "persoane juridice"}
        r = Biro26Store.set_client_type(cl["univers_cod"], is_company, idno)
        if not r.get("success"):
            return r
        return {"success": True, "data": {
            "is_company": is_company,
            "price_field": Biro26Store.client_price_field(cl["univers_cod"])}}

    @staticmethod
    def shop_clients() -> Dict[str, Any]:
        """RO: lista clientilor magazinului (pagina de marcare din back-office)."""
        return Biro26Store.shop_clients_list(
            search=request.args.get("search", ""),
            limit=request.args.get("limit", 200, type=int))

    @staticmethod
    def shop_client_mark_set() -> Dict[str, Any]:
        """RO: pune/scoate marcajul unui client (admin/test/trusted)."""
        d = request.get_json(silent=True) or {}
        return Biro26Store.shop_client_set_mark(d.get("univers_cod"), d.get("mark") or "")

    @staticmethod
    def shop_order_view(cod: int) -> Dict[str, Any]:
        """RO: detaliile comenzii pentru pagina de retur dupa plata — cerinta
        maib (numar, data, suma, marfurile). Vede DOAR clientul caruia ii
        apartine documentul; pentru strain raspunsul e identic cu «inexistenta».
        EN: order details for the post-payment return page (maib requirement),
        visible only to the owning client; a stranger gets the same answer as
        for a missing document."""
        from flask import session
        from models.biro26_report import Biro26Report
        from models.biro26_pay import Biro26Pay
        c = session.get("biro26_client")
        if not c:
            return {"success": False, "error": "login required"}
        try:
            cod = int(cod)
        except (TypeError, ValueError):
            return {"success": False, "error": "comandă inexistentă"}
        r = Biro26Report.doc_data(cod)
        if not r.get("success"):
            return {"success": False, "error": "comandă inexistentă"}
        if int(r.get("client_cod") or 0) != int(c["univers_cod"]):
            return {"success": False, "error": "comandă inexistentă"}
        d = r.get("data") or {}
        pay = Biro26Pay.doc_status(cod)
        return {"success": True, "data": {
            "cod": cod,
            "nr": d.get("nrmanual") or d.get("nr") or "",
            "date": d.get("date_ro") or d.get("date_short") or "",
            "total": d.get("total") or 0,
            "items": d.get("items") or [],
            "payments": (pay.get("data") or []) if isinstance(pay, dict) else []}}

    @staticmethod
    def shop_set_invoice_fmt() -> Dict[str, Any]:
        """RO: salveaza in cabinetul clientului formatele alese pentru
        cont (pdf/html/xlsx) — se refolosesc la conturile urmatoare.
        Se accepta DOAR formatele activate de admin (SHOP_FMT_*)."""
        from flask import session
        c = session.get("biro26_client")
        if not c:
            return {"success": False, "error": "login required"}
        d = request.get_json(silent=True) or {}
        allowed = {"pdf"}
        if Biro26Store.get_setting("SHOP_FMT_HTML", "1") == "1":
            allowed.add("html")
        if Biro26Store.get_setting("SHOP_FMT_XLSX", "1") == "1":
            allowed.add("xlsx")
        fmts = [f.strip().lower() for f in
                str(d.get("invoice_fmt") or "").split(",")
                if f.strip().lower() in allowed]
        fmt = ",".join(dict.fromkeys(fmts)) or "pdf"
        r = Biro26Store.set_client_invoice_fmt(c["univers_cod"], fmt)
        return (r if not r.get("success")
                else {"success": True, "data": {"invoice_fmt": fmt}})

    @staticmethod
    def shop_invoice() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        items = d.get("items") or []
        c = session.get("biro26_client")
        if c:
            client_cod = c["univers_cod"]
        elif d.get("client_cod") and (session.get("username")
                                      or Biro26Controller._api_token_ok()):
            # RO: operatorul din back-office SAU o integrare B2B cu cheie de
            #     incredere (X-API-Key) — angajati/aplicatii externe pot
            #     plasa comenzi pe un COD de client explicit.
            # EN: back-office operator OR a trusted-key (X-API-Key) B2B
            #     integration may issue for an explicit client COD
            try:
                client_cod = int(d["client_cod"])
            except (TypeError, ValueError, OverflowError):
                return {"success": False, "error": "client_cod invalid"}
        else:
            return {"success": False, "error": "login required"}
        # RO/EN: intrare publica — `items` trebuie sa fie o LISTA, altfel
        #        iterarea peste un numar/dict ar da 500 in loc de un raspuns.
        if not isinstance(items, list):
            return {"success": False, "error": "items must be a list"}
        clean = []
        for it in items:
            try:
                if not isinstance(it, dict):
                    raise TypeError("item must be an object")
                cod, qty, price = int(it["cod"]), float(it["qty"]), float(it.get("price") or 0)
            except Exception:
                return {"success": False, "error": "bad item format"}
            # RO/EN: NaN/inf trec de "qty <= 0" si strica toate verificarile
            #        de suma mai jos — le respingem explicit.
            if not (qty > 0) or qty != qty or qty in (float("inf"), float("-inf")):
                return {"success": False, "error": "qty must be > 0"}
            if price != price or price in (float("inf"), float("-inf")):
                return {"success": False, "error": "bad item format"}
            clean.append({"cod": cod, "qty": qty, "price": price,
                          "name": str(it.get("name") or "")[:180]})
        # RO: transportul tur-retur este OBLIGATORIU pentru clientii
        #     magazinului si se alege pe server dupa distanta comenzii
        #     (TMS_MPT_DISTANTE): TUR -> qty 1, KM -> qty = km. Liniile de
        #     transport trimise de client se ignora INTOTDEAUNA (anti-manipulare).
        #     La achitarea PRIN CREDIT transportul nu se mai presteaza (vezi
        #     .superpowers/sdd/transport-markup-brief.md): blocul de mai jos
        #     e SARIT complet — km nu e obligatoriu, nicio linie de transport
        #     nu se adauga; costul e acoperit de naceta organizatiei (blocul
        #     de credit, mai jos).
        # EN: round-trip transport is MANDATORY for shop clients and is
        #     picked server-side from the order distance: TUR -> qty 1,
        #     KM -> qty = km. Client-sent transport lines are ALWAYS discarded.
        #     On CREDIT payment transport is not delivered (see the brief
        #     above): the block below is SKIPPED entirely — km is not
        #     required and no transport line is added; the org's markup
        #     covers the cost instead (credit block below).
        credit_plan_id = d.get("credit_plan_id")
        if c:
            tariff_cods = {r["cod"] for r in
                           (Biro26Store.shop_transport_tariffs().get("data") or [])}
            clean = [it for it in clean if it["cod"] not in tariff_cods]
            if not credit_plan_id:
                try:
                    km = float(d.get("distance_km") or 0)
                except (TypeError, ValueError):
                    km = 0
                if km <= 0:
                    return {"success": False,
                            "error": "distance_km is required (transport obligatoriu)"}
                tr = Biro26Store.transport_for_km(km)
                if not tr.get("success"):
                    return tr
                t = tr["data"]
                # RO: distanta se masoara DE LA centrul logistic; centrul ales
                #     trebuie sa fie ACTIV (momentan doar mun. Balti)
                # EN: the distance is measured FROM the logistics center; the
                #     chosen center must be ACTIVE (only mun. Balti for now)
                centers = Biro26Store.shop_logistics_centers().get("data") or []
                if not centers:
                    return {"success": False, "error": "no active logistics center"}
                center = next((x for x in centers
                               if str(x["id"]) == str(d.get("center_id"))),
                              centers[0])
                clean.append({"cod": int(t["cod"]),
                              "qty": 1.0 if t["tarif_mode"] == "TUR" else km,
                              "price": 0,
                              "name": ((t["denumirea"] or "Transport tur-retur")
                                       + f" din {center['denumire']}")[:180]})

        # RO/EN: public client -> authoritative server-side prices only;
        #        operator -> server price fills items sent without a price
        need = [it["cod"] for it in clean] if c else \
               [it["cod"] for it in clean if it["price"] <= 0]
        if need:
            # RO: coloana de pret dupa TIPUL clientului din cabinet
            #     (pers. fizica -> SHOP_PRICE_FIZ, juridica -> SHOP_PRICE_JUR)
            pf = (Biro26Store.client_price_field(c["univers_cod"])
                  if c else "retail1")
            pr = Biro26Store.shop_prices_for(need, pf)
            if not pr.get("success"):
                return pr
            for it in clean:
                if c or it["price"] <= 0:
                    it["price"] = pr["data"].get(it["cod"], 0)
        # RO: ACHITARE PRIN CREDIT — metoda de calcul avansata a preturilor:
        #     la alegerea creditului, pretul FIECARUI rind se majoreaza cu
        #     naceta ACTIVA (comisionul pachetului MARKUP_PCT + majorarea
        #     organizatiei TRANSPORT_MARKUP_PCT care inlocuieste transportul
        #     neprestat), conform conditiilor organizatiei de creditare
        #     (vezi models/biro26_credit.py si transport-markup-brief.md).
        # EN: CREDIT payment — every line price is marked up with the
        #     EFFECTIVE markup (plan commission + the org's markup that
        #     replaces the undelivered transport) before the invoice is
        #     created.
        credit_months = credit_avans = None
        if credit_plan_id:
            from models.biro26_credit import Biro26Credit
            # RO: valoare publica — un plan_id nenumeric nu trebuie sa dea 500
            #     (si nici sa sara peste gardul de transport de mai sus).
            # EN: public input — a non-numeric plan id must not raise a 500.
            try:
                credit_plan_id = int(credit_plan_id)
            except (TypeError, ValueError, OverflowError):
                return {"success": False, "error": "pachet de credit invalid"}
            plan = Biro26Credit.plan_get(credit_plan_id)
            if not plan:
                return {"success": False, "error": "pachet de credit invalid"}
            try:
                credit_months = int(d.get("credit_months") or plan["months_max"])
            except (TypeError, ValueError, OverflowError):
                credit_months = int(plan["months_max"])
            credit_months = max(int(plan["months_min"]),
                                min(credit_months, int(plan["months_max"])))
            try:
                credit_avans = max(0.0, float(d.get("credit_avans") or 0))
            except (TypeError, ValueError, OverflowError):
                credit_avans = 0.0
            # RO: pragul minim al COMENZII pentru achitarea in rate — aceeasi
            #     valoare pe care vitrina o scrie cu rosu (CREDIT_MIN_ORDER).
            #     Verificarea se face si aici: butonul dezactivat in browser nu
            #     opreste o cerere trimisa direct catre API.
            # EN: server-side guard for the same minimum the storefront shows.
            try:
                min_order = float(Biro26Store.get_setting("CREDIT_MIN_ORDER", "1500"))
            except Exception:                              # noqa: BLE001
                min_order = 1500.0
            base_total = sum(it["qty"] * it["price"] for it in clean)
            if min_order > 0 and base_total < min_order:
                return {"success": False,
                        "error": f"Achitarea în rate / credit este disponibilă "
                                 f"la comenzi de la {min_order:.0f} lei · "
                                 f"Оплата в рассрочку — при заказе от {min_order:.0f} лей"}
            mk = 1 + (float(plan["markup_pct"] or 0)
                      + float(plan.get("transport_markup_pct") or 0)) / 100
            financed = round(sum(it["qty"] * it["price"] for it in clean) * mk
                             - credit_avans, 2)
            if financed < float(plan["amount_min"] or 0):
                return {"success": False,
                        "error": f"Credit: suma finanțată sub minim "
                                 f"({plan['amount_min']:.0f} lei)"}
            if financed > float(plan["amount_max"] or 1e12):
                return {"success": False,
                        "error": f"Credit: suma finanțată peste maxim "
                                 f"({plan['amount_max']:.0f} lei)"}
            for it in clean:
                it["price"] = round(it["price"] * mk, 2)
        res = Biro26Store.shop_create_invoice(client_cod, clean)
        if res.get("success") and credit_plan_id:
            Biro26Store.set_doc_credit(res["data"]["cod"], int(credit_plan_id),
                                       credit_months, credit_avans)
            # RO: pe linga marcajul comenzii se creeaza si DOCUMENTUL de credit
            #     (TMDB_CREDITE_M/D, serie 'CR'), legat prin DOC_COD_ORDER.
            #     Un esec aici nu anuleaza comanda — clientul si-a plasat-o deja.
            # EN: also create the ERP credit document linked to this order;
            #     a failure here must never void the order itself.
            try:
                doc = Biro26Credit.create_document(
                    res["data"]["cod"], client_cod, plan, credit_months,
                    credit_avans, clean,
                    client={"name": (c or {}).get("name") or "",
                            "phone": (c or {}).get("phone") or "",
                            "address": (d.get("address") or "").strip(),
                            "birth_date": (d.get("birth_date") or "").strip()},
                    req_id=d.get("credit_req_id"))
                if not doc.get("success"):
                    print(f"[credit-doc] cod={res['data']['cod']}: {doc.get('error')}")
            except Exception as e:                     # noqa: BLE001
                print(f"[credit-doc] cod={res['data']['cod']}: {e}")
        if res.get("success"):
            # RO: modul TVA ales la generare ('inclus' implicit / '0' /
            #     'fara') — formularele PDF il citesc din YBIRO_DOC_META
            # EN: the chosen VAT mode; the PDF forms read it from the meta
            tva_mode = d.get("tva_mode") or "inclus"
            if tva_mode not in ("inclus", "0", "fara"):
                tva_mode = "inclus"
            Biro26Store.set_doc_tva_mode(res["data"]["cod"], tva_mode)
            # RO/EN: notificari email/Telegram/WhatsApp — fire-and-forget
            from models.biro26_notify import Biro26Notify
            nr = res["data"].get("nrmanual") or res["data"].get("nrset")
            total = sum(it["qty"] * it["price"] for it in clean)
            Biro26Notify.notify_new_doc(
                res["data"]["cod"], nr,
                (c or {}).get("name") or f"COD {client_cod}",
                total, source="magazin" if c else "backoffice")
            # RO: confirmarea comenzii catre CLIENT (numar, data, suma, marfuri)
            #     — cerinta maib pentru e-commerce. Doar pentru comenzile din
            #     magazin, unde stim adresa clientului din cabinetul lui.
            # EN: order confirmation to the CUSTOMER — mandatory maib requirement;
            #     only for shop orders, where the client's e-mail is known.
            if c and c.get("email"):
                Biro26Notify.notify_client_order(
                    c["email"], c.get("name") or "", res["data"]["cod"], nr,
                    total, clean)
        return res

    @staticmethod
    def b2b_order() -> Dict[str, Any]:
        """RO: comanda B2B (angajati/integrari cu X-API-Key sau clienti
        autentificati) — plaseaza comanda si intoarce direct MOSTRA contului:
        numarul, totalul si linkurile semnate spre PDF si JSON.
        EN: B2B order — place it and return the invoice sample links."""
        res = Biro26Controller.shop_invoice()
        if not res.get("success"):
            return res
        from models.biro26_notify import Biro26Notify
        cod = res["data"]["cod"]
        sig = Biro26Notify.pdf_sig("invoice", cod)
        res["data"]["invoice_pdf"] = \
            f"/api/biro26/shop/report/invoice/{cod}?sig={sig}"
        res["data"]["invoice_html"] = \
            f"/api/biro26/shop/report-html/invoice/{cod}?sig={sig}"
        res["data"]["doc_json"] = f"/api/biro26/doc/{cod}"
        return res

    # ── documentele personale ale clientului (TMS_MUNC_ADDFILES) ─────────

    @staticmethod
    def _client_or_operator():
        """RO: (univers_cod, cine) — clientul vede DOAR dosarul sau; operatorul
        back-office (sesiune) poate lucra cu dosarul oricarui client (?cod=).
        EN: cabinet client sees only own files; back-office operator — any."""
        from flask import session
        c = session.get("biro26_client")
        if c:
            return int(c["univers_cod"]), f"client:{c.get('email') or c['univers_cod']}"
        if session.get("username") or session.get("authenticated"):
            cod = request.args.get("cod") or (
                (request.get_json(silent=True) or {}).get("cod")
                if request.is_json else None) or request.form.get("cod")
            if cod and str(cod).isdigit():
                return int(cod), f"operator:{session.get('username') or 'backoffice'}"
        return None, ""

    @staticmethod
    def client_quick_add() -> Dict[str, Any]:
        """RO: inregistrarea RAPIDA a unui client de catre OPERATOR (casier):
        minim = denumirea + tipul (fizica/juridica). Datele pot veni si din
        utilitarul local «Contragenti» (date.gov.md) — vezi butonul din pagina.
        Clientul ajunge in ACELEASI tabele ca inregistrarile de pe site.
        EN: operator-side quick client registration (same tables as sign-up)."""
        from flask import session
        from models.biro26_journal import Biro26Journal
        if not (session.get("username") or session.get("authenticated")):
            return {"success": False, "error": "auth required"}
        d = request.get_json(silent=True) or {}
        return Biro26Journal.client_quick_add(
            (d.get("name") or "").strip(),
            is_company=bool(d.get("is_company")),
            idno=(d.get("idno") or "").strip(),
            phone=(d.get("phone") or "").strip(),
            email=(d.get("email") or "").strip(),
            address=(d.get("address") or "").strip())

    @staticmethod
    def client_files_list() -> Dict[str, Any]:
        from models.biro26_client_files import Biro26ClientFiles, DOC_KINDS
        cod, _who = Biro26Controller._client_or_operator()
        if not cod:
            return {"success": False, "error": "login required"}
        r = Biro26ClientFiles.list(cod)
        if r.get("success"):
            r["kinds"] = DOC_KINDS
        return r

    @staticmethod
    def client_files_upload() -> Dict[str, Any]:
        """RO: incarcarea unui act din cabinet (buletin fata/verso, alt act)."""
        from models.biro26_client_files import Biro26ClientFiles
        cod, who = Biro26Controller._client_or_operator()
        if not cod:
            return {"success": False, "error": "login required"}
        f = request.files.get("file")
        if not f:
            return {"success": False, "error": "lipsește fișierul"}
        return Biro26ClientFiles.add(
            cod, request.form.get("kind") or "other",
            f.filename or "document", f.read(),
            mime=f.mimetype or "", who=who,
            ip=request.headers.get("X-Real-IP") or request.remote_addr or "",
            note=(request.form.get("note") or "")[:400])

    @staticmethod
    def client_files_get(file_id: int):
        import hmac
        import time
        from models.biro26_client_files import Biro26ClientFiles
        from models.biro26_notify import Biro26Notify
        # RO: LINK SEMNAT (?exp=&sig=) — actul se deschide direct din
        #     notificarea WhatsApp/Telegram, fara login, DAR: doar acel
        #     fisier, doar pina la expirare, si accesul se jurnalizeaza.
        # EN: signed, time-limited link so the document opens straight from
        #     the chat notification — one file only, logged like any access.
        sig = (request.args.get("sig") or "").strip()
        exp = (request.args.get("exp") or "").strip()
        if sig and exp.isdigit():
            if int(exp) < int(time.time()):
                return {"success": False, "error": "link expirat"}
            if hmac.compare_digest(sig, Biro26Notify.file_sig(int(file_id), int(exp))):
                return Biro26ClientFiles.get(
                    int(file_id), None, who="link-semnat",
                    ip=request.headers.get("X-Real-IP") or request.remote_addr or "")
        cod, who = Biro26Controller._client_or_operator()
        if not cod:
            return {"success": False, "error": "login required"}
        from flask import session
        # RO/EN: operatorul poate deschide orice dosar; clientul — doar al sau
        limit = None if (session.get("username")
                         and not session.get("biro26_client")) else cod
        return Biro26ClientFiles.get(
            int(file_id), limit, who=who,
            ip=request.headers.get("X-Real-IP") or request.remote_addr or "")

    @staticmethod
    def client_files_delete(file_id: int) -> Dict[str, Any]:
        from models.biro26_client_files import Biro26ClientFiles
        cod, who = Biro26Controller._client_or_operator()
        if not cod:
            return {"success": False, "error": "login required"}
        return Biro26ClientFiles.delete(
            int(file_id), cod, who=who,
            ip=request.headers.get("X-Real-IP") or request.remote_addr or "")

    @staticmethod
    def shop_my_invoices() -> Dict[str, Any]:
        """RO: cabinetul clientului — LISTA propriilor conturi de plata
        (nr, data, total) pentru sectiunea «Comenzile mele».
        EN: the client's own web invoices for the cabinet."""
        from flask import session
        from models.biro26_report import Biro26Report
        c = session.get("biro26_client")
        if not c:
            return {"success": False, "error": "login required"}
        return Biro26Report.docs_list(str(c["univers_cod"]),
                                      request.args.get("limit", 50, type=int))

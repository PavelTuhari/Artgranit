"""Biro26 module controller — thin HTTP handlers.

All methods @staticmethod, return {success, data?/output?, error?}.
Destructive package operations (import/archive/rollback/merge/prepare/assign)
mutate the live OfficePlus ERP; the UI gates them behind confirmation.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request, session

from models.biro26_oracle_store import Biro26Store, G_PARAMS
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
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_prices(
            d.get("codprice", 1), d.get("date_start"), d.get("date_end"))

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
            grupa=a.get("grupa"), price_date=a.get("price_date"),
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
                               or session.get("authenticated"))))

    @staticmethod
    def product_archive(cod: int) -> Dict[str, Any]:
        """RO: dezactivare/reactivare cartela (soft-delete nativ ISARHIV).
        EN: deactivate/reactivate a card (native ISARHIV soft-delete)."""
        d = request.get_json(silent=True) or {}
        return Biro26Store.set_product_archived(cod, bool(d.get("archived", True)))

    # ── shop display settings (admin: products per page etc.) ──
    @staticmethod
    def shop_settings_get() -> Dict[str, Any]:
        return {"success": True, "data": {
            "shop_page_size": Biro26Store.get_setting("SHOP_PAGE_SIZE", "24")}}

    @staticmethod
    def shop_settings_put() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        try:
            n = int(d.get("shop_page_size") or 24)
        except (TypeError, ValueError):
            return {"success": False, "error": "shop_page_size must be a number"}
        if not 1 <= n <= 200:
            return {"success": False, "error": "shop_page_size: 1..200"}
        r = Biro26Store.set_setting("SHOP_PAGE_SIZE", str(n))
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

    # ── product description + client comments (shop window / card) ──

    @staticmethod
    def shop_product_info(cod: int) -> Dict[str, Any]:
        """Public: description + comments for the shop's product window."""
        return Biro26Store.product_info(cod)

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
                                   price_date=d.get("price_effective") or None)
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
                                   price_date=d.get("price_effective") or None)
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
        return {"success": True,
                "data": {"name": c["name"], "email": c["email"]} if c else None}

    @staticmethod
    def shop_invoice() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        items = d.get("items") or []
        c = session.get("biro26_client")
        if c:
            client_cod = c["univers_cod"]
        elif d.get("client_cod") and session.get("username"):
            # RO/EN: back-office operator may issue for an explicit client COD
            client_cod = int(d["client_cod"])
        else:
            return {"success": False, "error": "login required"}
        clean = []
        for it in items:
            try:
                cod, qty, price = int(it["cod"]), float(it["qty"]), float(it.get("price") or 0)
            except Exception:
                return {"success": False, "error": "bad item format"}
            if qty <= 0:
                return {"success": False, "error": "qty must be > 0"}
            clean.append({"cod": cod, "qty": qty, "price": price,
                          "name": str(it.get("name") or "")[:180]})
        # RO: transportul tur-retur este OBLIGATORIU pentru clientii
        #     magazinului si se alege pe server dupa distanta comenzii
        #     (TMS_MPT_DISTANTE): TUR -> qty 1, KM -> qty = km. Liniile de
        #     transport trimise de client se ignora (anti-manipulare).
        # EN: round-trip transport is MANDATORY for shop clients and is
        #     picked server-side from the order distance: TUR -> qty 1,
        #     KM -> qty = km. Client-sent transport lines are discarded.
        if c:
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
            tariff_cods = {r["cod"] for r in
                           (Biro26Store.shop_transport_tariffs().get("data") or [])}
            clean = [it for it in clean if it["cod"] not in tariff_cods]
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
            pr = Biro26Store.shop_prices_for(need)
            if not pr.get("success"):
                return pr
            for it in clean:
                if c or it["price"] <= 0:
                    it["price"] = pr["data"].get(it["cod"], 0)
        res = Biro26Store.shop_create_invoice(client_cod, clean)
        if res.get("success"):
            # RO/EN: notificari email/Telegram/WhatsApp — fire-and-forget
            from models.biro26_notify import Biro26Notify
            Biro26Notify.notify_new_doc(
                res["data"]["cod"], res["data"]["nrset"],
                (c or {}).get("name") or f"COD {client_cod}",
                sum(it["qty"] * it["price"] for it in clean),
                source="magazin" if c else "backoffice")
        return res

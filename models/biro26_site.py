"""RO: Biro26Site — «limited admin»-ul vitrinei noului site Figma (TZ §6):
hero slides, «produsul zilei» (override), sectiunile paginii principale.
Persistenta: tabele Oracle normalizate YBIRO_SITE_* (nu KV, nu fisiere).
EN: storefront limited-admin storage for the new Figma site homepage."""

from typing import Any, Dict

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows


class Biro26Site:

    # RO: cache-ul intregii configuratii publice. Fiecare interogare trece
    #     printr-un subproces Oracle thick (~1s+), iar config() face 3-4 —
    #     endpoint-ul raspundea in ~5s LA FIECARE pagina. Configuratia se
    #     schimba doar din admin, deci 60s de cache nu se simt; orice save
    #     din admin o invalideaza imediat prin _invalidate().
    # EN: whole-config cache (60s TTL); every admin save invalidates it.
    _config_cache: Dict[str, Any] = {"exp": 0.0, "data": None}

    @staticmethod
    def _invalidate() -> None:
        Biro26Site._config_cache["exp"] = 0.0
        Biro26Site._featured_cache["exp"] = 0.0

    # ── public: configuratia vitrinei pentru pagina principala ─────────
    @staticmethod
    def config() -> Dict[str, Any]:
        import time as _t
        c = Biro26Site._config_cache
        if c["data"] is not None and c["exp"] > _t.time():
            return c["data"]
        db = Biro26DB()
        hero = _rows(db.execute_query(
            "SELECT ID, KICKER_RO, KICKER_RU, TITLE_RO, TITLE_RU, SUB_RO, "
            "SUB_RU, CTA_URL, BG, ORD, ENABLED FROM YBIRO_SITE_HERO "
            "WHERE ENABLED = '1' ORDER BY ORD, ID"))
        sections = _rows(db.execute_query(
            "SELECT CODE, ENABLED, ORD FROM YBIRO_SITE_SECTION ORDER BY ORD"))
        deal = None
        d = _rows(db.execute_query(
            "SELECT ID, PRODUCT_COD, TO_CHAR(ENDS_AT,'YYYY-MM-DD\"T\"HH24:MI:SS') "
            "ENDS_AT, ENABLED FROM YBIRO_SITE_DEAL WHERE ENABLED = '1' "
            "AND PRODUCT_COD IS NOT NULL ORDER BY ID DESC"))
        if d:
            deal = {"ends_at": d[0].get("ends_at"), "product": None}
            try:
                from models.biro26_oracle_store import Biro26Store
                pr = Biro26Store.get_products_stock(
                    cod=int(d[0]["product_cod"]), limit=1)
                rows = pr.get("data") or []
                if rows:
                    deal["product"] = rows[0]
            except Exception:
                deal = None
        res = {"success": True, "data": {
            "hero": [{k.lower(): v for k, v in h.items()} for h in hero],
            "sections": [{k.lower(): v for k, v in s.items()} for s in sections],
            "featured": Biro26Site.featured_products(),
            "deal": deal}}
        c.update(exp=_t.time() + 60, data=res)
        return res

    # ── admin: hero slides CRUD ────────────────────────────────────────
    @staticmethod
    def hero_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, KICKER_RO, KICKER_RU, TITLE_RO, TITLE_RU, SUB_RO, "
            "SUB_RU, CTA_URL, BG, ORD, ENABLED FROM YBIRO_SITE_HERO "
            "ORDER BY ORD, ID"))
        return {"success": True,
                "data": [{k.lower(): v for k, v in r.items()} for r in rows]}

    @staticmethod
    def hero_save(d: Dict[str, Any]) -> Dict[str, Any]:
        p = {"kr": (d.get("kicker_ro") or "")[:200],
             "ku": (d.get("kicker_ru") or "")[:200],
             "tr": (d.get("title_ro") or "")[:400],
             "tu": (d.get("title_ru") or "")[:400],
             "sr": (d.get("sub_ro") or "")[:400],
             "su": (d.get("sub_ru") or "")[:400],
             "cta": (d.get("cta_url") or "/catalog")[:400],
             "bg": (d.get("bg") or "")[:240],
             "o": int(d.get("ord") or 0),
             "e": "1" if str(d.get("enabled", "1")) == "1" else "0"}
        db = Biro26DB()
        if d.get("id"):
            p["i"] = int(d["id"])
            r = db.execute_dml(
                "UPDATE YBIRO_SITE_HERO SET KICKER_RO=:kr, KICKER_RU=:ku, "
                "TITLE_RO=:tr, TITLE_RU=:tu, SUB_RO=:sr, SUB_RU=:su, "
                "CTA_URL=:cta, BG=:bg, ORD=:o, ENABLED=:e WHERE ID=:i", p)
        else:
            r = db.execute_dml(
                "INSERT INTO YBIRO_SITE_HERO (ID, KICKER_RO, KICKER_RU, "
                "TITLE_RO, TITLE_RU, SUB_RO, SUB_RU, CTA_URL, BG, ORD, ENABLED) "
                "VALUES (YBIRO_SITE_HERO_SEQ.NEXTVAL, :kr, :ku, :tr, :tu, "
                ":sr, :su, :cta, :bg, :o, :e)", p)
        Biro26Site._invalidate()
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    @staticmethod
    def hero_delete(hid: int) -> Dict[str, Any]:
        r = Biro26DB().execute_dml(
            "DELETE FROM YBIRO_SITE_HERO WHERE ID = :i", {"i": int(hid)})
        Biro26Site._invalidate()
        return r

    # ── admin: produsul zilei (override) ───────────────────────────────
    @staticmethod
    def deal_get() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, PRODUCT_COD, TO_CHAR(ENDS_AT,'YYYY-MM-DD HH24:MI') "
            "ENDS_AT, ENABLED FROM YBIRO_SITE_DEAL ORDER BY ID DESC"))
        return {"success": True,
                "data": ({k.lower(): v for k, v in rows[0].items()}
                         if rows else None)}

    @staticmethod
    def deal_save(d: Dict[str, Any]) -> Dict[str, Any]:
        db = Biro26DB()
        cod = int(d.get("product_cod") or 0) or None
        ends = (d.get("ends_at") or "").strip() or None
        enabled = "1" if str(d.get("enabled", "1")) == "1" else "0"
        # RO: un singur rind activ — il actualizam sau il cream
        rows = _rows(db.execute_query(
            "SELECT ID FROM YBIRO_SITE_DEAL ORDER BY ID DESC"))
        if rows:
            r = db.execute_dml(
                "UPDATE YBIRO_SITE_DEAL SET PRODUCT_COD=:c, ENABLED=:e, "
                "ENDS_AT = CASE WHEN :d IS NULL THEN NULL ELSE "
                "TO_DATE(:d,'YYYY-MM-DD HH24:MI') END WHERE ID=:i",
                {"c": cod, "e": enabled, "d": ends, "i": rows[0]["id"]})
        else:
            r = db.execute_dml(
                "INSERT INTO YBIRO_SITE_DEAL (ID, PRODUCT_COD, ENDS_AT, ENABLED) "
                "VALUES (YBIRO_SITE_DEAL_SEQ.NEXTVAL, :c, CASE WHEN :d IS NULL "
                "THEN NULL ELSE TO_DATE(:d,'YYYY-MM-DD HH24:MI') END, :e)",
                {"c": cod, "d": ends, "e": enabled})
        Biro26Site._invalidate()
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    # ── "Cele mai populare": lista de COD-uri setata in backoffice ─────
    _featured_cache = {"exp": 0.0, "rows": []}

    @staticmethod
    def featured_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, PRODUCT_COD, ORD FROM YBIRO_SITE_FEATURED "
            "ORDER BY ORD, ID"))
        return {"success": True,
                "data": [{k.lower(): v for k, v in r.items()} for r in rows]}

    @staticmethod
    def featured_save(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: inlocuieste intreaga lista (COD-uri in ordinea dorita)."""
        try:
            cods = [int(c) for c in (d.get("cods") or []) if str(c).strip()][:50]
        except (TypeError, ValueError):
            return {"success": False, "error": "COD invalid"}
        db = Biro26DB()
        db.execute_dml("DELETE FROM YBIRO_SITE_FEATURED")
        for i, c in enumerate(cods, 1):
            r = db.execute_dml(
                "INSERT INTO YBIRO_SITE_FEATURED (ID, PRODUCT_COD, ORD) "
                "VALUES (YBIRO_SITE_FEATURED_SEQ.NEXTVAL, :c, :o)",
                {"c": c, "o": i})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
        Biro26Site._invalidate()
        return {"success": True, "data": {"count": len(cods)}}

    @staticmethod
    def featured_products() -> list:
        """RO: fisele produselor din lista (cache 120s — pagina publica)."""
        import time as _t
        c = Biro26Site._featured_cache
        if c["exp"] > _t.time():
            return c["rows"]
        rows = []
        try:
            from models.biro26_oracle_store import Biro26Store
            ids = _rows(Biro26DB().execute_query(
                "SELECT PRODUCT_COD FROM YBIRO_SITE_FEATURED ORDER BY ORD, ID"))
            for r in ids[:25]:
                pr = Biro26Store.get_products_stock(
                    cod=int(r["product_cod"]), limit=1)
                got = pr.get("data") or []
                if got:
                    rows.append(got[0])
        except Exception:
            rows = []
        c.update(exp=_t.time() + 120, rows=rows)
        return rows

    # ── newsletter: abonare publica + lista pentru admin ───────────────
    @staticmethod
    def subscribe(d: Dict[str, Any]) -> Dict[str, Any]:
        import re
        email = (d.get("email") or "").strip().lower()[:200]
        lang = (d.get("lang") or "ro")[:4]
        if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z0-9-]{2,}$", email, re.I):
            return {"success": False, "error": "Email invalid"}
        db = Biro26DB()
        ex = _rows(db.execute_query(
            "SELECT ID FROM YBIRO_SITE_SUBSCRIBER WHERE EMAIL = :e",
            {"e": email}))
        if ex:
            db.execute_dml("UPDATE YBIRO_SITE_SUBSCRIBER SET ENABLED='1' "
                           "WHERE EMAIL = :e", {"e": email})
            return {"success": True, "data": {"already": True}}
        r = db.execute_dml(
            "INSERT INTO YBIRO_SITE_SUBSCRIBER (ID, EMAIL, LANG) VALUES "
            "(YBIRO_SITE_SUBSCRIBER_SEQ.NEXTVAL, :e, :l)",
            {"e": email, "l": lang})
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    @staticmethod
    def subscribers_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, EMAIL, LANG, TO_CHAR(CREATED,'DD.MM.YYYY HH24:MI') "
            "CREATED, ENABLED FROM YBIRO_SITE_SUBSCRIBER ORDER BY ID DESC"))
        return {"success": True,
                "data": [{k.lower(): v for k, v in r.items()} for r in rows]}

    # ── admin: sectiunile paginii principale on/off ────────────────────
    @staticmethod
    def section_save(d: Dict[str, Any]) -> Dict[str, Any]:
        r = Biro26DB().execute_dml(
            "UPDATE YBIRO_SITE_SECTION SET ENABLED=:e WHERE CODE=:c",
            {"e": "1" if str(d.get("enabled", "1")) == "1" else "0",
             "c": (d.get("code") or "")[:40]})
        Biro26Site._invalidate()
        return r

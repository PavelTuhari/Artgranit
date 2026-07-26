"""RO: Biro26Site — «limited admin»-ul vitrinei noului site Figma (TZ §6):
hero slides, «produsul zilei» (override), sectiunile paginii principale.
Persistenta: tabele Oracle normalizate YBIRO_SITE_* (nu KV, nu fisiere).
EN: storefront limited-admin storage for the new Figma site homepage."""

from typing import Any, Dict

from models.biro26_db import Biro26DB


def _rows(res):
    return res.get("rows", []) if isinstance(res, dict) else (res or [])


class Biro26Site:

    # ── public: configuratia vitrinei pentru pagina principala ─────────
    @staticmethod
    def config() -> Dict[str, Any]:
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
        return {"success": True, "data": {
            "hero": [{k.lower(): v for k, v in h.items()} for h in hero],
            "sections": [{k.lower(): v for k, v in s.items()} for s in sections],
            "deal": deal}}

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
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    @staticmethod
    def hero_delete(hid: int) -> Dict[str, Any]:
        return Biro26DB().execute_dml(
            "DELETE FROM YBIRO_SITE_HERO WHERE ID = :i", {"i": int(hid)})

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
        return r if r.get("success") else {"success": False,
                                           "error": r.get("message")}

    # ── admin: sectiunile paginii principale on/off ────────────────────
    @staticmethod
    def section_save(d: Dict[str, Any]) -> Dict[str, Any]:
        return Biro26DB().execute_dml(
            "UPDATE YBIRO_SITE_SECTION SET ENABLED=:e WHERE CODE=:c",
            {"e": "1" if str(d.get("enabled", "1")) == "1" else "0",
             "c": (d.get("code") or "")[:40]})

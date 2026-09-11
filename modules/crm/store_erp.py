"""Aducerea datelor reale din ERP in CRM (marfa si contragentii).

RO: executia regulilor din `erp_source.py`, pe conexiunea OfficePlus 11g.
Doua operatii, amindoua idempotente:

  * `import_item(cod)` — pozitia din dictionarul ERP intra o data in
    CRM_ITEM (ERP_COD = TMS_UNIVERS.COD); a doua oara doar se reimprospateaza
    pretul, stocul si denumirea. Asa comanda pastreaza legatura (ITEM_ID) si
    dupa ce pretul din ERP se schimba;
  * `sync_clients()` — contragentii ERP (TMS_ORG) si conturile magazinului
    (YBIRO_CLIENT) intra in CRM_CLIENT, unite dupa IDNO.

Doar chiriasul OfficePlus vede datele reale: `Tenant.real`. Setul demo e alt
chirias ('demo') si nu se atinge niciodata de aici.
EN: writes real ERP goods/clients into the CRM tables of the office tenant.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

from modules.crm import erp_source as src
from modules.crm.tenant import Tenant


class ErpSource:
    """RO: sursa reala pentru un chirias. Scrie doar pentru OfficePlus."""

    def __init__(self, tenant: Tenant, db: Optional[Biro26DB] = None):
        self.t = tenant
        self.db = db or Biro26DB()

    # ── utilitare ────────────────────────────────────────────────────────
    def _rows(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        r = self.db.execute_query(sql, params or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare SQL")
        return _rows(r)

    def _dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        r = self.db.execute_dml(sql, params or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare DML")

    def _guard(self) -> None:
        if not self.t.real:
            raise ValueError("datele reale sint doar pentru OfficePlus "
                             "(regimul demo si cabinetul clientului au datele lor)")

    # ── marfa ────────────────────────────────────────────────────────────
    def search_goods(self, q: str = "", limit: int = 50, only_active: bool = True) -> List[Dict[str, Any]]:
        """RO: cautare vie in dictionarul ERP; nu scrie nimic."""
        self._guard()
        sql, p = src.goods_sql(q, only_active=only_active, limit=limit)
        out = []
        for r in self._rows(sql, p):
            it = src.item_from_good(r)
            it["group"] = r.get("gr1") or ""
            it["supplier"] = r.get("furnizor") or ""
            it["archived"] = 1 if (r.get("isarhiv") or "0") not in ("0", None) else 0
            out.append(it)
        return out

    def good(self, cod: int) -> Optional[Dict[str, Any]]:
        sql, p = src.goods_sql(cod=int(cod), limit=1)
        rows = self._rows(sql, p)
        return src.item_from_good(rows[0]) if rows else None

    def item_id_by_erp(self, cod: int) -> int:
        rows = self._rows("SELECT ID FROM CRM_ITEM WHERE OWNER_KIND = :ok AND OWNER_ID = :oi "
                          "AND ERP_COD = :c", dict(self.t.params(), c=int(cod)))
        return int(rows[0]["id"]) if rows else 0

    def import_item(self, cod: int) -> Dict[str, Any]:
        """RO: aduce (sau reimprospateaza) o pozitie ERP in CRM_ITEM."""
        self._guard()
        it = self.good(int(cod))
        if not it:
            raise LookupError("pozitia %s nu exista in dictionarul ERP" % cod)
        rid = self.item_id_by_erp(cod)
        p = dict(self.t.params(), code=it["code"], name=it["name"], kind=it["kind"],
                 un=it["unit_"], price=it["price"], stock=it["stock"], c=int(cod))
        if rid:
            # RO: exact parametrii instructiunii (ORA-01036 la o legatura nefolosita)
            up = {k: p[k] for k in ("code", "name", "un", "price", "stock", "ok", "oi")}
            up["id"] = rid
            self._dml("UPDATE CRM_ITEM SET CODE = :code, NAME = :name, UNIT_ = :un, "
                      "PRICE = :price, STOCK = :stock, SYNCED = SYSDATE "
                      "WHERE ID = :id AND OWNER_KIND = :ok AND OWNER_ID = :oi", up)
        else:
            self._dml("INSERT INTO CRM_ITEM (ID, OWNER_KIND, OWNER_ID, CODE, NAME, KIND, UNIT_, "
                      "PRICE, VAT, STOCK, SRC, ERP_COD, SYNCED) VALUES "
                      "(CRM_ITEM_SEQ.NEXTVAL, :ok, :oi, :code, :name, :kind, :un, "
                      ":price, 20, :stock, 'erp', :c, SYSDATE)", p)
            rid = self.item_id_by_erp(cod)
        it["id"] = rid
        it["imported"] = True
        return it

    def refresh_items(self, limit: int = 500) -> int:
        """RO: reimprospateaza pretul si stocul pozitiilor deja aduse."""
        self._guard()
        rows = self._rows("SELECT ERP_COD FROM CRM_ITEM WHERE OWNER_KIND = :ok AND OWNER_ID = :oi "
                          "AND ERP_COD IS NOT NULL AND ROWNUM <= :lim",
                          dict(self.t.params(), lim=int(limit)))
        n = 0
        for r in rows:
            try:
                self.import_item(int(r["erp_cod"]))
                n += 1
            except LookupError:            # pozitia a disparut din dictionar
                continue
        return n

    # ── contragenti ──────────────────────────────────────────────────────
    def _client_by_key(self, idno: str) -> int:
        rows = self._rows("SELECT ID FROM CRM_CLIENT WHERE OWNER_KIND = :ok AND OWNER_ID = :oi "
                          "AND IDNO = :idno", dict(self.t.params(), idno=idno))
        return int(rows[0]["id"]) if rows else 0

    def _save_client(self, c: Dict[str, Any]) -> str:
        """RO: scrie un contragent; intoarce 'nou' sau 'actualizat'."""
        idno = (c.get("idno") or "").strip()
        if not idno:
            return "sarit"
        rid = self._client_by_key(idno)
        # RO: Oracle refuza legaturile nefolosite (ORA-01036), deci fiecare
        #     ramura primeste EXACT parametrii instructiunii ei.
        p = {"idno": idno, "name": c.get("name") or "",
             "addr": c.get("address") or "", "phone": c.get("phone") or "",
             "email": c.get("email") or "", "cp": c.get("contact_person") or "",
             "mng": c.get("managers") or "", "ct": c.get("client_type") or "Клиент",
             "srcv": c.get("source") or "erp", "erp": c.get("erp_cod") or None}
        if rid:
            up = {k: p[k] for k in ("name", "addr", "phone", "email", "cp", "mng", "srcv", "erp")}
            up["id"] = rid
            # RO: nu se sterge ce a scris operatorul — se completeaza doar golurile
            self._dml("UPDATE CRM_CLIENT SET NAME = NVL(:name, NAME), "
                      "ADDRESS = NVL(ADDRESS, :addr), PHONE = NVL(PHONE, :phone), "
                      "EMAIL = NVL(EMAIL, :email), CONTACT_PERSON = NVL(CONTACT_PERSON, :cp), "
                      "MANAGERS = NVL(MANAGERS, :mng), SOURCE = :srcv, ERP_COD = NVL(:erp, ERP_COD), "
                      "UPDATED = SYSDATE WHERE ID = :id", up)
            return "actualizat"
        self._dml("INSERT INTO CRM_CLIENT (ID, OWNER_KIND, OWNER_ID, IDNO, NAME, ADDRESS, PHONE, "
                  "EMAIL, CONTACT_PERSON, MANAGERS, CLIENT_TYPE, SOURCE, ERP_COD, CREATED, UPDATED) "
                  "VALUES (CRM_CLIENT_SEQ.NEXTVAL, :ok, :oi, :idno, :name, :addr, :phone, "
                  ":email, :cp, :mng, :ct, :srcv, :erp, SYSDATE, SYSDATE)",
                  dict(self.t.params(), **p))
        return "nou"

    def sync_clients(self) -> Dict[str, int]:
        """RO: TMS_ORG + YBIRO_CLIENT -> CRM_CLIENT (chiriasul OfficePlus)."""
        self._guard()
        st = {"nou": 0, "actualizat": 0, "sarit": 0}
        for r in self._rows(src.ORG_SQL):
            st[self._save_client(src.client_from_org(r))] += 1
        for r in self._rows(src.SHOP_SQL):
            st[self._save_client(src.client_from_shop(r))] += 1
        return st

    # ── starea sursei (pentru pagina) ────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        goods = int(self._rows("SELECT COUNT(*) C FROM TMS_UNIVERS WHERE TIP = 'P' "
                               "AND (ISARHIV IS NULL OR ISARHIV = '0')")[0]["c"])
        orgs = int(self._rows("SELECT COUNT(*) C FROM TMS_ORG")[0]["c"])
        shop = int(self._rows("SELECT COUNT(*) C FROM YBIRO_CLIENT")[0]["c"])
        mine = self._rows("SELECT COUNT(*) C, SUM(CASE WHEN ERP_COD IS NULL THEN 0 ELSE 1 END) E "
                          "FROM CRM_ITEM WHERE OWNER_KIND = :ok AND OWNER_ID = :oi", self.t.params())
        cl = self._rows("SELECT COUNT(*) C FROM CRM_CLIENT WHERE OWNER_KIND = :ok AND OWNER_ID = :oi",
                        self.t.params())
        return {"erp_goods": goods, "erp_orgs": orgs, "shop_clients": shop,
                "items": int(mine[0]["c"] or 0), "items_erp": int(mine[0]["e"] or 0),
                "clients": int(cl[0]["c"] or 0), "tenant": self.t.kind, "real": self.t.real}

    # ── vederi ERP: marfa si comenzile reale (12.09.2026) ────────────────
    def items_view(self, q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        """RO: marfa reala din dictionar, gata de afisat in «Nomenclator».
        Pozitiile deja aduse in CRM nu se repeta — ele au rindul lor propriu."""
        self._guard()
        sql, p = src.goods_sql(q, only_active=True, limit=limit)
        taken = {int(r["erp_cod"]) for r in self._rows(
            "SELECT ERP_COD FROM CRM_ITEM WHERE OWNER_KIND = :ok AND OWNER_ID = :oi "
            "AND ERP_COD IS NOT NULL", self.t.params())}
        return [src.item_row(r) for r in self._rows(sql, p)
                if int(r.get("cod") or 0) not in taken]

    def orders_view(self, q: str = "", limit: int = 200) -> List[Dict[str, Any]]:
        """RO: comenzile reale = conturile de plata ale magazinului."""
        self._guard()
        sql, p = src.orders_sql(q, limit=limit)
        return [src.order_from_doc(r) for r in self._rows(sql, p)]

    def order_view(self, cod: int) -> Optional[Dict[str, Any]]:
        self._guard()
        sql, p = src.orders_sql(cod=int(cod))
        rows = self._rows(sql, p)
        if not rows:
            return None
        out = src.order_from_doc(rows[0])
        out["lines"] = self.order_lines_view(cod)
        return out

    def order_lines_view(self, cod: int) -> List[Dict[str, Any]]:
        return [src.line_from_doc(r) for r in
                self._rows(src.ORDER_LINES_SQL, {"cod": int(cod)})]

    def item_view(self, cod: int) -> Optional[Dict[str, Any]]:
        self._guard()
        sql, p = src.goods_sql(cod=int(cod), limit=1)
        rows = self._rows(sql, p)
        return src.item_row(rows[0]) if rows else None

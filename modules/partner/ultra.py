"""Clientul Ultra B2B API — officeplus.md ca PARTENER al ultra.md.

RO: consumam API-ul de dealer al Ultra (eshop.ultra.md/api) si aducem
catalogul lor in ERP-ul una.md pe drumul STANDARD de import: rindurile intra
in tabela-tampon BIRO26_GOODS (SHEET='ULTRA', GUID = uuid-ul Ultra), iar
publicarea in nomenclator ramine pe pipeline-ul existent al operatorului
(validate -> prepare -> assign-keys), exact ca la sursele impreso/officeshop.

Sincronizare: prima rulare = tot catalogul (paginat cite 1000); urmatoarele =
incremental prin /api/changes, cu reperul `next_since` tinut in YBIRO_SETTINGS
(PARTNER_ULTRA_SINCE). Credentialele: PARTNER_ULTRA_USER / _PASSWORD / _BASE
in YBIRO_SETTINGS (se introduc din pagina de administrare a modulului).

EN: Ultra dealer-API client; full + incremental sync into the standard
BIRO26_GOODS staging; publication stays on the operator pipeline.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

TIMEOUT_S = 60
PAGE = 1000
BATCH = 40          # rinduri per bloc PL/SQL la upsert (un subproces per bloc)


class UltraClient:

    def __init__(self, base: str, username: str, password: str):
        self.base = (base or "https://eshop.ultra.md/api").rstrip("/")
        self.username = username
        self.password = password
        self._token: Optional[str] = None
        self._sort_ok = True        # vezi iter_products: sortarea poate cadea

    @classmethod
    def from_settings(cls) -> "UltraClient":
        from models.biro26_oracle_store import Biro26Store
        return cls(Biro26Store.get_setting("PARTNER_ULTRA_BASE",
                                           "https://eshop.ultra.md/api"),
                   Biro26Store.get_setting("PARTNER_ULTRA_USER", ""),
                   Biro26Store.get_setting("PARTNER_ULTRA_PASSWORD", ""))

    # ── HTTP ───────────────────────────────────────────────────────────
    def _req(self, method: str, path: str, payload: Optional[Dict] = None,
             params: Optional[Dict] = None, auth: bool = True) -> Dict[str, Any]:
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(
                {k: v for k, v in params.items() if v not in (None, "")})
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "OfficePlus-Partner/1.0",
            **({"Authorization": f"Bearer {self._token}"}
               if auth and self._token else {}),
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                return {"success": True,
                        "data": json.loads(resp.read().decode() or "{}")}
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:400]
            return {"success": False, "status": e.code, "error": body}
        except Exception as e:                               # noqa: BLE001
            return {"success": False, "error": str(e)[:300]}

    def login(self) -> Dict[str, Any]:
        if not (self.username and self.password):
            return {"success": False,
                    "error": "RO: credentialele Ultra lipsesc — completati-le "
                             "in pagina Partner API / EN: Ultra credentials "
                             "are not configured"}
        r = self._req("POST", "/auth/token",
                      {"username": self.username, "password": self.password},
                      auth=False)
        if r.get("success"):
            self._token = (r["data"] or {}).get("access_token")
            if not self._token:
                return {"success": False, "error": "no access_token in reply"}
        return r

    def test(self) -> Dict[str, Any]:
        """RO: verificarea conexiunii pentru butonul din admin."""
        r = self.login()
        if not r.get("success"):
            return r
        r2 = self._req("GET", "/product", params={"limit": 1})
        if not r2.get("success"):
            return r2
        return {"success": True,
                "message": "RO: conectat la Ultra B2B API / EN: connected",
                "sample": (r2["data"].get("data") or r2["data"]
                           if isinstance(r2["data"], dict) else r2["data"])}

    # ── citirea catalogului ────────────────────────────────────────────
    def iter_products(self):
        """RO: generator peste TOT catalogul, paginat cite 1000."""
        offset = 0
        while True:
            # RO: paginarea Ultra FARA sortare e instabila (prima trecere:
            #     38.706 rinduri, doar 26.010 uuid-uri unice), deci cerem o
            #     ordine fixa. ATENTIE: `name_asc` din documentatia LOR da
            #     "Server Error" pe API-ul real — verificat 29.08.2026;
            #     `updated_at` merge. Daca si el cade, continuam fara sortare
            #     (deduplicarea pe uuid de mai jos ne acopera).
            # EN: their documented `name_asc` 500s on the live API; use
            #     `updated_at`, falling back to unsorted.
            params = {"limit": PAGE, "offset": offset}
            if self._sort_ok:
                params["sort"] = "updated_at"
            r = self._req("GET", "/product", params=params)
            if not r.get("success") and self._sort_ok:
                self._sort_ok = False           # o singura data, apoi fara sort
                r = self._req("GET", "/product",
                              params={"limit": PAGE, "offset": offset})
            if not r.get("success"):
                raise RuntimeError(f"GET /product: {r.get('error')}")
            body = r["data"]
            rows = body.get("data") if isinstance(body, dict) else body
            rows = rows or []
            for row in rows:
                yield row
            if len(rows) < PAGE:
                return
            offset += PAGE

    def changed_ids(self, since: str) -> (List[str], str):
        """RO: ID-urile schimbate de la `since`, prin /api/changes."""
        ids, next_since = set(), since
        while True:
            r = self._req("GET", "/changes",
                          params={"since": next_since, "limit": 1000})
            if not r.get("success"):
                raise RuntimeError(f"GET /changes: {r.get('error')}")
            body = r["data"] or {}
            for ch in body.get("changes") or []:
                if ch.get("entity") in ("product", "price", "quantity"):
                    ids.add(str(ch.get("entity_id")))
            next_since = body.get("next_since") or next_since
            if not body.get("has_more"):
                return list(ids), next_since

    def products_batch(self, codes: List[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for i in range(0, len(codes), 1000):
            r = self._req("POST", "/product/batch",
                          {"ultra_codes": codes[i:i + 1000]})
            if not r.get("success"):
                raise RuntimeError(f"POST /product/batch: {r.get('error')}")
            body = r["data"]
            out += (body.get("data") if isinstance(body, dict) else body) or []
        return out

    # ── scrierea in tampon (BIRO26_GOODS) ─────────────────────────────
    @staticmethod
    def _money(v: Any) -> Optional[float]:
        """RO: pretul REAL al Ultra e un obiect {amount, currency:{rate}} —
        dealer-ul primeste user_price in USD cu cursul zilei, retailul in
        MDL. Convertim totul in MDL (amount * rate). Documentatia lor arata
        numere simple; realitatea (verificata 28.08.2026) arata dict-uri.
        EN: Ultra prices are {amount, currency:{rate}} dicts — normalise to
        MDL; plain numbers are accepted too."""
        if v is None:
            return None
        if isinstance(v, dict):
            try:
                amount = float(v.get("amount") or 0)
                rate = float(((v.get("currency") or {}).get("rate")) or 1)
                mdl = round(amount * rate, 2)
                return mdl if mdl > 0 else None
            except (TypeError, ValueError):
                return None
        try:
            f = round(float(v), 2)
            return f if f > 0 else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _lang(v: Any, *keys: str) -> str:
        """RO: cimpurile multilingve vin cind dict, cind JSON-STRING
        ('{"ro":...}') — realitatea API-ului Ultra difera de documentatie.
        EN: multilingual fields arrive as dicts OR JSON strings."""
        if isinstance(v, str) and v.startswith("{"):
            try:
                v = json.loads(v)
            except ValueError:
                return v
        if isinstance(v, dict):
            for k in keys:
                if v.get(k):
                    return str(v[k])
            return ""
        return str(v or "")

    @staticmethod
    def _staging_row(p: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """RO: obiectul Ultra -> rindul tabelei-tampon. Stub-urile 'fara
        imagine' se arunca (lectia impreso)."""
        images = [u for u in (p.get("image_urls") or []) if u
                  and "noimage" not in u.lower() and "placeholder" not in u.lower()]
        code = p.get("ultra_code") or p.get("code")
        uuid = p.get("ultra_uuid") or p.get("uuid")
        if not (code and uuid):
            return None
        # RO: regula sursei ULTRA din TMS_ORG_IMPSRC (echipa de import):
        #     articol "slab" — sub 6 caractere SAU pur numeric — primeste
        #     prefixul ULT, ca sa nu se bata cap in cap cu articolele altor
        #     furnizori la potrivirea in nomenclator.
        # EN: weak articles (short or purely numeric) get the ULT prefix,
        #     per the import team's source rules.
        art = str(code)[:60]
        if art.isdigit() or len(art) < 6:
            art = ("ULT" + art)[:60]
        name_ro = UltraClient._lang(p.get("product_name"), "ro", "ru", "en")
        cat = p.get("category") or {}
        hierarchy = cat.get("hierarchy") or []
        cat_ro = UltraClient._lang(cat.get("name"), "ro", "ru", "en")
        retail = UltraClient._money(p.get("fixed_price"))             or UltraClient._money(p.get("promo_b2b"))
        dealer = UltraClient._money(p.get("user_price"))             or UltraClient._money(p.get("price_d"))
        return {
            "guid": str(uuid)[:100],
            "articol": art,
            "denumire": name_ro[:500],
            "brand": str((p.get("brand") or {}).get("name") or "")[:100] or None,
            "grupa": (UltraClient._lang(
                hierarchy[0] if hierarchy else cat_ro, "ro", "ru")[:200] or None),
            "categorie": (UltraClient._lang(
                hierarchy[-1], "ro", "ru")[:200] if len(hierarchy) > 1
                else (cat_ro[:200] or None)),
            "stoc": int(p.get("quantity") or 0),
            "retail1": (str(retail) if retail is not None else None),
            "angro": (str(dealer) if dealer is not None else None),
            "photo": (images[0][:1000] if images else None),
        }

    @staticmethod
    def upsert_staging(rows: List[Dict[str, Any]]) -> int:
        """RO: MERGE pe GUID in blocuri de 40 (un subproces Oracle per bloc).
        EN: MERGE by GUID in blocks of 40 rows."""
        from models.biro26_db import Biro26DB
        db = Biro26DB()
        written = 0
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            stmts, params = [], {}
            for j, r in enumerate(chunk):
                for k, v in r.items():
                    params[f"{k}{j}"] = v
                stmts.append(
                    "MERGE INTO BIRO26_GOODS g USING "
                    f"(SELECT :guid{j} GUID FROM dual) s ON (g.GUID = s.GUID) "
                    "WHEN MATCHED THEN UPDATE SET "
                    f"g.ARTICOL=:articol{j}, g.DENUMIRE=:denumire{j}, "
                    f"g.BRAND=:brand{j}, g.GRUPA=:grupa{j}, "
                    f"g.CATEGORIE=:categorie{j}, g.STOC=:stoc{j}, "
                    f"g.RETAIL1=:retail1{j}, g.ANGRO=:angro{j}, "
                    f"g.PHOTO_URL=:photo{j}, g.SHEET='ULTRA' "
                    "WHEN NOT MATCHED THEN INSERT "
                    "(GUID, ARTICOL, DENUMIRE, BRAND, GRUPA, CATEGORIE, STOC, "
                    " RETAIL1, ANGRO, PHOTO_URL, SHEET, FURNIZOR) VALUES "
                    f"(:guid{j}, :articol{j}, :denumire{j}, :brand{j}, "
                    f":grupa{j}, :categorie{j}, :stoc{j}, :retail1{j}, "
                    f":angro{j}, :photo{j}, 'ULTRA', 'Ultra');")
            block = "BEGIN " + " ".join(stmts) + " END;"
            r = db.execute_dml(block, params, timeout=120)
            if not r.get("success"):
                raise RuntimeError(f"upsert: {str(r.get('message'))[:200]}")
            written += len(chunk)
        return written

    # ── sincronizarea propriu-zisa ─────────────────────────────────────
    def sync(self, full: bool = False) -> Dict[str, Any]:
        from models.biro26_oracle_store import Biro26Store, cache_clear
        from modules.partner.store import PartnerStore
        import datetime
        r = self.login()
        if not r.get("success"):
            return r
        since = Biro26Store.get_setting("PARTNER_ULTRA_SINCE", "")
        try:
            if full or not since:
                rows, seen, uniq = [], 0, set()
                for p in self.iter_products():
                    seen += 1
                    row = self._staging_row(p)
                    if row and row["guid"] not in uniq:
                        uniq.add(row["guid"])
                        rows.append(row)
                written = self.upsert_staging(rows)
                mode = "full"
            else:
                ids, next_since = self.changed_ids(since)
                products = self.products_batch(ids) if ids else []
                rows = [x for x in (self._staging_row(p) for p in products) if x]
                written = self.upsert_staging(rows)
                seen = len(ids)
                mode = "incremental"
            Biro26Store.set_setting(
                "PARTNER_ULTRA_SINCE",
                datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            cache_clear()
            PartnerStore.log(None, "ultra_sync",
                             f"mode={mode} seen={seen} written={written}")
            return {"success": True, "mode": mode,
                    "seen": seen, "written": written}
        except RuntimeError as e:
            PartnerStore.log(None, "ultra_sync_fail", str(e)[:900])
            return {"success": False, "error": str(e)}

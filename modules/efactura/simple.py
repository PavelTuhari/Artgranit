"""Import SIMPLU al facturilor din e-Factura: fisier XML -> analiza -> una.md.

RO: a treia cale de import, alaturi de pachetul 12103 (parserul vendorului
PKG_EDI_XML) si actiunea din back-office-ul nativ. Aici NU trecem prin pachetul
vendorului si prin validarile lui (data, subdiviziune, dubluri): se citeste
fisierul descarcat din cabinetul e-Factura (`<Documents>` cu N `<Document>`),
se ANALIZEAZA fiecare pozitie si se leaga de ce exista deja in baza:

- marfa/serviciul: potrivire pe denumirea INTREAGA in `TMS_UNIVERS`
  (TIP 'P'), intii exact, apoi fara diacritice (baza e CL8MSWIN1251, deci
  cardul vechi poate fi scris «Acuarela», iar factura vine cu «Acuarelă»);
  gasit -> se REFOLOSESTE cardul, nu se creeaza altul;
- contragentul: dupa IDNO in `TMS_UNIVERS.CODVECHI` si `TMS_ORG.CODFISCAL`
  (conventia una.md: GR1 'E' => CODVECHI = codul fiscal).

Cerinta proprietarului (14.09.2026): «простой импорт данных с анализом входящих
позиций, если встречаются уже в oracle tms_univers по полному совпадению — то
использовать повторно, то же самое и про idno поставщика в поле codvechi и
codfiscal».

EN: third import path — plain file import with analysis; existing nomenclature
and counterparties are reused, never duplicated.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from modules.efactura.inbox import EfaInbox, fold, parse_invoice, strip_signature

# RO: cite denumiri intr-o singura interogare (IN-lista) la analiza unui pachet mare
_CHUNK = 200


def split_documents(xml: str) -> List[str]:
    """RO: pachetul portalului (`<Documents>`) sau o singura factura -> lista de `<Document>`."""
    body = strip_signature(xml or "")
    docs = re.findall(r"<Document\b.*?</Document>", body, re.S)
    if docs:
        return docs
    body = body.strip()
    return [body] if "<SupplierInfo" in body else []


def parse_package(xml: str) -> List[Dict[str, Any]]:
    """RO: fiecare `<Document>` prin acelasi parser ca la facturile din SFS."""
    out: List[Dict[str, Any]] = []
    for i, doc in enumerate(split_documents(xml), 1):
        try:
            inv = parse_invoice(doc)
        except ValueError as e:
            out.append({"nr_in_file": i, "error": str(e), "rows": []})
            continue
        inv["nr_in_file"] = i
        inv["xml"] = doc
        out.append(inv)
    return out


class EfaSimple:
    """RO: analiza si importul unui fisier XML de facturi, cu refolosirea nomenclatorului."""

    # ── potrivirea marfii dupa denumirea intreaga ────────────────────────
    @staticmethod
    def goods_by_names(names: List[str]) -> Dict[str, Dict[str, Any]]:
        """RO: {denumirea din factura -> cardul din TMS_UNIVERS}. Intii potrivire
        exacta pe denumire, apoi potrivire fara diacritice (`fold`), pe grupuri
        de cite `_CHUNK` denumiri — un pachet are sute de pozitii."""
        db, rows = EfaInbox._db()
        want = [n for n in dict.fromkeys((x or "").strip() for x in names) if n]
        found: Dict[str, Dict[str, Any]] = {}
        by_fold = {fold(n): n for n in want}
        for step in ("exact", "fold"):
            left = [n for n in want if n not in found]
            if not left:
                break
            keys = [n.upper() for n in left] if step == "exact" else [fold(n) for n in left]
            keys = list(dict.fromkeys(keys))
            for i in range(0, len(keys), _CHUNK):
                part = keys[i:i + _CHUNK]
                binds = {"k%d" % j: v for j, v in enumerate(part)}
                inlist = ", ".join(":k%d" % j for j in range(len(part)))
                col = ("UPPER(TRIM(u.DENUMIREA))" if step == "exact" else
                       "UPPER(TRIM(TRANSLATE(u.DENUMIREA, 'ăâîșşțţĂÂÎȘŞȚŢ', 'aaisstt AAISSTT')))")
                for r in rows(db.execute_query(
                        "SELECT u.COD, u.DENUMIREA, u.UM, %s KEY_ FROM TMS_UNIVERS u "
                        "WHERE u.TIP='P' AND u.ISARHIV IS NULL AND %s IN (%s)" % (col, col, inlist), binds)):
                    key = str(r.get("key_") or "")
                    name = by_fold.get(key) if step == "fold" else None
                    if name is None:
                        name = next((n for n in left if n.upper() == key), None)
                    if name and name not in found:
                        found[name] = {"cod": int(r["cod"]), "denumirea": r.get("denumirea"),
                                       "um": r.get("um"), "how": "denumire" if step == "exact" else "denumire-translit"}
        return found

    @staticmethod
    def org_by_idno(idno: Optional[str]) -> Optional[Dict[str, Any]]:
        """RO: contragentul dupa IDNO — CODVECHI (conventia GR1 'E') sau TMS_ORG.CODFISCAL."""
        if not idno:
            return None
        db, rows = EfaInbox._db()
        r = rows(db.execute_query(
            "SELECT u.COD, u.DENUMIREA, u.CODVECHI, o.CODFISCAL FROM TMS_UNIVERS u LEFT JOIN TMS_ORG o ON o.COD=u.COD "
            "WHERE u.TIP='O' AND (TRIM(u.CODVECHI)=:i OR o.CODFISCAL=:i) AND ROWNUM<=1", {"i": str(idno).strip()}))
        if not r:
            return None
        return {"cod": int(r[0]["cod"]), "denumirea": r[0].get("denumirea"),
                "how": "codvechi" if (r[0].get("codvechi") or "").strip() == str(idno).strip() else "codfiscal"}

    # ── analiza (nu scrie nimic) ────────────────────────────────────────
    @staticmethod
    def analyze(xml: str, seller_idno: Optional[str] = None) -> Dict[str, Any]:
        """RO: ce ar intra in baza: per document — contragentii si pozitiile, cu
        marcajul «se refoloseste cardul X» sau «card nou»."""
        from modules.efactura.store import EfaStore
        mine = str(seller_idno or EfaStore.settings().get("seller_idno") or "").strip()
        docs = parse_package(xml)
        if not docs:
            return {"success": False, "error": "fisierul nu contine documente e-Factura (<Document>)"}
        names: List[str] = []
        for d in docs:
            names.extend((r.get("name") or "") for r in d.get("rows") or [])
        cards = EfaSimple.goods_by_names(names)
        orgs: Dict[str, Optional[Dict[str, Any]]] = {}
        out, seen = [], {}
        n_rows = n_reuse = n_new = 0
        for d in docs:
            sup, buy = d.get("supplier") or {}, d.get("buyer") or {}
            for idno in (sup.get("idno"), buy.get("idno")):
                if idno and idno not in orgs:
                    orgs[idno] = EfaSimple.org_by_idno(idno)
            direction = ("out" if mine and sup.get("idno") == mine else
                         "in" if mine and buy.get("idno") == mine else "?")
            rws = []
            for r in d.get("rows") or []:
                name = (r.get("name") or "").strip()
                card = cards.get(name)
                n_rows += 1
                if card:
                    n_reuse += 1
                else:
                    n_new += 1
                rws.append(dict(r, name=name, card_cod=(card or {}).get("cod"),
                                card_name=(card or {}).get("denumirea"), card_um=(card or {}).get("um"),
                                how=(card or {}).get("how", "nou")))
            key = (d.get("seria") or "", d.get("number") or "")
            out.append({"nr_in_file": d.get("nr_in_file"), "seria": key[0], "number": key[1],
                        "issued_date": d.get("issued_date"), "total": d.get("total"), "total_tva": d.get("total_tva"),
                        "direction": direction, "error": d.get("error"),
                        "supplier": dict(sup, **{"match": orgs.get(sup.get("idno"))}),
                        "buyer": dict(buy, **{"match": orgs.get(buy.get("idno"))}),
                        "rows": rws, "duplicate_in_file": key in seen})
            seen[key] = True
        return {"success": True, "seller_idno": mine, "docs": out, "summary": {
            "documents": len(out), "incoming": sum(1 for d in out if d["direction"] == "in"),
            "outgoing": sum(1 for d in out if d["direction"] == "out"),
            "rows": n_rows, "rows_reused": n_reuse, "rows_new": n_new,
            "orgs": len(orgs), "orgs_found": sum(1 for v in orgs.values() if v),
            "orgs_new": sum(1 for v in orgs.values() if not v)}}

    # ── scrierea in baza ────────────────────────────────────────────────
    @staticmethod
    def create_org(idno: str, name: str, address: str = "") -> Dict[str, Any]:
        """RO: contragent nou dupa conventia una.md: TMS_UNIVERS TIP 'O' GR1 'E',
        CODVECHI = IDNO, plus rindul TMS_ORG cu CODFISCAL (la fel ca puntea Contragenti)."""
        db, rows = EfaInbox._db()
        den = EfaInbox_db_text(name)
        if not den:
            return {"success": False, "error": "denumire goala"}
        nx = rows(db.execute_query("SELECT ID_TMS_UNIVERS.NEXTVAL N FROM dual"))
        cod = int(nx[0]["n"])
        r = db.execute_dml(
            "INSERT INTO TMS_UNIVERS (COD, DENUMIREA, NAMERUS, TIP, GR1, CODVECHI) "
            "VALUES (:c, :d, :d, 'O', 'E', :i)", {"c": cod, "d": den[:200], "i": str(idno).strip()})
        if not r.get("success"):
            return {"success": False, "error": str(r.get("message"))[:400]}
        db.execute_dml("INSERT INTO TMS_ORG (COD, CODFISCAL, ADRESS) VALUES (:c, :i, :a)",
                       {"c": cod, "i": str(idno).strip(), "a": EfaInbox_db_text(address)[:200] or None})
        return {"success": True, "cod": cod, "denumirea": den}

    @staticmethod
    def create_goods(name: str, um: str = "buc.") -> Dict[str, Any]:
        """RO: card nou de marfa/serviciu: TMS_UNIVERS TIP 'P' GR1 'TVR' + rindul TMS_MPT_TVR."""
        db, rows = EfaInbox._db()
        den = EfaInbox_db_text(name)
        if not den:
            return {"success": False, "error": "denumire goala"}
        nx = rows(db.execute_query("SELECT ID_TMS_UNIVERS.NEXTVAL N FROM dual"))
        cod = int(nx[0]["n"])
        r = db.execute_dml(
            "INSERT INTO TMS_UNIVERS (COD, DENUMIREA, NAMERUS, TIP, GR1, UM, CODTVA) "
            "VALUES (:c, :d, :d, 'P', 'TVR', :u, 'A')",
            {"c": cod, "d": den[:200], "u": (um or "buc.")[:10]})
        if not r.get("success"):
            return {"success": False, "error": str(r.get("message"))[:400]}
        db.execute_dml("INSERT INTO TMS_MPT_TVR (COD) VALUES (:c)", {"c": cod})
        return {"success": True, "cod": cod, "denumirea": den}

    @staticmethod
    def import_file(xml: str, *, only: Optional[List[str]] = None, create_goods: bool = False,
                    create_orgs: bool = False, create_docs: bool = False,
                    env: str = "file", seller_idno: Optional[str] = None) -> Dict[str, Any]:
        """RO: analiza + scriere. Implicit NU creeaza nimic: doar aduce facturile in
        EFA_IN/EFA_IN_ROW cu potrivirile gasite (analiza persistata). Cu
        `create_goods`/`create_orgs` completeaza nomenclatorul lipsa, cu
        `create_docs` face documentul 1209 pentru facturile in care sintem CUMPARATOR.

        `only` — lista «SERIA NUMAR» de procesat (implicit toate)."""
        an = EfaSimple.analyze(xml, seller_idno)
        if not an.get("success"):
            return an
        db, rows = EfaInbox._db()
        pick = set(only or [])
        made_goods, made_orgs, made_docs, errors = [], [], [], []
        for d in an["docs"]:
            key = ("%s %s" % (d["seria"], d["number"])).strip()
            if pick and key not in pick:
                continue
            if d.get("error"):
                errors.append("%s: %s" % (key, d["error"]))
                continue
            # 1) contragentii
            for side in ("supplier", "buyer"):
                p = d[side]
                if p.get("match") or not p.get("idno"):
                    continue
                if create_orgs:
                    r = EfaSimple.create_org(p["idno"], p.get("title") or "", p.get("address") or "")
                    if r.get("success"):
                        p["match"] = {"cod": r["cod"], "denumirea": r["denumirea"], "how": "creat"}
                        made_orgs.append({"idno": p["idno"], "cod": r["cod"], "denumirea": r["denumirea"]})
                    else:
                        errors.append("%s: contragent %s — %s" % (key, p["idno"], r.get("error")))
            # 2) marfa
            for r0 in d["rows"]:
                if r0.get("card_cod") or not create_goods:
                    continue
                g = EfaSimple.create_goods(r0["name"], r0.get("um") or "buc.")
                if g.get("success"):
                    r0["card_cod"], r0["card_name"], r0["how"] = g["cod"], g["denumirea"], "creat"
                    made_goods.append({"cod": g["cod"], "denumirea": g["denumirea"]})
                else:
                    errors.append("%s: marfa «%s» — %s" % (key, r0["name"][:40], g.get("error")))
            # 3) factura in EFA_IN + pozitiile cu potrivirile (analiza ramine in baza)
            up = EfaInbox.upsert(env, {"xml": d_xml(xml, d), "seria": d["seria"], "number": d["number"]}, "file")
            if not up.get("success"):
                errors.append("%s: %s" % (key, up.get("error")))
                continue
            iid = int(up["id"])
            for r0 in d["rows"]:
                if r0.get("card_cod"):
                    db.execute_dml(
                        "UPDATE EFA_IN_ROW SET MATCH_KIND=:k, MATCH_COD=:c, MATCH_NAME=:n WHERE IN_ID=:i AND ROWN=:r "
                        "AND (MATCH_COD IS NULL OR MATCH_KIND IN ('none','denumire','denumire-translit','creat'))",
                        {"k": r0["how"], "c": int(r0["card_cod"]), "n": (r0.get("card_name") or "")[:200] or None,
                         "i": iid, "r": r0["rown"]})
            sup_cod = (d["supplier"].get("match") or {}).get("cod")
            if sup_cod:
                db.execute_dml("UPDATE EFA_IN SET SUPPLIER_COD=:c WHERE ID=:i", {"c": int(sup_cod), "i": iid})
            d["in_id"] = iid
            # 4) documentul de intrare — doar cind sintem cumparator
            if create_docs and d["direction"] == "in":
                if not sup_cod:
                    errors.append("%s: furnizorul lipseste din nomenclator" % key)
                    continue
                r = db.call_proc("BEGIN EFA_INBOX.create_doc_from_in(:i); END;", {"i": iid})
                if r.get("success"):
                    got = rows(db.execute_query("SELECT DEST_NRDOC N FROM EFA_IN WHERE ID=:i", {"i": iid}))
                    nr = int(got[0]["n"]) if got and got[0]["n"] else None
                    d["dest_nrdoc"] = nr
                    made_docs.append({"key": key, "nrdoc": nr})
                else:
                    errors.append("%s: document — %s" % (key, str(r.get("message"))[:300]))
        an["created"] = {"goods": made_goods, "orgs": made_orgs, "docs": made_docs}
        an["errors"] = errors
        an["summary"]["goods_created"] = len(made_goods)
        an["summary"]["orgs_created"] = len(made_orgs)
        an["summary"]["docs_created"] = len(made_docs)
        return an


def d_xml(_pkg: str, d: Dict[str, Any]) -> str:
    """RO: XML-ul unui singur document din pachet (parse_package il pastreaza)."""
    return d.get("xml") or ""


def EfaInbox_db_text(s: Optional[str]) -> str:
    """RO: text pentru CL8MSWIN1251: fara diacritice romanesti, fara ghilimele
    (triggerele YBIRO_UNIVERS_CHK_DIACRITICE si TRIG_BFIU_TMS_UNIVERS_CK_BANK)."""
    out = []
    for ch in (s or "").translate(str.maketrans({
            "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s", "ț": "t", "ţ": "t",
            "Ă": "A", "Â": "A", "Î": "I", "Ș": "S", "Ş": "S", "Ț": "T", "Ţ": "T",
            "—": "-", "–": "-", "«": "", "»": "", "’": "", "“": "", "”": ""})):
        try:
            ch.encode("cp1251")
            out.append(ch)
        except UnicodeEncodeError:
            continue
    return re.sub(r"\s+", " ", "".join(out).replace('"', "").replace("'", "")).strip()

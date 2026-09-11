"""Sursa reala din ERP pentru CRM: marfa si contragentii OfficePlus.

RO: cerinta proprietarului (10.09.2026) — «в officeplus должно все работать
на оракл, соедини с реальными данными и товар тоже; демо режим остается
отдельно». Aici stau REGULILE si SQL-ul, fara executie (se testeaza fara
wallet); executia e in `store_erp.py` (regula nr. 2: cod separat in fisier
separat).

De ce nu se copiaza dictionarul intreg: TMS_UNIVERS are 232 mii de pozitii
(188 mii nearhivate). O copie in CRM_ITEM ar fi moarta a doua zi, iar
preturile stau oricum in alta parte (TPR1D_PERPRLIST, perioade). De aceea:

  * cautarea in nomenclator merge DIRECT in dictionarul ERP;
  * pozitia folosita intr-o comanda se aduce o singura data in CRM_ITEM
    (ERP_COD = TMS_UNIVERS.COD, SRC = 'erp') si se poate reimprospata;
  * pretul: lista de preturi in vigoare (CODPRICE=1, perioada care cuprinde
    ziua de azi), cu intoarcere pe pretul din fluxul BIRO26_GOODS — exact
    lantul folosit de magazin (`Biro26Store.shop_prices_for`), ca sa nu apara
    doua adevaruri despre acelasi pret;
  * stocul: BIRO26_GOODS.STOC (fluxul furnizorului), cimp text in flux.

Contragentii reali: TMS_ORG (registrul ERP, numele vine din TMS_UNIVERS
TIP='O', IDNO = CODFISCAL) plus conturile magazinului YBIRO_CLIENT.
EN: real ERP data source for the CRM (goods dictionary, prices, clients).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# RO: pretul cu amanuntul din flux este text ('123,45' sau gol) — se ia
#     numeric doar daca chiar e numar (aceeasi verificare ca in magazin).
_RETAIL_NUM = ("CASE WHEN REGEXP_LIKE(TRIM(g.RETAIL1), '^-?[0-9]+([.,][0-9]+)?$') "
               "THEN TO_NUMBER(REPLACE(TRIM(g.RETAIL1), ',', '.')) END")
_STOC_NUM = ("CASE WHEN REGEXP_LIKE(TRIM(g.STOC), '^-?[0-9]+([.,][0-9]+)?$') "
             "THEN TO_NUMBER(REPLACE(TRIM(g.STOC), ',', '.')) END")

# RO: pozitia dictionarului + pretul in vigoare + stocul din flux.
GOODS_SELECT = (
    "SELECT u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.GR1, u.UM, u.ISARHIV, "
    "       NVL(MAX(pl.PRETV), MAX(%s)) AS PRICE, "
    "       NVL(MAX(%s), 0) AS STOC, "
    "       MAX(g.FURNIZOR) AS FURNIZOR "
    "  FROM TMS_UNIVERS u "
    "  LEFT JOIN BIRO26_GOODS g ON g.COD_UNIVERS = u.COD "
    "  LEFT JOIN TPR1D_PERPRLIST pl ON pl.CODPRICE = 1 AND pl.SC = u.COD "
    "       AND TRUNC(SYSDATE) BETWEEN pl.DATASTART AND pl.DATAEND "
    " WHERE u.TIP = 'P'" % (_RETAIL_NUM, _STOC_NUM))
GOODS_GROUP = (" GROUP BY u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.GR1, u.UM, u.ISARHIV")

MAX_ROWS = 200


def goods_sql(q: str = "", only_active: bool = True, limit: int = 50,
              cod: int = 0) -> Tuple[str, Dict[str, Any]]:
    """RO: cautarea in dictionarul ERP. Cauta dupa denumire (RO si RU), cod
    vechi (articol) si cod barat, ca in bacul-office (`get_univers`)."""
    sql, p = GOODS_SELECT, {}                      # type: str, Dict[str, Any]
    if cod:
        sql += " AND u.COD = :cod"
        p["cod"] = int(cod)
    else:
        text = (q or "").strip()
        if text:
            sql += (" AND (UPPER(u.DENUMIREA) LIKE UPPER(:s) OR UPPER(u.NAMERUS) LIKE UPPER(:s) "
                    "OR u.CODVECHI LIKE :s OR EXISTS (SELECT 1 FROM TMS_MPT_BARCODE b "
                    "WHERE b.COD = u.COD AND b.BARCODE LIKE :s))")
            p["s"] = "%" + text + "%"
        if only_active:
            sql += " AND (u.ISARHIV IS NULL OR u.ISARHIV = '0')"
    sql += GOODS_GROUP + " ORDER BY u.DENUMIREA"
    n = max(1, min(int(limit or 50), MAX_ROWS))
    return "SELECT * FROM (%s) WHERE ROWNUM <= %d" % (sql, n), p


# RO: contragentii reali. TMS_ORG e registrul ERP (numele in TMS_UNIVERS
#     TIP='O'), YBIRO_CLIENT sint conturile magazinului. Aceeasi persoana
#     poate fi in ambele — se uneste dupa IDNO la scriere (vezi store_erp).
ORG_SQL = (
    "SELECT o.COD, u.DENUMIREA AS NAME, o.CODFISCAL AS IDNO, o.ADRESS, "
    "       o.TELEFON, o.TELPRIM, o.DIRECTOR, o.CONTACT "
    "  FROM TMS_ORG o LEFT JOIN TMS_UNIVERS u ON u.COD = o.COD AND u.TIP = 'O' "
    " ORDER BY u.DENUMIREA")

SHOP_SQL = (
    "SELECT c.ID, c.FULL_NAME AS NAME, c.IDNO, c.ADDRESS, c.PHONE, c.EMAIL, "
    "       c.IS_COMPANY, c.UNIVERS_COD "
    "  FROM YBIRO_CLIENT c ORDER BY c.FULL_NAME")


def item_from_good(row: Dict[str, Any]) -> Dict[str, Any]:
    """RO: pozitia dictionarului ERP -> cimpurile lui CRM_ITEM. Numele se ia
    in romana (DENUMIREA); daca lipseste, cel rus. `kind`/`unit_` raman
    valorile canonice ale prototipului."""
    name = (row.get("denumirea") or row.get("namerus") or "").strip()
    unit = (row.get("um") or "").strip().lower()
    return {
        "code": (row.get("codvechi") or "").strip() or str(row.get("cod") or ""),
        "name": name[:300] or "pozitia %s" % row.get("cod"),
        "kind": "Товар",
        "unit_": unit_of(unit),
        "price": float(row.get("price") or 0),
        "vat": 20,
        "stock": float(row.get("stoc") or 0),
        "erp_cod": int(row.get("cod") or 0),
    }


# RO: unitatile ERP -> lista canonica a prototipului (ENUMS['unit']).
_UNITS = {"buc": "шт", "bucata": "шт", "шт": "шт", "kg": "кг", "кг": "кг",
          "m": "м", "м": "м", "m2": "м2", "м2": "м2", "l": "л", "л": "л",
          "ora": "час", "час": "час", "set": "компл", "компл": "компл",
          "serv": "услуга", "услуга": "услуга"}


def unit_of(um: str) -> str:
    return _UNITS.get((um or "").strip().lower(), "шт")


def client_from_org(row: Dict[str, Any]) -> Dict[str, Any]:
    """RO: contragentul ERP -> CRM_CLIENT. Fara IDNO nu se scrie nimic:
    IDNO e cheia de unire cu registrul de stat (regula puntii Contragenti)."""
    phone = (row.get("telefon") or row.get("telprim") or "").strip()
    return {
        "idno": (row.get("idno") or "").strip(),
        "name": (row.get("name") or "").strip()[:400],
        "address": (row.get("adress") or "").strip()[:1000],
        "phone": phone[:120],
        "contact_person": (row.get("contact") or row.get("director") or "").strip()[:200],
        "managers": (row.get("director") or "").strip()[:1000],
        "client_type": "Клиент",
        "source": "erp:TMS_ORG",
        "erp_cod": int(row.get("cod") or 0),
    }


def client_from_shop(row: Dict[str, Any]) -> Dict[str, Any]:
    """RO: contul magazinului -> CRM_CLIENT (persoanele fizice au IDNP gol,
    atunci cheia devine 'shop:<id>' ca sa nu se piarda contul)."""
    idno = (row.get("idno") or "").strip()
    return {
        "idno": idno or ("shop:%s" % row.get("id")),
        "name": (row.get("name") or "").strip()[:400] or "client %s" % row.get("id"),
        "address": (row.get("address") or "").strip()[:1000],
        "phone": (row.get("phone") or "").strip()[:120],
        "email": (row.get("email") or "").strip()[:200],
        "client_type": "Клиент",
        "source": "shop:YBIRO_CLIENT",
        "erp_cod": int(row.get("univers_cod") or 0) or None,
    }


def summary(goods: int, clients: int) -> str:
    return "marfa: %d, clienti: %d" % (int(goods), int(clients))


def rows_to_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item_from_good(r) for r in rows]


# ── vederile ERP pentru nomenclator si comenzi (12.09.2026) ──────────────
# RO: cerinta proprietarului: «особенно обрати внимание на marfa и на comenzi,
#     тут полно в оракл реальных данных». Deci cele doua sectiuni nu mai arata
#     doar ce a intrat in CRM: ele arata MARFA reala din dictionar si COMENZILE
#     reale (conturile de plata web, SYSFID=12280) — in citire, cu acelasi
#     lant de preturi ca magazinul. Randurile ERP au id NEGATIV (-COD), ca sa
#     nu se incurce niciodata cu randurile proprii (CRM_ITEM/CRM_ORDER.ID > 0).
WEB_INVOICE_SYSFID = 12280


def erp_id(cod) -> int:
    """RO: id-ul de afisare al unui rind ERP: -COD (randurile CRM au id > 0)."""
    return -abs(int(cod or 0))


def is_erp_id(rid) -> bool:
    return int(rid or 0) < 0


def cod_of(rid) -> int:
    return abs(int(rid or 0))


# RO: comenzile reale = conturile de plata emise de magazin. Antetul in
#     TMDB_DOCS + VMDB_ST201M (m.DTDEP = contragentul), totalul din liniile
#     VMDB_ST201D, denumirea clientului din TMS_UNIVERS.
ORDERS_SELECT = (
    "SELECT d.COD, TRIM(d.NRMANUAL) AS NRMANUAL, d.NRSET, "
    "       TO_CHAR(d.DATAMANUAL,'YYYY-MM-DD') AS DDATE, "
    "       m.DTDEP AS CLIENT_COD, u.DENUMIREA AS CLIENT_NAME, "
    "       (SELECT ROUND(SUM(l.SUMA),2) FROM VMDB_ST201D l WHERE l.NRDOC = d.COD) AS TOTAL, "
    "       m.CTNRDOC AS LIVR_COD "
    "  FROM TMDB_DOCS d "
    "  JOIN VMDB_ST201M m ON m.NRDOC = d.COD "
    "  LEFT JOIN TMS_UNIVERS u ON u.COD = m.DTDEP "
    " WHERE d.SYSFID = %d" % WEB_INVOICE_SYSFID)

ORDER_LINES_SQL = (
    "SELECT l.CTSC, l.CANT, l.PRET, l.SUMA, u.DENUMIREA, u.UM, u.CODVECHI "
    "  FROM VMDB_ST201D l LEFT JOIN TMS_UNIVERS u ON u.COD = l.CTSC "
    " WHERE l.NRDOC = :cod ORDER BY l.RROWID")


def orders_sql(q: str = "", limit: int = 200, cod: int = 0):
    """RO: comenzile reale, cele mai noi primele."""
    sql, p = ORDERS_SELECT, {}
    if cod:
        sql += " AND d.COD = :cod"
        p["cod"] = int(cod)
    else:
        text = (q or "").strip()
        if text:
            sql += (" AND (UPPER(u.DENUMIREA) LIKE UPPER(:s) OR TRIM(d.NRMANUAL) LIKE :s2 "
                    "OR TO_CHAR(d.NRSET) = :s3 OR TO_CHAR(d.COD) = :s3)")
            p.update({"s": "%" + text + "%", "s2": "%" + text + "%",
                      "s3": text.lstrip("#")})
    n = max(1, min(int(limit or 200), 500))
    return "SELECT * FROM (%s ORDER BY d.COD DESC) WHERE ROWNUM <= %d" % (sql, n), p


def order_from_doc(row) -> dict:
    """RO: contul de plata -> cimpurile entitatii «comenzi». Documentul are
    deja o nota de livrare (CTNRDOC) => comanda e livrata."""
    livrat = bool(row.get("livr_cod"))
    return {
        "id": erp_id(row.get("cod")),
        "number": (row.get("nrmanual") or "").strip() or str(row.get("nrset") or row.get("cod")),
        "order_date": row.get("ddate") or "",
        "client_id": None,
        "client_id__disp": (row.get("client_name") or "").strip(),
        "project_id": None, "project_id__disp": "",
        "kind": "Продажа",
        "status": "Выполнен" if livrat else "Подтверждён",
        "total": float(row.get("total") or 0),
        "advance": None, "paid": None,
        "due_date": row.get("ddate") or "", "ship_date": None,
        "notes": "",
        "src": "erp", "erp_cod": int(row.get("cod") or 0),
        "erp_client_cod": int(row.get("client_cod") or 0) or None,
    }


def line_from_doc(row) -> dict:
    qty = float(row.get("cant") or 0)
    total = float(row.get("suma") or 0)
    price = float(row.get("pret") or 0) or (round(total / qty, 2) if qty else 0.0)
    # RO: numele cimpurilor sint cele pe care le asteapta pagina (item_name, sum)
    return {
        "id": erp_id(row.get("ctsc")),
        "item_id": erp_id(row.get("ctsc")),
        "item_name": (row.get("denumirea") or "").strip(),
        "item_id__disp": (row.get("denumirea") or "").strip(),
        "code": (row.get("codvechi") or "").strip(),
        "unit_": row.get("um") or "",
        "qty": qty, "price": price, "sum": total, "line_sum": total,
    }


def item_row(row) -> dict:
    """RO: pozitia dictionarului ERP in forma entitatii «nomenclator»."""
    it = item_from_good(row)
    it.update({"id": erp_id(row.get("cod")), "src": "erp", "notes": ""})
    return it

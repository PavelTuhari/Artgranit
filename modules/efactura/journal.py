"""Jurnalul apelurilor catre SIA e-Factura — ce am trimis si ce a raspuns.

RO: dupa prima proba reala (02.09.2026) operatorul a vazut doar «ceva a
picat»: raspunsul SFS — «Validation failed: The 'Invoices' element is not
declared…» — se taia la 2000 de caractere in EFA_LOG si nu se vedea pe pagina.
De aici, fiecare apel SOAP se scrie INTREG in EFA_CALL: plicul trimis (cu
parola inlocuita de ******), raspunsul brut, statutul HTTP, durata si un
verdict scurt, iar pagina probei le arata jos, ca un jurnal.

Fisier separat (regula nr. 2): in `sfs.py` ramine un singur apel,
`journal.record(...)`, iar o eroare de jurnal nu opreste niciodata apelul.
EN: full SOAP request/response journal (password masked), shown on the test page.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_PASS = re.compile(r"(<wsse:Password[^>]*>)(.*?)(</wsse:Password>)", re.S)
_TAB = re.compile(r"[\t\r\n]+")


def mask(envelope: str) -> str:
    """RO: parola nu ajunge NICIODATA in jurnal."""
    return _PASS.sub(r"\1******\3", envelope or "")


def verdict(status: Optional[int], raw: str,
            parsed: Optional[Dict[str, Any]], error: Optional[str]) -> tuple:
    """RO: (rezultat, rezumat) intr-o fraza pe care o intelege un director."""
    body = (raw or "").lstrip()
    if status is None:
        return "network", (error or "fara raspuns")[:4000]
    if body[:9].lower().startswith(("<!doctype", "<html")):
        return "html", ("SFS a raspuns cu o pagina HTML (status %s) — eroare "
                        "SOAP mascata de portal" % status)
    if "<Fault" in body or ":Fault" in body:
        return "fault", (error or body)[:4000]
    p = parsed or {}
    err = p.get("ErrorMessage")
    if err:
        # RO: SFS pune fiecare eroare de validare dupa un TAB — le facem lista
        parts = [x.strip() for x in _TAB.split(err) if x.strip()]
        return "rejected", " • ".join(parts)[:4000]
    bits = []
    for k in ("Status", "TotalInvoices", "TotalInvoicesPosted", "RequestId"):
        if p.get(k) is not None:
            bits.append("%s=%s" % (k, p[k]))
    return "ok", (", ".join(bits) or "raspuns SOAP fara erori")[:4000]


def record(*, src: str, username: str, endpoint: str, method: str,
           request_xml: str, response_raw: str, status: Optional[int],
           duration_ms: int, result: str, summary: str) -> None:
    try:
        from models.biro26_db import Biro26DB
        Biro26DB().execute_dml(
            "INSERT INTO EFA_CALL (SRC, USERNAME, ENDPOINT, METHOD, HTTP_STATUS, "
            " DURATION_MS, RESULT, SUMMARY, REQUEST_XML, RESPONSE_XML) "
            "VALUES (:src, :usr, :ep, :m, :st, :ms, :res, :sm, :rq, :rs)",
            {"src": (src or "")[:20], "usr": (username or "")[:120],
             "ep": (endpoint or "")[:400], "m": (method or "")[:60],
             "st": status, "ms": int(duration_ms or 0),
             "res": (result or "")[:20], "sm": (summary or "")[:4000],
             "rq": mask(request_xml)[:200000],
             "rs": (response_raw or "")[:200000]})
    except Exception:                                        # noqa: BLE001
        pass                      # RO: jurnalul nu are voie sa strice apelul


CHUNK = 4000        # RO: DBMS_LOB.SUBSTR in SQL pe 11g da cel mult 4000 de octeti


def _lob_cols(col: str, alias: str, chunks: int) -> str:
    """RO: CLOB-ul citit pe bucati de 4000 — un SUBSTR de 32000 in SQL cade
    cu ORA-06502 pe 11g, iar `execute_query` inghite eroarea: pe 03.09.2026
    jurnalul din pagina era GOL desi tabelul avea 77 de rinduri."""
    return ", ".join(
        "DBMS_LOB.SUBSTR(%s, %d, %d) %s_%d" % (col, CHUNK, i * CHUNK + 1, alias, i)
        for i in range(chunks))


def _join(row: Dict[str, Any], alias: str, chunks: int) -> str:
    return "".join(row.get("%s_%d" % (alias, i)) or "" for i in range(chunks))


def _select(where: str, params: Dict[str, Any], limit: int,
            chunks: int) -> List[Dict[str, Any]]:
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    sql = ("SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI:SS') TS, SRC, "
           " USERNAME, ENDPOINT, METHOD, HTTP_STATUS, DURATION_MS, RESULT, SUMMARY, "
           " DBMS_LOB.GETLENGTH(REQUEST_XML) REQ_LEN, "
           " DBMS_LOB.GETLENGTH(RESPONSE_XML) RESP_LEN, "
           + _lob_cols("REQUEST_XML", "RQ", chunks) + ", "
           + _lob_cols("RESPONSE_XML", "RS", chunks)
           + f" FROM EFA_CALL{where} ORDER BY ID DESC) WHERE ROWNUM <= :l")
    params = dict(params, l=max(1, min(int(limit), 200)))
    out = []
    for r in _rows(Biro26DB().execute_query(sql, params)):
        row = {k: v for k, v in r.items()
               if not (k.startswith("rq_") or k.startswith("rs_"))}
        row["request_xml"] = _join(r, "rq", chunks)
        row["response_xml"] = _join(r, "rs", chunks)
        row["request_truncated"] = (r.get("req_len") or 0) > chunks * CHUNK
        row["response_truncated"] = (r.get("resp_len") or 0) > chunks * CHUNK
        out.append(row)
    return out


def recent(limit: int = 40, src: Optional[str] = None,
           chunks: int = 8) -> List[Dict[str, Any]]:
    """RO: ultimele apeluri, cele mai noi primele — TOATE (reusite si nu),
    cu plicul trimis (parola mascata) si raspunsul, pina la `chunks`*4000
    de caractere fiecare; restul se ia cu `get(id)`."""
    where = " WHERE SRC = :src" if src else ""
    params: Dict[str, Any] = {"src": src} if src else {}
    return _select(where, params, limit, chunks)


def get(call_id: int, chunks: int = 50) -> Optional[Dict[str, Any]]:
    """RO: un apel cu textul COMPLET (pina la 200000 de caractere)."""
    rows = _select(" WHERE ID = :id", {"id": int(call_id)}, 1, chunks)
    return rows[0] if rows else None

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


def recent(limit: int = 40, src: Optional[str] = None) -> List[Dict[str, Any]]:
    """RO: ultimele apeluri, cele mai noi primele — pentru panoul din pagina."""
    from models.biro26_db import Biro26DB
    from models.biro26_oracle_store import _rows
    where = " WHERE SRC = :src" if src else ""
    params: Dict[str, Any] = {"l": max(1, min(int(limit), 200))}
    if src:
        params["src"] = src
    rows = _rows(Biro26DB().execute_query(
        "SELECT * FROM (SELECT ID, TO_CHAR(TS,'DD.MM.YYYY HH24:MI:SS') TS, SRC, "
        " USERNAME, ENDPOINT, METHOD, HTTP_STATUS, DURATION_MS, RESULT, SUMMARY, "
        " DBMS_LOB.SUBSTR(REQUEST_XML, 32000, 1) REQUEST_XML, "
        " DBMS_LOB.SUBSTR(RESPONSE_XML, 32000, 1) RESPONSE_XML "
        f" FROM EFA_CALL{where} ORDER BY ID DESC) WHERE ROWNUM <= :l", params))
    return rows

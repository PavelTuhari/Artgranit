"""RO: Proxy de imagini pentru sursele fara HTTPS.
    EN: Image proxy for sources that have no HTTPS.

RO: De ce exista. impreso.md serveste imaginile DOAR prin http (https esueaza
    complet, nu e o eroare de certificat — nu exista serviciu pe 443). Magazinul
    ruleaza pe https, iar browserul blocheaza continutul mixt, deci imaginile nu
    se afiseaza desi URL-urile din baza sint corecte. Proxy-ul aduce imaginea pe
    server prin http si o serveste mai departe pe https.
EN: Why this exists. impreso.md serves images over http only (https fails outright
    — nothing listens on 443). The shop runs on https and browsers block mixed
    content, so the images never render even though the stored URLs are valid.
    The proxy fetches over http server-side and re-serves over https.

RO: SECURITATE — un proxy care descarca orice URL primit e o gaura SSRF: cineva
    l-ar putea folosi ca sa ceara adrese interne prin serverul nostru. De aceea:
      * doar gazdele din ALLOWED_HOSTS;
      * fara urmarirea redirectarilor (o redirectare ar putea duce in afara listei);
      * doar raspunsuri image/*;
      * limita de marime.
EN: SECURITY — a proxy that fetches arbitrary URLs is an SSRF hole, so: allowlisted
    hosts only, no redirect following, image/* responses only, size cap.
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from typing import Optional

# RO: gazdele pentru care avem voie sa aducem imagini / EN: hosts we may fetch from
ALLOWED_HOSTS = frozenset({
    "impreso.md", "www.impreso.md",
})

PROXY_PATH = "/api/biro26/img"
MAX_BYTES = 8 * 1024 * 1024          # RO: 8 MB — o poza de produs e sub 1 MB
TIMEOUT_S = 15


def _host_of(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def needs_proxy(url: Optional[str]) -> bool:
    """RO: doar URL-urile http:// de pe gazdele permise trec prin proxy.
    EN: only http:// URLs on allowlisted hosts go through the proxy."""
    if not url or not isinstance(url, str):
        return False
    return url.startswith("http://") and _host_of(url) in ALLOWED_HOSTS


def proxy_url(url: Optional[str]) -> Optional[str]:
    """RO: intoarce URL-ul de afisat: prin proxy daca e nevoie, altfel neschimbat.
    EN: the URL to render: proxied when needed, unchanged otherwise."""
    if not needs_proxy(url):
        return url
    return PROXY_PATH + "?u=" + urllib.parse.quote(url, safe="")


def rewrite_rows(rows, *fields):
    """RO: aplica proxy_url peste cimpurile date, in lista de dictionare a unui
    rezultat SQL. Numele coloanelor pot veni cu litera mica sau mare.
    EN: apply proxy_url over the given fields of a list of result dicts."""
    if not rows:
        return rows
    for row in rows:
        if not isinstance(row, dict):
            continue
        for f in fields:
            for key in (f, f.lower(), f.upper()):
                if key in row:
                    row[key] = proxy_url(row[key])
                    break
    return rows


def fetch(url: str):
    """RO: aduce imaginea. Intoarce (octeti, content_type) sau ridica ValueError
    cu un motiv lizibil. NU urmareste redirectari — o redirectare ar putea scoate
    cererea din lista alba.
    EN: fetch the image; returns (bytes, content_type) or raises ValueError.
    Redirects are NOT followed — one could lead outside the allowlist."""
    if not needs_proxy(url):
        raise ValueError("RO: adresa nu e permisa / EN: url not allowed")

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):     # noqa: D401
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "BIRO26-img/1.0"})
    with opener.open(req, timeout=TIMEOUT_S) as resp:
        ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not ctype.startswith("image/"):
            raise ValueError("RO: raspunsul nu e imagine / EN: not an image: " + ctype)
        data = resp.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("RO: imagine prea mare / EN: image too large")
    return data, ctype

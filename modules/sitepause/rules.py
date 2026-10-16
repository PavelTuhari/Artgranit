"""RO: reguli pure ale pauzei (fara baza de date) — testate fara wallet."""
from typing import Iterable

# RO: ce ramine deschis pe pauza. Tot restul pe domeniul magazinului = pagina 503.
OPEN_PREFIXES = (
    "/login", "/logout", "/static/", "/favicon", "/robots.txt", "/health",
    "/UNA.md/orasldev/",          # backoffice
    "/api/v1/", "/api-documentation",   # API-ul partenerilor (integrarile lor nu se rup)
)
# RO: ...dar vitrina insasi sta tot sub /UNA.md/orasldev/ (nginx: / -> biro26-site)
SHOP_PREFIXES = (
    "/UNA.md/orasldev/biro26-site", "/UNA.md/orasldev/biro26-1shop",
    "/UNA.md/orasldev/biro26-shop",
)


def flag_on(value) -> bool:
    return str(value or "").strip().lower() in ("1", "on", "da", "yes", "true")


def is_shop_host(host: str, shop_hosts: Iterable[str]) -> bool:
    h = (host or "").lower().split(":")[0]
    if h.startswith("www."):
        h = h[4:]
    return h in {x.strip().lower() for x in shop_hosts if x and x.strip()}


def path_is_paused(path: str) -> bool:
    p = path or "/"
    if any(p == s or p.startswith(s + "/") or p.startswith(s + "?") for s in SHOP_PREFIXES):
        return True
    if p.startswith("/UNA.md/orasldev/sitepause"):
        return False
    return not any(p == o.rstrip("/") or p.startswith(o) for o in OPEN_PREFIXES)


def wants_json(path: str) -> bool:
    return (path or "").startswith("/api/")

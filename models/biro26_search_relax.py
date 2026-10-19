"""Cautare relaxata in catalog cind fraza intreaga nu gaseste nimic.

RO: cautarea magazinului e un LIKE pe FRAZA intreaga ('%Smartphone Samsung
Galaxy A27 Negru%'), deci orice cuvint in plus (culoarea in romana, «Smartphone»
in fata, alta ordine) da 0 produse — «SOS! nu gaseste produse in catalog»
(proprietar, 08.09.2026). Aici, DOAR cind rezultatul e gol si fraza are cel
putin doua cuvinte, se incearca variante tot mai scurte, in ordine:
  1. sinonimele culorilor RO -> EN (negru -> black…), fara «smartphone/telefon»;
  2. fara ultimul cuvint, apoi fara ultimele doua… (culoarea, memoria);
  3. cel mai «tehnic» cuvint singur (are cifre: A27, A2768, 256GB…).
Raspunsul primeste `relaxed_query` / `original_query`, ca pagina sa poata
spune «nimic pentru «…», se arata rezultatele pentru «…»». Fisier propriu
(regula nr. 2); in controler ramine un apel de o linie.
EN: progressive query relaxation when the whole-phrase LIKE finds nothing.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

COLORS = {"negru": "black", "neagra": "black", "alb": "white", "alba": "white",
          "albastru": "blue", "albastra": "blue", "rosu": "red", "rosie": "red",
          "verde": "green", "gri": "gray", "argintiu": "silver", "argintie": "silver",
          "auriu": "gold", "aurie": "gold", "roz": "pink", "violet": "purple", "mov": "purple",
          "galben": "yellow", "maro": "brown", "portocaliu": "orange", "bej": "beige",
          "чёрный": "black", "черный": "black", "белый": "white", "синий": "blue",
          "красный": "red", "зелёный": "green", "зеленый": "green", "серый": "gray",
          "золотой": "gold", "серебристый": "silver", "розовый": "pink"}
GENERIC = {"smartphone", "smartphones", "telefon", "telefoane", "mobil", "mobile",
           "produs", "produse", "смартфон", "телефон"}


def _fold(w: str) -> str:
    return (w.lower().replace("ă", "a").replace("â", "a").replace("î", "i")
            .replace("ș", "s").replace("ş", "s").replace("ț", "t").replace("ţ", "t"))


def attempts(search: str) -> List[str]:
    """RO: variantele de incercat, in ordine, fara duplicate si fara fraza initiala."""
    words = [w for w in re.split(r"\s+", (search or "").strip()) if w]
    if len(words) < 2:
        return []
    seen, out = {" ".join(words).lower()}, []

    def add(ws: List[str]) -> None:
        s = " ".join(ws).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)

    syn = [COLORS.get(_fold(w), w) for w in words]
    add(syn)
    core = [w for w in syn if _fold(w) not in GENERIC]
    add(core)
    for k in range(1, len(core) - 1):
        add(core[:-k])                      # fara ultimul, ultimele doua… (min. 2 cuvinte)
    for k in range(1, len(core) - 1):
        add(core[k:])                       # fara primul, primele doua… (min. 2 cuvinte)
    # RO: codul de model singur (litere + cifre: A27, A2768) inaintea unui cuvint generic
    tech = sorted((w for w in core if re.search(r"\d", w)),
                  key=lambda w: (bool(re.search(r"[A-Za-z]", w)), len(w)), reverse=True)
    for w in tech[:2]:
        add([w])
    if core:
        add(core[:1])                       # abia la urma: primul cuvint singur (marca)
    return out[:8]


def _has_rows(r: Any) -> bool:
    return bool(isinstance(r, dict) and r.get("success", True) and r.get("data"))


def with_fallback(fn: Callable[..., Dict[str, Any]], kw: Dict[str, Any]) -> Dict[str, Any]:
    r = fn(**kw)
    search = kw.get("search") or ""
    if _has_rows(r) or not search.strip():
        return r
    for alt in attempts(search):
        r2 = fn(**dict(kw, search=alt))
        if _has_rows(r2):
            r2["relaxed_query"] = alt
            r2["original_query"] = search
            return r2
    return r

"""«Testează conexiunea» din Setari e-Factura — verdict clar, pe fiecare cont.

RO: pe 03.09.2026 contabilul a completat conturile API create in cabinetul
REAL de pe sfs.md, dar a lasat adresa mediului de PROBA. Butonul a aratat
«403» o secunda si mesajul a disparut — omul nu a inteles nimic. De aici:

1. se verifica AMBII semnatari (metoda `Test`, nu atinge nicio factura);
2. daca pe adresa aleasa contul pica, se incearca aceeasi verificare pe
   CELALALT mediu (proba <-> real): daca acolo merge, verdictul spune exact
   asta — «conturile sint create pe mediul X, schimbati adresa»;
3. rezultatul e un dict stabil pe care pagina il afiseaza intr-un bloc
   propriu, care nu se sterge la reincarcarea setarilor.
EN: connection check per signer with cross-environment hint.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from modules.efactura import sfs

LABELS = {sfs.ENDPOINT_TEST: "de PROBA (apiefactura-pre.sfs.md)",
          sfs.ENDPOINT_PROD: "REAL (efactura-api.sfs.md)"}


def other_endpoint(endpoint: str) -> Optional[str]:
    e = (endpoint or "").strip().rstrip("/")
    if e == sfs.ENDPOINT_TEST.rstrip("/"):
        return sfs.ENDPOINT_PROD
    if e == sfs.ENDPOINT_PROD.rstrip("/"):
        return sfs.ENDPOINT_TEST
    return None


def env_label(endpoint: str) -> str:
    return LABELS.get((endpoint or "").strip(), endpoint or "?")


def _one(signer: int, endpoint: Optional[str], src: str) -> Dict[str, Any]:
    api = {"endpoint": endpoint} if endpoint else None
    c = sfs.SfsClient.from_settings(signer, api=api, src=src)
    if not c.username:
        return {"skipped": True, "success": True,
                "message": "fara cont (se foloseste primul semnatar)"}
    if not c.configured():
        return {"success": False, "status": None,
                "error": "lipseste parola sau adresa serviciului"}
    r = c.test()
    return {"success": bool(r.get("success")), "status": r.get("status"),
            "user": c.username,
            "error": None if r.get("success") else (r.get("error") or "esuat"),
            "message": r.get("message") if r.get("success") else None}


def check(src: str = "backoffice") -> Dict[str, Any]:
    from modules.efactura.store import EfaStore
    s = EfaStore.settings()
    endpoint = (s.get("endpoint") or "").strip()
    signers = {}
    for label, n in (("prima_semnatura", 1), ("a_doua_semnatura", 2)):
        signers[label] = _one(n, None, src)
        if n == 2 and not s.get("username2"):
            signers[label]["skipped"] = True
    ok = all(v.get("success") for v in signers.values())
    out: Dict[str, Any] = {"success": ok, "endpoint": endpoint,
                           "env": env_label(endpoint), "signers": signers}
    if ok:
        out["message"] = "conectat la SIA e-Factura, mediul %s" % env_label(endpoint)
        return out
    # RO: verificare incrucisata — contul e bun, dar pe celalalt mediu?
    other = other_endpoint(endpoint)
    if other:
        cross = {}
        for label, n in (("prima_semnatura", 1), ("a_doua_semnatura", 2)):
            if signers[label].get("skipped"):
                continue
            cross[label] = _one(n, other, src + "-cross")
        if cross and all(v.get("success") for v in cross.values()):
            out["cross_endpoint"] = other
            out["hint"] = ("Conturile API merg pe mediul %s, dar adresa aleasa e "
                           "mediul %s: conturile au fost create pe celalalt "
                           "portal. Schimbati «Adresa serviciului» in %s si "
                           "salvati." % (env_label(other), env_label(endpoint),
                                          other))
    failed = [v for v in signers.values() if not v.get("success")]
    out["error"] = "; ".join(
        "%s: %s" % (v.get("user") or "?", v.get("error")) for v in failed)
    return out

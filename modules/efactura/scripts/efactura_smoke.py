#!/usr/bin/env python3
"""Proba completa e-Factura de pe calculatorul proprietarului: 1 leu, cap-coada.

RO: ruleaza pe Mac (iesirea prin VPN93 = 93.115.136.18, adresa deschisa de
SFS), cu parolele din macOS Keychain — nu din fisiere, nu din chat.

Proprietarul pune parolele O SINGURA DATA (comanda cere parola interactiv,
nu ramine in istoric):
    security add-generic-password -s efactura-api-pre -a ptuhari -w
    security add-generic-password -s efactura-api-pre -a otuhari -w

Apoi proba (parolele merg din Keychain direct in variabile de mediu; nu se
afiseaza si nu se scriu nicaieri):
    EFA_USER_1=ptuhari EFA_PASS_1="$(security find-generic-password -s efactura-api-pre -a ptuhari -w)" \\
    EFA_USER_2=otuhari EFA_PASS_2="$(security find-generic-password -s efactura-api-pre -a otuhari -w)" \\
    venv/bin/python modules/efactura/scripts/efactura_smoke.py [--send] [--real]

Fara --send doar verifica conturile si arata XML-ul. --real = mediul real
(document fiscal adevarat!) — implicit e mediul de proba.
Pasii: 1) Test pe ambele conturi; 2) factura de 1 leu (validata, plafonata
la 10 lei de testff); 3) PostInvoices; 4) cozile de semnare Order 1 si 2;
5) ce a ramas in jurnalul EFA_CALL.
EN: end-to-end smoke test with passwords from the macOS Keychain.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)


def _load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    _load_env()
    os.chdir(ROOT)
    from modules.efactura import sfs, testff
    u1, p1 = os.environ.get("EFA_USER_1", ""), os.environ.get("EFA_PASS_1", "")
    u2, p2 = os.environ.get("EFA_USER_2", ""), os.environ.get("EFA_PASS_2", "")
    if not (u1 and p1):
        print("EFA_USER_1 / EFA_PASS_1 lipsesc (vezi docstring: Keychain)")
        return 2
    endpoint = sfs.ENDPOINT_PROD if "--real" in sys.argv else sfs.ENDPOINT_TEST
    api = {"username": u1, "password": p1, "username2": u2, "password2": p2,
           "endpoint": endpoint}
    print("== e-Factura proba cap-coada ==")
    print("   mediu:", "REAL (document fiscal adevarat!)" if "--real" in sys.argv
          else "de proba", "|", endpoint)

    # 1) conturile
    r = testff.ping(api, src="smoke")
    for k, v in r["data"].items():
        print("   %-18s %s" % (k, ("✅ " if v.get("ok") else "❌ ") + str(v.get("reply", ""))[:140]
                                if v.get("configured") else "— neconfigurat"))
    if not all(v.get("ok") for k, v in r["data"].items() if v.get("configured") and k != "ip_server"):
        print("   STOP: un cont nu raspunde — nu trimit nimic.")
        return 3

    # 2) factura de 1 leu
    payload = {
        "api": api,
        "seller": {"idno": "1003600116460",
                   "name": "Centrul de Elaborare si Implementare a Sistemelor "
                           "Informationale de Management \"UNISIM-SOFT\" S.R.L.",
                   "address": "or. Chisinau, str. Alba Iulia, 75/b",
                   "iban": "MD22ML000000222442000432", "bank_code": "MOLDMD2X303",
                   "bank_name": "BC Moldindconbank S.A., filiala Alba-Iulia"},
        # RO: cumparatorul probei = Coninfo SRL, ca in pagina de test a
        #     proprietarului (02.09.2026: «по идее покупатель должен был быть
        #     Coninfo»). SFS ii inlocuieste oricum denumirea/adresa din registru.
        "buyer": {"idno": "1012600013725", "name": "Coninfo SRL",
                  "address": "or. Chisinau, str. Alba Iulia, 75/b"},
        "lines": [{"name": "Serviciu de test integrare e-Factura", "cod": "TEST-1",
                   "um": "buc.", "qty": 1, "price": 1.00}],
        "tva_rate": 20, "seria": "TST", "number": "",
    }
    pv = testff.preview(payload)
    if not pv.get("success"):
        print("   XML invalid:", pv.get("error"), pv.get("errors"))
        return 4
    print("   XML generat: nr.", pv["data"]["number"], "total", pv["data"]["total"], "lei")
    if "--send" not in sys.argv:
        print(pv["data"]["xml"][:1500])
        print("   (fara --send nu se trimite nimic)")
        return 0

    # 3) trimiterea
    r = testff.send(payload, src="smoke")
    d = r.get("data") or {}
    print("   PostInvoices:", "✅ ACCEPTATA" if r.get("success") else "❌ RESPINSA",
          "| RequestId", d.get("request_id"), "| reply:", str(d.get("reply") or r.get("error"))[:600])
    if not r.get("success"):
        return 5

    # 4) cozile de semnare
    q = testff.signing_queues(api, src="smoke")
    for k, v in q["data"].items():
        print("   coada %-16s %s" % (k, ("✅ " if v.get("ok") else "❌ ") + str(v.get("reply", ""))[:200]))

    # 5) jurnalul
    from modules.efactura import journal
    for row in journal.recent(6, src="smoke"):
        print("   jurnal: %s %-22s HTTP %s %s ms %-9s %s" % (
            row["ts"], row["method"], row["http_status"], row["duration_ms"],
            row["result"], str(row["summary"])[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

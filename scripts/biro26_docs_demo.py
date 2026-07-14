#!/usr/bin/env python3
"""Biro26/OfficePlus — DEMO de aplicatie EXTERNA (doar biblioteca standard).

RO: Arata cum o aplicatie terta (desktop/mobil/integrare) vede lista
    documentelor clientului si descarca «Contul de plata» sau «Comanda
    cumparatorului» ca PDF, folosind NUMARUL documentului in forma hashtag
    (#338) — numarul vizibil in orice aplicatie nativa OfficePlus — fara
    sa cunoasca COD-ul intern.
EN: External-app demo: list the customer's documents and download the
    invoice/order PDF by the document NUMBER in hashtag form (#338), the
    number visible in any native OfficePlus application.

API folosit (auth: header X-API-Key = BIRO26_API_TOKEN):
  GET /api/biro26/docs?client=<nume|cod|#nr>&limit=N   -> lista documentelor
  GET /api/biro26/report-by-nr/<invoice|order>/%23338  -> PDF
  GET /api/biro26/doc/<cod>                            -> datele ca JSON

Utilizare / usage:
  python3 biro26_docs_demo.py --url https://officeplus.md --key <TOKEN> list
  python3 biro26_docs_demo.py list "Alexei"          # filtreaza dupa client
  python3 biro26_docs_demo.py pdf invoice "#338"     # salveaza PDF-ul
  python3 biro26_docs_demo.py pdf order 338 -o comanda.pdf
  python3 biro26_docs_demo.py json "#338"
  python3 biro26_docs_demo.py                        # mod interactiv
URL si token pot veni si din env: BIRO26_URL / BIRO26_API_KEY.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


class Biro26DocsApi:
    """RO: strat minimal de acces API pentru aplicatii externe.
    EN: minimal API layer an external application would embed."""

    def __init__(self, base_url: str, api_key: str):
        self.base = base_url.rstrip("/")
        self.key = api_key

    def _get(self, path: str):
        req = urllib.request.Request(self.base + path,
                                     headers={"X-API-Key": self.key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
        return body, ctype

    def docs(self, client: str = "", limit: int = 50):
        qs = urllib.parse.urlencode({"client": client, "limit": limit})
        body, _ = self._get(f"/api/biro26/docs?{qs}")
        data = json.loads(body)
        if not data.get("success"):
            raise RuntimeError(data.get("error"))
        return data["data"]

    def pdf_by_nr(self, kind: str, nr: str) -> bytes:
        # RO: numarul poate fi dat ca '#338' sau '338' (hashtag-ul se
        # codifica %23 in URL) / EN: '#338' or '338', hashtag URL-encoded
        enc = urllib.parse.quote(str(nr).strip(), safe="")
        body, ctype = self._get(f"/api/biro26/report-by-nr/{kind}/{enc}")
        if "pdf" not in ctype:
            raise RuntimeError(body[:200].decode("utf-8", "replace"))
        return body

    def doc_json(self, cod: int):
        body, _ = self._get(f"/api/biro26/doc/{int(cod)}")
        data = json.loads(body)
        if not data.get("success"):
            raise RuntimeError(data.get("error"))
        return data["data"]


def print_docs(rows):
    print(f"{'Nr':>8}  {'Data':10}  {'Suma':>10}  {'COD':>7}  Client")
    print("-" * 72)
    for r in rows:
        print(f"{r['nr']:>8}  {r['ddate'] or '':10}  "
              f"{(r['total'] or 0):>10.2f}  {r['cod']:>7}  "
              f"{r['client_name'] or ''}")
    print(f"-- {len(rows)} documente --")


def save_pdf(api, kind, nr, out=None):
    pdf = api.pdf_by_nr(kind, nr)
    name = out or f"{'Cont_de_plata' if kind == 'invoice' else 'Comanda'}_{str(nr).lstrip('#')}.pdf"
    with open(name, "wb") as f:
        f.write(pdf)
    print(f"OK: {name} ({len(pdf)} bytes)")
    return name


def interactive(api):
    print("=== Biro26 DEMO aplicatie externa ===")
    print("Comenzi: list [client] | pdf invoice|order #NR | json #NR | quit")
    while True:
        try:
            line = input("demo> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line or line in ("q", "quit", "exit"):
            break
        parts = line.split()
        try:
            if parts[0] == "list":
                print_docs(api.docs(" ".join(parts[1:])))
            elif parts[0] == "pdf" and len(parts) >= 3:
                save_pdf(api, parts[1], parts[2])
            elif parts[0] == "json" and len(parts) >= 2:
                cod = None
                # RO: acceptam si #NR — il rezolvam prin lista
                for d in api.docs(parts[1]):
                    cod = d["cod"]
                    break
                if cod:
                    print(json.dumps(api.doc_json(cod), indent=1,
                                     ensure_ascii=False))
                else:
                    print("document negasit")
            else:
                print("comanda necunoscuta")
        except Exception as e:
            print("EROARE:", e)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--url", default=os.environ.get("BIRO26_URL",
                                                   "https://officeplus.md"))
    p.add_argument("--key", default=os.environ.get("BIRO26_API_KEY", ""))
    p.add_argument("cmd", nargs="?", choices=["list", "pdf", "json"],
                   help="fara comanda = mod interactiv")
    p.add_argument("args", nargs="*")
    p.add_argument("-o", "--out", help="fisier PDF de iesire")
    a = p.parse_args()
    if not a.key:
        sys.exit("Lipseste tokenul API: --key sau env BIRO26_API_KEY "
                 "(= BIRO26_API_TOKEN de pe server)")
    api = Biro26DocsApi(a.url, a.key)
    if not a.cmd:
        interactive(api)
    elif a.cmd == "list":
        print_docs(api.docs(" ".join(a.args)))
    elif a.cmd == "pdf":
        if len(a.args) < 2:
            sys.exit("pdf <invoice|order> <#NR>")
        save_pdf(api, a.args[0], a.args[1], a.out)
    elif a.cmd == "json":
        rows = api.docs(a.args[0] if a.args else "")
        if not rows:
            sys.exit("document negasit")
        print(json.dumps(api.doc_json(rows[0]["cod"]), indent=1,
                         ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genereaza actul de acceptare din rezultatele probei.

RO: citeste `static/biro26/docs/acceptance/rezultate.json` (scris de
`biro26_acceptance_test.py`) si scrie
`docs/Biro26/ACT_ACCEPTARE_2026-09-12.html` — tabel cu puncte, ce s-a masurat
si capturile de ecran. Actul nu se scrie de mina: se regenereaza dupa fiecare
rulare a probei.
"""
import datetime
import html
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "static", "biro26", "docs", "acceptance", "rezultate.json")
OUT = os.path.join(ROOT, "docs", "Biro26", "ACT_ACCEPTARE_2026-09-12.html")
IMG = "/static/biro26/docs/acceptance/"

HEAD = """<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Act de acceptare • CRM pe date reale, magazin si documente</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Space+Grotesk:wght@500;600&display=swap');
  body{font-family:'Inter',system-ui,sans-serif}
  .font-display{font-family:'Space Grotesk','Inter',system-ui,sans-serif;font-weight:600}
  .shot{border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 1px 2px rgb(0 0 0/.06);width:100%}
  table.g{width:100%;font-size:14px;border-collapse:collapse}
  table.g th{background:#f8fafc;text-align:left;font-weight:600;color:#334155;padding:9px 11px;border-bottom:1px solid #e2e8f0}
  table.g td{padding:9px 11px;border-bottom:1px solid #f1f5f9;vertical-align:top}
  .pass{color:#047857;font-weight:600}.fail{color:#b91c1c;font-weight:600}
  .badge{background:linear-gradient(90deg,#0f172a,#1e2937);color:#fff;font-size:.72rem;padding:.15rem .7rem;border-radius:999px;font-weight:600;letter-spacing:.03em}
  .k{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:1px 6px;font-size:12.5px}
  .card{background:#fff;border:1px solid #e2e8f0;border-radius:22px;padding:22px;margin-top:18px}
  @media print{body{background:#fff}}
</style>
</head>
<body class="bg-slate-50 text-slate-800 antialiased">
<div class="max-w-screen-xl mx-auto px-6 py-10">
"""


def val(v):
    if isinstance(v, dict):
        return "<br>".join("%s: <b>%s</b>" % (html.escape(str(k)), html.escape(str(x)))
                           for k, x in v.items())
    if isinstance(v, list):
        return html.escape(", ".join(str(x) for x in v)) if v else "—"
    return html.escape(str(v))


def main():
    t = json.load(open(SRC, encoding="utf-8"))
    total, ok = len(t), sum(1 for x in t if x["ok"])
    data = datetime.date.today().strftime("%d.%m.%Y")
    p = [HEAD]
    p.append("""  <div class="badge inline-block mb-3">ACT DE ACCEPTARE • %s</div>
  <h1 class="font-display text-3xl md:text-4xl text-slate-900 tracking-tight">
    CRM pe datele reale, magazinul si documentele — proba completa</h1>
  <p class="mt-3 text-lg text-slate-600 max-w-3xl">Toate punctele s-au verificat pe
    <strong>paginile vii</strong>, in browser real, pe conturul de lucru
    <a class="text-emerald-600 hover:underline" href="https://officeplus.md/UNA.md/orasldev/crm/">officeplus.md</a>.
    Proba doar citeste: nu s-a creat niciun document si nu s-a schimbat nicio inregistrare.</p>
  <div class="mt-5 flex flex-wrap gap-3 text-sm">
    <span class="px-3 py-1 rounded-full bg-white border border-slate-200">puncte verificate: <b>%d</b></span>
    <span class="px-3 py-1 rounded-full bg-white border border-slate-200">trecute: <b class="pass">%d</b></span>
    <span class="px-3 py-1 rounded-full bg-white border border-slate-200">cazute: <b class="%s">%d</b></span>
  </div>
""" % (data, total, ok, "fail" if total - ok else "pass", total - ok))

    # rezumat
    p.append('  <div class="card"><h2 class="font-display text-xl text-slate-900 mb-3">Rezumat</h2><table class="g">')
    p.append("<tr><th style='width:44px'>#</th><th>Ce s-a verificat</th><th style='width:110px'>Rezultat</th></tr>")
    for x in t:
        p.append("<tr><td>%d</td><td><a class='text-emerald-600 hover:underline' href='#p%d'>%s</a></td>"
                 "<td class='%s'>%s</td></tr>"
                 % (x["nr"], x["nr"], html.escape(x["titlu"]),
                    "pass" if x["ok"] else "fail", "trecut" if x["ok"] else "cazut"))
    p.append("</table></div>")

    # puncte
    for x in t:
        p.append('  <div class="card" id="p%d">' % x["nr"])
        p.append('<h2 class="font-display text-xl text-slate-900">%d. %s <span class="%s">· %s</span></h2>'
                 % (x["nr"], html.escape(x["titlu"]), "pass" if x["ok"] else "fail",
                    "trecut" if x["ok"] else "cazut"))
        p.append('<table class="g mt-3"><tr><th style="width:28%%">Ce se astepta</th><td>%s</td></tr>'
                 % html.escape(x["asteptat"]))
        p.append('<tr><th>Ce s-a masurat</th><td>%s</td></tr>' % val(x["masurat"]))
        if x.get("chirias"):
            p.append('<tr><th>Chirias</th><td>%s</td></tr>' % val(x["chirias"]))
        if x.get("erp"):
            p.append('<tr><th>Sursa ERP</th><td>%s</td></tr>' % val(x["erp"]))
        if x.get("act"):
            p.append('<tr><th>Act separat</th><td><a class="text-emerald-600 hover:underline" '
                     'href="https://officeplus.md%s">%s</a></td></tr>' % (x["act"], x["act"]))
        p.append('</table>')
        for c in x.get("capturi", []):
            p.append('<img class="shot mt-4" src="%s%s" alt="%s">' % (IMG, c, html.escape(x["titlu"])))
        p.append('</div>')

    p.append("""  <div class="card">
    <h2 class="font-display text-xl text-slate-900 mb-3">Cum se repeta proba</h2>
    <p class="text-[15px] text-slate-700">Proba si actul sint doua scripturi, deci se pot rula oricind, iar
      capturile si cifrele se refac singure:</p>
    <pre class="k" style="display:block;padding:12px;margin-top:8px">python3 scripts/biro26_acceptance_test.py
python3 scripts/biro26_acceptance_act.py</pre>
    <p class="text-[15px] text-slate-700 mt-3">Adrese vii: 
      <a class="text-emerald-600 hover:underline" href="https://officeplus.md/UNA.md/orasldev/crm/">CRM</a> ·
      <a class="text-emerald-600 hover:underline" href="https://officeplus.md/UNA.md/orasldev/biro26">hub-ul Biro26</a> ·
      <a class="text-emerald-600 hover:underline" href="https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html">ghidul utilizatorului</a> ·
      <a class="text-emerald-600 hover:underline" href="https://officeplus.md/UNA.md/orasldev/b26docs/Biro26/OFFICEPLUS_TECH_DOC.html">documentatia tehnica</a> ·
      <a class="text-emerald-600 hover:underline" href="https://nufarul.eminescu.md/UNA.md/orasldev/crm/">conturul de proba</a>
    </p>
  </div>
</div></body></html>""")
    open(OUT, "w", encoding="utf-8").write("\n".join(p))
    print("act:", OUT, "| puncte:", total, "trecute:", ok)


if __name__ == "__main__":
    main()

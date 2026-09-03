# 03.09.2026 — «proiectul a fost sters iar de alt push»: ce era de fapt

Semnalul proprietarului: pe `officeplus.md/UNA.md/orasldev/biro26` au disparut
plachetele e-Factura, iar pagina «Servicii» din back-office e rupta.

## Ce s-a gasit (masurat, nu presupus)

| Simptom | Cauza reala | Unde |
|---|---|---|
| plachetele e-Factura lipsesc din hub | `templates/biro26_admin.html` de pe biroul `.250` era versiunea celeilalte echipe (412 linii, 01.09 15:55), fara hub-ul refacut (523 linii: e-Factura, documentatie, partner, pay-test, pdfme, traduceri). Versiunea lor e un SUBSET al celei noastre — nimic pierdut la ei. | doar biroul; nufarul avea 523 |
| «Servicii» → `KeyError: 0` | `models/biro26_services.py` indexa rindurile ca tuple (`r[0]`), dar `_rows()` intoarce dictionare. Defect LATENT din 25.07 (f9f956f), identic in `main` si pe ambele contururi. Bonus: exportul CSV ar fi scris numele coloanelor pe fiecare rind. | ambele contururi |
| `/api/biro26/site/config` → 500 | `models/biro26_site.py`: titlul paginii WP pus in `_t`, care e si aliasul `import time as _t` → `_t.time()` pe `None`. Defect LATENT din 22.08 (a1b48de), identic peste tot. | ambele contururi |

Deci NU a fost un push care sa stearga munca de azi: fisierele modulului
e-Factura, CSS-ul cardurilor, link-ul mobil erau intacte (verificat prin
mtime: in ultimele 4 ore doar fisierele noastre). Doua erau bug-uri vechi in
fisiere comune, iesite la iveala cind s-a intrat pe paginile respective; unul
era hub-ul suprascris de deploy-ul lor de pe 01.09.

## Ce s-a facut

1. Hub-ul: versiunea de 523 de linii pusa inapoi pe birou, cu backup
   `templates/biro26_admin.html.bak-hub-*`.
2. `biro26_site.py`: `_wp_title, _html = _wp(...)` — aliasul `time` nu mai e
   ascuns.
3. `biro26_services.py`: acces prin chei (`r["code"]`, `rows[0]["src_sql"]`,
   `COUNT(*) CNT` → `rows[0]["cnt"]`), CSV din tuplele brute in ordinea lui
   `columns`.
4. Teste FARA Oracle (`tests/test_biro26_shared_fixes.py`, 5): lista, count,
   CSV, «nu a ramas indexare pe tuple», «aliasul nu e ascuns».
5. Ambele contururi: `/site/config` 200 (7 sectiuni, min_order 1500),
   «Servicii» intoarce functiile.

## Lectia (regula nr. 2, inca o data)

Cele doua bug-uri au trait saptamini in `models/` fara sa le vada nimeni,
pentru ca paginile lor se deschid rar si nu aveau teste. Un test de 5 linii
cu mock le-ar fi prins la commit. Fisierele comune nu se testeaza pe
productie.

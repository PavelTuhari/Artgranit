# Răspunsul către client (Mariana Solomon, una.md) — jurnal

> Ce s-a livrat, de ce, ce fișiere, cum se verifică. Rețea de siguranță:
> după acest fișier munca se poate reface dacă html-ul e suprascris.

## 05.09.2026 — versiunea a treia, „mapare pe mecanismele una.md"

**De ce.** Clientul: «raspuns punctual pe fiecare intrebare», «lirica AI știm
și noi», și a repetat întrebarea: *tabel separat sau field în nomenclator?*
Din cele cinci întrebări agrease una singură (mijlocul de plată).

**Ce s-a schimbat în `faq_arhitectura.html`:**

1. **Matricea deciziilor** (secțiunea 0): un tabel — întrebare → decizie →
   mecanism în una.md → stare (agreat / propus / de confirmat). Răspunsul
   pe o singură pagină înainte de detalii.
2. **Q1, „două straturi"**: atributele ambalajului = tabel separat
   (`SDA_PACK`); liniile de pe bon = coduri analitice în nomenclatorul lor,
   grupă „SDA" — date, nu schemă. Asta închide „câmp sau tabel" fără să
   contrazică felul în care casa lor emite linii.
3. **Q2, regula de tranziție**: cine decide, pe articol — EAN nou (nimic de
   făcut), stoc rezidual mic (`ACTIV_DIN`), stoc rezidual mare (cod geamăn
   „fără SD"). Pragul ~2 săptămâni, motivat: OfficePlus nu ține două
   stocuri sub același cod și nu-l învățăm doar pentru șase luni.
4. **Q3, „cod de marfă cu altfel de formule?"** — răspuns direct: da, cod
   analitic de serviciu, formule proprii (cont de decontare, fără TVA), nu
   cod de marfă; 5 categorii × 2 metode = 10 coduri în grupa „SDA — preluare".
5. **Q4, tipul de plată**: „Tichet SDA" și „Restituire depozit SD" ca
   tipuri de plată în nomenclatorul lor; tipul declanșează validarea prin
   `PK_SDA`, valoarea vine din registru.

**Fișiere:** `docs/SDA/faq_arhitectura.html` (servit la `/sda/faq`, fără
autentificare), acest jurnal. Fără schimbări de cod.

**Verificare:** `curl -s https://nufarul.eminescu.md/UNA.md/orasldev/sda/faq
| grep -c "Matricea deciziilor"` → 1; `pytest tests/test_sda.py` verde
(testul `test_faq_page_is_served_and_open_without_login`).

## 03.09.2026 — versiunea a doua, punctuală

Rescris ca spec după feedback: decizie într-o linie, obiecte cu câmpuri,
pași la casă. Adăugat stadiul real: 15 tabele instalate în Oracle.

## 03.09.2026 — versiunea întâi, narativă

Cinci întrebări, răspuns cu temei juridic. Respinsă de client ca prea
literară. Păstrată în istoricul git (`dd08aca`).

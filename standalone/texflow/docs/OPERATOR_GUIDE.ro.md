# Instrucțiuni pentru operatorul de recepție

[Русский](OPERATOR_GUIDE.md) · **Română** · [English](OPERATOR_GUIDE.en.md)

Scopul este să sortați un sac în câteva minute, nu în ore. Fiecare articol
trebuie înregistrat ca variantă „model · culoare · mărime”, cu cod de bare și
preț.

## Pregătirea locului de muncă

- Laptop sau PC cu TexFlow (`python run.py`). Pentru mai multe posturi:
  `python run.py --host 0.0.0.0`, iar pe celelalte se deschide
  `http://IP-laptop:5077`.
- Scaner de coduri de bare în regim tastatură, cu sufix Enter. Majoritatea
  scanerelor au acest regim implicit.
- Imprimantă termică Zebra sau TSC cu rolă 58×40 mm, sau o imprimantă
  obișnuită cu coli A4.
- O masă mare și cutii etichetate pe categorii: tricouri, blugi, rochii…
- Limba interfeței: comutatorul **RU / RO / EN** din antet.

## Pasul 1. Creați livrarea

„Livrări” → „Livrare nouă”.

| Câmp | Exemplu | De ce |
|---|---|---|
| Număr | `TR-2026-11-01` | referință în documente |
| Furnizor | `Istanbul Tekstil` | fișele produselor |
| Țara | Turcia / China | țara de origine |
| Valută, curs | USD × 17.8 | conversia achiziției în moneda locală |
| Transport, Vamă, Broker, Altele | 4500, 1200, 800, 0 | în moneda locală, intră în cost |
| Repartizarea cheltuielilor | după valoare | articolele scumpe poartă mai mult. „După greutate” — dacă s-a plătit la kg |
| Saci | 4 | creează imediat sacii 1..4 (dacă nu există listă) |

## Pasul 2. Încărcați lista de colete

Lista de la furnizor vine de obicei în Excel. Ea se salvează ca CSV:
„Fișier → Salvare ca → CSV (separator punct și virgulă)”.

Coloanele necesare (în orice ordine, cele în plus sunt ignorate):

| Coloană | Variante de antet |
|---|---|
| sac | `bag_no`, `sac`, `мешок`, `çuval`, `包` |
| categorie | `category`, `categorie`, `категория`, `kategori`, `类别` — cod (`TSH`, `JNS`) sau denumire din nomenclator (în rusă, română sau engleză) |
| descriere | `description`, `descriere`, `описание`, `açıklama`, `品名` |
| cantitate (**obligatoriu**) | `qty`, `cantitate`, `buc`, `кол-во`, `adet`, `数量` |
| preț pe buc | `unit_price`, `preț`, `цена`, `fiyat`, `单价` |
| greutate, kg | `weight_kg`, `greutate`, `вес`, `ağırlık`, `重量` |

Lista se numește aproximativă: „tricouri — 120 buc”, fără culori și mărimi.
Este suficient. Culorile și mărimile apar la sortare, iar cantitățile se
verifică la pasul 4.

Dacă o categorie nu este recunoscută, apare un avertisment. O astfel de
categorie se adaugă în „Nomenclatoare”, apoi lista se încarcă din nou.

## Pasul 3. Sortați sacul

Pagina livrării → „Sortează” la sac.

**Articolul există deja** (de exemplu, al doilea lot din același model):
scanați eticheta sau codul de bare — se adaugă +1 buc. Răspunsul apare sub
câmpul scanerului: ✓ — recepționat, ✗ — un astfel de cod nu există.

**Model nou:**

1. Așezați conținutul sacului pe masă pe modele. În cadrul modelului — pe
   culori, în cadrul culorii — pe mărimi. Acesta este procedeul principal:
   întâi așezați, apoi introduceți cantitatea, nu introduceți fiecare
   articol separat.
2. Completați „Model nou”: denumirea (cum va fi pe etichetă), categoria (de ea
   depind grila de mărimi și adaosul) și, dacă se cunoaște, compoziția.
   Articolul se creează singur (`TSH0007`). Prețul de achiziție se preia din
   lista de colete după categorie și poate fi corectat.
3. Se deschide matricea. Faceți click pe culorile necesare — fiecare devine un
   rând. Culorile sunt grupate ca pe site-ul Zara: Alb (alb, lăptos, ecru),
   Bej (bej, nisipiu, camel), Albastru (albastru, bleumarin, denim)…
4. Introduceți cantitatea în celulele „culoare × mărime”. **Enter** trece la
   celula următoare, săgețile mută cursorul. Totalurile pe rânduri și coloane
   se calculează imediat.
5. **Ctrl+Enter** sau „Înregistrează”. Butonul „Înregistrează și tipărește
   etichete” deschide direct tipărirea exact pentru acest lot.

**Greșeală:** în jurnalul recepției apăsați × la rând sau introduceți în
matrice un număr negativ (−2).

Când sacul e gol — „Sac sortat”.

## Pasul 4. Verificarea cu lista

Pagina livrării, blocurile „Verificare pe categorii” și „Verificare pe saci”:

- **corespunde** — totul e bine;
- **lipsă** (cu roșu) — a venit mai puțin decât în listă: temei de reclamație
  către furnizor;
- **surplus** — a venit mai mult;
- **nu e în listă** — categoria nu a fost declarată.

Lista este aproximativă, așa că o diferență de 2–5 % este de obicei normală.

## Pasul 5. Prețuri

„Prețuri” la livrare. Pentru fiecare model se vede:

- achiziția în valută;
- costul în moneda locală, cu taxa vamală și cota de transport, vamă și broker;
- adaosul categoriei;
- prețul propus (deja rotunjit: 189.90, 249.90…);
- adaosul real după rotunjire.

Puteți scrie un preț propriu în câmpul „Preț propriu”. Apoi „Înregistrează
prețurile în fișe”.

Dacă prețul unui model nu trebuie schimbat (promoție, preț negociat), el se
blochează în fișa modelului cu bifa „Blochează prețul”. Recalcularea nu atinge
un astfel de preț.

Adaosurile categoriilor se schimbă în „Nomenclatoare”. Rotunjirea (pasul,
terminația .90/.99) și TVA — în „Setări”.

## Pasul 6. Etichete

- **Pentru toată livrarea sau un sac** — de pe pagina livrării. Etichete câte
  bucăți au fost recepționate.
- **Pentru un model** — din fișa modelului.
- **O singură etichetă** — butonul „etichetă” la variantă (de exemplu, pentru
  a înlocui una deteriorată).

Înainte de tipărire puteți corecta numărul de copii pe fiecare rând.

Alegerea formatului:

- **ZPL** — pentru Zebra;
- **TSPL** — pentru TSC;
- **PDF A4** — pentru coli cu etichete autoadezive. Tipăriți la scara 100%.
  „Începe de la celula” permite completarea unei coli începute;
- **PDF rolă** — pentru tipărire prin driver sau la imprimanta virtuală.

Butoane: „Deschide / descarcă”, „Descarcă fișier”, „Tipărire la imprimantă”
(la adresa din setări).

Limba culorii pe etichetă (Negru / Чёрный / Black) se alege în „Setări”.
Detalii despre imprimante — [LABELS.ro.md](LABELS.ro.md).

## Pasul 7. Catalog

„Catalog” — fișele modelelor cu culori, preț și stoc. În fișă:

- culorile cu coduri și grupe;
- grila de mărimi (tăiată — nu e în stoc);
- tabelul SKU și EAN;
- butonul de tipărire a fișei.

**Export CSV** — lista completă a variantelor (articol, culoare, mărime, SKU,
EAN, preț, stoc) pentru încărcare în magazinul online sau la casă. Denumirile
culorilor și categoriilor sunt în limba curentă a interfeței.

## Taste rapide pe ecranul de sortare

| Tastă | Acțiune |
|---|---|
| Enter în câmpul scanerului | acceptă codul scanat |
| Enter în matrice | celula următoare |
| ← → ↑ ↓ | deplasare în matrice |
| Ctrl+Enter | înregistrează matricea |

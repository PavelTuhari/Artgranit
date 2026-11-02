# TexFlow — recepția îmbrăcămintei din saci, catalog, prețuri și etichete

[Русский](README.md) · **Română** · [English](README.en.md)

Aplicație web autonomă pe **Python + Flask + SQLite**. Servește la prelucrarea
rapidă a îmbrăcămintei care vine din Turcia și China în saci, unde totul e
amestecat, iar la livrare există doar o listă de colete **aproximativă**.

TexFlow duce marfa prin cinci pași:

1. o recepționează pe saci, așezând fiecare model în matricea „culoare × mărime” (ca la Zara);
2. compară faptul cu lista de colete;
3. calculează costul ținând cont de cheltuielile de import;
4. stabilește prețurile după adaosurile categoriilor;
5. tipărește etichete pe **Zebra (ZPL)**, **TSC (TSPL)** sau în **PDF** —
   coală A4 pentru imprimanta obișnuită sau rolă pentru imprimanta virtuală.

Interfața este în trei limbi: **rusă, română, engleză**. Comutatorul
RU / RO / EN este în antet. Denumirile culorilor, categoriilor și grilelor de
mărimi sunt traduse, iar culoarea de pe etichetă se poate tipări în oricare
dintre cele trei limbi.

Nu e nevoie de server sau internet: un singur fișier de bază de date
`instance/texflow.db`, pornire de pe laptop.

| Document | Despre ce |
|---|---|
| [docs/ARCHITECTURE.ro.md](docs/ARCHITECTURE.ro.md) | scheme Mermaid: proces, date (ER), calculul prețului, tipărire |
| [docs/LABELS.ro.md](docs/LABELS.ro.md) | imprimante Zebra/TSC, PDF, chirilică, calibrarea colii A4 |
| [docs/OPERATOR_GUIDE.ro.md](docs/OPERATOR_GUIDE.ro.md) | instrucțiune pas cu pas pentru operator / gestionar |
| [samples/](samples/) | exemple de liste de colete: turcă și chineză |

---

## 1. Instalare și pornire

Este nevoie de Python 3.10 sau mai nou (verificat pe 3.13).

```bash
cd standalone/texflow
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py --demo               # deschide http://127.0.0.1:5077/ cu o livrare demo
```

| Parametru | Ce face |
|---|---|
| `--host 0.0.0.0` | acces de pe tablete și PC-uri din rețeaua locală, de exemplu scaner la al doilea post |
| `--port 5077` | portul |
| `--db cale.db` | alt fișier de bază, de exemplu o bază separată pe sezon |
| `--demo` | încarcă livrarea demo `DEMO-TR-01`: 3 modele, bucăți recepționate, prețuri |
| `--no-browser` | nu deschide browserul automat |

Variabile de mediu: `TEXFLOW_DB` — calea bazei, `TEXFLOW_PDF_FONT` — font TTF
propriu pentru PDF.

**Copie de rezervă** — copiați fișierul `instance/texflow.db`. Dacă aplicația
rulează, e mai sigur așa: `sqlite3 instance/texflow.db ".backup backup.db"`.

## 2. Teste

```bash
cd standalone/texflow
python -m pytest -q
```

58 de teste, fără wallet Oracle și fără imprimantă. Ele verifică:

- reguli: EAN-13, SKU, rotunjirea, adaosul cu TVA, repartizarea cheltuielilor, verificarea;
- etichete: ZPL, TSPL, PDF;
- trimiterea la o „imprimantă” TCP falsă;
- scenariul HTTP complet;
- traducerile: fiecare șir al interfeței are RO și EN, iar paginile RO/EN nu au chirilică.

## 3. Cum se lucrează (pe scurt)

Instrucțiunea completă — [docs/OPERATOR_GUIDE.ro.md](docs/OPERATOR_GUIDE.ro.md).

1. **Livrări → Livrare nouă.** Număr, furnizor, țară, valută și curs față de
   moneda locală. Cheltuieli în moneda locală: transport, taxe vamale, broker,
   altele. Metoda de repartizare: după valoare, pe bucăți sau după greutatea
   sacilor.
2. **Lista de colete.** CSV `sac;categorie;descriere;cantitate;preț;greutate`.
   Antetele se pot scrie în rusă, română, engleză, turcă sau chineză.
   Codificările UTF-8, cp1251, cp1254 și GB18030 sunt recunoscute automat.
   Sacii se creează automat.
3. **Sortarea sacului.** O marfă deja înregistrată se scanează (EAN sau SKU):
   +1 buc. Un model nou se creează în formularul „Model nou”: click pe culori,
   apoi cantitățile în matricea de mărimi. Enter — celula următoare,
   Ctrl+Enter — salvează. Prețul de achiziție se preia din lista de colete
   după categorie.
4. **Verificarea** pe pagina livrării, pe categorii și pe saci: „corespunde”,
   „lipsă”, „surplus”, „nu e în listă”.
5. **Prețuri.** Cost → adaosul categoriei → TVA → preț frumos (de exemplu,
   189.90). Puteți scrie prețul propriu sau îl puteți bloca în fișă.
6. **Etichete** pentru toată livrarea, un sac, un model sau o variantă.
   Numărul de etichete este egal cu bucățile recepționate.

## 4. Limbi

| Unde | Cum |
|---|---|
| Interfață | comutatorul **RU / RO / EN** din antet; se memorează în browser. Limba implicită — „Setări → Limba implicită a interfeței” |
| Nomenclatoare | culoarea, grupa de culori, categoria și grila au `name` (RU), `name_ro`, `name_en`; traducere goală → denumirea rusă |
| Etichetă | „Setări → Limba denumirilor culorilor pe etichetă”: „Negru” în loc de „Чёрный”. Denumirea modelului și compoziția se tipăresc așa cum au fost introduse |
| Lista de colete | antetele sunt înțelese și în română; categoria se poate indica în română sau engleză |

## 5. Modelul de date (SQLite, normalizat)

| Tabel | Entitate |
|---|---|
| `suppliers` | furnizori |
| `size_scales`, `sizes` | grile de mărimi: litere XXS–3XL, damă EU 32–48, bărbați 44–58, blugi W24–38, copii după înălțime 86–164, încălțăminte 35–46, ONE |
| `color_families`, `colors` | grupe de culori în stil Zara (Alb, Negru, Bej, Albastru…) și culori cu coduri `001`, `800`, `401`… |
| `categories` | categorie → grila de mărimi, adaos %, taxă vamală %, cod NC |
| `shipments` | livrare: valută, curs, transport/vamă/broker/altele, metoda de repartizare, stare |
| `bags` | sacii livrării: număr, greutate, stare (`closed` → `sorting` → `done`) |
| `packing_lines` | rândurile listei de colete aproximative |
| `products` | model: articol, denumire, categorie, compoziție, preț de achiziție, preț cu amănuntul, blocare |
| `variants` | varianta „culoare × mărime”: `sku` și `ean13` unice |
| `intake_items` | jurnalul recepției: câte bucăți din ce variantă, din ce sac; achiziție; cost |
| `label_jobs` | jurnalul tipăririi |
| `settings` | setări: brand, TVA, rotunjire, dimensiunile etichetelor, imprimante, limbi |

Stocul nu este o coloană separată: este `SUM(intake_items.qty)` pe variantă.
O numărare greșită se corectează cu un rând cu cantitate negativă sau prin
ștergerea rândului din jurnal.

**SKU** = `ARTICOL-CODCULOARE-MĂRIME`, de exemplu `TSH0001-800-M`.
**EAN-13** — intern, cu prefixul `200` (intervalul 20–29 rezervat de GS1
pentru uz intern în magazin) și cifra de control corectă.

## 6. Formule

```
achiziție_loc = achiziție_val × curs
taxă_vamală   = achiziție_loc × taxa_categoriei %
cota          = (transport + vamă + broker + altele) × baza_poziției / Σ baza
                 baza: valoare | bucăți | greutate (greutatea sacului × cota bucăților din sac)
cost          = achiziție_loc + taxă_vamală + cota / qty
preț_calcul   = cost × (1 + max(adaos_categorie, adaos_minim) %) × (1 + TVA %)
preț          = ⌈(preț_calcul + terminație) / pas⌉ × pas − terminație      (pas 10, terminație 0.1 → 189.90)
```

## 7. Listă de verificare după instalare

1. `python -m pytest -q` — toate testele trec.
2. `python run.py --demo` deschide pagina principală; în „Catalog” sunt 3 modele cu prețuri.
3. Comutați la **RO** în antet — toată interfața este în română.
4. „Etichete” → livrarea `DEMO-TR-01` → „PDF A4” → „Deschide”: coală 3×8 cu coduri de bare.
   Scanerul trebuie să citească EAN-ul de pe hârtie.
5. Pentru Zebra/TSC: adresa imprimantei în „Setări”, apoi tipărirea unei etichete
   (butonul „etichetă” la variantă) și verificarea că se scanează.

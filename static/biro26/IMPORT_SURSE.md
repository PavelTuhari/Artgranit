# Sursele de import — catalog complet

> Generat din tabela `TMS_ORG_IMPSRC` (extinderea cartelei furnizorului `TMS_ORG`).
> Varianta tabelara: `IMPORT_SURSE.csv`. Regenerare: `python3 scripts/gen_import_surse.py`.

## De ce exista acest document

Fiecare sursa de date are propriile capcane: unde e antetul, ce coloane exista, cum
arata articolul, ce lipseste. Pana acum aceste detalii traiau doar in capul celui care
facea importul; acum stau in baza si pot fi alese din back-office.

## Prefixul de articol — regula cea mai importanta

Codurile scurte sau pur numerice (`248`, `670`, `2917`) inseamna **produse diferite la
fiecare furnizor**. Folosite ca atare, potrivesc marfuri complet nelegate — asa au aparut
629 de potriviri false la importul officeshop.

De aceea articolul slab primeste un prefix, ales in ordinea:

1. **BRAND-ul randului** (din fisier) — `Trefl` + `2080` -> `TREFL-2080`
2. **Prefixul sursei** (`ART_PREFIX`) — daca randul n-are brand -> `OS-2080`
3. Daca nu exista niciunul, randul **nu se importa** (paza 5).

Un articol e considerat slab daca are sub `ART_MIN_LEN` caractere (implicit 6) **sau**
e format numai din cifre.

## Sursele

| Cod | Denumire | Tip | Prefix | Algoritm | Doar articol | Produse NOI |
|---|---|---|---|---|---|---|
| `BIROLUX` | Birolux MT SRL | EMAIL | `BLX` | UNIVERSAL | da | doar cele noi |
| `BNN` | BNN | EMAIL | `BNN` | UNIVERSAL | da | doar cele noi |
| `CRAFTI` | CRAFTI BUSSINES SRL | EMAIL | `CRF` | UNIVERSAL | da | doar cele noi |
| `RADOP` | RADOP | EMAIL | `RDP` | PRICES_ONLY | da | doar cele noi |
| `RICHI` | RICHI-TICHI | EMAIL | `RCH` | UNIVERSAL | da | doar cele noi |
| `TEHELAN` | Tehelan (articole de menaj) | EMAIL | `THL` | UNIVERSAL | da | doar cele noi |
| `OFFICEPLUS` | Administrator OfficePlus (intern) | MANUAL | `—` | UNIVERSAL | da | doar cele noi |
| `BIROVITS` | birovits.md (scraping catalog) | SCRAPING | `BRV` | UNIVERSAL | da | doar cele noi |
| `OFFICESHOP` | officeshop.md (scraping catalog) | SCRAPING | `OS` | UNIVERSAL | da | doar cele noi |
| `ULTRA` | ULTRA.md | SCRAPING | `ULT` | UNIVERSAL | da | doar cele noi |

## Detalii per sursa

### BIROLUX — Birolux MT SRL

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier pe e-mail
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `BLX` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; 26 foi
- **Preturi doar dupa articol:** da

### BNN — BNN

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier pe e-mail
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `BNN` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx
- **Preturi doar dupa articol:** da
- **Cartela furnizorului:** `TMS_ORG.COD = 161242`

### CRAFTI — CRAFTI BUSSINES SRL

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier lunar pe e-mail
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `CRF` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; mai multe foi = categorii
- **Preturi doar dupa articol:** da
- **Cartela furnizorului:** `TMS_ORG.COD = 161245`

**Particularitati / capcane:**

> Preturi cu VIRGULA zecimala -> se normalizeaza la punct. Articole reformatate (spatii in plus). ANGRO = pretul de achizitie CU TVA. Fara coloana de coduri de bare.

### RADOP — RADOP

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier pe e-mail
- **Algoritm de incarcare:** `PRICES_ONLY`
- **Prefix de articol:** `RDP` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; 2 foi
- **Preturi doar dupa articol:** da

**Particularitati / capcane:**

> Lista de preturi noi.

### RICHI — RICHI-TICHI

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier pe e-mail
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `RCH` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; 15 foi
- **Preturi doar dupa articol:** da

### TEHELAN — Tehelan (articole de menaj)

- **Tip:** Fisier primit pe e-mail
- **Locatie:** fisier pe e-mail
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `THL` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; 3 foi
- **Preturi doar dupa articol:** da

### OFFICEPLUS — Administrator OfficePlus (intern)

- **Tip:** Incarcare manuala / export intern
- **Locatie:** export intern
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `—` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; 12 foi
- **Preturi doar dupa articol:** da

**Particularitati / capcane:**

> Export intern, articolele sint deja cele din catalog.

### BIROVITS — birovits.md (scraping catalog)

- **Tip:** Scraping de pe site
- **Locatie:** https://birovits.md
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `BRV` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; o foaie, 25 coloane
- **Preturi doar dupa articol:** da

**Particularitati / capcane:**

> Rand 1 = titlu "all_products", antetul e pe randul 2. Fara coduri de bare. images_all = galerie in aceeasi celula, separator " | ". Coloana is_new = marcaj de site, NU produs nou la noi. category_path e slug, nu denumire.

### OFFICESHOP — officeshop.md (scraping catalog)

- **Tip:** Scraping de pe site
- **Locatie:** https://officeshop.md
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `OS` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; Products (18 col) + Images_2 (galerie)
- **Preturi doar dupa articol:** da

**Particularitati / capcane:**

> Rand 1 = nota, antetul e pe randul 2. Articole scurte/numerice frecvente -> prefix obligatoriu. Coloana barcode exista dar e GOALA. 25% din randuri nu au articol deloc (se sar). Galeria se importa separat cu import_images(). ATENTIE: fisierul se numeste la fel ca la birovits.

### ULTRA — ULTRA.md

- **Tip:** Scraping de pe site
- **Locatie:** https://ultra.md
- **Algoritm de incarcare:** `UNIVERSAL`
- **Prefix de articol:** `ULT` · articol slab sub 6 caractere sau pur numeric
- **Format:** xlsx; foarte multe foi (136)
- **Preturi doar dupa articol:** da

**Particularitati / capcane:**

> Acelasi articol apare pe foi diferite cu produse diferite -> randul se alege verificind NUMELE. RETAIL vs ANGRO se confunda usor, verificati antetul.

## Istoricul incarcarilor

| Fisier | Foi | Randuri | Load | Prima incarcare |
|---|---|---|---|---|
| `Price nou.xlsx` | 2 | 1342 | 4–9 | 10.07.2026 |
| `radop_categories_grouped_4_ro.xlsx` | 2 | 20860 | 5–6 | 11.07.2026 |
| `PRISE NOU 11.07.2026.xlsx` | 1 | 10430 | 7–7 | 12.07.2026 |
| `radop.xlsx` | 2 | 8848 | 8–10 | 12.07.2026 |
| `angro CRAFTI.xlsx` | 7 | 63497 | 11–277 | 16.07.2026 |
| `ULTRA.md.xlsx` | 136 | 192488 | 12–189 | 20.07.2026 |
| `ULTRA.md (1).xlsx` | 68 | 96244 | 121–226 | 20.07.2026 |
| `Administrator OfficePlus.xlsx` | 12 | 78228 | 160–171 | 21.07.2026 |
| `3. Carti educationale.xlsx` | 3 | 94777 | 172–229 | 21.07.2026 |
| `RADOP PRISE NOU 11.07.2026.xlsx` | 2 | 20860 | 190–209 | 26.07.2026 |
| `angro CRAFTI (1).xlsx` | 2 | 18142 | 208–227 | 26.07.2026 |
| `Articole de menaj_tehelan.xlsx` | 3 | 3825 | 230–232 | 27.07.2026 |
| `RICHI-TICHI.xlsx` | 15 | 122408 | 233–248 | 27.07.2026 |
| `Книга1.xlsx` | 1 | 1 | 245–245 | 28.07.2026 |
| `Rechizite de birou.xlsx` | 2 | 18224 | 249–250 | 29.07.2026 |
| `Birolux MT SRL.xlsx` | 26 | 42338 | 251–276 | 06.08.2026 |
| `CRAFTI.xlsx` | 6 | 8020 | 278–283 | 10.08.2026 |
| `all_products 2.xlsx` | 3 | 22453 | 284–286 | 12.08.2026 |

> ⚠️ Fisierele **birovits** si **officeshop** se numesc amindoua `all_products 2.xlsx`.
> Numele fisierului NU identifica sursa — de aceea sursa se alege explicit la incarcare.

## Tabelele

```
TMS_UNIVERS (TIP='O')
   └── TMS_ORG                (cartela organizatiei)
            └── TMS_ORG_IMPSRC    (sursele de import)          1:N
                     └── TMS_ORG_IMPFILE (fisierele pastrate)  1:N
```

`TMS_ORG_IMPFILE` pastreaza fisierul original ca BLOB, impreuna cu amprenta SHA-256
(o reincarcare identica se recunoaste), legatura cu stagin-ul (`LOAD_ID`) si raportul
importului. DDL: `TMS_ORG_IMPORT.tab.sql`.

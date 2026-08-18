# Import din fișiere cu mai multe foi: foile sunt grupe de marfă

> Cum se importă un fișier în care marfa stă pe mai multe foi (tab-uri), fiecare foaie
> fiind o grupă. Întâi grupele, apoi marfa. Include și maparea manuală a coloanelor —
> obligatorie când antetul fișierului e stricat.

---

## 1. Când se folosește

Furnizorii trimit des un singur fișier Excel cu marfa împărțită pe tab-uri:

```
PRINTERRA.xlsx
 ├── Imprimante                        612 rânduri
 ├── Hirtie si baza pentru imprimare   278
 ├── Cerneala pentru imprimante        427
 ├── Cartuse pentru imprimante       1 887
 ├── Sublimare                         261
 └── Accesorii si piese IMPRIMANTE   1 682
```

Tab-urile **sunt** grupele de marfă. Fără o regulă explicită, toată marfa ar ateriza în
grupa implicită `IMPORT PT`, iar structura furnizorului s-ar pierde.

## 2. Algoritmul `SHEET_AS_GROUP`

Se alege în back-office din lista **«Algoritm de încărcare»**. Ce face:

- **numele foii devine GRUPA** mărfii din acea foaie;
- dacă fișierul are **și** o coloană `GRUPA`, **coloana are prioritate** — numele foii e
  doar rezervă. Așa un fișier corect nu e stricat de algoritm;
- coloana `CATEGORIE`, dacă există, rămâne subgrupă: rezultă `Grupă > Categorie`.

Lista completă a algoritmilor stă în tabela `YBIRO_IMPORT_ALGO` și se extinde fără
modificări de cod:

| Cod | Ce face |
|---|---|
| `UNIVERSAL` | detectare automată a coloanelor (implicit) |
| `SHEET_AS_GROUP` | **foile = grupe de marfă** |
| `MANUAL_MAP` | operatorul asociază manual coloanele |
| `PRICES_ONLY` | doar prețuri, nu creează marfă |
| `IMAGES` | doar galeria de imagini |
| `BARCODES` | doar coduri de bare |

## 3. Ordinea corectă: întâi grupele, apoi marfa

Grupele nu se creează separat, printr-un pas manual — se creează **odată cu marfa**, dar
sunt **înregistrate separat**, ca să se știe de unde au apărut și cum se anulează.

Ce se întâmplă la import, în ordine:

1. fiecare foaie se încarcă în stagingul brut, păstrându-și numele (`BIRO26PT_RAW.SHEET`);
2. la proiecție, `GRUPA` se completează din numele foii (dacă nu există coloană `GRUPA`);
3. marfa nouă se plasează în **nodul real** din arbore, după grupă;
4. grupele se scriu în `YBIRO_IMPORT_GROUPS` cu marcajul `CREATED` sau `EXISTING`;
5. se generează fișierele de grupe (CSV + SQL de anulare) în `grupe_import/`.

**De ce contează pasul 4:** o grupă marcată `CREATED` a apărut la acest import și se poate
anula. Una `EXISTING` era deja folosită de altcineva — anularea ei ar strica alte importuri.

```bash
python3 scripts/gen_import_groups.py <import_id>
```

## 4. Maparea manuală a coloanelor

### Când e obligatorie

Detectarea automată citește antetul. Dacă antetul e stricat, coloana **nu se găsește**, iar
importul **reușește tăcut**, fără prețuri.

Cazul real, setul 12 (PRINTERRA) — pe **4 din 6 foi** cineva suprascrisese antetul
coloanelor de preț cu valori din primul rând:

| Foaie | Coloanele 12–13 | Efect |
|---|---|---|
| Imprimante | `Price Online`, `Розничная цена с НДС` | ✅ detectate |
| Cerneala | `Price Online`, `Розничная цена с НДС` | ✅ detectate |
| Hirtie si baza | `43,50`, `43.5` | ❌ **fără preț** |
| Cartuse | `109,50`, `109.5` | ❌ **fără preț** |
| Sublimare | `189,00`, `189` | ❌ **fără preț** |
| Accesorii si piese | `526,50`, `526.5` | ❌ **fără preț** |

Fără mapare manuală, 4 108 din 5 147 de produse ar fi intrat **fără niciun preț**.

### Cum se face

La pasul *Analizează*, sub rezultat apare tabelul de mapare: fiecare câmp logic
(`ARTICOL`, `DENUMIRE`, `RETAIL`, `ANGRO`, …) cu o listă de coloane din fișier. Alegeți
coloana corectă — se salvează cu strategia `MANUAL` și analiza se reface.

**Maparea manuală nu se pierde la reanaliză.** Detectarea automată o respectă: nu suprascrie
nici câmpul, nici coloana pe care le-a fixat omul. (Până la setul 12 exista un defect —
`detect_columns` ștergea toate mapările, inclusiv cele manuale; corectat.)

### Ce se vede în raport

```
c10 -> ANGRO     [HEADER]  "Цена закупки с НДС"
c11 -> ONLINE    [MANUAL]  "43,50"        <- pus de operator
c12 -> RETAIL    [MANUAL]  "43.5"         <- pus de operator
```

Eticheta `[MANUAL]` arată exact ce a corectat omul față de ce a găsit sistemul.

## 5. Procedura completă, pas cu pas

1. **Sursa** — dacă furnizorul e nou, se înregistrează în `TMS_ORG_IMPSRC` (cod, prefix de
   articol, algoritm implicit, capcanele fișierului în `NOTES`).
2. **Încarcă** fișierul în back-office. Fiecare foaie devine o încărcare separată (`load_id`).
3. **Alege algoritmul**: `SHEET_AS_GROUP` pentru fișiere cu foi-grupe.
4. **Analizează** (dry-run) — nu se scrie nimic. Verifică:
   - fiecare coloană de preț e mapată? dacă nu — mapare manuală;
   - grupele arată ca numele foilor?
   - câte poziții noi vs existente?
5. **Sverka** (recomandat la fișiere mari): coloana `target_key` scrisă înapoi în Excel —
   se vede *înainte* de import ce se creează și ce se actualizează.
6. **Importă**. Se deschide o linie în `YBIRO_IMPORT_LOG`, se scriu marcajele de sursă în
   `TMS_MPT_IMPSRC`, se înregistrează grupele.
7. **Fișierele de grupe** — `gen_import_groups.py`, pentru evidență și anulare.

## 6. Rezultatul pe setul 12 (PRINTERRA)

| | |
|---|---|
| Produse importate | **5 147** |
| Grupe create | **98** (6 foi × categorii) |
| Cu cod de bare real din fișier | **5 147** (niciun EAN generat) |
| Prețuri verificate față de fișier | 5 147, **0 diferențe** |
| Diacritice stricate | 0 |

Repartiția pe foi:

| Foaie (grupă) | Categorii | Produse |
|---|---|---|
| Cartuse pentru imprimante | 16 | 1 887 |
| Accesorii si piese IMPRIMANTE | 31 | 1 682 |
| Imprimante | 13 | 612 |
| Cerneala pentru imprimante | 10 | 427 |
| Hirtie si baza pentru imprimare | 13 | 278 |
| Sublimare | 15 | 261 |

## 7. Detalii tehnice

`BIRO26PT_importData.import_file(..., p_algo => 'SHEET_AS_GROUP')` — algoritmul explicit
bate pe cel al sursei. Mai departe:

```sql
-- RO: rezerva pentru GRUPA e numele foii, nu grupa implicita
-- EN: the GRUPA fallback is the sheet name, not the default group
build_stg(p_load_id, p_grupa, p_sheet_group => TRUE);
```

Tabele implicate: `YBIRO_IMPORT_ALGO` (lista algoritmilor), `YBIRO_IMPORT_LOG` (jurnalul),
`YBIRO_IMPORT_GROUPS` (grupele per import), `TMS_MPT_IMPSRC` (marcajul de sursă).

Context complet: `GHID_IMPORT_ALTE_SCHEME.md` §9.28, `IMPORT_SURSE.md`.

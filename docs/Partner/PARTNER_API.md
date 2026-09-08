# Partner B2B API + integrarea Ultra

Modul izolat `modules/partner/` (nucleu: `core/module_loader.py`). Doua roluri:

1. **API pentru partenerii NOSTRI** — contract identic cu Ultra B2B API V1
   (`eshop.ultra.md/api-documentation`), ca un integrator care lucreaza deja
   cu Ultra sa se conecteze la officeplus.md schimbind doar base URL-ul si
   doua denumiri de cimpuri (`ultra_code`→`code`, `ultra_uuid`→`uuid`;
   alias-urile vechi sint acceptate in corpurile batch).
2. **Noi ca partener ULTRA** — clientul `modules/partner/ultra.py` aduce
   catalogul Ultra in ERP-ul una.md prin tamponul standard `BIRO26_GOODS`
   (SHEET='ULTRA'); publicarea ramine pe pipeline-ul de import al
   operatorului (validate → prepare → assign-keys).

## Adrese

| Ce | Unde |
|---|---|
| Documentatia publica (stil Ultra) | `https://officeplus.md/api-documentation` |
| Base URL public | `https://officeplus.md/api/v1` |
| Rutele reale Flask | `/UNA.md/orasldev/partner/api/...` (nginx face maparea) |
| Administrare (portal) | `/UNA.md/orasldev/partner/` |

## Obiecte Oracle (prefix PAPI_)

`PAPI_PARTNER` (conturi, legate de clientul ERP `TMS_UNIVERS.COD`),
`PAPI_TOKEN` (DOAR amprente SHA-256, access 1h / refresh 30 zile, rotatie),
`PAPI_LOG` (append-only: autentificari, comenzi, sincronizari Ultra).
Instalator PROPRIU: `python3 modules/partner/scripts/partner_deploy.py`
(instalatorul comun nu e atins). Instalat 28.08.2026, 9 obiecte VALID.

## Endpoint-uri

`POST /auth/token|refresh|revoke` · `GET /product` (+`/{id}`, `POST /batch`)
· `GET /category` · `GET /brand` · `GET /quantity` (+`POST /batch`) ·
`GET /changes?since&entity` (product/price/quantity, derivate din WEBATTR.
UPDATED_AT, TPR1D_PERPRLIST.DATASTART si diferenta instantaneelor de stoc) ·
`POST /order` (devine cont de plata REAL prin `Y_AI_BIRO26`; preturile DOAR
din coloana clientului; `validate_only:true` = verificare fara creare) ·
`GET /order` · `GET /health`. Limita: 120 cereri/min per partener.

## Integrarea Ultra (noi ca dealer)

Credentialele se introduc in pagina de administrare (YBIRO_SETTINGS:
`PARTNER_ULTRA_USER/_PASSWORD/_BASE`). Prima sincronizare = tot catalogul
(paginat 1000); urmatoarele = incremental prin `/api/changes` cu reperul
`PARTNER_ULTRA_SINCE`. Stub-urile "no image" se arunca (lectia impreso).
CLI/cron: `python3 modules/partner/scripts/ultra_sync.py [--full]`.
**Formatul REAL al API-ului Ultra difera de documentatia lor** (verificat
28.08.2026 cu contul de dealer): raspunsul la `/product` e o LISTA goala de
wrapper; `product_name` vine ca JSON-STRING (`'{"ro":...}'`), nu ca obiect;
preturile vin ca `{amount, currency: {code, name, rate}}` — `user_price`
(pretul de dealer) e in USD cu cursul zilei, `fixed_price` (retail) in MDL.
Clientul nostru normalizeaza totul la MDL (`amount * rate`) si accepta
ambele forme. Cont dealer: officeplussrl@gmail.com (parola in
YBIRO_SETTINGS.PARTNER_ULTRA_PASSWORD).

**Alte capcane ale API-ului lor, verificate pe viu (28–29.08.2026):**

| Ce zice documentatia | Ce face API-ul real | Ce facem noi |
|---|---|---|
| `sort=name_asc` e o optiune valida | raspunde **500 Server Error** | folosim `sort=updated_at`, cu revenire automata la "fara sortare" |
| paginare simpla `limit/offset` | fara sortare fixa **fereastra aluneca**: prima trecere = 38.706 rinduri cu doar **26.010 uuid-uri unice** (dubluri intre pagini, deci si goluri) | sortare fixa + deduplicare pe `ultra_uuid` in cadrul rularii |
| raspunsul e un obiect cu `data` | pentru `/product` e o **lista** direct | acceptam ambele forme |
| `product_name` e obiect multilingv | vine ca **JSON-STRING** | `_lang()` accepta si dict, si string |
| campurile de pret sint numere | sint `{amount, currency:{code,name,rate}}`, dealer in **USD** | `_money()` converteste in MDL dupa cursul din raspuns |

**Articolele Ultra sint numerice** (ex. `246019`), deci intra sub regula sursei
`ULTRA` din `TMS_ORG_IMPSRC` (`ART_PREFIX='ULT'`, `ART_MIN_LEN=6`): toate
primesc prefixul `ULT` inainte de a ajunge in tampon, ca sa nu se bata cap in
cap cu articolele altor furnizori.

## Verificare (28.08.2026, productie)

Token+refresh+revoke OK; 401 fara token / parola gresita; catalog cu preturi,
imagini, categorii; `/changes` OK; comanda reala **A-86** (doc 400, 20.159
lei) creata prin API si vizibila in `GET /order`; partener de test:
`apitest@officeplus.test` pe clientul "B2B Demo Client" (453040).

## Rulare locala si teste

`tests/test_partner.py` — doua teste de izolare + regulile pure (6 passed).
Modulul apare in `app.extensions["module_loader"]` la `loaded`.

---

## Puntea GOG <-> ULT (09.09.2026)

**Problema.** In iulie 2026 catalogul Ultra a fost incarcat din fisier
(`Set_data_import/7` si `/8`, `ULTRA.md (1).xlsx`). In coloana «Articol» acolo
statea codul NOSTRU intern `GOG*`, articolul furnizorului lipsea complet — asa
au aparut ~22 000 cartele nelegate de furnizor. Acum acelasi catalog vine prin
API cu articole `ULT*`, iar cheie comuna in baza NU exista:

| Cheie | Potriviri din 34 437 |
|---|---|
| uuid-ul lor -> `TMS_MPT_IMPSRC.SRC_PID` | 0 |
| `ULT*` -> `TMS_UNIVERS.CODVECHI` | 0 |
| denumire exacta | 252 |

Publicarea ca atare ar crea 34 437 cartele noi, dublind ~16 000 existente.

**Cheia** e in adresa imaginii — exista in ambele, doar gazda difera:

```
iulie : cdn.ultra.md/images/webp/products/<uuid>/images/26
API   : cdn-ultra.esempla.com/storage/webp/<uuid>.webp
```

Potrivire: **15 952** pozitii, toate cu cartela in nomenclator.
ATENTIE: uuid-ul PRODUSULUI (`BIRO26_GOODS.GUID`) nu merge — coincide doar in
1 704 cazuri. Cheia e a IMAGINII.

**Ordinea obligatorie de rulare:**

```bash
# 1. resincronizare cu diacriticele si grupa reparate
python3 modules/partner/scripts/ultra_sync.py --full

# 2. puntea — INAINTE de publicare, altfel se dubleaza 16 000 de cartele
python3 modules/partner/scripts/ultra_bridge.py            # analiza
python3 modules/partner/scripts/ultra_bridge.py --apply    # scrie legatura

# 3. publicarea prin conveierul obisnuit al operatorului
```

**Analiza din 09.09.2026** (34 437 rinduri in tampon):

| | |
|---|---|
| exista deja in nomenclator | 15 952 |
| produse noi | 18 485 |
| pretul creste | 1 845 |
| pretul scade | 2 140 |
| fara schimbare | 11 965 |

Preturile curente ale cartelelor `GOG*` sint din 20.07.2026 —
`VTPR1D_PERPRLIST.SC` = codul marfii (nu `CODPRICE`).

### De ce puntea e obligatorie: assign_keys nu cauta nimic

`YBIRO_Import_Marfa.assign_keys` **nu potriveste marfa cu nomenclatorul**. El
doar da un numar nou din secventa fiecarui rind fara cheie:

> `UPDATE BIRO26_GOODS SET COD_UNIVERS = <secventa>.NEXTVAL WHERE COD_UNIVERS IS NULL`

Deci orice rind care intra in conveier cu `COD_UNIVERS` gol devine o cartela
NOUA. Exact asa au aparut in iulie cele ~22 000 de cartele `GOG*`, si exact asa
s-ar dubla acum 15 952.

**Concluzie: puntea trebuie sa scrie `BIRO26_GOODS.COD_UNIVERS`** pentru cele
15 952 de pozitii INAINTE de `assign_keys`. Atunci `assign_keys` primeste doar
cele 18 485 de pozitii cu adevarat noi, iar cele existente isi actualizeaza
pretul si stocul prin `import_prices`.

Legatura in `TMS_MPT_IMPSRC` (SRC_PID / SRC_ARTICOL) ramine necesara separat —
pentru sincronizarile incrementale urmatoare prin `/api/changes`.

### Actualizarea automata a preturilor (de configurat)

Lantul, o data pe ora:

1. `ultra_sync.py` — incremental prin `/api/changes` (reperul
   `PARTNER_ULTRA_SINCE`), reimprospateaza `RETAIL1` / `ANGRO` / `STOC`;
2. `ultra_bridge.py --apply` — leaga pozitiile noi aparute intre timp;
3. `YBIRO_Import_Marfa.import_prices` — scrie preturile in lista.

Pasul 3 insereaza doar perioade care lipsesc (`NOT EXISTS ... datastart`), deci
rularea repetata e sigura.

**Stare la 09.09.2026: pasii 1–3 NU sint automatizati.** Codul pentru 1 si 2
exista si e testat in regim de analiza; scrierea in productie a fost blocata de
clasificatorul modului automat al agentului, iar drepturile nu si le poate
acorda singur — trebuie adaugate de proprietar in `.claude/settings.json`.

---

## Publicarea catalogului Ultra prin conveierul standard (09.09.2026)

`modules/partner/scripts/ultra_publish.py` — tamponul `BIRO26_GOODS`
(SHEET='ULTRA') → xlsx cu antet recunoscut de `detect_columns` → incarcatorul
standard `models/biro26pt_loader.py` → `BIRO26PT_importData.import_file(
p_src=>'ULTRA', p_algo=>'UNIVERSAL', p_mark_all_new=>FALSE)`.

Conveierul da singur: marcajul sursei (`TMS_MPT_IMPSRC`), jurnalul
`YBIRO_IMPORT_LOG`, plasarea in arbore dupa GRUPA/CATEGORIE, preturile cu
**perioada noua si inchiderea celei vechi** (vitrina citeste pretul cu
`:pd BETWEEN DATASTART AND DATAEND`), EAN-13 si „noutate" doar pentru pozitiile
noi. Fara `--commit` e DRY-RUN real: doar `classify`, nimic in productie.

**Puntea catre cartelele `GOG*` din iulie = codul de bare.** Cartela se
gaseste dupa uuid-ul imaginii (`TMS_MPT_TVR.IE_LINKADRES` ↔ `photo_url` din
API), iar in coloana `Barcode` se pune codul ei de bare unic `4841…`
(24 057 coduri, fiecare la exact o cartela activa). Prioritatea 1 din
`classify()` face restul. Scriptul nu contine logica proprie de potrivire.

Maparea antetului, verificata pe viu (load 326, test):
`Articol→ARTICOL, Barcode→BARCODE, Denumire→DENUMIRE, Grupa→GRUPA,
Categorie→CATEG, Brand→FURNIZOR, Angro→ANGRO, Retail→RETAIL, Image URL→URL`.

**Automat, o data pe ora:** `modules/partner/scripts/ultra_cron.sh`
(sync incremental → publish --commit, cu lock; jurnal `/tmp/ultra_cron.log`).

### Defectele sincronizarii reparate in aceeasi zi

| Defect | Efect | Reparatie |
|---|---|---|
| token de 1h, fara reautentificare | rularea completa murea la mijloc, **nimic scris** | re-login la 401/403 „token" + scriere in blocuri de 2 000 |
| `_lang(hierarchy[i])` in loc de `["name"]` | GRUPA goala la toate cele 34 437 | `element["name"]`; fara categorie → `Ultra - diverse` |
| text nefiltrat prin cp1251 | 6 813 denumiri cu `?` | `cp1251_safe()` pe tot textul |

### Rezultatul publicarii — 09.09.2026, load 326, `--commit`

| | |
|---|---|
| rinduri publicate | 37 373 |
| EXISTENTE (punte prin cod de bare) | **17 356**, din care cu pret schimbat **4 345** |
| NOI — cartele create, plasate in arbore, cu imagine si EAN-13 | **19 955** |
| AMBIGUE (nume deja pe o cartela activa — sarite) | 62 |
| perioade noi de pret | 24 221 |
| perioade anterioare inchise | 4 266 |
| grupe de pret noi | 12 |
| verificare pret | OK — toata marfa cu pret in fisier are pret in lista |

Cartela 304287 (Galaxy A27 Negru): 5 899 (20.07 → 08.09) → **6 599 din 09.09**.

Sincronizarea completa a adus 26 186 uuid-uri unice din 38 853 vazute —
paginarea Ultra dupa `updated_at` pierde pozitii cind ele se schimba in
timpul parcurgerii. Restul de 11 190 s-au adus adresat prin
`POST /product/batch` (`ultra_codes`), 3 nu mai exista la Ultra.

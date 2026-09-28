# Ghid de import date în alte scheme (playbook)

> Document de referință care adună **toată experiența acumulată** la importul BIRO26 →
> OfficePlus (Oracle). Scopul: să poți reproduce/adapta motorul de import la **altă
> schemă** (alt owner, altă bază, alt catalog de produse) fără să calci pe aceleași greșeli.
>
> Motor: pachetul PL/SQL `BIRO26PT_importData` + încărcătorul `biro26pt_loader.py`,
> care reutilizează pachetul de import `YBIRO_Import_Marfa`.

---

## 1. Principiul de bază (ce trebuie înțeles întâi)

1. **Cheia de potrivire e ARTICOLUL** (`CODVECHI`), nu numele. Numele produselor NU sunt
   unice în catalog (45% din catalogul OfficePlus are nume duplicate). Un fișier fără
   coloana articol **nu poate fi importat sigur** — potrivirea după nume dă ~83% ambiguu.
2. **Toată inteligența e în baza de date** (detecție + import în PL/SQL). Loader-ul Python
   e „prost" — doar toarnă celulele într-un stagin brut, fără interpretare.
3. **Dry-run implicit.** Nimic nu se scrie în producție fără `p_commit=TRUE`.
4. **Fără ștergeri.** Prețurile merg pe perioade (istoric), codurile de bare se adaugă,
   produsele doar se creează. Deduplicarea/ștergerile sunt operațiuni separate, deliberate.

---

## 2. Arhitectura în 2 straturi

```
Fișiere (xlsx/xls/csv, sau .zip) cu structură necunoscută
        │
   [Loader Python]  biro26pt_loader.py — fără interpretare
        ▼
   Stagin BRUT:  BIRO26PT_RAW (c0..c15) + BIRO26PT_HEADER + BIRO26PT_FILE
        │
   [PL/SQL BIRO26PT_importData]
        ├─ detect_columns  → BIRO26PT_MAP  (câmp logic → cNN, 3 strategii)
        ├─ build_stg       → BIRO26PT_STG  (proiecție „goods")
        ├─ classify        → status NEW/EXISTING/AMBIGUOUS/NOARTICOL
        └─ do_writes (p_commit=TRUE) → reutilizează YBIRO_Import_Marfa:
             import_univers, import_mpt, import_groups/dates + preț (nu-cobori),
             marcaj MATGR1, plasare în arbore (ensure_group), generare EAN-13
```

**De ce 2 straturi:** PL/SQL nu citește xlsx. Loader-ul generic acoperă orice fișier viitor;
detecția și importul rămân în DB (o singură logică, testabilă, auditabilă).

---

## 3. Obiectele necesare (și care sunt specifice schemei)

### 3.1 Obiecte proprii motorului (se creează la fel în orice schemă)

| Obiect | Rol |
|---|---|
| `BIRO26PT_RAW (load_id, src_file, sheet, row_no, c0..c15)` | celule brute, tot text |
| `BIRO26PT_HEADER (load_id, src_file, col_idx, header_text)` | rândul de antet |
| `BIRO26PT_FILE (load_id, src_file, sheet, n_rows, n_cols, loaded_at)` | registru încărcări |
| `BIRO26PT_COLMAP (pattern, logical_field, prio)` | dicționar sinonime antet |
| `BIRO26PT_LAYOUT (sig_name, col_idx, logical_field)` | scheme poziționale cunoscute |
| `BIRO26PT_MAP (load_id, logical_field, col_idx, strategy, confidence)` | rezultat detecție |
| `BIRO26PT_STG (...)` | proiecția „goods" + status |
| `BIRO26PT_LOG (...)` + `BIRO26PT_LOG_SEQ` | jurnal detecție/import |
| `BIRO26PT_EAN_SEQ` | corpul secvențial pentru EAN-13 |

### 3.2 Obiecte ale schemei-țintă (de identificat/mapat în schema nouă)

| În OfficePlus | Rol | La adaptare, găsește echivalentul |
|---|---|---|
| `TMS_UNIVERS` (COD, CODVECHI, DENUMIREA, TIP, GR1, UM, CACCESS, CODTVA, ISARHIV) | dicționarul de produse | tabela-catalog + cheia stabilă |
| `ID_TMS_UNIVERS` (sequence) | generatorul de `COD` | secvența de chei noi |
| `TMS_MPT` (COD, MATGR1, DEP_PRODUCER) | cartela produsului | tabela-cartelă; `MATGR1` = flag „produse noi" |
| `TMS_MPT_BARCODE` (COD, BARCODE, COMENT) | coduri de bare | tabela de coduri |
| `TMS_MPT_WEBATTR` (COD, DESCRIERE_*/BLOB + copii text) | atribute web multilingve (descriere) | tabelă-satelit proprie, vezi §3.4 |
| `VPR01M_GROUPS` / `VPR1D_PRDATE` / `VTPR1D_PERPRLIST`(view) → `TPR1D_PERPRLIST`(bază) | lista de prețuri | grupuri → perioade → prețuri |
| `TRG_VTPR1D_PERPRLIST_M_ALL` | trigger INSTEAD OF pe view-ul de preț | ⚠️ vezi §9.3 (bug NLS) |
| `TMS_SYSGR` / `TMS_SYSGRPH` / `TMS_SYSGRP` | arborele de marfă (rădăcini / noduri / plasări) | arborele de categorii |
| `TR_TMS_SYSGRP_B` | trigger pe plasare (interzice UPDATE la câmpuri-cheie) | ⚠️ vezi §9.4 |

### 3.4 Modelul „master + sateliți" (cum se leagă tabelele)

Toate tabelele de marfă se leagă de **master-tabelul `TMS_UNIVERS`** prin aceeași cheie:
coloana `COD`. Sateliții folosesc `COD` **și ca PK, și ca FK** (relație 1:1), iar tabelele
de tip listă (coduri de bare) au `COD` doar ca FK (1:N).

```
TMS_UNIVERS  (master · COD = cheia stabilă a mărfii · TIP='P')
   │
   ├─ TMS_MPT          COD PK/FK   1:1   cartela (MATGR1, DEP_PRODUCER)
   ├─ TMS_MPT_TVR      COD PK/FK   1:1   imagine (IE_LINKADRES), dimensiuni
   ├─ TMS_MPT_WEBATTR  COD PK/FK   1:1   descriere web + denumire completă   ← adăugată
   ├─ TMS_MPT_BARCODE  COD FK      1:N   coduri de bare
   ├─ TPR1D_PERPRLIST  SC  FK      1:N   perioade de preț
   ├─ TMS_SYSGRP       SC  FK      1:N   plasarea în arbore
   └─ BIRO26_GOODS     COD_UNIVERS 1:1   feed-ul care alimentează arborele + magazinul
```

**Regula pentru un satelit nou** (ex. `TMS_MPT_WEBATTR`): se copiază schema de cheie de la
`TMS_MPT` — `COD NUMBER NOT NULL`, `PRIMARY KEY (COD)`, `FOREIGN KEY (COD) REFERENCES
TMS_UNIVERS (COD)`. Așa moștenește integritatea (nu pot exista atribute fără marfă) și se
alătură direct oricărei interogări prin `JOIN ... ON x.cod = u.cod`.

`TMS_MPT_WEBATTR` — **multilingv (RO/RU/EN), cu originalul in BLOB**:

| Coloana | Tip | Cine scrie | Rol |
|---|---|---|---|
| `COD` | NUMBER, PK+FK | import | = `TMS_UNIVERS.COD` |
| `DESCRIERE_RO/RU/EN` | **BLOB** | **se editeaza** | ORIGINALUL (octeti UTF-8) — pastreaza diacriticele |
| `DENUMIRE_FULL_BLOB_RO/RU/EN` | **BLOB** | **se editeaza** | ORIGINALUL denumirii complete |
| `DESCRIERE_NON_DIACR_RO/RU/EN` | CLOB | **trigger** | copie fara diacritice — cautare / index vectorial |
| `DENUMIRE_FULL_RO/RU/EN` | VARCHAR2(4000) | **trigger** | dublura fara diacritice — cautare / index |
| `SRC`, `LOAD_ID`, `UPDATED_AT` | | import | trasabilitate |

**De ce BLOB.** Baza e `CL8MSWIN1251` (un octet): orice text scris intr-o coloana TEXT
pierde diacriticele (`ș` -> `?`). Un **BLOB pastreaza octetii asa cum sint**, deci textul
original supravietuieste indiferent de charset-ul bazei — problema e rezolvata la radacina,
nu prin transliterare.

**Regula de aur:** se editeaza **doar** coloanele BLOB. Copiile de cautare le completeaza
**automat** triggerul `TMS_MPT_WEBATTR_BIU` (nu le scrieti manual). Astfel:
- afisarea in magazin foloseste BLOB-ul -> diacritice corecte;
- cautarea/indexarea folosesc copiile text -> rapide si insensibile la diacritice
  („carti" gaseste „cărți").

**Cum se face conversia** (pachetul `YBIRO_TEXT_UTIL`): `BLOB (UTF-8) -> NCLOB` prin
`DBMS_LOB.CONVERTTOCLOB(..., 873, ...)`. Charset-ul national e `AL16UTF16` (Unicode complet),
deci diacriticele supravietuiesc; abia apoi se transliterreaza (`TRANSLATE` 1:1 +
`REPLACE` pentru `²`->`2`, `½`->`1/2`) si rezultatul ASCII coboara in charset-ul bazei.

**Stagin pentru original:** `BIRO26PT_RAW_BLOB (load_id, row_no, col_idx, val_blob)` —
loader-ul scrie octetii originali **doar** pentru celulele unde transliterarea a schimbat
ceva (volum mic: 45 509 celule la set 8). Importul ia originalul de acolo; daca celula
n-avea caractere speciale, textul din STG **este** originalul.

DDL: `TMS_MPT_WEBATTR.tab.sql`.

### 3.3 Variabile de configurare (în pachete — de rescris per schemă)

`YBIRO_Import_Marfa` (șapca pachetului):
```
g_tbl_goods='BIRO26_GOODS'  g_col_key='COD_UNIVERS'  g_col_articol='ARTICOL'
g_col_denumire='DENUMIRE'   g_col_group='GRUPA'      g_col_id='ID'
g_col_angro='ANGRO'  g_col_ionline='IONLINE'  g_col_retail='RETAIL1'
g_um='buc.'  g_gr1='TVR'  g_tip='P'  g_caccess='11100'  g_codtva='A'
g_len_codvechi=20  g_len_denumire=160  g_codprice=1
g_mpt_col_prod='DEP_PRODUCER'
```
`BIRO26PT_importData`:
```
g_tip='P'  g_len_codvechi=20  g_len_denumire=160  g_max_cols=16
g_sample_rows=80  g_min_anchor=3  g_default_grupa='IMPORT PT'  g_codprice=1
g_new_matgr=1  g_new_group='PRODUSE NOI'  g_ean_prefix='20'
```

---

## 4. Regulile fișierelor

- **Formate:** `.xlsx`, `.xls`, `.csv` (separator `;` sau `,` — detectat automat). Se poate
  încărca un grup de fișiere sau o arhivă `.zip`.
- **Primul rând = antet.** Datele încep din rândul 2. Foile/rândurile goale se ignoră.
- **Obligatoriu: coloana ARTICOL** (`Articol` / `Артикул` / `SKU` / `Cod produs`).
- **Recomandat:** DENUMIRE + cel puțin un preț (RETAIL).
- **Opțional:** BARCODE, VAT, categorie (GRUPA), URL imagine.
- Coloanele nerecunoscute se ignoră fără eroare.

---

## 5. Detecția coloanelor (3 strategii)

Rezultat: `BIRO26PT_MAP` = `câmp logic → cNN`. Câmpuri: `ARTICOL, DENUMIRE, BARCODE,
ANGRO, ONLINE, RETAIL, VAT` (+ `URL/IGNORE` neutilizate).

1. **După numele coloanei** (prioritar): `LOWER(header) LIKE pattern` din `BIRO26PT_COLMAP`
   (sinonime RO/RU/EN; `prio` mic câștigă). Dublă reducție: fiecare coloană ia un singur
   câmp, apoi fiecare câmp o singură coloană.
2. **După ordinea cunoscută** (`BIRO26PT_LAYOUT`): scheme poziționale (ex. fișiere de coduri
   `[1]=BARCODE,[2]=ARTICOL,[3]=DENUMIRE`). Se aplică dacă antetul nu s-a recunoscut.
3. **După conținut / produs cunoscut**: eșantion de rânduri; potrivire cu `CODVECHI`→ARTICOL,
   cu `DENUMIREA`→DENUMIRE (ancoră), regex `^\d{8,14}$`→BARCODE, numeric→prețuri
   (angro<online≤retail după mediană).

Prioritate: **antet → conținut → layout**. Fiecare decizie e jurnalizată în `BIRO26PT_LOG`.
Dacă lipsesc și ARTICOL, și DENUMIRE → fișier „nerecunoscut", sărit.

**Dicționarul de sinonime** se completează ușor (INSERT în `BIRO26PT_COLMAP`) — pentru
fiecare furnizor nou, adaugi anteturile lui o dată și apoi se recunosc automat.

---

## 6. Operațiunile de import (do_writes, doar la p_commit=TRUE)

1. **Poziții noi** → `COD` din secvență → `import_univers` (TMS_UNIVERS) + `import_mpt` (cartelă).
2. **Prețuri — regula „nu coborî"** → perioadă nouă (datastart = data încărcării sau `p_date`)
   **doar dacă prețul din fișier e strict mai mare** decât cel curent; altfel se păstrează cel
   curent. Perioada anterioară se închide (`DATAEND = start_nou − 1`, regula `LEAD(datastart)−1`).
3. **Marcaj „produse noi" = `MATGR1=1`** (filtru virtual, vizibil în `VMS_MPT`). `p_mark_all_new`:
   toate rândurile vs doar pozițiile noi.
4. **Plasare în arbore** — în **nodurile REALE** după `GRUPA` (`ensure_group` caută nodul după
   nume pe orice nivel; creează nod nou doar dacă numele nu există deloc). „PRODUSE NOI" e
   **virtual** (doar `MATGR1`), NU un nod fizic.
5. **Generare EAN-13** pentru pozițiile noi fără cod (prefix `20` + secvență + cifră de control).
   Dacă fișierul are coloană de coduri → se importă acelea.
6. **Atribute web** (`DESCRIERE`, `DENUM_FULL`) → `TMS_MPT_WEBATTR` prin `MERGE` pe `COD`.
   Regulă: **`NULL` nu șterge** valoarea existentă (`NVL(u.nou, t.vechi)`) — un fișier parțial
   (fără coloana descriere) nu pierde descrierile deja importate din alt fișier.

---

## 7. Fluxul de rulare

```bash
# 1) Încărcare (shell) — grup de fișiere sau o mapă:
export DYLD_LIBRARY_PATH=/Users/pt/Downloads/instantclient_23_26
python3 biro26pt_loader.py /cale/catre/mapa
```
```sql
SET SERVEROUTPUT ON
-- 2) Analiză (dry-run) — nimic nu se scrie:
BEGIN BIRO26PT_importData.import_file(p_load_id=>N, p_grupa=>'...', p_commit=>FALSE); END;
/
-- 3) Import real:
BEGIN BIRO26PT_importData.import_file(
        p_load_id=>N, p_grupa=>'...', p_codprice=>1,
        p_commit=>TRUE, p_mark_all_new=>TRUE, p_date=>NULL); END;
/
```

---

## 8. Verificări utile (după import)

```sql
-- integritate: fără suprapuneri de perioade pentru produsele importate
WITH aff AS (SELECT DISTINCT cod_univers sc FROM biro26pt_stg WHERE load_id=:N AND cod_univers IS NOT NULL)
SELECT COUNT(*) overlaps FROM (
  SELECT p.dataend, LEAD(p.datastart) OVER (PARTITION BY p.codprice,p.sc ORDER BY p.datastart) nxt
  FROM aff a JOIN tpr1d_perprlist p ON p.codprice=1 AND p.sc=a.sc
) WHERE nxt IS NOT NULL AND dataend >= nxt;               -- trebuie 0

-- produse noi complete: cod + cartelă + cod de bare
SELECT COUNT(*) FROM biro26pt_stg s WHERE load_id=:N AND status='NEW'
  AND NOT EXISTS (SELECT 1 FROM tms_mpt_barcode b WHERE b.cod=s.cod_univers);  -- 0

-- filtru „produse noi"
SELECT * FROM vms_mpt WHERE matgr1=1;
```

---

## 9. Capcane și lecții (PARTEA CEA MAI VALOROASĂ)

### 9.1 Charset-ul bazei: `CL8MSWIN1251` (nu UTF-8)
Baza OfficePlus e single-byte chirilic. **Datele/dicționarele cu chirilică se încarcă doar
prin `python-oracledb`** (convertește Unicode→win1251 corect). Inserarea chirilicei prin
SQLcl/heredoc **strică octeții** și `LIKE` nu mai potrivește (ne-a stricat detecția o dată).
Verifică: `SELECT value FROM nls_database_parameters WHERE parameter='NLS_CHARACTERSET';`

### 9.2 Locala `en_MD` → `ORA-12705` la login
Clientul thick pică la conectare din cauza localei. Remedii:
- SQLcl/JVM: `JAVA_TOOL_OPTIONS="-Duser.language=en -Duser.country=US"`.
- `python-oracledb` în mod **thin** — evită complet problema.

### 9.3 `ORA-01843: not a valid month` la scrierea prețului ⚠️ CLASIC
Triggerul `TRG_VTPR1D_PERPRLIST_M_ALL` face `NVL(:NEW.DATAEND,'31.12.3000')` — un **literal
text convertit implicit în dată** după `NLS_DATE_FORMAT`. `NVL` evaluează mereu ambele
argumente, deci conversia se face indiferent de valoare. Sesiunile cu format **lună-nume**
(`DD-MON-…`, tipic aplicații web) → „12 nu e lună" → ORA-01843. Merge din SQLcl (NLS englez),
pică din web.
- **Remediu în pachet:** `EXECUTE IMMEDIATE 'ALTER SESSION SET NLS_DATE_FORMAT=''DD.MM.YYYY'''`
  la începutul scrierii (deja pus în `do_writes`).
- **Remediu de fond (recomandat):** în trigger, `'31.12.3000'` → `DATE '3000-12-31'`
  (independent de NLS) — imunizează orice cod care scrie prețuri.

### 9.4 Triggere protective pe tabelele de bază (nu poți face UPDATE/DELETE naiv)
- `TMS_UNIVERS`: 3 triggere blochează ștergerea (`TMS_UNIVERS_DONT_DELETE`,
  `_DONT_DELETE_2022`, `TMH_UNIVERS_TRG`) + `UN$UNIVCONTROL` (referințe). Ștergerea reală
  cere dezactivarea lor temporară + curățarea referințelor (vezi `BIRO26_DEDUP.md`).
- `TMS_MPT_TRLOCK`: dacă e ENABLED, blochează UPDATE pe cartele. La noi era DISABLED.
- `TR_TMS_SYSGRP_B` (arbore): **interzice UPDATE la câmpurile-cheie** și calculează singur
  `ID1/ID2` din coloanele group. Ca să **muți** un produs în alt nod → **DELETE + INSERT**
  într-o singură tranzacție, nu UPDATE.

### 9.5 Modelul prețurilor pe perioade
`DATAEND` e stocat **în rândul de preț** (`TPR1D_PERPRLIST`), iar `VTPR1D_PERPRLIST` e un
view cu trigger INSTEAD OF. La un preț nou trebuie **închisă perioada precedentă**
(`DATAEND = start_nou − 1`) — altfel două perioade deschise se suprapun (bug reparat: 279
produse). Regula corectă: `DATAEND = LEAD(datastart) − 1` per `(codprice, sc)`; ultima rămâne
deschisă (`01.01.3000`).

### 9.6 „Produse noi" = atribut virtual, nu nod de arbore
Nu crea un nod fizic „PRODUSE NOI". Produsele noi intră în **nodurile lor reale** (după GRUPA);
„noutatea" e doar `MATGR1=1` (filtrul din magazin/backoffice). O corecție ne-a costat mutarea
a 523 produse dintr-un nod fizic greșit în nodurile reale.

### 9.7 Fișier fără categorie → totul aterizează într-un nod
Dacă fișierul n-are coloană de categorie și pui o `GRUPA` implicită, **toate** produsele intră
într-un singur nod (posibil greșit pentru un catalog divers). Soluție: cere o coloană de
categorie, sau plasează într-un nod neutru și folosește filtrul `MATGR1`.

### 9.8 Duplicate de nume în catalog
Catalogul are multe produse cu același nume (variante distinse prin articol). De aceea
potrivirea după nume e nesigură. Importuri repetate cu scheme de articol diferite **creează
duplicate**. Ai `Y_AI_BIRO26.dup_*` pentru dedup exact `(CODVECHI+DENUMIREA)` — dar NU prinde
duplicatele cu articole diferite.

### 9.9 Particularități SQLcl / versiune DB
- `FETCH FIRST n ROWS ONLY` a dat `ORA-00933` — folosește `WHERE ROWNUM<=n` (înfășurat).
- `GENERATED … AS IDENTITY` și `DEFAULT sequence.NEXTVAL` la CREATE TABLE au picat — folosește
  o secvență + NEXTVAL în INSERT.
- Cuvinte rezervate ca alias: **`ONLINE`, `RETAIL`** → `ORA-00923`. Folosește `pretv2 AS online_v`.
- Potrivirea după nume cu subquery corelat pe `UPPER(TRIM(DENUMIREA))` e **foarte lentă**
  (full scan/rând) → folosește un **hash join** cu agregare, nu subquery corelat.
- O funcție privată din body **nu poate fi apelată în SQL** (`PLS-00231`) — calculează în
  variabilă PL/SQL, apoi INSERT.

### 9.10 `ORA-01400` la codurile de bare (coloană parțial goală)
Dacă fișierul are coloană de cod de bare dar **nu toate rândurile au valoare**, inserarea
naivă încearcă `BARCODE = NULL` → `ORA-01400`. Reguli corecte:
1. Inserează codurile din fișier **doar unde `barcode IS NOT NULL`**, potrivite univoc după
   articol, protejate de duplicate și de unicitatea globală (`TMS_BARCODE_UNIQ`).
2. **Ordinea contează:** întâi codurile din fișier, apoi generează EAN-13 **doar** pentru
   pozițiile noi rămase fără niciun cod. (Ordinea inversă generează EAN + cod din fișier =
   coduri duble.)

### 9.11 `ORA-12899` — numele grupului de preț (max 25)
`GRUPA` e folosită și ca nume de grup de preț `TPR01M_GROUPS.GRPNAME` (**max 25 caractere**).
Categorii mai lungi (ex. „Accesorii pentru telefoane" = 26, „Ceasuri și brățări inteligente"
= 30) → `ORA-12899`. Remediu: **trunchiază `GRUPA` la 25** în `build_stg` (o folosesc și
nodul de arbore, și grupul de preț). Verifică limita reală a coloanei în schema ta.

### 9.12 Fișiere cu mai multe foi (sheets)
Un `.xlsx` poate avea **multe foi**, fiecare o categorie (ex. catalog electronic: 17 foi).
Loader-ul încarcă **fiecare foaie ca `load_id` separat**. La import, pasează **numele foii
drept `p_grupa`** → plasare corectă pe categorii, fără „totul într-un nod".

### 9.31 Setul 14 (atehno, 22 000 produse IT): patru straturi de aparare, patru defecte

Cel mai mare set de pina acum (22 397 randuri + 42 675 imagini) si primul catalog IT.
Continutul tehnic a lovit patru limite noi, una dupa alta — fiecare oprire a scos alt strat:

| # | Defect | Cauza | Corectia |
|---|---|---|---|
| 1 | `ORA-12899` la `TMS_MPT_WEBATTR.SRC` | nume de fisier > 60 caractere | trunchiere la 60 |
| 2 | `ORA-21560` in `YBIRO_TEXT_UTIL` | **emoji** in descrieri: LENGTH pe NVARCHAR2 (perechi surogat) nu corespunde bufferului convertit la cp1251 | conversia la charset-ul bazei INAINTE de `WRITEAPPEND`, lungimea masurata pe rezultat |
| 3 | `ORA-20077` de la garda de diacritice | **URL in denumire** — `?` din query string parea diacritica stricata | garda de URL in trigger (ca in algoritmul 5 de reparare) |
| 4 | `ORA-20000` de la triggerul nativ CK_BANK | **tolii** din numele IT (`27"`) si ghilimele in numele brandurilor — `"` e interzis in `TMS_UNIVERS` | sanitizare in STAGIN: `"` -> `''` la denumire SI la furnizor |

Sanitizarea ghilimelelor se face la nivel de **stagin** (build_stg), nu la insert: asa
potrivirile pe nume (paza 4) ramin consistente intre fisier si catalog — altfel fiecare
produs cu toli in nume ar fi devenit dublura la reimport.

**Nota de reluare:** un import intrerupt lasa pasii dinainte de eroare COMISI. La reluare
marfa e deja EXISTENTA, deci pasii doar-pentru-NOI (plasare in arbore, EAN) nu se repeta —
la atehno nu a durut (codurile de bare vin din fisier, plasarea se facuse), dar verificati
mereu ce a ramas nefacut (vezi si 9.30c, bestbuy).

#### Rezultat

| | |
|---|---|
| Produse | **21 732** (toate cu cod de bare REAL din fisier) |
| Preturi verificate fata de fisier | 21 746, **0 diferente**; verificarea automata: OK |
| Atribute web (descrieri) | 17 501 |
| Galerie | 16 645 imagini pentru 4 091 produse |
| Grupe | **122**, in rusa, 3 niveluri (`Компьютеры` 12 956, `Строительство` 4 029...) |
| Articole slabe prefixate | 14 953 (`ATH-`/brand) |
| Diacritice stricate | 0 |

Prima sursa de scraping cu coduri de bare complete — paza anti-dubluri a trecut fara
`p_force`, iar potrivirile viitoare se vor face intii pe cod de bare, cheia cea mai sigura.

### 9.30 Setul 13 (bestbuy): patru defecte gasite intr-un singur import

Fisier de scraping obisnuit — 8 655 de randuri, 29 de coloane, grupe in rusa — dar a scos
la iveala patru probleme deodata. Toate erau acolo de mult; abia dimensiunea fisierului
le-a facut vizibile.

#### a) Analiza rula 25 de minute fara sa se termine

Pazele din `classify()` compara `UPPER(TRIM(denumirea))` si articolul normalizat pentru
FIECARE rand. Fara indecsi pe aceste **expresii**, fiecare rand scaneaza integral
`TMS_UNIVERS` (~460 000). La 8 655 de randuri devine imposibil.

```sql
CREATE INDEX TMS_UNIVERS_UP_DENUMIREA  ON tms_univers (UPPER(TRIM(denumirea)));
CREATE INDEX TMS_UNIVERS_NORM_CODVECHI ON tms_univers
       (REPLACE(REPLACE(UPPER(codvechi),' ',''),'.',''));
```

Creati in sub o secunda fiecare. Rezultat: **25+ minute -> sub un minut**.

> Daca o paza compara o EXPRESIE, are nevoie de index pe exact acea expresie. Altfel merge
> la fisiere mici si cedeaza exact cind ai nevoie de ea.

#### b) Paza anti-dubluri testa "zero" in loc de o proportie

Fisierul avea **26 de coduri de bare din 8 655** (0,3%) — practic niciunul. Paza a tacut,
fiindca testa `v_bc_filled = 0`. Un singur rand completat dintr-o mie o dezarma.
Acum pragul e proportional: `g_min_bc_ratio` (implicit 5%).

#### c) Cod de bare duplicat IN ACELASI fisier oprea tot importul

`ORA-20000` de la triggerul nativ `TMS_MPT_BARCODE$TR$UNIQ_BAR`, la jumatatea importului:
marfa creata, codurile si preturile nu. Paza existenta verifica doar codurile deja aflate
in catalog — nu si pe cele repetate in interiorul lotului. Intr-un `INSERT ... SELECT`
randurile se vad intre ele: al doilea rand cu acelasi cod il loveste pe primul.

Rezolvat cu `ROW_NUMBER() OVER (PARTITION BY barcode)` plus verificare si in
`TMS_MPT_BARCODE`, nu doar in `TMS_BARCODE_UNIQ`.

> **Consecinta operationala:** un import oprit la jumatate lasa marfa creata dar nefinalizata.
> La reluare ea e deja EXISTENTA, deci pasii pentru marfa NOUA (generarea EAN-13) se sar.
> Dupa orice import intrerupt, verificati explicit ce a ramas nefacut.

#### d) Entitati HTML in denumiri si in numele grupelor

`Tablets &amp; Phones`, `children&#8217;s camera`, `USB &#8212; (16GB)` — exporturile de
site pastreaza entitatile din pagina. Decodarea a fost adaugata in loader **inainte** de
transliterare, ca rezultatul sa treaca apoi prin cp1251. Ordinea conteaza: decodate dupa
transliterare, ele raman gresite pentru totdeauna. Reparate retroactiv 178 de randuri.

#### Rezultatul importului

| | |
|---|---|
| Produse | **7 384** |
| Cu pret in lista de preturi | **7 384** (verificare automata: OK) |
| Preturi verificate fata de fisier | 0 diferente |
| Imagini de galerie | 5 832 |
| Grupe | 78, in rusa (chirilica trece intacta prin cp1251) |
| Diacritice stricate | 0 |
| Randuri sarite (fara articol) | 1 269 |

### 9.29 Grupa mai lunga de 25 de caractere = pret pierdut (defect vechi, sistemic)

Gasit la verificarea setului 12, dar vechi de multe importuri. Din 5 147 de produse
PRINTERRA, doar 2 760 aveau pret. Tiparul a iesit imediat:

| Grupa | Lungimea numelui | Pret |
|---|---|---|
| `Imprimante` (10), `Sublimare` (9), `Cartuse pentru imprimante` (**25**) | ≤ 25 | ✅ |
| `Cerneala pentru imprimante` (26), `Hirtie si baza pentru imprimare` (31), `Accesorii si piese IMPRIMANTE` (29) | > 25 | ❌ |

#### Cauza

`VPR01M_GROUPS.GRPNAME` are maxim 25 de caractere, de aceea stagin-ul are doua coloane:
`GRUPA` (numele complet, pina la 60) si `GRUPA_PRET` (trunchiat la 25). Grupele de pret se
creeaza din `GRUPA_PRET` — corect. Dar inserarea preturilor se lega pe numele **complet**:

```sql
-- gresit: s.grupa are pina la 60 de caractere, grpname are 25
JOIN vpr01m_groups vg ON vg.codprice = p_codprice AND vg.grpname = s.grupa
```

Cind numele incape in 25, cele doua coincid si totul merge. Peste 25, JOIN-ul nu gaseste
nimic, `INSERT ... SELECT` insereaza zero randuri — **fara eroare**. Corectat: `= s.grupa_pret`.

#### Cit a costat

Corelatia e perfecta, deci nu e coincidenta:

| Grupe | Marfuri | Cu pret |
|---|---|---|
| ≤ 25 caractere | 118 460 | 117 134 (99%) |
| **> 25 caractere** | 6 197 | **3 033 (49%)** |

**3 164 de produse** stateau in magazin cu pret in feed (`BIRO26_GOODS.RETAIL1`) dar fara
niciun rind in lista de preturi. Afectate: `Arta, creativitate si jocuri` (2 107),
`Rechizite scoala si gradinita` (761), `Ceai, cafea, vesela, pungi` (296) — toate
officeshop, plus cele 2 387 de la PRINTERRA.

Reparat prin insertie directa, cu legatura pe numele trunchiat. Dupa reparatie: **6 197 din
6 197**, adica 100%.

#### Restul de 1 326: alte doua cauze, gasite prin aceeasi verificare

Dupa corectarea JOIN-ului au mai ramas 1 326 de marfuri cu pret in feed dar fara pret in
lista. Nu era acelasi defect — erau doua, mai vechi:

**a) Virgula zecimala in feed (474).** `parse_price` intelege doar punctul, iar in
`BIRO26_GOODS.RETAIL1` se strinsesera valori ca `10,00`, `1.169,00`, `2,071.00` — trei
formate diferite, din surse diferite. Normalizate dupa regula **ultimul separator e cel
zecimal** (operatia pastreaza valoarea, doar formatul devine citibil):

| Din feed | Devine | De ce |
|---|---|---|
| `10,00` | `10.00` | virgula = zecimala |
| `1.169,00` | `1169.00` | european: punctul e separator de mii |
| `2,071.00` | `2071.00` | anglo-saxon: virgula e separator de mii |

25 457 de valori normalizate; zero ambiguitati (toate cele cu virgula aveau exact doua
zecimale, deci niciuna nu putea fi separator de mii).

**b) Grupa de pret inexistenta (302).** Marfa era intr-o grupa (`Carti de colorat`) pentru
care nu se crease niciodata un rind in `VPR01M_GROUPS`, deci n-avea unde sa fie pretul.
Create 5 grupe lipsa si perioadele lor.

Restul (550) aveau si grupa, si pret citibil — ramasite din importuri vechi, dinaintea
logicii actuale. Recuperate la fel.

**Rezultat final: 124 657 din 124 657** de marfuri active cu pret in feed au acum si un
rind valabil in lista de preturi. Zero exceptii.

> **Atentie, chestiune separata:** la ~3% din marfa, pretul din feed difera de cel din lista
> (perioade vechi, din iulie: feed 59.85 vs lista 12.35). Nu e cauzat de reparatie — ea a
> scris doar acolo unde nu exista niciun pret. Ramine de decis care dintre cele doua e cel
> corect.

#### De ce n-a fost prins mai devreme

Verificam mereu preturile comparind `BIRO26PT_STG` cu `BIRO26_GOODS` — si acolo totul era
corect, pentru ca feed-ul se scrie separat de lista de preturi. Nimeni nu compara **lista de
preturi** cu feed-ul.

> **Verificare noua, obligatorie dupa orice import:** cite din marfurile importate au un rind
> **in lista de preturi** (`TPR1D_PERPRLIST` cu `DATAEND >= SYSDATE`), nu doar un pret in
> `BIRO26_GOODS`. Diferenta dintre cele doua e exact locul unde se ascund defectele de acest
> tip.

```sql
-- RO: marfa importata fara pret in vigoare / EN: imported goods with no active price
SELECT COUNT(*) FROM biro26_goods g
 WHERE g.retail1 IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM tpr1d_perprlist p
                    WHERE p.sc = g.cod_univers AND p.dataend >= TRUNC(SYSDATE));
```

### 9.28 Foile = grupe, algoritm selectabil, mapare manuala care nu se pierde

Setul 12 (PRINTERRA) a cerut trei lucruri care lipseau: marfa pe **6 foi = 6 grupe**,
o **lista de algoritmi** in loc de un singur comportament implicit, si **maparea manuala**
a coloanelor — pentru ca fisierul avea antetul stricat.

#### Antet suprascris cu valori: esecul cel mai tacut de pina acum

Pe **4 din 6 foi**, cineva suprascrisese antetul coloanelor de pret cu valori din primul rand:

| Foaie | Coloanele 12–13 |
|---|---|
| Imprimante | `Price Online`, `Розничная цена с НДС` ✅ |
| Cerneala | `Price Online`, `Розничная цена с НДС` ✅ |
| Hirtie si baza | `43,50`, `43.5` ❌ |
| Cartuse | `109,50`, `109.5` ❌ |
| Sublimare | `189,00`, `189` ❌ |
| Accesorii si piese | `526,50`, `526.5` ❌ |

Detectarea automata nu gaseste coloana, importul **reuseste**, iar **4 108 din 5 147** de
produse ar fi intrat fara niciun pret. Nimic nu semnaleaza asta: nu e eroare, e absenta.

#### Defect gasit: maparea manuala se stergea singura

Interfata avea de mult un tabel de mapare manuala, dar era **inutilizabil**:
`detect_columns` incepea cu `DELETE FROM biro26pt_map WHERE load_id = ...` — fara conditie.
Orice reanaliza arunca ce corectase omul, iar analiza se reface la fiecare import.

Corectat: se sterg doar mapările automate, iar detectarea nu mai calca peste cimpurile sau
coloanele fixate manual.

```sql
-- RO: maparea MANUALA a operatorului se PASTREAZA
DELETE FROM biro26pt_map WHERE load_id = p_load_id AND NVL(strategy,'?') <> 'MANUAL';
```

In raport se vede exact ce a corectat omul:

```
c10 -> ANGRO     [HEADER]  "Цена закупки с НДС"
c11 -> ONLINE    [MANUAL]  "43,50"
c12 -> RETAIL    [MANUAL]  "43.5"
```

#### Algoritmii ca lista, nu ca implicit

`YBIRO_IMPORT_ALGO` — lista selectabila in back-office, extensibila fara cod. Fiecare
algoritm isi **declara** comportamentul (`SHEET_GROUP`, `CREATES_GOODS`, `NEEDS_MAP`), iar
interfata explica operatorului ce urmeaza sa se intimple **inainte** sa apese.

| Cod | Ce face |
|---|---|
| `UNIVERSAL` | detectare automata (implicit) |
| `SHEET_AS_GROUP` | numele foii devine GRUPA |
| `MANUAL_MAP` | cere maparea manuala a coloanelor |
| `PRICES_ONLY` / `IMAGES` / `BARCODES` | actualizari tintite, fara creare de marfa |

Precedenta: algoritmul ales explicit > cel al sursei (`TMS_ORG_IMPSRC.ALGO_CODE`) > `UNIVERSAL`.

#### Foaia ca grupa

In `build_stg`, rezerva pentru `GRUPA` devine numele foii in loc de grupa implicita —
dar **coloana `GRUPA` din fisier ramine prioritara**, deci algoritmul nu strica un fisier
corect. Atentie la legaturi: cu `p_sheet_group`, `:grp`/`:grpp` nu mai apar in SQL-ul
dinamic, deci `EXECUTE IMMEDIATE` leaga doar `load_id`.

Rezultat pe setul 12: **5 147 produse**, **98 grupe** (6 foi x categorii), toate cu cod de
bare **real** din fisier (niciun EAN generat), preturi verificate fata de fisier —
**0 diferente**, 0 diacritice stricate.

> **De verificat la orice fisier cu mai multe foi:** deschideti antetul **fiecarei** foi,
> nu doar al primei. Foile arata identic la prima vedere si difera exact acolo unde doare.

### 9.27 Sursa fara HTTPS: imaginile se importa, dar nu se vad

La impreso.md imaginile pareau "neimportate". Nu erau: toate cele 2 662 de URL-uri erau
in baza si corecte. Problema e alta si nu se vede din baza:

```
200  image/jpeg  47 693 octeti   <-  http://www.impreso.md/product/5634/image-1B.jpg
000  conexiune esuata            <-  https://www.impreso.md/product/5634/image-1B.jpg
```

Site-ul **nu are HTTPS deloc** — nu e o eroare de certificat, nu asculta nimic pe 443.
Magazinul ruleaza pe https, iar browserul refuza continut mixt: `<img src="http://...">`
pe o pagina https nu se incarca. In baza totul arata corect; doar in browser lipseste poza.

**Solutia: proxy, nu rescrierea URL-urilor.** `models/biro26_imgproxy.py` + ruta
`/api/biro26/img?u=<url>`: serverul aduce imaginea prin http si o serveste pe https.
Rescrierea se face central, in store, deci sablonul nu se atinge.

Un proxy care descarca orice URL primit e o **gaura SSRF** — ar putea fi folosit ca sa
ceara adrese interne prin serverul nostru. De aceea:

| Aparare | De ce |
|---|---|
| lista alba de gazde | doar impreso.md; restul nici nu intra in proxy |
| fara urmarirea redirectarilor | o redirectare ar putea scoate cererea din lista |
| doar raspunsuri `image/*` | nu servim HTML sau JSON de pe alt server |
| limita de 8 MB | o poza de produs e sub 1 MB |

Verificat: `http://evil.example.com/x.jpg` si `http://127.0.0.1:8080/admin` sint respinse.

#### Capcana alaturata: stub-ul "fara imagine"

319 produse aveau ca poza `img/product/noimage_b.jpg` — stub-ul site-ului, un JPEG **real**
de 57 KB. Importul l-a luat ca imagine valida, deci produsele pareau ca au poza. E mai rau
decit lipsa imaginii: interfata nu mai stie ca poza lipseste. Sters (`NULL`).

> **De verificat la orice sursa noua:** (1) imaginile se servesc pe https? (2) exista un
> URL-stub pentru "fara imagine" care se repeta la sute de produse? Amindoua se vad
> imediat: `curl -o /dev/null -w "%{http_code} %{content_type} %{size_download}"` pe
> citeva URL-uri, si un `GROUP BY` pe URL ca sa iasa la iveala cel repetat.

### 9.26 Import REGLEMENTAT: sursa marcata, grupe urmarite, anulare pregatita

Setul impreso.md e primul importat dupa **regulamentul complet** — nu ca exceptie, ci ca
procedura standard. Cinci pasi, in ordine:

1. **Inregistreaza sursa** in `TMS_ORG_IMPSRC` (aici: `IMPRESO`, prefix `IMP`), cu
   capcanele fisierului scrise in `NOTES`.
2. **Sverka inainte de import** (§9.25): `target_key` scris inapoi in Excel. A aratat
   dinainte ca 2 645 din 2 662 de rinduri sint marfa noua si doar 17 se suprapun — deci
   nu era un import de preturi, ci de catalog.
3. **Deschide jurnalul** (`YBIRO_IMPORT_LOG`), importa, **inchide-l** cu contoarele reale.
4. **Marcheaza fiecare cartela** in `TMS_MPT_IMPSRC`: sursa, rularea, `SRC_PID`
   (`product_id` de pe site) — cheia pentru reincarcari idempotente.
5. **Inregistreaza grupele** in `YBIRO_IMPORT_GROUPS` si exporta-le ca fisiere.

#### Grupele ca fisiere: de unde a aparut si cum o scot

Grupele intrau tacut: un fisier nou aducea zeci de categorii si peste o luna nimeni nu mai
stia care de unde a venit, nici ce se strica daca le scoti. Acum fiecare import produce
doua fisiere in `grupe_import/`:

| Fisier | Ce contine |
|---|---|
| `<SURSA>_<import_id>_<data>.csv` | fiecare grupa, cele 3 niveluri, `CREATED`/`EXISTING`, cite marfuri a pus **acest import** si cite are grupa **acum** |
| `<SURSA>_<import_id>_<data>.rollback.sql` | scriptul de anulare, **integral comentat** |

Distinctia `CREATED` / `EXISTING` e cea care conteaza: impreso a adus **24 de grupe, toate
noi**; officeshop-consolidat a adus 256, **niciuna noua** (existau din importurile
anterioare ale aceleiasi surse). Prima situatie e reversibila, a doua nu — nu poti sterge
o grupa pe care o folosesc si alte importuri.

Scriptul de anulare e comentat linie cu linie **intentionat**: il citesti, te uiti in CSV
cite marfuri atirna ACUM de fiecare grupa, si decomentezi doar ce vrei sa anulezi. Ordinea
lui: arhiveaza marfa (nu o sterge) -> scoate grupele ramase goale -> curata nodurile de
arbore fara marfa -> sterge marcajele si evidenta.

Generare (oricind, si retroactiv): `python3 scripts/gen_import_groups.py --all`.

#### Reincarcarea aceleiasi surse

`SRC_PID` face reimportul idempotent: aceeasi marfa de pe site se regaseste dupa ID-ul ei,
nu dupa nume sau articol. Verificare: 2 662 de rinduri IMPRESO -> 2 662 de `SRC_PID` unice.

> **De acum, orice sursa noua trece prin cei cinci pasi.** Costa zece minute in plus si
> raspunde la intrebarile care pina acum n-aveau raspuns: de unde a venit cartela asta,
> ce a adus rularea de marti, si cum dau inapoi.

### 9.25 Fisierul CU PASAPORT: regulile impuse de furnizorul de date

Setul `officeshop_prices_retail+angro.xlsx` a venit cu un **pasaport** scris pentru
importator (`README-for-AI.md`): provenienta, structura celor 4 foi si un **regulament
obligatoriu**. E primul fisier care spune singur cum trebuie importat, si a schimbat
regulile jocului.

#### Ce a confirmat pasaportul

Doua lucruri pe care le descoperisem pe cont propriu, cu pret:

- coloana `price` din API-ul angro e **dublul lui `price_opt`, nu pretul de raft** —
  exact capcana din §9.24, gasita dupa ce comparasem 1 369 de preturi;
- **site-ul nu publica coduri de bare nicaieri** — de aceea paza `g_max_new_nobc` se
  declanseaza mereu la aceasta sursa; nu are rost sa cerem coduri, nu exista.

Si unul nou, care ne-ar fi costat: **articolul din scraping-ul de retail e euristic**
(extras din coada denumirii, ~95% exact). Doar articolul din API-ul angro e exact.

#### Cele patru reguli, si cum le-am implementat

| Regula (pasaport) | Implementare |
|---|---|
| §3.1 jurnal de importuri | `YBIRO_IMPORT_LOG` — o linie per rulare, cu contoare |
| §3.2 sverka **inainte** de import | coloana `target_key` scrisa in Excel |
| §3.3 marcaj de sursa pe fiecare cartela | `TMS_MPT_IMPSRC` (satelit 1:1) |
| §3.4 nu amesteca sursele | potrivire in cadrul sursei; intre surse doar cod de bare **sau** brand+articol exact |

**Sverka pre-import (§3.2) e cea mai valoroasa idee din pasaport.** Inainte de a scrie
ceva, calculezi pentru fiecare rind daca marfa exista deja si scrii raspunsul **inapoi in
Excel**: `target_key` completat = UPDATE, gol = INSERT. Fisierul devine un act de sverka pe
care un om il poate verifica **cu ochii, inainte** de import. La setul acesta a aratat
imediat esentialul: din 7 268 de rinduri, **6 469 existau deja** — deci nu era un import de
marfa noua, ci o **actualizare de preturi**. Fara sverka am fi rulat orbeste.

#### Grupele: 3 niveluri intr-un arbore de 2

Sursa are `group1..group3` (1 197 de rinduri folosesc al treilea nivel), dar arborele din
back-office citeste `BIRO26_GOODS` cu doua coloane (GRUPA + CATEGORIE). Calea completa se
pastreaza in doua locuri, ca sa nu se piarda:

- `TMS_MPT_IMPSRC.SRC_GROUP_PATH` — sursa de adevar, pentru orice reconstructie;
- `BIRO26_GOODS.PRODUCT_TYPE` — cimpul standard Google feed pentru calea de categorii
  (`Rechizite de birou > Pixuri si mine > Pix ulei si semi-gel`), deci merge si in feed.

Cind echipa web va vrea arbore pe 3 niveluri, datele sint deja acolo.

#### Imaginile: preferati versiunea fara filigran

Scraping-ul de retail da URL-uri `images_1c_watermark`, API-ul angro da `images_1c` —
acelasi fisier, fara filigran (`id_1c` = numele fisierului, faptul §1.4 din pasaport).
Am inlocuit filigranul **doar** unde stim ca versiunea curata exista, adica la marfa cu
`match_status IN ('both','angro_only')`: 2 553 de imagini principale si 412 din galerie.
Cele 835 ramase sint `retail_only` — acolo versiunea curata chiar nu exista.

> **Ce sa ceri de acum de la orice furnizor de date:** un pasaport ca acesta. Zece minute
> de citit au inlocuit doua zile de arheologie si un incident.

### 9.24 Export B2B: o coloana numita „retail" care nu e pretul de raft

Setul officeshop-angro (`all_products angro 1-217.xlsx`, 5 413 randuri x 20 coloane) aduce
`price_angro_mdl` — pretul de achizitie care lipsea. Dar are si o coloana `price_retail`
care **pare** pretul de vinzare si nu este:

| Articol | price_angro_mdl | price_retail | pretul nostru |
|---|---|---|---|
| `PF025/16` | 90.86 | **90.86** | 80.10 |
| `MX61947` | 41.28 | **41.28** | 36.90 |
| `1897/1559` | 53.17 | 75.96 | 66.47 |

La multe randuri `price_retail` e **identica** cu pretul angro, iar in **1 348 din 1 369**
comparatii pretul nostru era mai mare. Este pretul de baza din zona B2B, nu cel de raft.

Importat ca `RETAIL`, ar fi pus produsele noi la vinzare **la pretul de achizitie**. Pe cele
existente regula „nu coborim pretul" le-ar fi protejat — deci paguba ar fi fost invizibila
la o verificare superficiala si vizibila abia in marja.

Coloana e mapata pe `IGNORE`; din acest fisier se ia **doar** `price_angro_mdl -> ANGRO`.
Sursa e inregistrata separat ca `OFFICESHOP_B2B` (tip `B2B`), cu capcana scrisa in `NOTES`.

> **Regula:** la un fisier de la un portal B2B, nu va increti in numele coloanei de pret.
> Comparati-o cu pretul curent pe citeva sute de randuri: daca al nostru e sistematic mai
> mare, coloana nu e pretul de raft.

#### Cit de mult a ajutat prefixarea (§9.23)

Acelasi furnizor, aceeasi lipsa de coduri de bare, dar cu prefixarea activa:

| | officeshop (fara prefix) | officeshop-angro (cu prefix) |
|---|---|---|
| Potriviri cu **nume complet diferit** | **643** din 1 162 | **21** din 2 810 |
| Reparatie necesara | 629 de cartele | niciuna |

Cele 21 ramase s-au dovedit, la verificare manuala, **potriviri corecte** — acelasi produs
scris altfel („Plic patrat Daco Invitas" vs „Plic 140x140mm/120gr patrat (Albastru)").
Similaritatea de text e o masura slaba cind cuvintele sint reordonate: foloseste-o ca semnal
de **triere**, nu ca verdict.

### 9.23 Prefixul de articol si registrul surselor de import

Solutia de fond la §9.22: in loc sa **respingem** articolele slabe, le facem **unice**.

**Prefixul**, ales in ordinea: BRAND-ul randului -> `ART_PREFIX`-ul sursei -> nimic
(atunci paza 5 opreste randul).

| In fisier | Brand | Devine |
|---|---|---|
| `2080` | Trefl | `TREFL-2080` |
| `59895` | Spree | `SPREE-59895` |
| `1841` | (lipsa) | `OS-1841` |

Prefixarea ruleaza in `apply_article_prefix()`, **intre `build_stg` si `classify`** — daca
ar rula dupa, potrivirea s-ar face tot pe codul scurt si am avea aceleasi potriviri false.

#### Registrul surselor: TMS_ORG_IMPSRC / TMS_ORG_IMPFILE

Fiecare sursa de date isi are acum cartela ei, legata de furnizor:

```
TMS_UNIVERS (TIP='O') -> TMS_ORG -> TMS_ORG_IMPSRC -> TMS_ORG_IMPFILE
```

`TMS_ORG_IMPSRC` tine tipul sursei (`SCRAPING` / `EMAIL` / `B2B` / `MANUAL`), algoritmul
de incarcare, prefixul de articol, pragul `ART_MIN_LEN` si — cel mai util — **capcanele
fisierului** in `NOTES`. `TMS_ORG_IMPFILE` pastreaza fisierul original ca BLOB, cu amprenta
SHA-256, legatura cu stagin-ul si raportul importului.

Sursa se alege in back-office (`import_pt.html`, selectorul "Sursa / algoritm") si ajunge
la pachet ca `p_src`. Fara sursa, importul merge ca inainte — generic, fara prefix.

Documentatia generata din tabela: `IMPORT_SURSE.md` + `IMPORT_SURSE.csv`
(regenerare: `python3 scripts/gen_import_surse.py`).

> **De ce conteaza:** numele fisierului NU identifica sursa — birovits si officeshop trimit
> amindoua un fisier numit `all_products 2.xlsx`. Sursa trebuie aleasa explicit.

#### Corectia retroactiva

Cele **3 139** de produse deja create cu articol slab (1 673 birovits + 1 466 officeshop)
au primit prefixul lor in `TMS_UNIVERS.CODVECHI` si `BIRO26_GOODS.ARTICOL`. Produsele mai
vechi din catalog **nu** au fost atinse: articolele lor circula de ani in documente.
Delimitarea s-a facut dupa `COD > 453493` (reperul obtinut prin flashback).

### 9.22 Articolul scurt/numeric NU e cheie — incidentul officeshop (load 285)

Cel mai costisitor incident de pina acum, si primul in care **potrivirea a fost gresita,
nu lipsa**. Exportul officeshop are multe articole scurte, pur numerice (`248`, `670`,
`1841`, `2917`). Astfel de coduri inseamna **produse diferite la fiecare furnizor**:

| Fisier officeshop | S-a potrivit cu (catalog) |
|---|---|
| Whiteboard magnetic Basy 120x180 | Hartie pentru tehnica de birou A3 |
| Joc de masa „Octopus Party" Trefl | Carnet A6 40 foi cu spirala |
| Husa pentru stampila R40 | Mine pentru creion mecanic Koh-I-Noor |
| Carte de colorat „Dinozauri" | Set de semne Meshu Meow Paw |

Din 1 162 de potriviri „existente": 163 bune, 356 indoielnice, **643 cu nume complet
diferit**. Aproape toate aveau articol de 3–5 caractere.

**Ce a ajuns in productie** pe 629 de cartele nelegate: 389 de perioade de pret, 458 de
imagini principale, 185 de imagini de galerie, plus **denumirea si articolul suprascrise**
in `BIRO26_GOODS` (adica in ce vede clientul in magazin).

#### De ce nu l-au prins pazele existente

Pazele acopereau alte forme ale aceleiasi probleme:
- §9.19 prioritatea 3 — articol **reformatat** (`T4gr120 12476` vs `T4gr12012476`);
- §9.21 paza 4 — articol **inlocuit** (nume identic, articol nou).

Aici e cazul invers: **articolul coincide, dar produsul e altul**. Nicio verificare nu se
uita la nume atunci cind articolul se potrivea exact.

#### Paza 5: articol prea slab ca sa fie cheie

```sql
LENGTH(TRIM(articol)) < g_min_articol_len   -- implicit 6
OR REGEXP_LIKE(TRIM(articol), '^[0-9]+$')   -- pur numeric
```
Randul nu se potriveste **si** nu se creeaza — devine `AMBIGUOUS`. Pragul e o constanta
(`g_min_articol_len`), deci se poate ajusta per schema.

Efect pe setul officeshop: 4 075 pozitii „noi" + 1 162 „existente" -> **2 391 sarite**.

#### Reparatia — flashback, nu ghicit

`BIRO26_GOODS` a fost readus **exact** la starea de dinainte, prin
`AS OF TIMESTAMP (SYSTIMESTAMP - INTERVAL '12' HOUR)`: 468 de randuri inserate gresit
sterse, 182 restaurate. Preturile: cele 389 de perioade de azi sterse, 102 perioade
anterioare redeschise (`DATAEND` inapoi la `01.01.3000` — marcajul de perioada deschisa).

> **Lectie:** inainte de orice import mare, verificati **distributia lungimii articolului**
> in fisier. Daca o parte insemnata are sub 6 caractere sau e numerica, cheia nu e sigura —
> cereti codul de bare sau articolul complet al furnizorului.

### 9.21 Fisiere LARGI (export de site): 3 capcane tacute — set 11

Setul 11 (`all_products`, export de pe birovits.md) e primul fisier care nu vine de la un
furnizor, ci de pe un site: **12 423 rinduri x 25 de coloane**. A scos la iveala trei
limite pe care nu le atinsese niciun fisier de pina acum. Toate esueaza **tacut**.

**a) Limita de 16 coloane.** `BIRO26PT_RAW` avea `c0..c15`, iar loader-ul `MAXCOL = 16`.
Fisierul are 25 de coloane, deci `image_main` (c22) si `description` (c24) **cadeau in afara
stagin-ului** — importul ar fi "reusit", fara imagini si fara descrieri, fara nicio eroare.
Stagin-ul e acum `c0..c31` (`g_max_cols = 32`, `MAXCOL = 32`); DDL:
`BIRO26PT_set11_25col.sql`.

**b) Rindul de antet nu e mereu primul.** Exportul pune pe rindul 1 un titlu
(`all_products`, restul celulelor goale), iar antetul real e pe rindul 2. Loader-ul lua
orbeste `rows[0]`, deci antetul devenea `all_products` + 24 de `NULL` -> **nicio coloana
detectata**. Regula noua: antetul e **primul rind (din primele 5) cu cel putin 3 celule
completate**; datele incep dupa el.

**c) Un antet nemapat nu e neutru.** Exportul are coloane care seamana cu altele:
`product_url` si `images_all` s-ar fi luat drept `URL` in locul lui `image_main`;
`category_path` (un slug: `akciya/goryacie-predlozeniya`) s-ar fi luat drept `CATEG` in
locul lui `group2`. Toate coloanele de zgomot sint acum **explicit `IGNORE`** — o intrare
`IGNORE` intentionata e documentatie, absenta ei e o loterie.

#### Paza 4 in `classify()`: nume identic = AMBIGUU, nu NOU

Cind un rind "nou" are un **nume identic** cu o cartela ACTIVA, furnizorul a schimbat de
fapt articolul (`DLEH379` in loc de `DLEH378`, `DLE38144-BL` in loc de `DLE5001-03`), iar
crearea rindului ar produce o dublura perfecta pe nume. Nu se poate decide automat care
cartela e cea buna, deci rindul devine `AMBIGUOUS` si se sare.

La setul 11: **3 417 -> 3 365** pozitii noi, adica 52 de dubluri evitate.

> Aceasta paza completeaza prioritatea 3 din §9.19 (articol normalizat): acolo prindem
> reformatarea articolului, aici prindem **inlocuirea** lui.

### 9.20 ANGRO = pret de achizitie **CU TVA** (nu fara)

Confirmat de client (10.08.2026): in OfficePlus **ANGRO se tine CU TVA**. Dictionarul
`BIRO26PT_COLMAP` trata `Цена закупки с НДС` ca `IGNORE` — deci la fisierele care au DOAR
coloana cu TVA (cazul CRAFTI, set 10) pretul de achizitie **nu se importa deloc**, tacut.

Maparea corecta (prioritate mica = cistiga):

| Antet | Cimp | Prio |
|---|---|---|
| `%цена закупки с ндс%` | `ANGRO` | 5 |
| `%закупки с ндс%` | `ANGRO` | 6 |
| `%angro%` | `ANGRO` | 10 |
| `%опт%` | `ANGRO` | 20 |
| `%закупки без ндс%` / `%цена закупки без%` | `ANGRO` | **30** (rezerva) |

Varianta fara TVA ramine, dar **retrogradata**: daca fisierul are ambele coloane cistiga
cea **cu TVA**; daca are doar varianta fara TVA, tot se importa ceva in loc de nimic.

> **Lectie generala:** o intrare `IGNORE` in dictionar e la fel de periculoasa ca o mapare
> gresita — nu produce nicio eroare, doar o coloana lipsa in rezultat. La un fisier nou,
> comparati lista coloanelor din antet cu `BIRO26PT_MAP`: fiecare coloana de pret NEmapata
> trebuie sa fie o decizie constienta, nu o scapare.

### 9.19 Formatul datelor din fisier: virgula zecimala si articol "reformatat"

Doua capcane descoperite la setul 10 (CRAFTI) — ambele **tacute**: importul „reuseste",
dar nu face ce trebuie.

**a) Virgula zecimala.** `YBIRO_Import_Marfa.parse_price` intelege DOAR punctul:
`parse_price('224.93') = 224.93`, dar `parse_price('69,66') = NULL`. Pretul de raft e
pastrat ca TEXT si parsat mai tirziu, deci un fisier cu virgula duce la **0 preturi
actualizate**, fara nicio eroare. La setul 10 asta ar fi blocat ~6 600 actualizari.
Normalizare in `build_stg` (doar daca nu exista deja punct — poate fi separator de mii):

```sql
CASE WHEN INSTR(col, '.') = 0 THEN REPLACE(col, ',', '.') ELSE col END
```

**b) Articol „reformatat" de furnizor.** Acelasi produs, alt format al articolului:
fisier `T4gr120 12476` vs catalog `T4gr12012476` (un spatiu in plus). Potrivirea exacta
esueaza -> produsul devine NOU -> **dublura**. La setul 10: **277** dubluri evitate.
Solutie — PRIORITATE 3 in `classify()`, dupa barcode si articol exact:

```sql
REPLACE(REPLACE(UPPER(u.codvechi),' ',''),'.','')
  = REPLACE(REPLACE(UPPER(s.articol),' ',''),'.','')
```
Se aplica DOAR cind potrivirea normalizata e **unica** si cardul e activ.

**c) Paza pe coduri de bare — verificati DATELE, nu antetul.** Un fisier poate avea coloana
`Barcode` complet **goala**; e la fel de periculos ca lipsa ei. Paza `g_max_new_nobc`
numara acum randurile cu barcode completat, nu prezenta coloanei.

> **Regula generala:** dupa dry-run comparati `preturi cu pret schimbat` (din clasificare)
> cu `preturi noi inserate` (din import). Daca al doilea e mult mai mic — pretul nu s-a
> parsat (format) sau grupa de pret lipseste.

### 9.18 ⛔ Un import trebuie sa vada DOAR incarcarea lui (stagin cumulativ)

`BIRO26PT_STG` / `BIRO26PT_RAW` sint **cumulative** — pastreaza randurile tuturor
incarcarilor. Iar `YBIRO_Import_Marfa.import_univers` citeste **toata tabela** pe care e
configurat (`g_tbl_goods`), **fara filtru pe `load_id`**:

```sql
SELECT g.cod_univers, ... FROM BIRO26PT_STG g          -- toata tabela!
 WHERE g.cod_univers IS NOT NULL AND g.denumire IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM tms_univers t WHERE t.cod = g.cod_univers)
```

**Efect real:** la importul set 9 stagin-ul avea **204 incarcari / 616 210 randuri**, din
care **73 146** ar fi fost inserate desi apartineau ALTOR fisiere. Importul a picat cu
`ORA-20077` pe un text stricat dintr-un feed complet diferit (RADOP), desi fisierul curent
era curat.

**Regula:** legati pachetul reutilizat la un **view filtrat pe incarcarea curenta**:

```sql
FUNCTION cur_load RETURN NUMBER;                       -- in pachet, intoarce g_cur_load

CREATE OR REPLACE VIEW BIRO26PT_STG_CUR AS
  SELECT * FROM biro26pt_stg WHERE load_id = BIRO26PT_importData.cur_load;
```
```plsql
g_cur_load := p_load_id;
YBIRO_Import_Marfa.g_tbl_goods := 'BIRO26PT_STG_CUR';
```

**Regula-sora (ORA-02291):** randurile **fara denumire** nu primesc `COD` — `import_univers`
le sare oricum (numele e obligatoriu), iar pasii urmatori ar refera un produs inexistent.
In plus, inserarea in arbore verifica explicit `EXISTS (SELECT 1 FROM tms_univers ...)`.

**Intretinere:** stergeti periodic stagin-ul vechi, altfel creste la nesfirsit:
```sql
DELETE FROM biro26pt_stg WHERE load_id IN (
  SELECT load_id FROM biro26pt_file WHERE loaded_at < SYSDATE - 30);
```

### 9.17 ⛔ Prefixe in articol ("SKU:", "Articol:", "Cod:") = dubluri

Fisierele furnizorilor pun uneori eticheta in celula: `SKU: CM600`, `Articol: 1035A`.
Daca prefixul ajunge in `CODVECHI`, potrivirea nu mai gaseste produsul existent (`CM600`)
si se creeaza un **card-dublura**, fara cod de bare. Efect real: **5 113 dubluri** arhivate.

**Prevenire (in `build_stg`)** — prefixul se taie inainte de potrivire:
```sql
SUBSTR(TRIM(REGEXP_REPLACE(<col_articol>,
  '^(SKU|Articol|Article|Cod|Code|Art)[[:space:]]*:[[:space:]]*', '', 1, 1, 'i')), 1, 60)
```
Testat: `SKU: CM600` -> `CM600` -> status **EXISTING** (nu mai creeaza dublura).

**Curatarea celor existente** (facuta): dublurile cu prefix care aveau un ORIGINAL ACTIV
(potrivire dupa articolul curatat sau dupa denumire) au fost **arhivate** (`ISARHIV='2'`);
cele **fara** original (produse unice cu articol murdar) au primit doar articolul curatat —
nu se arhiveaza, altfel s-ar pierde marfa. Jurnal reversibil: `YBIRO_PREFIX_DEDUP`
(`DUP_COD`, `DUP_ARTICOL`, `CLEAN_ARTICOL`, `ORIG_COD`, `MATCH_BY`, `ACTION`).

**Arhivarea nativa** cere doua conditii (altfel triggerele o blocheaza):
```sql
SET_ENV('param_userid', '<user din grupa UNIVERS/DEL/ALLOW>');
SET_ENV('DOC_CHANGE_ISARHIV', '1');
UPDATE tms_univers SET isarhiv='2' WHERE cod = :cod;
```

### 9.16 ⛔ Fișier FĂRĂ coloană de cod de bare = fabrică de dubluri (incidentul GOG)

**Ce s-a întâmplat.** Un fișier de 37 717 rânduri (load 164) a fost importat **fără coloana
BARCODE**. Potrivirea mergea doar după `ARTICOL` → cardurile vechi n-aveau articol
(`CODVECHI IS NULL`) → **toate rândurile au devenit NEW** → ~37,7k carduri-dublură cu articol
`GOG*` și cod de bare intern generat `2000000…`. Mai rău: încărcările **următoare**, care
aveau coduri de bare reale, se potriveau tot după articol și „se lipeau" de dublură.

**Regula.** Codul de bare real e **cheia primară de potrivire**, articolul — a doua:

```sql
-- PRIORITATE 1: barcode real, un singur card ACTIV
UPDATE biro26pt_stg s SET s.status='EXISTING',
       s.cod_univers = (SELECT MIN(b.cod) FROM tms_mpt_barcode b
                        JOIN tms_univers u ON u.cod=b.cod AND u.tip='P'
                        WHERE b.barcode=s.barcode AND NVL(u.isarhiv,'0')<>'2')
 WHERE s.load_id=:l AND s.barcode IS NOT NULL AND (...COUNT(DISTINCT b.cod)...) = 1;
-- PRIORITATE 2: după articol, doar rândurile nepotrivite mai sus
```

**Pază în pachet** (`g_max_new_nobc`, implicit 200): dacă fișierul **nu are** coloană de cod
de bare **și** ar crea mai mult de 200 de poziții NOI, `import_file` se **oprește** cu mesaj
explicit. Se poate forța conștient: `p_force => TRUE`. Testat: 300 poziții fără barcode →
import oprit; cu `p_force` → trece.

**Alte reguli deduse din incident:**
- **Nu emiteți serii noi de articole** pentru marfă care există deja — după deduplicare
  articolele `GOG*` stau pe cardurile ORIGINALE; folosiți-le pe acelea.
- Codurile interne `2000000…` (prefix EAN „2" = uz intern) **nu sunt** coduri de producător —
  nu le trimiteți în fișiere noi ca EAN reale.
- **Cardurile arhivate** (`ISARHIV='2'`) sînt excluse din potrivire (și după barcode, și după
  articol) — nu se mai scrie în dubluri. Lista: `SELECT dup_cod FROM YBIRO_GOG_DEDUP`.
- Curățarea e **reversibilă**: `YBIRO_GOG_DEDUP` păstrează 37 697 perechi
  `DUP_COD → ORIG_COD` cu articol și barcode.

### 9.13 ⚠️ Arborele „Grupe de marfă" se citește din `BIRO26_GOODS`, NU din arborele nativ
Back-office-ul (biro26-backoffice) construiește panoul „Grupe de marfă" / navigarea magazinului
**exclusiv din tabelul-feed `BIRO26_GOODS`** (coloanele text `GRUPA` + `CATEGORIE`, join
`TMS_UNIVERS TIP='P'`, `ISARHIV≠2`, dedupe pe `COD_UNIVERS`). **NU** citește
`TMS_SYSGR/SYSGRPH/SYSGRP`. Deci un produs importat direct în `TMS_UNIVERS` (fără rând în
`BIRO26_GOODS`) **nu apare** în arbore/magazin, oricât de corect ar fi în arborele nativ.
→ Importul **trebuie să scrie în `BIRO26_GOODS`** (`cod_univers`, `grupa`, `categorie`,
`furnizor`, `denumire`, prețuri). Producătorul afișat = `BIRO26_GOODS.FURNIZOR` (și opțional
`TMS_MPT.DEP_PRODUCER` → org `TIP='O', GR1='E'`). Nota: `GRUPA` e și nume de grup de preț
(max 25) — ține grupa plină pentru `BIRO26_GOODS`, dar trunchiază la 25 pentru prețuri
(coloana `GRUPA_PRET`, vezi §9.11).

### 9.15 ⚠️ Actualizarea `BIRO26_GOODS` „pe lângă pachet" NU actualizează lista de prețuri
Prețul afișat în grilă/magazin vine din **lista de prețuri** (`TPR1D_PERPRLIST`), nu din
`BIRO26_GOODS`. Dacă corectezi doar `BIRO26_GOODS` (ex. un sync ad-hoc), grila rămâne cu
prețul vechi → apare „retail = angro" sau valori vechi. Reguli:
- Preferă **întotdeauna** re-importul prin pachet (`do_writes` scrie ȘI `BIRO26_GOODS`, ȘI lista de prețuri).
- Corecție punctuală a listei din `BIRO26_GOODS` (set-based, rapid):
  `MERGE INTO tpr1d_perprlist ... USING (SELECT cod_univers, parse_price(retail1) pv, angro pv1, ionline pv2 FROM biro26_goods WHERE furnizor=... GROUP BY cod_univers) ON (codprice=1 AND sc=cod AND dataend=DATE '3000-01-01') WHEN MATCHED THEN UPDATE SET pretv=pv, pretv1=pv1, pretv2=pv2`.
- **Articolele ambigue** (un articol → mai multe produse) sunt sărite la import → prețul lor
  rămâne vechi; se rezolvă prin dedup, nu prin re-import.

### 9.14 ⚠️ Text stricat („?") — charset CL8MSWIN1251 (NU doar diacritice românești)
Baza e chirilică (win1251): **orice** caracter care nu încape în cp1251 se stochează ca `?` —
nu doar `ă â î ș ț`, ci și semne tipografice: `×` (22×10×32 → `22?10?32`), `²` (g/m² → `g/m?`),
`‑` non-breaking hyphen (Wi‑Fi → `Wi?Fi`), `′ ″ – — ½ ﬁ œ ß …`.

**Remediu în cod (obligatoriu în TOATE loaderele):** funcția `cp1251_safe()` —
tabel de transliterare (RO + semne tipografice) + fallback `unicodedata.NFKD` (scoate semnele
de pe orice literă), aplicată la **celule, numele foii** (devine GRUPA) **și numele fișierului**.
Chirilica rămâne neatinsă. ⚠️ Trebuie reparate **ambele** loadere: cel local
(`biro26pt_loader.py`) ȘI cel al aplicației web (`models/biro26pt_loader.py` din Artgranit) —
importul din GUI folosește copia lui, deci corectarea doar a unuia lasă bug-ul activ.

**Repararea datelor deja stricate** (3 valuri, în ordine, fiecare cu dry-run întâi):
1. **Din fișierele sursă** — pentru fiecare text din xlsx/csv se calculează varianta „stricată"
   (roundtrip cp1251) și cea corectă; potrivire exactă cu valorile din BD.
2. **Potrivire prin mască** — `?` = orice caracter, comparat cu textele deja CURATE (din fișiere
   și din BD). Se aplică doar când potrivirea e **unică**.
3. **La nivel de cuvânt** — corpus de cuvinte curate; „car?i" → „carti" dacă un candidat domină.

⚠️ **Regula de aur:** tratează drept stricat **doar `?` încadrat de litere/cifre pe ambele
părți**. Un `?` la final de cuvânt/frază e semn de întrebare real („Кто испек пирог?") — dacă îl
„repari", strici datele. (Am prins exact acest caz la audit: `Откуда берутся дети?` → `дети.`)

Curăță și **`BIRO26PT_RAW`** — altfel un re-import al unui `load_id` vechi readuce `?` în producție.

📌 **Algoritmii Python completi** (cp1251_safe + cele 4 valuri de reparare + garda pentru
URL-uri), **triggerul de protecție** `YBIRO_UNIVERS_CHK_DIACRITICE` și **modul „Servicii"**
din back-office: vezi `DIACRITICE_SI_SERVICII.md`; scripturi rulabile în `scripts/diacritics/`.

---

## 10. Cum adaptezi motorul la o SCHEMĂ NOUĂ (checklist)

1. **Conectare:** stabilește owner/DSN; verifică charset (§9.1) și locala (§9.2).
2. **Identifică obiectele-țintă** (§3.2): tabela-catalog + cheia stabilă, secvența de chei,
   tabela-cartelă, tabela de coduri, lista de prețuri (view + bază + trigger), arborele.
3. **Creează obiectele motorului** (§3.1) în schema nouă (staging + dicționare).
4. **Rescrie variabilele de configurare** (§3.3) în ambele pachete către numele reale ale
   schemei (tabele, coloane, constante `TIP/GR1/UM/CACCESS/CODTVA`, lungimi, `codprice`).
5. **Populează `BIRO26PT_COLMAP`** cu sinonimele anteturilor furnizorilor (prin python-oracledb
   dacă sunt chirilice).
6. **Verifică triggerele** de preț (§9.3) și de arbore (§9.4) — adaptează `do_writes`
   (ALTER SESSION NLS, delete+insert la mutări).
7. **Testează întâi DRY-RUN** pe un fișier real; confirmă maparea și clasificarea.
8. **Import real** pe un fișier mic; rulează verificările §8 (0 suprapuneri, produse complete).
9. **Documentează** dicționarul și eventualele particularități ale schemei noi.

---

## 11. Rezultate obținute (dovada că funcționează)

| Import | Rânduri | Rezultat |
|---|---|---|
| Coduri de bare + nomenclator | ~75 000 | +6 066 coduri; +4 146 produse + 4 393 coduri |
| Preț (Set 3) | 407 | +94 produse · 373 prețuri |
| Preț + produse noi (Set 4) | 935 | +523 produse · 523 EAN-13 · 875 marcaje · 552 prețuri |
| Preț fără articol (Set 5) | 10 430 | **0** — 8 579 nume ambigue (fără articol) |
| radop (Set 6) | 4 424 | +2 442 produse · 2 442 EAN-13 · prețuri · 1 974 imagini |

Corecții aplicate: deduplicare −3 817; perioade de preț reparate 279; produse mutate în
noduri reale 523; bug NLS preț (ORA-01843) remediat în pachet.

---

## 12. Fișiere și documente conexe

- Cod: `BIRO26PT_importData.pkg.sql`, `biro26pt_loader.py`, `YBIRO_Import_Marfa.pkg.sql`.
- Docs: `BIRO26PT_IMPORTDATA.md`, `BIRO26PT_WEB_INTERFACE_SPEC.md`, `IMPORT_TMS_UNIVERS.md`,
  `USING_GROUPED_RESULTS_FOR_PROD_DB.md`, `BIRO26_VARIANTS_IMPLEMENTATION.md`, `BIRO26_DEDUP.md`.
- Articol HTML pentru operatori: `import_reguli.html`.

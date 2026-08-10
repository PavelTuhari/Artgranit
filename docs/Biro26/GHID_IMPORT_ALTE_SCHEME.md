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

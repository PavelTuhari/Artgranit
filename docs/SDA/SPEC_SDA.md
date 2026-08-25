# Modulul SDA — specificație tehnică

> Modul al platformei Artgranit / BIRO26 pentru conformarea la Sistemul de
> Depozit pentru Ambalaje. Prefix Oracle **`SDA_`**, rute sub
> `/UNA.md/orasldev/sda-*`.
> Referințele „pct. N" trimit la Regulamentul SDA — vezi
> [sinteza normativă](LEGE_SDA_SINTEZA.md).

---

## 1. Principii de proiectare

1. **Oracle-first, normalized-first.** Fără KV, fără blob JSON ca stare primară,
   fără fișiere ca sursă autoritativă. Prefix unic `SDA_`.
2. **Tot ce legea nu a fixat este parametru versionat pe perioade**, nu
   constantă: valoarea depozitului, tariful de administrare (7 categorii),
   tariful de gestionare (5 categorii × manual/automat). Model de perioade
   `[DATA_START, DATA_END]`, ca `TPR1D_PERPRLIST` în BIRO26.
3. **O singură sursă pentru valoarea depozitului.** Se calculează server-side și
   se propagă în raft, coș, bon și factură. Divergența dintre afișări este
   defectul cel mai costisitor al acestui modul — vezi precedentul naceniei de
   credit din Biro26, unde aceeași valoare trebuia să coincidă în patru locuri.
4. **Idempotență la returnare.** Un ambalaj validat se validează o singură dată;
   un tichet se consumă o singură dată. Ambele constrângeri se impun în baza de
   date, nu doar în interfață.
5. **Evidența în bucăți ȘI kilograme** (pct. 100). Kilogramele se derivă din
   greutatea unitară din registru × bucăți; nu se cere cântărire la punct.

---

## 2. Model de date

### 2.1 Participanți și rețea

**`SDA_PARTIC`** — participanții la sistem, inclusiv organizația proprie.
`PARTIC_ID` · `IDNO` · `DENUMIRE` · `ROL` (`PROD` / `COM` / `HORECA` / `DISTR` /
`APL` / `ADMIN`) · `DATA_INREG` · `NR_CONTRACT` · `DATA_CONTRACT` ·
`CONTACT_NUME` · `CONTACT_TEL` · `CONTACT_EMAIL` · `STARE`.
Un operator poate avea mai multe roluri simultan (pct. 83) → rolurile într-o
tabelă-copil `SDA_PARTIC_ROL`, nu ca listă într-o coloană.

**`SDA_UNIT`** — unitățile de comercializare (pct. 78.3).
`UNIT_ID` · `PARTIC_ID` · `COD_ERP` (legătura cu depozitul/gestiunea OfficePlus)
· `DENUMIRE` · `ADRESA` · `LOCALITATE` · `RAION` · `SUPRAFATA_MP` ·
`TIP_AMPLASAMENT` (`MAGAZIN` / `TARABA` / `CHIOSC` / `BENZINARIE` /
`ALIMENTATIE_PUBLICA`) · `REGIM` (`A_PUNCT_PROPRIU` / `B_EXCEPTIE_APL` /
`C_HORECA`) · `REGIM_MOTIV` · `DATA_EVALUARE`.

`REGIM` se calculează, nu se introduce manual: pragul e 100 m², respectiv 150 m²
pentru tarabe, chioșcuri, benzinării și alimentație publică (pct. 93, 97).
Regula stă într-o funcție unică, iar rezultatul se stochează cu data evaluării,
ca să rămână auditabil dacă pragul sau suprafața se schimbă.

**`SDA_RETURN_POINT`** — punctele de returnare (pct. 85–87).
`POINT_ID` · `UNIT_ID` · `TIP` (`MANUAL` / `AUTOMAT` / `MIXT`) · `ADRESA` ·
`DISTANTA_M` (constrângere ≤ 150) · `ORAR` · `PARTENER_APL_ID` ·
`RESPONSABIL_NUME` · `RESPONSABIL_CONTACT` · `ACTIV_DIN` · `ACTIV_PANA`.

**`SDA_RVM`** — instalațiile automate de preluare (pct. 14.8).
`RVM_ID` · `POINT_ID` · `MODEL` · `SERIA` · `PROPRIETAR` (`COMERCIANT` /
`ADMINISTRATOR` — influențează tariful de gestionare) · `DATA_INSTALARE` ·
`STARE` · `ULTIM_HEARTBEAT`.

### 2.2 Registrul ambalajelor SD

**`SDA_PACK`** — nucleul modulului (pct. 14.3, 14.12, 25).
`PACK_ID` · `EAN` (unic) · `DENUMIRE` · `PRODUCATOR_ID` · `MATERIAL`
(`PLASTIC` / `STICLA` / `METAL`) · `REUTILIZABIL` (`D`/`N`) · `VOLUM_L` ·
`GREUTATE_G` · `CAT_ADMIN` (a…g, pct. 14.13) · `CAT_GEST` (a…e, pct. 14.14) ·
`ACTIV_DIN` · `ACTIV_PANA` · `SURSA` (`ADMIN_REGISTRU` / `MANUAL`).

`CAT_ADMIN` și `CAT_GEST` se derivă din material, culoare, barieră de oxigen și
volum — funcție unică, rezultat stocat.

**`SDA_PACK_SKU`** — puntea către nomenclatorul OfficePlus: `PACK_ID` ·
`COD_MPT` (poziția din `TMS_MPT`) · `EAN_SURSA` (din `TMS_MPT_BARCODE`). Un SKU
fără corespondent în `SDA_PACK` **nu** poartă depozit; un SKU de băutură fără
corespondent este o alertă de conformitate, nu o tăcere.

### 2.3 Tarife și depozit

**`SDA_TARIFF`** — antetul perioadei: `TARIFF_ID` · `TIP`
(`DEPOZIT` / `ADMIN` / `GESTIUNE`) · `DATA_START` · `DATA_END` · `ACT_NORMATIV`
· `OBS`.

**`SDA_TARIFF_LINE`** — valorile: `TARIFF_ID` · `CATEGORIE` (a…g sau a…e sau
`*` pentru depozit) · `METODA` (`MANUAL` / `AUTOMAT` / null) ·
`REUTILIZABIL` · `VALOARE_LEI`.

Perioadele nu se suprapun și nu lasă goluri; ultima linie a unei perioade nu se
poate șterge. Aceeași disciplină ca la prețurile pe perioade din BIRO26.

### 2.4 Operațiuni

**`SDA_SALE_DEPOSIT`** — depozitul încasat la vânzare (pct. 21.7, art. 54²).
`SALE_ID` · `UNIT_ID` · `DATA` · `DOC_ERP` (bon sau document OfficePlus) ·
`PACK_ID` · `BUCATI` · `VAL_UNITARA` · `VAL_TOTAL` · `TARIFF_ID`.
Se stochează valoarea unitară aplicată, nu doar referința la tarif — deconturile
trebuie să rămână reproductibile după orice modificare ulterioară de tarif.

**`SDA_RETURN`** — sesiunea de returnare: `RETURN_ID` · `POINT_ID` · `RVM_ID` ·
`DATA` · `METODA` (`MANUAL` / `AUTOMAT`) · `OPERATOR` · `TOTAL_BUC` ·
`TOTAL_KG` · `TOTAL_LEI` · `MOD_RAMBURSARE` (`NUMERAR` / `TICHET`) ·
`VOUCHER_ID`.

**`SDA_RETURN_LINE`** — `RETURN_ID` · `PACK_ID` · `BUCATI` · `KG` ·
`VAL_UNITARA` · `VAL_TOTAL` · `REZULTAT` (`ACCEPTAT` / `REFUZAT`) ·
`MOTIV_REFUZ` (temeiurile de la art. 54¹ alin. 9–10, pct. 91).

Refuzurile se înregistrează, nu se aruncă: sunt necesare pentru raportare și
pentru apărarea în caz de reclamație.

**`SDA_VOUCHER`** — registrul tichetelor (pct. 14.15, 90.2).
`VOUCHER_ID` · `COD` (unic, generat criptografic) · `POINT_ID` · `PARTIC_ID`
(emitentul — tichetul RVM se preschimbă la **același** comerciant) ·
`VALOARE_LEI` · `DATA_EMITERE` · `DATA_EXPIRARE` (= emitere + 12 luni) ·
`STARE` (`EMIS` / `PRESCHIMBAT_NUMERAR` / `FOLOSIT_CUMPARATURI` / `EXPIRAT` /
`ANULAT`) · `DATA_CONSUM` · `DOC_ERP_CONSUM`.

Tranziția din `EMIS` este singura permisă și se face sub blocare — dubla
utilizare a unui tichet este scenariul de fraudă cel mai probabil al sistemului.

**`SDA_HANDOVER`** / **`SDA_HANDOVER_LINE`** — predarea către centrul logistic
(pct. 14.2, 88). Antet: `HANDOVER_ID` · `POINT_ID` · `DATA` · `NR_SAC` ·
`NR_SIGILIU` · `TOTAL_BUC` · `TOTAL_KG` · `STARE` (`PREDAT` / `CONFIRMAT` /
`DIVERGENTA`) · `DATA_CONFIRMARE`. Linii pe `PACK_ID` sau pe categorie.

Divergențele între ce s-a predat și ce a confirmat centrul logistic se
urmăresc explicit: pe ele se plătește sau nu tariful de gestionare.

### 2.5 Financiar și raportare

**`SDA_SETTLEMENT`** — deconturile: `SETTLEMENT_ID` · `PARTIC_ID` · `PERIOADA` ·
`TIP` (`GESTIUNE_INCASAT` / `DEPOZIT_DATORAT` / `ADMIN_DATORAT`) ·
`VAL_CALCULATA` · `VAL_INCASATA` · `DATA_SCADENTA` · `DATA_PLATA` ·
`ZILE_INTARZIERE`. Pentru tariful de gestionare, `DATA_SCADENTA` aplică regula
celor **cel mult 14 zile** (pct. 14.14).

**`SDA_REPORT`** / **`SDA_REPORT_LINE`** — raportările generate: tipul
(`EVIDENTA_PCT100` / `LUNAR_10` / `PLATA_25` / `INREGISTRARE_PCT78` /
`SEMESTRIAL`), perioada, starea, fișierul exportat, data transmiterii.

**`SDA_EVENT_LOG`** — jurnal append-only al modulului: `EVENT_ID` · `DATA` ·
`TIP` · `ENTITATE` · `ENTITATE_ID` · `UTILIZATOR` · `DETALII`. Event log propriu
al modulului, nu container generic partajat.

---

## 3. Integrarea cu BIRO26 / OfficePlus

| Punct de contact | Cum |
|---|---|
| Nomenclator și coduri de bare | `TMS_MPT`, `TMS_MPT_BARCODE` → `SDA_PACK_SKU` prin EAN |
| Unități / gestiuni | codul gestiunii OfficePlus → `SDA_UNIT.COD_ERP` |
| Coș și facturare | linia de depozit se adaugă în `shop_invoice` și în coșul public, calculată server-side |
| Documente ERP | `SDA_SALE_DEPOSIT.DOC_ERP` și `SDA_VOUCHER.DOC_ERP_CONSUM` trimit la documentul nativ |
| Forme tipărite | tichetul și borderoul de predare prin sidecar-ul de rapoarte (jsReport / pdfme) |
| Acces Oracle 11g | prin `models/biro26_worker.py` — `init_oracle_client` rămâne exclusiv acolo |

Restricțiile Oracle 11g se păstrează: fără `OFFSET/FETCH` (paginare `ROWNUM`),
fără `IDENTITY` (secvență + trigger), exclusiv variabile bind.

---

## 4. Interfețe

Modulul a fost mutat în arhitectura de module izolate a portalului
(`docs/CORE_MODULES.md`): pachetul `modules/sda/` exportă un `blueprint`
Flask, iar `core/module_loader.py` îl descoperă și îl montează singur sub
`/UNA.md/orasldev/sda`, fără nicio linie în `app.py`. Rutele din `routes.py`
sunt scrise **fără** acest prefix — nucleul îl adaugă la înregistrare, deci
modulul nu poate, fizic, să ocupe o adresă din afara zonei lui.

### 4.1 Ce există astăzi

| Rută (adresa reală, cu prefixul adăugat de nucleu) | Conținut |
|---|---|
| `/UNA.md/orasldev/sda` | hubul de documentație al modulului (alias: `…/sda/docs`) |
| `…/sda/docs/<slug>` | un document al modulului |
| `…/sda/presentation` | dosarul de prezentare pentru client |
| `…/sda/console` | consola modulului: patru panouri — harta de conformitate, rețeaua de unități, registrul ambalajelor, participanții |

Fostul `/UNA.md/orasldev/sda-console` (vecin cu cratimă, imposibil sub
nucleu — un blueprint primește un singur prefix `/UNA.md/orasldev/<cheie>`)
a devenit calea copil `…/sda/console`.

API-ul livrat trăiește sub propriul prefix, nu în namespace-ul comun `/api/`:
`GET/POST …/sda/api/partic`, `GET/POST …/sda/api/units`,
`POST …/sda/api/units/reclassify`, `GET …/sda/api/compliance`,
`GET/POST …/sda/api/packs`, `GET …/sda/api/deposit`, `GET …/sda/api/dossier`.
Citirile sunt deschise, scrierile cer autentificare; dosarul cere de asemenea
autentificare. (Adresele vechi, de dinainte de migrare, erau
`/api/sda/...` — un modul nou nu mai are cum să ocupe namespace-ul comun
`/api/`, exact ideea nucleului.)

### 4.2 Rute planificate pentru etapele următoare

Rutele de mai jos **nu există încă** — ele aparțin etapelor 4–8 din § 7 și
sunt păstrate aici ca plan, nu ca stare a modulului:

| Rută | Conținut | Etapa |
|---|---|---|
| `…/sda-retur` | chioșcul de returnare: scanare EAN, validare, refuz motivat, emitere tichet | 5 |
| `…/sda-tichete` | validare și consum de tichet la casă, căutare după cod, istoric | 5 |
| `…/sda-predari` | predări către centrul logistic, saci și sigilii, confirmări, divergențe | 6 |
| `…/sda-tarife` | perioade de tarif: depozit, administrare, gestiune | 3 (rest) |
| `…/sda-decont` | cuvenit vs. încasat, control al termenului de 14 zile | 7 |
| `…/sda-rapoarte` | evidența pct. 100, dosarul pct. 78, afișajele pct. 84 și 92, exporturi | 8 |

Chioșcul de returnare reia tiparul `ScaleKiosk` din modulul AGRO: IIFE care
expune un obiect global, configurat prin constructor, cu selecție de elemente
prin atribute `data-*` și delegare de evenimente pe container. Scriptul extern
se încarcă înaintea blocului inline care îl instanțiază.

Meniul nu se scrie manual: `modules/sda/module.json` descrie titlul în trei
limbi, iconul, ordinea și adresa; descoperirea rutelor este automată.

---

## 5. Reguli de business care se impun în baza de date

1. `SDA_UNIT.REGIM` derivat din suprafață și tip de amplasament, cu data
   evaluării stocată.
1a. Regimul `C_HORECA` este disponibil doar unităților al căror
   `TIP_AMPLASAMENT` este `ALIMENTATIE_PUBLICA`. Controlorul respinge orice
   încercare de a marca `is_horeca` pentru un alt tip de amplasament —
   altfel reclasificarea ar citi `REGIM = 'C_HORECA'` înapoi ca intrare și
   ar perpetua la nesfârșit o clasificare eronată, chiar și pentru un
   magazin obișnuit.
2. `SDA_RETURN_POINT.DISTANTA_M ≤ 150`.
3. Perioadele din `SDA_TARIFF` nu se suprapun și nu lasă goluri pe același tip
   și aceeași categorie.
4. `SDA_VOUCHER.DATA_EXPIRARE = DATA_EMITERE + 12 luni`; consumul e permis o
   singură dată, sub blocare; tichetul emis de RVM se consumă doar la
   `PARTIC_ID` emitent.
5. Returnarea prin RVM nu poate avea `MOD_RAMBURSARE = NUMERAR` (pct. 90.2).
6. `SDA_RETURN_LINE.KG = PACK.GREUTATE_G × BUCATI / 1000`.
7. Un `EAN` absent din `SDA_PACK` nu generează depozit și ridică alertă.

---

## 6. Livrare

DDL în `sql/` cu includere în ordinea din `deploy_oracle_objects.py`. Obiectele
Oracle nu se creează prin deploy-ul de cod: se rulează separat
`python deploy_oracle_objects.py` sau deploy remote cu
`DEPLOY_ORACLE_ON_REMOTE=1`.

Verificare după livrare: obiectele `SDA_*` prezente în `USER_OBJECTS`; modulul
vizibil în `/UNA.md/orasldev/modules` și în bara laterală; rutele funcționale;
`curl -I https://nufarul.eminescu.md/login` → 200.

---

## 7. Etape de implementare

| # | Etapă | Conținut | Stare |
|---|---|---|---|
| 1 | Rețea și regimuri | `SDA_PARTIC`, `SDA_UNIT`, calculul regimului, harta de conformitate, dosarul pct. 78 | **Livrat** |
| 2 | Registru | `SDA_PACK`, `SDA_PACK_SKU`, sincronizare, alerte de mapare | **Livrat** |
| 3 | Tarife | perioade versionate, funcțiile de calcul | **Parțial** |
| 4 | Front | linia de depozit la casă și în coș, afișajele pct. 84 și 92 | — |
| 5 | Returnare | chioșc, refuzuri motivate, registrul tichetelor | — |
| 6 | Logistică | predări, sigilii, confirmări, divergențe | — |
| 7 | Financiar | deconturi, controlul termenului de 14 zile | — |
| 8 | Raportare | evidența pct. 100, exporturi, jurnal | — |

Etapa 3 este marcată **parțial** în mod deliberat: schema (`SDA_TARIFF`,
`SDA_TARIFF_LINE`) și regulile pure (`sda_rules.validate_periods`,
`sda_rules.pick_value`) există și sunt acoperite de teste, dar nu există nici
UI, nici API pentru tarife. `validate_periods` este apelată doar din teste, iar
rândurile de tarif pot fi introduse astăzi exclusiv prin SQL scris de mână.
Până când apare `…/sda-tarife`, etapa nu poate fi considerată livrată.

Etapa 1 are valoare de sine stătătoare: produce harta de conformitate și
dosarul de înregistrare, care sunt necesare indiferent de restul modulului.

Două decizii de arhitectură au fost fixate în etapele 1–3 și rămân
obligatorii pentru etapele următoare:

1. Tabelele `SDA_*` trăiesc în ADB-ul cloud al platformei Artgranit, nu în
   ERP-ul clientului. Rețeaua de retail nu capătă un schema propriu — modulul
   citește și scrie exclusiv în baza platformei, prin `models/sda_oracle_store.py`.
2. Nomenclatorul OfficePlus este doar-citire, accesat prin `biro26_db`.
   Modulul SDA nu scrie niciodată în schema OfficePlus/Biro26 — orice
   corelare cu SKU-uri sau prețuri de acolo este o citire, nu o sincronizare
   bidirecțională.

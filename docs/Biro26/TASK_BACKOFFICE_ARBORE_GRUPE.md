# TASK (echipa biro26-backoffice): categoriile importate nu apar în „Grupe de marfă"

> Destinatar: echipa/AI care întreține **biro26-backoffice** (officeplus.md/UNA.md/orasldev/biro26-backoffice).
> Autor: partea de import (pachet `BIRO26PT_importData`).
> Prioritate: blochează afișarea a ~22 000 produse noi (feed ULTRA) pe categoriile lor.

---

## 1. Rezumat (ce ne trebuie de la voi)

Produse noi importate (categorii electronice: Smartphone, Tablete, Foto și Video etc.) **nu apar
în panoul din stânga „Grupe de marfă"** (tab-ul *Marfă / Stoc*), deși structura din baza de date
este creată corect și **identică** cu a categoriilor care se afișează (ex. „Articole pentru arta").

Avem nevoie să ne spuneți **din ce sursă construiește back-office-ul panoul „Grupe de marfă"**
(ce query/tabel/câmp/cache/serviciu), ca fie să aliniem importul exact la ea, fie să ajustați
voi randarea ca să includă nodurile noi.

---

## 2. Simptom

- Importul creează categoriile în arbore (`TMS_SYSGRPH` / `TMS_SYSGRP`) + rândurile-categorie
  `TMS_UNIVERS (TIP='T')`, dar categoriile noi **nu apar** în panoul „Grupe de marfă".
- Produsele sunt corect în DB (au preț, cod de bare, imagine, producător), dar în panoul de
  navigare pe grupe nu se văd sub categoria lor.

---

## 3. Ce am făcut deja pe DB (structura e completă și corectă)

Am reprodus **exact** structura unei categorii funcționale. Exemplu concret — categoria de test
**„Foto și Video"** (`group1 = 301`), comparată cu una funcțională „Articole pentru arta"
(`group1 = 276`):

| Element | Categorie funcțională (276) | Categoria noastră (301) |
|---|---|---|
| Nod top în `TMS_SYSGRPH` (group2=0) | ✓ SCH=161251 | ✓ SCH=325465 |
| Rând-categorie `TMS_UNIVERS` `TIP='T', GR1='TREE'` | ✓ 161251 | ✓ 325465 |
| **Rândul-categorie plasat în `TMS_SYSGRP`** (sc=SCH, la nodul său) | ✓ (276,0) | ✓ (301,0) |
| Subcategorii (group2>0) cu SCH + rând `TIP='T'` + plasare | ✓ | ✓ (7 subcat.) |
| Produse plasate 2 niveluri (id1=top, id2=sub) | ✓ | ✓ (705 produse) |
| Producător (`TMS_MPT.DEP_PRODUCER`) | ✓ | ✓ ULTRA (cod 325464) |
| Nod orfan/gol | — | șters |

Structura este bit-cu-bit ca șablonul. **Totuși categoria nu apare în back-office** → concluzia:
panoul folosește o sursă/condiție suplimentară pe care nu o putem deduce fără codul back-office-ului.

---

## 4. Modelul de date al arborelui (reverse-engineered — pentru referință)

- **`TMS_SYSGR`** — rădăcini (ex. `id0=1` = „DEPOZIT", `TIP='P,T'`, `GR1='TVR,TREE'`).
- **`TMS_SYSGRPH`** — nodurile arborelui: `group1..group5`, `coment` (numele nodului),
  **`sch`** (= codul rândului-categorie din `TMS_UNIVERS`), `id0`, `id1`.
  - Nod top: `group2=0`. Subnod: `group1=<top>`, `group2>0`.
- **`TMS_SYSGRP`** — apartenențe: `group1..group5`, `sc` (cod produs SAU cod-categorie),
  `id0`, `id1` (=id1 nod top), `id2` (=id1 subnod).
- **`TMS_UNIVERS`** — rândurile-categorie au `TIP='T'`, `GR1='TREE'`, `denumirea`=numele categoriei.
  Produsele au `TIP='P'`.
- **`TMS_MPT.DEP_PRODUCER`** → cod org producător/furnizor (`TMS_UNIVERS TIP='O', GR1='E'`).

Reguli observate pentru un nod „valid" (toate reproduse de noi):
1. Rând `TMS_UNIVERS TIP='T'` pentru categorie → `cod` = `SCH`-ul nodului.
2. Nod în `TMS_SYSGRPH` cu `SCH` completat.
3. Rândul-categorie plasat și în `TMS_SYSGRP` (membru al nodului său).
4. Produsele plasate în `TMS_SYSGRP` sub subnod (`id1`=top, `id2`=sub).

---

## 5. Întrebarea deschisă (ce trebuie clarificat de voi)

**Cum construiește back-office-ul panoul „Grupe de marfă"?** Concret, unul din:
- Ce interogare/tabel/câmp folosește (direct `TMS_SYSGRPH`? un view? o tabelă proprie a app-ului?).
- Există un **cache** al arborelui care trebuie invalidat/reconstruit după import?
- Există câmpuri de sincronizare pe care importul trebuie să le seteze
  (`TMS_SYSGRPH.MYSQL_ID`, `MYSQL_PARENT_ID`, `SCH`, `TIP2`, `PARAM1..4`, `LAC`)?
  (La noi `MYSQL_ID/MYSQL_PARENT_ID` sunt NULL — dar sunt NULL și la nodurile funcționale.)
- Filtrează după un interval de `group1` / o rădăcină anume / un `TIP` anume?
- Nodurile trebuie înregistrate și în alt loc (o tabelă de categorii proprie a back-office-ului)?

---

## 6. Sarcini pentru echipa back-office

1. Identificați **sursa exactă** a panoului „Grupe de marfă" (query/tabel/cache/serviciu).
2. Determinați **de ce nodul 301 („Foto și Video") nu apare**, deși e structural identic cu 276.
3. Fie:
   - (a) documentați condiția/câmpurile necesare, ca **importul** (`BIRO26PT_importData`) să le
     completeze automat la crearea nodurilor; **sau**
   - (b) ajustați randarea/cache-ul back-office-ului ca să includă nodurile create de import.
4. Confirmați pe categoria de test **„Foto și Video"** (deja pregătită în DB) că apare corect,
   apoi anunțați-ne — noi aplicăm același tratament pe toate cele 17 categorii ULTRA (~22 000 produse).

---

## 7. Criterii de acceptare

- În *Marfă / Stoc → Grupe de marfă* apare **„Foto și Video"** cu cele 7 subcategorii și numărul
  corect de produse.
- Produsele au **Producător = ULTRA**; **ULTRA** apare în lista de furnizori.
- Repetabil pentru orice categorie nouă creată de import (nu doar cea de test).

---

## 8. Date de referință (pentru inspecție rapidă)

```sql
-- categoria de test creata (funcaza structural, dar nu apare in panou):
SELECT * FROM tms_sysgrph WHERE id0=1 AND group1=301 ORDER BY group2;         -- nod top + 7 subnoduri
SELECT * FROM tms_sysgrp  WHERE id0=1 AND group1=301 ORDER BY group2, sc;       -- rinduri-categorie + 705 produse
SELECT cod,denumirea,gr1,tip FROM tms_univers WHERE cod IN (325465,325466,325467,160814,325468,325469,325470,325471);
-- comparatie cu o categorie functionala:
SELECT * FROM tms_sysgrph WHERE id0=1 AND group1=276 ORDER BY group2;
SELECT * FROM tms_sysgrp  WHERE id0=1 AND group1=276 ORDER BY group2, sc;

-- furnizorul ULTRA:
SELECT cod,denumirea,gr1,tip FROM tms_univers WHERE cod=325464;                 -- ULTRA (TIP='O', GR1='E')

-- toate categoriile ULTRA importate (17 grupe) sunt in coloana c6/c7 din stagin:
SELECT DISTINCT c6 grupa, c7 categorie FROM biro26pt_raw WHERE load_id BETWEEN 121 AND 137;
```

Fișierul sursă al feed-ului: `Set_data_import/7/ULTRA.md (1).xlsx` (17 foi; col6=`GRUPA`, col7=`CATEGORIE`, col14=`PRODUCER`=ULTRA).

---

## 9. Note

- Partea de **import** (produse, prețuri, coduri de bare, imagini, producător, structura de arbore
  în DB) este completă și verificată. Rămâne **doar** afișarea în panoul back-office.
- Restul celor ~22 000 produse ULTRA sunt deja importate; le putem re-plasa în arbore identic cu
  „Foto și Video" imediat ce confirmați mecanismul corect.
- Referințe: `BIRO26PT_IMPORTDATA.md`, `GHID_IMPORT_ALTE_SCHEME.md`, `BIRO26PT_importData.pkg.sql`.

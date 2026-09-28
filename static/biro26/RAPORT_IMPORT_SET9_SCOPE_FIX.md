# Raport pentru echipa GUI: importul set 9 (RICHI-TICHI) — două erori de import, remediate

> **Cui:** echipa/AI care întreține interfața de import (`import_pt`, `biro26pt_store`, back-office).
> **De la:** partea de import (pachetul `BIRO26PT_importData`).
> **Statut:** ambele cauze **remediate în producție**; set 9 este **importat**.
> **De ce vă privește:** una dintre erori putea corupe orice import făcut din GUI, indiferent de fișier.

---

## 1. Ce a văzut utilizatorul

La apăsarea **„Importă în DB"** pentru `Set_data_import/9/RICHI-TICHI.xlsx`:

```
ORA-20077: RO: Text cu diacritice STRICATE in DENUMIREA ...
           Valoare: "Тройка с минусом,или происшествие в 5?А»"
ORA-06512: at "OFFICEPLUS.YBIRO_UNIVERS_CHK_DIACRITICE", line 20
ORA-06512: at "OFFICEPLUS.YBIRO_IMPORT_MARFA", line 133
ORA-06512: at "OFFICEPLUS.BIRO26PT_IMPORTDATA", line 404
```

Analiza a arătat imediat ceva ciudat: **acel text NU există în fișierul încărcat**.
În `RICHI-TICHI.xlsx` există doar 6 celule cu `?`, toate semne de întrebare reale
(„Te joci cu mine?", „Угадай кто?") — pe care triggerul de protecție le acceptă corect.

---

## 2. Cauza reală (BUG serios, vă privește direct)

`YBIRO_Import_Marfa.import_univers` citește **întreaga tabelă** pe care e configurat
(`g_tbl_goods`), **fără filtru pe `load_id`**:

```sql
INSERT INTO tms_univers (...)
SELECT g.cod_univers, ... FROM BIRO26PT_STG g          -- ← toată tabela!
 WHERE g.cod_univers IS NOT NULL AND g.denumire IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM tms_univers t WHERE t.cod = g.cod_univers);
```

Iar `BIRO26PT_STG` este **cumulativă** — păstrează rândurile tuturor încărcărilor.
În momentul erorii conținea:

| | |
|---|---|
| Încărcări diferite în stagin | **204** |
| Rânduri totale | **616 210** |
| Rânduri **din alte fișiere** care ar fi fost inserate | **73 146** |

Deci importul fișierului *set 9* încerca de fapt să scrie și rânduri rămase din
**alte** încărcări (printre ele textul stricat din feed-ul RADOP) — iar triggerul de
protecție a oprit tot procesul.

> ⚠️ Consecința pentru voi: **orice** import lansat din GUI, pentru orice fișier, putea
> insera în catalog rânduri din încărcările anterioare rămase în stagin. O parte din
> „dublurile apărute de nicăieri" reclamate anterior se explică exact prin acest mecanism.

### Remediere

Am introdus un **view limitat la încărcarea curentă** și am legat pachetul reutilizat de el:

```sql
-- funcție publică în pachet: întoarce load_id-ul încărcării în lucru
FUNCTION cur_load RETURN NUMBER;

CREATE OR REPLACE VIEW BIRO26PT_STG_CUR AS
  SELECT * FROM biro26pt_stg WHERE load_id = BIRO26PT_importData.cur_load;
```
```plsql
-- în do_writes, înainte de a apela pachetul reutilizat:
g_cur_load := p_load_id;
YBIRO_Import_Marfa.g_tbl_goods := 'BIRO26PT_STG_CUR';   -- nu mai vede alte încărcări
```

---

## 3. A doua eroare (apărută după prima remediere)

```
ORA-02291: integrity constraint (OFFICEPLUS.TMS_SYSGRP_FK) violated - parent key not found
```

**Cauză:** un rând al fișierului (poz. 5672, articol `00065`) are **denumirea goală**.
`import_univers` îl sare (numele e obligatoriu), dar rândul primise deja un `COD` din
secvență → pașii următori (plasarea în arbore) refereau un produs inexistent.

**Remediere — două verificări:**
1. rândurile **fără denumire nu mai primesc `COD`** (nu pot deveni produse oricum);
2. inserarea în arbore verifică explicit că produsul există:
   `AND EXISTS (SELECT 1 FROM tms_univers u2 WHERE u2.cod = s.cod_univers)`.

Verificat după import: **0** rânduri-orfan în arbore.

---

## 4. Rezultatul importului set 9

`RICHI-TICHI.xlsx` — 8 161 rânduri, 16 coloane, toate câmpurile detectate din antet
(`ARTICOL, DENUMIRE, DENUM_FULL, DESCRIERE, GRUPA, CATEG, FURNIZOR, ANGRO, ONLINE, RETAIL, VAT, BARCODE, URL`).

| Ce s-a scris | Cantitate |
|---|---|
| Produse noi în `TMS_UNIVERS` (+ cartele) | **4 147** |
| Prețuri (perioadă nouă) | **4 148** |
| Coduri de bare din fișier | **3 962** |
| Imagini (URL → `TMS_MPT_TVR`) | **3 701** |
| Atribute web (`TMS_MPT_WEBATTR`) | **3 234** |
| Rânduri sincronizate în `BIRO26_GOODS` (arbore + magazin) | **7 128** |
| Rânduri sărite (ambigue) | 921 |

Produsele apar în magazin/back-office prin `BIRO26_GOODS` (grupa `Jocuri si jucarii`).

---

## 5. Ce trebuie să faceți voi

1. **`git pull` + redeploy** — pachetul și view-ul sunt deja în producție, dar sursa din
   repo (`sql/biro26/BIRO26PT_importData.pkg.sql`) trebuie să fie cea nouă, ca un deploy
   viitor să nu readucă versiunea veche (fără filtrul pe `load_id`).
2. **Curățarea stagin-ului (recomandat).** `BIRO26PT_STG` are 616k rânduri din 204 încărcări.
   Filtrul rezolvă corectitudinea, dar tabela crește la nesfârșit. Propunere: după un import
   încheiat cu succes, ștergeți rândurile mai vechi de N zile:
   ```sql
   DELETE FROM biro26pt_stg WHERE load_id IN (
     SELECT load_id FROM biro26pt_file WHERE loaded_at < SYSDATE - 30);
   ```
   (la fel pentru `biro26pt_raw` / `biro26pt_raw_blob`, care sunt și mai mari).
3. **Afișați eroarea integral în UI.** Mesajul `ORA-20077` conține valoarea problematică —
   ea a fost cheia diagnosticului. Nu-l trunchiați.
4. **Nimic de schimbat în logica voastră** — corecțiile sunt în pachetul PL/SQL.

---

## 6. Despre triggerul de protecție (context util)

`YBIRO_UNIVERS_CHK_DIACRITICE` blochează scrierea în `TMS_UNIVERS` a textelor cu diacritice
stricate de charset (`5?А`, `car?i`, `?coala`). **Nu** blochează semnele de întrebare reale
(„Угадай кто?") — le recunoaște după poziție (`?` între litere/cifre = stricat).

Dacă un import se oprește cu `ORA-20077`:
- verificați **valoarea** din mesaj: dacă e text stricat, fișierul furnizorului e de refăcut;
- dacă valoarea nu apare în fișierul încărcat → e un rând rămas din altă încărcare
  (exact cazul de față — acum imposibil, datorită filtrului);
- dezactivare de urgență (conștientă): `ALTER TRIGGER YBIRO_UNIVERS_CHK_DIACRITICE DISABLE;`

---

## 7. Referințe

- `GHID_IMPORT_ALTE_SCHEME.md` §9.18 — regula „un import vede DOAR încărcarea lui"
- `TZ_WEB_TMS_MPT_WEBATTR.md` — atributele web (BLOB + copii de căutare)
- `DIACRITICE_SI_SERVICII.md` — triggerul de protecție și algoritmii de reparare
- `sql/biro26/BIRO26PT_importData.pkg.sql` — pachetul (main)

# Raport pentru echipa de import (BIRO26PT_importData): dubluri GOG + corecții aplicate

> **Кому / Cui:** echipa/AI care pregătește fișierele și rulează importurile de date
> (pachetul `BIRO26PT_importData`, seturile ULTRA/GOG).
> **De la:** echipa web (Artgranit / biro26).
> **Data:** 26.07.2026. **Statut:** problemele de mai jos sunt **deja remediate în producție**;
> documentul e informativ + cerințe pentru fluxurile voastre viitoare.

---

## 1. Ce s-a întâmplat (incidentul „marfă dublată")

În back-office și pe vitrină produsele apăreau **de două ori**: cardul vechi (feed Biblion,
barcode real `4840…`) și un card nou cu badge «NOU», articol `GOG7000xx` și barcode
intern `2000000…`.

### Cauza-rădăcină (dovedită pe date)

1. **Load 164** (fișier GOG, 37 717 rânduri) a fost importat **fără coloana BARCODE** —
   fișierul pur și simplu nu o conținea (antete: `URL, ARTICOL, Название в карточке,
   Полное название, DESCRIERE, GRUPA, CATEGORIE, ROUNIT, STOC, TAXRATE, prețuri`).
2. Potrivirea în `classify()` mergea **doar după ARTICOL** (`TMS_UNIVERS.CODVECHI`).
   Cardurile vechi nu au articol (`CODVECHI IS NULL`) → nimic nu s-a potrivit →
   **toate rândurile au devenit NEW** → ~37,7k carduri-dublură cu `CODVECHI = GOG*`.
3. Cardurile noi nu aveau barcode → sistemul a generat **EAN-13 intern cu prefix «2»**
   (`2000000NNNNNC`). Prefixul «2» este intervalul EAN rezervat oficial pentru uz intern —
   mecanismul e legitim și vechi (există ~47,8k asemenea coduri istorice), dar pe dubluri
   a fost simptomul lipsei barcode-ului în fișier.
4. **Loads 172/228** (fișiere GOG *cu* barcode-uri reale) nu au reparat situația:
   potrivirea după ARTICOL găsea acum **dublura** (articolul GOG exista deja pe ea),
   deci actualizările se «lipeau» de dublură, iar barcode-ul real din fișier aparținea
   de fapt cardului VECHI.

---

## 2. Ce am remediat noi (deja în producție)

| # | Acțiune | Detalii |
|---|---|---|
| 1 | **Jurnal reversibil** | Tabelul `YBIRO_GOG_DEDUP` (37 697 perechi `DUP_COD → ORIG_COD` + `ARTICOL`, `BARCODE`, `ORIG_CODVECHI_OLD`, `TS`). Perechile au fost identificate STRICT prin barcode-ul real din loads 172/228 → un singur card original ACTIV, fără articol. |
| 2 | **Articolul mutat pe original** | `GOG*` a trecut pe cardul ORIGINAL (`CODVECHI`), dublura a rămas fără articol — importurile viitoare se potrivesc în cardul corect. |
| 3 | **Dublurile arhivate soft** | `ISARHIV='2'` (mecanismul nativ, prin `un4public.set_env`); nimic șters fizic; vizibile în back-office cu filtrul «Vizualizare marfă dezactivată». |
| 4 | **Pachetul corectat** | `BIRO26PT_importData.classify()`: potrivirea se face acum **ÎNTÂI după BARCODE** (cod de bare real din fișier → un singur card activ), apoi după ARTICOL. Sursa: `sql/biro26/BIRO26PT_importData.pkg.sql` (main). Pachetul recompilat, VALID. |

Rezultat verificat: `#CarneCarne`, `#Pastapaste` etc. — un singur card activ pe vitrină,
cu barcode-ul real și articolul GOG pe el. Din cardurile create de load 164 active au
rămas **20** (fără original identificabil — probabil produse realmente noi).

---

## 3. Ce vă cerem pentru importurile viitoare (adaptați algoritmii)

1. **Fișier fără coloana BARCODE = interzis pentru seturi mari.** Dacă furnizorul nu dă
   barcode, NU rulați importul „pe articol" peste un sortiment care poate exista deja —
   întâi cereți/completați barcode-urile sau conveniți cu echipa web o cheie de potrivire.
   (Exact acest scenariu a produs 37,7k dubluri.)
2. **Nu regenerați articole noi pentru marfă veche.** Articolul (`GOG*`) acum stă pe
   cardurile ORIGINALE — folosiți aceleași articole în fișierele viitoare, nu emiteți
   serii noi pentru aceleași produse.
3. **Barcode-ul real este cheia primară de potrivire.** Pachetul potrivește acum întâi
   după barcode; puneți coloana de barcode în TOATE fișierele unde există fizic.
   Barcode-urile interne `2000000…` din exporturile voastre NU sunt coduri reale de
   producător — nu le propagați în fișiere noi ca și cum ar fi EAN-uri reale.
4. **Dublurile arhivate nu se re-folosesc.** Nu trimiteți update-uri țintite pe codurile
   univers ale dublurilor (lista completă: `SELECT dup_cod FROM YBIRO_GOG_DEDUP`).
   Dacă un set vechi le mai referă — regenerați setul.
5. **La nevoie de rollback / verificare:**
   ```sql
   -- perechile dublura -> original
   SELECT dup_cod, orig_cod, articol, barcode FROM ybiro_gog_dedup;
   -- dubluri inca active create de load 164 (ar trebui sa ramina ~20)
   SELECT u.cod, u.denumirea FROM tms_univers u
    WHERE u.codvechi LIKE 'GOG%' AND NVL(u.isarhiv,'0') <> '2'
      AND u.cod IN (SELECT cod_univers FROM biro26pt_stg WHERE load_id = 164);
   ```

---

## 4. A doua problemă, separată: `TMS_MPT_WEBATTR` nealiniat (set 8)

**1 274 din 30 004** rânduri din `TMS_MPT_WEBATTR` au denumirea/descrierea ALTUI produs
decât `TMS_UNIVERS` cu același COD (exemplu: COD 303284 — în UNIVERS «Smartphone Xiaomi
12T Pro», în WEBATTR descrierea «Imprimanta laser HP LaserJet Pro 3003dn»). Arată a
**deplasare de bloc de rânduri** la încărcarea set 8. Pe vitrină acele produse afișează
acum descrierea altui produs.

Verificare:
```sql
SELECT u.cod, u.denumirea, w.denumire_full_ro
  FROM tms_univers u JOIN tms_mpt_webattr w ON w.cod = u.cod
 WHERE w.denumire_full_ro IS NOT NULL
   AND UPPER(SUBSTR(u.denumirea,1,15)) <> UPPER(SUBSTR(w.denumire_full_ro,1,15));
```
**Cerere:** verificați maparea COD↔rând în fluxul vostru pentru set 8 și **reîncărcați
rândurile afectate** (scrierea corectă: BLOB-urile `DESCRIERE_*` / `DENUMIRE_FULL_BLOB_*`;
copiile fără diacritice le regenerează triggerul `TMS_MPT_WEBATTR_BIU`).

---

## 5. Referințe

- `TZ_WEB_TMS_MPT_WEBATTR.md` — arhitectura BLOB/diacritice (implementată de web).
- `sql/biro26/BIRO26PT_importData.pkg.sql` — pachetul cu potrivirea barcode-first (main).
- `README_BIRO26.html` §11А, §15 — importul universal + noutățile;
  live: `/UNA.md/orasldev/biro26-docs`.
- Jurnal dedup: tabelul `YBIRO_GOG_DEDUP` (producție).

*Întrebări — către echipa web (Artgranit/biro26).*

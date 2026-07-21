# Instrucțiune: Încărcarea datelor (Import asistent) — ghid pentru operator

> Cum încarci un fișier de la furnizor (prețuri, produse noi, coduri de bare) în OfficePlus,
> prin interfața **Back-office → Import (asistent)**. Fără cunoștințe tehnice.

---

## 1. Ce fișiere poți încărca

- **Format:** Excel (`.xlsx`, `.xls`) sau `.csv`. Poți încărca **mai multe fișiere** deodată
  sau o **arhivă `.zip`** a unei mape. Un fișier Excel cu **mai multe foi** e acceptat —
  fiecare foaie e tratată separat (des = o categorie).
- **Primul rând = antet** (numele coloanelor). Datele încep din rândul 2.

## 2. Ce coloane trebuie să aibă fișierul

Sistemul recunoaște coloanele automat, după numele din antet (română / rusă / engleză).

| Coloană | Obligatoriu? | Exemple de antet recunoscut |
|---|---|---|
| **Articol** (cod produs) | **DA — cheia** | `Articol`, `Артикул`, `SKU`, `Cod produs` |
| Denumire | Recomandat | `Название в карточке`, `Denumire` |
| Preț cu amănuntul (retail) | Recomandat | `Retail cu TVA`, `Розничная цена с НДС` |
| Preț online | Opțional | `Preț online`, `Price Online` |
| Preț angro / achiziție | Opțional | `ANGRO`, `Цена закупки без НДС` |
| Cod de bare | Opțional | `Barcode`, `Штрихкод`, `Cod de bare`, `EAN` |
| Grupă (categorie de sus) | Opțional | `GRUPA`, `Категория`, `Group` |
| Categorie (subgrupă) | Opțional | `CATEGORIE`, `Category` |
| Furnizor / producător | Opțional | `PRODUCER`, `Furnizor`, `Producător` |
| TVA | Opțional | `Ставка НДС`, `TVA` |

> ⚠️ **Cel mai important:** fișierul TREBUIE să aibă coloana **Articol**. Fără ea, produsele
> nu pot fi identificate cu certitudine (numele nu sunt unice) și importul se blochează.

## 3. Cei 3 pași în interfață

1. **Încarcă** — trage fișierele (sau `.zip`) în zona de încărcare. Vei vedea lista fișierelor
   cu numărul de rânduri și coloane.
2. **Analizează** (dry-run) — apasă *Analizează*. **Nu se scrie nimic** încă. Vezi:
   - **Cum au fost înțelese coloanele** (fiecare coloană → câmpul ei, cu bifă verde);
   - **Câte produse:** Noi · Existente (câte cu preț schimbat) · Ambigue · Fără articol.
   - Poți da *Rânduri* ca să vezi produsele una câte una.
3. **Importă** — dacă analiza arată bine, apasă *Importă în DB*. Datele se scriu în producție.

## 4. Ce face importul (automat)

- **Produse noi** → se creează în catalog + cartelă + se pun în categoria lor (Grupă › Categorie).
- **Prețuri** → preț de raft, online, achiziție (după coloanele din fișier). La produs existent,
  se creează o **perioadă nouă de preț** (istoric păstrat).
- **Cod de bare** → se atașează cel din fișier; dacă produsul nou n-are cod, se **generează EAN-13**.
- **„Produse noi"** → produsele importate apar sub filtrul **🆕 Produse noi** (magazin + back-office).
- **Furnizor** → se leagă producătorul/furnizorul din fișier (ex. ULTRA, CRAFTI).
- **Imagini** → dacă fișierul are coloană URL, imaginea se preia pe cartelă.

## 5. Reguli de preț

- Prețul din fișier **înlocuiește** prețul curent (perioadă nouă, la data încărcării).
- Perioadele nu se suprapun — cea veche se închide automat.
- **Verifică maparea prețurilor** la pasul *Analizează*: prețul de **raft** trebuie să vină din
  coloana „Retail / Розничная", nu din „ANGRO". (La fișiere cu ambele, asigură-te că antetul e clar.)

## 6. Probleme frecvente

| Problemă | Cauză | Soluție |
|---|---|---|
| „Fără articol" pentru toate rândurile | Fișierul n-are coloana Articol | Re-exportă fișierul cu coloana Articol |
| Multe „Ambigue" | Un articol duce la mai multe produse (variante/duplicate) | Se sar automat; rezolvă duplicatele separat |
| Prețul afișat = ANGRO, nu retail | Coloana retail neclară sau articol ambiguu | Verifică antetul „Retail"; pentru ambigue — dedup |
| Apar „?" în denumiri | Diacritice românești (baza nu are ș/ț) | Sistemul le convertește automat (s/t); re-încarcă |
| Categoriile noi nu apar în arbore | Produsele nu erau în tabelul-feed | Rezolvat — importul scrie automat în `BIRO26_GOODS` |

## 7. După import — verificare

- **Marfă / Stoc** → caută articolul; verifică Grupa, Categoria, Producătorul, prețurile.
- **Grupe de marfă** (panoul din stânga) → categoriile noi apar cu numărul de produse.
- Filtrul **🆕 Produse noi** → arată tot ce ai importat.

---

## 8. Pentru administrator (rulare directă, opțional)

Importul e disponibil și din SQL (același motor ca GUI-ul):
```sql
SET SERVEROUTPUT ON
-- analiză (dry-run):
BEGIN BIRO26PT_importData.import_file(p_load_id => :N, p_commit => FALSE); END;
/
-- import real:
BEGIN BIRO26PT_importData.import_file(p_load_id => :N, p_grupa => NULL, p_commit => TRUE); END;
/
```
Încărcarea fișierului în stagin: `python3 biro26pt_loader.py <mapă_sau_fișier>`.

Detalii tehnice complete: `GHID_IMPORT_ALTE_SCHEME.md`, `BIRO26PT_IMPORTDATA.md`,
`BIRO26PT_WEB_INTERFACE_SPEC.md`.

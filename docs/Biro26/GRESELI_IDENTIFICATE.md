# Greșeli identificate la import — catalog complet

> Fiecare intrare: **cum se manifestă**, **de ce se întâmplă**, **cum se verifică** și
> **ce s-a făcut**. Ordonate după cât de tăcut e eșecul — cele de sus nu dau nicio eroare
> și de aceea sunt cele mai scumpe.
>
> Detaliile complete: `GHID_IMPORT_ALTE_SCHEME.md` §9.x (referința e la fiecare intrare).

---

## Tabelul de sinteză

| # | Greșeala | Se manifestă | Cost real | §  |
|---|---|---|---|---|
| 1 | Grupă > 25 caractere | preț lipsă în lista de prețuri | **4 490 produse** | 9.29 |
| 2 | Articol scurt/numeric | potriviri false, marfă nelegată | **629 cartele** | 9.22 |
| 3 | Antet suprascris cu valori | coloană nedetectată, fără preț | **4 108 produse** | 9.28 |
| 4 | Virgulă zecimală | preț necitibil | **474 + 6 600** | 9.19, 9.29 |
| 5 | Coloană peste limita de 16 | imagini/descrieri pierdute | tot setul 11 | 9.21 |
| 6 | Antet nu pe primul rând | nicio coloană detectată | tot setul 11 | 9.21 |
| 7 | Sursă fără HTTPS | imagini invizibile în magazin | 2 324 produse | 9.27 |
| 8 | Stub „fără imagine" | poză falsă, filtrele nu-l găsesc | 319 produse | 9.27 |
| 9 | ANGRO tratat ca IGNORE | preț de achiziție neimportat | tot setul 10 | 9.20 |
| 10 | `price_retail` care nu e retail | marfă vândută la preț de achiziție | evitat la timp | 9.24 |
| 11 | Mapare manuală ștearsă | operatorul nu putea corecta nimic | funcție inutilizabilă | 9.28 |
| 12 | Import necorelat cu sursa | nu se știa de unde vine cartela | tot catalogul | 9.25 |
| 13 | Cod de bare duplicat în fișier | **importul se oprește** cu ORA-20000 | setul 13 | 9.30 |
| 14 | Pază pe „zero", nu pe proporție | 26 coduri din 8 655 nu declanșau paza | setul 13 | 9.30 |
| 15 | Entități HTML nedecodate | `Tablets &amp; Phones` în catalog | 178 rânduri | 9.30 |
| 16 | Potriviri fără index | analiză de **25+ minute** | setul 13 | 9.30 |

---

## 1. Grupă mai lungă de 25 de caractere → prețul se pierde

**Se manifestă:** produsul are preț în feed (`BIRO26_GOODS.RETAIL1`), dar niciun rând
valabil în lista de prețuri. În magazin apare fără preț.

**De ce:** `VPR01M_GROUPS.GRPNAME` are maximum 25 de caractere, de aceea stagingul ține
`GRUPA` (complet, până la 60) și `GRUPA_PRET` (trunchiat). Grupele se creau din cea
trunchiată, dar prețurile se legau pe numele **complet** — `JOIN ... vg.grpname = s.grupa`.
Sub 25 cele două coincid și totul merge; peste 25, JOIN-ul nu găsește nimic și
`INSERT ... SELECT` inserează **zero rânduri, fără eroare**.

**Verificare:**
```sql
SELECT COUNT(*) FROM biro26_goods g
 WHERE g.retail1 IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM tpr1d_perprlist p
                    WHERE p.sc = g.cod_univers AND p.dataend >= TRUNC(SYSDATE));
```

**Rezolvat:** JOIN pe `s.grupa_pret`; 4 490 de prețuri recuperate; verificarea de mai sus
rulează acum **automat la fiecare import** și avertizează în raport.

## 2. Articol scurt sau pur numeric → potriviri false

**Se manifestă:** prețuri și imagini aterizează pe produse complet nelegate.
„Joc de masă *Octopus Party*" s-a potrivit cu „Carnet A6 40 foi".

**De ce:** coduri ca `248`, `670`, `2917` înseamnă produs diferit la fiecare furnizor.

**Rezolvat:** prefixare — brand → prefixul sursei: `TREFL-2080`, `OS-1841`. Efect măsurat
pe același furnizor: potriviri cu nume complet diferit **643 → 21** (și acelea corecte).

## 3. Antet suprascris cu valori

**Se manifestă:** o coloană întreagă nu e detectată; produsele intră fără preț.

**De ce:** cineva a tras cu mouse-ul peste celulele de antet. `Price Online` devine `43,50`.
La PRINTERRA — pe **4 din 6 foi**.

**Verificare:** deschideți antetul **fiecărei** foi, nu doar al primei.

**Rezolvat:** mapare manuală în back-office (algoritm `MANUAL_MAP`).

## 4. Virgulă zecimală și formate mixte

**Se manifestă:** prețul nu se scrie, fără eroare.

**De ce:** aceeași coloană poate conține trei formate: `10,00`, `1.169,00` (european) și
`2,071.00` (anglo-saxon).

**Regula sigură:** **ultimul separator este cel zecimal**, celălalt e de mii.

**Rezolvat:** normalizare unică (`norm_txt`) pentru toate coloanele de preț; 25 457 de
valori din feed normalizate retroactiv. Operația păstrează valoarea.

## 5–6. Fișiere largi și antet care nu e pe primul rând

Stagingul avea 16 coloane — un export de site are 25–29, iar imaginile și descrierile
cădeau în afară. Extins la 32. Unele exporturi pun pe rândul 1 un titlu, antetul fiind pe
rândul 2 — acum antetul e primul rând cu cel puțin 3 celule completate.

## 7–8. Imagini

**Sursă fără HTTPS:** impreso.md nu ascultă pe 443. Browserul blochează `http://` pe pagină
https. Rezolvat cu proxy (listă albă, fără redirectări, doar `image/*`, limită 8 MB).

**Stub „fără imagine":** `noimage_b.jpg` e un JPEG **real** de 57 KB. Importat ca poză
validă, produsul *pare* că are imagine — mai rău decât lipsa ei. Acum se filtrează.

## 9–10. Prețuri interpretate greșit

**ANGRO era mapat pe `IGNORE`** pentru varianta „cu TVA" — dar în OfficePlus ANGRO **este**
cu TVA. Prețul de achiziție nu se importa deloc.

**`price_retail` dintr-un export B2B nu era prețul de raft** — la multe rânduri identic cu
angro. Importat ca retail, ar fi pus marfa la vânzare **la prețul de achiziție**; regula
„nu coborâm prețul" ar fi mascat problema pe marfa existentă, vizibilă abia în marjă.

**Regula:** nu vă încredeți în numele coloanei. Comparați-o cu prețul curent pe câteva sute
de rânduri: dacă al nostru e sistematic mai mare, coloana nu e prețul de raft.

## 11. Maparea manuală se ștergea singură

Tabelul exista în interfață, dar `detect_columns` începea cu un `DELETE` fără condiție —
orice reanaliză arunca ce corectase operatorul, iar analiza se reface la fiecare import.
Deci funcția **nu a fost niciodată utilizabilă**. Acum se șterg doar mapările automate.

## 12. Nu se știa de unde vine marfa

Fără marcaj de sursă nu se putea răspunde la „de unde a apărut cartela asta?". Rezolvat cu
`TMS_MPT_IMPSRC` (sursă, rulare, rândul exact din fișier), `YBIRO_IMPORT_LOG` (jurnalul) și
`YBIRO_IMPORT_GROUPS` + fișierele de grupe cu script de anulare.

## 13. Cod de bare duplicat in acelasi fisier -> importul se opreste

**Se manifesta:** `ORA-20000: Produsul cu acest cod de bare a fost deja adaugat` si importul
se opreste la jumatate — o parte din marfa e creata, restul nu.

**De ce:** un trigger nativ (`TMS_MPT_BARCODE$TR$UNIQ_BAR`) impune unicitatea codurilor.
Exista deja o paza impotriva codurilor prezente in catalog, dar **nu** impotriva celor
repetate in interiorul aceluiasi fisier: al doilea rand cu acelasi cod il loveste pe primul,
inserat cu o clipa inainte.

**Rezolvat:** deduplicare in lot (`ROW_NUMBER() OVER (PARTITION BY barcode)`) plus
verificare si in `TMS_MPT_BARCODE`, nu doar in `TMS_BARCODE_UNIQ`.

> **Lectie de proiectare:** o paza care verifica doar starea *dinainte* de operatie e
> incompleta. Intr-un `INSERT ... SELECT`, randurile se vad intre ele.

## 14. Paza anti-dubluri verifica "zero", nu o proportie

Fisierul bestbuy avea **26 de coduri de bare din 8 655 de randuri** (0,3%) — practic niciunul.
Paza n-a spus nimic, pentru ca testa `= 0`. Acum pragul e o **proportie** (`g_min_bc_ratio`,
implicit 5%): sub ea, coloana e considerata inutilizabila ca cheie.

> **Regula generala:** pragurile pe "exact zero" se ocolesc singure. Un singur rand completat
> dintr-o mie dezarmeaza paza fara sa aduca vreun beneficiu.

## 15. Entitati HTML nedecodate

**Se manifesta:** in catalog apar `Tablets &amp; Phones`, `children&#8217;s camera`,
`USB &#8212; (16GB)`.

**De ce:** exporturile de site pastreaza entitatile HTML din pagina. Nimeni nu le decodeaza,
iar ele ajung in denumire **si in numele grupei** — deci si in arborele magazinului.

**Rezolvat:** decodare (`html.unescape`) in loader, **inainte** de transliterare, ca rezultatul
sa treaca apoi prin filtrul cp1251. Reparate retroactiv 178 de randuri.

Ordinea conteaza: daca decodezi *dupa* transliterare, `&#8212;` a devenit deja text inofensiv
si ramane asa pentru totdeauna.

## 16. Potriviri fara index -> analiza devine imposibila

**Se manifesta:** dry-run-ul unui fisier de 8 655 de randuri rula de peste **25 de minute**
fara sa se termine.

**De ce:** pazele compara `UPPER(TRIM(denumirea))` si articolul normalizat pentru fiecare
rand. Fara indecsi pe aceste **expresii**, fiecare rand scaneaza integral `TMS_UNIVERS`
(~460 000 de randuri). 8 655 x scanare completa.

**Rezolvat:** doi indecsi functionali, creati in sub o secunda fiecare:

```sql
CREATE INDEX TMS_UNIVERS_UP_DENUMIREA  ON tms_univers (UPPER(TRIM(denumirea)));
CREATE INDEX TMS_UNIVERS_NORM_CODVECHI ON tms_univers
       (REPLACE(REPLACE(UPPER(codvechi),' ',''),'.',''));
```

Rezultat: de la 25+ minute la **sub un minut**.

> **Regula:** daca o paza compara o **expresie** (nu coloana bruta), are nevoie de un index
> pe exact acea expresie. Altfel functioneaza la fisiere mici si devine inutilizabila exact
> cand ai nevoie de ea.

---

## Lista de verificare, după orice import

1. **Preț în lista de prețuri**, nu doar în feed (§1) — rulează automat, dar citiți raportul.
2. Fiecare coloană de preț e mapată? La fișiere cu mai multe foi — pe **fiecare** foaie.
3. Câte poziții noi vs existente? Un salt neașteptat de „noi" înseamnă potriviri ratate.
4. Potrivirile au nume asemănătoare? Diferență mare de nume = articol care se ciocnește.
5. Imaginile: se servesc pe https? există un URL-stub repetat la sute de produse?
6. Grupele noi: sunt marcate `CREATED` sau `EXISTING`? Numai primele se pot anula.

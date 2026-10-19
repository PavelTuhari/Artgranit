# Ghidul back-office-ului OfficePlus — pe fiecare meniu

> Pentru operatorul care lucrează zilnic în **Back-office**
> (`https://officeplus.md/UNA.md/orasldev/biro26-backoffice`).
> Fiecare secțiune de mai jos = o filă din meniul de sus. Butonul **?** de
> lângă titlul filei deschide direct secțiunea ei de aici.
>
> Verificat pe sistemul real la **05.09.2026** (Oracle 11.2.0.4, profil `default`).
> Cifrele din text sunt cele văzute atunci — la tine vor fi altele, ordinea de
> mărime rămâne.

---

## Cum e construit ecranul

![Bara de sus și filele](/static/biro26/docs/backoffice/01_sursa.png)

| Element | Ce face |
|---|---|
| **B26 · OfficePlus — Back-office** | titlul; lângă el — **Profil activ: default** (profilul de mapare folosit de toate importurile, vezi *Mapare / Setări*) |
| **🛒 Coș (n)** | coșul de comandă al back-office-ului: din *Nomenclator*, *Marfă / Stoc* și *Stoc (calcul)* pui cantități în coloana **Comandă**, apeși **În coș (selectate)**, iar din coș faci **Creează cont de plată** sau copiezi CSV / XML |
| **RU · RO · EN** | limba interfeței; se ține minte în browser |
| **← OfficePlus** | înapoi la panoul modulului |
| bara albastră de jos | starea ultimei operații (*Finalizat*, *Eroare*) și fila curentă |

Toate tabelele au un rând de **filtre sub antet** (🔍 în fiecare coloană) și
sortare la clic pe antet. Filtrele din bara de sus (Brand, Furnizor, Status…)
merg la server; cele din antet filtrează ce e deja pe ecran.

**Regula de aur:** butoanele **albastre** din rândul de acțiuni scriu în ERP-ul
live. Fiecare cere confirmare. Butoanele **roșii** (Arhivare, Anulează lista)
șterg sau dezactivează — citește dialogul înainte de OK.

---

<a id="sursa"></a>
## 1. Sursă — marfa venită de la furnizori (`BIRO26_GOODS`)

![Sursă](/static/biro26/docs/backoffice/01_sursa.png)

**Ce este.** Tabelul-tampon în care ajunge tot ce s-a încărcat din fișierele
furnizorilor (ULTRA, Crafti, Biblion, Birolux…). Nimic de aici nu e încă în
catalog — este „sala de așteptare". La 05.09.2026: **231 814 rânduri**,
**6 965 branduri**.

**Filtre:** căutare după denumire / articol, **Brand**, **Furnizor** (cu numărul
de rânduri în paranteză), **Status**:

| Status | Înseamnă |
|---|---|
| **Nou** | rândul nu are încă un cod în nomenclator |
| **În dicționar** | rândul a primit `COD_UNIVERS` — marfa există în catalog |
| **Conflict** | același articol duce la mai multe mărfuri; se rezolvă manual |

Grila arată 300 de rânduri odată (foto, articol, denumire, brand, furnizor,
prețurile *Angro / Online / Retail*, stoc, cod univers, status).

**Acțiuni (în ordinea în care se folosesc):**

1. **Validare** — *nu scrie nimic*. Verifică fișierul-sursă și scrie un raport
   în panoul de sub butoane. Exemplu real din 05.09.2026:

   ```
   Total randuri: 231814
   Denumire goala (blocheaza insert): 1
   Articol > 20 (se trunchiaza): 248
   Denumire > 160 (se trunchiaza): 4871
   Brand gol: 122272
   Fara cheie COD_UNIVERS: 34437
   Pret RETAIL1 neconvertibil: 0
   ```
   Citește-l așa: *„blochează"* = rândul nu va intra deloc; *„se trunchiază"* =
   intră, dar tăiat la lungimea din profil (20 / 160 caractere);
   *„fără cheie"* = câte rânduri sunt încă **Nou**.
2. **Pregătire** — curăță datele (spații, caractere confundabile, prețuri ca
   text → număr) conform profilului activ. Scrie în tabelul-sursă.
3. **Atribuie chei** — dă `COD_UNIVERS` rândurilor **Nou** (după articol, prin
   secvența `ID_TMS_UNIVERS`). După ea statusul devine *În dicționar* și marfa
   poate fi importată din fila *Nomenclator*.

> Dacă *Validare* arată multe „Denumire goală" sau prețuri neconvertibile —
> oprește-te și repară fișierul; nu are rost să pregătești date stricate.

---

<a id="nomenclator"></a>
## 2. Nomenclator — catalogul ERP (`TMS_UNIVERS`)

![Nomenclator](/static/biro26/docs/backoffice/02_nomenclator.png)

**Ce este.** Catalogul adevărat al firmei, cel după care lucrează contabilitatea,
depozitul și magazinul online. Aici marfa are **Cod UNA.Univers** (cheia
permanentă), **Cod vechi** (articolul furnizorului), denumire, grupă (`gr1`,
de regulă `TVR`), unitate de măsură și semnul *Arhivat*.

**Filtre:** căutare după denumire / articol / **cod de bare**, grupă `gr1`,
**Arhivă: Active / Arhivate**.

**Fișa produsului.** Clic pe un rând → în dreapta apare **Fișă produs**:
codurile de bare, apoi toate câmpurile din `TMS_UNIVERS` și `TMS_MPT`
(cartela contabilă: TVA, producător `DEP_PRODUCER`, coeficienți…). Este
vizualizare, nu editare — editarea se face din *Marfă / Stoc*.

![Fișa produsului](/static/biro26/docs/backoffice/02b_fisa_produs.png)

**Acțiuni:**

| Buton | Ce face | Atenție |
|---|---|---|
| **Import nomenclator** | ia din *Sursă* rândurile cu cheie și le creează / actualizează în `TMS_UNIVERS` + `TMS_MPT` (după profilul activ: `um=buc.`, `gr1=TVR`, `tip=P`, `codtva=A`…) | operație pe ERP live; rulează întâi *Validare* în *Sursă* |
| **Arhivare** (roșu) | pune `ISARHIV=1` la pozițiile bifate — marfa dispare din magazin și din listele active, dar rămâne în istoric | ireversibil din interfață; se vede apoi cu filtrul *Arhivate* |
| **Corectează confundabile** | înlocuiește literele chirilice strecurate în articole latine (`С`→`C`, `О`→`O`, cel mult `confus_max_cyr=3` pe cod) | modifică `CODVECHI`; util după importuri din fișiere rusești |
| **În coș (selectate)** | pune în coș rândurile cu cantitate în coloana *Comandă* | — |

---

<a id="grupe"></a>
## 3. Grupe / Furnizori

![Grupe / Furnizori](/static/biro26/docs/backoffice/03_grupe.png)

**Ce este.** Patru liste de referință pe un ecran:

1. **Grupele listei de prețuri** (sus) — pentru **Cod preț** ales (implicit `1`
   = lista *BIRO*). La 05.09.2026: **126 grupe**. Coloane: cod preț, cod grupă,
   denumire (editabilă), *Tip SC* (`P` = produse), *Grupă SC*. Butonul
   **Salvează** pe rând scrie denumirea.
2. **Furnizori (nomenclator)** — contrapărțile din `TMS_UNIVERS` cu tip
   furnizor (17 la data verificării), cu căutare.
3. **Furnizori (din flux)** — brandurile / producătorii așa cum apar în *Sursă*,
   cu numărul de rânduri fiecare (6 965). Aici vezi dacă un furnizor a venit cu
   nume scris în două feluri (`ULTRA` și `Ultra`).
4. **Categorii** — rădăcinile arborelui (`DEPOZIT`, `Cheltuieli`…) cu tipul lor.

**Acțiuni:**

- **Import grupe** — creează în lista de prețuri câte o grupă pentru fiecare
  brand nou din *Sursă* (`group ← brand` din mapare). Se face **înainte** de
  *Import prețuri*, altfel prețurile n-au unde intra.
- **Îmbinare grupe** — mută toate prețurile din *grupa sursă* în *grupa
  destinație* și șterge grupa sursă goală (o singură tranzacție). Folosită
  exact pentru dublurile de mai sus: `Ultra (161)` → `ULTRA (705)`.

---

<a id="preturi"></a>
## 4. Listă de prețuri

![Listă de prețuri](/static/biro26/docs/backoffice/04_preturi.png)

**Ce este.** Prețurile de vânzare din ERP (`TPR1D_PERPRLIST`), pe **perioade**.
Ecranul este master-detail, ca în Windows: stânga sus — **listele de prețuri**
(`0 SOCIALE`, `1 BIRO`), stânga jos — **grupele** listei alese (127 cu *Toate*),
dreapta — pozițiile grupei: cod grupă, cod univers, denumire, **data start**,
`PRETV` (retail), `PRETV1` (angro), `PRETV2` (online). Fiecare rând se poate
edita direct în grilă și salva cu **Salvează**. Grila se încarcă pe măsură ce
derulezi (câte 200).

Jos, pliabil, **Perioade** — toate datele de start înregistrate pentru lista
aleasă (1 205 la verificare) cu numărul documentului.

**Acțiuni din bara de sus, de la stânga la dreapta:**

| Buton | Ce face |
|---|---|
| **Import grupe** | același ca în fila *Grupe* — pentru comoditate |
| **Import date** (+ câmp dată) | creează perioada de preț la data aleasă (implicit azi) pentru toate grupele listei; fără ea *Import prețuri* nu are unde scrie |
| **Import prețuri** (+ *Data de la / până la*) | ia `RETAIL1 / ANGRO / IONLINE` din *Sursă* și le scrie ca `PRETV / PRETV1 / PRETV2` în perioada dată |
| ☑ **Doar în baza Articolelor** | **pornit implicit.** Prețul ajunge doar la marfa al cărei *Articol* din ERP coincide cu cel din sursă; oprit — se potrivește și după `COD_UNIVERS`. Setarea se ține în `YBIRO_SETTINGS.PRICE_UPDATE_BY_ARTICLE` |
| **Anulează lista** (roșu) | **șterge** prețurile importate pentru codul de preț curent — dialogul te avertizează cu majuscule. Este butonul „am importat greșit, dă înapoi" |

**Ordinea corectă a unei reîmprospătări de prețuri:**
*Sursă → Validare → Pregătire → Atribuie chei* → *Grupe → Import grupe* →
*Prețuri → Import date → Import prețuri* → verificare în *Marfă / Stoc*.

---

<a id="mapare"></a>
## 5. Mapare / Setări

![Mapare / Setări](/static/biro26/docs/backoffice/05_mapare.png)

**Conexiune Oracle → Testează conexiunea.** Răspunsul bun arată așa:
`✓ Oracle Database 11g Enterprise Edition Release 11.2.0.4.0 - 64bit Production`.
Dacă apare eroare, nimic din back-office nu va merge — anunță administratorul
(VPN-ul spre server sau parola de la baza OfficePlus).

**Profiluri de mapare.** Un profil spune importului *de unde* ia fiecare câmp și
*cu ce constante* creează marfa. Cel marcat ★ este **implicit** și e cel din bara
de sus. **Vizualizare** deschide profilul în dreapta:

![Profilul default](/static/biro26/docs/backoffice/05b_profil.png)

| Grup | Câmpuri (valorile profilului `default`) |
|---|---|
| **Identificatori** | `tbl_goods=BIRO26_GOODS`, `col_key=COD_UNIVERS`, `col_articol=ARTICOL`, `col_denumire=DENUMIRE`, `col_retail=RETAIL1`, `col_angro=ANGRO`, `col_ionline=IONLINE`, `col_brand=BRAND`, `seq_key=ID_TMS_UNIVERS` |
| **Constante** | `codprice=1`, `um=buc.`, `gr1=TVR`, `tip=P`, `caccess=11100`, `codtva=A`, `date_start=2026-01-01`, `date_end=3000-01-01`, `group_type=P`, `empty_brand=NULL`, `len_codvechi=20`, `len_denumire=160`, `isarhiv_arc=1`, `isarhiv_lock=2`, `confus_max_cyr=3` |

**Profil nou** cere un nume și un cod de preț, copiază valorile implicite și îl
poți edita, apoi **Activează**. Se folosește când vine o sursă cu altă structură
sau o listă de prețuri separată (de ex. `SOCIALE`, `codprice=0`).

> Nu schimba `len_codvechi` / `len_denumire` „ca să nu se mai trunchieze":
> sunt lungimile coloanelor din baza ERP, nu preferințe.

---

<a id="import"></a>
## 6. Import (asistent) — în 4 pași, pentru o sursă SQL

![Pasul 1 — Sursă](/static/biro26/docs/backoffice/06_import_pas1.png)

**Ce este.** Asistentul leagă cele patru file de mai sus într-un fir ghidat,
pentru o **sursă din baza de date** (implicit `BIRO26_GOODS`: 32 coloane, 10
rânduri-mostră). Pașii se văd în stepper-ul de sus.

1. **Sursă** — alegi sursa. Pliabil, **Sursă nouă (SELECT)**: poți defini o
   sursă proprie dintr-un `SELECT` (nume + interogare), cu **AI: descriere** (scrie
   descrierea Markdown a coloanelor) și **AI: mapare** (propune maparea). Dacă
   serviciul AI lipsește, se folosește euristica — apare mesajul *AI indisponibil*.
   **Salvează sursa** o pune în listă.
2. **Mapare** — tabel *Câmp țintă ← Coloană sursă* cu exemple reale:

   ![Pasul 2 — Mapare](/static/biro26/docs/backoffice/06b_import_pas2.png)

   | Câmp țintă | Coloana sursă | Exemplu |
   |---|---|---|
   | `COD_UNIVERS (key)` | COD_UNIVERS | 162324, 162325 |
   | `CODVECHI ← articol` | ARTICOL | 11-012S, 11-009 |
   | `DENUMIREA ← denumire` | DENUMIRE | Ace de siguranta bold… |
   | `PRETV ← retail` | RETAIL1 | 8.00 |
   | `PRETV1 ← angro` | ANGRO | 5.56 |
   | `PRETV2 ← ionline` | IONLINE | 10.74 |
   | `group ← brand` | BRAND | Birolux-MT |

   Schimbi coloana din listă și **Înainte** salvează maparea în profilul activ.
3. **Verificare** — **Rulează validarea** = aceeași *Validare* din *Sursă*.
4. **Import** — **Importă nomenclatorul** (= *Import nomenclator*) și
   **Importă imaginile** (ia `PHOTO_URL` din sursă și îl pune pe cartela
   mărfii, `TMS_MPT_TVR.IE_LINKADRES`).

**Nu confunda cu încărcarea de fișiere.** Fișierele Excel / CSV de la furnizor
se încarcă pe pagina separată **Import fișiere (PT)** —
`/UNA.md/orasldev/biro26-import-pt` — în 3 pași (*Fișiere → Analiză dry-run →
Import*), descriși în [Instrucțiune: încărcarea datelor](INSTRUCTIUNE_INCARCARE_DATE.md).
Acea pagină scrie și în `BIRO26_GOODS`, deci după ea marfa apare aici, în *Sursă*.

![Import fișiere (PT)](/static/biro26/docs/backoffice/10_import_fisiere.png)

---

<a id="marfa"></a>
## 7. Marfă / Stoc — ecranul de lucru zilnic

![Marfă / Stoc](/static/biro26/docs/backoffice/07_marfa_stoc.png)

**Ce este.** Tot catalogul (**154 098** produse la verificare) cu prețurile și
stocul, într-o grilă de tip Excel, condusă de **arborele de grupe** din stânga
(143 grupe cu numărul de produse: *Accesorii IT 2977*, *Carti educationale
39805*…). Clic pe o grupă → grila arată doar produsele ei; **Toate produsele**
revine la tot.

**Bara de filtre:** căutare (denumire / articol / cod de bare), **Brand**,
☑ **🆕 Doar produse noi** (ce a intrat prin ultimele importuri), ☑ **Vizualizare
marfă dezactivată** (`ISARHIV=2`), **Prețuri la data** (grila arată prețurile
valabile la data aleasă — implicit azi), **Resetează filtrele**, **În coș
(selectate)**. **Constantă (dacă nu există stoc)** = cantitatea afișată pentru
marfa fără sold calculat (implicit `1000`); se ține minte în browser.

**Coloanele grilei:** Cod UNA.Univers · Foto · Articol · Cod de bare · Denumire
(cu eticheta **NOU**) · Grupă vamală · Grupă marfă · U.M. · **Cant.** ·
Achiziție fără TVA · Achiziție cu TVA · Preț online · Retail cu TVA ·
Producător · Cotă TVA % · Comandă. Sub antet — 🔍 filtre pe fiecare coloană.
Se încarcă pe măsură ce derulezi (câte 100).

**Ce poți face pe un rând:**

- **clic pe rând** → se deschide **Fișa produs** (coduri de bare, atributele web
  RO / RU / EN cu **💾 Salvează (limba curentă)**, comentariile clienților,
  toate câmpurile ERP) *și* jos se umple **Istoric prețuri**;
- **✎** → editează atributele (denumire, coduri de bare — *cod de bare nou* —,
  link imagine);
- **🗑** → dezactivează marfa (`ISARHIV=2`, soft-delete; se vede apoi cu filtrul
  *Vizualizare marfă dezactivată*).

![Rând deschis: fișa + istoricul prețurilor](/static/biro26/docs/backoffice/07b_marfa_rind.png)

**Istoric prețuri** (panoul de jos). Perioadele produsului: *De la / Până la /
Retail / Achiziție / Online*. Regulile, exact cum le aplică sistemul:
modificarea prețului **divizează** perioada la data aleasă; **Șterge perioada**
unește perioadele vecine, ca să nu rămână goluri; ultimul rând nu se poate
șterge. Exemplu real: `23.08.2026 → 01.01.3000 · 1139 lei`.

**Arborele de grupe.** Creionul **✎** de lângă o grupă: **Redenumește** sau
**Mută în altă grupă** — sistemul spune câte poziții vor fi modificate și cere
confirmare.

---

<a id="stoc"></a>
## 8. Stoc (calcul) — soldul real din contabilitate

![Stoc (calcul)](/static/biro26/docs/backoffice/08_stoc_calcul.png)

**Ce este.** Cantitățile din grila *Marfă / Stoc* vin din **ultimul calcul**
făcut aici. Calculul întreabă ERP-ul (`UN$SOLD.GET_SOLDT`) pe conturile de
marfă **217, 2165, 2114**, la o dată și, opțional, pe un departament.

**Câmpuri:** *Data document* (gol = azi), *Departament (m_ctdep)* (gol = toate),
*Conturi (pCont)* (implicit `217 2165 2114` — nu le schimba fără contabil).
**Calculează stocul** cere confirmare („interoghează ERP-ul live") și poate
dura câteva minute pe tot catalogul. Lângă buton se vede ultima rulare:
`Ultimul calcul: 18.08.2026 21:37 — 18.08.2026 / dep="" — 4114 cant.`

**Rezultatul ultimului calcul** — tabel *Cod univers / Denumire / Cant. /
Comandă* (primele 300), de unde poți pune direct în coș.

> Marfa care nu apare în rezultat primește în grilă **Constanta** din *Marfă /
> Stoc* (1000), nu zero — ca să nu dispară din magazin marfa neinventariată.
> Dacă vrei ca site-ul să arate solduri reale, calculul trebuie rulat regulat
> (după recepții și după facturile expediate).

---

<a id="servicii"></a>
## 9. Servicii — funcții de întreținere

![Servicii](/static/biro26/docs/backoffice/09_servicii.png)

**Ce este.** O listă de operațiuni de întreținere a datelor, fiecare cu
descriere, numărul de rânduri (se numără separat, ca lista să apară imediat) și
butonul **Descarcă** (CSV). **Reîmprospătează** recitește lista.

Lista **nu e în cod** — vine din tabelul `YBIRO_SERVICE_FUNCTIONS`: o funcție
nouă = o înregistrare cu un `SELECT`, fără programare (cum se adaugă —
[Diacritice și servicii](DIACRITICE_SI_SERVICII.md), §5). Se execută doar
`SELECT`-uri stocate în bază, niciodată SQL primit din browser.

Funcția existentă la 05.09.2026:

| Funcție | Ce dă | Rânduri |
|---|---|---|
| **Carduri de marfă problematice (diacritice stricate)** | CSV cu marfa al cărei text a fost stricat de codificarea bazei (`car?i`, `?coala`) și care **nu** a putut fi reparată automat (lipsește fișierul-sursă). Se corectează manual sau se reîncarcă fișierul original. | 1 645 |

---

## Probleme frecvente

| Simptom | Cauză probabilă | Ce faci |
|---|---|---|
| Fila arată *Se încarcă...* la nesfârșit | conexiunea Oracle a căzut | *Mapare / Setări → Testează conexiunea*; anunță administratorul |
| *Import prețuri* a trecut, dar prețurile nu s-au schimbat | ☑ *Doar în baza Articolelor* e pornit și articolul din fișier diferă de cel din ERP | verifică *Cod vechi* în *Nomenclator*; sau debifează (atent) opțiunea |
| Prețurile n-au intrat deloc | nu există perioadă la data respectivă | *Import date* înainte de *Import prețuri* |
| Marfa importată nu se vede în magazin | `ISARHIV` setat sau grupa lipsă | *Nomenclator → Arhivate*; *Grupe → Import grupe* |
| Cantitățile sunt toate `1000` | nu s-a rulat *Stoc (calcul)* | rulează calculul |
| `?` în denumiri | textul vechi, stricat de charset | *Servicii → Carduri problematice* → corectează / reîncarcă |
| Am importat greșit prețurile | — | *Listă de prețuri → Anulează lista* (șterge prețurile listei curente) |

## Documente conexe

- [Instrucțiune: încărcarea datelor](INSTRUCTIUNE_INCARCARE_DATE.md) — pagina *Import fișiere (PT)*, pas cu pas
- [Sursele de import](IMPORT_SURSE.md) — ce furnizor vine cu ce prefix de articol
- [Ghidul importului](GHID_IMPORT_ALTE_SCHEME.md) — motorul, capcanele, verificările (tehnic)
- [Marfă & Stoc — dezvoltare](DEV_MARFA_STOC.md) — cum e construită fila 7 (tehnic)
- [Diacritice și servicii](DIACRITICE_SI_SERVICII.md) — registrul funcțiilor din fila 9

---

*Fișiere:* acest ghid — `docs/Biro26/GHID_BACKOFFICE.md`; capturile —
`static/biro26/docs/backoffice/*.png`; butoanele **?** din file —
`static/biro26/backoffice-help.js` (o singură linie `<script>` în
`templates/biro26/backoffice.html`, conform regulii №2 din `CLAUDE.md`).

# Contragenti → una.md: cum intră IDNO în nomenclator și cum se repară înregistrările vechi

Cerința proprietarului (07.09.2026, pagina `biro26-clients`): «la inserarea
înregistrărilor în nomenclator prin utilitarul Contragenti — scrie IDNO în
`TMS_UNIVERS.CODVECHI` și `TMS_ORG.CODFISCAL`; la căutare orientează-te și
după denumirile firmelor care au intrat corect în una.md dar fără cod fiscal
(ex. COD 518172): cînd o caut din nou și apăs, informația trebuie să se
corecteze; și jurnalizează tot lucrul cu Contragenti, ca să poți analiza
întregul lanț și corecta algoritmii».

## Ce era greșit

Înregistrarea rapidă din back-office (`Biro26Journal.client_quick_add` →
`y_ai_BIRO26.register_client`) scria firma **doar** în `TMS_UNIVERS (COD,
DENUMIREA, TIP, GR1)` și fișa în `YBIRO_CLIENT` (cu `IDNO` acolo). Nu se
scria nici `TMS_UNIVERS.CODVECHI`, nici rîndul din `TMS_ORG` — deci în
aplicația nativă una.md («Контрагенты») firma apărea **fără cod fiscal**
(518172, Universitatea de Stat), deși pagina web arăta IDNO-ul. Erau 9 clienți
juridici în situația asta.

## Algoritmul nou — modulul izolat `modules/contragenti/` (prefix `CTG_`)

Un singur punct de intrare pentru orice pagină care primește un card de la
Contragenti: `POST /UNA.md/orasldev/contragenti/api/upsert` (JSON `{xml}` sau
cîmpurile `idno, denumire, adresa, administratori…`).

1. **Cardul** se parsează (`rules.parse_card_xml` / `card_from_fields`), textul
   se aduce la CL8MSWIN1251 (diacriticele → ASCII, chirilicele rămîn), se
   verifică cifra de control a IDNO (doar avertisment în jurnal).
2. **Potrivirea (deduplicarea)**, în ordine:
   1. `TMS_UNIVERS.CODVECHI = IDNO` și `GR1 = 'E'` — înregistrarea ERP de
      referință (convenția una.md: la `GR1='E'` CODVECHI = codul fiscal, cu
      unicitate ținută de triggerul `TRIG_UNIVERS_UNQ_CODVECHI`);
   2. `TMS_ORG.CODFISCAL = IDNO`;
   3. `YBIRO_CLIENT.IDNO = IDNO` — clientul site-ului;
   4. **denumirea normalizată** (`rules.norm_name`: fără diacritice, fără forma
      juridică — SRL / S.R.L. / «Societatea cu Răspundere Limitată» / SA / ÎI…,
      fără ghilimele și punctuație) printre organizațiile `TIP='O'`; o firmă cu
      același nume dar cu **alt** IDNO deja scris nu e considerată aceeași.
3. **Găsit → reparare**, fără să se suprascrie nimic existent:
   - `TMS_UNIVERS.CODVECHI` ← IDNO dacă e gol (+ `NAMERUS` ← denumirea din
     registru dacă e goală); dacă e altul → `conflict` în jurnal;
   - `TMS_ORG`: rînd nou `(COD, CODFISCAL, ADRESS, DIRECTOR)` dacă lipsește;
     dacă există, UPDATE **numai** pe coloanele goale pentru care cardul aduce
     valoare (un UPDATE gol e refuzat de un trigger al bazei — `ORA-20000
     Access denied`);
   - `YBIRO_CLIENT.IDNO` ← IDNO dacă fișa îl are gol.
   Rezultat `repaired` (cu lista a ce s-a completat) sau `unchanged`.
4. **Negăsit → client nou**: `client_quick_add` (aceeași cale ca butonul
   «Adaugă client»), apoi `CODVECHI`, `GR1='E'`, `NAMERUS`, `TMS_ORG` — rezultat
   `created`.
5. Maparea cîmpurilor e cea din `tms_export.map_company` al Contragenti
   (`DENUMIREA` = denumirea scurtă, `NAMERUS` = originalul, `DIRECTOR` = primul
   administrator fără rol, `ADRESS` ≤ 150).

## Pe pagina biro26-clients

După alegerea firmei în Contragenti (calea `fetch /pick` sau `return_to`)
pagina nu mai așteaptă «Adaugă client»: cheamă `api/upsert`, arată rezultatul
(«Înregistrare existentă COMPLETATĂ: COD 518172 … CODVECHI=…, CODFISCAL=…» sau
«Client NOU înregistrat») cu link la jurnal, și reîncarcă lista pe IDNO.
Formularul rămîne completat pentru eventuale corecturi (telefon, e-mail).

## Jurnalul lanțului — `CTG_EVENT_LOG`, pagina `/UNA.md/orasldev/contragenti`

| Pas | De unde | Ce înseamnă |
|---|---|---|
| `search_fallback` | browser | nimic în baza OfficePlus → date.gov.md |
| `pick_start` / `pick_cancel` / `pick_timeout` / `pick_error` | browser | apelul `/pick` la utilitar și ieșirea lui |
| `offline` | browser | API-ul local nu răspunde (s-a arătat scriptul de pornire) |
| `card_received` | server | cardul (payload complet în `PAYLOAD`) |
| `idno_check` | server | IDNO nu trece cifra de control (avertisment) |
| `match_found` / `match_none` | server | după ce s-a potrivit (`codvechi`/`codfiscal`/`yb_idno`/`name`) |
| `apply` | server | `repaired` + ce s-a completat, sau `unchanged` |
| `client_created` | server | client nou (COD) |
| `conflict` | server | codul existent diferă de IDNO-ul din card — nu s-a suprascris |
| `univers_update` / `org_update` / `org_insert` / `client_create` | server | erori Oracle, cu textul lor |
| `backfill` | script | completările în masă / fișele sărite |

Coloane: `TS, USERNAME, PAGE, STEP, Q, IDNO, UNIVERS_COD, RESULT, DETAIL, PAYLOAD`.
Filtrare după IDNO și pagină. Cu jurnalul se vede exact unde s-a pierdut o
informație pe drumul date.gov.md → Contragenti → browser → server → Oracle.

## Completarea celor vechi — `scripts/contragenti_backfill.py`

Trece prin clienții juridici ai site-ului fără `CODVECHI`/`CODFISCAL`
(`--apply` scrie, altfel doar arată), prin aceeași `CtgStore.apply`. Fișele
cu IDNO care nu trece cifra de control (înregistrări de test, ex. «SRL TEST
Casa Operator» 1026602001999) se sar și se notează în jurnal.

Rulat 07.09.2026: 518172 reparat cu cardul real din Contragenti
(CODVECHI = CODFISCAL = 1006600064263, adresa «MUN.CHISINAU, SEC.BUIUCANI
Alexei Mateevici 60»); backfill: 6 firme completate (453495 UNISIM-SOFT,
518168 VISTARCOM, 518169 CONINFO, 518170 EUGENIUS SOFT, 518171 47TH PARALLEL,
301271), 2 sărite (IDNO fals). A doua alegere a aceleiași firme → `unchanged`,
fără dubluri.

## Fișiere

`modules/contragenti/`: `rules.py`, `store.py`, `controller.py`, `routes.py`,
`templates/contragenti_journal.html`, `sql/01_ctg_core.sql`,
`scripts/contragenti_deploy.py`, `scripts/contragenti_backfill.py`,
`sdk/legal_forms.py` (copie MIT din Contragenti — parsarea formei juridice).
Pagina: `static/biro26/clients-gov.js` (`govUpsertXml`, `govUpsertFields`,
`govLog`) + 4 apeluri punctuale în `templates/biro26/clients.html`.
Teste: `tests/test_contragenti.py` (12).

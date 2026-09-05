# CRM (beta) — protocol de testare, 05.09.2026

Executat integral de agent (fără intervenția proprietarului), la cererea
«все сам тестируй, пиши протокол тестирования». Mediu: Mac-ul
proprietarului (Contragenti pornit local din sursele repo-ului, Python 3.12
+ Tk 9.0), Oracle-ul comun OfficePlus 11g, codul raskatat pe
`nufarul.eminescu.md` și `officeplus.md`, ramura `feat/crm`
(ultimul commit include corecția din T-UI-7).

Legendă: **PASS** — rezultatul corespunde așteptării; **NOTĂ** — comportament
corect, dar așteptarea inițială a testului trebuia ajustată; **NEEXECUTAT** —
cu motivul.

## A. Teste automate (fără Oracle) — `pytest tests/test_crm.py`

| # | Test | Rezultat |
|---|---|---|
| A1 | izolare: `app.py` nu menționează modulul | PASS |
| A2 | izolare: `deploy_oracle_objects.py` neatins | PASS |
| A3 | nucleul găsește modulul (`module_keys()` conține `crm`, blueprint `crm`) | PASS |
| A4 | rutele fără prefixul portalului; store folosește doar `Biro26DB` | PASS |
| A5 | manifest: 3 limbi, url, `sql_prefix = CRM_`, pagină `crm.app_page` | PASS |
| A6 | parser XML pe cardul etalon `sample_card.xml` (IDNO, denumire, fondator 100 %, datorie 0,98) | PASS |
| A7 | card cu `founders`/`debts` goale și `lichidata = Da` | PASS |
| A8 | XML gol / `<html>` / fără IDNO / trunchiat → `ValueError` | PASS |
| A9 | cifra de control IDNO (1003600116460 ✓, 1026602001999 ✗) | PASS |
| A10 | card din `return_to` (`status=ok`), refuz la `cancelled`/`timeout` | PASS |
| A11 | preseturi (`today`, `with_address`, necunoscut → toate) și `pick_url` | PASS |
| A12 | DDL: `/` înainte și după fiecare bloc, o comandă per bloc, ASCII, fără `;`/ghilimele în comentarii | PASS |
| A13 | instalatorul propriu țintește `modules/crm/sql` | PASS |
| A14 | pagina: `url_for`, fără adresa portalului în JS, fără `alert/confirm`, preseturi, ștergere în doi pași | PASS |

**15 / 15 PASS** (0,15 s).

## B. Instalare DDL pe Oracle-ul comun — `crm_deploy.py`

| # | Pas | Rezultat |
|---|---|---|
| B1 | 16 comenzi (5 tabele, 4 secvențe, 4 triggere, 3 indecși) | PASS — toate OK |
| B2 | `USER_OBJECTS LIKE 'CRM^_%'` | PASS — TABLE 5, SEQUENCE 4, TRIGGER 4 |
| B3 | reinstalare (idempotență) | PASS — obiectele existente → SKIP |

## C. API-ul modulului, cap-coadă (Flask test client, Oracle real, card REAL de la Contragenti)

Cardul folosit: `GET http://127.0.0.1:9393/card?idno=1003600116460&format=xml`
de la Contragenti-ul real (UNISIM-SOFT, 5 datorii la buget, 1 fondator).

| # | Pas | Așteptat | Rezultat |
|---|---|---|---|
| C1 | `GET api/clients` fără sesiune | 401 | PASS |
| C2 | `GET /` fără sesiune | 302 → `/login?next=…/crm/` | PASS |
| C3 | `GET /` cu sesiune | 200, tema Espo (buton «Creează», preseturi) | PASS |
| C4 | import card real, `src=contragenti` | `added` | PASS |
| C5 | același card | `dup`, același `id` | PASS |
| C6 | același card cu `refresh` | `updated` | PASS |
| C7 | `<html>` în loc de card | 400 + «radacina asteptata <counterparty>» | PASS |
| C8 | `GET api/clients/<id>`: fondatori, datorii, cîmpuri | 1 fondator, 5 datorii, denumire completă | **NOTĂ** — vezi N1 (diacritice) |
| C9 | listă `preset=today&q=UNISIM` | conține clientul | PASS |
| C10 | listă cu filtru inexistent | `[]` | PASS |
| C11 | `POST …/note` | notița se recitește | PASS |
| C12 | `api/stats` | total ≥ 1, today ≥ 1 | PASS |
| C13 | `api/events` | `updated, dup, added` în ordine | **NOTĂ** — vezi N2 |
| C14 | setări POST/GET, cheie necunoscută ignorată | `lang=ru`, `pick_timeout=120`, fără `hacker` | PASS |
| C15 | `api/pick-url?return=1` | `/pick?q=…&lang=ru&timeout=120&return_to=https://nufarul…/contragenti/callback&state=abc` | PASS |
| C16 | `contragenti/callback?status=ok&idno=1012600013725…` | 302 → `/?cb=added:<id>:1012600013725` | PASS |
| C17 | `contragenti/callback?status=cancelled` | 302 → `/?cb=err:Selectia a fost anulata` | PASS |
| C18 | `api/clients/<id>/events` | ≥ 3 evenimente | PASS |
| C19 | `DELETE` → apoi `GET` | 200, apoi 404 | PASS |
| C20 | curățenie (ștergere UNISIM) | 200 | PASS |
| C21 | jurnalul reține ștergerile | `deleted, deleted, …` | PASS |

**19 PASS + 2 NOTE, 0 defecte.** Baza a fost lăsată goală (CRM_CLIENT 0 rînduri;
jurnalul păstrează istoria).

## D. Contragenti real, pornit local (sursele repo-ului, macOS)

| # | Pas | Rezultat |
|---|---|---|
| D1 | `company_search.py --selftest` | PASS — database, i18n, xml export, socket, parsers, una.md mapping |
| D2 | server local `--no-tray --lang ro`; `GET /health` | PASS — `{"status":"ok","version":"1.0","db_count":140}` |
| D3 | `GET /search?q=UNISIM&format=json` | PASS — cardul UNISIM din baza locală |
| D4 | `GET /card?idno=1003600116460&format=xml` | PASS — 200, XML `<counterparty>` (cel folosit la C4) |
| D5 | `GET /card?idno=9999999999999` | PASS — 404 |
| D6 | antet CORS | PASS — `Access-Control-Allow-Origin: *` |
| D7 | `GET /pick?timeout=2` fără alegere | PASS — 504 |
| D8 | `GET /pick?timeout=2&return_to=https://nufarul…/callback&state=t1` | PASS — 302 → `…/callback?status=timeout&state=t1` |
| D9 | calea SDK: `--pick --auto-pick --q UNISIM --out card_pick.xml --no-server --no-tray` | PASS — exit 0, 753 B, XML valid (din cache-ul local, fără portal) |
| D10 | `/pick` cu alegere umană («Returnează contragentul» în fereastra Tk) | **NEEXECUTAT** — accesul la controlul aplicației Python/Tk a fost refuzat în dialogul de permisiuni; fluxul e acoperit de D7–D9 + C4/C16 |

## E. Pagina în browser (Chrome din panoul Claude), cu Contragenti REAL

Pagina e cea din `crm_app.html`, randată cu API-ul CRM simulat (răspunsuri
JSON identice cu cele reale) și **apelurile către Contragenti reale** — ca să
nu se introducă parole în portal din browser.

| # | Pas | Așteptat | Rezultat |
|---|---|---|---|
| E1 | randare: nav 232 px, Acasă/Clienți/…/Setări, bară de sus, tabel, panou «Prezentare generală» | ca Demo CRM | PASS (captură verificată) |
| E2 | indicatorul Contragenti la încărcare | verde + versiune + nr. în bază | PASS — «Contragenti v1.0 · 140 în bază» |
| E3 | click pe client → panoul cu fondatori, datorii, notiță, 3 butoane | | PASS |
| E4 | «Reîmprospătează din Contragenti» | `GET /card` real → `api/import-xml` cu `refresh=true`, mesaj verde «Client actualizat: …» | PASS |
| E5 | «Creează client» cu `pick_timeout=3`, fără alegere | 504 → galben «Timpul de selecție a expirat», după ~3 s | PASS (3,06 s) |
| E6 | «Creează client» cu Contragenti oprit (adresă moartă) | indicator roșu «Contragenti offline», mesaj galben, se deschid Setările | PASS |
| E7 | «Verifică Contragenti» după revenire | verde «Contragenti răspunde» | PASS |
| E8 | comutare limbă RU | «Создать клиента», «Клиенты» | PASS |
| E9 | pagina Setări | adresă, limbă, timeout, «Salvează», «Verifică», legături | PASS (captură) |

Defect găsit și corectat în timpul E4 (T-UI-7): la un răspuns fără `result`
linia de mesaje afișa «undefined:»; acum cade pe «ok». API-ul real întoarce
mereu `result`, deci pe producție nu se manifesta.

## F. Servere

| # | Verificare | Rezultat |
|---|---|---|
| F1 | nufarul: restart, `/login` 200, `/UNA.md/orasldev/crm/` 302 → login, jurnal fără Traceback | PASS |
| F2 | office (192.168.0.250): la fel | PASS |
| F3 | public: `officeplus.md/UNA.md/orasldev/crm/` 302; `api/clients` fără sesiune 401 | PASS |
| F4 | nucleul: `module_loader.as_dict()` → `crm` în `loaded`, `failed = {}` | PASS |
| F5 | `nufarul.eminescu.md/login` după fiecare restart | 200 |

## Note (comportamente de reținut, nu defecte)

- **N1 — diacriticele.** Baza OfficePlus e CL8MSWIN1251: «Ş», «ă», «ţ» se
  păstrează fără diacritice («CENTRUL DE ELABORARE SI IMPLEMENTARE…»,
  «Societate cu raspundere limitata»). Chirilicele se păstrează. Același
  lucru se întîmplă la toate modulele pe această bază (vezi e-Factura).
- **N2 — jurnalul** conține și `import_error` (C7), deci ordinea ultimelor
  evenimente e `import_error, updated, dup, added` — corect.
- **N3 — două baze Contragenti.** `db_count` a alternat 20/140 între apeluri:
  pe Mac rulau două instanțe Contragenti (una a proprietarului, una a
  testului) cu baze diferite; API-ul răspunde de la cea care a prins portul.
  Pe stația contabilului rulează una singură.
- **N4 — dedup doar după IDNO**: cardul din `return_to` (fără fondatori) și
  cel complet din `/card` se referă la același client; «Reîmprospătează»
  completează fondatorii/datoriile (`updated`).

## Concluzie

Modulul e funcțional pe ambele contururi. Singurul pas neexecutat de agent
este alegerea manuală în fereastra Contragenti (D10) — o face proprietarul
pe Windows: portal → CRM (beta) → «Creează client» → în Contragenti se alege
firma și se apasă «Returnează contragentul» → clientul apare în listă cu
mesajul verde «Client adăugat».

---

# Partea a II-a (05.09.2026, după-amiază) — căutarea unică, Contragenti indisponibil, scriptul de pornire

Cerința proprietarului: «căutare și pentru date.gov să fie în baza la
singura celulă de căutare; dacă nu se găsește nimic în baza OfficePlus —
automat pe date.gov.md; dacă s-a închis aplicația pe Mac, butonul vede că
127.0.0.1 nu este disponibil și se descarcă un script Python care pornește
utilitarul — la fel pe Windows și Linux». Plus: «testează tot și documentează
cu screenshoturi».

## G. Ce s-a schimbat

- **O singură căutare** (bara de sus și cîmpul din Clienți): întîi baza
  OfficePlus (`CRM_CLIENT`); dacă nu găsește nimic → mesaj «Nimic în baza
  OfficePlus pentru «…» — caut pe date.gov.md prin Contragenti…» și
  Contragenti se deschide cu acel filtru. Buton separat «🌐 date.gov.md»
  pentru căutarea directă în registru.
- **Contragenti indisponibil**: mesajul spune exact adresa
  («Contragenti (127.0.0.1:9393) nu este disponibil») și apare panoul cu
  scriptul de pornire pentru **macOS (.command)**, **Windows (.bat)**,
  **Linux / orice OS (.py)** — butonul OS-ului curent e evidențiat.
- **Scriptul de pornire** (`modules/crm/launcher.py`, rute
  `/launcher/py|command|bat`, doar biblioteca standard Python): dacă API-ul
  răspunde → doar ridică fereastra; altfel caută instalarea (Mac:
  `/Applications/Contragenti.app`, `~/Projects.AI/DATE.gov/Contragenti`;
  Windows: `Contragenti.exe` din MSI în `%LOCALAPPDATA%`/`Program Files`;
  Linux: `~/Contragenti`, `~/.local/share/contragenti`, `/opt/contragenti`),
  iar dacă nu există o descarcă din GitHub (`git clone` sau zip), face
  `.venv` + `pip install`, pornește utilitarul detașat, așteaptă `/health`
  pînă la 60 s și întoarce browserul în CRM. Același cod în trei ambalaje:
  `.py`; `.command` = bash + `python3 - <<'PYEOF'`; `.bat` = prima linie
  batch `@(python -x "%~f0" || py -3 -x "%~f0") & goto :eof`, restul Python
  (`-x` sare peste prima linie).
- `/Applications/Contragenti.app` pe Mac-ul proprietarului (lansator cu
  icoană; pornește copia din `~/Projects.AI/DATE.gov/Contragenti`, baza cu
  160 de firme; al doilea click doar ridică fereastra).

## H. Teste automate — `pytest tests/test_crm.py`: **18 / 18 PASS**

Noi: H1 cele trei ambalaje ale scriptului sînt Python valid (`ast.parse`),
conțin portul/limba/adresa de revenire și ramurile Darwin/Windows/Linux;
`render("exe")` → `ValueError`. H2 scriptul importă doar biblioteca
standard. H3 pagina are `searchAll` cu `n === 0 && q → createClient(q)`,
panoul offline, cele trei descărcări; ruta `/launcher/<kind>` cu
`Content-Disposition`.

## I. Rutele de descărcare (Flask test client)

| # | Pas | Rezultat |
|---|---|---|
| I1 | `/launcher/command` fără sesiune | 302 → `/login?next=…/crm/` |
| I2 | `/launcher/py` · `/command` · `/bat` cu sesiune | 200, `attachment; filename=start_contragenti.*`, MIME corect, `RETURN_URL = https://nufarul.eminescu.md/UNA.md/orasldev/crm/` |
| I3 | `/launcher/exe` | 404 |

## J. Scriptul de pornire pe viu (macOS, fișierele descărcate din CRM)

| # | Scenariu | Rezultat |
|---|---|---|
| J1 | Contragenti rulează → `python3 start_contragenti.py` | «ruleaza deja — ridic fereastra», apoi deschide CRM-ul în browser |
| J2 | Contragenti **oprit** (`pkill`), `/health` → 000 → `python3 start_contragenti.py` | «Pornesc Contragenti (app): /Applications/Contragenti.app … Contragenti raspunde» în **2,7 s**; `/health` → `db_count 160` |
| J3 | `bash start_contragenti.command` | identic cu J1 (ambalajul macOS funcționează) |
| J4 | `.bat`: prima linie batch, restul rulat cu `python3 -x start_contragenti.bat` | identic cu J1 (mecanismul `-x` funcționează; Windows real rămîne la proprietar) |
| J5 | repetat J2 în timpul capturilor (K6→K7) | Contragenti readus de script, indicatorul redevine verde |

## K. Pagina în browser (Playwright, 1280×800; API CRM simulat cu răspunsurile reale, Contragenti REAL) — capturi în `docs/CRM/testare/`

| # | Pas | Așteptat | Rezultat | Captură |
|---|---|---|---|---|
| K1 | Acasă: plăcuțe + evenimente recente | ca Demo CRM | PASS | `01_acasa.png` |
| K2 | Clienți + panoul clientului (fondatori, datorii, notiță, 3 butoane); indicator «Contragenti v1.0 · 160 în bază» | | PASS | `02_clienti_card.png` |
| K3 | căutare «CONINFO» — există în baza OfficePlus | 1 rînd, fără apel la Contragenti | PASS (`found: 1`) | `03_cautare_in_baza.png` |
| K4 | căutare «GRECU OFFICE GROUP» — nu e în bază | mesaj «Nimic în baza OfficePlus… caut pe date.gov.md» → Contragenti se deschide cu filtrul, pagina așteaptă | PASS (`/pick?q=GRECU%20OFFICE%20GROUP` real, fereastra Contragenti s-a deschis) | `04_fallback_dategov_asteptare.png` |
| K5 | fără alegere în fereastră (`pick_timeout` 8 s) | 504 → galben «Timpul de selecție a expirat» | PASS | `05_fallback_timeout.png` |
| K6 | Contragenti **oprit** → «Creează client» | roșu «Contragenti offline»; mesaj «Contragenti (127.0.0.1:9393) nu este disponibil — …»; panoul cu **macOS .command (evidențiat pe Mac) / Windows .bat / Linux .py** și indicația de lansare | PASS | `06_offline_script_pornire.png` |
| K7 | pornit cu scriptul (J5) → «Verifică Contragenti» | verde «Contragenti răspunde», panoul dispare, «160 în bază» | PASS | `07_online_din_nou.png` |
| K8 | Setări: adresă, limbă, timeout, «Pornirea utilitarului» cu cele trei descărcări, legături | | PASS | `08_setari.png` |
| K9 | interfața în RU | «Создать клиента», «Клиенты» | PASS | `09_interfata_ru.png` |

Consola browserului: doar `favicon.ico 404` (pagina de previzualizare) și
`504` pe `/pick` (așteptat la K5). Fără erori JS.

## L. Servere

nufarul și office repornite fără Traceback; `/UNA.md/orasldev/crm/launcher/py`
fără sesiune → 302 login (nufarul și public officeplus.md); `nufarul.eminescu.md/login` → 200.

## Ce rămîne la proprietar

- Alegerea manuală în fereastra Contragenti («Returnează contragentul») —
  agentul nu are voie să controleze fereastra Tk (permisiune refuzată).
- Proba pe **Windows real** a `start_contragenti.bat` (MSI + `Contragenti.exe`
  sau Python 3) și pe **Linux** a `.py` (`python3-tk`).

---

# Partea a III-a (05.09.2026, seara) — pagina back-office **biro26-clients** (`/UNA.md/orasldev/biro26-clients`)

Proprietarul a precizat că cerința «căutare unică → date.gov.md automat;
Contragenti indisponibil → script de pornire» se referea la **această**
pagină (clienții magazinului din Biro26), unde integrarea veche «lucra prost»:
două celule separate (lista căuta doar în clienții site-ului, fără IDNO;
butonul «Date.gov.md» cerea completarea manuală a formularului), iar la
utilitar oprit se oferea un zip cu `run.sh`.

## M. Ce s-a schimbat (fișiere: `static/biro26/clients-gov.js` nou; `templates/biro26/clients.html` și `models/biro26_oracle_store.py` — edituri punctuale; `modules/crm/routes.py` — `?return=`)

| | Înainte | Acum |
|---|---|---|
| căutarea | doar email / nume / telefon / COD, numai în baza site-ului | **nume / IDNO / email / telefon / COD**; fără rezultate → **automat date.gov.md** prin Contragenti cu același filtru; buton «🏛 date.gov.md» pentru căutare directă |
| rezultatul din registru | completa formularul | completează formularul + mesaj «verificați și apăsați «Adaugă client»» |
| Contragenti oprit | link la un zip + `run.sh` | panou «⚠ **Contragenti (127.0.0.1:9393) nu este disponibil**» cu **macOS .command / Windows .bat / Linux .py** (OS-ul curent evidențiat), «↻ Verifică din nou» care reia automat căutarea |
| utilitarul cade în timpul selecției | se deschidea un popup spre adresa moartă | se verifică `/health`; dacă nu răspunde → același panou |
| scriptul de pornire | — | din modulul CRM: `/UNA.md/orasldev/crm/launcher/<kind>?return=/UNA.md/orasldev/biro26-clients` (revine pe pagina care l-a cerut; doar căi din portal) |

Regula nr. 2: logica e în `clients-gov.js`; în șablonul comun sînt 7 edituri
punctuale (placeholder, buton, `if(!rows.length && q) govAuto(...)`,
`govOffline(msg)`, `pickFromGov(qArg)`, verificarea din `catch`, `<script src>`).
`git log` înainte de editare: ultimele schimbări ale fișierelor erau vechi
(daeec19 / 52a9acc). Pe **office** modelul diferă de `main` (1953 linii, cu
cache) → acolo s-a aplicat **doar linia IDNO**, punctual, cu backup; șablonul
office era identic cu `main` → înlocuit întreg, cu backup. Pe **nufarul**
modelul fusese suprascris din greșeală cu versiunea din `main` (fără cache-ul
vitrinei) — depistat imediat prin `diff` cu backup-ul (366 linii diferență),
**restaurat din backup** și aplicată doar linia IDNO; `site/config` → 200.

## N. Teste automate — `tests/test_biro26_clients_gov.py`: **4 / 4 PASS** (+ `test_crm.py` 18/18)

N1 șablonul apelează fișierul separat, scriptul extern e încărcat înainte de
`load()`, zip-ul vechi a dispărut; N2 `clients-gov.js`: trei OS-uri, ruta
launcher cu `return=`, `node --check`; N3 modelul caută și după IDNO; N4 ruta
launcher acceptă doar căi din portal.

## O. Pagina în browser (Playwright, 1280×800; `/api/biro26/*` simulat cu răspunsurile reale, Contragenti REAL)

| # | Pas | Așteptat | Rezultat | Captură |
|---|---|---|---|---|
| O1 | lista clienților, celula unică de căutare, butonul «🏛 date.gov.md» | | PASS | `10_biro26_clients_lista.png` |
| O2 | căutare după **IDNO** `1026602001837` (e în bază) | 1 client, fără Contragenti | PASS («1 clienți») | `11_biro26_cautare_idno_in_baza.png` |
| O3 | căutare «UNISIM» (nu e în bază) | «Nimic în baza OfficePlus pentru «UNISIM» → date.gov.md: Se deschide utilitarul Contragenti…», fereastra Contragenti se deschide cu filtrul | PASS (`/pick?q=UNISIM` real) | `12_biro26_fallback_dategov.png` |
| O4 | Contragenti **oprit** → aceeași căutare | panou «Contragenti (127.0.0.1:9393) nu este disponibil», trei descărcări cu `return=` pe pagina curentă, macOS evidențiat | PASS | `13_biro26_offline_script.png` |
| O5 | utilitarul repornit cu scriptul (2,7 s) → «↻ Verifică din nou» | «Contragenti activ», căutarea se reia automat pe date.gov.md | PASS | `14_biro26_online_din_nou.png` |

Defect găsit și corectat la O4: dacă utilitarul murea **în timpul** selecției,
pagina veche deschidea un popup spre adresa moartă; acum verifică `/health` și
arată panoul. Consola: doar erorile așteptate (adresa moartă, 504).

## P. Servere

nufarul: login 200, `clients-gov.js` 200, `site/config` 200, jurnal fără
Traceback, model restaurat + IDNO. office: login 200, `clients-gov.js` 200
(și public pe officeplus.md), `site/config` 200, model patch-uit punctual.

## Ce rămîne la proprietar

Proba pe **Windows** a `start_contragenti.bat` și alegerea manuală în fereastra
Contragenti («Vernuti contragentul») — după care formularul se completează și
se apasă «Adaugă client».

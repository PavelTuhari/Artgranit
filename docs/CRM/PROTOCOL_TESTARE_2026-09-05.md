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

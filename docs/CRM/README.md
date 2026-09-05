# CRM (beta) — modulul de clienți integrat cu Contragenti

Creat la 05.09.2026 la cererea proprietarului: «создай новый режим crm и
интегрируй его с github.com/PavelTuhari/Contragenti, а beta версию сделай
такую же как demo sdk crm в Contragenti».

**Beta = replica web a Demo CRM** din repo-ul Contragenti (`crm_delphi/`,
Delphi VCL + SQLite, interfață în stil EspoCRM): navigație stînga 232 px
(Acasă / Clienți / Contacte / Leaduri / Oferte / Calendar / Setări — lucrează
Acasă, Clienți, Setări), bară de sus cu căutare globală și «+», secțiunea
«Clienți» cu butonul albastru **«Creează client»**, preseturi «Toate /
Adăugate azi / Cu adresă juridică» + filtru, tabel cu bife, panoul
«Prezentare generală» (label/value, fondatori, datorii), ștergere în doi
pași, **fără ferestre modale** — toate mesajele în linia de jos, colorată ca
`label-state` EspoCRM. Trei limbi (RO / RU / EN), comutare pe loc.

## Ce face

```
CRM web ──fetch /pick?q=filtru──►  Contragenti (pe PC-ul utilizatorului, port 9393)
                                        │ utilizatorul alege firma în date.gov.md
CRM web ◄──── XML <counterparty> ───────┘
  └─ POST api/import-xml → Oracle CRM_CLIENT + CRM_FOUNDER + CRM_DEBT (dedup IDNO)
```

Trei căi de intrare, toate în același `CrmStore.add_from_card`
(cele trei ieșiri ale Demo CRM: **added / dup / updated**):

1. **`fetch` din browser la API-ul local** al Contragenti (`/pick`, CORS `*`;
   loopback-ul e context sigur și pe pagini HTTPS) → XML → `api/import-xml`.
2. **`return_to`** (browserul nu poate apela API-ul local): `api/pick-url?return=1`
   dă adresa `/pick…&return_to=<callback>&state=`; Contragenti redirecționează
   browserul la `contragenti/callback?status=ok&idno=…`; clientul se adaugă și
   pagina revine cu mesajul în linia de jos.
3. **Import XML** manual (lipit / fișier) — echivalentul
   `ContragentiCRM.exe --import card.xml`; util și fără Contragenti.

«Reîmprospătează din Contragenti» ia `GET /card?idno=&format=xml` din baza
locală a utilitarului și actualizează clientul (fondatori/datorii înlocuite).

## Obiecte Oracle (prefix `CRM_`, baza OfficePlus 11g, prin `Biro26DB`)

| Obiect | Rol |
|---|---|
| `CRM_SETTING` | `contragenti_url` (implicit `http://127.0.0.1:9393`), `lang`, `pick_timeout` |
| `CRM_CLIENT` | cardul: `IDNO` **UNIQUE**, `NAME`, `REG_DATE`, `LEGAL_FORM`, `IS_LIQUIDATED`, `ADDRESS`, `MANAGERS`, `DETAILS_TEXT` (CLOB), `SOURCE`, `SOURCE_UPDATED`, `NOTE`, `CREATED`, `UPDATED` |
| `CRM_FOUNDER` | fondatorii (`NAME`, `SHARE_PCT`), FK cascade |
| `CRM_DEBT` | datoriile la buget (`NR`, `DEBT_TYPE`, `AMOUNT`, `CURRENCY`), FK cascade |
| `CRM_EVENT_LOG` | append-only: `added / dup / updated / deleted / import_error`, sursa (`contragenti / return_to / xml / ui`) |

Corespondența XML → coloane urmează tabela din `INTEGRATION.md` §2 al
Contragenti (dedup **numai după IDNO**, niciodată după denumire).
Instalare: `python modules/crm/scripts/crm_deploy.py` (idempotent, `/` înainte
și după fiecare bloc PL/SQL). Instalat pe Oracle-ul comun la 05.09.2026.

## Rute (montate de nucleu sub `/UNA.md/orasldev/crm`)

| Rută | Ce |
|---|---|
| `GET /` | aplicația (sesiune portal) |
| `GET /api/clients?preset=all\|today\|with_address&q=` | lista |
| `GET /api/clients/<id>` · `DELETE` · `POST …/note` · `GET …/events` | un client |
| `POST /api/import-xml` (text XML sau JSON `{xml, src, refresh}`) | import card |
| `GET /api/pick-url?q=&return=1&state=` | adresa `/pick` a Contragenti |
| `GET /contragenti/callback` | ținta `return_to` |
| `GET/POST /api/settings` · `GET /api/stats` · `GET /api/events` | setări, plăcuțe, jurnal |

## Fișiere

`modules/crm/`: `__init__.py`, `rules.py` (pur: parser XML, IDNO, return_to,
preseturi, pick_url), `store.py`, `controller.py`, `routes.py`,
`templates/crm_app.html`, `sql/01_crm_core.sql`, `scripts/crm_deploy.py`,
`module.json`, `sdk/` (copii MIT din Contragenti: `sample_card.xml`,
`contragenti_sdk.py`, licența). Teste: `tests/test_crm.py` (17).

## Verificare

```bash
venv/bin/python -m pytest tests/test_crm.py -q
```
Pagina: portal → «CRM (beta)». Fără Contragenti pornit: indicatorul din bara
de sus e roșu, «Creează client» trimite la Setări cu mesaj; «Import XML» cu
`modules/crm/sdk/sample_card.xml` → «Client adăugat: CENTRUL … UNISIM-SOFT»,
a doua dată → «Duplicat».

## Căutarea unică și pornirea Contragenti (05.09.2026)

O singură căutare: baza OfficePlus, iar fără rezultate → automat date.gov.md
prin Contragenti (buton separat «🌐 date.gov.md» pentru căutarea directă).
Dacă utilitarul nu rulează, pagina spune «Contragenti (127.0.0.1:9393) nu este
disponibil» și oferă scriptul de pornire (`/launcher/command|bat|py`, generat
de `modules/crm/launcher.py`) pentru macOS / Windows / Linux: găsește sau
descarcă Contragenti, îl pornește și revine în CRM. Protocol cu capturi:
`PROTOCOL_TESTARE_2026-09-05.md`, partea a II-a.

## Ce urmează (după beta)

Contacte / Leaduri / Oferte / Calendar (acum doar în navigație, ca în Demo
CRM); «Creează în ERP» — cele trei blocuri `TMS_UNIVERS / TMS_ORG / TMS_ORG26`
exact ca hub-ul una.md din Contragenti (`HUB_ru.md`); legătura client CRM ↔
`TMS_UNIVERS.CODVECHI = IDNO`.

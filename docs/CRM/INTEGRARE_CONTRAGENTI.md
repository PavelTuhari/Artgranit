# Integrarea cu Contragenti — contractul folosit de CRM

Sursa: `github.com/PavelTuhari/Contragenti` — `INTEGRATION.md`, `API_ru.md`,
`crm_delphi/` (Demo CRM). Contragenti e un **proces separat pe PC-ul
utilizatorului** (Windows, MSI) care automatizează un Chrome real pe
`date.gov.md` (reCAPTCHA se rezolvă de om, nu se ocolește) și oferă un API
local `http://127.0.0.1:9393`.

## Ce folosește CRM-ul web

| Apel Contragenti | Cînd | Răspuns |
|---|---|---|
| `GET /health` | la pornirea paginii, «Verifică Contragenti» | `{status, version, db_count}` → indicatorul verde/roșu |
| `GET /pick?q=&lang=&timeout=&format=xml` | «Creează client» (calea 1, `fetch` din browser) | `200` XML card · `204` anulat · `504` timeout |
| `GET /pick?…&return_to=&state=` | «Creează client» (calea 2, browser fără `fetch` local) | `302` la `…/crm/contragenti/callback?status=ok\|cancelled\|timeout&idno=&denumire=&adresa=…` |
| `GET /card?idno=&format=xml` | «Reîmprospătează din Contragenti» | `200` XML · `404` nu e în baza locală |

Cardul XML (`<counterparty source idno updated>`: `idno, denumire,
inregistrare, forma_juridica, lichidata (Da/Nu), adresa, administratori,
founders/founder@name@share, debts@currency/debt@nr@type@sum, details_text`)
se descompune în `rules.parse_card_xml` → `CrmStore.add_from_card`.
Zecimalele vin cu virgulă («100,00», «180,78») și se convertesc.

## Trei ieșiri, ca în `uMainForm.pas`

| Rezultat | Linia de mesaje | Jurnal `CRM_EVENT_LOG` |
|---|---|---|
| client nou | verde «Client adăugat: …» | `added` |
| IDNO există | galben «Duplicat: acest IDNO există deja» | `dup` |
| anulat / timeout / offline | galben | — |
| XML invalid | roșu | `import_error` |

`refresh=1` (bifa la import, sau «Reîmprospătează») transformă duplicatul în
`updated`: cîmpurile se rescriu, fondatorii și datoriile se înlocuiesc.

## De ce funcționează din browser

API-ul Contragenti răspunde cu `Access-Control-Allow-Origin: *`, iar
`http://127.0.0.1` este tratat de Chrome/Edge/Firefox ca origine sigură
(nu e «mixed content» pe o pagină HTTPS). Dacă totuși un browser blochează,
pagina cade automat pe `return_to`. Timpul de așteptare al `/pick` e al
utilizatorului (implicit 300 s, setare `pick_timeout`).

## Verificat fără Contragenti

Testele `tests/test_crm.py` folosesc `modules/crm/sdk/sample_card.xml` —
cardul etalon al Demo CRM (`crm_delphi/sample_card.xml`, produs de
`build_card_xml`). Verificarea cu Contragenti real (Windows) rămîne la
proprietar: «Creează client» → fereastra Contragenti → «Vernuti contragent»
→ clientul apare în listă.

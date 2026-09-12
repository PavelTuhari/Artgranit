# CRM «de la contract la bani» — procesul, cabinetul clientului, API v2

**Data:** 08.09.2026 · **Ramura:** `feat/crm` (worktree `Artgranit-crm`) · **Contur:** doar `nufarul.eminescu.md` (cerința proprietarului: „pentru început desfășoară doar pe nufarul”).

**Cerința (proprietar, 08.09.2026):** „adaugă un modul CRM nou, în plus la tot ce există pe Biro26, ca instrument al OfficePlus **și** disponibil tuturor clienților OfficePlus prin cabinetul lor personal, pe baza TZ și după chipul și asemănarea celui din Delphi/Pascal”.

- **TZ:** `PavelTuhari/Contragenti/docs/TZ_CRM_ZAVOD.html` (ТЗ-CRM-2026-09, red. 1.0). Această livrare = **faza 0** din §8 (schema prototipului 1:1, demo-date, DML-test, cele 8 etape, kanban, rapoarte) + partea de portal a COM-09 (cabinetul clientului), pe Oracle OfficePlus în loc de PostgreSQL (§7.1 e ținta Zavodului; aici baza e ERP-ul existent — decizie proprie, vezi „Ce nu s-a schimbat din prototip”).
- **Prototipul:** `crm_delphi/` (uCrmData.pas — schema și regulile; uBoardCards.pas — doua; uReports.pas — rapoartele; uTestData.pas — demo și DML-test; lang.json — traducerile).

## Ce s-a livrat

| Bloc | Fișier | Ce face |
|---|---|---|
| Schema | `modules/crm/sql/02_crm_process.sql` | `CRM_CONTACT / LEAD / DEAL / ITEM / ORDER / ORDER_LINE / TASK / PROJECT` — coloanele prototipului (§9.1), + `OWNER_KIND/OWNER_ID` pe fiecare rând; `CRM_CLIENT` primește `CLIENT_TYPE, PHONE, EMAIL, CONTACT_PERSON` și chiriașul; IDNO unic **per chiriaș** |
| Descrieri | `modules/crm/entities.py` | portul lui `InitDefs`: câmpuri, tipuri, enumerări canonice (ru, ca în prototip), implicite `today+N`, lookup-uri |
| Reguli pure | `modules/crm/process.py` | `stage_where` / `overdue_where` (8 etape care se exclud, **nu se stochează**), coloanele celor 5 doua, `board_move_sql` = singurul punct de schimbare a etapei (MoveBoardCard), PostOrder, DoneStepsFor |
| Chiriaș | `modules/crm/tenant.py` | portal → `('office', 0)`; client din cabinet (`session['biro26_client']`) → `('client', id)`; condiția intră în fiecare SQL |
| Date | `modules/crm/store_process.py` | portul lui `TCrmData`: CRUD generic din descrieri, linii comandă + total, `post_order` (vânzare −stoc, producție +stoc, serviciu 0, o singură dată), `convert_lead`, `set_task_done` (Готово ⇔ done), `project_summary`, `stage_info`, doua, `move_card` |
| Rapoarte | `modules/crm/reports.py` | cele 6 ale prototipului: process, receivables, sales_by_client, funnel, stock, projects; JSON sau CSV (`;`, BOM) |
| API | `modules/crm/routes_process.py` | `/api/v2/…` după §7.4 (vezi mai jos) + pagina `/cabinet` |
| UI | `modules/crm/static/crm_process.js` + `templates/crm_app.html` | tablou de lucru (8 plite), kanban drag&drop, pagini de entități construite din `/api/v2/meta`, editor lateral, linii comandă, rapoarte; **fără ferestre modale**, ștergere în doi pași, trei limbi |
| Limbi | `modules/crm/lang.json` (generat de `scripts/crm_make_lang.py`) | RO/EN din prototip; RU = canonicul; 163 chei × 3 + 15 liste poziționale + `stage_title/stage_hint` |
| Demo | `modules/crm/seed.py`, `scripts/crm_seed.py` | portul lui `SeedDemo`: **17/20/12/22/21/23(41)/24/10(100)** — identic cu `crm_delphi/seed.log`; idempotent; iese cu 1 dacă vreo plită e goală |
| DML-test | `modules/crm/dml_test.py`, `scripts/crm_dml_test.py` | portul lui `RunDmlTest` pe chiriașul tehnic `('client', 999999)`: 60 verificări, 0 FAIL (08.09.2026) |
| Teste | `tests/test_crm.py` | 26 teste fără Oracle: izolare, reguli, entități, lang.json, DDL, rute, fără `alert/confirm/prompt` |

## API v2 (contractul din TZ §7.4, adaptat)

Toate sub `/UNA.md/orasldev/crm/api/v2/`, JSON UTF-8, date `yyyy-mm-dd`, erori `{success:false, error, detail, field}` cu 4xx/5xx — **niciodată 200 cu text de eroare**. Chiriașul = sesiunea.

| Metodă | Cale | Ce face |
|---|---|---|
| GET | `health`, `meta`, `lang` | stare + contoare; descrierile entităților, etapele, doua, rapoartele; lang.json |
| GET | `{entity}?q=&stage=&board=&col=&project_id=&client_id=&limit=` | listă (≤ 500); `stage` = filtrul unei plite; `board`+`col` = o coloană de kanban |
| GET/POST/PUT/DELETE | `{entity}[/{id}]` | entity ∈ clients, contacts, leads, deals, items, orders, tasks, projects; `orders/{id}` aduce și `lines`, `projects/{id}` și `summary` |
| POST/DELETE | `orders/{id}/lines[/{lid}]` | linie (preț implicit din nomenclator), total recalculat |
| POST | `orders/{id}/post` | contarea (PostOrder); 409 cu mesajul prototipului dacă nu se poate |
| POST | `leads/{id}/convert` | lead → client (ConvertLead); IDNO tehnic `L-<id>` până la cardul din registru |
| POST | `tasks/{id}/done` `{done}` | Готово ⇔ done |
| GET | `workspace/stages` | cele 8 plite (count, sum, overdue) + ultimele comenzi + sarcini apropiate |
| GET | `board/{kind}` · POST `board/{kind}/move {id,col}` | kind ∈ orders, deals, tasks, projects, project_tasks — **singurul** punct de schimbare a etapei de pe doua |
| GET | `reports/{slug}?lang=&format=json|csv` | process, receivables, sales_by_client, funnel, stock, projects |
| GET | `lookup/{client|deal|item|project}` | perechi id/denumire pentru editoare |
| POST | `seed` · `dml-test` | date demo pe chiriașul curent; DML-testul pe chiriașul tehnic |

## Cabinetul clientului

- `GET /UNA.md/orasldev/crm/cabinet` — aceeași aplicație, chiriașul `('client', YBIRO_CLIENT.ID)` din sesiunea magazinului; fără Contragenti și fără setări (butoanele sunt ascunse, API-ul beta răspunde 401). Clienții se adaugă manual (IDNO opțional → `M-<id>`).
- Legătura din cabinet: un rând în `templates/biro26/site_account.html` (fișier comun — **doar** un `<a>`; pe platformă se pune peste versiunea de acolo după md5, regula №4).
- Un client nu vede niciodată rândurile altuia sau ale OfficePlus: condiția `OWNER_KIND/OWNER_ID` e în fiecare SELECT/UPDATE/DELETE, nu doar în listă.

## Ce nu s-a schimbat din prototip (TZ §7.5)

Numele tabelelor și coloanelor (cu 3 excepții impuse de Oracle: `number→DOC_NO`, `sum→LINE_SUM`, `position→JOB_TITLE`; API-ul păstrează numele prototipului), valorile canonice ale enumerărilor, condițiile etapelor, regula contării, conversia leadului, `Готово ⇔ done`, cei 11 pași ai proiectului, contoarele demo. Diferența asumată: baza e **Oracle 11g OfficePlus** (Biro26DB, worker thick), nu PostgreSQL — pentru că CRM-ul e instrument al OfficePlus și trebuie să stea lângă ERP-ul lui; datele sunt `DATE`, nu text.

## Cum se verifică (comenzi, cod 0)

```bash
cd /Users/pt/Projects.AI/Artgranit-crm
/Users/pt/Projects.AI/Artgranit/venv/bin/python -m pytest tests/test_crm.py -q      # 26 passed
/Users/pt/Projects.AI/Artgranit/venv/bin/python modules/crm/scripts/crm_deploy.py    # DDL, idempotent
/Users/pt/Projects.AI/Artgranit/venv/bin/python modules/crm/scripts/crm_dml_test.py  # == OK: 0 FAIL ==
/Users/pt/Projects.AI/Artgranit/venv/bin/python modules/crm/scripts/crm_seed.py      # contoare = seed.log, plite goale: niciuna
```

În browser (autentificat pe portal): `/UNA.md/orasldev/crm/#workspace` — 8 plite nevide; `#kanban` — trageți un card între coloane; `#orders` → o comandă → linii → **Contabilizează**; `#leads` → **În clienți**; `#reports` → CSV.

## Deploy (doar nufarul, 08.09.2026)

`modules/crm/` întreg + `tests/test_crm.py` + `docs/CRM/` (patch punctual, md5 înainte), apoi `crm_deploy.py` pe server, `systemctl restart artgranit`, `curl -I https://nufarul.eminescu.md/login` → 200. Platformele officeplus (.250, 92.5.130.1) **nu** se ating în această livrare.

## Ce urmează (fazele 1–4 din TZ)

Roluri și audit (OWN-05), aprobări (OWN-04), documente și plăți (ACC-02/03), KP/specificații/contracte (COM-03/04), BOM și rute (PRD-01/02), depozite (WHS-01/02), Gantt și calendar cu drag&drop (COM-07), export xlsx/pdf prin `reports/` (jsReport). Fiecare — entitate nouă în `entities.py` + generator demo + DML-test + pas de test, în același commit (TEC-03).

---

## Adrese live

| Ce | Adresa |
|---|---|
| Tabloul de lucru (cele opt etape) | <https://officeplus.md/UNA.md/orasldev/crm/#workspace> |
| Kanban | <https://officeplus.md/UNA.md/orasldev/crm/#kanban> |
| Capitolele din ghid | <https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html#workspace> · <https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html#kanban> |

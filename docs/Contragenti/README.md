# Contragenti → una.md — puntea dintre registrul de stat și nomenclator

Modul izolat (`modules/contragenti/`, prefix Oracle `CTG_`), creat 07.09.2026.
Primește cardul de contraparte de la utilitarul local **Contragenti**
(date.gov.md) și îl scrie în nomenclatorul una.md — `TMS_UNIVERS`
(`CODVECHI` = IDNO, `GR1='E'`), `TMS_ORG` (`CODFISCAL`, adresă, director) și
fișa clientului de site (`YBIRO_CLIENT.IDNO`) — cu **deduplicare** după IDNO și
denumire (înregistrările vechi fără cod fiscal se repară, nu se dublează) și
**jurnalul întregului lanț** (`CTG_EVENT_LOG`, pagina
`/UNA.md/orasldev/contragenti`).

Algoritmul complet, cazul 518172 și jurnalul: `CONTRAGENTI_INSERARE_UNA.md`.

## Rute (montate de nucleu sub `/UNA.md/orasldev/contragenti`)

| Rută | Ce |
|---|---|
| `GET /` | jurnalul lanțului (sesiune portal) |
| `POST /api/upsert` | `{xml}` sau cîmpuri (+ `page`, `q`) → `{result: created\|repaired\|unchanged, univers_cod, changes, after}` |
| `POST /api/log` | pașii din browser (`step`, `result`, `q`, `detail`) |
| `GET /api/events?idno=&page=&limit=` | jurnalul |
| `GET /api/find?idno=&name=` | ce înregistrare s-ar potrivi (fără scriere) |

## Instalare și verificare

```bash
python modules/contragenti/scripts/contragenti_deploy.py      # CTG_EVENT_LOG (+ secvență, trigger)
python modules/contragenti/scripts/contragenti_backfill.py    # dry-run; --apply completează
venv/bin/python -m pytest tests/test_contragenti.py -q       # 12 teste, fără Oracle
```
Cine folosește modulul: pagina `biro26-clients` (după alegerea în Contragenti);
CRM (beta) își ține baza proprie `CRM_*` și poate apela același `api/upsert`
pentru «Creează în ERP» (pasul următor).

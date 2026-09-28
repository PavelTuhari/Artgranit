# e-Factura — raportul «facturi transmise» (pachet PL/SQL, web, Excel, PDF)

Cerința proprietarului (03.09.2026): în back-office să se vadă facturile
transmise în e-Factura printr-un **pachet PL/SQL nou care întoarce trei
seturi de date** — header (filtrul solicitat), master (totaluri per
e-factură), detail (mărfurile fiecărei e-facturi, legate de master) — cu
vizualizare web și descărcare Excel / PDF.

## Pachetul `EFA_REPORT` (`modules/efactura/sql/04_efa_report.sql`)

| Obiect | Rol |
|---|---|
| `EFA_RPT_HDR_T` / `EFA_RPT_HDR_TAB` | header: `FILTER_FROM, FILTER_TO, FILTER_STATUS, FILTER_CLIENT, GENERATED_AT, ENDPOINT, DOCS_CNT, SENT_CNT, ACCEPTED_CNT, ERROR_CNT, TOTAL_SUM` |
| `EFA_RPT_MST_T` / `EFA_RPT_MST_TAB` | master: `EFA_ID, DOC_COD, NRMANUAL, DOC_DATE, CLIENT_COD, CLIENT_NAME, CLIENT_IDNO, STATUS, SFS_SERIA, SFS_NUMBER, REQUEST_ID, SENT_AT, ERR_MSG, TOTAL, ROWS_CNT, QTY_SUM` |
| `EFA_RPT_DTL_T` / `EFA_RPT_DTL_TAB` | detail: `EFA_ID, DOC_COD, ROW_NO, GOODS_COD, CODE, NAME, UM, QTY, PRICE, SUMA` — legătura cu master prin `EFA_ID` (și `DOC_COD`) |
| `EFA_REPORT.header/master/detail(p_from, p_to, p_status, p_client)` | funcții **pipelined**: `SELECT * FROM TABLE(EFA_REPORT.master(DATE '2026-09-01', DATE '2026-09-30', NULL, NULL))` |
| `EFA_REPORT.sent(p_from, p_to, p_status, p_client, p_header OUT, p_master OUT, p_detail OUT)` | aceleași trei seturi ca `SYS_REFCURSOR` — pentru aplicațiile native (uniConf, rapoarte) |

Filtrul: perioada pe data trimiterii (`SENT_AT`, altfel `UPDATED`), statut
(`NULL` = toate; `SENT / ACCEPTED / SIGNED / ERROR / REJECTED / NEW`),
client (cod ERP, `NULL` = toți). Sursa: `EFA_DOC` + `TMDB_DOCS` +
`VMDB_ST201D` + `TMS_UNIVERS`. Un singur cursor de bază (`c_master`) hrănește
toate trei seturile, deci nu pot diverge. Textul DDL e ASCII (baza e
CL8MSWIN1251). Instalat pe Oracle-ul comun la 03.09.2026 (8 obiecte,
`VALID`); reinstalare: `python modules/efactura/scripts/efactura_deploy.py`
(rulează toate fișierele `sql/`, idempotent).

## Web

- Pagina: `/UNA.md/orasldev/efactura/report` (`efactura_report.html`,
  link din bara de sus a Setărilor și în manifest). Filtre: de la / pînă la
  (implicit luna curentă), statut, client; filtrele se țin în `localStorage`.
- Header ca plăcuțe (e-facturi, trimise, acceptate, cu eroare, total,
  perioada, adresa SFS). Master ca tabel; click pe linie → detail-ul ei.
- `GET /admin/report?from&to&status&client` → JSON `{header, master, detail}`;
  `/admin/report.xlsx` → Excel cu trei foi (Header, Master, Detail; `EFA_ID`
  și `DOC_COD` în fiecare foaie pentru legătură); `/admin/report.pdf` →
  PDF A4 landscape (reportlab; DejaVu Sans pentru diacritice/chirilice),
  master + cîte un tabel detail per e-factură.
- Cod: `modules/efactura/report.py` (`parse_filters`, `fetch`, `to_xlsx`,
  `to_pdf`); rutele în `routes.py`.

## Verificare

- `pytest tests/test_efactura.py -q` → 57 (DDL cu `/` în jurul fiecărui
  bloc, fără diacritice; filtre; Excel cu trei foi legate; PDF; rute și pagină).
- Pe date reale (01.08–03.09.2026): 11 e-facturi, 108 poziții, total
  262 373,5 lei; PDF și Excel generate.

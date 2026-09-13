# e-Factura primite: importul «ca în celelalte baze cloudbd» — proba vie din 13.09.2026

Cerința proprietarului: «Смотри как в других бд на cloudbd и делай также». Fluxul
din BMPUBLIC / FPROIECT (pachet 12103 → parserul vendorului `PKG_EDI_XML` →
documente de intrare) a fost portat în OFFICEPLUS **fără a atinge pachetul vendor**
și rulat pe factura reală de pe mediul de probă SFS. Documentul de bază:
[EFACTURA_FACTURI_PRIMITE.md](EFACTURA_FACTURI_PRIMITE.md).

## 1. Fluxul (identic cu celelalte baze)

```
SFS (rol cumpărător) ─► EFA_IN (XML)  ─► document 12103 «pachet XML» + OLE (TMDB_DOCS_OLE)
        │                                        │ pkg_edi_xml.import_xml_package_object (VENDOR)
        │                                        ▼
        │                          TMDB_XML_PACKAGE (STATUS_DOC: 1 valid, 6 dată, 7 furnizor, 8 subdiviziune…)
        │                                        │ EFA_INBOX.create_docs_1209 (al nostru)
        ▼                                        ▼
  decizie SFS                    document 1209 «Оприходование товара»: TMDB_DOCS + VMDB_ST201M
                                 (DT 2171 / CT 5211, DTDEP 1, CTDEP furnizor) + VMDB01M_VINZ
                                 (seria/nr FF) + VMDB_ST201D (poziții, DTSC din reguli/cod de bare/denumire)
```

Trei căi de intrare, toate ajung în același loc:

| De unde | Cum |
|---|---|
| back-office web, pagina de test | cardul «📥 Facturi primite» → «Importă în una.md (pachet 12103)» → `POST …/efactura/test/inbox/import` |
| back-office NATIV (Delphi) | formularul **12103** (creat de `scripts/efactura_native_form12103.py`, OBJ_ID 11530 sub «Intrări»), acțiunea «Preia din e-Factura (API)» = `EFA_INBOX.fetch_api_pr(:nrdoc)` → UTL_HTTP la `officeplus.md/api/biro26/efactura/inbox/package/<nrdoc>` → serverul aduce facturile noi din SFS și le pune în pachet; apoi «Загрузить XML» (vendor) și «Сформировать документы 1209» |
| API | `GET /api/biro26/efactura/inbox/package/<nrdoc>?api_key=…` (401 fără cheie) |

## 2. Ce a trebuit reparat ca să meargă LIVE (nu se vedea din cod)

| # | Simptom | Cauza | Rezolvare |
|---|---|---|---|
| 1 | `ORA-20101 Redactarea documentului este interzisa … inafara perioadei de lucru (-)` la `INSERT TMDB_DOCS` | `TRIG_BFALL_TMDB_DOCS` cere ca data documentului să fie în perioada de lucru din `TPARAMS`; în sesiunile de sistem (API, job) TPARAMS e gol | `EFA_INBOX.sys_guard`: ocolirea prevăzută de trigger (`un4public.envun4.envsetvalue('dont_fire_trigger','1')`, aceeași din `Y_AI_BIRO26`), ținută pe TOT blocul de creare (triggerele `VMDB_ST201M/D` → `UN$GFC` actualizează iar TMDB_DOCS) și ridicată imediat, inclusiv la excepție |
| 2 | `USERID` gol pe documentele create | triggerele TMDB_DOCS înlocuiesc USERID cu `SYS_CONTEXT('envun4','param_userid')`, gol în sesiunea noastră | `sys_guard` pune `param_userid` = setarea `in_userid` (implicit 1) dacă lipsește și îl scoate la ieșire |
| 3 | `ORA-01403 no data found` în `pkg_edi_xml` linia 3629 | vendorul citește `VMS_SYSS tip XM cod 1 cod1 6` (intervalul de zile pentru data facturii) — OfficePlus avea doar `XM cod 4` | `sql/07_efa_syss_seed.sql`: MERGE idempotent al rîndurilor `XM cod 1` (statusuri 0–15, cod1 6 UM = **364** zile ca FPROIECT; BMPUBLIC are 60) și `XM cod 3` (0 NN, 1 TTN), copiate de pe cloudbd |
| 4 | `STATUS_DOC 8 — Не заполнен код подразделения покупателя` | vendorul ia subdiviziunea cumpărătorului din `SupplierInfo/UnloadingPointCode` (VMS_UNIVERS TIP O / GR1 I); SFS trimite doar textul `UnloadingPoint` | `inbox.with_unloading_code`: la ambalarea pachetului se injectează `<UnloadingPointCode>` = setarea `in_dtdep` (1 = «Magazin 1»), fără a suprascrie unul existent |
| 5 | la re-import pozițiile se dublau (NRDOC1 2, 3, 4…) | `import_xml_package_object` doar adaugă rînduri | `EFA_INBOX.import_package` șterge întîi pozițiile fără `NRDOC_DEST` |
| 6 | `RROWID 7` pe prima poziție | `ROWN` din TMDB_XML_FACTURA numără pe tot pachetul | `ROW_NUMBER() OVER (ORDER BY ROWN)` per document |
| 7 | `ERR_MSG` vechi rămînea după un import reușit | — | `_apply` îl șterge cînd `DEST_NRDOC` e completat |
| 8 | furnizorul POSEIDONGRUP lipsea din nomenclator | — | adăugat prin puntea Contragenti: COD **540709**, `CODVECHI`/`CODFISCAL` 1014600011116 |

## 3. Protocolul probei (baza OFFICEPLUS de producție, mediul de probă SFS)

| Pas | Rezultat |
|---|---|
| formular 12103 în `A$ADM` | creat: OBJ_ID 11530 sub «Intrări» (2453), 5 acțiuni |
| `EfaPackage.import_invoices([1])` | pachet **439** (12103, OLE `EFACTURA_API_20260913_130055.xml`), parserul vendorului OK |
| validările vendorului | `STATUS_DOC 6` (factura de probă e din 11.06.2020 → în afara ±364 zile; pentru probă intervalul a fost lărgit temporar la 3000 și readus la 364), apoi `8` (subdiviziune), apoi **`1` valid** |
| `EFA_INBOX.create_docs_1209(439)` | document **1209 nr. 441**: `NRMANUAL EAA002514972`, data 11.06.2020, LEI, NRSET 201, USERID 1; `VMDB_ST201M` DT 2171 / CT 5211, DTDEP 1 «Magazin 1», CTDEP 540709 «POSEIDONGRUP SRL, 1014600011116», DTDATA/CTDATA 11.06.2020; `VMDB01M_VINZ` EAA / 002514972; `VMDB_ST201D` 1 poziție: 35 buc, SUMA 3500,00, fără TVA 2916,67, TVA 583,33; **DTSC gol** — «Mariflex PU 30 Grey 600 ML» nu e în nomenclator și nu are regulă/cod de bare (exact ca în Delphi: se alege manual) |
| `EFA_IN` | id 1 → `IMPORTED`, `PKG_NRDOC 439`, `PKG_STATUS 1`, `DEST_NRDOC 441` |
| lanțul NATIV: `EFA_INBOX.fetch_api(442)` din Oracle | `HTTP 200`: serverul a adus din SFS **o factură nouă** — **EBL 000435006** de la S.R.L. «TOTAL COMPUTER» (1008602007200), 101,00 lei — și a pus-o în pachetul 442 cu `STATUS_DOC 7` («furnizorul (IDNO) nu există în nomenclator»); EFA_IN id 21 `ERROR` cu același comentariu → butonul «Adaugă furnizorul» și re-import |
| teste | `tests/test_efactura.py`: **68 passed**; `efactura_deploy.py`: 0 FAIL, EFA_INBOX VALID |
| desfășurare | nufarul (92.5.3.187) și officeplus (192.168.0.250): `login 200`, 0 Traceback; `https://nufarul.eminescu.md/login` 200, `https://officeplus.md/cos` 200 |

Documente de probă rămase în baza de producție (de șters sau păstrat — decizia
proprietarului): 12103 nr. **438** (gol, prima încercare), **439** (pachetul cu
EAA 002514972), **442** (pachetul creat din Oracle pentru proba nativă), 1209 nr.
**441** (documentul contabil creat automat, datat 11.06.2020). Ștergerea cere
aceeași ocolire `dont_fire_trigger` (perioada de lucru), deci o fac eu la cerere.

## 4. Setările contabile (EFA_SETTING, pagina de administrare)

`in_nrset` 201, `in_dt` 2171, `in_ct` 5211, `in_dtdep` 1 (și subdiviziunea
cumpărătorului pentru vendor), `in_dt_row` 2171, `in_userid` 1. Valorile sînt
copiate din documentul 1209 nr. 4 al OfficePlus; contabilul le confirmă.

## 5. Adrese live

- pagina de test (cardul «📥 Facturi primite»): https://officeplus.md/UNA.md/orasldev/efactura/test (302 → login) · https://nufarul.eminescu.md/UNA.md/orasldev/efactura/test
- administrare (setări `in_*`, jurnalul SFS): https://officeplus.md/UNA.md/orasldev/efactura/admin
- API nativ: `http://officeplus.md/api/biro26/efactura/inbox/package/<nrdoc>?api_key=…` (401 fără cheie)
- cod: `modules/efactura/inbox.py`, `sql/06_efa_inbox_pkg.sql`, `sql/07_efa_syss_seed.sql`, `scripts/efactura_native_form12103.py`, `native_api.py`

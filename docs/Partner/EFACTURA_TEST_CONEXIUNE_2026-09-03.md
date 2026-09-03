# e-Factura — «Testează conexiunea» refăcut și conturile pe mediul greșit (03.09.2026)

## Ce s-a întîmplat

Contabilul OfficePlus a completat Setările e-Factura: conturile API
`officeplus_api` / `officeplus2_api` (create în cabinetul **real** de pe
`sfs.md`, firma Grecu Office Group SRL), dar a lăsat adresa serviciului pe
mediul de **probă** (`apiefactura-pre.sfs.md`). «Testează conexiunea» a
arătat o eroare 403 pentru o secundă, apoi mesajul a dispărut.

Două cauze, verificate:

1. **Interfața**: `testConn()` scria rezultatul în `s-info`, apoi chema
   `load()`, care rescria același element cu «✅ configurat». Rezultatul
   trăia cît dura reîncărcarea setărilor.
2. **Mediul**: de pe același IP (93.115.136.18) conturile UNISIM-SOFT
   (`ptuhari`/`otuhari`) trec pe mediul de probă; conturile Grecu Office
   Group pică pe probă (403, apoi 500) și trec pe mediul **real**
   (`efactura-api.sfs.md`, operația `Test`, ambii semnatari ✅). Deci
   lista de acces a mediului de probă e pe IP **și pe firmă**, iar mesajul
   vechi «IP-ul nu e pe listă» era înșelător.

## Ce s-a schimbat

| Fișier | Ce |
|---|---|
| `modules/efactura/conncheck.py` (nou) | `check()`: `Test` pe AMBII semnatari; la eșec, aceeași verificare pe celălalt mediu (probă ↔ real) și indiciul «conturile merg pe mediul X, schimbați adresa» |
| `modules/efactura/routes.py` | `/admin/test` folosește `conncheck.check`; jurnalul `EFA_LOG` primește verdictul fără blocul pe semnatari |
| `modules/efactura/templates/efactura_admin.html` | bloc propriu `#s-test` (ora, mediul, o linie per semnatar, indiciul); nu mai atinge `s-info`, nu mai cheamă `load()` |
| `modules/efactura/sfs.py` | textul pentru 403: probă = IP sau firmă neînscrise; real = cont/mediu |
| `tests/test_efactura.py` | +3 teste: indiciul de mediu, succes cu un semnatar, șablonul nu mai trece prin `s-info` (46 în total) |

## Verificare

- `pytest tests/test_efactura.py -q` → 46 passed.
- Setări e-Factura → «Testează conexiunea»: blocul rămîne pe ecran; cu adresa
  de probă și conturile reale apare 💡 cu adresa reală de pus.

## Regula pentru contabil

Adresa serviciului trebuie să fie a mediului pe care s-au creat conturile:
conturi din `sfs.md` → `https://efactura-api.sfs.md/Service.svc`;
conturi din `preproductie.sfs.md` → `https://apiefactura-pre.sfs.md/Service.svc`.
Pe mediul real nu se cere nimic la SFS (răspuns CTIF 03.09.2026).

## Completare (aceeași zi): lista mediilor

Cîmpul «Adresa serviciului» din Setări e acum o listă: **REAL**
(`efactura-api.sfs.md`), **de PROBĂ** (`apiefactura-pre.sfs.md`) sau
**alt text…** (apare cîmpul liber). Valoarea salvată rămîne în același
cîmp `endpoint` (`s-endpoint`), deci nimic nu se schimbă în API/store; la
încărcare, o adresă necunoscută selectează automat «alt text». Fișiere:
`efactura_admin.html`, `routes.py` (adresele vin din `sfs.ENDPOINT_*`),
test `test_admin_template_has_endpoint_picker`.

## Completare 2 (aceeași zi): jurnalul COMPLET al comunicărilor pe pagina Setări

Cerința proprietarului: în jurnal să fie **toate** comunicările cu SFS, nu
doar cele eșuate, cu textul întreg trimis și primit. Ele SE SCRIAU deja în
`EFA_CALL` (fiecare apel, reușit sau nu, plic cu parola mascată + răspuns
brut), dar:

1. pagina Setări arăta doar `EFA_LOG` (rezumat de 2000 de caractere);
2. citirea `EFA_CALL` era GOALĂ pe Oracle 11g: `DBMS_LOB.SUBSTR(…, 32000, 1)`
   în SQL depășește limita de 4000 și `execute_query` înghite eroarea —
   tabelul avea 77 de rînduri, pagina probei nu arăta niciunul.

Schimbări: `journal.py` citește CLOB-urile pe bucăți de 4000 (`recent`:
8 bucăți = 32000 de caractere; `get(id)`: 50 bucăți = tot textul), cu
semnalul «trunchiat»; rute noi `/admin/calls` și `/admin/calls/<id>`;
panoul «Comunicări cu SFS — toate apelurile, complet» pe pagina Setări
(click pe rînd → trimis / răspuns; «tot textul» aduce restul). Teste:
`test_journal_reads_clobs_in_4000_chunks`, `test_admin_page_shows_all_sfs_calls`
(49 în total).

## Completare 3 (aceeași zi): prima trimitere reală — `CreationMotiv` 1|2

Acțiunea din una.md pe contul A-90 (Grecu Office Group, mediul real):
«ORA-20000: … Motivul Crearii este indicat incorect trebue sa fie 1 sau 2».
Cauza: valoarea era fixă 4 (plătitor TVA); firma e neplătitoare, iar XSD-ul
spune că pentru neplătitori valorile sînt 1/2/3. Adăugată setarea
`creation_motiv` (`EFA_SETTING`, implicit 4) + cîmpul în Setări, alături
de `tva_rate` (care nu avea cîmp în pagină). `build_payload` o pune în
document, `build_invoice_xml` o scrie. Pe officeplus.md setate:
`creation_motiv = 1`, `tva_rate = 0`. Test: `test_creation_motiv_from_settings`.

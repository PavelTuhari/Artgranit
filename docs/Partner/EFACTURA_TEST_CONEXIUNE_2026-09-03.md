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

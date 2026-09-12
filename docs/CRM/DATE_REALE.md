# Date reale din ERP în OfficePlus; demo separat

**Cerința proprietarului (10.09.2026):** *«В officeplus должно всё работать
на оракл, соедини с реальными данными и товар тоже. Демо режим как сейчас
остаётся отдельно.»*

---

## 1. Ce s-a schimbat

Până acum CRM-ul portalului lucra pe setul demonstrativ semănat pe
08.09.2026 — el stătea chiar în chiriașul `office`. Acum:

| Chiriaș | Ce conține | Cine îl vede |
|---|---|---|
| `('office', 0)` | **datele reale**: contragenții ERP + conturile magazinului, marfa din dicționarul ERP | portalul OfficePlus |
| `('demo', 0)` | setul demonstrativ (17 clienți, 21 poziții, 23 comenzi, 10 proiecte, 124 sarcini) | portalul, cu comutatorul pe «Demo» |
| `('client', N)` | datele clientului | cabinetul clientului |

Comutatorul e în bara de sus: **● Date reale** / **⚗ Demo**. Un clic schimbă
chiriașul sesiunii și reîncarcă pagina; datele reale rămân neatinse. Butonul
«⚗ demo» (semănatul datelor de probă) apare **doar** în regimul demo, iar
API-ul răspunde `409` dacă cineva încearcă să semene peste datele reale.

## 2. Marfa: căutare vie, nu o copie

Dicționarul ERP are **232 149** poziții (188 857 nearhivate). O copie în
`CRM_ITEM` ar fi moartă a doua zi, iar prețurile stau oricum în perioadele
din `TPR1D_PERPRLIST`. De aceea:

1. **Căutarea** merge direct în `TMS_UNIVERS` (`TIP='P'`) — după denumire
   RO/RU, articol (`CODVECHI`) și cod de bare (`TMS_MPT_BARCODE`), exact ca
   în back-office;
2. **prețul** = lista în vigoare (`TPR1D_PERPRLIST`, `CODPRICE=1`, perioada
   care cuprinde ziua de azi), cu întoarcere pe prețul din fluxul
   `BIRO26_GOODS` — **același lanț ca la magazin** (`shop_prices_for`), ca să
   nu existe două adevăruri despre același preț;
3. **stocul** = `BIRO26_GOODS.STOC`;
4. poziția folosită într-o comandă se **aduce o singură dată** în `CRM_ITEM`
   (`SRC='erp'`, `ERP_COD = TMS_UNIVERS.COD`); butonul «Reîmprospătează
   prețurile» o resincronizează.

Panoul «Adaugă din ERP» stă în capul paginii **Nomenclator** și se vede doar
în regimul real.

## 3. Contragenții

Butonul **⇄ ERP** din pagina *Clienți* aduce:

* `TMS_ORG` — registrul ERP (numele din `TMS_UNIVERS TIP='O'`, IDNO =
  `CODFISCAL`, adresă, telefon, director);
* `YBIRO_CLIENT` — conturile magazinului (nume, IDNO, telefon, e-mail).

Unirea se face **după IDNO** (regula punții Contragenti). Un cont fizic fără
IDNO nu se pierde: cheia devine `shop:<id>`. Actualizarea **nu șterge** ce a
scris operatorul — completează doar golurile (`NVL(coloana, valoare_nouă)`).

Rezultatul primei sincronizări pe baza reală: **38 noi, 19 actualizați, 2
săriți** (contragenți ERP fără cod fiscal).

## 4. Obiecte și fișiere

| Fișier | Ce |
|---|---|
| `modules/crm/sql/05_crm_real.sql` | `CRM_ITEM.SRC/ERP_COD/SYNCED`, `CRM_CLIENT.ERP_COD`, indexuri |
| `modules/crm/erp_source.py` | regulile și SQL-ul (fără execuție — se testează fără wallet) |
| `modules/crm/store_erp.py` | execuția: căutare, import, reîmprospătare, sincronizarea clienților |
| `modules/crm/routes_erp.py` | `/api/v2/erp/*` și comutatorul `/api/v2/mode` |
| `modules/crm/static/crm_real.js` | panoul ERP și comutatorul din bara de sus |
| `modules/crm/scripts/crm_demo_move.py` | mutarea setului demo `office → demo` (reversibilă: `--back`) |

Indexul unic pe `(chiriaș, ERP_COD)` este **funcțional**: cu coloane simple,
rândurile proprii (fără `ERP_COD`) ar fi toate duplicate, fiindcă
`OWNER_KIND`/`OWNER_ID` nu sunt niciodată nule (`ORA-01452`).

### API

| Metodă | Adresă | Ce face |
|---|---|---|
| GET | `/api/v2/erp/status` | câte poziții și contragenți are ERP-ul, câte au fost aduse |
| GET | `/api/v2/erp/goods?q=` | căutare vie în dicționar (nu scrie nimic) |
| POST | `/api/v2/erp/items` | aduce (sau reîmprospătează) poziția `{cod}` / `{cods:[...]}` |
| POST | `/api/v2/erp/items/refresh` | reîmprospătează prețul și stocul pozițiilor aduse |
| POST | `/api/v2/erp/clients/sync` | `TMS_ORG` + `YBIRO_CLIENT` → `CRM_CLIENT` |
| GET/POST | `/api/v2/mode` | regimul sesiunii: real / demo |

## 5. Instalare și mutarea setului demo

```bash
python3 modules/crm/scripts/crm_deploy.py --file 05_crm_real.sql
python3 modules/crm/scripts/crm_demo_move.py            # doar raportul
python3 modules/crm/scripts/crm_demo_move.py --apply    # office -> demo
python3 modules/crm/scripts/crm_demo_move.py --apply --back   # înapoi
```

Mutarea schimbă doar `OWNER_KIND` al rândurilor demonstrative (270 rânduri în
10 tabele); setările canalelor de alertă (`CRM_ALERT_CFG`) rămân la OfficePlus.

## 6. Verificat pe baza reală (10–11.09.2026)

* `erp/status`: 188 857 poziții active, 33 contragenți ERP, 26 conturi magazin;
* căutarea «creion» → 50 de poziții reale cu articol, grupă, preț și stoc;
* «Adaugă» pe `CF81764` → poziția a intrat în nomenclator (1,80 MDL);
* reîmprospătarea prețurilor: 1 poziție, fără eroare;
* sincronizarea contragenților: 38 noi, 19 actualizați (61 clienți în total);
* capcană rezolvată: `ORA-01036` — Oracle refuză legăturile nefolosite, deci
  fiecare ramură (INSERT / UPDATE) primește exact parametrii instrucțiunii ei.

---

## 8. Marfa și comenzile reale direct în liste (12.09.2026)

**Cerința proprietarului:** *«особенно обрати внимание на marfa и на comenzi,
тут полно в оракл реальных данных»*. Deci cele două secțiuni nu mai arată doar
ce a fost introdus în CRM:

| Secțiune | Ce se vede acum |
|---|---|
| **Nomenclator** | pozițiile proprii (aduse din ERP sau create în CRM) și, după ele, **marfa reală din dicționar** — 188 857 poziții active, cu prețul din lista în vigoare și stocul din flux |
| **Comenzi** | comenzile proprii și **conturile de plată reale ale magazinului** — `TMDB_DOCS` cu `SYSFID=12280` (168 documente), cu client, dată, total și **liniile reale** din `VMDB_ST201D` (articol, cantitate, preț, sumă) |

### Cum se deosebesc de rândurile CRM

* **id negativ**: rândul ERP are `id = -COD` (rândurile CRM au întotdeauna
  `id > 0`), deci nu se pot confunda niciodată;
* în listă au o **bară verde** la stânga, iar în fișă un semn `din ERP`;
* fișa este **în citire**: câmpurile sunt blocate, liniile comenzii nu au
  „×", nu există formular de adăugare. `PUT`/`DELETE` pe un id negativ sunt
  refuzate cu mesaj („se modifică în ERP, nu în CRM");
* la marfă, fișa are butonul **„Adaugă în nomenclator”** — poziția intră o
  singură dată în `CRM_ITEM` (cu `ERP_COD`) și de atunci are rând propriu, iar
  din lista ERP dispare (nu se dublează).

### Capcană rezolvată

Ruta `/api/v2/<key>/<int:rid>` **nu prinde numerele negative** — convertorul
`int` al Werkzeug este fără semn, deci fișa unui rând ERP dădea `HTTP 404`.
Rutele fișei sunt acum `<int(signed=True):rid>`.

Filtrele de etapă și coloanele de kanban nu amestecă rânduri ERP (ele se aplică
numai datelor CRM), iar dacă ERP-ul nu răspunde, lista rămâne cu rândurile CRM
— nu se golește.


---

## 9. Fiecare secțiune pe date reale (12.09.2026)

Cerința proprietarului: *«везде должны быть реальные данные из оракл»*. Ce
sursă are fiecare secțiune în Oracle:

| Secțiune | Sursa reală | Cantitate (12.09.2026) |
|---|---|---|
| Clienți | `TMS_ORG` + `YBIRO_CLIENT`, uniți după IDNO | 45 |
| **Contacte** | oamenii conturilor magazinului (`YBIRO_CLIENT`) + `CONTACT`/`DIRECTOR` din `TMS_ORG` | 27 |
| **Lead-uri** | conturi înregistrate **fără nicio comandă** + `YBIRO_SITE_SUBSCRIBER` | 18 |
| **Oportunități** | `TMS_CREDITE_REQ` — cererile de credit (sumă, produs, termen, stare) | 33 |
| Nomenclator | `TMS_UNIVERS` + preț `TPR1D_PERPRLIST` + stoc din flux | 188 857 |
| Comenzi | `TMDB_DOCS` SYSFID=12280 + linii `VMDB_ST201D` | 164 |
| Angajați | arborele `A$ADM`/`A$ADP` | 35 |
| Proiecte, Calendar | **nu au echivalent în ERP** — rămân doar rândurile CRM | — |

Etapa oportunității se deduce din starea cererii: `NEW` → *Предложение*,
`PROCESSED`/`APPROVED` → *Выиграна*, `REJECTED`/`CANCELLED` → *Проиграна*.

Cheile din surse diferite nu se ciocnesc: contul magazinului rămâne `-id`,
contragentul ERP primește `-(id + 10 000 000)`, abonatul `-(id + 20 000 000)`,
cererea de credit `-(id + 30 000 000)`.

### Fișa produsului = cea din back-office

Pentru o poziție reală, CRM-ul **nu redesenează** fișa: folosește chiar
implementarea back-office-ului (`Biro26Store.get_univers_card` — poză prin
imgproxy, coduri de bare, brand/grupă/categorie, fișa `TMS_MPT`) plus
istoricul de prețuri al filei *Marfă/Stoc* (`get_price_history`). Un singur
adevăr despre produs, aceleași date ca la
<https://officeplus.md/UNA.md/orasldev/biro26-backoffice>.

---

## Adrese live

| Ce vreau să văd | Adresa |
|---|---|
| Marfa reală în nomenclator | <https://officeplus.md/UNA.md/orasldev/crm/#items> |
| Comenzile reale (conturile magazinului) | <https://officeplus.md/UNA.md/orasldev/crm/#orders> |
| Clienții reali | <https://officeplus.md/UNA.md/orasldev/crm/#clients> |
| Comutatorul real/demo | în bara de sus a <https://officeplus.md/UNA.md/orasldev/crm/> |
| Aceleași, pe conturul de probă | <https://nufarul.eminescu.md/UNA.md/orasldev/crm/> |
| Ghidul cu capturi (capitolele 5 și 6) | <https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html#marfa> · <https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html#comenzi> |

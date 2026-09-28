# e-Factura — facturile PRIMITE de la parteneri și importul lor în una.md

13.09.2026. Completarea motorului de test (care pînă acum emitea facturi din
baza OfficePlus) cu **partea de cumpărător**: preluarea facturilor emise de
parteneri, potrivirea cu nomenclatorul, aterizarea în tabelele standard
una.md și decizia (acceptare / respingere) în SFS. Totul cu **jurnal complet**
(`EFA_CALL`), ca la emitere.

## 1. Cum importă una.md o factură XML din e-Factura (cercetarea, corectată)

Concluzia altei sesiuni («baza nu are nicio procedură, totul e în Delphi») e
**greșită pentru OFFICEPLUS**: schema are pachetul **`PKG_EDI_XML`** (4690 de
linii, ticket 202006091019838 «выгрузка/загрузка в e-factura»), cu:

| Procedura | Ce face |
|---|---|
| `import_xml(p_nrdoc, p_file_name, p_dir_name, …)` | fișierul XML dintr-un `DIRECTORY` Oracle → `tmdb_docs_ole` (blob atașat documentului) → `fill_tmptable_1231` → `fill_doc_1231` |
| `fill_tmptable_1231` / `blob_to_table` (**private**) | XML → `TMDB_XML_FACTURA`: rîndul `ROWN=0, CODE='0'` = antetul, `ROWN=1..n` = pozițiile; XPath-uri `//Documents/Document/SupplierInfo/…` |
| `fill_doc_1231` | cere un document **`SYSFID=1231`**; furnizorul după `VMS_ORG.CODFISCAL`; **pozițiile numai după cod de bare** (`VMS_MPT_BARCODE`) → `VMDB_ST201M` + `VMDB_CST3A`; refuză la coduri de bare necunoscute sau duplicate |
| `TMS_IMPORT_EFACTURA` | regulile pe denumire (`TEXT1` = LIKE Oracle, `PRIORITET`, `DT` cont, `DTSC` card) — le aplică clientul Delphi, nu pachetul; în OfficePlus sînt 34 de reguli, toate pentru servicii (conturi 5442 și 7135), niciuna cu card |

Ce lipsește în OfficePlus: **formularul 1231** (nu există în `A$ADM`, zero
documente) — deci `fill_doc_1231` nu poate fi apelat; formularele de intrare
ale OfficePlus sînt cele din secțiunea «Intrari» (`DOC_88803` «Оприходование
товара», `DOC_88804» «Приёмка товара»), fără niciun document creat vreodată.
`TMDB_XML_FACTURA` în OfficePlus a fost folosită doar pentru **export**
(contul de plată `12280` → XML, `EF_403_…XML`), niciodată pentru import.
Triggerul `TRG_TMDB_XML_FACTURA` e dezactivat.

Furnizorii **nu trimit coduri de bare**: pe factura de probă `BarCode=""`,
`Code=""`; în schemele unde importul e folosit zilnic, codul e numărul de rînd.
De aceea marfa nu se importă automat nicăieri; regulile acoperă serviciile.

## 2. Ce face modulul acum (compatibil cu pachetul și tabelele existente)

```
SFS (rol 2 = cumpărător)  ──GetInvoicesForSigning / GetAcceptedInvoices──►  EFA_IN + EFA_IN_ROW
                                                                               │  potrivire una.md
      «Acceptă / Respinge» ◄──PostAcceptedInvoices / PostRejectedInvoices──    │
                                                                               ▼
                                              EFA_INBOX.land ──► TMDB_XML_FACTURA (antet + poziții)
```

- **Operațiile SOAP noi** (`sfs.py`, ordinea cîmpurilor din XSD): `SearchInvoices`
  (Parameters: BuyerIDNO, IssuedOn{EndDate, StartDate}, Seria…), `CheckInvoicesStatus`,
  `PostAcceptedInvoices`, `PostRejectedInvoices` (Number, Seria, Comment),
  `GetInvoicesContentForPrint` (PDF). `GetInvoicesForSigning` cu `ActorRole=2`
  întoarce facturile care ne așteaptă decizia **cu XML**; `GetAcceptedInvoices`
  doar lista, XML-ul se ia cu `GetInvoicesBySeriaNumber`.
- **`EFA_IN`** (o linie per factură: serie/nr, furnizor, IDNO, date, totaluri,
  `SFS_STATUS`, `STATUS` NEW/LANDED/ACCEPTED/REJECTED/ERROR, `SUPPLIER_COD`,
  `NRDOC`, XML CLOB) și **`EFA_IN_ROW`** (pozițiile + `MATCH_KIND`
  barcode/rule/none, `MATCH_COD`, `MATCH_DT`, `MATCH_RULE`). Unic pe
  (mediu, serie, număr). `sql/05_efa_inbox.sql`.
- **Potrivirea** (`inbox.py`): furnizorul `TMS_UNIVERS.CODVECHI = IDNO` (GR1 E)
  sau `TMS_ORG.CODFISCAL`; poziția: cod de bare → `TMS_MPT_BARCODE` (ca
  `fill_doc_1231`), altfel regula `TMS_IMPORT_EFACTURA` (LIKE pe denumirea
  fără diacritice, după `PRIORITET`), altfel «nepotrivit». Furnizorul negăsit
  se adaugă cu un buton prin **puntea Contragenti** (`modules/contragenti`,
  `TMS_UNIVERS.CODVECHI` + `TMS_ORG.CODFISCAL`).
- **Aterizarea**: pachetul propriu **`EFA_INBOX.land(p_nrdoc, p_xml, p_file_name)`**
  = copia XPath-urilor din `blob_to_table` (privat la ei), cu datele tăiate la
  19 caractere (SFS trimite `2020-06-11T16:17:09.8985986+03:00`, pe care
  `TO_DATE`-ul lor l-ar refuza), `FILE_NAME` completat (export_xml ia doar
  `file_name IS NULL`, deci nu ne atinge), `NRDOC` rezervat din `ID_TMDB_DOCS`
  (niciodată coliziune cu un document real). Idempotent: același NRDOC la
  reaterizare. XML-ul se ambalează în `<Documents>` (SFS dă `<Document>` gol),
  semnătura XAdES se scoate.
- **Decizia**: `PostAcceptedInvoices` → `Status 2`, factura trece din coada
  cumpărătorului în `GetAcceptedInvoices` cu `InvoiceStatus 3`; respingerea
  cere motiv (ajunge la furnizor).
- **Pagina de test**: cardul «📥 Facturi primite de la parteneri» — «Preia din
  e-Factura», lista (serie/nr, furnizor, IDNO, data, total, TVA, statut SFS,
  statutul nostru, furnizorul în una.md, poziții potrivite), click → detaliu cu
  pozițiile și potrivirea, butoane «XML», «Repotrivește», «Aterizează în una.md»,
  «Acceptă în SFS», «Respinge în SFS…», «Adaugă furnizorul în una.md».

## 2a. Importul «ca în celelalte baze cloudbd» (13.09.2026, după cerința proprietarului)

Fluxul de mai sus (`EFA_INBOX.land` → `TMDB_XML_FACTURA`) a rămas ca «aterizare
brută»; importul real merge acum **exact ca în BMPUBLIC / FPROIECT**: document
12103 «pachet XML» + OLE → `pkg_edi_xml.import_xml_package_object` (parserul și
validările vendorului, `TMDB_XML_PACKAGE`) → `EFA_INBOX.create_docs_1209`
(documente 1209 cu `VMDB_ST201M/D`, `VMDB01M_VINZ`, analitica după reguli /
cod de bare / denumire). Are și formular nativ 12103 cu acțiunea «Preia din
e-Factura (API)». Punctul 4.1 de mai jos e astfel rezolvat: documentul contabil
**se creează** (1209 «Оприходование товара»). Proba vie, reparațiile și
protocolul: [EFACTURA_IMPORT_PACHET_12103_2026-09-13.md](EFACTURA_IMPORT_PACHET_12103_2026-09-13.md).

## 3. Proba reală (13.09.2026, mediul de probă, contul UNISIM-SOFT)

| Pas | Rezultat |
|---|---|
| `GetInvoicesForSigning` rol 2, Order 1 | 1 factură: **EAA 002514972** de la POSEIDONGRUP S.R.L. (1014600011116) către UNISIM-SOFT, 11.06.2020, 3500,00 lei (TVA 583,33), 1 poziție «Mariflex PU 30 Grey 600 ML» ×35, fără cod de bare; `InvoiceStatus 7` |
| `sync` | `found 1, added 1`; pozițiile în `EFA_IN_ROW`; furnizor **negăsit** în una.md; poziția **nepotrivită** (fără cod de bare, nicio regulă) |
| `land` | `NRDOC 436`, 2 rînduri în `TMDB_XML_FACTURA` (antet `ROWN 0 CODE '0'` cu IDNO/serie/nr/date/total, poziția `ROWN 1`), `FILE_NAME = EFACTURA_IN_EAA_002514972.xml`; a doua aterizare → același NRDOC |
| `PostAcceptedInvoices` | SFS: `Status 2`; `CheckInvoicesStatus` → `InvoiceStatus 3`; coada cumpărătorului goală, factura în `GetAcceptedInvoices`; după `sync` → `STATUS ACCEPTED` |
| rute (test client) | 401 fără sesiune; listă / detaliu / XML / match / land / decision OK |
| teste unitare | `tests/test_efactura.py`: 66 |

Un defect prins în probă: `PostAcceptedInvoices` întoarce `Results/InvoiceResult`
(nu `Invoice`), iar prima versiune raporta «SFS nu a confirmat» deși SFS
acceptase — corectat (și `sync` marchează ACCEPTED după coada acceptate).

## 4. Ce rămîne — decizii ale contabilului, nu de cod

1. **În ce document una.md devine factura primită.** OfficePlus nu are
   formularul `1231`; candidați: «Приёмка товара» (`DOC_88804`) sau
   «Оприходование товара» (`DOC_88803`). După alegere, aterizarea poate crea
   și documentul (antet `VMDB_ST201M` cu furnizorul, atașamentul OLE cu XML-ul,
   pozițiile potrivite) — clonînd structura unui document real din acel formular.
2. **Marfa fără cod de bare**: fie furnizorii pun `BarCode` în XML, fie reguli
   `TMS_IMPORT_EFACTURA` cu card (`DTSC`) pe pozițiile care se repetă, fie
   potrivirea manuală în Delphi — exact ca în celelalte instalări una.md.
3. Pe mediul real: aceleași conturi API ale clientului, `ActorRole 2`.

## 5. Fișiere

`modules/efactura/inbox.py`, `sql/05_efa_inbox.sql` (EFA_IN, EFA_IN_ROW,
EFA_INBOX), `sfs.py` (operațiile de cumpărător), `routes.py` (`/test/inbox…`),
`templates/efactura_test.html` (cardul), `docs/Partner/sfs/ModelFacturaPrimita.xml`
(factura reală de probă, fără semnătură), `tests/test_efactura.py` (6 teste noi).

# Integrarea cu SIA „e-Factura” (SFS.md)

> ## ✅ STAREA CURENTA (31.08.2026): INTEGRAREA ESTE FACUTA
>
> Modulul `modules/efactura/` este scris, instalat pe toate conturile si
> functional. Mai lipsesc **doar credentialele** (utilizatorul API care se
> creeaza in e-Factura de persoana cu rol de Manager).
>
> * Pagina modulului: **`/UNA.md/orasldev/efactura/`** — setari, jurnal,
>   previzualizare XML, buton de trimitere.
> * Detaliile implementarii: [sectiunea 8](#8-implementat-31082026--modulul-modulesefactura)
>   de la finalul acestui document.
> * Ce trebuie de la companie: [sectiunea 5](#5-ce-trebuie-de-la-proprietar-nu-pot-obtine-singur).
>
> Sectiunile 1–7 de mai jos sint **analiza dinaintea dezvoltarii** — se
> pastreaza pentru ca explica DE CE integrarea arata asa (regimuri, metode
> API, capcane). Raspunsul „nu s-a facut" din sectiunea 1 se refera la
> starea de la 30.08.2026, INAINTE de dezvoltare.

---

**Intrebarea proprietarului (30.08.2026):** se poate face partajare cu sfs.md
ca factura sa se descarce in sistem si in e-Factura? S-a facut deja aceasta
integrare in proiect?

## 1. Raspuns scurt (la data analizei, 30.08.2026)

**Atunci integrarea NU exista** — nu era nicaieri in proiect. Singura urma era
o linie in specificatia modulului AGRO:
`Integration with e-factura/customs → Phase 2` (adica amanata, nu executata).

**Da, se poate face** — SFS publica un API oficial pentru sistemele contabile
(ERP), exact pentru acest scenariu. → **A si fost facuta a doua zi**, vezi
sectiunea 8.

## 2. Ce am verificat (inainte de dezvoltare)

| Verificare | Rezultat |
|---|---|
| Cod: `efactura`, `e-factura`, `sfs.md`, `mconnect`, `servicii.fisc` | doar mentiunea „Phase 2" din specul AGRO |
| Obiecte Oracle `%EFACT%`, `%E_FACT%`, `%SFS%` in schema OFFICEPLUS | niciunul |
| Aceleasi obiecte in TOATE schemele vizibile (`ALL_OBJECTS`) | niciunul (doar pachete Oracle native) |
| Rechizitele necesare exista in ERP? | **da**: `TMS_ORG.CODFISCAL` (IDNO), conturi bancare in `VMS_ORG_CONT_FISC` |
| Documentele magazinului | `TMDB_DOCS`, `SYSFID=12280` — **cont de plata**, 50 in ultimele 30 de zile |

**Atentie la o diferenta importanta:** magazinul emite acum *cont de plata*
(factura proforma), NU *factura fiscala*. In e-Factura se transmit facturi
FISCALE. Deci integrarea presupune si definirea documentului fiscal in ERP,
nu doar transmiterea celui existent.

Clienti persoane juridice in magazin: **5** din 17 (doar pentru ei e relevanta
e-Factura; persoanelor fizice nu li se emite factura fiscala electronica).

## 3. Ce ofera SFS (verificat in ghidul oficial de integrare)

SIA „e-Factura" expune un **serviciu SOAP/WCF** (nu REST):
`basicHttpBinding`, securitate `TransportWithMessageCredential`, contract
descris prin WSDL. Autentificare: utilizator + parola pe HTTPS, sistemul
intoarce un **token de sesiune** folosit la apelurile urmatoare.

**Metodele disponibile:**

| Trimitere | Citire |
|---|---|
| `PostInvoices` — transmite facturi (XML) | `GetAcceptedInvoices` |
| `PostInvoicesWithAttachment` | `GetRejectedInvoices` |
| `PostAcceptedInvoices` | `GetInvoicesBySeriaNumber` |
| `PostRejectedInvoices` | `GetInvoicesContentForPrint` |
| `PostCanceledInvoices` | `GetInvoicesForSigning`, `GetInvoicesQRcodes` |
| | `GetTaxpayersInfo`, `GetLogs` |

`PostInvoices` primeste `PostInvoicesRequest {RequestId, InvoicesXml,
ActorRole, InvoicesXmlStatus}` si intoarce `PostInvoicesResponse
{TotalInvoices, TotalInvoicesPosted, TimeStamp, Status, RequestId,
ErrorMessage}`. Continutul facturii — **XML valid dupa schema XSD** a SFS.

## 4. Doua regimuri — de aici depinde arhitectura

| | Semi-automatizat | Complet automatizat |
|---|---|---|
| Transmiterea prin API | da | da |
| Semnatura electronica | **manual**, in interfata web e-Factura, de persoana autorizata | automat, din sistem |
| Certificat digital in momentul transmiterii | **nu e nevoie** | **necesar** |
| Anulare / respingere | manual, din web | din sistem |
| Efort de implementare | mai mic | mai mare (integrarea semnaturii) |

Pentru inceput, regimul **semi-automatizat** este alegerea rationala: factura
pleaca din sistemul nostru automat, iar contabilul doar o semneaza in
e-Factura. Trecerea la „complet automatizat" se poate face ulterior, fara a
reface transmiterea.

## 5. Ce trebuie de la proprietar (nu pot obtine singur)

1. **Utilizator API in e-Factura.** Se creeaza DOAR de persoana cu rol de
   Manager (Director) al companiei: e-Factura → *Setari* → *Utilizatorii
   companiei* → butonul **„CREEAZĂ UN UTILIZATOR API"**. De acolo ies
   utilizatorul si parola pentru API.
2. **Decizia asupra regimului** (semi vs complet automatizat).
3. Pentru regimul complet automatizat — **certificatul digital** al companiei.
4. Confirmarea **organizatiei-vinzator** (IDNO-ul cu care se emit facturile).

## 6. Ce fac eu dupa primirea acestora

Modul izolat `modules/efactura/` (aceeasi schema ca `modules/partner/`):
contur Oracle propriu `EFA_*` (jurnal de transmiteri, statusuri, erori),
maparea documentului ERP → XML dupa XSD-ul SFS, buton „Trimite in e-Factura"
in back-office plus transmitere automata optionala, sincronizarea statusurilor
(`GetAcceptedInvoices` / `GetRejectedInvoices`), stocarea QR-codurilor si a
raspunsurilor pentru audit. Codul comun nu se atinge.

**Estimare:** transmiterea + jurnalul + statusurile — realizabile imediat ce
exista utilizatorul API. Partea nesigura fara acces este **XSD-ul exact** al
facturii: se descarca din sectiunea *Help* a e-Factura, cu contul companiei.

## 7. Surse

- [Ghid de integrare semi-automatizata SIA „e-Factura"](https://efactura.sfs.md/Help/Ghid_integrare_Semi_Automatizata.pdf)
- [CTIF — integrarea sistemelor contabile cu noua versiune „e-Factura"](https://www.ctif.gov.md/ro/integrarea-sistemelor-de-contabilitate-ale-agentilor-economici-cu-noua-versiune-sistemului-e)
- [SFS — e-Factura in baza fisierului XML](https://sfs.md/ro/stiri/in-atentia-contribuabililor-care-emit-e-factura-in-baza-fisierului-xml)
- [Ghidul utilizatorului SI „e-Factura" v.2.0](https://egov.md/sites/default/files/document/attachments/ghid_de_utilizare_e-factura.pdf)
- Suport tehnic CTIF: **022 822222**

---

## 8. IMPLEMENTAT (31.08.2026) — modulul `modules/efactura/`

Integrarea este scrisa si instalata pe toate conturile; **asteapta doar
credentialele** (utilizatorul API din e-Factura). Pina atunci modulul
functioneaza „in gol": arata XML-ul care ar pleca, dar nu trimite nimic.

### Trei intrari, o singura logica

Ca si forma tiparita a contului, trimiterea e disponibila din trei locuri, iar
in spate ruleaza EXACT acelasi cod (`modules/efactura/controller.py`):

| Intrare | Adresa | Cine are voie |
|---|---|---|
| Back-office | `/UNA.md/orasldev/efactura/` | sesiunea portalului |
| Cabinetul clientului | buton «e-Factura» linga PDF/HTML in „Comenzile mele" | clientul, DOAR documentele lui (serverul verifica) |
| API intern | `/UNA.md/orasldev/efactura/api/send/<doc>`, `/api/status/<doc>`, `/api/preview/<doc>`, `/api/docs`, `/api/health` | `X-API-Key` — acelasi antet ca restul API-ului Biro26, pentru back-office-urile native |

### Contur Oracle propriu (prefix EFA_)

`EFA_SETTING` (setarile integrarii), `EFA_DOC` (o linie per document:
status NEW/SENT/ACCEPTED/REJECTED/ERROR, numarul SFS, RequestId, eroarea),
`EFA_LOG` (jurnal append-only: ce XML a plecat si ce a raspuns SFS — pentru
audit fiscal). Instalator propriu:
`python3 modules/efactura/scripts/efactura_deploy.py`. Instalat 31.08.2026,
7 obiecte VALID.

### Clientul SOAP

Scris de mina, fara `zeep` (nu e in venv-ul productiei, iar o dependinta noua
pe conturul viu nu se justifica pentru cinci metode): plic SOAP cu
WS-Security `UsernameToken` peste HTTPS, exact cum cere
`basicHttpBinding` / `TransportWithMessageCredential` din ghidul SFS.
Metode acoperite: `PostInvoices`, `GetAcceptedInvoices`, `GetRejectedInvoices`,
`GetInvoicesBySeriaNumber`, `GetTaxpayersInfo`, `GetLogs`.

### Rechizitele vinzatorului — din ERP, nu din admin

`Biro26Report.doc_data` da deja blocul `firm` din care se tipareste contul:
IDNO `1026602001837`, denumirea, adresa, IBAN, banca. Modulul il foloseste
ca sursa, iar setarile din admin doar il SUPRASCRIU. Asa nu se poate intimpla
ca pe hirtie sa fie o firma si in e-Factura alta.

### Verificat pe documente reale

XML valid pentru contul A-86 (televizor + tonere) si pentru un client
persoana juridica (`CABINETUL AVOCATULUI…`, IDNO 3202121297825 in `<Buyer>`);
caracterele speciale (`"`, `&`, `<`) escapate; fara credentiale — mesaj clar,
nu exceptie; toate cele trei intrari intorc 401 fara autentificare.
Teste: `tests/test_efactura.py` (7 passed), inclusiv cele doua de izolare.

### Ce ramine de facut cind vin credentialele

1. Se completeaza in pagina modulului: **endpoint**, **utilizator API**,
   **parola** (+ eventual seria facturii).
2. Butonul **«Testează conexiunea»** confirma accesul.
3. La primul document real se compara XML-ul nostru cu **XSD-ul** descarcat
   din sectiunea *Help* a e-Facturii si se aliniaza denumirile nodurilor
   (XML-ul plecat se vede in jurnal, deci alinierea se face pe date reale).

---

## 9. Pornirea in 4 pasi (cind aveti utilizatorul API)

1. **Creati utilizatorul API** in e-Factura — DOAR persoana cu rol de
   Manager (Director) poate: *Setări → Utilizatorii companiei →*
   **„CREEAZĂ UN UTILIZATOR API"**. Notati utilizatorul si parola.
2. **Completati setarile** in `/UNA.md/orasldev/efactura/`: endpoint-ul
   serviciului, utilizatorul, parola. Restul (IDNO, denumire, IBAN, banca)
   se ia automat din ERP — se completeaza doar daca vreti sa suprascrieti.
3. **Apasati „Testează conexiunea"** — confirma accesul fara sa trimita nimic.
4. **Trimiteti primul document** si comparati XML-ul din jurnal cu **XSD-ul**
   descarcat din sectiunea *Help* a e-Facturii. Daca SFS cere alte denumiri de
   noduri, se aliniaza in `modules/efactura/sfs.py` (`build_invoice_xml`) —
   pe date reale, nu pe presupuneri.

### Verificat inainte de predare (31.08.2026)

| Ce | Rezultat |
|---|---|
| Obiecte Oracle `EFA_*` | 7, toate VALID |
| Setari | `configured = false` — asteapta credentialele; regim `semi`; doar persoane juridice |
| Document real de la client juridic → XML | contul **A-72**: vinzator IDNO `1026602001837`, cumparator IDNO `9999000161242`, 2 pozitii, total `222 000.00` |
| Trimitere fara credentiale | mesaj clar, nu exceptie |
| Jurnal | scrie corect (5 inregistrari) |
| Cele trei intrari fara autentificare | 401 / redirect la login |

---

## 10. Mini-modulul universal «Factura de TEST» (31.08.2026)

**Pentru ce:** orice director isi emite o factura fiscala de proba cu
rechizitele LUI, pe marfa sau serviciu, ca sa vada ca lantul
«sistemul nostru → SIA e-Factura → semnare» chiar merge — inainte ca prin el
sa treaca documentele reale.

**Adresa:** `/UNA.md/orasldev/efactura/test` (si plachet in hub-ul Biro26).

### Pagina e AUTONOMA — nu atinge setarile niciunui magazin

Corectat 31.08.2026, la cererea proprietarului. Pagina probei nu mai citeste
`EFA_SETTING`, nu mai afiseaza semnatarii configurati si nu mai ia rechizitele
din ERP-ul Biro26 (`VMS_ORG_CONT_FISC`). Tot ce foloseste vine din formular:
contul API, rechizitele vinzatorului si ale cumparatorului, pozitiile. Asa
proba merge la fel din orice modul al platformei, la orice director. Efectul
se vede si in teste: setul modulului ruleaza in ~0,3 s in loc de ~9 s, pentru
ca nu mai deschide Oracle pentru randarea paginii. Regula e prinsa in test
(`test_page_template_has_no_shop_coupling`, `test_test_page_never_reads_shop_settings`).

### Mediul il decide ADRESA serviciului

Implicit pagina merge pe mediul de **proba** al SFS —
`https://api-test.fisc.md/Service.svc`, constanta `sfs.TEST_ENDPOINT`
(o proprietate a SFS, nu o setare a firmei, de aceea sta in cod). Daca in
cimpul «Adresa serviciului SFS» se pune adresa sistemului real, factura devine
un **document fiscal adevarat**. Textul de avertisment din pagina spune exact
asta — varianta veche afirma neconditionat «sistem fiscal real», ceea ce nu
era adevarat cu adresa de test.

### Adresele REALE ale platformei API (ghidul SFS, verificate 31.08.2026)

Prima incercare reala a cazut cu `urlopen error [Errno -2]`, pentru ca in
setari statea `api-test.fisc.md` — gazda care nu se rezolva nici public
(`dig @8.8.8.8` fara raspuns), nici de pe serverele noastre. Ghidul de
integrare ERP publicat de SFS da adresele corecte:

| Ce | Adresa |
|---|---|
| Portal de test | `https://preproductie.sfs.md` |
| e-Factura, mediu de test | `https://efactura-pre.sfs.md` |
| **API, mediu de test** | `https://apiefactura-pre.sfs.md` |
| **API, mediu real** | `https://efactura-api.sfs.md` |

Verificat pe viu: `https://efactura-api.sfs.md/Service.svc` intoarce pagina
WCF si `?wsdl` complet (19 KB, `targetNamespace=http://tempuri.org/`).
`apiefactura-pre.sfs.md` raspunde 403 pina la deschiderea accesului.

Constantele `sfs.ENDPOINT_TEST` / `sfs.ENDPOINT_PROD` le tin in cod, iar
pagina probei are doua butoane care le pun in cimp.

### Accesul se da pe lista de IP — asta se cere de la SFS

Pentru mediul de test se trimite un e-mail la **asistenta@sfs.md** cu: IDNO,
numele si prenumele, IDNP, rolul in sistem (director / contabil), adresa
electronica, telefonul si **IP-ul extern al statiei sau serverului**.

Adresa de iesire conteaza pentru ca platforma filtreaza dupa ea: `GET` pe
`?wsdl` merge de oriunde, dar un `POST` de pe un IP nedeschis primeste o
PAGINA HTML cu status 500, nu un raspuns SOAP (masurat cu credentiale
evident invalide). De aceea clientul recunoaste acum acest caz si scrie
exact asta, in loc sa arate blocul HTML.

**Adresa care conteaza e a SERVERULUI, nu a statiei directorului**: apelul
SOAP il face aplicatia, nu browserul. Masurate pe viu (31.08.2026):

| Contur | IP de iesire | `apiefactura-pre.sfs.md` |
|---|---|---|
| officeplus.md (masina `192.168.0.250`) | **93.115.136.18** | 403 «Accesul este restricționat!» |
| nufarul | **92.5.3.187** | 403 |

Pe mediul REAL (`efactura-api.sfs.md`) de pe aceleasi IP-uri: `GET` pe
`?wsdl` da 200, iar `POST` da 500 «A apărut o eroare» — tot o pagina de la
nginx-ul SFS, nu un raspuns SOAP. Comportamentul nu se schimba nici cu
antetul WS-Security completat, nici cu alt User-Agent, deci nu tine de
plicul nostru.

Din 31.08.2026 butonul «Verifică contul» arata si **IP-ul de iesire al
serverului** — exact numarul care trebuie trimis la SFS.

### Accesul a fost acordat (tichet SFS TT1651472, 02.09.2026)

Raspunsul CTIF: accesul deschis conform cererii; portal de test
`https://preproductie.sfs.md/` (autentificare cu semnatura electronica, ca pe
sfs.md); platforma API de test `https://apiefactura-pre.sfs.md/`; utilizatorul
API se creeaza din SIA e-Factura → Setări → Utilizatorii companiei → «Creați
utilizator API»; ghidurile — la rubrica Ajutor.

Masurat imediat dupa, de pe AMBELE adrese de iesire (93.115.136.18 si
92.5.3.187):

| Proba | Rezultat |
|---|---|
| `GET /Service.svc`, `?wsdl` pe mediul de proba | **200**, WSDL de 19.630 B (inainte: 403) |
| contractul de proba vs cel real | **identic**: aceleasi 19 operatii, aceleasi tipuri (`PostInvocesRequest`, `SignRequest`, …), acelasi namespace DataContract |
| `POST` gol | 400 (raspunsul WCF) |
| `POST` cu `Content-Type: application/soap+xml` (SOAP 1.2) | 415 (raspunsul WCF) |
| `POST` cu actiune inexistenta | 500, **pagina HTML** |
| `POST Test` cu utilizator/parola invalide | 500, **pagina HTML** (`Server: nginx/1.30.1`) |

Concluzia, importanta pentru depanare: cererile AJUNG la serviciu (400 si
415 sint ale WCF), dar **orice fault SOAP — pe care WCF il trimite cu status
500 — este inlocuit de nginx-ul SFS cu pagina lor HTML**. Textul erorii
(autentificare gresita, XML respins de contract etc.) nu se poate citi de la
SFS; doar apelul reusit (200) intoarce SOAP. De aceea clientul spune acum:
**403 + HTML = IP-ul nu e pe lista; 500 + HTML = eroare SOAP mascata**, cel
mai des utilizator/parola API gresite sau cont creat pe alt mediu decit
adresa aleasa.

**Ce urmeaza, din partea proprietarului** (cere semnatura electronica, nu se
poate automatiza): intrare pe `https://preproductie.sfs.md/` cu semnatura →
Cabinetul personal → SIA e-Factura → Setări → Utilizatorii companiei →
«Creați utilizator API» — o data pentru primul semnatar (Tuhari Pavel) si o
data pentru al doilea (Tuhari Oxana). Perechile utilizator/parola se scriu in
pagina probei (`/UNA.md/orasldev/efactura/test`), adresa = «mediu de probă»,
apoi «🔌 Verifică contul». Un ✅ acolo inseamna ca lantul e intreg; abia apoi
se trimite prima factura de proba si se compara XML-ul cu XSD-ul din Ajutor.

### Prima proba reala: respinsa — si de ce nu s-a vazut (02.09.2026, seara)

Cu conturile `ptuhari` / `otuhari` create pe portalul de proba, «Verifică
contul» a dat ✅ pe ambele cozi. «Trimite proba» de doua ori (20:52, 20:57):
SIA e-Factura a RASPUNS (SOAP 200), cu `Status 3` si

> Validation failed: The 'Invoices' element is not declared. The 'Invoice'
> element is not declared. The 'Seria' element is not declared. …

Adica XML-ul nostru era inventat: radacina si toate nodurile. Nimic nu s-a
inregistrat in e-Factura. Pe pagina s-a vazut doar un JSON taiat, iar
`EFA_LOG` tine 2000 de caractere — de aici «непонятно что происходит».

**Ce s-a schimbat:**

1. **XML-ul dupa XSD-ul oficial** — `TaxInvoiceSchema.xsd` si
   `ModelFacturafiscala.xml` din e-Factura → Ajutor, copiate in
   `docs/Partner/sfs/`. Structura: `Documents/Document/SupplierInfo` cu
   `Seria?, Number?, IssuedDate?, DeliveryDate!, Supplier@, Buyer@, Total?,
   TotalTVA?, Merchandises/Row@, CreationMotiv!` — in aceasta ordine, fara
   namespace; rechizitele sint ATRIBUTE (`IDNO`, `Title`, `Address`,
   `TaxpayerType` 1=juridic/2=fizic/3=nerezident; `BankAccount@Account
   @BranchTitle @BranchCode`); rindul cere si valorile FARA TVA. Validat
   local cu `xmllint --schema` (test in `tests/test_efactura.py`).
2. **Jurnal complet, `EFA_CALL`** (`sql/02_efa_call.sql`, instalat): fiecare
   apel SOAP — plicul cu parola mascata, raspunsul brut, HTTP, durata,
   verdict (`ok / rejected / fault / html / network`). `journal.py`, un
   singur apel din `sfs.call()`. Pagina probei il arata jos; click pe rind =
   cererea si raspunsul intregi. Ruta `GET /test/log`.
3. **Rezultatul trimiterii, in cuvinte**: «Acceptată» + unde apare in
   e-Factura (facturile de semnat, Order 1) sau «Respinsă» + lista erorilor
   SFS, una pe rind.
4. **Parolele in Keychain, nu in pagina**: cimpurile au `autocomplete`
   standard in doua formulare, deci Safari/Chrome ofera salvarea; iar pentru
   proba automata de pe Mac — `modules/efactura/scripts/efactura_smoke.py`
   cu parolele din macOS Keychain (`security add-generic-password -s
   efactura-api-pre -a ptuhari -w`, la fel `otuhari`). Scriptul face cap-coada:
   Test pe ambele conturi → factura de 1 leu → PostInvoices → cozile Order
   1/2 → jurnalul. Fara `--send` nu trimite nimic; `--real` = mediul real.

### Plicul SOAP a fost aliniat la contractul VIU al serviciului

Citind `?wsdl` si `?xsd=xsd2` au iesit la iveala patru greseli pe care nicio
proba locala nu le-ar fi prins — s-ar fi vazut abia cind SFS ar fi refuzat
apelul:

1. **`SOAPAction` era `{ns}/{metoda}`**, iar contractul cere
   `{ns}/IService/{metoda}` — WCF ar fi raspuns «action not recognized».
2. **Copiii lui `<request>` stateau in `tempuri`**, dar tipurile sint din
   `http://schemas.datacontract.org/2004/07/AX.EFactura.Model.ApiModel`:
   DataContractSerializer i-ar fi citit ca `null`, adica factura ar fi
   „plecat" goala.
3. **Ordinea cimpurilor** trebuie sa fie cea din XSD (intii membrii clasei de
   baza): `RequestId`, `ActorRole`, apoi `InvoicesXml`, `InvoicesXmlStatus`.
4. **Metode cu alta structura decit presupuneam:** `GetAcceptedInvoices` si
   `GetRejectedInvoices` primesc doar `ActorBaseRequest` (fara interval de
   date, deci parametrul `days` din `refresh_statuses` nu are ce filtra);
   `GetInvoicesBySeriaNumber` cere o LISTA `ArrayOfInvoiceIndentificator`,
   nu doua cimpuri; `GetTaxpayersInfo` cere `FiscalCodes` ca
   `ArrayOfstring`; iar verificarea conexiunii foloseste acum metoda `Test`
   a serviciului in locul lui `GetLogs` cu `<Top>1</Top>` (cimp inexistent).

Toate cele patru sint prinse in teste (`TestSoapMatchesWsdl`).

### Plafonul de suma — pe SERVER, nu doar in formular

De la **0,01 lei** (un ban) pina la **10,00 lei**, maximum 5 pozitii. Limita
ramine si in mediul de proba, ca sa fie inofensiva si cind cineva schimba
adresa pe cea reala: daca o proba ramine uitata sau se semneaza din greseala,
paguba trebuie sa fie de citiva bani. Verificarea e in `testff.validate()`,
deci un apel direct la API nu o poate ocoli — verificat: `POST /test/send` cu
25 lei intoarce 400.

### Contul API cu care se face proba

Contul API se scrie **in pagina**: utilizator + parola pentru primul semnatar,
optional inca o pereche pentru al doilea. Proba pleaca sub acel cont —
`sfs.SfsClient.from_api()` nu citeste niciodata `EFA_SETTING`. Daca in formular
e un singur cont, tot el serveste si a doua coada de semnare, ca sa nu se
combine doi oameni intr-o proba. Fara utilizator si parola, trimiterea e
refuzata cu mesaj clar, fara apel in retea.

Parolele scrise aici traiesc **numai cit tine apelul**: nu se scriu in
`EFA_SETTING`, nu intra in jurnal si nu se pastreaza in browser (autosalvarea
retine doar utilizatorii). Butonul «🔌 Verifică contul» (`POST /test/ping`)
incearca ambele conturi fara sa trimita nimic in sistem.

### Valorile introduse se pastreaza singure

Tot ce se scrie in formular (rechizitele vinzatorului si ale cumparatorului,
pozitiile, cota TVA, seria si numarul) se salveaza automat in `localStorage`
sub cheia `efa_test_form_v1` si revine la urmatoarea deschidere a paginii —
proba se repeta fara sa se reintroduca nimic. Datele stau **doar in browserul
operatorului**, nu pe server. Butonul «🗑 Curata datele» sterge tot si readuce
formularul la starea initiala. In mod privat, cind `localStorage` arunca
exceptie, formularul merge mai departe fara salvare.

### Universal: activarea in alt modul = O SINGURA linie

Motorul (`modules/efactura/testff.py`) nu stie nimic despre Biro26. Orice
modul al platformei Artgranit pune butonul asa:

```html
<script src="/UNA.md/orasldev/efactura/widget.js"></script>
```

Widget-ul adauga butonul plutitor si deschide pagina probei intr-o fereastra
separata. Nu cere gazdei nici stiluri, nici biblioteci, nici modificari in
codul ei. Exista si calea masina-la-masina: `POST /test/preview`,
`POST /test/send`, `GET /test/queues` cu `X-API-Key`.

### DOUA semnaturi — doua conturi API

Ghidul SFS confirma ce spunea proprietarul: sistemul tine **cozi separate de
semnare** — `GetInvoicesForSigning` cu `Order = 1` (factura NEsemnata,
asteapta prima semnatura) si `Order = 2` (deja semnata cu prima, asteapta a
doua). De aceea in setari sint **doua conturi API** (de obicei director si
contabil-sef) plus numele semnatarilor. Al doilea e optional: daca lipseste,
se foloseste primul. Butonul «Vezi cozile de semnare» din pagina probei arata
imediat daca factura a ajuns in coada.

Documentul de test pleaca **nesemnat** (`InvoicesXmlStatus = 0`); semnarea
ramine la cei doi semnatari — in interfata web (regim semi) sau prin cozile
de mai sus.

### Eroare de protocol prinsa aici

Prima versiune trimitea `ActorRole = "Supplier"` si `InvoicesXmlStatus =
"Draft"` — **texte**. In ghidul SFS (tabelul 24) ambele sint **numere**:
rolul 1 = furnizor, 2 = cumparator, 3 = transportator; statutul 0 = nesemnat,
1 = semnat. SFS ar fi respins documentele. Corectat, cu test care fixeaza
valorile.

### Verificat

12 teste (2 de izolare, XML, plafon de suma, cimpuri obligatorii, valorile de
protocol). Pe baza vie: salvarea celor doua conturi, parolele nu se intorc
niciodata in interfata, o parola goala NU sterge cea salvata, clientul alege
corect contul dupa semnatar.

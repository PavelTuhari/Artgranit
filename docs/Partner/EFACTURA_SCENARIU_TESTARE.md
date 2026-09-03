# e-Factura (SFS) — scenariul de testare si toate nuantele descoperite

Actualizat 02.09.2026, dupa prima zi de probe reale pe mediul de test al SFS.
Fiecare nuanta de mai jos a iesit dintr-un raspuns REAL al sistemului —
toate sint in jurnalul `EFA_CALL` (pagina probei, jos).

## 1. Ce se testeaza si in ce ordine

| Pas | Ce | Cum | Semnul ca e bine |
|---|---|---|---|
| 0 | acces | `GET https://apiefactura-pre.sfs.md/Service.svc?wsdl` de pe IP-ul serverului | 200 + WSDL (403 = IP-ul nu e pe lista SFS) |
| 1 | conturile API | pagina probei → «🔌 Verifică contul» (sau `efactura_smoke.py`) | ✅ pe `prima_semnatura` si `a_doua_semnatura` (metoda `Test`) |
| 2 | XML-ul | «👁 Vezi XML-ul»; local `xmllint --schema TaxInvoiceSchema.xsd` (test automat) | valid |
| 3 | trimiterea | «📤 Trimite proba» (max 10 lei) sau `efactura_smoke.py --send` | `Status 2, TotalInvoicesPosted 1` |
| 4 | coada primei semnaturi | «👁 Vezi cozile» (Order 1, contul primului semnatar) | factura apare, `InvoiceStatus 0` (nesemnata) |
| 5 | prima semnatura | pe `preproductie.sfs.md`, cu semnatura electronica a primului semnatar | factura DISPARE din Order 1, APARE in Order 2 si primeste numarul SFS (ex. `000002358`) |
| 6 | a doua semnatura | la fel, al doilea semnatar | dispare din Order 2; apare la `GetAcceptedInvoices` |
| 7 | documente reale | back-office (`/admin`, «Trimite in e-Factura») si API intern (`POST /api/send/<cod>`) | `SENT` in `EFA_DOC`, factura in Order 1 |

Rulat integral pe 02.09.2026: pasii 0–5 pe factura de proba `TEST-09022119`
(1 leu), pasul 7 pe patru conturi reale din ERP-ul OfficePlus: **A-81, A-70**
(prin controller) si **A-79, 268** (prin API-ul intern de pe serverul de
birou). Toate patru: acceptate, in coada primei semnaturi.

## 2. Nuantele — fiecare cu raspunsul SFS care a dezvaluit-o

1. **Radacina XML e `Documents/Document/SupplierInfo`**, nu ceva inventat.
   Raspuns: «Validation failed: The 'Invoices' element is not declared…».
   Schema oficiala: e-Factura → Ajutor → `TaxInvoiceSchema.xsd` (copie in
   `docs/Partner/sfs/`). Rechizitele sint ATRIBUTE; rindurile sint
   `Merchandises/Row` cu preturile FARA TVA si totalurile pe rind.
2. **`CreationMotiv` e doar 4 (Livrare) sau 5 (Non-livrare).** Raspuns:
   «Motivul Crearii este indicat incorect trebue sa fie 4 sau 5». Modelul
   oficial din Ajutor are 1 — e depasit.
3. **Nodurile din exportul real trebuie sa existe, chiar goale**:
   `<Seria/>`, `<Number/>`, `BankAccount` la AMBELE parti,
   `VehicleLogbook`, `Redirections`, atributele `NResident`/`IsSupplierOnly`.
   Raspuns fara ele: «Object reference not set to an instance of an object»
   (NullReferenceException la ei; nu spune ce lipseste — s-a gasit prin
   comparatie cu exportul real din ghid).
4. **Data eliberarii: doar azi … azi+10 zile.** Raspuns: «Specify the correct
   date for the IssuedDate element … 0 days before or 10 days after the
   current date». Prima interpretare (refuz pentru documente vechi) a fost
   GRESITA si l-a blocat pe contabil pe 03.09.2026 cu un cont de ieri:
   documentul din ERP e un CONT la plata (comanda), nu factura fiscala.
   Corect: data facturii fiscale = ziua trimiterii — modulul pune
   IssuedDate/DeliveryDate = azi, data contului ramine in ERP.
   `override_date` exista DOAR pentru probe.
4a. **Diacriticele nu trec prin Oracle CL8MSWIN1251**: mesajul de eroare
   pentru aplicatia nativa a ajuns ca «Data eliberA?rii … A®n trecut».
   API-ul pentru una.md raspunde fara diacritice romanesti (chirilicele
   raman, CP1251 le are).
5. **SFS normalizeaza documentul**: `Seria`/`Number` vin goale pina la
   semnare (le da sistemul — proba a primit `000002358` la prima semnatura);
   `Title`/`Address` ale partilor sint inlocuite din registrul fiscal dupa
   IDNO (Coninfo, INTER-ENZIM-COM, «UNIUNEA PENTRU PREVENIREA…» au aparut cu
   denumirile din registru, nu cu ale noastre). Ce trimitem ca denumire e
   orientativ.
6. **Cumparatorul probei**: pagina proprietarului avea Coninfo SRL
   (1012600013725); scriptul de proba folosea propria firma — corectat la
   Coninfo. Nu conteaza pentru SFS (vezi 5), conteaza pentru claritatea
   probei.
7. **`TaxpayerType`**: 1 juridic, 2 persoana fizica, 3 nerezident. Se deduce
   din IDNO (pe 1) / IDNP (pe 2) cind nu e dat.
8. **Cota TVA** se deduce din document (tva/baza → 20/12/8/0); fara TVA in
   document → setarea `tva_rate` (implicit 20). De verificat cu contabilul
   pe documentele cu `tva = 0`.
9. **Erorile SOAP nu se vad**: orice fault (statut 500) e inlocuit de
   nginx-ul SFS cu o pagina HTML; 403 HTML = IP-ul nu e pe lista. Doar
   apelul reusit (200) intoarce SOAP — de aceea jurnalul complet si mesajele
   traduse conteaza atit.
10. **Accesul e pe IP-ul SERVERULUI**, nu al statiei directorului: 93.115.136.18
    (biroul) si 92.5.3.187 (nufarul). Se cere la asistenta@sfs.md.
11. **Doi semnatari = doua conturi API si doua cozi** (`GetInvoicesForSigning`
    Order 1 / Order 2). Al doilea e optional pentru firmele cu un semnatar.
12. **Contractul SOAP**: SOAPAction `http://tempuri.org/IService/<Metoda>`;
    copiii lui `<request>` in namespace-ul DataContract, in ordinea din XSD
    (RequestId, ActorRole, …). Mediul de proba si cel real au contract
    identic (19 operatii).
13. **Cumparatorul trebuie sa existe in registrul fiscal.** Raspuns pe A-74
    (client de test «SRL TEST Casa Operator», IDNO 1026602001999): «Buyer
    1026602001999 isn't registered in the fiscal registry». Clientii fictivi
    din ERP nu pot primi e-Factura; in productie e un semnal ca IDNO-ul din
    fisa clientului e gresit. Cifra de control (ponderi 7,3,1 pe 12 cifre,
    mod 10) desparte cazurile: fictivul pica la ea, deci modulul il refuza
    LOCAL (`rules.idno_error`), fara apel la SFS. Un IDNO corect ca forma dar
    absent din registrul de PROBA (Fundatia Terre des hommes, 1012620009625)
    e respins de SFS — registrul mediului de test nu e neaparat complet;
    pe mediul real se verifica din nou.
14. **Actiunea din back-office-ul nativ una.md** (`EFA_NATIVE.send_doc_pr`)
    merge pe HTTP simplu, sub `/api/biro26/efactura/…` — singurul prefix pe
    care intrarea officeplus.md nu-l redirecteaza la HTTPS (Oracle 11g nu are
    wallet TLS). Verificat din Oracle: trimitere, refuz cu mesaj in romana,
    ORA-20000 cu textul erorii. Actiunea insasi e inregistrata in
    configuratorul aplicatiei native (A$ADM/A$ADP, OBJ_ID 11522, formularul
    «CONT la plata»), clona actiunii «Сгенерировать счета» — script
    idempotent `efactura_native_action.py`.
15. **Idempotenta**: pe 03.09.2026 actiunea din una.md a reusit in tacere si
    a fost apasata de 4 ori pe A-89 -> 4 facturi in mediul de proba. Acum un
    document SENT nu se retrimite fara `resend` explicit, iar rezultatul
    (trimis / eroare / deja trimis) se scrie in istoria documentului
    (`TMDB_DOCS_LOG`, prin `DOCLOG`, kind `EFA`).
16. **Parolele**: niciodata in pagina/jurnal/chat. In browser — managerul
    de parole (Safari → Keychain); pentru probe automate — macOS Keychain
    (`security add-generic-password -s efactura-api-pre -a <utilizator> -w`),
    citite direct in variabile de mediu.

## 3. Ce ramine de facut pina la productie

- semnatura a doua pe proba (pasul 6) si pe cele patru facturi reale;
- contul API REAL (creat pe `sfs.md`, de firma care EMITE facturile — in
  productie furnizorul e firma din ERP, nu firma IT) si accesul IP pe
  `efactura-api.sfs.md` (cererea: `SCRISOARE_ACCES_EFACTURA_PROD.md`);
- in Setari e-Factura: adresa reala, conturile reale, `seller_*` GOALE
  (se ia firma din ERP), `seria` reala, `tva_rate` confirmat de contabil;
- regula datei in procesul de lucru: factura se trimite in ziua eliberarii.

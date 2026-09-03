# Cerere de acces la platforma API „e-Factura" — MEDIUL REAL (NU MAI E NECESARĂ)

> **03.09.2026 — nu se trimite.** Răspunsul CTIF (Secția suport sisteme
> informaționale fiscale, la TT1651472): pentru mediul de producție *nu este
> necesară acordarea unui acces suplimentar sau includerea adreselor IP
> într-o listă permisă*. Utilizatorii API pentru mediul real se creează din
> SIA e-Factura de pe portalul real `sfs.md` → Cabinetul personal → SIA
> E-factura/Setări → Utilizatorii companiei → «Creați utilizator API».
> Textul de mai jos rămîne doar ca istoric.

**Către:** asistenta@sfs.md
**De la:** info@una.md
**Subiect:** Re: TT1651472 — solicitare acces la mediul real al platformei API SIA „e-Factura" — „UNISIM-SOFT" S.R.L., IDNO 1003600116460

---

Bună ziua,

Vă mulțumim pentru soluționarea solicitării TT1651472. Confirmăm că
integrarea a fost verificată cu succes pe mediul de test:

- conturile API create pe `https://preproductie.sfs.md/` (utilizatorii
  `ptuhari` și `otuhari`) se autentifică pe `https://apiefactura-pre.sfs.md/`;
- la 02.09.2026, ora 21:19, o factură de probă a fost transmisă prin
  `PostInvoices` și înregistrată (`Status 2`, `TotalInvoicesPosted 1`),
  fiind vizibilă în coada de semnare (`GetInvoicesForSigning`, Order 1);
- XML-ul facturii respectă `TaxInvoiceSchema.xsd` publicată la rubrica Ajutor.

Vă rugăm să ne acordați accesul la **mediul real al platformei API**
(`https://efactura-api.sfs.md/`) pentru aceleași adrese IP externe de pe care
se fac apelurile (serverele aplicației, nu stațiile de lucru):

| Adresa IP | Ce este |
|---|---|
| 93.115.136.18 | serverul de producție al aplicației (magazinul officeplus.md) |
| 92.5.3.187 | al doilea server al aceleiași aplicații |

Datele agentului economic rămân cele din solicitarea TT1651472
(„UNISIM-SOFT" S.R.L., IDNO 1003600116460, or. Chișinău, str. Alba Iulia,
75/b, administrator Tuhari Pavel).

Vă rugăm să confirmați:

1. dacă utilizatorii API pentru mediul real se creează din SIA e-Factura de
   pe portalul real (`https://sfs.md/` → Cabinetul personal → Setări →
   Utilizatorii companiei → «Creați utilizator API»), la fel ca pe cel de test;
2. dacă lista de acces IP se aplică separat pentru mediul real;
3. adresa exactă a serviciului pentru mediul real — folosim
   `https://efactura-api.sfs.md/Service.svc`.

Cu respect,

Tuhari Pavel, administrator
Centrul de Elaborare și Implementare a Sistemelor Informaționale
de Management „UNISIM-SOFT" S.R.L.
IDNO 1003600116460 · or. Chișinău, str. Alba Iulia, 75/b
+373 22 59-43-44 · info@una.md

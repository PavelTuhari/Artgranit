# Cerere de acces la platforma API „e-Factura" — text gata de trimis

**Către:** asistenta@sfs.md
**De la:** info@una.md
**Subiect:** Cerere de acces la platforma API SIA „e-Factura" — „UNISIM-SOFT" S.R.L., IDNO 1003600116460

---

Stimați colegi,

Vă solicităm acordarea accesului la platforma API a SIA „e-Factura" pentru
integrarea sistemului nostru de evidență contabilă (ERP) prin API, conform
Ghidului de integrare semi-automatizată.

**Datele agentului economic**

| Cîmp | Valoare |
|---|---|
| Denumirea | Centrul de Elaborare și Implementare a Sistemelor Informaționale de Management „UNISIM-SOFT" S.R.L. |
| IDNO / Cod fiscal | 1003600116460 |
| Cod TVA | 0505230 |
| Nr. de înregistrare | 105100190 din 30.03.2001 |
| Adresa juridică | or. Chișinău, str. Alba Iulia, 75/b |
| Banca | Moldindconbank S.A., filiala Alba-Iulia |
| Codul băncii | MOLDMD2X303 |
| IBAN | MD22ML000000222442000432 |
| Telefon | +373 22 59-43-44, +373 22 59-44-49, +373 22 51-46-07 |
| Fax | +373 22 59-43-71 |
| E-mail | info@una.md |
| Administrator | Tuhari Pavel |

**Utilizatorii API solicitați** — cîte unul pentru fiecare semnatar, întrucît
SIA „e-Factura" ține cozi separate de semnare (`GetInvoicesForSigning`,
`Order` 1 și 2):

| Nr. | Nume, prenume | IDNP | Rolul în sistem |
|---|---|---|---|
| 1 | Tuhari Pavel | «IDNP» | director (administrator) |
| 2 | Tuhari Oxana | «IDNP» | «contabil-șef» |

**Adresele IP externe de pe care se vor face apelurile**

Apelurile către serviciu sînt inițiate de serverele aplicației noastre, nu de
stațiile de lucru ale utilizatorilor, de aceea vă rugăm să includeți în lista
de acces următoarele adrese:

| Adresa IP | Ce este |
|---|---|
| 93.115.136.18 | serverul de producție al aplicației (magazinul officeplus.md) |
| 92.5.3.187 | al doilea server al aceleiași aplicații |

**Vă rugăm să confirmați suplimentar:**

1. adresa exactă a serviciului pentru contul nostru — folosim
   `https://apiefactura-pre.sfs.md/Service.svc` pentru mediul de test și
   `https://efactura-api.sfs.md/Service.svc` pentru cel real;
2. dacă lista de acces se aplică separat pentru fiecare din cele două medii;
3. dacă pentru mediul real este necesară o cerere distinctă.

**Situația curentă**, ca punct de plecare pentru verificare: de pe ambele
adrese IP indicate mai sus, `apiefactura-pre.sfs.md` întoarce 403 „Accesul
este restricționat!", iar pe `efactura-api.sfs.md` un `GET` la `?wsdl`
întoarce 200, dar un `POST` întoarce pagina 500 „A apărut o eroare".

Cu respect,

Tuhari Pavel, administrator
Centrul de Elaborare și Implementare a Sistemelor Informaționale
de Management „UNISIM-SOFT" S.R.L.
IDNO 1003600116460 · or. Chișinău, str. Alba Iulia, 75/b
+373 22 59-43-44 · info@una.md

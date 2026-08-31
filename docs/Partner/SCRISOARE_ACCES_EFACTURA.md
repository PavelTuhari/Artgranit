# Cerere de acces la platforma API „e-Factura" — text gata de trimis

**Către:** asistenta@sfs.md
**Subiect:** Cerere de acces la platforma API SIA „e-Factura" (mediu de test și real) — IDNO «1003600116460»

---

Stimați colegi,

Vă solicităm acordarea accesului la platforma API a SIA „e-Factura" pentru
integrarea sistemului nostru de evidență contabilă (ERP) prin API, conform
Ghidului de integrare semi-automatizată.

**Datele agentului economic**

| Cîmp | Valoare |
|---|---|
| IDNO | «1003600116460» |
| Denumirea | «Unisim-Soft» SRL |
| Adresa | «str. Alba Iulia 75, mun. Chișinău» |
| Persoana de contact | «Pavel Tuhari» |
| E-mail | «ptuhari@gmail.com» |
| Telefon | «+373 ...» |

**Utilizatorii API solicitați** — cîte unul pentru fiecare semnatar, întrucît
SIA „e-Factura" ține cozi separate de semnare (`GetInvoicesForSigning`,
`Order` 1 și 2):

| Nr. | Nume, prenume | IDNP | Rolul în sistem |
|---|---|---|---|
| 1 | Pavel Tuhari | «2000...» | director |
| 2 | Oxana Tuhari | «2000...» | contabil-șef |

**Adresele IP externe de pe care se vor face apelurile**

Apelurile către serviciu sînt inițiate de serverele aplicației noastre, nu de
stațiile de lucru ale utilizatorilor, de aceea vă rugăm să includeți în lista
de acces următoarele adrese:

| Adresa IP | Ce este |
|---|---|
| 93.115.136.18 | serverul de producție al magazinului officeplus.md |
| 92.5.3.187 | serverul al doilea al aceleiași aplicații |

**Vă rugăm să confirmați suplimentar:**

1. adresa exactă a serviciului pentru contul nostru — folosim
   `https://apiefactura-pre.sfs.md/Service.svc` pentru mediul de test și
   `https://efactura-api.sfs.md/Service.svc` pentru cel real;
2. dacă lista de acces se aplică separat pentru fiecare din cele două medii;
3. dacă pentru mediul real este nevoie de o cerere distinctă.

**Situația curentă**, ca punct de plecare pentru verificare: de pe ambele
adrese de mai sus, `apiefactura-pre.sfs.md` întoarce 403 „Accesul este
restricționat!", iar pe `efactura-api.sfs.md` un `GET` la `?wsdl` întoarce
200, dar un `POST` întoarce pagina 500 „A apărut o eroare".

Cu respect,
«Pavel Tuhari», «administrator»
«Unisim-Soft» SRL, IDNO «1003600116460»
«+373 ...» · «ptuhari@gmail.com»

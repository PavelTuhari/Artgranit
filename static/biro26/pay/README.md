# Siglele sistemelor de plată · Логотипы платёжных систем

Cerință maib pentru e-commerce: siglele băncii și ale sistemelor internaționale
de plată trebuie afișate în subsolul site-ului
(https://docs.maibmerchants.md/main/ro/integration/requirements).

Puneți aici fișierele **oficiale**, primite de la bancă / de la sistemele de plată:

| Fișier | Pentru |
|---|---|
| `maib.svg` | maib (obligatoriu) |
| `visa.svg` | VISA |
| `mastercard.svg` | Mastercard |
| `maestro.svg` | Maestro |
| `amex.svg` | American Express |
| `mia.svg` | MIA |
| `applepay.svg` | Apple Pay |
| `easycredit.svg` | EasyCredit |
| `libercard.svg` | Liber Card |

Numele fișierului = denumirea din pagina WP «site-plati», litere mici, fără
spații și diacritice (vezi `paySlug()` în `static/biro26/site.js`).
Se acceptă și `.png` — atunci schimbați extensia în `payBadgeHtml()`.

## Două căi de administrare

1. **Din WordPress (recomandat):** încărcați siglele în galeria media și inserați-le
   ca imagini în pagina «Tipuri de plata (site)». Subsolul le preia automat —
   fără deploy, fără modificări de cod. Imaginile din pagină au PRIORITATE față
   de fișierele din acest folder.
2. **Din acest folder:** dacă pagina WP conține doar denumiri (text), subsolul
   caută `/static/biro26/pay/<slug>.svg`.

**Dacă lipsesc ambele**, în subsol rămâne badge-ul text cu denumirea — pagina
nu se strică. De aceea siglele pot fi adăugate oricând, fără modificări de cod.

⚠️ Nu desenați sigle „aproximative": mărcile sunt protejate, folosiți doar
fișierele oficiale furnizate de bancă și de sistemele de plată.

⚠️ `visa.svg` și `mastercard.svg` din acest folder sunt copii de lucru, puse aici
ca să existe ceva în subsol imediat. Pentru conformitate, înlocuiți-le cu
fișierele OFICIALE din pachetul de logo-uri primit de la maib (sau din brand
center-ul Visa / Mastercard).

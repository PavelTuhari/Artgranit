# Cartea V — Când ceva nu merge

> Găsiți cauza singur, în două minute, înainte să sunați programatorul.

---

## 1. Tabelul: simptom → cauză → ce faceți

| Ce vedeți | Cauza cea mai probabilă | Ce faceți |
|---|---|---|
| **Postarea nu a plecat în Facebook** | tokenul de pagină a expirat (se întâmplă la ~60 de zile) | se generează un token nou după [instrucțiune](SOCIAL_AUTOMATION.md); apăsați «Опубликовать сейчас» ca să verificați |
| **Instagram dă eroare „cere imagine”** | Instagram nu publică text simplu | normal, nu e defecțiune: postările fără fotografie nu merg acolo |
| **Ecranul ROI e gol** | nu s-au introdus cheltuielile reale | «Факты» → «Добавить расход», vedeți [Cartea II](GHID_2_EXECUTANT.md) |
| **Cifrele lunii sunt de două ori mai mari** | același CSV a fost încărcat de două ori | verificați jurnalul importurilor; folosiți întotdeauna «Предпросмотр» înainte de «Загрузить» |
| **Articolele arată prețuri vechi** | nu s-au regenerat după schimbarea prețurilor | rulați regenerarea, [Cartea III, punctul 8](GHID_3_CONTINUT.md) |
| **Articolul nu s-a actualizat, deși am regenerat** | cineva l-a editat de mână în WordPress | e intenționat: sistemul nu suprascrie munca omului. Ștergeți editarea manuală dacă vreți actualizare automată |
| **Un articol nu are fotografii** | grupa nu are poze în ERP | se rezolvă încărcând pozele în bază, nu din program |
| **Raportul pâlniei nu ajunge pe e-mail** | SMTP nu este configurat; serviciul de poștă lucrează doar 22:00–02:00 | folosiți Telegram sau WhatsApp; e-mailul e o cerere separată |
| **Site-ul s-a încetinit brusc** | cel mai des: serverul a repornit și memoria e rece | prima pagină după repornire e lentă, restul revin. Dacă ține mai mult de 10 minute — anunțați |
| **Nu văd un ecran din meniu** | nu sunteți autentificat sau nu aveți drept | intrați în back-office; dacă tot nu apare — cerere către administrator |

---

## 2. Două lucruri care par defecte, dar sunt intenționate

### „Articolele nu apar în Google”

Articolele stau pe **officeplus.una.md**, un domeniu **închis intenționat
pentru motoarele de căutare**. Este dublura tehnică a magazinului; dacă ar
fi indexată, Google ar vedea două magazine identice și ar împărți puterea
între ele — exact problema reparată la început.

**Oamenii le văd normal** — ascunderea este doar față de roboți.

Când conținutul se mută pe domeniul public, el începe să lucreze și pentru
căutare. Aceasta este o decizie, nu un defect.

### „Prețul din marcaj arată «la comandă», deși avem stoc”

Magazinul vinde și la comandă. Marcajul spune „se poate comanda”
(*BackOrder*) în loc de „indisponibil” (*OutOfStock*), pentru că butonul de
cumpărare este acolo și funcționează. A spune „indisponibil” când omul
poate cumpăra este o greșeală mai scumpă.

---

## 3. Capcana diacriticelor — citiți înainte să scrieți în ecranul «Стратегия»

Baza de date a back-office-ului folosește codificarea **CP1251**, în care
literele **ș, ț, ă, î, â nu există**.

Ce se întâmplă dacă le scrieți totuși: Oracle le înlocuiește cu `?`
**în tăcere** — lungimea rămâne aceeași, conținutul devine altul. Nimeni
nu primește eroare, iar textul se strică.

De aceea sistemul **verifică textul înainte de scriere** și refuză
salvarea, arătând exact ce caractere și pe ce rânduri sunt problematice.

**Ce faceți practic:** în documentele de strategie din back-office scrieți
româna **fără diacritice** (`Rechizite scolare`, nu `Rechizite școlare`).
Exact așa sunt scrise și denumirile în ERP.

> Această limitare privește **doar** textele scrise în baza back-office-ului.
> Articolele publicate pe site și cartea pe care o citiți acum sunt fișiere
> obișnuite și au diacritice complete.

---

## 4. Ce nu poate sistemul

Onest, ca să nu așteptați degeaba:

| Nu poate | De ce | Alternativa |
|---|---|---|
| Să garanteze locul 1 în Google | nimeni nu poate; cine promite, minte | muncă constantă, rezultat în luni |
| Să scrie articole „creative” despre orice | scrie din date, nu inventează | textele redacționale se scriu de om, o dată |
| Să publice în Instagram fără fotografie | restricția Instagram | adăugați poze în ERP |
| Să trimită e-mail acum | SMTP neconfigurat, poștă doar 22:00–02:00 | Telegram, WhatsApp |
| Să răspundă la comentarii în rețele | nu e construit pentru asta | om, zilnic, 10 minute |
| Să aducă vizitatori mâine | căutarea nu funcționează așa | reclamă plătită, dacă e nevoie urgentă |

---

## 5. Ce este blocat acum și cine deblochează

| Ce | Cine deblochează | Cât durează |
|---|---|---|
| Facebook, Instagram, VK, OK | administratorul paginii firmei — obține cheile | 30 min, o dată |
| Fotografii pentru 59 de grupe | departamentul care încarcă marfa în ERP | continuu |
| Google Search Console | cine are acces la DNS-ul `officeplus.md` | 15 min, o dată |
| E-mail pentru rapoarte | administratorul de sistem (configurare SMTP) | cerere separată |
| Mutarea articolelor pe domeniul public | decizie de conducere + administrator | o zi |

---

## 6. Reguli pentru cine atinge codul

Nu vă privesc dacă nu sunteți programator, dar sunt aici pentru că
nerespectarea lor a costat deja o funcție pierdută în producție.

1. **Logica importantă nu se scrie în fișiere comune** (`app.py`,
   șabloane comune). Fiecare logică — fișierul ei; în fișierul comun doar
   apelul de un rând.
2. **Fiecare modificare se documentează** într-un fișier md lângă cod.
3. **Înainte de desfășurare** se compară versiunea de pe server cu cea
   proprie: dacă serverul e mai nou, întâi se îmbină, apoi se desfășoară.
4. **Accesul la ERP** trece prin bazinul de procese de lungă durată.
   O citire durează ~0,16 s; dacă durează secunde, codul a ocolit bazinul.

Regulile complete: `CLAUDE.md` din proiect și
[Modelul de date](DATA_MODEL.md).

---

## 7. Pe cine chemați

| Problema | Cine |
|---|---|
| Comenzi blocate, clienți nemulțumiți | vânzări |
| Prețuri sau stocuri greșite | cine gestionează ERP |
| Fotografii lipsă | cine încarcă marfa |
| Chei pentru rețele | administratorul paginii firmei |
| Site căzut, ecran cu eroare | administratorul de sistem |
| „Nu înțeleg ce arată cifra asta” | [Cartea IV](GHID_4_MASURARE.md) |

---

**Înapoi la:** [Harta cărții](GHID_0_HARTA.md) · [Cartea I — Pentru director](GHID_1_DIRECTOR.md)

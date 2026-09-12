# Cartea V — Când ceva nu merge

> Găsiți cauza singur, în două minute, înainte să sunați programatorul.

---

## 1. Tabelul: simptom → cauză → ce faceți

### 1.1. Publicare și rețele

| Ce vedeți | Cauza probabilă | Ce faceți |
|---|---|---|
| **Postarea nu a plecat în Facebook** | tokenul de pagină a expirat (la ~60 de zile) | generați token nou după [instrucțiune](SOCIAL_AUTOMATION.md); verificați cu «Опубликовать сейчас» |
| **Instagram: „cere imagine”** | Instagram nu publică text simplu | normal, nu e defecțiune: fără fotografie nu merge |
| **Acoperirea postărilor a scăzut brusc** | s-a postat mai des decât o dată pe zi | reveniți la o postare pe zi; acoperirea revine în 1–2 săptămâni |
| **O rețea a căzut pe gri** | cheia a expirat sau a fost revocată | reintroduceți cheia |

### 1.2. Conținut și articole

| Ce vedeți | Cauza probabilă | Ce faceți |
|---|---|---|
| **Articolele arată prețuri vechi** | nu s-au regenerat după schimbarea prețurilor | rulați regenerarea, [Cartea III, punctul 11](GHID_3_CONTINUT.md) |
| **Am regenerat, articolul nu s-a schimbat** | cineva l-a editat de mână în WordPress | intenționat: sistemul nu suprascrie munca omului |
| **Un articol nu are fotografii** | grupa nu are poze în ERP | se încarcă pozele în bază, nu în program |
| **Denumirile rusești lipsesc** | nu sunt în dicționarul de traduceri | rămâne denumirea românească — corect, nu eroare |

### 1.3. Cifre și rapoarte

| Ce vedeți | Cauza probabilă | Ce faceți |
|---|---|---|
| **Ecranul ROI e gol** | nu s-au introdus cheltuielile reale | «Факты» → «Добавить расход» |
| **Cifrele lunii sunt duble** | același CSV încărcat de două ori | verificați jurnalul importurilor; folosiți «Предпросмотр» |
| **Raportul nu ajunge pe e-mail** | SMTP neconfigurat; poșta lucrează 22:00–02:00 | folosiți Telegram sau WhatsApp |
| **Traficul crește, comenzile nu** | public greșit sau pagina nu răspunde la ce caută | vedeți conversia, [Cartea IV, 4.4](GHID_4_MASURARE.md) |

### 1.4. Site și acces

| Ce vedeți | Cauza probabilă | Ce faceți |
|---|---|---|
| **Site-ul s-a încetinit brusc** | serverul a repornit, memoria e rece | prima pagină e lentă, restul revin; peste 10 minute — anunțați |
| **Nu văd un ecran din meniu** | nu sunteți autentificat sau nu aveți drept | intrați; dacă tot nu apare — cerere către administrator |

---

## 2. Ce pare defect, dar este intenționat

### 2.1. „Articolele nu apar în Google”

Articolele stau pe **officeplus.una.md**, domeniu **închis intenționat**
pentru motoarele de căutare. Este dublura tehnică a magazinului; dacă ar fi
indexată, Google ar vedea două magazine identice și ar împărți puterea între
ele — exact problema reparată la început.

**Oamenii le văd normal** — ascunderea este doar față de roboți.

Când conținutul se mută pe domeniul public, începe să lucreze și pentru
căutare. Aceasta este o decizie, nu un defect.

### 2.2. „Scrie «la comandă», deși avem stoc”

Magazinul vinde și la comandă. Marcajul spune „se poate comanda”
(*BackOrder*) în loc de „indisponibil” (*OutOfStock*), pentru că butonul de
cumpărare este acolo și funcționează. A spune „indisponibil” când omul poate
cumpăra este o greșeală mai scumpă.

### 2.3. „Sistemul nu mi-a actualizat articolul editat”

Corect. Un articol atins de om este considerat mai bun decât unul generat și
nu se suprascrie niciodată.

---

## 3. Capcana diacriticelor

**Citiți înainte să scrieți în ecranul «Стратегия».**

### 3.1. Ce se întâmplă

Baza de date a back-office-ului folosește codificarea **CP1251**, în care
literele **ș, ț, ă, î, â nu există**. Oracle le înlocuiește cu `?`
**în tăcere** — lungimea rămâne aceeași, conținutul devine altul. Nimeni nu
primește eroare, iar textul se strică.

### 3.2. Cum vă apără sistemul

Textul se verifică **înainte** de scriere, iar salvarea este refuzată, cu
lista exactă a caracterelor și a rândurilor problematice.

### 3.3. Ce faceți practic

În documentele de strategie din back-office scrieți româna **fără
diacritice** (`Rechizite scolare`, nu `Rechizite școlare`). Exact așa sunt
scrise și denumirile în ERP.

> Limitarea privește **doar** textele scrise în baza back-office-ului.
> Articolele publicate pe site, postările și cartea pe care o citiți acum
> sunt fișiere obișnuite și au diacritice complete.

---

## 4. Ce nu poate sistemul

Onest, ca să nu așteptați degeaba:

| Nu poate | De ce | Alternativa |
|---|---|---|
| Să garanteze locul 1 în Google | nimeni nu poate; cine promite, minte | muncă constantă, rezultat în luni |
| Să scrie articole „creative” despre orice | scrie din date, nu inventează | ghidurile și comparațiile se scriu de om |
| Să publice în Instagram fără fotografie | restricția Instagram | adăugați poze în ERP |
| Să trimită e-mail acum | SMTP neconfigurat, poștă doar 22:00–02:00 | Telegram, WhatsApp |
| Să sune organizațiile | nu există automat pentru asta | un om, zece contacte pe săptămână |
| Să răspundă la comentarii și recenzii | nu e construit pentru asta | om, zilnic, 10 minute |
| Să aducă vizitatori mâine | căutarea nu funcționează așa | reclamă plătită, dacă e urgent |

---

## 5. Ce este blocat acum și cine deblochează

| Ce | Cine deblochează | Cât durează |
|---|---|---|
| Facebook, Instagram, VK, OK | administratorul paginii firmei | 30 min, o dată |
| Fotografii pentru 59 de grupe | departamentul care încarcă marfa | continuu |
| Google Search Console | cine are acces la DNS-ul `officeplus.md` | 15 min, o dată |
| Profilul local pe hartă | conducerea (confirmare adresă, program) | 1 zi + verificare |
| Feed de produse către Google | decizie de conducere + pregătire | 2–4 săptămâni |
| E-mail pentru rapoarte | administratorul de sistem (SMTP) | cerere separată |
| Mutarea articolelor pe domeniul public | decizie + administrator | o zi |

---

## 6. Reguli pentru cine atinge codul

Nu vă privesc dacă nu sunteți programator, dar sunt aici pentru că
nerespectarea lor a costat deja o funcție pierdută în producție.

1. **Logica importantă nu se scrie în fișiere comune** (`app.py`, șabloane
   comune). Fiecare logică — fișierul ei; în fișierul comun doar apelul de un
   rând.
2. **Fiecare modificare se documentează** într-un fișier md lângă cod.
3. **Înainte de desfășurare** se compară versiunea de pe server cu cea
   proprie: dacă serverul e mai nou, întâi se îmbină.
4. **Accesul la ERP** trece prin bazinul de procese de lungă durată. O citire
   durează ~0,16 s; dacă durează secunde, codul a ocolit bazinul.

Regulile complete: `CLAUDE.md`, `AGENTS.md` și [Modelul de date](DATA_MODEL.md).

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

**Înapoi la:** [Harta cărții](GHID_0_HARTA.md) ·
[Cartea I — Pentru director](GHID_1_DIRECTOR.md)

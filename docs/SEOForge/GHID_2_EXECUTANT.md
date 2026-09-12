# Cartea II — Manualul executantului

> Ce faceți, în ce ordine, pe ce apăsați. Citiți-o cu programul deschis și
> faceți fiecare pas pe rând.

**Atenție utilă:** interfața back-office-ului este **în limba rusă**. În
tabelele de mai jos găsiți, între ghilimele, exact textul care scrie pe
ecran, ca să nu-l căutați.

---

## 1. Înainte de a începe

### 1.1. Ce vă trebuie

| | |
|---|---|
| **Acces** | cont în back-office (`/UNA.md/orasldev`) |
| **Timp** | 5 minute pe zi, 30–60 pe săptămână, 2 ore pe lună |
| **Cunoștințe** | niciuna tehnică — nu scrieți cod, nu atingeți serverul |

### 1.2. Harta ecranelor

| Ecran | Adresa | Ce face |
|---|---|---|
| Pâlnia | `/UNA.md/orasldev/funnel` | comenzi pe zile, ce se vinde, ce s-a blocat |
| Rețele | `/UNA.md/orasldev/social` | postarea zilei, rețelele conectate |
| SEOForge | `/UNA.md/orasldev/seoforge` | buget, cheltuieli, ROI, strategie |

### 1.3. Secțiunile din SEOForge

În ordinea din meniul din stânga:

| Ce scrie pe ecran | Înseamnă | Când intrați |
|---|---|---|
| «Портфель» | Portofoliu — toate site-urile, plan și rest de buget | privire de ansamblu |
| «Сайты» | Site-uri — domeniu, limbi, nișă | rar, la configurare |
| «Кампании» | Campanii — cod (= `utm_campaign`), termene, buget | la pornirea unei campanii |
| «Бюджет» | Buget — plan pe perioade, articole, canale | lunar |
| «Факты» | Fapte — cheltuieli reale și metrici | lunar, obligatoriu |
| «ROI» | ROI — cât a costat și cât a adus fiecare canal | lunar |
| «Стратегия» | Strategie — documentele de lucru, cu versiuni | la revizuiri |
| «Справочники» | Dicționare — canale, articole, cursuri valutare | la configurare |

---

## 2. Rutina zilnică — 5 minute

### 2.1. Pâlnia

**Pasul 1.** Deschideți `/UNA.md/orasldev/funnel`

**Pasul 2.** Priviți „Воронка за 7 дней” (*Pâlnia pe 7 zile*) — comenzile pe
zile. O singură întrebare: **ziua de ieri arată ca zilele dinainte?** O
cădere bruscă înseamnă fie sărbătoare, fie ceva stricat pe site.

**Pasul 3.** Coborâți la comenzile blocate — intrate, dar nelivrate de mult.
Fiecare rând este un client care așteaptă și un ban care nu a intrat. Dacă
apare ceva, sunați vânzările; nu rezolvați dumneavoastră.

### 2.2. Postarea zilei

Deschideți `/UNA.md/orasldev/social` și citiți „Что уйдёт сегодня”
(*Ce pleacă azi*). Dacă textul arată ciudat, opriți publicarea pentru azi
(debifați „публиковать ежедневно”) și anunțați.

> **Zilnic doar priviți.** Nu regenerați articole, nu schimbați bugete, nu
> postați manual „ca să fie mai mult”.

---

## 3. Rutina săptămânală — 30–60 de minute

### 3.1. Ce s-a vândut

În pâlnie: „Топ групп за 30 дней” (*Top grupe*) și „Топ товаров за 30 дней”
(*Top produse*). Notați **primele trei grupe** — acolo merită conținut și,
mai târziu, buget. Nu ghiciți ce se vinde; se vede aici.

### 3.2. Comenzile blocate

Aceeași listă ca zilnic, dar acum o **închideți**: fiecare rând cu un
răspuns de la vânzări.

### 3.3. Rețelele

Pe `/UNA.md/orasldev/social`, blocul „Площадки” (*Platforme*): rețelele
pornite trebuie să aibă „настроено” (*configurat*). Una căzută pe gri
înseamnă cheie expirată — cel mai des Facebook,
vezi [Cartea V](GHID_5_PROBLEME.md).

### 3.4. Zece contacte cu organizații

Partea care aduce cei mai mulți bani și singura care nu se face singură
(pârghia 6.1 din [Cartea I](GHID_1_DIRECTOR.md)).

1. Alegeți **zece** instituții sau firme din nord pe care nu le-am contactat.
2. Trimiteți oferta de o pagină (șablonul la punctul 7).
3. Notați într-un tabel simplu: cine, când, ce a răspuns.
4. Săptămâna următoare — reveniți la cei care n-au răspuns. **O singură
   dată.**

Zece pe săptămână înseamnă peste 400 pe an. Nu e nevoie de mai mult.

### 3.5. O privire în Google Analytics

Crește numărul de vizitatori din căutare față de săptămâna trecută? Nu
trageți concluzii dintr-o singură săptămână — urmăriți tendința.

---

## 4. Rutina lunară — 2 ore

Se face în primele zile ale lunii, pentru luna încheiată.

### 4.1. Introduceți cheltuielile reale (30 min)

Fără acest pas ecranul ROI arată gol și nimeni nu știe dacă banii au făcut
ceva.

1. `/UNA.md/orasldev/seoforge` → «Факты»
2. Pentru fiecare cheltuială: **«Добавить расход»** (*Adaugă cheltuială*) —
   data, canalul, campania, suma, moneda.
3. Dacă aveți export CSV din cabinetul de reclamă: **«Предпросмотр»**
   (*Previzualizare*) arată ce se va încărca, apoi **«Загрузить»**
   (*Încarcă*). **Priviți întotdeauna previzualizarea** — un import dublat
   strică toate cifrele lunii. Formatul:
   [Formatul importului CSV](CSV_FORMAT.md).

### 4.2. Citiți ROI (20 min)

«ROI» → perioada → **«Показать»** (*Arată*). Cum se citesc cifrele și când
opriți un canal — [Cartea IV](GHID_4_MASURARE.md).

### 4.3. Planificați luna următoare (15 min)

«Бюджет» → completați planul pe perioadă, articol și canal →
**«Записать план»** (*Înscrie planul*). Fără plan, ecranul nu are cu ce
compara cheltuiala și nu vedeți depășirile.

### 4.4. Campania de comandă repetată (30 min)

Vedeți punctul 8 — este pasul cu cel mai bun raport efort/rezultat din toată
luna.

### 4.5. Regenerați articolele (25 min)

Catalogul se schimbă; articolele trebuie să spună adevărul de azi.

```bash
# 1. Se generează textele din baza ERP
python modules/seoforge/scripts/wp_category_posts.py

# 2. Se încarcă în WordPress (actualizează, nu dublează)
sudo -u www-data wp --path=/var/www/officeplus \
  eval-file /tmp/wp_create_posts.php
```

Răspunsul corect: `создано 0, обновлено 526, сохранено ручных 0, ошибок 0`
— *create 0, actualizate 526, păstrate manual 0, erori 0*.

**„Păstrate manual”** înseamnă articole editate de om în WordPress:
sistemul **nu le atinge**. Un număr acolo nu este eroare.

Detalii: [Articole de catalog în WordPress](WP_CATEGORY_POSTS.md).

---

## 5. Pas cu pas: pornirea autopostării

Se face **o singură dată**, apoi merge singură.

1. Deschideți `/UNA.md/orasldev/social`
2. În „Площадки” vedeți ce rețele sunt gata. **Telegram este deja
   configurat.** Restul apar gri până se introduc cheile —
   [instrucțiunea](SOCIAL_AUTOMATION.md).
3. Ora: câmpul «в … :00». Recomandat **10:00**.
4. Limba: «язык» → RO sau RU.
5. **Înainte de a porni automatul**, apăsați **«Опубликовать сейчас»**
   (*Publică acum*) și priviți rezultatul: fiecare rețea răspunde separat,
   ✅ sau ❌ cu motivul.
6. A mers? Bifați «публиковать ежедневно» și **«Сохранить»**.

Lunea pleacă selecția „se cumpără acum” din comenzi reale; în restul zilelor
— câte o secțiune, prin rotație.

---

## 6. Pas cu pas: raportul automat către conducere

1. `/UNA.md/orasldev/funnel` → „Автономная сводка” (*Raportul autonom*)
2. Completați destinatarii și ora. **Ora implicită 22:00** nu e întâmplătoare:
   serviciul de poștă al serverului lucrează doar între 22:00 și 02:00.
3. **«Отправить сейчас»** (*Trimite acum*) — verificați că ajunge.
4. **«Сохранить»**.

> Poșta electronică (SMTP) **nu este configurată**. Telegram și WhatsApp
> funcționează. E-mailul este o cerere separată către administrator.

---

## 7. Pas cu pas: oferta pentru o organizație

Se folosește la punctul 3.4. Oferta stă **într-o singură pagină**.

### 7.1. Ce conține

1. **Cine suntem, într-o frază** — furnizor cu 172 594 de poziții, livrare
   în tot nordul.
2. **Ce rezolvăm pentru ei** — o comandă în loc de cinci furnizori; factură
   fiscală; livrare la adresă.
3. **Trei-patru poziții cu prețuri reale** din ce cumpără ei de obicei
   (hârtie A4, tonere, caiete, cretă). Prețurile se iau din catalog în ziua
   trimiterii.
4. **Cum se comandă** — telefon, e-mail, condiții pentru comenzi repetate.
5. **Un singur apel la acțiune:** „trimiteți lista, vă facem oferta în 24 de
   ore”.

### 7.2. Ce nu conține

Cataloage întregi, prezentări de zece pagini, adjective. Omul care conduce o
școală citește 40 de secunde.

### 7.3. După trimitere

Notați data. Dacă nu răspunde în **cinci zile lucrătoare** — un singur
telefon scurt. Dacă nici atunci, treceți mai departe: reveniți peste o lună,
nu peste o săptămână.

---

## 8. Pas cu pas: campania de comandă repetată

Cea mai ieftină vânzare din lună (pârghia 6.2).

### 8.1. Cui scrieți

Clienții care au cumpărat **consumabile** acum 60–90 de zile: hârtie,
tonere, markere, caiete, cretă. Lista se ia din istoricul comenzilor;
pâlnia arată ce s-a vândut și cui.

### 8.2. Ce scrieți

Un mesaj scurt, la obiect:

> Bună ziua. În martie ați comandat hârtie A4 (5 topuri). Dacă vi se apropie
> de final, o avem pe stoc la 129 lei topul — livrăm în Bălți în aceeași
> săptămână. Vreți să pregătim comanda?

**Trei elemente obligatorii:** ce a cumpărat, că avem pe stoc acum, cât
costă azi. Fără „ofertă specială” și fără presiune.

### 8.3. Regulile

| Regula | De ce |
|---|---|
| **Un memento pe ciclu** | al doilea este spam, al treilea e dezabonare |
| Se trimite pe canalul pe care a comunicat el | nu-l mutați pe alt canal |
| Nu se trimite celor cu comandă blocată | întâi rezolvați problema veche |
| Se notează rezultatul | altfel luna viitoare scrieți la fel acelorași oameni |

### 8.4. Ce măsurați

Câte mesaje au plecat, câte comenzi au venit în 14 zile. Dacă din 50 de
mesaje vin 5 comenzi, campania este un succes — comparați cu ce v-ar fi
costat 5 comenzi din reclamă plătită.

---

## 9. Pas cu pas: cererea de recenzii

### 9.1. Când

**După livrare**, nu după plată. Omul tocmai a primit marfa.

### 9.2. Cum

Un mesaj de două rânduri, cu legătura directă către profil:

> Mulțumim pentru comandă. Dacă totul a fost în regulă, ne ajutați mult cu
> un cuvânt aici: [legătura]. Dacă ceva nu a fost — scrieți-ne nouă întâi,
> reparăm.

A doua frază este importantă: clientul nemulțumit vă scrie dumneavoastră,
nu publicului.

### 9.3. Ce nu se face

Recenzii scrise de noi sau de angajați. Se văd, se sancționează și distrug
exact lucrul pe care trebuiau să-l construiască.

### 9.4. Ce faceți cu o recenzie proastă

Răspundeți **public**, calm, cu soluția concretă: ce s-a întâmplat, ce
faceți. O recenzie proastă cu un răspuns bun convinge mai mult decât zece
recenzii perfecte.

---

## 10. Ce nu faceți niciodată

| Nu faceți | De ce |
|---|---|
| Nu postați de mai multe ori pe zi în aceeași rețea | rețelele scad acoperirea celor care postează des |
| Nu scrieți reduceri sau promoții care nu există în bază | o vizită câștigată, un client pierdut, risc de penalizare |
| Nu trimiteți al doilea memento aceluiași om | mementoul devine spam |
| Nu editați articolele în WordPress fără motiv | e permis, dar acel articol nu se mai actualizează automat |
| Nu încărcați de două ori același CSV | dublează cheltuielile și strică ROI-ul |
| Nu trageți concluzii din două săptămâni | vedeți calendarul din [Cartea I](GHID_1_DIRECTOR.md) |
| Nu opriți o campanie fără să priviți ROI | poate tocmai ea aducea comenzile |
| Nu scrieți singur recenzii | vezi 9.3 |

---

## 11. Calendarul dumneavoastră, pe scurt

| Când | Ce | Unde | Cât |
|---|---|---|---|
| În fiecare dimineață | pâlnia + textul zilei | funnel, social | 5 min |
| Luni | top grupe, comenzi blocate, rețele | funnel, social | 20 min |
| Marți | **zece contacte cu organizații** | telefon, e-mail | 40 min |
| Prima zi lucrătoare a lunii | cheltuieli, ROI, plan | seoforge | 1 h |
| Prima săptămână a lunii | comandă repetată, regenerare articole | listă, comenzi | 1 h |
| După fiecare livrare | cererea de recenzie | mesaj scurt | 2 min |
| Cu 4 săptămâni înainte de sezon | conținut și seturi | [Cartea III](GHID_3_CONTINUT.md) | 1 zi |

---

**Următorul capitol:** [Cartea III — Conținutul](GHID_3_CONTINUT.md)

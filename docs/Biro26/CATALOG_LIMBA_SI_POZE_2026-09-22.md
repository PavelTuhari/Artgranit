# Catalog: categoriile în rusă la limba RO și pozele lipsă (22.09.2026)

Două reclamații din capturile proprietarului, pe pagina
`https://officeplus.md/catalog?grupa=ACCESORII+IT&categorie=UTP+Кабель+-+ELAN`:

1. «de ce denumirea la categorie și la unele produse sunt în rusă, dacă este
   aleasă limba română a sitului»;
2. «de ce nu sunt poze la produsele de la ANDIX?».

## 1. Categoriile în rusă — rezolvat

**Cauza.** Vitrina ia denumirea categoriei din `BIRO26_GOODS.CATEGORIE`. Acela e
numele de BAZĂ: el se afișează la limba română, el intră în URL și tot el e cheia
după care dicționarul `YBIRO_GRP_I18N` dă traducerile RU/EN. La **540 de
categorii** (4402 produse) numele de bază era scris **în rusă**, iar în dicționar
nu exista niciun rînd pentru ele — deci nu avea de unde să apară româna, oricare
ar fi fost limba aleasă.

**Ce s-a făcut.** Numele românesc a devenit numele de bază, iar rusescul a fost
păstrat în dicționar ca `NAME_RU` — la RU vitrina arată exact ca înainte.

| Ce | Unde | Cît |
|---|---|---|
| Glosar RU→RO + reguli (ordinea cuvintelor, omoglife, cozi numerice) | `models/biro26_cat_ro.py` | 496 intrări |
| Migrarea (rulabilă și în gol, cu jurnal) | `scripts/biro26_cat_ro_migrate.py` | — |
| Denumiri de categorii traduse | `BIRO26_GOODS.CATEGORIE` | 540 categorii, 4957 rînduri |
| Rusescul păstrat ca traducere | `YBIRO_GRP_I18N` (KIND `categorie`) | 540 rînduri noi (1492 în total cu RU) |
| Jurnal vechi → nou (reversibil) | `YBIRO_CAT_RENAME` | 542 rînduri |

Exemple: `UTP Кабель - ELAN` → **Cablu UTP - ELAN**;
`UTP кабель внутреннего исполнения` → **Cablu UTP de interior**;
`Dome камеры` → **Camere Dome**; `Дюбеля трехстороннего распора` → **Dibluri cu
expansiune pe trei părți**; `16-ти канальные HD-TVI DVR` → **16 canale HD-TVI DVR**.

Trei lucruri pe care le face glosarul dincolo de traducerea propriu-zisă:

- **ordinea cuvintelor** — în română determinantul stă după substantiv, deci
  «UTP Cablu» devine «Cablu UTP», «Dome camere» devine «Camere Dome»;
- **omoglifele** — denumiri altfel latine cu o literă chirilică rătăcită
  (`Ciocanе`, `Motoсultoare`, `Tigai si Сratite`) au fost curățate;
- **TRANSLATE nu se folosește în SQL**: un literal cu diacritice ajunge în baza
  CL8MSWIN1251 ca `aai?s?t` și strică textul («Agrafe» → « grafe»).

**Verificat viu:** pe `https://officeplus.md/catalog?grupa=ACCESORII+IT` la RO nu
mai există niciun cuvînt rusesc în pagină, iar la RU categoriile revin în rusă
(`Кабель`, `Пожарный кабель - ELAN`), deci dicționarul lucrează în ambele sensuri.

**De știut:** adresele vechi cu categoria în rusă (`?categorie=UTP+Кабель`) nu mai
răspund cu produse — cheia s-a schimbat odată cu denumirea. Legăturile din meniu,
din sitemap și din căutare se regenerează singure.

## 2. Pozele — parțial rezolvat, restul ține de furnizor

Aici sînt **două probleme diferite**, nu una.

### a) Poze rupte — reparat (1600 produse)

1600 de produse din catalog aveau în `TMS_MPT_TVR.IE_LINKADRES` o adresă care se
oprește la **folder**, fără nume de fișier: `https://papirus.md/upload/products/detail/`.
Browserul cerea acea adresă, primea o pagină în loc de imagine și afișa o iconiță
de imagine ruptă — mai rău decît lipsa pozei, pentru că interfața credea că poza
există și nu mai punea placeholder-ul propriu.

Reparat în `models/biro26_imgproxy.py`: o adresă fără nume de fișier e tratată ca
«fără poză», exact ca stub-urile `noimage.jpg` de pe site-urile sursă. Verificat
pe produsul 162325 — pagina nu mai face nicio cerere de imagine căzută.

### b) Poze care nu există nicăieri — 5518 produse

Pentru produsele din captură (cablurile ELAN, furnizor **Price BS** în sistem —
«ANDIX» nu apare nicăieri în bază) nu există poză **în nicio sursă**: nici pe
cartelă (`IE_LINKADRES`), nici în feed-ul furnizorului (`PHOTO_URL` / `IMAGE_LINK`).

Verificări făcute înainte de a trage concluzia:

| Verificare | Rezultat |
|---|---|
| Produse cu poză în feed dar fără poză pe cartelă (sincronizare ruptă) | **0** — nu e nimic de copiat |
| Produse fără poză care au un «geamăn» cu aceeași denumire și cu poză | doar **13** în catalog (cablurile ELAN nu au geamăn) |
| Rînduri de feed pentru Price BS / SlaideR | fără `SHEET`, cu **0** poze |

Lista completă, pe furnizori, ca să poată fi cerută de la ei:
[`BIRO26_PRODUSE_FARA_POZA_2026-09-22.xlsx`](BIRO26_PRODUSE_FARA_POZA_2026-09-22.xlsx)
— 5518 produse, 85 de furnizori. Primii: SlaideR 1800, Price BS 1407,
fără furnizor 745, Birolux-MT 674, Impreso 198, Biblion 179.

Cînd furnizorul dă pozele (fișier cu articol + adresă, sau un feed cu coloană de
imagine), importul lor există deja: `Biro26Store.import_feed_images` scrie în
`TMS_MPT_TVR.IE_LINKADRES` printr-un MERGE după COD.

## Verificare după desfășurare

- `models/biro26_cat_ro.py`, `models/biro26_imgproxy.py`, `scripts/biro26_cat_ro_migrate.py`
  duse pe toate trei contururile: office 192.168.0.250 (vitrina publică, prin
  failover-ul din nginx), 92.5.130.1 (rezerva), nufarul 92.5.3.187. Pe fiecare
  `login` 200 și 0 Traceback; fișierele înlocuite aveau md5-ul din git (nimic
  străin suprascris), cu `.bak-2026-09-22` alături.
- `tests/test_biro26.py`: două teste noi trec. Cele 7 teste care cad pe această
  ramură cădeau **și înainte** de modificări (listă identică) — nu le-am atins.

## Adrese live

- Catalog RO: <https://officeplus.md/catalog?grupa=ACCESORII+IT>
- Categoria din captură: <https://officeplus.md/catalog?grupa=ACCESORII+IT&categorie=Cablu+UTP+-+ELAN>
- Un produs fără poză (acum cu placeholder curat): <https://officeplus.md/produs/162325>

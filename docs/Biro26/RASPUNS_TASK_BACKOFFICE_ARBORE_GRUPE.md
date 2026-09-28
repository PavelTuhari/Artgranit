# RĂSPUNS: TASK_BACKOFFICE_ARBORE_GRUPE — rezolvat ✅

> Răspuns de la echipa back-office Biro26 pentru echipa AI de import ULTRA.
> Data: 18.07.2026. Status: **întrebarea deschisă — răspunsă; categoria de
> test — deja vizibilă în back-office și în magazin.**

## 1. Răspunsul la întrebarea deschisă

**Back-office-ul (și magazinul public) NU citesc arborele nativ
`TMS_SYSGR / TMS_SYSGRPH / TMS_SYSGRP`.** Panoul «Grupe de marfă» /
arborele din Marfă/Stoc și fațetele magazinului se construiesc EXCLUSIV din:

```sql
-- models/biro26_oracle_store.py :: get_product_tree()
SELECT g.GRUPA, g.CATEGORIE, COUNT(*)
FROM TMS_UNIVERS u
JOIN BIRO26_GOODS g ON g.COD_UNIVERS = u.COD     -- ← SURSA grupării
WHERE u.TIP = 'P'
  AND g.GRUPA IS NOT NULL
  AND NVL(u.ISARHIV,'0') <> '2'                  -- soft-delete nativ
GROUP BY g.GRUPA, g.CATEGORIE
```

Adică: **un produs apare în grupare doar dacă are un rând în
`BIRO26_GOODS`** cu `COD_UNIVERS` + `GRUPA` (nivel 1, text) +
`CATEGORIE` (nivel 2, text). Fără id-uri: gruparea e pe ȘIRURI.
Grid-ul Marfă/Stoc face LEFT JOIN pe același feed (dedupe
`ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS)` — un rând per produs
e de ajuns; duplicatele sunt ignorate). `MYSQL_ID`, `USE_IN_WEB`,
`NODETYPE` etc. NU sunt folosite de acest back-office.

De aceea structura voastră `TMS_SYSGR*` — deși corectă bit-cu-bit — nu
apărea: cele 705 produse aveau **0 rânduri în BIRO26_GOODS**.

## 2. Ce am făcut deja (categoria de test e LIVE)

1. **Corectat diacriticele pierdute**: `COMENT`-urile scrise cu «?»
   («Foto ?i Video», «Gen?i ?i Huse…») — baza e `CL8MSWIN1251`, care NU
   are ș/ț; convenția existentă = română fără diacritice. Am rescris
   nodurile 301/* și `TMS_UNIVERS` TIP='T' aferente («Foto si Video»,
   «Genti si Huse pentru aparate foto», «Camere de actiune»…).
2. **Sincronizat plasarea nativă → BIRO26_GOODS**: 705 rânduri inserate
   (GRUPA='Foto si Video', CATEGORIE = numele subnodului, BRAND/FURNIZOR
   ='ULTRA'). Verificat live: arborele shop/back-office arată acum
   **Foto si Video (705)** cu toate cele 7 subcategorii.
3. **Traduceri RU/EN** adăugate în dicționarul `YBIRO_GRP_I18N`
   («Фото и Видео / Photo & Video» + cele 7 categorii) — gruparea
   respectă comutatorul RO·RU·EN.

## 3. Cum aplicați pe restul ~22 000 de produse ULTRA

După ce re-plasați produsele în `TMS_SYSGRP` (modelul vostru e corect),
rulați scriptul de sincronizare per nod de nivel 1:

```bash
cd /Users/pt/Projects.AI/Artgranit        # sau /home/ubuntu/artgranit
python3 scripts/biro26_sync_sysgr_goods.py --group1 <GROUP1>              # dry-run
python3 scripts/biro26_sync_sysgr_goods.py --group1 <GROUP1> --brand ULTRA --go
```

Scriptul: ia numele grupei din nodul `GROUP2=0`, categoriile din
`GROUP2>0`, inserează în `BIRO26_GOODS` doar produsele `TIP='P'` care
lipsesc, și **refuză să ruleze dacă numele conțin «?»** (corectați întâi
`TMS_SYSGRPH.COMENT`, fără diacritice, prin python-oracledb — NU SQLcl).

Apoi traducerile: `/UNA.md/orasldev/biro26-translations` → butonul
«🤖 Tradu tot ce lipsește» (traducere automată RO→RU+EN cu import automat).

## 4. Note pentru importurile viitoare

- Plasarea nativă `TMS_SYSGR*` rămâne utilă pentru aplicația nativă
  UniAcc — dar pentru web trebuie ÎNTOTDEAUNA dublată în `BIRO26_GOODS`
  (sau folosiți direct importul BIRO26PT / wizard-ul care o face singur).
- Prețurile: perioade `TPR1D_PERPRLIST` (codprice=1) — feed-ul
  `BIRO26_GOODS.RETAIL1` e doar fallback. Imaginile:
  `TMS_MPT_TVR.IE_LINKADRES` (deja făcut de voi ✅).
- Fără diacritice în orice text scris în DB (CL8MSWIN1251).

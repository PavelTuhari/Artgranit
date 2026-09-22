# Codurile de bare în una.md și de ce lipseau în documentele din e-Factura (22.09.2026)

Reclamația proprietarului, pe documentul 1209 **EBL000413321** (factura primită,
importată din pachetul e-Factura): «Barcode должны быть везде, и они где-то есть,
но не везде продублированы» + «de ce «Разница» este cu minus».

Pe scurt, ce s-a găsit și ce s-a făcut:

| | Înainte | După |
|---|---|---|
| Rînduri cu «Штрих-код» în EBL000413321 | 0 din 61 | **61 din 61** |
| Rînduri cu «Штрих-код» în toate cele 46 de documente importate | 0 din 352 | **352 din 352** |
| Carduri active care aveau cod de bare în tabel, dar nu-l arătau în documente | 126 330 | **0** |
| Carduri e-Factura fără rînd-părinte `TMS_MPT` (deci fără drept la cod de bare) | 170 | 0 |
| Carduri active fără niciun cod de bare nicăieri | 10 536 | 10 533 (vezi §6) |

## 1. Unde stau codurile de bare (două locuri, nu unul)

Aceasta e cheia întregii probleme: un card de marfă are **două** locuri pentru
cod de bare, iar ecranele citesc locuri diferite.

| Loc | Ce e | Cine îl citește |
|---|---|---|
| `TMS_MPT.STRIH1_CODPRODUCER` | codul de bare **principal** (unul singur pe card) | documentul 1209 (coloana «Штрих-код»), rapoartele, EDI, etichetele — 30 de pachete și proceduri (`PKG_EDI`, `PKG_AVIZ_TVR`, `PKG_DCT`, `EXPORT_GOODS`, `PRINT_TTN_OUT_ORDER` …) |
| `TMS_MPT_BARCODE (COD, BARCODE, COMENT, NSIZE, LGHT, COLOR, NRORD)` | codurile **secundare** — oricîte pe card; 238 897 rînduri | căutarea la scanare, lista de alegere a mărfii în document, `VMS_MPT_BARCODE` |

View-ul `VMS_MPT_BARCODE` le unește și spune explicit care e care:

```sql
SELECT COD, BARCODE, 1 SECONDARY, COMENT FROM TMS_MPT_BARCODE
UNION ALL
SELECT COD, STRIH1_CODPRODUCER, 0, 'main' FROM TMS_MPT WHERE STRIH1_CODPRODUCER IS NOT NULL
```

**«Sînt undeva, dar nu peste tot duplicate»** înseamnă exact asta: 126 330 de
carduri active aveau cod în `TMS_MPT_BARCODE` (deci scanarea le găsea), dar
`STRIH1_CODPRODUCER` era gol — și documentul 1209, care citește doar principalul,
arăta coloana goală. Conveierul standard de import (`YBIRO_IMPORT_MARFA.assign_default_barcode`)
copiază primul cod în principal, dar mărfurile venite pe alte căi (EDI, cartele
făcute de mînă, importurile vechi) nu treceau prin el.

### Unicitatea

- `TMS_BARCODE_UNIQ (COD, BARCODE, SECONDARY)` — tabela de unicitate, întreținută de
  triggerul `TMS_MPT_BARCODE$TR$UNIQ_BAR` (INSERT/UPDATE/DELETE pe `TMS_MPT_BARCODE`);
  același cod de bare la două carduri = eroare la scriere.
- Ambele tabele au FK spre `TMS_MPT.COD` (`TMS_MPT_BARCODE_FK`, `TMS_BARCODE_UNIQ_FK`):
  **fără rînd în `TMS_MPT` nu se poate scrie niciun cod de bare** — de aici
  `ORA-02291 parent key not found` la prima încercare de completare (§4).
- `TRIG_BFIU_TMS_MPT` face `TRIM` pe principal; `YBMB_TMS_MPT`: dacă operatorul scrie
  `'00'` în principal, sistemul generează singur `200 + cod(9) + cifră de control`
  (o a doua schemă internă, mai veche, pe lîngă cea din §2).
- `TMS_MPT_BARCODE_BIU_TRG` (verificare de dubluri) e **dezactivat**; `TMS_MPT_TRLOCK`
  (blocarea editării `TMS_MPT` prin `UNIVLOCK_CHECKCOD`) e **dezactivat** — deci
  UPDATE-ul principalului nu e blocat (conveierul standard verifică exact asta).

### Ce prefixe există (toate 238 897 codurile)

| Prefix | Cîte | Ce e |
|---|---|---|
| `2000…` | 106 751 | EAN-13 **intern**, generat de sistem (§2) |
| `4840…`, `4841…`, `4842…`, `4844…` | 110 408 | EAN-13 Moldova (GS1 MD 484) — codul producătorului |
| `9857…`, `9359…` | 21 458 | serii interne mai vechi |
| altele (`7770…` etc.) | 282 | importuri diverse |

Lungime: 238 889 au 13 cifre; 7 au 15, unul are 6 (date vechi, neatinse).
7 027 carduri au mai mult de un cod secundar.

## 2. Cum se generează un cod nou (conveierul casei)

`BIRO26PT_IMPORTDATA` (importul standard de liste de prețuri) și acum și
`EFA_INBOX` (e-Factura) folosesc aceeași regulă, aceeași secvență, aceeași cifră
de control:

```
'20' || LPAD(BIRO26PT_EAN_SEQ.NEXTVAL, 10, '0') + cifra de control EAN-13
```

Secvența e la **107 019** (22.09.2026) — ultimul cod generat `2000001070185`.
Funcția `gen_ean13` e privată în `BIRO26PT_IMPORTDATA`; `EFA_INBOX.gen_ean13`
e o copie identică (verificat: `gen_ean13(4394) = 2000000043944` în ambele), ca să
nu existe două serii care să se calce.

Ordinea în care se ia codul pentru un card nou (`EFA_INBOX.ensure_barcode`):

1. dacă cardul are deja cod în `TMS_MPT_BARCODE` → acela;
2. altfel codul **din factură** (`EFA_IN_ROW.BARCODE`), dacă nu e deja al altui card
   în `TMS_BARCODE_UNIQ`;
3. altfel EAN generat `2000…`;
4. în toate cazurile: dacă `STRIH1_CODPRODUCER` e gol, se completează cu codul ales
   (`set_main_barcode`) — nu se suprascrie niciodată alegerea operatorului.

Comentariul din `TMS_MPT_BARCODE.COMENT` spune de unde a venit: `RO: cod de bare
din e-Factura / EN: barcode from e-Factura` sau `RO: EAN generat produs nou / EN:
generated EAN new product`.

## 3. Cum ajunge codul de bare pe ecranul documentului 1209 («cnf»)

Formularul 1209 = nodul `A$ADM` **5439**. Gridul cu pozițiile este LOB-ul
`A$LOB (OBJ_ID=5439, LOB_NAME=':fmDG1:gr21a')`, 10 053 octeți — la acest formular
nu e SDBG binar, ci **XML** (`<xml><props…/><cols>…</cols><ds>…</ds>`), ceea ce
se poate citi direct din SQL cu `dbms_lob.substr` fără uniConf.
Panoul de antet e `':fmDG1:dp21'` (LOB_TYPE 9), lista personalizată `pcCustom`.
Ghidul de configurare: `/Users/pt/Projects.AI/BIRO26/AI_CONF_AND_GRID_GUIDE.md`
(secțiunile 4.3 «Форматы blob» și 5 «Два источника SQL»).

Coloana din grid:

```xml
<col field="CLCSTRINGX_1" width="87" caption="Штрих-код">
```

Iar `CLCSTRINGX_1` vine din view-ul documentului `YBON_VMDB_ST201D_TVR`:

```sql
(SELECT t.STRIH1_CODPRODUCER FROM TMS_MPT t WHERE t.cod = a.dtsc) CLCSTRINGX_1
```

— adică **numai principalul**, nu tabela de coduri secundare. De aceea un card cu
cod în `TMS_MPT_BARCODE` dar cu principalul gol apare în document fără cod.

Al doilea loc unde apare codul de bare în același formular: lista de alegere a
mărfii (picklist-ul coloanei «Товар»), al cărei SQL e tot în LOB:

```sql
select distinct a.cod, r.barcode clcstringx_1, b.price pretv1, a.clccodt denumirea, 1 cant, 2171 dt
from vmdb_spec_cant a, vpr_div_prices b, vms_mpt_barcode r
where … and r.cod(+) = a.cod
-- RESULTFIELDS=dtsc,clcstringx_1,pret,clcdtsct,cant,dt
```

Aceasta citește `VMS_MPT_BARCODE` (principal + secundare), deci la alegerea
manuală a mărfii codul se completa; la documentele create din e-Factura rîndurile
se scriu direct în `VMDB_ST201D` și coloana se calculează la afișare — din
principal. Nu e nimic de schimbat în configurația formularului: e corect ca un
document să arate codul principal; trebuia doar ca principalul să existe.

## 4. De ce cardurile din e-Factura nu aveau nimic

Importul simplu (`modules/efactura/simple.py`, `EfaSimple.create_goods`) crea cardul
din `TMS_UNIVERS` (TIP `P`, GR1 `TVR`) + `TMS_MPT_TVR` — atît. Lipseau:

1. **rîndul-părinte `TMS_MPT`** — toate celelalte căi îl fac: triggerele view-ului
   `VMS_UNIVERS` (`TR_VMS_UNIV_P05/P10/P15`, `VMS_UNIV_MPT_ALL`), `YBIRO_IMPORT_MARFA`,
   `PKG_EDI`, `UN$STRL`, `YBON_TERMINAL`. Cardurile casei au `MATGR1=1`
   (146 287 din 201 667 active) și `DEP_PRODUCER` = furnizorul;
2. **codul de bare** — cele 47 de facturi din fișier aveau `<Barcode>` gol pe toate
   rîndurile, iar generarea nu era apelată;
3. **codul principal** — consecință a 1 și 2.

### Reparat în cod (`feat/efactura`, commit `da35146`)

| Fișier | Ce s-a schimbat |
|---|---|
| `modules/efactura/sql/06_efa_inbox_pkg.sql` | `ensure_barcode(cod, barcode)` + `gen_ean13` (copia conveierului) + `set_main_barcode` — completează `STRIH1_CODPRODUCER` dacă e gol; instalat cu `efactura_deploy.py`, pachet VALID |
| `modules/efactura/simple.py` | `create_goods(name, um, barcode, supplier_cod)` scrie și `TMS_MPT (COD, MATGR1=1, DEP_PRODUCER)` și apelează `EFA_INBOX.ensure_barcode`; `import_file` îi dă codul din factură și furnizorul |
| `tests/test_efactura.py` | +2 teste (`TMS_MPT` + barcode la creare; codul din factură și furnizorul ajung la creare) — 80 de teste trec |

### Reparat în date (22.09.2026, baza OfficePlus)

1. **170 carduri e-Factura** (540709–540968): `INSERT INTO TMS_MPT (COD, MATGR1,
   DEP_PRODUCER)` cu furnizorul din documentul în care apar, apoi
   `EFA_INBOX.ensure_barcode` → 170 de EAN-uri `2000001068496 … 2000001070185`
   (secvența 106 848 → 107 019); principalul completat.
2. **119 216 carduri** active cu exact un cod secundar și principalul gol:
   principal = acel cod (în loturi de 5 000, 114 s).
3. **6 744 carduri** active cu mai multe coduri secundare și principalul gol:
   principal = codul **producătorului** (care nu începe cu `200`), la egalitate cel
   cu `NRORD` mai mic — deci pe etichete și în EDI iese codul real, nu cel intern.
4. Nu s-a suprascris niciun principal existent (64 980 de carduri îl aveau deja);
   3 carduri au principal care nu e în tabela secundară — lăsate așa, e alegerea
   operatorului.

Triggerele care au rulat la aceste UPDATE-uri: `XTRIGLOG_MPT` (jurnal `Un$xlog`,
ca la orice editare), `TMS_MPT_ACL_TRG` (ACL după `DEP_PRODUCER`), `YLIN_TMS_MPT_TRG`
(doar TIP `T`/`TREE`). Replicarea `XRDB$LOG_UNIV_MPT` e dezactivată. Operația e
reversibilă: lista cardurilor atinse = cele cu `STRIH1_CODPRODUCER` egal cu un cod din
`TMS_MPT_BARCODE` și `Un$xlog` din 22.09.2026.

## 5. «Разница» cu minus

Coloana «Раз-ница» din grid e `CLCSUMAX_4`, definită în `YBON_VMDB_ST201D_TVR`:

```sql
ROUND(NVL(clcsumax_1,0) - NVL(pret,0), 2)  clcsumax_4   -- разница закуп. цен
```

unde `clcsumax_1` («закупочная») este prețul **din lista de prețuri a furnizorului**:
`VPR_DIV_PRICES.PRICE` pentru depozitul/clientul documentului, altfel
`VPR_PRLIST_TVR.PRETV2` la data documentului; iar `PRET` e prețul din factură.
Deci «Разница» = *prețul de listă − prețul facturat*: pozitiv cînd furnizorul a
facturat sub lista lui, negativ cînd peste, și **egal cu −PRET cînd cardul nu are
niciun preț de listă** (`NVL(…,0) − pret`). Exact cazul cardurilor noi din
e-Factura: 166 din 170 nu au niciun rînd în `VPR_PRLIST_TVR`, deci coloana arată
minus prețul de achiziție. Nu e o eroare de calcul — e semnalul că marfa nu are
încă preț de listă / de vînzare. La fel «Продажная цена» (`VINZ_PRET` = `PRETV4`)
și «КТН наш» sînt goale pentru ele.

### Regula prețurilor (proprietarul, 22.09.2026): «prețul de price să fie cu 10% mai mic ca prețul de vînzare»

Adică prețul de listă (`PRETV2`, cel cu care se compară factura) = prețul din
factură, iar prețul de vînzare (`PRETV4`) = `PRETV2 / (1 − 10%)`:
14,95 → 16,61; 1,95 → 2,17; 3,55 → 3,94. Prețul din factură se ia **cu TVA**
(`VMDB_ST201D.PRET`) — firma nu e plătitoare, deci acesta e costul real.

| Ce | Unde |
|---|---|
| Procentul (10) | `YBIRO_SETTINGS.EFA_PRICE_BELOW_SALE_PCT` — se schimbă din setări, nu din cod; seed idempotent în `07_efa_syss_seed.sql` |
| Regula | `EFA_INBOX.ensure_prices(nrdoc [, pct])` — pentru fiecare marfă din document: dacă nu are perioadă de preț la data documentului → `INSERT INTO VPR_PRLIST_TVR (DATA, SC, PRETV2, PRETV4, N1=nrdoc)` (triggerul view-ului închide singur perioada vecină, `DATAF = 31.12.3000`, exact ca `YLIN_DOCS` la postare); dacă are → completează **doar** `PRETV2`/`PRETV4` goale. Prețurile puse de operator nu se ating; rîndurile cu preț ≤ 0 (retururi, reduceri) se sar |
| Apel | `simple.py` → imediat după `create_doc_from_in` la importul simplu |

Aplicat pe cele 47 de documente importate (în ordinea datei): **256 din 257
carduri** au acum preț de listă = factura și preț de vînzare = listă/0,9; toate
cele 61 de rînduri din EBL000413321 au «Разница» = 0,00 și «Продажная цена»
completată. Singurul rînd rămas e o linie cu preț **−650** (reducere), care nu e
marfă cu preț. Cardurile vechi din aceleași documente (86) care nu aveau nicio
perioadă de preț au primit-o după aceeași regulă; cele 5 care aveau preț de
vînzare au rămas cu al lor.

Atenție, două prețuri ≠ vitrina: officeplus.md citește `VTPR1D_PERPRLIST`
(liste pe `CODPRICE`, `PRETV`/`PRETV1`/`PRETV2` = retail/angro/online) și
`BIRO26_GOODS`; cele 170 de carduri e-Factura nu sînt în `BIRO26_GOODS`, deci nu
apar pe site pînă nu sînt puse într-o listă de prețuri a vitrinei.

## 6. Ce a rămas fără cod de bare și de ce nu s-a generat

10 533 carduri active (TIP `P`, GR1 `TVR`) nu au cod nici principal, nici secundar.
Toate sînt vechi: **niciuna** nu apare într-un document din 2025–2026, niciuna nu
are preț de vînzare curent, niciuna nu a fost creată după 2025 (cod ≤ 500 000).
E nomenclator mort. Nu s-au generat coduri pentru ele — ar consuma 10 533 de
numere din serie pentru marfă care nu circulă. Dacă vreuna reintră în circulație,
la primul import/cartelă `ensure_barcode` sau conveierul standard îi dă cod.

Dacă totuși se vrea «absolut peste tot», comanda e una singură (reversibilă prin
`COMENT`):

```sql
BEGIN
  FOR c IN (SELECT u.cod FROM tms_univers u JOIN tms_mpt m ON m.cod=u.cod
             WHERE u.tip='P' AND NVL(u.isarhiv,'0')<>'2' AND m.strih1_codproducer IS NULL
               AND NOT EXISTS (SELECT 1 FROM tms_mpt_barcode b WHERE b.cod=u.cod)) LOOP
    DECLARE v VARCHAR2(15); BEGIN v := efa_inbox.ensure_barcode(c.cod); END;
  END LOOP;
END;
```

(8 dintre ele nu au nici `TMS_MPT` — pentru acelea întîi `INSERT INTO tms_mpt (cod, matgr1)`.)

## 7. Desfășurare și verificare

- Baza Oracle e comună tuturor contururilor — datele și pachetul `EFA_INBOX` sînt
  deja în vigoare peste tot.
- Codul (`simple.py`, `06_efa_inbox_pkg.sql`, `tests/test_efactura.py`) dus pe
  **nufarul 92.5.3.187** și **office 192.168.0.250** (vitrina publică prin failover):
  înainte de copiere md5-ul fișierelor de pe server era cel din git (`01ea09dd…`,
  `7a822319…`, `ac585733…`), deci nimic străin nu a fost suprascris; `.bak-2026-09-22`
  alături; `login` 200, 0 Traceback. Pe rezerva **92.5.130.1** modulul e-Factura e
  versiunea veche (fără `inbox.py`/`simple.py`) și nu servește trafic — neatins.
- Ramura `feat/efactura` (worktree `Artgranit-efactura`); ramura de import de date
  a celeilalte sesiuni (`feat/biro26-catalog` și altele) nu a fost atinsă:
  `git diff --name-only main HEAD` — doar `modules/efactura/`, `tests/test_efactura.py`,
  `docs/Partner/`.

Cum verifici în una.md: deschide 1209 **EBL000413321** — toate cele 61 de rînduri au
«Штрих-код»; sau

```sql
SELECT COUNT(*) total, COUNT(m.strih1_codproducer) cu_barcode
  FROM vmdb_st201d l JOIN efa_in e ON e.dest_nrdoc = l.nrdoc
  LEFT JOIN tms_mpt m ON m.cod = l.dtsc
 WHERE e.env = 'file';            -- 352 / 352
```

## Adrese live

- Acest document: <https://officeplus.md/UNA.md/orasldev/efactura/docs/EFACTURA_CODURI_DE_BARE.md>
  · <https://nufarul.eminescu.md/UNA.md/orasldev/efactura/docs/EFACTURA_CODURI_DE_BARE.md>
- Administrarea e-Factura (importul simplu): <https://officeplus.md/UNA.md/orasldev/efactura/>
- Actul importului simplu din 14.09.2026: <https://officeplus.md/UNA.md/orasldev/efactura/docs/EFACTURA_ACT_IMPORT_SIMPLU_2026-09-14.html>
- Raportul cu ce s-a inserat și unde: <https://officeplus.md/UNA.md/orasldev/efactura/docs/EFACTURA_IMPORT_14-09-2026.html>

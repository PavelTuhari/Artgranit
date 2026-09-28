# TVA în OfficePlus/UNA: de unde vine cota și ce a fost corectat

> Document tehnic. Varianta pentru utilizatori: `instructiune_tva_una.html`.

## 1. Cascada — `UN$FUNCTS.TVA(marfa, client, nrdoc, data)`

Verificările se fac în ordine și **prima care răspunde oprește căutarea**:

| # | Sursa | Condiția | Rezultat |
|---|---|---|---|
| 1 | parametrul `isVATPayer` | `= 0` | `0` |
| 2 | documentul `TMDB01M_VINZ.VATFREE` | `= 1` | `0` (cotă zero) |
| | | `= -1` | `NULL` (fără TVA) |
| 3 | cartela **clientului**, la data documentului | `CODTVA = '0'` | `0` |
| | | `CODTVA = 'N'` | `NULL` |
| 4 | cartela **mărfii**, la data documentului | `'0'`→0, `'N'`→NULL, `'B'`→0.08, `'C'`→0.05, `'D'`→0.06, `'E'`→0.1 | altfel `0.2` |

**Documentul bate clientul, clientul bate marfa.**

### Butoanele din formular = valorile din `VATFREE`

Confirmat din sursa aplicatiei (`Dll/unD001/ufmD001a.dfm`, `rg01TVAFree`, `DataField='VATFREE'`):

```
Items.Strings  = ('Cu TVA', 'TVA 0%', 'Fara TVA')
Values.Strings = ('0',      '1',      '-1')
```

Interfata si motorul **coincid**: `1` -> `return 0` (cota zero), `-1` -> `return null`
(fara TVA). Nu exista nepotrivire intre eticheta si efect. `VATFREE` se scrie exclusiv
din acest grup de butoane (`:VATFREE` in `uDMdata.dfm`), deci ia doar valorile 0 / 1 / -1.

`0` (cotă zero, impozabilă) și `N` (în afara TVA) se contabilizează diferit — nu sunt sinonime.

## 2. Istoricul de TVA

`TMS_UNIVERS.CODTVA` e valoarea *curentă* a cartelei. Valoarea **aplicabilă** vine din
istoric — `TMH_UNIVERS` (view-uri `VMH_UNIVERS`, `VMH_UNIVERS_ACT`), cu `START_DATE` /
`END_DATE`.

Istoricul se folosește doar când sesiunea are contextul `envun4.un$functs_hist_tva` setat;
altfel se citește direct cartela. **Schema UNI nu are deloc acest mecanism** — de aceea acolo
scutirea de pe cartelă se aplică instantaneu, indiferent de dată.

`TMH_UNIVERS_TRG` **interzice ștergerile** („Удаления из истории изменений запрещены!").
Istoricul e jurnal: intrările greșite se corectează prin `UPDATE`, nu se elimină.

## 3. Defectul corectat (22.08.2026)

În `UN$FUNCTS.get_codtva`, ramura fără dată explicită calcula corect data documentului în
`v_date`... și apoi o **ignora**, interogând `VMH_UNIVERS_ACT` — adică starea de *azi*:

```sql
-- inainte
select coalesce(un$datadoc, un$datauniv, trunc(sysdate)) into v_date from dual;
execute immediate 'select codtva from vmh_univers_act where cod = :p_cod'
  into v_vat_code using p_cod;              -- v_date nefolosita

-- dupa
execute immediate
  'select codtva from vmh_univers where cod = :p_cod and :p_date between start_date and end_date'
  into v_vat_code using p_cod, v_date;
```

`v_date` era folosită doar în mesajul de eroare — semn clar că interogarea rămăsese pe
view-ul greșit.

**Efectul:** o factură retrodatată primea cota de azi, nu pe cea valabilă la data ei. La
clientul 471738 (IURILEN-FLOR SRL), factura din 20.08.2026 ieșea cu 20% deși clientul era la
0% în acea zi.

### Verificare după corectare

| Data documentului | Cota |
|---|---|
| 19.08.2026 | **0.2** (înainte de scutire) |
| 20.08.2026 | **0.0** |
| 01.03.2027 | **0.0** |

Control, client normal (CRAFTI, 161245): `0.2` la toate datele — neschimbat.

## 3a. A doua corectie (23.08.2026): regenerarea GFC nu recalcula TVA-ul

Dupa corectia din §3 a iesit la iveala inca un strat: **TVA-ul de pe randurile
documentului este STOCAT** (`VMDB_ST201D.SUMAVALCT` / `SUMAGAAP`), scris la crearea
documentului. Regenerarea formulelor contabile (`YBON_DOCS.perecislenie_NN_GFC`)
doar **posta** aceste sume stocate — recalcularea (`Cassa_NN_calc_VAT`) era chemata
exclusiv la creare (`PKG_CARDS`).

Consecinta: schimbai regimul de TVA (pe document sau pe client), regenerai formulele —
si contabilitatea ramanea pe sumele VECHI. Exact simptomul de la documentul 369.

**Corectia:** `perecislenie_NN_GFC` apeleaza acum intii `Cassa_NN_calc_VAT(vNrdoc)`,
deci orice regenerare recalculeaza sumele dupa atributele CURENTE si abia apoi posteaza.

Verificat pe 369, ambele directii dintr-un singur apel:

| Atribute | 5342 (TVA colectat) | 6112 (venit) |
|---|---|---|
| Cu TVA (client `A`, `VATFREE=0`) | **776.18** | 3880.82 |
| TVA 0 (client `0`, `VATFREE=1`) | **0** | 4657 |

Fisier: `YBON_DOCS_fix_gfc_recalc_vat.sql`; copie de rezerva: `Backups/ybon_docs/`.

> **Lectie:** intr-un sistem cu valori stocate, o corectie de FUNCTIE nu repara datele
> deja scrise, iar o REGENERARE care nu recalculeaza nu e o regenerare completa.
> Verificati intotdeauna lantul intreg: functie -> randuri -> formule.

## 4. Corectarea de date

Istoricul clientului 471738 avea fereastra de 0% de **două zile** (20–21.08.2026), apoi
revenea la `A`. Rândul de la 22.08 a primit `CODTVA = '0'` (prin `UPDATE`, nu `DELETE` —
triggerul interzice ștergerea), deci scutirea e acum neîntreruptă de la 20.08.2026.

Istoricul rezultat păstrează ambele etape: fereastra inițială și corecția (vizibilă prin
`UPDATE_DATE`).

## 5. Fișiere

| Fișier | Ce conține |
|---|---|
| `UN_FUNCTS_fix_get_codtva.sql` | pachetul corectat, gata de rulat |
| `Backups/unfuncts/UN_FUNCTS_body_20260822_2024.sql` | versiunea dinainte, pentru revenire |
| `TMH_UNIVERS_fix_471738.sql` | corectarea istoricului clientului |
| `instructiune_tva_una.html` | instrucțiunea publică pentru utilizatori |

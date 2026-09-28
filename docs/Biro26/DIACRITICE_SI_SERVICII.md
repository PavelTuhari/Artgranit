# Diacritice românești în baza CL8MSWIN1251 — algoritmi Python, trigger de protecție, funcții de serviciu

> Documentul acoperă trei lucruri: **(1)** de ce se strică textul și cum se previne în cod
> (algoritm Python), **(2)** cum se repară datele deja stricate (4 algoritmi Python),
> **(3)** protecția în bază (trigger) și modul „Servicii" din back-office.

---

## 1. Cauza: baza NU e UTF-8

`OFFICEPLUS` are `NLS_CHARACTERSET = CL8MSWIN1251` (chirilic, un octet). **Orice** caracter
care nu încape în cp1251 devine `?` — tăcut, fără eroare:

| Sursă (xlsx/csv) | Stocat în BD |
|---|---|
| `Foto și Video` | `Foto ?i Video` |
| `Cărți educaționale` | `C?r?i educa?ionale` |
| `22×10×32 cm` | `22?10?32 cm` |
| `170 g/m²` | `170 g/m?` |
| `Wi‑Fi` (non-breaking hyphen) | `Wi?Fi` |

Chirilica trece corect (cp1251 o conține). Problema nu e doar diacritica românească — e
**orice** caracter non-cp1251.

---

## 2. Prevenirea în cod (algoritm Python) — `cp1251_safe()`

Se aplică **înainte** de scrierea în BD, la: celule, **numele foii** (devine GRUPA) și numele
fișierului. Există în **ambele** loadere: `biro26pt_loader.py` (local) și
`models/biro26pt_loader.py` (aplicația web / GUI).

```python
import unicodedata

_TRANSLIT = {
    "ă":"a","Ă":"A","â":"a","Â":"A","î":"i","Î":"I",
    "ș":"s","Ș":"S","ş":"s","Ş":"S","ț":"t","Ț":"T","ţ":"t","Ţ":"T",
    "×":"x","÷":":","−":"-","‐":"-","‑":"-","‒":"-","―":"-",
    "≤":"<=","≥":">=","≈":"~","≠":"!=","′":"'","″":'"',"ʼ":"'",
    "½":"1/2","¼":"1/4","¾":"3/4","⁄":"/","·":".","∙":".",
    "ﬁ":"fi","ﬂ":"fl","œ":"oe","Œ":"OE","æ":"ae","Æ":"AE",
    "ß":"ss","ø":"o","Ø":"O","đ":"d","Đ":"D","ł":"l","Ł":"L",
    "​":"","‌":"","‍":"","﻿":"","­":"",
    " ":" "," ":" "," ":" "," ":" ",
}

def cp1251_safe(s: str) -> str:
    """Text garantat stocabil în CL8MSWIN1251 / guaranteed cp1251-safe text."""
    out = []
    for ch in s:
        repl = _TRANSLIT.get(ch)
        if repl is not None:
            out.append(repl); continue
        try:                                  # deja în cp1251 (inclusiv chirilica)
            ch.encode("cp1251"); out.append(ch); continue
        except UnicodeEncodeError:
            pass
        dec = unicodedata.normalize("NFKD", ch)          # é -> e + accent
        dec = "".join(c for c in dec if not unicodedata.combining(c))
        dec = "".join(_TRANSLIT.get(c, c) for c in dec)
        try:
            dec.encode("cp1251"); out.append(dec)
        except UnicodeEncodeError:
            out.append("")                    # nerecuperabil (emoji) -> se elimină
    return "".join(out)
```

**Cheia algoritmului:** tabelul acoperă cazurile frecvente, iar `NFKD` prinde restul (orice
literă latină cu semne). Chirilica nu e atinsă niciodată.

---

## 3. Repararea datelor deja stricate — 4 algoritmi

Scripturile complete: `scripts/diacritics/01..05_*.py`. Se rulează **în ordine**, fiecare cu
dry-run întâi (fără `--go`).

### 3.1 Regula de aur (valabilă pentru toți algoritmii)

```python
def is_mangled_char(word, i):
    """'?' e stricat DOAR între litere/cifre. La final de cuvânt e semn de întrebare real."""
    return (word[i] == '?' and 0 < i < len(word) - 1
            and word[i-1].isalnum() and word[i+1].isalnum())
```

„Кто испек пирог?" trebuie să rămână neatins. (Un audit a prins exact acest caz —
`Откуда берутся дети?` fusese transformat în `дети.` și a fost derulat înapoi.)

### 3.2 Algoritmul 1 — din fișierele sursă (`01_repair_from_sources.py`)

Pentru fiecare text din xlsx/csv se calculează **forma stricată** (roundtrip cp1251) și forma
corectă; se potrivesc cu valorile din BD.

```python
def mangle(s):                       # exact ce ajunge în BD
    return s.encode('cp1251', errors='replace').decode('cp1251')

DICT = {}                            # mangled -> corect
for s in toate_textele_din_fisiere:
    m = mangle(s)
    if '?' in m:                     # sursa avea caractere non-cp1251
        c = cp1251_safe(s)
        if '?' not in c:
            DICT[m] = c
# apoi: UPDATE tabel SET col = DICT[val] WHERE col = val
```

### 3.3 Algoritmul 2 — potrivire prin mască (`02_repair_from_db.py`)

`?` = orice caracter; se compară cu textele **deja curate** (din fișiere ȘI din BD). Se aplică
doar când potrivirea e **unică** — altfel s-ar ghici.

```python
import re
def mask_match(v, candidates):
    rx = re.compile('^' + ''.join('.' if c == '?' else re.escape(c) for c in v))
    hits = {c[:len(v)] for c in candidates if len(c) >= len(v) and rx.match(c)}
    return hits.pop() if len(hits) == 1 else None      # ambiguu -> nu atingem
```
Funcționează și pentru texte **trunchiate** în BD (transliterarea e 1:1 pe caractere, deci
lungimea se păstrează și prefixele corespund).

### 3.4 Algoritmul 3 — la nivel de cuvânt (`03_repair_by_word.py`)

Corpus de cuvinte curate (din fișiere + BD); un cuvânt stricat se potrivește prin mască cu un
cuvânt cunoscut. Se acceptă doar dacă un candidat **domină** ca frecvență.

```python
from collections import Counter
WORDS = Counter()                    # corpus: cuvânt curat -> frecvență
MIN_RATIO = 4                        # top-ul trebuie să fie de 4× mai frecvent

def fix_word(w):
    rx = re.compile('^' + ''.join('.' if c == '?' else re.escape(c) for c in w) + '$')
    cand = sorted(((WORDS[x], x) for x in WORDS if len(x) == len(w) and rx.match(x)),
                  reverse=True)
    if cand and (len(cand) == 1 or cand[0][0] >= MIN_RATIO * cand[1][0]):
        return cand[0][1]            # "car?i" -> "carti"
    return None
```

### 3.5 Algoritmul 4 — margini de cuvânt (`04_repair_word_edges.py`)

Pentru `?` la **început** de cuvânt (`?coala`, `?i`) sau la **sfârșit** (`Co?`), cu protecție:

```python
REAL_Q_MIN = 3
def fix_word_edges(w):
    # dacă restul cuvântului e un cuvânt real frecvent -> e semn de întrebare, nu-l atingem
    if w.endswith('?') and WORDS.get(w[:-1], 0) >= REAL_Q_MIN:
        return None                  # "пирог?" -> lăsat în pace
    return fix_word(w)               # "?coala" -> "scoala"
```

> ⚠️ **Ce NU funcționează:** potrivirea *case-insensitive* a corpusului. A produs gunoi
> (`Cine e?ti?` → `Cine entin`, `РОБОТ?` → `РОБОТы`) și a fost abandonată.

### 3.6 Algoritmul 5 — staging RAW (`05_repair_raw_staging.py`)

Curăță `BIRO26PT_RAW`, altfel un re-import al unui `load_id` vechi readuce `?` în producție.
Are în plus o **gardă pentru URL-uri** (`?` acolo e separator de query string):

```python
if s.lstrip()[:8].lower().startswith(('http://', 'https:/', 'www.')):
    return None                      # "...webp?v=1728206119" - legitim
```

### 3.7 Rezultate obținute

| Tabel | Înainte | Rămas stricat |
|---|---|---|
| `TMS_UNIVERS.denumirea` | 9 748 | **173** |
| `BIRO26_GOODS.denumire` | 4 190 | **49** |
| `BIRO26_GOODS.categorie` | 5 798 | **90** |
| `BIRO26_GOODS.grupa` | 7 260 | **0** |
| `TMS_SYSGRPH.coment` | 7 | **0** |
| `BIRO26PT_RAW` | ~308 000 | 29 368 text + 71 969 URL (legitim) |

Restul (~170 carduri) nu are sursă de recuperare — se exportă din modul „Servicii" (§5).

---

## 3b. Soluția definitivă pentru câmpuri noi: originalul în BLOB

Transliterarea (§2) salvează datele, dar **pierde** diacriticele. Pentru câmpurile noi
(descrieri web) folosim soluția care nu pierde nimic: **originalul se ține în BLOB**.

Baza nu transcodează niciodată octeții unui BLOB, deci `Cărți educaționale` rămâne exact așa,
chiar dacă `NLS_CHARACTERSET` e `CL8MSWIN1251`. Copiile pentru căutare (fără diacritice) se
generează automat, prin trigger.

```
scriere:   text UTF-8 ──► BLOB (octeți, neatinși)
                            │  trigger TMS_MPT_WEBATTR_BIU
                            ▼
citire:    BLOB ──► NCLOB (AL16UTF16, Unicode) ──► TRANSLATE + REPLACE ──► CLOB/VARCHAR2
           (afișare cu diacritice)                 (căutare/index, fără diacritice)
```

Cheia tehnică — charset-ul **național** `AL16UTF16` suportă Unicode complet, deci pasul
`BLOB → NCLOB` (`DBMS_LOB.CONVERTTOCLOB(..., 873, ...)`, 873 = AL32UTF8) păstrează diacriticele;
abia după transliterare textul (deja ASCII) coboară în charset-ul bazei.

Implementare: pachetul `YBIRO_TEXT_UTIL` (`blob_to_nclob`, `strip_diacritics`, `blob_to_plain`,
`nclob_to_blob`) + tabela `TMS_MPT_WEBATTR` cu triggerul ei. Detalii: `GHID_IMPORT_ALTE_SCHEME.md` §3.4.

**Când se folosește ce:**
- câmp nou, unde diacriticele contează (descriere, denumire completă) → **BLOB + trigger**;
- câmpuri ERP existente (`TMS_UNIVERS.DENUMIREA` etc.) → transliterare (§2) + trigger de pază (§4).

## 4. Protecția în bază: trigger `YBIRO_UNIVERS_CHK_DIACRITICE`

Blochează scrierea de text stricat în `TMS_UNIVERS` (`DENUMIREA`, `NAMERUS`, `GR2`), ca
problema să nu se mai poată repeta din nicio aplicație. Sursa: `YBIRO_UNIVERS_CHK_DIACRITICE.trg.sql`.

**Ce detectează** (doar tipare sigure, ca să nu blocheze semne de întrebare reale):
1. `?` între litere/cifre → `car?i`, `22?10?32`
2. `?` la început de cuvânt → `?coala`, `?i`, `?tampila`

**Ce NU blochează:** `?` la sfârșit de cuvânt/frază („Ce sport sa-mi aleg?"), și nici
actualizarea pe alte coloane a rândurilor vechi care conțin deja `?`.

Testat pe 7 scenarii: 3 stricate → blocate; 1 curat → acceptat; 2 întrebări reale → acceptate;
1 update pe altă coloană a unui rând vechi → trece.

```sql
-- oprire de urgență / emergency off
ALTER TRIGGER YBIRO_UNIVERS_CHK_DIACRITICE DISABLE;
```

Mesajul de eroare (`ORA-20077`) e bilingv și spune exact ce trebuie făcut: transliterați
înainte de scriere.

---

## 5. Modul „Servicii" din back-office (registru dinamic)

Tab nou **Servicii** în back-office. Lista funcțiilor **nu e în cod** — vine din tabelul
`YBIRO_SERVICE_FUNCTIONS`, deci o funcție nouă = **un INSERT**.

### 5.1 Structura registrului

| Coloană | Rol |
|---|---|
| `code` | identificator (folosit în URL) |
| `ord` | ordinea în listă |
| `kind` | `csv` (export) |
| `name_ro/ru/en`, `descr_ro/ru/en` | texte trilingve pentru interfață |
| `src_sql` | interogarea **SELECT** care produce datele |
| `file_name` | numele fișierului CSV |
| `enabled` | `Y`/`N` |

### 5.2 Adăugarea unei funcții noi (fără cod)

```sql
INSERT INTO YBIRO_SERVICE_FUNCTIONS
 (code, ord, kind, name_ro, name_ru, name_en, descr_ro, descr_ru, descr_en, src_sql, file_name)
VALUES ('marfa_fara_pret', 20, 'csv',
  'Marfă fără preț', 'Товары без цены', 'Goods without price',
  'Marfa care nu are nicio perioadă de preț activă.',
  'Товары, у которых нет активного ценового периода.',
  'Goods with no active price period.',
  'SELECT u.cod, u.codvechi, u.denumirea FROM tms_univers u WHERE u.tip=''P''
     AND NOT EXISTS (SELECT 1 FROM tpr1d_perprlist p WHERE p.sc=u.cod)',
  'marfa_fara_pret');
COMMIT;
```
Funcția apare imediat în interfață, cu numărul de rânduri și buton de descărcare.

### 5.3 Securitate

Se execută **doar** interogări `SELECT` stocate în registru (administrate din bază), niciodată
SQL primit de la client. Verificare în `models/biro26_services.py`:

```python
_SELECT_ONLY = re.compile(r"^\s*select\s", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|drop|alter|create|"
                        r"truncate|grant|revoke|execute|begin|declare)\b", re.IGNORECASE)
```
Toate cele 3 endpoint-uri cer autentificare.

### 5.4 Prima funcție: `problem_cards`

Exportă cardurile de marfă rămase cu text stricat — cele care **nu** au putut fi reparate
automat (lipsește fișierul-sursă). View: `YBIRO_V_PROBLEM_CARDS`.

Coloane CSV: `COD; ARTICOL; DENUMIRE; TIP; GRUPA; CATEGORIE; FURNIZOR; BARCODE; TIP_PROBLEMA`
(`TIP_PROBLEMA` = `INNER` / `WORD_START`). Format: `;` + BOM → se deschide direct în Excel RO/RU.

**Ce face operatorul cu fișierul:** corectează denumirile manual în ERP, **sau** trimite
furnizorului cererea de re-export și reîncarcă fișierul prin *Import (asistent)* — de data
aceasta textul intră deja transliterat corect.

### 5.5 API

| Endpoint | Rol |
|---|---|
| `GET /api/biro26/services?lang=ro` | lista funcțiilor (dinamică) |
| `GET /api/biro26/services/<code>/count` | câte rânduri produce |
| `GET /api/biro26/services/<code>/csv` | descarcă CSV |

---

## 6. Fișiere

- Prevenire: `biro26pt_loader.py`, `Artgranit/models/biro26pt_loader.py` (`cp1251_safe`)
- Reparare: `scripts/diacritics/01..05_*.py`
- Protecție: `YBIRO_UNIVERS_CHK_DIACRITICE.trg.sql`
- Servicii: `Artgranit/models/biro26_services.py`, `app.py`, `templates/biro26/backoffice.html`
- Context: `GHID_IMPORT_ALTE_SCHEME.md` §9.14, `INSTRUCTIUNE_INCARCARE_DATE.md`

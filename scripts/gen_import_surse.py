# -*- coding: utf-8 -*-
import sys, csv, io; sys.path.insert(0,'/tmp')
from db import conn
c=conn(); cur=c.cursor()
cur.execute("ALTER SESSION SET NLS_DATE_FORMAT='DD.MM.YYYY'")
srcs=list(cur.execute("""SELECT src_code,cod_org,src_name,src_type,src_location,algo_code,
  art_prefix,art_min_len,file_format,mark_new,only_articol,notes,active
  FROM tms_org_impsrc ORDER BY src_type, src_code"""))
files=list(cur.execute("""SELECT src_file, COUNT(*), SUM(n_rows), MIN(load_id), MAX(load_id),
  TO_CHAR(MIN(loaded_at),'DD.MM.YYYY') FROM biro26pt_file GROUP BY src_file ORDER BY MIN(load_id)"""))
def rd(x): return '' if x is None else str(x)

# ---------- CSV ----------
with io.open('/Users/pt/Projects.AI/BIRO26/IMPORT_SURSE.csv','w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f, delimiter=';')
    w.writerow(['SRC_CODE','SRC_NAME','SRC_TYPE','SRC_LOCATION','ALGO_CODE','ART_PREFIX',
                'ART_MIN_LEN','FILE_FORMAT','MARK_NEW','ONLY_ARTICOL','ACTIVE','COD_ORG','NOTES'])
    for s in srcs:
        w.writerow([s[0],s[2],s[3],rd(s[4]),s[5],rd(s[6]),s[7],rd(s[8]),s[9],s[10],s[12],rd(s[1]),rd(s[11])])
print("CSV scris:", len(srcs), "surse")

TIP={'SCRAPING':'Scraping de pe site','EMAIL':'Fisier primit pe e-mail',
     'B2B':'Portal B2B pentru parteneri','MANUAL':'Incarcare manuala / export intern'}
L=[]
a=L.append
a('# Sursele de import — catalog complet')
a('')
a('> Generat din tabela `TMS_ORG_IMPSRC` (extinderea cartelei furnizorului `TMS_ORG`).')
a('> Varianta tabelara: `IMPORT_SURSE.csv`. Regenerare: `python3 scripts/gen_import_surse.py`.')
a('')
a('## De ce exista acest document')
a('')
a('Fiecare sursa de date are propriile capcane: unde e antetul, ce coloane exista, cum')
a('arata articolul, ce lipseste. Pana acum aceste detalii traiau doar in capul celui care')
a('facea importul; acum stau in baza si pot fi alese din back-office.')
a('')
a('## Prefixul de articol — regula cea mai importanta')
a('')
a('Codurile scurte sau pur numerice (`248`, `670`, `2917`) inseamna **produse diferite la')
a('fiecare furnizor**. Folosite ca atare, potrivesc marfuri complet nelegate — asa au aparut')
a('629 de potriviri false la importul officeshop.')
a('')
a('De aceea articolul slab primeste un prefix, ales in ordinea:')
a('')
a('1. **BRAND-ul randului** (din fisier) — `Trefl` + `2080` -> `TREFL-2080`')
a('2. **Prefixul sursei** (`ART_PREFIX`) — daca randul n-are brand -> `OS-2080`')
a('3. Daca nu exista niciunul, randul **nu se importa** (paza 5).')
a('')
a('Un articol e considerat slab daca are sub `ART_MIN_LEN` caractere (implicit 6) **sau**')
a('e format numai din cifre.')
a('')
a('## Sursele')
a('')
a('| Cod | Denumire | Tip | Prefix | Algoritm | Doar articol | Produse NOI |')
a('|---|---|---|---|---|---|---|')
for s in srcs:
    a('| `%s` | %s | %s | `%s` | %s | %s | %s |' % (
      s[0], s[2], s[3], s[6] or '—', s[5], 'da' if s[10] else 'nu', 'toate' if s[9] else 'doar cele noi'))
a('')
a('## Detalii per sursa')
a('')
for s in srcs:
    a('### %s — %s' % (s[0], s[2]))
    a('')
    a('- **Tip:** %s' % TIP.get(s[3], s[3]))
    if s[4]: a('- **Locatie:** %s' % s[4])
    a('- **Algoritm de incarcare:** `%s`' % s[5])
    a('- **Prefix de articol:** `%s` · articol slab sub %s caractere sau pur numeric' % (s[6] or '—', s[7]))
    if s[8]: a('- **Format:** %s' % s[8])
    a('- **Preturi doar dupa articol:** %s' % ('da' if s[10] else 'nu'))
    if s[1]: a('- **Cartela furnizorului:** `TMS_ORG.COD = %s`' % s[1])
    if s[11]:
        a('')
        a('**Particularitati / capcane:**')
        a('')
        a('> %s' % s[11])
    a('')
a('## Istoricul incarcarilor')
a('')
a('| Fisier | Foi | Randuri | Load | Prima incarcare |')
a('|---|---|---|---|---|')
for f in files:
    a('| `%s` | %s | %s | %s–%s | %s |' % (f[0], f[1], f[2], f[3], f[4], f[5]))
a('')
a('> ⚠️ Fisierele **birovits** si **officeshop** se numesc amindoua `all_products 2.xlsx`.')
a('> Numele fisierului NU identifica sursa — de aceea sursa se alege explicit la incarcare.')
a('')
a('## Tabelele')
a('')
a('```')
a('TMS_UNIVERS (TIP=\'O\')')
a('   └── TMS_ORG                (cartela organizatiei)')
a('            └── TMS_ORG_IMPSRC    (sursele de import)          1:N')
a('                     └── TMS_ORG_IMPFILE (fisierele pastrate)  1:N')
a('```')
a('')
a('`TMS_ORG_IMPFILE` pastreaza fisierul original ca BLOB, impreuna cu amprenta SHA-256')
a('(o reincarcare identica se recunoaste), legatura cu stagin-ul (`LOAD_ID`) si raportul')
a('importului. DDL: `TMS_ORG_IMPORT.tab.sql`.')
io.open('/Users/pt/Projects.AI/BIRO26/IMPORT_SURSE.md','w',encoding='utf-8').write("\n".join(L)+"\n")
print("MD scris:", len(L), "linii")

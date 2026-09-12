"""Собирает книгу-методичку в одну страницу из тех же md-файлов.

Генерация, а не переписывание: текст страницы физически не может
разойтись с текстом в репозитории.
"""
import html
import pathlib
import re

import markdown

DOCS = pathlib.Path("/Users/pt/Projects.AI/Artgranit-core/docs/SEOForge")
OUT = pathlib.Path(__file__).with_name("ghid.html")

CHAPTERS = [
    ("cap-0", "GHID_0_HARTA.md", "", "Harta cărții", "toți", "5 min"),
    ("cap-1", "GHID_1_DIRECTOR.md", "I", "Pentru director", "proprietar, director", "25 min"),
    ("cap-2", "GHID_2_EXECUTANT.md", "II", "Manualul executantului", "marketolog, operator", "40 min"),
    ("cap-3", "GHID_3_CONTINUT.md", "III", "Conținutul", "cine scrie și publică", "30 min"),
    ("cap-4", "GHID_4_MASURARE.md", "IV", "Măsurarea", "director, marketolog", "20 min"),
    ("cap-5", "GHID_5_PROBLEME.md", "V", "Când ceva nu merge", "toți", "la nevoie"),
]
ANCHOR = {f: cid for cid, f, *_ in CHAPTERS}

# Технические документы модуля: на странице их нет, ссылка вела бы в никуда.
TECH = {
    "README.md": "Modulul SEOForge",
    "STRATEGY_OFFICEPLUS.md": "Strategia OfficePlus",
    "WP_CATEGORY_POSTS.md": "Articole de catalog în WordPress",
    "SOCIAL_AUTOMATION.md": "Promovare în rețele fără buget",
    "CSV_FORMAT.md": "Formatul importului CSV",
    "DATA_MODEL.md": "Modelul de date",
}


def convert(md_text: str) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code",
                                                  "sane_lists", "attr_list"])
    # первый <h1> уходит — заголовок главы рисует обложка секции
    body = re.sub(r"<h1>.*?</h1>", "", body, count=1, flags=re.S)
    # заголовки главы съезжают на уровень вниз: <h2> уже занят названием
    # главы, иначе в оглавлении страницы два уровня спорят за один вес
    for a, b in (("h4", "h5"), ("h3", "h4"), ("h2", "h3")):
        body = body.replace(f"<{a}>", f"<{b}>").replace(f"</{a}>", f"</{b}>")

    def link(m):
        href, text = m.group(1), m.group(2)
        if href in ANCHOR:
            return f'<a href="#{ANCHOR[href]}">{text}</a>'
        if href in TECH:
            return (f'<span class="tech" title="документ модуля в репозитории">'
                    f'{text}<span class="tech-mark">doc</span></span>')
        return m.group(0)

    body = re.sub(r'<a href="([^"]+)">(.*?)</a>', link, body, flags=re.S)

    # «...» — это ровно то, что написано на кнопке в интерфейсе (он русский).
    # Показываем как элемент интерфейса, а не как цитату.
    def ui(m):
        return f'{m.group(1)}<span class="ui">{m.group(2)}</span>{m.group(3)}'
    body = re.sub(r"(>[^<]*?)«([^»<]{1,40})»([^<]*?<)", ui, body)
    body = re.sub(r"(>[^<]*?)„([^”<]{1,60})”([^<]*?<)", ui, body)

    body = body.replace("<table>", '<div class="tw"><table>')
    body = body.replace("</table>", "</table></div>")
    return body


def sections() -> str:
    out = []
    for cid, fname, num, title, who, mins in CHAPTERS:
        src = (DOCS / fname).read_text(encoding="utf-8")
        head = (f'<p class="eyebrow">{"Cartea " + num if num else "Introducere"}</p>'
                if num else '<p class="eyebrow">Introducere</p>')
        out.append(f"""
<section class="chapter" id="{cid}">
  <header class="ch-head">
    {head}
    <h2>{html.escape(title)}</h2>
    <p class="ch-meta"><span>{html.escape(who)}</span><span class="dot"></span><span>{mins}</span></p>
  </header>
  <div class="prose">{convert(src)}</div>
</section>""")
    return "\n".join(out)


def nav() -> str:
    items = []
    for cid, _f, num, title, who, mins in CHAPTERS:
        items.append(f"""<a class="nav-link" href="#{cid}">
      <span class="nav-num">{num or "•"}</span>
      <span class="nav-txt"><b>{html.escape(title)}</b><i>{html.escape(who)} · {mins}</i></span></a>""")
    return "\n".join(items)


OUT.write_text(
    pathlib.Path(__file__).with_name("shell.html").read_text(encoding="utf-8")
    .replace("<!--NAV-->", nav())
    .replace("<!--BODY-->", sections()),
    encoding="utf-8")
print("страница собрана:", OUT, OUT.stat().st_size // 1024, "КБ")

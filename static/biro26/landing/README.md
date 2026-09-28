# OfficePlus — автономный пакет (standalone)

**Требование:** сайт открывается **без Python, Node, Docker и серверов**.  
Все картинки **лежат внутри папки** (не symlinks). Подходит для:

1. **cPanel** — залить содержимое в `public_html` (или подпапку)
2. **Диск + браузер** — двойной клик по `index.html` (`file://`)
3. Любой static hosting (nginx, Apache, Netlify, S3…)

## Содержимое

```
officeplus-standalone/
  index.html
  styles.css
  assets/
    logo.png
    products-row.png
    about.png
    contact.png
    newsletter.png
    search-icon.png
  README.md
```

## Как открыть с диска

- macOS/Windows/Linux: открой `index.html` в Chrome/Firefox/Safari/Edge.
- Пути относительные — **не разноси** файлы по разным папкам.

## cPanel (минимум шагов)

1. Zip: заархивируй **содержимое** этой папки (или всю папку).
2. File Manager → `public_html` → Upload → Extract.
3. Если залил папкой `officeplus-standalone/`, сайт: `https://domain/officeplus-standalone/`
4. Если распаковал **внутрь** `public_html` (index.html в корне) → `https://domain/`

Не нужен: Python app, Passenger, Node selector, SSL от приложения (достаточно обычного SSL cPanel).

## Без сети

- HTML/CSS/PNG работают offline.
- Шрифт Inter грузится с Google Fonts (нужен интернет у посетителя). Без сети браузер возьмёт system-ui (уже в CSS fallback).

## Запрещено для этого пакета

- Не полагаться на `python -m http.server`
- Не оставлять symlinks на `OfficePlus-2`
- Не требовать сборки (`npm`, `build_site.py`)

# Материалы — только на nufarul.eminescu.md, officeplus.md целиком на паузе

*25.10.2026 · решение владельца: «все материалы ставим на nufarul eminescu, по адресу officeplus всё на паузе»*

## Что сделано

1. **Все ссылки в материалах переведены на nufarul.eminescu.md** — пакет «Проект-тип»
   (`docs/ProiectTip/*.md` и HTML), маркетинг (`docs/Marketing/*.md`), брошюра
   (`static/marketing/artgranit-prospect.html`), скрипт сборки (`HUB`).
   Магазин в ссылках — демо на nufarul:

   | Было (officeplus.md) | Стало (nufarul.eminescu.md/UNA.md/orasldev/biro26-site…) |
   |---|---|
   | `/` | `` (главная) |
   | `/catalog` | `/catalog` |
   | `/branduri` | `/brands` |
   | `/produs/<cod>` | `/product/<cod>` |
   | `/cos` | `/cart` |
   | `/cont` | `/account` |
   | `/livrare`, `/retur-produse`, `/contacte`, `/credite`, `/termeni-si-conditii`, `/politica-de-confidentialitate` | `/page/<тот же slug>` |
   | `/UNA.md/orasldev/…`, `/login` | тот же путь |

   Упоминания `officeplus.md` как названия боевого магазина в тексте оставлены.

2. **На officeplus.md материалы тоже закрыты паузой.** `modules/sitepause/rules.py`:
   `PAUSED_STATIC = ("/static/proiect-tip/", "/static/marketing/")` — на домене магазина
   при `SITE_PAUSE=1` эти адреса отдают страницу 503. На nufarul пауза не действует
   (`is_shop_host`), там они открыты. Тест: `tests/test_sitepause.py::test_public_materials_closed_on_paused_shop_host`.

## Адреса

- Пакет: https://nufarul.eminescu.md/static/proiect-tip/index.html
- Маркетинг: https://nufarul.eminescu.md/static/proiect-tip/01_MARKETING.html
- Покупателю: https://nufarul.eminescu.md/static/proiect-tip/04_INSTRUCTIUNI_CUMPARATOR.html
- Брошюра: https://nufarul.eminescu.md/static/marketing/artgranit-prospect.html
- Хаб (после входа): https://nufarul.eminescu.md/UNA.md/orasldev/b26docs/ProiectTip/00_INDEX.html · все разделы: https://nufarul.eminescu.md/UNA.md/orasldev/b26docs/
- Демо-магазин: https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site

## Проверка

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://nufarul.eminescu.md/static/proiect-tip/index.html   # 200
curl -s -o /dev/null -w '%{http_code}\n' https://officeplus.md/static/proiect-tip/index.html          # 503
```

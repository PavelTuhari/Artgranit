# TexFlow — intake of clothing from bags, catalogue, pricing and labels

[Русский](README.md) · [Română](README.ro.md) · **English**

A standalone web app built on **Python + Flask + SQLite**. It is made for fast
processing of clothing that arrives from Turkey and China in bags, where
everything is mixed together and the shipment comes with only a **rough**
packing list.

TexFlow takes goods through five steps:

1. receives them bag by bag, putting every model into a “colour × size” matrix (Zara-style);
2. reconciles the actual count against the packing list;
3. calculates landed cost including import costs;
4. sets prices from category markups;
5. prints labels on **Zebra (ZPL)**, **TSC (TSPL)** or as **PDF** —
   an A4 sheet for an office printer or a roll for a virtual printer.

The interface is in three languages: **Russian, Romanian, English**. The
RU / RO / EN switch is in the header. Colour, category and size-scale names
are translated, and the colour on the label can be printed in any of the
three languages.

No server or internet is needed: one database file `instance/texflow.db`,
run it from a laptop.

| Document | About |
|---|---|
| [docs/ARCHITECTURE.en.md](docs/ARCHITECTURE.en.md) | Mermaid diagrams: process, data (ER), pricing, printing |
| [docs/LABELS.en.md](docs/LABELS.en.md) | Zebra/TSC printers, PDF, Cyrillic, A4 sheet calibration |
| [docs/OPERATOR_GUIDE.en.md](docs/OPERATOR_GUIDE.en.md) | step-by-step guide for the operator / storekeeper |
| [samples/](samples/) | sample packing lists: Turkish and Chinese |

---

## 1. Install and run

Requires Python 3.10 or newer (tested on 3.13).

```bash
cd standalone/texflow
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py --demo               # opens http://127.0.0.1:5077/ with a demo shipment
```

| Option | What it does |
|---|---|
| `--host 0.0.0.0` | allow tablets and PCs on the local network, e.g. a scanner at a second workstation |
| `--port 5077` | port |
| `--db path.db` | another database file, e.g. a separate database per season |
| `--demo` | load the demo shipment `DEMO-TR-01`: 3 models, received pieces, prices |
| `--no-browser` | do not open the browser automatically |

Environment variables: `TEXFLOW_DB` — database path, `TEXFLOW_PDF_FONT` — your
own TTF font for PDF.

**Backup** — copy `instance/texflow.db`. While the app is running, this is
safer: `sqlite3 instance/texflow.db ".backup backup.db"`.

## 2. Tests

```bash
cd standalone/texflow
python -m pytest -q
```

63 tests, no Oracle wallet and no printer needed. They cover:

- rules: EAN-13, SKU, rounding, markup with VAT, cost allocation, reconciliation;
- labels: ZPL, TSPL, PDF;
- sending to a fake TCP “printer”;
- the full HTTP scenario;
- translations: every UI string has RO and EN, and the RO/EN pages contain no Cyrillic.

## 2b. HTML materials: documentation, test report, presentation

The HTML materials are in `docs/html/` and open offline, straight from the folder or in the app at
`http://127.0.0.1:5077/docs/`:

- `index.html` — all materials;
- `{ru,ro,en}/*.html` — documentation and screen galleries;
- `test_act.html` / `.pdf` — test report with screenshots;
- `presentation.html` / `.pdf` — slides.

Rebuild: `tools/run_all.sh`; archive identical to git: `tools/make_archive.sh`.

## 3. How to work (short)

Full guide — [docs/OPERATOR_GUIDE.en.md](docs/OPERATOR_GUIDE.en.md).

1. **Shipments → New shipment.** Number, supplier, country, currency and rate
   to the local currency. Costs in local currency: freight, customs fees,
   broker, other. Allocation method: by value, per piece or by bag weight.
2. **Packing list.** CSV `bag;category;description;qty;price;weight`. Headers
   can be in Russian, Romanian, English, Turkish or Chinese. UTF-8, cp1251,
   cp1254 and GB18030 are detected automatically. Bags are created
   automatically.
3. **Sorting a bag.** An item already in the system is scanned (EAN or SKU):
   +1 pc. A new model is created in the “New model” form: click the colours,
   then enter quantities into the size matrix. Enter — next cell,
   Ctrl+Enter — save. The purchase price is taken from the packing list by
   category.
4. **Reconciliation** on the shipment page, by category and by bag: “match”,
   “shortage”, “surplus”, “not in list”.
5. **Prices.** Landed cost → category markup → VAT → charm price (e.g. 189.90).
   You can type your own price or lock it on the product card.
6. **Labels** for the whole shipment, a bag, a model or one variant. The
   number of labels equals the pieces received.

## 4. Languages

| Where | How |
|---|---|
| Interface | the **RU / RO / EN** switch in the header; remembered in the browser. Default language — “Settings → Default interface language” |
| Reference data | colour, colour group, category and scale have `name` (RU), `name_ro`, `name_en`; empty translation → Russian name |
| Model | on the model card — name and composition in RO and EN (empty → the main one). Catalogue, sorting and pricing show the name in the interface language; search works in any language |
| Label | “Settings → Language of colour names on labels”: colour, model name and composition are printed in that language (“Black”, “Basic oversize T-shirt”) |
| Packing list | Romanian headers are understood too; a category can be given by its Romanian or English name |
| New UI string | in the template — `{{ _('Russian text') }}`, translation — in `texflow/i18n_catalog.py`; without it `test_every_ui_string_translated` fails |

## 5. Data model (SQLite, normalised)

| Table | Entity |
|---|---|
| `suppliers` | suppliers |
| `size_scales`, `sizes` | size scales: letters XXS–3XL, women EU 32–48, men 44–58, jeans W24–38, kids by height 86–164, shoes 35–46, ONE |
| `color_families`, `colors` | Zara-style colour groups (White, Black, Beige, Blue…) and colours with codes `001`, `800`, `401`… |
| `categories` | category → size scale, markup %, duty %, HS code |
| `shipments` | shipment: currency, rate, freight/customs/broker/other, allocation method, status |
| `bags` | bags of a shipment: number, weight, status (`closed` → `sorting` → `done`) |
| `packing_lines` | lines of the rough packing list |
| `products` | model: style no., name, category, composition, purchase price, retail price, lock |
| `variants` | “colour × size” variant: unique `sku` and `ean13` |
| `intake_items` | intake log: how many pieces of which variant from which bag; purchase; landed cost |
| `label_jobs` | print log |
| `settings` | settings: brand, VAT, rounding, label sizes, printers, languages |

Stock is not a separate column: it is `SUM(intake_items.qty)` per variant. A
miscount is fixed with a negative line or by deleting the log line.

**SKU** = `STYLE-COLOURCODE-SIZE`, e.g. `TSH0001-800-M`.
**EAN-13** — internal, prefix `200` (GS1 reserves 20–29 for in-store use)
with a correct check digit.

## 6. Formulas

```
purchase_loc  = purchase_fx × rate
duty          = purchase_loc × category_duty %
share         = (freight + customs + broker + other) × line_basis / Σ basis
                 basis: value | pieces | weight (bag weight × share of pieces in the bag)
landed        = purchase_loc + duty + share / qty
price_calc    = landed × (1 + max(category_markup, min_markup) %) × (1 + VAT %)
price         = ⌈(price_calc + ending) / step⌉ × step − ending      (step 10, ending 0.1 → 189.90)
```

## 7. Post-install checklist

1. `python -m pytest -q` — all tests pass.
2. `python run.py --demo` opens the home page; “Catalogue” shows 3 models with prices.
3. Switch to **EN** in the header — the whole interface is in English.
4. “Labels” → shipment `DEMO-TR-01` → “PDF A4” → “Open”: a 3×8 sheet with barcodes.
   A scanner must read the EAN from paper.
5. For Zebra/TSC: set the printer address in “Settings”, print one label
   (the “label” button next to a variant) and check that it scans.

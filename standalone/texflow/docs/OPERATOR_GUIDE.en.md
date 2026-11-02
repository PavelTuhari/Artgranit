# Intake operator guide

[Русский](OPERATOR_GUIDE.md) · [Română](OPERATOR_GUIDE.ro.md) · **English**

The goal is to sort a bag in minutes, not hours. Every item must be recorded
as a “model · colour · size” variant with a barcode and a price.

## Workstation setup

- A laptop or PC running TexFlow (`python run.py`). For several workstations:
  `python run.py --host 0.0.0.0`, and the others open
  `http://laptop-IP:5077`.
- A barcode scanner in keyboard mode with an Enter suffix. Most scanners use
  this mode by default.
- A Zebra or TSC thermal printer with a 58×40 mm roll, or an office printer
  with A4 sheets.
- A large table and boxes labelled by category: T-shirts, jeans, dresses…
- Interface language: the **RU / RO / EN** switch in the header.

## Step 1. Create the shipment

“Shipments” → “New shipment”.

| Field | Example | Why |
|---|---|---|
| Number | `TR-2026-11-01` | reference in documents |
| Supplier | `Istanbul Tekstil` | product cards |
| Country | Turkey / China | country of origin |
| Currency, rate | USD × 17.8 | converting purchase prices to local currency |
| Freight, Customs, Broker, Other | 4500, 1200, 800, 0 | in local currency, go into landed cost |
| Allocate costs | by value | expensive items carry more. “By weight” — if you paid per kg |
| Bags | 4 | create bags 1..4 right away (if there is no list) |

## Step 2. Upload the packing list

The supplier's list usually comes in Excel. Save it as CSV:
“File → Save as → CSV (semicolon-separated)”.

Required columns (any order, extra columns are ignored):

| Column | Header variants |
|---|---|
| bag | `bag_no`, `bag`, `sac`, `мешок`, `çuval`, `包` |
| category | `category`, `categorie`, `категория`, `kategori`, `类别` — code (`TSH`, `JNS`) or a reference name (Russian, Romanian or English) |
| description | `description`, `descriere`, `описание`, `açıklama`, `品名` |
| quantity (**required**) | `qty`, `cantitate`, `pcs`, `кол-во`, `adet`, `数量` |
| price per pc | `unit_price`, `price`, `preț`, `цена`, `fiyat`, `单价` |
| weight, kg | `weight_kg`, `weight`, `greutate`, `вес`, `ağırlık`, `重量` |

The list is called rough: “T-shirts — 120 pcs” with no colours or sizes.
That is enough. Colours and sizes appear during sorting, and the quantities
are checked in step 4.

If a category is not recognised, you get a warning. Add such a category in
“Reference data” and upload the list again.

## Step 3. Sort the bag

Shipment page → “Sort” next to the bag.

**The item already exists** (e.g. a second batch of the same model): scan its
label or barcode — +1 pc is added. The result appears under the scanner field:
✓ — received, ✗ — no such code.

**New model:**

1. Lay the bag's contents out on the table by model. Within a model — by
   colour, within a colour — by size. This is the key technique: lay out
   first, then enter quantities, instead of entering items one by one.
2. Fill in “New model”: the name (as it will appear on the label), the
   category (it determines the size scale and the markup) and, if known, the
   composition. The style number is generated (`TSH0007`). The purchase price
   is taken from the packing list by category and can be corrected.
3. The matrix opens. Click the colours you need — each becomes a row. Colours
   are grouped as on the Zara website: White (white, off-white, ecru), Beige
   (beige, sand, camel), Blue (blue, navy, denim)…
4. Enter quantities into the “colour × size” cells. **Enter** moves to the
   next cell, arrows move the cursor. Row and column totals update instantly.
5. **Ctrl+Enter** or “Save”. The “Save and print labels” button opens printing
   for exactly this batch.

**Mistake:** in the intake log press × on the line, or enter a negative number
(−2) in the matrix.

When the bag is empty — “Bag done”.

## Step 4. Reconcile with the list

Shipment page, blocks “Reconciliation by category” and “Reconciliation by bag”:

- **match** — all good;
- **shortage** (red) — less arrived than listed: grounds for a claim to the
  supplier;
- **surplus** — more arrived;
- **not in list** — the category was not declared.

The list is rough, so a 2–5 % difference is usually normal.

## Step 5. Prices

“Prices” on the shipment. For every model you see:

- the purchase price in currency;
- the landed cost in local currency, with duty and a share of freight,
  customs and broker;
- the category markup;
- the proposed price (already rounded: 189.90, 249.90…);
- the actual markup after rounding.

You can type your own price in “Own price”. Then “Write prices to product
cards”.

If a model's price must not change (promotion, negotiated price), lock it on
the model card with “Lock price”. Recalculation does not touch a locked price.

Category markups are changed in “Reference data”. Rounding (step, .90/.99
ending) and VAT — in “Settings”.

## Step 6. Labels

- **For the whole shipment or a bag** — from the shipment page. As many labels
  as pieces received.
- **For a model** — from the model card.
- **A single label** — the “label” button next to a variant (e.g. to replace a
  damaged one).

Before printing you can adjust the number of copies on each line.

Choosing a format:

- **ZPL** — for Zebra;
- **TSPL** — for TSC;
- **PDF A4** — for sheets of self-adhesive labels. Print at 100% scale.
  “Start at cell” lets you finish a partly used sheet;
- **PDF roll** — for printing through a driver or to a virtual printer.

Buttons: “Open / download”, “Download file”, “Print to printer” (to the
address from settings).

The colour language on the label (Black / Negru / Чёрный) is chosen in
“Settings”. Printer details — [LABELS.en.md](LABELS.en.md).

## Step 7. Catalogue

“Catalogue” — model cards with colours, price and stock. Inside a card:

- colours with codes and groups;
- the size grid (struck through — out of stock);
- the SKU and EAN table;
- a print-card button.

**Export CSV** — the full list of variants (style no., colour, size, SKU, EAN,
price, stock) for uploading to an online shop or POS. Colour and category
names are in the current interface language.

## Sorting screen shortcuts

| Key | Action |
|---|---|
| Enter in the scanner field | accept the scanned code |
| Enter in the matrix | next cell |
| ← → ↑ ↓ | move around the matrix |
| Ctrl+Enter | save the matrix |

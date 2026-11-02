# Labels: Zebra (ZPL), TSC (TSPL), PDF A4 and PDF roll

[Русский](LABELS.md) · [Română](LABELS.ro.md) · **English**

There is one label record (`LabelData`) and four outputs from it. The content
is the same everywhere:

```
┌──────────────────────────────────────┐
│ MY STORE                             │  brand (Settings → Brand)
│ Oversize T-shirt                     │  model name
│ Black   TSH0001-800-S                │  colour + SKU
│ ┌───┐                                │
│ │ S │                     179.90 MDL │  size in a box, price
│ └───┘                                │
│        ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌          │  EAN-13
│        2 000000 000015               │
│ 100% cotton                          │  composition
└──────────────────────────────────────┘
```

The language of the colour name (Black / Negru / Чёрный) is chosen in
“Settings → Language of colour names on labels”. The model name and
composition are printed in the same language when the card has a translation
(otherwise the main one is used).

## Which format to choose

| Format | Printer | How to print | When |
|---|---|---|---|
| **ZPL** | Zebra GK420t/d, ZD220, ZD230, ZD421, ZT230/ZT410, and printers with ZPL emulation (Godex, Xprinter, TSC in ZPL mode) | `tcp://IP:9100`, `cups://QUEUE` or download `.zpl` | main flow, fastest |
| **TSPL** | TSC TE200/TE210/TE300, TTP-244 Pro, DA200/DA210, Alpha-3R; many low-cost Chinese printers (Xprinter XP-360B and similar) | same | if the printer does not speak ZPL |
| **PDF A4** | any laser or inkjet printer | open the PDF → print at **100%** scale (“Actual size”) | no thermal printer, but sheets of self-adhesive labels |
| **PDF roll** | any printer with a driver, including Zebra/TSC via the Windows driver (Seagull), and the virtual “Microsoft Print to PDF” | one page = one label, page size equals label size | printing via a driver, archiving, sending by e-mail |

## Printer address

Set it in “Settings” (`printer_zpl`, `printer_tspl`) or directly in the
“Printer” field on the labels page.

| Address | What happens |
|---|---|
| `tcp://192.168.1.50:9100` | raw bytes go to port 9100 (RAW / JetDirect). This is how Zebra and TSC printers with Ethernet or Wi-Fi work |
| `cups://Zebra_ZD220` | `lp -d Zebra_ZD220 -o raw` — for a USB printer on Linux or macOS |
| `dir:///home/shop/spool` | the job file is saved to a folder for another script or driver to pick up |

### USB printer on Linux/macOS (CUPS)

```bash
lpinfo -v | grep -i usb                       # find the printer URI
sudo lpadmin -p Zebra_ZD220 -E -v "usb://Zebra%20Technologies/ZTC%20ZD220-203dpi%20ZPL" -m raw
# in TexFlow: cups://Zebra_ZD220
```

### USB printer on Windows

There are two ways:

1. **PDF roll** through the installed driver: in the driver settings set the
   paper size to 58×40 mm, and print at 100% scale.
2. **Raw ZPL/TSPL.** Share the printer (e.g. as `ZEBRA`), download `.zpl` and
   run `copy /b labels.zpl \\localhost\ZEBRA`.

If the printer has a network port, `tcp://IP:9100` is the simplest.

## Size and resolution

Configured in “Settings”:

| Parameter | Default | Comment |
|---|---|---|
| Width × height | 58 × 40 mm | common sizes: 58×40, 58×30, 40×30, 50×30, 43×25 |
| Gap | 2 mm | for TSPL (`GAP`) |
| DPI | 203 | 203 / 300 / 600. For ZPL the barcode module is 2 dots at 203 dpi and 3 dots at 300 dpi |

## Cyrillic and diacritics on a thermal printer

The built-in Zebra (`^A0`) and TSC (`"1"`…`"8"`) fonts **have no Cyrillic**.
So by default text on a ZPL/TSPL label is transliterated: “Футболка” →
“Futbolka”, and “ș ț ă î â” → “s t a i a”. Digits, price, SKU and barcode are
unchanged.

For the original text:

1. Download a TTF font to the printer: Zebra Setup Utilities → Download Fonts,
   for TSC — Diagnostic Tool → Font.
2. In “Settings” enter the font name on the printer:
   - ZPL: `E:ARIAL.TTF` (uses `^A@N,h,w,E:ARIAL.TTF`; UTF-8 is already on via `^CI28`);
   - TSPL: `ARIAL.TTF` (uses `CODEPAGE UTF-8` and `TEXT x,y,"ARIAL.TTF",...`).

For labels without Cyrillic, set the colour language to **English** or
**Română** and write model names in Latin letters.

In PDF, Cyrillic and diacritics always print: the system font DejaVu,
Liberation or Arial is used. Set your own font with the `TEXFLOW_PDF_FONT`
variable.

## A4 sheet calibration

Default sheet 3×8 = 24 labels of 70×37 mm. Other formats:

| Sheet | Columns × rows | Label, mm | Top margin, mm |
|---|---|---|---|
| 24 pcs | 3 × 8 | 70 × 37 | 0.5 |
| 21 pcs | 3 × 7 | 70 × 42.3 | 0.5 |
| 40 pcs | 4 × 10 | 52.5 × 29.7 | 0 |
| 14 pcs | 2 × 7 | 105 × 42.3 | 0.5 |
| 65 pcs | 5 × 13 | 38.1 × 21.2 | 10.7 (and left 4.7) |

Calibration steps:

1. Print on plain paper with a border (Settings → “Border”).
2. Lay it over a label sheet against the light.
3. Fix any offset with the margins.

The **“Start at cell”** field lets you finish a partly used sheet: e.g. `5`
skips the first five used labels.

## Checking without a printer

- **ZPL**: the labels page shows the ZPL of the first label. Paste it into
  https://labelary.com/viewer.html (8 dpmm = 203 dpi, 2.28×1.57 in = 58×40 mm).
- **TSPL**: download `.tspl` and open it in TSC Console / Diagnostic Tool, or
  send it to the printer: `nc 192.168.1.50 9100 < labels.tspl`.
- **PDF**: open it in a browser and scan the barcode from the screen with a
  phone.

The copy count is a single command: `^PQn` in ZPL and `PRINT 1,n` in TSPL. So
18 identical labels are one job, not 18. Full ZPL and TSPL examples are in
[LABELS.md](LABELS.md).

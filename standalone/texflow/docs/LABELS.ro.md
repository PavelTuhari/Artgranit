# Etichete: Zebra (ZPL), TSC (TSPL), PDF A4 și PDF rolă

[Русский](LABELS.md) · **Română** · [English](LABELS.en.md)

Există o singură înregistrare de etichetă (`LabelData`) și patru ieșiri din
ea. Conținutul este același peste tot:

```
┌──────────────────────────────────────┐
│ MY STORE                             │  brand (Setări → Brand)
│ Tricou oversize                      │  denumirea modelului
│ Negru   TSH0001-800-S                │  culoare + SKU
│ ┌───┐                                │
│ │ S │                     179.90 MDL │  mărimea în chenar, prețul
│ └───┘                                │
│        ▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌▌          │  EAN-13
│        2 000000 000015               │
│ 100% bumbac                          │  compoziție
└──────────────────────────────────────┘
```

Limba denumirii culorii (Negru / Чёрный / Black) se alege în
„Setări → Limba denumirilor culorilor pe etichetă”.
În aceeași limbă se tipăresc denumirea modelului și compoziția, dacă în fișă
există traducerea lor (altfel — cea principală).

## Ce format să alegeți

| Format | Imprimantă | Cum se tipărește | Când |
|---|---|---|---|
| **ZPL** | Zebra GK420t/d, ZD220, ZD230, ZD421, ZT230/ZT410, precum și imprimante cu emulare ZPL (Godex, Xprinter, TSC în regim ZPL) | `tcp://IP:9100`, `cups://COADĂ` sau descărcare `.zpl` | fluxul principal, cel mai rapid |
| **TSPL** | TSC TE200/TE210/TE300, TTP-244 Pro, DA200/DA210, Alpha-3R; multe imprimante chinezești ieftine (Xprinter XP-360B etc.) | la fel | dacă imprimanta nu înțelege ZPL |
| **PDF A4** | orice imprimantă laser sau cu jet | deschideți PDF-ul → tipărire la scara **100%** („Dimensiune reală”) | nu aveți imprimantă termică, aveți coli de etichete autoadezive |
| **PDF rolă** | orice imprimantă cu driver, inclusiv Zebra/TSC prin driverul Windows (Seagull), precum și „Microsoft Print to PDF” | o pagină = o etichetă, dimensiunea paginii egală cu a etichetei | tipărire prin driver, arhivă, trimitere prin e-mail |

## Adresa imprimantei

Se setează în „Setări” (`printer_zpl`, `printer_tspl`) sau direct în câmpul
„Imprimantă” de pe pagina etichetelor.

| Adresă | Ce se întâmplă |
|---|---|
| `tcp://192.168.1.50:9100` | octeții bruți merg pe portul 9100 (RAW / JetDirect). Așa funcționează Zebra și TSC cu Ethernet sau Wi-Fi |
| `cups://Zebra_ZD220` | `lp -d Zebra_ZD220 -o raw` — pentru imprimantă USB pe Linux sau macOS |
| `dir:///home/shop/spool` | fișierul lucrării se salvează într-un dosar, de unde îl preia alt script sau driver |

### Imprimantă USB pe Linux/macOS (CUPS)

```bash
lpinfo -v | grep -i usb                       # găsiți URI-ul imprimantei
sudo lpadmin -p Zebra_ZD220 -E -v "usb://Zebra%20Technologies/ZTC%20ZD220-203dpi%20ZPL" -m raw
# în TexFlow: cups://Zebra_ZD220
```

### Imprimantă USB pe Windows

Există două căi:

1. **PDF rolă** prin driverul instalat: în setările driverului dimensiunea
   hârtiei 58×40 mm, la tipărire scara 100%.
2. **ZPL/TSPL brut.** Partajați imprimanta (de exemplu, numele `ZEBRA`),
   descărcați `.zpl` și executați `copy /b labels.zpl \\localhost\ZEBRA`.

Dacă imprimanta are port de rețea, cel mai simplu este `tcp://IP:9100`.

## Dimensiuni și rezoluție

Se configurează în „Setări”:

| Parametru | Implicit | Comentariu |
|---|---|---|
| Lățime × înălțime | 58 × 40 mm | dimensiuni populare: 58×40, 58×30, 40×30, 50×30, 43×25 |
| Spațiu | 2 mm | pentru TSPL (`GAP`) |
| DPI | 203 | 203 / 300 / 600. Pentru ZPL modulul codului de bare este de 2 puncte la 203 dpi și 3 puncte la 300 dpi |

## Chirilica și diacriticele pe imprimanta termică

Fonturile încorporate Zebra (`^A0`) și TSC (`"1"`…`"8"`) **nu conțin
chirilică**. De aceea, implicit, textul pe eticheta ZPL/TSPL se
transliterează: „Футболка” → „Futbolka”, iar „ș ț ă î â” → „s t a i a”.
Cifrele, prețul, SKU și codul de bare nu se schimbă.

Pentru textul original:

1. Încărcați un font TTF în imprimantă: Zebra Setup Utilities → Download Fonts,
   la TSC — Diagnostic Tool → Font.
2. În „Setări” indicați numele fontului de pe imprimantă:
   - ZPL: `E:ARIAL.TTF` (se folosește `^A@N,h,w,E:ARIAL.TTF`; UTF-8 este deja activat prin `^CI28`);
   - TSPL: `ARIAL.TTF` (se folosesc `CODEPAGE UTF-8` și `TEXT x,y,"ARIAL.TTF",...`).

Pentru etichete fără chirilică puneți limba culorii **Română** sau **English**,
iar denumirile modelelor scrieți-le cu litere latine.

În PDF chirilica și diacriticele se tipăresc întotdeauna: se folosește fontul
de sistem DejaVu, Liberation sau Arial. Un font propriu se indică prin
variabila `TEXFLOW_PDF_FONT`.

## Coala A4 — calibrare

Implicit coala 3×8 = 24 de etichete 70×37 mm. Alte formate:

| Coală | Coloane × rânduri | Etichetă, mm | Margine sus, mm |
|---|---|---|---|
| 24 buc | 3 × 8 | 70 × 37 | 0.5 |
| 21 buc | 3 × 7 | 70 × 42.3 | 0.5 |
| 40 buc | 4 × 10 | 52.5 × 29.7 | 0 |
| 14 buc | 2 × 7 | 105 × 42.3 | 0.5 |
| 65 buc | 5 × 13 | 38.1 × 21.2 | 10.7 (și stânga 4.7) |

Ordinea calibrării:

1. Tipăriți pe hârtie simplă cu chenar (Setări → „Chenar”).
2. Puneți coala peste coala de etichete, în contra luminii.
3. Corectați deplasarea cu marginile.

Câmpul **„Începe de la celula”** permite completarea unei coli începute: de
exemplu, `5` sare peste primele cinci etichete ocupate.

## Verificare fără imprimantă

- **ZPL**: pagina etichetelor afișează ZPL-ul primei etichete. Îl puteți lipi
  în https://labelary.com/viewer.html (8 dpmm = 203 dpi, 2.28×1.57 inch = 58×40 mm).
- **TSPL**: descărcați `.tspl` și deschideți-l în TSC Console / Diagnostic Tool,
  sau trimiteți-l la imprimantă: `nc 192.168.1.50 9100 < labels.tspl`.
- **PDF**: deschideți-l în browser și scanați codul de bare de pe ecran cu
  telefonul.

Numărul de copii se dă printr-o singură comandă: `^PQn` în ZPL și
`PRINT 1,n` în TSPL. Astfel, 18 etichete identice sunt o singură lucrare, nu 18.
Exemple complete de ZPL și TSPL — în [LABELS.md](LABELS.md).

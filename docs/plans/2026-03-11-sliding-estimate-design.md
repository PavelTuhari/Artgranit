# DECOR Sliding Estimate Module - Design Document

**Date:** 2026-03-11
**Status:** Approved
**Scope:** Add HUUN Sliding glass partition estimate type to the DECOR module

---

## 1. Overview

Add a full configurator for HUUN Sliding aluminum glass partition systems alongside the existing Veranda estimate. The system supports three families (3-Rail, 5-Rail, Thermal) with variant-specific profile cutting formulas, configurable glass/assembly/installation options, and two output levels: quick estimate for quoting and production cutting list on demand.

## 2. System Variants

### 2.1 Three System Families

| Family | Variants | Width (mm) | Height (mm) | Max m² |
|--------|----------|-----------|------------|--------|
| 3-Rail Single Glass | 2, 3, 2+2, 3+3 panels | 1500–3750 | 1000–3000 | 11 |
| 5-Rail Single Glass | 2, 3, 4, 5, 2+2, 3+3, 4+4, 5+5 panels | 2500–6000 | 1000–3000 | 18 |
| Thermal Sliding | 2, 3, 4, 2+2, 3+3, 4+4 panels | 2000–5000 | 1000–3000 | 15 |

### 2.2 Per-Variant Calculation

Each variant defines:
- **Profile cut lengths** — piece count × length per profile code, derived from width/height with variant-specific offset constants
- **Panel dimensions** — glass panel width = (system_width - frame_offsets) / panel_count
- **Accessory quantities** — from panel count lookup table (e.g. 3 panels → 3 slide tracks, 4 brush/seal units)
- **Glass area** — per-panel width × height, summed across all panels

### 2.3 Two Calculation Modes

1. **Quick estimate** — area/perimeter × rate-based pricing for quoting
2. **Production cutting list** — exact piece-by-piece profile lengths (generated on demand after order confirmation)

## 3. Sliding Materials Catalog (Seeded from XLS)

### 3.1 Profiles (per meter, prices in MDL)

| Code | Name | Price/m | Weight g/m |
|------|------|--------:|----------:|
| M6332 | Profil 3 canale (superior) | 365 | 1552 |
| M6333 | Profil prag plat 3 canale | 280 | 1064 |
| 11574 | Profil superior fixare sticlă 10mm | 60 | 215 |
| 11579 | Profil inferior fixare sticlă 10mm | 230 | 1056 |
| M6334 | Profil vertical perete 3 canale | 350 | 1530 |
| M6305 | Profil vertical fixare sticlă | 210 | 929 |
| 11646 | Profil conexiune sticlă 10mm | 70 | 292 |
| M6313 | Profil mare col sliding | — | 1404 |
| M6544 | Profil colț fără stâlp | — | 944 |
| M6377 | Capac profil colț | — | 127 |
| Inox adapter | Adaptor inox prag | 113 | — |

### 3.2 Accessories (per piece/set, prices in MDL)

| Code | Name | Unit | Price |
|------|------|------|------:|
| 6778 | Mecanism sliding (1 lăcată, 180°) | set | 210 |
| 10038 | Mâner sliding fără cheie | buc | 155 |
| 10037 | Mâner sliding cu cheie | buc | 300 |
| 6777 | EPDM cauciuc | m | 8 |
| 6775 | Perie 48×480 panorama | m | 7 |
| 6776 | Perie 550 | m | 8 |
| 8983 | Conector plastic terminație | buc | 40 |
| 7953 | Accesorii rotile+plastic 3 canale | set | 2800 |
| EM07300010 | Centrare sliding | buc | — |
| EM07300011 | Roată sliding dublă | buc | — |
| EM06100145 | Capac plastic stâlp inferior | buc | — |
| EM06100151 | Plastic intermediar inferior TEKCAM | buc | — |
| EM06100152 | Plastic intermediar superior TEKCAM | buc | — |
| EM06100141 | Mâner superior TEKCAM negru | buc | — |
| EM06100140 | Mâner inferior TEKCAM negru | buc | — |
| EM06100142 | Scurgere apă 3 canale | buc | — |
| EM07100095 | Placă colț sudată 3 canale | buc | — |
| EM09100003 | Fix All High Tack 290ml | buc | — |
| EM06100331 | Capac lateral prag | set | — |

### 3.3 Services

| Name | Unit | Price (MDL) |
|------|------|------------:|
| Vopsire RAL | m² | 200 |
| Asamblare | per basis | 200 |
| Montaj | per basis | configurable |

## 4. Configurable Options

### 4.1 Glass (Sticlă inclusă)

Checkbox toggle. When enabled, sub-selectors:
- **System type:** TEKCAM / ISICAM
- **Finish:** Transparentă / Tonată / Mată
- **Thickness:** 8mm / 10mm

Price = glass_area_m2 × rate from 12-cell matrix:
```
glass_rate_matrix[system_type][finish][thickness]
```

### 4.2 Assembly (Asamblare inclusă)

Checkbox toggle. When enabled:
- **Metraj basis** (admin-configurable): Perimeter | Width | Different | Area
- Price = calculated_metraj × assembly_rate_per_unit

### 4.3 Installation (Montaj inclus)

Checkbox toggle. When enabled:
- **Metraj basis** (admin-configurable): Perimeter | Width | Different | Area
- Price = calculated_metraj × installation_rate_per_unit

### 4.4 Metraj Basis Options

| Option | Formula |
|--------|---------|
| Perimeter | 2 × width_m + 2 × height_m |
| Width | width_m (rail length) |
| Different | separate basis for assembly vs montaj |
| Area | width_m × height_m |

## 5. UI Changes

### 5.1 Operator Page (decor_operator.html)

Unified form with product type selector at top:
```
Tip produs: [ Verandă ▼ ] / [ Sliding ▼ ]
```

Sliding-specific fields (shown when Sliding selected):
- System family: 3-Rail / 5-Rail / Thermal
- Panel layout: variant dropdown (filtered by family)
- Width (mm), Height (mm) — with min/max validation per variant
- Orientation: Stânga / Dreapta
- Prag suplimentar: Da / Nu
- Glass options block (type, finish, thickness)
- Asamblare inclusă checkbox
- Montaj inclus checkbox
- Color selector

### 5.2 Admin Page (decor_admin.html)

New "Sliding" tab containing:
- Sliding materials catalog table (code, name, unit, price — editable)
- Sliding settings panel:
  - Glass rate matrix (12 cells)
  - Assembly rate + basis selector
  - Installation rate + basis selector
  - Painting rate per m²
  - Markup %, Waste %
- Variant dimension limits (editable)

## 6. JSON Store Extension

New top-level keys in `data/decor_store.json`:

```json
{
  "sliding_materials": [
    {"id": 1, "code": "M6332", "name": "Profil 3 canale (superior)", "category": "profile", "unit": "m", "unit_price": 365, "currency": "MDL", "weight_g_per_m": 1552, "active": "Y"}
  ],
  "sliding_settings": {
    "currency": "MDL",
    "glass_rate_matrix": {
      "TEKCAM": {"transparent_8mm": 0, "transparent_10mm": 0, "tinted_8mm": 0, "tinted_10mm": 0, "matte_8mm": 0, "matte_10mm": 0},
      "ISICAM": {"transparent_8mm": 0, "transparent_10mm": 0, "tinted_8mm": 0, "tinted_10mm": 0, "matte_8mm": 0, "matte_10mm": 0}
    },
    "assembly_rate": 200,
    "assembly_basis": "perimeter",
    "installation_rate": 200,
    "installation_basis": "perimeter",
    "painting_rate_m2": 200,
    "markup_percent": 18.0,
    "waste_percent": 7.0,
    "exchange_rate_mdl_to_usd": 0.056
  },
  "sliding_variants": {
    "3rail_2panel": {
      "family": "3rail",
      "panels": "2",
      "label": "3 Rail / 2 Panel",
      "width_min_mm": 1500, "width_max_mm": 3750,
      "height_min_mm": 1000, "height_max_mm": 3000,
      "max_area_m2": 11,
      "profiles": {
        "M6332": {"desc": "Top rail", "pieces_expr": "1", "length_expr": "W - 110"},
        "M6333": {"desc": "Bottom rail", "pieces_expr": "1", "length_expr": "W - 142"},
        "M6334": {"desc": "Side posts", "pieces_expr": "2", "length_expr": "H - 19"},
        "11574": {"desc": "Glass top holder", "pieces_expr": "panels", "length_expr": "(W - offsets) / panels - 90.4"},
        "11579": {"desc": "Glass bottom holder", "pieces_expr": "panels", "length_expr": "(W - offsets) / panels - 90.4"},
        "M6305": {"desc": "Glass side frame", "pieces_expr": "panels * 2", "length_expr": "H - 137"},
        "11646": {"desc": "Glass connector", "pieces_expr": "panels * 2", "length_expr": "H - 139"}
      },
      "accessories": {
        "EM07300010": {"qty_expr": "panels * 2"},
        "EM07300011": {"qty_expr": "panels * 2"},
        "7953": {"qty_expr": "1"},
        "EM06100151": {"qty_expr": "panels + 1"},
        "EM06100152": {"qty_expr": "panels + 1"}
      }
    }
  },
  "next_sliding_material_id": 100
}
```

## 7. Backend Methods (DecorLocalStore)

New methods:

| Method | Purpose |
|--------|---------|
| `calculate_sliding_quote(payload)` | Main estimator — quick estimate |
| `calculate_sliding_cutting_list(payload)` | Production cutting list (on demand) |
| `get_sliding_materials()` | List sliding materials catalog |
| `update_sliding_material(id, data)` | Edit material price/status |
| `get_sliding_settings()` | Get sliding config |
| `update_sliding_settings(payload)` | Update sliding config |
| `seed_sliding_materials()` | Initial import from XLS data |

Reuses existing: `create_order()`, `get_orders()`, order status workflow.
The `create_order()` method gains a `product_type` field to distinguish Veranda vs Sliding orders.

## 8. API Endpoints

New routes in app.py:

| Method | Path | Handler |
|--------|------|---------|
| GET | `/api/decor-admin/sliding-materials` | List sliding materials |
| POST | `/api/decor-admin/sliding-materials` | Update sliding material |
| GET | `/api/decor-admin/sliding-settings` | Get sliding settings |
| POST | `/api/decor-admin/sliding-settings` | Update sliding settings |
| POST | `/api/decor-operator/calculate-sliding` | Calculate sliding estimate |
| POST | `/api/decor-operator/sliding-cutting-list` | Generate cutting list |

## 9. Variant Formula Reference

### 3-Rail / 3 Panel (from xlsx "3 RAIL (3 PANEL) - POZ X")

```
M6332 (top rail):      1 pc × (W - 110mm)
M6333 (bottom rail):   1 pc × (W - 142mm)
M6334 (side posts):    2 pc × (H - 19mm)
11574 (glass top A):   1 pc × panel_A_width - 90.4mm
      (glass top B):   1 pc × panel_B_width - 58.5mm
      (glass top D):   1 pc × panel_A_width - 90.4mm
11579 (glass btm):     same pattern as 11574
M6305 (glass side):    2 pc × (H - 137mm)
11646 (glass conn):    4 pc × (H - 139mm)
M7524 (threshold):     1 pc × 15mm (if threshold = VAR)

Panel widths:
  panel_A = (W - 55) / 3 * factor_A
  panel_B = (W - 55) / 3 * factor_B
```

### 3-Rail / 2 Panel (from xlsx "3 RAIL (2 PANEL) - POZ X")

Similar structure with 2-panel offsets:
```
M6332: 1 pc × (W - 110mm)
M6333: 1 pc × (W - 142mm)
...
12039 (fixed profile): 1 pc × 68mm
12061 (fixed gasket):  1 pc × 4mm
```

### 3-Rail / 3+3 Panel (double opening)

Double-sided calculation with center post (M6313):
```
M6313 (center post):  1 pc × (H - 122mm)
```
Each side calculated as mirror of 3-panel.

### 3-Rail / 2+2 Panel (double with fix)

Double-sided with fixed panels + center post:
```
M6313: 1 pc × (H - 122mm)
12061: 1 pc × fixed_panel_width
12069: 1 pc × 72mm (fix glass gasket)
```

### 5-Rail and Thermal variants

Derived from PDF profile catalogs and dimensional constraints. Use same formula structure with family-specific profile codes and offset constants.

# Sliding Estimate Module - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add HUUN Sliding glass partition estimate type to the DECOR module with full configurator, variant-specific cutting formulas, configurable glass/assembly/installation options, and production cutting list.

**Architecture:** Extend `DecorLocalStore` with sliding-specific methods (`calculate_sliding_quote`, `calculate_sliding_cutting_list`, material/settings CRUD). Add API routes in `app.py`. Extend existing operator/admin HTML templates with product type selector and sliding-specific form sections. All data stored in the existing `data/decor_store.json`.

**Tech Stack:** Python 3.9 / Flask / JSON store / Vanilla JS / HTML templates

**Design doc:** `docs/plans/2026-03-11-sliding-estimate-design.md`

---

## Task 1: Seed Sliding Materials into JSON Store

**Files:**
- Create: `scripts/seed_sliding_materials.py`
- Modify: `data/decor_store.json` (via script execution)

**Step 1: Create the seed script**

```python
#!/usr/bin/env python3
"""Seed sliding materials and settings into decor_store.json."""
import json
from pathlib import Path

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "decor_store.json"

SLIDING_MATERIALS = [
    # Profiles (per meter, prices in MDL)
    {"id": 1, "code": "M6332", "name": "Profil 3 canale (superior)", "name_ro": "Profil superior 3 canale", "category": "profile", "unit": "m", "unit_price": 365, "currency": "MDL", "weight_g_per_m": 1552, "family": "3rail", "active": "Y"},
    {"id": 2, "code": "M6333", "name": "Profil prag plat 3 canale", "name_ro": "Profil prag plat 3 canale", "category": "profile", "unit": "m", "unit_price": 280, "currency": "MDL", "weight_g_per_m": 1064, "family": "3rail", "active": "Y"},
    {"id": 3, "code": "11574", "name": "Profil superior fixare sticlă 10mm", "name_ro": "Profil superior fixare sticlă 10mm", "category": "profile", "unit": "m", "unit_price": 60, "currency": "MDL", "weight_g_per_m": 215, "family": "common", "active": "Y"},
    {"id": 4, "code": "11579", "name": "Profil inferior fixare sticlă 10mm", "name_ro": "Profil inferior fixare sticlă 10mm", "category": "profile", "unit": "m", "unit_price": 230, "currency": "MDL", "weight_g_per_m": 1056, "family": "common", "active": "Y"},
    {"id": 5, "code": "M6334", "name": "Profil vertical perete (sistem 3 canale)", "name_ro": "Profil vertical perete 3 canale", "category": "profile", "unit": "m", "unit_price": 350, "currency": "MDL", "weight_g_per_m": 1530, "family": "3rail", "active": "Y"},
    {"id": 6, "code": "M6305", "name": "Profil vertical fixare sticlă (aluminiu)", "name_ro": "Profil vertical fixare sticlă", "category": "profile", "unit": "m", "unit_price": 210, "currency": "MDL", "weight_g_per_m": 929, "family": "common", "active": "Y"},
    {"id": 7, "code": "11646", "name": "Profil conexiune sticlă 10mm", "name_ro": "Profil conexiune sticlă 10mm", "category": "profile", "unit": "m", "unit_price": 70, "currency": "MDL", "weight_g_per_m": 292, "family": "common", "active": "Y"},
    {"id": 8, "code": "M6313", "name": "Profil mare col sliding", "name_ro": "Profil mare col sliding", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 1404, "family": "3rail", "active": "Y"},
    {"id": 9, "code": "M6544", "name": "Profil colț fără stâlp", "name_ro": "Profil colț fără stâlp", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 944, "family": "common", "active": "Y"},
    {"id": 10, "code": "M6377", "name": "Capac profil colț", "name_ro": "Capac profil colț", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 127, "family": "common", "active": "Y"},
    {"id": 11, "code": "INOX-ADAPT", "name": "Adaptor inox pentru prag", "name_ro": "Adaptor inox prag", "category": "profile", "unit": "m", "unit_price": 113, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 12, "code": "M7524", "name": "Profil prag suplimentar", "name_ro": "Profil prag suplimentar", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 13, "code": "12039", "name": "Profil fix sliding", "name_ro": "Profil fix sliding", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 431, "family": "common", "active": "Y"},
    {"id": 14, "code": "12061", "name": "Profil garnitură fix", "name_ro": "Profil garnitură fix", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 175, "family": "common", "active": "Y"},
    {"id": 15, "code": "12069", "name": "Profil fix sticlă garnitură", "name_ro": "Profil fix sticlă garnitură", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 16, "code": "M6822", "name": "Profil intermediar 5 canale", "name_ro": "Profil intermediar 5 canale", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 716, "family": "5rail", "active": "Y"},
    {"id": 17, "code": "M6819", "name": "Profil colț 5 canale", "name_ro": "Profil colț 5 canale", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 1231, "family": "5rail", "active": "Y"},
    {"id": 18, "code": "M6292", "name": "Profil superior 5 canale", "name_ro": "Profil superior 5 canale", "category": "profile", "unit": "m", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 1436, "family": "5rail", "active": "Y"},
    # Accessories
    {"id": 50, "code": "6778", "name": "Mecanism sliding (1 lăcată, 180°)", "name_ro": "Mecanism sliding", "category": "accessory", "unit": "set", "unit_price": 210, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 51, "code": "10038", "name": "Mâner sliding fără cheie (negru)", "name_ro": "Mâner fără cheie", "category": "accessory", "unit": "buc", "unit_price": 155, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 52, "code": "10037", "name": "Mâner sliding cu cheie (negru)", "name_ro": "Mâner cu cheie", "category": "accessory", "unit": "buc", "unit_price": 300, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 53, "code": "6777", "name": "EPDM cauciuc sliding", "name_ro": "EPDM cauciuc", "category": "accessory", "unit": "m", "unit_price": 8, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 54, "code": "6775", "name": "Perie 48x480 panorama sliding", "name_ro": "Perie 48x480", "category": "accessory", "unit": "m", "unit_price": 7, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 55, "code": "6776", "name": "Perie 550 sliding", "name_ro": "Perie 550", "category": "accessory", "unit": "m", "unit_price": 8, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 56, "code": "8983", "name": "Conector plastic terminație (R/L)", "name_ro": "Conector plastic terminație", "category": "accessory", "unit": "buc", "unit_price": 40, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 57, "code": "7953", "name": "Accesorii rotile+plastic 3 canale", "name_ro": "Set accesorii rotile 3 canale", "category": "accessory", "unit": "set", "unit_price": 2800, "currency": "MDL", "weight_g_per_m": 0, "family": "3rail", "active": "Y"},
    {"id": 58, "code": "EM07300010", "name": "Centrare sliding", "name_ro": "Centrare sliding", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 59, "code": "EM07300011", "name": "Roată sliding dublă", "name_ro": "Roată sliding dublă", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 60, "code": "EM06100145", "name": "Capac plastic stâlp inferior", "name_ro": "Capac plastic stâlp inferior", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 61, "code": "EM06100151", "name": "Plastic intermediar inferior TEKCAM", "name_ro": "Plastic intermediar inferior TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 62, "code": "EM06100152", "name": "Plastic intermediar superior TEKCAM", "name_ro": "Plastic intermediar superior TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 63, "code": "EM06100141", "name": "Mâner superior TEKCAM negru", "name_ro": "Mâner superior TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 64, "code": "EM06100140", "name": "Mâner inferior TEKCAM negru", "name_ro": "Mâner inferior TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 65, "code": "EM06100142", "name": "Scurgere apă 3 canale", "name_ro": "Scurgere apă 3 canale", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "3rail", "active": "Y"},
    {"id": 66, "code": "EM07100095", "name": "Placă colț sudată 3 canale", "name_ro": "Placă colț sudată 3 canale", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "3rail", "active": "Y"},
    {"id": 67, "code": "EM09100003", "name": "Fix All High Tack 290ml", "name_ro": "Sigilant Fix All 290ml", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 68, "code": "EM06100331", "name": "Capac lateral prag", "name_ro": "Capac lateral prag", "category": "accessory", "unit": "set", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 69, "code": "EM06100146", "name": "Plastic scurgere apă ISICAM", "name_ro": "Plastic scurgere ISICAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "isicam", "active": "Y"},
    {"id": 70, "code": "EM06100147", "name": "Plastic inferior ISICAM", "name_ro": "Plastic inferior ISICAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "isicam", "active": "Y"},
    {"id": 71, "code": "EM06100148", "name": "Plastic superior ISICAM", "name_ro": "Plastic superior ISICAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "isicam", "active": "Y"},
    {"id": 72, "code": "EM07100094", "name": "Metal colț ISICAM", "name_ro": "Metal colț ISICAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "isicam", "active": "Y"},
    {"id": 73, "code": "EM06100153", "name": "Plastic scurgere TEKCAM", "name_ro": "Plastic scurgere TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 74, "code": "EM07100096", "name": "Placă colț TEKCAM laser", "name_ro": "Placă colț TEKCAM laser", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 75, "code": "EM06100143", "name": "Plastic îmbinare centrală TEKCAM", "name_ro": "Plastic îmbinare TEKCAM", "category": "accessory", "unit": "buc", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    # Glass
    {"id": 80, "code": "EM05100011", "name": "Sticlă TEKCAM 10mm transparentă", "name_ro": "Sticlă TEKCAM 10mm transparentă", "category": "glass", "unit": "m2", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "tekcam", "active": "Y"},
    {"id": 81, "code": "EM05300037", "name": "Sticlă ISICAM termoizolantă", "name_ro": "Sticlă ISICAM termoizolantă", "category": "glass", "unit": "m2", "unit_price": 0, "currency": "MDL", "weight_g_per_m": 0, "family": "isicam", "active": "Y"},
    # Services
    {"id": 90, "code": "SRV-PAINT", "name": "Vopsire RAL", "name_ro": "Vopsire RAL", "category": "service", "unit": "m2", "unit_price": 200, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 91, "code": "SRV-ASSEMBLY", "name": "Asamblare", "name_ro": "Asamblare", "category": "service", "unit": "serviciu", "unit_price": 200, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
    {"id": 92, "code": "SRV-INSTALL", "name": "Montaj", "name_ro": "Montaj", "category": "service", "unit": "serviciu", "unit_price": 200, "currency": "MDL", "weight_g_per_m": 0, "family": "common", "active": "Y"},
]

SLIDING_SETTINGS = {
    "currency": "MDL",
    "glass_rate_matrix": {
        "TEKCAM": {
            "transparent_8mm": 0, "transparent_10mm": 0,
            "tinted_8mm": 0, "tinted_10mm": 0,
            "matte_8mm": 0, "matte_10mm": 0
        },
        "ISICAM": {
            "transparent_8mm": 0, "transparent_10mm": 0,
            "tinted_8mm": 0, "tinted_10mm": 0,
            "matte_8mm": 0, "matte_10mm": 0
        }
    },
    "assembly_rate": 200,
    "assembly_basis": "perimeter",
    "installation_rate": 200,
    "installation_basis": "perimeter",
    "painting_rate_m2": 200,
    "markup_percent": 18.0,
    "waste_percent": 7.0,
    "exchange_rate_mdl_to_usd": 0.056,
    "system_types": ["TEKCAM", "ISICAM"],
    "glass_finishes": ["transparent", "tinted", "matte"],
    "glass_thicknesses": ["8mm", "10mm"],
    "colors": ["Antracit", "Alb", "Negru", "Imitație lemn", "RAL individual"]
}

# Variant definitions with dimension constraints and profile formulas
# Formula expressions use W (width_mm), H (height_mm), P (panel_count)
# Offsets extracted from Configurator xlsx
SLIDING_VARIANTS = {
    # === 3-RAIL FAMILY ===
    "3rail_3panel": {
        "family": "3rail", "panels": "3", "label": "3 Rail / 3 Panel",
        "width_min_mm": 1500, "width_max_mm": 3750,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6332": {"desc": "Profil superior 3 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6334": {"desc": "Profil vertical perete", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4, "panel_offsets": {"A": -90.4, "B": -58.5}},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4, "panel_offsets": {"A": -90.4, "B": -58.5}},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM06100142": {"qty": 2}, "EM07100095": {"qty": 2},
            "EM09100003": {"qty": 3}, "EM06100331": {"qty": 1, "condition": "threshold"}
        }
    },
    "3rail_2panel": {
        "family": "3rail", "panels": "2", "label": "3 Rail / 2 Panel",
        "width_min_mm": 1500, "width_max_mm": 3750,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6332": {"desc": "Profil superior 3 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6334": {"desc": "Profil vertical perete", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -122},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -124},
            "12039": {"desc": "Profil fix", "pieces": 1, "length_mm": 68},
            "12061": {"desc": "Garnitură fix", "pieces": 1, "length_mm": 4}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 2}, "EM06100152": {"qty": 2},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM06100142": {"qty": 2}, "EM07100095": {"qty": 0},
            "EM09100003": {"qty": 3}, "EM06100331": {"qty": 1, "condition": "threshold"}
        }
    },
    "3rail_3plus3": {
        "family": "3rail", "panels": "3+3", "label": "3 Rail / 3+3 Panel (double)",
        "width_min_mm": 1500, "width_max_mm": 3750,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11,
        "max_panel_width_mm": 1200,
        "is_double": True,
        "profiles": {
            "M6332": {"desc": "Profil superior 3 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6334": {"desc": "Profil vertical perete", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -122},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -124}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM06100142": {"qty": 4}, "EM07100095": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "3rail_2plus2": {
        "family": "3rail", "panels": "2+2", "label": "3 Rail / 2+2 Panel (double with fix)",
        "width_min_mm": 1500, "width_max_mm": 3750,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11,
        "max_panel_width_mm": 1200,
        "is_double": True,
        "profiles": {
            "M6332": {"desc": "Profil superior 3 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6334": {"desc": "Profil vertical perete", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -122},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -124},
            "12061": {"desc": "Garnitură fix", "pieces": 1, "length_mm": 4},
            "12069": {"desc": "Fix sticlă garnitură", "pieces": 1, "length_mm": 72}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM06100142": {"qty": 4}, "EM07100095": {"qty": 0},
            "EM09100003": {"qty": 3}
        }
    },
    # === 5-RAIL FAMILY (derived from PDF specs + profile catalog) ===
    "5rail_5panel": {
        "family": "5rail", "panels": "5", "label": "5 Rail / 5 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 8, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 10}, "EM07300011": {"qty": 10},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_4panel": {
        "family": "5rail", "panels": "4", "label": "5 Rail / 4 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 6, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 6}, "EM06100152": {"qty": 6},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_3panel": {
        "family": "5rail", "panels": "3", "label": "5 Rail / 3 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_2panel": {
        "family": "5rail", "panels": "2", "label": "5 Rail / 2 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18,
        "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {
            "M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}
        },
        "accessory_formulas": {
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 2}, "EM06100152": {"qty": 2},
            "EM06100141": {"qty": 2}, "EM06100140": {"qty": 2},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_5plus5": {
        "family": "5rail", "panels": "5+5", "label": "5 Rail / 5+5 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 16, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 20}, "EM07300011": {"qty": 20},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 16}, "EM06100152": {"qty": 16},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_4plus4": {
        "family": "5rail", "panels": "4+4", "label": "5 Rail / 4+4 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 12, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 16}, "EM07300011": {"qty": 16},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 12}, "EM06100152": {"qty": 12},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_3plus3": {
        "family": "5rail", "panels": "3+3", "label": "5 Rail / 3+3 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 8, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_2plus2": {
        "family": "5rail", "panels": "2+2", "label": "5 Rail / 2+2 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central mare", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8},
            "EM06100145": {"qty": 2}, "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4},
            "EM06100141": {"qty": 4}, "EM06100140": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    # === THERMAL FAMILY (derived from PDF specs) ===
    "thermal_4panel": {
        "family": "thermal", "panels": "4", "label": "Thermal / 4 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 6, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 6}, "EM06100148": {"qty": 6},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_3panel": {
        "family": "thermal", "panels": "3", "label": "Thermal / 3 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 4}, "EM06100148": {"qty": 4},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_2panel": {
        "family": "thermal", "panels": "2", "label": "Thermal / 2 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 2}, "EM06100148": {"qty": 2},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_4plus4": {
        "family": "thermal", "panels": "4+4", "label": "Thermal / 4+4 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 12, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 16}, "EM07300011": {"qty": 16},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 12}, "EM06100148": {"qty": 12},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_3plus3": {
        "family": "thermal", "panels": "3+3", "label": "Thermal / 3+3 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -81},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 8, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 8}, "EM06100148": {"qty": 8},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_2plus2": {
        "family": "thermal", "panels": "2+2", "label": "Thermal / 2+2 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000,
        "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 15, "max_panel_width_mm": 1200, "is_double": True,
        "profiles": {
            "M6292": {"desc": "Profil superior termic", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical termic", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "M6313": {"desc": "Profil central", "pieces": 1, "length_basis": "H", "length_offset_mm": -122},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {},
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8},
            "EM06100145": {"qty": 2}, "EM06100147": {"qty": 4}, "EM06100148": {"qty": 4},
            "EM07100094": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    }
}


def main():
    state = json.loads(STORE_PATH.read_text(encoding="utf-8")) if STORE_PATH.exists() else {}
    state["sliding_materials"] = SLIDING_MATERIALS
    state["sliding_settings"] = SLIDING_SETTINGS
    state["sliding_variants"] = SLIDING_VARIANTS
    state["next_sliding_material_id"] = 100
    STORE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded {len(SLIDING_MATERIALS)} sliding materials, {len(SLIDING_VARIANTS)} variants, settings -> {STORE_PATH}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the seed script**

Run: `python3 scripts/seed_sliding_materials.py`
Expected: "Seeded 47 sliding materials, 18 variants, settings -> data/decor_store.json"

**Step 3: Verify data in store**

Run: `python3 -c "import json; d=json.load(open('data/decor_store.json')); print('materials:', len(d.get('sliding_materials',[])), 'variants:', len(d.get('sliding_variants',{})))"`
Expected: "materials: 47 variants: 18"

**Step 4: Commit**

```bash
git add scripts/seed_sliding_materials.py data/decor_store.json
git commit -m "feat(decor): seed sliding materials catalog and variant definitions"
```

---

## Task 2: Backend - Sliding Settings & Materials CRUD

**Files:**
- Modify: `decor_local_store.py` (add methods after line ~830)

**Step 1: Add sliding materials CRUD methods**

Add to `DecorLocalStore` class after the existing `report_by_day` method (line ~837):

```python
    # ── Sliding module ─────────────────────────────────────────────

    @classmethod
    def get_sliding_materials(cls, active_only: bool = False) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            mats = list(state.get("sliding_materials", []))
            if active_only:
                mats = [m for m in mats if (m.get("active") or "Y") == "Y"]
            return {"success": True, "data": mats}

    @classmethod
    def update_sliding_material(cls, material_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            for m in state.get("sliding_materials", []):
                if int(m.get("id", 0)) == int(material_id):
                    for key in ("name", "name_ro", "unit", "currency", "family", "active"):
                        if key in payload:
                            m[key] = str(payload[key]).strip()
                    if "unit_price" in payload:
                        m["unit_price"] = round(cls._to_float(payload["unit_price"]), 2)
                    if "weight_g_per_m" in payload:
                        m["weight_g_per_m"] = round(cls._to_float(payload["weight_g_per_m"]), 1)
                    cls._save(state)
                    return {"success": True, "data": m}
            return {"success": False, "error": "Material not found"}

    @classmethod
    def get_sliding_settings(cls) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            return {"success": True, "data": state.get("sliding_settings", {})}

    @classmethod
    def update_sliding_settings(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            s = state.get("sliding_settings", {})
            for key in ("assembly_rate", "installation_rate", "painting_rate_m2",
                        "markup_percent", "waste_percent", "exchange_rate_mdl_to_usd"):
                if key in payload:
                    s[key] = round(cls._to_float(payload.get(key), cls._to_float(s.get(key))), 4)
            for key in ("assembly_basis", "installation_basis"):
                if key in payload and payload[key] in ("perimeter", "width", "area", "different"):
                    s[key] = payload[key]
            if "glass_rate_matrix" in payload and isinstance(payload["glass_rate_matrix"], dict):
                grm = s.get("glass_rate_matrix", {})
                for sys_type, finishes in payload["glass_rate_matrix"].items():
                    if isinstance(finishes, dict):
                        if sys_type not in grm:
                            grm[sys_type] = {}
                        for finish_key, rate in finishes.items():
                            grm[sys_type][finish_key] = round(cls._to_float(rate), 2)
                s["glass_rate_matrix"] = grm
            for list_key in ("system_types", "glass_finishes", "glass_thicknesses", "colors"):
                if list_key in payload and isinstance(payload[list_key], list):
                    s[list_key] = [str(x).strip() for x in payload[list_key] if str(x).strip()]
            state["sliding_settings"] = s
            cls._save(state)
            return {"success": True, "data": s}

    @classmethod
    def get_sliding_variants(cls) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            return {"success": True, "data": state.get("sliding_variants", {})}
```

**Step 2: Verify import works**

Run: `python3 -c "from decor_local_store import DecorLocalStore; r=DecorLocalStore.get_sliding_materials(); print(r['success'], len(r['data']))"`
Expected: `True 47`

**Step 3: Commit**

```bash
git add decor_local_store.py
git commit -m "feat(decor): add sliding materials/settings CRUD methods"
```

---

## Task 3: Backend - Sliding Quote Calculator

**Files:**
- Modify: `decor_local_store.py` (add `calculate_sliding_quote` method)

**Step 1: Add the calculate_sliding_quote method**

Add after `get_sliding_variants`:

```python
    @classmethod
    def _calc_metraj(cls, basis: str, width_m: float, height_m: float) -> float:
        """Calculate metraj based on selected basis type."""
        if basis == "perimeter":
            return round(2 * width_m + 2 * height_m, 3)
        elif basis == "width":
            return round(width_m, 3)
        elif basis == "area":
            return round(width_m * height_m, 3)
        return round(2 * width_m + 2 * height_m, 3)  # default to perimeter

    @classmethod
    def calculate_sliding_quote(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            s = state.get("sliding_settings", {})
            variants = state.get("sliding_variants", {})
            materials_list = state.get("sliding_materials", [])
            mat_by_code = {m["code"]: m for m in materials_list}

            # Parse inputs
            variant_key = str(payload.get("variant") or "").strip()
            if variant_key not in variants:
                return {"success": False, "error": f"Unknown variant: {variant_key}"}
            variant = variants[variant_key]

            width_mm = max(cls._to_float(payload.get("width_mm")), 0.0)
            height_mm = max(cls._to_float(payload.get("height_mm")), 0.0)
            orientation = str(payload.get("orientation") or "left").lower()
            include_threshold = str(payload.get("include_threshold") or "N").upper() != "N"

            # Glass options
            include_glass = str(payload.get("include_glass") or "Y").upper() != "N"
            glass_system = str(payload.get("glass_system") or "TEKCAM").upper()
            glass_finish = str(payload.get("glass_finish") or "transparent").lower()
            glass_thickness = str(payload.get("glass_thickness") or "10mm").lower()

            # Service options
            include_assembly = str(payload.get("include_assembly") or "N").upper() != "N"
            include_installation = str(payload.get("include_installation") or "N").upper() != "N"

            # Validate dimensions
            w_min = cls._to_float(variant.get("width_min_mm"), 0)
            w_max = cls._to_float(variant.get("width_max_mm"), 99999)
            h_min = cls._to_float(variant.get("height_min_mm"), 0)
            h_max = cls._to_float(variant.get("height_max_mm"), 99999)
            if width_mm < w_min or width_mm > w_max:
                return {"success": False, "error": f"Width must be {w_min}-{w_max}mm for {variant.get('label')}"}
            if height_mm < h_min or height_mm > h_max:
                return {"success": False, "error": f"Height must be {h_min}-{h_max}mm for {variant.get('label')}"}

            width_m = width_mm / 1000.0
            height_m = height_mm / 1000.0
            area_m2 = round(width_m * height_m, 3)
            max_area = cls._to_float(variant.get("max_area_m2"), 999)
            if area_m2 > max_area:
                return {"success": False, "error": f"Area {area_m2}m² exceeds max {max_area}m² for {variant.get('label')}"}

            # Determine panel count
            panels_str = str(variant.get("panels", "3"))
            is_double = variant.get("is_double", False)
            if "+" in panels_str:
                parts = panels_str.split("+")
                panels_per_side = int(parts[0])
                total_panels = panels_per_side * 2
            else:
                total_panels = int(panels_str)
                panels_per_side = total_panels

            # Calculate panel width
            frame_offset_mm = 55 if not is_double else 110  # frame takes space
            effective_width = width_mm - frame_offset_mm
            if is_double:
                panel_width_mm = effective_width / 2.0 / panels_per_side
            else:
                panel_width_mm = effective_width / total_panels

            # Profile cost calculation
            lines = []
            profile_total_cost = 0.0
            profile_total_weight_kg = 0.0

            for code, pdef in variant.get("profiles", {}).items():
                mat = mat_by_code.get(code, {})
                unit_price_per_m = cls._to_float(mat.get("unit_price"), 0.0)
                weight_g_per_m = cls._to_float(mat.get("weight_g_per_m"), 0.0)

                if pdef.get("per_panel"):
                    # Per-panel profiles
                    offset = cls._to_float(pdef.get("length_offset_mm"), 0)
                    length_mm = panel_width_mm + offset
                    pieces = total_panels
                else:
                    pieces = int(pdef.get("pieces", 1))
                    basis = pdef.get("length_basis", "W")
                    if basis == "H":
                        base_mm = height_mm
                    else:
                        base_mm = width_mm
                    if "length_mm" in pdef:
                        length_mm = cls._to_float(pdef["length_mm"])
                    else:
                        length_mm = base_mm + cls._to_float(pdef.get("length_offset_mm"), 0)

                length_m = round(max(length_mm / 1000.0, 0), 4)
                total_length_m = round(length_m * pieces, 4)
                cost = round(total_length_m * unit_price_per_m, 2)
                weight_kg = round(total_length_m * weight_g_per_m / 1000.0, 3)
                profile_total_cost += cost
                profile_total_weight_kg += weight_kg

                lines.append({
                    "code": code,
                    "name": mat.get("name", pdef.get("desc", code)),
                    "qty": pieces,
                    "unit": "m",
                    "length_m": length_m,
                    "total_length_m": total_length_m,
                    "unit_price": unit_price_per_m,
                    "amount": cost,
                    "category": "profile",
                    "weight_kg": weight_kg,
                })

            # Optional profiles (threshold etc)
            for code, pdef in variant.get("optional_profiles", {}).items():
                condition = pdef.get("condition", "")
                if condition == "threshold" and not include_threshold:
                    continue
                mat = mat_by_code.get(code, {})
                pieces = int(pdef.get("pieces", 1))
                length_mm = cls._to_float(pdef.get("length_mm"), 0)
                length_m = round(length_mm / 1000.0, 4)
                unit_price = cls._to_float(mat.get("unit_price"), 0.0)
                cost = round(length_m * pieces * unit_price, 2)
                profile_total_cost += cost
                lines.append({
                    "code": code, "name": mat.get("name", code),
                    "qty": pieces, "unit": "m", "length_m": length_m,
                    "total_length_m": round(length_m * pieces, 4),
                    "unit_price": unit_price, "amount": cost,
                    "category": "profile",
                })

            # Accessory cost calculation
            accessory_total_cost = 0.0
            for code, adef in variant.get("accessory_formulas", {}).items():
                condition = adef.get("condition", "")
                if condition == "threshold" and not include_threshold:
                    continue
                mat = mat_by_code.get(code, {})
                qty = int(adef.get("qty", 0))
                if qty <= 0:
                    continue
                unit_price = cls._to_float(mat.get("unit_price"), 0.0)
                cost = round(qty * unit_price, 2)
                accessory_total_cost += cost
                lines.append({
                    "code": code, "name": mat.get("name", code),
                    "qty": qty, "unit": mat.get("unit", "buc"),
                    "unit_price": unit_price, "amount": cost,
                    "category": "accessory",
                })

            # Glass cost
            glass_cost = 0.0
            if include_glass:
                grm = s.get("glass_rate_matrix", {})
                rate_key = f"{glass_finish}_{glass_thickness}"
                glass_rate = cls._to_float((grm.get(glass_system) or {}).get(rate_key), 0.0)
                glass_cost = round(area_m2 * glass_rate, 2)
                lines.append({
                    "code": "GLASS", "name": f"Sticlă {glass_system} {glass_finish} {glass_thickness}",
                    "qty": area_m2, "unit": "m2",
                    "unit_price": glass_rate, "amount": glass_cost,
                    "category": "glass",
                })

            # Assembly cost
            assembly_cost = 0.0
            if include_assembly:
                basis = s.get("assembly_basis", "perimeter")
                metraj = cls._calc_metraj(basis, width_m, height_m)
                rate = cls._to_float(s.get("assembly_rate"), 0.0)
                assembly_cost = round(metraj * rate, 2)
                lines.append({
                    "code": "ASSEMBLY", "name": f"Asamblare ({basis})",
                    "qty": metraj, "unit": "m" if basis != "area" else "m2",
                    "unit_price": rate, "amount": assembly_cost,
                    "category": "service",
                })

            # Installation cost
            install_cost = 0.0
            if include_installation:
                basis = s.get("installation_basis", "perimeter")
                metraj = cls._calc_metraj(basis, width_m, height_m)
                rate = cls._to_float(s.get("installation_rate"), 0.0)
                install_cost = round(metraj * rate, 2)
                lines.append({
                    "code": "INSTALL", "name": f"Montaj ({basis})",
                    "qty": metraj, "unit": "m" if basis != "area" else "m2",
                    "unit_price": rate, "amount": install_cost,
                    "category": "service",
                })

            # Totals
            direct_cost = round(profile_total_cost + accessory_total_cost + glass_cost + assembly_cost + install_cost, 2)
            waste_pct = cls._to_float(s.get("waste_percent"), 0.0)
            markup_pct = cls._to_float(s.get("markup_percent"), 0.0)
            waste_amount = round(direct_cost * (waste_pct / 100.0), 2)
            subtotal = round(direct_cost + waste_amount, 2)
            margin_amount = round(subtotal * (markup_pct / 100.0), 2)
            total = round(subtotal + margin_amount, 2)
            mdl_to_usd = cls._to_float(s.get("exchange_rate_mdl_to_usd"), 0.0)

            lines.append({"code": "WASTE", "name": f"Deșeuri teh. {waste_pct:.1f}%", "qty": 1, "unit": "job", "unit_price": waste_amount, "amount": waste_amount, "category": "overhead"})
            lines.append({"code": "MARGIN", "name": f"Marjă {markup_pct:.1f}%", "qty": 1, "unit": "job", "unit_price": margin_amount, "amount": margin_amount, "category": "overhead"})

            return {
                "success": True,
                "data": {
                    "product_type": "sliding",
                    "inputs": {
                        "variant": variant_key,
                        "variant_label": variant.get("label", variant_key),
                        "family": variant.get("family"),
                        "width_mm": width_mm, "height_mm": height_mm,
                        "orientation": orientation,
                        "include_threshold": include_threshold,
                        "include_glass": include_glass,
                        "glass_system": glass_system,
                        "glass_finish": glass_finish,
                        "glass_thickness": glass_thickness,
                        "include_assembly": include_assembly,
                        "include_installation": include_installation,
                    },
                    "metrics": {
                        "area_m2": area_m2,
                        "perimeter_m": round(2 * width_m + 2 * height_m, 3),
                        "total_panels": total_panels,
                        "panel_width_mm": round(panel_width_mm, 1),
                        "profile_weight_kg": round(profile_total_weight_kg, 2),
                    },
                    "lines": lines,
                    "summary": {
                        "currency": s.get("currency", "MDL"),
                        "profile_cost": profile_total_cost,
                        "accessory_cost": accessory_total_cost,
                        "glass_cost": glass_cost,
                        "assembly_cost": assembly_cost,
                        "installation_cost": install_cost,
                        "direct_cost": direct_cost,
                        "waste_amount": waste_amount,
                        "subtotal": subtotal,
                        "margin_amount": margin_amount,
                        "total": total,
                        "total_usd": round(total * mdl_to_usd, 2) if mdl_to_usd else None,
                    },
                }
            }
```

**Step 2: Test the calculator**

Run: `python3 -c "from decor_local_store import DecorLocalStore; r=DecorLocalStore.calculate_sliding_quote({'variant':'3rail_3panel','width_mm':3000,'height_mm':2500}); print('OK' if r['success'] else r['error']); d=r.get('data',{}); print('Total:', d.get('summary',{}).get('total'), d.get('summary',{}).get('currency')); print('Panels:', d.get('metrics',{}).get('total_panels'), 'Width:', d.get('metrics',{}).get('panel_width_mm')); print('Lines:', len(d.get('lines',[])))"`

Expected: OK, Total with MDL currency, 3 panels, reasonable panel width, 15+ lines

**Step 3: Commit**

```bash
git add decor_local_store.py
git commit -m "feat(decor): add sliding quote calculator with variant-specific formulas"
```

---

## Task 4: Backend - Sliding Cutting List Generator

**Files:**
- Modify: `decor_local_store.py` (add `calculate_sliding_cutting_list` method)

**Step 1: Add cutting list method after calculate_sliding_quote**

```python
    @classmethod
    def calculate_sliding_cutting_list(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed production cutting list with exact piece lengths."""
        quote = cls.calculate_sliding_quote(payload)
        if not quote.get("success"):
            return quote

        qd = quote["data"]
        inputs = qd["inputs"]
        width_mm = inputs["width_mm"]
        height_mm = inputs["height_mm"]
        variant_key = inputs["variant"]

        with cls._lock:
            state = cls._load()
            variants = state.get("sliding_variants", {})
            materials_list = state.get("sliding_materials", [])
            mat_by_code = {m["code"]: m for m in materials_list}

        variant = variants.get(variant_key, {})
        panels_str = str(variant.get("panels", "3"))
        is_double = variant.get("is_double", False)
        if "+" in panels_str:
            panels_per_side = int(panels_str.split("+")[0])
            total_panels = panels_per_side * 2
        else:
            total_panels = int(panels_str)
            panels_per_side = total_panels

        frame_offset = 55 if not is_double else 110
        effective_w = width_mm - frame_offset
        if is_double:
            panel_w = effective_w / 2.0 / panels_per_side
        else:
            panel_w = effective_w / total_panels

        cutting_lines = []
        for code, pdef in variant.get("profiles", {}).items():
            mat = mat_by_code.get(code, {})
            if pdef.get("per_panel"):
                offsets = pdef.get("panel_offsets", {})
                if offsets:
                    for label, off in offsets.items():
                        length_mm = round(panel_w + off, 1)
                        cutting_lines.append({
                            "code": code, "name": mat.get("name", code),
                            "panel_label": label,
                            "pieces": 1, "length_mm": length_mm,
                            "length_cm": round(length_mm / 10.0, 2),
                            "weight_g_per_m": cls._to_float(mat.get("weight_g_per_m")),
                        })
                else:
                    offset = cls._to_float(pdef.get("length_offset_mm"), 0)
                    length_mm = round(panel_w + offset, 1)
                    cutting_lines.append({
                        "code": code, "name": mat.get("name", code),
                        "panel_label": "all",
                        "pieces": total_panels, "length_mm": length_mm,
                        "length_cm": round(length_mm / 10.0, 2),
                        "weight_g_per_m": cls._to_float(mat.get("weight_g_per_m")),
                    })
            else:
                pieces = int(pdef.get("pieces", 1))
                if "length_mm" in pdef:
                    length_mm = cls._to_float(pdef["length_mm"])
                else:
                    basis = pdef.get("length_basis", "W")
                    base = height_mm if basis == "H" else width_mm
                    length_mm = round(base + cls._to_float(pdef.get("length_offset_mm"), 0), 1)
                cutting_lines.append({
                    "code": code, "name": mat.get("name", code),
                    "panel_label": "-",
                    "pieces": pieces, "length_mm": length_mm,
                    "length_cm": round(length_mm / 10.0, 2),
                    "weight_g_per_m": cls._to_float(mat.get("weight_g_per_m")),
                })

        return {
            "success": True,
            "data": {
                "variant_label": variant.get("label", variant_key),
                "width_mm": width_mm, "height_mm": height_mm,
                "total_panels": total_panels,
                "panel_width_mm": round(panel_w, 1),
                "cutting_lines": cutting_lines,
                "quote_summary": qd["summary"],
            }
        }
```

**Step 2: Test the cutting list**

Run: `python3 -c "from decor_local_store import DecorLocalStore; r=DecorLocalStore.calculate_sliding_cutting_list({'variant':'3rail_3panel','width_mm':3000,'height_mm':2500}); print('OK' if r['success'] else r['error']); d=r['data']; print('Lines:', len(d['cutting_lines'])); [print(f\"  {l['code']}: {l['pieces']}pc x {l['length_cm']}cm\") for l in d['cutting_lines'][:5]]"`

Expected: OK, 7+ cutting lines with realistic cm lengths

**Step 3: Commit**

```bash
git add decor_local_store.py
git commit -m "feat(decor): add sliding production cutting list generator"
```

---

## Task 5: Backend - Extend create_order for Sliding

**Files:**
- Modify: `decor_local_store.py:702-742` (modify `create_order` method)

**Step 1: Modify create_order to support product_type**

Replace the `create_order` method to detect product_type and dispatch accordingly:

```python
    @classmethod
    def create_order(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        product_type = str(payload.get("product_type") or "veranda").lower()
        if product_type == "sliding":
            quote = cls.calculate_sliding_quote(payload)
        else:
            quote = cls.calculate_quote(payload)
        if not quote.get("success"):
            return quote
        qd = quote["data"]

        with cls._lock:
            state = cls._load()
            order_id = int(state.get("next_order_id") or 1)
            state["next_order_id"] = order_id + 1
            order_number = cls._order_number(state)
            status = cls._status_by_id(state, 1) or {"id": 1, "code": "lead", "name": "Лид / Новый"}

            order = {
                "id": order_id,
                "order_number": order_number,
                "barcode": order_number,
                "product_type": product_type,
                "client_name": str(payload.get("client_name") or "").strip(),
                "client_phone": str(payload.get("client_phone") or "").strip(),
                "client_email": str(payload.get("client_email") or "").strip(),
                "project_type": str(payload.get("project_type") or ("Sliding" if product_type == "sliding" else "Стеклянная крыша")).strip(),
                "project_name": str(payload.get("project_name") or "").strip(),
                "location": str(payload.get("location") or "").strip(),
                "color": str(payload.get("color") or "").strip(),
                "notes": str(payload.get("notes") or "").strip(),
                "status_id": status.get("id"),
                "status_code": status.get("code"),
                "status_name": status.get("name"),
                "quote": qd,
                "items": qd.get("lines") or [],
                "total_amount": (qd.get("summary") or {}).get("total") or 0,
                "currency": (qd.get("summary") or {}).get("currency") or "MDL",
                "created_at": cls._now_iso(),
                "updated_at": cls._now_iso(),
            }
            if not order["client_name"] or not order["client_phone"]:
                return {"success": False, "error": "Numele și telefonul clientului sunt obligatorii"}

            state.setdefault("orders", []).insert(0, order)
            cls._save(state)
            return {"success": True, "data": order}
```

**Step 2: Verify backward compatibility**

Run: `python3 -c "from decor_local_store import DecorLocalStore; r=DecorLocalStore.calculate_quote({'width_mm':4000,'projection_mm':3000,'front_height_mm':2500,'rear_height_mm':2900}); print('Veranda OK' if r['success'] else 'FAIL')"`

Expected: "Veranda OK"

**Step 3: Commit**

```bash
git add decor_local_store.py
git commit -m "feat(decor): extend create_order to support sliding product type"
```

---

## Task 6: API Routes for Sliding

**Files:**
- Modify: `app.py` (add routes after line ~2730)

**Step 1: Add sliding API endpoints**

Insert after the existing decor operator routes (line ~2731):

```python
# ── Sliding API ────────────────────────────────────────────

@app.route('/api/decor-admin/sliding-materials', methods=['GET'])
def api_decor_admin_sliding_materials():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(DecorLocalStore.get_sliding_materials())

@app.route('/api/decor-admin/sliding-materials/<int:material_id>', methods=['POST', 'PUT'])
def api_decor_admin_sliding_material_update(material_id):
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    resp = DecorLocalStore.update_sliding_material(material_id, data)
    return jsonify(resp), (200 if resp.get("success") else 400)

@app.route('/api/decor-admin/sliding-settings', methods=['GET'])
def api_decor_admin_sliding_settings():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(DecorLocalStore.get_sliding_settings())

@app.route('/api/decor-admin/sliding-settings', methods=['POST'])
def api_decor_admin_sliding_settings_update():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    resp = DecorLocalStore.update_sliding_settings(data)
    return jsonify(resp), (200 if resp.get("success") else 400)

@app.route('/api/decor-admin/sliding-variants', methods=['GET'])
def api_decor_admin_sliding_variants():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    return jsonify(DecorLocalStore.get_sliding_variants())

@app.route('/api/decor-operator/calculate-sliding', methods=['POST'])
def api_decor_operator_calculate_sliding():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    resp = DecorLocalStore.calculate_sliding_quote(data)
    return jsonify(resp), (200 if resp.get("success") else 400)

@app.route('/api/decor-operator/sliding-cutting-list', methods=['POST'])
def api_decor_operator_sliding_cutting_list():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "error": "Authentication required"}), 401
    data = request.get_json(silent=True) or {}
    resp = DecorLocalStore.calculate_sliding_cutting_list(data)
    return jsonify(resp), (200 if resp.get("success") else 400)
```

**Step 2: Verify routes load**

Run: `python3 -c "from app import app; rules=[r.rule for r in app.url_map.iter_rules() if 'sliding' in r.rule]; print(len(rules), 'sliding routes'); [print(' ',r) for r in sorted(rules)]"`

Expected: 7 sliding routes listed

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat(decor): add sliding API routes"
```

---

## Task 7: Operator UI - Product Type Selector & Sliding Form

**Files:**
- Modify: `templates/decor_operator.html`

**Step 1: Add product type selector**

After line 105 (`<p class="muted" id="introText"...`), before the first `<div class="card">`, insert the product type selector:

```html
    <div class="card" style="padding:10px 16px;">
        <div class="row" style="gap:12px;">
            <label style="font-weight:700; font-size:14px; margin:0;">Tip produs:</label>
            <button class="btn btn-primary" id="btnProductVeranda" type="button" onclick="setProductType('veranda')">Verandă</button>
            <button class="btn btn-ghost" id="btnProductSliding" type="button" onclick="setProductType('sliding')">Sliding</button>
        </div>
    </div>
```

**Step 2: Add sliding form section**

After the product type selector, add the sliding-specific form (hidden by default). Insert before the existing `<div class="card">` for section 1:

```html
    <div class="card" id="slidingFormBlock" style="display:none;">
        <h2 style="font-size:16px; margin-bottom:10px;">1. Parametrii Sliding</h2>
        <div class="grid grid-3">
            <div>
                <label>Familie sistem</label>
                <select id="slidingFamily" onchange="onSlidingFamilyChange()">
                    <option value="3rail">3 Rail Single Glass</option>
                    <option value="5rail">5 Rail Single Glass</option>
                    <option value="thermal">Thermal Sliding</option>
                </select>
            </div>
            <div>
                <label>Configurație panouri</label>
                <select id="slidingVariant"></select>
            </div>
            <div>
                <label>Culoare</label>
                <select id="slidingColor"></select>
            </div>
            <div><label>Lățime, mm</label><input type="number" id="slidingWidth" value="3000" min="1000" max="6000"></div>
            <div><label>Înălțime, mm</label><input type="number" id="slidingHeight" value="2500" min="1000" max="3000"></div>
            <div>
                <label>Orientare</label>
                <select id="slidingOrientation">
                    <option value="left">Stânga (sol)</option>
                    <option value="right">Dreapta (sağ)</option>
                </select>
            </div>
            <div><label>Denumire proiect</label><input type="text" id="slidingProjectName" placeholder="Villa / Terrace"></div>
        </div>

        <div style="margin-top:12px; padding:12px; border:1px solid var(--line); border-radius:10px; background:#fbfeff;">
            <div style="font-weight:700; font-size:13px; margin-bottom:8px;">Opțiuni sticlă</div>
            <div class="row" style="margin-bottom:8px;">
                <label class="checkbox"><input type="checkbox" id="slidingIncludeGlass" checked onchange="toggleSlidingGlassOptions()"> Sticlă inclusă</label>
            </div>
            <div id="slidingGlassOptions" class="grid grid-3">
                <div>
                    <label>Tip sistem sticlă</label>
                    <select id="slidingGlassSystem">
                        <option value="TEKCAM">TEKCAM (simplă)</option>
                        <option value="ISICAM">ISICAM (termoizolantă)</option>
                    </select>
                </div>
                <div>
                    <label>Finisaj sticlă</label>
                    <select id="slidingGlassFinish">
                        <option value="transparent">Transparentă</option>
                        <option value="tinted">Tonată</option>
                        <option value="matte">Mată</option>
                    </select>
                </div>
                <div>
                    <label>Grosime sticlă</label>
                    <select id="slidingGlassThickness">
                        <option value="8mm">8 mm</option>
                        <option value="10mm" selected>10 mm</option>
                    </select>
                </div>
            </div>
        </div>

        <div class="row" style="margin-top:10px;">
            <label class="checkbox"><input type="checkbox" id="slidingThreshold"> Prag suplimentar</label>
            <label class="checkbox"><input type="checkbox" id="slidingAssembly"> Asamblare inclusă</label>
            <label class="checkbox"><input type="checkbox" id="slidingInstallation"> Montaj inclus</label>
            <button class="btn btn-primary" id="btnCalcSliding" onclick="calcSliding()">Calculează</button>
            <button class="btn btn-ghost" onclick="resetSliding()">Reset</button>
        </div>
        <div id="slidingCalcError" class="err" style="display:none;"></div>
        <div id="slidingQuoteBlock" style="display:none; margin-top:12px;">
            <div class="kpis">
                <div class="kpi"><div class="label">Arie</div><div class="value" id="skpiArea">0</div></div>
                <div class="kpi"><div class="label">Panouri</div><div class="value" id="skpiPanels">0</div></div>
                <div class="kpi"><div class="label">Greutate profil</div><div class="value" id="skpiWeight">0</div></div>
                <div class="kpi"><div class="label">Total</div><div class="value" id="skpiTotal">0</div></div>
            </div>
            <div style="margin-top:12px; overflow:auto;">
                <table>
                    <thead><tr><th>Cod</th><th>Denumire</th><th>Cant.</th><th>UM</th><th class="right">Preț unit.</th><th class="right">Sumă</th></tr></thead>
                    <tbody id="slidingQuoteLines"></tbody>
                </table>
            </div>
            <div class="row" style="justify-content:space-between; margin-top:8px;">
                <div>
                    <button class="btn btn-alt" id="btnCuttingList" onclick="showCuttingList()">Fișă tăiere producție</button>
                </div>
                <div class="quote-total" id="slidingTotalText"></div>
            </div>
        </div>
        <div id="cuttingListBlock" style="display:none; margin-top:12px; border-top:1px solid var(--line); padding-top:12px;">
            <h3 style="font-size:14px; margin-bottom:8px;">Fișă tăiere producție</h3>
            <table>
                <thead><tr><th>Cod profil</th><th>Denumire</th><th>Panou</th><th>Buc.</th><th class="right">Lungime (cm)</th><th class="right">Lungime (mm)</th></tr></thead>
                <tbody id="cuttingListLines"></tbody>
            </table>
        </div>
    </div>
```

**Step 3: Add JavaScript for sliding functionality**

At the end of the existing `<script>` block, add the sliding JS functions. Find the closing `</script>` tag and insert before it:

```javascript
// ── Sliding module ───────────────────────────────────
let currentProductType = 'veranda';
let slidingVariants = {};
let lastSlidingQuote = null;

function setProductType(type) {
    currentProductType = type;
    document.getElementById('btnProductVeranda').className = type === 'veranda' ? 'btn btn-primary' : 'btn btn-ghost';
    document.getElementById('btnProductSliding').className = type === 'sliding' ? 'btn btn-primary' : 'btn btn-ghost';
    // Toggle form visibility
    const verandaCards = document.querySelectorAll('.card');
    const slidingBlock = document.getElementById('slidingFormBlock');
    // Section 1 (veranda params) is the card right after product type selector
    const sec1 = verandaCards[2]; // 0=langbar area, 1=product selector, 2=veranda params
    if (type === 'sliding') {
        if (sec1) sec1.style.display = 'none';
        slidingBlock.style.display = '';
        loadSlidingVariants();
    } else {
        if (sec1) sec1.style.display = '';
        slidingBlock.style.display = 'none';
    }
}

async function loadSlidingVariants() {
    try {
        const r = await fetch('/api/decor-admin/sliding-variants');
        const j = await r.json();
        if (j.success) slidingVariants = j.data;
        onSlidingFamilyChange();
        // Load colors
        const sr = await fetch('/api/decor-admin/sliding-settings');
        const sj = await sr.json();
        if (sj.success) {
            const sel = document.getElementById('slidingColor');
            sel.innerHTML = '';
            (sj.data.colors || []).forEach(c => { const o = document.createElement('option'); o.value = c; o.textContent = c; sel.appendChild(o); });
        }
    } catch(e) { console.error('loadSlidingVariants', e); }
}

function onSlidingFamilyChange() {
    const family = document.getElementById('slidingFamily').value;
    const sel = document.getElementById('slidingVariant');
    sel.innerHTML = '';
    for (const [key, v] of Object.entries(slidingVariants)) {
        if (v.family === family) {
            const o = document.createElement('option');
            o.value = key;
            o.textContent = v.label;
            sel.appendChild(o);
        }
    }
}

function toggleSlidingGlassOptions() {
    document.getElementById('slidingGlassOptions').style.display =
        document.getElementById('slidingIncludeGlass').checked ? '' : 'none';
}

async function calcSliding() {
    const errEl = document.getElementById('slidingCalcError');
    const quoteBlock = document.getElementById('slidingQuoteBlock');
    errEl.style.display = 'none';
    quoteBlock.style.display = 'none';
    document.getElementById('cuttingListBlock').style.display = 'none';

    const payload = {
        variant: document.getElementById('slidingVariant').value,
        width_mm: parseFloat(document.getElementById('slidingWidth').value) || 0,
        height_mm: parseFloat(document.getElementById('slidingHeight').value) || 0,
        orientation: document.getElementById('slidingOrientation').value,
        include_threshold: document.getElementById('slidingThreshold').checked ? 'Y' : 'N',
        include_glass: document.getElementById('slidingIncludeGlass').checked ? 'Y' : 'N',
        glass_system: document.getElementById('slidingGlassSystem').value,
        glass_finish: document.getElementById('slidingGlassFinish').value,
        glass_thickness: document.getElementById('slidingGlassThickness').value,
        include_assembly: document.getElementById('slidingAssembly').checked ? 'Y' : 'N',
        include_installation: document.getElementById('slidingInstallation').checked ? 'Y' : 'N',
    };

    try {
        const r = await fetch('/api/decor-operator/calculate-sliding', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        const j = await r.json();
        if (!j.success) { errEl.textContent = j.error || 'Eroare calcul'; errEl.style.display = ''; return; }
        lastSlidingQuote = j.data;
        renderSlidingQuote(j.data);
    } catch(e) { errEl.textContent = 'Network error'; errEl.style.display = ''; }
}

function renderSlidingQuote(data) {
    const m = data.metrics;
    const s = data.summary;
    document.getElementById('skpiArea').textContent = m.area_m2 + ' m²';
    document.getElementById('skpiPanels').textContent = m.total_panels;
    document.getElementById('skpiWeight').textContent = m.profile_weight_kg + ' kg';
    document.getElementById('skpiTotal').textContent = s.total.toLocaleString() + ' ' + s.currency;

    const tbody = document.getElementById('slidingQuoteLines');
    tbody.innerHTML = '';
    (data.lines || []).forEach(l => {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td>' + (l.code||'') + '</td><td>' + (l.name||'') + '</td><td>' + (l.qty||0) +
            '</td><td>' + (l.unit||'') + '</td><td class="right">' + (l.unit_price||0).toLocaleString() +
            '</td><td class="right">' + (l.amount||0).toLocaleString() + '</td>';
        tbody.appendChild(tr);
    });
    document.getElementById('slidingTotalText').textContent = s.total.toLocaleString() + ' ' + s.currency + (s.total_usd ? ' (~$' + s.total_usd + ')' : '');
    document.getElementById('slidingQuoteBlock').style.display = '';
}

async function showCuttingList() {
    if (!lastSlidingQuote) return;
    const payload = {
        variant: lastSlidingQuote.inputs.variant,
        width_mm: lastSlidingQuote.inputs.width_mm,
        height_mm: lastSlidingQuote.inputs.height_mm,
        orientation: lastSlidingQuote.inputs.orientation,
        include_threshold: lastSlidingQuote.inputs.include_threshold ? 'Y' : 'N',
        include_glass: lastSlidingQuote.inputs.include_glass ? 'Y' : 'N',
        glass_system: lastSlidingQuote.inputs.glass_system,
        glass_finish: lastSlidingQuote.inputs.glass_finish,
        glass_thickness: lastSlidingQuote.inputs.glass_thickness,
        include_assembly: lastSlidingQuote.inputs.include_assembly ? 'Y' : 'N',
        include_installation: lastSlidingQuote.inputs.include_installation ? 'Y' : 'N',
    };
    try {
        const r = await fetch('/api/decor-operator/sliding-cutting-list', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        const j = await r.json();
        if (!j.success) return;
        const tbody = document.getElementById('cuttingListLines');
        tbody.innerHTML = '';
        (j.data.cutting_lines || []).forEach(l => {
            const tr = document.createElement('tr');
            tr.innerHTML = '<td>' + l.code + '</td><td>' + l.name + '</td><td>' + l.panel_label +
                '</td><td>' + l.pieces + '</td><td class="right">' + l.length_cm +
                '</td><td class="right">' + l.length_mm + '</td>';
            tbody.appendChild(tr);
        });
        document.getElementById('cuttingListBlock').style.display = '';
    } catch(e) { console.error(e); }
}

function resetSliding() {
    document.getElementById('slidingWidth').value = '3000';
    document.getElementById('slidingHeight').value = '2500';
    document.getElementById('slidingQuoteBlock').style.display = 'none';
    document.getElementById('cuttingListBlock').style.display = 'none';
    document.getElementById('slidingCalcError').style.display = 'none';
    lastSlidingQuote = null;
}
```

Also modify the existing `btnCreateOrder` click handler to include product_type and sliding data when creating orders. Find the order creation fetch call and add:

```javascript
// In the existing order creation logic, add product_type detection:
// If currentProductType === 'sliding', use sliding quote data for order payload
```

**Step 4: Wire order creation for sliding**

Modify the existing `btnCreateOrder` handler to detect product type. In the existing JS, find where `btnCreateOrder` is set up and modify to include product_type in the payload. The existing code posts to `/api/decor-operator/order` — sliding should use the same endpoint with `product_type: 'sliding'` plus the sliding-specific fields.

**Step 5: Commit**

```bash
git add templates/decor_operator.html
git commit -m "feat(decor): add sliding configurator UI to operator page"
```

---

## Task 8: Admin UI - Sliding Materials & Settings Tab

**Files:**
- Modify: `templates/decor_admin.html`

**Step 1: Add Sliding tab to admin navigation**

Find the existing tab navigation in admin template and add a "Sliding" tab button alongside existing tabs (Materials, Settings, Orders, Reports).

**Step 2: Add sliding materials section**

Add a new tab content div for sliding materials — a table listing all sliding materials with editable price fields and save buttons.

**Step 3: Add sliding settings section**

Add the glass rate matrix editor (12 inputs in a grid), assembly/installation rate + basis selectors, markup/waste fields.

**Step 4: Add sliding JS handlers**

Load sliding materials on tab switch, save material prices inline, load/save sliding settings.

**Step 5: Commit**

```bash
git add templates/decor_admin.html
git commit -m "feat(decor): add sliding admin tab for materials and settings"
```

---

## Task 9: Integration Testing & Verification

**Step 1: Start the app and test sliding calculation**

Run: `python3 app.py` (or the usual dev server command)

Test via curl:
```bash
curl -s -X POST http://localhost:5000/api/decor-operator/calculate-sliding \
  -H 'Content-Type: application/json' \
  -d '{"variant":"3rail_3panel","width_mm":3000,"height_mm":2500,"include_glass":"Y","glass_system":"TEKCAM","glass_finish":"transparent","glass_thickness":"10mm"}' | python3 -m json.tool | head -30
```

Expected: JSON with success=true, lines array, summary with total in MDL

**Step 2: Test cutting list**

```bash
curl -s -X POST http://localhost:5000/api/decor-operator/sliding-cutting-list \
  -H 'Content-Type: application/json' \
  -d '{"variant":"3rail_3panel","width_mm":3000,"height_mm":2500}' | python3 -m json.tool | head -30
```

Expected: JSON with cutting_lines array containing profile codes and lengths in cm

**Step 3: Test backward compatibility**

```bash
curl -s -X POST http://localhost:5000/api/decor-operator/calculate \
  -H 'Content-Type: application/json' \
  -d '{"width_mm":4000,"projection_mm":3000,"front_height_mm":2500,"rear_height_mm":2900}' | python3 -m json.tool | head -10
```

Expected: Existing veranda calculation still works

**Step 4: Test all variants**

```bash
for v in 3rail_3panel 3rail_2panel 3rail_3plus3 3rail_2plus2 5rail_5panel 5rail_3panel thermal_4panel thermal_2panel; do
  echo -n "$v: "
  curl -s -X POST http://localhost:5000/api/decor-operator/calculate-sliding \
    -H 'Content-Type: application/json' \
    -d "{\"variant\":\"$v\",\"width_mm\":3000,\"height_mm\":2500}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('OK' if d.get('success') else 'FAIL: '+d.get('error',''))"
done
```

Expected: All variants return OK

**Step 5: Test dimension validation**

```bash
curl -s -X POST http://localhost:5000/api/decor-operator/calculate-sliding \
  -H 'Content-Type: application/json' \
  -d '{"variant":"3rail_3panel","width_mm":500,"height_mm":2500}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('error',''))"
```

Expected: Error about width being below minimum

**Step 6: Commit verification**

```bash
git add -A
git commit -m "test(decor): verify sliding integration - all variants pass"
```

---

## Summary of Files Modified

| File | Action | Task |
|------|--------|------|
| `scripts/seed_sliding_materials.py` | Create | Task 1 |
| `data/decor_store.json` | Modify (via seed) | Task 1 |
| `decor_local_store.py` | Modify (add ~300 lines) | Tasks 2-5 |
| `app.py` | Modify (add ~60 lines) | Task 6 |
| `templates/decor_operator.html` | Modify (add ~200 lines HTML + ~150 lines JS) | Task 7 |
| `templates/decor_admin.html` | Modify (add ~150 lines) | Task 8 |

## Execution Order

Tasks 1-6 are sequential (each depends on the previous).
Tasks 7 and 8 (UI) can be done in parallel after Task 6.
Task 9 requires all previous tasks complete.

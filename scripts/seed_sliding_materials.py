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
    "exchange_rate_mdl_to_usd": 0.056,
    "system_types": ["TEKCAM", "ISICAM"],
    "glass_finishes": ["transparent", "tinted", "matte"],
    "glass_thicknesses": ["8mm", "10mm"],
    "colors": ["Antracit", "Alb", "Negru", "Imitație lemn", "RAL individual"]
}

# Variant definitions — all 18 variants for 3-rail, 5-rail, and thermal families
# Each has profile formulas with offset constants from the HUUN configurator xlsx
SLIDING_VARIANTS = {
    "3rail_3panel": {
        "family": "3rail", "panels": "3", "label": "3 Rail / 3 Panel",
        "width_min_mm": 1500, "width_max_mm": 3750, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11, "max_panel_width_mm": 1200,
        "profiles": {
            "M6332": {"desc": "Profil superior 3 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6334": {"desc": "Profil vertical perete", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4, "panel_offsets": {"A": -90.4, "B": -58.5}},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4, "panel_offsets": {"A": -90.4, "B": -58.5}},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM06100142": {"qty": 2}, "EM07100095": {"qty": 2},
            "EM09100003": {"qty": 3}, "EM06100331": {"qty": 1, "condition": "threshold"}
        }
    },
    "3rail_2panel": {
        "family": "3rail", "panels": "2", "label": "3 Rail / 2 Panel",
        "width_min_mm": 1500, "width_max_mm": 3750, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11, "max_panel_width_mm": 1200,
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
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 2}, "EM06100152": {"qty": 2}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM06100142": {"qty": 2}, "EM07100095": {"qty": 0},
            "EM09100003": {"qty": 3}, "EM06100331": {"qty": 1, "condition": "threshold"}
        }
    },
    "3rail_3plus3": {
        "family": "3rail", "panels": "3+3", "label": "3 Rail / 3+3 Panel (double)",
        "width_min_mm": 1500, "width_max_mm": 3750, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11, "max_panel_width_mm": 1200, "is_double": True,
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
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM06100142": {"qty": 4}, "EM07100095": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "3rail_2plus2": {
        "family": "3rail", "panels": "2+2", "label": "3 Rail / 2+2 Panel (double with fix)",
        "width_min_mm": 1500, "width_max_mm": 3750, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 11, "max_panel_width_mm": 1200, "is_double": True,
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
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM06100142": {"qty": 4}, "EM07100095": {"qty": 0},
            "EM09100003": {"qty": 3}
        }
    },
    "5rail_5panel": {
        "family": "5rail", "panels": "5", "label": "5 Rail / 5 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 8, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 10}, "EM07300011": {"qty": 10}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_4panel": {
        "family": "5rail", "panels": "4", "label": "5 Rail / 4 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 6, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 6}, "EM06100152": {"qty": 6}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_3panel": {
        "family": "5rail", "panels": "3", "label": "5 Rail / 3 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -90.4},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 4, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_2panel": {
        "family": "5rail", "panels": "2", "label": "5 Rail / 2 Panel",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
        "max_area_m2": 18, "max_panel_width_mm": 1200,
        "profiles": {
            "M6292": {"desc": "Profil superior 5 canale", "pieces": 1, "length_offset_mm": -110},
            "M6333": {"desc": "Profil prag plat", "pieces": 1, "length_offset_mm": -142},
            "M6822": {"desc": "Profil vertical perete 5 canale", "pieces": 2, "length_basis": "H", "length_offset_mm": -19},
            "11574": {"desc": "Profil sup fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "11579": {"desc": "Profil inf fixare sticlă", "per_panel": True, "length_basis": "panel_w", "length_offset_mm": -115},
            "M6305": {"desc": "Profil vertical sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -137},
            "11646": {"desc": "Profil conexiune sticlă", "pieces": 2, "length_basis": "H", "length_offset_mm": -139}
        },
        "optional_profiles": {"M7524": {"desc": "Prag suplimentar", "condition": "threshold", "pieces": 1, "length_mm": 15}},
        "accessory_formulas": {
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 2}, "EM06100152": {"qty": 2}, "EM06100141": {"qty": 2},
            "EM06100140": {"qty": 2}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_5plus5": {
        "family": "5rail", "panels": "5+5", "label": "5 Rail / 5+5 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 20}, "EM07300011": {"qty": 20}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 16}, "EM06100152": {"qty": 16}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_4plus4": {
        "family": "5rail", "panels": "4+4", "label": "5 Rail / 4+4 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 16}, "EM07300011": {"qty": 16}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 12}, "EM06100152": {"qty": 12}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_3plus3": {
        "family": "5rail", "panels": "3+3", "label": "5 Rail / 3+3 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 8}, "EM06100152": {"qty": 8}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "5rail_2plus2": {
        "family": "5rail", "panels": "2+2", "label": "5 Rail / 2+2 Panel (double)",
        "width_min_mm": 2500, "width_max_mm": 6000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8}, "EM06100145": {"qty": 2},
            "EM06100151": {"qty": 4}, "EM06100152": {"qty": 4}, "EM06100141": {"qty": 4},
            "EM06100140": {"qty": 4}, "EM09100003": {"qty": 3}
        }
    },
    "thermal_4panel": {
        "family": "thermal", "panels": "4", "label": "Thermal / 4 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 6}, "EM06100148": {"qty": 6}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "thermal_3panel": {
        "family": "thermal", "panels": "3", "label": "Thermal / 3 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 6}, "EM07300011": {"qty": 6}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 4}, "EM06100148": {"qty": 4}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "thermal_2panel": {
        "family": "thermal", "panels": "2", "label": "Thermal / 2 Panel",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 4}, "EM07300011": {"qty": 4}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 2}, "EM06100148": {"qty": 2}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "thermal_4plus4": {
        "family": "thermal", "panels": "4+4", "label": "Thermal / 4+4 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 16}, "EM07300011": {"qty": 16}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 12}, "EM06100148": {"qty": 12}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "thermal_3plus3": {
        "family": "thermal", "panels": "3+3", "label": "Thermal / 3+3 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 12}, "EM07300011": {"qty": 12}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 8}, "EM06100148": {"qty": 8}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
        }
    },
    "thermal_2plus2": {
        "family": "thermal", "panels": "2+2", "label": "Thermal / 2+2 Panel (double)",
        "width_min_mm": 2000, "width_max_mm": 5000, "height_min_mm": 1000, "height_max_mm": 3000,
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
            "EM07300010": {"qty": 8}, "EM07300011": {"qty": 8}, "EM06100145": {"qty": 2},
            "EM06100147": {"qty": 4}, "EM06100148": {"qty": 4}, "EM07100094": {"qty": 4},
            "EM09100003": {"qty": 3}
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

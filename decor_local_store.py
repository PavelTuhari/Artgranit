"""
Oracle-backed normalized relational store для проекта DECOR.
При первом чтении мигрирует существующий state из legacy Oracle KV или data/decor_store.json.
"""
from __future__ import annotations

import json
import threading
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from models.decor_oracle_store import load_state as load_decor_state, save_state as save_decor_state


class DecorLocalStore:
    _lock = threading.RLock()
    _path = Path(__file__).resolve().parent / "data" / "decor_store.json"
    _store_key = "decor_store"
    _image_map_path = Path(__file__).resolve().parent / "data" / "decor_material_images.json"
    _image_map_docs_html_path = Path(__file__).resolve().parent / "data" / "decor_material_images_docs_html.json"
    _manual_translation_path = Path(__file__).resolve().parent / "data" / "decor_manual_translations.json"
    _image_map_cache: Optional[Dict[str, Any]] = None
    _image_map_docs_html_cache: Optional[Dict[str, Any]] = None
    _manual_translation_cache: Optional[Dict[str, Any]] = None

    _material_meta_by_code: Dict[str, Dict[str, str]] = {
        "M6521": {"name_original": "ARKA BAĞLANTI PRF", "original_lang": "tr", "name_ro": "Profil de conexiune spate"},
        "M6523": {"name_original": "CAM TAŞIYICI ARA PRF", "original_lang": "tr", "name_ro": "Profil intermediar port-sticlă"},
        "M6383": {"name_original": "CAM TAŞIYICI ORTA KAPAK", "original_lang": "tr", "name_ro": "Capac central profil port-sticlă"},
        "M6385": {"name_original": "CAM TAŞIYICI KENAR KAPAK", "original_lang": "tr", "name_ro": "Capac lateral profil port-sticlă"},
        "EM07100091": {"name_original": "Veranda Gutter Cover R+L", "original_lang": "en", "name_ro": "Capac jgheab verandă D+S"},
        "EM07100090": {"name_original": "Veranda Rear Cover R+L", "original_lang": "en", "name_ro": "Capac spate verandă D+S"},
        "EM06100001": {"name_original": "Gutter Water Drainage Plastic", "original_lang": "en", "name_ro": "Scurgere apă jgheab (plastic)"},
        "VRD-0004": {"name_original": "CF-03 VERANDA EPDM FİTİL", "original_lang": "tr", "name_ro": "Garnitură EPDM verandă CF-03"},
        "VRD-0007": {"name_original": "CF-09 VERANDA EPDM FİTİL", "original_lang": "tr", "name_ro": "Garnitură EPDM verandă CF-09"},
        "LED-WHITE": {"name_original": "LED illumination (white)", "original_lang": "en", "name_ro": "Iluminare LED (alb)"},
        "LED-RGB": {"name_original": "RGB LED + dimmer", "original_lang": "en", "name_ro": "LED RGB + dimmer"},
        "GLASS-ISICAM": {"name_original": "Insulated glass unit (ISICAM)", "original_lang": "en", "name_ro": "Pachet de sticlă termoizolantă (ISICAM)"},
        "GLASS-TEKCAM": {"name_original": "Single glass (TEKCAM)", "original_lang": "en", "name_ro": "Sticlă simplă (TEKCAM)"},
        "INSTALL": {"name_original": "Installation works", "original_lang": "en", "name_ro": "Lucrări de montaj"},
    }
    _image_overrides_by_code: Dict[str, str] = {
        "M6521": "/static/decor/materials/001_huun_new_veranda_material_base_price_list_2024__profile_new_system_r15_c3.png",
        "M6523": "/static/decor/materials/001_huun_new_veranda_material_base_price_list_2024__profile_new_system_r15_c3.png",
        "M6383": "/static/decor/materials/001_huun_new_veranda_material_base_price_list_2024__profile_new_system_r15_c3.png",
        "M6385": "/static/decor/materials/001_huun_new_veranda_material_base_price_list_2024__profile_new_system_r15_c3.png",
        "EM07100091": "/static/decor/materials/007_huun_new_veranda_material_base_price_list_2024__accessory_2_r6_c4.png",
        "EM07100090": "/static/decor/materials/008_huun_new_veranda_material_base_price_list_2024__accessory_2_r7_c4.png",
        "EM06100001": "/static/decor/materials/012_huun_new_veranda_material_base_price_list_2024__accessory_2_r9_c4.png",
        "VRD-0004": "/static/decor/materials/016_huun_new_veranda_material_base_price_list_2024__accessory_2_r22_c4.png",
        "VRD-0007": "/static/decor/materials/017_huun_new_veranda_material_base_price_list_2024__accessory_2_r23_c4.png",
        "LED-WHITE": "/static/decor/materials/020_yeni_veranda_u_reti_m_mali_yet_hesaplama__ret_m_prof_l_r21_c5.jpg",
        "LED-RGB": "/static/decor/materials/022_yeni_veranda_u_reti_m_mali_yet_hesaplama__aksesuar_sayfasi_r23_c6.png",
        "GLASS-ISICAM": "/static/decor/materials/029_yeni_veranda_u_reti_m_mali_yet_hesaplama__veranda_cam_r2_c1.png",
        "GLASS-TEKCAM": "/static/decor/materials/030_yeni_veranda_u_reti_m_mali_yet_hesaplama__veranda_cam_r2_c6.png",
        "INSTALL": "/static/decor/materials/033_yeni_veranda_u_reti_m_mali_yet_hesaplama__mal_yet_hesaplama_r5_c2.png",
    }
    _image_fallback_by_category: Dict[str, str] = {
        "profile": "/static/decor/materials/001_huun_new_veranda_material_base_price_list_2024__profile_new_system_r15_c3.png",
        "accessory": "/static/decor/materials/008_huun_new_veranda_material_base_price_list_2024__accessory_2_r7_c4.png",
        "drainage": "/static/decor/materials/012_huun_new_veranda_material_base_price_list_2024__accessory_2_r9_c4.png",
        "consumable": "/static/decor/materials/016_huun_new_veranda_material_base_price_list_2024__accessory_2_r22_c4.png",
        "option_led": "/static/decor/materials/022_yeni_veranda_u_reti_m_mali_yet_hesaplama__aksesuar_sayfasi_r23_c6.png",
        "glass": "/static/decor/materials/029_yeni_veranda_u_reti_m_mali_yet_hesaplama__veranda_cam_r2_c1.png",
        "service": "/static/decor/materials/033_yeni_veranda_u_reti_m_mali_yet_hesaplama__mal_yet_hesaplama_r5_c2.png",
    }

    @classmethod
    def _ensure_parent(cls) -> None:
        cls._path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _image_map(cls) -> Dict[str, Any]:
        if cls._image_map_cache is not None:
            return cls._image_map_cache
        if not cls._image_map_path.exists():
            cls._image_map_cache = {"by_code": {}}
            return cls._image_map_cache
        try:
            cls._image_map_cache = json.loads(cls._image_map_path.read_text(encoding="utf-8"))
        except Exception:
            cls._image_map_cache = {"by_code": {}}
        return cls._image_map_cache

    @classmethod
    def _image_map_docs_html(cls) -> Dict[str, Any]:
        if cls._image_map_docs_html_cache is not None:
            return cls._image_map_docs_html_cache
        if not cls._image_map_docs_html_path.exists():
            cls._image_map_docs_html_cache = {"by_code": {}}
            return cls._image_map_docs_html_cache
        try:
            cls._image_map_docs_html_cache = json.loads(cls._image_map_docs_html_path.read_text(encoding="utf-8"))
        except Exception:
            cls._image_map_docs_html_cache = {"by_code": {}}
        return cls._image_map_docs_html_cache

    @classmethod
    def _manual_translation_map(cls) -> Dict[str, Any]:
        if cls._manual_translation_cache is not None:
            return cls._manual_translation_cache
        if not cls._manual_translation_path.exists():
            cls._manual_translation_cache = {}
            return cls._manual_translation_cache
        try:
            raw = json.loads(cls._manual_translation_path.read_text(encoding="utf-8"))
            cls._manual_translation_cache = raw if isinstance(raw, dict) else {}
        except Exception:
            cls._manual_translation_cache = {}
        return cls._manual_translation_cache

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _default_statuses(cls) -> List[Dict[str, Any]]:
        return [
            {"id": 1, "code": "lead", "name": "Лид / Новый"},
            {"id": 2, "code": "quoted", "name": "Смета отправлена"},
            {"id": 3, "code": "approved", "name": "Согласовано"},
            {"id": 4, "code": "production", "name": "В производстве"},
            {"id": 5, "code": "installation", "name": "Монтаж"},
            {"id": 6, "code": "completed", "name": "Завершено"},
            {"id": 7, "code": "cancelled", "name": "Отменено"},
        ]

    @classmethod
    def _default_materials(cls) -> List[Dict[str, Any]]:
        # Базовый seed на основании файлов veranda (HUUN profile/accessory + производственная калькуляция).
        rows = [
            {"id": 1, "code": "M6521", "name": "Rare Connection Profile", "category": "profile", "unit": "m", "unit_price": 34.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "PROFILE (NEW SYSTEM)", "active": "Y"},
            {"id": 2, "code": "M6523", "name": "Angle Profile", "category": "profile", "unit": "m", "unit_price": 12.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "PROFILE (NEW SYSTEM)", "active": "Y"},
            {"id": 3, "code": "M6383", "name": "Main Carrier Middle Cover Profile", "category": "profile", "unit": "m", "unit_price": 8.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "PROFILE (NEW SYSTEM)", "active": "Y"},
            {"id": 4, "code": "M6385", "name": "Main Carrier Side Cover Profile", "category": "profile", "unit": "m", "unit_price": 10.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "PROFILE (NEW SYSTEM)", "active": "Y"},
            {"id": 5, "code": "EM07100091", "name": "Veranda Gutter Cover R+L", "category": "accessory", "unit": "pc", "unit_price": 14.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "ACCESSORY (2)", "active": "Y"},
            {"id": 6, "code": "EM07100090", "name": "Veranda Rear Cover R+L", "category": "accessory", "unit": "pc", "unit_price": 14.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "ACCESSORY (2)", "active": "Y"},
            {"id": 7, "code": "EM06100001", "name": "Gutter Water Drainage Plastic", "category": "drainage", "unit": "pc", "unit_price": 8.0, "currency": "USD", "source_file": "HUUN- NEW VERANDA- Material Base Price List -2024.xlsx", "source_sheet": "ACCESSORY (2)", "active": "Y"},
            {"id": 8, "code": "VRD-0004", "name": "CF-03 VERANDA EPDM FITIL", "category": "consumable", "unit": "kg", "unit_price": 5.0, "currency": "USD", "source_file": "YENI VERANDA ÜRETİM MALİYET HESAPLAMA.xlsx", "source_sheet": "VERANDA MALZEME LİSTESİ", "active": "Y"},
            {"id": 9, "code": "VRD-0007", "name": "CF-09 VERANDA EPDM FITIL", "category": "consumable", "unit": "kg", "unit_price": 5.0, "currency": "USD", "source_file": "YENI VERANDA ÜRETİM MALİYET HESAPLAMA.xlsx", "source_sheet": "VERANDA MALZEME LİSTESİ", "active": "Y"},
            {"id": 10, "code": "LED-WHITE", "name": "LED illumination (white)", "category": "option_led", "unit": "m", "unit_price": 18.0, "currency": "USD", "source_file": "inferred", "source_sheet": "TZ", "active": "Y"},
            {"id": 11, "code": "LED-RGB", "name": "RGB LED + dimmer", "category": "option_led", "unit": "set", "unit_price": 165.0, "currency": "USD", "source_file": "inferred", "source_sheet": "TZ", "active": "Y"},
            {"id": 12, "code": "GLASS-ISICAM", "name": "Insulated glass unit (ISICAM)", "category": "glass", "unit": "m2", "unit_price": 78.0, "currency": "USD", "source_file": "YENI VERANDA ÜRETİM MALİYET HESAPLAMA.xlsx", "source_sheet": "Veri Sayfası-2", "active": "Y"},
            {"id": 13, "code": "GLASS-TEKCAM", "name": "Single glass (TEKCAM)", "category": "glass", "unit": "m2", "unit_price": 49.0, "currency": "USD", "source_file": "YENI VERANDA ÜRETİM MALİYET HESAPLAMA.xlsx", "source_sheet": "Veri Sayfası-2", "active": "Y"},
            {"id": 14, "code": "INSTALL", "name": "Installation works", "category": "service", "unit": "m2", "unit_price": 42.0, "currency": "USD", "source_file": "inferred", "source_sheet": "TZ", "active": "Y"},
        ]
        return [cls._normalize_material_row(r) for r in rows]

    @classmethod
    def _infer_original_lang(cls, row: Dict[str, Any]) -> str:
        code = str(row.get("code") or "").upper()
        if code.startswith("VRD-") or code.startswith("PRG-"):
            return "tr"
        source_file = str(row.get("source_file") or "")
        if "YENI" in source_file.upper():
            return "tr"
        return "en"

    @classmethod
    def _lang_label(cls, lang: str) -> str:
        labels = {"en": "English", "tr": "Türkçe", "ro": "Română"}
        return labels.get((lang or "").lower(), (lang or "").upper() or "Unknown")

    @classmethod
    def _normalize_material_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(row)
        code = str(out.get("code") or "").strip().upper()
        manual_meta = cls._manual_translation_map().get(code, {})
        meta = {**cls._material_meta_by_code.get(code, {}), **(manual_meta if isinstance(manual_meta, dict) else {})}
        orig_name = str(out.get("name_original") or meta.get("name_original") or out.get("name") or "").strip()
        orig_lang = str(out.get("original_lang") or meta.get("original_lang") or cls._infer_original_lang(out)).strip().lower() or "en"
        name_ro = str(out.get("name_ro") or meta.get("name_ro") or out.get("name") or orig_name).strip()

        image_url = str(out.get("image_url") or "").strip()
        html_exact = (((cls._image_map_docs_html().get("by_code") or {}).get(code) or {}).get("url") or "").strip()
        if html_exact and (not image_url or "/static/decor/materials/" in image_url):
            image_url = html_exact
        if not image_url:
            exact = html_exact
            if not exact:
                exact = cls._image_overrides_by_code.get(code)
            if not exact:
                by_code = (cls._image_map().get("by_code") or {})
                exact = ((by_code.get(code) or {}).get("url") or "").strip()
            image_url = exact or cls._image_fallback_by_category.get(str(out.get("category") or "").strip(), "")

        out["name_original"] = orig_name or str(out.get("name") or "").strip()
        out["original_lang"] = orig_lang
        out["original_lang_label"] = cls._lang_label(orig_lang)
        out["name_ro"] = name_ro or str(out.get("name") or "").strip()
        out["image_url"] = image_url
        # Preserve legacy field for existing UI/API consumers
        out["name"] = str(out.get("name") or out["name_original"]).strip()
        return out

    @classmethod
    def _default_settings(cls) -> Dict[str, Any]:
        return {
            "currency": "USD",
            "exchange_rate_usd_to_mdl": 17.85,
            "markup_percent": 18.0,
            "waste_percent": 7.0,
            "profile_weight_kg_per_m2": 9.5,
            "accessory_fixed_per_m2": 12.0,
            "drainage_fixed": 55.0,
            "transport_fixed": 120.0,
            "install_rate_m2": 42.0,
            "glass_rate_m2": {
                "TEKCAM": 49.0,
                "ISICAM": 78.0,
            },
            "led_options": {
                "none": 0.0,
                "white_led": 18.0,
                "rgb_led_dimmer": 165.0,
            },
            "project_types": ["Стеклянная крыша", "Веранда", "Пергола", "Козырек"],
            "system_types": ["TEKCAM", "ISICAM"],
            "colors": ["Антрацит", "Белый", "Черный", "Под дерево", "Индивидуальный RAL"],
        }

    @classmethod
    def _default_state(cls) -> Dict[str, Any]:
        return {
            "materials": cls._default_materials(),
            "statuses": cls._default_statuses(),
            "settings": cls._default_settings(),
            "orders": [],
            "next_material_id": 1000,
            "next_order_id": 1,
            "next_quote_seq": 1,
        }

    @classmethod
    def _load(cls) -> Dict[str, Any]:
        try:
            state = load_decor_state(
                default_factory=cls._default_state,
                fallback_path=cls._path,
            )
        except Exception:
            state = cls._default_state()

        # Backward-compatible fill.
        base = cls._default_state()
        for key, value in base.items():
            state.setdefault(key, deepcopy(value))
        # Normalize materials to enrich old stores with images/translations.
        state["materials"] = [cls._normalize_material_row(m) for m in state.get("materials", [])]
        return state

    @classmethod
    def _save(cls, state: Dict[str, Any]) -> None:
        save_decor_state(state)

    @classmethod
    def _status_by_id(cls, state: Dict[str, Any], status_id: int) -> Optional[Dict[str, Any]]:
        for s in state.get("statuses", []):
            if int(s.get("id") or 0) == int(status_id):
                return s
        return None

    @classmethod
    def _order_number(cls, state: Dict[str, Any]) -> str:
        seq = int(state.get("next_quote_seq") or 1)
        state["next_quote_seq"] = seq + 1
        return f"DEC-{datetime.now().strftime('%Y%m')}-{seq:05d}"

    @classmethod
    def _to_float(cls, v: Any, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            if isinstance(v, str):
                v = v.replace(",", ".").strip()
            return float(v)
        except Exception:
            return default

    @classmethod
    def _norm_text(cls, s: Any) -> str:
        text = str(s or "").lower().strip()
        text = text.replace("ă", "a").replace("â", "a").replace("î", "i").replace("ș", "s").replace("ş", "s").replace("ț", "t").replace("ţ", "t")
        text = text.replace("ü", "u").replace("ı", "i").replace("ğ", "g").replace("ö", "o").replace("ç", "c")
        text = re.sub(r"[^a-z0-9.+-]+", " ", text)
        return " ".join(text.split())

    @classmethod
    def _ai_split_parts(cls, text: str) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        for raw in re.split(r"[\n;,]+", text or ""):
            line = str(raw or "").strip()
            if not line:
                continue
            qty = 1.0
            token = line
            m1 = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*[xх*]?\s+(.+)$", line, flags=re.I)
            m2 = re.match(r"^(.+?)\s+[xх*]?\s*(\d+(?:[.,]\d+)?)\s*$", line, flags=re.I)
            if m1:
                qty = cls._to_float(m1.group(1), 1.0)
                token = m1.group(2).strip()
            elif m2 and len(m2.group(1).split()) > 0:
                qty = cls._to_float(m2.group(2), 1.0)
                token = m2.group(1).strip()
            parts.append({"original": line, "token": token, "qty": max(qty, 0.001)})
        return parts

    @classmethod
    def _ai_score_material(cls, token_norm: str, m: Dict[str, Any]) -> float:
        code = cls._norm_text(m.get("code"))
        n1 = cls._norm_text(m.get("name"))
        n2 = cls._norm_text(m.get("name_original"))
        n3 = cls._norm_text(m.get("name_ro"))
        if token_norm == code and code:
            return 100.0
        if code and code in token_norm:
            return 95.0
        if token_norm and any(token_norm in n for n in (n1, n2, n3) if n):
            return 90.0
        best = 0.0
        for cand in [code, n1, n2, n3]:
            if not cand:
                continue
            best = max(best, SequenceMatcher(None, token_norm, cand).ratio() * 100.0)
        return round(best, 2)

    @classmethod
    def get_catalog(cls, active_only: bool = True) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            materials = state.get("materials", [])
            if active_only:
                materials = [m for m in materials if (m.get("active") or "Y") == "Y"]
            return {
                "success": True,
                "data": {
                    "materials": materials,
                    "settings": state.get("settings", {}),
                    "statuses": state.get("statuses", []),
                }
            }

    @classmethod
    def ai_parse_items(cls, text: str, threshold: int = 40, backend: str = "local") -> Dict[str, Any]:
        # Oracle mode placeholder: current DECOR uses local JSON catalog, so fallback to local matching.
        try:
            parts = cls._ai_split_parts(text)
            if not parts:
                return {"success": True, "matches": [], "backend": "local"}
            state = cls._load()
            mats = [m for m in state.get("materials", []) if (m.get("active") or "Y") == "Y"]
            matches: List[Dict[str, Any]] = []
            th = max(0, min(int(threshold), 100))
            for part in parts:
                token = part["token"]
                token_norm = cls._norm_text(token)
                best = None
                best_score = -1.0
                for m in mats:
                    score = cls._ai_score_material(token_norm, m)
                    if score > best_score:
                        best_score = score
                        best = m
                if best and best_score >= th:
                    qty = round(cls._to_float(part["qty"], 1.0), 3)
                    unit_price = round(cls._to_float(best.get("unit_price")), 2)
                    matches.append({
                        "material_id": best.get("id"),
                        "code": best.get("code"),
                        "name": best.get("name"),
                        "name_original": best.get("name_original"),
                        "name_ro": best.get("name_ro"),
                        "original_lang": best.get("original_lang"),
                        "category": best.get("category"),
                        "unit": best.get("unit"),
                        "unit_price": unit_price,
                        "qty": qty,
                        "amount": round(unit_price * qty, 2),
                        "image_url": best.get("image_url"),
                        "confidence": round(best_score, 2),
                        "original": part["original"],
                        "token": token,
                    })
                else:
                    matches.append({
                        "material_id": None,
                        "code": None,
                        "name": None,
                        "name_original": None,
                        "name_ro": None,
                        "original_lang": None,
                        "category": None,
                        "unit": None,
                        "unit_price": 0.0,
                        "qty": round(cls._to_float(part["qty"], 1.0), 3),
                        "amount": 0.0,
                        "image_url": None,
                        "confidence": round(max(best_score, 0.0), 2),
                        "original": part["original"],
                        "token": token,
                    })
            return {"success": True, "matches": matches, "backend": "local" if backend != "oracle" else "oracle(local-fallback)"}
        except Exception as e:
            return {"success": False, "error": str(e), "matches": [], "backend": "local"}

    @classmethod
    def get_materials(cls, active_only: bool = False) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            rows = state.get("materials", [])
            if active_only:
                rows = [m for m in rows if (m.get("active") or "Y") == "Y"]
            rows = sorted(rows, key=lambda x: ((x.get("category") or ""), (x.get("code") or "")))
            return {"success": True, "data": rows}

    @classmethod
    def upsert_material(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            rows = state.get("materials", [])
            mid = int(payload.get("id") or 0)
            data = {
                "code": str(payload.get("code") or "").strip(),
                "name": str(payload.get("name") or "").strip(),
                "name_original": str(payload.get("name_original") or "").strip(),
                "original_lang": str(payload.get("original_lang") or "").strip().lower(),
                "name_ro": str(payload.get("name_ro") or "").strip(),
                "image_url": str(payload.get("image_url") or "").strip(),
                "category": str(payload.get("category") or "other").strip(),
                "unit": str(payload.get("unit") or "pcs").strip(),
                "unit_price": round(cls._to_float(payload.get("unit_price")), 2),
                "currency": str(payload.get("currency") or state.get("settings", {}).get("currency", "USD")).strip() or "USD",
                "source_file": str(payload.get("source_file") or "").strip(),
                "source_sheet": str(payload.get("source_sheet") or "").strip(),
                "notes": str(payload.get("notes") or "").strip(),
                "active": "N" if str(payload.get("active") or "Y").upper() == "N" else "Y",
            }
            if not data["name"]:
                data["name"] = data["name_original"] or data["name_ro"]
            if not data["code"] or not data["name"]:
                return {"success": False, "error": "code и name обязательны"}
            data = cls._normalize_material_row(data)
            existing = None
            for row in rows:
                if int(row.get("id") or 0) == mid and mid:
                    existing = row
                    break
            if existing:
                existing.update(data)
                existing["updated_at"] = cls._now_iso()
                saved = existing
            else:
                new_id = int(state.get("next_material_id") or 1000)
                state["next_material_id"] = new_id + 1
                saved = {"id": new_id, **data, "created_at": cls._now_iso(), "updated_at": cls._now_iso()}
                rows.append(saved)
            state["materials"] = rows
            cls._save(state)
            return {"success": True, "data": saved}

    @classmethod
    def delete_material(cls, material_id: int) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            before = len(state.get("materials", []))
            state["materials"] = [m for m in state.get("materials", []) if int(m.get("id") or 0) != int(material_id)]
            if len(state["materials"]) == before:
                return {"success": False, "error": "Материал не найден"}
            cls._save(state)
            return {"success": True}

    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            return {"success": True, "data": state.get("settings", {})}

    @classmethod
    def update_settings(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            s = state.get("settings", {})
            for key in [
                "exchange_rate_usd_to_mdl", "markup_percent", "waste_percent",
                "profile_weight_kg_per_m2", "accessory_fixed_per_m2", "drainage_fixed",
                "transport_fixed", "install_rate_m2"
            ]:
                if key in payload:
                    s[key] = round(cls._to_float(payload.get(key), cls._to_float(s.get(key))), 4)
            if "glass_rate_m2" in payload and isinstance(payload.get("glass_rate_m2"), dict):
                s["glass_rate_m2"] = {
                    str(k): round(cls._to_float(v), 2)
                    for k, v in payload["glass_rate_m2"].items()
                }
            if "led_options" in payload and isinstance(payload.get("led_options"), dict):
                s["led_options"] = {
                    str(k): round(cls._to_float(v), 2)
                    for k, v in payload["led_options"].items()
                }
            for list_key in ("project_types", "system_types", "colors"):
                if list_key in payload and isinstance(payload.get(list_key), list):
                    s[list_key] = [str(x).strip() for x in payload[list_key] if str(x).strip()]
            state["settings"] = s
            cls._save(state)
            return {"success": True, "data": s}

    @classmethod
    def calculate_quote(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            s = state.get("settings", {})
            width_mm = max(cls._to_float(payload.get("width_mm")), 0.0)
            projection_mm = max(cls._to_float(payload.get("projection_mm")), 0.0)
            front_h_mm = max(cls._to_float(payload.get("front_height_mm")), 0.0)
            rear_h_mm = max(cls._to_float(payload.get("rear_height_mm")), 0.0)
            systems = set((s.get("system_types") or []))
            system_type = str(payload.get("system_type") or "ISICAM").upper()
            if systems and system_type not in systems:
                system_type = next(iter(systems))
            led_option = str(payload.get("led_option") or "none")
            include_installation = str(payload.get("include_installation") or "Y").upper() != "N"
            include_transport = str(payload.get("include_transport") or "Y").upper() != "N"
            include_drainage = str(payload.get("include_drainage") or "Y").upper() != "N"

            area_m2 = round((width_mm / 1000.0) * (projection_mm / 1000.0), 3)
            width_m = width_mm / 1000.0
            projection_m = projection_mm / 1000.0
            perimeter_m = round((2 * width_m) + (2 * projection_m), 3) if width_m and projection_m else 0.0
            slope_mm = round(max(rear_h_mm - front_h_mm, 0.0), 1)
            slope_pct = round((slope_mm / projection_mm) * 100.0, 2) if projection_mm > 0 else 0.0

            glass_rate = cls._to_float((s.get("glass_rate_m2") or {}).get(system_type), 0.0)
            install_rate = cls._to_float(s.get("install_rate_m2"), 0.0)
            led_rates = s.get("led_options") or {}
            led_rate = cls._to_float(led_rates.get(led_option), 0.0)
            profile_weight = cls._to_float(s.get("profile_weight_kg_per_m2"), 0.0)
            accessory_per_m2 = cls._to_float(s.get("accessory_fixed_per_m2"), 0.0)
            drainage_fixed = cls._to_float(s.get("drainage_fixed"), 0.0) if include_drainage else 0.0
            transport_fixed = cls._to_float(s.get("transport_fixed"), 0.0) if include_transport else 0.0
            waste_pct = cls._to_float(s.get("waste_percent"), 0.0)
            markup_pct = cls._to_float(s.get("markup_percent"), 0.0)

            # Приближение к production-шаблону veranda: считаем геометрию/элементы по размерам
            module_span_m = 1.2  # типичный шаг секций
            beam_step_m = 0.7    # шаг поперечных профилей / стеклодержателей
            post_count = max(2, int(round(width_m / module_span_m + 0.499))) if width_m > 0 else 0
            section_count = max(1, post_count - 1) if post_count else 0
            beam_count = max(1, int(round(projection_m / beam_step_m + 0.499))) if projection_m > 0 else 0
            rafter_len_m = round((projection_m**2 + max((rear_h_mm - front_h_mm) / 1000.0, 0.0)**2) ** 0.5, 3) if projection_m else 0.0
            total_rafter_m = round(rafter_len_m * max(2, post_count), 3)
            frame_length_m = round((2 * width_m) + (2 * projection_m) + total_rafter_m, 3)
            profile_weight_total_kg = round(frame_length_m * profile_weight, 2)

            # Базовая цена профиля по массе (USD/kg) плюс фикс профилей из справочника category=profile
            profile_kg_rate = 2.4
            avg_profile_item = None
            profile_items = [m for m in state.get("materials", []) if (m.get("category") == "profile" and (m.get("active") or "Y") == "Y")]
            if profile_items:
                prices = [cls._to_float(m.get("unit_price")) for m in profile_items if cls._to_float(m.get("unit_price")) > 0]
                if prices:
                    avg_profile_item = sum(prices) / len(prices)
                    # смешанная ставка: учитываем характерный price list в USD
                    profile_kg_rate = max(2.4, min(avg_profile_item / 10.0, 6.5))

            profile_material_cost = round(profile_weight_total_kg * profile_kg_rate, 2)
            glass_cost = round(area_m2 * glass_rate, 2)
            accessory_units = max(1, section_count * 2 + beam_count * 2)
            accessory_cost = round((area_m2 * accessory_per_m2) + accessory_units * 1.75, 2)
            led_cost = round((perimeter_m if led_option == "white_led" else 1.0) * led_rate, 2) if led_option != "none" else 0.0
            install_cost = round(area_m2 * install_rate, 2) if include_installation else 0.0

            direct_cost = round(profile_material_cost + glass_cost + accessory_cost + drainage_fixed + led_cost + install_cost + transport_fixed, 2)
            waste_amount = round(direct_cost * (waste_pct / 100.0), 2)
            subtotal = round(direct_cost + waste_amount, 2)
            margin_amount = round(subtotal * (markup_pct / 100.0), 2)
            total = round(subtotal + margin_amount, 2)
            mdl_rate = cls._to_float(s.get("exchange_rate_usd_to_mdl"), 0.0)

            glass_panel_width_m = round(width_m / max(section_count, 1), 3) if width_m else 0.0
            glass_panel_length_m = rafter_len_m
            glass_panel_area_m2 = round(glass_panel_width_m * glass_panel_length_m, 3) if glass_panel_width_m and glass_panel_length_m else 0.0
            glass_panel_count = max(1, section_count * max(1, beam_count // 2))

            lines = [
                {"code": "AREA", "name": "Площадь изделия", "qty": area_m2, "unit": "m2", "unit_price": 0, "amount": 0},
                {"code": "FRAME_LEN", "name": "Длина профильной системы (оценка)", "qty": frame_length_m, "unit": "m", "unit_price": 0, "amount": 0},
                {"code": "PROFILE_KG", "name": "Профильная масса (оценка)", "qty": profile_weight_total_kg, "unit": "kg", "unit_price": round(profile_kg_rate, 2), "amount": profile_material_cost},
                {"code": "GLASS", "name": f"Стекло ({system_type})", "qty": area_m2, "unit": "m2", "unit_price": glass_rate, "amount": glass_cost},
                {"code": "ACCESSORY", "name": "Аксессуары и крепёж", "qty": accessory_units, "unit": "set", "unit_price": round(accessory_cost / accessory_units, 2) if accessory_units else 0, "amount": accessory_cost},
            ]
            if include_drainage:
                lines.append({"code": "DRAINAGE", "name": "Водоотвод / gutter set", "qty": 1, "unit": "set", "unit_price": drainage_fixed, "amount": drainage_fixed})
            if led_cost:
                lines.append({"code": "LED", "name": f"LED option ({led_option})", "qty": perimeter_m if led_option == 'white_led' else 1, "unit": "m" if led_option == "white_led" else "set", "unit_price": led_rate, "amount": led_cost})
            if include_installation:
                lines.append({"code": "INSTALL", "name": "Монтаж", "qty": area_m2, "unit": "m2", "unit_price": install_rate, "amount": install_cost})
            if include_transport:
                lines.append({"code": "TRANSPORT", "name": "Транспорт/логистика", "qty": 1, "unit": "job", "unit_price": transport_fixed, "amount": transport_fixed})
            lines.append({"code": "WASTE", "name": f"Тех. отходы {waste_pct:.1f}%", "qty": 1, "unit": "job", "unit_price": waste_amount, "amount": waste_amount})
            lines.append({"code": "MARGIN", "name": f"Маржа {markup_pct:.1f}%", "qty": 1, "unit": "job", "unit_price": margin_amount, "amount": margin_amount})

            # AI/manual batch-added extra items from text parsing (operator mode)
            extra_items = payload.get("extra_items")
            extras_total = 0.0
            if isinstance(extra_items, list):
                for idx, raw in enumerate(extra_items, start=1):
                    if not isinstance(raw, dict):
                        continue
                    code = str(raw.get("code") or f"AI-{idx:03d}").strip()[:80]
                    name = str(raw.get("name") or raw.get("name_ro") or raw.get("name_original") or code).strip()[:300]
                    qty = max(round(cls._to_float(raw.get("qty"), 0.0), 3), 0.0)
                    unit = str(raw.get("unit") or "pc").strip()[:20]
                    unit_price = round(cls._to_float(raw.get("unit_price"), 0.0), 2)
                    if qty <= 0:
                        continue
                    amount = round(unit_price * qty, 2)
                    extras_total += amount
                    lines.append({
                        "code": code,
                        "name": name + " [AI]",
                        "qty": qty,
                        "unit": unit,
                        "unit_price": unit_price,
                        "amount": amount,
                        "source": "ai_batch",
                        "image_url": str(raw.get("image_url") or "").strip(),
                        "category": str(raw.get("category") or "").strip(),
                    })

            if extras_total:
                # Recalculate commercial totals including extra items before waste/margin lines already added.
                # Existing lines include waste+margin calculated before extras, so recompute summary and replace their amounts.
                base_direct_without_waste_margin = direct_cost
                direct_cost = round(base_direct_without_waste_margin + extras_total, 2)
                waste_amount = round(direct_cost * (waste_pct / 100.0), 2)
                subtotal = round(direct_cost + waste_amount, 2)
                margin_amount = round(subtotal * (markup_pct / 100.0), 2)
                total = round(subtotal + margin_amount, 2)
                for line in lines:
                    if line.get("code") == "WASTE":
                        line["name"] = f"Тех. отходы {waste_pct:.1f}%"
                        line["unit_price"] = waste_amount
                        line["amount"] = waste_amount
                    elif line.get("code") == "MARGIN":
                        line["name"] = f"Маржа {markup_pct:.1f}%"
                        line["unit_price"] = margin_amount
                        line["amount"] = margin_amount

            return {
                "success": True,
                "data": {
                    "inputs": {
                        "width_mm": width_mm,
                        "projection_mm": projection_mm,
                        "front_height_mm": front_h_mm,
                        "rear_height_mm": rear_h_mm,
                        "system_type": system_type,
                        "led_option": led_option,
                        "include_installation": include_installation,
                        "include_transport": include_transport,
                        "include_drainage": include_drainage,
                        "extra_items_count": len(extra_items) if isinstance(extra_items, list) else 0,
                    },
                    "metrics": {
                        "area_m2": area_m2,
                        "perimeter_m": perimeter_m,
                        "slope_mm": slope_mm,
                        "slope_percent": slope_pct,
                        "post_count": post_count,
                        "section_count": section_count,
                        "beam_count": beam_count,
                        "rafter_length_m": rafter_len_m,
                        "frame_length_m": frame_length_m,
                        "profile_weight_total_kg": profile_weight_total_kg,
                        "glass_panel_count": glass_panel_count,
                        "glass_panel_area_m2": glass_panel_area_m2,
                        "glass_panel_width_m": glass_panel_width_m,
                        "glass_panel_length_m": glass_panel_length_m,
                    },
                    "lines": lines,
                    "summary": {
                        "currency": s.get("currency", "USD"),
                        "direct_cost": direct_cost,
                        "waste_amount": waste_amount,
                        "subtotal": subtotal,
                        "margin_amount": margin_amount,
                        "total": total,
                        "exchange_rate_usd_to_mdl": mdl_rate,
                        "total_mdl": round(total * mdl_rate, 2) if mdl_rate else None,
                        "extra_items_amount": round(extras_total, 2),
                    },
                }
            }

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

    @classmethod
    def get_orders(
        cls,
        status_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            rows = list(state.get("orders", []))
            if status_id:
                rows = [o for o in rows if int(o.get("status_id") or 0) == int(status_id)]
            if date_from:
                rows = [o for o in rows if str(o.get("created_at") or "")[:10] >= str(date_from)]
            if date_to:
                rows = [o for o in rows if str(o.get("created_at") or "")[:10] <= str(date_to)]
            if search:
                q = search.strip().lower()
                rows = [
                    o for o in rows
                    if q in str(o.get("order_number") or "").lower()
                    or q in str(o.get("barcode") or "").lower()
                    or q in str(o.get("client_name") or "").lower()
                    or q in str(o.get("client_phone") or "").lower()
                    or q in str(o.get("project_name") or "").lower()
                ]
            return {"success": True, "data": rows[: max(1, min(int(limit or 200), 1000))]}

    @classmethod
    def get_recent_orders(cls, limit: int = 20) -> Dict[str, Any]:
        return cls.get_orders(limit=limit)

    @classmethod
    def get_order_by_number(cls, number_or_barcode: str) -> Dict[str, Any]:
        q = (number_or_barcode or "").strip().lower()
        if not q:
            return {"success": False, "error": "Не указан номер заказа"}
        with cls._lock:
            state = cls._load()
            for o in state.get("orders", []):
                if q in (
                    str(o.get("order_number") or "").lower(),
                    str(o.get("barcode") or "").lower(),
                ):
                    return {"success": True, "data": o}
            return {"success": False, "error": "Заказ не найден"}

    @classmethod
    def get_order_by_id(cls, order_id: int) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            for o in state.get("orders", []):
                if int(o.get("id") or 0) == int(order_id):
                    return {"success": True, "data": o}
            return {"success": False, "error": "Заказ не найден"}

    @classmethod
    def update_order_status(cls, order_id: int, status_id: int) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            status = cls._status_by_id(state, status_id)
            if not status:
                return {"success": False, "error": "Статус не найден"}
            for o in state.get("orders", []):
                if int(o.get("id") or 0) == int(order_id):
                    o["status_id"] = status["id"]
                    o["status_code"] = status["code"]
                    o["status_name"] = status["name"]
                    o["updated_at"] = cls._now_iso()
                    cls._save(state)
                    return {"success": True, "data": o}
            return {"success": False, "error": "Заказ не найден"}

    @classmethod
    def get_statuses(cls) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            return {"success": True, "data": state.get("statuses", [])}

    @classmethod
    def report_by_day(cls, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        orders = cls.get_orders(date_from=date_from, date_to=date_to, limit=10000)
        if not orders.get("success"):
            return orders
        agg: Dict[str, Dict[str, Any]] = {}
        for o in orders.get("data", []):
            day = str(o.get("created_at") or "")[:10] or "unknown"
            row = agg.setdefault(day, {"date": day, "orders_count": 0, "total_amount": 0.0, "currency": o.get("currency") or "USD"})
            row["orders_count"] += 1
            row["total_amount"] = round(cls._to_float(row["total_amount"]) + cls._to_float(o.get("total_amount")), 2)
        data = [agg[k] for k in sorted(agg.keys(), reverse=True)]
        return {"success": True, "data": data}

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

    @classmethod
    def _calc_metraj(cls, basis: str, width_m: float, height_m: float) -> float:
        if basis == "perimeter":
            return round(2 * width_m + 2 * height_m, 3)
        elif basis == "width":
            return round(width_m, 3)
        elif basis == "area":
            return round(width_m * height_m, 3)
        return round(2 * width_m + 2 * height_m, 3)

    @classmethod
    def calculate_sliding_quote(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        with cls._lock:
            state = cls._load()
            s = state.get("sliding_settings", {})
            variants = state.get("sliding_variants", {})
            materials_list = state.get("sliding_materials", [])
            mat_by_code = {m["code"]: m for m in materials_list}

            variant_key = str(payload.get("variant") or "").strip()
            if variant_key not in variants:
                return {"success": False, "error": f"Unknown variant: {variant_key}"}
            variant = variants[variant_key]

            width_mm = max(cls._to_float(payload.get("width_mm")), 0.0)
            height_mm = max(cls._to_float(payload.get("height_mm")), 0.0)
            orientation = str(payload.get("orientation") or "left").lower()
            include_threshold = str(payload.get("include_threshold") or "N").upper() != "N"
            include_glass = str(payload.get("include_glass") or "Y").upper() != "N"
            glass_system = str(payload.get("glass_system") or "TEKCAM").upper()
            glass_finish = str(payload.get("glass_finish") or "transparent").lower()
            glass_thickness = str(payload.get("glass_thickness") or "10mm").lower()
            include_assembly = str(payload.get("include_assembly") or "N").upper() != "N"
            include_installation = str(payload.get("include_installation") or "N").upper() != "N"

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

            panels_str = str(variant.get("panels", "3"))
            is_double = variant.get("is_double", False)
            if "+" in panels_str:
                panels_per_side = int(panels_str.split("+")[0])
                total_panels = panels_per_side * 2
            else:
                total_panels = int(panels_str)
                panels_per_side = total_panels

            frame_offset_mm = 55 if not is_double else 110
            effective_width = width_mm - frame_offset_mm
            if is_double:
                panel_width_mm = effective_width / 2.0 / panels_per_side
            else:
                panel_width_mm = effective_width / total_panels

            lines = []
            profile_total_cost = 0.0
            profile_total_weight_kg = 0.0

            for code, pdef in variant.get("profiles", {}).items():
                mat = mat_by_code.get(code, {})
                unit_price_per_m = cls._to_float(mat.get("unit_price"), 0.0)
                weight_g_per_m = cls._to_float(mat.get("weight_g_per_m"), 0.0)
                if pdef.get("per_panel"):
                    offset = cls._to_float(pdef.get("length_offset_mm"), 0)
                    length_mm = panel_width_mm + offset
                    pieces = total_panels
                else:
                    pieces = int(pdef.get("pieces", 1))
                    basis = pdef.get("length_basis", "W")
                    base_mm = height_mm if basis == "H" else width_mm
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
                    "code": code, "name": mat.get("name", pdef.get("desc", code)),
                    "qty": pieces, "unit": "m", "length_m": length_m,
                    "total_length_m": total_length_m, "unit_price": unit_price_per_m,
                    "amount": cost, "category": "profile", "weight_kg": weight_kg,
                })

            for code, pdef in variant.get("optional_profiles", {}).items():
                if pdef.get("condition") == "threshold" and not include_threshold:
                    continue
                mat = mat_by_code.get(code, {})
                pieces = int(pdef.get("pieces", 1))
                length_mm = cls._to_float(pdef.get("length_mm"), 0)
                length_m = round(length_mm / 1000.0, 4)
                unit_price = cls._to_float(mat.get("unit_price"), 0.0)
                cost = round(length_m * pieces * unit_price, 2)
                profile_total_cost += cost
                lines.append({
                    "code": code, "name": mat.get("name", code), "qty": pieces, "unit": "m",
                    "length_m": length_m, "total_length_m": round(length_m * pieces, 4),
                    "unit_price": unit_price, "amount": cost, "category": "profile",
                })

            accessory_total_cost = 0.0
            for code, adef in variant.get("accessory_formulas", {}).items():
                if adef.get("condition") == "threshold" and not include_threshold:
                    continue
                mat = mat_by_code.get(code, {})
                qty = int(adef.get("qty", 0))
                if qty <= 0:
                    continue
                unit_price = cls._to_float(mat.get("unit_price"), 0.0)
                cost = round(qty * unit_price, 2)
                accessory_total_cost += cost
                lines.append({
                    "code": code, "name": mat.get("name", code), "qty": qty,
                    "unit": mat.get("unit", "buc"), "unit_price": unit_price,
                    "amount": cost, "category": "accessory",
                })

            glass_cost = 0.0
            if include_glass:
                grm = s.get("glass_rate_matrix", {})
                rate_key = f"{glass_finish}_{glass_thickness}"
                glass_rate = cls._to_float((grm.get(glass_system) or {}).get(rate_key), 0.0)
                glass_cost = round(area_m2 * glass_rate, 2)
                lines.append({
                    "code": "GLASS", "name": f"Sticlă {glass_system} {glass_finish} {glass_thickness}",
                    "qty": area_m2, "unit": "m2", "unit_price": glass_rate,
                    "amount": glass_cost, "category": "glass",
                })

            assembly_cost = 0.0
            if include_assembly:
                basis = s.get("assembly_basis", "perimeter")
                metraj = cls._calc_metraj(basis, width_m, height_m)
                rate = cls._to_float(s.get("assembly_rate"), 0.0)
                assembly_cost = round(metraj * rate, 2)
                lines.append({
                    "code": "ASSEMBLY", "name": f"Asamblare ({basis})",
                    "qty": metraj, "unit": "m" if basis != "area" else "m2",
                    "unit_price": rate, "amount": assembly_cost, "category": "service",
                })

            install_cost = 0.0
            if include_installation:
                basis = s.get("installation_basis", "perimeter")
                metraj = cls._calc_metraj(basis, width_m, height_m)
                rate = cls._to_float(s.get("installation_rate"), 0.0)
                install_cost = round(metraj * rate, 2)
                lines.append({
                    "code": "INSTALL", "name": f"Montaj ({basis})",
                    "qty": metraj, "unit": "m" if basis != "area" else "m2",
                    "unit_price": rate, "amount": install_cost, "category": "service",
                })

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
                        "variant": variant_key, "variant_label": variant.get("label", variant_key),
                        "family": variant.get("family"), "width_mm": width_mm, "height_mm": height_mm,
                        "orientation": orientation, "include_threshold": include_threshold,
                        "include_glass": include_glass, "glass_system": glass_system,
                        "glass_finish": glass_finish, "glass_thickness": glass_thickness,
                        "include_assembly": include_assembly, "include_installation": include_installation,
                    },
                    "metrics": {
                        "area_m2": area_m2, "perimeter_m": round(2 * width_m + 2 * height_m, 3),
                        "total_panels": total_panels, "panel_width_mm": round(panel_width_mm, 1),
                        "profile_weight_kg": round(profile_total_weight_kg, 2),
                    },
                    "lines": lines,
                    "summary": {
                        "currency": s.get("currency", "MDL"), "profile_cost": profile_total_cost,
                        "accessory_cost": accessory_total_cost, "glass_cost": glass_cost,
                        "assembly_cost": assembly_cost, "installation_cost": install_cost,
                        "direct_cost": direct_cost, "waste_amount": waste_amount,
                        "subtotal": subtotal, "margin_amount": margin_amount,
                        "total": total, "total_usd": round(total * mdl_to_usd, 2) if mdl_to_usd else None,
                    },
                }
            }

    @classmethod
    def calculate_sliding_cutting_list(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
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
                            "code": code, "name": mat.get("name", code), "panel_label": label,
                            "pieces": 1, "length_mm": length_mm, "length_cm": round(length_mm / 10.0, 2),
                            "weight_g_per_m": cls._to_float(mat.get("weight_g_per_m")),
                        })
                else:
                    offset = cls._to_float(pdef.get("length_offset_mm"), 0)
                    length_mm = round(panel_w + offset, 1)
                    cutting_lines.append({
                        "code": code, "name": mat.get("name", code), "panel_label": "all",
                        "pieces": total_panels, "length_mm": length_mm, "length_cm": round(length_mm / 10.0, 2),
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
                    "code": code, "name": mat.get("name", code), "panel_label": "-",
                    "pieces": pieces, "length_mm": length_mm, "length_cm": round(length_mm / 10.0, 2),
                    "weight_g_per_m": cls._to_float(mat.get("weight_g_per_m")),
                })

        return {
            "success": True,
            "data": {
                "variant_label": variant.get("label", variant_key),
                "width_mm": width_mm, "height_mm": height_mm,
                "total_panels": total_panels, "panel_width_mm": round(panel_w, 1),
                "cutting_lines": cutting_lines, "quote_summary": qd["summary"],
            }
        }

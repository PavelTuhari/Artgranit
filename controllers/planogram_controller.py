"""
Контроллер модуля «Планограммы» — управление выкладкой товара, зонами
торгового зала, проходимостью, акциями, задачами мерчандайзинга
и версионированием планограмм.

Мультиязычность: RU / RO / EN.
  * справочники и master-data хранят NAME_RU / NAME_RO / NAME_EN;
  * строки интерфейса живут в PLG_I18N;
  * контроллер сводит языковые колонки к одному ключу (`name`, `title`, …)
    по параметру lang — см. _localize().

Oracle-объекты: префикс PLG_
  sql/80_plg_tables.sql, 81_plg_views.sql, 82_plg_demo_data.sql, 83_plg_i18n.sql
Спецификация: docs/Planograms/PLANOGRAMS_MODULE.md
"""
import os
import sys
from typing import Any, Dict, List, Optional

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from flask import session

from models.database import DatabaseModel


class PlanogramController:
    """Модуль планограмм: карта зала, выкладка, проходимость, акции, задачи"""

    LANGS = ('ru', 'ro', 'en')
    DEFAULT_LANG = 'ru'

    # ==================== Инфраструктура ====================

    @staticmethod
    def lang(value: Optional[str]) -> str:
        """Нормализует код языка. Неизвестный язык -> язык по умолчанию."""
        code = (value or '').strip().lower()[:2]
        return code if code in PlanogramController.LANGS else PlanogramController.DEFAULT_LANG

    @staticmethod
    def _rows(result: Dict) -> List[Dict]:
        if not result.get("success") or not result.get("data"):
            return []
        cols = [c.lower() for c in (result.get("columns") or [])]
        return [dict(zip(cols, row)) for row in result["data"]]

    @staticmethod
    def _first(result: Dict) -> Optional[Dict]:
        rows = PlanogramController._rows(result)
        return rows[0] if rows else None

    @staticmethod
    def _localize(rows: List[Dict], lang: str) -> List[Dict]:
        """
        Добавляет к тройкам колонок `<base>_ru/_ro/_en` сводный ключ `<base>`
        на выбранном языке. Если перевода нет — подставляет русский вариант.
        Исходные языковые колонки сохраняются: они нужны формам редактирования,
        где оператор правит все три языка сразу.
        """
        suffixes = tuple('_' + code for code in PlanogramController.LANGS)
        out = []
        for row in rows:
            bases = {k[:-3] for k in row if k.endswith(suffixes)}
            new = dict(row)
            for base in bases:
                value = row.get(base + '_' + lang)
                if value in (None, ''):
                    value = row.get(base + '_ru')
                new[base] = value
            out.append(new)
        return out

    @staticmethod
    def _localized(result: Dict, lang: str) -> List[Dict]:
        return PlanogramController._localize(PlanogramController._rows(result), lang)

    @staticmethod
    def _username() -> str:
        return session.get('username', 'system') if session else 'system'

    @staticmethod
    def _fail(result: Dict) -> Dict:
        return {"success": False, "error": result.get("message") or "Ошибка выполнения запроса"}

    @staticmethod
    def _audit(action: str, entity_type: str, entity_id: Optional[int], details: str = "") -> None:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "INSERT INTO PLG_EVENT_LOG (ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME) "
                    "VALUES (:p_action, :p_etype, :p_eid, :p_details, :p_user)",
                    {"p_action": action[:50], "p_etype": entity_type[:30], "p_eid": entity_id,
                     "p_details": (details or "")[:2000], "p_user": PlanogramController._username()}
                )
                db.connection.commit()
        except Exception:
            pass

    @staticmethod
    def _multilang_params(data: Dict, field: str, prefix: str, required: bool = False) -> Dict:
        """
        Готовит bind-параметры для тройки языковых колонок.
        Принимает либо `field` (одно значение -> во все языки, если пусто),
        либо `field_ru` / `field_ro` / `field_en`.
        """
        base = data.get(field)
        values = {}
        for code in PlanogramController.LANGS:
            values[code] = data.get(f"{field}_{code}") or (base if code == 'ru' else None)
        if required and not values['ru']:
            values['ru'] = base or values['ro'] or values['en']
        return {f"{prefix}_{code}": values[code] for code in PlanogramController.LANGS}

    # ==================== Языки и словарь интерфейса ====================

    @staticmethod
    def get_langs(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, IS_DEFAULT, SORT_ORDER "
                    "FROM PLG_REF_LANGS ORDER BY SORT_ORDER"
                )
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_i18n(lang: str = DEFAULT_LANG) -> Dict:
        """Словарь строк интерфейса: {msg_key: text} на выбранном языке."""
        lang = PlanogramController.lang(lang)
        column = {'ru': 'TEXT_RU', 'ro': 'TEXT_RO', 'en': 'TEXT_EN'}[lang]
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    f"SELECT MSG_KEY, NVL({column}, TEXT_RU) AS TXT FROM PLG_I18N ORDER BY MSG_KEY"
                )
                if not r.get("success"):
                    return PlanogramController._fail(r)
                data = {row["msg_key"]: row["txt"] for row in PlanogramController._rows(r)}
                return {"success": True, "data": data, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Справочники ====================

    @staticmethod
    def get_refs(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        queries = {
            "langs":         "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, IS_DEFAULT FROM PLG_REF_LANGS ORDER BY SORT_ORDER",
            "zone_types":    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON, IS_SELLING FROM PLG_REF_ZONE_TYPES ORDER BY SORT_ORDER",
            "fixture_types": "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, DEFAULT_W_MM, DEFAULT_H_MM, DEFAULT_D_MM, SHELF_COUNT, ICON FROM PLG_REF_FIXTURE_TYPES ORDER BY SORT_ORDER",
            "plg_statuses":  "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, COLOR, IS_FINAL FROM PLG_REF_PLG_STATUSES ORDER BY SORT_ORDER",
            "task_types":    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, ICON FROM PLG_REF_TASK_TYPES ORDER BY SORT_ORDER",
            "promo_types":   "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, COLOR FROM PLG_REF_PROMO_TYPES ORDER BY SORT_ORDER",
            "doc_types":     "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, ICON FROM PLG_REF_DOC_TYPES ORDER BY SORT_ORDER",
            "categories":    "SELECT ID, CODE, PARENT_ID, NAME_RU, NAME_RO, NAME_EN, COLOR, ICON FROM PLG_CATEGORIES WHERE STATUS = 'active' ORDER BY SORT_ORDER",
        }
        data: Dict[str, Any] = {}
        try:
            with DatabaseModel() as db:
                for key, sql in queries.items():
                    data[key] = PlanogramController._localized(db.execute_query(sql), lang)
            return {"success": True, "data": data, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Магазины ====================

    @staticmethod
    def get_stores(lang: str = DEFAULT_LANG, dataset_id: Optional[int] = None) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = ("SELECT s.ID, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN, s.CITY, "
               "s.ADDRESS_RU, s.ADDRESS_RO, s.ADDRESS_EN, s.AREA_SQM, s.MAP_WIDTH, s.MAP_HEIGHT, "
               "s.CHECKOUT_QTY, s.MANAGER_NAME, s.STATUS, s.STORE_FORMAT, s.DATASET_ID, "
               "(SELECT COUNT(*) FROM PLG_ZONES z WHERE z.STORE_ID = s.ID) AS ZONE_COUNT "
               "FROM PLG_STORES s WHERE s.STATUS <> 'inactive'")
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND s.DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY ZONE_COUNT DESC, s.CODE", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _resolve_store(db: DatabaseModel, store_id: Optional[int]) -> Optional[int]:
        """
        Возвращает переданный магазин либо магазин по умолчанию — тот, у которого
        уже размечены зоны зала (пустой магазин показывать бессмысленно).
        """
        if store_id:
            return int(store_id)
        r = db.execute_query(
            "SELECT s.ID FROM PLG_STORES s WHERE s.STATUS = 'active' "
            "ORDER BY (SELECT COUNT(*) FROM PLG_ZONES z WHERE z.STORE_ID = s.ID) DESC, s.ID "
            "FETCH FIRST 1 ROWS ONLY")
        row = PlanogramController._first(r)
        return row.get("id") if row else None

    # ==================== Дашборд «Обзор» ====================

    @staticmethod
    def get_dashboard(store_id: Optional[int] = None, lang: str = DEFAULT_LANG, days: int = 14) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            days = max(1, min(int(days or 14), 90))
        except (TypeError, ValueError):
            days = 14
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                if not sid:
                    return {"success": True, "data": {"store": None, "stats": {}, "metrics": [],
                                                      "categories": [], "promos": [], "notifications": []},
                            "lang": lang}

                stats = PlanogramController._first(db.execute_query(
                    "SELECT * FROM V_PLG_DASHBOARD_STATS WHERE STORE_ID = :p_store",
                    {"p_store": sid}))
                stats = (PlanogramController._localize([stats], lang)[0] if stats else {})

                metrics = PlanogramController._rows(db.execute_query(
                    "SELECT * FROM V_PLG_STORE_METRICS WHERE STORE_ID = :p_store "
                    "AND METRIC_DATE >= TRUNC(SYSDATE) - :p_days ORDER BY METRIC_DATE",
                    {"p_store": sid, "p_days": days}))

                categories = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_TOP_CATEGORIES WHERE STORE_ID = :p_store "
                    "AND METRIC_DATE = (SELECT MAX(METRIC_DATE) FROM PLG_CATEGORY_METRICS "
                    "                    WHERE STORE_ID = :p_store) "
                    "AND RANK_NO <= 5 ORDER BY RANK_NO",
                    {"p_store": sid}), lang)

                promos = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_PROMOS WHERE STORE_ID = :p_store "
                    "AND EFFECTIVE_STATUS = 'active' ORDER BY DATE_TO",
                    {"p_store": sid}), lang)

                notifications = PlanogramController._localized(db.execute_query(
                    "SELECT ID, STORE_ID, LEVEL_CODE, ENTITY_TYPE, ENTITY_ID, "
                    "TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT "
                    "FROM PLG_NOTIFICATIONS WHERE STORE_ID = :p_store "
                    "ORDER BY CREATED_AT DESC FETCH FIRST 20 ROWS ONLY",
                    {"p_store": sid}), lang)

                return {"success": True, "lang": lang, "data": {
                    "store_id": sid,
                    "stats": stats,
                    "metrics": metrics,
                    "categories": categories,
                    "promos": promos,
                    "notifications": notifications,
                }}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== План магазина ====================

    @staticmethod
    def get_store_map(store_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        """Зоны и оборудование магазина в координатах карты + габариты сетки."""
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                if not sid:
                    return {"success": True, "data": {"store": None, "zones": [], "fixtures": []}, "lang": lang}

                store = PlanogramController._first(db.execute_query(
                    "SELECT ID, CODE, NAME_RU, NAME_RO, NAME_EN, CITY, ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, "
                    "AREA_SQM, MAP_WIDTH, MAP_HEIGHT, CHECKOUT_QTY, MANAGER_NAME "
                    "FROM PLG_STORES WHERE ID = :p_store", {"p_store": sid}))
                store = PlanogramController._localize([store], lang)[0] if store else None

                zones = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_ZONES WHERE STORE_ID = :p_store AND STATUS = 'active' "
                    "ORDER BY SORT_ORDER", {"p_store": sid}), lang)

                fixtures = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_FIXTURES WHERE STORE_ID = :p_store AND STATUS <> 'decommissioned' "
                    "ORDER BY CODE", {"p_store": sid}), lang)

                return {"success": True, "lang": lang,
                        "data": {"store": store, "zones": zones, "fixtures": fixtures}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Зоны ====================

    @staticmethod
    def get_zones(store_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                r = db.execute_query(
                    "SELECT * FROM V_PLG_ZONES WHERE STORE_ID = :p_store ORDER BY SORT_ORDER",
                    {"p_store": sid})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_zone(data: Dict, zone_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_type": data.get("zone_type") or "dept",
            "p_cat": data.get("category_id") or None,
            "p_x": data.get("pos_x") or 0,
            "p_y": data.get("pos_y") or 0,
            "p_w": data.get("width") or 72,
            "p_h": data.get("height") or 55,
            "p_color": data.get("color"),
            "p_area": data.get("area_sqm"),
            "p_sort": data.get("sort_order") or 0,
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_name_ru"]:
            return {"success": False, "error": "Не указано название зоны"}
        try:
            with DatabaseModel() as db:
                if zone_id:
                    params["p_id"] = int(zone_id)
                    r = db.execute_query(
                        "UPDATE PLG_ZONES SET CODE = :p_code, ZONE_TYPE = :p_type, CATEGORY_ID = :p_cat, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        "POS_X = :p_x, POS_Y = :p_y, WIDTH = :p_w, HEIGHT = :p_h, COLOR = :p_color, "
                        "AREA_SQM = :p_area, SORT_ORDER = :p_sort WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_ZONES (STORE_ID, CODE, ZONE_TYPE, CATEGORY_ID, "
                        "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, COLOR, AREA_SQM, SORT_ORDER) "
                        "VALUES (:p_store, :p_code, :p_type, :p_cat, :p_name_ru, :p_name_ro, :p_name_en, "
                        ":p_x, :p_y, :p_w, :p_h, :p_color, :p_area, :p_sort)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if zone_id else "create", "zone", zone_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_zone(zone_id: int) -> Dict:
        return PlanogramController._delete("PLG_ZONES", zone_id, "zone")

    # ==================== Оборудование ====================

    @staticmethod
    def get_fixtures(store_id: Optional[int] = None, zone_id: Optional[int] = None,
                     lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                sql = "SELECT * FROM V_PLG_FIXTURES WHERE STORE_ID = :p_store"
                params: Dict[str, Any] = {"p_store": sid}
                if zone_id:
                    sql += " AND ZONE_ID = :p_zone"
                    params["p_zone"] = int(zone_id)
                r = db.execute_query(sql + " ORDER BY CODE", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_fixture(data: Dict, fixture_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_zone": data.get("zone_id") or None,
            "p_code": (data.get("code") or "").strip(),
            "p_type": data.get("fixture_type") or "shelf",
            "p_x": data.get("pos_x") or 0,
            "p_y": data.get("pos_y") or 0,
            "p_w": data.get("width") or 80,
            "p_h": data.get("height") or 42,
            "p_orient": data.get("orientation") or "H",
            "p_shelves": data.get("shelf_count") or 4,
            "p_wmm": data.get("width_mm") or 1000,
            "p_hmm": data.get("height_mm") or 1800,
            "p_dmm": data.get("depth_mm") or 500,
            "p_serial": data.get("serial_number"),
            "p_status": data.get("status") or "active",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name"))
        if not params["p_code"]:
            return {"success": False, "error": "Не указан код оборудования"}
        try:
            with DatabaseModel() as db:
                if fixture_id:
                    params["p_id"] = int(fixture_id)
                    r = db.execute_query(
                        "UPDATE PLG_FIXTURES SET ZONE_ID = :p_zone, CODE = :p_code, FIXTURE_TYPE = :p_type, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        "POS_X = :p_x, POS_Y = :p_y, WIDTH = :p_w, HEIGHT = :p_h, ORIENTATION = :p_orient, "
                        "SHELF_COUNT = :p_shelves, WIDTH_MM = :p_wmm, HEIGHT_MM = :p_hmm, DEPTH_MM = :p_dmm, "
                        "SERIAL_NUMBER = :p_serial, STATUS = :p_status WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, "
                        "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, "
                        "SHELF_COUNT, WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER, STATUS) "
                        "VALUES (:p_store, :p_zone, :p_code, :p_type, :p_name_ru, :p_name_ro, :p_name_en, "
                        ":p_x, :p_y, :p_w, :p_h, :p_orient, :p_shelves, :p_wmm, :p_hmm, :p_dmm, "
                        ":p_serial, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if fixture_id else "create", "fixture", fixture_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_fixture(fixture_id: int) -> Dict:
        return PlanogramController._delete("PLG_FIXTURES", fixture_id, "fixture")

    # ==================== Товары ====================

    @staticmethod
    def get_products(category_id: Optional[int] = None, search: Optional[str] = None,
                     lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_PRODUCTS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if category_id:
            sql += " AND CATEGORY_ID = :p_cat"
            params["p_cat"] = int(category_id)
        if search:
            sql += (" AND (UPPER(CODE) LIKE :p_q OR UPPER(NAME_RU) LIKE :p_q "
                    "OR UPPER(NAME_RO) LIKE :p_q OR UPPER(NAME_EN) LIKE :p_q OR BARCODE LIKE :p_q)")
            params["p_q"] = f"%{search.strip().upper()}%"
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY CODE FETCH FIRST 500 ROWS ONLY", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_product(data: Dict, product_id: Optional[int] = None) -> Dict:
        params = {
            "p_code": (data.get("code") or "").strip(),
            "p_cat": data.get("category_id") or None,
            "p_barcode": data.get("barcode"),
            "p_brand": data.get("brand"),
            "p_uom": data.get("uom") or "pcs",
            "p_price": data.get("price"),
            "p_curr": data.get("currency") or "MDL",
            "p_wmm": data.get("width_mm") or 80,
            "p_hmm": data.get("height_mm") or 200,
            "p_dmm": data.get("depth_mm") or 60,
            "p_minf": data.get("min_facings") or 1,
            "p_img": data.get("image_url"),
            "p_status": data.get("status") or "active",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код и название товара обязательны"}
        try:
            with DatabaseModel() as db:
                if product_id:
                    params["p_id"] = int(product_id)
                    r = db.execute_query(
                        "UPDATE PLG_PRODUCTS SET CODE = :p_code, CATEGORY_ID = :p_cat, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        "BARCODE = :p_barcode, BRAND = :p_brand, UOM = :p_uom, PRICE = :p_price, "
                        "CURRENCY = :p_curr, WIDTH_MM = :p_wmm, HEIGHT_MM = :p_hmm, DEPTH_MM = :p_dmm, "
                        "MIN_FACINGS = :p_minf, IMAGE_URL = :p_img, STATUS = :p_status WHERE ID = :p_id",
                        params)
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_PRODUCTS (CODE, CATEGORY_ID, NAME_RU, NAME_RO, NAME_EN, "
                        "BARCODE, BRAND, UOM, PRICE, CURRENCY, WIDTH_MM, HEIGHT_MM, DEPTH_MM, "
                        "MIN_FACINGS, IMAGE_URL, STATUS) "
                        "VALUES (:p_code, :p_cat, :p_name_ru, :p_name_ro, :p_name_en, :p_barcode, "
                        ":p_brand, :p_uom, :p_price, :p_curr, :p_wmm, :p_hmm, :p_dmm, :p_minf, "
                        ":p_img, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if product_id else "create", "product", product_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_product(product_id: int) -> Dict:
        return PlanogramController._delete("PLG_PRODUCTS", product_id, "product")

    # ==================== Планограммы ====================

    @staticmethod
    def get_planograms(store_id: Optional[int] = None, status: Optional[str] = None,
                       zone_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                sql = "SELECT * FROM V_PLG_PLANOGRAMS WHERE STORE_ID = :p_store"
                params: Dict[str, Any] = {"p_store": sid}
                if status:
                    sql += " AND STATUS = :p_status"
                    params["p_status"] = status
                if zone_id:
                    sql += " AND ZONE_ID = :p_zone"
                    params["p_zone"] = int(zone_id)
                r = db.execute_query(sql + " ORDER BY UPDATED_AT DESC", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_planogram(planogram_id: int, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                head = PlanogramController._first(db.execute_query(
                    "SELECT * FROM V_PLG_PLANOGRAMS WHERE ID = :p_id", {"p_id": int(planogram_id)}))
                if not head:
                    return {"success": False, "error": "Планограмма не найдена"}
                items = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_PLANOGRAM_ITEMS WHERE PLANOGRAM_ID = :p_id "
                    "ORDER BY FIXTURE_CODE, SHELF_NO, POSITION_NO", {"p_id": int(planogram_id)}), lang)
                history = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_HISTORY WHERE PLANOGRAM_ID = :p_id "
                    "ORDER BY CHANGED_AT DESC", {"p_id": int(planogram_id)}), lang)
                data = PlanogramController._localize([head], lang)[0]
                data["items"] = items
                data["history"] = history
                return {"success": True, "data": data, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_planogram(data: Dict, planogram_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_zone": data.get("zone_id") or None,
            "p_status": data.get("status") or "draft",
            "p_from": data.get("valid_from") or None,
            "p_to": data.get("valid_to") or None,
            "p_author": data.get("author") or PlanogramController._username(),
            "p_notes": data.get("notes"),
            "p_share": data.get("shelf_share_pct"),
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_name_ru"]:
            return {"success": False, "error": "Не указано название планограммы"}
        date_expr_from = "TO_DATE(:p_from, 'YYYY-MM-DD')"
        date_expr_to = "TO_DATE(:p_to, 'YYYY-MM-DD')"
        try:
            with DatabaseModel() as db:
                if planogram_id:
                    params["p_id"] = int(planogram_id)
                    r = db.execute_query(
                        "UPDATE PLG_PLANOGRAMS SET ZONE_ID = :p_zone, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        f"STATUS = :p_status, VALID_FROM = {date_expr_from}, VALID_TO = {date_expr_to}, "
                        "AUTHOR = :p_author, NOTES = :p_notes, SHELF_SHARE_PCT = :p_share, "
                        "VERSION_NO = VERSION_NO + 1 WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                    new_id = int(planogram_id)
                    action = "updated"
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_PLANOGRAMS (STORE_ID, ZONE_ID, NAME_RU, NAME_RO, NAME_EN, "
                        f"STATUS, VALID_FROM, VALID_TO, AUTHOR, NOTES, SHELF_SHARE_PCT) "
                        f"VALUES (:p_store, :p_zone, :p_name_ru, :p_name_ro, :p_name_en, :p_status, "
                        f"{date_expr_from}, {date_expr_to}, :p_author, :p_notes, :p_share)", params)
                    new_id = None
                    action = "created"
                if not r.get("success"):
                    return PlanogramController._fail(r)

                if new_id is None:
                    row = PlanogramController._first(db.execute_query(
                        "SELECT MAX(ID) AS ID FROM PLG_PLANOGRAMS"))
                    new_id = row.get("id") if row else None

                db.execute_query(
                    "INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, "
                    "SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY) "
                    "SELECT ID, VERSION_NO, :p_action, :p_sru, :p_sro, :p_sen, :p_user "
                    "FROM PLG_PLANOGRAMS WHERE ID = :p_id",
                    {"p_action": action, "p_id": new_id, "p_user": PlanogramController._username(),
                     "p_sru": "Планограмма создана" if action == "created" else "Планограмма изменена",
                     "p_sro": "Planogramă creată" if action == "created" else "Planogramă modificată",
                     "p_sen": "Planogram created" if action == "created" else "Planogram updated"})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit(action, "planogram", new_id, params["p_name_ru"])
        return {"success": True, "id": new_id}

    @staticmethod
    def set_planogram_status(planogram_id: int, status: str) -> Dict:
        allowed = {"draft", "review", "approved", "active", "rejected", "archived"}
        if status not in allowed:
            return {"success": False, "error": f"Недопустимый статус: {status}"}
        user = PlanogramController._username()
        try:
            with DatabaseModel() as db:
                old = PlanogramController._first(db.execute_query(
                    "SELECT STATUS, VERSION_NO FROM PLG_PLANOGRAMS WHERE ID = :p_id",
                    {"p_id": int(planogram_id)}))
                if not old:
                    return {"success": False, "error": "Планограмма не найдена"}
                r = db.execute_query(
                    "UPDATE PLG_PLANOGRAMS SET STATUS = :p_status, "
                    "APPROVED_BY = CASE WHEN :p_status IN ('approved','active') THEN :p_user ELSE APPROVED_BY END, "
                    "APPROVED_AT = CASE WHEN :p_status IN ('approved','active') THEN SYSTIMESTAMP ELSE APPROVED_AT END "
                    "WHERE ID = :p_id",
                    {"p_status": status, "p_user": user, "p_id": int(planogram_id)})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.execute_query(
                    "INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, FIELD_NAME, "
                    "OLD_VALUE, NEW_VALUE, SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY) "
                    "VALUES (:p_id, :p_ver, 'status_change', 'STATUS', :p_old, :p_new, "
                    ":p_sru, :p_sro, :p_sen, :p_user)",
                    {"p_id": int(planogram_id), "p_ver": old.get("version_no"),
                     "p_old": old.get("status"), "p_new": status, "p_user": user,
                     "p_sru": f"Статус изменён: {old.get('status')} → {status}",
                     "p_sro": f"Status modificat: {old.get('status')} → {status}",
                     "p_sen": f"Status changed: {old.get('status')} → {status}"})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("status_change", "planogram", int(planogram_id), status)
        return {"success": True}

    @staticmethod
    def delete_planogram(planogram_id: int) -> Dict:
        return PlanogramController._delete("PLG_PLANOGRAMS", planogram_id, "planogram")

    # ==================== Позиции планограммы ====================

    @staticmethod
    def save_planogram_item(planogram_id: int, data: Dict, item_id: Optional[int] = None) -> Dict:
        params = {
            "p_plg": int(planogram_id),
            "p_fixt": data.get("fixture_id") or None,
            "p_prod": data.get("product_id"),
            "p_shelf": data.get("shelf_no") or 1,
            "p_pos": data.get("position_no") or 1,
            "p_fac": data.get("facings") or 1,
            "p_depth": data.get("depth_qty") or 1,
            "p_xmm": data.get("x_mm"),
            "p_wmm": data.get("width_mm"),
            "p_promo": 1 if data.get("is_promo") else 0,
            "p_notes": data.get("notes"),
        }
        if not params["p_prod"]:
            return {"success": False, "error": "Не указан товар"}
        try:
            with DatabaseModel() as db:
                if item_id:
                    params["p_id"] = int(item_id)
                    r = db.execute_query(
                        "UPDATE PLG_PLANOGRAM_ITEMS SET FIXTURE_ID = :p_fixt, PRODUCT_ID = :p_prod, "
                        "SHELF_NO = :p_shelf, POSITION_NO = :p_pos, FACINGS = :p_fac, "
                        "DEPTH_QTY = :p_depth, X_MM = :p_xmm, WIDTH_MM = :p_wmm, IS_PROMO = :p_promo, "
                        "NOTES = :p_notes WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_plg"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_PLANOGRAM_ITEMS (PLANOGRAM_ID, FIXTURE_ID, PRODUCT_ID, "
                        "SHELF_NO, POSITION_NO, FACINGS, DEPTH_QTY, X_MM, WIDTH_MM, IS_PROMO, NOTES) "
                        "VALUES (:p_plg, :p_fixt, :p_prod, :p_shelf, :p_pos, :p_fac, :p_depth, "
                        ":p_xmm, :p_wmm, :p_promo, :p_notes)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.execute_query(
                    "INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, "
                    "SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY) "
                    "SELECT ID, VERSION_NO, :p_action, :p_sru, :p_sro, :p_sen, :p_user "
                    "FROM PLG_PLANOGRAMS WHERE ID = :p_id",
                    {"p_action": "item_updated" if item_id else "item_added",
                     "p_id": int(planogram_id), "p_user": PlanogramController._username(),
                     "p_sru": "Изменена позиция выкладки" if item_id else "Добавлена позиция выкладки",
                     "p_sro": "Poziție de expunere modificată" if item_id else "Poziție de expunere adăugată",
                     "p_sen": "Layout item updated" if item_id else "Layout item added"})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("item_save", "planogram_item", item_id, f"planogram={planogram_id}")
        return {"success": True}

    @staticmethod
    def delete_planogram_item(item_id: int) -> Dict:
        return PlanogramController._delete("PLG_PLANOGRAM_ITEMS", item_id, "planogram_item")

    # ==================== История изменений ====================

    @staticmethod
    def get_history(store_id: Optional[int] = None, planogram_id: Optional[int] = None,
                    limit: int = 200, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            limit = max(1, min(int(limit or 200), 1000))
        except (TypeError, ValueError):
            limit = 200
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_PLG_HISTORY WHERE 1 = 1"
                params: Dict[str, Any] = {}
                if planogram_id:
                    sql += " AND PLANOGRAM_ID = :p_plg"
                    params["p_plg"] = int(planogram_id)
                else:
                    sid = PlanogramController._resolve_store(db, store_id)
                    sql += " AND STORE_ID = :p_store"
                    params["p_store"] = sid
                sql += f" ORDER BY CHANGED_AT DESC FETCH FIRST {limit} ROWS ONLY"
                r = db.execute_query(sql, params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Акции ====================

    @staticmethod
    def get_promos(store_id: Optional[int] = None, only_active: bool = False,
                   lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                sql = "SELECT * FROM V_PLG_PROMOS WHERE STORE_ID = :p_store"
                if only_active:
                    sql += " AND EFFECTIVE_STATUS = 'active'"
                r = db.execute_query(sql + " ORDER BY DATE_FROM DESC", {"p_store": sid})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_promo(data: Dict, promo_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_type": data.get("promo_type") or "discount",
            "p_label": data.get("label"),
            "p_disc": data.get("discount_pct"),
            "p_from": data.get("date_from"),
            "p_to": data.get("date_to"),
            "p_color": data.get("color"),
            "p_status": data.get("status") or "planned",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_from"] or not params["p_to"]:
            return {"success": False, "error": "Код акции и период обязательны"}
        try:
            with DatabaseModel() as db:
                if promo_id:
                    params["p_id"] = int(promo_id)
                    r = db.execute_query(
                        "UPDATE PLG_PROMOS SET CODE = :p_code, PROMO_TYPE = :p_type, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        "LABEL = :p_label, DISCOUNT_PCT = :p_disc, "
                        "DATE_FROM = TO_DATE(:p_from, 'YYYY-MM-DD'), DATE_TO = TO_DATE(:p_to, 'YYYY-MM-DD'), "
                        "COLOR = :p_color, STATUS = :p_status WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_PROMOS (CODE, STORE_ID, PROMO_TYPE, NAME_RU, NAME_RO, NAME_EN, "
                        "LABEL, DISCOUNT_PCT, DATE_FROM, DATE_TO, COLOR, STATUS) "
                        "VALUES (:p_code, :p_store, :p_type, :p_name_ru, :p_name_ro, :p_name_en, "
                        ":p_label, :p_disc, TO_DATE(:p_from, 'YYYY-MM-DD'), TO_DATE(:p_to, 'YYYY-MM-DD'), "
                        ":p_color, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if promo_id else "create", "promo", promo_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_promo(promo_id: int) -> Dict:
        return PlanogramController._delete("PLG_PROMOS", promo_id, "promo")

    # ==================== Задачи ====================

    @staticmethod
    def get_tasks(store_id: Optional[int] = None, status: Optional[str] = None,
                  lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                sql = "SELECT * FROM V_PLG_TASKS WHERE STORE_ID = :p_store"
                params: Dict[str, Any] = {"p_store": sid}
                if status == "open":
                    sql += " AND STATUS NOT IN ('done','cancelled')"
                elif status:
                    sql += " AND STATUS = :p_status"
                    params["p_status"] = status
                r = db.execute_query(sql + " ORDER BY IS_OVERDUE DESC, DUE_DATE, CREATED_AT DESC", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_task(data: Dict, task_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_zone": data.get("zone_id") or None,
            "p_plg": data.get("planogram_id") or None,
            "p_type": data.get("task_type") or "relayout",
            "p_descr": data.get("description"),
            "p_prio": data.get("priority") or "medium",
            "p_status": data.get("status") or "new",
            "p_assignee": data.get("assignee"),
            "p_due": data.get("due_date") or None,
        }
        params.update(PlanogramController._multilang_params(data, "title", "p_title", required=True))
        if not params["p_title_ru"]:
            return {"success": False, "error": "Не указано название задачи"}
        try:
            with DatabaseModel() as db:
                if task_id:
                    params["p_id"] = int(task_id)
                    r = db.execute_query(
                        "UPDATE PLG_TASKS SET ZONE_ID = :p_zone, PLANOGRAM_ID = :p_plg, TASK_TYPE = :p_type, "
                        "TITLE_RU = :p_title_ru, TITLE_RO = :p_title_ro, TITLE_EN = :p_title_en, "
                        "DESCRIPTION = :p_descr, PRIORITY = :p_prio, STATUS = :p_status, "
                        "ASSIGNEE = :p_assignee, DUE_DATE = TO_DATE(:p_due, 'YYYY-MM-DD'), "
                        "DONE_AT = CASE WHEN :p_status = 'done' THEN NVL(DONE_AT, SYSTIMESTAMP) ELSE NULL END "
                        "WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                else:
                    params["p_user"] = PlanogramController._username()
                    r = db.execute_query(
                        "INSERT INTO PLG_TASKS (STORE_ID, ZONE_ID, PLANOGRAM_ID, TASK_TYPE, "
                        "TITLE_RU, TITLE_RO, TITLE_EN, DESCRIPTION, PRIORITY, STATUS, ASSIGNEE, "
                        "DUE_DATE, CREATED_BY) "
                        "VALUES (:p_store, :p_zone, :p_plg, :p_type, :p_title_ru, :p_title_ro, :p_title_en, "
                        ":p_descr, :p_prio, :p_status, :p_assignee, TO_DATE(:p_due, 'YYYY-MM-DD'), :p_user)",
                        params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if task_id else "create", "task", task_id, params["p_title_ru"])
        return {"success": True}

    @staticmethod
    def delete_task(task_id: int) -> Dict:
        return PlanogramController._delete("PLG_TASKS", task_id, "task")

    # ==================== Документы ====================

    @staticmethod
    def get_documents(store_id: Optional[int] = None, planogram_id: Optional[int] = None,
                      lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM V_PLG_DOCUMENTS WHERE 1 = 1"
                params: Dict[str, Any] = {}
                if planogram_id:
                    sql += " AND PLANOGRAM_ID = :p_plg"
                    params["p_plg"] = int(planogram_id)
                else:
                    sid = PlanogramController._resolve_store(db, store_id)
                    sql += " AND STORE_ID = :p_store"
                    params["p_store"] = sid
                r = db.execute_query(sql + " ORDER BY CREATED_AT DESC", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_document(data: Dict, document_id: Optional[int] = None) -> Dict:
        params = {
            "p_store": data.get("store_id"),
            "p_plg": data.get("planogram_id") or None,
            "p_type": data.get("doc_type") or "instruction",
            "p_file": data.get("file_name"),
            "p_mime": data.get("mime_type"),
            "p_url": data.get("file_url"),
            "p_size": data.get("file_size_kb"),
            "p_ver": data.get("version_no") or 1,
        }
        params.update(PlanogramController._multilang_params(data, "title", "p_title", required=True))
        if not params["p_title_ru"]:
            return {"success": False, "error": "Не указано название документа"}
        try:
            with DatabaseModel() as db:
                if document_id:
                    params["p_id"] = int(document_id)
                    r = db.execute_query(
                        "UPDATE PLG_DOCUMENTS SET PLANOGRAM_ID = :p_plg, DOC_TYPE = :p_type, "
                        "TITLE_RU = :p_title_ru, TITLE_RO = :p_title_ro, TITLE_EN = :p_title_en, "
                        "FILE_NAME = :p_file, MIME_TYPE = :p_mime, FILE_URL = :p_url, "
                        "FILE_SIZE_KB = :p_size, VERSION_NO = :p_ver WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_store"})
                else:
                    params["p_user"] = PlanogramController._username()
                    r = db.execute_query(
                        "INSERT INTO PLG_DOCUMENTS (STORE_ID, PLANOGRAM_ID, DOC_TYPE, "
                        "TITLE_RU, TITLE_RO, TITLE_EN, FILE_NAME, MIME_TYPE, FILE_URL, "
                        "FILE_SIZE_KB, VERSION_NO, CREATED_BY) "
                        "VALUES (:p_store, :p_plg, :p_type, :p_title_ru, :p_title_ro, :p_title_en, "
                        ":p_file, :p_mime, :p_url, :p_size, :p_ver, :p_user)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if document_id else "create", "document", document_id,
                                   params["p_title_ru"])
        return {"success": True}

    @staticmethod
    def delete_document(document_id: int) -> Dict:
        return PlanogramController._delete("PLG_DOCUMENTS", document_id, "document")

    # ==================== Уведомления ====================

    @staticmethod
    def get_notifications(store_id: Optional[int] = None, unread_only: bool = False,
                          lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                sql = ("SELECT ID, STORE_ID, LEVEL_CODE, ENTITY_TYPE, ENTITY_ID, "
                       "TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT "
                       "FROM PLG_NOTIFICATIONS WHERE STORE_ID = :p_store")
                if unread_only:
                    sql += " AND IS_READ = 0"
                r = db.execute_query(sql + " ORDER BY CREATED_AT DESC FETCH FIRST 200 ROWS ONLY",
                                     {"p_store": sid})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def mark_notification_read(notification_id: Optional[int] = None,
                               store_id: Optional[int] = None) -> Dict:
        try:
            with DatabaseModel() as db:
                if notification_id:
                    r = db.execute_query("UPDATE PLG_NOTIFICATIONS SET IS_READ = 1 WHERE ID = :p_id",
                                         {"p_id": int(notification_id)})
                else:
                    sid = PlanogramController._resolve_store(db, store_id)
                    r = db.execute_query(
                        "UPDATE PLG_NOTIFICATIONS SET IS_READ = 1 WHERE STORE_ID = :p_store AND IS_READ = 0",
                        {"p_store": sid})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
                return {"success": True, "updated": r.get("rowcount", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Аналитика ====================

    @staticmethod
    def get_analytics(store_id: Optional[int] = None, days: int = 14,
                      lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            days = max(1, min(int(days or 14), 90))
        except (TypeError, ValueError):
            days = 14
        try:
            with DatabaseModel() as db:
                sid = PlanogramController._resolve_store(db, store_id)
                if not sid:
                    return {"success": True, "data": {"zones": [], "categories": [], "metrics": []},
                            "lang": lang}

                zones = PlanogramController._localized(db.execute_query(
                    "SELECT z.ID AS ZONE_ID, z.CODE, z.NAME_RU, z.NAME_RO, z.NAME_EN, z.COLOR, "
                    "t.METRIC_DATE, t.TRAFFIC_PCT, t.VISITORS, t.DWELL_SEC, t.PICKUPS "
                    "FROM PLG_ZONE_TRAFFIC t JOIN PLG_ZONES z ON z.ID = t.ZONE_ID "
                    "WHERE z.STORE_ID = :p_store AND t.METRIC_HOUR IS NULL "
                    "AND t.METRIC_DATE >= TRUNC(SYSDATE) - :p_days "
                    "ORDER BY z.SORT_ORDER, t.METRIC_DATE",
                    {"p_store": sid, "p_days": days}), lang)

                categories = PlanogramController._localized(db.execute_query(
                    "SELECT c.ID AS CATEGORY_ID, c.CODE, c.NAME_RU, c.NAME_RO, c.NAME_EN, c.COLOR, "
                    "m.METRIC_DATE, m.VISITS, m.SALES_QTY, m.SALES_AMT "
                    "FROM PLG_CATEGORY_METRICS m JOIN PLG_CATEGORIES c ON c.ID = m.CATEGORY_ID "
                    "WHERE m.STORE_ID = :p_store AND m.METRIC_DATE >= TRUNC(SYSDATE) - :p_days "
                    "ORDER BY c.SORT_ORDER, m.METRIC_DATE",
                    {"p_store": sid, "p_days": days}), lang)

                metrics = PlanogramController._rows(db.execute_query(
                    "SELECT * FROM V_PLG_STORE_METRICS WHERE STORE_ID = :p_store "
                    "AND METRIC_DATE >= TRUNC(SYSDATE) - :p_days ORDER BY METRIC_DATE",
                    {"p_store": sid, "p_days": days}))

                return {"success": True, "lang": lang, "days": days,
                        "data": {"zones": zones, "categories": categories, "metrics": metrics}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Настройки и аудит ====================

    @staticmethod
    def get_settings(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT PARAM_CODE, PARAM_VALUE, DESCR_RU, DESCR_RO, DESCR_EN, UPDATED_AT "
                    "FROM PLG_SETTINGS ORDER BY PARAM_CODE")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_setting(param_code: str, param_value: str) -> Dict:
        if not param_code:
            return {"success": False, "error": "Не указан параметр"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "MERGE INTO PLG_SETTINGS s USING (SELECT :p_code AS PARAM_CODE FROM DUAL) src "
                    "ON (s.PARAM_CODE = src.PARAM_CODE) "
                    "WHEN MATCHED THEN UPDATE SET s.PARAM_VALUE = :p_value "
                    "WHEN NOT MATCHED THEN INSERT (PARAM_CODE, PARAM_VALUE) VALUES (:p_code, :p_value)",
                    {"p_code": param_code, "p_value": param_value})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("setting", "settings", None, f"{param_code}={param_value}")
        return {"success": True}

    @staticmethod
    def get_audit(limit: int = 200) -> Dict:
        try:
            limit = max(1, min(int(limit or 200), 1000))
        except (TypeError, ValueError):
            limit = 200
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, ACTION, ENTITY_TYPE, ENTITY_ID, DETAILS, USERNAME, CREATED_AT "
                    f"FROM PLG_EVENT_LOG ORDER BY CREATED_AT DESC FETCH FIRST {limit} ROWS ONLY")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Общий помощник удаления ====================

    _DELETABLE = {
        "PLG_ZONES", "PLG_FIXTURES", "PLG_PRODUCTS", "PLG_PLANOGRAMS",
        "PLG_PLANOGRAM_ITEMS", "PLG_PROMOS", "PLG_TASKS", "PLG_DOCUMENTS",
        "PLG_DC", "PLG_VEHICLES", "PLG_SHIPMENTS", "PLG_SUPPLIERS",
        "PLG_SUPPLIER_CONTACTS", "PLG_CONTRACTS", "PLG_COMPETITORS",
        "PLG_MARKETS", "PLG_MARKET_CHAINS", "PLG_PROCESSES",
    }

    @staticmethod
    def _delete(table: str, entity_id: int, entity_type: str) -> Dict:
        if table not in PlanogramController._DELETABLE:
            return {"success": False, "error": f"Удаление из {table} не разрешено"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(f"DELETE FROM {table} WHERE ID = :p_id", {"p_id": int(entity_id)})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("delete", entity_type, int(entity_id), table)
        return {"success": True}

    # ==================== Наборы тестовых данных ====================

    @staticmethod
    def get_datasets(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_PLG_DATASETS ORDER BY IS_PROTECTED DESC, CREATED_AT DESC")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_dataset(data: Dict) -> Dict:
        params = {
            "p_code": (data.get("code") or "").strip() or None,
            "p_kind": data.get("kind") or "test",
            "p_descr": data.get("description"),
            "p_stores": data.get("store_count") or 10,
            "p_sku": data.get("sku_count") or 400,
            "p_days": data.get("days") or 365,
            "p_seed": data.get("seed") or 20260815,
            "p_user": PlanogramController._username(),
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_name_ru"]:
            return {"success": False, "error": "Не указано название набора"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "INSERT INTO PLG_DATASETS (CODE, KIND, NAME_RU, NAME_RO, NAME_EN, DESCRIPTION, "
                    "STATUS, STORE_COUNT, SKU_COUNT, DAYS_DEPTH, SEED, CREATED_BY) "
                    "VALUES (:p_code, :p_kind, :p_name_ru, :p_name_ro, :p_name_en, :p_descr, "
                    "'building', :p_stores, :p_sku, :p_days, :p_seed, :p_user)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
                row = PlanogramController._first(db.execute_query(
                    "SELECT MAX(ID) AS ID FROM PLG_DATASETS"))
                new_id = row.get("id") if row else None
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("create", "dataset", new_id, params["p_name_ru"])
        return {"success": True, "id": new_id}

    @staticmethod
    def delete_dataset(dataset_id: int) -> Dict:
        """
        Удаляет набор целиком. Порядок обязателен: планограммы не каскадируются
        от магазина (обычный FK), а позиции выкладки ссылаются на товар без каскада,
        поэтому сначала документы, потом магазины, потом товары.
        """
        try:
            with DatabaseModel() as db:
                row = PlanogramController._first(db.execute_query(
                    "SELECT CODE, IS_PROTECTED FROM PLG_DATASETS WHERE ID = :p_id",
                    {"p_id": int(dataset_id)}))
                if not row:
                    return {"success": False, "error": "Набор не найден"}
                if int(row.get("is_protected") or 0):
                    return {"success": False,
                            "error": f"Набор {row.get('code')} защищён от удаления"}
                steps = [
                    # Планограммы не каскадируются от магазина — только явно
                    "DELETE FROM PLG_PLANOGRAMS WHERE STORE_ID IN "
                    "(SELECT ID FROM PLG_STORES WHERE DATASET_ID = :p_id)",
                    # Транспорт держит FK на набор, рейсы уйдут каскадом от РЦ/магазина/поставщика
                    "DELETE FROM PLG_VEHICLES WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_DC WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_STORES WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_COMPETITORS WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_MARKETS WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_SUPPLIERS WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_PRODUCTS WHERE DATASET_ID = :p_id",
                    "DELETE FROM PLG_DATASETS WHERE ID = :p_id",
                ]
                for sql in steps:
                    r = db.execute_query(sql, {"p_id": int(dataset_id)})
                    if not r.get("success"):
                        return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("delete", "dataset", int(dataset_id), row.get("code"))
        return {"success": True}

    # ==================== Генерация тестовых данных ====================

    @staticmethod
    def get_gen_algorithms(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, "
                    "PARAMS_JSON, STAGE_ORDER FROM PLG_GEN_ALGORITHMS WHERE IS_ACTIVE = 1 "
                    "ORDER BY STAGE_ORDER")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def start_generation(data: Dict) -> Dict:
        """
        Запускает генерацию. Если dataset_id не передан — создаёт новый набор
        по параметрам запроса. Прогон идёт в фоновом потоке, прогресс пишется
        в PLG_GEN_RUNS и опрашивается админкой.
        """
        from models.plg_datagen import DataGenerator

        dataset_id = data.get("dataset_id")
        params = {
            "store_count": int(data.get("store_count") or 10),
            "sku_count": int(data.get("sku_count") or 400),
            "days": int(data.get("days") or 365),
            "seed": int(data.get("seed") or 20260815),
            "noise_pct": float(data.get("noise_pct") or 18),
            "oos_rate": float(data.get("oos_rate") or 0.015),
            "trend_pct_year": float(data.get("trend_pct_year") or 6),
            "weekly_amplitude": float(data.get("weekly_amplitude") or 0.35),
            "yearly_amplitude": float(data.get("yearly_amplitude") or 0.20),
            "promo_per_store": int(data.get("promo_per_store") or 6),
            "planogram_per_store": int(data.get("planogram_per_store") or 5),
            "task_per_store": int(data.get("task_per_store") or 8),
            "conversion_min": float(data.get("conversion_min") or 16),
            "conversion_max": float(data.get("conversion_max") or 21),
        }
        if params["store_count"] < 1 or params["store_count"] > 100:
            return {"success": False, "error": "Число магазинов должно быть от 1 до 100"}
        if params["sku_count"] < 10 or params["sku_count"] > 5000:
            return {"success": False, "error": "Число SKU должно быть от 10 до 5000"}
        if params["days"] < 14 or params["days"] > 1095:
            return {"success": False, "error": "Глубина истории должна быть от 14 до 1095 дней"}

        if not dataset_id:
            created = PlanogramController.create_dataset({
                "name": data.get("name") or f"Тестовая сеть {params['store_count']}×{params['sku_count']}",
                "name_ro": data.get("name_ro"), "name_en": data.get("name_en"),
                "code": data.get("code"), "kind": data.get("kind") or "test",
                "description": data.get("description"),
                "store_count": params["store_count"], "sku_count": params["sku_count"],
                "days": params["days"], "seed": params["seed"],
            })
            if not created.get("success"):
                return created
            dataset_id = created["id"]

        stages = data.get("stages") or DataGenerator.STAGES
        result = DataGenerator.launch(int(dataset_id), params, list(stages),
                                      PlanogramController._username())
        if result.get("success"):
            PlanogramController._audit("generate", "dataset", int(dataset_id),
                                       f"stages={','.join(result.get('stages') or [])}")
        return result

    @staticmethod
    def get_gen_runs(dataset_id: Optional[int] = None, limit: int = 50,
                     lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            limit = max(1, min(int(limit or 50), 500))
        except (TypeError, ValueError):
            limit = 50
        sql = "SELECT * FROM V_PLG_GEN_RUNS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + f" ORDER BY STARTED_AT DESC FETCH FIRST {limit} ROWS ONLY", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_gen_run(run_id: int, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                row = PlanogramController._first(db.execute_query(
                    "SELECT * FROM V_PLG_GEN_RUNS WHERE ID = :p_id", {"p_id": int(run_id)}))
                if not row:
                    return {"success": False, "error": "Прогон не найден"}
                return {"success": True, "data": PlanogramController._localize([row], lang)[0],
                        "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_generation(run_id: int) -> Dict:
        from models.plg_datagen import DataGenerator
        result = DataGenerator.cancel(int(run_id))
        if result.get("success"):
            PlanogramController._audit("cancel", "gen_run", int(run_id), "")
        return result

    # ==================== Модели прогноза заказов ====================

    @staticmethod
    def get_fct_algorithms(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, "
                    "PARAMS_SCHEMA, PARAMS_JSON, MIN_HISTORY FROM PLG_FCT_ALGORITHMS "
                    "WHERE IS_ACTIVE = 1 ORDER BY SORT_ORDER")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_fct_models(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT * FROM V_PLG_FCT_MODELS ORDER BY ALGORITHM, CODE")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_fct_model(data: Dict, model_id: Optional[int] = None) -> Dict:
        import json as _json
        raw_params = data.get("params")
        if isinstance(raw_params, dict):
            params_json = _json.dumps(raw_params, ensure_ascii=False)
        else:
            params_json = (raw_params or "{}").strip()
            try:
                _json.loads(params_json)
            except (ValueError, TypeError):
                return {"success": False, "error": "Параметры модели — некорректный JSON"}

        params = {
            "p_code": (data.get("code") or "").strip(),
            "p_algo": data.get("algorithm"),
            "p_params": params_json[:2000],
            "p_horizon": int(data.get("horizon_days") or 7),
            "p_sl": float(data.get("service_level") or 95),
            "p_lead": int(data.get("lead_time_days") or 2),
            "p_pack": 1 if data.get("round_to_pack", 1) else 0,
            "p_active": 1 if data.get("is_active", 1) else 0,
            "p_default": 1 if data.get("is_default") else 0,
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_algo"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код, алгоритм и название модели обязательны"}
        if not 1 <= params["p_horizon"] <= 90:
            return {"success": False, "error": "Горизонт прогноза — от 1 до 90 дней"}
        if not 50 <= params["p_sl"] <= 99.9:
            return {"success": False, "error": "Уровень сервиса — от 50 до 99.9 %"}
        try:
            with DatabaseModel() as db:
                if model_id:
                    params["p_id"] = int(model_id)
                    r = db.execute_query(
                        "UPDATE PLG_FCT_MODELS SET CODE = :p_code, ALGORITHM = :p_algo, "
                        "NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, NAME_EN = :p_name_en, "
                        "PARAMS_JSON = :p_params, HORIZON_DAYS = :p_horizon, SERVICE_LEVEL = :p_sl, "
                        "LEAD_TIME_DAYS = :p_lead, ROUND_TO_PACK = :p_pack, IS_ACTIVE = :p_active, "
                        "IS_DEFAULT = :p_default WHERE ID = :p_id", params)
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_FCT_MODELS (CODE, ALGORITHM, NAME_RU, NAME_RO, NAME_EN, "
                        "PARAMS_JSON, HORIZON_DAYS, SERVICE_LEVEL, LEAD_TIME_DAYS, ROUND_TO_PACK, "
                        "IS_ACTIVE, IS_DEFAULT, CREATED_BY) "
                        "VALUES (:p_code, :p_algo, :p_name_ru, :p_name_ro, :p_name_en, :p_params, "
                        ":p_horizon, :p_sl, :p_lead, :p_pack, :p_active, :p_default, :p_user)",
                        {**params, "p_user": PlanogramController._username()})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                if params["p_default"]:
                    # Модель по умолчанию должна быть ровно одна
                    db.execute_query(
                        "UPDATE PLG_FCT_MODELS SET IS_DEFAULT = 0 WHERE CODE <> :p_code",
                        {"p_code": params["p_code"]})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if model_id else "create", "fct_model",
                                   model_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_fct_model(model_id: int) -> Dict:
        try:
            with DatabaseModel() as db:
                r = db.execute_query("DELETE FROM PLG_FCT_MODELS WHERE ID = :p_id",
                                     {"p_id": int(model_id)})
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("delete", "fct_model", int(model_id), "")
        return {"success": True}

    # ==================== Прогоны прогноза ====================

    @staticmethod
    def start_forecast(data: Dict) -> Dict:
        from models.plg_forecast import ForecastEngine
        model_id = data.get("model_id")
        if not model_id:
            return {"success": False, "error": "Не выбрана модель прогноза"}
        result = ForecastEngine.launch(
            int(model_id), data.get("dataset_id"), data.get("store_id"),
            data.get("mode") or "forecast", PlanogramController._username())
        if result.get("success"):
            PlanogramController._audit("forecast", "fct_run", result.get("run_id"),
                                       f"model={result.get('model')} mode={result.get('mode')}")
        return result

    @staticmethod
    def get_fct_runs(model_id: Optional[int] = None, dataset_id: Optional[int] = None,
                     limit: int = 50, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            limit = max(1, min(int(limit or 50), 500))
        except (TypeError, ValueError):
            limit = 50
        sql = "SELECT * FROM V_PLG_FCT_RUNS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if model_id:
            sql += " AND MODEL_ID = :p_m"
            params["p_m"] = int(model_id)
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + f" ORDER BY STARTED_AT DESC FETCH FIRST {limit} ROWS ONLY", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_fct_run(run_id: int, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                row = PlanogramController._first(db.execute_query(
                    "SELECT * FROM V_PLG_FCT_RUNS WHERE ID = :p_id", {"p_id": int(run_id)}))
                if not row:
                    return {"success": False, "error": "Прогон не найден"}
                return {"success": True, "data": PlanogramController._localize([row], lang)[0],
                        "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_forecast(run_id: int) -> Dict:
        from models.plg_forecast import ForecastEngine
        result = ForecastEngine.cancel(int(run_id))
        if result.get("success"):
            PlanogramController._audit("cancel", "fct_run", int(run_id), "")
        return result

    @staticmethod
    def get_order_proposal(run_id: int, store_id: Optional[int] = None,
                           limit: int = 200, lang: str = DEFAULT_LANG) -> Dict:
        """Рекомендуемый заказ по итогам прогона, отсортированный по сумме."""
        lang = PlanogramController.lang(lang)
        try:
            limit = max(1, min(int(limit or 200), 2000))
        except (TypeError, ValueError):
            limit = 200
        sql = "SELECT * FROM V_PLG_ORDER_PROPOSAL WHERE RUN_ID = :p_run AND ORDER_QTY > 0"
        params: Dict[str, Any] = {"p_run": int(run_id)}
        if store_id:
            sql += " AND STORE_ID = :p_st"
            params["p_st"] = int(store_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + f" ORDER BY ORDER_AMOUNT DESC NULLS LAST FETCH FIRST {limit} ROWS ONLY",
                    params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                rows = PlanogramController._localized(r, lang)
                totals = PlanogramController._first(db.execute_query(
                    "SELECT COUNT(*) AS SKU_COUNT, ROUND(SUM(ORDER_QTY),3) AS QTY_TOTAL, "
                    "ROUND(SUM(ORDER_AMOUNT),2) AS AMOUNT_TOTAL "
                    "FROM V_PLG_ORDER_PROPOSAL WHERE RUN_ID = :p_run AND ORDER_QTY > 0",
                    {"p_run": int(run_id)})) or {}
                return {"success": True, "data": rows, "totals": totals, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Логистика: РЦ, транспорт, рейсы ====================

    @staticmethod
    def get_dc(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_DC WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY CODE", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_dc(data: Dict, dc_id: Optional[int] = None) -> Dict:
        params = {
            "p_ds": data.get("dataset_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_city": data.get("city"),
            "p_area": data.get("area_sqm"),
            "p_docks": data.get("dock_count") or 12,
            "p_slots": data.get("pallet_slots") or 8000,
            "p_from": data.get("work_from") or "06:00",
            "p_to": data.get("work_to") or "22:00",
            "p_fresh": 1 if data.get("has_fresh", 1) else 0,
            "p_mgr": data.get("manager_name"),
            "p_status": data.get("status") or "active",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        params.update(PlanogramController._multilang_params(data, "address", "p_addr"))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код и название РЦ обязательны"}
        try:
            with DatabaseModel() as db:
                if dc_id:
                    params["p_id"] = int(dc_id)
                    r = db.execute_query(
                        "UPDATE PLG_DC SET CODE = :p_code, NAME_RU = :p_name_ru, NAME_RO = :p_name_ro, "
                        "NAME_EN = :p_name_en, CITY = :p_city, ADDRESS_RU = :p_addr_ru, "
                        "ADDRESS_RO = :p_addr_ro, ADDRESS_EN = :p_addr_en, AREA_SQM = :p_area, "
                        "DOCK_COUNT = :p_docks, PALLET_SLOTS = :p_slots, WORK_FROM = :p_from, "
                        "WORK_TO = :p_to, HAS_FRESH = :p_fresh, MANAGER_NAME = :p_mgr, "
                        "STATUS = :p_status WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_ds"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_DC (DATASET_ID, CODE, NAME_RU, NAME_RO, NAME_EN, CITY, "
                        "ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, AREA_SQM, DOCK_COUNT, PALLET_SLOTS, "
                        "WORK_FROM, WORK_TO, HAS_FRESH, MANAGER_NAME, STATUS) "
                        "VALUES (:p_ds, :p_code, :p_name_ru, :p_name_ro, :p_name_en, :p_city, "
                        ":p_addr_ru, :p_addr_ro, :p_addr_en, :p_area, :p_docks, :p_slots, "
                        ":p_from, :p_to, :p_fresh, :p_mgr, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if dc_id else "create", "dc", dc_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_dc(dc_id: int) -> Dict:
        return PlanogramController._delete("PLG_DC", dc_id, "dc")

    @staticmethod
    def get_vehicles(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_VEHICLES WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY VEHICLE_TYPE, CODE", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_vehicle(data: Dict, vehicle_id: Optional[int] = None) -> Dict:
        params = {
            "p_ds": data.get("dataset_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_plate": data.get("plate_no"),
            "p_type": data.get("vehicle_type") or "midi",
            "p_carrier": data.get("carrier"),
            "p_own": 1 if data.get("is_own", 1) else 0,
            "p_driver": data.get("driver_name"),
            "p_dc": data.get("home_dc_id") or None,
            "p_cap": data.get("capacity_kg"),
            "p_vol": data.get("volume_m3"),
            "p_slots": data.get("pallet_slots"),
            "p_status": data.get("status") or "active",
        }
        if not params["p_code"]:
            return {"success": False, "error": "Не указан код машины"}
        try:
            with DatabaseModel() as db:
                if vehicle_id:
                    params["p_id"] = int(vehicle_id)
                    r = db.execute_query(
                        "UPDATE PLG_VEHICLES SET CODE = :p_code, PLATE_NO = :p_plate, "
                        "VEHICLE_TYPE = :p_type, CARRIER = :p_carrier, IS_OWN = :p_own, "
                        "DRIVER_NAME = :p_driver, HOME_DC_ID = :p_dc, CAPACITY_KG = :p_cap, "
                        "VOLUME_M3 = :p_vol, PALLET_SLOTS = :p_slots, STATUS = :p_status "
                        "WHERE ID = :p_id", {k: v for k, v in params.items() if k != "p_ds"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_VEHICLES (DATASET_ID, CODE, PLATE_NO, VEHICLE_TYPE, CARRIER, "
                        "IS_OWN, DRIVER_NAME, HOME_DC_ID, CAPACITY_KG, VOLUME_M3, PALLET_SLOTS, STATUS) "
                        "VALUES (:p_ds, :p_code, :p_plate, :p_type, :p_carrier, :p_own, :p_driver, "
                        ":p_dc, :p_cap, :p_vol, :p_slots, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if vehicle_id else "create", "vehicle",
                                   vehicle_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_vehicle(vehicle_id: int) -> Dict:
        return PlanogramController._delete("PLG_VEHICLES", vehicle_id, "vehicle")

    @staticmethod
    def get_shipments(dataset_id: Optional[int] = None, date_from: Optional[str] = None,
                      days: int = 7, store_id: Optional[int] = None,
                      shipment_type: Optional[str] = None, limit: int = 1000,
                      lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            days = max(1, min(int(days or 7), 60))
            limit = max(1, min(int(limit or 1000), 5000))
        except (TypeError, ValueError):
            days, limit = 7, 1000
        sql = ("SELECT * FROM V_PLG_SHIPMENTS WHERE PLANNED_START >= "
               "NVL(TO_DATE(:p_from, 'YYYY-MM-DD'), TRUNC(SYSDATE) - :p_days) "
               "AND PLANNED_START < NVL(TO_DATE(:p_from, 'YYYY-MM-DD'), TRUNC(SYSDATE) - :p_days) "
               "+ :p_days + 1")
        params: Dict[str, Any] = {"p_from": date_from, "p_days": days}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if store_id:
            sql += " AND STORE_ID = :p_st"
            params["p_st"] = int(store_id)
        if shipment_type:
            sql += " AND SHIPMENT_TYPE = :p_type"
            params["p_type"] = shipment_type
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + f" ORDER BY PLANNED_START FETCH FIRST {limit} ROWS ONLY", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_gantt(dataset_id: Optional[int] = None, date_from: Optional[str] = None,
                  days: int = 3, group_by: str = 'vehicle', lang: str = DEFAULT_LANG) -> Dict:
        """
        Готовит данные диаграммы Ганта: строки-ресурсы и полосы-рейсы
        со смещением в минутах от начала окна. Всю арифметику делаем здесь,
        чтобы шаблон только рисовал прямоугольники.
        """
        lang = PlanogramController.lang(lang)
        group_by = group_by if group_by in ('vehicle', 'store', 'dock', 'supplier') else 'vehicle'
        try:
            days = max(1, min(int(days or 3), 14))
        except (TypeError, ValueError):
            days = 3

        res = PlanogramController.get_shipments(dataset_id, date_from, days, None, None, 5000, lang)
        if not res.get("success"):
            return res
        rows = res["data"]

        key_field = {'vehicle': 'vehicle_code', 'store': 'store_code',
                     'dock': 'dock_no', 'supplier': 'supplier_code'}[group_by]
        label_field = {'vehicle': 'plate_no', 'store': 'store',
                       'dock': 'dock_no', 'supplier': 'supplier'}[group_by]

        groups: Dict[str, Dict[str, Any]] = {}
        bars: List[Dict[str, Any]] = []
        t_min = t_max = None
        for row in rows:
            key = row.get(key_field)
            if key is None:
                key = '—'
            key = str(key)
            grp = groups.setdefault(key, {
                "key": key,
                "label": str(row.get(label_field) or key),
                "sub": row.get('vehicle_type_name') if group_by == 'vehicle' else row.get('store_code'),
                "color": row.get('vehicle_color') or '#64748b',
                "count": 0, "pallets": 0.0, "late": 0,
            })
            grp["count"] += 1
            grp["pallets"] += float(row.get('pallets') or 0)
            grp["late"] += int(row.get('is_late') or 0)

            start, end = row.get('planned_start'), row.get('planned_end')
            if not start or not end:
                continue
            t_min = start if t_min is None or start < t_min else t_min
            t_max = end if t_max is None or end > t_max else t_max
            bars.append({
                "group": key, "id": row.get('id'), "code": row.get('code'),
                "type": row.get('shipment_type'), "type_name": row.get('shipment_type_name'),
                "color": row.get('type_color') or '#2563eb',
                "start": start, "end": end,
                "actual_start": row.get('actual_start'), "actual_end": row.get('actual_end'),
                "status": row.get('status'), "delay": row.get('delay_min') or 0,
                "is_late": row.get('is_late') or 0,
                "pallets": row.get('pallets'), "dock": row.get('dock_no'),
                "temp": row.get('temp_mode'),
                "from": row.get('supplier') or row.get('dc') or '—',
                "to": row.get('store') or row.get('dc') or '—',
            })

        order = sorted(groups.values(), key=lambda g: (-g["count"], g["label"]))
        return {"success": True, "lang": lang, "group_by": group_by,
                "data": {"groups": order, "bars": bars,
                         "from": t_min, "to": t_max, "days": days,
                         "total": len(bars),
                         "late": sum(1 for b in bars if b["is_late"]),
                         "pallets": round(sum(float(b["pallets"] or 0) for b in bars), 1)}}

    @staticmethod
    def save_shipment(data: Dict, shipment_id: Optional[int] = None) -> Dict:
        params = {
            "p_type": data.get("shipment_type") or "transfer",
            "p_sup": data.get("supplier_id") or None,
            "p_dc": data.get("dc_id") or None,
            "p_store": data.get("store_id") or None,
            "p_veh": data.get("vehicle_id") or None,
            "p_dock": data.get("dock_no") or None,
            "p_start": data.get("planned_start"),
            "p_end": data.get("planned_end"),
            "p_status": data.get("status") or "planned",
            "p_temp": data.get("temp_mode") or "ambient",
            "p_pallets": data.get("pallets") or 0,
            "p_weight": data.get("weight_kg") or 0,
            "p_amount": data.get("amount") or 0,
            "p_dist": data.get("distance_km"),
            "p_notes": data.get("notes"),
        }
        if not params["p_start"] or not params["p_end"]:
            return {"success": False, "error": "Окно разгрузки обязательно (начало и конец)"}
        fmt = "'YYYY-MM-DD\"T\"HH24:MI'"
        try:
            with DatabaseModel() as db:
                if shipment_id:
                    params["p_id"] = int(shipment_id)
                    r = db.execute_query(
                        "UPDATE PLG_SHIPMENTS SET SHIPMENT_TYPE = :p_type, SUPPLIER_ID = :p_sup, "
                        "DC_ID = :p_dc, STORE_ID = :p_store, VEHICLE_ID = :p_veh, DOCK_NO = :p_dock, "
                        f"PLANNED_START = TO_DATE(:p_start, {fmt}), PLANNED_END = TO_DATE(:p_end, {fmt}), "
                        "STATUS = :p_status, TEMP_MODE = :p_temp, PALLETS = :p_pallets, "
                        "WEIGHT_KG = :p_weight, AMOUNT = :p_amount, DISTANCE_KM = :p_dist, "
                        "NOTES = :p_notes WHERE ID = :p_id", params)
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_SHIPMENTS (SHIPMENT_TYPE, SUPPLIER_ID, DC_ID, STORE_ID, "
                        "VEHICLE_ID, DOCK_NO, PLANNED_START, PLANNED_END, STATUS, TEMP_MODE, "
                        "PALLETS, WEIGHT_KG, AMOUNT, DISTANCE_KM, NOTES) "
                        "VALUES (:p_type, :p_sup, :p_dc, :p_store, :p_veh, :p_dock, "
                        f"TO_DATE(:p_start, {fmt}), TO_DATE(:p_end, {fmt}), :p_status, :p_temp, "
                        ":p_pallets, :p_weight, :p_amount, :p_dist, :p_notes)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if shipment_id else "create", "shipment",
                                   shipment_id, params["p_type"])
        return {"success": True}

    @staticmethod
    def delete_shipment(shipment_id: int) -> Dict:
        return PlanogramController._delete("PLG_SHIPMENTS", shipment_id, "shipment")

    @staticmethod
    def get_logistics_stats(dataset_id: Optional[int] = None, days: int = 7,
                            lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            days = max(1, min(int(days or 7), 90))
        except (TypeError, ValueError):
            days = 7
        sql = ("SELECT SHIPMENT_TYPE, SHIPMENT_TYPE_NAME_RU, SHIPMENT_TYPE_NAME_RO, "
               "SHIPMENT_TYPE_NAME_EN, TYPE_COLOR, COUNT(*) AS TRIPS, "
               "ROUND(AVG(PLANNED_MIN)) AS AVG_MIN, SUM(IS_LATE) AS LATE_TRIPS, "
               "ROUND(SUM(PALLETS), 1) AS PALLETS, ROUND(SUM(AMOUNT), 2) AS AMOUNT, "
               "ROUND(AVG(DELAY_MIN), 1) AS AVG_DELAY, ROUND(SUM(DISTANCE_KM), 1) AS DISTANCE "
               "FROM V_PLG_SHIPMENTS WHERE PLANNED_START >= TRUNC(SYSDATE) - :p_days")
        params: Dict[str, Any] = {"p_days": days}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        sql += (" GROUP BY SHIPMENT_TYPE, SHIPMENT_TYPE_NAME_RU, SHIPMENT_TYPE_NAME_RO, "
                "SHIPMENT_TYPE_NAME_EN, TYPE_COLOR ORDER BY TRIPS DESC")
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang),
                        "days": days, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== Поставщики: карточка, контакты, контракты ====================

    @staticmethod
    def get_suppliers(dataset_id: Optional[int] = None, search: Optional[str] = None,
                      lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_SUPPLIERS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if search:
            sql += (" AND (UPPER(CODE) LIKE :p_q OR UPPER(NAME_RU) LIKE :p_q "
                    "OR UPPER(NAME_RO) LIKE :p_q OR UPPER(NAME_EN) LIKE :p_q)")
            params["p_q"] = f"%{search.strip().upper()}%"
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY IS_KEY DESC, ANNUAL_TURNOVER DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_supplier(supplier_id: int, lang: str = DEFAULT_LANG) -> Dict:
        """Карточка поставщика: реквизиты, контакты, контракты, товарные группы."""
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                head = PlanogramController._first(db.execute_query(
                    "SELECT * FROM V_PLG_SUPPLIERS WHERE ID = :p_id", {"p_id": int(supplier_id)}))
                if not head:
                    return {"success": False, "error": "Поставщик не найден"}
                data = PlanogramController._localize([head], lang)[0]
                data["contacts"] = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_SUPPLIER_CONTACTS WHERE SUPPLIER_ID = :p_id "
                    "ORDER BY IS_PRIMARY DESC, FULL_NAME", {"p_id": int(supplier_id)}), lang)
                data["contracts"] = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_CONTRACTS WHERE SUPPLIER_ID = :p_id "
                    "ORDER BY DATE_FROM DESC", {"p_id": int(supplier_id)}), lang)
                data["categories"] = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_SUPPLIER_CATEGORIES WHERE SUPPLIER_ID = :p_id "
                    "ORDER BY TURNOVER DESC NULLS LAST", {"p_id": int(supplier_id)}), lang)
                data["shipments"] = PlanogramController._localized(db.execute_query(
                    "SELECT * FROM V_PLG_SHIPMENTS WHERE SUPPLIER_ID = :p_id "
                    "ORDER BY PLANNED_START DESC FETCH FIRST 15 ROWS ONLY",
                    {"p_id": int(supplier_id)}), lang)
                return {"success": True, "data": data, "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_supplier(data: Dict, supplier_id: Optional[int] = None) -> Dict:
        params = {
            "p_ds": data.get("dataset_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_type": data.get("supplier_type") or "distributor",
            "p_country": data.get("country") or "MD",
            "p_city": data.get("city"),
            "p_addr": data.get("address"),
            "p_idno": data.get("idno"),
            "p_web": data.get("website"),
            "p_phone": data.get("phone"),
            "p_email": data.get("email"),
            "p_rating": data.get("rating"),
            "p_otif": data.get("otif_pct"),
            "p_turn": data.get("annual_turnover"),
            "p_key": 1 if data.get("is_key") else 0,
            "p_del": data.get("delivers_to") or "dc",
            "p_status": data.get("status") or "active",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код и название поставщика обязательны"}
        try:
            with DatabaseModel() as db:
                if supplier_id:
                    params["p_id"] = int(supplier_id)
                    r = db.execute_query(
                        "UPDATE PLG_SUPPLIERS SET CODE = :p_code, NAME_RU = :p_name_ru, "
                        "NAME_RO = :p_name_ro, NAME_EN = :p_name_en, SUPPLIER_TYPE = :p_type, "
                        "COUNTRY = :p_country, CITY = :p_city, ADDRESS = :p_addr, IDNO = :p_idno, "
                        "WEBSITE = :p_web, PHONE = :p_phone, EMAIL = :p_email, RATING = :p_rating, "
                        "OTIF_PCT = :p_otif, ANNUAL_TURNOVER = :p_turn, IS_KEY = :p_key, "
                        "DELIVERS_TO = :p_del, STATUS = :p_status WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_ds"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_SUPPLIERS (DATASET_ID, CODE, NAME_RU, NAME_RO, NAME_EN, "
                        "SUPPLIER_TYPE, COUNTRY, CITY, ADDRESS, IDNO, WEBSITE, PHONE, EMAIL, "
                        "RATING, OTIF_PCT, ANNUAL_TURNOVER, IS_KEY, DELIVERS_TO, STATUS) "
                        "VALUES (:p_ds, :p_code, :p_name_ru, :p_name_ro, :p_name_en, :p_type, "
                        ":p_country, :p_city, :p_addr, :p_idno, :p_web, :p_phone, :p_email, "
                        ":p_rating, :p_otif, :p_turn, :p_key, :p_del, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if supplier_id else "create", "supplier",
                                   supplier_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_supplier(supplier_id: int) -> Dict:
        return PlanogramController._delete("PLG_SUPPLIERS", supplier_id, "supplier")

    @staticmethod
    def save_contact(supplier_id: int, data: Dict, contact_id: Optional[int] = None) -> Dict:
        params = {
            "p_sup": int(supplier_id),
            "p_name": (data.get("full_name") or "").strip(),
            "p_role": data.get("role_code") or None,
            "p_pos": data.get("position_tx"),
            "p_phone": data.get("phone"),
            "p_mob": data.get("mobile"),
            "p_mail": data.get("email"),
            "p_msg": data.get("messenger"),
            "p_prim": 1 if data.get("is_primary") else 0,
            "p_notes": data.get("notes"),
        }
        if not params["p_name"]:
            return {"success": False, "error": "Не указано имя контактного лица"}
        try:
            with DatabaseModel() as db:
                if contact_id:
                    params["p_id"] = int(contact_id)
                    r = db.execute_query(
                        "UPDATE PLG_SUPPLIER_CONTACTS SET FULL_NAME = :p_name, ROLE_CODE = :p_role, "
                        "POSITION_TX = :p_pos, PHONE = :p_phone, MOBILE = :p_mob, EMAIL = :p_mail, "
                        "MESSENGER = :p_msg, IS_PRIMARY = :p_prim, NOTES = :p_notes WHERE ID = :p_id",
                        params)
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_SUPPLIER_CONTACTS (SUPPLIER_ID, FULL_NAME, ROLE_CODE, "
                        "POSITION_TX, PHONE, MOBILE, EMAIL, MESSENGER, IS_PRIMARY, NOTES) "
                        "VALUES (:p_sup, :p_name, :p_role, :p_pos, :p_phone, :p_mob, :p_mail, "
                        ":p_msg, :p_prim, :p_notes)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                if params["p_prim"]:
                    # Основной контакт у поставщика должен быть один
                    db.execute_query(
                        "UPDATE PLG_SUPPLIER_CONTACTS SET IS_PRIMARY = 0 "
                        "WHERE SUPPLIER_ID = :p_sup AND FULL_NAME <> :p_name",
                        {"p_sup": int(supplier_id), "p_name": params["p_name"]})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if contact_id else "create", "contact",
                                   contact_id, params["p_name"])
        return {"success": True}

    @staticmethod
    def delete_contact(contact_id: int) -> Dict:
        return PlanogramController._delete("PLG_SUPPLIER_CONTACTS", contact_id, "contact")

    @staticmethod
    def get_contracts(dataset_id: Optional[int] = None, supplier_id: Optional[int] = None,
                      expiring: bool = False, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_CONTRACTS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if supplier_id:
            sql += " AND SUPPLIER_ID = :p_sup"
            params["p_sup"] = int(supplier_id)
        if expiring:
            sql += " AND EXPIRING_SOON = 1"
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY DATE_TO NULLS LAST, DATE_FROM DESC", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_contract(supplier_id: int, data: Dict, contract_id: Optional[int] = None) -> Dict:
        params = {
            "p_sup": int(supplier_id),
            "p_code": (data.get("code") or "").strip() or None,
            "p_type": data.get("contract_type") or "supply",
            "p_from": data.get("date_from"),
            "p_to": data.get("date_to") or None,
            "p_curr": data.get("currency") or "MDL",
            "p_pay": data.get("payment_days") or 30,
            "p_retro": data.get("retro_bonus_pct") or 0,
            "p_disc": data.get("discount_pct") or 0,
            "p_mkt": data.get("marketing_fee") or 0,
            "p_min": data.get("min_order_amt"),
            "p_inco": data.get("incoterms") or "DDP",
            "p_lead": data.get("lead_time_days") or 2,
            "p_renew": 1 if data.get("auto_renew") else 0,
            "p_status": data.get("status") or "active",
            "p_signed": data.get("signed_by"),
            "p_file": data.get("file_url"),
            "p_notes": data.get("notes"),
        }
        params.update(PlanogramController._multilang_params(data, "title", "p_title"))
        if not params["p_from"]:
            return {"success": False, "error": "Не указана дата начала контракта"}
        try:
            with DatabaseModel() as db:
                if contract_id:
                    params["p_id"] = int(contract_id)
                    r = db.execute_query(
                        "UPDATE PLG_CONTRACTS SET CONTRACT_TYPE = :p_type, TITLE_RU = :p_title_ru, "
                        "TITLE_RO = :p_title_ro, TITLE_EN = :p_title_en, "
                        "DATE_FROM = TO_DATE(:p_from, 'YYYY-MM-DD'), "
                        "DATE_TO = TO_DATE(:p_to, 'YYYY-MM-DD'), CURRENCY = :p_curr, "
                        "PAYMENT_DAYS = :p_pay, RETRO_BONUS_PCT = :p_retro, DISCOUNT_PCT = :p_disc, "
                        "MARKETING_FEE = :p_mkt, MIN_ORDER_AMT = :p_min, INCOTERMS = :p_inco, "
                        "LEAD_TIME_DAYS = :p_lead, AUTO_RENEW = :p_renew, STATUS = :p_status, "
                        "SIGNED_BY = :p_signed, FILE_URL = :p_file, NOTES = :p_notes WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_code"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_CONTRACTS (SUPPLIER_ID, CODE, CONTRACT_TYPE, TITLE_RU, "
                        "TITLE_RO, TITLE_EN, DATE_FROM, DATE_TO, CURRENCY, PAYMENT_DAYS, "
                        "RETRO_BONUS_PCT, DISCOUNT_PCT, MARKETING_FEE, MIN_ORDER_AMT, INCOTERMS, "
                        "LEAD_TIME_DAYS, AUTO_RENEW, STATUS, SIGNED_BY, FILE_URL, NOTES) "
                        "VALUES (:p_sup, :p_code, :p_type, :p_title_ru, :p_title_ro, :p_title_en, "
                        "TO_DATE(:p_from, 'YYYY-MM-DD'), TO_DATE(:p_to, 'YYYY-MM-DD'), :p_curr, "
                        ":p_pay, :p_retro, :p_disc, :p_mkt, :p_min, :p_inco, :p_lead, :p_renew, "
                        ":p_status, :p_signed, :p_file, :p_notes)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if contract_id else "create", "contract",
                                   contract_id, str(params["p_code"] or ''))
        return {"success": True}

    @staticmethod
    def delete_contract(contract_id: int) -> Dict:
        return PlanogramController._delete("PLG_CONTRACTS", contract_id, "contract")

    @staticmethod
    def get_supplier_graph(dataset_id: Optional[int] = None, top: int = 18,
                           lang: str = DEFAULT_LANG) -> Dict:
        """
        Двудольный граф «поставщик ↔ товарная группа» для визуализации.
        Возвращает узлы обеих долей и рёбра с весом = годовой оборот.
        """
        lang = PlanogramController.lang(lang)
        try:
            top = max(3, min(int(top or 18), 60))
        except (TypeError, ValueError):
            top = 18
        sql = "SELECT * FROM V_PLG_SUPPLIER_CATEGORIES WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY TURNOVER DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                rows = PlanogramController._localized(r, lang)
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Оставляем top поставщиков по суммарному обороту — иначе граф нечитаем
        totals: Dict[int, float] = {}
        for row in rows:
            totals[row["supplier_id"]] = totals.get(row["supplier_id"], 0.0) + float(row.get("turnover") or 0)
        keep = {sid for sid, _ in sorted(totals.items(), key=lambda x: -x[1])[:top]}
        rows = [r2 for r2 in rows if r2["supplier_id"] in keep]

        suppliers: Dict[int, Dict] = {}
        categories: Dict[int, Dict] = {}
        edges = []
        for row in rows:
            sid, cid = row["supplier_id"], row["category_id"]
            suppliers.setdefault(sid, {
                "id": sid, "code": row.get("supplier_code"), "name": row.get("supplier"),
                "type": row.get("supplier_type"), "is_key": row.get("is_key"),
                "rating": row.get("rating"), "turnover": round(totals.get(sid, 0), 2), "links": 0})
            categories.setdefault(cid, {
                "id": cid, "code": row.get("category_code"), "name": row.get("category"),
                "color": row.get("category_color") or '#64748b', "turnover": 0.0, "links": 0})
            suppliers[sid]["links"] += 1
            categories[cid]["links"] += 1
            categories[cid]["turnover"] += float(row.get("turnover") or 0)
            edges.append({"supplier_id": sid, "category_id": cid,
                          "turnover": float(row.get("turnover") or 0),
                          "share": row.get("share_pct"), "sku": row.get("sku_count"),
                          "margin": row.get("margin_pct"),
                          "is_primary": row.get("is_primary"),
                          "color": row.get("category_color") or '#64748b'})
        for c in categories.values():
            c["turnover"] = round(c["turnover"], 2)
        return {"success": True, "lang": lang, "data": {
            "suppliers": sorted(suppliers.values(), key=lambda s: -s["turnover"]),
            "categories": sorted(categories.values(), key=lambda c: -c["turnover"]),
            "edges": edges,
            "max_turnover": round(max([e["turnover"] for e in edges], default=0), 2)}}

    # ==================== Конкуренты ====================

    @staticmethod
    def get_competitors(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_COMPETITORS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY MARKET_SHARE DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_competitor(data: Dict, competitor_id: Optional[int] = None) -> Dict:
        params = {
            "p_ds": data.get("dataset_id"),
            "p_code": (data.get("code") or "").strip(),
            "p_country": data.get("country") or "MD",
            "p_fmt": data.get("format_mix"),
            "p_stores": data.get("store_count"),
            "p_pos": data.get("positioning") or "mid",
            "p_idx": data.get("price_index"),
            "p_share": data.get("market_share"),
            "p_rev": data.get("annual_revenue"),
            "p_pl": data.get("private_label_pct"),
            "p_web": data.get("website"),
            "p_color": data.get("color"),
            "p_status": data.get("status") or "active",
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код и название конкурента обязательны"}
        try:
            with DatabaseModel() as db:
                if competitor_id:
                    params["p_id"] = int(competitor_id)
                    r = db.execute_query(
                        "UPDATE PLG_COMPETITORS SET CODE = :p_code, NAME_RU = :p_name_ru, "
                        "NAME_RO = :p_name_ro, NAME_EN = :p_name_en, COUNTRY = :p_country, "
                        "FORMAT_MIX = :p_fmt, STORE_COUNT = :p_stores, POSITIONING = :p_pos, "
                        "PRICE_INDEX = :p_idx, MARKET_SHARE = :p_share, ANNUAL_REVENUE = :p_rev, "
                        "PRIVATE_LABEL_PCT = :p_pl, WEBSITE = :p_web, COLOR = :p_color, "
                        "STATUS = :p_status WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_ds"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_COMPETITORS (DATASET_ID, CODE, NAME_RU, NAME_RO, NAME_EN, "
                        "COUNTRY, FORMAT_MIX, STORE_COUNT, POSITIONING, PRICE_INDEX, MARKET_SHARE, "
                        "ANNUAL_REVENUE, PRIVATE_LABEL_PCT, WEBSITE, COLOR, STATUS) "
                        "VALUES (:p_ds, :p_code, :p_name_ru, :p_name_ro, :p_name_en, :p_country, "
                        ":p_fmt, :p_stores, :p_pos, :p_idx, :p_share, :p_rev, :p_pl, :p_web, "
                        ":p_color, :p_status)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if competitor_id else "create", "competitor",
                                   competitor_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_competitor(competitor_id: int) -> Dict:
        return PlanogramController._delete("PLG_COMPETITORS", competitor_id, "competitor")

    @staticmethod
    def get_price_index(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        """Матрица ценового индекса «конкурент × товарная группа» для тепловой шкалы."""
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_PRICE_INDEX_CAT WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY COMPETITOR_CODE, CATEGORY_RU", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_price_compare(dataset_id: Optional[int] = None, competitor_id: Optional[int] = None,
                          category_id: Optional[int] = None, position: Optional[str] = None,
                          limit: int = 300, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            limit = max(1, min(int(limit or 300), 2000))
        except (TypeError, ValueError):
            limit = 300
        sql = "SELECT * FROM V_PLG_PRICE_COMPARE WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if competitor_id:
            sql += " AND COMPETITOR_ID = :p_c"
            params["p_c"] = int(competitor_id)
        if category_id:
            sql += " AND CATEGORY_ID = :p_cat"
            params["p_cat"] = int(category_id)
        if position:
            sql += " AND POSITION_CODE = :p_pos"
            params["p_pos"] = position
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + f" ORDER BY ABS(PRICE_INDEX - 100) DESC FETCH FIRST {limit} ROWS ONLY", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_competitor_suppliers(dataset_id: Optional[int] = None,
                                 competitor_id: Optional[int] = None,
                                 lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_COMPETITOR_SUPPLIERS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if competitor_id:
            sql += " AND COMPETITOR_ID = :p_c"
            params["p_c"] = int(competitor_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    sql + " ORDER BY IS_SHARED DESC, EST_SHARE_PCT DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def import_competitor_prices(csv_text: str, dataset_id: Optional[int] = None) -> Dict:
        """
        Импорт замеров цен из CSV: код_конкурента;код_товара;дата;цена;промо
        Разделитель — ';' или ','. Первая строка может быть заголовком.
        Существующий замер за ту же дату перезаписывается.
        """
        import csv as _csv
        import io as _io
        if not (csv_text or '').strip():
            return {"success": False, "error": "Пустой файл импорта"}

        sample = csv_text[:2000]
        delim = ';' if sample.count(';') >= sample.count(',') else ','
        reader = _csv.reader(_io.StringIO(csv_text), delimiter=delim)
        rows = [r for r in reader if any((c or '').strip() for c in r)]
        if not rows:
            return {"success": False, "error": "В файле нет строк"}
        head = [c.strip().lower() for c in rows[0]]
        if not head[0].replace('-', '').replace('_', '').isalnum() or 'code' in head[0] or 'код' in head[0]:
            rows = rows[1:]

        imported = skipped = 0
        errors: List[str] = []
        try:
            with DatabaseModel() as db:
                comp_sql = "SELECT ID, CODE FROM PLG_COMPETITORS WHERE 1 = 1"
                prod_sql = "SELECT ID, CODE, PRICE FROM PLG_PRODUCTS WHERE 1 = 1"
                params: Dict[str, Any] = {}
                if dataset_id:
                    comp_sql += " AND DATASET_ID = :p_ds"
                    prod_sql += " AND DATASET_ID = :p_ds"
                    params["p_ds"] = int(dataset_id)
                comps = {c[1]: int(c[0]) for c in db.execute_query(comp_sql, params).get("data", [])}
                prods = {p[1]: (int(p[0]), float(p[2] or 0))
                         for p in db.execute_query(prod_sql, params).get("data", [])}

                for i, row in enumerate(rows, start=1):
                    if len(row) < 4:
                        skipped += 1
                        continue
                    ccode, pcode, cdate, price = (row[0].strip(), row[1].strip(),
                                                  row[2].strip(), row[3].strip())
                    promo = 1 if len(row) > 4 and row[4].strip().lower() in ('1', 'y', 'yes', 'да', 'true') else 0
                    if ccode not in comps or pcode not in prods:
                        skipped += 1
                        if len(errors) < 5:
                            errors.append(f"строка {i}: неизвестный код {ccode}/{pcode}")
                        continue
                    try:
                        price_v = float(price.replace(',', '.'))
                    except ValueError:
                        skipped += 1
                        if len(errors) < 5:
                            errors.append(f"строка {i}: некорректная цена «{price}»")
                        continue
                    prod_id, our_price = prods[pcode]
                    r = db.execute_query(
                        "MERGE INTO PLG_COMPETITOR_PRICES t USING (SELECT :p_c AS C, :p_p AS P, "
                        "TO_DATE(:p_d, 'YYYY-MM-DD') AS D FROM DUAL) s "
                        "ON (t.COMPETITOR_ID = s.C AND t.PRODUCT_ID = s.P AND t.CHECK_DATE = s.D) "
                        "WHEN MATCHED THEN UPDATE SET t.PRICE = :p_price, t.OUR_PRICE = :p_our, "
                        "t.IS_PROMO = :p_promo, t.SOURCE = 'manual' "
                        "WHEN NOT MATCHED THEN INSERT (COMPETITOR_ID, PRODUCT_ID, CHECK_DATE, PRICE, "
                        "OUR_PRICE, IS_PROMO, SOURCE) VALUES (s.C, s.P, s.D, :p_price, :p_our, "
                        ":p_promo, 'manual')",
                        {"p_c": comps[ccode], "p_p": prod_id, "p_d": cdate,
                         "p_price": price_v, "p_our": our_price, "p_promo": promo})
                    if r.get("success"):
                        imported += 1
                    else:
                        skipped += 1
                        if len(errors) < 5:
                            errors.append(f"строка {i}: {r.get('message', '')[:80]}")
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("import", "competitor_prices", None,
                                   f"imported={imported} skipped={skipped}")
        return {"success": True, "imported": imported, "skipped": skipped, "errors": errors}

    # ==================== Рынки других стран ====================

    @staticmethod
    def get_markets(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_MARKETS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY RETAIL_VOLUME_MLN DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_market(data: Dict, market_id: Optional[int] = None) -> Dict:
        params = {
            "p_ds": data.get("dataset_id"),
            "p_code": (data.get("country_code") or "").strip().upper(),
            "p_pop": data.get("population_mln"),
            "p_gdp": data.get("gdp_per_capita"),
            "p_curr": data.get("currency"),
            "p_retail": data.get("retail_volume_mln"),
            "p_modern": data.get("modern_trade_pct"),
            "p_top5": data.get("top5_share_pct"),
            "p_check": data.get("avg_check"),
            "p_check_eur": data.get("avg_check_eur"),
            "p_per100k": data.get("stores_per_100k"),
            "p_pl": data.get("private_label_pct"),
            "p_notes": data.get("notes"),
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код страны и название рынка обязательны"}
        try:
            with DatabaseModel() as db:
                if market_id:
                    params["p_id"] = int(market_id)
                    r = db.execute_query(
                        "UPDATE PLG_MARKETS SET COUNTRY_CODE = :p_code, NAME_RU = :p_name_ru, "
                        "NAME_RO = :p_name_ro, NAME_EN = :p_name_en, POPULATION_MLN = :p_pop, "
                        "GDP_PER_CAPITA = :p_gdp, CURRENCY = :p_curr, RETAIL_VOLUME_MLN = :p_retail, "
                        "MODERN_TRADE_PCT = :p_modern, TOP5_SHARE_PCT = :p_top5, AVG_CHECK = :p_check, "
                        "AVG_CHECK_EUR = :p_check_eur, STORES_PER_100K = :p_per100k, "
                        "PRIVATE_LABEL_PCT = :p_pl, NOTES = :p_notes WHERE ID = :p_id",
                        {k: v for k, v in params.items() if k != "p_ds"})
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_MARKETS (DATASET_ID, COUNTRY_CODE, NAME_RU, NAME_RO, NAME_EN, "
                        "POPULATION_MLN, GDP_PER_CAPITA, CURRENCY, RETAIL_VOLUME_MLN, MODERN_TRADE_PCT, "
                        "TOP5_SHARE_PCT, AVG_CHECK, AVG_CHECK_EUR, STORES_PER_100K, PRIVATE_LABEL_PCT, NOTES) "
                        "VALUES (:p_ds, :p_code, :p_name_ru, :p_name_ro, :p_name_en, :p_pop, :p_gdp, "
                        ":p_curr, :p_retail, :p_modern, :p_top5, :p_check, :p_check_eur, :p_per100k, "
                        ":p_pl, :p_notes)", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if market_id else "create", "market",
                                   market_id, params["p_code"])
        return {"success": True}

    @staticmethod
    def delete_market(market_id: int) -> Dict:
        return PlanogramController._delete("PLG_MARKETS", market_id, "market")

    @staticmethod
    def get_market_chains(dataset_id: Optional[int] = None, market_id: Optional[int] = None,
                          lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        sql = "SELECT * FROM V_PLG_MARKET_CHAINS WHERE 1 = 1"
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        if market_id:
            sql += " AND MARKET_ID = :p_m"
            params["p_m"] = int(market_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY REVENUE_MLN DESC NULLS LAST", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_market_chain(market_id: int, data: Dict, chain_id: Optional[int] = None) -> Dict:
        params = {
            "p_m": int(market_id),
            "p_name": (data.get("name") or "").strip(),
            "p_owner": data.get("owner_group"),
            "p_fmt": data.get("format_mix"),
            "p_stores": data.get("store_count"),
            "p_rev": data.get("revenue_mln"),
            "p_share": data.get("market_share_pct"),
            "p_sqm": data.get("avg_store_sqm"),
            "p_sku": data.get("sku_count"),
            "p_pl": data.get("private_label_pct"),
            "p_chk": data.get("avg_check_eur"),
            "p_online": data.get("online_share_pct"),
            "p_loy": 1 if data.get("loyalty_program", 1) else 0,
            "p_bench": 1 if data.get("is_benchmark") else 0,
            "p_notes": data.get("notes"),
        }
        if not params["p_name"]:
            return {"success": False, "error": "Не указано название сети"}
        try:
            with DatabaseModel() as db:
                if chain_id:
                    params["p_id"] = int(chain_id)
                    r = db.execute_query(
                        "UPDATE PLG_MARKET_CHAINS SET NAME = :p_name, OWNER_GROUP = :p_owner, "
                        "FORMAT_MIX = :p_fmt, STORE_COUNT = :p_stores, REVENUE_MLN = :p_rev, "
                        "MARKET_SHARE_PCT = :p_share, AVG_STORE_SQM = :p_sqm, SKU_COUNT = :p_sku, "
                        "PRIVATE_LABEL_PCT = :p_pl, AVG_CHECK_EUR = :p_chk, "
                        "ONLINE_SHARE_PCT = :p_online, LOYALTY_PROGRAM = :p_loy, "
                        "IS_BENCHMARK = :p_bench, NOTES = :p_notes WHERE ID = :p_id", params)
                else:
                    r = db.execute_query(
                        "INSERT INTO PLG_MARKET_CHAINS (MARKET_ID, NAME, OWNER_GROUP, FORMAT_MIX, "
                        "STORE_COUNT, REVENUE_MLN, MARKET_SHARE_PCT, AVG_STORE_SQM, SKU_COUNT, "
                        "PRIVATE_LABEL_PCT, AVG_CHECK_EUR, ONLINE_SHARE_PCT, LOYALTY_PROGRAM, "
                        "IS_BENCHMARK, NOTES) "
                        "VALUES (:p_m, :p_name, :p_owner, :p_fmt, :p_stores, :p_rev, :p_share, "
                        ":p_sqm, :p_sku, :p_pl, :p_chk, :p_online, :p_loy, :p_bench, :p_notes)",
                        params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if chain_id else "create", "market_chain",
                                   chain_id, params["p_name"])
        return {"success": True}

    @staticmethod
    def delete_market_chain(chain_id: int) -> Dict:
        return PlanogramController._delete("PLG_MARKET_CHAINS", chain_id, "market_chain")

    @staticmethod
    def get_market_benchmark(dataset_id: Optional[int] = None, lang: str = DEFAULT_LANG) -> Dict:
        """
        Данные пузырьковой диаграммы: сети других стран плюс точка «наша сеть»,
        посчитанная из фактических магазинов и метрик набора.
        """
        lang = PlanogramController.lang(lang)
        chains = PlanogramController.get_market_chains(dataset_id, None, lang)
        if not chains.get("success"):
            return chains
        markets = PlanogramController.get_markets(dataset_id, lang)
        try:
            with DatabaseModel() as db:
                sql = ("SELECT COUNT(DISTINCT s.ID) AS STORE_COUNT, "
                       "ROUND(AVG(s.AREA_SQM), 1) AS AVG_SQM, "
                       "ROUND(SUM(m.REVENUE) / 1000000, 3) AS REVENUE_MLN, "
                       "ROUND(AVG(m.AVG_CHECK), 2) AS AVG_CHECK "
                       "FROM PLG_STORES s LEFT JOIN PLG_STORE_METRICS m ON m.STORE_ID = s.ID "
                       "AND m.METRIC_DATE >= TRUNC(SYSDATE) - 365 WHERE 1 = 1")
                params: Dict[str, Any] = {}
                if dataset_id:
                    sql += " AND s.DATASET_ID = :p_ds"
                    params["p_ds"] = int(dataset_id)
                ours = PlanogramController._first(db.execute_query(sql, params)) or {}
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Средний чек приводим к евро по курсу MDL/EUR, иначе точки несопоставимы
        mdl_eur = 19.4
        our_point = {
            "name": "—", "is_ours": 1, "country_code": "MD",
            "store_count": ours.get("store_count") or 0,
            "avg_store_sqm": ours.get("avg_sqm"),
            "revenue_mln": ours.get("revenue_mln"),
            "avg_check_eur": round(float(ours.get("avg_check") or 0) / mdl_eur, 2),
            "market_share_pct": None, "private_label_pct": None,
        }
        return {"success": True, "lang": lang, "data": {
            "chains": chains["data"],
            "markets": markets.get("data", []),
            "ours": our_point}}

    # ==================== Фреш: маршруты и профили категорий ====================

    @staticmethod
    def get_fresh_routes(lang: str = DEFAULT_LANG, store_id: Optional[int] = None) -> Dict:
        """Маршруты поставки скоропортящегося товара по магазину."""
        sql = "SELECT * FROM V_PLG_FRESH_ROUTES"
        params: Dict[str, Any] = {}
        if store_id:
            sql += " WHERE STORE_ID = :p_st"
            params["p_st"] = store_id
        sql += " ORDER BY STORE_CODE, PRIORITY, CATEGORY_NAME_RU"
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "lang": lang,
                        "data": PlanogramController._localized(r, lang)}
        except Exception as e:                                   # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_fresh_route(route_id: int, payload: Dict) -> Dict:
        """
        Правка маршрута. Календари проверяем строго: маска не из семи нулей
        и единиц молча превратила бы график поставок в «каждый день»,
        и заказ поехал бы по несуществующему расписанию.
        """
        for key in ("order_days", "delivery_days"):
            val = payload.get(key)
            if val is not None and (len(str(val)) != 7 or set(str(val)) - {"0", "1"}):
                return {"success": False,
                        "error": f"Календарь {key}: нужны семь символов из 0 и 1"}
        if payload.get("delivery_days") == "0000000":
            return {"success": False, "error": "Нельзя оставить маршрут без дней поставки"}
        fields = {
            "ROUTE": payload.get("route"), "LEAD_TIME_DAYS": payload.get("lead_time_days"),
            "TRANSIT_DAYS": payload.get("transit_days"), "ORDER_DAYS": payload.get("order_days"),
            "DELIVERY_DAYS": payload.get("delivery_days"), "CUTOFF_TIME": payload.get("cutoff_time"),
            "MIN_ORDER_QTY": payload.get("min_order_qty"),
            "MIN_ORDER_AMOUNT": payload.get("min_order_amount"),
            "RECEIPT_SHELF_PCT": payload.get("receipt_shelf_pct"),
            "SUPPLIER_ID": payload.get("supplier_id"), "DC_ID": payload.get("dc_id"),
            "IS_ACTIVE": payload.get("is_active"), "NOTES": payload.get("notes"),
        }
        sets, params = [], {"p_id": route_id}
        for i, (col, val) in enumerate(f for f in fields.items() if f[1] is not None):
            sets.append(f"{col} = :p_{i}")
            params[f"p_{i}"] = val
        if not sets:
            return {"success": False, "error": "Нечего менять"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    f"UPDATE PLG_FRESH_ROUTES SET {', '.join(sets)} WHERE ID = :p_id", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
            PlanogramController._audit("update", "fresh_route", route_id, str(payload)[:2000])
            return {"success": True}
        except Exception as e:                                   # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_fresh_profiles(lang: str = DEFAULT_LANG) -> Dict:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT * FROM V_PLG_FRESH_PROFILES ORDER BY SHELF_LIFE_DAYS, CATEGORY_CODE")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "lang": lang,
                        "data": PlanogramController._localized(r, lang)}
        except Exception as e:                                   # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_fresh_profile(profile_id: int, payload: Dict) -> Dict:
        fields = {
            "TEMP_REGIME": payload.get("temp_regime"),
            "SHELF_LIFE_DAYS": payload.get("shelf_life_days"),
            "RECEIPT_SHELF_PCT": payload.get("receipt_shelf_pct"),
            "PRESENTATION_MIN": payload.get("presentation_min"),
            "SALVAGE_PCT": payload.get("salvage_pct"),
            "WASTE_TARGET_PCT": payload.get("waste_target_pct"),
            "MARGIN_PCT": payload.get("margin_pct"),
            "ROUND_STEP": payload.get("round_step"),
            "IS_ACTIVE": payload.get("is_active"),
        }
        sets, params = [], {"p_id": profile_id}
        for i, (col, val) in enumerate(f for f in fields.items() if f[1] is not None):
            sets.append(f"{col} = :p_{i}")
            params[f"p_{i}"] = val
        if not sets:
            return {"success": False, "error": "Нечего менять"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    f"UPDATE PLG_FRESH_PROFILES SET {', '.join(sets)} WHERE ID = :p_id", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                db.connection.commit()
            PlanogramController._audit("update", "fresh_profile", profile_id, str(payload)[:2000])
            return {"success": True}
        except Exception as e:                                   # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_fresh_order(lang: str = DEFAULT_LANG, run_id: Optional[int] = None,
                        store_id: Optional[int] = None) -> Dict:
        """
        Рекомендуемый заказ фреш. Без run_id берётся последний завершённый
        прогон фреш-модели: оператор открывает раздел и сразу видит цифры,
        а не пустой экран с просьбой выбрать прогон.
        """
        try:
            with DatabaseModel() as db:
                if run_id:
                    run_ids = [int(run_id)]
                else:
                    # Берём последний прогон КАЖДОЙ фреш-модели, а не просто
                    # максимальный ID: иначе экран показывает только тот маршрут,
                    # который считали последним, и половина заказа исчезает.
                    r = db.execute_query(
                        "SELECT MAX(r.ID) AS ID FROM PLG_FCT_RUNS r "
                        "JOIN PLG_FCT_MODELS m ON m.ID = r.MODEL_ID "
                        "WHERE m.ALGORITHM = 'fresh' AND r.STATUS = 'done' "
                        "AND r.RUN_MODE = 'forecast' GROUP BY r.MODEL_ID")
                    run_ids = [int(x["id"]) for x in PlanogramController._rows(r) if x.get("id")]
                if not run_ids:
                    return {"success": True, "lang": lang, "data": [], "run_id": None,
                            "message": "Прогонов фреш-модели ещё не было"}
                in_list = ",".join(str(int(x)) for x in run_ids)   # значения из БД, не из запроса
                sql = f"SELECT * FROM V_PLG_FRESH_ORDER WHERE RUN_ID IN ({in_list})"
                params: Dict[str, Any] = {}
                if store_id:
                    sql += " AND STORE_ID = :p_st"
                    params["p_st"] = store_id
                sql += " ORDER BY ORDER_AMOUNT DESC NULLS LAST"
                res = db.execute_query(sql, params)
                if not res.get("success"):
                    return PlanogramController._fail(res)
                data = PlanogramController._localized(res, lang)
                summary = db.execute_query(
                    "SELECT ROUTE, COUNT(*) AS SKU_COUNT, ROUND(SUM(ORDER_QTY),2) AS ORDER_QTY, "
                    "ROUND(SUM(ORDER_AMOUNT),2) AS ORDER_AMOUNT, "
                    "ROUND(SUM(WASTE_FORECAST),2) AS WASTE_QTY, "
                    "ROUND(SUM(WASTE_AMOUNT),2) AS WASTE_AMOUNT, "
                    "SUM(SHELF_LIMITED) AS SHELF_LIMITED "
                    f"FROM V_PLG_FRESH_ORDER WHERE RUN_ID IN ({in_list})"
                    + (" AND STORE_ID = :p_st" if store_id else "")
                    + " GROUP BY ROUTE", params)
            return {"success": True, "lang": lang, "run_id": run_ids[0],
                    "run_ids": run_ids, "data": data,
                    "summary": PlanogramController._rows(summary)}
        except Exception as e:                                   # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ==================== Бизнес-процессы (схемы draw.io) ====================

    @staticmethod
    def get_processes(lang: str = DEFAULT_LANG, with_xml: bool = False) -> Dict:
        """
        Список бизнес-процессов модуля. XML схемы по умолчанию не отдаём —
        он весит килобайты и в списке не нужен.
        """
        lang = PlanogramController.lang(lang)
        cols = ("ID, CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, "
                "NODE_COUNT, SORT_ORDER, STATUS, UPDATED_BY, UPDATED_AT")
        if with_xml:
            cols += ", DIAGRAM_XML"
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    f"SELECT {cols} FROM PLG_PROCESSES WHERE STATUS <> 'archived' "
                    "ORDER BY SORT_ORDER, CODE")
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang),
                        "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_process(code: str, lang: str = DEFAULT_LANG) -> Dict:
        """Один процесс вместе со схемой в формате draw.io."""
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                row = PlanogramController._first(db.execute_query(
                    "SELECT ID, CODE, NAME_RU, NAME_RO, NAME_EN, DESCR_RU, DESCR_RO, DESCR_EN, "
                    "DIAGRAM_XML, NODE_COUNT, SORT_ORDER, STATUS, UPDATED_BY, UPDATED_AT "
                    "FROM PLG_PROCESSES WHERE CODE = :p_code OR TO_CHAR(ID) = :p_code",
                    {"p_code": str(code)}))
                if not row:
                    return {"success": False, "error": "Процесс не найден"}
                return {"success": True, "data": PlanogramController._localize([row], lang)[0],
                        "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_process(data: Dict, process_id: Optional[int] = None) -> Dict:
        """
        Создание или правка процесса. XML принимается как есть — это выгрузка
        из draw.io; проверяем только, что он разбирается и содержит mxGraphModel,
        иначе просмотрщик получит мусор и раздел «сломается» без объяснения.
        """
        import xml.etree.ElementTree as ET

        xml = (data.get("diagram_xml") or "").strip()
        if xml:
            try:
                root = ET.fromstring(xml)
            except ET.ParseError as e:
                return {"success": False, "error": f"Схема не разбирается как XML: {e}"}
            model = root if root.tag == 'mxGraphModel' else root.find('.//mxGraphModel')
            if model is None:
                return {"success": False,
                        "error": "В файле нет mxGraphModel — это не схема draw.io. "
                                 "Экспортируйте из diagrams.net как .drawio или XML."}
            xml = ET.tostring(model, encoding='unicode')
            nodes = len([c for c in model.findall('.//mxCell') if c.get('vertex') == '1'])
        else:
            nodes = 0

        params = {
            "p_code": (data.get("code") or "").strip(),
            "p_descr_ru": data.get("descr_ru") or data.get("description"),
            "p_descr_ro": data.get("descr_ro"),
            "p_descr_en": data.get("descr_en"),
            "p_nodes": nodes,
            "p_sort": data.get("sort_order") or 0,
            "p_status": data.get("status") or "active",
            "p_user": PlanogramController._username(),
        }
        params.update(PlanogramController._multilang_params(data, "name", "p_name", required=True))
        if not params["p_code"] or not params["p_name_ru"]:
            return {"success": False, "error": "Код и название процесса обязательны"}

        try:
            with DatabaseModel() as db:
                cur = db.connection.cursor()
                if process_id:
                    cur.execute(
                        "UPDATE PLG_PROCESSES SET CODE = :p_code, NAME_RU = :p_name_ru, "
                        "NAME_RO = :p_name_ro, NAME_EN = :p_name_en, DESCR_RU = :p_descr_ru, "
                        "DESCR_RO = :p_descr_ro, DESCR_EN = :p_descr_en, "
                        "DIAGRAM_XML = NVL(:p_xml, DIAGRAM_XML), NODE_COUNT = :p_nodes, "
                        "SORT_ORDER = :p_sort, STATUS = :p_status, UPDATED_BY = :p_user "
                        "WHERE ID = :p_id",
                        {**params, "p_xml": xml or None, "p_id": int(process_id)})
                else:
                    cur.execute(
                        "INSERT INTO PLG_PROCESSES (CODE, NAME_RU, NAME_RO, NAME_EN, "
                        "DESCR_RU, DESCR_RO, DESCR_EN, DIAGRAM_XML, NODE_COUNT, "
                        "SORT_ORDER, STATUS, UPDATED_BY) "
                        "VALUES (:p_code, :p_name_ru, :p_name_ro, :p_name_en, :p_descr_ru, "
                        ":p_descr_ro, :p_descr_en, :p_xml, :p_nodes, :p_sort, :p_status, :p_user)",
                        {**params, "p_xml": xml or None})
                db.connection.commit()
        except Exception as e:
            return {"success": False, "error": str(e)}
        PlanogramController._audit("update" if process_id else "create", "process",
                                   process_id, params["p_code"])
        return {"success": True, "nodes": nodes}

    @staticmethod
    def delete_process(process_id: int) -> Dict:
        return PlanogramController._delete("PLG_PROCESSES", process_id, "process")

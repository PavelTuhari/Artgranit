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
    def get_stores(lang: str = DEFAULT_LANG) -> Dict:
        lang = PlanogramController.lang(lang)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT s.ID, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN, s.CITY, "
                    "s.ADDRESS_RU, s.ADDRESS_RO, s.ADDRESS_EN, s.AREA_SQM, s.MAP_WIDTH, s.MAP_HEIGHT, "
                    "s.CHECKOUT_QTY, s.MANAGER_NAME, s.STATUS, "
                    "(SELECT COUNT(*) FROM PLG_ZONES z WHERE z.STORE_ID = s.ID) AS ZONE_COUNT "
                    "FROM PLG_STORES s WHERE s.STATUS <> 'inactive' "
                    "ORDER BY ZONE_COUNT DESC, s.CODE"
                )
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _resolve_store(db: DatabaseModel, store_id: Optional[int]) -> Optional[int]:
        """Возвращает переданный магазин либо первый доступный."""
        if store_id:
            return int(store_id)
        r = db.execute_query("SELECT MIN(ID) AS ID FROM PLG_STORES WHERE STATUS = 'active'")
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

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import oracledb

from .database import DatabaseConnection


_DECOR_CORE_TABLE = "DECOR_MATERIALS"
_SCHEMA_READY = False


def _db_error_code(exc: Exception) -> int | None:
    err = getattr(exc, "args", [None])[0]
    return getattr(err, "code", None)


def _legacy_state(default_factory: Callable[[], dict[str, Any]] | None, fallback_path: Path | None) -> dict[str, Any]:
    if fallback_path and fallback_path.exists():
        try:
            payload = json.loads(fallback_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass

    return default_factory() if default_factory else {}


def ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    connection = DatabaseConnection.get_connection()
    try:
        with connection.cursor() as cursor:
            for statement in (
                """
                CREATE TABLE DECOR_MATERIALS (
                  ID NUMBER PRIMARY KEY,
                  CODE VARCHAR2(80) NOT NULL,
                  NAME VARCHAR2(300) NOT NULL,
                  NAME_ORIGINAL VARCHAR2(300),
                  ORIGINAL_LANG VARCHAR2(16),
                  NAME_RO VARCHAR2(300),
                  IMAGE_URL VARCHAR2(1000),
                  CATEGORY VARCHAR2(50),
                  UNIT VARCHAR2(20),
                  UNIT_PRICE NUMBER(14,2),
                  CURRENCY VARCHAR2(10),
                  SOURCE_FILE VARCHAR2(300),
                  SOURCE_SHEET VARCHAR2(200),
                  NOTES VARCHAR2(1000),
                  ACTIVE CHAR(1),
                  CREATED_AT VARCHAR2(40),
                  UPDATED_AT VARCHAR2(40)
                )
                """,
                "CREATE UNIQUE INDEX UQ_DECOR_MATERIALS_CODE ON DECOR_MATERIALS (CODE)",
                """
                CREATE TABLE DECOR_STATUSES (
                  ID NUMBER PRIMARY KEY,
                  CODE VARCHAR2(50) NOT NULL,
                  NAME VARCHAR2(200) NOT NULL
                )
                """,
                "CREATE UNIQUE INDEX UQ_DECOR_STATUSES_CODE ON DECOR_STATUSES (CODE)",
                """
                CREATE TABLE DECOR_SETTINGS (
                  SETTINGS_ID NUMBER PRIMARY KEY,
                  CURRENCY VARCHAR2(10),
                  EXCHANGE_RATE_USD_TO_MDL NUMBER(14,4),
                  MARKUP_PERCENT NUMBER(14,4),
                  WASTE_PERCENT NUMBER(14,4),
                  PROFILE_WEIGHT_KG_PER_M2 NUMBER(14,4),
                  ACCESSORY_FIXED_PER_M2 NUMBER(14,4),
                  DRAINAGE_FIXED NUMBER(14,4),
                  TRANSPORT_FIXED NUMBER(14,4),
                  INSTALL_RATE_M2 NUMBER(14,4)
                )
                """,
                """
                CREATE TABLE DECOR_SETTING_GLASS_RATES (
                  SETTINGS_ID NUMBER NOT NULL,
                  SYSTEM_TYPE VARCHAR2(50) NOT NULL,
                  RATE NUMBER(14,4),
                  CONSTRAINT PK_DECOR_SETTING_GLASS_RATES PRIMARY KEY (SETTINGS_ID, SYSTEM_TYPE),
                  CONSTRAINT FK_DECOR_SET_GLASS_SETTINGS FOREIGN KEY (SETTINGS_ID) REFERENCES DECOR_SETTINGS(SETTINGS_ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SETTING_LED_OPTIONS (
                  SETTINGS_ID NUMBER NOT NULL,
                  OPTION_CODE VARCHAR2(50) NOT NULL,
                  RATE NUMBER(14,4),
                  CONSTRAINT PK_DECOR_SETTING_LED_OPTIONS PRIMARY KEY (SETTINGS_ID, OPTION_CODE),
                  CONSTRAINT FK_DECOR_SET_LED_SETTINGS FOREIGN KEY (SETTINGS_ID) REFERENCES DECOR_SETTINGS(SETTINGS_ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SETTING_LIST_VALUES (
                  SETTINGS_ID NUMBER NOT NULL,
                  LIST_TYPE VARCHAR2(50) NOT NULL,
                  VALUE_TEXT VARCHAR2(300) NOT NULL,
                  SORT_ORDER NUMBER NOT NULL,
                  CONSTRAINT PK_DECOR_SETTING_LIST_VALUES PRIMARY KEY (SETTINGS_ID, LIST_TYPE, SORT_ORDER),
                  CONSTRAINT FK_DECOR_SET_LIST_SETTINGS FOREIGN KEY (SETTINGS_ID) REFERENCES DECOR_SETTINGS(SETTINGS_ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_COUNTERS (
                  COUNTER_KEY VARCHAR2(50) PRIMARY KEY,
                  COUNTER_VALUE NUMBER NOT NULL
                )
                """,
                """
                CREATE TABLE DECOR_ORDERS (
                  ID NUMBER PRIMARY KEY,
                  ORDER_NUMBER VARCHAR2(50) NOT NULL,
                  BARCODE VARCHAR2(50),
                  PRODUCT_TYPE VARCHAR2(20),
                  CLIENT_NAME VARCHAR2(300),
                  CLIENT_PHONE VARCHAR2(100),
                  CLIENT_EMAIL VARCHAR2(300),
                  PROJECT_TYPE VARCHAR2(200),
                  PROJECT_NAME VARCHAR2(300),
                  LOCATION VARCHAR2(300),
                  COLOR VARCHAR2(200),
                  NOTES VARCHAR2(2000),
                  STATUS_ID NUMBER,
                  CURRENCY VARCHAR2(10),
                  TOTAL_AMOUNT NUMBER(14,2),
                  CREATED_AT VARCHAR2(40),
                  UPDATED_AT VARCHAR2(40),
                  CONSTRAINT FK_DECOR_ORD_STATUS FOREIGN KEY (STATUS_ID) REFERENCES DECOR_STATUSES(ID)
                )
                """,
                "CREATE UNIQUE INDEX UQ_DECOR_ORDERS_NUMBER ON DECOR_ORDERS (ORDER_NUMBER)",
                """
                CREATE TABLE DECOR_ORDER_INPUTS (
                  ORDER_ID NUMBER PRIMARY KEY,
                  WIDTH_MM NUMBER(14,3),
                  PROJECTION_MM NUMBER(14,3),
                  FRONT_HEIGHT_MM NUMBER(14,3),
                  REAR_HEIGHT_MM NUMBER(14,3),
                  SYSTEM_TYPE VARCHAR2(50),
                  LED_OPTION VARCHAR2(50),
                  INCLUDE_INSTALLATION CHAR(1),
                  INCLUDE_TRANSPORT CHAR(1),
                  INCLUDE_DRAINAGE CHAR(1),
                  EXTRA_ITEMS_COUNT NUMBER,
                  VARIANT_KEY VARCHAR2(100),
                  VARIANT_LABEL VARCHAR2(200),
                  FAMILY VARCHAR2(50),
                  HEIGHT_MM NUMBER(14,3),
                  ORIENTATION VARCHAR2(20),
                  INCLUDE_THRESHOLD CHAR(1),
                  INCLUDE_GLASS CHAR(1),
                  GLASS_SYSTEM VARCHAR2(50),
                  GLASS_FINISH VARCHAR2(50),
                  GLASS_THICKNESS VARCHAR2(50),
                  INCLUDE_ASSEMBLY CHAR(1),
                  CONSTRAINT FK_DECOR_ORD_INPUTS FOREIGN KEY (ORDER_ID) REFERENCES DECOR_ORDERS(ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_ORDER_METRICS (
                  ORDER_ID NUMBER PRIMARY KEY,
                  AREA_M2 NUMBER(14,3),
                  PERIMETER_M NUMBER(14,3),
                  SLOPE_MM NUMBER(14,3),
                  SLOPE_PERCENT NUMBER(14,3),
                  POST_COUNT NUMBER,
                  SECTION_COUNT NUMBER,
                  BEAM_COUNT NUMBER,
                  RAFTER_LENGTH_M NUMBER(14,3),
                  FRAME_LENGTH_M NUMBER(14,3),
                  PROFILE_WEIGHT_TOTAL_KG NUMBER(14,3),
                  GLASS_PANEL_COUNT NUMBER,
                  GLASS_PANEL_AREA_M2 NUMBER(14,3),
                  GLASS_PANEL_WIDTH_M NUMBER(14,3),
                  GLASS_PANEL_LENGTH_M NUMBER(14,3),
                  TOTAL_PANELS NUMBER,
                  PANEL_WIDTH_MM NUMBER(14,3),
                  PROFILE_WEIGHT_KG NUMBER(14,3),
                  CONSTRAINT FK_DECOR_ORD_METRICS FOREIGN KEY (ORDER_ID) REFERENCES DECOR_ORDERS(ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_ORDER_SUMMARY (
                  ORDER_ID NUMBER PRIMARY KEY,
                  CURRENCY VARCHAR2(10),
                  PROFILE_COST NUMBER(14,2),
                  ACCESSORY_COST NUMBER(14,2),
                  GLASS_COST NUMBER(14,2),
                  ASSEMBLY_COST NUMBER(14,2),
                  INSTALLATION_COST NUMBER(14,2),
                  DIRECT_COST NUMBER(14,2),
                  WASTE_AMOUNT NUMBER(14,2),
                  SUBTOTAL NUMBER(14,2),
                  MARGIN_AMOUNT NUMBER(14,2),
                  TOTAL NUMBER(14,2),
                  EXCHANGE_RATE_USD_TO_MDL NUMBER(14,4),
                  TOTAL_MDL NUMBER(14,2),
                  EXTRA_ITEMS_AMOUNT NUMBER(14,2),
                  TOTAL_USD NUMBER(14,2),
                  CONSTRAINT FK_DECOR_ORD_SUMMARY FOREIGN KEY (ORDER_ID) REFERENCES DECOR_ORDERS(ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_ORDER_ITEMS (
                  ORDER_ID NUMBER NOT NULL,
                  LINE_NO NUMBER NOT NULL,
                  CODE VARCHAR2(80),
                  NAME VARCHAR2(300),
                  QTY NUMBER(14,4),
                  UNIT VARCHAR2(20),
                  UNIT_PRICE NUMBER(14,4),
                  AMOUNT NUMBER(14,2),
                  CATEGORY VARCHAR2(50),
                  SOURCE_NAME VARCHAR2(50),
                  IMAGE_URL VARCHAR2(1000),
                  LENGTH_M NUMBER(14,4),
                  TOTAL_LENGTH_M NUMBER(14,4),
                  WEIGHT_KG NUMBER(14,4),
                  CONSTRAINT PK_DECOR_ORDER_ITEMS PRIMARY KEY (ORDER_ID, LINE_NO),
                  CONSTRAINT FK_DECOR_ORD_ITEMS FOREIGN KEY (ORDER_ID) REFERENCES DECOR_ORDERS(ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_MATERIALS (
                  ID NUMBER PRIMARY KEY,
                  CODE VARCHAR2(80) NOT NULL,
                  NAME VARCHAR2(300) NOT NULL,
                  NAME_RO VARCHAR2(300),
                  UNIT VARCHAR2(20),
                  CURRENCY VARCHAR2(10),
                  FAMILY VARCHAR2(50),
                  CATEGORY VARCHAR2(50),
                  UNIT_PRICE NUMBER(14,2),
                  WEIGHT_G_PER_M NUMBER(14,3),
                  ACTIVE CHAR(1)
                )
                """,
                "CREATE UNIQUE INDEX UQ_DECOR_SLIDING_MAT_CODE ON DECOR_SLIDING_MATERIALS (CODE)",
                """
                CREATE TABLE DECOR_SLIDING_SETTINGS (
                  SETTINGS_ID NUMBER PRIMARY KEY,
                  CURRENCY VARCHAR2(10),
                  ASSEMBLY_RATE NUMBER(14,4),
                  INSTALLATION_RATE NUMBER(14,4),
                  PAINTING_RATE_M2 NUMBER(14,4),
                  MARKUP_PERCENT NUMBER(14,4),
                  WASTE_PERCENT NUMBER(14,4),
                  EXCHANGE_RATE_MDL_TO_USD NUMBER(14,4),
                  ASSEMBLY_BASIS VARCHAR2(20),
                  INSTALLATION_BASIS VARCHAR2(20)
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_GLASS_RATES (
                  SETTINGS_ID NUMBER NOT NULL,
                  SYSTEM_TYPE VARCHAR2(50) NOT NULL,
                  FINISH_KEY VARCHAR2(100) NOT NULL,
                  RATE NUMBER(14,4),
                  CONSTRAINT PK_DECOR_SLIDING_GLASS_RATES PRIMARY KEY (SETTINGS_ID, SYSTEM_TYPE, FINISH_KEY),
                  CONSTRAINT FK_DECOR_SL_GLASS_SET FOREIGN KEY (SETTINGS_ID) REFERENCES DECOR_SLIDING_SETTINGS(SETTINGS_ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_LIST_VALUES (
                  SETTINGS_ID NUMBER NOT NULL,
                  LIST_TYPE VARCHAR2(50) NOT NULL,
                  VALUE_TEXT VARCHAR2(300) NOT NULL,
                  SORT_ORDER NUMBER NOT NULL,
                  CONSTRAINT PK_DECOR_SLIDING_LIST_VALUES PRIMARY KEY (SETTINGS_ID, LIST_TYPE, SORT_ORDER),
                  CONSTRAINT FK_DECOR_SL_LIST_SET FOREIGN KEY (SETTINGS_ID) REFERENCES DECOR_SLIDING_SETTINGS(SETTINGS_ID) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_VARIANTS (
                  VARIANT_KEY VARCHAR2(100) PRIMARY KEY,
                  FAMILY VARCHAR2(50),
                  PANELS VARCHAR2(20),
                  LABEL VARCHAR2(200),
                  WIDTH_MIN_MM NUMBER(14,3),
                  WIDTH_MAX_MM NUMBER(14,3),
                  HEIGHT_MIN_MM NUMBER(14,3),
                  HEIGHT_MAX_MM NUMBER(14,3),
                  MAX_AREA_M2 NUMBER(14,3),
                  MAX_PANEL_WIDTH_MM NUMBER(14,3),
                  IS_DOUBLE CHAR(1)
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_VARIANT_PROFILES (
                  VARIANT_KEY VARCHAR2(100) NOT NULL,
                  PROFILE_KIND VARCHAR2(20) NOT NULL,
                  CODE VARCHAR2(80) NOT NULL,
                  DESC_TEXT VARCHAR2(300),
                  PIECES NUMBER,
                  PER_PANEL CHAR(1),
                  LENGTH_BASIS VARCHAR2(20),
                  LENGTH_OFFSET_MM NUMBER(14,3),
                  LENGTH_MM NUMBER(14,3),
                  CONDITION_EXPR VARCHAR2(50),
                  CONSTRAINT PK_DECOR_SLIDING_VAR_PROF PRIMARY KEY (VARIANT_KEY, PROFILE_KIND, CODE),
                  CONSTRAINT FK_DECOR_SL_VAR_PROF FOREIGN KEY (VARIANT_KEY) REFERENCES DECOR_SLIDING_VARIANTS(VARIANT_KEY) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_PANEL_OFFSETS (
                  VARIANT_KEY VARCHAR2(100) NOT NULL,
                  PROFILE_KIND VARCHAR2(20) NOT NULL,
                  CODE VARCHAR2(80) NOT NULL,
                  PANEL_LABEL VARCHAR2(50) NOT NULL,
                  OFFSET_MM NUMBER(14,3),
                  CONSTRAINT PK_DECOR_SLIDING_PANEL_OFFSETS PRIMARY KEY (VARIANT_KEY, PROFILE_KIND, CODE, PANEL_LABEL),
                  CONSTRAINT FK_DECOR_SL_PANEL_PROF FOREIGN KEY (VARIANT_KEY, PROFILE_KIND, CODE) REFERENCES DECOR_SLIDING_VARIANT_PROFILES(VARIANT_KEY, PROFILE_KIND, CODE) ON DELETE CASCADE
                )
                """,
                """
                CREATE TABLE DECOR_SLIDING_VARIANT_ACCESSORIES (
                  VARIANT_KEY VARCHAR2(100) NOT NULL,
                  CODE VARCHAR2(80) NOT NULL,
                  QTY NUMBER,
                  CONDITION_EXPR VARCHAR2(50),
                  CONSTRAINT PK_DECOR_SLIDING_VAR_ACC PRIMARY KEY (VARIANT_KEY, CODE),
                  CONSTRAINT FK_DECOR_SL_VAR_ACC FOREIGN KEY (VARIANT_KEY) REFERENCES DECOR_SLIDING_VARIANTS(VARIANT_KEY) ON DELETE CASCADE
                )
                """,
            ):
                try:
                    cursor.execute(statement)
                except oracledb.DatabaseError as exc:
                    if _db_error_code(exc) != 955:
                        raise
        connection.commit()
        _SCHEMA_READY = True
    finally:
        connection.close()


def _is_seeded(cursor: oracledb.Cursor) -> bool:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {_DECOR_CORE_TABLE}")
        return int((cursor.fetchone() or [0])[0] or 0) > 0
    except oracledb.DatabaseError as exc:
        if _db_error_code(exc) == 942:
            return False
        raise


def _as_flag(value: Any) -> str:
    return "Y" if str(value or "N").upper() not in {"N", "0", "FALSE", ""} else "N"


def _replace_state(cursor: oracledb.Cursor, state: dict[str, Any]) -> None:
    for table_name in (
        "DECOR_SLIDING_PANEL_OFFSETS",
        "DECOR_SLIDING_VARIANT_ACCESSORIES",
        "DECOR_SLIDING_VARIANT_PROFILES",
        "DECOR_SLIDING_VARIANTS",
        "DECOR_SLIDING_LIST_VALUES",
        "DECOR_SLIDING_GLASS_RATES",
        "DECOR_SLIDING_SETTINGS",
        "DECOR_SLIDING_MATERIALS",
        "DECOR_ORDER_ITEMS",
        "DECOR_ORDER_SUMMARY",
        "DECOR_ORDER_METRICS",
        "DECOR_ORDER_INPUTS",
        "DECOR_ORDERS",
        "DECOR_COUNTERS",
        "DECOR_SETTING_LIST_VALUES",
        "DECOR_SETTING_LED_OPTIONS",
        "DECOR_SETTING_GLASS_RATES",
        "DECOR_SETTINGS",
        "DECOR_STATUSES",
        "DECOR_MATERIALS",
    ):
        cursor.execute(f"DELETE FROM {table_name}")

    for material in state.get("materials", []):
        cursor.execute(
            """
            INSERT INTO DECOR_MATERIALS (
              ID, CODE, NAME, NAME_ORIGINAL, ORIGINAL_LANG, NAME_RO, IMAGE_URL,
              CATEGORY, UNIT, UNIT_PRICE, CURRENCY, SOURCE_FILE, SOURCE_SHEET,
              NOTES, ACTIVE, CREATED_AT, UPDATED_AT
            ) VALUES (
              :id, :code, :name, :name_original, :original_lang, :name_ro, :image_url,
              :category, :unit, :unit_price, :currency, :source_file, :source_sheet,
              :notes, :active, :created_at, :updated_at
            )
            """,
            {
                "id": int(material.get("id") or 0),
                "code": str(material.get("code") or "").strip(),
                "name": str(material.get("name") or "").strip(),
                "name_original": str(material.get("name_original") or "").strip(),
                "original_lang": str(material.get("original_lang") or "").strip(),
                "name_ro": str(material.get("name_ro") or "").strip(),
                "image_url": str(material.get("image_url") or "").strip(),
                "category": str(material.get("category") or "").strip(),
                "unit": str(material.get("unit") or "").strip(),
                "unit_price": float(material.get("unit_price") or 0),
                "currency": str(material.get("currency") or "").strip(),
                "source_file": str(material.get("source_file") or "").strip(),
                "source_sheet": str(material.get("source_sheet") or "").strip(),
                "notes": str(material.get("notes") or "").strip(),
                "active": _as_flag(material.get("active") or "Y"),
                "created_at": str(material.get("created_at") or "").strip(),
                "updated_at": str(material.get("updated_at") or "").strip(),
            },
        )

    for status in state.get("statuses", []):
        cursor.execute(
            "INSERT INTO DECOR_STATUSES (ID, CODE, NAME) VALUES (:id, :code, :name)",
            {
                "id": int(status.get("id") or 0),
                "code": str(status.get("code") or "").strip(),
                "name": str(status.get("name") or "").strip(),
            },
        )

    settings = state.get("settings", {})
    cursor.execute(
        """
        INSERT INTO DECOR_SETTINGS (
          SETTINGS_ID, CURRENCY, EXCHANGE_RATE_USD_TO_MDL, MARKUP_PERCENT, WASTE_PERCENT,
          PROFILE_WEIGHT_KG_PER_M2, ACCESSORY_FIXED_PER_M2, DRAINAGE_FIXED,
          TRANSPORT_FIXED, INSTALL_RATE_M2
        ) VALUES (
          1, :currency, :exchange_rate_usd_to_mdl, :markup_percent, :waste_percent,
          :profile_weight_kg_per_m2, :accessory_fixed_per_m2, :drainage_fixed,
          :transport_fixed, :install_rate_m2
        )
        """,
        {
            "currency": str(settings.get("currency") or "USD"),
            "exchange_rate_usd_to_mdl": float(settings.get("exchange_rate_usd_to_mdl") or 0),
            "markup_percent": float(settings.get("markup_percent") or 0),
            "waste_percent": float(settings.get("waste_percent") or 0),
            "profile_weight_kg_per_m2": float(settings.get("profile_weight_kg_per_m2") or 0),
            "accessory_fixed_per_m2": float(settings.get("accessory_fixed_per_m2") or 0),
            "drainage_fixed": float(settings.get("drainage_fixed") or 0),
            "transport_fixed": float(settings.get("transport_fixed") or 0),
            "install_rate_m2": float(settings.get("install_rate_m2") or 0),
        },
    )
    for system_type, rate in (settings.get("glass_rate_m2") or {}).items():
        cursor.execute(
            "INSERT INTO DECOR_SETTING_GLASS_RATES (SETTINGS_ID, SYSTEM_TYPE, RATE) VALUES (1, :system_type, :rate)",
            {"system_type": str(system_type), "rate": float(rate or 0)},
        )
    for option_code, rate in (settings.get("led_options") or {}).items():
        cursor.execute(
            "INSERT INTO DECOR_SETTING_LED_OPTIONS (SETTINGS_ID, OPTION_CODE, RATE) VALUES (1, :option_code, :rate)",
            {"option_code": str(option_code), "rate": float(rate or 0)},
        )
    for list_type in ("project_types", "system_types", "colors"):
        for idx, value in enumerate(settings.get(list_type) or [], start=1):
            cursor.execute(
                "INSERT INTO DECOR_SETTING_LIST_VALUES (SETTINGS_ID, LIST_TYPE, VALUE_TEXT, SORT_ORDER) VALUES (1, :list_type, :value_text, :sort_order)",
                {"list_type": list_type, "value_text": str(value), "sort_order": idx},
            )

    counters = {
        "next_material_id": int(state.get("next_material_id") or 1000),
        "next_order_id": int(state.get("next_order_id") or 1),
        "next_quote_seq": int(state.get("next_quote_seq") or 1),
        "next_sliding_material_id": int(state.get("next_sliding_material_id") or 1),
    }
    for counter_key, counter_value in counters.items():
        cursor.execute(
            "INSERT INTO DECOR_COUNTERS (COUNTER_KEY, COUNTER_VALUE) VALUES (:counter_key, :counter_value)",
            {"counter_key": counter_key, "counter_value": counter_value},
        )

    for order in state.get("orders", []):
        cursor.execute(
            """
            INSERT INTO DECOR_ORDERS (
              ID, ORDER_NUMBER, BARCODE, PRODUCT_TYPE, CLIENT_NAME, CLIENT_PHONE, CLIENT_EMAIL,
              PROJECT_TYPE, PROJECT_NAME, LOCATION, COLOR, NOTES, STATUS_ID,
              CURRENCY, TOTAL_AMOUNT, CREATED_AT, UPDATED_AT
            ) VALUES (
              :id, :order_number, :barcode, :product_type, :client_name, :client_phone, :client_email,
              :project_type, :project_name, :location, :color, :notes, :status_id,
              :currency, :total_amount, :created_at, :updated_at
            )
            """,
            {
                "id": int(order.get("id") or 0),
                "order_number": str(order.get("order_number") or ""),
                "barcode": str(order.get("barcode") or ""),
                "product_type": str(order.get("product_type") or ""),
                "client_name": str(order.get("client_name") or ""),
                "client_phone": str(order.get("client_phone") or ""),
                "client_email": str(order.get("client_email") or ""),
                "project_type": str(order.get("project_type") or ""),
                "project_name": str(order.get("project_name") or ""),
                "location": str(order.get("location") or ""),
                "color": str(order.get("color") or ""),
                "notes": str(order.get("notes") or ""),
                "status_id": int(order.get("status_id") or 0),
                "currency": str(order.get("currency") or ""),
                "total_amount": float(order.get("total_amount") or 0),
                "created_at": str(order.get("created_at") or ""),
                "updated_at": str(order.get("updated_at") or ""),
            },
        )
        quote = order.get("quote") or {}
        inputs = quote.get("inputs") or {}
        metrics = quote.get("metrics") or {}
        summary = quote.get("summary") or {}
        cursor.execute(
            """
            INSERT INTO DECOR_ORDER_INPUTS (
              ORDER_ID, WIDTH_MM, PROJECTION_MM, FRONT_HEIGHT_MM, REAR_HEIGHT_MM, SYSTEM_TYPE,
              LED_OPTION, INCLUDE_INSTALLATION, INCLUDE_TRANSPORT, INCLUDE_DRAINAGE, EXTRA_ITEMS_COUNT,
              VARIANT_KEY, VARIANT_LABEL, FAMILY, HEIGHT_MM, ORIENTATION, INCLUDE_THRESHOLD,
              INCLUDE_GLASS, GLASS_SYSTEM, GLASS_FINISH, GLASS_THICKNESS, INCLUDE_ASSEMBLY
            ) VALUES (
              :order_id, :width_mm, :projection_mm, :front_height_mm, :rear_height_mm, :system_type,
              :led_option, :include_installation, :include_transport, :include_drainage, :extra_items_count,
              :variant_key, :variant_label, :family, :height_mm, :orientation, :include_threshold,
              :include_glass, :glass_system, :glass_finish, :glass_thickness, :include_assembly
            )
            """,
            {
                "order_id": int(order.get("id") or 0),
                "width_mm": float(inputs.get("width_mm") or 0),
                "projection_mm": float(inputs.get("projection_mm") or 0),
                "front_height_mm": float(inputs.get("front_height_mm") or 0),
                "rear_height_mm": float(inputs.get("rear_height_mm") or 0),
                "system_type": str(inputs.get("system_type") or ""),
                "led_option": str(inputs.get("led_option") or ""),
                "include_installation": _as_flag(inputs.get("include_installation")),
                "include_transport": _as_flag(inputs.get("include_transport")),
                "include_drainage": _as_flag(inputs.get("include_drainage")),
                "extra_items_count": int(inputs.get("extra_items_count") or 0),
                "variant_key": str(inputs.get("variant") or ""),
                "variant_label": str(inputs.get("variant_label") or ""),
                "family": str(inputs.get("family") or ""),
                "height_mm": float(inputs.get("height_mm") or 0),
                "orientation": str(inputs.get("orientation") or ""),
                "include_threshold": _as_flag(inputs.get("include_threshold")),
                "include_glass": _as_flag(inputs.get("include_glass")),
                "glass_system": str(inputs.get("glass_system") or ""),
                "glass_finish": str(inputs.get("glass_finish") or ""),
                "glass_thickness": str(inputs.get("glass_thickness") or ""),
                "include_assembly": _as_flag(inputs.get("include_assembly")),
            },
        )
        cursor.execute(
            """
            INSERT INTO DECOR_ORDER_METRICS (
              ORDER_ID, AREA_M2, PERIMETER_M, SLOPE_MM, SLOPE_PERCENT, POST_COUNT, SECTION_COUNT,
              BEAM_COUNT, RAFTER_LENGTH_M, FRAME_LENGTH_M, PROFILE_WEIGHT_TOTAL_KG,
              GLASS_PANEL_COUNT, GLASS_PANEL_AREA_M2, GLASS_PANEL_WIDTH_M, GLASS_PANEL_LENGTH_M,
              TOTAL_PANELS, PANEL_WIDTH_MM, PROFILE_WEIGHT_KG
            ) VALUES (
              :order_id, :area_m2, :perimeter_m, :slope_mm, :slope_percent, :post_count, :section_count,
              :beam_count, :rafter_length_m, :frame_length_m, :profile_weight_total_kg,
              :glass_panel_count, :glass_panel_area_m2, :glass_panel_width_m, :glass_panel_length_m,
              :total_panels, :panel_width_mm, :profile_weight_kg
            )
            """,
            {
                "order_id": int(order.get("id") or 0),
                "area_m2": float(metrics.get("area_m2") or 0),
                "perimeter_m": float(metrics.get("perimeter_m") or 0),
                "slope_mm": float(metrics.get("slope_mm") or 0),
                "slope_percent": float(metrics.get("slope_percent") or 0),
                "post_count": int(metrics.get("post_count") or 0),
                "section_count": int(metrics.get("section_count") or 0),
                "beam_count": int(metrics.get("beam_count") or 0),
                "rafter_length_m": float(metrics.get("rafter_length_m") or 0),
                "frame_length_m": float(metrics.get("frame_length_m") or 0),
                "profile_weight_total_kg": float(metrics.get("profile_weight_total_kg") or 0),
                "glass_panel_count": int(metrics.get("glass_panel_count") or 0),
                "glass_panel_area_m2": float(metrics.get("glass_panel_area_m2") or 0),
                "glass_panel_width_m": float(metrics.get("glass_panel_width_m") or 0),
                "glass_panel_length_m": float(metrics.get("glass_panel_length_m") or 0),
                "total_panels": int(metrics.get("total_panels") or 0),
                "panel_width_mm": float(metrics.get("panel_width_mm") or 0),
                "profile_weight_kg": float(metrics.get("profile_weight_kg") or 0),
            },
        )
        cursor.execute(
            """
            INSERT INTO DECOR_ORDER_SUMMARY (
              ORDER_ID, CURRENCY, PROFILE_COST, ACCESSORY_COST, GLASS_COST, ASSEMBLY_COST,
              INSTALLATION_COST, DIRECT_COST, WASTE_AMOUNT, SUBTOTAL, MARGIN_AMOUNT, TOTAL,
              EXCHANGE_RATE_USD_TO_MDL, TOTAL_MDL, EXTRA_ITEMS_AMOUNT, TOTAL_USD
            ) VALUES (
              :order_id, :currency, :profile_cost, :accessory_cost, :glass_cost, :assembly_cost,
              :installation_cost, :direct_cost, :waste_amount, :subtotal, :margin_amount, :total,
              :exchange_rate_usd_to_mdl, :total_mdl, :extra_items_amount, :total_usd
            )
            """,
            {
                "order_id": int(order.get("id") or 0),
                "currency": str(summary.get("currency") or order.get("currency") or ""),
                "profile_cost": float(summary.get("profile_cost") or 0),
                "accessory_cost": float(summary.get("accessory_cost") or 0),
                "glass_cost": float(summary.get("glass_cost") or 0),
                "assembly_cost": float(summary.get("assembly_cost") or 0),
                "installation_cost": float(summary.get("installation_cost") or 0),
                "direct_cost": float(summary.get("direct_cost") or 0),
                "waste_amount": float(summary.get("waste_amount") or 0),
                "subtotal": float(summary.get("subtotal") or 0),
                "margin_amount": float(summary.get("margin_amount") or 0),
                "total": float(summary.get("total") or order.get("total_amount") or 0),
                "exchange_rate_usd_to_mdl": float(summary.get("exchange_rate_usd_to_mdl") or 0),
                "total_mdl": float(summary.get("total_mdl") or 0),
                "extra_items_amount": float(summary.get("extra_items_amount") or 0),
                "total_usd": float(summary.get("total_usd") or 0),
            },
        )
        for line_no, item in enumerate(order.get("items") or [], start=1):
            cursor.execute(
                """
                INSERT INTO DECOR_ORDER_ITEMS (
                  ORDER_ID, LINE_NO, CODE, NAME, QTY, UNIT, UNIT_PRICE, AMOUNT,
                  CATEGORY, SOURCE_NAME, IMAGE_URL, LENGTH_M, TOTAL_LENGTH_M, WEIGHT_KG
                ) VALUES (
                  :order_id, :line_no, :code, :name, :qty, :unit, :unit_price, :amount,
                  :category, :source_name, :image_url, :length_m, :total_length_m, :weight_kg
                )
                """,
                {
                    "order_id": int(order.get("id") or 0),
                    "line_no": line_no,
                    "code": str(item.get("code") or ""),
                    "name": str(item.get("name") or ""),
                    "qty": float(item.get("qty") or 0),
                    "unit": str(item.get("unit") or ""),
                    "unit_price": float(item.get("unit_price") or 0),
                    "amount": float(item.get("amount") or 0),
                    "category": str(item.get("category") or ""),
                    "source_name": str(item.get("source") or ""),
                    "image_url": str(item.get("image_url") or ""),
                    "length_m": float(item.get("length_m") or 0),
                    "total_length_m": float(item.get("total_length_m") or 0),
                    "weight_kg": float(item.get("weight_kg") or 0),
                },
            )

    for material in state.get("sliding_materials", []):
        cursor.execute(
            """
            INSERT INTO DECOR_SLIDING_MATERIALS (
              ID, CODE, NAME, NAME_RO, UNIT, CURRENCY, FAMILY, CATEGORY, UNIT_PRICE, WEIGHT_G_PER_M, ACTIVE
            ) VALUES (
              :id, :code, :name, :name_ro, :unit, :currency, :family, :category, :unit_price, :weight_g_per_m, :active
            )
            """,
            {
                "id": int(material.get("id") or 0),
                "code": str(material.get("code") or ""),
                "name": str(material.get("name") or ""),
                "name_ro": str(material.get("name_ro") or ""),
                "unit": str(material.get("unit") or ""),
                "currency": str(material.get("currency") or ""),
                "family": str(material.get("family") or ""),
                "category": str(material.get("category") or ""),
                "unit_price": float(material.get("unit_price") or 0),
                "weight_g_per_m": float(material.get("weight_g_per_m") or 0),
                "active": _as_flag(material.get("active") or "Y"),
            },
        )

    sliding_settings = state.get("sliding_settings", {})
    cursor.execute(
        """
        INSERT INTO DECOR_SLIDING_SETTINGS (
          SETTINGS_ID, CURRENCY, ASSEMBLY_RATE, INSTALLATION_RATE, PAINTING_RATE_M2,
          MARKUP_PERCENT, WASTE_PERCENT, EXCHANGE_RATE_MDL_TO_USD, ASSEMBLY_BASIS, INSTALLATION_BASIS
        ) VALUES (
          1, :currency, :assembly_rate, :installation_rate, :painting_rate_m2,
          :markup_percent, :waste_percent, :exchange_rate_mdl_to_usd, :assembly_basis, :installation_basis
        )
        """,
        {
            "currency": str(sliding_settings.get("currency") or "MDL"),
            "assembly_rate": float(sliding_settings.get("assembly_rate") or 0),
            "installation_rate": float(sliding_settings.get("installation_rate") or 0),
            "painting_rate_m2": float(sliding_settings.get("painting_rate_m2") or 0),
            "markup_percent": float(sliding_settings.get("markup_percent") or 0),
            "waste_percent": float(sliding_settings.get("waste_percent") or 0),
            "exchange_rate_mdl_to_usd": float(sliding_settings.get("exchange_rate_mdl_to_usd") or 0),
            "assembly_basis": str(sliding_settings.get("assembly_basis") or ""),
            "installation_basis": str(sliding_settings.get("installation_basis") or ""),
        },
    )
    for system_type, finish_map in (sliding_settings.get("glass_rate_matrix") or {}).items():
        for finish_key, rate in (finish_map or {}).items():
            cursor.execute(
                "INSERT INTO DECOR_SLIDING_GLASS_RATES (SETTINGS_ID, SYSTEM_TYPE, FINISH_KEY, RATE) VALUES (1, :system_type, :finish_key, :rate)",
                {"system_type": str(system_type), "finish_key": str(finish_key), "rate": float(rate or 0)},
            )
    for list_type in ("system_types", "glass_finishes", "glass_thicknesses", "colors"):
        for idx, value in enumerate(sliding_settings.get(list_type) or [], start=1):
            cursor.execute(
                "INSERT INTO DECOR_SLIDING_LIST_VALUES (SETTINGS_ID, LIST_TYPE, VALUE_TEXT, SORT_ORDER) VALUES (1, :list_type, :value_text, :sort_order)",
                {"list_type": list_type, "value_text": str(value), "sort_order": idx},
            )

    for variant_key, variant in (state.get("sliding_variants") or {}).items():
        cursor.execute(
            """
            INSERT INTO DECOR_SLIDING_VARIANTS (
              VARIANT_KEY, FAMILY, PANELS, LABEL, WIDTH_MIN_MM, WIDTH_MAX_MM,
              HEIGHT_MIN_MM, HEIGHT_MAX_MM, MAX_AREA_M2, MAX_PANEL_WIDTH_MM, IS_DOUBLE
            ) VALUES (
              :variant_key, :family, :panels, :label, :width_min_mm, :width_max_mm,
              :height_min_mm, :height_max_mm, :max_area_m2, :max_panel_width_mm, :is_double
            )
            """,
            {
                "variant_key": str(variant_key),
                "family": str(variant.get("family") or ""),
                "panels": str(variant.get("panels") or ""),
                "label": str(variant.get("label") or ""),
                "width_min_mm": float(variant.get("width_min_mm") or 0),
                "width_max_mm": float(variant.get("width_max_mm") or 0),
                "height_min_mm": float(variant.get("height_min_mm") or 0),
                "height_max_mm": float(variant.get("height_max_mm") or 0),
                "max_area_m2": float(variant.get("max_area_m2") or 0),
                "max_panel_width_mm": float(variant.get("max_panel_width_mm") or 0),
                "is_double": _as_flag(variant.get("is_double")),
            },
        )
        for profile_kind, key_name in (("profile", "profiles"), ("optional", "optional_profiles")):
            for code, pdef in (variant.get(key_name) or {}).items():
                cursor.execute(
                    """
                    INSERT INTO DECOR_SLIDING_VARIANT_PROFILES (
                      VARIANT_KEY, PROFILE_KIND, CODE, DESC_TEXT, PIECES, PER_PANEL,
                      LENGTH_BASIS, LENGTH_OFFSET_MM, LENGTH_MM, CONDITION_EXPR
                    ) VALUES (
                      :variant_key, :profile_kind, :code, :desc_text, :pieces, :per_panel,
                      :length_basis, :length_offset_mm, :length_mm, :condition_expr
                    )
                    """,
                    {
                        "variant_key": str(variant_key),
                        "profile_kind": profile_kind,
                        "code": str(code),
                        "desc_text": str(pdef.get("desc") or ""),
                        "pieces": int(pdef.get("pieces") or 0),
                        "per_panel": _as_flag(pdef.get("per_panel")),
                        "length_basis": str(pdef.get("length_basis") or ""),
                        "length_offset_mm": float(pdef.get("length_offset_mm") or 0),
                        "length_mm": float(pdef.get("length_mm") or 0),
                        "condition_expr": str(pdef.get("condition") or ""),
                    },
                )
                for panel_label, offset_mm in (pdef.get("panel_offsets") or {}).items():
                    cursor.execute(
                        "INSERT INTO DECOR_SLIDING_PANEL_OFFSETS (VARIANT_KEY, PROFILE_KIND, CODE, PANEL_LABEL, OFFSET_MM) VALUES (:variant_key, :profile_kind, :code, :panel_label, :offset_mm)",
                        {
                            "variant_key": str(variant_key),
                            "profile_kind": profile_kind,
                            "code": str(code),
                            "panel_label": str(panel_label),
                            "offset_mm": float(offset_mm or 0),
                        },
                    )
        for code, adef in (variant.get("accessory_formulas") or {}).items():
            cursor.execute(
                "INSERT INTO DECOR_SLIDING_VARIANT_ACCESSORIES (VARIANT_KEY, CODE, QTY, CONDITION_EXPR) VALUES (:variant_key, :code, :qty, :condition_expr)",
                {
                    "variant_key": str(variant_key),
                    "code": str(code),
                    "qty": int(adef.get("qty") or 0),
                    "condition_expr": str(adef.get("condition") or ""),
                },
            )


def _dict_from_rows(rows: list[tuple[Any, ...]], key_idx: int, value_idx: int) -> dict[str, Any]:
    return {str(row[key_idx]): row[value_idx] for row in rows}


def _load_rows(cursor: oracledb.Cursor, sql: str, params: dict[str, Any] | None = None) -> list[tuple[Any, ...]]:
    cursor.execute(sql, params or {})
    return cursor.fetchall() or []


def load_state(default_factory: Callable[[], dict[str, Any]] | None = None, fallback_path: Path | None = None) -> dict[str, Any]:
    ensure_schema()
    connection = DatabaseConnection.get_connection()
    try:
        with connection.cursor() as cursor:
            if not _is_seeded(cursor):
                state = _legacy_state(default_factory, fallback_path)
                _replace_state(cursor, state)
                connection.commit()

            materials = []
            for row in _load_rows(cursor, "SELECT ID, CODE, NAME, NAME_ORIGINAL, ORIGINAL_LANG, NAME_RO, IMAGE_URL, CATEGORY, UNIT, UNIT_PRICE, CURRENCY, SOURCE_FILE, SOURCE_SHEET, NOTES, ACTIVE, CREATED_AT, UPDATED_AT FROM DECOR_MATERIALS ORDER BY ID"):
                materials.append({
                    "id": int(row[0] or 0), "code": row[1] or "", "name": row[2] or "", "name_original": row[3] or "",
                    "original_lang": row[4] or "", "name_ro": row[5] or "", "image_url": row[6] or "",
                    "category": row[7] or "", "unit": row[8] or "", "unit_price": float(row[9] or 0), "currency": row[10] or "",
                    "source_file": row[11] or "", "source_sheet": row[12] or "", "notes": row[13] or "",
                    "active": row[14] or "Y", "created_at": row[15] or "", "updated_at": row[16] or "",
                })

            statuses = []
            for row in _load_rows(cursor, "SELECT ID, CODE, NAME FROM DECOR_STATUSES ORDER BY ID"):
                statuses.append({"id": int(row[0] or 0), "code": row[1] or "", "name": row[2] or ""})
            status_by_id = {s["id"]: s for s in statuses}

            settings_rows = _load_rows(cursor, "SELECT CURRENCY, EXCHANGE_RATE_USD_TO_MDL, MARKUP_PERCENT, WASTE_PERCENT, PROFILE_WEIGHT_KG_PER_M2, ACCESSORY_FIXED_PER_M2, DRAINAGE_FIXED, TRANSPORT_FIXED, INSTALL_RATE_M2 FROM DECOR_SETTINGS WHERE SETTINGS_ID = 1")
            if settings_rows:
                row = settings_rows[0]
                settings = {
                    "currency": row[0] or "USD",
                    "exchange_rate_usd_to_mdl": float(row[1] or 0),
                    "markup_percent": float(row[2] or 0),
                    "waste_percent": float(row[3] or 0),
                    "profile_weight_kg_per_m2": float(row[4] or 0),
                    "accessory_fixed_per_m2": float(row[5] or 0),
                    "drainage_fixed": float(row[6] or 0),
                    "transport_fixed": float(row[7] or 0),
                    "install_rate_m2": float(row[8] or 0),
                }
            else:
                settings = {}
            settings["glass_rate_m2"] = _dict_from_rows(_load_rows(cursor, "SELECT SYSTEM_TYPE, RATE FROM DECOR_SETTING_GLASS_RATES WHERE SETTINGS_ID = 1 ORDER BY SYSTEM_TYPE"), 0, 1)
            settings["led_options"] = _dict_from_rows(_load_rows(cursor, "SELECT OPTION_CODE, RATE FROM DECOR_SETTING_LED_OPTIONS WHERE SETTINGS_ID = 1 ORDER BY OPTION_CODE"), 0, 1)
            list_rows = _load_rows(cursor, "SELECT LIST_TYPE, VALUE_TEXT, SORT_ORDER FROM DECOR_SETTING_LIST_VALUES WHERE SETTINGS_ID = 1 ORDER BY LIST_TYPE, SORT_ORDER")
            for list_type in ("project_types", "system_types", "colors"):
                settings[list_type] = [row[1] for row in list_rows if row[0] == list_type]

            counters = {str(row[0]): int(row[1] or 0) for row in _load_rows(cursor, "SELECT COUNTER_KEY, COUNTER_VALUE FROM DECOR_COUNTERS")}

            inputs_by_order: dict[int, dict[str, Any]] = {}
            for row in _load_rows(cursor, "SELECT ORDER_ID, WIDTH_MM, PROJECTION_MM, FRONT_HEIGHT_MM, REAR_HEIGHT_MM, SYSTEM_TYPE, LED_OPTION, INCLUDE_INSTALLATION, INCLUDE_TRANSPORT, INCLUDE_DRAINAGE, EXTRA_ITEMS_COUNT, VARIANT_KEY, VARIANT_LABEL, FAMILY, HEIGHT_MM, ORIENTATION, INCLUDE_THRESHOLD, INCLUDE_GLASS, GLASS_SYSTEM, GLASS_FINISH, GLASS_THICKNESS, INCLUDE_ASSEMBLY FROM DECOR_ORDER_INPUTS"):
                inputs_by_order[int(row[0] or 0)] = {
                    "width_mm": float(row[1] or 0), "projection_mm": float(row[2] or 0), "front_height_mm": float(row[3] or 0),
                    "rear_height_mm": float(row[4] or 0), "system_type": row[5] or "", "led_option": row[6] or "",
                    "include_installation": (row[7] or "N") == "Y", "include_transport": (row[8] or "N") == "Y",
                    "include_drainage": (row[9] or "N") == "Y", "extra_items_count": int(row[10] or 0),
                    "variant": row[11] or "", "variant_label": row[12] or "", "family": row[13] or "",
                    "height_mm": float(row[14] or 0), "orientation": row[15] or "", "include_threshold": (row[16] or "N") == "Y",
                    "include_glass": (row[17] or "N") == "Y", "glass_system": row[18] or "", "glass_finish": row[19] or "",
                    "glass_thickness": row[20] or "", "include_assembly": (row[21] or "N") == "Y",
                }
            metrics_by_order: dict[int, dict[str, Any]] = {}
            for row in _load_rows(cursor, "SELECT ORDER_ID, AREA_M2, PERIMETER_M, SLOPE_MM, SLOPE_PERCENT, POST_COUNT, SECTION_COUNT, BEAM_COUNT, RAFTER_LENGTH_M, FRAME_LENGTH_M, PROFILE_WEIGHT_TOTAL_KG, GLASS_PANEL_COUNT, GLASS_PANEL_AREA_M2, GLASS_PANEL_WIDTH_M, GLASS_PANEL_LENGTH_M, TOTAL_PANELS, PANEL_WIDTH_MM, PROFILE_WEIGHT_KG FROM DECOR_ORDER_METRICS"):
                metrics_by_order[int(row[0] or 0)] = {
                    "area_m2": float(row[1] or 0), "perimeter_m": float(row[2] or 0), "slope_mm": float(row[3] or 0),
                    "slope_percent": float(row[4] or 0), "post_count": int(row[5] or 0), "section_count": int(row[6] or 0),
                    "beam_count": int(row[7] or 0), "rafter_length_m": float(row[8] or 0), "frame_length_m": float(row[9] or 0),
                    "profile_weight_total_kg": float(row[10] or 0), "glass_panel_count": int(row[11] or 0),
                    "glass_panel_area_m2": float(row[12] or 0), "glass_panel_width_m": float(row[13] or 0), "glass_panel_length_m": float(row[14] or 0),
                    "total_panels": int(row[15] or 0), "panel_width_mm": float(row[16] or 0), "profile_weight_kg": float(row[17] or 0),
                }
            summary_by_order: dict[int, dict[str, Any]] = {}
            for row in _load_rows(cursor, "SELECT ORDER_ID, CURRENCY, PROFILE_COST, ACCESSORY_COST, GLASS_COST, ASSEMBLY_COST, INSTALLATION_COST, DIRECT_COST, WASTE_AMOUNT, SUBTOTAL, MARGIN_AMOUNT, TOTAL, EXCHANGE_RATE_USD_TO_MDL, TOTAL_MDL, EXTRA_ITEMS_AMOUNT, TOTAL_USD FROM DECOR_ORDER_SUMMARY"):
                summary_by_order[int(row[0] or 0)] = {
                    "currency": row[1] or "", "profile_cost": float(row[2] or 0), "accessory_cost": float(row[3] or 0),
                    "glass_cost": float(row[4] or 0), "assembly_cost": float(row[5] or 0), "installation_cost": float(row[6] or 0),
                    "direct_cost": float(row[7] or 0), "waste_amount": float(row[8] or 0), "subtotal": float(row[9] or 0),
                    "margin_amount": float(row[10] or 0), "total": float(row[11] or 0), "exchange_rate_usd_to_mdl": float(row[12] or 0),
                    "total_mdl": float(row[13] or 0), "extra_items_amount": float(row[14] or 0), "total_usd": float(row[15] or 0),
                }
            items_by_order: dict[int, list[dict[str, Any]]] = {}
            for row in _load_rows(cursor, "SELECT ORDER_ID, LINE_NO, CODE, NAME, QTY, UNIT, UNIT_PRICE, AMOUNT, CATEGORY, SOURCE_NAME, IMAGE_URL, LENGTH_M, TOTAL_LENGTH_M, WEIGHT_KG FROM DECOR_ORDER_ITEMS ORDER BY ORDER_ID, LINE_NO"):
                items_by_order.setdefault(int(row[0] or 0), []).append({
                    "code": row[2] or "", "name": row[3] or "", "qty": float(row[4] or 0), "unit": row[5] or "",
                    "unit_price": float(row[6] or 0), "amount": float(row[7] or 0), "category": row[8] or "",
                    "source": row[9] or "", "image_url": row[10] or "", "length_m": float(row[11] or 0),
                    "total_length_m": float(row[12] or 0), "weight_kg": float(row[13] or 0),
                })
            orders = []
            for row in _load_rows(cursor, "SELECT ID, ORDER_NUMBER, BARCODE, PRODUCT_TYPE, CLIENT_NAME, CLIENT_PHONE, CLIENT_EMAIL, PROJECT_TYPE, PROJECT_NAME, LOCATION, COLOR, NOTES, STATUS_ID, CURRENCY, TOTAL_AMOUNT, CREATED_AT, UPDATED_AT FROM DECOR_ORDERS ORDER BY ID DESC"):
                order_id = int(row[0] or 0)
                status = status_by_id.get(int(row[12] or 0), {})
                orders.append({
                    "id": order_id, "order_number": row[1] or "", "barcode": row[2] or "", "product_type": row[3] or "",
                    "client_name": row[4] or "", "client_phone": row[5] or "", "client_email": row[6] or "",
                    "project_type": row[7] or "", "project_name": row[8] or "", "location": row[9] or "", "color": row[10] or "",
                    "notes": row[11] or "", "status_id": int(row[12] or 0), "status_code": status.get("code"), "status_name": status.get("name"),
                    "currency": row[13] or "", "total_amount": float(row[14] or 0), "created_at": row[15] or "", "updated_at": row[16] or "",
                    "items": items_by_order.get(order_id, []),
                    "quote": {
                        "product_type": row[3] or "",
                        "inputs": inputs_by_order.get(order_id, {}),
                        "metrics": metrics_by_order.get(order_id, {}),
                        "lines": items_by_order.get(order_id, []),
                        "summary": summary_by_order.get(order_id, {}),
                    },
                })

            sliding_materials = []
            for row in _load_rows(cursor, "SELECT ID, CODE, NAME, NAME_RO, UNIT, CURRENCY, FAMILY, CATEGORY, UNIT_PRICE, WEIGHT_G_PER_M, ACTIVE FROM DECOR_SLIDING_MATERIALS ORDER BY ID"):
                sliding_materials.append({
                    "id": int(row[0] or 0), "code": row[1] or "", "name": row[2] or "", "name_ro": row[3] or "", "unit": row[4] or "",
                    "currency": row[5] or "", "family": row[6] or "", "category": row[7] or "", "unit_price": float(row[8] or 0),
                    "weight_g_per_m": float(row[9] or 0), "active": row[10] or "Y",
                })
            sliding_settings_rows = _load_rows(cursor, "SELECT CURRENCY, ASSEMBLY_RATE, INSTALLATION_RATE, PAINTING_RATE_M2, MARKUP_PERCENT, WASTE_PERCENT, EXCHANGE_RATE_MDL_TO_USD, ASSEMBLY_BASIS, INSTALLATION_BASIS FROM DECOR_SLIDING_SETTINGS WHERE SETTINGS_ID = 1")
            if sliding_settings_rows:
                row = sliding_settings_rows[0]
                sliding_settings = {
                    "currency": row[0] or "MDL", "assembly_rate": float(row[1] or 0), "installation_rate": float(row[2] or 0),
                    "painting_rate_m2": float(row[3] or 0), "markup_percent": float(row[4] or 0), "waste_percent": float(row[5] or 0),
                    "exchange_rate_mdl_to_usd": float(row[6] or 0), "assembly_basis": row[7] or "", "installation_basis": row[8] or "",
                }
            else:
                sliding_settings = {}
            glass_rows = _load_rows(cursor, "SELECT SYSTEM_TYPE, FINISH_KEY, RATE FROM DECOR_SLIDING_GLASS_RATES WHERE SETTINGS_ID = 1 ORDER BY SYSTEM_TYPE, FINISH_KEY")
            sliding_settings["glass_rate_matrix"] = {}
            for system_type, finish_key, rate in glass_rows:
                sliding_settings["glass_rate_matrix"].setdefault(system_type, {})[finish_key] = float(rate or 0)
            list_rows = _load_rows(cursor, "SELECT LIST_TYPE, VALUE_TEXT, SORT_ORDER FROM DECOR_SLIDING_LIST_VALUES WHERE SETTINGS_ID = 1 ORDER BY LIST_TYPE, SORT_ORDER")
            for list_type in ("system_types", "glass_finishes", "glass_thicknesses", "colors"):
                sliding_settings[list_type] = [row[1] for row in list_rows if row[0] == list_type]

            variants: dict[str, Any] = {}
            for row in _load_rows(cursor, "SELECT VARIANT_KEY, FAMILY, PANELS, LABEL, WIDTH_MIN_MM, WIDTH_MAX_MM, HEIGHT_MIN_MM, HEIGHT_MAX_MM, MAX_AREA_M2, MAX_PANEL_WIDTH_MM, IS_DOUBLE FROM DECOR_SLIDING_VARIANTS ORDER BY VARIANT_KEY"):
                variants[str(row[0])] = {
                    "family": row[1] or "", "panels": row[2] or "", "label": row[3] or "", "width_min_mm": float(row[4] or 0),
                    "width_max_mm": float(row[5] or 0), "height_min_mm": float(row[6] or 0), "height_max_mm": float(row[7] or 0),
                    "max_area_m2": float(row[8] or 0), "max_panel_width_mm": float(row[9] or 0), "is_double": (row[10] or "N") == "Y",
                    "profiles": {}, "optional_profiles": {}, "accessory_formulas": {},
                }
            profile_rows = _load_rows(cursor, "SELECT VARIANT_KEY, PROFILE_KIND, CODE, DESC_TEXT, PIECES, PER_PANEL, LENGTH_BASIS, LENGTH_OFFSET_MM, LENGTH_MM, CONDITION_EXPR FROM DECOR_SLIDING_VARIANT_PROFILES ORDER BY VARIANT_KEY, PROFILE_KIND, CODE")
            for row in profile_rows:
                variant = variants.get(str(row[0]))
                if not variant:
                    continue
                target = variant["profiles"] if row[1] == "profile" else variant["optional_profiles"]
                target[str(row[2])] = {
                    "desc": row[3] or "", "pieces": int(row[4] or 0), "per_panel": (row[5] or "N") == "Y",
                    "length_basis": row[6] or "", "length_offset_mm": float(row[7] or 0), "length_mm": float(row[8] or 0),
                    **({"condition": row[9]} if row[9] else {}),
                }
            offset_rows = _load_rows(cursor, "SELECT VARIANT_KEY, PROFILE_KIND, CODE, PANEL_LABEL, OFFSET_MM FROM DECOR_SLIDING_PANEL_OFFSETS ORDER BY VARIANT_KEY, PROFILE_KIND, CODE, PANEL_LABEL")
            for row in offset_rows:
                variant = variants.get(str(row[0]))
                if not variant:
                    continue
                target = variant["profiles"] if row[1] == "profile" else variant["optional_profiles"]
                entry = target.get(str(row[2]))
                if not entry:
                    continue
                entry.setdefault("panel_offsets", {})[str(row[3])] = float(row[4] or 0)
            for row in _load_rows(cursor, "SELECT VARIANT_KEY, CODE, QTY, CONDITION_EXPR FROM DECOR_SLIDING_VARIANT_ACCESSORIES ORDER BY VARIANT_KEY, CODE"):
                variant = variants.get(str(row[0]))
                if not variant:
                    continue
                payload = {"qty": int(row[2] or 0)}
                if row[3]:
                    payload["condition"] = row[3]
                variant["accessory_formulas"][str(row[1])] = payload

            return {
                "materials": materials,
                "statuses": statuses,
                "settings": settings,
                "orders": orders,
                "next_material_id": counters.get("next_material_id", 1000),
                "next_order_id": counters.get("next_order_id", 1),
                "next_quote_seq": counters.get("next_quote_seq", 1),
                "sliding_materials": sliding_materials,
                "sliding_settings": sliding_settings,
                "sliding_variants": variants,
                "next_sliding_material_id": counters.get("next_sliding_material_id", 1),
            }
    finally:
        connection.close()


def save_state(state: dict[str, Any]) -> None:
    ensure_schema()
    connection = DatabaseConnection.get_connection()
    try:
        with connection.cursor() as cursor:
            _replace_state(cursor, state)
        connection.commit()
    finally:
        connection.close()

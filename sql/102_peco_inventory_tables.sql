-- ============================================================
-- PECO: складской контур — приход цистерн, замеры, журнал событий.
-- ============================================================

CREATE SEQUENCE PECO_DELIVERIES_SEQ      START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_DELIVERY_ITEMS_SEQ  START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_TANK_DIPS_SEQ       START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE PECO_EVENT_LOG_SEQ       START WITH 1 INCREMENT BY 1 NOCACHE;

-- Шапка прихода цистерны. Одна цистерна имеет несколько отсеков и
-- заполняет несколько резервуаров за один визит — отсюда разделение
-- на шапку и строки.
CREATE TABLE PECO_DELIVERIES (
  ID           NUMBER        NOT NULL,
  STATION_ID   NUMBER        NOT NULL,
  SUPPLIER     VARCHAR2(150) NOT NULL,
  WAYBILL_NO   VARCHAR2(60)  NOT NULL,
  DRIVER_NAME  VARCHAR2(150),
  VEHICLE_NO   VARCHAR2(30),
  ARRIVED_AT   TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  ACCEPTED_AT  TIMESTAMP,
  ACCEPTED_BY  NUMBER,
  NOTE         VARCHAR2(500),
  CONSTRAINT PK_PECO_DELIVERIES PRIMARY KEY (ID),
  CONSTRAINT UQ_PECO_DELIV_WB UNIQUE (STATION_ID, WAYBILL_NO),
  -- Опорный UNIQUE для составного FK PECO_DELIVERY_ITEMS: приход проверяется на ту же станцию, что и связанная строка
  CONSTRAINT UQ_PECO_DELIVERIES_ID_ST UNIQUE (ID, STATION_ID),
  CONSTRAINT FK_PECO_DELIV_ST FOREIGN KEY (STATION_ID)  REFERENCES PECO_STATIONS (ID),
  CONSTRAINT FK_PECO_DELIV_AB FOREIGN KEY (ACCEPTED_BY) REFERENCES PECO_EMPLOYEES (ID)
);

-- Строка прихода по одному резервуару. Хранятся и заявленный, и
-- фактически принятый объём — недолив проявляется немедленно.
CREATE TABLE PECO_DELIVERY_ITEMS (
  ID            NUMBER       NOT NULL,
  DELIVERY_ID   NUMBER       NOT NULL,
  TANK_ID       NUMBER       NOT NULL,
  STATION_ID    NUMBER       NOT NULL,
  GRADE_CODE    VARCHAR2(10) NOT NULL,
  LITERS_DOC    NUMBER(14,3) NOT NULL,
  LITERS_RECV   NUMBER(14,3) NOT NULL,
  TEMPERATURE_C NUMBER(6,2),
  DIP_BEFORE_L  NUMBER(14,3),
  DIP_AFTER_L   NUMBER(14,3),
  CONSTRAINT PK_PECO_DELIVERY_ITEMS PRIMARY KEY (ID),
  -- Составной FK: приход и строка обязаны принадлежать одной и той же станции
  -- (иначе приход соседней АЗС попадёт в чужую станцию)
  CONSTRAINT FK_PECO_DI_DE FOREIGN KEY (DELIVERY_ID, STATION_ID) REFERENCES PECO_DELIVERIES (ID, STATION_ID),
  -- Составной FK: резервуар строки обязан принадлежать той же станции, что и строка
  -- (иначе резервуар соседней АЗС попадёт в чужую станцию)
  CONSTRAINT FK_PECO_DI_TA FOREIGN KEY (TANK_ID, STATION_ID)     REFERENCES PECO_TANKS (ID, STATION_ID),
  -- Составной FK: вид топлива строки обязан совпадать с видом топлива его резервуара
  -- (иначе приход неправильно учитывает объём в разрезе видов топлива)
  CONSTRAINT FK_PECO_DI_TA_GR FOREIGN KEY (TANK_ID, GRADE_CODE) REFERENCES PECO_TANKS (ID, GRADE_CODE),
  CONSTRAINT FK_PECO_DI_GR FOREIGN KEY (GRADE_CODE)  REFERENCES PECO_REF_FUEL_GRADES (CODE)
);

-- Ручной замер уровня (метршток/щуп) — корректировка складского реестра.
CREATE TABLE PECO_TANK_DIPS (
  ID          NUMBER       NOT NULL,
  TANK_ID     NUMBER       NOT NULL,
  STATION_ID  NUMBER       NOT NULL,
  SHIFT_ID    NUMBER,
  MEASURED_L  NUMBER(14,3) NOT NULL,
  MEASURED_AT TIMESTAMP    DEFAULT SYSTIMESTAMP NOT NULL,
  MEASURED_BY NUMBER,
  -- OPEN | CLOSE | DELIVERY | CONTROL
  DIP_KIND    VARCHAR2(15) DEFAULT 'CONTROL' NOT NULL,
  CONSTRAINT PK_PECO_TANK_DIPS PRIMARY KEY (ID),
  CONSTRAINT CK_PECO_DIP_KIND CHECK (DIP_KIND IN ('OPEN','CLOSE','DELIVERY','CONTROL')),
  -- Составной FK: резервуар замера обязан принадлежать той же станции, что и замер
  -- (иначе резервуар соседней АЗС попадёт в чужую станцию)
  CONSTRAINT FK_PECO_DIP_TA FOREIGN KEY (TANK_ID, STATION_ID)     REFERENCES PECO_TANKS (ID, STATION_ID),
  -- Составной FK: смена замера обязана принадлежать той же станции, что и замер;
  -- обратим внимание, что смена может быть NULL (замер вне смены), и Oracle не
  -- применяет составной FK, когда любой его столбец NULL — это допустимое поведение
  CONSTRAINT FK_PECO_DIP_SH FOREIGN KEY (SHIFT_ID, STATION_ID)    REFERENCES PECO_SHIFTS (ID, STATION_ID),
  CONSTRAINT FK_PECO_DIP_MB FOREIGN KEY (MEASURED_BY) REFERENCES PECO_EMPLOYEES (ID)
);

-- Append-only журнал событий модуля. НЕ хранилище состояния.
-- Намеренно БЕЗ иностранных ключей: журнал должен сохраняться
-- даже если связанные сущности позже архивируются или удаляются.
CREATE TABLE PECO_EVENT_LOG (
  ID          NUMBER        NOT NULL,
  STATION_ID  NUMBER,
  SHIFT_ID    NUMBER,
  EVENT_TYPE  VARCHAR2(40)  NOT NULL,
  ENTITY_TYPE VARCHAR2(30),
  ENTITY_ID   NUMBER,
  EMPLOYEE_ID NUMBER,
  PAYLOAD     VARCHAR2(2000),
  CREATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT PK_PECO_EVENT_LOG PRIMARY KEY (ID)
);

CREATE INDEX IX_PECO_EVL_ST    ON PECO_EVENT_LOG (STATION_ID, CREATED_AT);
CREATE INDEX IX_PECO_DIP_TA    ON PECO_TANK_DIPS (TANK_ID, MEASURED_AT);
CREATE INDEX IX_PECO_DI_DE     ON PECO_DELIVERY_ITEMS (DELIVERY_ID);
CREATE INDEX IX_PECO_DELIV_ST_DT ON PECO_DELIVERIES (STATION_ID, ARRIVED_AT);

-- ============================================================================
-- ServOuts26 — obiecte proprii ale modulului (prefix SRVO), schema UNITEST
-- ServOuts26 — module-owned objects (SRVO prefix), UNITEST schema
-- Restul modulului lucreaza peste obiectele ERP existente (TMS_*, TPR*, XLOG).
-- The rest of the module works on top of existing ERP objects (TMS_*, TPR*, XLOG).
-- ============================================================================

-- RO: tabel staging pentru feed-ul de servicii/marfuri (sursa importului).
--     Coloanele sursa sunt VARCHAR2 — parsarea o face YServOuts_BP.parse_price.
-- EN: staging table for the goods/services feed (import source).
--     Source columns are VARCHAR2 — parsing is done by YServOuts_BP.parse_price.
CREATE TABLE SRVO_INPUT_GOODS (
  ID           NUMBER        NOT NULL,
  ARTICOL      VARCHAR2(64),
  DENUMIRE     VARCHAR2(255),
  BRAND        VARCHAR2(64),
  RETAIL1      VARCHAR2(32),
  ANGRO        VARCHAR2(32),
  IONLINE      VARCHAR2(32),
  COD_UNIVERS  NUMBER,
  STATUS       VARCHAR2(16) DEFAULT 'NEW',
  ERR_MSG      VARCHAR2(500),
  CONSTRAINT SRVO_INPUT_GOODS_PK PRIMARY KEY (ID)
)
/

-- RO: generator de ID pentru staging.
-- EN: ID generator for the staging table.
CREATE SEQUENCE SRVO_INPUT_SEQ START WITH 1 NOCACHE
/

-- RO: profiluri de mapare denumite — valorile variabilelor g_* ale pachetului
--     YServOuts_BP, salvate ca perechi (profil, parametru, valoare).
-- EN: named mapping profiles — values of the YServOuts_BP g_* package
--     variables, stored as (profile, parameter, value) pairs.
CREATE TABLE SRVO_MAP_PROFILES (
  PROFILE_NAME VARCHAR2(64)  NOT NULL,
  PARAM_NAME   VARCHAR2(64)  NOT NULL,
  PARAM_VALUE  VARCHAR2(400),
  UPDATED_AT   DATE DEFAULT SYSDATE,
  CONSTRAINT SRVO_MAP_PROFILES_PK PRIMARY KEY (PROFILE_NAME, PARAM_NAME)
)
/

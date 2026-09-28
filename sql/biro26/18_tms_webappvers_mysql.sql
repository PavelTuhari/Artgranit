-- =====================================================================
-- RO: Perechea MySQL a tabelei Oracle TMS_WEBAPPVERS — aceleasi coloane,
--     aceleasi randuri. Traieste in baza WordPress (officeplus_wp), ca sa
--     putem compara direct ce stie Oracle si ce stie MySQL.
-- EN: MySQL twin of the Oracle TMS_WEBAPPVERS — same columns, same rows,
--     inside the WordPress database, so both sides can be compared directly.
-- Vezi: docs/Biro26/WEB_APP_VERSIONING.md
-- =====================================================================

CREATE TABLE IF NOT EXISTS tms_webappvers (
  id         BIGINT AUTO_INCREMENT PRIMARY KEY,
  app_code   VARCHAR(30)  NOT NULL,
  vers       VARCHAR(20)  NOT NULL,
  is_current CHAR(1)      NOT NULL DEFAULT '0',
  src_hash   VARCHAR(64)  NULL,
  note       VARCHAR(400) NULL,
  released   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- RO: o singura versiune curenta per aplicatie. In MySQL NULL-urile nu
  --     se ciocnesc in indecsii UNIQUE, deci coloana generata pastreaza
  --     'app_code' doar cind randul e curent — exact ca in Oracle.
  cur_key    VARCHAR(30) GENERATED ALWAYS AS
             (CASE WHEN is_current = '1' THEN app_code END) STORED,
  UNIQUE KEY ux_tms_webappvers_cur (cur_key),
  KEY ix_tms_webappvers_app (app_code, released)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

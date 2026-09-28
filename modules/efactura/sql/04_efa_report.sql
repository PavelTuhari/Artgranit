-- RO: Raportul "facturi transmise in e-Factura" — pachetul EFA_REPORT (03.09.2026).
--     Trei seturi de date, la cererea proprietarului:
--       header  - o linie: filtrul cerut + totalurile lui;
--       master  - o linie per e-factura (EFA_DOC + antetul documentului ERP);
--       detail  - pozitiile (marfurile) fiecarei e-facturi, legate de master
--                 prin EFA_ID / DOC_COD.
--     Doua fete ale aceluiasi raport:
--       * functii PIPELINED (SELECT * FROM TABLE(EFA_REPORT.master(...))) —
--         pentru web (execute_query nu stie ref-cursoare prin worker);
--       * procedura SENT cu trei OUT SYS_REFCURSOR — pentru aplicatiile
--         native (uniConf / rapoarte Delphi).
--     Filtrul: perioada (pe SENT_AT, altfel UPDATED), statutul EFA_DOC
--     (NULL = toate), clientul (NULL = toti).
--     Textul e ASCII: baza e CL8MSWIN1251 si diacriticele s-ar strica.
-- EN: EFA_REPORT package: header/master/detail sets as pipelined functions
--     and as a 3-ref-cursor procedure.

CREATE OR REPLACE TYPE EFA_RPT_HDR_T AS OBJECT (
    FILTER_FROM    DATE,
    FILTER_TO      DATE,
    FILTER_STATUS  VARCHAR2(20),
    FILTER_CLIENT  NUMBER,
    GENERATED_AT   DATE,
    ENDPOINT       VARCHAR2(400),
    DOCS_CNT       NUMBER,
    SENT_CNT       NUMBER,
    ACCEPTED_CNT   NUMBER,
    ERROR_CNT      NUMBER,
    TOTAL_SUM      NUMBER
)
/

CREATE OR REPLACE TYPE EFA_RPT_HDR_TAB AS TABLE OF EFA_RPT_HDR_T
/

CREATE OR REPLACE TYPE EFA_RPT_MST_T AS OBJECT (
    EFA_ID       NUMBER,
    DOC_COD      NUMBER,
    NRMANUAL     VARCHAR2(40),
    DOC_DATE     DATE,
    CLIENT_COD   NUMBER,
    CLIENT_NAME  VARCHAR2(400),
    CLIENT_IDNO  VARCHAR2(20),
    STATUS       VARCHAR2(20),
    SFS_SERIA    VARCHAR2(20),
    SFS_NUMBER   VARCHAR2(40),
    REQUEST_ID   VARCHAR2(80),
    SENT_AT      DATE,
    ERR_MSG      VARCHAR2(1000),
    TOTAL        NUMBER,
    ROWS_CNT     NUMBER,
    QTY_SUM      NUMBER
)
/

CREATE OR REPLACE TYPE EFA_RPT_MST_TAB AS TABLE OF EFA_RPT_MST_T
/

CREATE OR REPLACE TYPE EFA_RPT_DTL_T AS OBJECT (
    EFA_ID       NUMBER,
    DOC_COD      NUMBER,
    ROW_NO       NUMBER,
    GOODS_COD    NUMBER,
    CODE         VARCHAR2(60),
    NAME         VARCHAR2(400),
    UM           VARCHAR2(40),
    QTY          NUMBER,
    PRICE        NUMBER,
    SUMA         NUMBER
)
/

CREATE OR REPLACE TYPE EFA_RPT_DTL_TAB AS TABLE OF EFA_RPT_DTL_T
/

CREATE OR REPLACE PACKAGE EFA_REPORT AS
  -- RO: functii pipelined pentru web (SELECT * FROM TABLE(...))
  FUNCTION header(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_HDR_TAB PIPELINED;
  FUNCTION master(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_MST_TAB PIPELINED;
  FUNCTION detail(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_DTL_TAB PIPELINED;
  -- RO: aceleasi trei seturi, ca ref-cursoare (aplicatii native)
  PROCEDURE sent(p_from DATE, p_to DATE, p_status VARCHAR2, p_client NUMBER,
                 p_header OUT SYS_REFCURSOR, p_master OUT SYS_REFCURSOR,
                 p_detail OUT SYS_REFCURSOR);
END EFA_REPORT;
/

CREATE OR REPLACE PACKAGE BODY EFA_REPORT AS

  -- RO: SELECT-ul de baza (master) — un singur loc, folosit de toate cele trei seturi
  CURSOR c_master(p_from DATE, p_to DATE, p_status VARCHAR2, p_client NUMBER) IS
    SELECT e.ID EFA_ID, e.DOC_COD, NVL(TRIM(d.NRMANUAL), e.NRMANUAL) NRMANUAL,
           TRUNC(d.DATAMANUAL) DOC_DATE, e.CLIENT_COD,
           u.DENUMIREA CLIENT_NAME, e.CLIENT_IDNO, e.STATUS,
           e.SFS_SERIA, e.SFS_NUMBER, e.REQUEST_ID, e.SENT_AT, e.ERR_MSG,
           e.TOTAL,
           (SELECT COUNT(*) FROM VMDB_ST201D l WHERE l.NRDOC = e.DOC_COD) ROWS_CNT,
           (SELECT NVL(SUM(l.CANT), 0) FROM VMDB_ST201D l WHERE l.NRDOC = e.DOC_COD) QTY_SUM
      FROM EFA_DOC e
      LEFT JOIN TMDB_DOCS d ON d.COD = e.DOC_COD
      LEFT JOIN TMS_UNIVERS u ON u.COD = e.CLIENT_COD
     WHERE TRUNC(NVL(e.SENT_AT, e.UPDATED)) BETWEEN TRUNC(NVL(p_from, DATE '2000-01-01'))
                                             AND TRUNC(NVL(p_to, SYSDATE))
       AND (p_status IS NULL OR e.STATUS = UPPER(p_status))
       AND (p_client IS NULL OR e.CLIENT_COD = p_client)
     ORDER BY NVL(e.SENT_AT, e.UPDATED) DESC, e.ID DESC;

  FUNCTION header(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_HDR_TAB PIPELINED IS
    v_ep   VARCHAR2(400);
    v_docs NUMBER := 0; v_sent NUMBER := 0; v_acc NUMBER := 0;
    v_err  NUMBER := 0; v_sum NUMBER := 0;
  BEGIN
    BEGIN
      SELECT SVALUE INTO v_ep FROM EFA_SETTING WHERE SKEY = 'endpoint';
    EXCEPTION WHEN NO_DATA_FOUND THEN v_ep := NULL;
    END;
    FOR r IN c_master(p_from, p_to, p_status, p_client) LOOP
      v_docs := v_docs + 1;
      v_sum  := v_sum + NVL(r.TOTAL, 0);
      IF r.STATUS = 'SENT' THEN v_sent := v_sent + 1; END IF;
      IF r.STATUS IN ('ACCEPTED', 'SIGNED') THEN v_acc := v_acc + 1; END IF;
      IF r.STATUS IN ('ERROR', 'REJECTED') THEN v_err := v_err + 1; END IF;
    END LOOP;
    PIPE ROW (EFA_RPT_HDR_T(TRUNC(NVL(p_from, DATE '2000-01-01')), TRUNC(NVL(p_to, SYSDATE)),
                            UPPER(p_status), p_client, SYSDATE, v_ep,
                            v_docs, v_sent, v_acc, v_err, v_sum));
    RETURN;
  END header;

  FUNCTION master(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_MST_TAB PIPELINED IS
  BEGIN
    FOR r IN c_master(p_from, p_to, p_status, p_client) LOOP
      PIPE ROW (EFA_RPT_MST_T(r.EFA_ID, r.DOC_COD, r.NRMANUAL, r.DOC_DATE, r.CLIENT_COD,
                              r.CLIENT_NAME, r.CLIENT_IDNO, r.STATUS, r.SFS_SERIA,
                              r.SFS_NUMBER, r.REQUEST_ID, r.SENT_AT, r.ERR_MSG,
                              r.TOTAL, r.ROWS_CNT, r.QTY_SUM));
    END LOOP;
    RETURN;
  END master;

  FUNCTION detail(p_from DATE, p_to DATE, p_status VARCHAR2 DEFAULT NULL,
                  p_client NUMBER DEFAULT NULL) RETURN EFA_RPT_DTL_TAB PIPELINED IS
  BEGIN
    FOR r IN c_master(p_from, p_to, p_status, p_client) LOOP
      FOR l IN (SELECT ROW_NUMBER() OVER (ORDER BY l.RROWID) RN, l.CTSC,
                       u.CODVECHI, u.DENUMIREA, u.UM, l.CANT, l.PRET, l.SUMA
                  FROM VMDB_ST201D l LEFT JOIN TMS_UNIVERS u ON u.COD = l.CTSC
                 WHERE l.NRDOC = r.DOC_COD) LOOP
        PIPE ROW (EFA_RPT_DTL_T(r.EFA_ID, r.DOC_COD, l.RN, l.CTSC,
                                NVL(TRIM(l.CODVECHI), TO_CHAR(l.CTSC)), l.DENUMIREA,
                                l.UM, l.CANT, l.PRET, l.SUMA));
      END LOOP;
    END LOOP;
    RETURN;
  END detail;

  PROCEDURE sent(p_from DATE, p_to DATE, p_status VARCHAR2, p_client NUMBER,
                 p_header OUT SYS_REFCURSOR, p_master OUT SYS_REFCURSOR,
                 p_detail OUT SYS_REFCURSOR) IS
  BEGIN
    OPEN p_header FOR SELECT * FROM TABLE(EFA_REPORT.header(p_from, p_to, p_status, p_client));
    OPEN p_master FOR SELECT * FROM TABLE(EFA_REPORT.master(p_from, p_to, p_status, p_client));
    OPEN p_detail FOR SELECT * FROM TABLE(EFA_REPORT.detail(p_from, p_to, p_status, p_client));
  END sent;

END EFA_REPORT;
/

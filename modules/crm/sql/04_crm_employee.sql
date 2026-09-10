-- RO: Conturul CRM_* partea a patra (10.09.2026) - ANGAJATII.
--     Cerinta proprietarului: angajatii ii inregistreaza administratorul, in
--     lista se vede data inregistrarii, contul se poate dezactiva, parola
--     standard cu posibilitate de recuperare, e-mailul si telefonul, in
--     rapoarte - alegere pe persoana si total.
--
--     Utilizatorul REAL al ERP-ului UNA nu se muta si nu se dubleaza: el
--     ramine nodul din arborele de configurare, exact ca in uniConf ->
--       A$ADM  OBJ_TYPE=7 OBJ_SUBTYPE=0  (utilizator), PARENT_ID = grupa (7,-1)
--       A$ADP  proprietatile: USERNAME, ID, ENABLED, ADMIN, FAMILIA, PASSDATE...
--     Intrarea si parola raamin ale ERP-ului: A$UTIL.LOGIN / A$UTIL.SET_PASSWD
--     (acelasi algoritm ca UniacCLNT: UN$USERPARAMS.REGISTERUSER -> a$util.login).
--
--     CRM_EMPLOYEE e FISA DE PERSONAL a aceluiasi om (e-mail, telefon, data
--     inregistrarii, notite) - lucruri pe care arborele nu le tine. Cheia
--     este OBJ_ID-ul nodului, deci nu exista al doilea registru de utilizatori.
--     Sincronizarea in ambele sensuri o fac triggerele de mai jos, prin
--     pachetul CRM_EMP_SYNC (metoda arborelui: proprietati in A$ADP).
--
--     Doua proprietati noi in arbore: EMAIL si PHONE (tip S) - restul exista.
-- EN: employee cards mirroring the UNA config-tree users, synced both ways.

CREATE TABLE CRM_EMPLOYEE (
    OBJ_ID      NUMBER         NOT NULL,          -- A$ADM.OBJ_ID al nodului utilizator
    USER_ID     NUMBER,                           -- proprietatea ID din arbore
    USERNAME    VARCHAR2(100)  NOT NULL,
    FULL_NAME   VARCHAR2(200),
    EMAIL       VARCHAR2(120),
    PHONE       VARCHAR2(60),
    GROUP_ID    NUMBER,
    ENABLED     NUMBER(1)      DEFAULT 1 NOT NULL,
    IS_ADMIN    NUMBER(1)      DEFAULT 0 NOT NULL,
    REG_DATE    DATE           DEFAULT SYSDATE NOT NULL,
    PASS_DATE   DATE,
    LOCKED_DATE DATE,
    NOTES       VARCHAR2(1000),
    SRC         VARCHAR2(10)   DEFAULT 'erp' NOT NULL,   -- erp = venit din arbore, web = creat aici
    SYNCED      DATE           DEFAULT SYSDATE NOT NULL,
    CONSTRAINT PK_CRM_EMPLOYEE PRIMARY KEY (OBJ_ID),
    CONSTRAINT UQ_CRM_EMPLOYEE_USERNAME UNIQUE (USERNAME)
)
/

CREATE INDEX IX_CRM_EMPLOYEE_USER ON CRM_EMPLOYEE (USER_ID)
/

-- RO: jurnal al actiunilor administratorului asupra conturilor - cine, cind, ce.
CREATE TABLE CRM_EMPLOYEE_LOG (
    ID         NUMBER         NOT NULL,
    TS         DATE           DEFAULT SYSDATE NOT NULL,
    OBJ_ID     NUMBER,
    USERNAME   VARCHAR2(100),
    ACTION     VARCHAR2(30)   NOT NULL,   -- created | enabled | disabled | password | updated | synced
    ACTOR      VARCHAR2(100),
    DETAIL     VARCHAR2(1000),
    CONSTRAINT PK_CRM_EMPLOYEE_LOG PRIMARY KEY (ID)
)
/

CREATE INDEX IX_CRM_EMPLOYEE_LOG_TS ON CRM_EMPLOYEE_LOG (TS)
/

CREATE SEQUENCE CRM_EMPLOYEE_LOG_SEQ START WITH 1 INCREMENT BY 1
/

CREATE OR REPLACE TRIGGER CRM_EMPLOYEE_LOG_BI
BEFORE INSERT ON CRM_EMPLOYEE_LOG FOR EACH ROW
WHEN (NEW.ID IS NULL)
BEGIN
  SELECT CRM_EMPLOYEE_LOG_SEQ.NEXTVAL INTO :NEW.ID FROM dual;
END;
/

CREATE OR REPLACE PACKAGE CRM_EMP_SYNC IS
  -- RO: sincronizarea fisei de personal cu arborele de configurare al UNA.
  --     g_busy opreste bucla trigger -> trigger (fisa scrie in A$ADP, iar
  --     triggerul de pe A$ADP scrie inapoi in fisa).
  g_busy BOOLEAN := FALSE;

  -- RO: proprietatile nodului utilizator pe care le tinem sincronizate
  FUNCTION is_user_node(p_obj_id NUMBER) RETURN BOOLEAN;

  -- RO: fisa -> arbore. Valorile vin ca parametri (:NEW din trigger), NU se
  --     citesc din CRM_EMPLOYEE: un SELECT pe tabela care tocmai se schimba
  --     da ORA-04091 (mutating table) si sincronizarea ar tacea.
  PROCEDURE to_erp(p_obj_id NUMBER, p_enabled NUMBER, p_full VARCHAR2,
                   p_email VARCHAR2, p_phone VARCHAR2);

  -- RO: arbore -> fisa, o proprietate (o cheama triggerul de pe A$ADP)
  PROCEDURE prop_changed(p_obj_id NUMBER, p_key VARCHAR2, p_svalue VARCHAR2,
                         p_ivalue NUMBER, p_bvalue VARCHAR2, p_dvalue DATE);

  -- RO: arbore -> fisa, nodul intreg (import initial si reimprospatare)
  PROCEDURE from_erp(p_obj_id NUMBER);

  -- RO: aduce in fise toti utilizatorii din arbore (idempotent)
  FUNCTION pull_all RETURN NUMBER;
END;
/

CREATE OR REPLACE PACKAGE BODY CRM_EMP_SYNC IS

  FUNCTION is_user_node(p_obj_id NUMBER) RETURN BOOLEAN IS
    v_n NUMBER;
  BEGIN
    SELECT COUNT(*) INTO v_n FROM A$ADM
     WHERE OBJ_ID = p_obj_id AND OBJ_TYPE = 7 AND OBJ_SUBTYPE = 0;
    RETURN v_n > 0;
  EXCEPTION WHEN OTHERS THEN
    RETURN FALSE;
  END;

  -- RO: scrie o proprietate in arbore exact ca uniConf: o linie in A$ADP
  PROCEDURE set_prop(p_obj_id NUMBER, p_key VARCHAR2, p_vtype VARCHAR2,
                     p_s VARCHAR2 := NULL, p_i NUMBER := NULL,
                     p_b VARCHAR2 := NULL, p_d DATE := NULL) IS
    v_gr A$ADP.GR%TYPE;
  BEGIN
    UPDATE A$ADP SET VTYPE = p_vtype, SVALUE = p_s, IVALUE = p_i,
                     BVALUE = p_b, DVALUE = p_d
     WHERE OBJ_ID = p_obj_id AND KEY = UPPER(p_key);
    IF SQL%ROWCOUNT = 0 THEN
      -- RO: grupa proprietatii (coloana GR) o luam de la nodul insusi, ca sa
      --     apara in uniConf linga celelalte, asa nu scriem chirilica in DDL.
      SELECT MAX(GR) INTO v_gr FROM A$ADP WHERE OBJ_ID = p_obj_id AND KEY = 'USERNAME';
      INSERT INTO A$ADP (OBJ_ID, KEY, NAME, GR, VTYPE, SVALUE, IVALUE, BVALUE, DVALUE)
      VALUES (p_obj_id, UPPER(p_key), p_key, v_gr, p_vtype, p_s, p_i, p_b, p_d);
    END IF;
  END;

  PROCEDURE to_erp(p_obj_id NUMBER, p_enabled NUMBER, p_full VARCHAR2,
                   p_email VARCHAR2, p_phone VARCHAR2) IS
  BEGIN
    IF g_busy THEN RETURN; END IF;
    g_busy := TRUE;
    IF is_user_node(p_obj_id) THEN
      -- RO: in arbore boolean-ul e '1' / '0' (A$ADP$V face decode(bvalue,1,'true',0,'false'),
      --     deci un 'T' ar da ORA-01722 chiar la a$util.login)
      set_prop(p_obj_id, 'Enabled', 'B', p_b => CASE WHEN p_enabled = 1 THEN '1' ELSE '0' END);
      IF p_full  IS NOT NULL THEN set_prop(p_obj_id, 'Familia', 'S', p_s => p_full);  END IF;
      IF p_email IS NOT NULL THEN set_prop(p_obj_id, 'Email',   'S', p_s => p_email); END IF;
      IF p_phone IS NOT NULL THEN set_prop(p_obj_id, 'Phone',   'S', p_s => p_phone); END IF;
    END IF;
    g_busy := FALSE;
  EXCEPTION WHEN OTHERS THEN
    g_busy := FALSE;                       -- RO: sincronizarea nu poate rupe nimic
  END;

  PROCEDURE prop_changed(p_obj_id NUMBER, p_key VARCHAR2, p_svalue VARCHAR2,
                         p_ivalue NUMBER, p_bvalue VARCHAR2, p_dvalue DATE) IS
    v_key VARCHAR2(255) := UPPER(p_key);
  BEGIN
    IF g_busy THEN RETURN; END IF;
    g_busy := TRUE;
    -- RO: fara SELECT pe A$ADP (tabela in mutatie) - folosim doar valorile primite
    IF v_key = 'USERNAME' THEN
      UPDATE CRM_EMPLOYEE SET USERNAME = NVL(p_svalue, USERNAME), SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'ENABLED' THEN
      UPDATE CRM_EMPLOYEE SET ENABLED = CASE WHEN NVL(p_bvalue,'1') IN ('0','F','N','f','n') THEN 0 ELSE 1 END,
             SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'ID' THEN
      UPDATE CRM_EMPLOYEE SET USER_ID = p_ivalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'ADMIN' THEN
      UPDATE CRM_EMPLOYEE SET IS_ADMIN = CASE WHEN NVL(p_svalue,'0') = '1' THEN 1 ELSE 0 END,
             SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key IN ('FAMILIA', 'FAMILIA NUMELE PRENUMELE') THEN
      UPDATE CRM_EMPLOYEE SET FULL_NAME = p_svalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'EMAIL' THEN
      UPDATE CRM_EMPLOYEE SET EMAIL = p_svalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'PHONE' THEN
      UPDATE CRM_EMPLOYEE SET PHONE = p_svalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'PASSDATE' THEN
      UPDATE CRM_EMPLOYEE SET PASS_DATE = p_dvalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    ELSIF v_key = 'AUTOLOCKEDDATE' THEN
      UPDATE CRM_EMPLOYEE SET LOCKED_DATE = p_dvalue, SYNCED = SYSDATE WHERE OBJ_ID = p_obj_id;
    END IF;
    g_busy := FALSE;
  EXCEPTION WHEN OTHERS THEN
    g_busy := FALSE;                       -- RO: ERP-ul scrie mai departe orice s-ar intimpla aici
  END;

  PROCEDURE from_erp(p_obj_id NUMBER) IS
    v_username  VARCHAR2(100);
    v_user_id   NUMBER;
    v_enabled   NUMBER(1);
    v_admin     NUMBER(1);
    v_full      VARCHAR2(200);
    v_email     VARCHAR2(120);
    v_phone     VARCHAR2(60);
    v_passdate  DATE;
    v_locked    DATE;
    v_group     NUMBER;
    v_modified  DATE;
  BEGIN
    IF NOT is_user_node(p_obj_id) THEN RETURN; END IF;
    SELECT PARENT_ID, MODIFIED INTO v_group, v_modified FROM A$ADM WHERE OBJ_ID = p_obj_id;
    SELECT MAX(CASE WHEN KEY = 'USERNAME' THEN SVALUE END),
           MAX(CASE WHEN KEY = 'ID' THEN IVALUE END),
           MAX(CASE WHEN KEY = 'ENABLED' THEN CASE WHEN NVL(BVALUE,'1') IN ('0','F','N','f','n') THEN 0 ELSE 1 END END),
           MAX(CASE WHEN KEY = 'ADMIN' THEN CASE WHEN NVL(SVALUE,'0') = '1' THEN 1 ELSE 0 END END),
           MAX(CASE WHEN KEY IN ('FAMILIA', 'FAMILIA NUMELE PRENUMELE') THEN SVALUE END),
           MAX(CASE WHEN KEY = 'EMAIL' THEN SVALUE END),
           MAX(CASE WHEN KEY = 'PHONE' THEN SVALUE END),
           MAX(CASE WHEN KEY = 'PASSDATE' THEN DVALUE END),
           MAX(CASE WHEN KEY = 'AUTOLOCKEDDATE' THEN DVALUE END)
      INTO v_username, v_user_id, v_enabled, v_admin, v_full, v_email, v_phone, v_passdate, v_locked
      FROM A$ADP WHERE OBJ_ID = p_obj_id;
    IF v_username IS NULL THEN RETURN; END IF;
    g_busy := TRUE;
    MERGE INTO CRM_EMPLOYEE e
    USING (SELECT p_obj_id OBJ_ID FROM dual) n ON (e.OBJ_ID = n.OBJ_ID)
    WHEN MATCHED THEN UPDATE SET USERNAME = v_username, USER_ID = v_user_id,
         ENABLED = NVL(v_enabled,1), IS_ADMIN = NVL(v_admin,0), FULL_NAME = NVL(v_full, FULL_NAME),
         EMAIL = NVL(v_email, EMAIL), PHONE = NVL(v_phone, PHONE), PASS_DATE = v_passdate,
         LOCKED_DATE = v_locked, GROUP_ID = v_group, SYNCED = SYSDATE
    WHEN NOT MATCHED THEN INSERT (OBJ_ID, USER_ID, USERNAME, FULL_NAME, EMAIL, PHONE, GROUP_ID,
         ENABLED, IS_ADMIN, REG_DATE, PASS_DATE, LOCKED_DATE, SRC)
      VALUES (p_obj_id, v_user_id, v_username, v_full, v_email, v_phone, v_group,
              NVL(v_enabled,1), NVL(v_admin,0), NVL(v_modified, SYSDATE), v_passdate, v_locked, 'erp');
    g_busy := FALSE;
  EXCEPTION WHEN OTHERS THEN
    g_busy := FALSE;
    RAISE;
  END;

  FUNCTION pull_all RETURN NUMBER IS
    v_n NUMBER := 0;
  BEGIN
    FOR c IN (SELECT OBJ_ID FROM A$ADM WHERE OBJ_TYPE = 7 AND OBJ_SUBTYPE = 0) LOOP
      from_erp(c.OBJ_ID);
      v_n := v_n + 1;
    END LOOP;
    RETURN v_n;
  END;
END;
/

-- RO: fisa -> arbore. Nu atinge USERNAME si parola: acelea sint ale ERP-ului.
CREATE OR REPLACE TRIGGER CRM_EMPLOYEE_AIU
AFTER INSERT OR UPDATE ON CRM_EMPLOYEE FOR EACH ROW
BEGIN
  CRM_EMP_SYNC.to_erp(:NEW.OBJ_ID, :NEW.ENABLED, :NEW.FULL_NAME, :NEW.EMAIL, :NEW.PHONE);
END;
/

-- RO: arbore -> fisa. Acesta e SINGURUL obiect al modulului asezat pe o tabela
--     nativa a ERP-ului, deci e facut sa nu poata strica nimic:
--       1. WHEN il lasa sa porneasca doar la cele zece chei ale utilizatorului,
--       2. apelul e DINAMIC - daca pachetul CRM_EMP_SYNC lipseste sau e invalid,
--          triggerul NU devine invalid si nu blocheaza scrierile in A$ADP
--          (un apel static ar da ORA-04098 la fiecare salvare din uniConf),
--       3. orice eroare e inghitita: configuratorul isi scrie proprietatea mai
--          departe, iar fisa se aduce la zi la urmatorul "Sincronizeaza".
--     Fara tranzactie proprie: mergem in aceeasi tranzactie ca ERP-ul, deci un
--     rollback al configuratorului anuleaza si oglindirea.
CREATE OR REPLACE TRIGGER CRM_EMP_ADP_AIU
AFTER INSERT OR UPDATE ON A$ADP FOR EACH ROW
WHEN (NEW.KEY IN ('USERNAME','ENABLED','ID','ADMIN','FAMILIA','FAMILIA NUMELE PRENUMELE',
                  'EMAIL','PHONE','PASSDATE','AUTOLOCKEDDATE'))
BEGIN
  EXECUTE IMMEDIATE
    'begin CRM_EMP_SYNC.prop_changed(:1, :2, :3, :4, :5, :6); end;'
    USING :NEW.OBJ_ID, :NEW.KEY, :NEW.SVALUE, :NEW.IVALUE, :NEW.BVALUE, :NEW.DVALUE;
EXCEPTION WHEN OTHERS THEN
  NULL;
END;
/

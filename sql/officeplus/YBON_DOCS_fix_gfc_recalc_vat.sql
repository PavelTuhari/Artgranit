-- =====================================================================
-- RO: YBON_DOCS — corectie GFC (23.08.2026): perecislenie_NN_GFC recalculeaza
--     intii TVA-ul pe randuri (Cassa_NN_calc_VAT) si abia apoi posteaza.
--     Pina acum regenerarea formulelor posta sumele STOCATE la crearea
--     documentului, deci schimbarea regimului de TVA (document sau client)
--     nu se reflecta in contabilitate — vezi documentul 369.
-- EN: GFC fix — regeneration now recalculates row VAT from CURRENT attributes
--     before posting; it used to re-post the stale stored amounts.
-- RO: Copie de rezerva: Backups/ybon_docs/ (in repo-ul BIRO26).
-- =====================================================================

CREATE OR REPLACE PACKAGE BODY YBON_DOCS AS

vSc20proc    NUMBER := Yparams.vSc20proc; --16545;
vSc8proc     NUMBER := Yparams.vSc8proc; --16547;
vSc6proc     NUMBER := Yparams.vSc6proc;
vSc0proc     NUMBER := Yparams.vSc0proc; --16546;
vScTVRB20proc NUMBER := Yparams.vScTVRB20proc; --797;
vScTVRB8proc  NUMBER := Yparams.vScTVRB8proc; --798;
vScTVRB6proc  NUMBER := Yparams.vScTVRB6proc; 
vScTVRB0proc  NUMBER := Yparams.vSc0proc; --799;

---------------------------------------------------------------------------------------
FUNCTION decode_sc(vSc INT, vCont INT) RETURN NUMBER IS
 vSC_Ret INT;
BEGIN
IF Yparams.vTip_Retail=2 THEN
 IF NVL(vSC,0)=0 OR NVL(vCont,0)=0 THEN
  msg(lng('Nu este indicata analitica sau cont!!!', 'Не указана аналитика или счет!!!'));
 END IF;
----
SELECT CASE vCont
   WHEN Yparams.vCont_MatPrima THEN
    DECODE(Un$functs.tva(vSC), Yparams.vProc20, vScTVRB20proc, Yparams.vProc8, vScTVRB8proc, vScTVRB0proc)
   WHEN Yparams.vCont_Marfa THEN
    DECODE(Un$functs.tva(vSC), Yparams.vProc20, vSc20proc, Yparams.vProc8, vSc8proc, vSc0proc)
   ELSE vSC END INTO vSC_Ret FROM dual;
ELSE
 vSC_Ret:=vSC;
END IF;
RETURN vSC_Ret;
END decode_sc;
---------------------------------------------------------------------------------------

PROCEDURE INS_DOCS(vNrdoc NUMBER
                  ,vNrdoc_baza NUMBER
                  ,vParam VARCHAR2 DEFAULT NULL
                  ) IS
 tmpVar1 NUMBER;
 tmpVar2 NUMBER;
 vDT     NUMBER;
 sql1    LONG;
 sql2    LONG;
 sql3    LONG;
 vcnt int;
 vDocExistent number;
 v_data date;
 v_data_baza date;
 v_dtdep_baza number;
 v_dtdep number;
 vsysfid number;
BEGIN

 sql1:='SELECT COUNT(*)
       FROM VMDB_DOCS
       WHERE cod=:vNrdoc_baza
         AND '||un$g$util.ScSpCond('sysfid',vParam);

 EXECUTE IMMEDIATE sql1 INTO tmpVar1 USING vNrdoc_baza;
 --   AND sysfid IN (DECODE(NVL(vParam,0),0,sysfid,vParam));

 SELECT COUNT(*)
   INTO tmpVar2
   FROM VMDB_CMR
  WHERE nrdoc=vNrdoc_baza;

 IF tmpVar1=0
  THEN
--   msg(vNrdoc_baza||','||tmpVar1||','||tmpVar2);
   msg('Базовый документ не существует!!!');
 ELSIF tmpVar1<>0 AND tmpVar2=0 and vParam not in('402','4021')
  THEN
   msg('Базовый документ '||vNrdoc_baza||' отключен,либо не имеет проводок!!!');
 END IF;
 
 -- Controale asupra 1201 conform doc 1209  20.06.16 (ovi)
 if vParam = '1209' then
   v_data := PKG_DOCS_UTIL.doc_date(vNrdoc);
   v_data_baza := PKG_DOCS_UTIL.doc_date(vNrdoc_baza);
   if v_data <> v_data_baza then
       msg('Data documentului '||vnrdoc_baza||' nu corespunde datei documentului curent : '||vnrdoc);
     end if;
     select count(*) into vcnt from TMDB_CM where nrdoc = vNrdoc_baza; 
     /*
   if vcnt = 0 then
      msg('Documentul de baza '||vnrdoc_baza||' nu are inregistrari contabile!');
     end if;
     */
    select dtdep into v_dtdep_baza from vmdb_st201m where nrdoc = vNrdoc_baza;
    select dtdep into v_dtdep from vmdb_st201m where nrdoc = vNrdoc;
   if v_dtdep_baza <> v_dtdep
     then
        msg('Depozitul Documentului de baza '||vnrdoc_baza||' nu corespunde depozitului documentului curent : '||vnrdoc);
     end if;
 end if;

IF vParam='1227,1218' or vParam = '1209'
 THEN
 begin
 SELECT nrdoc into vDocExistent from VMDB_ST201M m where ctnrdoc=vNrdoc_baza 
 and exists (select null from vmdb_docs where cod=m.nrdoc and at1 is null);
  EXCEPTION WHEN NO_DATA_FOUND then null;
 end; 
 IF nvl(vDocExistent,0)<>0  and get_env('IGNORE_FOR_REFILL') is null
  THEN msg('Документ'||vNrdoc_baza||' уже был заполнен в документе '||vDocExistent); 
 END IF;
END IF;
 
 DELETE FROM VMDB_ST201D WHERE nrdoc=vNrdoc;
say('vaparam='|| vParam);

 IF vParam IS NULL
  THEN
    sql1:='INSERT INTO vmdb_st201d (nrdoc, dt, dtstrsc, ct,ctsc,ctdep,ctsc1, ctstrsc, ctdata, cant, i_pret, i_pretv)
   SELECT :nrdoc1, dt, dtstrsc, 2175, ctsc,ctdep,ctsc1, ctstrsc, ctdata, cant, i_pret, i_pretv
     FROM VMDB_ST201D
    WHERE nrdoc=:nrdoc';
   EXECUTE IMMEDIATE sql1 USING vNrdoc, vNrdoc_baza;
  UPDATE VMDB_ST201M a
     SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
   WHERE nrdoc=vNrdoc
     AND ctdep IS NULL;
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
  ELSIF vParam='1227,1218' or vParam = '1209' -- перемещение из ТЗ/ЦС с изм-ем кода
   THEN
    SELECT dt INTO vDT FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
    UPDATE VMDB_ST201M 
     SET (dtdep,ctdep,ctnrdoc)=(SELECT dtdep,ctdep,vNrdoc_baza FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza)
    WHERE nrdoc=vNrdoc;
    ------------- control 1201
     SELECT sysfid  INTO vsysfid  FROM VMDB_DOCS WHERE cod=vnrdoc;
     if vsysfid=1201
     then
      SELECT  wm_concat(d.dtsc) into sql1 FROM VMDB_ST201D d, TMS_MPT s WHERE d.nrdoc=vnrdoc_baza and d.dtsc is not null and s.cod=d.dtsc and NVL(prodkoefum2,0)=0; 
      if length(sql1)>3 then msg('Введите коэффициент перевода в карточку продукта '||sql1);
      end if;
     end if;
    ---------------
    sql1:='INSERT INTO vmdb_st201d (nrdoc,dt,ct,ctsc,cant,suma,ctnrdoc) '||
    'SELECT :nrdoc, :vDT, m.dt, d.dtsc, d.cant, d.suma,d.rrowid '||--/(1+Un$functs.tva(d.dtsc)),d.rrowid '||
    ' FROM VMDB_ST201D d,VMDB_ST201M m '||
    'WHERE m.nrdoc=:nrdoc1 AND  d.nrdoc=m.nrdoc and d.dtsc is not null';
   
   EXECUTE IMMEDIATE sql1 USING vNrdoc,vDT,vNrdoc_baza;
  ELSIF vParam=1300
   THEN
    sql1:='INSERT INTO vmdb_st201d (nrdoc,dt,ct,ctsc,cant,suma,dtdep)
    SELECT :nrdoc, 2171, dt, dtsc, cant,suma,1497
      FROM VMDB_ST201D
    WHERE nrdoc=:nrdoc1';
 UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND ctdep IS NULL;
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
  ELSIF vParam in (1310) 
    THEN
    select count(nrdoc) into vcnt from vmdb_st201m m, vmdb_docs d
    where m.nrdoc=d.cod and sysfid=1202 and doccolor is null and dtnrdoc=vNrdoc_baza and nrdoc<>vNrdoc;
    if vcnt>0 then msg('По указанному док-ту выхода ГП ('||vNrdoc_baza||') уже создан док-т перемещения!'); end if;
    sql1:='INSERT INTO vmdb_st201d (nrdoc,dt,ct,ctsc,cant,suma,dtdep)
    SELECT :nrdoc, 2171, 2165, sc, cant1,suma1,1497
      FROM VMDB_CST3A
    WHERE nrdoc=:nrdoc1';
 UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND ctdep IS NULL;
  UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
       , dtnrdoc=vNrdoc_baza
  WHERE nrdoc=vNrdoc;
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
  ELSIF vParam in (48108) 
    THEN
    select count(nrdoc) into vcnt from vmdb_st201m m, vmdb_docs d
    where m.nrdoc=d.cod and sysfid=1238 and doccolor is null and dtnrdoc=vNrdoc_baza and nrdoc<>vNrdoc;
    if vcnt>0 then msg('По указанному Док-ту Акт укомплектовки('||vNrdoc_baza||') уже создан док-т перемещения!'); end if;
    sql1:='INSERT INTO VMDB_CST3A (nrdoc,cont,sc,cant1,suma1,dep)
    SELECT :nrdoc, 2171,  sc, cant1,suma1,(select dtdep from vmdb_st201m where nrdoc = '||vNrdoc||')
      FROM VMDB_CST3A
    WHERE nrdoc=:nrdoc1';
 UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND ctdep IS NULL;
  UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
       , dtnrdoc=vNrdoc_baza
  WHERE nrdoc=vNrdoc;
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
    ELSIF vParam=402 -------------------------------------************************
   THEN
      sql1:='INSERT INTO VMDB_CST_PRET (nrdoc,tov_sc,pret_prih_1)
    SELECT :nrdoc, cod,price
      FROM vylin_spec_prices
    WHERE spec_id=:nrdoc1';
 /*UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND ctdep IS NULL;
  UPDATE VMDB_ST201M a
    SET ctdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
       , dtnrdoc=vNrdoc_baza
  WHERE nrdoc=vNrdoc;*/
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
  ELSIF vParam=4021 -------------------------------------************************
   THEN
      sql1:='INSERT INTO VMDB_CST_PRET (nrdoc,tov_sc,pret_prih_1)
    SELECT :nrdoc, cod,price
      FROM vylin_spec_prices_inc
    WHERE spec_id=:nrdoc1';
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza;
  ----------- ------------------*****************************
  ELSIF vParam=1233 
   THEN
    sql1:='INSERT INTO vmdb_cst3a (nrdoc,sc,prm1,cant2,cant1,pret1)
    SELECT :nrdoc,sc,:nrdoc11,cant1,cant1,pret1
      FROM VMDB_CST3A
    WHERE nrdoc=:nrdoc11';
 UPDATE VMDB_ST201M a
    SET dtdep=(SELECT dtdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND dtdep IS NULL;
    UPDATE VMDB_ST201M a
       SET ctdep=(SELECT ctdep FROM VMDB_ST201M b WHERE nrdoc=vNrdoc_baza )
  WHERE nrdoc=vNrdoc
    AND ctdep IS NULL;
  EXECUTE IMMEDIATE sql1 USING vNrdoc,vNrdoc_baza,vNrdoc_baza;
  END IF;
 UPDATE VMDB_DOCS SET nrmanual=vNrdoc_baza WHERE cod=vNrdoc;
------------
END INS_DOCS;
----------------------------------------------------------------------------------------
PROCEDURE ins_cassa(vNrdoc NUMBER) IS
 t      NUMBER;
 sql1   LONG;
 vData  DATE;
 vCasa  VARCHAR2(30);
 vFiltr LONG;
 vTemp VARCHAR2(50):=Un$sold.GET_ztemp_tablename;

  vGFC_cassa BOOLEAN:=FALSE; /* Если TRUE, то после заполнения формирует проводки */
  vShema1 LONG:='c2bam';
  vDBLink1 LONG:='NB.WORLD';  -- линк для связи с ноутбуком
  vInc_9221 NUMBER:=0;

BEGIN
--  RAISE_APPLICATION_ERROR (-20000,'DBLink'||vDBLink1);
 BEGIN
  EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM dual@'||vDBLink1 INTO t ;
 EXCEPTION WHEN OTHERS THEN
  RAISE_APPLICATION_ERROR (-20001,'Нет связи с кассой!!!');
 END;

 SELECT datamanual INTO vData FROM VMDB_DOCS WHERE cod=vNrdoc;
 SELECT dtdep INTO vCasa FROM VMDB_ST201M WHERE nrdoc=vNrdoc;

 IF vCasa IS NOT NULL THEN
  vFiltr:=' and casa=(SELECT OI_TIPSECT_S_79 FROM tms_org WHERE cod='||vCasa||')';
 END IF;

 DELETE FROM VMDB_ST201D WHERE nrdoc=vNrdoc;
 COMMIT;

 sql1:='create global temporary table '||vTemp||' on commit preserve rows as
 SELECT d.bliuda sc, m.source_nrdoc, m.state, aa.id_casa casa, codtva,
 DECODE(NVL(state,0),10,-cant, cant) cant,
 DECODE(NVL(state,0),10,-clcsumat , clcsumat ) suma,
 DECODE(NVL(state,0),10,-SUMTVA_CORRECT , SUMTVA_CORRECT ) sumatva
 ,DECODE(cnt_sk,1,cnt_sk,NULL) isTerminal, DECODE(cnt_sk,1,PAY,0) sumaCashTerminal
 ,DECODE(NVL(state,0),10,1,0) isRet
 FROM '||vShema1||'.VMDB_COMENZD_DELTA_TVA@'||vDBLink1||' d, '||vShema1||'.TMDB_COMENZ@'||vDBLink1||' m,
 '||vShema1||'.TMDB_sold@'||vDBLink1||' aa
 WHERE m.cod=d.nr_comand AND aa.nrdoc=m.nrdoc AND TRUNC(m.DATA)='''||vData||''' AND state NOT IN (0,1,5)';
--say(sql1);
 EXECUTE IMMEDIATE sql1;
 COMMIT;

sql1:='
 INSERT INTO VMDB_ST201D (nrdoc, ct, ctsc, dtnrdoc, ctnrcm, cant, suma, sumagaap, txtcoment,dtstrsc,i_pret,ctstrsc)
 SELECT nrdoc, dt ct, sc, source_nrdoc, casa, cant, suma, sumatva,
 (SELECT DECODE(PRTVA_NR,NULL,'''',PRTVA_SERIA||'' ''||PRTVA_NR) FROM VMDB01M_VINZ WHERE cod=source_nrdoc) nakl
 ,isTerminal,sumaCashTerminal,isRet
 FROM (
 SELECT '||vNrdoc||' nrdoc, sc, source_nrdoc, casa,
 CASE WHEN '||vInc_9221||'=1 AND NVL(source_nrdoc,0)<>0 THEN 2175 ELSE 2171 END dt,
 DECODE(codtva,''A'',0.2,''B'',0.08,''C'',0.05,0) codtva,
 SUM(cant) cant, SUM(suma) suma, SUM(sumatva) sumatva,
 isTerminal, SUM(sumaCashTerminal) sumaCashTerminal,isRet
 FROM '||vTemp||'
 GROUP BY source_nrdoc, casa, sc,codtva,isTerminal,isRet
 ) a WHERE 0=0'||vFiltr;
--Imt(sql1);
--say(sql1);

EXECUTE IMMEDIATE sql1;

 IF vGFC_cassa THEN
   gfc_cassa(vNrdoc,1);
 END IF;
END;
------------------------------------------------------------------------------------------
PROCEDURE ins_casa_nrdoc(vData DATE) IS
t NUMBER;

  vCont_casa NUMBER:=2414;
  vSysfid_casa NUMBER:=1211;
  vMOL NUMBER;

BEGIN

 SELECT MAX(cod) INTO t FROM VMDB_DOCS WHERE sysfid=vSysfid_casa AND datamanual=vData AND nrset=1;
  IF NVL(t,0)=0 THEN
   SELECT id_tmdb_docs.NEXTVAL INTO t FROM dual;
   INSERT INTO VMDB_DOCS(cod, datamanual, sysfid, nrset)  VALUES (t,vData, vSysfid_casa,1);
   INSERT INTO VMDB_ST201M (nrdoc,dt,ct,ctsc1) VALUES (t,vCont_casa,2171,vMOL);
  END IF;
  ins_cassa(t);
  UPDATE VMDB_ST201D SET sumavalct=cant WHERE nrdoc=t;
END ins_casa_nrdoc;
------------------------------------------------------------------------------------------
PROCEDURE ins_cassaF(vNrdoc NUMBER) IS
doc NUMBER;
new_doc NUMBER;
t NUMBER;
r NUMBER;

  vSC_Flux NUMBER:=5017;
  vCont_casa NUMBER:=2414;
  vGFC_cassa BOOLEAN:=FALSE; /* Если TRUE, то после заполнения формирует проводки */
  vSysfid_casa NUMBER:=1211;
  vSysfid_casaF NUMBER:=48309;
  vShema1 LONG:='c2bam';
--  vDBLink LONG:='ora10g1.world';  -- линк для связи с кассами
  vDBLink LONG:='boncassa.world';  -- линк для связи с кассами
  vDBLink1 LONG:='NB.WORLD';  -- линк для связи с ноутбуком
  vShema LONG:='c2bam';
  vMOL NUMBER;
  vInc_9221 NUMBER:=0;

BEGIN
SELECT nrset INTO r FROM VMDB_DOCS WHERE cod=vNrdoc;
IF r<>1 THEN
 RAISE_APPLICATION_ERROR(-20000,'Данный документ сам является производным!!!');
END IF;
SELECT dtnrdoc INTO doc FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
SELECT COUNT(*) INTO t FROM VMDB_DOCS WHERE cod=doc;
IF t=0 THEN
 UPDATE VMDB_ST201M SET dtnrdoc=NULL WHERE nrdoc=vNrdoc;
 doc:=NULL;
END IF;
IF NVL(doc,0)=0 THEN
   SELECT id_tmdb_docs.NEXTVAL INTO new_doc FROM dual;
   INSERT INTO VMDB_DOCS(cod, datamanual, sysfid, nrset)
   SELECT new_doc,Datamanual, vSysfid_casaF,2 FROM VMDB_DOCS WHERE cod=vNrdoc;
   INSERT INTO VMDB_ST201M (nrdoc,dt,ct,ctsc1, dtnrdoc)
   SELECT new_doc, dt,ct,ctsc1, vNrdoc FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   UPDATE VMDB_ST201M SET dtnrdoc=new_doc WHERE nrdoc=vNrdoc;
   doc:=new_doc;
END IF;
   DELETE FROM VMDB_ST201D WHERE nrdoc=doc;
   EXECUTE IMMEDIATE '
   INSERT INTO VMDB_ST201D (nrdoc, ct, ctsc, dtnrdoc, ctnrcm, cant, suma, txtcoment, sumagaap)
   SELECT a.*, ROUND(NVL(suma,0)*Un$functs.TVA(ctsc,ctsc, '||doc||')/(1+Un$functs.TVA(ctsc, ctsc,'||doc||')),2) tva FROM
   (SELECT '||doc||', NVL(ct,2171) ct, ctsc, dtnrdoc, ctnrcm, ctcant, NVL(clcsumax_2,0)*NVL(ctcant,0) suma, txtcoment
   FROM vmdb_st201d_tvrv WHERE nrdoc='||vNrdoc||') a WHERE NVL(ctcant,0)<>0 /*AND NVL(suma,0)<>0*/';
END ins_cassaF;
--------------------------------------------------------------------------------------------
PROCEDURE gfc_cassa(vNrdoc NUMBER, vTip NUMBER) IS
 vTVA NUMBER;
 vData DATE;
 sql1 LONG;

  vSC_Flux NUMBER:=5017;
  vCont_casa NUMBER:=2414;
  vGFC_cassa BOOLEAN:=FALSE; /* Если TRUE, то после заполнения формирует проводки */
  vSysfid_casa NUMBER:=1211;
  vSysfid_casaF NUMBER:=48309;
  vShema1 LONG:='c2bam';
--  vDBLink LONG:='ora10g1.world';  -- линк для связи с кассами
  vDBLink LONG:='boncassa.world';  -- линк для связи с кассами
  vDBLink1 LONG:='NB.WORLD';  -- линк для связи с ноутбуком
  vShema LONG:='c2bam';
  vMOL NUMBER;
  vInc_9221 NUMBER:=0;

BEGIN
 BEGIN
  SELECT NVL(VATFREE,0) INTO vTVA FROM TMDB01M_VINZ WHERE COD=vNrdoc;
 EXCEPTION WHEN OTHERS THEN vTVA:=0; END;

SELECT datamanual INTO vData FROM VMDB_DOCS WHERE cod=vNrdoc;

/*IF vTip=2 THEN
  ybmb_Docs.check_cant(vNrdoc,'(select ctsc sc, nvl(cant,0) cant1, nvl(ctcant,0) cant2,
    NVL(sumavalct,0) cant3 FROM vmdb_st201d WHERE nrdoc='||vNrdoc||')');
END IF;*/

DELETE FROM VMDB_CMI WHERE nrdoc=vNrdoc;

 /* Себестоимость 2171*/
sql1:=
   'INSERT INTO vmdb_cmi (nrdoc, funct, dt,  dtsc, dtdep, ct, ctsc, ctdep, ctsc1, cant, suma)
 SELECT :Nrdoc, 1, Un$functs.GETCONT_VINZ7(NVL(d.ct,2171)) dt,  d.ctsc dtsc,
 Ybmb_Docs.get_casa_nr(NVL(m.ctstrsc,d.ctnrcm)), NVL(d.ct,2171), d.ctsc,
 --DECODE(m.ctdep,NULL,(SELECT codi FROM vms_univers WHERE cod=m.ctsc1)) ctdep,
 NVL(d.ctdep, m.ctdep),
 DECODE('||vTip||',2,m.ctsc1,d.ctsc1),
 DECODE('||vTip||',2,d.cant,d.sumavalct) cant,
 DECODE('||vTip||',2,/*NVL(d.cant,0)*NVL(d.i_pretv,0)*/ clcsumax_4, NVL(d.sumavalct,0)*NVL(d.i_pretv,0))  suma
 FROM VMDB_ST201D_TVRV d, VMDB_ST201M m
 WHERE m.nrdoc=d.nrdoc AND m.nrdoc=:nrdoc
 AND trim(d.txtcoment) IS NULL';
--Imt(sql1);
EXECUTE IMMEDIATE sql1 USING vNrdoc, vNrdoc;

EXECUTE IMMEDIATE /* Доход + НДС */
   'INSERT INTO vmdb_cmi (nrdoc, cod, funct, dt, dt1, dtsc, dtdep, ct, ct1, ctsc, ctdep, cant, suma, codfcdebaza, ctstrsc)
 SELECT :nrdoc, d.rrowid, 2,
  m.dt, DECODE(NVL(d.ct,2171),2174,4,0),    :scFLUX dtsc, Ybmb_Docs.get_casa_nr(NVL(m.ctstrsc,d.ctnrcm)),
 Un$functs.GETCONT_VINZ6(NVL(d.ct,2171)) ct, DECODE(NVL(d.ct,2171),2174,4,0) ct1, d.ctsc, Ybmb_Docs.get_casa_nr(NVL(m.ctstrsc,d.ctnrcm)) CTDEP,
 DECODE('||vTip||',2,d.cant,d.sumavalct) cant,
    DECODE('||vTip||',2,(d.suma /*clcsumax_3*//*NVL(d.suma,0)*/-NVL(d.sumagaap,0)),NVL(d.sumavaldt,0) ) suma,
--    DECODE('||vTVA||',1,NVL(d.sumavaldt,0),(NVL(d.suma,0)-NVL(d.sumagaap,0))) suma,
 CAST (NULL AS NUMBER) codfcdebaza,
 CASE WHEN '||vInc_9221||'=1 AND d.dtnrdoc IS NOT NULL THEN ''casa''  ELSE NULL END ctstrsc
 FROM vmdb_st201d_tvrv d, VMDB_ST201M m
 WHERE m.nrdoc=d.nrdoc AND m.nrdoc=:nrdoc AND trim(d.txtcoment) IS NULL
 UNION ALL
 SELECT :nrdoc, CAST (NULL AS NUMBER) cod, 3, m.dt,DECODE(NVL(d.ct,2171),2174,4,0),:scFLUX dtsc, Ybmb_Docs.get_casa_nr(NVL(m.ctstrsc,d.ctnrcm)) ctdep,
 5342 ct, Un$functs.TVA_cont1(d.ctsc) ct1, CAST (NULL AS NUMBER) ctsc, CAST (NULL AS NUMBER) CTDEP, CAST (NULL AS NUMBER) cant,
    DECODE('||vTip||',2,NVL(d.sumagaap,0),0) suma,d.rrowid,
 CASE WHEN '||vInc_9221||'=1 AND d.dtnrdoc IS NOT NULL THEN ''casa'' ELSE NULL END ctstrsc
 FROM VMDB_ST201D d, VMDB_ST201M m
 WHERE m.nrdoc=d.nrdoc AND m.nrdoc=:nrdoc AND trim(d.txtcoment) IS NULL AND '||vTVA||'<>1'
 USING vNrdoc, vSC_Flux,vNrdoc,vNrdoc,vSC_Flux,vNrdoc;

EXECUTE IMMEDIATE /* Закрытие долга по НН через кассу */
   'INSERT INTO vmdb_cmi (nrdoc, dt, dtsc, dtdep, ct,ctdep,suma,funct)
 SELECT  :nrdoc, a.dt,  :ini_SCFlux, a.dtdep, /*(SELECT dt FROM vmdb_st201m WHERE nrdoc=a.dtnrdoc)*/ 2211 ct,
 (SELECT dtdep FROM VMDB_ST201M WHERE nrdoc=a.dtnrdoc) ctdep, a.suma, 4 FROM (
 SELECT m.dt,  m.dtdep, SUM(d.SUMA) suma, d.dtnrdoc FROM VMDB_ST201D d, VMDB_ST201M m
 WHERE d.nrdoc=m.nrdoc AND m.nrdoc=:nrdoc AND d.dtnrdoc IS NOT NULL AND txtcoment IS NOT NULL
 GROUP BY m.dt,m.dtdep,d.dtnrdoc) a
 WHERE dtnrdoc IN (SELECT cod FROM VMDB01M_VINZ WHERE prtva_seria IS NOT NULL AND prtva_nr IS NOT NULL)'
 USING vNrdoc, vSC_Flux,vNrdoc;

IF vInc_9221=1 THEN
 EXECUTE IMMEDIATE
   'INSERT INTO vmdb_cmi (nrdoc, ct,ctsc,ctdep, cant, suma, funct)
 SELECT d.nrdoc, 9221, d.ctsc,(SELECT dtdep FROM VMDB_ST201M WHERE nrdoc=d.dtnrdoc) ctdep, d.cant, d.suma,10
 FROM VMDB_ST201D d WHERE d.nrdoc=:nrdoc AND d.dtnrdoc IS NOT NULL AND txtcoment IS NULL ' using vNrdoc;
END IF;
-----------------------------
END gfc_cassa;
--------------------------------------------------------------------------------------------
FUNCTION get_casa_nr(vCassa NUMBER) RETURN NUMBER IS
t NUMBER;
BEGIN
IF NVL(vCassa,0)=0 THEN
 RAISE_APPLICATION_ERROR(-20001,'Укажите № кассы!!!');
END IF;
 BEGIN
  SELECT cod INTO t FROM TMS_ORG WHERE OI_TIPSECT_S_79=vCassa;
 EXCEPTION WHEN NO_DATA_FOUND
  THEN RAISE_APPLICATION_ERROR(-20000,'В карточке № кассы укажите код кассы!'||vCassa);
 WHEN TOO_MANY_ROWS
  THEN RAISE_APPLICATION_ERROR(-20000,'Несколько касс под одним кодом!'||vCassa);
 END;
 RETURN t;
--------------------------------------
END get_casa_nr;
--------------------------------------------------------------------------------
PROCEDURE check_cant(vNrdoc NUMBER, vTable VARCHAR2) IS
BEGIN
 EXECUTE IMMEDIATE
  'BEGIN '||
  'FOR c1_rec IN ('||vTable||')  LOOP '||
   'IF c1_rec.cant1<>c1_rec.cant2+c1_rec.cant3 THEN  '||
    'RAISE_APPLICATION_ERROR (-20001,''Не совпадает кол-во по товару: ''||c1_rec.sc); '||
  ' END IF; '||
  'END LOOP; '||
 'END;';
----------------------------------------
END check_cant;
--------------------------------------------------------------------------------
/*PROCEDURE gfc_Akt_peresort(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vCont830 NUMBER:=8301;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>vCont830
  ,vCt     =>'nvl(d.dt,m.dt)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  ,vCod    =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_U
  ,vCtNrCM   =>vNrCM_U
  ,vWhere_before =>' and d.dtstrsc=1'
  );

 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>vCont830
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  ,vCod    =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_U
  ,vCtNrCM   =>vNrCM_U
  ,vWhere_before =>' and d.dtstrsc=2'
  );

 IF vNrset=3 THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>vCont830
  ,vCt     =>'nvl(d.dt,m.dt)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.sumagaap'
--  ,vCod    =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vWhere_before =>' and d.dtstrsc=1'
  );

 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>vCont830
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.sumagaap'
--  ,vCod    =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vWhere_before =>' and d.dtstrsc=2'
  );
 END IF;
--------
END gfc_Akt_peresort;*/
--
PROCEDURE gfc_Akt_peresort(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vCont830 NUMBER:=Yparams.vCont8301;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;
IF Yparams.vUse_U AND (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201(vNrdoc, vDt=>vCont830, vCt=>'nvl(d.dt,m.dt)', vDtSC=>'d.dtsc', vCtSC=>'d.dtsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.ctdep', vCant=>'d.cant', vSuma=>'d.suma', vCod=>'d.rrowid'
  ,vDtNrCM=>vNrCM_U, vCtNrCM=>vNrCM_U, vWhere_before =>' and d.dtstrsc=1');
 Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vCt=>vCont830, vDtSC=>'d.dtsc', vCtSC=>'d.dtsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.ctdep', vCant=>'d.cant', vSuma=>'d.suma', vCod=>'d.rrowid'
  ,vDtNrCM=>vNrCM_U, vCtNrCM=>vNrCM_U, vWhere_before=>' and d.dtstrsc=2');
END IF;
IF (vNrset=2 OR vNrset=3) THEN
 IF Yparams.vTip_Retail=1 THEN --coli4estvenno-summovoi
  --Dt 8301 Ct 217
 Gfc_Util.gfc201(vNrdoc, vDt=>vCont830, vCt=>'nvl(d.dt,m.dt)', vDtSC=>'d.dtsc', vCtSC=>'d.dtsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.ctdep', vCant=>'d.cant', vSuma=>'d.suma'
  ,vDtNrCM=>vNrCM_F, vCtNrCM=>vNrCM_F, vWhere_before=>' and d.dtstrsc=1');
  -- Dt 217 Ct 8301
 Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vCt=>vCont830, vDtSC=>'d.dtsc'
 --, vCtSC=>'(select f.dtsc from YBON_VMDB_ST201D_TVR f  where f.nrdoc=d.Nrdoc and f.dtstrsc=1 and f.dtsc=)'
 , vCtSC=>'(select f.dtsc from (
select d.dtsc, row_number() over(order by rrowid) rn  from YBON_VMDB_ST201D_TVR  d where d.nrdoc='||vNrdoc||' and d.dtstrsc=1
) f
where rn = (select rn from (select row_number() over(order by rrowid) rn, g.dtsc, g.rrowid  from YBON_VMDB_ST201D_TVR  g where g.nrdoc='||vNrdoc||' and g.dtstrsc=2) g where g.dtsc = d.dtsc and g.rrowid=d.rrowid ) )'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.ctdep', vCant=>'d.cant', vSuma=>'d.suma'
  ,vDtNrCM=>vNrCM_F, vCtNrCM=>vNrCM_F, vWhere_before=>' and d.dtstrsc=2'/*,vDebug=> true*/);
 ELSIF Yparams.vTip_Retail=2 THEN --summovoi
 NULL;
 END IF;
END IF;
--------
END gfc_Akt_peresort;
--------------------------------------------------------------------------------
PROCEDURE gfc_PeremescIzTZ(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 cnt NUMBER;

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 SELECT COUNT(*) INTO cnt FROM VMDB01M_VINZ WHERE cod=vNrdoc;
 IF cnt=0 THEN
  INSERT INTO VMDB01M_VINZ(cod,SCOMMENT) VALUES (vNrdoc,' ');
 END IF;
 IF vNrset=1 THEN
   UPDATE VMDB01M_VINZ SET VATFREE=1 WHERE cod=vNrdoc;
 END IF;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(m.dt,8300)'
  ,vCt     =>'nvl(d.dt,m.ct)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
--  ,vCod    =>'d.rrowid'
  ,vDtNrdoc  =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_U
  ,vCtNrCM   =>vNrCM_U
  ,vWhere    =>''
  );
END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(m.dt,8300)'
  ,vCt     =>'nvl(d.dt,m.ct)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  --,vSuma   =>'d.suma'
  ,vSuma   =>'d.suma/(1+un$functs.tva(d.dtsc,m.ctdep))'
  ,vDtNrdoc  =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vWhere    =>''
  );
 END IF;
--------
END gfc_PeremescIzTZ;
--------------------------------------------------------------------------------
PROCEDURE gfc_PeremescIzTZ2(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 cnt NUMBER;

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 SELECT COUNT(*) INTO cnt FROM VMDB01M_VINZ WHERE cod=vNrdoc;
 IF cnt=0 THEN
  INSERT INTO VMDB01M_VINZ(cod,SCOMMENT) VALUES (vNrdoc,' ');
 END IF;
 IF vNrset=1 THEN
   UPDATE VMDB01M_VINZ SET VATFREE=1 WHERE cod=vNrdoc;
 END IF;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'8300'
  ,vCt     =>'nvl(d.dt,m.ct)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
--  ,vCod    =>'d.rrowid'
  ,vDtNrdoc  =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_U
  ,vCtNrCM   =>vNrCM_U
  ,vWhere    =>''
  );
END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'8300'
  ,vCt     =>'nvl(d.dt,m.ct)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.dtsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma/(1+un$functs.tva(d.dtsc,m.ctdep))'
  ,vDtNrdoc  =>'d.rrowid'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vWhere    =>''
  );
 END IF;
--------
END gfc_PeremescIzTZ2;
--------------------------------------------------------------------------------
PROCEDURE gfc_PeremescNaKuhniu(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 cnt NUMBER;

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 SELECT COUNT(*) INTO cnt FROM VMDB01M_VINZ WHERE cod=vNrdoc;
 IF cnt=0 THEN
  INSERT INTO VMDB01M_VINZ(cod,SCOMMENT) VALUES (vNrdoc,' ');
 END IF;
 IF vNrset=1 THEN
   UPDATE VMDB01M_VINZ SET VATFREE=1 WHERE cod=vNrdoc;
 END IF;

-- dt 2172 ct 8300

IF Yparams.vUse_U AND (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vCt=>Yparams.vCont8300, vDtSC=>'d.dtsc', vCtSC=>'d.ctsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.dtdep', vCant=>'nvl(d.dtcant1,d.cant)', vSuma=> 'd.suma'
  ,vDtNrCM=>vNrCM_U, vCtNrCM=>vNrCM_U, vCtnrdoc =>'', vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)'
  ,vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
  --  ,vWhere_before=>' and m.ct<>m.dt and (d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant)'
   ,vWhere=>'' );
-- dt 8300 ct 2171
  Gfc_Util.gfc201(vNrdoc, vDt=>Yparams.vCont8300, vCt=>'nvl(d.ct,m.ct)', vDtSC=>'d.ctsc', vCtSC=>'d.ctsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.dtdep', vCant=>'d.cant', vSuma=>'d.suma'
  ,vDtNrdoc=>'d.rrowid', vDtNrCM=>vNrCM_U, vCtNrCM=>vNrCM_U
  ,vWhere_before=>' and nvl(d.ct,m.ct)<>'||Yparams.vCont8300||' and d.dtsc<>d.ctsc'-- and nvl(d.dtcant1,d.cant)<>d.cant'
                --' and nvl(d.ct,m.ct)<>8300 and m.ct<>m.dt and d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant'
  ,vWhere=>'');
 END IF;

 /*IF (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201
  (vNrdoc ,vDt     =>'nvl(d.dt,m.dt)'  ,vCt     =>'8300'  ,vDtSC   =>'d.dtsc'  ,vCtSC   =>'d.ctsc'  --'decode (nvl(m.ct,d.ct),8300,d.ctsc,d.dtsc)'
  ,vDtDep  =>'m.dtdep'  ,vCtDep  =>'m.dtdep'  ,vCant   =>'nvl(d.dtcant1,d.cant)'  ,vSuma   =>'d.suma'--*(1+un$functs.tva(d.ctsc))'
  ,vDtNrCM   =>vNrCM_U  ,vCtNrCM   =>vNrCM_U  ,vCtnrdoc =>''  ,vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)'
  ,vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
--  ,vWhere_before=>' and m.ct<>m.dt and (d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant)'
   ,vWhere=>''
  );
--  ,vWhere_before=>' and m.ct<>m.dt'

-- dt 8300 ct 2171
  Gfc_Util.gfc201
  (vNrdoc  ,vDt          =>'8300'  ,vCt          =>'nvl(d.ct,m.ct)'  ,vDtSC        =>'d.ctsc'  ,vCtSC        =>'d.ctsc'
  ,vDtDep       =>'m.dtdep'  ,vCtDep       =>'m.dtdep'  ,vCant        =>'d.cant'  ,vSuma        =>'d.suma'--*(1+un$functs.tva(d.ctsc))'
  ,vDtNrdoc     =>'d.rrowid'  ,vDtNrCM      =>vNrCM_U  ,vCtNrCM      =>vNrCM_U
  ,vWhere_before=>' and nvl(d.ct,m.ct)<>8300 and d.dtsc<>d.ctsc'-- and nvl(d.dtcant1,d.cant)<>d.cant'
                --' and nvl(d.ct,m.ct)<>8300 and m.ct<>m.dt and d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant'
  ,vWhere=>''
  );
---  ,vWhere_before=>' and nvl(m.ct,d.ct)<>8300 and m.ct<>m.dt'

END IF;*/
--  ,vWhere_before=>' and m.ct=m.dt and d.dtsc=d.ctsc and m.dtdep<>m.ctdep'

 IF (vNrset=2 OR vNrset=3) THEN
 IF Yparams.vTip_Retail=1 THEN --coli4estvenno-summovoi
-- dt 217 ct 8300
  Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vDtSC=>'d.dtsc', vDtDep=>'m.dtdep'
  ,vCt=>'decode(nvl(m.ct,d.ct),'||Yparams.vCont8300||',nvl(m.ct,d.ct),'||Yparams.vCont8300||')'
  ,vCtSC=>'decode (nvl(m.ct,d.ct),'||Yparams.vCont8300||',d.ctsc,d.dtsc)', vCtDep=>'m.dtdep'
  ,vCant=>'nvl(d.dtcant1,d.cant)', vSuma=>/*'d.suma'*/'d.suma/(1+un$functs.tva(d.ctsc,m.dtdep))', vDtNrCM=>vNrCM_F, vCtNrCM=>vNrCM_F, vCtnrdoc=>''
  ,vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)', vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
  ,vWhere_before=>' and m.ct<>m.dt and (d.dtsc<>d.ctsc or nvl(d.dtcant1,d.cant)<>d.cant)', vWhere=>'');
-- dt 8300 ct 2171
  Gfc_Util.gfc201(vNrdoc, vDt=>Yparams.vCont8300, vCt=>'nvl(d.ct, m.ct)', vDtSC=>'d.ctsc', vCtSC=>'d.ctsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'nvl(d.ctdep,m.dtdep)', vCant=>'d.cant', vSuma=>/*'d.suma'*/'d.suma/(1+un$functs.tva(d.ctsc,m.dtdep))', vDtNrdoc=>'d.rrowid', vDtNrCM=>vNrCM_F, vCtNrCM=>vNrCM_F
  ,vWhere_before=>' and nvl(d.ct,m.ct)<>'||Yparams.vCont8300||' and /*m.ct<>m.dt and (*/d.dtsc<>d.ctsc /*or nvl(d.dtcant1,d.cant)<>d.cant)*/'
  ,vWhere=>'');
-- ???????? WHAT IS THIS??????????
/*  Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(m.dt,d.dt)', vCt=>'nvl(m.ct,d.ct)', vDtSC=>'d.dtsc', vCtSC=>'d.ctsc'
  ,vDtDep=>'m.dtdep', vCtDep=>'m.dtdep', vCant=>'nvl(d.dtcant1,d.cant)', vSuma=>'d.suma'
  ,vDtNrCM=>vNrCM_F, vCtNrCM=>vNrCM_F, vCtnrdoc=>''
  ,vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)', vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
  ,vWhere_before=>'and (d.dtsc<>d.ctsc or d.dtsc=d.ctsc) and nvl(d.dtcant1,d.cant)=d.cant'
  ,vWhere=>'');*/
 ELSIF Yparams.vTip_Retail=2 THEN --summovoi
 NULL;
 END IF;
 
/*  Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>'decode(nvl(m.ct,d.ct),8300,nvl(m.ct,d.ct),8300)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'decode (nvl(m.ct,d.ct),8300,d.ctsc,d.dtsc)'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.dtdep'
  ,vCant   =>'nvl(d.dtcant1,d.cant)'
  ,vSuma   =>'d.suma'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vCtnrdoc =>''
  ,vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)'
  ,vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
  ,vWhere_before=>' and m.ct<>m.dt and (d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant)'
  ,vWhere=>''
  );

-- dt 8300 ct 2171
  Gfc_Util.gfc201
  (vNrdoc
  ,vDt          =>'8300'
  ,vCt          =>'nvl(m.ct,d.ct)'
  ,vDtSC        =>'d.dtsc'
  ,vCtSC        =>'d.ctsc'
  ,vDtDep       =>'m.dtdep'
  ,vCtDep       =>'m.dtdep'
  ,vCant        =>'d.cant'
  ,vSuma        =>'d.suma'
  ,vDtNrdoc     =>'d.rrowid'
  ,vDtNrCM      =>vNrCM_F
  ,vCtNrCM      =>vNrCM_F
  ,vWhere_before=>' and nvl(m.ct,d.ct)<>8300 and m.ct<>m.dt and d.dtsc<>d.ctsc and nvl(d.dtcant1,d.cant)<>d.cant'
  ,vWhere=>''
  );

  Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(m.dt,d.dt)'
  ,vCt     =>'nvl(m.ct,d.ct)'
  ,vDtSC   =>'d.dtsc'
  ,vCtSC   =>'d.ctsc'
  ,vDtDep  =>'m.dtdep'
  ,vCtDep  =>'m.dtdep'
  ,vCant   =>'nvl(d.dtcant1,d.cant)'
  ,vSuma   =>'d.suma'
  ,vDtNrCM   =>vNrCM_F
  ,vCtNrCM   =>vNrCM_F
  ,vCtnrdoc =>''
  ,vCODFCDEBAZA =>'nvl(d.CTNRDOC,d.rrowid)'
  ,vNRDOCFCDEBAZA =>'nvl(m.CTNRDOC,m.nrdoc)'
  ,vWhere_before=>'and (d.dtsc<>d.ctsc or d.dtsc=d.ctsc) and nvl(d.dtcant1,d.cant)=d.cant'
  ,vWhere=>''
  );*/
--  ,vWhere_before=>' and m.ct=m.dt and d.dtsc=d.ctsc and m.dtdep<>m.ctdep'

 END IF;

--------
END gfc_PeremescNaKuhniu;
--------------------------------------------------------------------------------
PROCEDURE gfc_VozvrOtPokup(vNrdoc NUMBER,vSC_2414 NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'un$functs.GETCONT_VINZ7(M.Dt)'
  ,vCt     =>'nvl(m.Dt,d.Dt)'
  ,vCt1=>''
  ,vDtSc   =>'d.dtsc'
  ,vCtSc   =>'d.dtsc'
  ,vDtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'nvl(-d.sumagaap,0)'
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtnrcm=>vNrCM_U
  ,vCtnrcm=>vNrCM_U
  );

  Gfc_Util.gfc201(
   vNrdoc
  --,vCod  =>'d.rrowid'
  ,vDt   =>'m.ct'
  ,vCt   =>'un$functs.GETCONT_VINZ6(m.Dt)'
  ,vDtSc =>vSC_2414
  ,vCtSc =>'d.dtsc'
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep =>'m.DtDep'
  ,vDtsc1 =>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1 =>''
  ,vCant  =>'-d.cant'
  ,vSuma  =>'nvl(-d.suma,0)'---round((d.suma)/(1+un$functs.tva(d.dtsc)),2),0)'
  ,vWhere =>''
  ,vDtnrcm=>vNrCM_U
  ,vCtnrcm=>vNrCM_U
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
     -- доход ------------
  Gfc_Util.gfc201(
   vNrdoc
  ,vCod  =>'d.rrowid'
  ,vDt   =>'m.ct'
  ,vCt   =>'un$functs.GETCONT_VINZ6(m.Dt)'
  ,vct1=>'nvl(d.ct1,Un$functs.tva_cont1(d.dtsc))'
  ,vDtSc =>vSC_2414
  ,vCtSc =>'decode(nvl('||Yparams.get_params('vTip_Retail')||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep =>'m.DtDep'
  ,vDtsc1 =>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1 =>''
  ,vCant  =>'-d.cant'
  ,vSuma  =>'nvl(nvl(-d.suma,0)-nvl(-d.sumavaldt,0),nvl(-d.sumagaap,0))'
  ,vWhere =>''
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  );
 -- НДС ------------------
  Gfc_Util.gfc201(
   vNrdoc
  ,vDt=>'m.ct'
  ,vCt=>'5342'
  ,vct1=>'nvl(d.ct1,Un$functs.tva_cont1(d.dtsc))'
  ,vDtSc=>vSC_2414
  ,vCtSc=>''
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep=>''
  ,vDtsc1=>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1=>''
  ,vCant=>''
  ,vsuma=>'nvl(-d.SUMAVALDT,-d.sumavalct)'
  --,vSuma  =>'nvl(-round((d.suma)/(1+un$functs.tva(d.dtsc))*un$functs.tva(d.dtsc),2),0)'
  ,vWhere=>''
  ,vCODFCDEBAZA=>'d.RROWID'
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  ,vTVACont1Recognition=>false
 );
 -- себестоимость------
 Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'un$functs.GETCONT_VINZ7(M.Dt)'
  ,vCt     =>'nvl(m.Dt,d.Dt)'
  ,vCt1=>''
  ,vDt1=>'nvl(d.ct1,Un$functs.tva_cont1(d.dtsc))'
  ,vDtSc =>'decode(nvl('||Yparams.vTip_Retail||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vCtSc =>'decode(nvl('||Yparams.vTip_Retail||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vDtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'nvl(nvl(-d.suma,0)-nvl(-d.sumavaldt,0),nvl(-d.sumagaap,0))'
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  );
END IF;
--------
END gfc_VozvrOtPokup;
--------------------------------------------------------------------------------
PROCEDURE gfc_VozvrOtPokup_group_tva(vNrdoc NUMBER,vSC_2414 NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
  (vNrdoc, 777
  ,vDt     =>'un$functs.GETCONT_VINZ7(M.Dt)'
  ,vCt     =>'nvl(m.Dt,d.Dt)'
  ,vDtSc   =>'d.dtsc'
  ,vCtSc   =>'d.dtsc'
  ,vDtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'nvl(-d.sumagaap,0)'
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtnrcm=>vNrCM_U
  ,vCtnrcm=>vNrCM_U
  );

  Gfc_Util.gfc201(
   vNrdoc,777
  --,vCod  =>'d.rrowid'
  ,vDt   =>'m.ct'
  ,vCt   =>'un$functs.GETCONT_VINZ6(m.Dt)'
  ,vDtSc =>vSC_2414
  ,vCtSc =>'d.dtsc'
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep =>'m.DtDep'
  ,vDtsc1 =>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1 =>''
  ,vCant  =>'-d.cant'
  ,vSuma  =>'nvl(-d.suma,0)'---round((d.suma)/(1+un$functs.tva(d.dtsc)),2),0)'
  ,vWhere =>''
  ,vDtnrcm=>vNrCM_U
  ,vCtnrcm=>vNrCM_U
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
     -- доход ------------
  Gfc_Util.gfc201(
   vNrdoc,777
  ,vCod  =>'d.rrowid'
  ,vDt   =>'m.ct'
  ,vCt   =>'un$functs.GETCONT_VINZ6(m.Dt)'
  ,vct1=>'Un$functs.tva_cont1(d.dtsc)'
  ,vDtSc =>vSC_2414
  ,vCtSc =>'decode(nvl('||Yparams.get_params('vTip_Retail')||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep =>'m.DtDep'
  ,vDtsc1 =>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1 =>''
  ,vCant  =>'-d.cant'
  ,vSuma  =>'nvl(-d.sumagaap,0)'
  ,vWhere =>''
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  );
 -- НДС ------------------
  Gfc_Util.gfc201(
   vNrdoc,777
  ,vDt=>'m.ct'
  ,vCt=>'5342'
  ,vct1=>'Un$functs.tva_cont1(d.dtsc)'
  ,vDtSc=>vSC_2414
  ,vCtSc=>''
  ,vDtdep =>'nvl(m.CtDep,d.dtdep)'
  ,vCtdep=>''
  ,vDtsc1=>'nvl(d.dtsc1,m.ctsc1)'
  ,vCtsc1=>''
  ,vCant=>''
  ,vsuma=>'-d.SUMAVALCT'
  --,vSuma  =>'nvl(-round((d.suma)/(1+un$functs.tva(d.dtsc))*un$functs.tva(d.dtsc),2),0)'
  ,vWhere=>''
  ,vCODFCDEBAZA=>'d.RROWID'
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  ,vTVACont1Recognition=>false
 );
 -- себестоимость------
 Gfc_Util.gfc201
  (vNrdoc,777
  ,vDt     =>'un$functs.GETCONT_VINZ7(M.Dt)'
  ,vCt     =>'nvl(m.Dt,d.Dt)'
  ,vDt1=>'Un$functs.tva_cont1(d.dtsc)'
  ,vDtSc =>'decode(nvl('||Yparams.vTip_Retail||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vCtSc =>'decode(nvl('||Yparams.vTip_Retail||',1), 1, d.dtsc, Ybon_Docs.decode_sc(d.dtsc,d.dt))'
  ,vDtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCtDep  =>'nvl(m.dtdep,d.dtdep)'
  ,vCant   =>'-d.cant'
  --,vSuma   =>'nvl(-d.sumagaap,0)'
  ,vSuma   =>'nvl(-d.ctcant1,0)'
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtnrcm=>vNrCM_F
  ,vCtnrcm=>vNrCM_F
  );
END IF;
--------
END gfc_VozvrOtPokup_group_tva;
--------------------------------------------------------------------------------
PROCEDURE GFC_Peremesc_v_TZ(
                        in_doc NUMBER
                      , in_date DATE
                       ) IS
 vSQL  LONG;
 vSQL1 LONG;
 vCount1 NUMBER:=1;
 vCount2 NUMBER:=0;
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(in_doc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(in_doc,1);
BEGIN
--------
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=in_doc;
---------
-- перемещение ГП
 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
 (
   vNrdoc=>in_doc
 , vCod=>'d.rrowid'
 , vDt=>'nvl(m.dt,d.dt)'
 , vCt=>'nvl(m.ct,d.ct)'
 , vDtsc=>'d.ctsc'
 , vCtsc=>'d.ctsc'
 , vDtDep=>'m.dtdep'
 , vCtDep=>'m.ctdep'
 --, vDtsc1=>'m.dtsc1'
 --, vCtsc1=>'m.ctsc1'
 , vCant=>'d.cant'
 , vSuma=>'round(nvl(d.suma,0),2)'
    , vDtNrCm=>vNrCM_U
    , vCtNrCm=>vNrCM_U
    ,vWhere=>''
 );
 ---
 Gfc_Util.gfc201
 (
   vNrdoc=>in_doc
 , vDt=>'nvl(m.dt,d.dt)'
 , vCt=>6126
 , vDtsc=>'d.ctsc'
 , vCtsc=>'d.ctsc'
 , vDtDep=>'m.dtdep'
 , vCtDep=>'m.ctdep'
 --, vDtsc1=>'m.dtsc1'
 --, vCtsc1=>'m.ctsc1'
 , vCant=>NULL
 , vCodfcdebaza=>'d.rrowid'
 , vSuma=>'round(nvl(d.sumavalct,0)-nvl(d.suma,0),2)'
    , vDtNrCm=>vNrCM_U
    , vCtNrCm=>vNrCM_U
    ,vWhere=>''
 );
 END IF;
 IF (vNrset=2 OR vNrset=3)
  THEN
 Gfc_Util.gfc201
 (
   vNrdoc=>in_doc
 , vCod=>'-d.rrowid'
 , vDt=>'nvl(m.dt,d.dt)'
 , vCt=>'nvl(m.ct,d.ct)'
 , vDtsc=>'d.ctsc'
 , vCtsc=>'d.ctsc'
 , vDtDep=>'m.dtdep'
 , vCtDep=>'m.ctdep'
 --, vDtsc1=>'m.dtsc1'
 --, vCtsc1=>'m.ctsc1'
 --, vCant=>'d.cant'
 , vSuma=>'round(d.suma/(1+un$functs.tva(d.ctsc)),2)'
    , vDtNrCm=>vNrCM_F
    , vCtNrCm=>vNrCM_F
    ,vWhere=>''
 );
 --- Убрано АК по заявке 2011102810845 
 /*
 Gfc_Util.gfc201
 (
   vNrdoc=>in_doc
 , vDt=>'nvl(m.dt,d.dt)'
 , vCt=>6126
 , vDtsc=>'d.ctsc'
 , vCtsc=>'d.ctsc'
 , vDtDep=>'m.dtdep'
 , vCtDep=>'m.ctdep'
 , vCant=>NULL
 , vCodfcdebaza=>'-d.rrowid'
 , vSuma=>'round((d.sumavalct-d.suma)/(1+un$functs.tva(d.ctsc)),2)'
    , vDtNrCm=>vNrCM_F
    , vCtNrCm=>vNrCM_F
    ,vWhere=>''
 );*/
  END IF;
------------------
END GFC_Peremesc_v_TZ;
------------------------------------------------------------------------------------------------------------------
PROCEDURE GFC_Vihod_GP (
  in_doc NUMBER
, in_date DATE
--, in_cod_cuhni NUMBER DEFAULT 1280
--, in_cod_rest NUMBER DEFAULT 1277
) IS
 cError  CONSTANT NUMBER:=25; -- кол-во уровней вложенности полуфабрикатов
 vTable  VARCHAR2(30); -- таблица блюд из документа
 vTable1 VARCHAR2(30); -- таблица продуктов по регистру норм
 vTable2 VARCHAR2(30); -- имя таблицы возвращенной из ф-ции ybon_norme.Calc_matnorme
 vTable3 VARCHAR2(30); -- имя таблицы подготавливаемой для вставки в СМ
 vSQL  LONG;
 vSQL1 LONG;
 vCount1 NUMBER:=1;
 vCount2 NUMBER:=0;
 vDtCont NUMBER:=8281; -- счет производства
 vCtCont NUMBER:=2165; -- счет ГП
-- vCont7111 NUMBER:=7111; -- счет ГП
-- vCont7112 NUMBER:=7112; -- счет ГП
 vLvl    NUMBER:=0;
 vDestDep NUMBER;      -- место продажи
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(in_doc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(in_doc,1);

BEGIN

 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=in_doc;

 vTable:=un$ttemp.GetTempName(); -- таблица товаров и п/ф
 vTable2:=un$ttemp.GetTempName(); -- таблица продуктов

 vSQL:='select dtdep from vmdb_st201m where nrdoc='||in_doc;
 EXECUTE IMMEDIATE vSQL INTO vDestDep;

 vSQL:='create global temporary table '||vTable||'(
    lvl     NUMBER -- уровень вложенности 0-ой означает сам продукт
   ,ctcont  NUMBER
   ,parnt   NUMBER -- изначальный продукт
   ,dtsc    NUMBER -- субузел
   ,sc      NUMBER -- подузел для нулевого уровня все 3 значения одинаковы
   ,dtdep   NUMBER -- кухня
   ,dtdata  DATE
   ,portii  NUMBER
   ,cant    NUMBER
   ,suma    NUMBER
   ) ON COMMIT PRESERVE ROWS';
 EXECUTE IMMEDIATE vSQL;

 vSQL:='insert into '||vTable||'(lvl,parnt,dtsc,sc,dtdep,dtdata,cant)
 SELECT DISTINCT '||vLvl||',d.dtsc,d.dtsc,d.dtsc,m.ctdep,'''||in_date||''',d.cant
 FROM VMDB_ST201D d,VMDB_ST201M m WHERE d.nrdoc='||in_doc||' AND m.nrdoc='||in_doc;
 EXECUTE IMMEDIATE vSQL;
 COMMIT;

 vSql1:='SELECT ctsc_d2_mat sc FROM VUN9MAGR_1REGNORM_D2 INTERSECT
 SELECT sc_m_produs sc FROM VUN9MAGR_1REGNORM_M_D1';
 LOOP
  vLvl:=vLvl+1;
--- получаем нормы для продуктов и полуфабрикатов
  vSQL:='(select dtdata data, sc, dtdep depct,nvl(cant,1) cant
          FROM '||vTable||'
          WHERE lvl='||vLvl||'-1)';
  vTable1:=Ybon_Norme.calc_matnorme(vTable=>vSql, tip=>2);
--- вставляем только п/ф из норм для текущего уровня
  vSQL:='insert into '||vTable||'(lvl,ctcont,parnt,dtsc,dtdata,sc,dtdep,cant)
  SELECT '||vLvl||',b.cont,a.parnt,a.sc,a.dtdata,b.produs,b.depct,b.norma
  FROM '||vTable||' a,'||vTable1||' b
  WHERE b.produs IN ('||vSql1||')
  AND a.sc=b.sc
  AND a.lvl='||vLvl||'-1';
  EXECUTE IMMEDIATE vSQL;
--  say(vSql);
--- проверка условия для выхода из цикла
  vSQL:='select count(*) from '||vTable||' where Lvl='||vLvl;
  EXECUTE IMMEDIATE vSQL INTO vCount1;
  EXIT WHEN vCount1=0;
--- проверка зацикливания (ограничение кол-ва вложенных узлов)
  IF vLvl=cError THEN
   RAISE_APPLICATION_ERROR(-20000,'Проверьте нормы, где-то есть циклическое вхождение!!!');
  END IF;
 END LOOP;

 vSQL:='create global temporary table '||vTable2||'(
    contct  NUMBER
   ,parnt   NUMBER
   ,dtsc    NUMBER
   ,dtdep   NUMBER
   ,ctsc    NUMBER
   ,cant    NUMBER
   ,pret    NUMBER
   ) ON COMMIT PRESERVE ROWS';
 EXECUTE IMMEDIATE vSQL;

 vSql1:='SELECT sc FROM '||vTable;
 vSQL:='insert into '||vTable2||'(contct,parnt,dtsc,dtdep,ctsc,cant)
  SELECT
   d2.ct
  ,d.parnt
  ,d.SC
  ,d.dtdep
  ,d2.CTSC_D2_MAT
  ,(d2.CANT/DECODE(NVL(regm.p1,1),0,1,regm.p1))*NVL(d.cant,1) cant
  FROM VUN9MAGR_1REGNORM_D2 d2
     , VUN9MAGR_1REGNORM_M_D1 regm
     , '||vTable||' d
    WHERE d2.ID_M=regm.ID_M
    AND d2.ID_D1=regm.ID_D1
    AND regm.SC_M_PRODUS=d.sc
    AND d.dtdata BETWEEN regm.DATASTART AND regm.DATAEND
    AND d2.CTSC_D2_MAT NOT IN ('||vSql1||')';
 EXECUTE IMMEDIATE vSQL;

 vSQL:='update '||vTable2||'
    SET pret=ROUND(Ybon_Control.get_price(ctsc,dtdep,'''||in_date||'''),3)';
 EXECUTE IMMEDIATE vSQL;
--- проставление цен на ГП
 vSQL:='update '||vTable||' b
    SET suma=(SELECT SUM(cant*pret) FROM '||vTable2||' a WHERE a.parnt=b.dtsc)
    WHERE b.lvl=0';
 EXECUTE IMMEDIATE vSQL;

 vSQL:='update '||vTable||' b
    SET suma=(SELECT SUM(cant*pret) FROM '||vTable2||' a
    WHERE a.parnt=b.parnt AND a.dtsc=b.sc)
    WHERE b.lvl<>0';
 EXECUTE IMMEDIATE vSQL;

 vSQL:='update '||vTable||' b
    SET portii=(SELECT p1 FROM VUN9MAGR_1REGNORM_M_D1 m
    WHERE m.SC_M_PRODUS=b.dtsc
    AND b.dtdata BETWEEN m.DATASTART AND m.DATAEND)
    WHERE b.lvl=0';
 EXECUTE IMMEDIATE vSQL;

 vTable3:=un$ttemp.GetTempName();
 vSQL:='create global temporary table '||vTable3||'(
    dt NUMBER
   ,ct NUMBER
   ,dtsc NUMBER
   ,ctsc NUMBER
   ,dtdep NUMBER
   ,ctdep NUMBER
   ,ctsc1 NUMBER
   ,cant NUMBER
   ,suma NUMBER
   ) ON COMMIT PRESERVE ROWS';
 EXECUTE IMMEDIATE vSQL;

 vSql1:='select '||vDtCont||',contct,dtsc,ctsc,dtdep,dtdep,round(cant,4),round(cant*pret,2) from '||vTable2;
 vSQL:='insert into '||vTable3||' (dt,ct,dtsc,ctsc,dtdep,ctdep,cant,suma) '||vSql1;
-- say(vSql);
 EXECUTE IMMEDIATE vSQL;

 vSql1:='select '||vDtCont||',ctcont,dtsc,sc,dtdep,dtdep,round(cant,4),round(suma,2) from '||vTable||
 ' where lvl>0';
 vSQL:='insert into '||vTable3||' (dt,ct,dtsc,ctsc,dtdep,ctdep,cant,suma) '||vSql1;
 EXECUTE IMMEDIATE vSQL;

 vSql1:='select ctcont,'||vDtCont||',sc,sc,dtdep,dtdep,round(cant,4),round(suma,2) from '||vTable||
 ' where lvl>0';
 vSQL:='insert into '||vTable3||' (dt,ct,dtsc,ctsc,dtdep,ctdep,cant,suma) '||vSql1;
 EXECUTE IMMEDIATE vSQL;

 vSQL:='update '||vTable3||' set ctsc1=(select distinct dtsc1 from vmdb_st201d where nrdoc='||in_doc||' and rownum=1)';
 EXECUTE IMMEDIATE vSQL;
-- проставление суммы по с/с в детэйле документа
 vSQL:='update vmdb_st201d d
        SET pret=(SELECT SUM(suma) FROM '||vTable||' a
         WHERE a.parnt=d.dtsc AND a.lvl=0)
        WHERE nrdoc='||in_doc;
 EXECUTE IMMEDIATE vSQL;

 IF (vNrset=1 OR vNrset=3) THEN
 vSql1:='select '||in_doc||',a.dt,a.ct,a.dtsc,a.ctsc,a.ctdep,a.ctdep,a.ctsc1,a.ctsc1,a.cant,'||
         ' CASE WHEN a.dt=2151 then a.cant else cast(null as number) end ctcant1,'||
         ' CASE WHEN a.suma<0.01 THEN 0.01 ELSE round(a.suma*(1+un$functs.tva(a.dtsc)),2) end'||
       ' , '||vNrCM_U||','||vNrCM_U||
          ' FROM '||vTable3||' a';
 vSQL:='insert into vmdb_cmi (nrdoc,dt,ct,dtsc,ctsc,dtdep,ctdep,dtsc1,ctsc1,cant,ctcant1,suma,dtnrcm,ctnrcm)
  '||vSql1;
 EXECUTE IMMEDIATE vSQL;
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  vSql1:='select '||in_doc||',a.dt,a.ct,a.dtsc,a.ctsc,a.ctdep,a.ctdep,a.ctsc1,a.ctsc1,a.cant,'||
          ' CASE WHEN a.dt=2151 then a.cant else cast(null as number) end ctcant1,'||
          ' CASE WHEN a.suma<0.01 THEN 0.01 ELSE round(a.suma,2) end '||
       ' , '||vNrCM_F||','||vNrCM_F||
          ' FROM '||vTable3||' a';
  vSQL:='insert into vmdb_cmi (nrdoc,dt,ct,dtsc,ctsc,dtdep,ctdep,dtsc1,ctsc1,cant,ctcant1,suma,dtnrcm,ctnrcm)
   '||vSql1;
 EXECUTE IMMEDIATE vSQL;
 END IF;

--- проводки на выпуск готовой продукции из производства в кухню
 IF (vNrset=1 OR vNrset=3) THEN
  vSql1:='select '||in_doc||','||vCtCont||','||vDtCont||
         ',a.dtsc,a.dtsc,a.dtdep,a.dtdep,a.cant,a.cant,'||
         ' CASE WHEN a.suma<0.01 THEN 0.01 ELSE round(a.suma*(1+un$functs.tva(a.dtsc)),2) end '||
   ' , '||vNrCM_U||','||vNrCM_U||
         ' FROM '||vTable||' a WHERE lvl=0';
  vSQL:='insert into vmdb_cmi (nrdoc,dt,ct,dtsc,ctsc,dtdep,ctdep,cant,ctcant1,suma,dtnrcm,ctnrcm)
   '||vSql1;
  EXECUTE IMMEDIATE vSQL;
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  vSql1:='select '||in_doc||','||vCtCont||','||vDtCont||
         ',a.dtsc,a.dtsc,a.dtdep,a.dtdep,a.cant,a.cant,'||
         ' CASE WHEN a.suma<0.01 THEN 0.01 ELSE round(a.suma,2) end '||
   ' , '||vNrCM_F||','||vNrCM_F||
         ' FROM '||vTable||' a WHERE lvl=0';
  vSQL:='insert into vmdb_cmi (nrdoc,dt,ct,dtsc,ctsc,dtdep,ctdep,cant,ctcant1,suma,dtnrcm,ctnrcm)
   '||vSql1;
  EXECUTE IMMEDIATE vSQL;
 END IF;
--- проводки на перемещение готовой продукции из кухни в место продажи BonAmie не исп-ся
 vSql1:='select '||in_doc||','||vCtCont||','||vCtCont||',a.dtsc,a.dtsc,'||vDestDep||',a.dtdep,a.cant,'||
         ' CASE WHEN a.suma<0.01 THEN 0.01 ELSE round(a.suma,2) end
         FROM '||vTable||' a WHERE lvl=0 AND '||vDestDep||'<>a.dtdep';
 vSQL:='insert into vmdb_cmi (nrdoc,dt,ct,dtsc,ctsc,dtdep,ctdep,cant,suma)
  '||vSql1;
-- EXECUTE IMMEDIATE vSQL;
------------
END GFC_Vihod_GP;
--------------------------------------------------------------------------------
PROCEDURE gfc_SpisanieTVR(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
 ,vDt     =>'nvl(m.dt,d.dt)'
 ,vCt     =>'nvl(d.ct,m.ct)'
 ,vDtDep  =>'nvl(m.dtdep, d.dtdep)'
 ,vCtDep  =>'nvl(m.ctdep, d.ctdep)'
 ,vDtSc1  =>'m.dtsc1'
 ,vCant   =>'d.cant'
 ,vSuma   =>'d.suma'
 ,vDtNrCM =>vNrCM_U
 ,vCtNrCM =>vNrCM_U
 ,vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc, vCod=>'d.rrowid', vFunct=>1, vDt=>'nvl(m.dt,d.dt)', vCt=>'nvl(d.ct,m.ct)'
   ,vDt1=>'case when nvl(d.dt,m.dt) between 7000 and 7999 then nvl(d.ct1,Un$functs.tva_cont1(d.ctsc)) else null end'
   ,vDtDep=>'m.dtdep',vCt1    =>'', vCtDep=>'m.ctdep', vSuma=>'d.suma', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F,vWhere=>'');
  ELSIF Yparams.vTip_Retail=2 THEN --summovoi
     Gfc_Util.gfc201
     (vNrdoc  =>vNrdoc
     ,vDt     =>'nvl(m.dt,d.dt)'
     ,vDt1    =>'nvl(d.ct1,Un$functs.tva_cont1(d.ctsc))'
     ,vCt     =>'nvl(d.ct,m.ct)'
     ,vCt1    =>''
     ,vCtSc   =>'(case nvl(d.ct,m.ct) when 2172 then decode(un$functs.tva(d.ctsc),0.2,'||Yparams.vScTVRB20proc||',0.08,'||Yparams.vScTVRB8proc||','||Yparams.vScTVRB0proc||')
                                       WHEN 2171 THEN DECODE(Un$functs.tva(d.ctsc),0.2,'||Yparams.vSc20proc||',0.08,'||Yparams.vSc8proc||','||Yparams.vSc0proc||')
                                          WHEN 2165 THEN DECODE(Un$functs.tva(d.ctsc),0.2,'||Yparams.vSc20proc||',0.08,'||Yparams.vSc8proc||','||Yparams.vSc0proc||')
                                       ELSE d.ctsc END)'
     ,vDtDep  =>'nvl(m.dtdep, d.dtdep)'
     ,vCtDep  =>'nvl(m.ctdep, d.ctdep)'
     ,vDtSc1  =>'m.dtsc1'
     ,vCant   =>'(case when d.ct not in (2171,2172,2165) then d.cant end)'
     ,vSuma   =>'d.suma/(1+un$functs.tva(d.ctsc))'
     ,vDtNrCM =>vNrCM_F
     ,vCtNrCM =>vNrCM_F
     ,vWhere=>''
       );
  end if;     
 END IF;
--------
END gfc_SpisanieTVR;
-------------------------------------------------------------------------------------------------------------------------------
PROCEDURE gfc_SpisanieTVR_12008(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);

BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
 ,vDt     =>'nvl(m.dt,d.dt)'
 ,vCt     =>'nvl(d.ct,m.ct)'
 ,vDtDep  =>'nvl(m.dtdep, d.dtdep)'
 ,vCtDep  =>'nvl(m.ctdep, d.ctdep)'
 ,vDtSc   =>'m.dtsc1'
 ,vDtSc1  =>'m.dtsc'
 ,vCant   =>'d.cant'
 ,vSuma   =>'d.suma'
 ,vDtNrCM =>vNrCM_U
 ,vCtNrCM =>vNrCM_U
 ,vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc, vCod=>'d.rrowid', vFunct=>1, vDt=>'nvl(m.dt,d.dt)', vCt=>'nvl(d.ct,m.ct)'
   ,vDt1=>'case when nvl(d.dt,m.dt) between 7000 and 7999 then Un$functs.tva_cont1(d.ctsc) else null end'
   ,vDtSc=>'m.dtsc1',vDtSc1=>'m.dtsc',vDtDep=>'m.dtdep', vCtDep=>'m.ctdep', vSuma=>'d.suma', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F,vWhere=>'');
  ELSIF Yparams.vTip_Retail=2 THEN --summovoi
     Gfc_Util.gfc201
     (vNrdoc  =>vNrdoc
     ,vDt     =>'nvl(m.dt,d.dt)'
     ,vDt1    =>'Un$functs.tva_cont1(d.ctsc)'
     ,vCt     =>'nvl(d.ct,m.ct)'
     ,vCtSc   =>'(case nvl(d.ct,m.ct) when 2172 then decode(un$functs.tva(d.ctsc),0.2,'||Yparams.vScTVRB20proc||',0.08,'||Yparams.vScTVRB8proc||','||Yparams.vScTVRB0proc||')
                                       WHEN 2171 THEN DECODE(Un$functs.tva(d.ctsc),0.2,'||Yparams.vSc20proc||',0.08,'||Yparams.vSc8proc||','||Yparams.vSc0proc||')
                                          WHEN 2165 THEN DECODE(Un$functs.tva(d.ctsc),0.2,'||Yparams.vSc20proc||',0.08,'||Yparams.vSc8proc||','||Yparams.vSc0proc||')
                                       ELSE d.ctsc END)'
     ,vDtDep  =>'nvl(m.dtdep, d.dtdep)'
     ,vCtDep  =>'nvl(m.ctdep, d.ctdep)'
     ,vDtSc1  =>'m.dtsc1'
     ,vCant   =>'(case when d.ct not in (2171,2172,2165) then d.cant end)'
     ,vSuma   =>'d.suma/(1+un$functs.tva(d.ctsc))'
     ,vDtNrCM =>vNrCM_F
     ,vCtNrCM =>vNrCM_F
     ,vWhere=>''
       );
  end if;     
 END IF;
--------
END gfc_SpisanieTVR_12008;
--------------------------------------------------------------------------------
PROCEDURE Prihod_Transport(pNrdoc NUMBER
                          ,pDt NUMBER DEFAULT 7123
                          ,pDtsc NUMBER DEFAULT NULL
        ,pDtSc1 NUMBER DEFAULT NULL
        , pTva number default 5342
        ) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(pNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(pNrdoc,1);
 vCodFc NUMBER;
BEGIN

 SELECT id_tmdb_cm.NEXTVAL
   INTO vCodFc
   FROM dual;

 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=pNrdoc;

-- msg(vNrset);
 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc
 (tSource=>'(select * from vmdb_st201m where nrdoc='||pNrdoc||')'
 ,vNrdoc=>pNrdoc
 ,vNrdoc_field=>pNrdoc
 ,vCod=>''
 ,vDt=>pDt
 ,vCt=>'ct'
 ,vDt1=>''
 ,vCt1=>''
 ,vDtSc=>pDtSc
 ,vCtSc=>''
 ,vDtDep=>'dtdep' --:ini_dep7133
 ,vCtDep=>'ctdep'
 ,vDtSc1=>pDtSc1
 ,vCtSc1=>''
 ,vValutaDt=>''
 ,vValutaCt=>''
 ,vSumaValDt=>''
 ,vSumaValCt=>''
 ,vCant=>''
 ,vDtCant1=>''
 ,vCtCant1=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
 ,vSuma=>'sb+sc'
 ,vFunct=>''
 ,vWhere_before=>' and nvl(sb,0)<>0'
 );
 END IF;
 IF (vNrset=2 OR vNrset=3)
  THEN
--  RAISE_APPLICATION_ERROR (-20000,'Hier');
  Gfc_Util.gfc
  (tSource=>'(select * from vmdb_st201m where nrdoc='||pNrdoc||')'
  ,vNrdoc=>pNrdoc
  ,vNrdoc_field=>pNrdoc
  ,vCod=>vCodFc
  ,vDt=>pDt
  ,vCt=>'ct'
  ,vDt1=>''
  ,vCt1=>''
  ,vDtSc=>pDtSc
  ,vCtSc=>''
  ,vDtDep=>'dtdep' --:ini_dep7133
  ,vCtDep=>'ctdep'
  ,vDtSc1=>pDtSc1
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant=>''
  ,vDtCant1=>''
  ,vCtCant1=>''
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vSuma=>'sb'
  ,vFunct=>''
  ,vWhere_before=>' and nvl(sb,0)<>0'
  );

  Gfc_Util.gfc
  (tSource=>'(select * from vmdb_st201m where nrdoc='||pNrdoc||')'
  ,vNrdoc=>pNrdoc
  ,vNrdoc_field=>pNrdoc
  ,vDt=>'5342'
  ,vDt1=>'Un$functs.TVA_CONT1('||pDtSc1||',ctdep,'||pNrdoc||')'
  ,vCt=>'ct'
  ,vCt1=>''
  ,vDtSc=>''
  ,vCtSc=>''
  ,vDtDep=>''
  ,vCtDep=>'ctdep'
  ,vDtSc1=>''
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant=>''
  ,vDtCant1=>''
  ,vCtCant1=>''
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vSuma=>'sc'
  ,vCodFCdeBaza=>vCodFC
  ,vWhere_before=>' and nvl(sc,0)<>0'
  ,vTVACont1Recognition=>FALSE
  );
 END IF;
END Prihod_Transport;
--------------------------------------------------------------------------------
--- Приход товара - основные проводки
  PROCEDURE Prihod_GFC(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData   DATE;
 vsql    LONG;
 vDtDep  NUMBER;
 vCtDep  NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;
 
 v_dt1 number:=2171;
 v_dt2 number:=2172;
 
 v_funct number:=99;
BEGIN
 SELECT datamanual, Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;
  
  begin
   select 2178, 2179
   into v_dt1, v_dt2
   from tmdb_docs_add a
   where cod = vNrdoc
   and exists
     (
     select null
     from vmdb_docs d
     where d.cod = a.parent_nrdoc
     and d.sysfid = 1282
     );
     
   v_funct := 777;
  exception when no_data_found then
    v_dt1 := 2171;
    v_dt2 := 2172;
    
    v_funct := 99;
  end;

 IF (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201
  (vNrdoc, v_funct
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>'nvl(m.Ct,d.Ct)'
  ,vCt1    =>'decode('||vNrset||',1,1,null)'
  ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtStrSc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vCtCant1=>''
  ,vWhere=>''
--  , vDebug=>true
  );
 END IF;

    IF (vNrset=2 OR vNrset=3)  THEN
      IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
    -- check_prices;
     -- Osnovnie provodki
      Gfc_Util.gfc201(vNrdoc, v_funct,vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)' , vCtDep=>'nvl(d.ctdep,m.ctdep)',vSuma=>'d.sumagaap',
                      vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F,vWhere=>'');
     -- NDS
       Gfc_Util.gfc201(vNrdoc, v_funct, vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
        ,vDtDep=>'', vCtDep=>'nvl(d.ctdep,m.ctdep)', vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
        ,vTVACont1Recognition=>FALSE,vWhere=>'' );

     ELSIF Yparams.vTip_Retail=2 THEN --summovoi

      SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
       INTO vCnt FROM dual;
      IF vCnt <> 0 THEN
       RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
          'Укажите продажные цены на товар с кодом - '||vCnt);
      ELSE
       SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

       -- Sebestoimosti -----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(sumagaap) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=v_dt1
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (c.rrowid, vNrdoc, v_dt1, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;
       -- NDS ---------------
      IF vTipTVA=-1 THEN
        SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
        SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm, funct)
        VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F, v_funct);
      ELSE
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
           , SUM(sumavalct) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=v_dt1
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;
      END IF;
      --- NDS v tovare ----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_6) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=v_dt1
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (vNrdoc, v_dt1, c.sc, vDtdep, 8251, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;
       -- Natsenka ------------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_5)-SUM(clcsumax_6)-SUM(sumagaap) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=v_dt1
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (vNrdoc, v_dt1, c.sc, vDtdep, 8211, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;

        -- Sebestoimosti 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=v_dt2) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (c.rrowid, vNrdoc, c.dt, DECODE(Un$functs.tva(c.sc),0.2,vScTVRB20proc,0.08,vScTVRB8proc,vScTVRB0proc),
               vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;

        -- Sebestoimosti ne 2171 i ne 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt NOT IN (v_dt1,v_dt2)) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
       END LOOP;

       --- NDS ne 2171----------
       IF vTipTVA<>-1 THEN
       FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt<>v_dt1) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F, v_funct);
        END LOOP;
       END IF;
      END IF;
     END IF;
    END IF;
    ---------------
END Prihod_GFC;
--------------------------------------------------------------------------------
--------------------------------------------------------------------------------
--- Приход товара - основные проводки
  PROCEDURE Prihod_GFC_2178(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData   DATE;
 vsql    LONG;
 vDtDep  NUMBER;
 vCtDep  NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;
BEGIN
 SELECT datamanual, Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;
  
 IF (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>'nvl(m.Ct,d.Ct)'
  ,vCt1    =>'decode('||vNrset||',1,1,null)'
  ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtStrSc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vCtCant1=>''
  ,vWhere=>''
--  , vDebug=>true
  );
 END IF;

    IF (vNrset=2 OR vNrset=3)  THEN
      IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
    -- check_prices;
     -- Osnovnie provodki
      Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',
                      vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F,vWhere=>'');
     -- NDS
       Gfc_Util.gfc201(vNrdoc, vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
        ,vDtDep=>'', vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
        ,vTVACont1Recognition=>FALSE,vWhere=>'' );

     ELSIF Yparams.vTip_Retail=2 THEN --summovoi

      SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
       INTO vCnt FROM dual;
      IF vCnt <> 0 THEN
       RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
          'Укажите продажные цены на товар с кодом - '||vCnt);
      ELSE
       SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

       -- Sebestoimosti -----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(sumagaap) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2178
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, 2178, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
       -- NDS ---------------
      IF vTipTVA=-1 THEN
        SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
        SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm)
        VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F);
      ELSE
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
           , SUM(sumavalct) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2178
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
      END IF;
      --- NDS v tovare ----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_6) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2178
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, 2178, c.sc, vDtdep, 8251, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
       -- Natsenka ------------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_5)-SUM(clcsumax_6)-SUM(sumagaap) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2178
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, 2178, c.sc, vDtdep, 8211, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

        -- Sebestoimosti 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2179) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, c.dt, DECODE(Un$functs.tva(c.sc),0.2,vScTVRB20proc,0.08,vScTVRB8proc,vScTVRB0proc),
               vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

        -- Sebestoimosti ne 2171 i ne 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt NOT IN (2178,2179)) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

       --- NDS ne 2171----------
       IF vTipTVA<>-1 THEN
       FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt<>2172) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
        END LOOP;
       END IF;
      END IF;
     END IF;
    END IF;
    ---------------
END Prihod_GFC_2178;
--------------------------------------------------------------------------------
-- Для 1222 (НН по кассе) в p_shop_id передаётся ctdep
-- Для 1214 (Возврат товаров от покупателей) в p_shop_id передаётся dtdep
-- (В шапках документов для выбора магазина исп-ся разные поля)
PROCEDURE Casa_NN_Fill_TVR(vNrdoc NUMBER, p_shop_id NUMBER,p_secondary NUMBER:=0) IS
--  vNrset NUMBER;
--  vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
--  vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
  t      NUMBER;
  vsql    LONG; -- конеченый select из всех нижних
  vsql3   LONG; -- выборка из кассового сервера
  vData  DATE;
  vCeki  LONG; -- список чеков по которым надо печатать накладную
  vFiltr LONG;
  vDt    NUMBER;
  vDummy1 NUMBER;
  vDummy2 NUMBER;
  vDummy3 NUMBER;
  v_filtr_cas long;
--  vSC_Flux NUMBER:=0;
--  vCont_casa NUMBER:=2414;
--  vGFC_cassa BOOLEAN:=FALSE; /* Если TRUE, то после заполнения формирует проводки */
--  vShema1 LONG:='lin_casa';
  vDBLink LONG:='l_casa1.world';  -- линк для связи с кассами
--  vDBLink1 LONG:='l_casa1.world';  -- линк для связи с резервным сервером
  vShema LONG:='lin_casa';
--  vMOL NUMBER;
--  vInc_9221 NUMBER:=0;
--  v_shop_id NUMBER;

BEGIN

  IF p_shop_id IS NULL
  THEN
      msg('Не выбран магазин!');
  END IF;

  vDbLink := Ybmb_Pk_Dif_Cassa.get_db_link_by_nr_group(p_shop_id,p_secondary);
  BEGIN
    EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM dual@'||vDBLink INTO t ;
  EXCEPTION WHEN OTHERS THEN
    RAISE_APPLICATION_ERROR (-20001,'Нет связи с кассой!!!');
  END;
  vShema := Ybmb_Pk_Dif_Cassa.get_shema_by_nr_group(p_shop_id,0,p_secondary);

  SELECT datamanual INTO vData
  FROM VMDB_DOCS
  WHERE cod=vNrdoc;

  SELECT TXTCOMMENT INTO vCeki
  FROM VMDB_DOCS_ADD
  WHERE cod =vNrdoc;

  SELECT dt INTO vDt
  FROM VMDB_ST201M
  WHERE nrdoc =vNrdoc;

  vCeki:=LTRIM(RTRIM(vCeki));
  IF vCeki IS NOT NULL
  THEN
    vDummy1:=INSTR(vCeki||',',',');
    vDummy2:=INSTR(vCeki||',',' ');
    vDummy3:=LENGTH(vCeki||',');
--   warn(vDummy1||' '||vDummy2||' '||vDummy3);
    IF    (vDummy1<>0 AND vDummy1<>vDummy3 AND vDummy2<>0) OR vCeki<>UPPER(vCeki)
       OR (vDummy2<>0 AND vDummy1=vDummy3)
       OR (vDummy1<>0 AND vDummy1=vDummy3 AND vDummy2=0 AND INSTR(vCeki,'.')<>0)
    THEN
       RAISE_APPLICATION_ERROR(-20000,'Проверьте правильность ввода номеров чеков!!!Не должно быть пробелов, точек и других нецифровых символов, кроме запятой, между номерами чеков!!!');
    END IF;
    vFiltr:=' and m.cod in ('||vCeki||') ';
  ELSIF vCeki IS NULL
  THEN
    RAISE_APPLICATION_ERROR(-20000,'Не указаны номера чеков!!!');
  END IF;

  --DELETE FROM VMDB_ST201D WHERE nrdoc=vNrdoc;
   vsql3:='
    select sc, cant, suma, sumatva, codtva, casa, casir'||CHR(10)||
    ',/* case when codtva = ''B'' then*/ round((sumatva*100)/(nvl(suma,0)-nvl(sumatva,0))) ct1 '||CHR(10)||
    'from'||CHR(10)||
    '('||CHR(10)||
      'SELECT d.bliuda sc '||CHR(10)||
      ',DECODE(NVL(state,0),10,-cant, cant) cant '||CHR(10)||
      ',DECODE(NVL(state,0),10,-clcsumat , clcsumat ) suma '||CHR(10)||
      ',decode(nvl(state,0),10,-sumtva, d.sumtva ) sumatva '||CHR(10)||
      ',codtva '||CHR(10)||
      ' ,(SELECT cod FROM TMS_ORG WHERE OI_TIPSECT_S_79=aa.id_casa) casa'||CHR(10)||
      ',(SELECT dep FROM '||vShema||'.tms_casir@'||vDBLink||' c WHERE c.cod=m.oficiant '||v_filtr_cas||') casir'||CHR(10)||
      'FROM '||vShema||'.vmdb_comenzd@'||vDBLink||' d, '||CHR(10)||
      vShema||'.TMDB_COMENZ@'||vDBLink||' m, '||CHR(10)||
      vShema||'.TMDB_sold@'||vDBLink||' aa'||CHR(10)||
      'WHERE m.cod=d.nr_comand AND aa.nrdoc=m.nrdoc'||CHR(10)||
      'AND TRUNC(m.DATA) between add_months('''||vData||''',-3) and '''||vData||''''||CHR(10)||
      'AND m.state NOT IN (0,1,5)'||vFiltr||CHR(10)||
    ')';

 vSql:='INSERT INTO vmdb_st201d(nrdoc,dt,dtsc,CANT,suma,sumavaldt,sumavalct,sumagaap,dtdep,dtsc1 , ct1 ) ';
 vSql:=vSql||'select :vNrdoc nrdoc, :vDt dt,a.sc,sum(a.cant),sum(suma),sum(sumatva),sum(sumatva),sum(suma)-sum(sumatva),casa,casir, ct1 '||
             'from('||vsql3||') a '||
             ' group by a.sc,a.casa,a.casir, ct1';
-- msg(vSql);
  say(vsql3);
  EXECUTE IMMEDIATE vSql USING vNrDoc, vDt;

  /* vsql3:='SELECT d.bliuda sc '||CHR(10)||
    ',DECODE(NVL(state,0),10,-cant, cant) cant '||CHR(10)||
    ',DECODE(NVL(state,0),10,-clcsumat , clcsumat ) suma '||CHR(10)||
    ' ,(SELECT cod FROM TMS_ORG WHERE OI_TIPSECT_S_79=aa.id_casa) casa'||CHR(10)||
    ',(SELECT dep FROM '||vShema||'.tms_casir@'||vDBLink||' c WHERE c.cod=m.oficiant) casir'||CHR(10)||
    'FROM '||vShema||'.VMDB_COMENZD_DELTA_TVA@'||vDBLink||' d, '||CHR(10)||
    vShema||'.TMDB_COMENZ@'||vDBLink||' m, '||CHR(10)||
    vShema||'.TMDB_sold@'||vDBLink||' aa'||CHR(10)||
    'WHERE m.cod=d.nr_comand AND aa.nrdoc=m.nrdoc'||CHR(10)||
    'AND TRUNC(m.DATA) between add_months('''||vData||''',-3) and '''||vData||''''||CHR(10)||    
    'AND m.state NOT IN (0,1,5)'||vFiltr;

 vSql:='INSERT INTO vmdb_st201d(nrdoc,dt,dtsc,CANT,suma,dtdep,dtsc1) ';
 vSql:=vSql||'select :vNrdoc nrdoc, :vDt dt,a.sc,sum(a.cant),sum(suma),casa,casir '||
             'from('||vsql3||') a '||
             ' group by a.sc,a.casa,a.casir'; 
-- msg(vSql);
--  say(vsql);
  EXECUTE IMMEDIATE vSql USING vNrDoc, vDt;*/
--------
END Casa_NN_Fill_TVR;
------------------------------------------------------------------------------------------------------------------
PROCEDURE Cassa_NN_calc_VAT(p_nrdoc NUMBER) IS
v_sysfid INT;
BEGIN
  SELECT sysfid INTO v_sysfid FROM TMDB_DOCS WHERE cod = p_nrdoc;
  IF v_sysfid = 1222 THEN
    UPDATE ybon_vmdb_st201d_tvr
       SET sumavalct=NVL(suma,0)*Un$functs.tva(dtsc,NULL,p_nrdoc)/(1+Un$functs.tva(dtsc,NULL,p_nrdoc))
     WHERE nrdoc = p_nrdoc;
    UPDATE ybon_vmdb_st201d_tvr
       SET sumagaap=NVL(suma,0)-NVL(sumavalct,0)
     WHERE nrdoc = p_nrdoc;
  ELSE     -- пока 1228
    UPDATE vmdb_st201d
     SET sumavalct = NVL(suma,0)*Un$functs.tva(ctsc,NULL,p_nrdoc)/(1+Un$functs.tva(ctsc,NULL,p_nrdoc))
    WHERE nrdoc=p_nrdoc;
    --
    UPDATE vmdb_st201d
      SET sumagaap = NVL(suma,0)-NVL(sumavalct,0)
    WHERE nrdoc=p_nrdoc;
  END IF;
END;
------------------------------------------------------------------------------------------------------------------
PROCEDURE Casa_NN_gfc(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE;
 vDt    NUMBER;
 vCt    NUMBER;
 vDtSc NUMBER;
 vCtSc NUMBER;
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDtScIf2414  NUMBER;
 vCodFC    NUMBER;
 vCasaCont NUMBER:=2414; -- счет кассы магазина

  vSC_Flux NUMBER:=1276;
  vSysfid_casa NUMBER:=1211;
  vSysfid_casaF NUMBER:=48309;
  vShema1 LONG:='c2bam';
--  vDBLink LONG:='ora10g1.world';  -- линк для связи с кассами
  vDBLink LONG:='boncassa.world';  -- линк для связи с кассами
  vDBLink1 LONG:='NB.WORLD';  -- линк для связи с ноутбуком
  vShema LONG:='c2bam';
  vMOL NUMBER;
  vInc_9221 NUMBER:=0;
  vTipTVA INT;
 tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct
   INTO vDt,vCt
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /*sql1:='create global temporary table '||tmpTable||' on commit preserve rows
             AS SELECT dtsc dtdep,ctsc ctsc,ctdep ctdep,tva,0 AS codfc
            ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
   FROM
   (SELECT m.dtsc
   ,d.ctsc
   ,m.ctdep
   ,(SELECT Un$functs.tva(d.ctsc)*100 FROM dual) tva
   ,d.sumagaap sumaftva
   ,d.sumavalct sumatva
   FROM VMDB_ST201M M, VMDB_ST201D D
   WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
   )GROUP BY dtsc,ctsc,tva,ctdep';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
  EXECUTE IMMEDIATE sql1;*/

 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>'decode(m.dt,'||vCasaCont||','||vSc_Flux||',null)'
 ,vCtsc=>'d.dtsc'
 ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
 ,vCtDep=>'m.CtDep'
 ,vCant=>'d.cant'
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 IF vDt<>vCasaCont THEN
  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vDt=>vCasaCont
  ,vCt=>'M.Dt'
  ,vDtsc=>vSc_Flux
  ,vCtsc=>''
  ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
  ,vCtDep=>'m.DtDep'
  ,vCant=>'d.cant'
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
 -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
  );
  END IF;
---  сторнировка дохода
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vDt=>vCasaCont
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>vSc_Flux
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>'-d.cant'
   ,vSuma=>'-d.suma'
   ,vDtNrCm=>vNrCM_U
   ,vCtNrCm=>vNrCM_U
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN
  IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
   ---venit
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vCod=>'d.rrowid'
   ,vDt=>'m.Dt'
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>'decode(m.dt,'||vCasaCont||','||vSc_Flux||',null)'
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>'d.cant'
   ,vSuma=>'d.sumagaap'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
   --NDS
  Gfc_Util.gfc201
    (vNrdoc=>vNrdoc
 ,vCodfcdebaza=>'d.rrowid'
    ,vDt=>'m.Dt'
    ,vCt=>5342
 ,vCt1=>'nvl( d.ct1 , Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||') )'
    ,vDtsc=>''
    ,vCtsc=>''
    ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
    ,vCtDep=>''
    ,vCant=>''
    ,vSuma=>'d.sumavalct'
    ,vDtNrCm=>vNrCM_F
    ,vCtNrCm=>vNrCM_F
   -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
    );
  -- 2414 -> 2211 ---------------
  IF vDt<>vCasaCont THEN
  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vDt=>vCasaCont
  ,vCt=>'M.Dt'
  ,vDtsc=>vSc_Flux
  ,vCtsc=>''
  ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
  ,vCtDep=>'m.DtDep'
  ,vCant=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
 -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
  );

  ---  сторнировка сумм по кассам
  ---  сторнировка дохода
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vCod=>'-d.rrowid'
   ,vDt=>vCasaCont
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>vSc_Flux
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>'-d.cant'
   ,vSuma=>'-d.sumagaap'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
   ---  сторнировка сумм по кассам
   ---  сторнировка НДС
   Gfc_Util.gfc201
    (vNrdoc=>vNrdoc
 ,vCodfcdebaza=>'-d.rrowid'
    ,vDt=>vCasaCont
    ,vCt=>5342
 ,vCt1=>'nvl(d.ct1 , Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||'))'
    ,vDtsc=>vSc_Flux
    ,vCtsc=>''
    ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
    ,vCtDep=>''
    ,vCant=>''
    ,vSuma=>'-d.sumavalct'
    ,vDtNrCm=>vNrCM_F
    ,vCtNrCm=>vNrCM_F
   -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
    );

  END IF;

  ELSIF Yparams.vTip_Retail=2 THEN --summovoi
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(dt,0) INTO vDt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(dtsc,0) INTO vDtSc FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   IF vDt=vCasaCont THEN vDtScIf2414:=vSc_Flux; ELSE vDtScIf2414:=NULL; END IF;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   --  dohod  -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(ctcant1) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtScIf2414, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
  IF vTipTVA=-1 THEN
   INSERT INTO VMDB_CMI (nrdoc, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
   VALUES (vNrdoc, 5342, 92, vCt, vCtdep, 0, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
       , SUM(SUMAVALCT) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtsc, dtdep, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, vDt, vDtScIf2414, vDtDep, 5342, c.ct1, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
  END IF;
 -- 2414 -> 2211 ---------------
   IF vDt<>vCasaCont THEN
    FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
        , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
        , SUM(suma) suma
        , NVL(dtdep,vDtsc) dtdep
        , NVL(dtsc1,0) dtsc1
               FROM YBON_VMDB_ST201D_TVR
               WHERE nrdoc=vNrdoc
               GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
               ) LOOP
     INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctdep, suma, dtnrcm, ctnrcm)
     VALUES (vNrdoc, vCasaCont, vSc_Flux, c.dtdep, c.dtsc1, vDt, vDtdep, c.suma, vNrCM_F, vNrCM_F);
    END LOOP;
   END IF;
---  сторнировка сумм по кассам
---  сторнировка дохода
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc)  sc
       , SUM((NVL(SUMA,0)-NVL(suma,0)*Un$functs.tva(dtsc)/(1+Un$functs.tva(dtsc)))) suma
       , MIN(rrowid) rrowid
       , NVL(dtdep,vDtsc) dtdep
       , NVL(dtsc1,0) dtsc1
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (-c.rrowid, vNrdoc, vCasaCont, vSC_Flux, c.dtdep, c.dtsc1, 6112, c.sc, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
---  сторнировка сумм по кассам
---  сторнировка НДС
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(NVL(suma,0)*Un$functs.tva(dtsc)/(1+Un$functs.tva(dtsc))) suma
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
       , MIN(rrowid) rrowid
       , NVL(dtdep,vDtsc) dtdep
       , NVL(dtsc1,0) dtsc1
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtsc, dtdep, dtsc1, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, -c.rrowid, vCasaCont, vSC_Flux, c.dtdep, c.dtsc1, 5342, c.ct1, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
 END IF;

 END IF;
  --------
END Casa_NN_gfc;
------------------------------------------------------------------------------------------------------------------
PROCEDURE Casa_NN_gfc_group_tva(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE;
 vDt    NUMBER;
 vCt    NUMBER;
 vDtSc NUMBER;
 vCtSc NUMBER;
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDtScIf2414  NUMBER;
 vCodFC    NUMBER;
 vCasaCont NUMBER:=2414; -- счет кассы магазина

  vSC_Flux NUMBER:=1276;
  vSysfid_casa NUMBER:=1211;
  vSysfid_casaF NUMBER:=48309;
  vShema1 LONG:='c2bam';
--  vDBLink LONG:='ora10g1.world';  -- линк для связи с кассами
  vDBLink LONG:='boncassa.world';  -- линк для связи с кассами
  vDBLink1 LONG:='NB.WORLD';  -- линк для связи с ноутбуком
  vShema LONG:='c2bam';
  vMOL NUMBER;
  vInc_9221 NUMBER:=0;
  vTipTVA INT;
 tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct
   INTO vDt,vCt
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /*sql1:='create global temporary table '||tmpTable||' on commit preserve rows
             AS SELECT dtsc dtdep,ctsc ctsc,ctdep ctdep,tva,0 AS codfc
            ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
   FROM
   (SELECT m.dtsc
   ,d.ctsc
   ,m.ctdep
   ,(SELECT Un$functs.tva(d.ctsc)*100 FROM dual) tva
   ,d.sumagaap sumaftva
   ,d.sumavalct sumatva
   FROM VMDB_ST201M M, VMDB_ST201D D
   WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
   )GROUP BY dtsc,ctsc,tva,ctdep';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
  EXECUTE IMMEDIATE sql1;*/

 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>'decode(m.dt,'||vCasaCont||','||vSc_Flux||',null)'
 ,vCtsc=>'d.dtsc'
 ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
 ,vCtDep=>'m.CtDep'
 ,vCant=>''
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 IF vDt<>vCasaCont THEN
  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vDt=>vCasaCont
  ,vCt=>'M.Dt'
  ,vDtsc=>vSc_Flux
  ,vCtsc=>''
  ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
  ,vCtDep=>'m.DtDep'
  ,vCant=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
 -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
  );
  END IF;
---  сторнировка дохода
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vDt=>vCasaCont
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>vSc_Flux
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>'-d.cant'
   ,vSuma=>'-d.suma'
   ,vDtNrCm=>vNrCM_U
   ,vCtNrCm=>vNrCM_U
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN
  IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
   ---venit
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vCod=>'d.rrowid'
   ,vDt=>'m.Dt'
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>'decode(m.dt,'||vCasaCont||','||vSc_Flux||',null)'
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>''
   ,vSuma=>'d.sumagaap'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
      --  sinecost -----------------------
     Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
--   ,vCod=>'d.rrowid'
   ,vDt=>'7112'
   ,vCt=>'d.ct'
   ,vDtsc=>'d.dtsc'
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'m.CtDep'
   ,vCtDep=>'m.CtDep'
   ,vCant=>''
   ,vSuma=>'d.ctcant1'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );   
      --NDS
     Gfc_Util.gfc201
    (vNrdoc=>vNrdoc
    ,vCodfcdebaza=>'d.rrowid'
    ,vDt=>'m.Dt'
    ,vCt=>5342
    ,vCt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    ,vDtsc=>''
    ,vCtsc=>''
    ,vDtDep=>'decode(m.dt,'||vCasaCont||',m.DtSc,m.DtDep)'
    ,vCtDep=>''
    ,vCant=>''
    ,vSuma=>'d.sumavalct'
    ,vDtNrCm=>vNrCM_F
    ,vCtNrCm=>vNrCM_F
   -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
    );
  -- 2414 -> 2211 ---------------
  IF vDt<>vCasaCont THEN
  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vDt=>vCasaCont
  ,vCt=>'M.Dt'
  ,vDtsc=>vSc_Flux
  ,vCtsc=>''
  ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
  ,vCtDep=>'m.DtDep'
  ,vCant=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
 -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
  );

  ---  сторнировка сумм по кассам
  ---  сторнировка дохода
   Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
   ,vCod=>'-d.rrowid'
   ,vDt=>vCasaCont
   ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
   ,vDtsc=>vSc_Flux
   ,vCtsc=>'d.dtsc'
   ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
   ,vCtDep=>'m.CtDep'
   ,vCant=>'-d.cant'
   ,vSuma=>'-d.sumagaap'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
  -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
   );
   ---  сторнировка сумм по кассам
   ---  сторнировка НДС
   Gfc_Util.gfc201
    (vNrdoc=>vNrdoc
    ,vCodfcdebaza=>'-d.rrowid'
    ,vDt=>vCasaCont
    ,vCt=>5342
    ,vCt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    ,vDtsc=>vSc_Flux
    ,vCtsc=>''
    ,vDtDep=>'nvl(d.dtdep,m.DtSc)'
    ,vCtDep=>''
    ,vCant=>''
    ,vSuma=>'-d.sumavalct'
    ,vDtNrCm=>vNrCM_F
    ,vCtNrCm=>vNrCM_F
   -- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
    );
    
  END IF;
   
  ELSIF Yparams.vTip_Retail=2 THEN --summovoi
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(dt,0) INTO vDt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(dtsc,0) INTO vDtSc FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   IF vDt=vCasaCont THEN vDtScIf2414:=vSc_Flux; ELSE vDtScIf2414:=NULL; END IF;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   --  dohod  -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtScIf2414, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
  IF vTipTVA=-1 THEN
   INSERT INTO VMDB_CMI (nrdoc, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
   VALUES (vNrdoc, 5342, 92, vCt, vCtdep, 0, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
       , SUM(SUMAVALCT) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtsc, dtdep, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, vDt, vDtScIf2414, vDtDep, 5342, c.ct1, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
  END IF;
 -- 2414 -> 2211 ---------------
   IF vDt<>vCasaCont THEN
    FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
        , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
        , SUM(suma) suma
        , NVL(dtdep,vDtsc) dtdep
        , NVL(dtsc1,0) dtsc1
               FROM YBON_VMDB_ST201D_TVR
               WHERE nrdoc=vNrdoc
               GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
               ) LOOP
     INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctdep, suma, dtnrcm, ctnrcm)
     VALUES (vNrdoc, vCasaCont, vSc_Flux, c.dtdep, c.dtsc1, vDt, vDtdep, c.suma, vNrCM_F, vNrCM_F);
    END LOOP;
   END IF;
---  сторнировка сумм по кассам
---  сторнировка дохода
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc)  sc  
       , SUM((NVL(SUMA,0)-NVL(suma,0)*Un$functs.tva(dtsc)/(1+Un$functs.tva(dtsc)))) suma
       , MIN(rrowid) rrowid
       , NVL(dtdep,vDtsc) dtdep
       , NVL(dtsc1,0) dtsc1
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (-c.rrowid, vNrdoc, vCasaCont, vSC_Flux, c.dtdep, c.dtsc1, 6112, c.sc, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
---  сторнировка сумм по кассам
---  сторнировка НДС
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(NVL(suma,0)*Un$functs.tva(dtsc)/(1+Un$functs.tva(dtsc))) suma
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) ct1
       , MIN(rrowid) rrowid
       , NVL(dtdep,vDtsc) dtdep
       , NVL(dtsc1,0) dtsc1
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CLCSTRINGX_2, NVL(dtdep,vDtsc), dtsc1
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtsc, dtdep, dtsc1, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, -c.rrowid, vCasaCont, vSC_Flux, c.dtdep, c.dtsc1, 5342, c.ct1, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
 END IF;
 
 END IF;
  --------
END Casa_NN_gfc_group_tva;
------------------------------------------------------------------------------------------------------------------
PROCEDURE perecislenie_NN_GFC(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE:=abm_util.data_by_nrdoc(vNrdoc);
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCnt   NUMBER:=0;
 vTipTVA INT;
 vTip_Opl int;
 vSuma_Total number;

  --tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
-- RO: TVA-ul de pe randuri este STOCAT (sumavalct/sumagaap), scris la crearea
--     documentului. Fara recalculare, schimbarea regimului de TVA (pe document
--     sau pe client) urmata de regenerarea formulelor pastra TVA-ul VECHI —
--     vezi documentul 369. Acum regenerarea recalculeaza intii sumele dupa
--     atributele CURENTE, apoi posteaza.
-- EN: row VAT is STORED at document creation; regenerating the postings used to
--     re-post the STALE amounts after a VAT-regime change. Recalculate first.
Cassa_NN_calc_VAT(vNrdoc);
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct,sa
   INTO vDt,vCt,vTip_Opl
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /* Arhaism - pri summovom u4ete
  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc, dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc dtdep
,d.dtsc
,(SELECT Un$functs.tva(d.dtsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,dtdep,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
*/

  select nvl((select ctsc from vmdb_st201d where nrdoc=vNrdoc and pret is null and rownum=1),0)
    into vCnt from dual;
  if vCnt <> 0 then
   msg('Проводки возможны только при наличии продажных цен!'||chr(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  end if;      
     
  select count(*) into vCnt from vmdb_st201d where nrdoc=vNrdoc and nvl(sumagaap,0)=0;  
  if vCnt<>0 then 
   msg('Пересчитайте документ: имеются нулевые суммы без НДС!!!');
  end if; 
      
 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>''
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'un$functs.GETCONT_VINZ7(M.Ct)'
 ,vCt=>'d.Ct'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vDtSc1=>''
 ,vCant=>'d.cant'
 ,vSuma=>'d.i_pretv*d.cant'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN
 IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
 --check_prices;
 -- Osnovnie provodki
  Gfc_Util.gfc201
  (vNrdoc
  ,vDt=>'nvl(m.dt,d.dt)'
  ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
  ,vCt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
  ,vDtDep=>'nvl(m.dtdep,d.dtdep)'
  ,vSuma=>'d.sumagaap'
  ,vCod=>'d.rrowid'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vWhere=>'');
 -- NDS
   Gfc_Util.gfc201
   (vNrdoc
   , vCt=>'5342'
   , vCt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
   ,vDtDep=>'nvl(m.dtdep,d.dtdep)'
   , vSuma=>'d.sumavalct'
   , vCant=>''
   , vCodFCdeBaza=>'d.rrowid'
   , vDtNrCM =>vNrCM_F
   , vCtNrCM =>vNrCM_F
   ,vTVACont1Recognition=>FALSE
   , vWhere=>''/*,vdebug=>true*/ );
 
 -- Автозакрытие сумм за наличный расчет на 2416
   if nvl(vTip_Opl,0)=1 and vData>='01.10.2012' then
    select sum(suma) into vSuma_Total from vmdb_st201d where nrdoc=vNrdoc;
    if nvl(vSuma_Total,0)<>0 then
     insert into vmdb_cmi (nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
     select nrdoc, 2417 dt, 1276, /*ctdep*/135435, dt, dtdep, vSuma_Total, vNrCM_F, vNrCM_F
     from vmdb_st201m 
     where nrdoc=vNrdoc;
    end if;
   end if;
   
 --sinecost
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc,
                    vDt=>'un$functs.GETCONT_VINZ7(M.Ct)',
                    vDt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')',
                    vCt=>'d.Ct', 
                    vDtsc=>'d.ctsc',
                    vCtsc=>'d.ctsc',
                    vDtDep=>'nvl(d.ctdep,m.CtDep)', 
                    vCtDep=>'nvl(d.ctdep,m.CtDep)', 
                    vDtSc1=>'', 
                    vCant=>'d.cant', 
                    vSuma=>'d.i_pretv*d.cant', 
                    vWhere=>'', 
                    vDtNrCm=>vNrCM_F, 
                    vCtNrCm=>vNrCM_F);

 ELSIF Yparams.vTip_Retail=2 THEN --summovoi

   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   -- Dohod 2171-----------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Dohod 2172-----------
   FOR c IN (SELECT DECODE(CODTVA,0,vScTVRB0proc,8,vScTVRB8proc,20,vScTVRB20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct=2172
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Dohod ne 2171 i ne 2172-----------
   FOR c IN (SELECT ctsc sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct NOT IN (2171,2172,2165)
              GROUP BY ctsc
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
  IF vTipTVA=-1 THEN
   INSERT INTO VMDB_CMI (nrdoc, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
   VALUES (vNrdoc, 5342, 92, vCt, vCtdep, 0, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CODTVA,0,91,8,8,20,20,'',92) ct1
       , SUM(sumavalct) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtdep, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, vDt, vDtDep, 5342, c.ct1, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
  END IF;
  --- NDS v tovare ----------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , ct
       , SUM(sumavalct) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA,ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 8251, c.sc, vCtdep, c.ct/*2171*/, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti 2171 (v tom 4isle natsenka) ------------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       ,DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1
       , ct
       , SUM(sumagaap) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA, ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dt1, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1 ,c.sc, vCtdep, c.ct/*2171*/, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti 2172 ------------
   FOR c IN (SELECT DECODE(CODTVA,0,vScTVRB0proc,8,vScTVRB8proc,20,vScTVRB20proc) sc
        ,DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1
       , SUM(CANT*I_PRETV) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct=2172
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt,dt1, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1, c.sc, vCtdep, 2172, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti ne 2171 i ne 2172 ------------
   FOR c IN (SELECT ctsc sc,
        DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1,
        ct, SUM(cant) cant
       , SUM(CANT*I_PRETV) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct NOT IN (2171,2172,2165)
              GROUP BY ctsc,ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dt1, dtsc, dtdep, ct, ctsc, ctdep, cant, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1, c.sc, vCtdep, c.ct, c.sc, vCtdep, c.cant, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;   
  END IF;
 END IF;
  --------
END perecislenie_NN_GFC;
------------------------------------------------------------------------------------------------------------------
PROCEDURE perecislenie_NN_GFC_group_TVA(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE:=abm_util.data_by_nrdoc(vNrdoc);
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCnt   NUMBER:=0;
 vTipTVA INT;
 vTip_Opl int;
 vSuma_Total number;

  --tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct,sa
   INTO vDt,vCt,vTip_Opl
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /* Arhaism - pri summovom u4ete
  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc, dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc dtdep
,d.dtsc
,(SELECT Un$functs.tva(d.dtsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,dtdep,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
*/

  select nvl((select ctsc from vmdb_st201d where nrdoc=vNrdoc and pret is null and rownum=1),0)
    into vCnt from dual;
  if vCnt <> 0 then
   msg('Проводки возможны только при наличии продажных цен!'||chr(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  end if;      
     
  select count(*) into vCnt from vmdb_st201d where nrdoc=vNrdoc and nvl(sumagaap,0)=0;  
  if vCnt<>0 then 
   msg('Пересчитайте документ: имеются нулевые суммы без НДС!!!');
  end if; 
      
 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>''
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'un$functs.GETCONT_VINZ7(M.Ct)'
 ,vCt=>'d.Ct'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vDtSc1=>''
 ,vCant=>'d.cant'
 ,vSuma=>'d.ctcant1'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN
 IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
 --check_prices;
 -- Osnovnie provodki
  Gfc_Util.gfc201
  (vNrdoc
  ,vDt=>'nvl(m.dt,d.dt)'
  ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
  ,vCt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
  ,vDtDep=>'nvl(m.dtdep,d.dtdep)'
  ,vSuma=>'d.sumagaap'
  ,vCod=>'d.rrowid'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vWhere=>'');
 -- NDS
   Gfc_Util.gfc201
   (vNrdoc
   , vCt=>'5342'
   , vCt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
   ,vDtDep=>'nvl(m.dtdep,d.dtdep)'
   , vSuma=>'d.sumavalct'
   , vCant=>''
   , vCodFCdeBaza=>'d.rrowid'
   , vDtNrCM =>vNrCM_F
   , vCtNrCM =>vNrCM_F
   ,vTVACont1Recognition=>FALSE
   , vWhere=>''/*,vdebug=>true*/ );
 
 -- Автозакрытие сумм за наличный расчет на 2416
   if nvl(vTip_Opl,0)=1 and vData>='01.10.2012' then
    select sum(suma) into vSuma_Total from vmdb_st201d where nrdoc=vNrdoc;
    if nvl(vSuma_Total,0)<>0 then
     insert into vmdb_cmi (nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
     select nrdoc, 2417 dt, 1276, /*ctdep*/135435, dt, dtdep, vSuma_Total, vNrCM_F, vNrCM_F
     from vmdb_st201m 
     where nrdoc=vNrdoc;
    end if;
   end if;
   
 --sinecost
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc,
                    vDt=>'un$functs.GETCONT_VINZ7(M.Ct)',
                    vDt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')',
                    vCt=>'d.Ct', 
                    vDtsc=>'d.ctsc',
                    vCtsc=>'d.ctsc',
                    vDtDep=>'nvl(d.ctdep,m.CtDep)', 
                    vCtDep=>'nvl(d.ctdep,m.CtDep)', 
                    vDtSc1=>'', 
                    vCant=>'d.cant', 
                    vSuma=>'d.ctcant1', 
                    vWhere=>'', 
                    vDtNrCm=>vNrCM_F, 
                    vCtNrCm=>vNrCM_F);

 ELSIF Yparams.vTip_Retail=2 THEN --summovoi

   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   -- Dohod 2171-----------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Dohod 2172-----------
   FOR c IN (SELECT DECODE(CODTVA,0,vScTVRB0proc,8,vScTVRB8proc,20,vScTVRB20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct=2172
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Dohod ne 2171 i ne 2172-----------
   FOR c IN (SELECT ctsc sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct NOT IN (2171,2172,2165)
              GROUP BY ctsc
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, vDt, vDtdep, 6112, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
  IF vTipTVA=-1 THEN
   INSERT INTO VMDB_CMI (nrdoc, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
   VALUES (vNrdoc, 5342, 92, vCt, vCtdep, 0, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CODTVA,0,91,8,8,20,20,'',92) ct1
       , SUM(sumavalct) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dtdep, ct, ct1, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, vDt, vDtDep, 5342, c.ct1, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
  END IF;
  --- NDS v tovare ----------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , ct
       , SUM(sumavalct) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA,ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 8251, c.sc, vCtdep, c.ct/*2171*/, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti 2171 (v tom 4isle natsenka) ------------
   FOR c IN (SELECT DECODE(CODTVA,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       ,DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1
       , ct
       , SUM(sumagaap) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct in (2171,2165)
              GROUP BY CODTVA, ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dt1, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1 ,c.sc, vCtdep, c.ct/*2171*/, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti 2172 ------------
   FOR c IN (SELECT DECODE(CODTVA,0,vScTVRB0proc,8,vScTVRB8proc,20,vScTVRB20proc) sc
        ,DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1
       , SUM(CANT*I_PRETV) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct=2172
              GROUP BY CODTVA
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt,dt1, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1, c.sc, vCtdep, 2172, c.sc, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Sebestoimosti ne 2171 i ne 2172 ------------
   FOR c IN (SELECT ctsc sc,
        DECODE(CODTVA,0,91,8,8,20,20,'',92) dt1,
        ct, SUM(cant) cant
       , SUM(CANT*I_PRETV) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND ct NOT IN (2171,2172,2165)
              GROUP BY ctsc,ct
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dt1, dtsc, dtdep, ct, ctsc, ctdep, cant, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 7112, c.dt1, c.sc, vCtdep, c.ct, c.sc, vCtdep, c.cant, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;   
  END IF;
 END IF;
  --------
end;
------------------------------------------------------------------------------------------------------------------
PROCEDURE GFC_Cassa_F(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE;
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCasaCont NUMBER:=2414; -- счет кассы магазина
 vSC_Flux NUMBER:=1276;

-- vCnt   NUMBER:=0;
--  tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct, NVL(dtdep,0)
   INTO vDt,vCt , vDtDep
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;


 IF vNrset<>2 AND vDtDep NOT IN (16984) THEN
  RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при фильтре Ф!');
/*  select nvl((select dtsc from VMDB_ST201D where nrdoc=vNrdoc and pret is null and rownum=1),0)
   into vCnt from dual;
  IF vCnt <> 0 THEN
   RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);*/
  ELSE
--   SELECT NVL(dtdep,0) INTO vDtDep FROM vmdb_st201m WHERE nrdoc=vNrdoc;
--   select nvl(ctdep,0) into vCtDep from vmdb_st201m where nrdoc=vNrdoc;
--   select nvl(ct,0) into vCt from vmdb_st201m where nrdoc=vNrdoc;

   -- Dohod -----------
 INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT d.nrdoc1, m.nrdoc, vCasaCont, vSC_Flux, dep, sc1,
   6112, vSc20proc, m.DtDep, NVL(suma1-suma2,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma1,0)<>0);
 ------
 INSERT INTO VMDB_CMI (/*cod,*/ nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT /*d.nrdoc1+1,*/ m.nrdoc, vCasaCont, vSC_Flux, dep, sc1,
   6112, vSc8proc, m.DtDep, NVL(suma3-suma4,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma3,0)<>0);
 ------
 INSERT INTO VMDB_CMI (/*cod,*/ nrdoc, dt, dtsc, dtdep, dtsc1, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT /*d.nrdoc1+2,*/ m.nrdoc, vCasaCont, vSC_Flux, dep, sc1,
   6112, vSc0proc, m.DtDep, NVL(suma5,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma5,0)<>0);

   -- NDS ---------------
 INSERT INTO VMDB_CMI (nrdoc, sumagaap, dt, dtsc, dtdep, dtsc1, ct, ct1, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, suma1-suma2, vCasaCont, vSC_Flux, dep, sc1,
   5342, 20, NVL(suma2,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND (NVL(suma1,0)<>0 OR NVL(suma2,0)<>0));
 --------
 INSERT INTO VMDB_CMI (nrdoc,sumagaap, dt, dtsc, dtdep, dtsc1, ct, ct1, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, suma3-suma4, vCasaCont, vSC_Flux, dep, sc1,
   5342, 8, NVL(suma4,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND (NVL(suma3,0)<>0 OR NVL(suma4,0)<>0));
 --------
 INSERT INTO VMDB_CMI (nrdoc,sumagaap, dt, dtsc, dtdep, dtsc1, ct, ct1, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, NVL(suma5,0), vCasaCont, vSC_Flux, dep, sc1,
   5342, 92, 0, vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(d.suma5,0)<>0);

   -- NDS v Tovare -----------
 INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, 8251, vSc20proc, m.DtDep,
   2171, vSc20proc, m.DtDep, NVL(suma2,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma2,0)<>0);
 ------
 INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, 8251, vSc8proc, m.DtDep,
   2171, vSc8proc, m.DtDep, NVL(suma4,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma4,0)<>0);

   -- Sebestoimosti -----------
 INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, 7112, vSc20proc, m.DtDep,
   2171, vSc20proc, m.DtDep, NVL(suma1-suma2,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma1,0)<>0);
 ------
 INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, 7112, vSc8proc, m.DtDep,
   2171, vSc8proc, m.DtDep, NVL(suma3-suma4,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma3,0)<>0);
 ------
 INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
 (SELECT m.nrdoc, 7112, vSc0proc, m.DtDep,
   2171, vSc0proc, m.DtDep, NVL(suma5,0), vNrCM_F, vNrCM_F
 FROM VMDB_CST3A d, VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC AND NVL(suma5,0)<>0);

   -- V tsentralinuiu kassu za vi4etom summi POS-terminala -----------
 SELECT DATAMANUAL INTO vData FROM VMDB_DOCS WHERE cod=vNrdoc;
 IF vData<TO_DATE('19.05.2008','DD.MM.YYYY') THEN
   INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
  (SELECT m.nrdoc, 2411, vSC_Flux, 16656,
    vCasaCont,  vSC_Flux, Dep, NVL(NVL(suma1,0)+NVL(suma3,0)+NVL(suma5,0)-NVL(suma6,0),0), vNrCM_F, vNrCM_F
  FROM VMDB_CST3A d, VMDB_ST201M m
   WHERE d.nrdoc=vNrdoc AND m.nrdoc=d.NRDOC);
 END IF;
 ------
 END IF;

  --------
END GFC_Cassa_F;
------------------------------------------------------------------------------------------------------------------
PROCEDURE sponsor_GFC(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE;
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCodFC    NUMBER;

  tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct
   INTO vDt,vCt
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc
,d.ctsc
,(SELECT Un$functs.tva(d.ctsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
 IF (vNrset=1 OR vNrset=3)
  THEN
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>vDt
 ,vCt=>'d.Ct'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vCant=>'d.cant'
 ,vSuma=>'d.suma'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>vDt
 ,vCt=>'d.ct'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vCant=>'d.cant'
 ,vSuma=>'d.suma'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vCod=>'d.rrowid'
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
   --- TVA
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'Un$pdc_util.cont_conversion(7134)'
 ,vCt=>'5342'
 ,vDtsc=>'25739'
 ,vCtsc=>''
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vCant=>''
 ,vSuma=>'d.sumavalct'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vCodFcDeBaza=>'d.rrowid'
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;

  --------
END sponsor_GFC;
------------------------------------------------------------------------------------------------------------------
PROCEDURE Import_GFC(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE;
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCasaCont NUMBER:=2414; -- счет кассы магазина
 CURSOR c1 IS
   SELECT cont,dep,sc,suma1 FROM VMDB_CST3A
    WHERE SUMA1<>0 AND nrdoc=vNrdoc;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct
   INTO vDt,vCt
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

-- if (vNrset=1 or vNrset=3) then
-- основная проводка
  Gfc_Util.gfc201(
  vNrdoc=>vNrdoc
 ,vFunct=>1
 ,vCod=>'d.Rrowid'
 ,vDtsc=>'d.dtsc'
 ,vCtsc=>''
 ,vValutadt=>'''LEI'''
 ,vValutaCT=>'m.valutact'
 ,vSUMA=>'d.SUMAVALCT'
 ,vSUMAVALCT=>'d.SUMA'
 ,vSUMAVALDT=>'d.SUMAVALCT'
 );
-- процедуры
  Gfc_Util.gfc201(
  vNrdoc=>vNrdoc
 ,vCt=>'2343'
 ,vDtsc=>'d.dtsc'
 ,vCtsc=>'23560'
 ,vDtDep=>'m.dtdep'
 ,vCtDep=>'23555'
    ,vCant=>''
 ,vSUMA=>'d.SUMAgaap'
 ,vValutadt=>'''LEI'''
 ,vValutaCT=>'''LEI'''
 );
-- пошлины
  Gfc_Util.gfc201(
  vNrdoc=>vNrdoc
 ,vCt=>'2343'
 ,vDtsc=>'d.dtsc'
 ,vCtsc=>'23561'
 ,vDtDep=>'m.dtdep'
 ,vCtDep=>'23555'
    ,vCant=>''
 ,vSUMA=>'d.dtcant1'
 ,vValutadt=>'''LEI'''
 ,vValutaCT=>'''LEI'''
 );
-- аккцизы
  Gfc_Util.gfc201(
  vNrdoc=>vNrdoc
 ,vCt=>'2343'
 ,vDtsc=>'d.dtsc'
 ,vCtsc=>'23563'
 ,vDtDep=>'m.dtdep'
 ,vCtDep=>'23555'
    ,vCant=>''
 ,vSUMA=>'d.ctcant1'
 ,vValutadt=>'''LEI'''
 ,vValutaCT=>'''LEI'''
 );

-- end if;
-- проводка на НДС
 Gfc_Util.gfc201(
 vNrdoc, 4
 ,vCodfcdebaza=>'d.rrowid'
 ,vCt=>'2343' --:ini_cont_vama
 ,vDt=>'5342'
 ,vDtsc=>''
 ,vctsc=>'23562' --:ini_scTVA
 ,vDtdep=>''
 ,vctdep=>'23555' --:ini_scTVADep
 ,vValutadt=>'''LEI'''
 ,vValutact=>'''LEI'''
 ,vSUMA=>'m.sB*ratio_to_report(d.suma)OVER()'
 ,vCant=>''
 ,vWhere_before=>' and m.sb is not null'
 -- ,vDebug=>TRUE
 );
  EXECUTE IMMEDIATE 'delete from vmdb_cmi '||
                    'where nrdoc=:nrdoc and dt=5342 '||
     'and dt1=93 and suma is null'
  USING vNrdoc;

 BEGIN
 FOR c1rec IN c1 LOOP
  Gfc_Util.gfc201(
  vNrdoc, 2
  ,vCodfcdebaza=>'d.rrowid'
  ,vDt=>'nvl(d.dt,(SELECT contsinec FROM tms_mpt WHERE cod=d.dtsc))'
  ,vCt=>c1rec.cont
  ,vCtsc=>c1rec.sc
  ,vCtdep=>c1rec.dep
  ,vValutact=>'''LEI'''
  ,vCant=>''
  ,vFitToSuma=>c1rec.suma1
  ,vWhere_before=>' and m.ctdep<>'||c1rec.dep
  -- ,vDebug=>TRUE
  );
  Gfc_Util.gfc201(
  vNrdoc, 2
  ,vCodfcdebaza=>'d.rrowid'
  ,vDt=>'nvl(d.dt,(SELECT contsinec FROM tms_mpt WHERE cod=d.dtsc))'
  ,vCtsc=>c1rec.sc
  ,vCant=>''
  ,vDtnrdoc=>vNrdoc
  ,vSumavalct=>'(CASE WHEN row_number() OVER(ORDER BY d.suma DESC)=1 THEN '||c1rec.suma1||' ELSE 0 END)'
  ,vFitToSuma=>'Un$valuta.getcurs('''||vData||''',m.valutact)*'||c1rec.suma1
  ,vWhere_Before=>' and m.ctdep='||c1rec.dep
  --,vDebug=>TRUE
  );
  END LOOP;
   END;

 IF (vNrset=2 OR vNrset=3)
  THEN
   NULL;
  END IF;

  --------
END Import_GFC;
------------------------------------------------------------------------------------------------------------------
PROCEDURE Akt_razdelki_Raspredelenie(vNrdoc NUMBER) IS
 vNrset NUMBER;
 sql1 LONG;
 sql2 LONG;
 vDep NUMBER;
 vSuma NUMBER;
BEGIN
 SELECT NVL(dtdep,0) INTO vDep
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

 /*UPDATE VMDB_CST3B
    SET suma1=NULL,pret1=NULL
  WHERE nrdoc=vNrdoc AND prm1 IS NULL;*/

 FOR rc IN (SELECT nrdoc,nrdoc1,sc,suma1 FROM VMDB_CST3A m WHERE nrdoc=vNrdoc)
 LOOP
  SELECT NVL(SUM(suma1),0) INTO vSuma FROM VMDB_CST3B
  WHERE nrdoc=rc.Nrdoc AND nrdoc1=rc.nrdoc1 AND /*suma1*/ prm1 IS NOT NULL ;
  UPDATE VMDB_CST3B d
  SET suma1=(SELECT suma1 FROM (
      SELECT sc,nrdoc2,cant1,(rc.suma1-vSuma)*ratio_to_report(suma1) OVER (PARTITION BY nrdoc1) suma1
        FROM VMDB_CST3B
       WHERE NRDOC=rc.nrdoc AND nrdoc1=rc.nrdoc1 AND /*suma1*/ prm1 IS NULL)a
         WHERE a.sc=d.sc AND a.nrdoc2=d.nrdoc2)
   WHERE NRDOC=rc.nrdoc AND d.nrdoc1=rc.NRDOC1;
 END LOOP;
--------
END Akt_razdelki_Raspredelenie;
--------------------------------------------------------------------------------
PROCEDURE Akt_razdelki_gfc(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vSql1 LONG;
 vContProd NUMBER:=8301;-- по аналогии с актом пересорта только в корреспондеции с 2172
                       --8281;  счет производства
 sc_sum0 NUMBER;
BEGIN
 SELECT Get_Nrset(nrset) INTO vNrset
   FROM VMDB_DOCS
 WHERE cod=vNrdoc;

 SELECT NVL((SELECT sc FROM(
  SELECT a.sc FROM vmdb_cst3a a, vmdb_cst3b b
 WHERE a.nrdoc=vNrdoc AND a.nrdoc=b.nrdoc(+) AND a.nrdoc1=b.nrdoc1(+)
  GROUP BY a.sc, a.nrdoc1, a.suma1
 HAVING NVL(a.suma1,0)<>SUM(nvl(b.suma1,0))
 )WHERE ROWNUM=1),0)
 INTO sc_sum0 FROM dual;

 IF sc_sum0<>0 THEN
  msg('По позиции '||sc_sum0||' не совпадают суммы!');
 END IF;

 vSql1:='select m.dt,d.cont ct,m.dtdep,m.dtdep ctdep,m.nrdoc,d.nrdoc1,d.sc,d.cant1 cant,d.suma1 suma '||
        'from vmdb_st201m m,VMDB_CST3A d where m.nrdoc='||vNrdoc||' and d.nrdoc=m.nrdoc';

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc
  (tSource =>vSql1
  ,vNrdoc  =>vNrdoc
  ,vCod    =>'d.nrdoc1'
  ,vDt     =>vContProd
  ,vCt     =>'d.ct'
  ,vDt1=>''
  ,vCt1=>''
  ,vDtSc   =>'d.sc'
  ,vCtSc   =>'d.sc'
  ,vDtDep  =>'d.dtdep'
  ,vCtDep  =>'d.ctdep'
  ,vDtSc1=>''
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'--*(1+un$functs.tva(d.sc,d.dtdep))
  ,vWhere  =>''
  ,vDtNrCM =>vNrCM_U
  ,vCtNrCM =>vNrCM_U
  ,vDtCant1=>''
  ,vCtCant1=>''
  ,vFunct=>''
--  ,vDebug=>True
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 Gfc_Util.gfc
  (tSource =>vSql1
  ,vNrdoc  =>vNrdoc
--  ,vCod    =>'d.nrdoc1'
  ,vDt     =>vContProd
  ,vCt     =>'d.ct'
  ,vDt1=>''
  ,vCt1=>''
  ,vDtSc   =>'d.sc'
  ,vCtSc   =>'d.sc'
  ,vDtDep  =>'d.dtdep'
  ,vCtDep  =>'d.ctdep'
  ,vDtSc1=>''
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  --,vSuma   =>'d.suma/(1+un$functs.tva(d.sc,d.dtdep))'
  ,vWhere  =>''
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vDtCant1=>''
  ,vCtCant1=>''
  ,vFunct=>''
--  ,vDebug=>True
  );
 END IF;

 vSql1:='select /*m.dt*/d.cont dt,m.ct,m.dtdep,m.dtdep ctdep,m.nrdoc,d.nrdoc1,d.sc,d.cant1 cant,d.suma1 suma '||
        'from vmdb_st201m m,VMDB_CST3B d where m.nrdoc='||vNrdoc||' and d.nrdoc=m.nrdoc';

 IF (vNrset=1 OR vNrset=3) THEN
 Gfc_Util.gfc
  (tSource =>vSql1
  ,vNrdoc  =>vNrdoc
  ,vCodFcDeBaza=>'d.nrdoc1'
  ,vDt     =>'d.dt'
  ,vCt     =>vContProd
  ,vDt1=>''
  ,vCt1=>''
  ,vDtSc   =>'d.sc'
  ,vCtSc   =>'(select sc from vmdb_cst3a where nrdoc=d.nrdoc and nrdoc1=d.nrdoc1)'
--  ,vCtSc   =>'d.sc'
  ,vDtDep  =>'d.dtdep'
  ,vCtDep  =>'d.dtdep'
  ,vDtSc1=>''
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'--*(1+un$functs.tva(d.sc,d.dtdep))'
  ,vWhere  =>''
  ,vDtNrCM =>vNrCM_U
  ,vCtNrCM =>vNrCM_U
  ,vDtCant1=>''
  ,vCtCant1=>'D.CANT'
  ,vFunct=>''
--  ,vDebug=>True
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 Gfc_Util.gfc
  (tSource =>vSql1
  ,vNrdoc  =>vNrdoc
--  ,vCodFcDeBaza=>'d.nrdoc1'
  ,vDt     =>'d.dt'
  ,vCt     =>vContProd
  ,vDt1=>''
  ,vCt1=>''
  ,vDtSc   =>'d.sc'
  ,vCtSc   =>'(select sc from vmdb_cst3a where nrdoc=d.nrdoc and nrdoc1=d.nrdoc1)'
--  ,vCtSc   =>'d.sc'
  ,vDtDep  =>'d.dtdep'
  ,vCtDep  =>'d.dtdep'
  ,vDtSc1=>''
  ,vCtSc1=>''
  ,vValutaDt=>''
  ,vValutaCt=>''
  ,vSumaValDt=>''
  ,vSumaValCt=>''
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  --,vSuma   =>'d.suma/(1+un$functs.tva(d.sc,d.dtdep))'
  ,vWhere  =>''
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vDtCant1=>''
  ,vCtCant1=>'D.CANT'
  ,vFunct=>''
--  ,vDebug=>True
  );
 END IF;

--------
END Akt_razdelki_gfc;
--------------------------------------------------------------------------------
--- Касса расход - проводки SYSFID=1151
PROCEDURE Kassa_rashod_gfc(vNrdoc   NUMBER
                          ,pCont    NUMBER DEFAULT NULL
                          ,pSC5348j NUMBER DEFAULT NULL
                          ,pSC5348f NUMBER DEFAULT NULL
                           ) IS
 vNrset   NUMBER;
 vMinFin   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
 vsql     LONG; -- конеченый запрос
 cont5348 NUMBER:=NVL(pCont,5348);
 sc5348j   NUMBER:=NVL(pSC5348j,25487);
 sc5348f   NUMBER:=NVL(pSC5348f,29724);
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT NVL(ctsc1,1328)
   INTO vMinFin
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vDt1  =>'decode('||vNrset||',1,1,null)'
  ,vSuma =>'d.suma'
  ,vDtNrCM =>vNrCM_U
  ,vCtNrCM =>vNrCM_U
  );
 END IF;

 IF (vNrset=2 OR vNrset=3)
  THEN

  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vCod=>'d.rrowid'
  ,vSuma=>'(d.suma-nvl(d.sumagaap,0))'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  );

  Gfc_Util.gfc201
  (vNrdoc=>vNrdoc
  ,vCodFcDeBaza=>'d.rrowid'
  ,vCt=>cont5348
 -- ,vCt=>'6112'
  ,vCtsc=>'decode((select CONTSP1 from vms_org where cod=d.dtdep),null,'||SC5348j||',5,'||SC5348f||')'
  ,vDtDep=>'d.DtDep'
  ,vCtDep=>vMinFin
  ,vCant=>''
  ,vSuma=>'d.sumagaap'
  ,vSumagaap=>'d.suma'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vWhere_Before=>' and nvl(d.sumagaap,0)<>0'
  );
 END IF;
--------------------
END Kassa_rashod_gfc;
--------------------------------------------------------------------------------
--- Возврат товара поставщику - основные проводки
PROCEDURE Vozvrat_postav_GFC(vNrdoc NUMBER
                             )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
 vsql    LONG;
 vSa     NUMBER:=0;
 vDtDep    NUMBER;
 vCtDep    NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;
 
 v_dt1 number:=2171;
 v_dt2 number:=2172;
 v_funct number:=99;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;
  
 begin
   select 2178, 2179
   into v_dt1, v_dt2
   from tmdb_docs_add a
   where cod = vNrdoc
   and exists
     (
     select null
     from vmdb_docs d
     where d.cod = a.parent_nrdoc
     and d.sysfid = 1282
     );
   
   v_funct := 777;
  exception when no_data_found then
    v_dt1 := 2171;
    v_dt2 := 2172;
    
    v_funct := 99;
  end;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc, vfunct => v_funct
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'nvl(m.Ct,d.Ct)'
    ,vCt1    =>'decode('||vNrset||',1,1,null)'
    ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'-d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) 
  THEN
 IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
 -- Osnovnie provodki
  Gfc_Util.gfc201(vNrdoc, v_funct, vCod=>'d.rrowid'
    , vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
 , vSuma=>'-d.sumagaap', vCant=>'-d.cant'
    , vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F, vWhere=>'');
 -- NDS
   Gfc_Util.gfc201(vNrdoc, v_funct, vCodFCdeBaza=>'d.rrowid'
    , vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    , vDtDep=>'', vSuma=>'-d.sumavalct', vCant=>'', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
    ,vTVACont1Recognition=>FALSE,vWhere=>'');

 ELSIF Yparams.vTip_Retail=2 THEN --summovoi  
  SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
   INTO vCnt FROM dual;
  IF vCnt <> 0 THEN
   RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  ELSE
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   -- Sebestoimosti -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt1
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (c.rrowid, vNrdoc, v_dt1, c.sc, vDtdep, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;
   -- NDS ---------------
 IF vTipTVA=-1 THEN
    SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
    SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm, funct)
    VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F, v_funct);
  ELSE
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
       , SUM(sumavalct) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt1
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;
 END IF;
  --- NDS v tovare ----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(clcsumax_6) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt1
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (vNrdoc, v_dt1, c.sc, vDtdep, 8251, c.sc, vDtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;
   -- Natsenka ------------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(clcsumax_5)-SUM(clcsumax_6)-SUM(sumagaap) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt1
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (vNrdoc, v_dt1, c.sc, vDtdep, 8211, c.sc, vDtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;

    -- Sebestoimosti 2172-----------
   FOR c IN (SELECT sumagaap suma, cant cant, dt, dtsc sc, rrowid
           FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt2) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (c.rrowid, vNrdoc, c.dt, DECODE(Un$functs.tva(c.sc),0.2,vScTVRB20proc,0.08,vScTVRB8proc,vScTVRB0proc),
           vDtdep, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;

    -- Sebestoimosti ne 2171 i ne 2172-----------
   FOR c IN (SELECT sumagaap suma, cant cant, dt, dtsc sc, rrowid
           FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt NOT IN (v_dt1,v_dt2)) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, cant, dtnrcm, ctnrcm, funct)
    VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, -c.suma, -c.cant, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;

   --- NDS ne 2171----------
  IF vTipTVA<>-1 THEN
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt<>v_dt1 AND sumavalct<>0) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;
   END IF;
  END IF;
  end if;
 END IF;
--------------------
END Vozvrat_postav_GFC;
--------------------------------------------------------------------------------
--- Возврат товара поставщику - основные проводки
PROCEDURE Vozvrat_postav_GFC_2178(vNrdoc NUMBER
                             )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
 vsql    LONG;
 vSa     NUMBER:=0;
 vDtDep    NUMBER;
 vCtDep    NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;

BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'nvl(m.Ct,d.Ct)'
    ,vCt1    =>'decode('||vNrset||',1,1,null)'
    ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'-d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) 
  THEN
 IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
 -- Osnovnie provodki
  Gfc_Util.gfc201(vNrdoc, vCod=>'d.rrowid'
    , vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
 , vSuma=>'-d.sumagaap', vCant=>'-d.cant'
    , vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F, vWhere=>'');
 -- NDS
   Gfc_Util.gfc201(vNrdoc, vCodFCdeBaza=>'d.rrowid'
    , vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    , vDtDep=>'', vSuma=>'-d.sumavalct', vCant=>'', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
    ,vTVACont1Recognition=>FALSE,vWhere=>'' );

 ELSIF Yparams.vTip_Retail=2 THEN --summovoi  
  SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
   INTO vCnt FROM dual;
  IF vCnt <> 0 THEN
   RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  ELSE
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   -- Sebestoimosti -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2178
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, 2178, c.sc, vDtdep, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
 IF vTipTVA=-1 THEN
    SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
    SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm)
    VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
       , SUM(sumavalct) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2178
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
 END IF;
  --- NDS v tovare ----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(clcsumax_6) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2178
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 2178, c.sc, vDtdep, 8251, c.sc, vDtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Natsenka ------------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(clcsumax_5)-SUM(clcsumax_6)-SUM(sumagaap) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2178
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 2178, c.sc, vDtdep, 8211, c.sc, vDtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;

    -- Sebestoimosti 2172-----------
   FOR c IN (SELECT sumagaap suma, cant cant, dt, dtsc sc, rrowid
           FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2179) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, c.dt, DECODE(Un$functs.tva(c.sc),0.2,vScTVRB20proc,0.08,vScTVRB8proc,vScTVRB0proc),
           vDtdep, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;

    -- Sebestoimosti ne 2171 i ne 2172-----------
   FOR c IN (SELECT sumagaap suma, cant cant, dt, dtsc sc, rrowid
           FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt NOT IN (2178,2179)) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, cant, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, -c.suma, -c.cant, vNrCM_F, vNrCM_F);
   END LOOP;

   --- NDS ne 2171----------
  IF vTipTVA<>-1 THEN
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt<>2178 AND sumavalct<>0) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   END IF;
  END IF;
  end if;
 END IF;
--------------------
END Vozvrat_postav_GFC_2178;
--------------------------------------------------------------------------------
--- Возврат товара поставщику - основные проводки
PROCEDURE Vozvrat_postav_GFC_plus(vNrdoc NUMBER
                             )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vCt     =>'nvl(d.dt,m.dt)'
    ,vDt     =>'nvl(m.Ct,d.Ct)'
    ,vCt1    =>'decode('||vNrset||',1,1,null)'
    ,vCtsc   =>'d.dtsc'
    ,vCtDep  =>'nvl(d.dtdep,m.dtdep)'
    ,vDtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  );
 END IF;

 IF (vNrset=2 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vDt     =>'nvl(m.Ct,d.Ct)'
    ,vCt     =>'nvl(d.Ct,m.Dt)'
    ,vCtsc   =>'d.dtsc'
    ,vCtDep  =>'nvl(d.dtdep,m.dtdep)'
    ,vDtDep  =>'m.ctdep'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.sumagaap'
  ,vCod    =>'d.rrowid'
    ,vDtNrCM =>vNrCM_F
    ,vCtNrCM =>vNrCM_F
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  );
 END IF;
--------------------
END Vozvrat_postav_GFC_plus;
--------------------------------------------------------------------------------
--- Возврат товара поставщику - проводки НДС 5342,2261
PROCEDURE Vozvrat_postav_GFC_TVA(vNrdoc NUMBER
                                ,p2261 NUMBER DEFAULT NULL
                                 )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=2 OR vNrset=3)
  THEN
   IF p2261 IS NULL
    THEN
     Gfc_Util.gfc201
   (vNrdoc=>vNrdoc
      ,vct=>'m.ct'
      ,vDt=>'5342'
      ,vDtdep=>''
      ,vDtsc1=>''
      ,vCant=>''
      ,vSuma=>'nvl(-d.sumavalct,0)'
      ,vDtNrCM =>vNrCM_F
      ,vCtNrCM =>vNrCM_F
      ,vWhere=>''
      ,vCODFCDEBAZA=>'d.RROWID'
      );
   ELSE
     Gfc_Util.gfc201(
     vNrdoc=>vNrdoc
    ,vct=>'m.ct'
    ,vDt=>'2261'
    ,vDtdep=>'m.ctdep'
    ,vDtsc1=>''
    ,vCant=>''
    ,vSuma=>'nvl(-d.sumavalct,0)'
    ,vDtNrCM =>vNrCM_F
    ,vCtNrCM =>vNrCM_F
    ,vWhere=>''
    ,vCODFCDEBAZA=>'d.RROWID'
    );
  END IF;
 END IF;
--------------------
END Vozvrat_postav_GFC_TVA;
--------------------------------------------------------------------------------
--- Возврат товара поставщику - основные проводки
PROCEDURE SpisanieKUH_GFC(vNrdoc NUMBER
                             )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'nvl(d.Ct,m.Ct)'
    ,vDtSC   =>'m.dtsc'
    ,vCtSC   =>'d.ctsc'
    ,vDtDep  =>'m.dtdep'
    ,vCtDep  =>'m.ctdep'
   ,vCant   =>'d.cant'
   ,vSuma   =>'d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
    ,vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'nvl(d.Ct,m.Ct)'
    ,vDtSC   =>'m.dtsc'
    ,vCtSC   =>'d.ctsc'
    ,vDtDep  =>'m.dtdep'
    ,vCtDep  =>'m.ctdep'
   ,vCant   =>'d.cant'
   ,vSuma   =>'d.suma/(1+Un$Functs.tva(d.ctsc,m.dtdep))'
    ,vDtNrCM =>vNrCM_F
    ,vCtNrCM =>vNrCM_F
    ,vWhere=>''
  );
 END IF;
--------------------
END SpisanieKUH_GFC;
--------------------------------------------------------------------------------
PROCEDURE TVA_realiz_nije_sinecost_Fill(vNrdoc INTEGER)IS
 vSql   LONG;
 vCont  INTEGER;
 vDatab DATE;
 vDataf DATE;
BEGIN
 SELECT dt,dtdata,ctdata
   INTO vCont,vDatab,vDataf
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

 DELETE FROM VMDB_ST201D WHERE nrdoc=vNrdoc;

 vSql:='insert into vmdb_st201d(nrdoc,dt,dtsc,suma,sumagaap,sumavalct,cant) ';
 vSql:= vSql||'select '||vNrdoc||' nrdoc,:1 dt, t1.sc,t1.suma_sinec,t2.suma_venit,t2.suma_venit-t1.suma_sinec raznitsa,((t2.suma_venit-t1.suma_sinec)*un$functs.tva(t1.sc))as suma_cant '||CHR(10)||
       'from(select dtsc sc, sum(suma) suma_sinec '||CHR(10)||
       'from vmdb_cmr '||CHR(10)||
       'where data between :datab and :datas '||CHR(10)||
       'and ct=:ct '||CHR(10)||
       'and dt=7212 /*un$functs.GETCONT_VINZ7(:ct)*/ '||CHR(10)||
       'group by dtsc) t1, '||CHR(10)||
       '(select ctsc sc, sum(suma) suma_venit '||CHR(10)||
       'from vmdb_cmr '||CHR(10)||
       'where data between :datab and :datas '||CHR(10)||
       'and ct=6212/*un$functs.GETCONT_VINZ6(:ct) */'||CHR(10)||
       'group by ctsc)t2 '||CHR(10)||
       'where t1.sc=t2.sc';

say(vSql);
 EXECUTE IMMEDIATE vSql USING vCont,vDatab,vDataf,vCont,vDatab,vDataf;
-----------
END TVA_realiz_nije_sinecost_Fill;
-------------------------------------------------------------------------------------
PROCEDURE TVA_realiz_nije_sinecost_GFC(vNrdoc INTEGER)
 IS
BEGIN
  ----  проводки на НДС
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.ct'
 ,vCt=>'5342'
 ,vCt1=>'100'
 ,vDtsc=>'m.CtSC'
 ,vDtDep=>'m.CtDep'
 ,vDtSC1=>'d.CtSC1'
 ,vCant=>''
 ,vSuma=>'abs(d.sumavalct)*un$functs.tva(d.dtsc)'
 ,vSumagaap=>'abs(d.sumavalct)'
 ,vWhere_before=>' and d.sumavalct<0  and un$functs.tva(d.dtsc) in (0.2,0.08)'
 );
--------------
END TVA_realiz_nije_sinecost_GFC;
--------------------------------------------------------------------------------
--- Приход материалов - -------
  PROCEDURE Prihod_mat(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData   DATE;
BEGIN
 SELECT datamanual, Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)  THEN
  Gfc_Util.gfc201(
  vNrdoc
  ,vct=>'m.ct'
  ,vdt=>'nvl(d.dt,m.dt)'
--  ,vDtsc1=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  , vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 ------ без НДС --------
  Gfc_Util.gfc201(
  vNrdoc
  ,1
  ,vCod=>'d.RROWID'
  ,vct=>'m.ct'
  ,vdt=>'nvl(d.dt,m.dt)'
--  ,vDtsc1=>''
  ,vSuma=>'d.sumagaap'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  , vWhere=>''
  );
 ------ НДС --------
 Gfc_Util.gfc201(
  vNrdoc
 ,2
 ,vCODFCDEBAZA=>'d.RROWID'
 ,vct=>'m.ct'
 ,vDt=>'5342'
 ,vDtdep=>''
 ,vCtdep=>'m.ctdep'
 ,vDtsc1=>''
 ,vCant=>''
 ,vSuma=>'nvl(d.sumavalct,0)'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vWhere=>''
 );
 END IF;
---------------
END Prihod_mat;
--------------------------------------------------------------------------------
--- Приход материалов по актам закупки -------
  PROCEDURE Prihod_mat_act_zakup(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF Yparams.vUse_U and (vNrset=1 OR vNrset=3)  THEN
  Gfc_Util.gfc201(
  vNrdoc
  ,vct=>'m.ct'
  ,vdt=>'nvl(d.dt,m.dt)'
  ,vDtsc1=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  , vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  IF Yparams.vTip_Retail=1 THEN --coli4estvenno-summovoi
   Gfc_Util.gfc201(
    vNrdoc
   ,vCod=>'d.rrowid'
   ,vct=>'m.ct'
   ,vdt=>'nvl(d.dt,m.dt)'
   ,vDtsc1=>''
   ,vSuma=>'d.suma'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
   , vWhere=>'' );
  ELSIF Yparams.vTip_Retail=2 THEN --summovoi
   Gfc_Util.gfc201(
    vNrdoc
   ,vCod=>'d.rrowid'
   ,vdt=>'nvl(d.dt,m.dt)'
      ,vDtSC=>'Ybon_Docs.decode_sc(d.dtsc, nvl(d.dt,m.dt))'
   ,vDtsc1=>''
   ,vct=>'m.ct'
   ,vSuma=>'d.suma'
   ,vDtNrCm=>vNrCM_F
   ,vCtNrCm=>vNrCM_F
   , vWhere=>'' );
  END IF;
 END IF;
---------------
end;
--------------------------------------------------------------------------------
--- Покупка услуг от фирм РМ - sysfid - 1401 -------
  PROCEDURE Pokupka_uslug(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT  Get_Nrset(nrset) INTO vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)  THEN
 Gfc_Util.gfc201(
  vNrdoc
  ,vDt=>'d.Dt'
  ,vCt=>'m.Ct'
  ,vCtdep=>'m.ctdep'
  ,vCtSc =>'m.ctsc'
  ,vCant=>''
  ,vSuma=>'d.sumagaap'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  ,vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 ------ без НДС --------
 Gfc_Util.gfc201(
  vNrdoc
  ,1
  ,vCod=>'d.RROWID'
  ,vDt=>'d.Dt'
  ,vCt=>'m.Ct'
  ,vDt1=>'case when substr(d.dt,1,1)=''7'' then Un$functs.tva_cont1(d.dtsc) else null end'
  ,vCtdep=>'m.ctdep'
  ,vCtSc =>'m.ctsc'
  ,vCant=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vWhere=>''
  );
 ------ НДС --------
 Gfc_Util.gfc201(
  vNrdoc
 ,2
 ,vCODFCDEBAZA=>'d.RROWID'
 ,vct=>'m.ct'
 ,vDt=>'5342'
 ,vDt1=>'Un$functs.tva_cont1(d.dtsc)'
 ,vDtdep=>''
 ,vCtdep=>'m.ctdep'
 ,vCtSc =>'m.ctsc'
 ,vDtsc1=>''
 ,vCant=>''
 ,vSuma=>'nvl(d.sumavalct,0)'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vWhere=>''
 );
 END IF;
---------------
END Pokupka_uslug;
---------------------------------------------------------------------------------------------------------------------------------
--- Покупка услуг от фирм РМ - sysfid - 1401 -------
  PROCEDURE Pokupka_uslug_refact(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT  Get_Nrset(nrset) INTO vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)  THEN
 Gfc_Util.gfc201(
  vNrdoc
  ,vDt=>'d.Dt'
  ,vCt=>'m.Ct'
  ,vCtdep=>'m.ctdep'
  ,vCtSc =>'m.ctsc'
  ,vCant=>''
  ,vSuma=>'d.sumagaap'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  ,vWhere=>''
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
 ------ без НДС --------
 Gfc_Util.gfc201(
  vNrdoc
  ,1
  ,vCod=>'d.RROWID'
  ,vDt=>'d.Dt'
  ,vCt=>'m.Ct'
  ,vDt1=>'case when substr(d.dt,1,1)=''7'' then Un$functs.tva_cont1(d.dtsc) else null end'
  ,vCtdep=>'m.ctdep'
  ,vCtSc =>'m.ctsc'
  ,vCant=>''
  ,vSuma=>'d.sumagaap'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vWhere_Before=>' and d.dt=8361'
  );
  
   Gfc_Util.gfc201(
  vNrdoc
  ,1
  ,vCod=>'d.RROWID'
  ,vDt=>'d.Dt'
  ,vCt=>'m.Ct'
  ,vDt1=>'case when substr(d.dt,1,1)=''7'' then Un$functs.tva_cont1(d.dtsc) else null end'
  ,vCtdep=>'m.ctdep'
  ,vCtSc =>'m.ctsc'
  ,vCant=>''
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vWhere_Before=>' and d.dt!=8361'
  );
 ------ НДС --------
 Gfc_Util.gfc201(
  vNrdoc
 ,2
 ,vCODFCDEBAZA=>'d.RROWID'
 ,vct=>'m.ct'
 ,vDt=>'5342'
 ,vDtdep=>''
 ,vCtdep=>'m.ctdep'
 ,vCtSc =>'m.ctsc'
 ,vDtsc1=>''
 ,vCant=>''
 ,vSuma=>'nvl(d.sumavalct,0)'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vWhere=>''
 );
  Gfc_Util.gfc201(
  vNrdoc
 ,2
 ,vCODFCDEBAZA=>'d.RROWID'
 ,vct=>'m.ct'
 ,vDt=>'5342'
 ,vDtdep=>''
 ,vCtdep=>'m.ctdep'
 ,vCtSc =>'m.ctsc'
 ,vDtsc1=>''
 ,vCant=>''
 ,vSuma=>'nvl(-d.sumavalct,0)'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 ,vWhere_Before=>' and d.dt=8361'
 );
 END IF;
---------------
END Pokupka_uslug_refact;
---------------------------------------------------------------------------------------------------------------------------------
--- Ввод в эксплуатацию МБП- sysfid - 1404
PROCEDURE mater_miscare_plus_mbp(vNrdoc NUMBER,isPrihod NUMBER :=0 )
IS
 dt_dep   NUMBER;
 ct_dep   NUMBER;
 tmp      NUMBER;
 vcountd  NUMBER;
 vcountm  NUMBER;
 vNrset   NUMBER;
 vNrCM_F  INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U  INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);

BEGIN
 SELECT  Get_Nrset(nrset) INTO vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;

 IF isPrihod=1 THEN
  NULL;
 END IF;

 UPDATE VMDB_ST201DE SET /*dsdsd*/ i_pret=DECODE(cant,0,0,suma/cant) WHERE nrdoc=vNrdoc AND 1=0;

 SELECT NVL(dtsc,0), NVL(dtdep,0)
   INTO ct_dep,dt_dep
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

 SELECT COUNT(*) INTO vcountm
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc
    AND ct IS NOT NULL;


 IF vcountm=1 THEN
  UPDATE VMDB_ST201DE SET (cc1,cc11,cc1sc,cc1dep,cc1sc1)=
  (SELECT ct,ct1,ctsc,ctdep,ctsc1 FROM VMDB_ST201M WHERE nrdoc=vNrdoc )
   WHERE nrdoc=vNrdoc
     AND cc1 IS NULL
     AND cc11 IS NULL
     AND cc1sc IS NULL
     AND cc1dep IS NULL
     AND cc1sc1 IS NULL
     AND ct=2132 AND dt=2131;
 END IF;

 SELECT COUNT(*)
   INTO vcountd
   FROM VMDB_ST201DE
  WHERE ct=2132
    AND dt=2131
    AND NVL(cc1,0)=0
    AND nrdoc=vNrdoc;
 IF NVL(vcountd,0)<>0 THEN
   RAISE_APPLICATION_ERROR(-20001,'Укажите затратный счет для МБП!');
 END IF;

 IF (vNrset=2 OR vNrset=3)  THEN

 Gfc_Util.gfc('vmdb_st201de'
 ,vNrdoc,1
 ,vCod=>'d.rrowid'
 ,vDt=>'nvl(Ct,Dt)'
 ,vCt=>'Dt'
 ,vCtsc=>'Dtsc'
 ,vDtsc=>'nvl(Ctsc,Dtsc)'
 ,vDtdep=>'nvl(d.ctdep,'||dt_dep||')'
 ,vCtdep=>'DtDep'
 ,vCtSC1=>'DtSC1'
 ,vDtcant1=>'CtCant'
 ,vCtcant1=>'CtCant'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
 );


-- свыше 100L
 INSERT INTO VMDB_CMI (nrdoc, funct,dt,ct,dt1,ct1,dtsc,dtsc1,ctsc,ctsc1,dtdep,ctdep,suma,codfcdebaza,DtNrCm,CtNrCm)
 SELECT d.nrdoc AS nrdoc
 ,2 AS funct
 ,d.CC1 AS Dt
 ,2141 AS CT
 ,d.dt1 AS DT1
 ,d.ct1 AS CT1
 ,NVL(d.cc1sc,1325) AS DTSC
 ,d.cc1sc1 AS DTSC1
 ,d.dtsc AS CTSC
 ,d.ctsc1 AS CTSC1
 ,NVL(d.cc1dep,m.dtdep) AS DTDEP
 ,NVL(d.cc1dep,m.dtdep) AS CTDEP
 ,d.suma AS SUMA,d.rrowid AS CODFCDEBAZA
 ,vNrCM_F AS DtNrCm, vNrCM_F AS CtNrCm
  FROM VMDB_ST201DE d,VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND d.nrdoc=m.nrdoc
    AND (d.ct=2132 AND d.dt=2131) AND NVL(d.DT,0)<>0
    AND  Un$functs.CHECKMBPUZUR(d.dt,d.ct,d.I_PRET)=2;

-- ниже 100L
 INSERT INTO VMDB_CMI (nrdoc, funct,
             dt,dt1,dtsc,dtdep,dtsc1,
             ct,ct1,ctsc,ctdep,ctsc1
             ,suma,codfcdebaza,cant
             ,DtNrCm,CtNrCm)
 SELECT
  d.nrdoc AS nrdoc
 ,3 AS funct
 ,d.CC1 AS Dt
 ,d.dt1 AS DT1
 ,NVL(d.cc1sc,1325) AS DTSC
 ,NVL(d.cc1dep,m.dtdep) AS DTDEP
 ,d.cc1sc1 AS DTSC1
 ,d.CT
 ,d.ct1
 ,d.dtsc
 ,NVL(d.ctdep,m.dtdep)
 ,d.dtsc1
 ,d.suma
 ,d.rrowid AS CODFCDEBAZA
 ,d.cant
 ,vNrCM_F AS DtNrCm
 ,vNrCM_F AS CtNrCm
 FROM VMDB_ST201DE d, VMDB_ST201M m
 WHERE d.nrdoc=vNrdoc AND d.nrdoc=m.nrdoc
   AND (d.ct=2132 AND d.dt=2131)
   AND NVL(d.DT,0)<>0
   AND  Un$functs.CHECKMBPUZUR(d.dt,d.ct,d.i_pret)=1;
 END IF;
---------------------
 IF (vNrset=1 OR vNrset=3)  THEN

 Gfc_Util.gfc('vmdb_st201de'
 ,vNrdoc,1
 ,vCod=>'-d.rrowid'
 ,vDt=>'nvl(Ct,Dt)'
 ,vCt=>'Dt'
 ,vCtsc=>'Dtsc'
 ,vDtsc=>'nvl(Ctsc,Dtsc)'
 ,vDtdep=>'nvl(d.ctdep,'||dt_dep||')'
 ,vCtdep=>'DtDep'
 ,vCtSC1=>'DtSC1'
 ,vDtcant1=>'CtCant'
 ,vCtcant1=>'CtCant'
 ,vSuma=>'suma*(1+un$functs.tva(d.dtsc))'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
 );
-- свыше 100L
 INSERT INTO VMDB_CMI (nrdoc, funct,dt,ct,dt1,ct1,dtsc,dtsc1,ctsc,ctsc1,dtdep,ctdep,suma,codfcdebaza,DtNrCm,CtNrCm)
 SELECT d.nrdoc AS nrdoc
 ,2 AS funct
 ,d.CC1 AS Dt
 ,2141 AS CT
 ,d.dt1 AS DT1
 ,d.ct1 AS CT1
 ,NVL(d.cc1sc,1325) AS DTSC
 ,d.cc1sc1 AS DTSC1
 ,d.dtsc AS CTSC
 ,d.ctsc1 AS CTSC1
 ,NVL(d.cc1dep,m.dtdep) AS DTDEP
 ,NVL(d.cc1dep,m.dtdep) AS CTDEP
 ,d.suma*(1+Un$functs.tva(d.dtsc)) AS SUMA,-d.rrowid AS CODFCDEBAZA
 ,vNrCM_U AS DtNrCm, vNrCM_U AS CtNrCm
  FROM VMDB_ST201DE d,VMDB_ST201M m
  WHERE d.nrdoc=vNrdoc AND d.nrdoc=m.nrdoc
    AND (d.ct=2132 AND d.dt=2131) AND NVL(d.DT,0)<>0
    AND  Un$functs.CHECKMBPUZUR(d.dt,d.ct,d.I_PRET)=2;

-- ниже 100L
 INSERT INTO VMDB_CMI (nrdoc, funct,
             dt,dt1,dtsc,dtdep,dtsc1,
             ct,ct1,ctsc,ctdep,ctsc1
             ,suma,codfcdebaza,cant
             ,DtNrCm,CtNrCm)
 SELECT
  d.nrdoc AS nrdoc
 ,3 AS funct
 ,d.CC1 AS Dt
 ,d.dt1 AS DT1
 ,NVL(d.cc1sc,1325) AS DTSC
 ,NVL(d.cc1dep,m.dtdep) AS DTDEP
 ,d.cc1sc1 AS DTSC1
 ,d.CT
 ,d.ct1
 ,d.dtsc
 ,NVL(d.ctdep,m.dtdep)
 ,d.dtsc1
 ,d.suma*(1+Un$functs.tva(d.dtsc))
 ,-d.rrowid AS CODFCDEBAZA
 ,d.cant
 ,vNrCM_U AS DtNrCm
 ,vNrCM_U AS CtNrCm
 FROM VMDB_ST201DE d, VMDB_ST201M m
 WHERE d.nrdoc=vNrdoc AND d.nrdoc=m.nrdoc
   AND (d.ct=2132 AND d.dt=2131)
   AND NVL(d.DT,0)<>0
   AND  Un$functs.CHECKMBPUZUR(d.dt,d.ct,d.i_pret)=1;
 END IF;

 END;
--------------------------------------------------------------------------------
--- Приход товара - суммовой в продажных ценах
  PROCEDURE Prihod_prod_price (vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData   DATE;
 vsql    LONG;
 vDtDep  NUMBER;
 vCtDep  NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;

BEGIN
 SELECT datamanual, Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND i_pret IS NULL AND ROWNUM=1),0)
   INTO vCnt FROM dual;
  IF vCnt <> 0 THEN
   RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии суммы в продажных ценах!'||CHR(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  ELSE
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(suma) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2171
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 2171, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_U, vNrCM_U);
   END LOOP;
 END IF;

 IF (vNrset=2 OR vNrset=3)  THEN
    -- Sebestoimosti -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2171
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, 2171, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- NDS ---------------
 IF vTipTVA=-1 THEN
    SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
    SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm)
    VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F);
  ELSE
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
       , SUM(sumavalct) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2171
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
 END IF;
  --- NDS v tovare ----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(i_pret-(i_pret/(1+NVL(codtva,CLCSTRINGX_2)/100))) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2171
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 2171, c.sc, vDtdep, 8251, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   -- Natsenka ------------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(i_pret)-SUM(i_pret-(i_pret/(1+NVL(codtva,CLCSTRINGX_2)/100)))-SUM(sumagaap) suma
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=2171
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, 2171, c.sc, vDtdep, 8211, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;

    -- Sebestoimosti ne 2171-----------
   FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
           FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt<>2171) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
   --- NDS ne 2171----------
  IF vTipTVA<>-1 THEN
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt<>2171) LOOP
    INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
    VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
   END LOOP;
  END IF;
  END IF;
 END IF;
---------------
END Prihod_prod_price;
--------------------------------------------------------------------------------
--- Приход в кассу - sysfid 1150
PROCEDURE Casa_Prihod_gfc (vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
BEGIN
 SELECT Get_Nrset(nrset)INTO vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;
 IF (vNrset=2 OR vNrset=3)  THEN
 Gfc_Util.gfc201(vNrdoc
  ,vFunct=>1
  ,vCod=>'d.rrowid'
  ,vDTdep=>'m.dtdep'
  ,vCtDep=>'nvl(d.dtdep,d.ctdep)'
  ,vSuma=>'(d.suma-nvl(d.sumagaap,0)-NVL(D.SUMAVALCT,0))'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
 );
 Gfc_Util.gfc201
  (vNrdoc
  ,vCodFcDeBaza=>'d.rrowid'
  ,vDt=>2254
 -- ,vCt=>'6112'
  ,vDtsc=>1250
  ,vDtDep=>1328
  ,vCtDep=>'nvl(d.dtdep,d.ctdep)'
  ,vCant=>''
  ,vSuma=>'d.sumagaap'
  ,vWhere_Before=>' and nvl(d.sumagaap,0)<>0'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
 );
 Gfc_Util.gfc201
  (vNrdoc
  ,vCodFcDeBaza=>'d.rrowid'
  ,vFunct=>2
  ,vCt=>'5342'
  ,vDtDep=>'m.DtDep'
  ,vCtDep=>'nvl(d.dtdep,d.ctdep)'
  ,vCant=>''
  ,vSuma=>'d.sumaVALCT'
  ,vWhere_Before=>' and nvl(d.sumavalct,0)<>0'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
 );
 END IF;

 IF (vNrset=1 OR vNrset=3)  THEN
 Gfc_Util.gfc201(vNrdoc
  ,vFunct=>1
  ,vDTdep=>'m.dtdep'
  ,vCtDep=>'nvl(d.dtdep,d.ctdep)'
  ,vSuma=>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
 );
 END IF;
---------------
END Casa_Prihod_gfc;
------------------------------------------------------------------------------------------------------------------
PROCEDURE prodaja_cost(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);   
 vData  DATE; 
 vDtDep NUMBER;  
 vCtDep NUMBER;  
 vDt    NUMBER;  
 vCt    NUMBER;
 vDtsc0 NUMBER;
 vCnt   NUMBER:=0; 
 vTipTVA INT;
 vCodFC  NUMBER;
 vSuma_Total number;
BEGIN
 /*SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN*/
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vCod=>'d.rrowid'
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>'m.dtsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vCant=>''
 ,vSuma=>'d.sumagaap'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
 );
 
 ---tva
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vCodfcdebaza=>'d.rrowid'
 ,vDt=>'m.Dt'
 ,vCt=>'5342'
 ,vDtsc=>'m.dtsc'
 ,vCtsc=>''
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>''
 ,vCant=>''
 ,vSuma=>'d.sumavalct'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
 );
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'un$functs.GETCONT_VINZ7(M.Ct)'
 ,vCt=>'d.Ct'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCant=>'d.cant'
 ,vSuma=>'d.sumagaap'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
 );
 --END IF;  -- закончились проводки по 1
  --------
END prodaja_cost;
------------------------------------------------------------------------------------------------------------------

PROCEDURE Prihod2174_GFC(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vDatadoc   DATE; vDateCurr DATE; vCnt INT; vN2 INT;
-- vPret VARCHAR2(150):=' decode(nvl(v.cant,0),0,v.sumagaap,round(v.sumagaap/v.cant,2)) ';
 vSQL1 LONG;
BEGIN
SELECT Get_Nrset(nrset) INTO vNrset FROM TMDB_DOCS WHERE cod=vNrdoc;
SELECT Get_Env('UN$DATAUNIV'), Get_Env('UN$DATADOC') INTO vDateCurr, vDatadoc FROM dual;

IF Yparams.vUse_U AND (vNrset=1 OR vNrset=3) THEN
--   vPret:='v.pret';
   Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
     ,vSuma=>'d.suma', vDtNrCM =>vNrCM_U, vCtNrCM =>vNrCM_U);
END IF;
--- FO
IF (vNrset=2 OR vNrset=3) THEN
 IF Yparams.vTip_Retail=1 THEN
-- Osnovnie provodki
  Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F);
 ELSIF Yparams.vTip_Retail=2 THEN
   Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)'
     ,vDtSc=>'Ybon_Docs.decode_sc(d.dtsc, nvl(d.dt,m.dt))'
     ,vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F);
 END IF;
-- NDS
   Gfc_Util.gfc201(vNrdoc, vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    ,vDtDep=>'', vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
    ,vTVACont1Recognition=>FALSE );
END IF;
end;


/*PROCEDURE Prihod2174_GFC(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vDatadoc   DATE; vDateCurr DATE; vCnt INT; vN2 INT;
-- vPret VARCHAR2(150):=' decode(nvl(v.cant,0),0,v.sumagaap,round(v.sumagaap/v.cant,2)) ';
 vSQL1 LONG;
BEGIN
SELECT Get_Nrset(nrset) INTO vNrset FROM TMDB_DOCS WHERE cod=vNrdoc;
SELECT Get_Env('UN$DATAUNIV'), Get_Env('UN$DATADOC') INTO vDateCurr, vDatadoc FROM dual;

IF Yparams.vUse_U AND (vNrset=1 OR vNrset=3) THEN
--   vPret:='v.pret';
   Gfc_Util.gfc201(vNrdoc, vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
     ,vSuma=>'d.suma', vDtNrCM =>vNrCM_U, vCtNrCM =>vNrCM_U);
END IF;
--- FO
IF (vNrset=2 OR vNrset=3) THEN
 IF Yparams.vTip_Retail=1 THEN
-- Osnovnie provodki
  Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F);
 ELSIF Yparams.vTip_Retail=2 THEN
   Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)'
     ,vDtSc=>'Ybon_Docs.decode_sc(d.dtsc, nvl(d.dt,m.dt))'
     ,vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F);
 END IF;
-- NDS
   Gfc_Util.gfc201(vNrdoc, vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
    ,vDtDep=>'', vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
    ,vTVACont1Recognition=>FALSE );
END IF;
end;*/
--------------------------------------------------------------------------------
PROCEDURE Casa_1221_GFC (vNrdoc NUMBER) is 
vDep int; 
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
begin
 select ctdep into vDep from vmdb_st201m where nrdoc=vNrdoc;
 if vDep is null then
  msg('Выберите торговую точку!');
 end if; 
---
 select get_nrset(nrset) into vNrset from tmdb_docs where cod=vNrdoc;
 
  if (vNrset=1 or vNrset=3) then
   ---venit
   Gfc_Util.gfc201(vNrdoc=>vNrdoc, vDt=>'m.Dt', vDtsc=>yparams.vSC_Flux_vinz, vDtDep=>'m.CtDep'
   ,vCt=>'un$functs.getcont_vinz6(m.Ct)', vCtsc=>'d.dtsc', vCtDep=>'m.CtDep'
   ,vCant=>'d.cant', vSuma=>'d.suma', vDtNrCm=>vNrCM_U, vCtNrCm=>vNrCM_U);
  -- sinecost
   Gfc_Util.gfc201(vNrdoc=>vNrdoc, vDt=>'un$functs.getcont_vinz7(m.Ct)', vDtsc=>'d.dtsc',vDtDep=>'nvl(d.ctdep,m.CtDep)'
   ,vCt=>'m.Ct', vCtsc=>'d.dtsc', vCtDep=>'nvl(d.ctdep,m.CtDep)'
   ,vCant=>'d.cant', vSuma=>'d.sumagaap', vDtNrCm=>vNrCM_U, vCtNrCm=>vNrCM_U);
  end if; 

 if (vNrset=2 or vNrset=3) then
    ---venit
   Gfc_Util.gfc201(vNrdoc=>vNrdoc, vCod=>'d.rrowid', vDt=>'m.Dt', vDtsc=>yparams.vSC_Flux_vinz, vDtDep=>'nvl(m.dtdep,m.CtDep)' , vDtsc1=>'m.dtsc1'
   ,vCt=>'un$functs.getcont_vinz6(nvl(m.Ct,d.dt))', vCtsc=>'d.dtsc', vCtDep=>'m.CtDep'
   ,vCant=>'d.cant', vSuma=>'d.sumagaap', vDtNrCm=>vNrCM_F, vCtNrCm=>vNrCM_F, vWhere=>'');
    -- NDS
   Gfc_Util.gfc201(vNrdoc, vDt=>'m.dt', vDtsc=>yparams.vSC_Flux_vinz, vDtDep=>'nvl(m.dtdep,m.CtDep)' 
   ,vCt=>'5342', vCt1=>'Un$functs.tva_cont1(d.dtsc,m.ctdep,'||vNrdoc||')', vCtDep=>''
   ,vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid'
   ,vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F, vTVACont1Recognition=>FALSE, vWhere=>'');
   --sinecost
   Gfc_Util.gfc201(vNrdoc=>vNrdoc, vDt=>'un$functs.getcont_vinz7(nvl(m.Ct,d.dt))', vDtsc=>'d.dtsc',vDtDep=>'nvl(d.ctdep,m.CtDep)'
   ,vCt=>'nvl(m.Ct,d.dt)', vCtsc=>'d.dtsc', vCtDep=>'nvl(d.ctdep,m.CtDep)'
   ,vCant=>'d.cant', vSuma=>'d.sumagaap', vDtNrCm=>vNrCM_F, vCtNrCm=>vNrCM_F);
 end if;
end;
-------------------------------------------------------------------------------------
PROCEDURE Vozvrat_postav_TTN_GFC(vNrdoc NUMBER) IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;

BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'m.Ct'
    ,vCt1    =>'decode('||vNrset||',1,1,null)'
    ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
    ,vCtDep  =>'m.ctdep'
    ,vCant   =>'-d.cant'
    ,vSuma   =>'-d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
 ,vDtData =>'d.dtdata'
    ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
 ,vCtNrdoc=>'m.nrdoc'
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN
  IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
  -- Osnovnie provodki
   Gfc_Util.gfc201(vNrdoc, vCod=>'d.rrowid'
     , vDt=>'un$functs.GETCONT_VINZ7(nvl(d.dt,m.dt))' 
     , vCt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
     , vCtDep=>'nvl(d.dtdep,m.dtdep)'
     , vCtSc=>'d.dtsc'
  , vDtData =>'d.dtdata', vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  , vCtNrdoc=>'m.nrdoc'
  , vSuma=>'-d.sumagaap', vCant=>'-d.cant'
     , vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F, vWhere=>'');
  END IF;
 END IF;
END Vozvrat_postav_TTN_GFC;
--------------------------------------------------------------------------------
-- Возврат товара поставщику по Налоговой Накладной с использованием промежуточного счета 8521 - заполнение
PROCEDURE Vozvrat_postav_NN_Fill (vNrdoc NUMBER) IS
vDep INT; vDepTTN INT; vNrTTN NUMBER; vCnt INT; vSysFid INT;
BEGIN
SELECT ctdep, ctnrdoc INTO vDep, vNrTTN FROM vmdb_st201m WHERE nrdoc=vNrdoc;
--
IF NVL(vDep,0) = 0 THEN
 msg(lng('Alegeti furnizorul!','Выберите поставщика!!!'));
ELSE
 IF NVL(vNrTTN,0) = 0 THEN
  msg(lng('Introduceti Nr electronic a Facturei de Expeditie!','Введите электронный номер ТТН!!!'));
 ELSE
  SELECT COUNT(*), MIN(ctdep) INTO vCnt, vDepTTN FROM vmdb_st201m WHERE nrdoc=vNrTTN;
  IF vCnt=0 THEN
   msg(lng('Documentul '||vNrTTN||' nu exista!!!','Документ с № '||vNrTTN||' не найден!!!'));
  END IF;
   SELECT MIN(sysfid) INTO vSysFid FROM TMDB_DOCS WHERE cod=vNrTTN;
   IF NVL(vSysFid,0)<>1260 THEN
    msg(lng('Nu corespunde tipul documentului!!!','Не соответствует тип документа!!!'));
   END IF;
 END IF;
END IF;

IF NVL(vDepTTN,0)<>NVL(vDep,0) THEN
 msg(lng('Furnizorul nu coincide cu furnizorul din FE!!!','Поставщик не совпадает с поставщиком из ТТН!!!'));
END IF;
--
IF vNrdoc=NVL(vNrTTN,0) THEN
 msg(lng('Nr FE coincide cu Nr doc curent!!!','Указанный № док-та по ТТН совпадает с текущим документом!!!'));
END IF;
SELECT COUNT(*) INTO vCnt FROM vmdb_st201d WHERE nrdoc=vNrdoc AND ctnrdoc=vNrTTN;
IF vCnt>0 THEN
 msg(lng('Datele din documentul '||vNrTTN||' deja sunt introduse in document curent!!!','Данные по документу '||vNrTTN||' уже внесены в текущий документ!!!'));
END IF;
--
INSERT INTO vmdb_st201d (nrdoc, dt, dtsc, cant, suma, sumagaap, sumavalct, ctnrdoc)
SELECT vNrdoc, dt, dtsc, cant, suma, sumagaap, sumavalct, nrdoc
FROM vmdb_st201d WHERE nrdoc=vNrTTN AND Nrdoc<>vNrdoc;

END Vozvrat_postav_NN_Fill;
--------------------------------------------------------------------------------
--- Возврат товара поставщику по Налоговой Накладной с использованием промежуточного счета 8521 - проводки
PROCEDURE Vozvrat_postav_NN_GFC (vNrdoc NUMBER) IS
 vNrset   NUMBER;
 vNrCM_F  INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U  INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;

BEGIN
 SELECT datamanual, Get_Nrset(nrset) INTO vData, vNrset FROM VMDB_DOCS WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
    INSERT INTO vmdb_cmi (nrdoc, dt, dtdep, dtnrdoc, dtnrcm, ct, ct1, ctdep, ctnrcm, suma)
 SELECT vNrdoc, m.dt, m.ctdep, d.ctnrdoc, vNrCM_U, m.ct, m.ct1, m.ctdep, vNrCM_U, -SUM(d.suma)
 FROM vmdb_st201d d, vmdb_st201m m WHERE m.nrdoc=vNrdoc AND m.nrdoc=d.nrdoc
 GROUP BY m.dt, m.ctdep, d.ctnrdoc, m.ct, m.ct1;
 END IF;

 IF (vNrset=2 OR vNrset=3) THEN

    INSERT INTO vmdb_cmi (nrdoc, dt, dtdep, dtnrdoc, dtnrcm, ct, ct1, ctdep, ctnrcm, suma)
    SELECT m.nrdoc, 2211, m.ctdep, d.ctnrdoc, vNrCM_F, m.ct, m.ct1, m.ctdep, vNrCM_F, -d.FTVA
 FROM vmdb_st201m m,
 (SELECT d.nrdoc, d.ctnrdoc, d.CLCSTRINGX_2 cod_TVA, SUM(d.sumagaap) FTVA, SUM(d.sumavalct) TVA
    FROM YBON_VMDB_ST201D_TVR d WHERE nrdoc=vNrdoc
    GROUP BY d.nrdoc, d.ctnrdoc, d.CLCSTRINGX_2) d
 WHERE m.nrdoc=d.nrdoc;
 -- NDS
    INSERT INTO vmdb_cmi (nrdoc, dt, dt1, dtnrcm, ct, ct1, ctdep, ctnrcm, suma, sumagaap)
    SELECT m.nrdoc, 5342 dt, DECODE(cod_TVA,NULL,92,0,91,cod_tva) dt1,
 vNrCM_F, m.ct, m.ct1, m.ctdep, vNrCM_F, -d.TVA, -d.FTVA
 FROM vmdb_st201m m,
 (SELECT d.nrdoc, d.ctnrdoc, d.CLCSTRINGX_2 cod_TVA, SUM(d.sumagaap) FTVA, SUM(d.sumavalct) TVA
    FROM YBON_VMDB_ST201D_TVR d WHERE nrdoc=vNrdoc
    GROUP BY d.nrdoc, d.ctnrdoc, d.CLCSTRINGX_2) d
 WHERE m.nrdoc=d.nrdoc;
 
 END IF;
END Vozvrat_postav_NN_GFC;
--------------------------------------------------------------------------------
--- Приход товара - основные проводки
  PROCEDURE Prihod_GFC_12009(vNrdoc NUMBER) IS
 vNrset  NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData   DATE;
 vsql    LONG;
 vDtDep  NUMBER;
 vCtDep  NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;
BEGIN
 SELECT datamanual, Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 IF (vNrset=1 OR vNrset=3) THEN
  Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'nvl(d.dt,m.dt)'
  ,vCt     =>'nvl(m.Ct,d.Ct)'
  ,vCt1    =>'decode('||vNrset||',1,1,null)'
  ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'d.cant'
  ,vSuma   =>'d.suma'
  ,vDtNrCm=>vNrCM_U
  ,vCtNrCm=>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtStrSc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vCtCant1=>''
  ,vWhere=>''
--  , vDebug=>true
  );
 END IF;

    IF (vNrset=2 OR vNrset=3)  THEN
      IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
    -- check_prices;
     -- Osnovnie provodki
      Gfc_Util.gfc201(vNrdoc,vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)',vSuma=>'d.sumagaap',
                      vCod=>'d.rrowid',vDtNrCM =>vNrCM_F,vCtNrCM =>vNrCM_F,vWhere=>'');
     --NDS-------------------------------------------------------------------------------------
       Gfc_Util.gfc201(vNrdoc, vDt=>'5342', vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
        ,vDtDep=>'', vSuma=>'d.sumavalct', vCant=>'', vCodFCdeBaza=>'d.rrowid', vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F
        ,vTVACont1Recognition=>FALSE,vWhere=>'' );
     ---storno 521---------------------------------------------------------------------------storno 521
         Gfc_Util.gfc201
  (vNrdoc
  ,vDt     =>'m.ct'
  ,vCt     =>'6224'
  ,vDtDep  =>'m.ctdep'
  ,vCtDep  =>'m.dtdep'
  ,vCant   =>''
  ,vSuma   =>'d.sumagaap'
  ,vCtSc   =>'137807'
  ,vDtNrCm=>vNrCM_F
  ,vCtNrCm=>vNrCM_F
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vDtStrSc=>'nvl(d.dtnrdoc,d.nrdoc)'
  ,vCtCant1=>''
  ,vWhere=>'');
    --storno NDS-------------------------------------------------------------------------------------
       Gfc_Util.gfc201
       (vNrdoc
       ,vDt=>'5342'
       ,vCt=>'m.ct'
       ,vDt1=>'Un$functs.TVA_CONT1(d.dtsc,m.ctdep,'||vNrdoc||')'
       ,vDtDep=>''
       ,vCtDep  =>'m.ctdep'
       ,vSuma=>'-d.sumavalct'
       ,vSumagaap=>''
       ,vCant=>''
       ,vCodFCdeBaza=>null
       ,vDtNrCM =>vNrCM_F
       ,vCtNrCM =>vNrCM_F
       ,vTVACont1Recognition=>FALSE
       ,vWhere=>'' );

     ELSIF Yparams.vTip_Retail=2 THEN --summovoi

      SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
       INTO vCnt FROM dual;
      IF vCnt <> 0 THEN
       RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
          'Укажите продажные цены на товар с кодом - '||vCnt);
      ELSE
       SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
       SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

       -- Sebestoimosti -----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(sumagaap) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2171
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, 2171, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
       -- NDS ---------------
      IF vTipTVA=-1 THEN
        SELECT SUM(sumagaap) INTO  vSumaGaap FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc;
        SELECT rrowid INTO vCodFCdeBaza FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND ROWNUM=1;
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, sumagaap, dtnrcm, ctnrcm)
        VALUES (vNrdoc, vCodFCdeBaza, 5342, 92, vCt, vCtdep, 0, vSumaGaap, vNrCM_F, vNrCM_F);
      ELSE
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1
           , SUM(sumavalct) suma
           , MIN(rrowid) rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2171
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
      END IF;
      --- NDS v tovare ----------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_6) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2171
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, 2171, c.sc, vDtdep, 8251, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;
       -- Natsenka ------------
       FOR c IN (SELECT DECODE(NVL(CLCSTRINGX_2,0),0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
           , SUM(clcsumax_5)-SUM(clcsumax_6)-SUM(sumagaap) suma
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2171
                  GROUP BY CLCSTRINGX_2
                  ) LOOP
        INSERT INTO VMDB_CMI (nrdoc, dt, dtsc, dtdep, ct, ctsc, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, 2171, c.sc, vDtdep, 8211, c.sc, vDtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

        -- Sebestoimosti 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt=2172) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, c.dt, DECODE(Un$functs.tva(c.sc),0.2,vScTVRB20proc,0.08,vScTVRB8proc,vScTVRB0proc),
               vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

        -- Sebestoimosti ne 2171 i ne 2172-----------
       FOR c IN (SELECT sumagaap suma, dt, dtsc sc, rrowid
               FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt NOT IN (2171,2172)) LOOP
        INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (c.rrowid, vNrdoc, c.dt, c.sc, vDtdep, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
       END LOOP;

       --- NDS ne 2171----------
       IF vTipTVA<>-1 THEN
       FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,91,8,8,20,20,'',92) dt1, sumavalct suma, dt, dtsc sc, rrowid
                  FROM YBON_VMDB_ST201D_TVR
                  WHERE nrdoc=vNrdoc AND dt<>2171) LOOP
        INSERT INTO VMDB_CMI (nrdoc, codfcdebaza, dt, dt1, ct, ctdep, suma, dtnrcm, ctnrcm)
        VALUES (vNrdoc, c.rrowid, 5342, c.dt1, vCt, vCtdep, c.suma, vNrCM_F, vNrCM_F);
        END LOOP;
       END IF;
      END IF;
     END IF;
    END IF;
    ---------------
END Prihod_GFC_12009;
--------------------------------------------------------------------------------
procedure income_full_gfc(p_nrdoc number) is
v_cnt int;
v_datamanual date;
begin
  select datamanual into v_datamanual from tmdb_docs where cod = p_nrdoc;
  -- 1
  check_rights(p_nrdoc,'SYSFID_GFC');
  --
  select count(*) into v_cnt from vmdb01m_vinz where cod = p_nrdoc;
  if v_cnt = 0 then
    insert into vmdb01m_vinz(cod,SCOMMENT) values (p_nrdoc,' ');
  end if;
  --
  -- 2
  Prihod_GFC(p_nrdoc);
  --
  -- 3
  --zapolnenie tablitsi ylin_prices - u4etnaja i prodajnaja tsena
  merge into ylin_prices d
  using
  (
    select v_datamanual data, m.dtdep sc_shop, d.dtsc sc_tov,
    (select round(pret,2) from vmdb_cmi where nrdoc=p_nrdoc and get_nrset(dtnrcm)=1 and dtsc=d.dtsc) pret_u,
    (select round(pret,2) from vmdb_cmi where nrdoc=p_nrdoc and get_nrset(dtnrcm)=2 and dtsc=d.dtsc) pret_f, p_nrdoc nrdoc
    from vmdb_st201d d, vmdb_st201m m where d.nrdoc=m.nrdoc and m.nrdoc=p_nrdoc
  ) s
  on(d.sc_tov = s.sc_tov and d.sc_shop = s.sc_shop and d.data = s.data )
  when matched then
  update
  set pret_u = s.pret_u, pret_f = s.pret_f, nrdoc_from = s.nrdoc
  when not matched then
  insert(data, sc_shop, sc_tov, pret_u, pret_f, nrdoc_from)
  values(s.data, s.sc_shop, s.sc_tov, s.pret_u, s.pret_f, s.nrdoc);
  --
  -- 4
  ylin_docs.obnov_price_iz1209gfc(p_nrdoc);
end;
--------------------------------------------------------------------------------
procedure check_datadoc_export_1C(p_nrdoc number) is
 v_data     date;
 v_data_max date;
begin
  v_data := abm_util.data_by_nrdoc(p_nrdoc);
  
  begin
    select to_date(p.value, 'dd.mm.yyyy')
    into v_data_max
    from a$adp$v p
    where obj_id = (select obj_id from a$adm where  name0 = 'Docs')
    and  lower( name ) = lower( 'MaxData_Export1C' );
  exception when others then
    v_data_max := to_date('31.12.3000');
  end;
  
  if v_data >= v_data_max then
    msg(lng('Nu se permite creare acestor documente cu data mai mare decit '
          , 'Запрещено создание данного типа документов с датой больше ')
          ||to_char(v_data_max, 'dd.mm.yyyy'));
  end if;
end;
--------------------------------------------------------------------------------
procedure price_by_partition(p_nrdoc number) is
 v_data DATE;
 v_src INT;
 db_sc varchar2(200);
 db_cant varchar2(200);
 check_cant number;
 dt number;
 maxpr number;
begin
  for i in 
  (
  select count(dtsc) cnt,dtsc 
  from YBON_VMDB_ST201D_TVR 
  where nrdoc=p_nrdoc 
  group by dtsc
  ) loop
    if i.cnt>1 then 
    db_sc:=db_sc||i.dtsc||' ';
    end if;
  end loop;
  
  if db_sc is not null then
    msg('Необходимо сгруппировать данные по товарам: '||db_sc);
  end if;
  
  v_data := abm_util.data_by_nrdoc(p_nrdoc);
  
  SELECT m.dt.dep 
  INTO v_src 
  FROM TMDB_ST201M m 
  WHERE cod=p_nrdoc;
  
  un$sld.make(v_data,1,'ABCDEFGI12','217 2114',pDep=>v_src);
  /*
  for i in (select sum(cant) cnt,dtsc from YBON_VMDB_ST201D_TVR where nrdoc=:nrdoc group by dtsc) loop
  select sum(cant) into check_cant from vsld1 where  sc=i.dtsc and cant>0 and data is not null;
  if i.cnt>check_cant then 
  db_cant:=db_cant||i.dtsc||' ';
  end if;
  end loop;
  if db_cant is not null then
  msg('Cantitatea introdusa pentru produsul '||db_cant||' depaseste cantitatea primita !');
  end if;*/
  
  for i in 
  (
  select b.sc,a.cant,b.cant cantsold,a.dtdata,
  /*(select pretv2 from vpr_prlist_tvr t where t.sc=b.sc and b.data between data and dataf)*/ 
  round(price*(1+un$functs.tva(a.dtsc)),2)pprice,b.data,a.rrowid
  from YBON_VMDB_ST201D_TVR a,
    (
    select * 
    from 
      (
      select sc , price , data ,cant ,nrdoc, row_number() over (partition by sc order by sc) tf from vsld1 
      where data is not null and cant>0 and dep=v_src 
      group by (sc, price , data ,cant,nrdoc) 
      having cant >0 
      order by 1 ,3 asc , 2 desc
      )m
    where m.tf=1
    )  b 
  where b.sc=a.dtsc and b.cant>0 /*and a.dtdata is null */
  and b.data = 
    (
    SELECT min(c.data) 
    FROM vsld1 c 
    where c.sc=a.dtsc and c.cant>0 and c.data is not null /*and c.strsc is not null and c.strsc <>0*/ 
    and c.dep=v_src
    ) 
  and a.nrdoc=p_nrdoc
  ) loop
    select count(data) into dt 
    from vsld1 where sc=i.sc and data=i.data /*and strsc is not null and strsc <>0*/ and cant>0 and dep=v_src;
    
    /*if dt>1 then 
    select cant,maxpr into i.cantsold,i.price from vsld1 where sc=i.sc and data=i.data and strsc is not null and strsc <>0 and cant>0 and price=maxpr;
    end if;*/
    /*checking if doc cant > sold cant*/
    
    if i.cant>i.cantsold then 
      checking(i.sc,i.cant,i.cantsold,i.pprice,i.dtdata,i.data,i.rrowid,p_nrdoc,dt,v_src);
    else
      /*update all, data,dtnrdoc,pret*/
      update YBON_VMDB_ST201D_TVR a 
      set a.dtdata=i.data
      where a.nrdoc=p_nrdoc and a.rrowid=i.rrowid;
      
      update YBON_VMDB_ST201D_TVR a set 
      a.dtnrdoc=(SELECT nvl(b.strsc,b.nrdoc) FROM vsld1 b where b.sc=a.dtsc and b.cant>0 and /*b.strsc is not null and b.strsc <>0 and*/ b.data=a.dtdata and b.dep=v_src),
      a.pret=i.pprice,
      a.dtdep=v_src/*(SELECT b.dep FROM vsld1 b where b.sc=a.dtsc and b.cant>0 and b.data=a.dtdata and b.strsc is not null and b.strsc <>0)*/
      --,a.clcdtdept=(SELECT DENUMIREA FROM VMS_UNIVERS u,vsld1 v WHERE u.cod=v.dep and v.dep=v_src and v.sc=a.dtsc and v.data=a.dtdata and v.nrdoc is not null and v.cant>0 and v.strsc is not null and v.strsc <>0)
      where a.nrdoc=p_nrdoc and a.rrowid=i.rrowid;
    end if;
  end loop;
end;
--------------------------------------------------------------------------------
procedure price_by_partition_act_price(p_nrdoc number) is
 v_data DATE;
 v_src INT;
 db_sc varchar2(200);
 db_cant varchar2(200);
 check_cant number;
 dt number;
 maxpr number;
----------------------------
PROCEDURE checking(ssc number,cantdoc number,cantsold number,mprice number,ddtdata date,ddata date,oldrrowid number,nrdocc number,dt number,v_src number) is
newid number;
cant1 number;
cant2 number;
pret1 number;
data1 date;
check_data date;
maxprice number;
newdt number;
v_check int;
begin
  if cantdoc > cantsold then
    /*update old record when need*/
    if ddtdata is null then
      update YBON_VMDB_ST201D_TVR a 
      set a.dtdata=ddata
      where a.nrdoc=nrdocc and a.rrowid=oldrrowid;
      
      update YBON_VMDB_ST201D_TVR a set 
      a.dtnrdoc= 
        (
        SELECT nvl(min(t.strsc),min(t.nrdoc))
        FROM 
          (
          select max(b.price) over(partition by sc,data,dep) max_price
          , b.*
          from vsld1 b
          ) t
        where t.price = t.max_price
        and t.sc=a.dtsc and t.cant>0 and t.data=a.dtdata and t.dep=v_src
        ),
      a.pret=mprice,
      a.dtdep=v_src
      --,a.clcdtdept=(SELECT distinct(DENUMIREA) FROM VMS_UNIVERS u,vsld1 v WHERE u.cod=v_src and v.sc=a.dtsc and v.data=a.dtdata and v.nrdoc is not null and v.cant>0 and v.strsc is not null and v.strsc <>0)
      where a.nrdoc=nrdocc and a.rrowid=oldrrowid;
    end if;

    update YBON_VMDB_ST201D_TVR s 
    set s.cant = cantsold 
    where  s.nrdoc=nrdocc and s.rrowid=oldrrowid;
    
    /*copy*/
    SELECT max(f.rrowid)+1 INTO newid from YBON_VMDB_ST201D_TVR f;
    
    INSERT INTO YBON_VMDB_ST201D_TVR m (m.Nrdoc,m.dt,m.dtsc,m.dtnrdoc,m.cant/*,m.clcdtsct*/,m.pret,m.dtdata,m.clcstringx_1,m.rrowid)
    (select nrdocc,r.dt,r.dtsc,null,(cantdoc-cantsold)cant/*,r.clcdtsct*/,null,null,r.clcstringx_1,newid from YBON_VMDB_ST201D_TVR r where r.nrdoc=nrdocc and r.rrowid=oldrrowid);
    
    /*update new record dtdata*/
    -----------------------
    if dt>1 then
      update YBON_VMDB_ST201D_TVR s 
      set s.dtdata=ddata
      where s.nrdoc=nrdocc and s.rrowid=newid;
      
      /*update new record ,pret*/      
      update YBON_VMDB_ST201D_TVR s 
      set s.pret=mprice
      where s.nrdoc=nrdocc and s.rrowid=newid;

      update YBON_VMDB_ST201D_TVR s 
      set s.dtnrdoc=
      (
        SELECT nvl(min(t.strsc),min(t.nrdoc))
        FROM 
          (
          select max(b.price) over(partition by sc,data,dep) max_price
          , b.*
          from vsld1 b
          ) t
        where t.price = t.max_price
        and t.sc=s.dtsc and t.cant>0 and t.data=s.dtdata and t.dep=v_src
        ),
      s.dtdep=v_src
      --,s.clcdtdept=(SELECT distinct(nvl(DENUMIREA,null)) FROM VMS_UNIVERS u,vsld1 v WHERE u.cod=v_src and v.sc=s.dtsc and v.data=s.dtdata and v.nrdoc is not null and v.cant>0 and v.strsc is not null and v.strsc <>0 and round(v.price*(1+un$functs.tva(s.dtsc)),2)=maxprice)
      where s.nrdoc=nrdocc and s.rrowid=newid;
      
      newdt:=dt-1;
    -------------------
    else 
      update YBON_VMDB_ST201D_TVR s 
      set s.dtdata=(SELECT nvl(min(c.data),null) FROM vsld1 c where c.sc=s.dtsc and c.cant>0 and c.data is not null and c.data>ddata and c.strsc is not null and c.strsc <>0 and c.dep=v_src)
      where s.nrdoc=nrdocc and s.rrowid=newid;
      
      /*update new record dtnrdoc,pret*/
      update YBON_VMDB_ST201D_TVR s 
      set s.dtnrdoc=
      (
        SELECT nvl(min(t.strsc),min(t.nrdoc))
        FROM 
          (
          select max(b.price) over(partition by sc,data,dep) max_price
          , b.*
          from vsld1 b
          ) t
        where t.price = t.max_price
        and t.sc=s.dtsc and t.cant>0 and t.data=s.dtdata and t.dep=v_src
        ),
      s.pret=mprice,
      s.dtdep=v_src
      --,s.clcdtdept=(SELECT nvl(DENUMIREA,null) FROM VMS_UNIVERS u,vsld1 v WHERE u.cod=v_src and v.sc=s.dtsc and v.data=s.dtdata and v.nrdoc is not null and v.cant>0 and v.strsc is not null and v.strsc <>0)
      where s.nrdoc=nrdocc and s.rrowid=newid;
      -----------------
    end if;

    select dtdata 
    into check_data 
    from YBON_VMDB_ST201D_TVR 
    where nrdoc=nrdocc and rrowid=newid;
    
    if check_data is not null then
      v_check := 1;
      begin
      select distinct a.cant,a.cant_b,a.pret,a.dtdata 
      into cant1,cant2,pret1,data1 
      from
        (
        select a.cant,b.cant cant_b,a.pret,a.dtdata
        , nvl(b.strsc,b.nrdoc) dtnrdoc
        --, nvl(min(t.strsc),min(t.nrdoc)) over(partition by a.rrowid,a.nrdoc,b.sc,a.pret,a.dtdata) min_dtnrdoc
        , min(b.strsc) over(partition by a.rrowid,a.nrdoc,b.sc,a.pret,a.dtdata) min_dtstrsc
        , min(b.nrdoc) over(partition by a.rrowid,a.nrdoc,b.sc,a.pret,a.dtdata) min_dtnrdoc
        from YBON_VMDB_ST201D_TVR a, vsld1 b 
        where a.rrowid=newid and a.nrdoc=nrdocc and b.sc=a.dtsc and b.cant>0
        and a.pret=mprice and a.dtdata=b.data 
        and a.dtdata=check_data and b.strsc is not null and b.strsc <>0
        ) a
      where nvl(min_dtstrsc, min_dtnrdoc) = dtnrdoc;
      exception when no_data_found then
        v_check := null;
      end;
      
      if cant1>cant2 and nvl(v_check, 0) = 1 then
        checking(ssc,cant1,cant2,pret1,data1,data1,newid,nrdocc,newdt,v_src);
      end if;
      
    end if;
  end if;
end;
----------------------------
begin
  for i in 
  (
  select count(dtsc) cnt,dtsc 
  from YBON_VMDB_ST201D_TVR 
  where nrdoc=p_nrdoc 
  group by dtsc
  ) loop
    if i.cnt>1 then 
    db_sc:=db_sc||i.dtsc||' ';
    end if;
  end loop;
    
  if db_sc is not null then
    msg('Необходимо сгруппировать данные по товарам: '||db_sc||','||p_nrdoc);
  end if;
  
  v_data := abm_util.data_by_nrdoc(p_nrdoc);
  
  SELECT m.dt.dep 
  INTO v_src 
  FROM TMDB_ST201M m 
  WHERE cod=p_nrdoc;
  
  un$sld.make(v_data,1,'ABCDEFGI12','217 2114',pDep=>v_src);
  /*
  for i in (select sum(cant) cnt,dtsc from YBON_VMDB_ST201D_TVR where nrdoc=:nrdoc group by dtsc) loop
  select sum(cant) into check_cant from vsld1 where  sc=i.dtsc and cant>0 and data is not null;
  if i.cnt>check_cant then 
  db_cant:=db_cant||i.dtsc||' ';
  end if;
  end loop;
  if db_cant is not null then
  msg('Cantitatea introdusa pentru produsul '||db_cant||' depaseste cantitatea primita !');
  end if;*/
  
  for i in 
  (
  select b.sc,a.cant,b.cant cantsold,a.dtdata,
  /*(select pretv2 from vpr_prlist_tvr t where t.sc=b.sc and b.data between data and dataf)*/ 
  --round(price*(1+un$functs.tva(a.dtsc)),2)pprice
  a.pret pprice
  ,b.data,a.rrowid
  from YBON_VMDB_ST201D_TVR a,
    (
    select * 
    from 
      (
      select sc , price , data ,cant ,nrdoc, row_number() over (partition by sc order by data) tf from vsld1 
      where data is not null and cant>0 and dep=v_src 
      group by (sc, price , data ,cant,nrdoc) 
      having cant >0 
      order by 1 ,3 asc , 2 desc
      )m
    where m.tf=1
    )  b 
  where b.sc=a.dtsc and b.cant>0 /*and a.dtdata is null */
  and b.data = 
    (
    SELECT min(c.data) 
    FROM vsld1 c 
    where c.sc=a.dtsc and c.cant>0 and c.data is not null /*and c.strsc is not null and c.strsc <>0*/ 
    and c.dep=v_src
    ) 
  and a.nrdoc=p_nrdoc
  ) loop
    select count(data) into dt 
    from vsld1 where sc=i.sc and data=i.data /*and strsc is not null and strsc <>0*/ and cant>0 and dep=v_src;
    
    /*if dt>1 then 
    select cant,maxpr into i.cantsold,i.price from vsld1 where sc=i.sc and data=i.data and strsc is not null and strsc <>0 and cant>0 and price=maxpr;
    end if;*/
    /*checking if doc cant > sold cant*/
    
    if i.cant>i.cantsold then 
      say('i.sc= '||i.sc||' ,i.cant = '||i.cant||' ,i.cantsold = '||i.cantsold||' ,i.pprice = '||i.pprice||' ,i.dtdata = '||to_char(i.dtdata, 'dd.mm.yy')||'
      , i.data ='||to_char(i.data, 'dd.mm.yy')||', i.rrowid = '||i.rrowid||' ,p_nrdoc = '||p_nrdoc||' ,dt = '||dt||' ,v_src = '||v_src);
        say(p_nrdoc);
      checking(i.sc,i.cant,i.cantsold,i.pprice,i.dtdata,i.data,i.rrowid,p_nrdoc,dt,v_src);
    else
      /*update all, data,dtnrdoc,pret*/
      update YBON_VMDB_ST201D_TVR a 
      set a.dtdata=i.data
      where a.nrdoc=p_nrdoc and a.rrowid=i.rrowid;
      
    say('i.pprice = '||i.pprice||' i.sc = '||i.sc||' i.rrowid = '||i.rrowid);
      update YBON_VMDB_ST201D_TVR a set 
      a.dtnrdoc=
        (
        SELECT nvl(min(t.strsc),min(t.nrdoc)) dtnrdoc
        FROM 
          (
          select max(b.price) over(partition by sc,data,dep) max_price
          , b.*
          from vsld1 b
          ) t
        where t.price = t.max_price
        and t.sc=a.dtsc and t.cant>0 and t.data=a.dtdata and t.dep=v_src
        ),
      a.pret=i.pprice,
      a.dtdep=v_src/*(SELECT b.dep FROM vsld1 b where b.sc=a.dtsc and b.cant>0 and b.data=a.dtdata and b.strsc is not null and b.strsc <>0)*/
      --,a.clcdtdept=(SELECT DENUMIREA FROM VMS_UNIVERS u,vsld1 v WHERE u.cod=v.dep and v.dep=v_src and v.sc=a.dtsc and v.data=a.dtdata and v.nrdoc is not null and v.cant>0 and v.strsc is not null and v.strsc <>0)
      where a.nrdoc=p_nrdoc and a.rrowid=i.rrowid;
    end if;
  end loop;
end;
--------------------------------------------------------------------------------
------------------------------------------------------------------------------------------------------------------
PROCEDURE DISCOUNT_old(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE:=abm_util.data_by_nrdoc(vNrdoc);
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCnt   NUMBER:=0;
 vTipTVA INT;
 vTip_Opl int;
 vSuma_Total number;

  --tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct,sa
   INTO vDt,vCt,vTip_Opl
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /* Arhaism - pri summovom u4ete
  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc, dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc dtdep
,d.dtsc
,(SELECT Un$functs.tva(d.dtsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,dtdep,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
*/

     
     
  select count(*) into vCnt from vmdb_st201d where nrdoc=vNrdoc and nvl(sumagaap,0)=0;  
  if vCnt<>0 then 
   msg('Пересчитайте документ: имеются нулевые суммы без НДС!!!');
  end if; 
      
 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>''
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'un$functs.GETCONT_VINZ7(M.Ct)'
 ,vCt=>'m.dt'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vDtSc1=>''
 ,vCant=>'d.cant'
 ,vSuma=>'d.i_pretv*d.cant'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN

  Gfc_Util.gfc201
  (vNrdoc
  ,vDt=>'nvl(m.dt,d.dt)'
  ,vDtsc=>'d.ctsc'
  ,vCt=>'m.ct'
  ,vDtDep=>'nvl(m.dtdep,d.dtdep)'
  ,vSuma=>'d.sumagaap'
  ,vCod=>'d.rrowid'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vWhere=>'');
 -- NDS
   Gfc_Util.gfc201
   (vNrdoc
   , vDt=>'5342'
   , vDt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
   ,vCt=>'m.ct'
   ,vDtDep=>''
   , vSuma=>'d.sumavalct'
   , vCant=>''
   , vCodFCdeBaza=>'d.rrowid'
   , vDtNrCM =>vNrCM_F
   , vCtNrCM =>vNrCM_F
   ,vTVACont1Recognition=>FALSE
   , vWhere=>''/*,vdebug=>true*/ );
   
 --sinecost
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc,
                    vDt=>'7112',
                    vDt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')',
                    vCt=>'m.dt', 
                    vDtsc=>'d.ctsc',
                    vCtsc=>'d.ctsc',
                    vDtDep=>'nvl(d.dtdep,m.dtDep)', 
                    vCtDep=>'nvl(d.dtdep,m.dtDep)', 
                    vDtSc1=>'', 
                    vCant=>'d.cant', 
                    vSuma=>'d.sumagaap', 
                    vWhere=>'', 
                    vDtNrCm=>vNrCM_F, 
                    vCtNrCm=>vNrCM_F);


 END IF;
  --------
END  ;
------------------------------------------------------------------------------------------------------------------
PROCEDURE DISCOUNT(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE:=abm_util.data_by_nrdoc(vNrdoc);
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCnt   NUMBER:=0;
 vTipTVA INT;
 vTip_Opl int;
 vSuma_Total number;

  --tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset)
   INTO vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct,sa
   INTO vDt,vCt,vTip_Opl
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /* Arhaism - pri summovom u4ete
  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc, dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc dtdep
,d.dtsc
,(SELECT Un$functs.tva(d.dtsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,dtdep,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
*/

     
     
  select count(*) into vCnt from vmdb_st201d where nrdoc=vNrdoc and nvl(sumagaap,0)=0;  
  if vCnt<>0 then 
   msg('Пересчитайте документ: имеются нулевые суммы без НДС!!!');
  end if; 
      
 IF (vNrset=1 OR vNrset=3) THEN
 ---venit
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'m.Dt'
 ,vCt=>'un$functs.GETCONT_VINZ6(M.Ct)'
 ,vDtsc=>''
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.suma'
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
-- sinecost
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>'un$functs.GETCONT_VINZ7(M.Ct)'
 ,vCt=>'m.dt'
 ,vDtsc=>'d.ctsc'
 ,vCtsc=>'d.ctsc'
 ,vDtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vCtDep=>'nvl(d.ctdep,m.CtDep)'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.i_pretv*d.cant'
 ,vWhere=>''
 ,vDtNrCm=>vNrCM_U
 ,vCtNrCm=>vNrCM_U
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 END IF;  -- закончились проводки по 1

 IF (vNrset=2 OR vNrset=3)
  THEN

  Gfc_Util.gfc201
  (vNrdoc
  ,vCt=>'nvl(m.dt,d.dt)'
  ,vCtsc=>'d.ctsc'
  ,vDt=>'m.ct'
  ,vDtDep=>'m.ctdep'
  ,vDtsc1=>'nvl(m.ctsc1,d.ctsc1)'
  ,vCtDep=>'nvl(d.dtdep,m.dtdep)'
  , vCant=>''
  ,vSuma=>'-d.sumagaap'
  ,vCod=>'d.rrowid'
  ,vDtNrCM =>vNrCM_F
  ,vCtNrCM =>vNrCM_F
  ,vWhere=>'');
 -- NDS
   Gfc_Util.gfc201
   (vNrdoc
   ,vDt=>'m.ct'
   ,vDtDep=>'m.ctdep'
   ,vDtsc1=>'nvl(m.ctsc1,d.ctsc1)'
   , vCt=>'5342'
   , vCt1=>'Un$functs.TVA_CONT1(d.ctsc,m.ctdep,'||vNrdoc||')'
   ,vCtDep=>''
   , vSuma=>'-d.sumavalct'
   , vCant=>''
   , vCodFCdeBaza=>'d.rrowid'
   , vDtNrCM =>vNrCM_F
   , vCtNrCM =>vNrCM_F
   ,vTVACont1Recognition=>FALSE
   , vWhere=>''/*,vdebug=>true*/ );
   
 --sinecost
   Gfc_Util.gfc201 (vNrdoc=>vNrdoc,
                    vDt=>'m.dt',
                    vCt=>'6112', 
                    vDtsc=>'d.ctsc',
                    vCtsc=>'d.ctsc',
                    vDtDep=>'nvl(d.dtdep,m.dtDep)', 
                    vCtDep=>'nvl(d.dtdep,m.dtDep)', 
                    vDtSc1=>'', 
                    vCant=>'', 
                    vSuma=>'-d.sumagaap', 
                    vWhere=>'', 
                    vDtNrCm=>vNrCM_F, 
                    vCtNrCm=>vNrCM_F);


 END IF;
  --------
END DISCOUNT ;
--- Возврат товара поставщику - основные проводки
PROCEDURE Vozvrat_postav_GFC_FTVA(vNrdoc NUMBER
                             )IS
 vNrset   NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 vData    DATE;
 vsql    LONG;
 vSa     NUMBER:=0;
 vDtDep    NUMBER;
 vCtDep    NUMBER;
 vCt    NUMBER:=5211;
 vCnt    NUMBER:=0;
 vTipTVA INT;
 vSumaGaap NUMBER;
 vCodFCdeBaza NUMBER;
 
 v_dt1 number:=2171;
 v_dt2 number:=2172;
 v_funct number:=99;
BEGIN
 SELECT datamanual,Get_Nrset(nrset)
   INTO vData,vNrset
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;
  
 begin
   select 2178, 2179
   into v_dt1, v_dt2
   from tmdb_docs_add a
   where cod = vNrdoc
   and exists
     (
     select null
     from vmdb_docs d
     where d.cod = a.parent_nrdoc
     and d.sysfid = 1282
     );
   
   v_funct := 777;
  exception when no_data_found then
    v_dt1 := 2171;
    v_dt2 := 2172;
    
    v_funct := 99;
  end;

 IF (vNrset=1 OR vNrset=3)
  THEN
   Gfc_Util.gfc201
    (vNrdoc  =>vNrdoc, vfunct => v_funct
    ,vDt     =>'nvl(d.dt,m.dt)'
    ,vCt     =>'nvl(m.Ct,d.Ct)'
    ,vCt1    =>'decode('||vNrset||',1,1,null)'
    ,vDtDep  =>'nvl(d.dtdep,m.dtdep)'
  ,vCant   =>'-d.cant'
  ,vSuma   =>'-d.suma'
    ,vDtNrCM =>vNrCM_U
    ,vCtNrCM =>vNrCM_U
  ,vDtNrDoc=>'nvl(d.dtnrdoc,d.nrdoc)'
  );
 END IF;

 IF (vNrset=2 OR vNrset=3) 
  THEN
 IF Yparams.vTip_Retail=1 THEN  -- coli4estvenno-summovoi
 -- Osnovnie provodki
  Gfc_Util.gfc201(vNrdoc, v_funct, vCod=>'d.rrowid'
    , vDt=>'nvl(d.dt,m.dt)', vDtDep=>'nvl(d.dtdep,m.dtdep)'
 , vSuma=>'-d.sumagaap', vCant=>'-d.cant'
    , vDtNrCM =>vNrCM_F, vCtNrCM =>vNrCM_F, vWhere=>'');

 ELSIF Yparams.vTip_Retail=2 THEN --summovoi  
  SELECT NVL((SELECT dtsc FROM YBON_VMDB_ST201D_TVR WHERE nrdoc=vNrdoc AND dt=2171 AND clcsumax_2 IS NULL AND ROWNUM=1),0)
   INTO vCnt FROM dual;
  IF vCnt <> 0 THEN
   RAISE_APPLICATION_ERROR(-20000,'Проводки возможны только при наличии продажных цен!'||CHR(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  ELSE
   SELECT NVL(dtdep,0) INTO vDtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ctdep,0) INTO vCtDep FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT NVL(ct,0) INTO vCt FROM VMDB_ST201M WHERE nrdoc=vNrdoc;
   SELECT MIN(NVL(VATFREE,0)) INTO vTipTVA FROM vmdb01m_vinz WHERE cod=vNrdoc;

   -- Sebestoimosti -----------
   FOR c IN (SELECT DECODE(CLCSTRINGX_2,0,vSc0proc,8,vSc8proc,20,vSc20proc) sc
       , SUM(sumagaap) suma
       , MIN(rrowid) rrowid
              FROM YBON_VMDB_ST201D_TVR
              WHERE nrdoc=vNrdoc AND dt=v_dt1
              GROUP BY CLCSTRINGX_2
              ) LOOP
    INSERT INTO VMDB_CMI (cod, nrdoc, dt, dtsc, dtdep, ct, ctdep, suma, dtnrcm, ctnrcm, funct)
    VALUES (c.rrowid, vNrdoc, v_dt1, c.sc, vDtdep, vCt, vCtdep, -c.suma, vNrCM_F, vNrCM_F, v_funct);
   END LOOP;
   -- NDS ---------------
 
 
  END IF;
  end if;
 END IF;
--------------------
END ;
--------------------------------------------------------------------------------
procedure fill_1301_from_1238(p_nrdoc int) is
  v_doc int;
begin
  select txtcomment into v_doc from vmdb_docs_add where cod = p_nrdoc;
  
  if v_doc is null then
    msg(lng('Completati in adaugator numarul documentului 1238'));
  end if;
  
  delete VMDB_CST3A where nrdoc = p_nrdoc;
  
  insert into VMDB_CST3A (nrdoc, nrdoc1, cont, sc, cant1, pret1)
  select p_nrdoc, id_tmdb_cm.nextval, cont, sc, cant1, pret1
  from vmdb_cst3a
  where nrdoc = v_doc;
end;
--------------------------------------------------------------------------------
-----
procedure  raschet_ostatok12282(p_nrdoc number, p_sc number ) 
is 
v_src number; v_data date;v_sold number ; v_ctdep number;
begin
SELECT m.dtdep ,d.datamanual,m.ctdep
  INTO v_src ,v_data,v_ctdep
  FROM vMDB_ST201M m, vmdb_docs d  
  WHERE  m.nrdoc=d.cod and m.nrdoc=p_nrdoc;
  
 select  -Un$sold.CALC_SOLD(v_data, '5231',' ',' ',v_src) into v_sold from dual;
  update vmdb_st201d  set SUMAVALDT= nvl(v_sold,0), ctdep=v_src
   where  nrdoc=p_nrdoc and  ctsc=p_sc;
end; 

PROCEDURE perecislenie_NN_GFC24(vNrdoc NUMBER) IS
 vNrset NUMBER;
 vNrCM_F INTEGER:=Get_Nrset_By_Doc(vNrdoc,2);
 vNrCM_U INTEGER:=Get_Nrset_By_Doc(vNrdoc,1);
 sql1 LONG;
 vData  DATE:=abm_util.data_by_nrdoc(vNrdoc);
 vDtDep NUMBER;
 vCtDep NUMBER;
 vDt    NUMBER;
 vCt    NUMBER;
 vCnt   NUMBER:=0;
 vTipTVA INT;
 vTip_Opl int;
 vSuma_Total number;
  v_sysfid number; v_sumval number;

  --tmpTable VARCHAR2(30):=un$ttemp.gettempname;
BEGIN
 SELECT Get_Nrset(nrset),sysfid
   INTO vNrset,v_sysfid
   FROM VMDB_DOCS
  WHERE cod=vNrdoc;

 SELECT dt,ct,sa
   INTO vDt,vCt,vTip_Opl
   FROM VMDB_ST201M
  WHERE nrdoc=vNrdoc;

  /* Arhaism - pri summovom u4ete
  sql1:='create global temporary table '||tmpTable||' on commit preserve rows
 AS SELECT dtsc, dtdep,tva,0 AS codfc
 ,SUM(sumaftva) sumaftva,SUM(sumatva) sumatva
FROM
 (SELECT m.dtsc dtdep
,d.dtsc
,(SELECT Un$functs.tva(d.dtsc)*100 FROM dual) tva
,d.sumagaap sumaftva
,d.sumavalct sumatva
FROM VMDB_ST201M M, VMDB_ST201D D
WHERE m.nrdoc='||vNrdoc||' AND d.nrdoc=m.nrdoc
 )GROUP BY dtsc,dtdep,tva';

  EXECUTE IMMEDIATE sql1;
  sql1:='UPDATE '||tmpTable||' SET codfc=id_tmdb_cm.NEXTVAL';
EXECUTE IMMEDIATE sql1;
*/

  select nvl((select ctsc from vmdb_st201d where nrdoc=vNrdoc and pret is null and rownum=1),0)
    into vCnt from dual;
  if vCnt <> 0 then
   msg('Проводки возможны только при наличии продажных цен!'||chr(10)||
      'Укажите продажные цены на товар с кодом - '||vCnt);
  end if;      
     
  select count(*) into vCnt from vmdb_st201d where nrdoc=vNrdoc and nvl(sumagaap,0)=0;  
  if vCnt<>0 then 
   msg('Пересчитайте документ: имеются нулевые суммы без НДС!!!');
  end if; 

 -----
 select  SUMAVALDT into  v_sumval from vmdb_st201d where nrdoc =vNrdoc;
 if v_sysfid= 12282 then 
-- msg('Nu lucreaza');
if v_sumval=0 then
warn (lng('Fiti  atenti :Suma avnsului  este 0! Repetati  inca o data  actiunea!','Предупреждение ! Сумма  аванса 0! Повторите  действие!')); 

 -----2311 614
  Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vcod=>'d.rrowid'
 ,vDt=>'d.dt'
 ,vCt=>'d.ct'
 ,vDtsc=>''
 ,vCtsc=>'d.CTSC'
 ,vDtDep=>'m.DTdep'
 ,vCtDep=>'m.CTDEP'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMAGAAP'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 ----2311 5342
 ----2311 5342
   Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vCodfcdebaza=>'d.rrowid'
 ,vDt=>'d.dt'
 ,vCt=>5342
 ,vct1 => 20
 ,vDtsc=>''
 ,vCtsc=>''
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMAVALCT'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
  ,vTVACont1Recognition=>false
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 ----523 2311
 /*Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>5231
 ,vCt=>'d.dt'
 ,vDtsc=>'d.CTSC'
 ,vCtsc=>'d.CTSC'
 ,vDtDep=>'m.dtDep'
 ,vCtDep=>'m.DtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMA'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );*/
 elsif  v_sumval <> 0 then
  -----2311 614
  Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vcod=>'d.rrowid'
 ,vDt=>'d.dt'
 ,vCt=>'d.ct'
 ,vDtsc=>''
 ,vCtsc=>'d.CTSC'
 ,vDtDep=>'m.DTdep'
 ,vCtDep=>'m.CTDEP'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMAGAAP'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 ----2311 5342
   Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vCodfcdebaza=>'d.rrowid'
 ,vDt=>'d.dt'
 ,vCt=>5342
 ,vct1 => 20
 ,vDtsc=>''
 ,vCtsc=>''
 ,vDtDep=>'m.DtDep'
 ,vCtDep=>'m.CtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMAVALCT'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
  ,vTVACont1Recognition=>false
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 ----523 2311
 Gfc_Util.gfc201
 (vNrdoc=>vNrdoc
 ,vDt=>5231
 ,vCt=>'d.dt'
 ,vDtsc=>'d.CTSC'
 ,vCtsc=>'d.CTSC'
 ,vDtDep=>'m.dtDep'
 ,vCtDep=>'m.DtDep'
 ,vDtSc1=>''
 ,vCant=>''
 ,vSuma=>'d.SUMA'
 ,vDtNrCm=>vNrCM_F
 ,vCtNrCm=>vNrCM_F
-- ,vWhere_Before=>' and nvl(d.cant,0)<>0'
 );
 end if;
 end if; 
  --------
END perecislenie_NN_GFC24;
END;
/
SHOW ERRORS

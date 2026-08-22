-- =====================================================================
-- RO: Corectare UN$FUNCTS.get_codtva — cota TVA se lua de la data de AZI,
--     nu de la data documentului. Vezi comentariul din corpul functiei.
-- EN: Fix UN$FUNCTS.get_codtva — the VAT rate was read as of TODAY instead
--     of as of the document date.
-- RO: Copie de rezerva a versiunii curente:
--     Backups/unfuncts/UN_FUNCTS_body_20260822_2024.sql
-- =====================================================================

CREATE OR REPLACE package body un$functs as

procedure DecodeDate(dC date , Yr out integer, Mnth out integer, day out integer)
is
begin
Yr:=TO_CHAR(dC,'YYYY');
Mnth:=TO_CHAR(dC,'MM');
day:=TO_CHAR(dC,'DD');
end;

function  TDateTime(Yr integer,Mnth integer, D integer) return date
is
dd varchar(100);
begin
dd:=D||'.'||Mnth||'.'||Yr;
return TO_DATE(dd,'DD.MM.YYYY');
end TDateTime;

function GetCasaNumPerDay ( vDATA date ) return number is
TmpVar number;
pragma autonomous_transaction;
begin

select ID into TmpVar from WBOOKCASSATTLS where DATA=vdata;
return TmpVar;
   exception
     when NO_DATA_FOUND then
       select count(*) into TmpVar from VMDB_CMR
           where DATA=vDATA and
                     (CT between 2410 and 2419 or dT between 2410 and 2419);
           if TmpVar=0 then RAISE_APPLICATION_ERROR(-20000,'Nu aveti rotatii pe casa pe '||vDATA); end if;

      select count(*)into tmpvar from WBOOKCASSATTLS where DATA=vDATA;
           if TmpVar=0 then RAISE_APPLICATION_ERROR(-20000,'Introduceti data '||vDATA||' in registrul de casa'); end if;

      select max(ID)+1 into TmpVar from WBOOKCASSATTLS;

--           SELECT ID_WBOOKCASSATTLS.NEXTVAL INTO TmpVar FROM DUAL;
           insert into WBOOKCASSATTLS   (ID,DATA,USERID)
                             select TmpVar,vDATA,USERID           from TPARAMS;
           commit;
           return TmpVar;
end GetCasaNumPerDay;
----------------------------------------------------------------------------------------------------
function get_codtva(p_cod number, p_date date := null) return varchar2 is
v_vat_code tms_univers.codtva%type;
v_date date;
begin  
  if sys_context('envun4','un$functs_hist_tva') is null then
    select codtva into v_vat_code from vms_univers where cod = p_cod;
  else
    begin
      if p_date is null then
        select  coalesce
        (
          to_date(sys_context('envun4','un$datadoc'),'dd.mm.yyyy'),
          to_date(sys_context('envun4','un$datauniv'),'dd.mm.yyyy'),
          trunc(sysdate)
        )
        into v_date
        from dual;
      
        -- RO: se cauta cota valabila LA DATA DOCUMENTULUI (v_date, calculata mai sus),
        --     nu starea de azi. Inainte se interoga VMH_UNIVERS_ACT, iar v_date ramanea
        --     nefolosita (doar in mesajul de eroare): un document din 20.08 primea cota
        --     curenta, nu pe cea valabila la 20.08.
        -- EN: look up the rate valid ON THE DOCUMENT DATE (v_date); VMH_UNIVERS_ACT
        --     ignored v_date entirely, so a back-dated document got today's rate.
        execute immediate
        'select codtva from vmh_univers where cod = :p_cod and :p_date between start_date and end_date'
        into v_vat_code using p_cod, v_date;
      else
        v_date := p_date;
   
        execute immediate 
        'select codtva from vmh_univers where cod = :p_cod and :p_date between start_date and end_date'
        into v_vat_code using p_cod, v_date;
      end if;
    exception when no_data_found then
        msg(lng('Nu au fost gasite datele in istoria TVA pentru pozitia '||p_cod||' si data: '||v_date
              , 'Не найдены данные в истории НДС для позиции '||p_cod||' и даты: '||v_date));
    end;
  end if;

  return v_vat_code;
exception when too_many_rows then
  msg('Ошибочные значения интервалов дат в истории универсального справочника!'||chr(10)||
      'Код: '||p_cod||case when p_date is not null then '. На дату: '||nvl(v_date,p_date) end);
end;
----------------------------------------------------------------------------------------------------
function TVA(inSC_Product number, inSC_Client number:=0, inVinzNrdoc number:=0, p_date date := null)
return number
is
 TVA_SC  number;
 vTVA_DEP varchar2(1);
 iDocsID number(10);
 v_vat_code tms_univers.codtva%type;
begin
  if NVL(Un$functs.get_const('PARAMS','isVATPayer',SYS_CONTEXT('envun4','UN$DATADOC'),0),1)=0 then
    return 0;
  end if;

  if inVinzNrdoc<>0 or Un$docpipes.currentDocumetID <> 0 then
    begin
      if inVinzNrdoc<>0 then iDocsID:=inVinzNrdoc; else iDocsID:=Un$docpipes.currentDocumetID; end if;
      select NVL(VATFREE,0) into TVA_SC from TMDB01M_VINZ where COD=iDocsID;
      if TVA_SC=1  then return 0;    end if;
      if TVA_SC=-1 then return null; end if;
    exception when NO_DATA_FOUND then null;
    end;
  end if;
  TVA_SC:=null;
  if NVL(inSC_Client,0)!=0 then
    vTVA_DEP := get_codtva(inSC_Client, p_date);
    if vTVA_DEP='0' then return 0;
    elsif vTVA_DEP='N' then return null;
    end if;
  end if;

  if NVL(inSC_Product,0)=0 then return 0.2; end if;
    begin
      v_vat_code := get_codtva(inSC_Product, p_date);
      select decode(v_vat_code,'0',0,'N',null,'B',0.08,'C',0.05,'D',0.06,'E',0.1,0.2) into TVA_SC from dual;
    exception when no_data_found then TVA_SC :=0.2;
    end;
  return TVA_SC;
end;
----------------------------------------------------------------------------------------------------
function ACCIZ ( inSC_Product number,inSC_Client number:=0,inVinzNrdoc number:=0, inPriceID number:=2001, inGroupID number:=0 ) return number
is
   ACCIZ_SC  number;
   vACCIZ_DEP varchar2(1);
   iDocsID number(10);
   pDataDoc date;
   rezAcciz number;
begin
  -- proverka na osvobojdenia ot acciza
  if inVinzNrdoc<>0 or Un$docpipes.currentDocumetID <> 0 then
    begin
        if inVinzNrdoc<>0 then iDocsID:=inVinzNrdoc; else iDocsID:=Un$docpipes.currentDocumetID; end if;
        select NVL(VATFREE,0) into ACCIZ_SC from TMDB01M_VINZ where COD=iDocsID;
--        raise_application_error(-20000,'sfdsfd='||TVA_SC);
        if ACCIZ_SC=1 then return 0;   end if;
        exception when NO_DATA_FOUND then null;
        end;
  end if;
  ACCIZ_SC:=null;
  if NVL(inSC_Client,0)!=0 then
    begin
     select codtva into vACCIZ_DEP from VMS_UNIVERS where cod=inSC_Client;
         if vACCIZ_DEP='0' or vACCIZ_DEP='N' then
           return 0;
         end if;
        exception when NO_DATA_FOUND then null;
        end;
  end if;
  -- rascet acciza
  begin
    select datamanual into  pDataDoc from VMDB_DOCS where cod=inVinzNrdoc;
    exception when NO_DATA_FOUND then pDataDoc:='31.12.3000';
  end;
  begin
    select DECODE(inGroupID,0,PRODP4,1)  ,PRODSCH into rezAcciz,ACCIZ_SC from VMS_MPT where cod=inSC_Product;
  exception when NO_DATA_FOUND then return 0;
  end;
  rezAcciz:=rezAcciz*Pkg_Prices.GET_SC_PRICE( pDataDoc, inPriceID, inGroupID , ACCIZ_SC );
  return rezAcciz;
end ACCIZ;

function GETCONT_VINZ7 ( inCont number ) return number
is
rezCont number(5);
begin

if Un$userparams.iniparam_MODMATER_mode67=1 then
begin
execute immediate '
 SELECT number1 FROM (
 SELECT number1 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND pret=4 AND UM='||inCont||'
 UNION ALL
 SELECT number1 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND pret=3 AND UM=SUBSTR('||inCont||',1,3)
 UNION ALL
 SELECT number1 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND UM=SUBSTR('||inCont||',1,3)
 ) WHERE ROWNUM=1' into rezCont;
 if NVL(rezCont,0)=0 then null; else return rezCont;end if;
 exception when NO_DATA_FOUND then null;
end;
end if;

 if inCont>=2110 and incont<=2139 and incont <> 2132 then
   return 7141;
 --elsif inCont=2165 then   return 7141; -- заявка 2013070310881 
 elsif inCont=2132 then
   return 2141;
 elsif incont>=1211 and incont<=1219 then
   return 7211;
 elsif incont>=2610 and incont<=2619 then
   return 7141;
 elsif incont>=2160 and incont<=2169 then
   return 7111;
 elsif incont>=2170 and incont<=2179 then
   return Un$userparams.iniparam_MODMATER_ContTVR71;
  else return null;
 end if;

end GETCONT_VINZ7;

function GETCONT_VINZ6 ( inCont number ) return number
is
rezCont number(5);
begin

if Un$userparams.iniparam_MODMATER_mode67=1 then
begin
execute immediate '
 SELECT number2 FROM (
 SELECT number2 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND pret=4 AND UM='||inCont||'
 UNION ALL
 SELECT number2 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND pret=3 AND UM=SUBSTR('||inCont||',1,3)
 UNION ALL
 SELECT number2 FROM VMS_SYSS WHERE tip=''M'' AND cod=10 AND UM=SUBSTR('||inCont||',1,3)
 ) WHERE ROWNUM=1' into rezCont;
--msg(rezCont);
if NVL(rezCont,0)=0 then null; else return rezCont;end if;
 exception when NO_DATA_FOUND then null;
end;
end if;

 if inCont>=2110 and incont<=2139 then
   return 6121;
 elsif incont>=2160 and incont<=2169 then
   return 6111;
 elsif incont>=1211 and incont<=1219 then
   return 6211;
 elsif incont>=2170 and incont<=2179 then
   return Un$userparams.iniparam_MODMATER_ContTVR61;
  else return null;
 end if;


end GETCONT_VINZ6;

function GETCONT_221   ( inSC_Product number,inSC_Client number ) return number
is
   vTVA_DEP varchar2(1);
begin
   if NVL(inSC_Client,0)!=0 then
     begin
          select codtva into vTVA_DEP from VMS_UNIVERS where cod=inSC_Client;
     exception     when NO_DATA_FOUND then
            RAISE_APPLICATION_ERROR(-20000,'Client not exist in tms_univers cod='||inSC_Client);
     end;
         if vTVA_DEP='0' then
           return 2212;
           end if;
           if vTVA_DEP='B' then
           return 2213;
         end if;
   end if;
return 2211;
end;


procedure Check_Cmn202cants01(vnrdoc  number ,vdatadoc date,vconts999 varchar2:='9991') --RETURN NUMBER
is
tmpVar VMDB_CMN202D.CLCCTSCT%type;
txtError varchar2(4000);
vNrdocMaster VMDB_DOCS.cod%type;
vNrdocMasterErr VMDB_DOCS.cod%type;
cursor  c1(ccnrdoc number,pData date) is select D.CLCCTSCT from VMDB_CMN202D D,VMDB_CMN202M M
         where D.nrdoc=ccnrdoc and M.nrdoc=ccnrdoc
           and Un$sold.CALC_SOLD(pData,vconts999,' ',D.CTSC,' ',' ',M.DTNRDOC,' ',' ',' ',1)<D.cant;
iswaserr boolean;

begin

select dtnrdoc into vNrdocMaster from VMDB_CMN202M M where M.nrdoc=vnrdoc;
vNrdocMasterErr:=null;

/*select nrdoc into vNrdocMasterErr from vmdb_cmn202M M, vmdb_docs DC
where DC.datamanual>=vdatadoc and DC.cod=M.nrdoc
and M.nrdoc!=vnrdoc and M.dtnrdoc=vNrdocMaster and rownum=1 and DC.Cod>;

if vNrdocMasterErr is not null then
    --un$gfc.setDoc_Incorrect (vnrdoc,-2);
        rollback;
        RAISE_APPLICATION_ERROR(-20000,'Operatia neadmisibila! Aveti document '||to_char(vNrdocMasterErr));
end if;
*/
   txtError:='Aveti sold commandat mai mare '||CHR(13);
   iswaserr:=false;
   open c1 (vnrdoc   ,vdatadoc);
 loop
   fetch c1 into tmpVar;
   exit when C1%notfound;
   txtError:=txtError||tmpVar||CHR(13);
   iswaserr:=true;
 end loop;

 if    iswaserr=true then
    RAISE_APPLICATION_ERROR(-20000,txtError);
 end if;

-- RETURN  0;
end Check_Cmn202cants01;


function  CheckMBPUzur   ( inDt number,inCt number,inPret number,inPretGRANITA number:=1000) return number  -- 0 (ne to) 1 (da, pret<50) 2 (da, pret>=50)
is
begin
if inDt=2131 and inCt=2132 then
 if inpret<inPretGRANITA then
       return 1;
  else return 2;
 end if;
end if;
return 0;

end;

function  CheckMBPUzurMAGR   ( inDt number,inCt number,inPret number) return number  -- 0 (ne to) 1 (da, pret<50) 2 (da, pret>=50)
is
begin
if inDt=2131 and inCt=2132 then
 if inpret<0 then
       return 1;
  else return 2;
 end if;
end if;
return 0;

end;

function  First_Day   ( inDD date) return date is
begin
return '01.'||TO_CHAR(inDD,'MM')||TO_CHAR(inDD,'.YYYY');
end;


function  GetFirstDayOfQuarter(datastart date) return date
is
tempmonths integer;
begin
select TO_NUMBER(TO_CHAR(datastart,'MM')) into tempmonths from dual;
 if tempmonths between 2 and 3 then   tempmonths := 1;
 elsif tempmonths between 5 and 6 then tempmonths := 4;
 elsif tempmonths between 8 and 9 then tempmonths := 7;
 elsif tempmonths between 11 and 12 then tempmonths := 10;
end if;

return
  TO_DATE('01.'||tempmonths||'.'||TO_CHAR(datastart,'YYYY'),'DD.MM.YYYY');
end GetFirstDayOfQuarter;

function  GetFirstDayOfMonth(datastart date) return date
is
begin
return  TO_DATE('01.'||TO_CHAR(datastart,'MM')||'.'||TO_CHAR(datastart,'YYYY'),'DD.MM.YYYY');
end GetFirstDayOfMonth;

function  GetFirstDayOfYear(datastart date) return date
is
begin
return TO_DATE('01.01.'||TO_CHAR(datastart,'YYYY'),'DD.MM.YYYY');
end GetFirstDayOfYear;

--Function  MaconGetPeriodID(datastart date) return number;

procedure CheckOnlyOneMonth(dB date , dE date )
is
begin
 if TO_CHAR(dB,'MM')<>TO_CHAR(dE,'MM') or TO_CHAR(dB,'YYYY')<>TO_CHAR(dE,'YYYY') then
   RAISE_APPLICATION_ERROR(-20997,'Perioada este mai mare de 1 luna!!!');
 end if;
end ;


procedure GET_BASE_ID_UM ( vid_um number, k1out out number,id_um_base out number)
is
begin
begin
select K,CLCBASEID_UM
into K1out ,id_um_base
from VMS_UM A
where id_um=vid_um;
 exception when NO_DATA_FOUND then
  k1out:=null;
  id_um_base:=null;
  --RAISE_APPLICATION_ERROR(-20000,'Единица измерения не найдена в справочнике!');
end;

end;

function GET_SCOTHER_UM (inSC_Product number, inOtherID_M number,inCANT_X number :=0 ) return number
is
 rez number; vCodUm number(10);
 vK1 number; vCodbase1 number;
 vK2 number; vCodbase2 number;
begin

begin
select DECODE(inCANT_X,0,CANT_ID_UM,CANT1_ID_UM) into vCodUm
 from TMS_MPT A where cod=inSC_Product;
 exception when NO_DATA_FOUND then return 1;
end;

if inOtherID_M=vCodUm then return 1; end if;

GET_BASE_ID_UM(vCodUm,vK1,vCodbase1);
GET_BASE_ID_UM(inOtherID_M,vK2,vCodbase2);

if NVL(vK2,0)=0 then return null; end if;

if vCodbase1=vCodbase2 then
     return vK1/vK2;
else

begin
select DECODE(inCANT_X,0,CANT_K,CANT1_K)
into rez
from TMS_UMLINKS
where COD=inSC_Product and ID_UM=vCodbase2 ;
 exception when NO_DATA_FOUND then return null;
end;
end if;

return rez*vK1/vK2;

end ;

function TVA_CONT1 ( inSC_Product number,inSC_Client number:=0,inVinzNrdoc number:=0 ) return number
is
vTmp number;
begin
vTmp:=TVA(inSC_Product,inSC_Client,inVinzNrdoc);
if vTmp is null then return 92;
elsif vTmp=0 then return 91;
elsif vTmp=.2 then return 20;
elsif vTmp=.08 then return 8;
elsif vTmp=.05 then return 5;
elsif vTmp=.06 then return 6;
elsif vTmp=.1 then return 10;
else return 0;
end if;
end;

procedure set_const
 (vTip varchar2,vID varchar2,vValue varchar2,vDatastart date:=null,vDenumirea varchar2:=null,vForce boolean:=false)
as
begin
 insert into TMS_CONST(tip,ID,value,Datastart,denumirea)
 values (vTip,vID,vValue,NVL(vDatastart,TO_DATE('01.01.1900')),vDenumirea);
 exception when DUP_VAL_ON_INDEX then
  if vForce then
   update TMS_CONST set value=vValue,denumirea=vDenumirea
   where tip=vTip and ID=vID and Datastart=NVL(vDatastart,TO_DATE('01.01.1900'));
  end if;
end set_const;

function get_const (vTip varchar2,vID varchar2,vActData date:=null,vWarnNDF int:=1,vValue varchar2:='', vDenumirea varchar2:='') return varchar2
is
 vData date;
begin
if vActData is null then
 vData:=NVL(TO_DATE(SYS_CONTEXT('envun4','UN$DATACURENT')),TRUNC(sysdate));
else
 vData:=vActData;
end if;

for c in (select * from TMS_CONST where tip=vTip and ID=vID
  and datastart<=vData order by datastart desc)
loop
 return c.VALUE;
end loop;

for c1 in (select * from TMS_CONST where tip='HIERARCHY' and ID=vTip
  and datastart<=vData order by datastart desc)
loop
 begin
 return get_const(c1.VALUE,vID,vData,1);
  exception when others then null;
 end;
end loop;

if vErrorWarn then 
 if vWarnNDF=1 then  
  msg('Константа Tip='||vTip||', ID='||vID||' на дату '||vData||' не определена');
 elsif vWarnNDF=2 then
  if vValue is null then
   msg('Константа Tip='||vTip||', ID='||vID||' на дату '||vData||' не определена. Также не указано значение по умолчанию');
  else
   set_const(vTip,vID,vValue,'01.01.1900',vDenumirea);
   commit;
   msg('Константа Tip='||vTip||', ID='||vID||' на дату '||vData||' не определена. Будет инициализирована значением по умолчанию: '||vValue);
  end if;
 end if;
end if;

return null;

end get_const;

end;
/

SHOW ERRORS

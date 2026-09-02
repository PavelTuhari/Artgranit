CREATE OR REPLACE package body pkg_tickets_mail
is
----------------------------------------------------------------------------------------------------
function begin_auth_session
  return UTL_SMTP.connection
is
begin
  return pkg_mail.begin_auth_session (mail_params.get_user,
                                         mail_params.get_password);
end;
----------------------------------------------------------------------------------------------------
procedure add_attachments (arr        in out mail_attachments_type,
                          data       in     blob,
                          filename          varchar2,
                          format varchar2)
is
begin
  arr.EXTEND ();
  arr (arr.COUNT) := mail_attachments_table (filename, data, format);
end;
----------------------------------------------------------------------------------------------------
function tickets_formating (--  p_conn  in out nocopy utl_smtp.connection,
p_reservation_code number, p_international number := 0)
return mail_attachments_type
is
 v_url                 varchar2 (4000);
 v_url_print           varchar2 (32000);
 v_counter             number := 1;
 v_first_ticket_hash   varchar2 (20);        --для шифрования имени файла
 l_blob           blob;
 l_raw            raw(32767);
 l_http_request   utl_http.req;
 l_http_response  utl_http.resp;

 type localization is table of varchar2 (4000) index by varchar2 (2);
 type org_info is table of varchar2 (500) index by varchar2 (8);

 v_local       varchar2(4000);
 v_org_info    varchar2(500);
 v_attachments mail_attachments_type := mail_attachments_type ();
 v_org_id int := pkg_tickets_utl_25.get_org_id_by_reservation_code(p_reservation_code);
 v_can_select_places boolean := pkg_tickets_utl_25.can_select_places(p_reservation_code);
 v_reservation_detail t1rutabroni_detail%rowtype := pkg_tickets_utl_25.get_reservation_detail(p_reservation_code);
 v_ticket_params t_mail_ticket%rowtype;
 
 v_db_link varchar2(64) := pkg_integration.get_dblink_by_idbroni(p_reservation_code);
 v_ticket_cod varchar2(16);
  
begin
  DBMS_LOB.createtemporary(l_blob, false);  
  begin 
    select * 
    into v_ticket_params 
    from t_mail_ticket
    where org_id = v_org_id
      and lang   = v_reservation_detail.lang;
  exception when no_data_found then
    select * 
    into v_ticket_params 
    from t_mail_ticket
    where org_id = 20048
      and lang   = v_reservation_detail.lang;
  end;
    
  v_org_info := '&cod_fiscal=' || v_ticket_params.org_name || ' <br>c/f: ' || v_ticket_params.cod_fiscal;

v_ticket_params.n_top_text := replace(v_ticket_params.n_top_text, '#p_reservation_code#',p_reservation_code);


if p_international = 1 then
  v_local := 
  '&n_pasaport='|| v_ticket_params.n_pasaport ||
  '&n_name='|| v_ticket_params.n_name;
end if;

v_local := v_local ||
  '&n_procurat='|| v_ticket_params.n_procurat ||
  '&n_codu='|| v_ticket_params.n_codu ||
  '&n_event='|| v_ticket_params.n_event ||
  '&n_departure='|| v_ticket_params.n_departure ||  
  '&n_arrival='|| v_ticket_params.n_arrival ||  
  '&n_date='|| v_ticket_params.n_date ||
  '&n_time='|| v_ticket_params.n_time ||
  '&n_price='|| v_ticket_params.n_price ||
  '&n_preliminary='|| v_ticket_params.n_preliminary ||
  '&n_costul='|| v_ticket_params.n_costul ||
  '&n_order_id='|| v_ticket_params.n_order_id || 
  '&n_rez_cod='|| v_ticket_params.n_rez_cod ||
  '&lege='|| v_ticket_params.lege ||
  '&n_locul='|| v_ticket_params.n_locul ||
  '&n_rindul='|| v_ticket_params.n_rindul || 
  '&n_sectorul='|| v_ticket_params.n_sectorul || 
  '&n_info_link='|| v_ticket_params.n_info_link || 
  '&n_design='|| v_ticket_params.n_design || 
  '&n_free='|| v_ticket_params.n_free ||
  '&n_top_text=' || v_ticket_params.n_top_text ||
  '&n_barcode_height=' || v_ticket_params.n_barcode_height ||
  '&n_barcode_width=' || v_ticket_params.n_barcode_width || 
  '&n_barcode_top=' ||  round( (70 - v_ticket_params.n_barcode_width) / 2) ||
  '&n_web_comision=' || nvl(v_reservation_detail.web_comision,0) ;

  for c
  in (select   s.*
           ,decode (s.lang,'en', 'Sector: '|| s.sector|| '/R'|| s.myrow|| ' Place:'|| s.loc,
                                              'ru','Сектор: '|| s.sector|| '/Р'|| s.myrow|| ' Место:'|| s.loc,
                                              'Sector: '|| s.sector|| '/R'|| s.myrow|| ' Locul:'|| s.loc
           ) as place
        from   (select   distinct decode(p_international,1,ad.pasaport,null) pasaport
                    , decode(p_international,1,substr(ad.pers_numele,1,25),null) as full_name, a.cod codu
                    , (select denumirea from tms_syss
                       where id = b.codoras) as arrival
                    , (select denumirea from tms_syss
                       where id = b.codgara) as departure
                    , nvl((select codbc
                       from t0bilet_codbc
                       where   cod = b.cod),b.cod) barcod
                    , b.cod, r.ruta, a.data, a.ora
                    , decode (d.lang, 'en', nvl (a.event_name_en, a.denum),
                                      'ru', nvl (a.event_name_ru, a.denum),
                                            nvl (a.event_name_ro, a.denum)) event_name
                    , decode (d.lang, 'en', nvl (a.name_en, a.den_sala),
                                      'ru', nvl (a.name_ru, a.den_sala),
                                            nvl (a.name_ro, a.den_sala)) location
                         --,circus.get_comision_circ (b.loc,a.sala,r.ruta,r.data) as cost
                    , gra.calcBiletSumaOplati(b.cod) as total
                    , (select s.name_ro
                       from t0marca_sectors s, t0marca_places p
                       where s.nrord = p.sector_nr
                         and s.autobus = p.cod_autobus
                         and s.tip = p.tip
                         and p.abs_nr = b.loc
                         and p.cod_autobus = a.sala) as sector
                    , (select s.tribune_name
                       from t0marca_sectors s, t0marca_places p
                       where s.nrord = p.sector_nr
                         and s.autobus = p.cod_autobus
                         and s.tip = p.tip
                         and p.abs_nr = b.loc
                         and p.cod_autobus = a.sala) as tribuna
                    , circus.get_row_by_abs_nr (a.sala, b.loc) myrow
                    , circus.get_nr_in_row_by_abs_nr (a.sala, b.loc) loc
                    , d.lang, a.org_id, a.time_in
                    , nvl((select sum(suma) from t0bilet_sums 
                       where cod = b.cod
                         and dt = 2413 and ct = 5161
                         and ctsc = 1),0) cost
                    , nvl((select sum(suma) from t0bilet_sums 
                       where cod = b.cod
                         and dt = 2413 and ct = 5161
                         and ctsc = 3),0) prealabil
                    ,(SELECT   s.denumirea
                      FROM   tms_syss s
                     WHERE   tip = 'G0' AND cod = 306 and cod1=r.pay_type) tip_plata
                  from   t1rutabroni r,
                         t0bilet b, t0bilet_add ad,
                         th_afisha_full a,
                         t1rutabroni_detail d
                 where       r.idcasalenta = p_reservation_code
                         and b.idcaslenta = r.idcasalenta
                         and b.cod = ad.cod(+)
                         and a.cod = r.ruta
                         and a.data = r.data
                         and b.idcaslenta = d.idcasalenta) s)
  loop
     if v_counter = 1
     then
        v_url_print := 'barcode=' || c.barcod || '&res_cod='|| p_reservation_code|| v_local || v_org_info
                          || '&logo=' || v_ticket_params.logo
                          ;
        v_first_ticket_hash := c.barcod;
     end if;
  
    if v_db_link = 'not_set' then
      v_ticket_cod := c.cod;
    else
      v_ticket_cod := pkg_integration.get_ticket_code_gara(c.cod, v_db_link);
    end if;
  
     v_url_print := v_url_print || '&barcode' || v_counter || '=' || c.barcod|| '&codu'|| v_counter|| '=' || c.codu
                          || '&pasaport' || v_counter || '=' || c.pasaport || '&full_name' || v_counter || '=' || c.full_name
                          || '&event_name' || v_counter || '=' || replace(c.event_name,'->',' -> ') --Пробелы в название добавил, чтобы wrap сработал  
                          || '&departure'|| v_counter || '=' || c.departure  
                          || '&date'|| v_counter || '=' || c.data
                          || '&time'|| v_counter || '=' || c.ora
                          || '&arrival'|| v_counter || '=' || c.arrival                                   
                          --|| '&access' || v_counter || '='|| c.time_in 
                          || '&total' || v_counter|| '='|| c.total
                          || '&cost' || v_counter|| '='|| c.cost
                          || '&prealabil' || v_counter|| '='|| c.prealabil
                          || '&tip_plata' || v_counter|| '='|| c.tip_plata
                          || '&sectorul' || v_counter|| '='|| v_ticket_cod
                          || '&rindul' || v_counter || '=' || case when v_can_select_places then c.myrow end
                          || '&locul'|| v_counter || '=' || case when v_can_select_places then c.loc end;
     v_counter := v_counter + 1;
     --Genirate tickets for mobile devices
     v_url := 'http://linktickets.una.md/um/ticket/ticketp.php?barcode=' || c.barcod || '&codu=' || c.codu 
                          || '&event_name=' || c.event_name || '&date='|| c.data
                          || '&total=' || c.total || '&tribuna=' || c.tribuna || '&sectorul=' || c.sector 
                          || '&rindul='|| case when v_can_select_places then c.myrow end
                          || '&locul=' || case when v_can_select_places then c.loc end;
  /*  pkg_mail_blob_atach.add_attachments(p_conn
          ,HTTPURITYPE.createuri(utl_url.escape(v_url,false,'UTF8')).getblob()
          , c.barcod);*/
  -- Пока не отпавлять для мобильной телефонов --temporary excluded
  end loop;

  if v_counter > 1
  then
      say('URL PDF'||'http://linktickets.una.md/um/ticket/ticketp_print_gara_isdei.php');
     say ('v_url_print:'||v_url_print);
   l_http_request  := UTL_HTTP.begin_request(url=>'http://linktickets.una.md/um/ticket/ticketp_print_gara_isdei.php', method => 'POST');       
   UTL_HTTP.SET_HEADER (r      =>  l_http_request,
                   name   =>  'Content-Type',
                   value  =>  'application/x-www-form-urlencoded; charset=utf-8');                       
   UTL_HTTP.SET_HEADER (r      =>   l_http_request,
                   name   =>   'Content-Length',
                   value  =>   length(utl_url.escape(v_url_print,false,'UTF8'))); 
   UTL_HTTP.WRITE_TEXT (r      =>   l_http_request,
                   data   =>   utl_url.escape(v_url_print,false,'UTF8'));
   l_http_response := UTL_HTTP.get_response(l_http_request);  
       
   begin
    loop
      UTL_HTTP.read_raw(l_http_response, l_raw, 32767);
      DBMS_LOB.writeappend (l_blob, UTL_RAW.length(l_raw), l_raw);
    end loop;
  exception
    when UTL_HTTP.end_of_body then
    UTL_HTTP.end_response(l_http_response);
  end;                
   add_attachments (
        v_attachments,
        l_blob,
        'Bilete_' || p_reservation_code,
        'pdf'
     );
     update   t1rutabroni_detail t set   
          --ticket_url = 'http://linktickets.una.md/um/ticket/pdf/Bilete_' || v_first_ticket_hash || '.pdf'
          ticket_url = 'http://una.md:3323/um/ticket/pdf/Bilete_' || v_first_ticket_hash || '.pdf'
        , t.mail_sent = sysdate
      where   idcasalenta = p_reservation_code;
  end if;

  DBMS_LOB.freetemporary(l_blob);
  return v_attachments;
exception
  when others
  then
     un$process_log.log_exception (un$process_log.get_id ('mail_server'),
                                   'Ошибка при формировании вложения. ',
                                   p_reservation_code);
    say(DBMS_UTILITY.format_error_backtrace);  
  return mail_attachments_type();  
end;

----------------------------------------------------------------------------------------------------
procedure mail (
  p_recipients     varchar2,
  p_sender varchar2,  
  p_subject        varchar2,
  p_text           varchar2,
  p_cc             varchar2 := null,
  p_bcc            varchar2 :='',
--      p_bcc            VARCHAR2 := 'circul.chisinau@mail.md',
  p_attachments    mail_attachments_type := mail_attachments_type ()
)
is
  v_conn         UTL_SMTP.connection;
  v_url          varchar2 (1000);
  v_result       blob;
  v_event_info   varchar2 (3000);
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
  v_un9mail_pack un9mail_pack%rowtype;
begin
  
  v_nrmsg := id_mail_sender.nextval;
    
  v_un9mail_msg.nrmsg := v_nrmsg;
  v_un9mail_msg.subject := p_subject;
  v_un9mail_msg.sender := p_sender;
  v_un9mail_msg.text := p_text;
  v_un9mail_msg.status := 1;
  v_un9mail_msg.recipients := p_recipients;
  
  fill_un9mail_msg(v_un9mail_msg);
  send_email_api_php(v_nrmsg);
  
 /* v_conn := begin_auth_session;
  
  begin
    pkg_mail.begin_mail_in_session (
       conn         => v_conn,
       sender       => p_sender,
       recipients   => p_recipients,
       cc           => p_cc,
       bcc          => p_bcc,
       subject      => p_subject,
       mime_type    => pkg_mail.multipart_mime_type
    );

    pkg_mail.attach_mb_text (conn => v_conn, data => p_text, last => false
    , mime_type => 'text/plain; charset=Windows-1251'
    );

    --Adding attachments if exists
    for i in 1 .. p_attachments.COUNT
    loop
       pkg_mail_blob_atach.add_attachments (v_conn,
                                            p_attachments (i).data,
                                            p_attachments (i).filename,
                                            p_attachments (i).format);
    end loop;

    pkg_mail.end_mail (conn => v_conn);
  exception when others then 
    pkg_mail.end_mail (conn => v_conn);
    un$process_log.log_exception (un$process_log.get_id ('mail_server'),p_subject);
  end;*/
exception when others then
     un$process_log.log_exception (un$process_log.get_id ('mail_server'), p_subject);
end;
----------------------------------------------------------------------------------------------------
function get_mail_settings(p_lang varchar2, p_mail_type int)
  return v_mail_settings%rowtype
is
  v_settings v_mail_settings%rowtype;
  v_org_id number(30);
  v_autobus number(7);
  v_codu varchar2(10);
  v_fields varchar2(1024);
begin

  select listagg(lower(column_name) || ', ' ) within group (order by column_id)
  into v_fields
  from user_tab_columns where table_name = 'V_MAIL_SETTINGS';
  
  v_fields := substr(v_fields, 1, length(v_fields) - 2);
  
  execute immediate 
  '
  select ' || v_fields || '
  from
    (select v.*
        , row_number() over (order by org_id, autobus, codu nulls last) rn
    from v_mail_settings v
    where lang = :p_lang
      and mail_type = :p_mail_type) a
  where rn = 1
  '  into v_settings using p_lang, p_mail_type ;

  return v_settings;
end;
----------------------------------------------------------------------------------------------------
function get_mail_settings(p_reservation_code int, p_lang varchar2, p_mail_type number)
  return v_mail_settings%rowtype
is
  v_settings v_mail_settings%rowtype;
  v_org_id number(30);
  v_autobus number(7);
  v_codu varchar2(10);
  v_reservation t1rutabroni%rowtype := pkg_tickets_utl_25.get_reservation(p_reservation_code);
  v_route t0ruta%rowtype := pkg_tickets_utl_25.get_route(pkg_tickets_utl_25.get_codu_baza(v_reservation.ruta));
  v_fields varchar2(1024);
begin

  select listagg(lower(column_name) || ', ' ) within group (order by column_id)
  into v_fields
  from user_tab_columns where table_name = 'V_MAIL_SETTINGS';
  
  v_fields := substr(v_fields, 1, length(v_fields) - 2);
  say('v_route.web_merchant_id:'||v_route.web_merchant_id);
  say('v_route.autobus:'||v_route.autobus);
  say('v_route.codu:'||v_route.codu);
  say('p_lang:'||p_lang);
  say('p_mail_type:'||p_mail_type);
  
  execute immediate 
  '
  select ' || v_fields || '
  from
    (select v.*
        , row_number() over (order by org_id, autobus, codu nulls last) rn
    from v_mail_settings v
    where (org_id = :merchant or org_id is null)
      and (autobus = :autobus or autobus is null)
      and (codu = :codu or codu is null)
      and lang = :p_lang
      and mail_type = :p_mail_type) a
  where rn = 1
  '  into v_settings using v_route.web_merchant_id, v_route.autobus, v_route.codu, p_lang, p_mail_type ;

  return v_settings;
end;
----------------------------------------------------------------------------------------------------
function get_cancel_link
(
  p_lang varchar2,
  p_org varchar2,
  p_event_txt_id varchar2,
  p_idbroni number
) return varchar2 is
begin
  msg('p_org'||p_org);
return 'http://' || pkg_tickets_utl_25.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name 
                || '/cancel.php?language=' || p_lang
                || '&org=' || p_org
                || '&event=' || p_event_txt_id
                || '&code=' || p_idbroni;
end;
----------------------------------------------------------------------------------------------------
function get_merchant_link
(
  p_org varchar2
) return varchar2 is
begin
return 'http://' || pkg_tickets_utl_25.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name
               || '/' ||p_org ;
end;
----------------------------------------------------------------------------------------------------
function replace_variables
(
  p_text varchar2, 
  p_location_text varchar2, 
  p_route t0ruta%rowtype, 
  p_reservation t1rutabroni%rowtype, 
  p_info t1rutabroni_detail%rowtype,
  p_marca t0marca%rowtype,
  p_org_attributes t_org_attributes%rowtype
) 
  return varchar2
is
  v_text varchar2(4000) := p_text;
  v_rules varchar2(4000);
  v_cancel_link varchar2(4000);
  v_org varchar2(128);
  v_personal_data_link varchar2(4000);
  v_merchant_link varchar2(4000);
  v_event_link varchar2(4000);
  v_cancel_captcha_link varchar2(4000);
  v_hash varchar2(128) := circus.get_hash_by_idbroni(p_info.idcasalenta); 
  v_ruta_m t1ruta_m%rowtype := pkg_tickets_utl_25.get_ruta_m(p_reservation.ruta, p_reservation.data);
  v_startpoint varchar2(256) := pkg_tickets_utl_25.get_startpoint_by_idbroni(p_reservation.idcasalenta);
  v_endpoint varchar2(256) := pkg_tickets_utl_25.get_endpoint_by_idbroni(p_reservation.idcasalenta);
  v_end_time date := broni_25.get_cancel_plan_data(p_reservation.idcasalenta);
begin

  select um into v_org
  from tms_univers 
  where cod = p_route.web_merchant_id; 
    
  select replace(lege,'<br>') into v_rules 
  from t_mail_ticket 
  where org_id = /*p_route.web_merchant_id*/20048
    and lang = p_info.lang; 
      
  v_cancel_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name 
                || '/cancel.php?language=' || p_info.lang
                || '&org=' || v_org
                --NG 05.05.2025
                --|| '&event=' || p_route.event_txt_id
                || '&event=' || p_route.codu
                || '&code=' || p_reservation.idcasalenta;
  v_cancel_link := replace(v_cancel_link, ' ', '%20');
  
  /*v_personal_data_link := 'https://'||p_org_attributes.domen||'/' 
                         || pkg_tickets_utl_25.get_project_name
                         || '/new/reservation/' 
                         || p_info.idcasalenta
                         || '/complete/' 
                         || v_hash;*/

  v_personal_data_link := 'https://'||p_org_attributes.domen||'/ticket/' 
                         --|| pkg_tickets_utl_25.get_project_name
                         || '/personal_data.php?'
                         || 'r='||p_info.lang 
                         || '&code=' ||p_info.idcasalenta
                         || '&hash=' || v_hash;

  v_personal_data_link := replace (v_personal_data_link, ' ', '%20');
  
  v_merchant_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
                  || '/' ||v_org;
                 
  v_event_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
               || '/' ||v_org || '/' 
               --NG 05.05.2025
               --|| p_route.event_txt_id;
               || p_route.codu;
  v_event_link := 'http://'||p_org_attributes.domen||'/ticket/'
               || 'index.php?&api_type=bta28&org=bta28'
               || '&event='||get_event_txt_id(p_route.codu)
               || '&destination='||v_endpoint
               || '&startPoint='||v_startpoint
               || '&RouteCode='||p_route.codu;
  v_event_link := replace(v_event_link, ' ', '%20');
  
    v_cancel_captcha_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
                  || '/cancel_reservation.php?org=' ||v_org||'&code='||p_reservation.idcasalenta;
               
  v_text := replace(v_text, '#reservation_code#', p_info.idcasalenta);
  v_text := replace(v_text, '#event_name#', p_route.denumirea || '-' || p_route.codu);
  v_text := replace(v_text, '#org_name#', case p_info.lang   when 'ro' then p_org_attributes.title_ro
                                                             when 'en' then p_org_attributes.title_en
                                                             when 'ru' then p_org_attributes.title_ru end);
  v_text := replace(v_text, '#rules#', v_rules);                                                             
  v_text := replace(v_text, '#event_date#', TO_CHAR (v_ruta_m.data, 'dd.mm.yyyy'));
  v_text := replace(v_text, '#event_time#', TO_CHAR (v_ruta_m.data, 'hh24:mi'));
  v_text := replace(v_text, '#broni_date#', TO_CHAR (p_reservation.databroni, 'dd.mm.yyyy'));
  v_text := replace(v_text, '#broni_time#', TO_CHAR (p_reservation.databroni, 'hh24:mi'));
  v_text := replace(v_text, '#first_name#', p_info.first_name);
  v_text := replace(v_text, '#last_name#', p_info.last_name);
  v_text := replace(v_text, '#location_text#', p_location_text);
  v_text := replace(v_text, '#website_url#', p_org_attributes.website_url);
  v_text := replace(v_text, '#website_contacts_url#', p_org_attributes.website_contacts_url);
  v_text := replace(v_text, '#event_place#', p_marca.denumirea);
  v_text := replace(v_text, '#cancel_link#', v_cancel_link);
  v_text := replace(v_text, '#personal_data_link#', v_personal_data_link);
  v_text := replace(v_text, '#merchant_link#', v_merchant_link);
  v_text := replace(v_text, '#event_link#', v_event_link);
  v_text := replace(v_text, '#phone#', p_info.phone);
  v_text := replace(v_text, '#startpoint#', v_startpoint);
  v_text := replace(v_text, '#endpoint#', v_endpoint);
  v_text := replace(v_text, '#transaction_id#', p_reservation.transaction_id);
  v_text := replace(v_text, '#end_time#', to_char(v_end_time,'hh24:mi:ss'));
  v_text := replace(v_text, '#cancel_captcha_link#',v_cancel_captcha_link);
  

  
return v_text; 
end;
----------------------------------------------------------------------------------------------------
function get_event_link
(
  p_org varchar2,
  p_event_txt_id varchar2
) return varchar2 is
begin
return 'http://' || pkg_tickets_utl_25.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name
               || '/' ||p_org || '/' || p_event_txt_id;
end;
--------------------------------------------------------------------------------
function get_lifetime_text
(
  p_idbroni int,
  p_lang varchar2
) return varchar2 is
v_lifetime number:= get_lifetime_25(p_idbroni);
v_lifetime_minutes number:= round(v_lifetime * 60); 
v_text varchar2(128);
v_mod int := mod(v_lifetime, 10); --остаток от деления на 10
begin
  if p_lang = 'en' then 
    if v_lifetime > 1 then 
      v_text := ' hours';
    else
      v_text := ' minutes';
    end if;
  elsif p_lang = 'ro' then
    if v_lifetime > 1 then
      if v_lifetime > 20 then   
        v_text := ' de ore';
      else
        v_text := 'ore ';
      end if;
    else
      v_text := ' minute';
    end if;
  elsif p_lang = 'ru' then
    if v_lifetime not between 11 and 14 then
      if v_mod = 1 then
        v_text := ' час';
      elsif v_mod in (2,3,4) then
        v_text := ' часа';
      else v_text := ' часов';
      end if;
    end if;
  end if;
  
  return v_lifetime || v_text;
end;
----------------------------------------------------------------------------------------------------
function replace_variables_blob
(
  p_text blob, 
  p_location_text varchar2, 
  p_route t0ruta%rowtype, 
  p_reservation t1rutabroni%rowtype, 
  p_info t1rutabroni_detail%rowtype,
  p_marca t0marca%rowtype,
  p_org_attributes t_org_attributes%rowtype
) 
  return blob
is
  v_text blob := p_text;
  v_rules varchar2(4000);
  v_cancel_link varchar2(4000);
  v_org varchar2(128);
  v_personal_data_link varchar2(4000);
  v_merchant_link varchar2(4000);
  v_event_link varchar2(4000);
  v_cancel_captcha_link varchar2(4000);
  v_hash varchar2(128) := circus.get_hash_by_idbroni(p_info.idcasalenta); 
  v_ruta_m t1ruta_m%rowtype := pkg_tickets_utl_25.get_ruta_m(p_reservation.ruta, p_reservation.data);
  v_startpoint varchar2(256) := pkg_tickets_utl_25.get_startpoint_by_idbroni(p_reservation.idcasalenta);
  v_endpoint varchar2(256) := pkg_tickets_utl_25.get_endpoint_by_idbroni(p_reservation.idcasalenta);
  v_end_time date := broni_25.get_cancel_plan_data(p_reservation.idcasalenta);
begin
  say('-----');
  say(UTL_RAW.CAST_TO_VARCHAR2(dbms_lob.substr(v_text)));
  say('-----');

  select um into v_org
  from tms_univers 
  where cod = p_route.web_merchant_id; 
    
  select replace(lege,'<br>') into v_rules 
  from t_mail_ticket 
  where org_id = /*p_route.web_merchant_id*/20048
    and lang = p_info.lang; 
      
  v_cancel_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name 
                || '/cancel.php?language=' || p_info.lang
                || '&org=' || v_org
                --NG 05.05.2025
                --|| '&event=' || p_route.event_txt_id
                || '&event=' || p_route.codu
                || '&code=' || p_reservation.idcasalenta;
  v_cancel_link := replace(v_cancel_link, ' ', '%20');
  
  /*v_personal_data_link := 'https://'||p_org_attributes.domen||'/' 
                         || pkg_tickets_utl_25.get_project_name
                         || '/new/reservation/' 
                         || p_info.idcasalenta
                         || '/complete/' 
                         || v_hash;*/

  v_personal_data_link := 'https://'||p_org_attributes.domen||'/ticket/' 
                         --|| pkg_tickets_utl_25.get_project_name
                         || '/personal_data.php?'
                         || 'r='||p_info.lang 
                         || '&code=' ||p_info.idcasalenta
                         || '&hash=' || v_hash;

  v_personal_data_link := replace (v_personal_data_link, ' ', '%20');
  
  v_merchant_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
                  || '/' ||v_org;
                 
  v_event_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
               || '/' ||v_org || '/' 
               --NG 05.05.2025
               --|| p_route.event_txt_id;
               || p_route.codu;
  v_event_link := 'http://'||p_org_attributes.domen||'/ticket/'
               || 'index.php?&api_type=bta28&org=bta28'
               || '&event='||get_event_txt_id(p_route.codu)
               || '&destination='||v_endpoint
               || '&startPoint='||v_startpoint
               || '&RouteCode='||p_route.codu;
  v_event_link := replace(v_event_link, ' ', '%20');
  
    v_cancel_captcha_link := 'http://'||p_org_attributes.domen||'/ticket/' --|| pkg_tickets_utl_25.get_project_name
                  || '/cancel_reservation.php?org=' ||v_org||'&code='||p_reservation.idcasalenta;
               
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#reservation_code#', p_info.idcasalenta);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_name#', p_route.denumirea || '-' || p_route.codu);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#org_name#', case p_info.lang   when 'ro' then p_org_attributes.title_ro
                                                             when 'en' then p_org_attributes.title_en
                                                             when 'ru' then p_org_attributes.title_ru end);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#rules#', v_rules);                                                             
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_date#', TO_CHAR (v_ruta_m.data, 'dd.mm.yyyy'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_time#', TO_CHAR (v_ruta_m.data, 'hh24:mi'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#broni_date#', TO_CHAR (p_reservation.databroni, 'dd.mm.yyyy'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#broni_time#', TO_CHAR (p_reservation.databroni, 'hh24:mi'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#first_name#', p_info.first_name);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#last_name#', p_info.last_name);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#location_text#', p_location_text);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#website_url#', p_org_attributes.website_url);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#website_contacts_url#', p_org_attributes.website_contacts_url);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_place#', p_marca.denumirea);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cancel_link#', v_cancel_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#personal_data_link#', v_personal_data_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#merchant_link#', v_merchant_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_link#', v_event_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#phone#', p_info.phone);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#startpoint#', v_startpoint);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#endpoint#', v_endpoint);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#transaction_id#', p_reservation.transaction_id);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#end_time#', to_char(v_end_time,'hh24:mi:ss'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cancel_captcha_link#',v_cancel_captcha_link);
  
  
  
return v_text; 
end;
----------------------------------------------------------------------------------------------------
function replace_variables_by_agent_cod(p_agent_cod number, p_text varchar2) return varchar2 is
  v_agent_name varchar2(4000);
  v_text varchar2(4000):=p_text;
begin
  select denumirea into  v_agent_name
  from tms_orgtrans_ancheta
  where cod = p_agent_cod;
  
  v_text := replace(v_text, '#agent_name#', v_agent_name); 
  
  return v_text;
end;
--------------------------------------------------------------------------------
function get_location_text(p_reservation_code int, p_autobus int, p_lang varchar2) return varchar2 is
v_location_text varchar2(4000);
  lf                varchar2 (1) := CHR (10);
begin
  
  for c  in 
  (
    select loc rn, loc nr, (select sum(suma) from t0bilet_sums where cod = t.cod) suma, t.*
    from t0bilet t
    where t.idcaslenta = p_reservation_code
  )
  loop
     v_location_text := v_location_text
        || case when p_lang = 'ro' then 'Locul '
                when p_lang = 'ru' then 'Место '
                when p_lang = 'en' then 'Place '  end || c.nr
        || lf;
  end loop;
  
  
  return v_location_text;
end;
----------------------------------------------------------------------------------------------------
procedure send_mail (p_reservation_code int, p_mail_type number)
is
  v_info t1rutabroni_detail%rowtype := pkg_tickets_utl_25.get_reservation_detail (p_reservation_code) ;
  v_reservation t1rutabroni%rowtype := pkg_tickets_utl_25.get_reservation (p_reservation_code) ;
  v_route t0ruta%rowtype := pkg_tickets_utl_25.get_route(pkg_tickets_utl_25.get_codu_baza(v_reservation.ruta));
  v_marca t0marca%rowtype := pkg_tickets_utl_25.get_marca(v_route.autobus, v_route.tip);
  v_org_attributes t_org_attributes%rowtype := pkg_tickets_utl_25.get_org_attributes(v_route.web_merchant_id);
  
  
  v_settings v_mail_settings%rowtype := get_mail_settings(p_reservation_code, v_info.lang, p_mail_type);
  v_subject varchar2(256) := v_settings.subject;
  v_text    varchar2(4000) := v_settings.text;
  v_org_url varchar2(512);
  
  v_location_text   varchar2(4000) := get_location_text(p_reservation_code, v_route.autobus, v_info.lang);

  v_attachments     mail_attachments_type := mail_attachments_type ();
  
  v_transaction_email varchar2(128);
  
  v_mail varchar2(128);
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
  v_un9mail_pack un9mail_pack%rowtype;
  v_text_mail long;
  v_text_blob    blob := v_settings.text_blob;
begin

  if p_mail_type = 9 then
    select case when u.email   is not null then u.email   ||', ' end ||
           case when org.email is not null then org.email end
           into v_transaction_email
    from t0users u, tms_orgtrans_ancheta org
    where u.org_cod_univ = org.cod
      and u.id = v_reservation.casir;
  end if;
  say(pkg_tickets_utl_25.get_codu_baza(v_reservation.ruta));

  select um into v_org_url
  from tms_univers
  where cod = v_route.web_merchant_id;

  v_subject := replace(v_subject, '#reservation_code#', p_reservation_code);
  v_text := replace_variables(v_text, v_location_text, v_route, v_reservation, v_info, v_marca, v_org_attributes);
  
  --Если у нас письмо с кодом подтверждения то отправляем кассиру агента, а не пользователю
  if p_mail_type = 11 then
    select email into v_mail
    from t0users
    where id = v_reservation.casir;
  else
    v_mail := v_info.email; 
  end if;   
  say(v_mail);   
  say(v_text);
  un$process_log.LOG (un$process_log.get_id ('mail_server'),
                      'mail: '||v_mail||chr(13)||
                      v_text,
                      'I',
                      p_reservation_code);
  
  v_text_blob := replace_variables_blob(v_text_blob, v_location_text, v_route, v_reservation, v_info, v_marca, v_org_attributes);
                      
  --NG, 07.02.2024 PHP API
  v_text_mail := UTL_RAW.CAST_TO_VARCHAR2(dbms_lob.substr(v_text_blob));
  v_nrmsg := id_mail_sender.nextval;
  say('v_text_mail:'||v_text_mail);
    
  v_un9mail_msg.nrmsg := v_nrmsg;
  v_un9mail_msg.subject := v_subject;
  v_un9mail_msg.sender := 'support@unisim-soft.com';
  v_un9mail_msg.text := v_text_mail;
  v_un9mail_msg.status := 1;
  v_un9mail_msg.recipients := v_info.email;
  --v_un9mail_msg.cc := 'c_tickets_UNAmd@googlegroups.com'||v_email_bcc;
  ------------------------------------------
             
  if p_mail_type = 3 then
      v_attachments.EXTEND ();
      v_attachments (1) := mail_attachments_table (null, null, null);
      v_attachments := tickets_formating (p_reservation_code, v_route.ipas);
    if v_settings.id_banner is not null then
      v_attachments.EXTEND ();
      v_attachments (2) := mail_attachments_table (v_settings.image_name, v_settings.image, v_settings.image_format );
    end if;

      if v_attachments.COUNT > 0 then

         /*mail (v_mail, 'support@una.md',
               v_subject,
               v_text,
               p_attachments   => v_attachments,
               p_bcc => v_settings.bcc);*/
         un$process_log.LOG (
            un$process_log.get_id ('mail_server'),
               'Письмо отправлено,прикреплено '
            || v_attachments.COUNT
            || ' файлов',
            'I',
            p_reservation_code
         );
         
         fill_un9mail_msg(v_un9mail_msg);
         
         for i in 1 .. v_attachments.COUNT
          loop
            v_un9mail_pack.nrmsg := v_nrmsg;  
            v_un9mail_pack.nrord := ID_TMDB_CM.NEXTVAL;   
            v_un9mail_pack.filename := v_attachments(i).filename||'.'||v_attachments(i).format; 
            v_un9mail_pack.pack := v_attachments(i).data;
            
            fill_un9mail_pack(v_un9mail_pack);
          end loop;
          
          send_email_api_php(v_nrmsg);
          --send_email_post_api(v_nrmsg);
      else
         un$process_log.log_exception (
            un$process_log.get_id ('mail_server'),
            'Не сформированно ни одного вложения, отправка невозможна!',
            p_reservation_code
         );
      end if;
  else
    --mail (v_mail, 'support@una.md', v_subject, v_text, p_bcc => v_settings.bcc);
    fill_un9mail_msg(v_un9mail_msg);
    send_email_api_php(v_nrmsg);
    --send_email_post_api(v_nrmsg);
    
    un$process_log.LOG (un$process_log.get_id ('mail_server'),
                      'Письмо ' || p_mail_type || 'отправлено,',
                      'I',
                      p_reservation_code);
  end if;
end;

procedure send_error(p_error_text varchar2) is
begin
    mail ('support@una.md', 'support@una.md', 
          'Web-method error. Project '  || pkg_tickets_utl_25.get_project_name, p_error_text, p_bcc => null);
end;

procedure send_mail_transaction(p_transaction_id int, p_mail_type number)
is
  v_email varchar2(256);
  v_cc varchar2(256);
  v_subject varchar2(4000);
  v_text varchar2(4000);
  v_bcc varchar2(4000);
  v_transaction_date date;
  v_transaction_sum number;
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
begin

  select case when u.email   is not null then u.email end,
         case when org.email is not null then org.email end
         into v_email, v_cc
  from t0users u, tms_orgtrans_ancheta org, tmdb_cards_cm cm, t1rutabroni br
  where u.org_cod_univ = org.cod
    and br.casir = u.id
    and cm.nrdoc = br.idcasalenta
    and cm.id = p_transaction_id;
    
  select subject, text
  into v_subject, v_text
  from t_mail_setting_detail
  where mail_type = p_mail_type
    and lang = 'ro';
  
  select bcc into v_bcc
  from t_mail_setting
  where id = 1;
   
  select oper_date, -amount
  into v_transaction_date, v_transaction_sum
  from tmdb_cards_cm
  where id = p_transaction_id;
  
  
  v_text := replace(v_text, '#transaction_date#',  v_transaction_date);
  v_text := replace(v_text, '#transaction_sum#', v_transaction_sum);
  
  v_nrmsg := id_mail_sender.nextval;
    
  v_un9mail_msg.nrmsg := v_nrmsg;
  v_un9mail_msg.subject := v_subject;
  v_un9mail_msg.sender := 'support@unisim-soft.com';
  v_un9mail_msg.text := v_text;
  v_un9mail_msg.status := 1;
  v_un9mail_msg.recipients := v_email;
  v_un9mail_msg.bcc := v_bcc;
  v_un9mail_msg.cc := v_cc;
  
  --mail (v_email, 'support@una.md', v_subject, v_text, p_bcc => v_bcc);
  fill_un9mail_msg(v_un9mail_msg);
  send_email_post_api(v_nrmsg);

end;
--------------------------------------------------------------------------------
procedure send_mail_by_agent(p_agent_cod int, p_mail_type int) is
  v_settings v_mail_settings%rowtype := get_mail_settings('ro', p_mail_type);
  v_email varchar2(128);
  v_agent_name varchar2(4000);
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
begin
  select email into v_email
  from tms_orgtrans_ancheta
  where cod = p_agent_cod;
  
  v_settings.text := replace_variables_by_agent_cod(p_agent_cod, v_settings.text);
  
  v_nrmsg := id_mail_sender.nextval;
    
  v_un9mail_msg.nrmsg := v_nrmsg;
  v_un9mail_msg.subject := v_settings.subject;
  v_un9mail_msg.sender := 'support@unisim-soft.com';
  v_un9mail_msg.text := v_settings.text;
  v_un9mail_msg.status := 1;
  v_un9mail_msg.recipients := v_email;
  
  --mail (v_email, 'support@una.md', v_settings.subject, v_settings.text, p_bcc => v_settings.bcc);
  fill_un9mail_msg(v_un9mail_msg);
  send_email_post_api(v_nrmsg);

end;
----------------------------------------------------------------------------------------------------
procedure fill_un9mail_msg(p_un9mail_msg un9mail_msg%rowtype) is
  pragma autonomous_transaction;
begin
    insert into un9mail_msg
    (nrmsg, subject, sender, text, status, recipients, cc, bcc)
  values
    (p_un9mail_msg.nrmsg, p_un9mail_msg.subject, p_un9mail_msg.sender, 
     p_un9mail_msg.text, p_un9mail_msg.status, p_un9mail_msg.recipients, p_un9mail_msg.cc, p_un9mail_msg.bcc);
  commit;
end;
--un9mail_pack
----------------------------------------------------------------------------------------------------
procedure fill_un9mail_pack(p_un9mail_pack un9mail_pack%rowtype) is
  pragma autonomous_transaction;
begin
  insert into un9mail_pack
    (nrmsg, nrord, filename, pack, nrdoc1)
  values
    (p_un9mail_pack.nrmsg, p_un9mail_pack.nrord, 
     p_un9mail_pack.filename, p_un9mail_pack.pack, p_un9mail_pack.nrdoc1);
  commit;
end;
----------------------------------------------------------------------------------------------------
procedure send_email_api_php(p_nrmsg int) is 
  pragma autonomous_transaction;
  l_req  UTL_HTTP.REQ;
  l_resp UTL_HTTP.RESP;
  buffer varchar2(4000);
  
  v_req_result varchar2(4000);
  v_cnt integer;
  
  v_url varchar2(4000);
begin
  say('start api');
  select count(*) into v_cnt from UN9MAIL_MSG i where i.nrmsg = p_nrmsg and i.status = 1;
  say('v_cnt '||v_cnt);
  if v_cnt = 0 then
    return;
  end if;
  
  v_url := 'http://api.unisim-soft.com/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=bta28';
  --v_url := 'http://una.md/ticket/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=garadei';
  say('Continuare');
  say('URL:'||v_url);
  
  l_req := utl_http.begin_request(
    url    => v_url,
    --url    => 'http://una.md/ticket/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=tickets',
    method => 'GET'
  );
  
  utl_http.set_header(l_req, 'Pragma', 'no-cache');
  utl_http.set_header(l_req, 'Cache-Control', 'no-cache');
  utl_http.set_header(l_req, 'Connection', 'close');
  
  utl_http.set_response_error_check(enable => TRUE);
  l_resp := utl_http.get_response(r => l_req);

  begin
    loop
      utl_http.read_line(l_resp, buffer);
      v_req_result := v_req_result ||buffer;
    end loop;
    utl_http.end_response(l_resp);
  exception
    when utl_http.end_of_body
    then utl_http.end_response(l_resp);
  end;
  
  if instr(v_req_result, 'OK:SEND') > 0 then
    update un9mail_msg f set
      f.status = 2,
      f.err_msg = null,
      f.sent_date = sysdate      
    where f.nrmsg = p_nrmsg;
  else
    update un9mail_msg f set
      f.status = 1,
      f.err_msg = v_req_result,
      f.sent_date = sysdate 
    where f.nrmsg = p_nrmsg;
  end if;
  
  say('v_req_result: '||v_req_result);
  
  commit;
  
exception
  WHEN OTHERS THEN
    v_req_result:= 'eroare request '||SQLERRM;
   say('v_req_result: '||v_req_result);
    update un9mail_msg f set
      f.status = 1,
      f.err_msg = v_req_result,
      f.sent_date = sysdate 
    where f.nrmsg = p_nrmsg;
    commit;
end;
----------------------------------------------------------------------------------------------------
procedure send_email_post_api(p_nrmsg int) is
  v_url         VARCHAR2(200) := 'https://www.garileauto.md/email_api/send_mail_api.php';
  v_request     UTL_HTTP.req;
  v_response    UTL_HTTP.resp;
  v_boundary    VARCHAR2(100) := '----WebKitFormBoundary123456789';
  v_header      VARCHAR2(32767);
  v_body_header  CLOB; 
  v_body_footer  CLOB;
  v_file_name   VARCHAR2(100);
  v_mail_to     VARCHAR2(200);
  v_mail_cc     VARCHAR2(512);
  v_mail_bcc     VARCHAR2(512);
  v_mail_subject VARCHAR2(200);
  v_mail_body   VARCHAR2(32767);
  v_nrmsg       NUMBER := p_nrmsg;
  v_response_text VARCHAR2(32767);
  v_blob_length  NUMBER;
  v_pos          NUMBER := 1; 
  v_chunk        RAW(32767);
  
  v_un9mail_msg un9mail_msg%rowtype;
  v_un9mail_pack un9mail_pack%rowtype;
  v_content_type varchar2(250);
  v_mail_user varchar2(255);
  
  buffer varchar2(4000);
  v_req_result varchar2(4000);
  l_auth_base64 VARCHAR2(4000);
BEGIN
  begin
    select * into v_un9mail_msg
    from un9mail_msg
    where nrmsg = v_nrmsg;
  exception when others then
     msg('Nu sa gasit mesaj cu nr '||v_nrmsg);
  end;
  
  begin
    SELECT * INTO v_un9mail_pack
    FROM UN9MAIL_PACK
    WHERE nrmsg = v_nrmsg and rownum=1;
  exception when others then
     null;
  end;
  
  v_mail_to := v_un9mail_msg.recipients;
  v_mail_cc := v_un9mail_msg.cc;
  v_mail_bcc := v_un9mail_msg.bcc;
  v_mail_subject := v_un9mail_msg.subject;
  v_mail_body := v_un9mail_msg.text;
  v_mail_user := v_un9mail_msg.sender;
  
  if v_un9mail_pack.nrmsg is not null then
    v_blob_length := DBMS_LOB.GETLENGTH(v_un9mail_pack.pack);
    v_file_name := v_un9mail_pack.filename;
    if instr(v_un9mail_pack.filename, '.pdf') > 0 then
      v_content_type := 'application/pdf';
    elsif instr(v_un9mail_pack.filename, '.xlsx') > 0 then
      v_content_type := 'application/pdf';
    else 
      v_content_type := 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    end if;
  else 
    v_blob_length := 0;
    v_content_type := 'application/x-www-form-urlencoded';
  end if;

  v_body_header := 
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="to"' || CHR(10) || CHR(10) || v_mail_to || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="cc"' || CHR(10) || CHR(10) || v_mail_cc || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="bcc"' || CHR(10) || CHR(10) || v_mail_bcc || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="subject"' || CHR(10) || CHR(10) || v_mail_subject || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="username"' || CHR(10) || CHR(10) || v_mail_user || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    'Content-Disposition: form-data; name="body"' || CHR(10) || CHR(10) || v_mail_body || CHR(10) ||
    '--' || v_boundary || CHR(10) ||
    case when v_un9mail_pack.nrmsg is not null then
      'Content-Disposition: form-data; name="file"; filename="' || v_file_name || '"' || CHR(10) ||
      'Content-Type: '||v_content_type || CHR(10) || CHR(10)
    else ''|| CHR(10) end;

  v_body_footer := CHR(10) || '--' || v_boundary || '--';
  v_request := UTL_HTTP.begin_request(v_url, 'POST', 'HTTP/1.1');
  UTL_HTTP.set_header(v_request, 'Content-Type', 'multipart/form-data; boundary=' || v_boundary);
  UTL_HTTP.set_header(v_request, 'Content-Length', (v_blob_length + LENGTH(v_body_header) + LENGTH(v_body_footer)));
  l_auth_base64 := 'Basic ' || UTL_RAW.cast_to_varchar2(UTL_ENCODE.base64_encode(
                         UTL_RAW.cast_to_raw(API_MAIL_USERNAME || ':' || API_MAIL_PASSWORD)));
  UTL_HTTP.set_header(v_request, 'Authorization', l_auth_base64);

  UTL_HTTP.write_text(v_request, v_body_header);
  
  if v_un9mail_pack.nrmsg is not null then
    WHILE v_pos <= v_blob_length LOOP
      -- Extrage un segment din BLOB
      v_chunk := DBMS_LOB.SUBSTR(v_un9mail_pack.pack, 32767, v_pos);
      v_pos := v_pos + 32767;

      -- Trimite segmentul curent
      UTL_HTTP.write_raw(v_request, v_chunk);
    END LOOP;
  end if;

  UTL_HTTP.write_text(v_request, v_body_footer);

  v_response := UTL_HTTP.get_response(v_request);
  
  begin
    loop
      utl_http.read_line(v_response, buffer);
      v_req_result := v_req_result ||buffer;
    end loop;
    utl_http.end_response(v_response);
  exception
    when utl_http.end_of_body
    then utl_http.end_response(v_response);
  end;

  --UTL_HTTP.read_text(v_response, v_response_text);

  DBMS_OUTPUT.PUT_LINE('Raspuns: ' || v_req_result);
  if instr(v_req_result, 'OK:SEND') > 0 then
    update un9mail_msg f set
      f.status = 2,
      f.err_msg = null,
      f.sent_date = sysdate      
    where f.nrmsg = p_nrmsg;
  else
    update un9mail_msg f set
      f.status = 1,
      f.err_msg = v_req_result,
      f.sent_date = sysdate 
    where f.nrmsg = p_nrmsg;
  end if;

  utl_http.end_response(v_response);
exception
  when others then
    dbms_output.put_line('Eroare: ' || sqlerrm);
end;
end;

/

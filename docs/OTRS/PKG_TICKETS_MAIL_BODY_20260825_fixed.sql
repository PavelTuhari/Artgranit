CREATE OR REPLACE package body pkg_tickets_mail
is
----------------------------------------------------------------------------------------------------
function begin_auth_session
  return UTL_SMTP.connection
is
  v_username_conn varchar2(64);
  v_psw_conn varchar2(64);
begin
  v_username_conn:=utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('support@unisim-soft.com')));
  v_psw_conn := utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('Deosebit88#')));
  
  --v_username_conn:=mail_params.get_user;
  --v_psw_conn := mail_params.get_password;
  
  return pkg_mail_24.begin_auth_session (v_username_conn,
                                         v_psw_conn);
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
function get_lang (p_reservation_code number) return varchar2 is
v_lang varchar2(2);
begin
  select coalesce(r.ticket_lang, o.ticket_lang, det.lang) into v_lang
  from t1rutabroni_detail det, t1rutabroni rb, t0ruta r, t1ruta_m m, t_org_attributes o
  where det.idcasalenta = rb.idcasalenta
    and rb.ruta = m.codu
    and trunc(rb.data) = trunc(m.data) 
    and r.codu = m.rutadebaza
    and r.intrepr = o.org_id
    and rb.idcasalenta = p_reservation_code;
  return v_lang;
end;
----------------------------------------------------------------------------------------------------
function tickets_formating (--  p_conn  in out nocopy utl_smtp.connection,
p_reservation_code number)
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
 v_org_id int := pkg_tickets_utl.get_org_id_by_reservation_code(p_reservation_code);
 v_can_select_places boolean;
 v_reservation_detail t1rutabroni_detail%rowtype := pkg_tickets_utl.get_reservation_detail(p_reservation_code);
 v_ticket_params t_mail_ticket%rowtype;
 v_lang varchar2(2):= get_lang(p_reservation_code);
 
 v_sala integer := null;
begin
  DBMS_LOB.createtemporary(l_blob, false);  
  
  begin
    select * 
    into v_ticket_params 
    from t_mail_ticket
    where org_id = v_org_id
      and lang   = v_lang;
  exception when no_data_found then 
    select * 
    into v_ticket_params 
    from t_mail_ticket
    where org_id = 3260
      and lang   = v_lang;
  end;
    
  v_org_info := '&cod_fiscal=' || v_ticket_params.org_name || ' <br>c/f: ' || v_ticket_params.cod_fiscal;

v_ticket_params.n_top_text := replace(v_ticket_params.n_top_text, '#p_reservation_code#',p_reservation_code);

begin
select a.sala into v_sala
from T1RUTABRONI r, th_afisha a 
where r.idcasalenta=p_reservation_code 
  and a.cod = r.ruta
  and a.data = r.data;
EXCEPTION
   WHEN NO_DATA_FOUND THEN
      v_sala := null;
END;

v_local := 
  '&n_location='|| v_ticket_params.n_location ||
  '&n_event='|| v_ticket_params.n_event ||
  '&n_date='|| v_ticket_params.n_date ||
  '&n_price='|| v_ticket_params.n_price ||
  '&n_order_id='|| v_ticket_params.n_order_id || 
  '&n_rez_cod='|| v_ticket_params.n_rez_cod ||
  '&lege='|| v_ticket_params.lege ||
  '&n_locul='|| v_ticket_params.n_locul ||
  '&n_rindul='|| v_ticket_params.n_rindul || 
  '&n_sectorul='|| v_ticket_params.n_sectorul || 
  '&n_info_link='|| v_ticket_params.n_info_link || 
  '&n_design='|| v_ticket_params.n_design || 
  '&n_access='|| v_ticket_params.n_access ||
  '&n_free='|| v_ticket_params.n_free ||
  '&n_top_text=' || v_ticket_params.n_top_text ||
  '&n_barcode_height=' || v_ticket_params.n_barcode_height ||
  '&n_barcode_width=' || v_ticket_params.n_barcode_width || 
  '&n_barcode_top=' ||  round( (70 - v_ticket_params.n_barcode_width) / 2)||
  '&n_sala='||v_sala;

  for c
  in (select   s.*
           ,decode (s.lang,'en', 'Sector: '|| s.sector|| '/R'|| s.myrow|| ' Place:'|| s.loc,
                                              'ru','Сектор: '|| s.sector|| '/Р'|| s.myrow|| ' Место:'|| s.loc,
                                              'Sector: '|| s.sector|| '/R'|| s.myrow|| ' Locul:'|| s.loc
           ) as place
           ,SUBSTR(rowPlaceText_, 1, INSTR(rowPlaceText_, 'Locul')-1) rowPlaceText
        from   (select   distinct b.cod,
                          (select   codbc
                           from   t0bilet_codbc
                           where   cod = b.cod) barcod
                           ,r.ruta
                           ,a.dataora as data
                           ,pkg_tickets_utl.get_date_in_words(to_date(a.data), v_lang) date_in_words
                           ,decode (v_lang, 'en', nvl (a.event_name_en, a.denum),
                                                         'ru', nvl (a.event_name_ru, a.denum),
                                                         nvl (a.event_name_ro, a.denum)) event_name
                           ,decode (v_lang, 'en', address_en,
                                            'ru', address_ru,
                                            'ro', address_ro) address
                           ,decode (v_lang, 'en', nvl (a.name_en, a.den_sala),
                                                         'ru', nvl (a.name_ru, a.den_sala),
                                                         nvl (a.name_ro, a.den_sala)) location
                         ,circus.get_comision_circ (b.loc,a.sala,r.ruta,r.data) as cost
                         ,(select   s.name_ro
                           from   t0marca_sectors s, t0marca_places p
                           where       s.nrord = p.sector_nr
                                   and s.autobus = p.cod_autobus
                                   and s.tip = p.tip
                                   and p.abs_nr = b.loc
                                   and p.cod_autobus = a.sala) as sector
                         ,(select   s.tribune_name
                           from   t0marca_sectors s, t0marca_places p
                           where       s.nrord = p.sector_nr
                                   and s.autobus = p.cod_autobus
                                   and s.tip = p.tip
                                   and p.abs_nr = b.loc
                                   and p.cod_autobus = a.sala) as tribuna
                         ,circus.get_row_by_abs_nr (a.sala, b.loc) myrow
                         ,circus.get_placetext_by_abs_nr (a.sala, b.loc) loc
                         ,v_lang lang
                         ,a.org_id
                         ,a.time_in
                         ,circus.GET_STR_RIND_LOC_BY_ABSLOC_24(a.sala, b.loc) rowPlaceText_
                         ,nvl((select k.valuta from WS_EVENTS_TIME k where k.CODU = r.ruta and rownum = 1), 'MDL') valuta
                  from   t1rutabroni r,
                         t0bilet b,
                         th_afisha a,
                         t1rutabroni_detail d
                 where       r.idcasalenta = p_reservation_code
                         and b.idcaslenta = r.idcasalenta
                         and a.cod = r.ruta
                         and a.data = r.data
                         and b.idcaslenta = d.idcasalenta) s order by 1)
  loop
     if v_counter = 1
     then
        v_url_print := 'barcode=' || c.barcod || '&res_cod='|| p_reservation_code|| v_local || v_org_info
                          || '&logo=' || case when c.ruta = '200629' then 'empty.jpg' else v_ticket_params.logo end;
        v_first_ticket_hash := c.barcod;
     end if;

     v_can_select_places := pkg_tickets_utl.can_select_places(c.cod);

     v_url_print := v_url_print || '&barcode' || v_counter || '=' || c.barcod|| '&location'|| v_counter|| '=' || c.location 
                          || '&event_name' || v_counter || '=' || c.event_name || '&date'|| v_counter || '=' || c.data
                          || '&access' || v_counter || '='|| c.time_in 
                          || '&cost' || v_counter|| '='|| c.cost
                          || '&valuta' || v_counter|| '='|| c.valuta
                          || '&sectorul' || v_counter|| '='|| c.sector
                          || '&rindul' || v_counter || '=' || case when v_can_select_places then c.myrow end
                          || '&locul'|| v_counter || '=' || case when v_can_select_places then c.loc end
                          || '&address'|| v_counter || '=' || c.address
                          || '&date_in_words'|| v_counter || '=' || c.date_in_words
                          || '&rowPlaceText'|| v_counter || '=' || c.rowPlaceText;
     v_counter := v_counter + 1;
     --Genirate tickets for mobile devices
     v_url := 'http://linktickets1.una.md/um/ticket/ticketp.php?barcode=' || c.barcod || '&location=' || c.location 
                          || '&event_name=' || c.event_name || '&date='|| c.data|| '&access=' || c.time_in
                          || '&cost=' || c.cost || '&tribuna=' || c.tribuna || '&sectorul=' || c.sector 
                          || '&rindul='|| case when v_can_select_places then c.myrow end
                          || '&locul=' || case when v_can_select_places then c.loc end
                          || '&address=' || c.address || '&date_in_words=' || c.date_in_words;
  /*  pkg_mail_24_blob_atach.add_attachments(p_conn
          ,HTTPURITYPE.createuri(utl_url.escape(v_url,false,'UTF8')).getblob()
          , c.barcod);*/
  -- Пока не отпавлять для мобильной телефонов --temporary excluded
  end loop;

  if v_counter > 1
  then
     say ('####'||chr(13)||v_url_print||chr(13)||'####');
   l_http_request  := UTL_HTTP.begin_request(url=>v_ticket_params.ticket_php, method => 'POST');
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
     update   t1rutabroni_detail t
        set   ticket_url = 'http://linktickets1.una.md/um/ticket/pdf/Bilete_' || v_first_ticket_hash || '.pdf'
        --, t.mail_sent = sysdate
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
  p_sender         varchar2,  
  p_subject        varchar2,
  p_text           varchar2,
  p_cc             varchar2 := null,
  p_bcc            varchar2 := 'tickets@una.md',
--      p_bcc            VARCHAR2 := 'circul.chisinau@mail.md',
  p_attachments    mail_attachments_type := mail_attachments_type ()
)
is
  v_conn         UTL_SMTP.connection;
  v_url          varchar2 (1000);
  v_result       blob;
  v_event_info   varchar2 (3000);
  p_bcc1          varchar2 (1000):=p_bcc;
begin
  v_conn := begin_auth_session;
  if p_bcc = 'tickets@una.md' then p_bcc1:= NULL; end if;
  pkg_mail_24.begin_mail_in_session (
     conn         => v_conn,
     sender       => p_sender,
     recipients   => p_recipients,
     cc           => p_cc,
     bcc          => p_bcc1,
     subject      => p_subject,
     mime_type    => pkg_mail_24.multipart_mime_type
  );

  pkg_mail_24.attach_mb_text (conn => v_conn, data => p_text, last => false
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
  
  pkg_mail_24.end_mail (conn => v_conn);
exception when others then
     un$process_log.log_exception (un$process_log.get_id ('mail_server'));
end;
----------------------------------------------------------------------------------------------------
procedure mail(
  p_recipients     varchar2,
  p_sender         varchar2,
  p_subject        varchar2,
  p_text           blob,
  p_cc             varchar2 := null,
  p_bcc            varchar2 := 'tickets@una.md', -- desactivated pt 2021 12 DECODE(:p_bcc,'tickets@una.md', NULL, :p_bcc) 
--      p_bcc            VARCHAR2 := 'circul.chisinau@mail.md',
  p_attachments    mail_attachments_type := mail_attachments_type ()
) is
  v_conn         UTL_SMTP.connection;
  v_url          varchar2 (1000);
  v_result       blob;
  v_event_info   varchar2 (3000);
  v_type varchar2(4000):='multipart/mixed; boundary="-----7D81B75CCC90D2974F7A1CBD"; charset=utf-8';
  p_bcc1          varchar2 (1000):=p_bcc;
begin
  v_conn := begin_auth_session;
  if p_bcc = 'tickets@una.md' then p_bcc1:= NULL; end if;
  pkg_mail_24.begin_mail_in_session (
     conn         => v_conn,
     sender       => p_sender,
     recipients   => p_recipients,
     cc           => p_cc,
     bcc          => p_bcc1,
     subject      => p_subject,
     --mime_type => 'text/plain; charset=utf-8'
     mime_type => v_type
  );

  pkg_mail_24.begin_attachment(v_conn, 'text/plain; charset=utf-8', true, null);
  pkg_mail_24.write_raw(v_conn, p_text);
  pkg_mail_24.end_attachment(v_conn, false);

  --Adding attachments if exists
  for i in 1 .. p_attachments.COUNT
  loop
     pkg_mail_blob_atach.add_attachments (v_conn,
                                          p_attachments (i).data,
                                          p_attachments (i).filename,
                                          p_attachments (i).format);
  end loop;
  
  pkg_mail_24.end_mail (conn => v_conn);
exception when others then
     un$process_log.log_exception (un$process_log.get_id ('mail_server'));
end;
----------------------------------------------------------------------------------------------------
function get_mail_settings(p_reservation_code int, p_lang varchar2, p_mail_type number)
  return v_mail_settings%rowtype
is
  v_settings v_mail_settings%rowtype;
  v_org_id number(30);
  v_autobus number(7);
  v_codu varchar2(10);
  v_reservation t1rutabroni%rowtype := pkg_tickets_utl.get_reservation(p_reservation_code);
  v_reservation_detail t1rutabroni_detail%rowtype := pkg_tickets_utl.get_reservation_detail(p_reservation_code);
  v_route t0ruta%rowtype := pkg_tickets_utl.get_route(v_reservation.ruta);
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
    where (org_id = :intrepr or org_id is null)
      and (autobus = :autobus or autobus is null)
      and (codu = :codu or codu is null)
      and lang = :p_lang
      and mail_type = :p_mail_type) a
  where rn = 1
  '  into v_settings using v_route.intrepr, v_route.autobus, v_route.codu, p_lang, p_mail_type ;
  
  if v_settings.bcc like '%#user_mail#%' then
    v_settings.bcc := replace(v_settings.bcc, '#user_mail#', v_reservation_detail.email);
  end if;
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
return 'http://' || pkg_tickets_utl.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name 
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
return 'http://' || pkg_tickets_utl.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name
               || '/' ||p_org ;
end;
----------------------------------------------------------------------------------------------------
function get_event_link
(
  p_org varchar2,
  p_event_txt_id varchar2
) return varchar2 is
begin
return 'http://' || pkg_tickets_utl.get_domen_by_org_url(p_org) ||'.md/' || pkg_tickets_utl.get_project_name
               || '/' ||p_org || '/' || p_event_txt_id;
end;
----------------------------------------------------------------------------------------------------
function get_lifetime_text
(
  p_idbroni int,
  p_lang varchar2
) return varchar2 is
v_lifetime number:= get_lifetime(p_idbroni);
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
  v_lang varchar2(2) := get_lang(p_reservation.idcasalenta);
  v_text varchar2(4000) := p_text;
  v_rules varchar2(4000);
  v_org varchar2(128) := pkg_tickets_utl.get_org_url_by_cod(p_route.intrepr);
  v_cancel_plan_data date := broni.get_cancel_plan_data(p_reservation.idcasalenta);
  v_cancel_link varchar2(4000) := get_cancel_link(v_lang, v_org, p_route.event_txt_id, p_reservation.idcasalenta);
  v_merchant_link varchar2(4000) := get_merchant_link(v_org);
  v_cabinet_link varchar2(4000) := 'https://una.md/ticket/user.php?org='||v_org;
  v_event_link varchar2(4000) := get_event_link (v_org, p_route.event_txt_id);
  v_lifetime_text varchar2(1024):= get_lifetime_text(p_reservation.idcasalenta, v_lang);
begin
  
  select replace(lege,'<br>') into v_rules 
  from t_mail_ticket 
  where org_id = p_route.intrepr
    and lang = v_lang;

  v_text := replace(v_text, '#reservation_code#', p_info.idcasalenta);
  v_text := replace(v_text, '#event_name#', p_route.denumirea);
  v_text := replace(v_text, '#org_name#', case v_lang when 'ro' then p_org_attributes.title_ro
                                                      when 'en' then p_org_attributes.title_en
                                                      when 'ru' then p_org_attributes.title_ru end);
  v_text := replace(v_text, '#rules#', v_rules);                                                             
  v_text := replace(v_text, '#event_date#', TO_CHAR (p_reservation.data, 'dd.mm.yyyy'));
  v_text := replace(v_text, '#event_time#', TO_CHAR (p_route.time_out, 'hh24:mi'));
  v_text := replace(v_text, '#broni_date#', TO_CHAR (p_reservation.databroni, 'dd.mm.yyyy'));
  v_text := replace(v_text, '#broni_time#', TO_CHAR (p_reservation.databroni, 'hh24:mi'));  
  v_text := replace(v_text, '#first_name#', p_info.first_name);
  v_text := replace(v_text, '#last_name#', p_info.last_name);
  v_text := replace(v_text, '#phone#', p_info.phone);
  v_text := replace(v_text, '#location_text#', p_location_text);
  v_text := replace(v_text, '#website_url#', p_org_attributes.website_url);
  v_text := replace(v_text, '#email#', p_org_attributes.email);
  v_text := replace(v_text, '#website_contacts_url#', p_org_attributes.website_contacts_url);
  v_text := replace(v_text, '#event_place#', nvl( case v_lang when 'ro' then p_marca.name_ro
                                                              when 'ru' then p_marca.name_ru
                                                              when 'en' then p_marca.name_en end, p_marca.denumirea));
  v_text := replace(v_text, '#event_address#', nvl( case v_lang when 'ro' then p_marca.address_ro
                                                                when 'ru' then p_marca.address_ru
                                                                when 'en' then p_marca.address_en end, p_marca.denumirea));
  v_text := replace(v_text, '#cancel_link#', v_cancel_link);
  v_text := replace(v_text, '#merchant_link#', v_merchant_link);
  v_text := replace(v_text, '#event_link#', v_event_link);
  v_text := replace(v_text, '#cabinet_link#', v_cabinet_link);
  v_text := replace(v_text, '#cancel_plan_data#', TO_CHAR (v_cancel_plan_data, 'hh24:mi dd.mm.yyyy'));  
  v_text := replace(v_text, '#lifetime_text#', v_lifetime_text);
  v_text := replace(v_text, '#org_url#', v_org);
  
return v_text; 
end;
--------------------------------------------------------------------------------
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
  --NG 23.02.2024
  --v_lang varchar2(2) := get_lang(p_reservation.idcasalenta);
  v_lang varchar2(2) := 'ro';
  v_text blob := p_text;
  v_rules varchar2(4000);
  v_org varchar2(128) := pkg_tickets_utl.get_org_url_by_cod(p_route.intrepr);
  v_cancel_plan_data date := broni.get_cancel_plan_data(p_reservation.idcasalenta);
  v_cancel_link varchar2(4000) := get_cancel_link(v_lang, v_org, p_route.event_txt_id, p_reservation.idcasalenta);
  v_merchant_link varchar2(4000) := get_merchant_link(v_org);
  v_cabinet_link varchar2(4000) := p_org_attributes.website_url||'/ticket/user.php?org='||v_org;  
  v_event_link varchar2(4000) := get_event_link (v_org, p_route.event_txt_id);
  v_lifetime_text varchar2(1024):= get_lifetime_text(p_reservation.idcasalenta, v_lang);
  v_nvarchar nvarchar2(256);
   v_cancel_captcha_link varchar2(4000);
  v_linck_pasport varchar2(4000);
begin
  dbms_output.put_line('p_reservation.idcasalenta:'||p_reservation.idcasalenta);
  begin
    select replace(lege,'<br>') into v_rules 
    from t_mail_ticket 
    where org_id = p_route.intrepr
      and lang = v_lang;
  exception when no_data_found then
    select replace(lege,'<br>') into v_rules  --Если не ввели настройки, берём дефолтные 
    from t_mail_ticket 
    where org_id = 0
      and lang = v_lang;
  end;
  
   v_cancel_captcha_link := p_org_attributes.website_url || pkg_tickets_utl.get_project_name
                  || '/cancel_reservation.php?code='||p_reservation.idcasalenta;
                  
  select /*p_org_attributes.website_url*/'https://unisim-soft.com/tickets.unisim-soft.com/' || 
         pkg_tickets_utl.get_project_name || 
         '/personal_data.php?language='||v_lang||'&code='||p_reservation.idcasalenta||
         '&hash=' || circus.get_hash_by_idbroni(p_reservation.idcasalenta)
  into v_linck_pasport from dual;
  
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#reservation_code#', p_info.idcasalenta);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_name#', pkg_tickets_utl.get_name_blob_by_codu(p_route.codu));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#org_name#', case v_lang when 'ro' then p_org_attributes.title_ro
                                                      when 'en' then p_org_attributes.title_en
                                                      when 'ru' then p_org_attributes.title_ru end);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#rules#', v_rules);                                                             
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_date#', TO_CHAR (p_reservation.data, 'dd.mm.yyyy'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_time#', TO_CHAR (p_route.time_out, 'hh24:mi'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#broni_date#', TO_CHAR (p_reservation.databroni, 'dd.mm.yyyy'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#broni_time#', TO_CHAR (p_reservation.databroni, 'hh24:mi')); 
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#first_name#', p_info.first_name);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#last_name#', p_info.last_name);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#phone#', p_info.phone);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#location_text#', p_location_text);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#website_url#', p_org_attributes.website_url);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#email#', p_org_attributes.email);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#org_phone#', p_org_attributes.CASHDESK_PHONE);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#website_contacts_url#', p_org_attributes.website_contacts_url);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_place#', nvl( case v_lang when 'ro' then p_marca.name_ro
                                                              when 'ru' then p_marca.name_ru
                                                              when 'en' then p_marca.name_en end, p_marca.denumirea));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_address#', nvl( case v_lang when 'ro' then p_marca.address_ro
                                                                when 'ru' then p_marca.address_ru
                                                                when 'en' then p_marca.address_en end, p_marca.denumirea));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cancel_link#', v_cancel_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#merchant_link#', v_merchant_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#event_link#', v_event_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cabinet_link#', v_cabinet_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cancel_plan_data#', TO_CHAR (v_cancel_plan_data, 'hh24:mi dd.mm.yyyy'));  
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#lifetime_text#', v_lifetime_text);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#org_url#', v_org);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#cancel_captcha_link#',v_cancel_captcha_link);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#rrn#', p_reservation.rrn_init);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#total_amount#', pkg_tickets_utl.get_sum_by_idbroni(p_info.idcasalenta));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#approval#', p_reservation.approval);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#transaction_date#', TO_CHAR (p_reservation.transaction_date, 'hh24:mi dd.mm.yyyy'));
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#merchant_name#', p_org_attributes.merchant_name);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#refund_policy#', p_org_attributes.refund_policy);
  v_text := LOB_UTL_PCKG.replace_blob(v_text, '#linck_pasport#', v_linck_pasport);
  
  
return v_text; 
end;
----------------------------------------------------------------------------------------------------
procedure send_mail (p_reservation_code int, p_mail_type number)
is
  v_info t1rutabroni_detail%rowtype := pkg_tickets_utl.get_reservation_detail (p_reservation_code) ;
  v_reservation t1rutabroni%rowtype := pkg_tickets_utl.get_reservation (p_reservation_code) ;
  v_route t0ruta%rowtype := pkg_tickets_utl.get_route(v_reservation.ruta);
  v_marca t0marca%rowtype := pkg_tickets_utl.get_marca(v_route.autobus, v_route.tip);
  v_org_attributes t_org_attributes%rowtype := pkg_tickets_utl.get_org_attributes(v_route.intrepr);
  v_can_select_places boolean := pkg_tickets_utl.can_select_places(p_reservation_code);
  
  --NG 23.02.2024
  --v_lang varchar2(2) := get_lang(p_reservation_code);
  v_lang varchar2(2) := 'ro';
  
  v_settings v_mail_settings%rowtype := get_mail_settings(p_reservation_code, v_lang, p_mail_type);
  v_subject varchar2(256) := v_settings.subject;
  v_text_blob    blob := v_settings.text_blob;
  v_text    varchar2(4000) := v_settings.text;
  v_org_url varchar2(512);
  v_email_bcc varchar2(512);
  v_email_block integer;
  v_lifetime_text varchar2(1024):= get_lifetime_text(p_reservation_code, 'en');
  
  --NG 23.02.2024
  --v_location_text   varchar2(4000) := pkg_tickets_utl.get_location_text(p_reservation_code, v_route.autobus, v_info.lang);
  v_location_text   varchar2(4000) := pkg_tickets_utl.get_location_text(p_reservation_code, v_route.autobus, 'ro');

  v_attachments     mail_attachments_type := mail_attachments_type ();
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
  v_un9mail_pack un9mail_pack%rowtype;
  v_text_mail long;
begin
  for c in (select cod from t0bilet where idcaslenta = p_reservation_code)
  loop
    v_can_select_places := pkg_tickets_utl.can_select_places(c.cod);
    if v_can_select_places then 
      exit;
    end if;
  end loop;
  
  select um into v_org_url
  from tms_univers
  where cod = v_route.intrepr;

  begin
    select email into v_email_bcc from tms_bcc_org where org_url = v_org_url;
    exception when no_data_found then
    null;
  end;
  
  begin
    select send_mails into v_email_block from TMS_SEND_MAIL_ORG where org_url = v_org_url;
    exception when no_data_found then
    null;
  end;

  
   if v_email_bcc is not null then 
      v_email_bcc:=','||v_email_bcc;
    end if;
  

  /*if not v_can_select_places and v_settings.text_standing is not null then
    v_text := v_settings.text_standing;
  end if;*/

  v_subject := replace(v_subject, '#reservation_code#', p_reservation_code);
  
  v_subject := replace(v_subject, '#lifetime_text#', v_lifetime_text);
  
    v_text_blob := replace_variables_blob(v_text_blob, v_location_text, v_route, v_reservation, v_info, v_marca, v_org_attributes);
    
    --NG, 07.02.2024 PHP API
    v_text_mail := UTL_RAW.CAST_TO_VARCHAR2(dbms_lob.substr(v_text_blob));
    v_nrmsg := id_mail_sender.nextval;
    
    v_un9mail_msg.nrmsg := v_nrmsg;
    v_un9mail_msg.subject := v_subject;
    v_un9mail_msg.sender := 'support@unisim-soft.com';
    v_un9mail_msg.text := v_text_mail;
    v_un9mail_msg.status := 1;
    v_un9mail_msg.recipients := v_info.email;
    v_un9mail_msg.cc := 'c_tickets_UNAmd@googlegroups.com'||v_email_bcc;
    ------------------------------------------
                      
  if p_mail_type = 3 then
      v_attachments.EXTEND ();
      v_attachments (1) := mail_attachments_table (null, null, null);
      v_attachments := tickets_formating (p_reservation_code);
    if v_settings.id_banner is not null then
      v_attachments.EXTEND ();
      v_attachments (2) := mail_attachments_table (v_settings.image_name, v_settings.image, v_settings.image_format );
    end if;

      if v_attachments.COUNT > 0
      then
        if v_email_block<>1 or v_email_block is null then
             mail (v_info.email, 'support@unisim-soft.com',
                 v_subject,
                 v_text_blob,
                 p_attachments   => v_attachments,
                 p_bcc => /*v_settings.bcc||*/v_email_bcc);  
          
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
          
          update t1rutabroni_detail set mail_sent = sysdate where idcasalenta = p_reservation_code; 
          un$process_log.LOG (
              un$process_log.get_id ('mail_server'),
                 'Письмо отправлено,прикреплено '
              || v_attachments.COUNT
              || ' файлов',
              'I',
              p_reservation_code
           );
            
        end if;
      else
         un$process_log.log_exception (
            un$process_log.get_id ('mail_server'),
            'Не сформированно ни одного вложения, отправка невозможна!',
            p_reservation_code
         );
        
      end if;
  else
   if v_email_block<>1 or v_email_block is null or p_mail_type=2 then
    --NG, 07.02.2024
    --mail (v_info.email, 'support@unisim-soft.com', v_subject, v_text_blob, p_bcc => /*v_settings.bcc||*/v_email_bcc);
    
    fill_un9mail_msg(v_un9mail_msg);
    send_email_api_php(v_nrmsg);
    
    un$process_log.LOG (un$process_log.get_id ('mail_server'),
                      'Письмо ' || p_mail_type || ' отправлено,',
                      'I',
                      p_reservation_code);
   end if;    
  end if;
exception when others then 
  un$process_log.log_exception (un$process_log.get_id ('mail_server'), p_nrdoc => p_reservation_code );
end;

procedure send_error(p_error_text varchar2) is
begin
    mail ('support@unisim-soft.com', 'support@unisim-soft.com', 
          'Web-method error. Project '  || pkg_tickets_utl.get_project_name, p_error_text, p_bcc => null);
end;

----------------------------------------------------------------------------------------------------
procedure fill_un9mail_msg(p_un9mail_msg un9mail_msg%rowtype) is
  pragma autonomous_transaction;
begin
    insert into un9mail_msg
    (nrmsg, subject, sender, text, status, recipients, cc)
  values
    (p_un9mail_msg.nrmsg, p_un9mail_msg.subject, p_un9mail_msg.sender, 
     p_un9mail_msg.text, p_un9mail_msg.status, p_un9mail_msg.recipients, p_un9mail_msg.cc);
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
  buffer varchar2(32767);
  -- 25.08.2026: ответ PHP копился в varchar2(4000) -> ORA-06502 на письмах
  -- крупнее 4000 байт (ни одно такое письмо не уходило). Теперь CLOB.
  v_req_result   clob;
  v_cnt          integer;
  v_attempt      pls_integer := 0;
  c_max_attempts constant pls_integer := 3;
  v_sent         boolean := false;
  v_last_err     varchar2(4000);
begin
  say('start api');
  select count(*) into v_cnt from UN9MAIL_MSG i where i.nrmsg = p_nrmsg and i.status = 1;
  say('v_cnt '||v_cnt);
  if v_cnt = 0 then
    return;
  end if;
  say('Continuare');

  while v_attempt < c_max_attempts and not v_sent loop
    v_attempt := v_attempt + 1;
    begin
      dbms_lob.createtemporary(v_req_result, true);

      l_req := utl_http.begin_request(
        url    => 'http://api.unisim-soft.com/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=tickets',
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
          if buffer is not null then
            dbms_lob.writeappend(v_req_result, length(buffer), buffer);
          end if;
        end loop;
      exception
        when utl_http.end_of_body then null;
      end;
      utl_http.end_response(l_resp);

      if dbms_lob.getlength(v_req_result) > 0
         and dbms_lob.instr(v_req_result, 'OK:SEND') > 0 then
        v_sent := true;
      else
        v_last_err := dbms_lob.substr(v_req_result, 3900, 1);
      end if;

      dbms_lob.freetemporary(v_req_result);

    exception
      when others then
        v_last_err := 'eroare request (incercarea '||v_attempt||') '||SQLERRM;
        -- без end_response дескрипторы утекают -> ORA-29270 на следующих письмах
        begin utl_http.end_response(l_resp); exception when others then null; end;
        begin dbms_lob.freetemporary(v_req_result); exception when others then null; end;
    end;

    -- пауза перед повтором снимает HTTP 508 при пакетной рассылке
    if not v_sent and v_attempt < c_max_attempts then
      dbms_lock.sleep(2 * v_attempt);
    end if;
  end loop;

  if v_sent then
    update un9mail_msg f set
      f.status = 2,
      f.err_msg = null,
      f.err_code = null,
      f.sent_date = sysdate
    where f.nrmsg = p_nrmsg;
  else
    -- status=3 - окончательный отказ; sent_date не затираем, чтобы
    -- сохранилось время постановки в очередь
    update un9mail_msg f set
      f.status = 3,
      f.err_msg = v_last_err,
      f.err_code = v_attempt
    where f.nrmsg = p_nrmsg;
  end if;

  commit;
end;

end;

/

CREATE OR REPLACE package body pkg_ticket_mail is
----------------------------------------------------------------------------------------------------
type t_mail_data is record
(
  conn utl_smtp.connection,
  sender varchar2(1024),
  recipients varchar2(1024),
  cc varchar2(1024),
  bcc varchar2(1024),
  subject varchar2(512),
  mime_type varchar2(256)
);
----------------------------------------------------------------------------------------------------
function process_name return varchar2 as begin return 'ticket_mail'; end;

function process_id return number as
begin  return un$process_log.get_id(process_name); end;
----------------------------------------------------------------------------------------------------
procedure get_article_data(p_article_id number, p_article in out nocopy article%rowtype) is
begin
  select * into p_article from article where id = p_article_id;
exception when no_data_found then
  msg('Article with id = '||p_article_id||' not found!');
end;
----------------------------------------------------------------------------------------------------
procedure get_ticket_data(p_ticket_id number, p_ticket in out nocopy ticket%rowtype) is
begin
  select * into p_ticket from ticket where id = p_ticket_id;
exception when no_data_found then
  msg('Ticket with id = '||p_ticket_id||' not found!');
end;
----------------------------------------------------------------------------------------------------
procedure get_ticket_data_by_article(p_article_id number, p_ticket in out nocopy ticket%rowtype) is
v_ticket_id number;
begin
  select ticket_id into v_ticket_id from article where id = p_article_id;
  get_ticket_data(v_ticket_id, p_ticket);
exception when no_data_found then
  msg('Article with id = '||p_article_id||' not found!');
end;
----------------------------------------------------------------------------------------------------
function get_article_owner(p_article_id number) return int is
v_result int;
begin
  select min(owner_id) into v_result from ticket_history t
  where t.ticket_id = (select ticket_id from article where id = p_article_id)
    and t.article_id = p_article_id;

  return v_result;
end;
----------------------------------------------------------------------------------------------------
function get_user_email_addr(p_user_id int) return varchar2 is
  v_addr varchar2(256);
begin
  select min(preferences_value) into v_addr from user_preferences
  where user_id = p_user_id and preferences_key = 'UserEmail';
  /*if v_addr is null then
    msg('Email address for user with id = '||p_user_id||' is not set!');
  end if;*/
  return nvl(v_addr,'email@unisim-soft.com');
end;
----------------------------------------------------------------------------------------------------
function get_client_email_addr_by_tn(p_tn varchar2) return varchar2 is
  v_addr varchar2(256);
begin
  select min(c.email) into v_addr
  from customer_user c, ticket t
  where 0=0
    and c.login = t.customer_user_id
    and t.tn = p_tn;
  return v_addr;
end;
----------------------------------------------------------------------------------------------------
function get_client_email_addr_by_tid(p_ticket_id varchar2) return varchar2 is
  v_addr varchar2(256);
begin
  select min(c.email) into v_addr
  from customer_user c, ticket t
  where 0=0
    and c.login = t.customer_user_id
    and t.id = p_ticket_id;
  return v_addr;
end;
----------------------------------------------------------------------------------------------------
function get_ticket_created_text return varchar2 is
  v_result varchar2(4000);
begin
  select text into v_result
  from t_mail_texts
  where msg_type = 'ticket_created';

  return v_result;
end;
----------------------------------------------------------------------------------------------------
function format_message(p_article_id number, p_history_type_id number) return clob is
v_article article%rowtype;
v_ticket ticket%rowtype;
v_owner system_user%rowtype;
v_user system_user%rowtype;
v_template long;
v_body clob;
v_body_pattern varchar2(64);
v_body_pos int;
begin
  get_article_data(p_article_id,v_article);
  get_ticket_data(v_article.ticket_id,v_ticket);

  select * into v_owner from system_user where id = v_ticket.user_id;
  select * into v_user from system_user where id = v_article.create_by;

  select min(text) into v_template from notifications
  where notification_type = 'Agent::'||(select name from ticket_history_type where id = p_history_type_id)
    and notification_language = 'ru';

  v_template := replace(v_template,'<OTRS_OWNER_USERFIRSTNAME>',v_owner.first_name);
  v_template := replace(v_template,'<OTRS_CURRENT_USERFIRSTNAME>',v_user.first_name);
  v_template := replace(v_template,'<OTRS_CURRENT_USERLASTNAME>',v_user.last_name);
  v_template := replace(v_template,'<OTRS_TICKET_TicketNumber>',v_ticket.tn);
  v_template := replace(v_template,'<OTRS_TICKET_TicketID>',v_ticket.id);
  v_template := replace(v_template,'<OTRS_CONFIG_HttpType>','http');
  v_template := replace(v_template,'<OTRS_CONFIG_FQDN>','uniacc.md');
  v_template := replace(v_template,'<OTRS_CONFIG_ScriptAlias>','otrs/');

  if instr(v_template,'<OTRS_COMMENT>') > 0 then
    v_body_pattern := '<OTRS_COMMENT>';
  elsif instr(v_template,'<OTRS_CUSTOMER_BODY>') > 0 then
    v_body_pattern := '<OTRS_CUSTOMER_BODY>';
  else
    msg('Message body pattern not found!');
  end if;

  v_body_pos := instr(v_template,v_body_pattern);

  v_body := substr(v_template,1,v_body_pos - 1);
  dbms_lob.append(v_body,v_article.a_body);
  dbms_lob.append(v_body,substr(v_template,v_body_pos + length(v_body_pattern)));

  return v_body;
end;
----------------------------------------------------------------------------------------------------
function begin_session return utl_smtp.connection is
  v_username_conn varchar2(64);
  v_psw_conn varchar2(64);
begin
  v_username_conn:=utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('support_unamd@erp1.eu')));
  v_psw_conn := utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('^b3,]Ldklr^q')));
  
  --v_username_conn:=mail_params.get_user;
  --v_psw_conn := mail_params.get_password;
  
  -- utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw(
  return pkg_mail_24.begin_auth_session(v_username_conn, v_psw_conn);
end;
----------------------------------------------------------------------------------------------------
procedure begin_mail(p_mail in out nocopy t_mail_data) is
begin
   if get_env('send_report_day_all') = 1 then
     p_mail.conn := begin_session;
     pkg_mail_24.begin_mail_in_session
     (
       conn => p_mail.conn,
       sender => p_mail.sender,
       recipients => p_mail.recipients,
       --
       cc => 'otuhari@mail.ru,pt@una.md,secretar@unisim-soft.com',
       bcc => p_mail.bcc,
       subject => p_mail.subject,
       mime_type => pkg_mail_24.multipart_mime_type
     );
   else
     p_mail.conn := begin_session;
     pkg_mail_24.begin_mail_in_session
     (
       conn => p_mail.conn,
       sender => p_mail.sender,
       recipients => p_mail.recipients,
       --
       cc => p_mail.cc,
       bcc => p_mail.bcc,
       subject => p_mail.subject,
       mime_type => pkg_mail_24.multipart_mime_type
     );
   end if;
end;
----------------------------------------------------------------------------------------------------
procedure add_attachments(p_article_id number, p_mail in out nocopy t_mail_data) is
n int;
len int;
begin
  for c in
  (
    select * from article_attachment
    where article_id = p_article_id
    order by id
  )
  loop
    pkg_mail_24.begin_attachment
    (
      conn => p_mail.conn,
      mime_type => c.content_type,
      filename => c.filename,
      inline => false,
      transfer_enc => 'base64'
    );
    n := 1;
    len := dbms_lob.getlength(c.content);
    while n < len loop
      pkg_mail_24.write_raw(p_mail.conn, utl_raw.cast_to_raw(
              dbms_lob.substr(c.content, pkg_mail_24.max_base64_line_width, n)));
      n := n + pkg_mail_24.max_base64_line_width;
    end loop;
    pkg_mail_24.end_attachment(p_mail.conn);
  end loop;
end;
----------------------------------------------------------------------------------------------------
-- Если считывать информацию о владельце заявки из ticket, то при смене владельца сообщение
-- должно отправляться сразу после смены или до следующего изменения владельца, иначе отправка будет
-- произведена по другому адресу.
----------------------------------------------------------------------------------------------------
procedure notification(p_article_id number, p_history_type_id number) is
v_article article%rowtype;
v_ticket ticket%rowtype;
v_mail t_mail_data;
v_body clob;
begin
  get_article_data(p_article_id,v_article);
  get_ticket_data(v_article.ticket_id,v_ticket);
  --
  -- note-internal
  if v_article.article_sender_type_id = 1 and v_article.article_type_id = 9 then
    --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.sender := 'support_unamd@erp1.eu';
--    v_mail.recipients := get_user_email_addr(get_article_owner(p_article_id));
    v_mail.recipients := get_user_email_addr(v_ticket.user_id);
    v_mail.cc := v_article.a_cc;
    v_mail.subject := '[Ticket#'||v_ticket.tn||'] '||v_ticket.title;
    v_body := format_message(p_article_id , p_history_type_id);
  end if;

  -- email-external
  if v_article.article_sender_type_id = 1 and v_article.article_type_id = 1 then
    v_mail.sender := v_article.a_from_user;
    v_mail.recipients := v_article.a_to;
    v_mail.cc := v_article.a_cc;
    v_mail.bcc := 'support@una.md';
    v_mail.subject := v_article.a_subject;
  end if;
  if lower(v_mail.recipients) like 'no_email@%' then
    return;
  end if;
  begin_mail(v_mail);
  add_attachments(p_article_id,v_mail);
  pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
  (
    conn => v_mail.conn,
    data => nvl(v_body,v_article.a_body),
    mime_type => replace(v_article.a_content_type,',',';'),
    last => true
  );
  pkg_mail_24.end_mail(conn => v_mail.conn);
end;
----------------------------------------------------------------------------------------------------
/*procedure agent_notification is
begin
  null;
end;
----------------------------------------------------------------------------------------------------
procedure customer_notification is
begin
  null;
end;
----------------------------------------------------------------------------------------------------
procedure auto_response is
begin
  null;
end;*/
----------------------------------------------------------------------------------------------------
procedure create_automate_tickets is
  v_ticket_id number(32);
begin

  dbms_application_info.set_module('pkg_ticket_mail','create_automate_tickets');

  mail_client.disconnect_server;        --на случай открытого соединения

  mail_client.connect_server(                       --Подключаемся к почтовому серверу
    p_hostname => '192.168.0.104',
    p_port     => 143,
    p_protocol => mail_client.protocol_imap,
    p_userid   => 'otrsvirt',
    p_passwd   => 'b}Sd629Sc<zv',
    p_ssl      => false
  );

  mail_client.open_inbox;

  insert into t_inbox(msg_number, subject, sender_email, sent_date, content_type, text)     --загружаем все незагруженные письма за последний день
  select t.msg_number, t.subject, /*t.sender_email*/'support_unamd@erp1.eu', t.sent_date, t.content_type
      , mail_client.get_message(t.msg_number).get_content_clob() text
  from table(mail_client.get_mail_headers()) t
  where sent_date > sysdate - 10
    --and subject like 'Re:%'
    and (sent_date, message_size) not in (select sent_date, message_size
                                          from t_inbox
                                          where sent_date > sysdate - 10)
  order by 1;

  for c in (select * from t_inbox where ticket_id = 0 and dbms_lob.getlength(text) <> 0 and subject is not null and dbms_lob.getlength(text) < 4000)          --создаем заявки
  loop
    begin
      v_ticket_id := pkg_ticket.create_ticket(1, substr(c.subject,0,254), c.text);
      update t_inbox set ticket_id = v_ticket_id where id = c.id;

      --mail();
    exception when others then
      un$process_log.log_exception(process_id);
    end;
  end loop;

  mail_client.disconnect_server;
exception when others then
  begin mail_client.disconnect_server; exception when others then null; end;
  un$process_log.log_exception(process_id);
end;
----------------------------------------------------------------------------------------------------
procedure send_week_report_all is
  v_raport varchar2(4000);
  v_week_begin date;
  v_week_end date;
  v_mail t_mail_data;
begin
  select max(data) into v_week_begin
  from
     (select trunc(sysdate) - nr + 1 data from xnr
      order by 1)
  where to_char(data,'DAY','NLS_DATE_LANGUAGE=''numeric date language''') = 1;
  v_week_end := v_week_begin + 4;

  for c in (select distinct x.userid, u.first_name, u.last_name, pkg_ticket_mail.get_user_email_addr(x.userid) mail
            from xuserwork x, system_user u
            where ieventid = 11
              and trunc(datest) between v_week_begin and v_week_end
              and x.userid = u.id)
  loop
    select  '             '||c.first_name || ' ' ||c.last_name
    || chr(10)||'--------------------Saptamana '||to_char(v_week_begin,'dd.mm')||' - '||to_char(v_week_end,'dd.mm.yyyy')||'-------------------------------'
    || chr(10)|| listagg('Ticket#: ' || nticket ||']' || wcomment, chr(10) ) within group (order by datest)
    into v_raport
    from xuserwork
    where userid = c.userid
      and ieventid = 11
      and datest between v_week_begin and v_week_end;
    say(v_raport);

    --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.sender := 'support_unamd@erp1.eu';
--    v_mail.recipients := get_user_email_addr(get_article_owner(p_article_id));
    v_mail.recipients := 'otalmazan@una.md'/*c.userid*/;
    v_mail.subject := 'Raport de lucru saptaminal '||to_char(v_week_begin,'dd.mm')||' - '||to_char(v_week_end,'dd.mm.yyyy');
    begin_mail(v_mail);

    pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
    (
      conn => v_mail.conn,
      data => v_raport,
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );
    pkg_mail_24.end_mail(conn => v_mail.conn);
  end loop;
end;
----------------------------------------------------------------------------------------------------
procedure send_day_report_by_user(p_user_id number, p_date date, p_date_f date :=null) is
  v_raport varchar2(4000);
  v_mail t_mail_data;
  v_first_name varchar2(256);
  v_last_name  varchar2(256);
  v_report2 clob;
  v_date_f date;
  k number;
  j number := 4000;
  v_id_mesage int;
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
begin
    
  if p_date_f is null then v_date_f:=p_date; end if;
  select first_name, last_name
  into v_first_name, v_last_name
  from system_user
  where id = p_user_id;

/*    select  '             '||v_first_name || ' ' ||v_last_name
--  || chr(10)||'--------------------'||to_char(p_date,'dd.mm.yyyy')||'-------------------------------'
    || chr(10)||'    S-a lucrat '||trunc(sum(utime)/3600)||':'||trim(to_char(mod(sum(utime),3600)/60,'00'))
    ||' ore pe data '||to_char(p_date,'dd.mm.yyyy')||', detaliat:    '
--  || chr(10)|| listagg(||'Ticket#: ' || nticket ||']' || wcomment, chr(10) ) within group (order by datest)
    || chr(10) || listagg(time_elaps||' ore, '||nticket ||']' || ' ' || (select customer_id from ticket where tn = nticket) ||' '|| wcomment
    || chr(10) || 'http://una.md/otrs/index.pl?&Action=AgentTicketZoom&TicketNumber='||nticket, chr(10) ) within group (order by datest)
    into v_raport
    from temp_rep
    where userid = p_user_id
      and ieventid in (10,11,12,13)
      and trunc(datest) = trunc(p_date)
      and del = 0;*/

  /* if p_user_id not in (653) then

   select '             '||v_first_name || ' ' ||v_last_name
    || chr(10)||'    S-a lucrat '||trunc(sum(time_by_client)/3600)||':'||trim(to_char(mod(sum(time_by_client),3600)/60,'00'))
    ||' ore pe data '||to_char(p_date,'dd.mm.yyyy')||', detaliat:    '
    || chr(10) || chr(10) || listagg(customer_id2 ||', '|| trunc(time_by_client/3600)||':'||trim(to_char(mod(time_by_client,3600)/60,'00')) || chr(10) || chr(10) || lines_by_client, chr(10) || chr(10)) within group (order by sort_time desc )
    into v_raport
    from
      (select customer_id2, time_by_client, listagg(rep_string, chr(10)) within group (order by datest) lines_by_client
        , case when customer_id2 = 'Others' then 0 else time_by_client end sort_time
      from v_temp_rep
      where userid = p_user_id
        and trunc(datest) = trunc(p_date)
      group by customer_id2, time_by_client
      order by 1 desc);


    v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.recipients := get_user_email_addr(p_user_id);
--    v_mail.recipients := 'otalmazan@una.md';
    v_mail.subject := 'Raport de lucru zilnic '||to_char(p_date,'dd.mm.yyyy');
    begin_mail(v_mail);

    pkg_mail.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
    (
      conn => v_mail.conn,
      data => v_raport,
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );
    pkg_mail.end_mail(conn => v_mail.conn);

    else */
    --new format DCodreanu

   select '             '||v_first_name || ' ' ||v_last_name
    || chr(10)||'    S-a lucrat '||trunc(sum(time_by_client)/3600)||':'||trim(to_char(mod(sum(time_by_client),3600)/60,'00'))
    ||' ore pe data '||to_char(p_date,'dd.mm.yyyy')||', detaliat:    '
    into v_report2
    from
    (
      select time_by_client
      from v_temp_rep
      where userid = p_user_id
        and trunc(datest) =trunc(p_date)--between trunc(p_date) and trunc(v_date_f) 
      group by customer_id2, time_by_client--,trunc(datest)
    );

    for c in (
      select replace(info, chr(10)||chr(10), chr(10)) info
      from
      (
        select 
          -- For?am concatenarea in CLOB folosind to_clob
          to_clob(case when rn = 1 then chr(10)||customer_id2 ||', '|| trunc(time_by_client/3600)||':'||trim(to_char(mod(time_by_client,3600)/60,'00')) end)
          || chr(10) || lines_by_client || chr(10) || body_by_ticket  as info
        from
        (
          select v.customer_id2, v.time_by_client, v.lines_by_client, b.body_by_ticket,
                 row_number() over (partition by v.customer_id2, v.time_by_client order by v.customer_id2, v.time_by_client) rn
          from
          (
            -- Agregare in CLOB pentru lines_by_client
            select customer_id2, nticket, time_by_client,  
                   rtrim(
                     dbms_xmlgen.convert(
                       xmlcast(
                         xmlagg(xmlelement(e, rep_string || chr(10)) order by datest) 
                         as clob
                       ), 1
                     ),
                     chr(10)
                   ) lines_by_client
            from V_TEMP_REP v
            where v.userid = p_user_id
              and trunc(v.datest) = p_date
              and v.nticket is not null
              and nvl(utime,0) <> 0
            group by customer_id2, nticket, time_by_client
          ) v
          left join
          -- Agregare in CLOB pentru corpul tichetului (body_by_ticket)
          (
            select t.tn, 
                   rtrim(
                     dbms_xmlgen.convert(
                       xmlcast(
                         xmlagg(xmlelement(e, substr(a.a_body,1,1000) || chr(10)) order by a.create_time) 
                         as clob
                       ), 1
                     ),
                     chr(10)
                   ) body_by_ticket
            from ticket t, article_vw a
            where t.id = a.ticket_id(+)
            and a.create_by(+) = 888
            and trunc(a.create_time(+)) ='19.06.2026'
            and a.article_type_id(+) = 9  
            group by t.tn
          ) b on v.nticket = b.tn
        )
        order by customer_id2, rn
      )
  )
  loop
    v_report2 := v_report2||chr(10)||c.info;
  end loop;


      
  --
  --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
  v_mail.sender := 'support_unamd@erp1.eu';
  v_mail.recipients := get_user_email_addr(p_user_id);
--    v_mail.recipients := 'otalmazan@una.md';
  --v_mail.recipients := 'dcodreanu@una.md';
  
  if p_date_f is not null then 
    v_mail.subject := 'Raport de lucru pentru perioada '||to_char(p_date,'dd.mm.yyyy')||'-'||to_char(v_date_f,'dd.mm.yyyy'); 
  else
    v_mail.subject := 'Raport de lucru zilnic '||to_char(p_date,'dd.mm.yyyy');
  end if;
  
  --v_mail.subject := 'Raport de lucru zilnic '||to_char(p_date,'dd.mm.yyyy');
  --select u.nrmsg, u.subject, u.sender, u.text, u.status, u.recipients, u.cc from un9mail_msg u;
  
  v_nrmsg := id_mail_sender.nextval;
  
  v_un9mail_msg.nrmsg := v_nrmsg;
  v_un9mail_msg.subject := v_mail.subject;
  v_un9mail_msg.sender := v_mail.sender;
  v_un9mail_msg.text := dbms_lob.substr(v_report2);
  v_un9mail_msg.status := 1;
  v_un9mail_msg.recipients := v_mail.recipients;
  v_un9mail_msg.cc := 'otuhari@mail.ru,pt@una.md,secretar@unisim-soft.com';
  
  fill_un9mail_msg(v_un9mail_msg);
  send_email_api_php(v_nrmsg);
   
  --NG, 07.02.2024 
  /*begin
    begin_mail(v_mail);

    --write_mime_header(conn, 'Content-Type', mime_type);

    \*k := ceil(dbms_lob.getlength(v_report2)/j);

    for i in 1..k
      loop
       v_raport := dbms_lob.substr(v_report2, j, 1 + j * (i - 1 ));

       pkg_mail.write_mb_text
       (
         conn => v_mail.conn,
         message => v_raport
       );
      end loop;
      *\
      pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob SUBSTR(p_text, 0, 2048)
      (
        conn => v_mail.conn,
        data => dbms_lob.substr(v_report2),
        --data => SUBSTR(dbms_lob.substr(v_report2), 0, 2048),
        mime_type => 'text/plain; charset=Windows-1251',
        last => true
      );

      pkg_mail_24.end_mail(conn => v_mail.conn);
      set_flag_report_day(p_user_id, p_date);
    exception when others then
      un$process_log.log(process_id, 'Error sending report to mail:'||sqlerrm, 'E');
    end;*/
    
    /*insert into TST_TABLE
      (sender, data_email, mesaj)
    values 
      ('1', sysdate, dbms_lob.substr(v_report2));*/
   --NG, 07.02.2024 
    
    fill_RAPORT_HR_OTRS(p_user_id, p_date
                        , v_id_mesage);
    send_message_hr(v_id_mesage);
    
    send_report_file_hr(p_date, p_user_id);

    --end if;
end;
----------------------------------------------------------------------------------------------------
procedure mail (p_sender varchar2, p_recipients varchar2, p_subject varchar2, p_text varchar2, p_msg varchar2:=null) is
  v_mail t_mail_data;
begin

  if nvl(get_env('mail_off'),0) = 1 then
    return;
  end if;
    --
    --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.sender := 'support_unamd@erp1.eu';
    v_mail.recipients := p_recipients;
--    v_mail.recipients := 'otalmazan@una.md'/*c.userid*/;
    v_mail.subject := p_subject;

    begin_mail(v_mail);

    pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
    (
      conn => v_mail.conn,
      data => p_text,
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );
    pkg_mail_24.end_mail(conn => v_mail.conn);
exception when others then
  begin pkg_mail.end_mail(conn => v_mail.conn); exception when others then null; end;
  un$process_log.log_exception(process_id, p_msg);
end;
----------------------------------------------------------------------------------------------------
procedure send_ticket_created_mails is
begin
  for c in (select * from t_inbox
            where sent_date > trunc(sysdate)
              and answer_sent is null
              and ticket_id is not null)
  loop
    mail(/*'OTRS Notification Master <otrs@uniacc.md>'*/'support_unamd@erp1.eu', c.sender_email, c.subject, get_ticket_created_text);

    update t_inbox set answer_sent = sysdate where id = c.id;
  end loop;
end;
----------------------------------------------------------------------------------------------------
--Процедура ищет заявки, которые уже больше 3 недель без ответа и шлёт предупреждение, что их надо рассмотреть, и что через месяц
--они будут автоматом переведены Павлу
--заявка 2018072718096072 
procedure send_month_warning_mail is
  v_text long;
  v_subject long;
  v_introduction long;
  v_week_cnt int;
  v_mail long;
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
begin

  dbms_application_info.set_module('pkg_ticket_mail','send_month_warning_mail');

  -- Первое письмо - владельцу заявки
  v_subject := 'Tickets warning!';

  v_introduction := 
'Внимание , рассмотрите указанные ниже заявки или  через
несколько дней эти заявки  будут автоматически
перенаправленны на вашего директора   

Atentie , prelucrati tikete anexate mai jos, in caz contrar
in cateva zile acestea tikete va fi trimise la director d-ra
in regim automat
';

  for c in (select user_id, user_id_email
              --NG 20.05.2025
              ,XMLAGG(
                   XMLELEMENT(e, tn || ' ' || title || ' ' || chr(10) || ticket_link || chr(10) || chr(10))
                   ORDER BY id
                 ).EXTRACT('//text()').getClobVal() as warning_tickets
              --, listagg( tn || ' ' || title || ' ' ||chr(10)|| ticket_link||chr(10) ||chr(10)) within group (order by id) warning_tickets 
            from vticket_info t
            where user_id in (select id from system_user where valid_id = 1)  --мониторим только заявки активных пользователей
              and user_id not in (1,2,66,102,199,364,380)                     --исключаем из обработки некоторых специфических пользователей
              and ticket_state_id in (1,4)                     --только открытые заявки смотрим
              and change_time < sysdate - 23                                  --ограничения на один месяц - неделя
              and not exists (select null from xuserwork x where x.nticket = t.tn and datest > sysdate - 23 and utime > 0)
              and not exists (select null from article a where a.ticket_id = t.id and change_time > sysdate - 23)
            group by user_id, user_id_email)
  loop
    v_text := v_introduction || chr(10) || chr(10) || c.warning_tickets;
    
    --NG, 08.02.2024
    --mail('OTRS Notification Master <otrs@uniacc.md>', c.user_id_email, v_subject, v_text, 'send_month_warning_mail ' ||c.user_id);
    v_nrmsg := id_mail_sender.nextval;
  
    v_un9mail_msg.nrmsg := v_nrmsg;
    v_un9mail_msg.subject := v_subject;
    v_un9mail_msg.sender := 'support@unisim-soft.com';
    v_un9mail_msg.text := v_text;
    v_un9mail_msg.status := 1;
    v_un9mail_msg.recipients := c.user_id_email;
    --v_un9mail_msg.cc := 'otuhari@mail.ru,pt@una.md';
    
    fill_un9mail_msg(v_un9mail_msg);
    send_email_api_php(v_nrmsg);
  end loop;


--Второе письмо - менеджеру и Павлу
  for c in (select --user_id, user_id_email, last_change_date, id_manager, tn || ' ' || title || ' ' ||chr(10)|| ticket_link||chr(10) ||chr(10) warning_tickets, t.ticket_detail
              t.*,  tn || ' ' || title || ' ' ||chr(10)|| ticket_link||chr(10) ||chr(10) warning_tickets
              --NG 20.05.2025
             ,get_user_email_addr(id_manager)  mail_manager
            from vticket_info t
            where user_id in (select id from system_user where valid_id = 1)  --мониторим только заявки активных пользователей
              and user_id not in (1,2,66,102,199,364,380)                     --исключаем из обработки некоторых специфических пользователей
              and ticket_state_id in (1,4)                     --только открытые заявки смотрим
              and change_time < sysdate - 23                                  --ограничения на один месяц - неделя
              and not exists (select null from xuserwork x where x.nticket = t.tn and datest > sysdate - 23 and utime > 0)
              and not exists (select null from article a where a.ticket_id = t.id and change_time > sysdate - 23)
            )
  loop
    v_week_cnt := floor((sysdate - c.last_change_date)/7);
    
    if 'pt@una.md' <> get_user_email_addr(c.user_id) then
      v_mail := 'pt@una.md, '|| get_user_email_addr(c.user_id);
    else 
      v_mail := 'pt@una.md';
    end if;
    
    if c.id_manager is not null 
      --and c.id_manager <> 'pt@una.md' 
      --and c.id_manager <> get_user_email_addr(c.user_id) then
      --NG 20.05.2025
      and c.mail_manager <> 'pt@una.md' 
      and c.mail_manager <> get_user_email_addr(c.user_id) then
        v_mail := v_mail ||', '||get_user_email_addr(c.id_manager);
    end if; 
    
    /*if c.id_manager is not null then 
      v_mail := get_user_email_addr(c.id_manager) || ', pt@una.md, '|| get_user_email_addr(c.user_id);
    else 
      v_mail := 'pt@una.md, '|| get_user_email_addr(c.user_id);
    end if;*/
    v_text := '
Acest tiket probabil va fi  migrat automat la director de
BOT din motiv
ca cererea mai mult de '||v_week_cnt||' saptamani nu se misca' || chr(10) || chr(10) || chr(10)
|| c.warning_tickets || chr(13) || chr(13) ||
c.ticket_detail
;
    v_subject := 'OTRSUNA.tw: ' || c.customer_id || ' ' ||c.max_buget_chr || '/' ||c.ticket_time_chr || ' ' || c.title || ',' || c.owner_login || ',' || c.tn;
    --NG, 08.02.2024
    --mail('OTRS Notification Master <otrs@uniacc.md>', v_mail, v_subject, v_text, 'send_month_warning_mail ' ||c.user_id);
    v_nrmsg := id_mail_sender.nextval;
  
    v_un9mail_msg.nrmsg := v_nrmsg;
    v_un9mail_msg.subject := v_subject;
    v_un9mail_msg.sender := 'support@unisim-soft.com';
    v_un9mail_msg.text := v_text;
    v_un9mail_msg.status := 1;
    v_un9mail_msg.recipients := v_mail;
    --v_un9mail_msg.cc := 'otuhari@mail.ru,pt@una.md';
    
    fill_un9mail_msg(v_un9mail_msg);
    send_email_api_php(v_nrmsg);
  end loop;
exception when others then
  un$process_log.log_exception(process_id);
end;
----------------------------------------------------------------------------------------------------
--Процедура ищет заявки, которые находятся у пользователя doljniki и в начале которых есть тэг #sendeveryweek
--По таким заявкам отправляется текст заметки каждую пятницу
--Заявка 201904051014133 
procedure send_debtor_notification is
  v_mail varchar2(256);
  v_text long;
  v_subject long;
begin

  v_subject := 'Reminding from Unisim';

  for c in (
    select a.*, t.tn 
    from article a, ticket t
    where 0=0
      and a.ticket_id = t.id
      and lower(a_body) like '#sendeveryweek,debtormessageonmail%'
      )
  loop
    v_mail := get_client_email_addr_by_tn(c.tn);
    
    select regexp_replace(c.a_body,'(#Sendeveryweek,DEBTORMessageOnMail)', '', 1, 1, 'i') 
    into v_text
    from dual;
    
    mail('OTRS Notification Master <otrs@uniacc.md>', v_mail, v_subject, v_text, 'send_debtor_notification ' ||c.id);
  end loop;
end;


----------------------------------------------------------------------------------------------------
procedure send_period_report_by_user(p_user_id number, p_date date, p_date_f date :=null) is
  v_raport varchar2(4000);
  v_mail t_mail_data;
  v_first_name varchar2(256);
  v_last_name  varchar2(256);
  v_report2 clob;
  v_date_f date;
  k number;
  j number := 4000;
  
  v_id_mesage int;
begin
    
  if p_date_f is  null then v_date_f:=p_date;  else  v_date_f:=p_date_f; end if;
  select first_name, last_name
  into v_first_name, v_last_name
  from system_user
  where id = p_user_id;
    
    
  select '             '||v_first_name || ' ' ||v_last_name
    || chr(10)||'    S-a lucrat '||trunc(sum(time_by_client)/3600)||':'||trim(to_char(mod(sum(time_by_client),3600)/60,'00'))
    ||' ore pentru perioada '||
        to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy')||', detaliat:    '
    into v_report2
    from
    (
      select time_by_client
      from v_temp_rep
      where userid = p_user_id
        and trunc(datest) between trunc(p_date) and trunc(v_date_f) 
      group by customer_id2, time_by_client--,trunc(datest)
    );

    for c in (
      select replace(info,chr(10)||chr(10),chr(10)) info
      from
      (
        select case when rn = 1 then chr(10)||customer_id2 ||', '|| trunc(time_by_client/3600)||':'||trim(to_char(mod(time_by_client,3600)/60,'00')) end
          || chr(10) || lines_by_client || chr(10) ||body_by_ticket  as info
        from
        (
          select customer_id2, time_by_client,  listagg(rep_string, chr(10)) within group (order by datest) lines_by_client
          , case when customer_id2 = 'Others' then 0 else time_by_client end sort_time
          , b.body_by_ticket
          , row_number() over (partition by customer_id2,time_by_client order by customer_id2,time_by_client) rn
          from v_temp_rep v,
          (
            select t.tn, listagg(substr(a.a_body,1,1000), chr(10)) within group (order by a.create_time) body_by_ticket
            from ticket t, article_vw a
            where t.id = a.ticket_id(+)
            and a.create_by(+) = p_user_id
            and trunc(a.create_time(+))  between trunc(p_date) and trunc(v_date_f) 
            and a.article_type_id(+) = 9  --type internal note
            group by t.tn
          ) b
          where v.userid = p_user_id
            and trunc(v.datest) between trunc(p_date) and trunc(v_date_f) 
            and v.nticket is not null
            and nvl(utime,0) <> 0
            and v.nticket = b.tn(+)
          group by customer_id2, nticket, time_by_client,b.body_by_ticket--,trunc(v.datest)
          order by 1 desc
        )
      order by customer_id2, rn
    )
  )
  loop
    v_report2 := v_report2||chr(10)||c.info;
  end loop;
    
    
    /*
        select
        chr(10)||'    S-a lucrat '||trunc(sum(utime)/3600)||':'||trim(to_char(mod(sum(utime),3600)/60,'00'))||' ore pentru perioada '||
        to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy')||', detaliat:    '||
        --chr(10)||'Count='|| count (*)|| 
        chr(10)||chr(10)||
        listagg(coment, chr(10) ) within group (order by customer_id) 

        as coment into v_report2

        from 
        (
         select  c.customer_id , sum(utime) utime,
            chr(10)||c.customer_id||', '||trunc(sum(utime)/3600)||':'||trim(to_char(mod(sum(utime),3600)/60,'00'))||' ore'||
            chr(10)||listagg(TIME_ELAPS||' ore, ['|| 'Ticket#: ' || nticket ||'] '||c.customer_id||' '|| wcomment||chr(10)|| 
            'Adaugat '||DATEST||' Ultima modificare '||dateend||chr(10) 
            , chr(10) ) within group (order by datest)
            
            as coment
            
            from v_temp_rep w,
            ticket c
            where userid = p_user_id
              and w.nticket=c.tn
              --and ieventid = 10
              and trunc(w.datest) between trunc(p_date) and trunc(p_date_f)
              --and trunc(datest) between trunc(p_date) and trunc(p_date_f) 
              --and rownum<=10
              and utime>0
              group by c.customer_id  
              
            ) b;*/
	--
  --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
  v_mail.sender := 'support_unamd@erp1.eu';
  v_mail.recipients := get_user_email_addr(p_user_id);
  v_mail.subject := 'Raport de lucru pentru perioada '||to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy'); 
  
  begin_mail(v_mail);

    pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
    (
      conn => v_mail.conn,
      data => dbms_lob.substr(v_report2),
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );
    
    pkg_mail_24.end_mail(conn => v_mail.conn);
    set_flag_report_day(p_user_id, p_date);
    
end;
----------------------------------------------------------------------------------------------------
procedure send_period_report_by_user2(p_user_id number, p_date date, p_date_f date :=null) is
  v_raport varchar2(4000);
  v_mail t_mail_data;
  v_first_name varchar2(256);
  v_last_name  varchar2(256);
  v_report2 clob;
  v_date_f date;
  k number;
  j number := 4000;
begin
  if p_date_f is  null then v_date_f:=p_date;  else  v_date_f:=p_date_f; end if;
  select first_name, last_name
  into v_first_name, v_last_name
  from system_user
  where id = p_user_id;
  say(v_date_f);
    
  select '             '||v_first_name || ' ' ||v_last_name
    || chr(10)||'    S-a lucrat '||trunc(sum(time_by_client)/3600)||':'||trim(to_char(mod(sum(time_by_client),3600)/60,'00'))
    ||' ore pentru perioada '||
        to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy')||', detaliat:    '
    into v_report2
    from
    (
      select time_by_client
      from v_temp_rep
      where userid = p_user_id
        and trunc(datest) between trunc(p_date) and trunc(v_date_f) 
      group by customer_id2, time_by_client--,trunc(datest)
    );

    for c in (
      select replace(info,chr(10)||chr(10),chr(10)) info
      from
      (
        select case when rn = 1 then chr(10)||customer_id2 ||', '|| trunc(time_by_client/3600)||':'||trim(to_char(mod(time_by_client,3600)/60,'00')) end
          || chr(10) || lines_by_client || chr(10) ||body_by_ticket  as info
        from
        (
          select customer_id2, time_by_client,  listagg(rep_string, chr(10)) within group (order by datest) lines_by_client
          , case when customer_id2 = 'Others' then 0 else time_by_client end sort_time
          , b.body_by_ticket
          , row_number() over (partition by customer_id2,time_by_client order by customer_id2,time_by_client) rn
          from v_temp_rep v,
          (
            select t.tn, listagg(substr(a.a_body,1,1000), chr(10)) within group (order by a.create_time) body_by_ticket
            from ticket t, article_vw a
            where t.id = a.ticket_id(+)
            and a.create_by(+) = p_user_id
            and trunc(a.create_time(+))  between trunc(p_date) and trunc(v_date_f) 
            and a.article_type_id(+) = 9  --type internal note
            group by t.tn
          ) b
          where v.userid = p_user_id
            and trunc(v.datest) between trunc(p_date) and trunc(v_date_f) 
            and v.nticket is not null
            and nvl(utime,0) <> 0
            and v.nticket = b.tn(+)
          group by customer_id2, nticket, time_by_client,b.body_by_ticket--,trunc(v.datest)
          order by 1 desc
        )
      order by customer_id2, rn
    )
  )
  loop
    v_report2 := v_report2||chr(10)||c.info;
  end loop;
    
    
    /*
        select
        chr(10)||'    S-a lucrat '||trunc(sum(utime)/3600)||':'||trim(to_char(mod(sum(utime),3600)/60,'00'))||' ore pentru perioada '||
        to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy')||', detaliat:    '||
        --chr(10)||'Count='|| count (*)|| 
        chr(10)||chr(10)||
        listagg(coment, chr(10) ) within group (order by customer_id) 

        as coment into v_report2

        from 
        (
         select  c.customer_id , sum(utime) utime,
            chr(10)||c.customer_id||', '||trunc(sum(utime)/3600)||':'||trim(to_char(mod(sum(utime),3600)/60,'00'))||' ore'||
            chr(10)||listagg(TIME_ELAPS||' ore, ['|| 'Ticket#: ' || nticket ||'] '||c.customer_id||' '|| wcomment||chr(10)|| 
            'Adaugat '||DATEST||' Ultima modificare '||dateend||chr(10) 
            , chr(10) ) within group (order by datest)
            
            as coment
            
            from v_temp_rep w,
            ticket c
            where userid = p_user_id
              and w.nticket=c.tn
              --and ieventid = 10
              and trunc(w.datest) between trunc(p_date) and trunc(p_date_f)
              --and trunc(datest) between trunc(p_date) and trunc(p_date_f) 
              --and rownum<=10
              and utime>0
              group by c.customer_id  
              
            ) b;*/

  --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
  v_mail.sender := 'support_unamd@erp1.eu';
  v_mail.recipients := get_user_email_addr(p_user_id);
  v_mail.subject := 'Raport de lucru pentru perioada '||to_char(p_date,'dd.mm.yyyy')||'-'||to_char(p_date_f,'dd.mm.yyyy'); 
  
  begin_mail(v_mail);

    pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
    (
      conn => v_mail.conn,
      data => dbms_lob.substr(v_report2),
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );

    pkg_mail_24.end_mail(conn => v_mail.conn);
end;
----------------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------
procedure set_flag_report_day(p_user_id int, p_date date, p_type varchar2:='TGR') is
  pragma autonomous_transaction;
  v_process_id int := un$process_log.get_id('#raportulmeuzilnic');
begin
  update xuserwork_rep_flag t
  set t.flag = 1,
      t.data_send_report = sysdate
  where t.user_id = p_user_id
    and t.data_flag = p_date;
    
  if sql%rowcount = 0 then
    insert into xuserwork_rep_flag
      (user_id, data_flag, data_send_report, flag)
    values
      (p_user_id, p_date, sysdate, 1);
  end if;
  
  un$process_log.log(v_process_id, 'Set Flag user: '||p_user_id||' - '||p_type);
  commit;
end;
----------------------------------------------------------------------------------------------------
----------------------------------------------------------------------------------------------------
procedure fill_RAPORT_HR_OTRS(p_user_id int, p_date date, p_id out int) is
  pragma autonomous_transaction;
  v_id integer := sq_RAPORT_HR_OTRS.Nextval;
  v_msg long;
  v_msg2 long;
  v_first_name varchar2(256);
  v_last_name  varchar2(256);
  v_title long := ' lucrari efectuate ('||p_date||'):'||chr(13);
begin
  select first_name, last_name
  into v_first_name, v_last_name
  from system_user
  where id = p_user_id;  
  
  v_title := v_first_name || ' ' ||v_last_name||chr(13)||v_title||chr(13)||chr(13)||chr(10);

  /*for c in (
    select '— ('||t.customer_id||') #'||t.tn||' ] '||t.title||chr(10) mticket, t.tn
           ,t.freetext3, t.customer_id
    from xuserwork x, ticket t
    where userid=p_user_id 
      and t.tn = x.nticket
      and trunc(x.datest_system) = trunc(p_date)
      and x.ieventid in (10,11,12,13)
      and x.nticket is not null
      and nvl(x.utime, 0) > 0
    group by t.tn, t.customer_id, t.title, t.freetext3, t.customer_id
  ) loop
    v_msg2 := '';
    for r in (
      select x.wcomment
      from xuserwork x, ticket t
      where userid=p_user_id 
        and t.tn = x.nticket
        and t.tn = c.tn
        and trunc(x.datest_system) = trunc(p_date)
        and x.wcomment is not null
    ) loop
      v_msg2 := v_msg2||'  * '||r.wcomment||chr(10);
    end loop;
    v_msg := v_msg
             ||'________________________________________________________'||chr(13)||chr(10)
             ||c.mticket||v_msg2||chr(13)||chr(13)||chr(10)
             ||'Client => '||c.customer_id||chr(13)||chr(10)
             ||'Manager => '||c.freetext3||chr(13)||chr(13)||chr(10)
             ;
    
  end loop;*/
  for c in (
    select '*'||t.customer_id||') #'||t.tn||' ] '||t.title||'*'||chr(10) mticket, t.tn
           ,t.freetext3, t.customer_id
    from xuserwork x, ticket t
    where userid=p_user_id 
      and t.tn = x.nticket
      and trunc(x.datest_system) = trunc(p_date)
      and x.ieventid in (10,11,12,13)
      and x.nticket is not null
      and nvl(x.utime, 0) > 0
    group by t.tn, t.customer_id, t.title, t.freetext3, t.customer_id
  ) loop
    v_msg2 := '';
    for r in (
      select x.wcomment
      from xuserwork x, ticket t
      where userid=p_user_id 
        and t.tn = x.nticket
        and t.tn = c.tn
        and trunc(x.datest_system) = trunc(p_date)
        and x.wcomment is not null
    ) loop
      v_msg2 := v_msg2||''||REPLACE(r.wcomment, '_', '-')||chr(10);
    end loop;
    v_msg := v_msg
             ||'*Client => '||c.customer_id||chr(10)
             || 'Manager => '||c.freetext3||'*'||chr(10)
             ||c.mticket
             ||'_'||v_msg2||'_'||chr(13)||chr(13)||chr(10)
             ;
    
  end loop;
  
  insert into RAPORT_HR_OTRS
      (ID_MESAGE, OTRS_USER_ID, MESSAGE, title_message)
    values
      (v_id, p_user_id, v_msg, v_title);
      
  commit;
  p_id := v_id;
end;
----------------------------------------------------------------------------------------------------
procedure send_report_day_all(p_date date) is 
  v_process_id int := un$process_log.get_id('#raportulmeuzilnic');
  v_date date := trunc(p_date);
begin
  un$process_log.log(v_process_id, 'INCEPEREA GENERARII/TRIMITERII RAPOARTELOR ZILNICE '||p_date);
  set_env('send_report_day_all', 1);
  
  for r in (
    select distinct userid from XUSERWORK u 
    where trunc(u.datest) = v_date
      and u.userid not in (select t.user_id from XUSERWORK_REP_FLAG t 
                           where trunc(t.data_flag) = v_date and t.flag = 1)
     --Excludem Userii care nu doresc sa vina automat raportul
      and u.userid not in (310)
  ) loop
    begin
      --send_period_report_by_user2(r.userid, v_date, v_date);
      update XUSERWORK f 
      set f.wcomment = '#raportulmeuzilnic'||f.wcomment
      where f.userid =r.userid 
        and trunc(f.datest) = v_date
        and rownum = 1;
      say(sql%rowcount);
      set_flag_report_day(r.userid, v_date, 'PROC');
      
      say(r.userid||' Ok '||v_date);
      un$process_log.log(v_process_id, r.userid||' USER SEND SUCCESS');
    exception when others then
      un$process_log.log_exception(v_process_id, r.userid||' USER SEND ERROR, '||sqlerrm);
    end;
  end loop;
  set_env('send_report_day_all', 0);
  un$process_log.log(v_process_id, 'SFIRSITUL GENERARII/TRIMITERII RAPOARTELOR ZILNICE '||p_date);
end;
----------------------------------------------------------------------------------------------------
procedure send_mail_warning_tikets(p_date date) is
  v_clob_contract_valid clob;
  v_clob_timp_datorii clob;
  
  v_sql_contract_valid long;
  v_sql_timp_datorii long;
  
  v_mail t_mail_data;
  
  v_text_mail long;
  v_cnt_contract_valid number;
  v_cnt_timp_datorii number;
  v_table long;
  
  v_coninfo varchar2(20) := '218,974,2445';
  
  v_nrmsg integer;
  v_un9mail_msg un9mail_msg%rowtype;
begin
  uni.pkg_mail_job.fill_table_debitor(p_date);
  
  v_sql_contract_valid := '
    select tn, customer_id, cod_univ, denumirea from (
    select t.tn
          ,t.customer_id
          ,c.cod_univ
          ,(select b.denumirea from TMS_UNIVERS b where b.cod=c.cod_univ) denumirea
    from XUSERWORK u, TICKET t, CUSTOMER_USER c
        where trunc(u.datest) = '''||p_date||'''
          and u.nticket=t.tn
          and c.customer_id=t.customer_id
          and c.cod_univ is not null
          /*and u.userid not in (select t.user_id from XUSERWORK_REP_FLAG t 
                               where trunc(t.data_flag) = '''||p_date||''' and t.flag = 1)*/
          and c.cod_univ not in (select v.clientid from uni.tmbd_list_contr_valid v
                                 where /*v.data_completion=*/'''||p_date||''' between v.datastart and v.dataend
                                 and exists 
       (select null from uni.vcn1d_spec_vinz v1, uni.vcn0m_contr_client v2
        where v.contractid = v1.contractid and v1.contractid=v2.contractid
          and '''||p_date||''' between v2.datastart and v2.dataend 
          and v2.zalog_o_117 = 1
          --and '''||p_date||''' between v1.datastart and v1.dataend 
          --and v1.conditii_de_livrare_o_104 in (4,6,7)
       ))
    group by t.tn, t.customer_id, c.cod_univ
      ) t
    where cod_univ not in ('||v_coninfo||')  
    order by denumirea, tn';
  say('v_sql_contract_valid: '||chr(13)||v_sql_contract_valid);
  
  execute immediate
  'select
  xmlagg(xmlelement("tr"
                    ,xmlelement("td",CONCAT(rpad(tn, 18),chr(09)))
                    ,xmlelement("td",CONCAT(rpad(cod_univ,8),chr(09)||chr(09)))
                    ,xmlelement("td",case when denumirea is null then '' ''||chr(13) else denumirea||chr(13) end)
                    )).extract(''//text()'').getClobVal() v
    from(select * from('||v_sql_contract_valid||'))' into v_clob_contract_valid; 
  say('v_clob_contract_valid:'||chr(13)||v_clob_contract_valid);

  v_sql_timp_datorii := '
  select tn, customer_id, cod_univ, denumirea, durata from (
    select t.tn
        ,t.customer_id
        ,c.cod_univ
        ,(select b.denumirea from TMS_UNIVERS b where b.cod=c.cod_univ) denumirea
        ,(select v.cant from uni.tmdb_list_dept_client v 
          where v.client_cod=c.cod_univ and v.data_completion='''||p_date||''') durata
    from XUSERWORK u, TICKET t, CUSTOMER_USER c
      where trunc(u.datest) = '''||p_date||'''
        and u.nticket=t.tn
        and c.customer_id=t.customer_id
        and c.cod_univ is not null
        /*and u.userid not in (select t.user_id from XUSERWORK_REP_FLAG t 
                             where trunc(t.data_flag) = '''||p_date||''' and t.flag = 1)*/
        and not exists (select null from uni.vmdb_cmr r where r.data between add_months('''||p_date||''',-6) and '''||p_date||''' and r.ctdep = c.cod_univ)                      
      /*  and c.cod_univ in (select v.client_cod from uni.tmdb_list_dept_client v
                           where v.data_completion='''||p_date||''')   */  --- проверка на наличие задолженности         
    group by t.tn, t.customer_id, c.cod_univ
        ) t
  where cod_univ not in ('||v_coninfo||')  
  order by denumirea, tn';
  say('v_sql_timp_datorii:'||chr(13)||v_sql_timp_datorii);
  
  execute immediate
  'select
  xmlagg(xmlelement("tr"
                    ,xmlelement("td",CONCAT(rpad(tn, 18),chr(09)))
                    ,xmlelement("td",CONCAT(rpad(durata||'' (W)'', 8),chr(09)||chr(09)))
                    ,xmlelement("td",CONCAT(rpad(cod_univ, 8),chr(09)||chr(09)))
                    ,xmlelement("td",case when denumirea is null then '' ''||chr(13) else denumirea||chr(13) end)
                    )).extract(''//text()'').getClobVal() v
    from(select * from('||v_sql_timp_datorii||'))' into v_clob_timp_datorii; 
  say('v_clob_contract_valid:'||chr(13)||v_clob_timp_datorii);
  
  execute immediate 'select count(*) from ('||v_sql_contract_valid||')' into v_cnt_contract_valid;
  execute immediate 'select count(*) from ('||v_sql_timp_datorii||')' into v_cnt_timp_datorii;

  if v_cnt_timp_datorii > 0 or v_cnt_contract_valid > 0 then 
    v_text_mail := 'ATENTIE!!!'||chr(13)||
                   'mai jos sunt atasate lista ticketelor la care sa lucrat pe data '||p_date||chr(13)||
                   'clientii acestor tickete nu au contracte valide sau nu au fost plati mai mult de 24 saptamini'||chr(13)||chr(13) ;
                   
    if v_cnt_contract_valid > 0 then
      select rpad('Id ticket',20)||rpad('Id client',15)||rpad('Client name',40)||chr(13)/*||rpad(' ',150,'-')*/ 
      into v_table from dual;
      v_text_mail := v_text_mail||
                     'CONTRACTE INVALIDE: '||chr(13)||v_table||
                     v_clob_contract_valid||chr(13);
    end if;
    
    if v_cnt_timp_datorii > 0 then
      select rpad('Id ticket',20)||rpad('Timp',10)||rpad('Id client',15)||rpad('Client name',40)||chr(13)/*||rpad(' ',150,'-')*/ 
      into v_table from dual;
      v_text_mail := v_text_mail||
                     'FARA PLATI MAI MULT DE 6 LUNI: '||chr(13)||v_table||
                     v_clob_timp_datorii||chr(13);
    end if;
    
    say(v_text_mail);
    
    --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.sender := 'support_unamd@erp1.eu';
    v_mail.recipients := 'ptuhari@gmail.com, pt@unisim-soft.com, secretar@unisim-soft.com, otuhari@mail.ru, arnautangela.us@gmail.com';
    ---v_mail.recipients := 'arnautangela.us@gmail.com';
    ---v_mail.subject := 'WARNING CLIENT TICKETS';
    ---v_mail.subject := 'AHTUNG! WARNING! ВНИМАНИЕ! проводятся работы с клиентом у которого высок риск неоплаты!';
    v_mail.subject := 'AHTUNG! WARNING! ATENTIE! se lucreaza cu un client care are un risc ridicat de neplata';
    
    --NG, 07.02.2024
    v_nrmsg := id_mail_sender.nextval;
  
    v_un9mail_msg.nrmsg := v_nrmsg;
    v_un9mail_msg.subject := v_mail.subject;
    v_un9mail_msg.sender := v_mail.sender;
    v_un9mail_msg.text := dbms_lob.substr(v_text_mail);
    v_un9mail_msg.status := 1;
    v_un9mail_msg.recipients := 'secretar@unisim-soft.com';
    v_un9mail_msg.cc := 'ptuhari@gmail.com,pt@unisim-soft.com,secretar@unisim-soft.com,otuhari@mail.ru,arnautangela.us@gmail.com';
    
    fill_un9mail_msg(v_un9mail_msg);
    send_email_api_php(v_nrmsg);
    
    --NG, 07.02.2024
    /*v_mail.conn := begin_session;
    pkg_mail_24.begin_mail_in_session
    (
         conn => v_mail.conn,
         sender => v_mail.sender,
         recipients => v_mail.recipients,
         --
         --cc => 'arnautangela.us@gmail.com',
         --bcc => p_mail.bcc,
         subject => v_mail.subject,
         mime_type => pkg_mail_24.multipart_mime_type
    );
    
    pkg_mail_24.attach_mb_text  --  TO DO: Добавить pkg_mail.attach_mb_clob
      (
        conn => v_mail.conn,
        data => dbms_lob.substr(v_text_mail),
        mime_type => 'text/plain; charset=Windows-1251',
        last => true
      );

   pkg_mail_24.end_mail(conn => v_mail.conn);*/
   --NG, 07.02.2024
 end if;
end;
----------------------------------------------------------------------------------------------------
procedure send_mail_plan_zilnic is
  v_mail t_mail_data; 
  
  v_list_mail varchar2(1000);
begin
  for c in (
    select * from vtelegram_hr_chat t where nvl(t.SEND_MAYL_FLAG, 0) = 0
  ) loop
  
    --v_mail.sender := 'OTRS Notification Master <otrs@uniacc.md>';
    v_mail.sender := 'support_unamd@erp1.eu';
    v_list_mail := 'ptuhari@gmail.com, pt@unisim-soft.com, otuhari@mail.ru';
    --v_list_mail := 'nicolaegaidarji@gmail.com, arnautangela.us@gmail.com';
    if c.user_email is not null then
      v_list_mail := v_list_mail||', '||c.user_email;
    end if;
    
    v_mail.recipients := v_list_mail;
    v_mail.subject := 'Planul de lucru '||trunc(c.data_msg)||', '||nvl(c.long_name,c.username);
      
    begin_mail(v_mail);
    
    pkg_mail_24.attach_mb_text 
    (
      conn => v_mail.conn,
      data => c.message,
      mime_type => 'text/plain; charset=Windows-1251',
      last => true
    );
    
    pkg_mail_24.end_mail(conn => v_mail.conn);
    
    update telegram_hr_chat i set
      i.send_mayl_flag = 1
    where i.id = c.id;
    
  end loop;
end;
----------------------------------------------------------------------------------------------------
procedure send_message_hr(p_id int) is 
  pragma autonomous_transaction;
  l_req  UTL_HTTP.REQ;
  l_resp UTL_HTTP.RESP;
  buffer varchar2(4000);
  
  v_req_result varchar2(4000);
  v_message vraport_hr_otrs%rowtype;
begin
  select * into v_message from vraport_hr_otrs v where v.ID_MESAGE = p_id;
  
  if v_message.id_chat_telegram is null then
    update RAPORT_HR_OTRS f set
      f.is_send_hr = null,
      f.date_send = sysdate,
      f.req_result = 'Nu este indicat Chat ID telegram'
    where f.id_mesage = p_id;
    
    commit;
    return;
  end if;
  
  l_req := utl_http.begin_request(
    --url    => 'http://una.md/iRuta-devel/telegram_unisim_hr/send_message.php',
    url    => 'http://api.unisim-soft.com/unisim_util/send_message_bot.php?id='||p_id,
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
  
  if instr(v_req_result, 'OK') > 0 then
    update RAPORT_HR_OTRS f set
      f.is_send_hr = 1,
      f.date_send = sysdate,
      f.req_result = v_req_result
    where f.id_mesage = p_id;
  else
    update RAPORT_HR_OTRS f set
      f.is_send_hr = null,
      f.date_send = sysdate,
      f.req_result = v_req_result
    where f.id_mesage = p_id;
  end if;
  
  commit;
  
exception
  WHEN OTHERS THEN
    v_req_result:= 'eroare request '||SQLERRM;
    update RAPORT_HR_OTRS f set
      f.is_send_hr = null,
      f.date_send = sysdate,
      f.req_result = v_req_result
    where f.id_mesage = p_id;
    commit;
end;
----------------------------------------------------------------------------------------------------
procedure send_report_file_hr(p_data date, p_user_id int) is
  pragma autonomous_transaction;
  l_req  UTL_HTTP.REQ;
  l_resp UTL_HTTP.RESP;
  buffer varchar2(4000);
  
  v_req_result varchar2(4000);
  v_message vraport_hr_otrs%rowtype;
begin
  for c in (
    select t.USERID
          ,(select s.first_name||' '||s.last_name from system_user s where s.id=t.USERID) user_name
          ,u.id_chat_telegram
    from VXUSERWORK t, TELEGRAM_HR_USERS u
    where 1=1
      and t.USERID = p_user_id
      and t.USERID = u.otrs_user
      and trunc(t.datest_system) = p_data
      and t.wcomment is not null
      and u.id_chat_telegram is not null
    group by t.USERID, u.id_chat_telegram
  ) loop
    begin
        l_req := utl_http.begin_request(
        --url    => 'http://una.md/iRuta-devel/telegram_unisim_hr/send_message.php',
        url    => 'http://api.unisim-soft.com/unisim_util/send_rep_file_bot.php?user_id='||c.userid||'&data='||p_data||'&chat_id='||c.id_chat_telegram,
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
      
      say(v_req_result);
      
    exception
      WHEN OTHERS THEN
        v_req_result:= 'eroare request '||SQLERRM;
        say(v_req_result);
    end;
  end loop;
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
        url    => 'http://api.unisim-soft.com/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=otrs',
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
end;

/

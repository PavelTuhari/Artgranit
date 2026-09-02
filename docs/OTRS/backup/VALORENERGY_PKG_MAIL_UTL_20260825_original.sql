CREATE OR REPLACE package body pkg_mail_utl is
----------------------------------------------------------------------------------------------------
function get_pwd_hash(p_user varchar2) return varchar2 is
begin
  return null;
  --Sm5sdGtSZmxoamQxNA==
end;
----------------------------------------------------------------------------------------------------
function begin_session return utl_smtp.connection is
 --v_user varchar2(64) := utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('electron.docs@gcc.md')));
 --v_psw varchar2(64) := utl_raw.cast_to_varchar2(utl_encode.base64_encode(utl_raw.cast_to_raw('33ae41Mu1')));
 v_user varchar2(64) := mail_params.get_user;
 v_psw varchar2(64) := mail_params.get_password;
begin
  --msg(v_user || ' ' || mail_params.get_user);
  pkg_mail.smtp_host := mail_params.get_smtp_host;
  pkg_mail.smtp_port := mail_params.get_smtp_port;
  pkg_mail.smtp_domain := mail_params.get_smtp_domain;
  return pkg_mail.begin_auth_session(
         v_user
        ,v_psw);
end;
----------------------------------------------------------------------------------------------------
function send_list_non_empty return boolean is
begin
  for c in (select * from un9mail_msg where status = 1) loop
    return true;
  end loop;

  return false;
end;
----------------------------------------------------------------------------------------------------
/*procedure begin_mail(p_conn in out utl_smtp.connection, p_msg un9mail_msg%rowtype) is
begin
  pkg_mail.begin_mail_in_session
  (
    conn => p_conn,
    sender => p_msg.sender,
    recipients => p_msg.recipients,
    cc => p_msg.cc,
    bcc => p_msg.bcc,
    subject => p_msg.subject,
    mime_type => pkg_mail.multipart_mime_type
  );
end;*/
----------------------------------------------------------------------------------------------------
procedure add_attachments(p_conn in out utl_smtp.connection, p_nrmsg int, p_nrdoc int) is
  n int;
  len int;
begin
  for c in
  (
    select nvl(d.oleobj, p.pack) attachment
         , nvl(d.pfile, p.filename) filename
         , p.mime_type
    from un9mail_pack p, tmdb_docs_ole d
    where p.nrmsg = p_nrmsg
      and p.nrdoc1 = d.nrdoc1 (+)
      and d.nrdoc (+) = p_nrdoc
    order by p.nrord
  )
  loop
    pkg_mail.begin_attachment
    (
      conn => p_conn,
      mime_type => c.mime_type,
      filename => c.filename,
      inline => false,
      transfer_enc => 'base64'
    );

    n := 1;
    len := dbms_lob.getlength(c.attachment);
    while n < len loop
      pkg_mail.write_raw(p_conn, utl_encode.base64_encode(
                                 dbms_lob.substr(c.attachment, pkg_mail.max_base64_line_width, n)));
      n := n + pkg_mail.max_base64_line_width;
    end loop;

    pkg_mail.end_attachment(p_conn);
  end loop;
end;
----------------------------------------------------------------------------------------------------
procedure set_status(p_nrmsg int, p_status int) is
-- pragma autonomous_transaction;
begin
  update un9mail_msg set status = p_status
       , sent_date = case when status = 2 then sysdate else sent_date end
  where nrmsg = p_nrmsg;
  commit;
end;
----------------------------------------------------------------------------------------------------
procedure send_doc(p_nrdoc number) is
 v_conn utl_smtp.connection;
 V_ID_PROCESS int:=un$process_log.get_id('Expediere_mail_automat');
begin

  if send_list_non_empty then
    v_conn := begin_session;
  else
    return;
  end if;

  for c in (select * from un9mail_msg where status = 1 and dep = p_nrdoc order by nrmsg) loop
    begin
      pkg_mail.begin_mail_in_session
      (
        conn => v_conn,
        sender => c.sender,
        recipients => c.recipients,
        cc => c.cc,
        bcc => c.bcc,
        subject => c.subject,
        mime_type => pkg_mail.multipart_mime_type
      );

      if c.text is not null then
        pkg_mail.attach_text(v_conn, c.text);
      end if;

      add_attachments(v_conn, c.nrmsg, c.nrdoc);

      pkg_mail.end_mail_in_session(conn => v_conn);

      set_status(c.nrmsg, 2);
    exception when others then
      if sqlcode = -29279 then
        msg('Check the e-mail address - '|| c.recipients ||chr(10)||'Cod: '||c.sc);
      end if;
        msg(sqlerrm);
    end;
  end loop;

  pkg_mail.end_session(v_conn);
end;
----------------------------------------------------------------------------------------------------
procedure send_all(
          p_skip_errors boolean := false
        , p_nr_mails int:=100)
     is
 v_conn utl_smtp.connection;
 c_spaces constant varchar2(10) := ' '||chr(9)||chr(10)||chr(13);
 V_ID_PROCESS int;
 v_count int;
 v_msg long;
 v_err_code int;
begin
  
   V_ID_PROCESS:=un$process_log.get_id('Expediere_mail_automat');
  select count(*) into v_count from un9mail_msg e  where e.status = 1  and rownum <= p_nr_mails order by e.nrmsg;
  if v_count>0 then
   begin
     v_conn := begin_session;
   exception
    when others then null;
        V_ID_PROCESS:=un$process_log.get_id('Expediere_mail_automat');
        un$process_log.log(V_ID_PROCESS,'Expediere email Connectiun error:  ErrCode: '||sqlcode||', ErrMSG: '||sqlerrm, 'E'); 
        return;         
    end;
  else
    return;
  end if; 
  
    un$process_log.log(V_ID_PROCESS,'Lansare Expediere email', 'I');

  for c in (select * from (select * from un9mail_msg where status = 1 order by nrmsg) where rownum <= p_nr_mails) loop
    begin
      pkg_mail.begin_mail_in_session
      (
        conn => v_conn,
        sender => c.sender,
            recipients => ltrim(rtrim(c.recipients, c_spaces), c_spaces),
        cc => c.cc,
        bcc => c.bcc,
        subject => c.subject,
        mime_type => pkg_mail.multipart_mime_type
        --mime_type=>'text/plain; charset=windows-1251'
      );


      if c.text is not null then
        --pkg_mail.attach_text(v_conn,c.text);
        pkg_mail.attach_text (conn => v_conn, data => c.text, last => false, mime_type => 'text/plain; charset=Windows-1251');
      end if;

      add_attachments(v_conn, c.nrmsg, c.nrdoc);

      pkg_mail.end_mail_in_session(conn => v_conn);
    
      un$process_log.log(V_ID_PROCESS,'Email expediat catre: '||c.recipients||' NrMSG: '|| c.nrmsg);

      set_status(c.nrmsg, 2);
    exception 
        when others then
        begin
          utl_smtp.rset(v_conn);
        exception
          when others then
            un$process_log.log(V_ID_PROCESS,'!!!Email neexpediat catre: '||c.recipients||' NrMSG: '|| c.nrmsg||', RSET on error: '||sqlerrm, 'E', C.NRDOC);
            null; -- ignore
        end;  
    
       v_msg:=sqlerrm;
       if sqlcode = -29279 then       
            v_msg:= ('Check the e-mail address - '|| c.recipients); 
            v_err_code := sqlcode;
            update un9mail_msg  set err_code = v_err_code, err_msg = substr(v_msg, 1, 4000),status = 2, sent_date =  sysdate
                    where  status = 1 and  nrmsg=c.nrmsg;
       end if;      
      un$process_log.log(V_ID_PROCESS,v_msg, 'E', C.NRDOC, c.dep);
           
      --
        if( not p_skip_errors ) then
          commit;
            msg(v_msg );
        end if;
      
    end;
  end loop;
    pkg_mail.end_session(v_conn);
    
  exception
  when others then
     commit;  
     begin
        pkg_mail.end_session(v_conn);
      exception
        when others then
          null; -- ignore
      end; 
end;
----------------------------------------------------------------------------------------------------
procedure mail (
  p_recipients     varchar2,
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
begin
  v_conn := begin_session;

  begin
    pkg_mail.begin_mail_in_session (
       conn         => v_conn,
       sender       => 'support@una.md',
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
    un$process_log.log_exception (un$process_log.get_id ('mail_server'));
  end;
exception when others then
     un$process_log.log_exception (un$process_log.get_id ('mail_server'));
end;

----------------------------------------------------------------------------------------------------
procedure send_email_api_php(p_nrmsg int) is 
  pragma autonomous_transaction;
  l_req  UTL_HTTP.REQ;
  l_resp UTL_HTTP.RESP;
  buffer varchar2(4000);
  
  v_req_result varchar2(4000);
  v_cnt integer;
begin
  say('start api');
  select count(*) into v_cnt from UN9MAIL_MSG i where i.nrmsg = p_nrmsg and i.status = 1;
  say('v_cnt '||v_cnt);
  if v_cnt = 0 then
    return;
  end if;
  say('Continuare');
  
  l_req := utl_http.begin_request(
    --url    => 'http://una.md/iRuta-devel/telegram_unisim_hr/send_message.php',
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
  
  commit;
  
exception
  WHEN OTHERS THEN
    v_req_result:= 'eroare request '||SQLERRM;
    update un9mail_msg f set
      f.status = 1,
      f.err_msg = v_req_result,
      f.sent_date = sysdate 
    where f.nrmsg = p_nrmsg;
    commit;
end;

----------------------------------------------------------------------------------------------------
procedure send_all_php(
          p_skip_errors boolean := false
        , p_nr_mails int:=100)
     is
 v_conn utl_smtp.connection;
 c_spaces constant varchar2(10) := ' '||chr(9)||chr(10)||chr(13);
 V_ID_PROCESS int;
 v_count int;
 v_msg long;
 v_err_code int;
begin
  
   V_ID_PROCESS:=un$process_log.get_id('Expediere_mail_automat_API_PHP');
  select count(*) into v_count from un9mail_msg e  where e.status = 1  and rownum <= p_nr_mails order by e.nrmsg;
  if v_count>0 then
   begin
     v_conn := begin_session;
   exception
    when others then null;
        V_ID_PROCESS:=un$process_log.get_id('Expediere_mail_automat_API_PHP');
        un$process_log.log(V_ID_PROCESS,'Expediere email Connectiun error:  ErrCode: '||sqlcode||', ErrMSG: '||sqlerrm, 'E'); 
        return;         
    end;
  else
    return;
  end if; 
  
    un$process_log.log(V_ID_PROCESS,'Lansare Expediere email', 'I');

  for c in (select * from (select * from un9mail_msg where status = 1 order by nrmsg) where rownum <= p_nr_mails) loop
      send_email_api_php(c.nrmsg);
  end loop;
    
  exception
  when others then
     commit;  
     begin
        say(1);
      exception
        when others then
          null; -- ignore
      end; 
end;

end;

/

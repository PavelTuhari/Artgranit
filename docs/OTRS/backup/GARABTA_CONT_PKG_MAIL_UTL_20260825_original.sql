CREATE OR REPLACE package body pkg_mail_utl is

----------------------------------------------------------------------------------------------------
procedure fill_un9mail_msg(p_un9mail_msg un9mail_msg%rowtype) is
  pragma autonomous_transaction;
begin
    insert into un9mail_msg
    (nrmsg, subject, sender, text, status, recipients, cc, bcc,nrdoc,dep)
  values
    (p_un9mail_msg.nrmsg, p_un9mail_msg.subject, p_un9mail_msg.sender, 
     p_un9mail_msg.text, p_un9mail_msg.status, p_un9mail_msg.recipients, p_un9mail_msg.cc, p_un9mail_msg.bcc,
     p_un9mail_msg.nrdoc, p_un9mail_msg.dep);
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
  v_url := 'http://api.unisim-soft.com/email_util/send_from_un9mail_msg.php?nr_msg='||p_nrmsg||'&schema=garadei_cont';
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

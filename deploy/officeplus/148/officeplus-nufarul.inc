# PT 27.10.2026: officeplus.una.md (pryamye zahody posle demo-parolya) -> nufarul.eminescu.md.
# Vladelec: "officeplus.una.md perevesti na nufarul ... i front i bek, kak budto eto
# prezhniy officeplus.md". Na nufarul pauza SITE_PAUSE ne deystvuet (Host = nufarul),
# poetomu zdes vse rabotaet. Trafik oblaka (officeplus.md, $op_cloud=1) syuda NE popadaet -
# on po-prezhnemu idet na .250 (@opoffice) i ostaetsya na pauze.
proxy_set_header Host              nufarul.eminescu.md;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header Accept-Encoding   "";
proxy_set_header Upgrade           $http_upgrade;
proxy_set_header Connection        $op_nuf_conn_upgrade;
proxy_ssl_server_name on;
proxy_ssl_name        nufarul.eminescu.md;
proxy_redirect https://nufarul.eminescu.md/ https://officeplus.una.md/;
proxy_redirect http://nufarul.eminescu.md/  https://officeplus.una.md/;
proxy_cookie_domain nufarul.eminescu.md officeplus.una.md;
sub_filter_types text/css application/javascript application/json text/javascript;
sub_filter 'https://nufarul.eminescu.md' 'https://officeplus.una.md';
sub_filter_once off;
add_header X-Robots-Tag "noindex, nofollow" always;
add_header X-Shop-Origin "nufarul" always;
proxy_pass https://92.5.3.187;

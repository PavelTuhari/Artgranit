# Pauza «lucrari tehnice» pentru WordPress-ul officeplus.md (wp-login.php, /wp-admin/)
#
# Proprietarul 22.10.2026: «https://officeplus.md/wp-login.php?... это тоже на паузу,
# типа тех работы ведутся». Comutatorul e ACELASI ca la vitrina: SITE_PAUSE in
# YBIRO_SETTINGS, butonul din https://officeplus.md/UNA.md/orasldev/sitepause/.
#
# Cum: auth_request intreaba Flask-ul local (127.0.0.1:8000, modules/sitepause/routes.py
# /gate): 204 -> cererea merge mai departe ca de obicei (inclusiv cheia secreta
# opgate din officeplus-wp-gate.inc); 403 -> pagina de pauza (503).
# Daca Flask-ul nu raspunde, auth_request da 500 -> tot pagina de pauza (fail-closed
# doar pentru administrarea WP; vitrina nu depinde de acest fisier).
#
# Fisier separat (regula nr. 2). Se include in serverul officeplus.md o singura data;
# directivele «auth_request /_op_wp_pause; error_page 403 500 = @op_wp_pause;» se pun
# in location = /wp-login.php (snippets/wp-harden.conf) si ^~ /wp-admin/
# (officeplus-wp-gate.inc). Copie in git: deploy/officeplus/wp-pause.inc.

location = /_op_wp_pause {
    internal;
    proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/sitepause/gate;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
    proxy_set_header Host officeplus.md;
    proxy_connect_timeout 2s;
    proxy_read_timeout 5s;
}

location @op_wp_pause {
    proxy_pass http://127.0.0.1:8000/UNA.md/orasldev/sitepause/page;
    proxy_set_header Host officeplus.md;
    proxy_intercept_errors off;
}

# Секретный вход в админку WordPress — officeplus.md
#
# Задача (владелец, 01.09.2026): перенести вход на нестандартный адрес, чтобы
# без знания ссылки нельзя было попасть даже на окно логина.
#
#   1. /op-intrare-6b89dc08 — секретная «дверь»: ставит cookie, уводит на форму.
#   2. wp-login.php и /wp-admin/ отдают 404 всем, у кого cookie нет.
#
# ВАЖНО: настоящий «хештег» (#...) браузер на сервер НЕ отправляет, поэтому
# секрет сделан частью пути — эффект тот же, но работает.
#
# wp-login.php здесь НЕ описан: он остаётся в snippets/wp-harden.conf вместе
# с лимитом попыток (limit_req), туда лишь добавлена проверка cookie. Иначе
# получался бы дубль location и терялась защита от перебора.
#
# Отдельный файл — по CLAUDE.md, правило №2.

# ── секретная дверь ───────────────────────────────────────────────────────
location = /op-intrare-6b89dc08 {
    add_header Set-Cookie "opgate=56b2a084855fc3c279411b17d7999d87; Path=/; Max-Age=43200; HttpOnly; Secure; SameSite=Lax";
    return 302 https://$host/wp-login.php;
}

# ── админка: только с cookie ──────────────────────────────────────────────
# admin-ajax.php и admin-post.php остаются открытыми: ими пользуется
# ПУБЛИЧНАЯ часть сайта (формы, плагины) — закрыв их, сломаем витрину.
location = /wp-admin/admin-ajax.php {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/run/php/php8.3-fpm.sock;
}
location = /wp-admin/admin-post.php {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/run/php/php8.3-fpm.sock;
}
location ^~ /wp-admin/ {
    if ($cookie_opgate != "56b2a084855fc3c279411b17d7999d87") { return 404; }
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    }
}

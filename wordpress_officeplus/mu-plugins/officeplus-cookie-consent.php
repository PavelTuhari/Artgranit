<?php
/**
 * Plugin Name: OfficePlus — consimțămînt cookie
 * Description: Același banner de cookie ca pe vitrina (Flask), pe paginile servite de
 *              WordPress (azi practic doar pagina 404). Logica e una singură:
 *              https://officeplus.md/static/biro26/cookie-consent.js — alegerea
 *              (cookie op_consent) e comună cu magazinul. JivoChat pe paginile WP
 *              il porneste tot acest script (vezi officeplus-jivochat.php).
 * Version:     1.0
 *
 * De ce: noua lege a datelor cu caracter personal — nimic ne-esențial înainte de acord.
 * Documentatie: docs/Biro26/COOKIE_CONSIMTAMINT_2026-10-09.md
 */
if (!defined('ABSPATH')) { exit; }

const OFFICEPLUS_CC_VER = '2026100902';   // = ?v= din templates/biro26/_site_cookie_consent.html

add_action('wp_head', function () {
    if (is_admin()) { return; }
    printf('<link rel="stylesheet" href="https://officeplus.md/static/biro26/cookie-consent.css?v=%s">' . "\n",
           OFFICEPLUS_CC_VER);
}, 1);

add_action('wp_footer', function () {
    if (is_admin()) { return; }
    printf('<script src="https://officeplus.md/static/biro26/cookie-consent.js?v=%s" defer></script>' . "\n",
           OFFICEPLUS_CC_VER);
}, 100);

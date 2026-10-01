<?php
/**
 * noindex pentru domeniul INTERN officeplus.una.md.
 *
 * Frontalul public (officeplus.md) trimite cererile incoace tot cu Host
 * intern, dar le marcheaza cu X-Public-Site: 1 - acelea NU primesc
 * noindex, altfel am scoate din Google site-ul public. Doar vizitele
 * DIRECTE pe numele intern se inchid.
 */
add_action('send_headers', function () {
    $host = strtolower($_SERVER['HTTP_HOST'] ?? '');
    $public = ($_SERVER['HTTP_X_PUBLIC_SITE'] ?? '') === '1';
    if ($host === 'officeplus.una.md' && !$public) {
        header('X-Robots-Tag: noindex, nofollow');
    }
});
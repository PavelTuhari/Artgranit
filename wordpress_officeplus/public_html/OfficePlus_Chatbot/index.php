<?php
// RO: nginx-ul site-ului are «index index.php», deci un folder cu doar index.html
//     raspundea 403. Pagina ramine in index.html, aici doar o servim (16.09.2026).
declare(strict_types=1);
header('Content-Type: text/html; charset=utf-8');
readfile(__DIR__ . '/index.html');

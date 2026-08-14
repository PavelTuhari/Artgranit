<?php
/**
 * Plugin Name: OfficePlus Social Analytics
 * Description: Eficiența traficului din rețele sociale și reclamă (fbclid, gclid, ttclid, utm...). Vizitele și conversiile sînt captate de nucleul site-ului și scrise în tabelele wp_op_social_visit / wp_op_social_conv; aici se analizează pe canale, campanii și perioade.
 * Version: 1.0.0
 * Author: OfficePlus
 */

if (!defined('ABSPATH')) exit;

/* ── activare: tabelele (același DDL ca în models/biro26_social.py) ── */
register_activation_hook(__FILE__, function () {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $cs = $wpdb->get_charset_collate();
    dbDelta("CREATE TABLE {$wpdb->prefix}op_social_visit (
        id BIGINT UNSIGNED AUTO_INCREMENT,
        ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        visitor CHAR(32) NOT NULL,
        channel VARCHAR(32) NOT NULL,
        click_param VARCHAR(24) NULL,
        click_id VARCHAR(512) NULL,
        utm_source VARCHAR(150) NULL,
        utm_medium VARCHAR(150) NULL,
        utm_campaign VARCHAR(150) NULL,
        utm_content VARCHAR(150) NULL,
        utm_term VARCHAR(150) NULL,
        landing VARCHAR(512) NULL,
        referrer VARCHAR(512) NULL,
        ua VARCHAR(256) NULL,
        ip_hash CHAR(16) NULL,
        PRIMARY KEY  (id),
        KEY ix_ts (ts), KEY ix_ch (channel, ts), KEY ix_vis (visitor)
    ) $cs;");
    dbDelta("CREATE TABLE {$wpdb->prefix}op_social_conv (
        id BIGINT UNSIGNED AUTO_INCREMENT,
        ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        visitor CHAR(32) NOT NULL,
        first_channel VARCHAR(32) NOT NULL,
        last_channel VARCHAR(32) NOT NULL,
        utm_campaign VARCHAR(150) NULL,
        kind VARCHAR(24) NOT NULL,
        doc_cod VARCHAR(40) NULL,
        amount DECIMAL(12,2) NULL,
        currency CHAR(3) NOT NULL DEFAULT 'MDL',
        PRIMARY KEY  (id),
        KEY ix_ts (ts), KEY ix_ch (last_channel, ts), KEY ix_vis (visitor)
    ) $cs;");
});

/* ── meniul din admin ─────────────────────────────────────────────── */
add_action('admin_menu', function () {
    add_menu_page('Social Analytics', 'Social Analytics',
        'manage_options', 'op-social-analytics',
        'opsa_render_page', 'dashicons-share', 58);
});

/* ── widget pe Dashboard: rezumat 30 zile ─────────────────────────── */
add_action('wp_dashboard_setup', function () {
    wp_add_dashboard_widget('opsa_summary',
        'Rețele sociale — ultimele 30 zile', function () {
        global $wpdb;
        $v = (int)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}op_social_visit
                                  WHERE ts >= NOW() - INTERVAL 30 DAY");
        $c = $wpdb->get_row("SELECT COUNT(*) n, COALESCE(SUM(amount),0) s
                             FROM {$wpdb->prefix}op_social_conv
                             WHERE ts >= NOW() - INTERVAL 30 DAY
                               AND last_channel <> 'direct'");
        printf('<p>Vizite atribuite: <b>%s</b> · Conversii din rețele: <b>%s</b> · Sumă: <b>%s lei</b></p>
                <a href="%s">Raport detaliat →</a>',
            number_format_i18n($v), number_format_i18n((int)$c->n),
            number_format_i18n((float)$c->s, 2),
            esc_url(admin_url('admin.php?page=op-social-analytics')));
    });
});

/* ── etichete canale ──────────────────────────────────────────────── */
function opsa_channel_label($c) {
    $map = array(
        'facebook' => 'Facebook', 'instagram' => 'Instagram',
        'telegram' => 'Telegram', 'tiktok' => 'TikTok',
        'twitter' => 'X (Twitter)', 'vk' => 'VK',
        'odnoklassniki' => 'Odnoklassniki', 'linkedin' => 'LinkedIn',
        'youtube' => 'YouTube', 'pinterest' => 'Pinterest',
        'viber' => 'Viber', 'whatsapp' => 'WhatsApp',
        'google-ads' => 'Google Ads', 'google-organic' => 'Google (organic)',
        'yandex-direct' => 'Yandex Direct', 'yandex-organic' => 'Yandex (organic)',
        'bing-ads' => 'Bing Ads', 'bing-organic' => 'Bing (organic)',
        'snapchat' => 'Snapchat', 'email' => 'Email', 'mailru' => 'Mail.ru',
        'direct' => 'Direct / altele');
    return isset($map[$c]) ? $map[$c] : esc_html($c);
}

/* ── pagina raportului ────────────────────────────────────────────── */
function opsa_render_page() {
    global $wpdb;
    $days = isset($_GET['days']) ? max(1, min(730, (int)$_GET['days'])) : 30;
    $pv = $wpdb->prefix . 'op_social_visit';
    $pc = $wpdb->prefix . 'op_social_conv';

    $visits = $wpdb->get_results($wpdb->prepare(
        "SELECT channel, COUNT(*) clicks, COUNT(DISTINCT visitor) visitors
         FROM $pv WHERE ts >= NOW() - INTERVAL %d DAY
         GROUP BY channel", $days), OBJECT_K);
    $convs = $wpdb->get_results($wpdb->prepare(
        "SELECT last_channel ch, COUNT(*) n, COALESCE(SUM(amount),0) amount
         FROM $pc WHERE ts >= NOW() - INTERVAL %d DAY
         GROUP BY last_channel", $days), OBJECT_K);
    $camps = $wpdb->get_results($wpdb->prepare(
        "SELECT utm_campaign, channel, COUNT(*) clicks,
                COUNT(DISTINCT visitor) visitors
         FROM $pv WHERE ts >= NOW() - INTERVAL %d DAY
           AND utm_campaign IS NOT NULL AND utm_campaign <> ''
         GROUP BY utm_campaign, channel ORDER BY clicks DESC LIMIT 20", $days));
    $recent = $wpdb->get_results($wpdb->prepare(
        "SELECT ts, last_channel, first_channel, kind, doc_cod, amount,
                utm_campaign
         FROM $pc WHERE ts >= NOW() - INTERVAL %d DAY
         ORDER BY ts DESC LIMIT 30", $days));

    // canalele reunite (vizite ∪ conversii, fara direct in tabelul principal)
    $channels = array_unique(array_merge(array_keys($visits), array_keys($convs)));
    sort($channels);
    $maxClicks = 1;
    foreach ($visits as $v) $maxClicks = max($maxClicks, (int)$v->clicks);

    echo '<div class="wrap"><h1>📊 Social Analytics — eficiența rețelelor</h1>';
    echo '<p>Sursa datelor: nucleul site-ului (Flask) scrie fiecare vizită cu
          fbclid / gclid / ttclid / utm / referrer social și fiecare conversie
          (factură, comandă B2B, cerere de credit) în tabelele
          <code>wp_op_social_*</code>. Cookie de atribuție: 90 zile,
          first-touch + last-touch.</p>';
    echo '<form method="get" style="margin:12px 0">
            <input type="hidden" name="page" value="op-social-analytics">
            Perioada: <select name="days" onchange="this.form.submit()">';
    foreach (array(7 => '7 zile', 30 => '30 zile', 90 => '90 zile',
                   365 => '12 luni') as $d => $l)
        printf('<option value="%d"%s>%s</option>', $d,
               $d === $days ? ' selected' : '', $l);
    echo '</select></form>';

    echo '<table class="widefat striped" style="max-width:1000px">
          <thead><tr><th>Canal</th><th>Click-uri</th><th></th>
          <th>Vizitatori</th><th>Conversii</th><th>Rată conv.</th>
          <th>Sumă (lei)</th></tr></thead><tbody>';
    foreach ($channels as $ch) {
        if ($ch === 'direct') continue;
        $vi = isset($visits[$ch]) ? $visits[$ch] : null;
        $co = isset($convs[$ch]) ? $convs[$ch] : null;
        $clicks = $vi ? (int)$vi->clicks : 0;
        $vis = $vi ? (int)$vi->visitors : 0;
        $n = $co ? (int)$co->n : 0;
        $amt = $co ? (float)$co->amount : 0;
        $rate = $vis ? round(100 * $n / $vis, 1) . '%' : '—';
        $bar = (int)round(220 * $clicks / $maxClicks);
        printf('<tr><td><b>%s</b></td><td>%d</td>
                <td><span style="display:inline-block;height:12px;width:%dpx;
                     background:#2271b1;border-radius:3px"></span></td>
                <td>%d</td><td>%d</td><td>%s</td><td>%s</td></tr>',
            opsa_channel_label($ch), $clicks, $bar, $vis, $n, $rate,
            number_format_i18n($amt, 2));
    }
    // conversii fara atribuție — linia de referință
    if (isset($convs['direct'])) {
        printf('<tr style="color:#666"><td>%s</td><td>—</td><td></td><td>—</td>
                <td>%d</td><td>—</td><td>%s</td></tr>',
            opsa_channel_label('direct'), (int)$convs['direct']->n,
            number_format_i18n((float)$convs['direct']->amount, 2));
    }
    echo '</tbody></table>';

    if ($camps) {
        echo '<h2 style="margin-top:26px">Campanii (utm_campaign)</h2>
              <table class="widefat striped" style="max-width:800px">
              <thead><tr><th>Campanie</th><th>Canal</th><th>Click-uri</th>
              <th>Vizitatori</th></tr></thead><tbody>';
        foreach ($camps as $c)
            printf('<tr><td>%s</td><td>%s</td><td>%d</td><td>%d</td></tr>',
                esc_html($c->utm_campaign), opsa_channel_label($c->channel),
                (int)$c->clicks, (int)$c->visitors);
        echo '</tbody></table>';
    }

    if ($recent) {
        echo '<h2 style="margin-top:26px">Ultimele conversii</h2>
              <table class="widefat striped" style="max-width:1000px">
              <thead><tr><th>Data</th><th>Canal (ultim)</th><th>Canal (prim)</th>
              <th>Tip</th><th>Document</th><th>Sumă</th><th>Campanie</th></tr>
              </thead><tbody>';
        $kinds = array('invoice' => 'Factură', 'b2b' => 'Comandă B2B',
                       'credit' => 'Cerere credit', 'credit_req' => 'Solicitare credit');
        foreach ($recent as $r)
            printf('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>
                    <td>%s</td><td>%s</td><td>%s</td></tr>',
                esc_html(mysql2date('d.m.Y H:i', $r->ts)),
                opsa_channel_label($r->last_channel),
                opsa_channel_label($r->first_channel),
                isset($kinds[$r->kind]) ? $kinds[$r->kind] : esc_html($r->kind),
                esc_html($r->doc_cod ?: '—'),
                $r->amount !== null ? number_format_i18n((float)$r->amount, 2) . ' lei' : '—',
                esc_html($r->utm_campaign ?: '—'));
        echo '</tbody></table>';
    }
    echo '</div>';
}

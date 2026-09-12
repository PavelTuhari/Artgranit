<?php
/**
 * Plugin Name: OfficePlus — JivoChat
 * Description: Чат JivoChat на страницах WordPress. Виджет тот же, что на витрине,
 *              иначе чат пропадает, когда посетитель уходит с магазина на
 *              контентные страницы (/despre-companie и прочие их отдаёт WP).
 * Version:     1.0
 *
 * Почему mu-plugin, а не плагин из каталога: он не отключается случайно и
 * переживает смену темы — так же сделаны соседние noindex-internal.php
 * и auto-updates.php.
 *
 * ID виджета: Настройки → Общие → «JivoChat: ID виджета».
 * Тот же ID должен стоять в YBIRO_SETTINGS.SHOP_JIVO_ID для витрины.
 */
if (!defined('ABSPATH')) { exit; }

const OFFICEPLUS_JIVO_OPTION = 'officeplus_jivo_id';

/** Поле в «Настройки → Общие», чтобы ID менялся из админки, а не в коде. */
add_action('admin_init', function () {
    register_setting('general', OFFICEPLUS_JIVO_OPTION, [
        'type'              => 'string',
        'sanitize_callback' => function ($v) {
            // только то, что бывает в ID виджета: буквы, цифры, дефис
            return preg_replace('/[^A-Za-z0-9\-]/', '', (string) $v);
        },
        'default'           => '',
    ]);
    add_settings_field(
        OFFICEPLUS_JIVO_OPTION,
        'JivoChat: ID виджета',
        function () {
            $v = esc_attr(get_option(OFFICEPLUS_JIVO_OPTION, ''));
            echo '<input type="text" id="' . OFFICEPLUS_JIVO_OPTION . '" name="'
               . OFFICEPLUS_JIVO_OPTION . '" value="' . $v . '" class="regular-text">'
               . '<p class="description">Из личного кабинета JivoChat: Управление → '
               . 'Установить JivoChat → код вида <code>//code.jivosite.com/widget/'
               . '<b>XXXXXXXXXX</b></code>. Пусто — чат выключен.</p>';
        },
        'general'
    );
});

/** Сам виджет — в подвал, асинхронно, чтобы не задерживать отрисовку. */
add_action('wp_footer', function () {
    if (is_admin()) { return; }
    $id = trim((string) get_option(OFFICEPLUS_JIVO_OPTION, ''));
    if ($id === '') { return; }          // не задан — чата нет вовсе
    printf(
        '<script src="//code.jivosite.com/widget/%s" async></script>' . "\n",
        esc_attr($id)
    );
}, 99);

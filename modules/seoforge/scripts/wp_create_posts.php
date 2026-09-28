<?php
/**
 * Создание постов-разделов по docs/SEOForge/WP_CATEGORY_POSTS.md.
 *
 * Идемпотентно: пост опознаётся по адресу (slug). Если человек правил
 * текст — пост НЕ перезаписывается, иначе ручная работа пропала бы при
 * следующем прогоне (инструкция, §6).
 *
 * Запуск: wp eval-file wp_create_posts.php [--publish]
 */

$file = '/tmp/officeplus_wp_posts.json';
if (!file_exists($file)) {
    WP_CLI::error("нет файла $file");
}
$posts = json_decode(file_get_contents($file), true);
if (!is_array($posts)) {
    WP_CLI::error('не разобрал JSON');
}

$publish = in_array('--publish', $GLOBALS['argv'] ?? [], true);
$status  = $publish ? 'publish' : 'draft';

// Рубрика для всех постов-разделов — чтобы их было видно вместе.
$cat = get_category_by_slug('ghid-catalog');
if (!$cat) {
    $r = wp_insert_term('Ghid catalog', 'category', ['slug' => 'ghid-catalog']);
    $cat_id = is_wp_error($r) ? 0 : (int) $r['term_id'];
} else {
    $cat_id = (int) $cat->term_id;
}

$created = $updated = $kept = $failed = 0;

foreach ($posts as $p) {
    $slug = sanitize_title($p['slug']);
    $hash = md5($p['content']);

    $existing = get_posts([
        'name'        => $slug,
        'post_type'   => 'post',
        'post_status' => ['publish', 'draft', 'pending', 'private', 'future'],
        'numberposts' => 1,
    ]);

    if ($existing) {
        $post = $existing[0];
        $stored = get_post_meta($post->ID, '_officeplus_hash', true);
        // текст на сайте не совпадает с тем, что мы записали -> правил человек
        if ($stored && md5($post->post_content) !== $stored) {
            $kept++;
            continue;
        }
        $res = wp_update_post([
            'ID'           => $post->ID,
            'post_title'   => $p['title'],
            'post_content' => $p['content'],
            'post_excerpt' => $p['excerpt'],
        ], true);
        if (is_wp_error($res)) { $failed++; continue; }
        update_post_meta($post->ID, '_officeplus_hash', $hash);
        $updated++;
        continue;
    }

    $id = wp_insert_post([
        'post_title'    => $p['title'],
        'post_name'     => $slug,
        'post_content'  => $p['content'],
        'post_excerpt'  => $p['excerpt'],
        'post_status'   => $status,
        'post_type'     => 'post',
        'post_category' => $cat_id ? [$cat_id] : [],
    ], true);

    if (is_wp_error($id) || !$id) { $failed++; continue; }
    update_post_meta($id, '_officeplus_hash', $hash);
    update_post_meta($id, '_officeplus_autogen', '1');
    update_post_meta($id, '_officeplus_kind', $p['kind']);
    update_post_meta($id, '_officeplus_catalog_url', $p['catalog_url']);
    $created++;
}

WP_CLI::success(sprintf(
    'создано %d, обновлено %d, сохранено ручных %d, ошибок %d (статус: %s)',
    $created, $updated, $kept, $failed, $status));

<?php
/**
 * Plugin Name: OfficePlus Auto Updates
 * Description: Enables automatic WordPress core, plugin, theme, and translation updates.
 */

add_filter('auto_update_core', '__return_true');
add_filter('auto_update_plugin', '__return_true');
add_filter('auto_update_theme', '__return_true');
add_filter('auto_update_translation', '__return_true');

// Email site admin when an update completes (WordPress default uses admin_email).
add_filter('auto_core_update_send_email', '__return_true');
add_filter('auto_plugin_update_send_email', '__return_true');
add_filter('auto_theme_update_send_email', '__return_true');

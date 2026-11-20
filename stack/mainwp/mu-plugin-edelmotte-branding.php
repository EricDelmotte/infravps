<?php
/**
 * Plugin Name: Personnalisation e-delmotte
 * Description: Logo e-delmotte sur la page de connexion et icone d onglet.
 */
add_action('login_enqueue_scripts', function () {
	$logo = content_url('uploads/edelmotte/login-logo.png');
	echo '<style>#login h1 a{background-image:url(' . esc_url($logo) . ');background-size:contain;background-position:center;width:320px;height:92px;margin-bottom:20px}</style>';
});
add_filter('login_headerurl', function () { return 'https://www.e-delmotte.fr'; });
add_filter('login_headertext', function () { return 'Eric Delmotte'; });
$edm_icon = function () { echo '<link rel="icon" type="image/png" href="' . esc_url(content_url('uploads/edelmotte/icon.png')) . '">'; };
add_action('login_head', $edm_icon);
add_action('admin_head', $edm_icon);

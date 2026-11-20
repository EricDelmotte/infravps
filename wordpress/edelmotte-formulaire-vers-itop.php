<?php
/**
 * Plugin Name: Formulaire de contact → ticket iTop (e-delmotte)
 * Description: Transmet chaque message du formulaire de contact (Contact Form 7 ou WPForms) à n8n, qui crée une demande ou un incident dans iTop.
 * Version: 1.0
 *
 * Installation : copier ce fichier dans wp-content/mu-plugins/ de l'installation, puis ajouter dans wp-config.php :
 *   define('EDM_FORMULAIRE_SECRET', '…');   // même valeur que /opt/stack/n8n/secrets/form_secret sur le VPS
 *   define('EDM_FORMULAIRE_SITES', 'www.e-delmotte.com,www.arbitre-echecs.fr');
 * Sur un réseau multisite, seuls les sites listés dans EDM_FORMULAIRE_SITES envoient leurs formulaires
 * (les sites des clients hébergés sur le même réseau ne sont pas concernés).
 * Routage côté n8n : www.arbitre-echecs.fr → tâche du tableau de bord Pilotage (pas de ticket) ;
 * les autres sites → demande ou incident iTop.
 *
 * Champs reconnus (noms de champs du formulaire) :
 *   nom      : your-name, nom, name
 *   e-mail   : your-email, email
 *   message  : your-message, message
 *   type     : type  (valeurs « demande » ou « incident » ; « demande » par défaut)
 *   site     : site, your-site, url
 *   téléphone: telephone, your-phone, tel
 * Le formulaire garde son propre envoi d'e-mail : n8n s'ajoute, il ne remplace rien.
 */

if (!defined('ABSPATH')) { exit; }

const EDM_FORMULAIRE_WEBHOOK = 'https://auto.e-delmotte.fr/webhook/formulaire';

function edm_formulaire_choisir(array $donnees, array $cles): string
{
    foreach ($cles as $c) {
        if (isset($donnees[$c]) && $donnees[$c] !== '') {
            $v = $donnees[$c];
            return trim(is_array($v) ? implode(', ', $v) : (string) $v);
        }
    }
    return '';
}

function edm_formulaire_envoyer(array $donnees): void
{
    if (!defined('EDM_FORMULAIRE_SECRET') || EDM_FORMULAIRE_SECRET === '' || !defined('EDM_FORMULAIRE_SITES')) {
        return;
    }
    $hote = (string) wp_parse_url(home_url(), PHP_URL_HOST);
    $sites = array_map('trim', explode(',', strtolower(EDM_FORMULAIRE_SITES)));
    if (!in_array(strtolower($hote), $sites, true)) {
        return; // site non concerné (ex. site d'un client sur le même réseau)
    }
    $type = strtolower(edm_formulaire_choisir($donnees, ['type', 'your-type']));
    $corps = [
        'source'    => $hote,
        'type'      => (strpos($type, 'incident') !== false || strpos($type, 'problème') !== false) ? 'incident' : 'demande',
        'nom'       => edm_formulaire_choisir($donnees, ['your-name', 'nom', 'name']),
        'email'     => edm_formulaire_choisir($donnees, ['your-email', 'email']),
        'telephone' => edm_formulaire_choisir($donnees, ['telephone', 'your-phone', 'tel']),
        'site'      => edm_formulaire_choisir($donnees, ['site', 'your-site', 'url']),
        'message'   => edm_formulaire_choisir($donnees, ['your-message', 'message']),
        'ip'        => $_SERVER['REMOTE_ADDR'] ?? '',
    ];
    if ($corps['email'] === '' || $corps['message'] === '') {
        return;
    }
    wp_remote_post(EDM_FORMULAIRE_WEBHOOK, [
        'timeout'  => 8,
        'blocking' => false, // n'allonge pas l'envoi du formulaire pour le visiteur
        'headers'  => ['Content-Type' => 'application/json', 'X-Formulaire-Secret' => EDM_FORMULAIRE_SECRET],
        'body'     => wp_json_encode($corps),
    ]);
}

// Contact Form 7 : après l'envoi réussi de l'e-mail
add_action('wpcf7_mail_sent', function ($form) {
    if (!class_exists('WPCF7_Submission')) { return; }
    $sub = WPCF7_Submission::get_instance();
    if ($sub) { edm_formulaire_envoyer((array) $sub->get_posted_data()); }
});

// WPForms : après validation de l'entrée (les champs sont identifiés par leur libellé)
add_action('wpforms_process_complete', function ($champs) {
    $donnees = [];
    foreach ((array) $champs as $c) {
        $libelle = strtolower(remove_accents($c['name'] ?? ''));
        $valeur  = (string) ($c['value'] ?? '');
        if (strpos($libelle, 'mail') !== false)                                    { $donnees['email'] = $valeur; }
        elseif (strpos($libelle, 'nom') !== false || strpos($libelle, 'name') !== false) { $donnees['nom'] = $valeur; }
        elseif (strpos($libelle, 'message') !== false)                             { $donnees['message'] = $valeur; }
        elseif (strpos($libelle, 'type') !== false || strpos($libelle, 'concerne') !== false) { $donnees['type'] = $valeur; }
        elseif (strpos($libelle, 'site') !== false)                                { $donnees['site'] = $valeur; }
        elseif (strpos($libelle, 'tel') !== false)                                 { $donnees['telephone'] = $valeur; }
    }
    edm_formulaire_envoyer($donnees);
});

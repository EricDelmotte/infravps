# infravps

Configuration de la plateforme technique e-delmotte sur le VPS OVHcloud `vps-c21dda1c` (Ubuntu 26.04, Docker + Caddy). Ce dépôt sert de référence pour reconstruire ou comprendre le serveur ; **aucun secret n'y figure** : mots de passe, jetons et clés restent dans `/opt/stack/<service>/secrets/` sur le serveur (lecture root uniquement).

> Les données des clients (contacts, contrats, fiches) ne sont pas dans ce dépôt : elles vivent dans iTop et BookStack.

## Services

| Dossier | Adresse | Rôle |
|---|---|---|
| `stack/caddy` | toutes | Reverse proxy et HTTPS automatique ; seul conteneur exposé (80/443) |
| `stack/site-fr` | www.e-delmotte.fr | PHP-FPM du site vitrine (formulaire de contact) ; le site lui-même vient du dépôt `site-e-delmotte-fr` |
| `stack/mainwp` | moniteur-wp.e-delmotte.fr | MainWP (mises à jour des réseaux WordPress) |
| `stack/uptime-kuma` | status.e-delmotte.fr | Surveillance des sites et pages d'état |
| `stack/itop` | itsm.e-delmotte.fr | iTop (tickets, CMDB, contrats) ; `e-delmotte-branding` = extension de logos |
| `stack/bookstack` | docs.e-delmotte.fr | Documentation (procédures publiques, privées, fiches clients) |
| `stack/n8n` | auto.e-delmotte.fr | Automatisations (voir ci-dessous) |
| dépôt `PilotageDashboard` | pilotage.e-delmotte.fr | Tableau de bord personnel |

Réseau Docker externe partagé : `proxy` (Caddy ↔ services). Chaque base de données reste sur un réseau `interne` propre à son service.

## Automatisations n8n

| Workflow | Déclencheur | Effet |
|---|---|---|
| Formulaire de contact → ticket iTop | `POST /webhook/formulaire` (en-tête `X-Formulaire-Secret`) | Crée une demande ou un incident, rattaché au client si l'e-mail est connu et au site concerné |
| Alerte Uptime Kuma → incident iTop | notification Kuma « n8n → iTop » vers `http://n8n:5678/webhook/kuma` (réseau interne uniquement, bloqué par Caddy depuis Internet) | Incident à la panne, résolution automatique au retour |
| Échéances des domaines à J-15 | tous les jours à 8 h 05 | Ticket + tâche dans le tableau de bord : vérifier le renouvellement automatique, ou confirmer avec le client si renouvellement manuel |

Les workflows sont générés par `stack/n8n/build/build.py` puis importés et publiés en ligne de commande :

```bash
sudo docker exec n8n n8n import:workflow --input=/import/n8n-<id>.json
sudo docker exec n8n n8n publish:workflow --id=<id>
```

`wordpress/edelmotte-formulaire-vers-itop.php` : extension à déposer dans `wp-content/mu-plugins/` d'un site WordPress (prévu pour e-delmotte.com) pour envoyer ses formulaires Contact Form 7 ou WPForms vers le même webhook.

## Tâches planifiées (`systemd/`, scripts dans `bin/`)

| Timer | Fréquence | Rôle |
|---|---|---|
| `maj-site-fr` | 5 min | Met à jour le site e-delmotte.fr depuis GitHub (clé de déploiement en lecture seule) |
| `maj-pilotage` | 5 min | Met à jour et reconstruit le tableau de bord depuis GitHub |
| `mainwp-cron` | — | Tâches de fond de MainWP |
| `itop-cron` | 5 min | Tâches de fond d'iTop (e-mails, délais) |

Autres scripts : `ovh-snapshot` (snapshot du VPS via l'API OVH, droits limités au VPS), `bookstack-artisan` (commandes BookStack en tant qu'utilisateur `abc`).

## Remettre un service en route

```bash
cd /opt/stack/<service>
# recréer secrets/ (voir le docker-compose.yml : fichiers attendus)
sudo docker compose up -d
sudo docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Procédures détaillées : livre « Guides du VPS » et « Plateforme e-delmotte » sur docs.e-delmotte.fr.

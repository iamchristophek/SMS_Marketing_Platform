# Baoryx Connect

Plateforme SaaS de marketing par SMS destinée aux PME/PMI de Côte d'Ivoire.

Le suivi des travaux (fait, à faire, anomalies trouvées) est dans [`TASKS.md`](TASKS.md).

## 1. Présentation

Baoryx Connect permet à une entreprise (boutique, restaurant, cabinet, distributeur…) de :

- gérer son fichier clients : contacts, groupes, consentement marketing ;
- envoyer des campagnes SMS personnalisées, tout de suite ou à une date planifiée, en voyant le coût exact avant d'envoyer ;
- acheter des crédits SMS en francs CFA ;
- intégrer l'envoi de SMS dans ses propres outils (ERP, site e-commerce, caisse) grâce à une API REST.

L'application est écrite en Flask (Python). En production, elle s'appuie sur PostgreSQL, Redis, Celery et Caddy (HTTPS automatique). Elle traite en priorité les numéros ivoiriens (+225, plan de numérotation à 10 chiffres) et les agrégateurs utilisés localement (Africa's Talking, Orange, CinetPay).

## 2. Fonctionnalités

**Comptes et sécurité**
- Inscription en libre-service : elle crée une entreprise (`Business`) et son utilisateur propriétaire (`owner`), avec `FREE_TRIAL_CREDITS` crédits offerts, inscrits au journal comptable.
- Connexion, déconnexion, changement de mot de passe, page « Mon compte » (entreprise, email, clés API).
- Protection CSRF sur tous les formulaires (un test vérifie que chaque formulaire POST porte un jeton), erreurs de validation affichées.
- Si le site est servi en HTTP alors que le cookie de session exige HTTPS, un bandeau et une page d'erreur expliquent le problème au lieu d'un formulaire qui échoue en silence.
- Rate limiting : 5 inscriptions par heure, 10 connexions par minute, 200 requêtes par heure par défaut (partagé entre workers via Redis en production).
- En-têtes de sécurité : `X-Content-Type-Options`, `X-Frame-Options` et `Referrer-Policy`.

**Contacts**
- Création, modification, suppression ; liste paginée avec recherche (nom, numéro, email) et filtres (groupe, statut, consentement, opérateur).
- Actions groupées sur les contacts cochés : ajout ou retrait d'un groupe, consentement, suppression.
- Import CSV (virgule ou point-virgule, comme Excel en français) : colonnes `telephone`/`phone` (obligatoire), `prenom`, `nom`, `email`, `consentement`. Les doublons et les numéros invalides sont comptés et ignorés. Taille limitée à `MAX_UPLOAD_MB`.
- Export CSV (avec les filtres en cours), lisible directement dans Excel.
- Consentement marketing daté, par contact, à l'import ou en masse.
- Opérateur détecté automatiquement (plan 2021 : 07 Orange, 05 MTN, 01 Moov). Les lignes fixes (27, 25, 21) sont signalées et exclues des campagnes : elles ne reçoivent pas de SMS.
- Désabonnement : STOP, ARRET ou ARRÊT reçu sur le webhook des SMS entrants marque le contact `opted_out`. Le réabonnement demande une action explicite.

**Modèles de messages** : messages réutilisables (promotionnel, transactionnel, informatif), sélectionnables dans le formulaire de campagne.

**Campagnes**
- En deux étapes : **brouillon → aperçu → confirmation**. L'aperçu montre le nombre de destinataires, le nombre de SMS par destinataire, l'encodage, les crédits nécessaires, le solde après envoi, des exemples de messages personnalisés et les contacts écartés (désabonnés, lignes fixes, sans consentement) avec la raison.
- Cible : un groupe ou tous les contacts ; option « contacts ayant donné leur consentement uniquement ».
- Personnalisation `{prenom}` et `{nom}`, facturée destinataire par destinataire.
- Calcul exact des segments (GSM 03.38 / UCS-2) : un seul caractère hors alphabet GSM (ç, â, ê, ’, emoji…) fait passer le message à 70 caractères par SMS. Le compteur du formulaire l'indique et nomme les caractères en cause.
- Envoi immédiat ou planifié ; annulation d'une campagne planifiée (crédits rendus) ; duplication.
- Suivi SMS par SMS : en attente, envoyé, livré, échec, non livré, avec la raison de l'échec.
- Une campagne sans destinataire ou sans crédits suffisants ne peut pas être confirmée.

**Tableau de bord** : crédits disponibles, SMS envoyés et crédits consommés dans le mois, contacts actifs et consentants, histogramme des envois sur 30 jours, contacts par opérateur, taux de livraison (seulement quand des accusés de livraison existent), campagnes à finaliser et planifiées, guide « Bien démarrer » pour un nouveau client.

**Crédits et paiement**
- Packs de crédits tarifés en F CFA (`CreditPackage`).
- Journal comptable de tous les mouvements (`CreditTransaction`) : achat, envoi SMS, remboursement, crédits offerts.
- Paiement `manual` (hors plateforme, validé par un administrateur) ou `cinetpay` (Orange Money, MTN MoMo, Moov Money, Wave et carte, par redirection).

**API REST v1** : JWT ou clé API (`X-API-Key`) ; contacts, groupes, SMS unitaire, campagnes, solde (voir la section 8).

**Exploitation** : `/healthz`, commandes d'administration en ligne de commande (section 9), Docker Compose avec PostgreSQL, Redis, worker et beat Celery, et Caddy.

## 3. Architecture

```
app/
├── __init__.py             # Application factory : extensions, ProxyFix, blueprints, erreurs (HTML/JSON), filtres Jinja
├── config.py               # Profils development / testing / production, pilotés par variables d'environnement
├── extensions.py           # SQLAlchemy (conventions de nommage), Migrate, LoginManager, CSRF, Limiter, JWT
├── cli.py                  # Commandes d'administration (voir section 9)
├── models/
│   ├── user.py             # Business (tenant) et User (rôles owner / staff)
│   ├── contact.py          # Contact (consentement, opérateur), ContactGroup, table d'association
│   ├── campaign.py         # Campaign, Message (un SMS : texte, statut, crédits réservés/consommés)
│   ├── template.py         # MessageTemplate
│   ├── billing.py          # CreditPackage, CreditTransaction (journal), Payment
│   └── api_key.py          # ApiKey (seul le hash SHA-256 est stocké)
├── blueprints/
│   ├── auth/               # /register, /login, /logout, /change-password
│   ├── dashboard/          # / (accueil) et /dashboard
│   ├── contacts/           # /contacts : contacts, groupes, actions groupées, import/export CSV
│   ├── templates_msg/      # /modeles : modèles de messages
│   ├── campaigns/          # /campaigns : brouillon, aperçu/confirmation, détail, annulation, duplication
│   ├── billing/            # /billing : packs, demandes d'achat, historique
│   ├── account/            # /compte : entreprise, profil, clés API
│   ├── webhooks/           # /webhooks : accusés de livraison, SMS entrants (STOP), notifications de paiement
│   └── api/                # /api/v1 : API JSON et authentification JWT / clé API
├── services/
│   ├── phone.py            # Normalisation E.164, plan +225, opérateurs
│   ├── contact_service.py  # Filtres, import et export CSV
│   ├── campaign_service.py # Personnalisation, estimation, réservation, envoi, annulation
│   ├── billing_service.py  # Mouvements de crédits, validation des paiements
│   ├── stats_service.py    # Chiffres du tableau de bord
│   ├── account_service.py  # Création entreprise + propriétaire
│   ├── sms/                # SmsProvider (console, africastalking, orange, twilio) et encoding.py (GSM-7/UCS-2)
│   └── payment/            # PaymentProvider (manual, cinetpay)
├── tasks/                  # Celery : send_campaign, dispatch_scheduled_campaigns, reconcile_pending_payments
├── templates/              # Gabarits Jinja2
└── static/                 # CSS, js/sms-counter.js (même calcul de segments que le serveur)
migrations/                 # Migrations Alembic (versionnées)
wsgi.py                     # Point d'entrée Gunicorn / Flask CLI
celery_worker.py            # Point d'entrée worker et beat
Caddyfile                   # Reverse proxy HTTPS
tests/                      # Tests pytest
```

### Multi-entreprise

L'unité de cloisonnement est la `Business`, pas l'utilisateur. Contacts, groupes, campagnes, messages, modèles, transactions, paiements et clés API portent tous un `business_id`, et chaque requête filtre dessus. Un même numéro peut exister chez plusieurs entreprises.

### Registre de crédits

- `Business.credit_balance` est un solde en cache. Chaque mouvement passe par `billing_service.adjust_credits()`, qui met à jour le solde et écrit une ligne `CreditTransaction` avec `balance_after`.
- **Réservation à la confirmation.** Quand le client confirme une campagne, la liste des destinataires est figée : un `Message` « en attente » par destinataire, avec son texte personnalisé et son coût exact. La somme est débitée d'un coup. Un brouillon ne coûte rien et n'est jamais envoyé par le worker.
- **Remboursement.** À la fin de l'envoi, les crédits des SMS non partis (échec du fournisseur, contact désabonné entre-temps) sont rendus. L'annulation d'une campagne planifiée rend toute la réservation.
- **SMS unitaire par l'API.** Débité avant l'envoi, remboursé si le fournisseur renvoie une erreur.
- **Paiements.** `billing_service.complete_payment()` crédite un paiement une seule fois, qu'il soit validé par le webhook, la réconciliation périodique ou un administrateur.

### Traitement asynchrone

- `send_campaign` envoie les SMS en attente d'une campagne. En cas d'erreur, la nouvelle tentative reprend là où l'envoi s'était arrêté, sans double envoi ; après la dernière tentative, la campagne passe en échec et les crédits non consommés sont rendus.
- `dispatch_scheduled_campaigns` tourne toutes les 60 s dans Celery beat et lance les campagnes planifiées dont l'heure est passée.
- `reconcile_pending_payments` revérifie auprès de CinetPay les paiements restés en attente.

## 4. Démarrage rapide en local

Prérequis : Python 3.11 ou plus. **N'utilisez pas de fichier `.env` en local** : `.env.example` est prévu pour la production Docker, et les valeurs par défaut du profil `development` suffisent.

```bash
python -m venv venv
source venv/bin/activate            # Windows : venv\Scripts\activate
pip install -r requirements-dev.txt

export FLASK_APP=wsgi.py            # FLASK_ENV vaut development par défaut
flask db upgrade                    # crée la base SQLite instance/sms_marketing.db
flask seed-demo                     # packs de crédits + compte demo (3 contacts)
flask run
```

Ouvrez http://127.0.0.1:5000 et connectez-vous avec **`demo` / `Demo1234!`** (100 crédits).

En profil `development` :
- la base est SQLite ;
- Celery tourne en mode *eager* : les campagnes partent dans la requête, sans Redis ni worker ;
- le fournisseur SMS est `console` : les SMS sont écrits dans les logs ;
- le paiement `manual` laisse les achats en attente ; validez-les avec `flask payments approve <id>`, ou définissez `MANUAL_PAYMENT_AUTO_APPROVE=true` pour une démonstration.

Les campagnes **planifiées** ne partent que si Celery beat tourne : lancez Redis, puis `celery -A celery_worker.celery worker` et `celery -A celery_worker.celery beat`, avec `CELERY_TASK_ALWAYS_EAGER=false`.

## 5. Tests

```bash
pytest            # ou : pytest --cov=app
```

Les tests utilisent le profil `testing` : SQLite en mémoire (clés étrangères activées, comme sur PostgreSQL), CSRF et rate limiting désactivés sauf dans les tests qui les vérifient, Celery *eager* et fournisseur SMS `console`. Ils ne font aucun appel réseau.

## 6. Configuration

Toutes les variables sont lues dans `app/config.py`. Le profil est choisi par `FLASK_ENV`.

| Variable | Rôle | Défaut |
|---|---|---|
| `FLASK_ENV` | Profil : `development`, `testing` ou `production` | `development` |
| `SECRET_KEY`, `JWT_SECRET_KEY` | Clés de signature des sessions et des JWT. En production : obligatoires, 32 caractères minimum, différentes de la valeur d'exemple | valeur de dev en `development` |
| `DOMAIN` | *(docker-compose)* Nom de domaine (certificat Let's Encrypt automatique) ou adresse IP (certificat interne, test) servi par Caddy | — |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | *(docker-compose)* Base PostgreSQL ; `DATABASE_URL` est construite à partir de ces valeurs | `baoryx` / obligatoire / `baoryx` |
| `DATABASE_URL` | URL SQLAlchemy hors Docker. `postgres://` est réécrit en `postgresql://` | `sqlite:///instance/sms_marketing.db` |
| `ALLOW_SQLITE_IN_PROD` | Autorise SQLite en production (déconseillé) | désactivé |
| `SESSION_COOKIE_SECURE` | Cookies envoyés en HTTPS uniquement. `false` seulement pour un test en HTTP sans certificat | `true` (prod), `false` (dev) |
| `PROXY_FIX_COUNT` | Nombre de reverse proxies de confiance (lecture de `X-Forwarded-*`) | `0` ; `1` dans docker-compose |
| `RATELIMIT_STORAGE_URI` | Compteurs de rate limiting | `memory://` ; Redis dans docker-compose |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis pour Celery | `redis://localhost:6379/0` et `/1` |
| `CELERY_TASK_ALWAYS_EAGER` | Exécute les tâches sans worker | `true` (dev), `false` (prod) |
| `WEB_CONCURRENCY` | Nombre de workers Gunicorn (~100 Mo de RAM chacun) | `min(2×CPU+1, 4)` |
| `SMS_PROVIDER` | `console`, `africastalking`, `orange` ou `twilio` | `console` |
| `SMS_SENDER_ID` | Nom d'expéditeur affiché sur les SMS | `BAORYX` |
| `SMS_WEBHOOK_TOKEN` | Jeton secret des URL de callback SMS. Obligatoire en production avec un vrai fournisseur (16 caractères minimum) | — |
| `SMS_COST_CREDITS` | Crédits consommés par segment SMS | `1` |
| `FREE_TRIAL_CREDITS` | Crédits offerts à l'inscription et par `create-admin` | `20` |
| `LOW_BALANCE_THRESHOLD` | Seuil d'alerte de solde faible sur le tableau de bord | `50` |
| `MAX_UPLOAD_MB` | Taille maximale d'un import CSV | `5` |
| `AFRICASTALKING_USERNAME`, `AFRICASTALKING_API_KEY` | Africa's Talking (`sandbox` active le bac à sable) | — |
| `ORANGE_CLIENT_ID`, `ORANGE_CLIENT_SECRET`, `ORANGE_SENDER_ADDRESS` | Orange SMS API | — |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Twilio | — |
| `PAYMENT_PROVIDER` | `manual` ou `cinetpay` | `manual` |
| `MANUAL_PAYMENT_INSTRUCTIONS` | Instructions affichées au client ; `{montant}` et `{reference}` sont remplacés | texte générique |
| `MANUAL_PAYMENT_AUTO_APPROVE` | Crédite tout achat immédiatement. Démonstration uniquement ; **refusé en production** | `false` |
| `CINETPAY_API_KEY`, `CINETPAY_SITE_ID`, `CINETPAY_SECRET_KEY` | CinetPay ; la clé secrète vérifie la signature des notifications | — |
| `MAIL_SUPPORT_ADDRESS` | Adresse de support affichée quand aucune offre de recharge n'existe | `support@baoryx.ci` |

## 7. Fournisseurs SMS et paiement

### SMS (`SMS_PROVIDER`)

| Valeur | Usage | Variables requises |
|---|---|---|
| `console` | Développement et tests : aucun envoi réel | aucune |
| `africastalking` | Agrégateur multi-opérateurs (Orange, MTN, Moov) | `AFRICASTALKING_USERNAME`, `AFRICASTALKING_API_KEY` |
| `orange` | Orange SMS API | `ORANGE_CLIENT_ID`, `ORANGE_CLIENT_SECRET`, `ORANGE_SENDER_ADDRESS` |
| `twilio` | Secours international ; `SMS_SENDER_ID` n'est pas utilisé | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` |

### Paiement (`PAYMENT_PROVIDER`)

| Valeur | Comportement |
|---|---|
| `manual` | En attendant une API Mobile Money. Le client choisit un pack : la demande reste **en attente** avec une référence (ex. `BX12-4F2A`) et les instructions de `MANUAL_PAYMENT_INSTRUCTIONS`. Il paie hors plateforme en indiquant la référence ; un administrateur vérifie la réception puis lance `flask payments approve <id>`. Le client peut annuler une demande non payée. |
| `cinetpay` | Redirection vers la page de paiement CinetPay. Les crédits sont ajoutés quand la notification arrive (signature vérifiée, statut revérifié auprès de CinetPay), ou par la réconciliation périodique. |

### Webhooks à déclarer chez les fournisseurs

| URL | Méthode | Rôle |
|---|---|---|
| `https://<DOMAIN>/webhooks/sms/delivery-report?token=<SMS_WEBHOOK_TOKEN>` | POST | Accusé de livraison : `id` ou `messageId`, `status` (`success`/`delivered` ou `failed`/`rejected`/`expired`), `failureReason` (format Africa's Talking) |
| `https://<DOMAIN>/webhooks/sms/inbound?token=<SMS_WEBHOOK_TOKEN>` | POST | SMS entrants : `from` ou `phoneNumber`, `text`. STOP, ARRET ou ARRÊT désabonne le numéro |
| `https://<DOMAIN>/webhooks/payment/callback` | POST ou GET | Notification CinetPay, authentifiée par signature HMAC (`X-TOKEN`) |

Sans le bon jeton, les webhooks SMS répondent 403. Le jeton peut aussi être passé dans l'en-tête `X-Webhook-Token`.

## 8. API REST v1

Préfixe : `/api/v1`. Réponses JSON, y compris les erreurs (`{"error": "..."}`).

### Authentification

1. **Clé API** : en-tête `X-API-Key: baoryx_...`, pour les intégrations serveur à serveur. Les clés se créent et se révoquent dans **Mon compte → Clés API** ; la valeur en clair n'est affichée qu'une seule fois.
2. **JWT** : en-tête `Authorization: Bearer <access_token>`.

```bash
curl -X POST https://<DOMAIN>/api/v1/auth/token \
  -H "Content-Type: application/json" -d '{"username": "...", "password": "..."}'
# → {"access_token": "...", "refresh_token": "..."}   (accès : 1 h, rafraîchissement : 30 jours)
```

### Endpoints

| Méthode | Chemin | Description |
|---|---|---|
| POST | `/auth/token` | Jetons d'accès et de rafraîchissement (10 requêtes/minute) |
| POST | `/auth/refresh` | Nouveau jeton d'accès (JWT de rafraîchissement) |
| GET | `/me` | Entreprise et solde |
| GET | `/contacts?page=&per_page=` | Contacts paginés (`per_page` ≤ 200) |
| POST | `/contacts` | Crée un contact : `phone` (requis), `first_name`, `last_name`, `email`. 409 si le numéro existe |
| GET | `/groups` | Groupes et nombre de contacts actifs |
| POST | `/sms/send` | SMS unitaire : `to`, `message` (≤ 640 caractères). 201, 402 (crédits insuffisants) ou 502 (échec fournisseur, remboursé). 60 requêtes/minute |
| POST | `/campaigns` | Crée **et confirme** une campagne (pas d'aperçu pour un système externe) : `name`, `message`, `group_id`, `consent_only`, `scheduled_at` (ISO 8601, UTC par défaut). 402 si crédits insuffisants, 422 sans destinataire |
| GET | `/campaigns/<id>` | Statut et compteurs |
| GET, POST, DELETE | `/api-keys` | Gestion des clés par une session web (équivalent de l'écran Mon compte) |

Hors préfixe, `GET /healthz` renvoie `{"status": "ok"}`.

```bash
curl -X POST https://<DOMAIN>/api/v1/sms/send \
  -H "X-API-Key: baoryx_xxxxxxxxxxxxxxxx" -H "Content-Type: application/json" \
  -d '{"to": "07 12 34 56 78", "message": "Votre commande #1234 est prête. Merci !"}'
# → 201 {"id": 42, "status": "sent", "provider_message_id": "...", "credits_used": 1, "error": null}
```

## 9. Déploiement en production

`docker-compose.yml` démarre six services : `db` (PostgreSQL 16), `redis`, `web` (migrations puis Gunicorn), `worker` et `beat` (Celery), et `caddy` (HTTPS, seul service exposé, ports 80 et 443).

```bash
cp .env.example .env
# Renseignez au minimum :
#   SECRET_KEY, JWT_SECRET_KEY   python -c "import secrets; print(secrets.token_urlsafe(64))"
#   DOMAIN                       nom de domaine pointant vers le serveur (ou IP pour un test)
#   POSTGRES_PASSWORD
#   SMS_PROVIDER + identifiants, SMS_SENDER_ID, SMS_WEBHOOK_TOKEN
#   MANUAL_PAYMENT_INSTRUCTIONS  (votre numéro Orange Money / Wave)

docker compose up -d --build
docker compose exec web flask seed-packages       # packs de crédits par défaut
docker compose exec web flask create-admin        # premier compte (mot de passe demandé)
```

L'application est alors disponible sur `https://<DOMAIN>`. Avec une adresse IP, Caddy utilise un certificat interne : le navigateur affiche un avertissement à accepter une fois (suffisant pour un test, pas pour des clients).

### Administration courante

```bash
docker compose exec web flask businesses list                  # entreprises, soldes, propriétaires
docker compose exec web flask payments list [--all]            # demandes d'achat en attente
docker compose exec web flask payments approve <id>            # paiement reçu : crédite l'entreprise
docker compose exec web flask payments reject <id>             # paiement jamais reçu
docker compose exec web flask credits add <utilisateur> 50 --reason "Geste commercial"
docker compose exec web flask reset-password <utilisateur>     # mot de passe oublié
```

`flask seed-demo` est refusé en production : il crée un compte au mot de passe public.

### Points à connaître

- **Garde-fous du profil production.** L'application refuse de démarrer avec des clés secrètes absentes, courtes ou d'exemple, avec SQLite (sauf `ALLOW_SQLITE_IN_PROD=1`), avec `MANUAL_PAYMENT_AUTO_APPROVE`, ou avec un vrai fournisseur SMS sans `SMS_WEBHOOK_TOKEN`.
- **Migrations.** `flask db upgrade` est lancé à chaque démarrage de `web`. Après une modification des modèles : `flask db migrate -m "description"`, relire le fichier généré (types et valeurs par défaut compatibles PostgreSQL), puis `flask db upgrade`.
- **Montée en charge.** Web : `WEB_CONCURRENCY`. Envois : `docker compose up -d --scale worker=3` ou `--concurrency`. Ne lancez qu'**une seule** instance de `beat`.
- **Healthchecks.** `web` interroge `/healthz`, `worker` répond à `celery inspect ping`.

## 10. Avant l'ouverture à de vrais clients

La liste détaillée et à jour est dans [`TASKS.md`](TASKS.md). Les points qui ne relèvent pas du code :

- Signer avec un agrégateur SMS et faire enregistrer le sender ID (`SMS_SENDER_ID`) auprès d'Orange, MTN et Moov.
- Paiement : décider du numéro Mobile Money qui reçoit les paiements manuels, puis ouvrir un compte marchand CinetPay pour automatiser.
- Conformité à la **loi n°2013-450** (protection des données) : déclaration auprès de l'ARTCI, CGU/CGV, politique de confidentialité, durée de conservation.
- Règles anti-spam : plages horaires d'envoi, mention « STOP » dans les messages promotionnels.
- Sauvegardes automatisées du volume PostgreSQL (`baoryx_db_data`), avec test de restauration ; supervision (Sentry, alertes sur les files Celery).
- Recette avec de vrais numéros Orange, MTN et Moov.

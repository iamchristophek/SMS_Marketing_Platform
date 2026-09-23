# Baoryx Connect

Plateforme SaaS de marketing par SMS destinée aux PME/PMI de Côte d'Ivoire.

## 1. Présentation

Baoryx Connect permet à une entreprise (boutique, restaurant, cabinet, distributeur…) de :

- gérer son fichier clients (contacts et groupes) ;
- envoyer des campagnes SMS, tout de suite ou à une date planifiée ;
- acheter des crédits SMS en Francs CFA (XOF) ;
- intégrer l'envoi de SMS dans ses propres outils (ERP, site e-commerce, CRM) grâce à une API REST.

L'application est écrite en Flask (Python). Elle s'appuie sur PostgreSQL, Redis et Celery en production. Elle traite en priorité les numéros ivoiriens (+225, plan de numérotation à 10 chiffres) et les agrégateurs utilisés localement (Africa's Talking, Orange, CinetPay).

## 2. Fonctionnalités

**Comptes et sécurité**
- Inscription en libre-service, qui crée une entreprise (`Business`) et son utilisateur propriétaire (`owner`). Le nouveau compte reçoit `FREE_TRIAL_CREDITS` crédits offerts.
- Connexion, déconnexion et changement de mot de passe.
- Protection CSRF sur les formulaires web.
- Rate limiting : 5 inscriptions par heure, 10 connexions par minute, 200 requêtes par heure par défaut.
- En-têtes de sécurité : `X-Content-Type-Options`, `X-Frame-Options` et `Referrer-Policy`.

**Contacts**
- Création manuelle, suppression et liste paginée.
- Import CSV. Colonnes acceptées : `phone` / `téléphone` / `telephone`, `first_name` / `prenom`, `last_name` / `nom` et `email`. Les doublons et les numéros invalides sont comptés et ignorés.
- Groupes (segments) : création et suppression, avec un nom unique par entreprise.
- Normalisation des numéros au format E.164 (`app/services/phone.py`). Les formats `07 12 34 56 78`, `0712345678`, `+2250712345678` et `00225…` sont acceptés. Préfixes ivoiriens reconnus : 01, 05, 07, 21, 25, 27.
- Désabonnement : le contact est marqué `opted_out` à la réception de STOP, ARRET ou ARRÊT sur le webhook des SMS entrants. Il est alors exclu des campagnes.

**Campagnes**
- Une campagne cible un groupe ou tous les contacts actifs. Un message fait au plus 640 caractères.
- Le nombre de segments est calculé en GSM-7 : 160 caractères pour un SMS unique, 153 par segment au-delà.
- Envoi immédiat ou planifié. Les crédits sont réservés à la création de la campagne.
- Envoi asynchrone par Celery, avec un suivi message par message : `queued`, `sent`, `delivered`, `failed` ou `undelivered`.
- Une campagne en brouillon ou planifiée peut être supprimée. Ses crédits réservés sont alors remboursés.
- Le tableau de bord affiche le nombre de campagnes, de contacts actifs et de SMS envoyés, ainsi que le taux de livraison moyen.

**Crédits et paiement**
- Packs de crédits tarifés en XOF (`CreditPackage`).
- Journal comptable des mouvements de crédits (`CreditTransaction`) de type `purchase`, `consumption`, `refund` ou `bonus`.
- Paiement `manual`, validé immédiatement, ou `cinetpay` (Orange Money, MTN MoMo, Moov Money, Wave et carte, par redirection).

**API REST v1**
- Authentification par JWT ou par clé d'API (`X-API-Key`).
- Endpoints pour les contacts, les groupes, l'envoi de SMS unitaires, les campagnes et le solde (voir la section 8).

**Exploitation**
- Endpoint `/healthz`.
- Commandes CLI `flask create-admin` et `flask seed-demo`.
- Image Docker et `docker-compose.yml` avec les services web, worker, beat, PostgreSQL et Redis.

## 3. Architecture

```
app/
├── __init__.py            # Application factory : extensions, blueprints, erreurs (HTML/JSON), /healthz, en-têtes de sécurité
├── config.py              # Profils development / testing / production, tous pilotés par variables d'environnement
├── extensions.py          # Instances partagées : SQLAlchemy, Migrate, LoginManager, CSRF, Limiter, JWT
├── cli.py                 # Commandes `flask create-admin` et `flask seed-demo`
├── models/
│   ├── user.py            # Business (tenant) et User (rôles owner / staff)
│   ├── contact.py         # Contact, ContactGroup, table d'association
│   ├── campaign.py        # Campaign, Message, calcul des segments SMS
│   ├── billing.py         # CreditPackage, CreditTransaction (journal), Payment
│   └── api_key.py         # ApiKey (seul le hash SHA-256 est stocké)
├── blueprints/
│   ├── auth/              # /register, /login, /logout, /change-password
│   ├── dashboard/         # / (accueil) et /dashboard
│   ├── contacts/          # /contacts : contacts, groupes, import CSV
│   ├── campaigns/         # /campaigns : création, détail, suppression
│   ├── billing/           # /billing : packs, historique, achat
│   ├── webhooks/          # /webhooks : accusés de livraison, SMS entrants (STOP), callback de paiement
│   └── api/               # /api/v1 : API JSON (routes.py) et authentification JWT / clé API (auth.py)
├── services/
│   ├── phone.py           # Normalisation E.164, spécificités +225
│   ├── billing_service.py # Mouvements de crédits (débit, remboursement, achat, bonus)
│   ├── campaign_service.py# Destinataires, estimation du coût, réservation, exécution de l'envoi
│   ├── sms/               # Abstraction SmsProvider : console, africastalking, orange, twilio
│   └── payment/           # Abstraction PaymentProvider : manual, cinetpay
├── tasks/
│   ├── __init__.py        # Configuration Celery (make_celery) et planning beat
│   └── sms_tasks.py       # send_campaign et dispatch_scheduled_campaigns
├── templates/             # Gabarits Jinja2 (pages web et pages d'erreur 403/404/429/500)
└── static/                # CSS
wsgi.py                    # Point d'entrée Gunicorn / Flask CLI (wsgi:app)
celery_worker.py           # Point d'entrée des processus Celery worker et beat
gunicorn.conf.py           # Écoute sur 0.0.0.0:8000, 2×CPU+1 workers sync
tests/                     # Tests pytest
```

### Multi-tenancy

L'unité de cloisonnement est la `Business` (l'entreprise cliente), pas l'utilisateur. Contacts, groupes, campagnes, messages, transactions, paiements et clés d'API portent tous un `business_id`. Chaque requête filtre sur l'entreprise de l'utilisateur connecté (`current_user.business_id`) ou sur celle qui est résolue par l'API (`g.current_business`). Un même numéro de téléphone peut exister chez plusieurs entreprises (unicité `business_id` + `phone_e164`).

### Registre de crédits

- `Business.credit_balance` est un solde en cache. Chaque mouvement passe par `billing_service.adjust_credits()`, qui met à jour le solde et écrit une ligne `CreditTransaction` avec `balance_after`. Un mouvement qui rendrait le solde négatif lève `InsufficientCreditsError`.
- **Réservation à la création.** `campaign_service.reserve_credits()` calcule `segments × SMS_COST_CREDITS × nombre de destinataires` et débite ce montant tout de suite. Si le solde ne suffit pas, la campagne est refusée (HTTP 402 côté API). Cela empêche une entreprise de lancer en parallèle plusieurs campagnes au-delà de son solde.
- **Remboursement des échecs.** À la fin de l'envoi, `execute_campaign()` rembourse la différence entre les crédits réservés et les crédits réellement consommés, c'est-à-dire les SMS refusés par le fournisseur.
- **SMS unitaire par l'API.** Le coût est débité avant l'envoi et remboursé si le fournisseur renvoie une erreur.
- Supprimer une campagne en brouillon ou planifiée rembourse la totalité de sa réservation.

### Abstraction des fournisseurs

- **SMS.** `SmsProvider.send(to_e164, message, sender_id)` renvoie toujours un `SmsSendResult` et ne lève jamais d'exception réseau. `services/sms/factory.py` choisit l'implémentation d'après `SMS_PROVIDER`.
- **Paiement.** `PaymentProvider.initiate()` démarre la transaction, puis `verify_status()` interroge le fournisseur pour connaître l'état réel. `services/payment/factory.py` choisit l'implémentation d'après `PAYMENT_PROVIDER`.

Pour ajouter un fournisseur, il suffit d'écrire une classe et de l'ajouter à la factory.

### Traitement asynchrone

- La tâche `send_campaign` envoie une campagne. Elle est lancée par `.delay()` pour un envoi immédiat.
- La tâche périodique `dispatch_scheduled_campaigns` tourne toutes les 60 s dans Celery beat. Elle met en file les campagnes `scheduled` dont l'heure (`scheduled_at`) est passée.

## 4. Démarrage rapide en local

Prérequis : Python 3.11 ou plus (l'image Docker utilise 3.12).

```bash
python -m venv venv
source venv/bin/activate            # Windows : venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env
```

**Attention :** `.env.example` est préparé pour la production Docker. La Flask CLI charge automatiquement `.env` (grâce à python-dotenv). Avant de lancer en local, ouvrez `.env` et faites les changements suivants :

```dotenv
FLASK_ENV=development
SESSION_COOKIE_SECURE=false        # sinon la session ne fonctionne pas en http://
# Commentez ces lignes : en local, SQLite est utilisé par défaut (instance/sms_marketing.db)
# DATABASE_URL=postgresql://baoryx:baoryx@db:5432/baoryx
# CELERY_BROKER_URL=...
# CELERY_RESULT_BACKEND=...
```

Ensuite :

```bash
export FLASK_APP=wsgi.py
flask db upgrade        # applique les migrations Alembic (dossier migrations/)
flask seed-demo         # packs de crédits + compte de démonstration
flask run
```

Ouvrez http://127.0.0.1:5000 et connectez-vous avec le compte de démonstration : **`demo` / `Demo1234!`** (100 crédits).

En profil `development` :
- la base est SQLite (`instance/sms_marketing.db`) ;
- Celery tourne en mode *eager* (`CELERY_TASK_ALWAYS_EAGER=true`) : les campagnes sont envoyées de façon synchrone dans la requête, sans Redis ni worker ;
- le fournisseur SMS par défaut est `console`, qui se contente d'écrire les SMS dans les logs ;
- le paiement par défaut est `manual` : l'achat d'un pack crédite le compte tout de suite.

Redis n'est donc pas nécessaire en local. Les campagnes **planifiées** ne partent cependant que si Celery beat tourne. Pour les tester, lancez Redis puis `celery -A celery_worker.celery worker` et `celery -A celery_worker.celery beat`, avec `CELERY_TASK_ALWAYS_EAGER=false`.

Pour créer un vrai compte propriétaire :

```bash
flask create-admin --username admin --email admin@ma-pme.ci --business "Ma PME"
# le mot de passe est demandé de façon interactive
```

## 5. Tests

```bash
pytest            # ou : pytest --cov=app
```

Les tests utilisent le profil `testing` : SQLite en mémoire (clés étrangères activées, comme sur PostgreSQL), CSRF et rate limiting désactivés, Celery *eager* et fournisseur SMS `console`. Ils ne font aucun appel réseau. Ils couvrent l'authentification, la facturation, les campagnes (dont la reprise après échec et l'anti-double envoi), la normalisation des numéros, les fournisseurs SMS, les pages web, les webhooks et l'API REST.

## 6. Configuration

Toutes les variables sont lues dans `app/config.py`. Le profil est choisi par `FLASK_ENV`.

| Variable | Rôle | Défaut |
|---|---|---|
| `FLASK_ENV` | Profil : `development`, `testing` ou `production` | `development` |
| `SECRET_KEY` | Clé de signature des sessions. **Obligatoire en production** | `dev-secret-key-change-me` en dev, aucun défaut en prod |
| `JWT_SECRET_KEY` | Clé de signature des JWT de l'API | valeur de `SECRET_KEY` |
| `DATABASE_URL` | URL SQLAlchemy. `postgres://` est réécrit en `postgresql://` | `sqlite:///instance/sms_marketing.db` |
| `ALLOW_SQLITE_IN_PROD` | Autorise SQLite en production (déconseillé) | désactivé |
| `SESSION_COOKIE_SECURE` | Cookies de session et « remember me » envoyés en HTTPS uniquement | `true` (prod), `false` (dev) |
| `RATELIMIT_STORAGE_URI` | Stockage des compteurs de rate limiting, par exemple `redis://redis:6379/2` | `memory://` |
| `CELERY_BROKER_URL` | Broker Celery | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Backend de résultats Celery | `redis://localhost:6379/1` |
| `CELERY_TASK_ALWAYS_EAGER` | Exécute les tâches de façon synchrone, sans worker | `true` (dev), `false` (prod) |
| `SMS_PROVIDER` | `console`, `africastalking`, `orange` ou `twilio` | `console` |
| `SMS_SENDER_ID` | Nom d'expéditeur (sender ID) affiché sur les SMS | `BAORYX` |
| `SMS_COST_CREDITS` | Crédits consommés par segment SMS | `1` |
| `SMS_MAX_PER_MESSAGE_SEGMENTS` | Lu dans la configuration mais **pas encore utilisé** par le code | `3` |
| `FREE_TRIAL_CREDITS` | Crédits offerts à l'inscription et par `create-admin` | `20` |
| `AFRICASTALKING_USERNAME` / `AFRICASTALKING_API_KEY` | Identifiants Africa's Talking. Le username `sandbox` active le bac à sable | — |
| `ORANGE_CLIENT_ID` / `ORANGE_CLIENT_SECRET` / `ORANGE_SENDER_ADDRESS` | Identifiants Orange SMS API (OAuth2 client_credentials) | — |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` | Identifiants Twilio | — |
| `PAYMENT_PROVIDER` | `manual` ou `cinetpay` | `manual` |
| `CINETPAY_API_KEY` / `CINETPAY_SITE_ID` | Identifiants CinetPay | — |
| `CINETPAY_SECRET_KEY` | Clé secrète marchande CinetPay, utilisée pour vérifier la signature HMAC (`X-TOKEN`) des notifications de paiement. Obligatoire avec `cinetpay` : sans elle, toutes les notifications sont rejetées | — |
| `MAIL_SUPPORT_ADDRESS` | Adresse de support. Lue dans la configuration mais **pas encore utilisée** | `support@baoryx.ci` |

Certaines valeurs sont fixes dans le code et ne sont pas configurables par variable d'environnement : sessions de 12 h, JWT d'accès valable 1 h, JWT de rafraîchissement valable 30 jours, indicatif par défaut `225` et `PREFERRED_URL_SCHEME=https`.

## 7. Fournisseurs SMS et paiement

### SMS (`SMS_PROVIDER`)

| Valeur | Usage | Variables requises |
|---|---|---|
| `console` | Développement et tests : aucun envoi réel, les SMS sont écrits dans les logs | aucune |
| `africastalking` | Agrégateur multi-opérateurs (Orange, MTN, Moov) | `AFRICASTALKING_USERNAME`, `AFRICASTALKING_API_KEY` |
| `orange` | Orange SMS API (Orange Developer) | `ORANGE_CLIENT_ID`, `ORANGE_CLIENT_SECRET`, `ORANGE_SENDER_ADDRESS` |
| `twilio` | Solution de secours internationale. Le SMS part de `TWILIO_FROM_NUMBER`, et `SMS_SENDER_ID` n'est pas utilisé | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` |

S'il manque une variable requise, une `ValueError` est levée au premier envoi.

### Paiement (`PAYMENT_PROVIDER`)

| Valeur | Comportement | Variables requises |
|---|---|---|
| `manual` | Le paiement est considéré comme réussi immédiatement et les crédits sont ajoutés tout de suite. **À réserver à la démonstration ou à une phase pilote contrôlée.** | aucune |
| `cinetpay` | Redirige vers la page de paiement CinetPay. Les crédits sont ajoutés quand le callback arrive, après revérification du statut auprès de CinetPay. | `CINETPAY_API_KEY`, `CINETPAY_SITE_ID` |

### Webhooks à déclarer chez les fournisseurs

Les webhooks sont exemptés de CSRF.

| URL | Méthode | Rôle | Format attendu |
|---|---|---|---|
| `https://<domaine>/webhooks/sms/delivery-report` | POST | Accusé de livraison (DLR) | Formulaire ou JSON avec `id` ou `messageId`, `status` (`success`/`delivered` ou `failed`/`rejected`/`expired`) et `failureReason` en option. C'est le format d'Africa's Talking. |
| `https://<domaine>/webhooks/sms/inbound` | POST | SMS entrants. STOP, ARRET ou ARRÊT désabonne le numéro | `from` ou `phoneNumber`, et `text` |
| `https://<domaine>/webhooks/payment/callback` | POST ou GET | Notification de paiement (`notify_url`) | `transaction_id`, `cpm_trans_id` ou `?token=` |

L'application envoie elle-même l'URL de callback de paiement à CinetPay à chaque transaction (`url_for(..., _external=True)`). Elle doit donc voir le bon nom d'hôte et le bon schéma derrière le reverse proxy (voir la checklist).

## 8. API REST v1

Préfixe : `/api/v1`. Les réponses sont en JSON, y compris les erreurs (`{"error": "..."}`).

### Authentification

Deux mécanismes sont acceptés sur les routes protégées. Ils sont essayés dans cet ordre :

1. **Clé d'API** : en-tête `X-API-Key: baoryx_...`. Elle est destinée aux intégrations serveur à serveur. La clé est créée par un utilisateur connecté à l'interface web avec `POST /api/v1/api-keys` (session et jeton CSRF requis). Sa valeur en clair n'est affichée qu'une seule fois. Il n'existe pas encore d'écran dédié dans l'interface.
2. **JWT** : en-tête `Authorization: Bearer <access_token>`.

```bash
# Obtenir un couple de jetons (limité à 10 requêtes par minute)
curl -X POST https://<domaine>/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "Demo1234!"}'
# → {"access_token": "...", "refresh_token": "..."}

# Rafraîchir le jeton d'accès (valable 1 h) avec le jeton de rafraîchissement (valable 30 jours)
curl -X POST https://<domaine>/api/v1/auth/refresh \
  -H "Authorization: Bearer <refresh_token>"
```

### Endpoints

| Méthode | Chemin | Auth | Description |
|---|---|---|---|
| POST | `/auth/token` | aucune | Échange un nom d'utilisateur et un mot de passe contre un jeton d'accès et un jeton de rafraîchissement |
| POST | `/auth/refresh` | JWT de rafraîchissement | Nouveau jeton d'accès |
| GET | `/me` | clé API ou JWT | Entreprise et solde de crédits |
| GET | `/contacts?page=&per_page=` | clé API ou JWT | Liste paginée des contacts (`per_page` ≤ 200) |
| POST | `/contacts` | clé API ou JWT | Crée un contact : `phone` (requis), `first_name`, `last_name`, `email`. Renvoie 409 si le numéro existe déjà |
| GET | `/groups` | clé API ou JWT | Liste des groupes, avec le nombre de contacts actifs |
| POST | `/sms/send` | clé API ou JWT | SMS transactionnel unitaire : `to`, `message` (≤ 640 caractères). Renvoie 201, 402 (crédits insuffisants) ou 502 (échec fournisseur, remboursé). Limité à 60 requêtes par minute |
| POST | `/campaigns` | clé API ou JWT | Crée une campagne : `name`, `message`, `group_id` en option, `scheduled_at` en option (ISO 8601, UTC par défaut). Envoi immédiat si l'heure est absente ou passée. Renvoie 402 si les crédits sont insuffisants |
| GET | `/campaigns/<id>` | clé API ou JWT | Statut et compteurs (envoyés, livrés, en échec, crédits) |
| GET | `/api-keys` | session web | Liste des clés de l'entreprise |
| POST | `/api-keys` | session web + CSRF | Crée une clé (`name`) et renvoie la valeur en clair une seule fois |
| DELETE | `/api-keys/<id>` | session web + CSRF | Révoque une clé |

Hors préfixe, `GET /healthz` renvoie `{"status": "ok"}`.

### Exemples

```bash
# Envoyer un SMS (confirmation de commande, par exemple)
curl -X POST https://<domaine>/api/v1/sms/send \
  -H "X-API-Key: baoryx_xxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{"to": "07 12 34 56 78", "message": "Votre commande #1234 est prête. Merci !"}'
# → 201 {"id": 42, "status": "sent", "provider_message_id": "...", "credits_used": 1, "error": null}

# Créer une campagne planifiée pour un groupe
curl -X POST https://<domaine>/api/v1/campaigns \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Promo rentrée", "message": "-20% ce week-end dans nos boutiques de Cocody et Yopougon !", "group_id": 3, "scheduled_at": "2026-10-01T09:00:00+00:00"}'
# → 201 {"id": 7, "status": "scheduled", "total_recipients": 250}
```

## 9. Déploiement en production

`docker-compose.yml` démarre cinq services :
- `db` : PostgreSQL 16 ;
- `redis` : Redis 7 ;
- `web` : exécute `flask db upgrade` puis Gunicorn sur le port 8000 ;
- `worker` : worker Celery (`--concurrency=2`) ;
- `beat` : planificateur Celery.

```bash
cp .env.example .env
# Renseignez au minimum SECRET_KEY et JWT_SECRET_KEY (valeurs longues et aléatoires),
# SMS_PROVIDER, les identifiants correspondants, SMS_SENDER_ID et PAYMENT_PROVIDER.
# Par exemple : python -c "import secrets; print(secrets.token_urlsafe(64))"

docker compose up -d --build
docker compose exec web flask create-admin
docker compose exec web flask seed-demo     # optionnel : crée les packs de crédits (et le compte demo)
```

Points à connaître :

- **Garde-fous du profil production.** `ProductionConfig` refuse de démarrer sans `SECRET_KEY`. Il refuse aussi une base SQLite, sauf si `ALLOW_SQLITE_IN_PROD=1`.
- **Migrations.** Le schéma est géré par Flask-Migrate / Alembic (dossier `migrations/`, versionné). Après une modification des modèles : `flask db migrate -m "description"`, relire le fichier généré, puis `flask db upgrade`.
- **Packs de crédits.** Il n'existe pas encore d'interface d'administration. Les packs sont créés par `flask seed-demo`, qui crée aussi le compte `demo`, ou directement en base. Supprimez ou désactivez le compte `demo` en production.
- **HTTPS et reverse proxy.** `SESSION_COOKIE_SECURE=true` par défaut : il faut servir l'application en HTTPS derrière un reverse proxy (Nginx, Caddy, Traefik) qui termine le TLS et redirige vers `web:8000`. En HTTP simple, la connexion ne fonctionne pas. L'application ne configure pas encore `ProxyFix` (voir la checklist).
- **Mot de passe PostgreSQL.** Les identifiants PostgreSQL (`baoryx`/`baoryx`) sont écrits en dur dans `docker-compose.yml`. Changez-les et gardez `DATABASE_URL` cohérent.
- **Rate limiting partagé.** Définissez `RATELIMIT_STORAGE_URI=redis://redis:6379/2`. Sinon, chaque worker Gunicorn garde ses propres compteurs en mémoire.
- **Montée en charge des envois.** Augmentez le nombre de workers Celery avec `docker compose up -d --scale worker=3` ou via `--concurrency`. Ne lancez qu'**une seule** instance de `beat`, sinon les campagnes planifiées sont mises en file plusieurs fois.
- **Montée en charge du web.** Gunicorn démarre `2 × CPU + 1` workers synchrones (`gunicorn.conf.py`).
- **Healthcheck.** L'image Docker interroge `/healthz` toutes les 30 s.

## 10. Checklist avant mise en production

Ce qui reste à faire ou à valider avant un vrai lancement en Côte d'Ivoire. Chaque point a été vérifié dans le code actuel.

**Contrats et conformité**
- [ ] Signer un contrat avec un agrégateur SMS (Africa's Talking, Orange ou autre) et **faire enregistrer le sender ID** (`SMS_SENDER_ID`) auprès des opérateurs (Orange, MTN, Moov).
- [ ] Ouvrir un compte marchand **CinetPay**, puis passer `PAYMENT_PROVIDER=cinetpay`. Avec `manual`, n'importe quel utilisateur obtient des crédits gratuitement en cliquant sur « Acheter ».
- [ ] Se mettre en conformité avec la **loi n°2013-450** relative à la protection des données à caractère personnel : déclaration ou autorisation auprès de l'**ARTCI**, politique de confidentialité, CGU/CGV, recueil du consentement des destinataires, durée de conservation, droit d'accès et de suppression.
- [ ] Mettre en place les mentions et règles anti-spam : plages horaires d'envoi, mention « STOP » dans les messages.

**Sécurité**
- [ ] **Authentifier les webhooks SMS.** Le callback de paiement CinetPay vérifie la signature HMAC (`X-TOKEN`, avec `CINETPAY_SECRET_KEY`) puis revérifie le statut auprès du fournisseur avant de créditer le compte. En revanche, `/webhooks/sms/delivery-report` et `/webhooks/sms/inbound` ne sont **pas authentifiés** : n'importe qui peut marquer des messages comme livrés ou désabonner des numéros.
- [ ] Ajouter `werkzeug.middleware.proxy_fix.ProxyFix` derrière le reverse proxy. Sans lui, le rate limiting voit l'IP du proxy pour tout le monde, et la `notify_url` envoyée à CinetPay risque d'avoir un mauvais schéma ou un mauvais hôte.
- [ ] Limiter la taille des uploads (`MAX_CONTENT_LENGTH` n'est pas défini) pour l'import CSV.
- [ ] Changer les identifiants PostgreSQL par défaut et ne pas exposer PostgreSQL ni Redis.

**Fonctionnel manquant**
- [ ] **Vérification de l'adresse email et réinitialisation du mot de passe** : pas implémentées. Aucun envoi d'email n'existe.
- [ ] **Back-office d'administration** : pas implémenté. Il manque la gestion des packs, des entreprises, des remboursements et du support.
- [ ] Gestion des utilisateurs `staff` : le rôle existe dans le modèle, mais aucun écran ne permet d'inviter un collaborateur.
- [ ] Écran de gestion des clés d'API : aujourd'hui, les clés ne se gèrent que par les endpoints `/api/v1/api-keys`.
- [ ] Facturation des messages accentués : le nombre de segments est calculé en GSM-7 (160 ou 153 caractères). Or un message contenant un seul caractère hors alphabet GSM-7 (ê, â, ç, î, ô, û, ë, ï, apostrophe typographique…) est envoyé en UCS-2, soit 70 ou 67 caractères par segment. Le coût réel facturé par l'agrégateur peut donc dépasser les crédits débités.
- [ ] Accusés de livraison : seul le format d'Africa's Talking (`id`, `status`) est géré. Ceux de Twilio (`MessageSid`, `MessageStatus`) et d'Orange ne sont pas interprétés.

**Exploitation**
- [ ] **Sauvegardes PostgreSQL** automatisées (volume `baoryx_db_data`), avec rétention et test de restauration.
- [ ] **Monitoring et logs** : il n'y a pour l'instant que les logs stdout de Gunicorn et Celery. Prévoir une centralisation des logs, un suivi des erreurs (Sentry par exemple), des métriques et des alertes sur les files Celery et sur les échecs d'envoi.
- [ ] **Tests de charge** : envoi de campagnes de plusieurs milliers de destinataires (l'envoi est séquentiel, un appel HTTP par SMS) et débit maximal autorisé par l'agrégateur.
- [ ] Recette de bout en bout avec de vrais numéros ivoiriens (Orange, MTN, Moov) et de vrais paiements Mobile Money en environnement de test CinetPay.

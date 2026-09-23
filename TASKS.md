# TASKS — Baoryx Connect

Liste de suivi du backend et du tableau de bord client. Chaque ligne est
cochée quand le travail est terminé **et** testé. Toute nouvelle anomalie
trouvée est ajoutée ici, avec sa source.

Légende des priorités :
- **P0** : empêche un vrai client d'utiliser l'application.
- **P1** : attendu d'un MVP propre pour un client.
- **P2** : amélioration, ou reporté volontairement.

---

## Déjà fait (PR #1)

- [x] Architecture `app/` : factory, blueprints, SQLAlchemy, migrations Alembic
- [x] Multi-entreprise (`Business`), registre de crédits (`CreditTransaction`)
- [x] Fournisseurs SMS interchangeables (console, Africa's Talking, Orange, Twilio)
- [x] Envoi asynchrone Celery : reprise sans double envoi, remboursement en cas d'échec final
- [x] API REST v1 (JWT et clé API), webhooks de livraison, STOP et paiement
- [x] Docker Compose : web, worker, beat, PostgreSQL, Redis
- [x] Suite de tests (85 tests), vérifiée aussi sur PostgreSQL
- [x] README en français
- [x] Fusion de `main` : l'ancien prototype est retiré, ses fonctions sont reprises ci-dessous

---

## P0 — Bloquants constatés en test réel

Test de bout en bout du 23/09/2026 : profil `production`, PostgreSQL, Redis,
Gunicorn, worker et beat Celery, navigateur Chromium.

- [x] **Connexion impossible en HTTP.** Si l'application est ouverte par
  `http://IP:8000` (tout test sans certificat), le cookie de session
  `Secure` n'est jamais renvoyé par le navigateur. La vérification CSRF
  échoue alors et l'inscription comme la connexion réaffichent le
  formulaire **sans aucun message**. C'est très probablement le blocage
  constaté avec le premier client.
  - [x] Afficher une erreur explicite quand le jeton CSRF ou la session manque
  - [x] Détecter la configuration incohérente (cookie `Secure` servi en HTTP) et l'expliquer
  - [x] Ajouter `ProxyFix` pour fonctionner derrière un reverse proxy HTTPS
  - [x] Ajouter un reverse proxy HTTPS automatique (Caddy) dans `docker-compose.yml`
- [x] **Erreurs de formulaire invisibles.** Les templates n'affichent jamais
  les erreurs WTForms : confirmation de mot de passe différente, email
  invalide, champ trop long… Le formulaire revient sans explication.
- [x] **Aucun pack de crédits en production.** Les packs ne sont créés que par
  `flask seed-demo`, qui crée aussi un compte `demo` au mot de passe public.
  Il faut une commande séparée `flask seed-packages`, et un message clair sur
  la page Crédits quand aucun pack n'existe.
- [x] **Paiement `manual` : crédits gratuits.** Tout clic sur « Acheter » crédite
  le compte immédiatement. En attendant l'API Mobile Money, il faut que la
  demande reste en attente et qu'un administrateur la valide
  (`flask payments list` / `flask payments approve <id>`), après réception
  du paiement hors plateforme.
- [x] **Facturation des messages accentués.** Un seul caractère hors
  GSM-7 (ç, â, ê, î, ô, û, ë, ï, ’, emoji…) fait passer le SMS en UCS-2 :
  70 caractères, ou 67 par segment au-delà. Aujourd'hui, ces messages sont
  facturés comme du GSM-7, donc moins que ce que l'agrégateur facture.
- [x] **Mot de passe oublié : aucune récupération possible.** Il n'y a pas
  d'envoi d'email. Pour le MVP : une commande `flask reset-password`.
  La récupération par email vient plus tard (P2).

## P1 — Backend client et tableau de bord

### Contacts
- [x] Modifier un contact (nom, numéro, email, groupes, consentement)
- [x] Ajouter ou retirer des contacts existants d'un groupe
- [x] Rechercher et filtrer les contacts (nom, numéro, groupe, statut)
- [x] Consentement marketing : case dans le formulaire, colonne `consent` à
  l'import CSV, affichage et date *(repris de `main`)*
- [x] Opérateur détecté automatiquement (Orange 07, MTN 05, Moov 01 sur le plan
  à 10 chiffres) et affiché *(repris de `main`, préfixes mis à jour)*
- [x] Réabonner un contact désabonné, uniquement sur action explicite
- [x] Exporter les contacts en CSV

### Modèles de messages *(repris de `main`)*
- [x] Créer, modifier et supprimer des modèles (promotionnel, transactionnel, informatif)
- [x] Choisir un modèle dans le formulaire de campagne

### Campagnes
- [x] Aperçu avant envoi : nombre de destinataires, segments, encodage, coût,
  solde après envoi *(repris de `main` : écran de confirmation)*
- [x] Refuser une campagne sans destinataire
- [x] Option « contacts ayant donné leur consentement uniquement »
- [x] Détail de campagne : liste des messages (numéro, statut, erreur)
- [x] Libellés de statut en français
- [x] Personnalisation `{prenom}` / `{nom}` dans le message

### Tableau de bord et statistiques
- [ ] SMS envoyés ce mois-ci et crédits consommés ce mois-ci
- [ ] Activité des 30 derniers jours (envois par jour)
- [ ] Répartition des contacts et des envois par opérateur *(repris de `main`)*
- [ ] Taux de livraison affiché seulement quand des accusés de livraison existent
- [ ] Seuil d'alerte de solde faible configurable

### Compte
- [ ] Page « Mon compte » : entreprise (nom, secteur, ville, téléphone) et utilisateur
- [ ] Lien vers le changement de mot de passe dans la navigation
- [ ] Écran de gestion des clés API (créer, voir le préfixe, révoquer)
- [x] Types de transaction en français sur la page Crédits

### Intégrité des données
- [x] Crédits offerts à l'inscription (et par `create-admin` / `seed-demo`)
  écrits dans le journal `CreditTransaction`, pas seulement dans le solde
- [x] `seed-demo` : créer quelques contacts comme l'indique sa docstring

### Nouveautés découvertes en cours de route
- [x] `seed-demo` refusé en production (compte `demo` au mot de passe public)
- [x] Commandes d'administration : `flask businesses list`, `flask credits add`
- [x] Le client peut annuler une demande d'achat manuelle non payée
- [x] La réconciliation des paiements ignorait le fournisseur : elle aurait
  interrogé CinetPay pour des paiements `manual` après un changement de
  fournisseur. Elle ne traite plus que les paiements du fournisseur actif.
- [x] Compteur de caractères du formulaire de campagne aligné sur le calcul
  serveur (GSM-7/UCS-2) et signalant les caractères qui coûtent cher
- [x] **Trois formulaires cassés en production** : supprimer un contact, un
  groupe ou une campagne envoyait un POST sans jeton CSRF (erreur 400). Les
  tests ne le voyaient pas car ils désactivent CSRF. Un test vérifie
  désormais que chaque formulaire POST de l'application porte un jeton.
- [x] **Lignes fixes (27, 25, 21)** : numéros valides mais qui ne reçoivent pas
  de SMS. Ils sont marqués « Fixe » et exclus des campagnes (crédits gaspillés sinon).
- [x] **Brouillons envoyables gratuitement** : le worker acceptait d'envoyer une
  campagne en brouillon, sans crédits réservés. Seules les campagnes
  confirmées (planifiées) sont envoyées.
- [x] **Destinataires ajoutés après la confirmation envoyés sans être facturés** :
  la liste est désormais figée à la confirmation (un SMS « en attente » par
  destinataire, texte personnalisé et coût exact). Un contact qui envoie STOP
  entre-temps est retiré à l'envoi et ses crédits sont rendus.
- [x] API `POST /campaigns` : une date `scheduled_at` invalide était vérifiée après
  la réservation des crédits ; validation désormais faite avant toute écriture.
- [x] Annuler une campagne planifiée (crédits rendus) et dupliquer une campagne
- [x] Import CSV : séparateur point-virgule (Excel en français) détecté automatiquement

## P1 — Sécurité et exploitation

- [ ] Authentifier les webhooks SMS (jeton secret dans l'URL de callback)
- [ ] Limiter la taille des uploads (`MAX_CONTENT_LENGTH`) pour l'import CSV
- [x] `RATELIMIT_STORAGE_URI` sur Redis dans `docker-compose.yml`
- [x] Identifiants PostgreSQL lus depuis `.env` au lieu d'être écrits en dur dans `docker-compose.yml`
- [x] Profil production : refuser les `SECRET_KEY` d'exemple de `.env.example`

## P2 — Reporté ou plus tard

- [ ] Paiement Mobile Money réel (CinetPay en production) — *reporté à la demande*
- [ ] Récupération du mot de passe et vérification de l'email par courriel
- [ ] Back-office d'administration web (entreprises, paiements, support)
- [ ] Comptes collaborateurs (`staff`) : invitation et droits
- [ ] Accusés de livraison Twilio (`MessageSid`/`MessageStatus`) et Orange
- [ ] Envoi par lots pour les grosses campagnes (aujourd'hui un appel HTTP par SMS, sauf Africa's Talking)
- [ ] Monitoring (Sentry), sauvegardes PostgreSQL, tests de charge
- [ ] Conformité ARTCI (loi n°2013-450) : déclaration, CGU, politique de confidentialité
- [ ] `scripts/migrate_legacy_data.py` : vérifier la compatibilité avec le
  schéma de l'ancien prototype tel que modifié par le commit 8dd0892 de `main`
  (tables `contacts`, `message_templates`, `user_balances`)

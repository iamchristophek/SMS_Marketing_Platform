# SMS Marketing Platform - Côte d'Ivoire 🇨🇮

## Vue d'ensemble

Cette plateforme de marketing SMS est spécialement conçue pour le marché ivoirien, avec support pour les trois principaux opérateurs télécoms : Orange, MTN et Moov.

## Fonctionnalités Spécifiques au Marché Ivoirien

### 🏢 Opérateurs Supportés
- **Orange Côte d'Ivoire** : 25 FCFA/SMS
- **MTN Côte d'Ivoire** : 30 FCFA/SMS  
- **Moov Côte d'Ivoire** : 20 FCFA/SMS

### 📱 Gestion des Numéros
- Format automatique : +225 XX XX XX XX
- Détection automatique de l'opérateur
- Support des formats locaux (0X XX XX XX)

### 💰 Système de Tarification
- Devise : Franc CFA (FCFA)
- Tarification par opérateur
- Gestion des soldes utilisateurs
- Historique des transactions

### 🔒 Conformité Réglementaire
- Gestion du consentement obligatoire
- Système de désabonnement (STOP)
- Limites de messages par jour
- Logs d'audit complets

## Installation et Configuration

### Prérequis
```bash
pip install -r requirements.txt
```

### Configuration des Variables d'Environnement
```bash
cp config.env.example .env
```

Éditez le fichier `.env` avec vos clés API :
```env
ORANGE_API_KEY=votre_cle_orange
MTN_API_KEY=votre_cle_mtn
MOOV_API_KEY=votre_cle_moov
```

### Initialisation de la Base de Données
```bash
python init_db.py
```

### Lancement de l'Application
```bash
python app.py
```

## API des Opérateurs

### Orange Côte d'Ivoire
- **Endpoint** : https://api.orange.com/smsmessaging/v1/outbound
- **Coût** : 25 FCFA/SMS
- **Documentation** : https://developer.orange.com

### MTN Côte d'Ivoire
- **Endpoint** : https://api.mtn.ci/sms/v1/send
- **Coût** : 30 FCFA/SMS
- **Documentation** : https://developer.mtn.ci

### Moov Côte d'Ivoire
- **Endpoint** : https://api.moov.ci/sms/send
- **Coût** : 20 FCFA/SMS
- **Documentation** : https://developer.moov.ci

## Fonctionnalités Avancées

### 📊 Analytics Spécifiques
- Répartition par opérateur
- Coûts par opérateur
- Recommandations d'optimisation
- Métriques de performance

### 🎯 Gestion des Contacts
- Import CSV avec détection d'opérateur
- Gestion des groupes de contacts
- Suivi du consentement
- Système de désabonnement

### 📝 Templates de Messages
- Templates prédéfinis pour différents secteurs
- Personnalisation par opérateur
- Gestion des caractères spéciaux

### 💳 Système de Paiement
- Rechargement par Mobile Money
- Virements bancaires
- Paiement en espèces
- Suivi des transactions

## Déploiement en Production

### Serveur Recommandé
- **OS** : Ubuntu 20.04 LTS
- **RAM** : 4GB minimum
- **Stockage** : 50GB SSD
- **CPU** : 2 vCPU

### Configuration Nginx
```nginx
server {
    listen 80;
    server_name votre-domaine.ci;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Configuration SSL
```bash
sudo certbot --nginx -d votre-domaine.ci
```

## Sécurité et Conformité

### 🔐 Chiffrement
- Chiffrement des numéros de téléphone
- Hashage des mots de passe
- Sessions sécurisées

### 📋 Audit
- Logs de toutes les activités
- Traçabilité des envois
- Rapports de conformité

### 🛡️ Protection des Données
- Conformité RGPD local
- Gestion du consentement
- Droit à l'oubli

## Support et Maintenance

### 📞 Support Technique
- **Téléphone** : +225 XX XX XX XX
- **Email** : support@smsmarketing.ci
- **Horaires** : 8h-18h (GMT+0)

### 🔧 Maintenance
- Sauvegarde quotidienne
- Mise à jour des tarifs
- Monitoring 24/7

## Roadmap

### Phase 1 (Actuelle)
- ✅ Support Orange, MTN, Moov
- ✅ Interface en français
- ✅ Gestion des consentements
- ✅ Analytics de base

### Phase 2 (Q2 2024)
- 🔄 Intégration Mobile Money
- 🔄 API REST complète
- 🔄 Webhooks avancés
- 🔄 Multi-tenant

### Phase 3 (Q3 2024)
- 📋 Expansion Ghana
- 📋 Expansion Kenya
- 📋 IA pour optimisation
- 📋 Intégration WhatsApp

## Contribution

### Développement Local
```bash
git clone https://github.com/votre-repo/sms-marketing-ci.git
cd sms-marketing-ci
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Tests
```bash
python -m pytest tests/
```

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## Contact

- **Développeur Principal** : Votre Nom
- **Email** : dev@smsmarketing.ci
- **LinkedIn** : https://linkedin.com/in/votre-profil

---

**Fait avec ❤️ pour le marché africain**

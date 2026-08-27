"""
Configuration spécifique pour le marché ivoirien
"""

# Configuration des devises et tarifs
CURRENCY = "FCFA"  # Franc CFA de l'Afrique de l'Ouest
CURRENCY_SYMBOL = "F"

# Tarifs SMS par opérateur (en FCFA)
SMS_PRICING = {
    'orange': {
        'domestic': 25,  # SMS national
        'international': 50,  # SMS international
        'premium': 100  # SMS premium
    },
    'mtn': {
        'domestic': 30,
        'international': 60,
        'premium': 120
    },
    'moov': {
        'domestic': 20,
        'international': 40,
        'premium': 80
    }
}

# Préfixes des opérateurs en Côte d'Ivoire
OPERATOR_PREFIXES = {
    'orange': ['07', '08', '09'],
    'mtn': ['05', '06'],
    'moov': ['01', '02', '03', '04']
}

# Configuration des fuseaux horaires
TIMEZONE = "Africa/Abidjan"
TIME_FORMAT = "%d/%m/%Y %H:%M"

# Langues supportées
SUPPORTED_LANGUAGES = {
    'fr': 'Français',
    'en': 'English',
    'ba': 'Bambara'
}

# Messages par défaut en français
DEFAULT_MESSAGES = {
    'welcome': "Bienvenue sur notre plateforme de marketing SMS !",
    'campaign_created': "Votre campagne SMS a été créée avec succès.",
    'sms_sent': "SMS envoyé avec succès.",
    'error_generic': "Une erreur s'est produite. Veuillez réessayer.",
    'insufficient_balance': "Solde insuffisant pour envoyer ce SMS.",
    'invalid_number': "Numéro de téléphone invalide.",
    'consent_required': "Le consentement du destinataire est requis."
}

# Configuration des réglementations
REGULATORY_CONFIG = {
    'consent_required': True,  # Consentement obligatoire
    'opt_out_keyword': 'STOP',  # Mot-clé pour se désabonner
    'max_messages_per_day': 10,  # Limite de messages par jour par destinataire
    'business_hours_only': False,  # Envoi uniquement pendant les heures ouvrables
    'business_hours': {
        'start': '08:00',
        'end': '18:00',
        'timezone': 'Africa/Abidjan'
    }
}

# Configuration des templates de messages
MESSAGE_TEMPLATES = {
    'promotional': {
        'name': 'Promotionnel',
        'description': 'Messages promotionnels et publicitaires',
        'max_length': 160,
        'consent_required': True
    },
    'transactional': {
        'name': 'Transactionnel',
        'description': 'Messages de confirmation, factures, etc.',
        'max_length': 160,
        'consent_required': False
    },
    'informational': {
        'name': 'Informatif',
        'description': 'Messages informatifs et notifications',
        'max_length': 160,
        'consent_required': True
    }
}

# Configuration des analytics spécifiques au marché africain
ANALYTICS_CONFIG = {
    'track_delivery_rates': True,
    'track_open_rates': True,
    'track_click_rates': False,  # Pas applicable aux SMS
    'track_opt_out_rates': True,
    'track_cost_per_message': True,
    'track_roi': True
}

# Configuration des notifications
NOTIFICATION_CONFIG = {
    'email_notifications': True,
    'sms_notifications': True,
    'low_balance_threshold': 1000,  # Seuil d'alerte de solde bas (en FCFA)
    'daily_report': True,
    'weekly_report': True,
    'monthly_report': True
}

# Configuration de l'interface utilisateur
UI_CONFIG = {
    'default_language': 'fr',
    'date_format': '%d/%m/%Y',
    'time_format': '%H:%M',
    'currency_display': 'FCFA',
    'phone_format': '+225 XX XX XX XX',
    'theme': 'african'  # Thème visuel adapté au marché africain
}

# Configuration des limites
LIMITS_CONFIG = {
    'max_contacts_per_user': 10000,
    'max_campaigns_per_user': 100,
    'max_messages_per_campaign': 1000,
    'max_scheduled_campaigns': 50,
    'daily_sms_limit': 10000
}

# Configuration des opérateurs partenaires
PARTNER_OPERATORS = {
    'orange': {
        'name': 'Orange Côte d\'Ivoire',
        'api_endpoint': 'https://api.orange.com',
        'support_phone': '+225 20 30 40 50',
        'support_email': 'support@orange.ci'
    },
    'mtn': {
        'name': 'MTN Côte d\'Ivoire',
        'api_endpoint': 'https://api.mtn.ci',
        'support_phone': '+225 20 30 40 60',
        'support_email': 'support@mtn.ci'
    },
    'moov': {
        'name': 'Moov Côte d\'Ivoire',
        'api_endpoint': 'https://api.moov.ci',
        'support_phone': '+225 20 30 40 70',
        'support_email': 'support@moov.ci'
    }
}

# Configuration des webhooks
WEBHOOK_CONFIG = {
    'delivery_reports': True,
    'opt_out_notifications': True,
    'balance_alerts': True,
    'campaign_completion': True
}

# Configuration de la sécurité
SECURITY_CONFIG = {
    'encrypt_phone_numbers': True,
    'log_all_activities': True,
    'ip_whitelist': False,
    'two_factor_auth': False,  # À implémenter plus tard
    'session_timeout': 3600  # 1 heure en secondes
}

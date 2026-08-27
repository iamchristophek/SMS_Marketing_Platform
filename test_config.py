"""
Configuration pour les tests de la plateforme SMS Marketing - Côte d'Ivoire
"""

import os
import tempfile
import shutil

class TestConfig:
    """Configuration pour les tests"""
    
    # Base de données de test
    TEST_DATABASE = 'test_sms_marketing.db'
    
    # Clés API de test (factices)
    TEST_API_KEYS = {
        'ORANGE_API_KEY': 'test_orange_key_12345',
        'MTN_API_KEY': 'test_mtn_key_67890',
        'MOOV_API_KEY': 'test_moov_key_abcdef'
    }
    
    # Numéros de test ivoiriens
    TEST_PHONE_NUMBERS = {
        'orange': ['071234567', '081234567', '091234567'],
        'mtn': ['051234567', '061234567'],
        'moov': ['011234567', '021234567', '031234567', '041234567']
    }
    
    # Messages de test
    TEST_MESSAGES = {
        'promotional': "🎉 Nouvelle promotion ! Réduction de 20% sur tous nos produits. Valable jusqu'au 31/12/2024. Code: PROMO20",
        'transactional': "Votre commande #12345 a été confirmée. Livraison prévue le 15/01/2024. Merci pour votre confiance !",
        'informational': "Rappel: Votre rendez-vous médical est prévu demain à 14h00. Dr. Kouassi - Clinique du Plateau"
    }
    
    # Données de test pour les utilisateurs
    TEST_USERS = [
        {
            'username': 'test_user_1',
            'email': 'test1@example.ci',
            'password': 'test_password_123'
        },
        {
            'username': 'test_user_2', 
            'email': 'test2@example.ci',
            'password': 'test_password_456'
        }
    ]
    
    # Contacts de test
    TEST_CONTACTS = [
        {
            'name': 'Jean Kouassi',
            'phone': '071234567',
            'email': 'jean.kouassi@example.ci',
            'operator': 'orange'
        },
        {
            'name': 'Marie Traoré',
            'phone': '051234567', 
            'email': 'marie.traore@example.ci',
            'operator': 'mtn'
        },
        {
            'name': 'Paul Diabaté',
            'phone': '011234567',
            'email': 'paul.diabate@example.ci', 
            'operator': 'moov'
        }
    ]
    
    # Campagnes de test
    TEST_CAMPAIGNS = [
        {
            'name': 'Promotion Noël 2024',
            'message': '🎄 Joyeux Noël ! Profitez de nos offres spéciales jusqu\'au 25 décembre. Visitez nos magasins !',
            'scheduled_date': '2024-12-20 10:00:00'
        },
        {
            'name': 'Rappel Paiement',
            'message': 'Rappel: Votre facture du mois de décembre est due. Paiement en ligne disponible.',
            'scheduled_date': '2024-12-15 09:00:00'
        }
    ]
    
    @classmethod
    def setup_test_environment(cls):
        """Configure l'environnement de test"""
        # Définir les variables d'environnement de test
        for key, value in cls.TEST_API_KEYS.items():
            os.environ[key] = value
        
        # Créer un répertoire temporaire pour les tests
        cls.test_dir = tempfile.mkdtemp(prefix='sms_marketing_test_')
        
        return cls.test_dir
    
    @classmethod
    def cleanup_test_environment(cls):
        """Nettoie l'environnement de test"""
        # Supprimer la base de données de test si elle existe
        if os.path.exists(cls.TEST_DATABASE):
            os.remove(cls.TEST_DATABASE)
        
        # Supprimer le répertoire temporaire
        if hasattr(cls, 'test_dir') and os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir)
        
        # Nettoyer les variables d'environnement de test
        for key in cls.TEST_API_KEYS.keys():
            if key in os.environ:
                del os.environ[key]

# Configuration des tests unitaires
class UnitTestConfig(TestConfig):
    """Configuration pour les tests unitaires"""
    
    # Désactiver les appels API réels
    MOCK_API_CALLS = True
    
    # Réponses simulées des API
    MOCK_API_RESPONSES = {
        'orange': {
            'success': True,
            'message_id': 'orange_msg_12345',
            'cost': 25,
            'provider': 'Orange'
        },
        'mtn': {
            'success': True,
            'message_id': 'mtn_msg_67890',
            'cost': 30,
            'provider': 'MTN'
        },
        'moov': {
            'success': True,
            'message_id': 'moov_msg_abcdef',
            'cost': 20,
            'provider': 'Moov'
        }
    }

# Configuration des tests d'intégration
class IntegrationTestConfig(TestConfig):
    """Configuration pour les tests d'intégration"""
    
    # Utiliser de vraies clés API (en mode test)
    USE_REAL_API_KEYS = False
    
    # Endpoints de test des opérateurs
    TEST_ENDPOINTS = {
        'orange': 'https://api.orange.com/test/smsmessaging/v1/outbound',
        'mtn': 'https://api.mtn.ci/test/sms/v1/send',
        'moov': 'https://api.moov.ci/test/sms/send'
    }

# Configuration des tests de performance
class PerformanceTestConfig(TestConfig):
    """Configuration pour les tests de performance"""
    
    # Nombre de messages pour les tests de charge
    LOAD_TEST_MESSAGE_COUNT = 1000
    
    # Délai entre les envois (en secondes)
    MESSAGE_DELAY = 0.1
    
    # Timeout pour les requêtes (en secondes)
    REQUEST_TIMEOUT = 30

# Configuration des tests de sécurité
class SecurityTestConfig(TestConfig):
    """Configuration pour les tests de sécurité"""
    
    # Données sensibles pour les tests
    SENSITIVE_DATA = {
        'phone_numbers': ['071234567', '051234567', '011234567'],
        'emails': ['test@example.ci', 'user@domain.ci'],
        'passwords': ['password123', 'secret456']
    }
    
    # Tests de chiffrement
    ENCRYPTION_TESTS = True
    
    # Tests de validation des entrées
    INPUT_VALIDATION_TESTS = True

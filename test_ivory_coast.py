#!/usr/bin/env python3
"""
Tests pour la plateforme SMS Marketing - Côte d'Ivoire
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Ajouter le répertoire courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestSMSMarketingPlatform(unittest.TestCase):
    """Tests pour la classe SMSMarketingPlatform"""
    
    def setUp(self):
        """Configuration des tests"""
        # Mock de la base de données pour les tests
        with patch('sms_platform.sqlite3.connect'):
            from sms_platform import SMSMarketingPlatform
            self.platform = SMSMarketingPlatform()
    
    def test_detect_operator_orange(self):
        """Test de détection de l'opérateur Orange"""
        # Numéros Orange en Côte d'Ivoire
        orange_numbers = ['071234567', '081234567', '091234567', '+225071234567']
        
        for number in orange_numbers:
            with self.subTest(number=number):
                operator = self.platform._detect_operator(number)
                self.assertEqual(operator, 'orange')
    
    def test_detect_operator_mtn(self):
        """Test de détection de l'opérateur MTN"""
        # Numéros MTN en Côte d'Ivoire
        mtn_numbers = ['051234567', '061234567', '+225051234567']
        
        for number in mtn_numbers:
            with self.subTest(number=number):
                operator = self.platform._detect_operator(number)
                self.assertEqual(operator, 'mtn')
    
    def test_detect_operator_moov(self):
        """Test de détection de l'opérateur Moov"""
        # Numéros Moov en Côte d'Ivoire
        moov_numbers = ['011234567', '021234567', '031234567', '041234567', '+225011234567']
        
        for number in moov_numbers:
            with self.subTest(number=number):
                operator = self.platform._detect_operator(number)
                self.assertEqual(operator, 'moov')
    
    def test_detect_operator_unknown(self):
        """Test de détection d'opérateur inconnu"""
        unknown_numbers = ['123456789', '999999999', 'invalid']
        
        for number in unknown_numbers:
            with self.subTest(number=number):
                operator = self.platform._detect_operator(number)
                self.assertEqual(operator, 'unknown')

class TestSMSProviders(unittest.TestCase):
    """Tests pour les fournisseurs SMS"""
    
    def test_orange_sms_format(self):
        """Test du formatage des numéros pour Orange"""
        from sms_providers import OrangeSMS
        
        orange = OrangeSMS("test_key")
        
        # Test de formatage
        test_cases = [
            ('071234567', '+225071234567'),
            ('+225071234567', '+225071234567'),
            ('071234567', '+225071234567'),
            ('225071234567', '+225071234567')
        ]
        
        for input_number, expected in test_cases:
            with self.subTest(input=input_number):
                result = orange._format_phone_number(input_number)
                self.assertEqual(result, expected)
    
    def test_mtn_sms_format(self):
        """Test du formatage des numéros pour MTN"""
        from sms_providers import MTNSMS
        
        mtn = MTNSMS("test_key")
        
        # Test de formatage
        test_cases = [
            ('051234567', '+225051234567'),
            ('+225051234567', '+225051234567'),
            ('051234567', '+225051234567')
        ]
        
        for input_number, expected in test_cases:
            with self.subTest(input=input_number):
                result = mtn._format_phone_number(input_number)
                self.assertEqual(result, expected)
    
    def test_moov_sms_format(self):
        """Test du formatage des numéros pour Moov"""
        from sms_providers import MoovSMS
        
        moov = MoovSMS("test_key")
        
        # Test de formatage
        test_cases = [
            ('011234567', '+225011234567'),
            ('+225011234567', '+225011234567'),
            ('011234567', '+225011234567')
        ]
        
        for input_number, expected in test_cases:
            with self.subTest(input=input_number):
                result = moov._format_phone_number(input_number)
                self.assertEqual(result, expected)

class TestConfiguration(unittest.TestCase):
    """Tests pour la configuration ivoirienne"""
    
    def test_currency_config(self):
        """Test de la configuration des devises"""
        from config_ivory_coast import CURRENCY, CURRENCY_SYMBOL
        
        self.assertEqual(CURRENCY, "FCFA")
        self.assertEqual(CURRENCY_SYMBOL, "F")
    
    def test_sms_pricing(self):
        """Test des tarifs SMS"""
        from config_ivory_coast import SMS_PRICING
        
        # Vérifier que tous les opérateurs ont des tarifs
        self.assertIn('orange', SMS_PRICING)
        self.assertIn('mtn', SMS_PRICING)
        self.assertIn('moov', SMS_PRICING)
        
        # Vérifier les tarifs
        self.assertEqual(SMS_PRICING['orange']['domestic'], 25)
        self.assertEqual(SMS_PRICING['mtn']['domestic'], 30)
        self.assertEqual(SMS_PRICING['moov']['domestic'], 20)
    
    def test_operator_prefixes(self):
        """Test des préfixes des opérateurs"""
        from config_ivory_coast import OPERATOR_PREFIXES
        
        # Vérifier les préfixes Orange
        self.assertIn('07', OPERATOR_PREFIXES['orange'])
        self.assertIn('08', OPERATOR_PREFIXES['orange'])
        self.assertIn('09', OPERATOR_PREFIXES['orange'])
        
        # Vérifier les préfixes MTN
        self.assertIn('05', OPERATOR_PREFIXES['mtn'])
        self.assertIn('06', OPERATOR_PREFIXES['mtn'])
        
        # Vérifier les préfixes Moov
        self.assertIn('01', OPERATOR_PREFIXES['moov'])
        self.assertIn('02', OPERATOR_PREFIXES['moov'])
        self.assertIn('03', OPERATOR_PREFIXES['moov'])
        self.assertIn('04', OPERATOR_PREFIXES['moov'])
    
    def test_regulatory_config(self):
        """Test de la configuration réglementaire"""
        from config_ivory_coast import REGULATORY_CONFIG
        
        # Vérifier les paramètres de conformité
        self.assertTrue(REGULATORY_CONFIG['consent_required'])
        self.assertEqual(REGULATORY_CONFIG['opt_out_keyword'], 'STOP')
        self.assertEqual(REGULATORY_CONFIG['max_messages_per_day'], 10)

class TestSMSManager(unittest.TestCase):
    """Tests pour le gestionnaire SMS"""
    
    def test_create_ivory_coast_manager(self):
        """Test de création du gestionnaire SMS pour la Côte d'Ivoire"""
        from sms_providers import create_ivory_coast_sms_manager
        
        # Test avec clés API factices
        manager = create_ivory_coast_sms_manager(
            orange_api_key="test_orange",
            mtn_api_key="test_mtn",
            moov_api_key="test_moov"
        )
        
        self.assertIsNotNone(manager)
        self.assertIn('orange', manager.providers)
        self.assertIn('mtn', manager.providers)
        self.assertIn('moov', manager.providers)
    
    def test_get_optimal_provider(self):
        """Test de sélection du fournisseur optimal"""
        from sms_providers import SMSManager
        
        manager = SMSManager()
        
        # Test avec numéros Orange
        orange_provider = manager.get_optimal_provider('071234567')
        self.assertEqual(orange_provider, 'orange')
        
        # Test avec numéros MTN
        mtn_provider = manager.get_optimal_provider('051234567')
        self.assertEqual(mtn_provider, 'mtn')
        
        # Test avec numéros Moov
        moov_provider = manager.get_optimal_provider('011234567')
        self.assertEqual(moov_provider, 'moov')

def run_tests():
    """Lance tous les tests"""
    print("Lancement des tests pour SMS Marketing Platform - Cote d'Ivoire")
    print("=" * 70)
    
    # Créer la suite de tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Ajouter tous les tests
    suite.addTests(loader.loadTestsFromTestCase(TestSMSMarketingPlatform))
    suite.addTests(loader.loadTestsFromTestCase(TestSMSProviders))
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestSMSManager))
    
    # Lancer les tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Afficher le résumé
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("Tous les tests sont passes avec succes !")
        return True
    else:
        print(f"{len(result.failures)} test(s) ont echoue, {len(result.errors)} erreur(s)")
        return False

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)

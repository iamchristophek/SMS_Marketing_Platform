#!/usr/bin/env python3
"""
Test des routes de l'application SMS Marketing - Côte d'Ivoire
"""

import requests
import time
import sys
from urllib.parse import urljoin

class RouteTester:
    def __init__(self, base_url="http://127.0.0.1:5000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.results = []
    
    def test_route(self, route, method="GET", data=None, expected_status=200, description=""):
        """Test une route spécifique"""
        url = urljoin(self.base_url, route)
        
        try:
            if method == "GET":
                response = self.session.get(url, timeout=5)
            elif method == "POST":
                response = self.session.post(url, data=data, timeout=5)
            else:
                return False, f"Méthode {method} non supportée"
            
            success = response.status_code == expected_status
            result = {
                'route': route,
                'method': method,
                'status_code': response.status_code,
                'expected_status': expected_status,
                'success': success,
                'description': description,
                'response_size': len(response.content)
            }
            
            self.results.append(result)
            return success, f"Status: {response.status_code}"
            
        except requests.exceptions.ConnectionError:
            result = {
                'route': route,
                'method': method,
                'status_code': 0,
                'expected_status': expected_status,
                'success': False,
                'description': description,
                'error': 'Connection refused - Server not running'
            }
            self.results.append(result)
            return False, "Connection refused - Server not running"
        except Exception as e:
            result = {
                'route': route,
                'method': method,
                'status_code': 0,
                'expected_status': expected_status,
                'success': False,
                'description': description,
                'error': str(e)
            }
            self.results.append(result)
            return False, str(e)
    
    def run_all_tests(self):
        """Lance tous les tests de routes"""
        print("🧪 Test des routes de l'application SMS Marketing - Côte d'Ivoire")
        print("=" * 70)
        
        # Routes publiques
        self.test_route("/", description="Page d'accueil")
        self.test_route("/login", description="Page de connexion")
        self.test_route("/register", description="Page d'inscription")
        
        # Routes protégées (devraient rediriger vers login)
        self.test_route("/dashboard", expected_status=302, description="Tableau de bord (redirection)")
        self.test_route("/contacts", expected_status=302, description="Contacts (redirection)")
        self.test_route("/balance", expected_status=302, description="Solde (redirection)")
        self.test_route("/analytics", expected_status=302, description="Analytics (redirection)")
        self.test_route("/templates", expected_status=302, description="Templates (redirection)")
        self.test_route("/create_campaign", expected_status=302, description="Créer campagne (redirection)")
        self.test_route("/add_contact", expected_status=302, description="Ajouter contact (redirection)")
        self.test_route("/add_balance", expected_status=302, description="Ajouter solde (redirection)")
        self.test_route("/create_template", expected_status=302, description="Créer template (redirection)")
        
        # Test des routes avec paramètres
        self.test_route("/campaign/1", expected_status=302, description="Voir campagne (redirection)")
        self.test_route("/send_campaign/1", expected_status=302, description="Envoyer campagne (redirection)")
        self.test_route("/delete_campaign/1", expected_status=302, description="Supprimer campagne (redirection)")
        self.test_route("/update_consent/1", expected_status=302, description="Mettre à jour consentement (redirection)")
        self.test_route("/opt_out/071234567", expected_status=302, description="Désabonnement (redirection)")
        
        # Test des routes POST
        self.test_route("/login", method="POST", data={
            'username': 'test',
            'password': 'test'
        }, expected_status=200, description="Connexion (POST)")
        
        self.test_route("/register", method="POST", data={
            'username': 'test',
            'email': 'test@example.com',
            'password': 'test',
            'confirm_password': 'test'
        }, expected_status=200, description="Inscription (POST)")
    
    def print_results(self):
        """Affiche les résultats des tests"""
        print("\n📊 Résultats des tests :")
        print("-" * 70)
        
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r['success']])
        failed_tests = total_tests - successful_tests
        
        print(f"Total des tests : {total_tests}")
        print(f"Tests réussis : {successful_tests}")
        print(f"Tests échoués : {failed_tests}")
        print(f"Taux de réussite : {(successful_tests/total_tests)*100:.1f}%")
        
        print("\n📋 Détail des tests :")
        print("-" * 70)
        
        for result in self.results:
            status_icon = "✅" if result['success'] else "❌"
            print(f"{status_icon} {result['method']} {result['route']} - {result['description']}")
            print(f"   Status: {result['status_code']} (attendu: {result['expected_status']})")
            if 'error' in result:
                print(f"   Erreur: {result['error']}")
            print()
        
        return successful_tests == total_tests

def main():
    """Fonction principale"""
    print("🚀 Démarrage des tests de routes...")
    print("⚠️  Assurez-vous que l'application est démarrée sur http://127.0.0.1:5000")
    print()
    
    # Attendre un peu pour que l'utilisateur puisse démarrer l'application
    print("⏳ Attente de 3 secondes...")
    time.sleep(3)
    
    tester = RouteTester()
    tester.run_all_tests()
    success = tester.print_results()
    
    if success:
        print("🎉 Tous les tests de routes sont passés avec succès !")
        print("✅ L'application est fonctionnelle et toutes les pages sont accessibles.")
    else:
        print("❌ Certains tests ont échoué.")
        print("🔧 Vérifiez que l'application est bien démarrée et que tous les templates existent.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Script de lancement pour la plateforme SMS Marketing - Côte d'Ivoire
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def print_banner():
    """Affiche la bannière de l'application"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║    🇨🇮 SMS Marketing Platform - Côte d'Ivoire 🇨🇮            ║
    ║                                                              ║
    ║    Plateforme de marketing SMS adaptée au marché ivoirien    ║
    ║    Support: Orange, MTN, Moov                               ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def check_environment():
    """Vérifie l'environnement de développement"""
    print("🔍 Vérification de l'environnement...")
    
    # Vérifier Python
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ requis")
        return False
    
    # Vérifier les fichiers requis
    required_files = [
        'app.py',
        'sms_platform.py', 
        'sms_providers.py',
        'config_ivory_coast.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ Fichiers manquants : {', '.join(missing_files)}")
        return False
    
    print("✅ Environnement OK")
    return True

def install_dependencies():
    """Installe les dépendances"""
    print("📦 Installation des dépendances...")
    
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ], check=True)
        print("✅ Dépendances installées")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de l'installation des dépendances")
        return False

def setup_database():
    """Initialise la base de données"""
    print("🗄️ Initialisation de la base de données...")
    
    try:
        subprocess.run([sys.executable, "init_db.py"], check=True)
        print("✅ Base de données initialisée")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de l'initialisation de la base de données")
        return False

def run_tests():
    """Lance les tests"""
    print("🧪 Lancement des tests...")
    
    try:
        subprocess.run([sys.executable, "test_ivory_coast.py"], check=True)
        print("✅ Tests passés avec succès")
        return True
    except subprocess.CalledProcessError:
        print("❌ Certains tests ont échoué")
        return False

def run_demo():
    """Lance la démonstration"""
    print("🎬 Lancement de la démonstration...")
    
    try:
        subprocess.run([sys.executable, "demo_ivory_coast.py"], check=True)
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de la démonstration")
        return False

def start_application(debug=True, host='127.0.0.1', port=5000):
    """Démarre l'application"""
    print(f"🚀 Démarrage de l'application sur {host}:{port}")
    print("   Mode debug:", "activé" if debug else "désactivé")
    print("   URL: http://{}:{}".format(host, port))
    print("\n   Appuyez sur Ctrl+C pour arrêter l'application")
    print("-" * 60)
    
    # Définir les variables d'environnement
    os.environ['FLASK_APP'] = 'app.py'
    os.environ['FLASK_ENV'] = 'development' if debug else 'production'
    
    try:
        # Importer et lancer l'application
        from app import app
        app.run(debug=debug, host=host, port=port)
    except KeyboardInterrupt:
        print("\n👋 Arrêt de l'application")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage : {e}")
        return False
    
    return True

def show_help():
    """Affiche l'aide"""
    help_text = """
🇨🇮 SMS Marketing Platform - Côte d'Ivoire

Commandes disponibles :

  python run_ivory_coast.py [options]

Options :
  --help, -h          Affiche cette aide
  --install, -i       Installe les dépendances
  --setup, -s         Configure l'environnement complet
  --test, -t          Lance les tests
  --demo, -d          Lance la démonstration
  --start             Démarre l'application
  --host HOST         Adresse IP (défaut: 127.0.0.1)
  --port PORT         Port (défaut: 5000)
  --no-debug          Désactive le mode debug

Exemples :
  python run_ivory_coast.py --setup
  python run_ivory_coast.py --start
  python run_ivory_coast.py --start --host 0.0.0.0 --port 8080
  python run_ivory_coast.py --demo
    """
    print(help_text)

def main():
    """Fonction principale"""
    parser = argparse.ArgumentParser(description='SMS Marketing Platform - Côte d\'Ivoire')
    parser.add_argument('--install', '-i', action='store_true', help='Installe les dépendances')
    parser.add_argument('--setup', '-s', action='store_true', help='Configure l\'environnement complet')
    parser.add_argument('--test', '-t', action='store_true', help='Lance les tests')
    parser.add_argument('--demo', '-d', action='store_true', help='Lance la démonstration')
    parser.add_argument('--start', action='store_true', help='Démarre l\'application')
    parser.add_argument('--host', default='127.0.0.1', help='Adresse IP (défaut: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5000, help='Port (défaut: 5000)')
    parser.add_argument('--no-debug', action='store_true', help='Désactive le mode debug')
    
    args = parser.parse_args()
    
    # Afficher la bannière
    print_banner()
    
    # Si aucune option n'est spécifiée, afficher l'aide
    if not any([args.install, args.setup, args.test, args.demo, args.start]):
        show_help()
        return
    
    # Vérifier l'environnement
    if not check_environment():
        return
    
    # Installer les dépendances
    if args.install or args.setup:
        if not install_dependencies():
            return
    
    # Configurer la base de données
    if args.setup:
        if not setup_database():
            return
    
    # Lancer les tests
    if args.test:
        if not run_tests():
            return
    
    # Lancer la démonstration
    if args.demo:
        if not run_demo():
            return
    
    # Démarrer l'application
    if args.start:
        debug = not args.no_debug
        start_application(debug=debug, host=args.host, port=args.port)

if __name__ == "__main__":
    main()

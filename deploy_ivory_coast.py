#!/usr/bin/env python3
"""
Script de déploiement pour la plateforme SMS Marketing en Côte d'Ivoire
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_requirements():
    """Vérifie les prérequis système"""
    print("🔍 Vérification des prérequis...")
    
    # Vérifier Python
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ requis")
        return False
    
    # Vérifier pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], check=True)
    except subprocess.CalledProcessError:
        print("❌ pip non trouvé")
        return False
    
    print("✅ Prérequis OK")
    return True

def install_dependencies():
    """Installe les dépendances"""
    print("📦 Installation des dépendances...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("✅ Dépendances installées")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de l'installation des dépendances")
        return False

def setup_environment():
    """Configure l'environnement"""
    print("⚙️ Configuration de l'environnement...")
    
    # Créer le fichier .env s'il n'existe pas
    if not os.path.exists('.env'):
        if os.path.exists('config.env.example'):
            shutil.copy('config.env.example', '.env')
            print("📝 Fichier .env créé à partir de config.env.example")
            print("⚠️  N'oubliez pas de configurer vos clés API dans .env")
        else:
            print("❌ Fichier config.env.example non trouvé")
            return False
    
    # Créer les dossiers nécessaires
    directories = ['logs', 'backups', 'uploads']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Dossier {directory} créé")
    
    print("✅ Environnement configuré")
    return True

def initialize_database():
    """Initialise la base de données"""
    print("🗄️ Initialisation de la base de données...")
    
    try:
        subprocess.run([sys.executable, "init_db.py"], check=True)
        print("✅ Base de données initialisée")
        return True
    except subprocess.CalledProcessError:
        print("❌ Erreur lors de l'initialisation de la base de données")
        return False

def create_systemd_service():
    """Crée un service systemd pour la production"""
    print("🔧 Création du service systemd...")
    
    service_content = f"""[Unit]
Description=SMS Marketing Platform - Côte d'Ivoire
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={os.getcwd()}
Environment=PATH={os.getcwd()}/venv/bin
ExecStart={os.getcwd()}/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    try:
        with open('/tmp/sms-marketing-ci.service', 'w') as f:
            f.write(service_content)
        
        print("📝 Service systemd créé dans /tmp/sms-marketing-ci.service")
        print("⚠️  Pour l'installer :")
        print("   sudo cp /tmp/sms-marketing-ci.service /etc/systemd/system/")
        print("   sudo systemctl daemon-reload")
        print("   sudo systemctl enable sms-marketing-ci")
        print("   sudo systemctl start sms-marketing-ci")
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du service : {e}")
        return False

def create_nginx_config():
    """Crée la configuration Nginx"""
    print("🌐 Création de la configuration Nginx...")
    
    nginx_config = """
server {
    listen 80;
    server_name votre-domaine.ci;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /path/to/your/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
"""
    
    try:
        with open('/tmp/sms-marketing-ci.nginx', 'w') as f:
            f.write(nginx_config)
        
        print("📝 Configuration Nginx créée dans /tmp/sms-marketing-ci.nginx")
        print("⚠️  Pour l'installer :")
        print("   sudo cp /tmp/sms-marketing-ci.nginx /etc/nginx/sites-available/sms-marketing-ci")
        print("   sudo ln -s /etc/nginx/sites-available/sms-marketing-ci /etc/nginx/sites-enabled/")
        print("   sudo nginx -t")
        print("   sudo systemctl reload nginx")
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création de la config Nginx : {e}")
        return False

def create_backup_script():
    """Crée un script de sauvegarde"""
    print("💾 Création du script de sauvegarde...")
    
    backup_script = f"""#!/bin/bash
# Script de sauvegarde pour SMS Marketing Platform - Côte d'Ivoire

BACKUP_DIR="/var/backups/sms-marketing-ci"
DATE=$(date +%Y%m%d_%H%M%S)
APP_DIR="{os.getcwd()}"

# Créer le dossier de sauvegarde
mkdir -p $BACKUP_DIR

# Sauvegarder la base de données
cp $APP_DIR/sms_marketing.db $BACKUP_DIR/sms_marketing_$DATE.db

# Sauvegarder les logs
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz $APP_DIR/logs/

# Sauvegarder les uploads
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz $APP_DIR/uploads/

# Nettoyer les anciennes sauvegardes (garder 30 jours)
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Sauvegarde terminée : $DATE"
"""
    
    try:
        with open('/tmp/backup_sms_marketing.sh', 'w') as f:
            f.write(backup_script)
        
        os.chmod('/tmp/backup_sms_marketing.sh', 0o755)
        
        print("📝 Script de sauvegarde créé dans /tmp/backup_sms_marketing.sh")
        print("⚠️  Pour l'installer :")
        print("   sudo cp /tmp/backup_sms_marketing.sh /usr/local/bin/")
        print("   sudo crontab -e")
        print("   # Ajouter : 0 2 * * * /usr/local/bin/backup_sms_marketing.sh")
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du script de sauvegarde : {e}")
        return False

def main():
    """Fonction principale de déploiement"""
    print("🚀 Déploiement de SMS Marketing Platform - Côte d'Ivoire")
    print("=" * 60)
    
    steps = [
        ("Vérification des prérequis", check_requirements),
        ("Installation des dépendances", install_dependencies),
        ("Configuration de l'environnement", setup_environment),
        ("Initialisation de la base de données", initialize_database),
        ("Création du service systemd", create_systemd_service),
        ("Création de la config Nginx", create_nginx_config),
        ("Création du script de sauvegarde", create_backup_script)
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Échec à l'étape : {step_name}")
            return False
    
    print("\n🎉 Déploiement terminé avec succès !")
    print("\n📋 Prochaines étapes :")
    print("1. Configurez vos clés API dans le fichier .env")
    print("2. Testez l'application : python app.py")
    print("3. Configurez Nginx et le service systemd")
    print("4. Configurez les sauvegardes automatiques")
    print("5. Configurez SSL avec Let's Encrypt")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sms_providers import create_ivory_coast_sms_manager
from config_ivory_coast import OPERATOR_PREFIXES, SMS_PRICING, CURRENCY

class SMSMarketingPlatform:
    def __init__(self):
        self.conn = sqlite3.connect('sms_marketing.db')
        self.cursor = self.conn.cursor()
        self.sms_manager = None
        self.create_tables()
        self.initialize_sms_providers()

    def create_tables(self):
        try:
            # Créer les tables
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    scheduled_date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sent_messages (
                    id INTEGER PRIMARY KEY,
                    campaign_id INTEGER NOT NULL,
                    recipient TEXT NOT NULL,
                    sent_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS contact_groups (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    group_id INTEGER,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    consent_given BOOLEAN DEFAULT 0,
                    consent_date TEXT,
                    opt_out BOOLEAN DEFAULT 0,
                    opt_out_date TEXT,
                    operator TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (group_id) REFERENCES contact_groups (id)
                )
            ''')
            
            # Table pour les soldes des utilisateurs
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_balances (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    balance REAL DEFAULT 0,
                    currency TEXT DEFAULT 'FCFA',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Table pour l'historique des transactions
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    transaction_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'FCFA',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Table pour les templates de messages
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_templates (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    template_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Commit les changements après la création des tables
            self.conn.commit()
            
            # Vérifier si l'index existe déjà
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_campaigns_user_id'")
            if not self.cursor.fetchone():
                # Créer l'index s'il n'existe pas
                self.cursor.execute('CREATE INDEX idx_campaigns_user_id ON campaigns (user_id)')
            
            # Vérifier si l'autre index existe déjà
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_sent_messages_campaign_id'")
            if not self.cursor.fetchone():
                # Créer l'index s'il n'existe pas
                self.cursor.execute('CREATE INDEX idx_sent_messages_campaign_id ON sent_messages (campaign_id)')
            
            # Commit à nouveau après la création des index
            self.conn.commit()
            
            print("Tables and indexes created successfully")
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")
            self.conn.rollback()

    def add_user(self, username, email, password):
        password_hash = generate_password_hash(password)
        try:
            self.cursor.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                                (username, email, password_hash))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def user_exists(self, username):
        self.cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        return self.cursor.fetchone() is not None

    def check_password(self, user_id, password):
        self.cursor.execute('SELECT password_hash FROM users WHERE id = ?', (user_id,))
        user = self.cursor.fetchone()
        if user:
            return check_password_hash(user[0], password)
        return False

    def change_password(self, user_id, new_password):
        password_hash = generate_password_hash(new_password)
        self.cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def authenticate_user(self, username, password):
        self.cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
        user = self.cursor.fetchone()
        if user and check_password_hash(user[1], password):
            return user[0]
        return None

    def get_user_info(self, user_id):
        self.cursor.execute('SELECT username, email FROM users WHERE id = ?', (user_id,))
        return self.cursor.fetchone()

    def add_client(self, user_id, name, phone, email):
        self.cursor.execute('INSERT INTO clients (user_id, name, phone, email) VALUES (?, ?, ?, ?)',
                            (user_id, name, phone, email))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_user_clients(self, user_id):
        self.cursor.execute('SELECT * FROM clients WHERE user_id = ?', (user_id,))
        return self.cursor.fetchall()

    def create_campaign(self, user_id, name, message, scheduled_date):
        self.cursor.execute('''
            INSERT INTO campaigns (user_id, name, message, scheduled_date)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, message, scheduled_date))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_campaign(self, campaign_id, user_id):
        self.cursor.execute('''
            SELECT id, name, message, scheduled_date, created_at 
            FROM campaigns 
            WHERE id = ? AND user_id = ?
        ''', (campaign_id, user_id))
        return self.cursor.fetchone()

    def get_user_campaigns(self, user_id):
        self.cursor.execute('''
            SELECT id, name, message, scheduled_date, created_at 
            FROM campaigns 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 5
        ''', (user_id,))
        return self.cursor.fetchall()

    def delete_campaign(self, campaign_id, user_id):
        self.cursor.execute('DELETE FROM campaigns WHERE id = ? AND user_id = ?', (campaign_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_monthly_messages(self, user_id):
        first_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        self.cursor.execute('''
            SELECT COUNT(*) FROM sent_messages
            JOIN campaigns ON sent_messages.campaign_id = campaigns.id
            WHERE campaigns.user_id = ? AND sent_messages.sent_date >= ?
        ''', (user_id, first_of_month))
        return self.cursor.fetchone()[0]

    def get_average_open_rate(self, user_id):
        self.cursor.execute('''
            SELECT AVG(CASE WHEN status = 'OPENED' THEN 100.0 ELSE 0 END)
            FROM sent_messages
            JOIN campaigns ON sent_messages.campaign_id = campaigns.id
            WHERE campaigns.user_id = ?
        ''', (user_id,))
        result = self.cursor.fetchone()[0]
        return result if result is not None else 0
    
    def add_contact(self, user_id, name, phone, email=None, group_id=None):
        self.cursor.execute('''
            INSERT INTO contacts (user_id, group_id, name, phone, email)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, group_id, name, phone, email))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_contacts(self, user_id):
        self.cursor.execute('''
            SELECT c.id, c.name, c.phone, c.email, g.name as group_name
            FROM contacts c
            LEFT JOIN contact_groups g ON c.group_id = g.id
            WHERE c.user_id = ?
        ''', (user_id,))
        return self.cursor.fetchall()

    def update_contact(self, contact_id, user_id, name, phone, email, group_id):
        self.cursor.execute('''
            UPDATE contacts
            SET name = ?, phone = ?, email = ?, group_id = ?
            WHERE id = ? AND user_id = ?
        ''', (name, phone, email, group_id, contact_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def delete_contact(self, contact_id, user_id):
        self.cursor.execute('DELETE FROM contacts WHERE id = ? AND user_id = ?', (contact_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def add_group(self, user_id, name):
        self.cursor.execute('INSERT INTO contact_groups (user_id, name) VALUES (?, ?)', (user_id, name))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_groups(self, user_id):
        self.cursor.execute('SELECT id, name FROM contact_groups WHERE user_id = ?', (user_id,))
        return self.cursor.fetchall()

    def import_contacts_from_csv(self, user_id, file_path):
        import csv
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                self.add_contact(user_id, row['name'], row['phone'], row.get('email'))
        self.conn.commit()

    def initialize_sms_providers(self):
        """Initialise les fournisseurs SMS pour la Côte d'Ivoire"""
        # Configuration des clés API (à récupérer depuis les variables d'environnement)
        import os
        orange_key = os.getenv('ORANGE_API_KEY')
        mtn_key = os.getenv('MTN_API_KEY')
        moov_key = os.getenv('MOOV_API_KEY')
        
        self.sms_manager = create_ivory_coast_sms_manager(
            orange_api_key=orange_key,
            mtn_api_key=mtn_key,
            moov_api_key=moov_key
        )
    
    def add_contact_with_consent(self, user_id, name, phone, email=None, group_id=None, consent_given=False):
        """Ajoute un contact avec gestion du consentement"""
        # Détecter l'opérateur basé sur le numéro
        operator = self._detect_operator(phone)
        
        self.cursor.execute('''
            INSERT INTO contacts (user_id, group_id, name, phone, email, consent_given, consent_date, operator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, group_id, name, phone, email, consent_given, 
              datetime.now().isoformat() if consent_given else None, operator))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def _detect_operator(self, phone_number):
        """Détecte l'opérateur basé sur le numéro de téléphone"""
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        # Supprimer le préfixe 225 si présent
        if clean_number.startswith('225'):
            number = clean_number[3:]
        elif clean_number.startswith('0'):
            number = clean_number  # Garder le 0 pour la détection
        else:
            number = clean_number
        
        # Vérifier les préfixes des opérateurs
        for operator, prefixes in OPERATOR_PREFIXES.items():
            for prefix in prefixes:
                if number.startswith(prefix):
                    return operator
        
        return 'unknown'
    
    def send_sms_campaign(self, campaign_id, user_id):
        """Envoie une campagne SMS avec gestion des coûts et du consentement"""
        # Récupérer la campagne
        campaign = self.get_campaign(campaign_id, user_id)
        if not campaign:
            return {'success': False, 'error': 'Campagne non trouvée'}
        
        # Récupérer les contacts avec consentement
        self.cursor.execute('''
            SELECT phone, operator FROM contacts 
            WHERE user_id = ? AND consent_given = 1 AND opt_out = 0
        ''', (user_id,))
        contacts = self.cursor.fetchall()
        
        if not contacts:
            return {'success': False, 'error': 'Aucun contact avec consentement trouvé'}
        
        # Calculer le coût total
        total_cost = 0
        results = []
        
        for phone, operator in contacts:
            # Déterminer le fournisseur optimal
            provider = self.sms_manager.get_optimal_provider(phone)
            
            # Envoyer le SMS
            result = self.sms_manager.send_sms(phone, campaign[2], provider)
            
            if result['success']:
                # Calculer le coût
                cost = SMS_PRICING.get(provider, {}).get('domestic', 25)
                total_cost += cost
                
                # Enregistrer l'envoi
                self.cursor.execute('''
                    INSERT INTO sent_messages (campaign_id, recipient, sent_date, status)
                    VALUES (?, ?, ?, ?)
                ''', (campaign_id, phone, datetime.now().isoformat(), 'SENT'))
                
                # Débiter le solde de l'utilisateur
                self._debit_user_balance(user_id, cost)
                
                # Enregistrer la transaction
                self._record_transaction(user_id, 'SMS_SENT', cost, f'SMS envoyé à {phone}')
            
            results.append({
                'phone': phone,
                'success': result['success'],
                'cost': result.get('cost', 0),
                'provider': result.get('provider', 'unknown')
            })
        
        self.conn.commit()
        
        return {
            'success': True,
            'total_sent': len([r for r in results if r['success']]),
            'total_cost': total_cost,
            'results': results
        }
    
    def get_user_balance(self, user_id):
        """Récupère le solde de l'utilisateur"""
        self.cursor.execute('SELECT balance FROM user_balances WHERE user_id = ?', (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0
    
    def add_user_balance(self, user_id, amount):
        """Ajoute du crédit au solde de l'utilisateur"""
        current_balance = self.get_user_balance(user_id)
        new_balance = current_balance + amount
        
        self.cursor.execute('''
            INSERT OR REPLACE INTO user_balances (user_id, balance, last_updated)
            VALUES (?, ?, ?)
        ''', (user_id, new_balance, datetime.now().isoformat()))
        
        # Enregistrer la transaction
        self._record_transaction(user_id, 'BALANCE_ADDED', amount, 'Crédit ajouté au compte')
        
        self.conn.commit()
        return new_balance
    
    def _debit_user_balance(self, user_id, amount):
        """Débite le solde de l'utilisateur"""
        current_balance = self.get_user_balance(user_id)
        if current_balance >= amount:
            new_balance = current_balance - amount
            
            self.cursor.execute('''
                INSERT OR REPLACE INTO user_balances (user_id, balance, last_updated)
                VALUES (?, ?, ?)
            ''', (user_id, new_balance, datetime.now().isoformat()))
            
            self.conn.commit()
            return True
        return False
    
    def _record_transaction(self, user_id, transaction_type, amount, description):
        """Enregistre une transaction"""
        self.cursor.execute('''
            INSERT INTO transactions (user_id, transaction_type, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, transaction_type, amount, description))
        self.conn.commit()
    
    def get_user_transactions(self, user_id, limit=50):
        """Récupère l'historique des transactions de l'utilisateur"""
        self.cursor.execute('''
            SELECT transaction_type, amount, description, created_at
            FROM transactions 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        return self.cursor.fetchall()
    
    def create_message_template(self, user_id, name, content, template_type):
        """Crée un template de message"""
        self.cursor.execute('''
            INSERT INTO message_templates (user_id, name, content, template_type)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, content, template_type))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_user_templates(self, user_id):
        """Récupère les templates de l'utilisateur"""
        self.cursor.execute('''
            SELECT id, name, content, template_type, created_at
            FROM message_templates 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (user_id,))
        return self.cursor.fetchall()
    
    def update_contact_consent(self, contact_id, user_id, consent_given):
        """Met à jour le consentement d'un contact"""
        self.cursor.execute('''
            UPDATE contacts 
            SET consent_given = ?, consent_date = ?
            WHERE id = ? AND user_id = ?
        ''', (consent_given, datetime.now().isoformat() if consent_given else None, 
              contact_id, user_id))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def opt_out_contact(self, phone_number):
        """Gère le désabonnement d'un contact"""
        self.cursor.execute('''
            UPDATE contacts 
            SET opt_out = 1, opt_out_date = ?
            WHERE phone = ?
        ''', (datetime.now().isoformat(), phone_number))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_campaign_analytics(self, campaign_id, user_id):
        """Récupère les analytics d'une campagne"""
        # Statistiques de base
        self.cursor.execute('''
            SELECT COUNT(*) FROM sent_messages 
            WHERE campaign_id = ?
        ''', (campaign_id,))
        total_sent = self.cursor.fetchone()[0]
        
        self.cursor.execute('''
            SELECT COUNT(*) FROM sent_messages 
            WHERE campaign_id = ? AND status = 'DELIVERED'
        ''', (campaign_id,))
        delivered = self.cursor.fetchone()[0]
        
        # Calculer le taux de livraison
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        
        # Coût total
        self.cursor.execute('''
            SELECT SUM(amount) FROM transactions 
            WHERE user_id = ? AND transaction_type = 'SMS_SENT'
            AND description LIKE ?
        ''', (user_id, f'%Campaign {campaign_id}%'))
        total_cost = self.cursor.fetchone()[0] or 0
        
        return {
            'total_sent': total_sent,
            'delivered': delivered,
            'delivery_rate': round(delivery_rate, 2),
            'total_cost': total_cost,
            'cost_per_message': round(total_cost / total_sent, 2) if total_sent > 0 else 0
        }
    
    def get_ivory_coast_analytics(self, user_id):
        """Analytics spécifiques au marché ivoirien"""
        # Messages par opérateur
        self.cursor.execute('''
            SELECT c.operator, COUNT(sm.id) as count
            FROM contacts c
            LEFT JOIN sent_messages sm ON c.phone = sm.recipient
            WHERE c.user_id = ? AND c.consent_given = 1
            GROUP BY c.operator
        ''', (user_id,))
        operator_stats = dict(self.cursor.fetchall())
        
        # Coût par opérateur
        operator_costs = {}
        for operator in ['orange', 'mtn', 'moov']:
            if operator in operator_stats:
                operator_costs[operator] = operator_stats[operator] * SMS_PRICING[operator]['domestic']
        
        return {
            'operator_distribution': operator_stats,
            'operator_costs': operator_costs,
            'total_contacts': sum(operator_stats.values()),
            'currency': CURRENCY
        }

    def close_connection(self):
        self.conn.close()
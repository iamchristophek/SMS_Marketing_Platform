import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class SMSMarketingPlatform:
    def __init__(self):
        self.conn = sqlite3.connect('sms_marketing.db')
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                password_hash TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                email TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY,
                client_id INTEGER,
                name TEXT,
                message TEXT,
                scheduled_date TEXT,
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_messages (
                id INTEGER PRIMARY KEY,
                campaign_id INTEGER,
                recipient TEXT,
                sent_date TEXT,
                status TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            )
        ''')
        self.conn.commit()

    def add_client(self, name, phone, email):
        self.cursor.execute('INSERT INTO clients (name, phone, email) VALUES (?, ?, ?)',
                            (name, phone, email))
        self.conn.commit()

    def create_campaign(self, client_id, name, message, scheduled_date):
        self.cursor.execute('''
            INSERT INTO campaigns (client_id, name, message, scheduled_date)
            VALUES (?, ?, ?, ?)
        ''', (client_id, name, message, scheduled_date))
        self.conn.commit()
        

    def send_sms(self, campaign_id, recipient):
        # Ici,intégrer l'API du fournisseur SMS
        # Pour cet exemple, nous allons simplement simuler l'envoi
        sent_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "SENT"  # En réalité, cela dépendrait de la réponse de l'API

        self.cursor.execute('''
            INSERT INTO sent_messages (campaign_id, recipient, sent_date, status)
            VALUES (?, ?, ?, ?)
        ''', (campaign_id, recipient, sent_date, status))
        self.conn.commit()

    def get_campaign_stats(self, campaign_id):
        self.cursor.execute('''
            SELECT status, COUNT(*) FROM sent_messages
            WHERE campaign_id = ?
            GROUP BY status
        ''', (campaign_id,))
        return self.cursor.fetchall()

    def add_user(self, username, password):
        password_hash = generate_password_hash(password)
        self.cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                            (username, password_hash))
        self.conn.commit()

    def authenticate_user(self, username, password):
        self.cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_data = self.cursor.fetchone()
        if user_data and check_password_hash(user_data[2], password):
            return user_data[0]  # Retourne l'ID de l'utilisateur
        return None

    # Ajoutez ici les méthodes pour la gestion des abonnés et des opt-outs
    
    
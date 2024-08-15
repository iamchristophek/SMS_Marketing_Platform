import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class SMSMarketingPlatform:
    def __init__(self):
        self.conn = sqlite3.connect('sms_marketing.db')
        self.cursor = self.conn.cursor()
        self.create_tables()

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

    def close_connection(self):
        self.conn.close()
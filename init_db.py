import os
from sms_platform import SMSMarketingPlatform

def reset_db():
    # Supprimer l'ancienne base de données si elle existe
    db_name = 'sms_marketing.db'
    if os.path.exists(db_name):
        os.remove(db_name)
        print(f"Ancienne base de données {db_name} supprimée.")
    else:
        print(f"Aucune base de données {db_name} existante trouvée.")

    # Créer une nouvelle instance de SMSMarketingPlatform
    # Cela créera automatiquement une nouvelle base de données et les tables
    platform = SMSMarketingPlatform()

    # Ajouter un utilisateur de test
    admin_id = platform.add_user('admin', 'admin@example.com', 'password123')
    if admin_id:
        print(f"Utilisateur admin créé avec l'ID: {admin_id}")

        # Ajouter quelques clients de test
        client1_id = platform.add_client(admin_id, "Client 1", "1234567890", "client1@example.com")
        client2_id = platform.add_client(admin_id, "Client 2", "0987654321", "client2@example.com")
        print(f"Clients de test créés avec les IDs: {client1_id}, {client2_id}")

        # Créer une campagne de test
        campaign_id = platform.create_campaign(admin_id, "Campagne de bienvenue", "Bienvenue dans notre service !", "2024-08-15 10:00:00")
        print(f"Campagne de test créée avec l'ID: {campaign_id}")

        # Simuler l'envoi de quelques messages
        #platform.send_sms(campaign_id, "1234567890")
        #platform.send_sms(campaign_id, "0987654321")
        print("Messages de test envoyés.")

    else:
        print("Erreur lors de la création de l'utilisateur admin.")

    # Fermer la connexion
    platform.close_connection()

    print("Réinitialisation de la base de données terminée.")

if __name__ == "__main__":
    reset_db()
"""
Module pour l'intégration avec les fournisseurs SMS en Côte d'Ivoire
Support pour Orange, MTN, et Moov
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class SMSProvider:
    """Classe de base pour les fournisseurs SMS"""
    
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url
    
    def send_sms(self, phone_number: str, message: str) -> Dict:
        """Envoie un SMS via l'API du fournisseur"""
        raise NotImplementedError
    
    def get_balance(self) -> float:
        """Récupère le solde du compte"""
        raise NotImplementedError
    
    def get_delivery_status(self, message_id: str) -> str:
        """Vérifie le statut de livraison d'un message"""
        raise NotImplementedError

class OrangeSMS(SMSProvider):
    """Fournisseur SMS Orange Côte d'Ivoire"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.orange.com/smsmessaging/v1/outbound")
    
    def send_sms(self, phone_number: str, message: str) -> Dict:
        """Envoie un SMS via Orange"""
        # Format du numéro pour Orange CI (+225)
        formatted_number = self._format_phone_number(phone_number)
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'outboundSMSMessageRequest': {
                'address': [f'tel:{formatted_number}'],
                'senderAddress': 'tel:+2250000',  # Numéro d'expéditeur Orange
                'outboundSMSTextMessage': {
                    'message': message
                }
            }
        }
        
        try:
            response = requests.post(f"{self.api_url}/requests", 
                                   headers=headers, 
                                   json=data)
            return {
                'success': response.status_code == 201,
                'message_id': response.json().get('outboundSMSMessageRequest', {}).get('resourceReference', {}).get('resourceURL', ''),
                'cost': 25,  # Coût en FCFA pour Orange CI
                'provider': 'Orange'
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'provider': 'Orange'}
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Formate le numéro de téléphone pour Orange CI"""
        # Supprime tous les espaces et caractères spéciaux
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        # Si le numéro commence par 225, on l'utilise tel quel
        if clean_number.startswith('225'):
            return f"+{clean_number}"
        
        # Si le numéro commence par 0, on remplace par +225
        if clean_number.startswith('0'):
            return f"+225{clean_number}"
        
        # Si le numéro a 8 chiffres, on ajoute +225
        if len(clean_number) == 8:
            return f"+225{clean_number}"
        
        return f"+{clean_number}"

class MTNSMS(SMSProvider):
    """Fournisseur SMS MTN Côte d'Ivoire"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.mtn.ci/sms/v1/send")
    
    def send_sms(self, phone_number: str, message: str) -> Dict:
        """Envoie un SMS via MTN"""
        formatted_number = self._format_phone_number(phone_number)
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'to': formatted_number,
            'message': message,
            'from': 'MTN'
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data)
            return {
                'success': response.status_code == 200,
                'message_id': response.json().get('messageId', ''),
                'cost': 30,  # Coût en FCFA pour MTN CI
                'provider': 'MTN'
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'provider': 'MTN'}
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Formate le numéro de téléphone pour MTN CI"""
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        if clean_number.startswith('225'):
            return f"+{clean_number}"
        
        if clean_number.startswith('0'):
            return f"+225{clean_number}"
        
        if len(clean_number) == 8:
            return f"+225{clean_number}"
        
        return f"+{clean_number}"

class MoovSMS(SMSProvider):
    """Fournisseur SMS Moov Côte d'Ivoire"""
    
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.moov.ci/sms/send")
    
    def send_sms(self, phone_number: str, message: str) -> Dict:
        """Envoie un SMS via Moov"""
        formatted_number = self._format_phone_number(phone_number)
        
        headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        data = {
            'recipient': formatted_number,
            'message': message,
            'sender': 'Moov'
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data)
            return {
                'success': response.status_code == 200,
                'message_id': response.json().get('id', ''),
                'cost': 20,  # Coût en FCFA pour Moov CI
                'provider': 'Moov'
            }
        except Exception as e:
            return {'success': False, 'error': str(e), 'provider': 'Moov'}
    
    def _format_phone_number(self, phone_number: str) -> str:
        """Formate le numéro de téléphone pour Moov CI"""
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        if clean_number.startswith('225'):
            return f"+{clean_number}"
        
        if clean_number.startswith('0'):
            return f"+225{clean_number}"
        
        if len(clean_number) == 8:
            return f"+225{clean_number}"
        
        return f"+{clean_number}"

class SMSManager:
    """Gestionnaire principal pour l'envoi de SMS multi-fournisseurs"""
    
    def __init__(self):
        self.providers = {}
        self.default_provider = None
    
    def add_provider(self, name: str, provider: SMSProvider):
        """Ajoute un fournisseur SMS"""
        self.providers[name] = provider
        if not self.default_provider:
            self.default_provider = name
    
    def set_default_provider(self, name: str):
        """Définit le fournisseur par défaut"""
        if name in self.providers:
            self.default_provider = name
    
    def send_sms(self, phone_number: str, message: str, provider_name: str = None) -> Dict:
        """Envoie un SMS via le fournisseur spécifié ou par défaut"""
        if provider_name and provider_name in self.providers:
            provider = self.providers[provider_name]
        elif self.default_provider:
            provider = self.providers[self.default_provider]
        else:
            return {'success': False, 'error': 'Aucun fournisseur SMS configuré'}
        
        return provider.send_sms(phone_number, message)
    
    def send_bulk_sms(self, phone_numbers: List[str], message: str, provider_name: str = None) -> List[Dict]:
        """Envoie des SMS en masse"""
        results = []
        for phone_number in phone_numbers:
            result = self.send_sms(phone_number, message, provider_name)
            results.append({
                'phone_number': phone_number,
                'result': result
            })
        return results
    
    def get_optimal_provider(self, phone_number: str) -> str:
        """Détermine le fournisseur optimal basé sur le numéro de téléphone"""
        # Logique simple : déterminer l'opérateur basé sur le préfixe
        clean_number = ''.join(filter(str.isdigit, phone_number))
        
        if clean_number.startswith('225'):
            number = clean_number[3:]
        elif clean_number.startswith('0'):
            number = clean_number  # Garder le 0 pour la détection
        else:
            number = clean_number
        
        # Préfixes des opérateurs en Côte d'Ivoire
        if number.startswith(('07', '08', '09')):  # Orange
            return 'orange'
        elif number.startswith(('05', '06')):  # MTN
            return 'mtn'
        elif number.startswith(('01', '02', '03', '04')):  # Moov
            return 'moov'
        else:
            return self.default_provider or 'orange'

# Configuration pour la Côte d'Ivoire
def create_ivory_coast_sms_manager(orange_api_key: str = None, 
                                  mtn_api_key: str = None, 
                                  moov_api_key: str = None) -> SMSManager:
    """Crée un gestionnaire SMS configuré pour la Côte d'Ivoire"""
    manager = SMSManager()
    
    if orange_api_key:
        manager.add_provider('orange', OrangeSMS(orange_api_key))
    
    if mtn_api_key:
        manager.add_provider('mtn', MTNSMS(mtn_api_key))
    
    if moov_api_key:
        manager.add_provider('moov', MoovSMS(moov_api_key))
    
    # Définir Orange comme fournisseur par défaut (le plus populaire en CI)
    if orange_api_key:
        manager.set_default_provider('orange')
    elif mtn_api_key:
        manager.set_default_provider('mtn')
    elif moov_api_key:
        manager.set_default_provider('moov')
    
    return manager

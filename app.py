from flask import Flask, flash, request, jsonify, render_template, redirect, session, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, Optional
from sms_platform import SMSMarketingPlatform
from forms import LoginForm, CampaignForm, RegistrationForm, ChangePasswordForm
from config_ivory_coast import *
import functools


app = Flask(__name__)
app.secret_key = 'superappsecretkey' # secret key for session management to provide before using session object the app
platform = SMSMarketingPlatform()

def login_required(f):
    """Décorateur pour vérifier l'authentification"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Vous devez être connecté pour accéder à cette page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = SMSMarketingPlatform()
    user_info = platform.get_user_info(session['user_id'])
    campaigns = platform.get_user_campaigns(session['user_id'])
    total_campaigns = len(campaigns)
    monthly_messages = platform.get_monthly_messages(session['user_id'])
    average_open_rate = platform.get_average_open_rate(session['user_id'])
    #contacts = platform.get_user_clients(session['user_id'])
    return render_template('dashboard.html', user_info=user_info, campaigns=campaigns,
                           total_campaigns=total_campaigns, monthly_messages=monthly_messages,
                           average_open_rate=average_open_rate) #contacts=contacts)

@app.route('/campaigns')
def campaigns_management():
    """Page de gestion des campagnes"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    campaigns = platform.get_user_campaigns(session['user_id'])
    monthly_messages = platform.get_monthly_messages(session['user_id'])
    
    return render_template('campaigns_management.html', 
                         campaigns=campaigns,
                         monthly_messages=monthly_messages)

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = SMSMarketingPlatform()
    user_info = platform.get_user_info(session['user_id'])
    return render_template('dashboard.html', user_info=user_info)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Veuillez remplir tous les champs', 'error')
            return render_template('login.html')
        
        platform = SMSMarketingPlatform()
        user_id = platform.authenticate_user(username, password)
        
        if user_id:
            session['user_id'] = user_id
            flash('Connexion réussie ! Bienvenue sur la plateforme SMS Marketing Côte d\'Ivoire', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
    
    return render_template('login.html')
    
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Déconnexion réussie', 'info')
    return redirect(url_for('login'))

@app.route('/campaign/<int:campaign_id>')
def view_campaign(campaign_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    campaign = platform.get_campaign(campaign_id, session['user_id'])
    
    if not campaign:
        flash('Campagne non trouvée.', 'error')
        return redirect(url_for('dashboard'))
    
    # Récupérer les analytics de la campagne
    analytics = platform.get_campaign_analytics(campaign_id, session['user_id'])
    
    return render_template('campaigns.html', campaign=campaign, analytics=analytics)



@app.route('/create_campaign', methods=['GET', 'POST'])
def create_campaign():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    form = CampaignForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            platform = SMSMarketingPlatform()
            campaign = platform.create_campaign(
                user_id=session['user_id'],
                name=form.name.data,
                message=form.message.data,
                scheduled_date=form.scheduled_date.data
            )
            flash('Campaign created successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error creating campaign: {str(e)}', 'error')
    
    return render_template('create_campaign.html', form=form)

@app.route('/delete_campaign/<int:campaign_id>')
def delete_campaign(campaign_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = SMSMarketingPlatform()
    if platform.delete_campaign(campaign_id, session['user_id']):
        flash('Campagne supprimée avec succès')
    else:
        flash('Erreur lors de la suppression de la campagne')
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        terms = request.form.get('terms')
        
        # Validation des données
        if not username or not email or not password or not confirm_password:
            flash('Veuillez remplir tous les champs obligatoires', 'error')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères', 'error')
            return render_template('register.html')
        
        if not terms:
            flash('Vous devez accepter les conditions d\'utilisation', 'error')
            return render_template('register.html')
        
        # Vérifier si l'utilisateur existe déjà
        platform = SMSMarketingPlatform()
        if platform.user_exists(username):
            flash('Nom d\'utilisateur déjà utilisé', 'error')
            return render_template('register.html')
        
        # Créer l'utilisateur
        try:
            platform.add_user(username, password, email)
            flash('Compte créé avec succès ! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Erreur lors de la création du compte. Veuillez réessayer.', 'error')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        flash('Vous devez être connecté pour accéder à cette page', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')
        
        # Validation des données
        if not current_password or not new_password or not confirm_new_password:
            flash('Veuillez remplir tous les champs', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_new_password:
            flash('Les nouveaux mots de passe ne correspondent pas', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('Le nouveau mot de passe doit contenir au moins 6 caractères', 'error')
            return render_template('change_password.html')
        
        platform = SMSMarketingPlatform()
        user_id = session['user_id']
        
        # Vérifie si le mot de passe actuel est correct
        if platform.check_password(user_id, current_password):
            # Change le mot de passe
            platform.change_password(user_id, new_password)
            flash('Mot de passe modifié avec succès', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Mot de passe actuel incorrect', 'error')
    
    return render_template('change_password.html')

# Nouvelles routes pour le marché ivoirien

@app.route('/balance')
def balance():
    """Affiche le solde de l'utilisateur"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    user_balance = platform.get_user_balance(session['user_id'])
    transactions = platform.get_user_transactions(session['user_id'], limit=20)
    
    return render_template('balance.html', 
                         balance=user_balance, 
                         currency=CURRENCY_SYMBOL,
                         transactions=transactions)

@app.route('/add_balance', methods=['GET', 'POST'])
def add_balance():
    """Ajoute du crédit au compte"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        amount = float(request.form.get('amount', 0))
        if amount > 0:
            platform = SMSMarketingPlatform()
            new_balance = platform.add_user_balance(session['user_id'], amount)
            flash(f'Crédit de {amount} {CURRENCY_SYMBOL} ajouté avec succès !', 'success')
            return redirect(url_for('balance'))
        else:
            flash('Montant invalide', 'error')
    
    return render_template('add_balance.html')

@app.route('/contacts')
def contacts():
    """Gestion des contacts avec consentement"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    contacts = platform.get_contacts(session['user_id'])
    groups = platform.get_groups(session['user_id'])
    
    return render_template('contacts.html', contacts=contacts, groups=groups)

@app.route('/add_contact', methods=['GET', 'POST'])
def add_contact():
    """Ajoute un contact avec gestion du consentement"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        group_id = request.form.get('group_id')
        consent_given = 'consent' in request.form
        
        platform = SMSMarketingPlatform()
        contact_id = platform.add_contact_with_consent(
            session['user_id'], name, phone, email, group_id, consent_given
        )
        
        if contact_id:
            flash('Contact ajouté avec succès !', 'success')
        else:
            flash('Erreur lors de l\'ajout du contact', 'error')
        
        return redirect(url_for('contacts'))
    
    platform = SMSMarketingPlatform()
    groups = platform.get_groups(session['user_id'])
    return render_template('add_contact.html', groups=groups)

@app.route('/send_campaign/<int:campaign_id>')
def send_campaign(campaign_id):
    """Affiche la page de confirmation d'envoi de campagne"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    campaign = platform.get_campaign(campaign_id, session['user_id'])
    
    if not campaign:
        flash('Campagne non trouvée', 'error')
        return redirect(url_for('campaigns_management'))
    
    return render_template('send_campaign.html', campaign=campaign)

@app.route('/confirm_send_campaign/<int:campaign_id>')
def confirm_send_campaign(campaign_id):
    """Confirme et envoie une campagne SMS"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    
    # Vérifier le solde
    balance = platform.get_user_balance(session['user_id'])
    if balance < 100:  # Seuil minimum
        flash('Solde insuffisant. Veuillez recharger votre compte.', 'error')
        return redirect(url_for('balance'))
    
    # Envoyer la campagne
    result = platform.send_sms_campaign(campaign_id, session['user_id'])
    
    if result['success']:
        flash(f'Campagne envoyée ! {result["total_sent"]} SMS envoyés pour {result["total_cost"]} {CURRENCY_SYMBOL}', 'success')
    else:
        flash(f'Erreur: {result["error"]}', 'error')
    
    return redirect(url_for('campaigns_management'))

@app.route('/analytics')
def analytics():
    """Analytics spécifiques au marché ivoirien"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    analytics_data = platform.get_ivory_coast_analytics(session['user_id'])
    
    return render_template('analytics.html', 
                         analytics=analytics_data,
                         currency=CURRENCY_SYMBOL)

@app.route('/templates')
def templates():
    """Gestion des templates de messages"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    templates = platform.get_user_templates(session['user_id'])
    
    return render_template('templates.html', templates=templates)

@app.route('/create_template', methods=['GET', 'POST'])
def create_template():
    """Crée un template de message"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        content = request.form.get('content')
        template_type = request.form.get('template_type')
        
        platform = SMSMarketingPlatform()
        template_id = platform.create_message_template(
            session['user_id'], name, content, template_type
        )
        
        if template_id:
            flash('Template créé avec succès !', 'success')
            return redirect(url_for('templates'))
        else:
            flash('Erreur lors de la création du template', 'error')
    
    return render_template('create_template.html', 
                         template_types=MESSAGE_TEMPLATES)

@app.route('/opt_out/<phone_number>')
def opt_out(phone_number):
    """Gère le désabonnement d'un contact"""
    platform = SMSMarketingPlatform()
    if platform.opt_out_contact(phone_number):
        flash('Désabonnement enregistré', 'info')
    else:
        flash('Erreur lors du désabonnement', 'error')
    
    return redirect(url_for('contacts'))

@app.route('/update_consent/<int:contact_id>', methods=['GET', 'POST'])
def update_consent(contact_id):
    """Met à jour le consentement d'un contact"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    platform = SMSMarketingPlatform()
    
    # Récupérer les informations du contact
    contacts = platform.get_contacts(session['user_id'])
    contact = None
    for c in contacts:
        if c[0] == contact_id:
            contact = {
                'id': c[0],
                'name': c[1],
                'phone': c[2],
                'email': c[3],
                'consent_given': c[6] if len(c) > 6 else False,
                'consent_date': c[7] if len(c) > 7 else None
            }
            break
    
    if not contact:
        flash('Contact non trouvé', 'error')
        return redirect(url_for('contacts'))
    
    if request.method == 'POST':
        consent_given = 'consent_given' in request.form
        if platform.update_contact_consent(contact_id, session['user_id'], consent_given):
            flash('Consentement mis à jour avec succès !', 'success')
        else:
            flash('Erreur lors de la mise à jour du consentement', 'error')
        return redirect(url_for('contacts'))
    
    return render_template('update_consent.html', contact=contact)


if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, flash, request, jsonify, render_template, redirect, session, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from sms_platform import SMSMarketingPlatform
from forms import LoginForm, CampaignForm, RegistrationForm, ChangePasswordForm


app = Flask(__name__)
app.secret_key = 'superappsecretkey' # secret key for session management to provide before using session object the app
platform = SMSMarketingPlatform()


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

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = SMSMarketingPlatform()
    user_info = platform.get_user_info(session['user_id'])
    return render_template('dashboard.html', user_info=user_info)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        platform = SMSMarketingPlatform()
        user_id = platform.authenticate_user(username, password)
        if user_id:
            session['user_id'] = user_id
            flash('Connexion réussie !', 'success')
            return redirect(url_for('home'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
    return render_template('login.html', form=form)
    
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
    
    return render_template('campaigns.html', campaign=campaign)



@app.route('/create_campaign', methods=['GET', 'POST'])
@login_required
def create_campaign():
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
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        # Vérifie si l'utilisateur existe déjà
        platform = SMSMarketingPlatform()
        if platform.user_exists(username):
            flash('Nom d\'utilisateur déjà utilisé', 'error')
            return redirect(url_for('register'))
        #platform.add_user(username, password)
        
        else:
            #creéation de l'utilisateur
            platform.add_user(username, password)
            flash('Compte créé avec succès !', 'success')
            #flash('Erreur lors de la création du compte', 'error')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        flash('Vous devez être connecté pour accéder à cette page', 'error')
        return redirect(url_for('login'))
    
    form = ChangePasswordForm()
    if form.validate_on_submit():
        platform = SMSMarketingPlatform()
        user_id = session['user_id']
        old_password = form.old_password.data
        new_password = form.new_password.data
        
        
        # Vérifie si le mot de passe actuel est correct
        if platform.check_password(user_id, old_password):
             # Change le mot de passe
            platform.change_password(user_id, new_password)
            flash('Mot de passe modifié avec succès', 'success')
            return redirect(url_for('home'))
        else:
            flash('Erreur lors de la modification du mot de passe', 'error')
    return render_template('change_password.html', form=form)


if __name__ == '__main__':
    app.run(debug=True)

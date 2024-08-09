from flask import Flask, flash, request, jsonify, render_template, redirect, session, url_for
from sms_platform import SMSMarketingPlatform


app = Flask(__name__)
app.secret_key = 'superappsecretkey' # secret key for session management to provide before using session object the app
platform = SMSMarketingPlatform()


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    platform = SMSMarketingPlatform()
    user_info = platform.get_user_info(session['user_id'])
    return render_template('dashboard.html', user_info=user_info)


@app.route('/login', methods=['GET', 'POST'])
def login(platform=None):
    if not platform:
        platform = SMSMarketingPlatform()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = platform.authenticate_user(username, password)
        if user_id:
            session['user_id'] = user_id
            return redirect('/')
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')
    
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/campaigns')
def campaigns(platform=None):
    if not platform:
        platform = SMSMarketingPlatform()
    # Récupérer et afficher les campagnes
    #campaigns = platform.get_campaigns()
    return render_template('campaigns.html')
    #return render_template('campaigns.html')

@app.route('/create_campaign', methods=['GET', 'POST'])
def create_campaign():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        platform = SMSMarketingPlatform()
        name = request.form['name']
        message = request.form['message']
        scheduled_date = request.form['scheduled_date']
        platform.create_campaign(session['user_id'], name, message, scheduled_date)
        return redirect(url_for('home'))
    return render_template('create_campaign.html')

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




if __name__ == '__main__':
    app.run(debug=True)
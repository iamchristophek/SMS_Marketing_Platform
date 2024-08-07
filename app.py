from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from sms_platform import SMSMarketingPlatform


app = Flask(__name__)
app.secret_key = 'superappsecretkey' # secret key for session management to provide before using session object the app
platform = SMSMarketingPlatform()


@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('/login'))
    return render_template('dashboard.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_id = platform.authenticate_user(username, password)
        if user_id:
            session['user_id'] = user_id
            return redirect(url_for('/'))
        return render_template(url_for('login.html'), error='Invalid username or password')
    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

@app.route('/campaigns')
def campaigns():
    # Récupérer et afficher les campagnes
    campaigns = platform.get_campaigns()
    return render_template('campaigns.html', campaigns=campaigns)
    #return render_template('campaigns.html')

@app.route('/create_campaign', methods=['GET', 'POST'])
def create_campaign():
    if request.method == 'POST':
        name = request.form['name']
        message = request.form['message']
        platform.create_campaign(name, message)
        return redirect(url_for('campaigns'))
    return render_template('create_campaign.html')



if __name__ == '__main__':
    app.run(debug=True)
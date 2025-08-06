from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests
from datetime import timedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random key in production
app.permanent_session_lifetime = timedelta(days=1)  # Session expires after 1 day

# API Configuration
API_BASE_URL = 'https://routinely-positive-rattler.ngrok-free.app'
API_TIMEOUT = 10  # seconds

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'login':
            return handle_login()
        elif form_type == 'signup':
            return handle_signup()
    
    return render_template('auth.html')

def handle_login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('auth.html', error="Email and password are required")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/login",
            json={'email': email, 'password': password},
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                session.permanent = True
                session['token'] = response_data.get('data', {}).get('token')
                return check_quiz_status()
            else:
                error = response_data.get('error', 'Invalid credentials')
                return render_template('auth.html', error=error)
        else:
            return render_template('auth.html', error="Login failed. Please try again.")
            
    except requests.exceptions.RequestException as e:
        return render_template('auth.html', error="Connection error. Please try again later.")

def handle_signup():
    data = {
        'email': request.form.get('email'),
        'password': request.form.get('password'),
        'full_name': request.form.get('full_name'),
        'age': request.form.get('age', type=int),
        'gender': request.form.get('gender')
    }
    
    # Basic validation
    if not all([data['email'], data['password'], data['full_name']]):
        return render_template('auth.html', error="Please fill all required fields")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/signup",
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                session.permanent = True
                session['token'] = response_data.get('data', {}).get('token')
                return redirect(url_for('questions'))
            else:
                error = response_data.get('error', 'Signup failed. Please try again.')
                return render_template('auth.html', error=error)
        else:
            return render_template('auth.html', error="Signup failed. Please try again.")
            
    except requests.exceptions.RequestException as e:
        return render_template('auth.html', error="Connection error. Please try again later.")

def check_quiz_status():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    try:
        headers = {
            'Authorization': f"Bearer {session.get('token')}",
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f"{API_BASE_URL}/api/profile",
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                profile = response_data.get('data', {})
                if profile.get('quiz_completed', False):
                    return redirect(url_for('explore'))
                else:
                    return redirect(url_for('questions'))
    
    except requests.exceptions.RequestException:
        pass
        
    return redirect(url_for('questions'))

@app.route('/explore')
def explore():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    try:
        headers = {
            'Authorization': f"Bearer {session.get('token')}",
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f"{API_BASE_URL}/api/matches",
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        matches = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                matches = response_data.get('data', [])
        
        return render_template('explore.html', matches=matches)
    
    except requests.exceptions.RequestException:
        return render_template('explore.html', matches=[])

@app.route('/chat')
def chat():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    try:
        headers = {
            'Authorization': f"Bearer {session.get('token')}",
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f"{API_BASE_URL}/api/chats",
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        chats = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                chats = response_data.get('data', [])
        
        return render_template('chat.html', chats=chats)
    
    except requests.exceptions.RequestException:
        return render_template('chat.html', chats=[])

@app.route('/profile')
def profile():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    try:
        headers = {
            'Authorization': f"Bearer {session.get('token')}",
            'Content-Type': 'application/json'
        }
        response = requests.get(
            f"{API_BASE_URL}/api/profile",
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        profile_data = {}
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                profile_data = response_data.get('data', {})
        
        return render_template('profile.html', profile=profile_data)
    
    except requests.exceptions.RequestException:
        return render_template('profile.html', profile={})

@app.route('/questions', methods=['GET', 'POST'])
def questions():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        answers = request.form.getlist('answers[]')
        
        try:
            headers = {
                'Authorization': f"Bearer {session.get('token')}",
                'Content-Type': 'application/json'
            }
            response = requests.post(
                f"{API_BASE_URL}/api/quiz/submit",
                json={'answers': answers},
                headers=headers,
                timeout=API_TIMEOUT
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('success'):
                    return redirect(url_for('explore'))
        
        except requests.exceptions.RequestException:
            pass
    
    return render_template('questions.html')

@app.route('/logout')
def logout():
    if 'token' in session:
        try:
            headers = {
                'Authorization': f"Bearer {session.get('token')}",
                'Content-Type': 'application/json'
            }
            requests.post(
                f"{API_BASE_URL}/api/logout",
                headers=headers,
                timeout=API_TIMEOUT
            )
        except requests.exceptions.RequestException:
            pass
        
        session.pop('token', None)
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
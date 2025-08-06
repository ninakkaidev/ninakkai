from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure secret key

# API Configuration
API_BASE_URL = 'https://routinely-positive-rattler.ngrok-free.app'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        if 'login' in request.form:
            # Handle login
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Call login API
            response = requests.post(
                f"{API_BASE_URL}/api/login",
                json={'email': email, 'password': password}
            )
            
            if response.status_code == 200 and response.json().get('success'):
                session['token'] = response.json().get('data', {}).get('token')
                return check_quiz_status()
            else:
                return render_template('auth.html', error="Invalid credentials")
                
        elif 'signup' in request.form:
            # Handle signup
            data = {
                'email': request.form.get('email'),
                'password': request.form.get('password'),
                'full_name': request.form.get('full_name'),
                'age': request.form.get('age'),
                'gender': request.form.get('gender')
            }
            
            # Call signup API
            response = requests.post(
                f"{API_BASE_URL}/api/signup",
                json=data
            )
            
            if response.status_code == 200 and response.json().get('success'):
                session['token'] = response.json().get('data', {}).get('token')
                return redirect(url_for('questions'))
            else:
                return render_template('auth.html', error=response.json().get('error', 'Signup failed'))
    
    return render_template('auth.html')

def check_quiz_status():
    # Check if user has completed the quiz
    headers = {'Authorization': f"Bearer {session.get('token')}"}
    response = requests.get(f"{API_BASE_URL}/api/profile", headers=headers)
    
    if response.status_code == 200 and response.json().get('success'):
        profile = response.json().get('data', {})
        if profile.get('quiz_completed', False):
            return redirect(url_for('explore'))
        else:
            return redirect(url_for('questions'))
    return redirect(url_for('questions'))

@app.route('/login')
def login():
    return redirect(url_for('auth'))

@app.route('/explore')
def explore():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    headers = {'Authorization': f"Bearer {session.get('token')}"}
    response = requests.get(f"{API_BASE_URL}/api/matches", headers=headers)
    
    if response.status_code == 200 and response.json().get('success'):
        matches = response.json().get('data', [])
        return render_template('explore.html', matches=matches)
    return render_template('explore.html', matches=[])

@app.route('/chat')
def chat():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    headers = {'Authorization': f"Bearer {session.get('token')}"}
    response = requests.get(f"{API_BASE_URL}/api/chats", headers=headers)
    
    if response.status_code == 200 and response.json().get('success'):
        chats = response.json().get('data', [])
        return render_template('chat.html', chats=chats)
    return render_template('chat.html', chats=[])

@app.route('/profile')
def profile():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    headers = {'Authorization': f"Bearer {session.get('token')}"}
    response = requests.get(f"{API_BASE_URL}/api/profile", headers=headers)
    
    if response.status_code == 200 and response.json().get('success'):
        profile_data = response.json().get('data', {})
        return render_template('profile.html', profile=profile_data)
    return render_template('profile.html', profile={})

@app.route('/questions', methods=['GET', 'POST'])
def questions():
    if 'token' not in session:
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        # Submit quiz answers
        answers = request.form.getlist('answers[]')
        headers = {'Authorization': f"Bearer {session.get('token')}"}
        response = requests.post(
            f"{API_BASE_URL}/api/quiz/submit",
            json={'answers': answers},
            headers=headers
        )
        
        if response.status_code == 200 and response.json().get('success'):
            return redirect(url_for('explore'))
    
    return render_template('questions.html')

@app.route('/logout')
def logout():
    if 'token' in session:
        headers = {'Authorization': f"Bearer {session.get('token')}"}
        requests.post(f"{API_BASE_URL}/api/logout", headers=headers)
        session.pop('token', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
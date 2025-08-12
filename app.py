from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
import requests
from datetime import timedelta
import logging
from urllib.parse import urljoin
import re
import os

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()  # Secure random key
app.permanent_session_lifetime = timedelta(days=1)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = 'https://routinely-positive-rattler.ngrok-free.app'
API_TIMEOUT = 10  # seconds

@app.route('/')
def index():
    logger.debug(f"Session in index: {session}")
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    logger.debug(f"Session in auth: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'login':
            return handle_login()
        elif form_type == 'signup':
            return handle_signup()
        elif form_type == 'resend_verification':
            return resend_verification()
        
        return jsonify({'success': False, 'error': 'Invalid form type'}), 400
    
    email_verified = request.cookies.get('email_verified') == '1'
    verification_pending = session.get('verification_pending', False)
    email = session.get('email', '')
    
    if email_verified:
        verification_success = True
        resp = make_response(render_template('auth.html', 
                                            verification_sent=verification_pending,
                                            verification_success=verification_success,
                                            email=email))
        resp.set_cookie('email_verified', '', expires=0)
        return resp
    
    return render_template('auth.html', 
                          verification_sent=verification_pending,
                          verification_success=False,
                          email=email)

def handle_login():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        response = requests.post(
            urljoin(API_BASE_URL, '/api/login'),
            json={'email': email, 'password': password},
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response from API: {response.text}")
            return jsonify({'success': False, 'error': 'Invalid response from server'}), 500
        
        if response.status_code == 200:
            if response_data.get('success'):
                session.permanent = True
                session['email'] = email
                session['user_id'] = response_data.get('user', {}).get('id')  # Use 'id' from API
                logger.debug(f"Session set after login: {session}")
                
                return jsonify({
                    'success': True,
                    'redirect': url_for('explore') if response_data.get('quiz_completed', False) else url_for('questions')
                })
            else:
                error = response_data.get('error', 'Invalid credentials')
                return jsonify({'success': False, 'error': error}), 401
        elif response.status_code == 401 and response_data.get('verification_required'):
            session['email'] = email
            session['verification_pending'] = True
            return jsonify({
                'success': False,
                'verification_required': True,
                'email': email,
                'message': 'Please verify your email before logging in'
            })
        else:
            error = response_data.get('error', 'Login failed. Please try again.')
            return jsonify({'success': False, 'error': error}), response.status_code
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Login request failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Connection error. Please try again later.'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in login: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

def handle_signup():
    try:
        data = {
            'email': request.form.get('email'),
            'password': request.form.get('password'),
            'full_name': request.form.get('full_name'),
            'age': request.form.get('age', type=int),
            'gender': request.form.get('gender')
        }
        
        if not all([data['email'], data['password'], data['full_name']]):
            return jsonify({'success': False, 'error': 'Please fill all required fields'}), 400
        
        if not validate_email(data['email']):
            return jsonify({'success': False, 'error': 'Please enter a valid email address'}), 400
        
        if len(data['password']) < 8:
            return jsonify({'success': False, 'error': 'Password must be at least 8 characters'}), 400
        
        response = requests.post(
            urljoin(API_BASE_URL, '/api/signup'),
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response from API: {response.text}")
            return jsonify({'success': False, 'error': 'Invalid response from server'}), 500
        
        if response.status_code == 201:
            if response_data.get('success'):
                session.permanent = True
                session['email'] = data['email']
                session['user_id'] = response_data.get('user_id')  # Use 'user_id' from API
                session['verification_pending'] = True
                logger.debug(f"Session set after signup: {session}")
                
                return jsonify({
                    'success': True,
                    'verification_required': True,
                    'email': data['email'],
                    'message': 'Verification email sent! Please check your inbox.'
                })
            else:
                error = response_data.get('error', 'Signup failed. Please try again.')
                return jsonify({'success': False, 'error': error}), 400
        else:
            error = response_data.get('error', 'Signup failed. Please try again.')
            return jsonify({'success': False, 'error': error}), response.status_code
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Signup request failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Connection error. Please try again later.'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in signup: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

def resend_verification():
    try:
        email = request.json.get('email') or session.get('email')
        if not email:
            return jsonify({'success': False, 'error': 'No email provided'}), 400
        
        response = requests.post(
            urljoin(API_BASE_URL, '/api/resend-verification'),
            json={'email': email},
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response from API: {response.text}")
            return jsonify({'success': False, 'error': 'Invalid response from server'}), 500
        
        if response.status_code == 200:
            session['verification_pending'] = True
            session['email'] = email
            return jsonify({
                'success': True,
                'message': 'Verification email resent successfully!'
            })
        else:
            error = response_data.get('error', 'Failed to resend verification email.')
            return jsonify({'success': False, 'error': error}), response.status_code
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Resend verification request failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Connection error. Please try again later.'}), 500
    except Exception as e:
        logger.error(f"Unexpected error in resend verification: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

def validate_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def check_quiz_status():
    try:
        if 'user_id' not in session:
            logger.debug("No user_id in session for quiz status check")
            return {'quiz_completed': False}
        
        headers = {'Content-Type': 'application/json'}
        response = requests.get(
            urljoin(API_BASE_URL, f"/api/profile"),
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                return {'quiz_completed': response_data.get('quiz_completed', False)}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Quiz status check failed: {str(e)}")
    
    return {'quiz_completed': False}

@app.route('/api/check-session', methods=['GET'])
def check_session():
    logger.debug(f"Session in check_session: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No active session'}), 401
    return jsonify({'success': True, 'user_id': session.get('user_id'), 'email': session.get('email')})

@app.route('/verify-email')
def verify_email_endpoint():
    logger.debug(f"Session in verify-email: {session}")
    token = request.args.get('token')
    if not token:
        return redirect(url_for('auth', error='Invalid verification link'))
    
    try:
        response = requests.post(
            urljoin(API_BASE_URL, '/api/verify-email'),
            json={'token': token},
            headers={'Content-Type': 'application/json'},
            timeout=API_TIMEOUT
        )
        
        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response from API: {response.text}")
            return redirect(url_for('auth', error='Invalid response from server'))
        
        if response.status_code == 200 and response_data.get('success'):
            resp = make_response(redirect(url_for('auth')))
            resp.set_cookie('email_verified', '1', max_age=60)
            return resp
        else:
            error = response_data.get('error', 'Verification failed. Please try again.')
            return redirect(url_for('auth', error=error))
    except requests.exceptions.RequestException as e:
        logger.error(f"Verification API request failed: {str(e)}")
        return redirect(url_for('auth', error='Verification service unavailable. Please try again later.'))

@app.route('/explore')
def explore():
    logger.debug(f"Session in explore: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /explore")
        return redirect(url_for('auth'))
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.get(
            urljoin(API_BASE_URL, '/api/matches'),
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        matches = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                matches = response_data.get('matches', [])
        
        return render_template('explore.html', matches=matches)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Explore request failed: {str(e)}")
        return render_template('explore.html', matches=[])

@app.route('/chat')
def chat():
    logger.debug(f"Session in chat: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /chat")
        return redirect(url_for('auth'))
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.get(
            urljoin(API_BASE_URL, '/api/chats'),
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        chats = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                chats = response_data.get('chats', [])
        
        return render_template('chat.html', chats=chats)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Chat request failed: {str(e)}")
        return render_template('chat.html', chats=[])

@app.route('/profile')
def profile():
    logger.debug(f"Session in profile: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /profile")
        return redirect(url_for('auth'))
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.get(
            urljoin(API_BASE_URL, '/api/profile'),
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        profile_data = {}
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                profile_data = response_data.get('profile', {})
        
        return render_template('profile.html', profile=profile_data)
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Profile request failed: {str(e)}")
        return render_template('profile.html', profile={})

@app.route('/questions', methods=['GET'])
def questions():
    logger.debug(f"Session in questions: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /questions")
        return redirect(url_for('auth'))
    
    quiz_status = check_quiz_status()
    if quiz_status.get('quiz_completed', False):
        return redirect(url_for('explore'))
    
    return render_template('questions.html')

@app.route('/api/quiz/submit', methods=['POST'])
def submit_quiz():
    logger.debug(f"Session in submit_quiz: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        logger.error("No user_id in session")
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'success': False, 'error': 'Missing answers data'}), 400
    
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            urljoin(API_BASE_URL, '/api/quiz/submit'),
            json={'answers': data['answers'], 'user_id': session.get('user_id')},
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Invalid JSON response from API: {response.text}")
            return jsonify({'success': False, 'error': 'Invalid response from server'}), 500
        
        if response.status_code == 200:
            if response_data.get('success'):
                return jsonify({'success': True})
            else:
                error = response_data.get('error', 'Quiz submission failed')
                return jsonify({'success': False, 'error': error}), 400
        else:
            error = response_data.get('error', 'Quiz submission failed')
            return jsonify({'success': False, 'error': error}), response.status_code
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Quiz submission failed: {str(e)}")
        return jsonify({'success': False, 'error': 'Connection error. Please try again later.'}), 500

@app.route('/logout')
def logout():
    logger.debug(f"Session in logout: {session}")
    if 'user_id' in session:
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                urljoin(API_BASE_URL, '/api/logout'),
                headers=headers,
                timeout=API_TIMEOUT
            )
            logger.debug(f"Logout API response: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Logout request failed: {str(e)}")
        
        session.clear()
        return redirect(url_for('index'))
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
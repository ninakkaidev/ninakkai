from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
import requests
from datetime import timedelta
import logging
from urllib.parse import urljoin
import re
import os
from flask_cors import CORS

app = Flask(__name__)
# Use environment variable for secret key, fallback to a secure default
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secure-fixed-secret-key-here')  # Replace with a secure key
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(
    SESSION_COOKIE_SAMESITE='None',  # Align with API-side for cross-origin requests
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV', 'development') != 'development',  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_NAME='for_you_session',  # Use same cookie name as API
    SESSION_COOKIE_PATH='/'
)

# Configure CORS
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": [
            'https://routinely-positive-rattler.ngrok-free.app',
            'http://localhost:5050',
            'https://client1-ez5pxwg0k-ashiks-projects-05a199d3.vercel.app',
            'https://client1-amber.vercel.app',
            'https://www.ninakkai.com'
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Session-ID"],
        "expose_headers": ["Set-Cookie"],
        "supports_credentials": True
    }
})

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# API Configuration
API_BASE_URL = 'https://routinely-positive-rattler.ngrok-free.app'  # Update with correct API URL
API_TIMEOUT = 10  # seconds

# Temporary mock signup endpoint for testing (remove in production)
@app.route('/api/signup', methods=['POST'])
def mock_signup():
    data = request.get_json()
    logger.debug(f"Mock signup called with data: {data}")
    return jsonify({
        'success': True,
        'user_id': 'mock_user_id_123',
        'message': 'Mock signup successful. Please verify your email.'
    }), 201

@app.after_request
def log_response(response):
    logger.debug(f"Response - Route: {request.path}, Status: {response.status_code}, Set-Cookie: {response.headers.get('Set-Cookie', 'None')}")
    return response

@app.before_request
def log_session_info():
    logger.debug(f"Before request - Route: {request.path}, Session: {session}, Cookies: {request.cookies}, Secret Key: {app.secret_key[:4]}...")
    logger.debug(f"Session SID: {session.sid if hasattr(session, 'sid') else 'No SID'}")

@app.route('/')
def index():
    logger.debug(f"Session in index: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    return render_template('index.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    logger.debug(f"Session in auth: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    error = None
    success = None
    verification_sent = False
    verification_success = False
    email = session.get('email', '')

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            
            if not email or not password:
                error = 'Email and password are required'
            else:
                try:
                    response = requests.post(
                        urljoin(API_BASE_URL, '/api/login'),  # Verify endpoint
                        json={'email': email, 'password': password},
                        headers={'Content-Type': 'application/json'},
                        timeout=API_TIMEOUT
                    )
                    logger.debug(f"API login response: {response.status_code}, {response.text}")
                    
                    response_data = response.json()
                    
                    if response.status_code == 200 and response_data.get('success'):
                        session.permanent = True
                        session['email'] = email
                        session['user_id'] = response_data.get('user', {}).get('id')
                        session.modified = True
                        logger.debug(f"Session set after login: {session}, SID: {session.sid if hasattr(session, 'sid') else 'No SID'}")
                        resp = make_response(redirect(url_for('questions')))
                        resp.set_cookie('for_you_session', session.sid, max_age=86400, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
                        logger.debug(f"Login response headers: {resp.headers}")
                        quiz_completed = response_data.get('quiz_completed', False)
                        return resp if not quiz_completed else make_response(redirect(url_for('explore')))
                    elif response.status_code == 401 and response_data.get('verification_required'):
                        session['email'] = email
                        session['verification_pending'] = True
                        session.modified = True
                        verification_sent = True
                        error = response_data.get('message', 'Please verify your email before logging in')
                    else:
                        error = response_data.get('error', 'Login failed. Please try again.')
                except Exception as e:
                    logger.error(f"Login error: {str(e)}")
                    error = 'An error occurred during login. Please try again.'
        
        elif form_type == 'signup':
            data = {
                'email': request.form.get('email'),
                'password': request.form.get('password'),
                'full_name': request.form.get('full_name'),
                'age': request.form.get('age', type=int),
                'gender': request.form.get('gender')
            }
            
            if not all([data['email'], data['password'], data['full_name']]):
                error = 'Please fill all required fields'
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
                error = 'Please enter a valid email address'
            elif len(data['password']) < 8:
                error = 'Password must be at least 8 characters'
            else:
                try:
                    # Use mock endpoint for local testing; replace with actual endpoint
                    endpoint = '/api/signup'  # Update if endpoint is different (e.g., '/api/register')
                    response = requests.post(
                        urljoin(API_BASE_URL, endpoint),
                        json=data,
                        headers={'Content-Type': 'application/json'},
                        timeout=API_TIMEOUT
                    )
                    logger.debug(f"API signup response: {response.status_code}, {response.text}")
                    
                    response_data = response.json()
                    
                    if response.status_code == 201 and response_data.get('success'):
                        session.permanent = True
                        session['email'] = data['email']
                        session['user_id'] = response_data.get('user_id')
                        session['verification_pending'] = True
                        session.modified = True
                        verification_sent = True
                        success = response_data.get('message', 'Verification email sent! Please check your inbox.')
                        resp = make_response(render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, email=email))
                        resp.set_cookie('for_you_session', session.sid, max_age=86400, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
                        logger.debug(f"Session after signup: {session}, SID: {session.sid if hasattr(session, 'sid') else 'No SID'}")
                        return resp
                    else:
                        error = response_data.get('error', f'Signup failed with status {response.status_code}: {response.text}')
                except Exception as e:
                    logger.error(f"Signup error: {str(e)}")
                    error = 'An error occurred during signup. Please try again.'
        
        elif form_type == 'resend_verification':
            return resend_verification()

    if request.cookies.get('email_verified') == '1':
        verification_success = True
        resp = make_response(render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, email=email))
        resp.set_cookie('email_verified', '', expires=0)
        return resp

    return render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, email=email)

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
        logger.debug(f"API resend-verification response: {response.status_code}, {response.text}")
        
        response_data = response.json()
        
        if response.status_code == 200:
            session['verification_pending'] = True
            session['email'] = email
            session.modified = True
            logger.debug(f"Session set after resend: {session}, SID: {session.sid if hasattr(session, 'sid') else 'No SID'}")
            resp = make_response(jsonify({
                'success': True,
                'message': 'Verification email resent successfully!'
            }))
            resp.set_cookie('for_you_session', session.sid, max_age=86400, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
            return resp
        else:
            error = response_data.get('error', 'Failed to resend verification email.')
            return jsonify({'success': False, 'error': error}), response.status_code
            
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

def check_quiz_status():
    try:
        if 'user_id' not in session:
            logger.debug("No user_id in session for quiz status check")
            return {'quiz_completed': False}
        
        headers = {'Content-Type': 'application/json'}
        response = requests.get(
            urljoin(API_BASE_URL, f"/api/profile"),
            json={'user_id': session.get('user_id')},
            headers=headers,
            timeout=API_TIMEOUT
        )
        logger.debug(f"API profile response: {response.status_code}, {response.text}")
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                return {'quiz_completed': response_data.get('quiz_completed', False)}
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Quiz status check failed: {str(e)}")
    
    return {'quiz_completed': False}

@app.route('/api/check-quiz-status', methods=['GET'])
def check_quiz_status_endpoint():
    logger.debug(f"Session in check_quiz_status: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    result = check_quiz_status()
    return jsonify(result)

@app.route('/api/check-session', methods=['GET'])
def check_session():
    logger.debug(f"Session in check_session: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'No active session'}), 401
    return jsonify({'success': True, 'user_id': session.get('user_id'), 'email': session.get('email')})

@app.route('/debug-session')
def debug_session():
    return jsonify({
        'session': dict(session),
        'cookies': dict(request.cookies),
        'sid': session.sid if hasattr(session, 'sid') else 'No SID'
    })

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
        logger.debug(f"API verify-email response: {response.status_code}, {response.text}")
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('success'):
            session.pop('verification_pending', None)
            session.modified = True
            resp = make_response(redirect(url_for('auth')))
            resp.set_cookie('email_verified', '1', max_age=60)
            resp.set_cookie('for_you_session', session.sid, max_age=86400, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
            return resp
        else:
            error = response_data.get('error', 'Verification failed. Please try again.')
            return redirect(url_for('auth', error=error))
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        return redirect(url_for('auth', error='An unexpected error occurred during verification.'))

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
            json={'user_id': session.get('user_id')},
            headers=headers,
            timeout=API_TIMEOUT
        )
        logger.debug(f"API matches response: {response.status_code}, {response.text}")
        
        matches = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                matches = response_data.get('matches', [])
        
        return render_template('explore.html', matches=matches)
    
    except Exception as e:
        logger.error(f"Explore error: {str(e)}")
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
            json={'user_id': session.get('user_id')},
            headers=headers,
            timeout=API_TIMEOUT
        )
        logger.debug(f"API chats response: {response.status_code}, {response.text}")
        
        chats = []
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                chats = response_data.get('chats', [])
        
        return render_template('chat.html', chats=chats)
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
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
            json={'user_id': session.get('user_id')},
            headers=headers,
            timeout=API_TIMEOUT
        )
        logger.debug(f"API profile response: {response.status_code}, {response.text}")
        
        profile_data = {}
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                profile_data = response_data.get('profile', {})
        
        return render_template('profile.html', profile=profile_data)
    
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
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
        logger.error("Authentication required - no user_id in session for submit_quiz")
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
        logger.debug(f"API quiz submit response: {response.status_code}, {response.text}")
        
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('success'):
            return jsonify({'success': True})
        else:
            error = response_data.get('error', 'Quiz submission failed')
            return jsonify({'success': False, 'error': error}), 400
    except Exception as e:
        logger.error(f"Quiz submission error: {str(e)}")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@app.route('/logout')
def logout():
    logger.debug(f"Session in logout: {session}")
    if 'user_id' in session:
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(
                urljoin(API_BASE_URL, '/api/logout'),
                json={'user_id': session.get('user_id')},
                headers=headers,
                timeout=API_TIMEOUT
            )
            logger.debug(f"API logout response: {response.status_code}, {response.text}")
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
        
        session.clear()
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('for_you_session', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
        return resp
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5050)
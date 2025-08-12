from flask import Flask, request, jsonify, session, redirect, url_for, make_response
from firebase_service import FirebaseService
from mongo_service import MongoService
from functools import wraps
import os
import logging
from datetime import timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer
from bson import ObjectId
from flask_cors import CORS

app = Flask(__name__)

# Enhanced CORS configuration for your client domain
CORS(app, 
     supports_credentials=True,
     resources={
         r"/*": {
             "origins": ["https://ninakkai.com"],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "expose_headers": ["Set-Cookie"],
             "supports_credentials": True
         }
     })

# Session configuration
app.secret_key = os.urandom(24)
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_NAME='for_you_session',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1)
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Services
firebase = FirebaseService()
mongo = MongoService()

# Email Configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = os.getenv('SMTP_USERNAME', 'ninakkaiforyou@gmail.com')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', 'porz cqqt bumr wdgj')
SENDER_EMAIL = 'ninakkaiforyou@gmail.com'
APP_DOMAIN = os.getenv('APP_DOMAIN', 'https://ninakkai.com')

# Initialize the serializer for generating tokens
serializer = URLSafeTimedSerializer(app.secret_key)

def send_verification_email(email, verification_token):
    try:
        verification_link = f"{APP_DOMAIN}/verify-email?token={verification_token}"
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = email
        msg['Subject'] = "Verify Your Email Address"
        
        html = f"""
        <html>
          <body>
            <h2>നിനക്കായി-ForYou Email Verification</h2>
            <p>Please click the button below to verify your email address:</p>
            <a href="{verification_link}" style="background-color: #4CAF50; color: white; padding: 14px 20px; text-align: center; text-decoration: none; display: inline-block; border-radius: 5px;">
              Verify Email
            </a>
            <p>If you didn't request this, please ignore this email.</p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(html, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        return False

def generate_verification_token(email):
    return serializer.dumps(email, salt='email-verification')

def verify_token(token, expiration=3600):
    try:
        email = serializer.loads(
            token,
            salt='email-verification',
            max_age=expiration
        )
        return email
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        logger.debug(f"Session in {f.__name__}: {session}")
        logger.debug(f"Incoming cookies in {f.__name__}: {request.cookies}")
        if 'user_id' not in session:
            logger.error(f"Authentication required - no user_id in session for {f.__name__}")
            response = make_response(jsonify({'success': False, 'error': 'Authentication required'}))
            response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return jsonify({'message': 'Welcome to നിനക്കായി-ForYou API'})

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        required_fields = ['email', 'password', 'full_name']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        result = mongo.create_user(
            data['email'],
            data['password'],
            data['full_name'],
            data.get('age'),
            data.get('gender')
        )
        
        if not result['success']:
            return jsonify(result), 400
            
        verification_token = generate_verification_token(data['email'])
        if not send_verification_email(data['email'], verification_token):
            return jsonify({
                'success': False,
                'error': 'Failed to send verification email'
            }), 500
        
        session.permanent = True
        session['user_id'] = result['user']['id']
        session['email'] = data['email']
        logger.debug(f"Session set after signup: {session}")
        
        response = make_response(jsonify({
            'success': True,
            'message': 'Account created. Verification email sent.',
            'user_id': result['user']['id']
        }))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 201
        
    except Exception as e:
        logger.error(f"Signup error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'An error occurred during signup'}), 500

@app.route('/api/verify-email', methods=['POST'])
def verify_email():
    try:
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({'success': False, 'error': 'Missing verification token'}), 400
        
        email = verify_token(data['token'])
        if not email:
            return jsonify({'success': False, 'error': 'Invalid or expired verification token'}), 400
        
        user_data = mongo.get_user_by_email(email)
        if not user_data:
            return jsonify({'success': False, 'error': 'User not found'}), 404
            
        mongo.update_user(user_data['id'], {'email_verified': True})
        firebase.update_profile(user_data['id'], {'email_verified': True})
        
        response = make_response(jsonify({
            'success': True,
            'message': 'Email verified successfully'
        }))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': 'An error occurred during verification'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'success': False, 'error': 'Missing email or password'}), 400

        result = mongo.verify_user(data['email'], data['password'])
        
        if not result['success']:
            if result.get('needs_verification'):
                return jsonify({
                    'success': False,
                    'verification_required': True,
                    'message': 'Please verify your email before logging in'
                }), 401
            return jsonify(result), 401

        session.permanent = True
        session['user_id'] = result['user']['id']
        session['email'] = data['email']
        logger.debug(f"Session set after login: {session}")
        
        firebase_user = firebase.get_user_profile(result['user']['id'])
        quiz_completed = firebase_user.get('profile_complete', False) if firebase_user else False
        
        response = make_response(jsonify({
            'success': True,
            'user': result['user'],
            'quiz_completed': quiz_completed
        }))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred during login'}), 500

@app.route('/api/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json()
        email = data.get('email')
        if not email:
            return jsonify({'success': False, 'error': 'No email provided'}), 400
        
        verification_token = generate_verification_token(email)
        if not send_verification_email(email, verification_token):
            return jsonify({
                'success': False,
                'error': 'Failed to resend verification email'
            }), 500
        
        response = make_response(jsonify({
            'success': True,
            'message': 'Verification email resent successfully'
        }))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while resending verification'}), 500

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    try:
        session.clear()
        response = make_response(jsonify({'success': True, 'message': 'Logged out successfully'}))
        response.set_cookie('for_you_session', '', expires=0)
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred during logout'}), 500

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    try:
        user_id = session['user_id']
        profile = firebase.get_user_profile(user_id)
        if profile:
            response = make_response(jsonify({
                'success': True, 
                'profile': profile,
                'quiz_completed': profile.get('profile_complete', False)
            }))
            response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            return response, 200
        return jsonify({'success': False, 'error': 'Profile not found'}), 404
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while fetching profile'}), 500

@app.route('/api/profile/update', methods=['POST'])
@login_required
def update_profile():
    try:
        user_id = session['user_id']
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        allowed_fields = ['full_name', 'age', 'gender', 'bio', 'interests', 'location']
        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}
        
        result = firebase.update_profile(user_id, update_data)
        response = make_response(jsonify(result))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200 if result['success'] else 400
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while updating profile'}), 500

@app.route('/api/quiz/submit', methods=['OPTIONS'])
def quiz_options():
    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "https://ninakkai.com")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "POST")
    response.headers.add("Access-Control-Allow-Credentials", "true")
    return response

@app.route('/api/quiz/submit', methods=['POST'])
@login_required
def submit_quiz():
    logger.debug(f"Incoming cookies: {request.cookies}")
    logger.debug(f"Session data: {session}")
    if 'user_id' not in session:
        response = make_response(jsonify({'success': False, 'error': 'Unauthorized'}))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 401
    
    data = request.get_json()
    if not data or 'answers' not in data:
        return jsonify({'success': False, 'error': 'Missing answers data'}), 400

    user_id = session['user_id']
    logger.debug(f"Processing quiz for user: {user_id}")
    
    result = mongo.save_quiz_results(user_id, data['answers'])
    
    if not result['success']:
        return jsonify(result), 400

    firebase.update_profile(user_id, {
        'profile_complete': True,
        'personality_profile': result.get('scores', {})
    })
    
    response = make_response(jsonify({
        'success': True,
        'message': 'Quiz submitted successfully',
        'redirect_url': '/explore',
        'personality_type': result.get('personality_type', ''),
        'compatibility_matches': result.get('compatibility_matches', [])
    }))
    response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response, 200
        
@app.route('/api/matches', methods=['GET'])
@login_required
def get_matches():
    try:
        user_id = session['user_id']
        limit = request.args.get('limit', default=10, type=int)

        matches = firebase.find_matches(user_id, limit)
        response = make_response(jsonify({'success': True, 'matches': matches}))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    except Exception as e:
        logger.error(f"Get matches error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while fetching matches'}), 500

@app.route('/api/chat/create', methods=['POST'])
@login_required
def create_chat():
    try:
        user_id = session['user_id']
        data = request.get_json()
        
        if not data or 'other_user_id' not in data:
            return jsonify({'success': False, 'error': 'Missing other user ID'}), 400
        
        result = firebase.create_chat(user_id, data['other_user_id'])
        response = make_response(jsonify(result))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200 if result['success'] else 400
    except Exception as e:
        logger.error(f"Create chat error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while creating chat'}), 500

@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    try:
        user_id = session['user_id']
        data = request.get_json()
        
        if not data or 'chat_id' not in data or 'message' not in data:
            return jsonify({'success': False, 'error': 'Missing chat ID or message'}), 400
        
        result = firebase.send_message(data['chat_id'], user_id, data['message'])
        response = make_response(jsonify(result))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200 if result['success'] else 400
    except Exception as e:
        logger.error(f"Send message error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while sending message'}), 500

@app.route('/api/chat/messages', methods=['GET'])
@login_required
def get_chat_messages():
    try:
        chat_id = request.args.get('chat_id')
        limit = request.args.get('limit', default=50, type=int)
        
        if not chat_id:
            return jsonify({'success': False, 'error': 'Missing chat ID'}), 400
        
        messages = firebase.get_chat_messages(chat_id, limit)
        response = make_response(jsonify({'success': True, 'messages': messages}))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    except Exception as e:
        logger.error(f"Get messages error: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while fetching messages'}), 500

@app.route('/api/chats', methods=['GET'])
@login_required
def get_user_chats():
    try:
        user_id = session['user_id']
        chats = firebase.get_user_chats(user_id)
        response = make_response(jsonify({'success': True, 'chats': chats}))
        response.headers['Access-Control-Allow-Origin'] = 'https://ninakkai.com'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response, 200
    except Exception as e:
        logger.error(f"Get chats error: {str(e)}") 
        return jsonify({'success': False, 'error': 'An error occurred while fetching chats'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5050)
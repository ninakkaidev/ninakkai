from flask import Flask, request, make_response, session, render_template, redirect, url_for, send_from_directory
from pymongo import MongoClient
from typing import Dict, Any, Optional, List
from bson import ObjectId
import os
import logging
from datetime import datetime, timedelta, timezone
import re
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.security import generate_password_hash, check_password_hash

# Configure logging
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            static_url_path='/static',
            static_folder='static',
            template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secure-fixed-secret-key-here')
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(
    SESSION_COOKIE_SAMESITE='None',
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV', 'development') != 'development',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_NAME='for_you_session',
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_DOMAIN=None
)

class MongoService:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI', "mongodb+srv://ninakkaiforyou:9t2GADiJUf8xFhDZ@cluster0.fdoiudh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.client = MongoClient(self.uri)
        try:
            self.client.admin.command('ping')
            logger.info("MongoDB connection successful")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
        self.db = self.client['ninakkai']
        self.users = self.db['users']
        self.quiz_results = self.db['quiz_results']

    def create_user(self, email: str, password: str, full_name: str, age: int = None, gender: str = None) -> Dict[str, Any]:
        try:
            hashed_password = generate_password_hash(password)
            verification_token = secrets.token_urlsafe(32)
            user_data = {
                'email': email,
                'password': hashed_password,
                'full_name': full_name,
                'age': age,
                'gender': gender,
                'profile_complete': False,
                'email_verified': False,
                'verification_token': verification_token,
                'created_at': datetime.now(timezone.utc)
            }
            result = self.users.insert_one(user_data)
            return {
                'success': True,
                'user': {
                    'id': str(result.inserted_id),
                    'email': email,
                    'full_name': full_name,
                    'verification_token': verification_token
                }
            }
        except Exception as e:
            logger.error(f"Create user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        try:
            user = self.users.find_one({'email': email})
            if user:
                user['id'] = str(user['_id'])
                del user['_id']
                return user
            return None
        except Exception as e:
            logger.error(f"Get user error: {str(e)}")
            return None

    def get_user_by_verification_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            user = self.users.find_one({'verification_token': token})
            if user:
                user['id'] = str(user['_id'])
                del user['_id']
                return user
            return None
        except Exception as e:
            logger.error(f"Get user by verification token error: {str(e)}")
            return None

    def verify_user(self, email: str, password: str) -> Dict[str, Any]:
        try:
            user = self.users.find_one({'email': email})
            if not user:
                return {'success': False, 'error': 'User not found'}
            if not check_password_hash(user['password'], password):
                return {'success': False, 'error': 'Invalid password'}
            if not user.get('email_verified', False):
                return {
                    'success': False,
                    'error': 'Email not verified',
                    'needs_verification': True
                }
            user['id'] = str(user['_id'])
            del user['_id']
            del user['password']
            return {
                'success': True,
                'user': user
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def verify_email(self, token: str) -> Dict[str, Any]:
        try:
            user = self.get_user_by_verification_token(token)
            if not user:
                return {'success': False, 'error': 'Invalid or expired verification token'}
            result = self.users.update_one(
                {'_id': ObjectId(user['id'])},
                {'$set': {'email_verified': True}, '$unset': {'verification_token': ''}}
            )
            return {'success': result.modified_count > 0, 'email': user['email']}
        except Exception as e:
            logger.error(f"Verify email error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': update_data}
            )
            return {'success': result.modified_count > 0}
        except Exception as e:
            logger.error(f"Update user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def update_user_by_email(self, email: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = self.users.update_one(
                {'email': email},
                {'$set': update_data}
            )
            return {'success': result.modified_count > 0}
        except Exception as e:
            logger.error(f"Update user by email error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def save_quiz_results(self, user_id: str, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            scores = self._calculate_scores(quiz_data['answers'])
            quiz_result = {
                'user_id': user_id,
                'quiz_data': quiz_data,
                'scores': scores,
                'completed_at': datetime.now(timezone.utc)
            }
            result = self.quiz_results.insert_one(quiz_result)
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'profile_complete': True}}
            )
            return {
                'success': True,
                'result_id': str(result.inserted_id),
                'scores': scores
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_quiz_results(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.quiz_results.find_one({'user_id': user_id}, sort=[('completed_at', -1)])
            if result:
                result['id'] = str(result['_id'])
                del result['_id']
                return result
            return None
        except Exception as e:
            logger.error(f"Get quiz results error: {str(e)}")
            return None

    def _calculate_scores(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        type_counts = {}
        mandatory_answers = answers[:10]
        for answer in mandatory_answers:
            answer_type = answer['type']
            type_counts[answer_type] = type_counts.get(answer_type, 0) + 1
        if len(set(type_counts.values())) < len(type_counts):
            q2_answer = answers[1]
            ranked_types = self._parse_ranked_types(q2_answer['answer'])
            tied_types = [t for t, cnt in type_counts.items() if cnt == max(type_counts.values())]
            dominant_type = self._resolve_tie_with_ranking(tied_types, ranked_types)
        else:
            dominant_type = max(type_counts, key=type_counts.get)
        keeper_seeker = self._determine_keeper_seeker(answers[10:13] if len(answers) > 10 else None)
        optional_answers = answers[13:] if len(answers) > 13 else []
        optional_boosts = self._calculate_optional_boosts(dominant_type, optional_answers)
        total_mandatory = sum(type_counts.values())
        dominant_score = type_counts.get(dominant_type, 0)
        dominant_percentage = int((dominant_score / total_mandatory) * 100)
        secondary_type = None
        secondary_score = 0
        secondary_percentage = 0
        if len(type_counts) > 1:
            temp_counts = type_counts.copy()
            temp_counts.pop(dominant_type)
            secondary_type = max(temp_counts, key=temp_counts.get)
            secondary_score = temp_counts[secondary_type]
            secondary_percentage = int((secondary_score / total_mandatory) * 100)
        profile = {
            'dominant_type': dominant_type,
            'dominant_score': dominant_score,
            'dominant_percentage': dominant_percentage,
            'secondary_type': secondary_type,
            'secondary_score': secondary_score,
            'secondary_percentage': secondary_percentage,
            'optional_traits_boost': optional_boosts,
            'type_counts': type_counts
        }
        if keeper_seeker:
            profile['keeper_seeker_type'] = keeper_seeker
        return profile

    def _parse_ranked_types(self, ranked_answer: str) -> List[str]:
        if not ranked_answer.startswith("Ranked:"):
            return []
        parts = [p.strip() for p in ranked_answer.split("Ranked:")[1].split(",")]
        ordered_items = []
        for part in parts:
            item = part.split(".", 1)[1].strip() if "." in part else part.strip()
            ordered_items.append(item)
        item_to_type = {
            "Trust": "🛡️ Protector",
            "Emotional connection": "🌿 Nurturer",
            "Shared goals": "👂 Listener",
            "Physical intimacy": "💘 Romantic"
        }
        return [item_to_type.get(item, "") for item in ordered_items if item in item_to_type]

    def _resolve_tie_with_ranking(self, tied_types: List[str], ranked_types: List[str]) -> str:
        for type_ in ranked_types:
            if type_ in tied_types:
                return type_
        return tied_types[0]

    def _determine_keeper_seeker(self, answers: List[Dict[str, Any]]) -> Optional[str]:
        if not answers or len(answers) < 3:
            return None
        keeper_seeker_map = {
            "A": "Keeper",
            "B": "Seeker",
            "C": "Keeper",
            "D": "Seeker"
        }
        keeper_count = 0
        seeker_count = 0
        for answer in answers:
            classification = keeper_seeker_map.get(answer['answer'][0], None)
            if classification == "Keeper":
                keeper_count += 1
            elif classification == "Seeker":
                seeker_count += 1
        if keeper_count >= 2:
            return "Keeper"
        elif seeker_count >= 2:
            return "Seeker"
        return None

    def _calculate_optional_boosts(self, dominant_type: str, optional_answers: List[Dict[str, Any]]) -> Dict[str, int]:
        boosts = {}
        for answer in optional_answers:
            answer_type = answer['type']
            if answer_type == dominant_type:
                boosts[dominant_type] = boosts.get(dominant_type, 0) + 1
            elif answer_type in boosts:
                boosts[answer_type] += 1
        return boosts

mongo_service = MongoService()

def send_verification_email(email: str, verification_token: str) -> Dict[str, Any]:
    try:
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_user = 'ninakkaiforyou@gmail.com'
        smtp_password = os.environ.get('SMTP_PASSWORD', 'porz cqqt bumr wdgj')
        verification_url = f"https://www.ninakkai.com/verify-email?token={verification_token}"
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email
        msg['Subject'] = 'Verify Your Email - Ninakkai'
        body = f"""
        Hello,

        Thank you for signing up with Ninakkai! Please verify your email by clicking the link below:

        {verification_url}

        If you did not sign up for this account, please ignore this email.

        Best regards,
        The Ninakkai Team
        """
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, email, msg.as_string())
        logger.info(f"Verification email sent to {email}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {str(e)}")
        return {'success': False, 'error': str(e)}

@app.after_request
def log_response(response):
    logger.debug(f"Response - Route: {request.path}, Status: {response.status_code}, Set-Cookie: {response.headers.get('Set-Cookie', 'None')}")
    return response

@app.before_request
def log_session_info():
    logger.debug(f"Before request - Route: {request.path}, Session: {session}, Cookies: {request.cookies}, Secret Key: {app.secret_key[:4]}...")

@app.route('/')
def index():
    logger.debug(f"Session in index: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' in session:
        quiz_completed = bool(mongo_service.get_quiz_results(session['user_id']))
        return redirect(url_for('explore') if quiz_completed else url_for('questions'))
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index.html: {str(e)}")
        return render_template('error.html', error='Template not found'), 404

@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception as e:
        logger.error(f"Error serving favicon.ico: {str(e)}")
        return render_template('error.html', error='Favicon not found'), 404

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    logger.debug(f"Session in auth: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    error = None
    success = None
    verification_sent = False
    verification_success = False
    email = session.get('email', '')

    # Check if user is already logged in
    if 'user_id' in session:
        return redirect(url_for('questions'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            if not email or not password:
                error = 'Email and password are required'
            else:
                try:
                    result = mongo_service.verify_user(email, password)
                    if not result['success']:
                        if result.get('needs_verification'):
                            session.permanent = True
                            session['email'] = email
                            session['verification_pending'] = True
                            session.modified = True
                            verification_sent = True
                            error = 'Please verify your email before logging in'
                        else:
                            error = result.get('error', 'Login failed. Please try again.')
                    else:
                        session.permanent = True
                        session['email'] = email
                        session['user_id'] = result['user']['id']
                        session.modified = True
                        logger.debug(f"Session set after login: {session}")
                        return redirect(url_for('questions'))
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
            elif data['password'] != request.form.get('confirm_password'):
                error = 'Passwords do not match'
            else:
                try:
                    existing_user = mongo_service.get_user_by_email(data['email'])
                    if existing_user:
                        error = 'Email already registered'
                    else:
                        result = mongo_service.create_user(
                            data['email'], data['password'], data['full_name'], data['age'], data['gender']
                        )
                        if not result['success']:
                            error = result.get('error', 'Failed to create user')
                        else:
                            email_result = send_verification_email(data['email'], result['user']['verification_token'])
                            if not email_result['success']:
                                error = 'Failed to send verification email'
                            else:
                                session.permanent = True
                                session['email'] = data['email']
                                session['user_id'] = result['user']['id']
                                session['verification_pending'] = True
                                session.modified = True
                                verification_sent = True
                                success = 'Verification email sent! Please check your inbox.'
                except Exception as e:
                    logger.error(f"Signup error: {str(e)}")
                    error = 'An error occurred during signup. Please try again.'
        elif form_type == 'resend_verification':
            try:
                email = request.form.get('email') or session.get('email')
                if not email:
                    error = 'No email provided'
                else:
                    user = mongo_service.get_user_by_email(email)
                    if not user:
                        error = 'User not found'
                    elif user.get('email_verified', False):
                        error = 'Email already verified'
                    else:
                        verification_token = user.get('verification_token')
                        if not verification_token:
                            verification_token = secrets.token_urlsafe(32)
                            mongo_service.update_user(user['id'], {'verification_token': verification_token})
                        email_result = send_verification_email(email, verification_token)
                        if not email_result['success']:
                            error = 'Failed to send verification email'
                        else:
                            session.permanent = True
                            session['email'] = email
                            session['verification_pending'] = True
                            session.modified = True
                            verification_sent = True
                            success = 'Verification email resent successfully!'
            except Exception as e:
                logger.error(f"Resend verification error: {str(e)}")
                error = 'An unexpected error occurred'

    if request.cookies.get('email_verified') == '1':
        verification_success = True
        resp = make_response(render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, email=email))
        resp.set_cookie('email_verified', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
        return resp

    return render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, email=email)

@app.route('/verify-email')
def verify_email_endpoint():
    logger.debug(f"Session in verify-email: {session}")
    token = request.args.get('token')
    if not token:
        return redirect(url_for('auth', error='Invalid verification link'))
    try:
        result = mongo_service.verify_email(token)
        if not result['success']:
            return redirect(url_for('auth', error=result.get('error', 'Verification failed. Please try again.')))
        session.permanent = True
        session['email'] = result['email']
        session['verification_pending'] = False
        session.modified = True
        resp = make_response(redirect(url_for('auth')))
        resp.set_cookie('email_verified', '1', max_age=60, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
        return resp
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
        matches = []
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
        chats = []
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
        user = mongo_service.users.find_one({'_id': ObjectId(session['user_id'])})
        if not user:
            return render_template('profile.html', profile={})
        profile = {
            'id': str(user['_id']),
            'email': user['email'],
            'full_name': user['full_name'],
            'age': user.get('age'),
            'gender': user.get('gender'),
            'quiz_completed': bool(mongo_service.get_quiz_results(session['user_id']))
        }
        return render_template('profile.html', profile=profile)
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
    return render_template('questions.html')

@app.route('/logout')
def logout():
    logger.debug(f"Session in logout: {session}")
    session.clear()
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('for_you_session', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
    resp.set_cookie('email_verified', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='None')
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
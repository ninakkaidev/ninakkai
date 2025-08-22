from flask import Flask, request, make_response, session, render_template, redirect, url_for, send_from_directory, jsonify
from flask_cors import CORS
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
import cloudinary
import cloudinary.uploader

# Configure Cloudinary
os.environ['CLOUDINARY_URL'] = 'cloudinary://869559855343136:FfJnI44v31rzfPvp7-K9lnI5BDM@dibbkr9vs'
cloudinary.config(secure=True)

# Configure logging
logging.getLogger('pymongo').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            static_url_path='/static',
            static_folder='static',
            template_folder='templates')
CORS(app)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your-secure-fixed-secret-key-here')
app.permanent_session_lifetime = timedelta(days=1)
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,  # Set to False for local development
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
        self.likes = self.db['likes']
        self.passes = self.db['passes']

    def create_user(self, email: str, password: str, full_name: str, age: int = None, gender: str = None, image: str = None, occupation: str = None, bio: str = None, interests: List[str] = None) -> Dict[str, Any]:
        try:
            hashed_password = generate_password_hash(password)
            verification_token = secrets.token_urlsafe(32)
            default_image = 'https://randomuser.me/api/portraits/women/44.jpg'
            if gender == 'male':
                default_image = 'https://i.ibb.co/4RbtYQBM/luthfi-alfarizi-jl-Jp-DBK17-Hw-unsplash.jpg'
            elif gender == 'female':
                default_image = 'https://i.ibb.co/Ld65xcCC/luthfi-alfarizi-y-XAGGb-Vuh-EY-unsplash.jpg'
            user_data = {
                'email': email,
                'password': hashed_password,
                'full_name': full_name,
                'age': age,
                'gender': gender,
                'image': image or default_image,
                'occupation': occupation,
                'bio': bio,
                'interests': interests or [],
                'photos': [],
                'location': '',
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

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            user = self.users.find_one({'_id': ObjectId(user_id)})
            if user:
                user['id'] = str(user['_id'])
                del user['_id']
                return user
            return None
        except Exception as e:
            logger.error(f"Get user by id error: {str(e)}")
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
            return {'success': result.modified_count > 0, 'email': user['email'], 'user_id': user['id']}
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

    def find_matches(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            user_quiz = self.get_quiz_results(user_id)
            if not user_quiz:
                return []
            user_scores = user_quiz['scores']
            dominant_type = user_scores['dominant_type']
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id}})
            matches = []
            for other_user in all_users:
                other_scores = other_user['scores']
                match_percentage = self._calculate_match_percentage(user_scores, other_scores)
                if other_scores['dominant_type'] == dominant_type or other_scores.get('secondary_type') == dominant_type:
                    user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                    if user_data:
                        matches.append({
                            'id': str(user_data['_id']),
                            'full_name': user_data['full_name'],
                            'age': user_data.get('age'),
                            'gender': user_data.get('gender'),
                            'image': user_data.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                            'occupation': user_data.get('occupation', 'N/A'),
                            'bio': user_data.get('bio', 'No bio available'),
                            'interests': user_data.get('interests', []),
                            'distance': 'N/A',  # Placeholder; implement geolocation if needed
                            'rating': '4.5',  # Placeholder; implement rating system if needed
                            'dominant_type': other_scores['dominant_type'],
                            'match_percentage': match_percentage
                        })
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Find matches error: {str(e)}")
            return []

    def _calculate_match_percentage(self, user_scores: Dict[str, Any], other_scores: Dict[str, Any]) -> int:
        try:
            # Simple match percentage based on dominant and secondary type overlap
            dominant_match = 50 if user_scores['dominant_type'] == other_scores['dominant_type'] else 20
            secondary_match = 30 if user_scores.get('secondary_type') == other_scores.get('secondary_type') and user_scores.get('secondary_type') else 10
            return min(dominant_match + secondary_match, 100)
        except Exception as e:
            logger.error(f"Calculate match percentage error: {str(e)}")
            return 50  # Fallback percentage

    def like_user(self, user_id: str, matched_user_id: str) -> Dict[str, Any]:
        try:
            like_data = {
                'user_id': user_id,
                'matched_user_id': matched_user_id,
                'timestamp': datetime.now(timezone.utc)
            }
            result = self.likes.insert_one(like_data)
            return {'success': True, 'like_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Like user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def pass_user(self, user_id: str, passed_user_id: str) -> Dict[str, Any]:
        try:
            pass_data = {
                'user_id': user_id,
                'passed_user_id': passed_user_id,
                'timestamp': datetime.now(timezone.utc)
            }
            result = self.passes.insert_one(pass_data)
            return {'success': True, 'pass_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Pass user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def search_matches(self, query: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            query = query.lower().strip()
            matches = []
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id}})
            user_quiz = self.get_quiz_results(user_id)
            if not user_quiz:
                return []
            user_scores = user_quiz['scores']
            for other_user in all_users:
                user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                if user_data and (query in user_data['full_name'].lower() or any(query in interest.lower() for interest in user_data.get('interests', []))):
                    match_percentage = self._calculate_match_percentage(user_scores, other_user['scores'])
                    matches.append({
                        'id': str(user_data['_id']),
                        'full_name': user_data['full_name'],
                        'age': user_data.get('age'),
                        'gender': user_data.get('gender'),
                        'image': user_data.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                        'occupation': user_data.get('occupation', 'N/A'),
                        'bio': user_data.get('bio', 'No bio available'),
                        'interests': user_data.get('interests', []),
                        'distance': 'N/A',
                        'rating': '4.5',
                        'dominant_type': other_user['scores']['dominant_type'],
                        'match_percentage': match_percentage
                    })
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Search matches error: {str(e)}")
            return []

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

    def get_liked_users(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            likes = self.likes.find({'user_id': user_id})
            liked_users = []
            for like in likes:
                user = self.get_user_by_id(like['matched_user_id'])
                if user:
                    liked_users.append({
                        'id': user['id'],
                        'full_name': user['full_name'],
                        'image': user['image'],
                        'occupation': user.get('occupation', 'N/A')
                    })
            return liked_users
        except Exception as e:
            logger.error(f"Get liked users error: {str(e)}")
            return []

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

    if 'user_id' in session:
        logger.debug(f"User already logged in, redirecting to questions: {session['user_id']}")
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
                'gender': request.form.get('gender'),
                'occupation': request.form.get('occupation', ''),
                'bio': request.form.get('bio', ''),
                'interests': request.form.get('interests', '').split(',') if request.form.get('interests') else []
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
                            data['email'], data['password'], data['full_name'], data['age'], data['gender'],
                            data.get('image'), data['occupation'], data['bio'], data['interests']
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
        resp.set_cookie('email_verified', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
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
        session['user_id'] = result['user_id']
        session['verification_pending'] = False
        session.modified = True
        logger.debug(f"Session set after email verification: {session}")
        resp = make_response(redirect(url_for('questions')))
        resp.set_cookie('email_verified', '1', max_age=60, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
        return resp
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        return redirect(url_for('auth', error='An unexpected error occurred during verification.'))

@app.route('/explore')
def explore():
    logger.debug(f"Session in explore: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /explore")
        return redirect(url_for('auth', error='Please log in to access the explore page'))
    
    try:
        # Fetch user data
        user = mongo_service.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('auth', error='User not found. Please log in again.'))
        
        # Fetch quiz results
        quiz_result = mongo_service.get_quiz_results(session['user_id'])
        if not quiz_result:
            return redirect(url_for('questions', error='Please complete the quiz to access the explore page'))
        
        # Fetch matches
        matches = mongo_service.find_matches(session['user_id'])
        
        # Prepare user profile data
        profile = {
            'id': user['id'],
            'full_name': user['full_name'],
            'email': user['email'],
            'age': user.get('age'),
            'gender': user.get('gender'),
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'dominant_type': quiz_result['scores']['dominant_type'],
            'dominant_percentage': quiz_result['scores']['dominant_percentage'],
            'secondary_type': quiz_result['scores']['secondary_type'],
            'secondary_percentage': quiz_result['scores']['secondary_percentage']
        }
        
        # Split matches into categories (for simplicity, use same matches for all sections)
        discovery = matches
        nearby = matches
        
        return render_template('explore.html', profile=profile, matches=matches, discovery=discovery, nearby=nearby, error=None)
    except Exception as e:
        logger.error(f"Explore error: {str(e)}")
        return render_template('explore.html', profile={}, matches=[], discovery=[], nearby=[], error='An error occurred while loading the explore page. Please try again.')

@app.route('/like-user', methods=['POST'])
def like_user():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        matched_user_id = data.get('matched_user_id')
        if not matched_user_id:
            return jsonify({'success': False, 'error': 'No user ID provided'}), 400
        result = mongo_service.like_user(session['user_id'], matched_user_id)
        if result['success']:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Failed to like user')}), 500
    except Exception as e:
        logger.error(f"Like user endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/pass-user', methods=['POST'])
def pass_user():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        passed_user_id = data.get('passed_user_id')
        if not passed_user_id:
            return jsonify({'success': False, 'error': 'No user ID provided'}), 400
        result = mongo_service.pass_user(session['user_id'], passed_user_id)
        if result['success']:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Failed to pass user')}), 500
    except Exception as e:
        logger.error(f"Pass user endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/search-matches')
def search_matches():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': False, 'error': 'No search query provided'}), 400
        matches = mongo_service.search_matches(query, session['user_id'])
        return jsonify({'success': True, 'matches': matches}), 200
    except Exception as e:
        logger.error(f"Search matches endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/user-profile/<user_id>')
def user_profile(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        user = mongo_service.get_user_by_id(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        quiz_result = mongo_service.get_quiz_results(user_id)
        profile = {
            'id': user['id'],
            'full_name': user['full_name'],
            'age': user.get('age'),
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'distance': 'N/A',
            'rating': '4.5',
            'match_percentage': 50,  # Placeholder; calculate based on quiz results
            'personality': {
                'dominant_type': quiz_result['scores']['dominant_type'] if quiz_result else 'N/A',
                'dominant_percentage': quiz_result['scores']['dominant_percentage'] if quiz_result else 0,
                'secondary_type': quiz_result['scores']['secondary_type'] if quiz_result else 'N/A',
                'secondary_percentage': quiz_result['scores']['secondary_percentage'] if quiz_result else 0
            }
        }
        return jsonify({'success': True, 'user': profile}), 200
    except Exception as e:
        logger.error(f"User profile endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        user = mongo_service.get_user_by_id(session['user_id'])
        if not user:
            return render_template('profile.html', profile={}, liked_users=[])
        quiz_result = mongo_service.get_quiz_results(session['user_id'])
        profile = {
            'id': user['id'],
            'email': user['email'],
            'full_name': user['full_name'],
            'age': user.get('age'),
            'gender': user.get('gender'),
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'photos': user.get('photos', []),
            'location': user.get('location', ''),
            'quiz_completed': bool(quiz_result),
            'dominant_type': quiz_result['scores']['dominant_type'] if quiz_result else 'N/A',
            'dominant_percentage': quiz_result['scores']['dominant_percentage'] if quiz_result else 0
        }
        liked_users = mongo_service.get_liked_users(session['user_id'])
        return render_template('profile.html', profile=profile, liked_users=liked_users)
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return render_template('profile.html', profile={}, liked_users=[])

@app.route('/questions', methods=['GET'])
def questions():
    logger.debug(f"Session in questions: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /questions")
        return redirect(url_for('auth'))
    quiz_completed = bool(mongo_service.get_quiz_results(session['user_id']))
    if quiz_completed:
        return redirect(url_for('explore'))
    logger.debug(f"Rendering questions.html for user_id: {session['user_id']}")
    return render_template('questions.html')

@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    logger.debug(f"Session in submit-quiz: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /submit-quiz")
        return redirect(url_for('auth'))
    
    try:
        data = request.get_json()
        answers = data.get('answers', [])
        if not answers:
            return jsonify({'success': False, 'error': 'No answers provided'}), 400
        
        processed_answers = []
        required_questions = [
            {
                'answers': ["Safe and calm inside", "Excited and full of butterflies", "Like I've found someone truly rare", "Scared of being too vulnerable"],
                'types': ["👂 Listener", "💘 Romantic", "🌙 Dreamer", "🛡️ Protector"]
            },
            {
                'answers': ["Trust", "Emotional connection", "Shared goals", "Physical intimacy"],
                'types': ["🛡️ Protector", "🌿 Nurturer", "👂 Listener", "💘 Romantic"],
                'isRankQuestion': True
            },
            {
                'answers': ["Someone silently sitting with me through pain", "Someone helping me fix the situation", "Someone saying exactly the right words", "Someone holding me tight without speaking"],
                'types': ["🌿 Nurturer", "🛡️ Protector", "👂 Listener", "💘 Romantic"]
            },
            {
                'answers': ["Try to stay calm and really listen", "Express your emotions openly", "Try to solve it quickly and move on", "Take it personally and overthink it"],
                'types': ["👂 Listener", "💘 Romantic", "🛡️ Protector", "🌙 Dreamer"]
            },
            {
                'answers': ["Kind and soft", "Strong and independent", "Perfect and without flaws", "Honest and growing"],
                'types': ["🌿 Nurturer", "🛡️ Protector", "🌟 Idealist", "👂 Listener"]
            },
            {
                'answers': ["Peace and emotional safety", "Excitement and mystery", "Growth and learning together", "Feeling truly known and accepted"],
                'types': ["🌿 Nurturer", "💘 Romantic", "🌟 Idealist", "🌙 Dreamer"]
            },
            {
                'answers': ["Deep, late-night emotional conversations", "Intense physical closeness and passion", "When someone notices the little things", "Solving life's problems together"],
                'types': ["🌙 Dreamer", "💘 Romantic", "🌿 Nurturer", "🛡️ Protector"]
            },
            {
                'answers': ["Cry or let it out", "Get silent and withdraw", "Keep busy to avoid it", "Talk it out with someone trusted"],
                'types': ["🌙 Dreamer", "🛡️ Protector", "🌟 Idealist", "👂 Listener"]
            },
            {
                'answers': ["Freedom to spend and still save together", "Clear roles — one earns, one manages", "Always discuss big spending decisions", "Having separate money but shared goals"],
                'types': ["🛡️ Protector", "🌿 Nurturer", "👂 Listener", "🌟 Idealist"]
            }
        ]
        optional_questions = [
            {
                'answers': ["I need space to process alone", "I want to talk it through together", "I focus on practical solutions", "I lean on my partner for comfort"],
                'types': ["🛡️ Protector", "👂 Listener", "🌟 Idealist", "🌿 Nurturer"]
            },
            {
                'answers': ["Dream big and figure it out later", "Set clear goals and timelines", "Go with the flow and see what happens", "Discuss every step together"],
                'types': ["🌙 Dreamer", "🛡️ Protector", "💘 Romantic", "👂 Listener"]
            }
        ]
        
        all_questions = required_questions + optional_questions
        for answer_data in answers:
            question_idx = answer_data.get('question')
            if question_idx >= len(all_questions):
                continue
            question = all_questions[question_idx]
            if question.get('isRankQuestion'):
                ranking = answer_data.get('ranking', [])
                ranked_answer = "Ranked: " + ", ".join(f"{r['rank']}. {question['answers'][r['index']]}" for r in ranking)
                processed_answers.append({
                    'type': question['types'][ranking[0]['index']] if ranking else question['types'][0],
                    'answer': ranked_answer
                })
            else:
                answer_idx = answer_data.get('answer')
                if answer_idx is not None and 0 <= answer_idx < len(question['answers']):
                    processed_answers.append({
                        'type': question['types'][answer_idx],
                        'answer': question['answers'][answer_idx]
                    })

        quiz_data = {'answers': processed_answers}
        result = mongo_service.save_quiz_results(session['user_id'], quiz_data)
        if result['success']:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Failed to save quiz results')}), 500
    except Exception as e:
        logger.error(f"Submit quiz error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
def logout():
    logger.debug(f"Session in logout: {session}")
    session.clear()
    resp = make_response(redirect(url_for('index')))
    resp.set_cookie('for_you_session', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
    resp.set_cookie('email_verified', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
    return resp

@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    try:
        upload_result = cloudinary.uploader.upload(file)
        url = upload_result['secure_url']
        mongo_service.update_user(session['user_id'], {'image': url})
        return jsonify({'success': True, 'url': url}), 200
    except Exception as e:
        logger.error(f"Upload profile picture error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    user = mongo_service.get_user_by_id(session['user_id'])
    if len(user.get('photos', [])) >= 7:
        return jsonify({'success': False, 'error': 'Maximum 7 photos allowed'}), 400
    try:
        upload_result = cloudinary.uploader.upload(file)
        url = upload_result['secure_url']
        photos = user.get('photos', []) + [url]
        mongo_service.update_user(session['user_id'], {'photos': photos})
        return jsonify({'success': True, 'url': url}), 200
    except Exception as e:
        logger.error(f"Upload photo error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'}), 400
    user = mongo_service.get_user_by_id(session['user_id'])
    photos = user.get('photos', [])
    if url in photos:
        photos.remove(url)
        mongo_service.update_user(session['user_id'], {'photos': photos})
        return jsonify({'success': True}), 200
    return jsonify({'success': False, 'error': 'Photo not found'}), 404

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    update_data = {}
    if 'full_name' in data:
        update_data['full_name'] = data['full_name']
    if 'age' in data:
        update_data['age'] = int(data['age'])
    if 'bio' in data:
        update_data['bio'] = data['bio']
    if 'location' in data:
        update_data['location'] = data['location']
    if 'interests' in data:
        update_data['interests'] = data['interests']
    if update_data:
        result = mongo_service.update_user(session['user_id'], update_data)
        return jsonify(result)
    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True) 
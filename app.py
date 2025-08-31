from flask import Flask, request, make_response, session, render_template, redirect, url_for, send_from_directory, jsonify, Response
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
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
import cloudinary.api
import pytz
import json
import http.client

# Configure Cloudinary with explicit credentials and enhanced logging
def configure_cloudinary():
    try:
        cloudinary.config(
            cloud_name='dibbkr9vs',
            api_key='869559855343136',
            api_secret='FfJnI44v31rzfPvp7-K9lnI5BDM',
            secure=True
        )
        config = cloudinary.config()
        if not (config.cloud_name and config.api_key and config.api_secret):
            raise Exception("Cloudinary configuration incomplete: missing cloud_name, api_key, or api_secret")
        logger.info("Cloudinary configured successfully")
    except Exception as e:
        logger.error(f"Failed to configure Cloudinary: {str(e)}")
        raise Exception(f"Cloudinary configuration failed: {str(e)}")

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

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Cloudinary
configure_cloudinary()

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
        self.notifications = self.db['notifications']

    def check_rate_limit(self, key: str, max_attempts: int, period: timedelta = timedelta(hours=1)) -> bool:
        now = datetime.now(timezone.utc)
        limit = self.db['rate_limits'].find_one({'key': key})
        if limit:
            last_reset = limit['last_reset']
            if last_reset.tzinfo is None:
                last_reset = pytz.UTC.localize(last_reset)
            if now - last_reset > period:
                self.db['rate_limits'].update_one(
                    {'key': key},
                    {'$set': {'attempts': 0, 'last_reset': now}}
                )
                attempts = 0
            else:
                attempts = limit['attempts']
        else:
            self.db['rate_limits'].insert_one({
                'key': key,
                'attempts': 0,
                'last_reset': now
            })
            attempts = 0
        return attempts < max_attempts

    def inc_rate_limit(self, key: str):
        self.db['rate_limits'].update_one(
            {'key': key},
            {'$inc': {'attempts': 1}}
        )

    def reset_rate_limit(self, key: str):
        self.db['rate_limits'].update_one(
            {'key': key},
            {'$set': {'attempts': 0, 'last_reset': datetime.now(timezone.utc)}}
        )

    def create_user(self, email: str, password: str, full_name: str, age: int = None, gender: str = None, image: str = None, occupation: str = None, bio: str = None, interests: List[str] = None) -> Dict[str, Any]:
        try:
            if age is not None and age < 18:
                return {'success': False, 'error': 'You must be at least 18 years old to sign up'}
            if gender not in ['male', 'female']:
                return {'success': False, 'error': 'Invalid gender selection'}
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
                'blocked_users': [],
                'profile_complete': False,
                'email_verified': False,
                'age_verified': False,  # Added age_verified field
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

    def get_user_by_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            user = self.users.find_one({'reset_token': token, 'reset_token_expiry': {'$gt': datetime.now(timezone.utc)}})
            if user:
                user['id'] = str(user['_id'])
                del user['_id']
                return user
            return None
        except Exception as e:
            logger.error(f"Get user by reset token error: {str(e)}")
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

    def update_password(self, user_id: str, new_password: str) -> Dict[str, Any]:
        try:
            hashed_password = generate_password_hash(new_password)
            result = self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'password': hashed_password}, '$unset': {'reset_token': '', 'reset_token_expiry': ''}}
            )
            return {'success': result.modified_count > 0}
        except Exception as e:
            logger.error(f"Update password error: {str(e)}")
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

    def delete_quiz_results(self, user_id: str) -> Dict[str, Any]:
        try:
            self.quiz_results.delete_many({'user_id': user_id})
            self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'profile_complete': False}}
            )
            return {'success': True}
        except Exception as e:
            logger.error(f"Delete quiz results error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def find_matches(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            current_user = self.get_user_by_id(user_id)
            if not current_user:
                return []
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
                    if user_data and user_data['gender'] != current_user['gender']:
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
                            'dominant_type': other_scores['dominant_type'],
                            'match_percentage': match_percentage
                        })
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Find matches error: {str(e)}")
            return []

    def _calculate_match_percentage(self, user_scores: Dict[str, Any], other_scores: Dict[str, Any]) -> int:
        try:
            dominant_match = 50 if user_scores['dominant_type'] == other_scores['dominant_type'] else 20
            secondary_match = 30 if user_scores.get('secondary_type') == other_scores.get('secondary_type') and user_scores.get('secondary_type') else 10
            return min(dominant_match + secondary_match, 100)
        except Exception as e:
            logger.error(f"Calculate match percentage error: {str(e)}")
            return 50

    def is_matched(self, user1: str, user2: str) -> bool:
        try:
            like1 = self.likes.find_one({'user_id': user1, 'matched_user_id': user2})
            like2 = self.likes.find_one({'user_id': user2, 'matched_user_id': user1})
            return bool(like1 and like2)
        except Exception as e:
            logger.error(f"Is matched error: {str(e)}")
            return False

    def get_matched_users(self, user_id: str) -> List[str]:
        try:
            likers = [str(l['user_id']) for l in self.likes.find({'matched_user_id': user_id})]
            my_likes = self.likes.find({'user_id': user_id, 'matched_user_id': {'$in': likers}})
            matches = [str(l['matched_user_id']) for l in my_likes]
            return matches
        except Exception as e:
            logger.error(f"Get matched users error: {str(e)}")
            return []

    def like_user(self, user_id: str, matched_user_id: str) -> Dict[str, Any]:
        try:
            if self.has_liked_user(user_id, matched_user_id):
                return {'success': False, 'error': 'Already liked'}
            logger.info(f"Processing like from user {user_id} to {matched_user_id}")
            current_user = self.get_user_by_id(user_id)
            if current_user['gender'] == 'male':
                rate_key = f"daily_likes_{user_id}"
                if not self.check_rate_limit(rate_key, 5, timedelta(days=1)):
                    return {'success': False, 'error': 'Daily like limit exceeded'}
            like_data = {
                'user_id': user_id,
                'matched_user_id': matched_user_id,
                'timestamp': datetime.now(timezone.utc)
            }
            result = self.likes.insert_one(like_data)
            if current_user['gender'] == 'male':
                self.inc_rate_limit(rate_key)
                limit_doc = self.db['rate_limits'].find_one({'key': rate_key})
                attempts = limit_doc['attempts']
                likes_remaining = 5 - attempts
            else:
                likes_remaining = None
            liker = self.get_user_by_id(user_id)
            liked = self.get_user_by_id(matched_user_id)
            self.add_notification(matched_user_id, f"{liker['full_name']} liked your profile", 'like', user_id)
            is_match = self.is_matched(user_id, matched_user_id)
            if is_match:
                self.add_notification(user_id, f"You matched with {liked['full_name']}", 'match', matched_user_id)
                self.add_notification(matched_user_id, f"You matched with {liker['full_name']}", 'match', user_id)
            logger.info(f"Like successful, like_id: {str(result.inserted_id)}, is_match: {is_match}")
            response = {'success': True, 'like_id': str(result.inserted_id), 'is_match': is_match}
            if likes_remaining is not None:
                response['likes_remaining'] = likes_remaining
            return response
        except Exception as e:
            logger.error(f"Like user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def pass_user(self, user_id: str, passed_user_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Processing pass from user {user_id} to {passed_user_id}")
            pass_data = {
                'user_id': user_id,
                'passed_user_id': passed_user_id,
                'timestamp': datetime.now(timezone.utc)
            }
            result = self.passes.insert_one(pass_data)
            logger.info(f"Pass successful, pass_id: {str(result.inserted_id)}")
            return {'success': True, 'pass_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Pass user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def search_matches(self, query: str, user_id: str) -> List[Dict[str, Any]]:
        try:
            current_user = self.get_user_by_id(user_id)
            if not current_user:
                return []
            query = query.lower().strip()
            matches = []
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id}})
            user_quiz = self.get_quiz_results(user_id)
            if not user_quiz:
                return []
            user_scores = user_quiz['scores']
            for other_user in all_users:
                user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                if user_data and user_data['gender'] != current_user['gender'] and (query in user_data['full_name'].lower() or any(query in interest.lower() for interest in user_data.get('interests', []))):
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
                        'match_percentage': match_percentage,
                        'liked': self.has_liked_user(user_id, str(user_data['_id']))
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
                        'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                        'occupation': user.get('occupation', 'N/A')
                    })
            return liked_users
        except Exception as e:
            logger.error(f"Get liked users error: {str(e)}")
            return []

    def get_pending_likers(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            likers = self.likes.find({'matched_user_id': user_id, 'user_id': {'$ne': user_id}})
            liker_ids = [str(l['user_id']) for l in likers]
            my_likes = [str(l['matched_user_id']) for l in self.likes.find({'user_id': user_id})]
            passed = [str(p['passed_user_id']) for p in self.passes.find({'user_id': user_id})]
            pending_ids = [pid for pid in liker_ids if pid not in my_likes and pid not in passed]
            pending_users = []
            for pid in pending_ids:
                user = self.get_user_by_id(pid)
                if user:
                    pending_users.append({
                        'id': user['id'],
                        'full_name': user['full_name'],
                        'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                        'occupation': user.get('occupation', 'N/A')
                    })
            return pending_users
        except Exception as e:
            logger.error(f"Get pending likers error: {str(e)}")
            return []

    def delete_account(self, user_id: str) -> Dict[str, Any]:
        try:
            self.users.delete_one({'_id': ObjectId(user_id)})
            self.likes.delete_many({'$or': [{'user_id': user_id}, {'matched_user_id': user_id}]})
            self.passes.delete_many({'$or': [{'user_id': user_id}, {'passed_user_id': user_id}]})
            self.quiz_results.delete_many({'user_id': user_id})
            self.notifications.delete_many({'user_id': user_id})
            return {'success': True}
        except Exception as e:
            logger.error(f"Delete account error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def has_liked_user(self, user_id: str, matched_user_id: str) -> bool:
        """Check if a user has already liked another"""
        try:
            like = self.likes.find_one({'user_id': user_id, 'matched_user_id': matched_user_id})
            return bool(like)
        except Exception as e:
            logger.error(f"Has liked user error: {str(e)}")
            return False

    def has_passed_user(self, user_id: str, passed_user_id: str) -> bool:
        """Check if a user has already passed on another user"""
        try:
            passed = self.passes.find_one({'user_id': user_id, 'passed_user_id': passed_user_id})
            return bool(passed)
        except Exception as e:
            logger.error(f"Has passed user error: {str(e)}")
            return False

    def get_filtered_matches(self, user_id: str) -> List[Dict[str, Any]]:
        """Get matches excluding liked and passed users"""
        try:
            current_user = self.get_user_by_id(user_id)
            if not current_user:
                return []
            user_quiz = self.get_quiz_results(user_id)
            if not user_quiz:
                return []
            
            # Get all users that current user has liked or passed on
            liked_users = [str(like['matched_user_id']) for like in self.likes.find({'user_id': user_id})]
            passed_users = [str(passed['passed_user_id']) for passed in self.passes.find({'user_id': user_id})]
            excluded_users = set(liked_users + passed_users)
            
            user_scores = user_quiz['scores']
            dominant_type = user_scores['dominant_type']
            
            # Get all potential matches excluding the ones user has already interacted with
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id, '$nin': list(excluded_users)}})
            
            matches = []
            for other_user in all_users:
                other_scores = other_user['scores']
                match_percentage = self._calculate_match_percentage(user_scores, other_scores)
                
                if other_scores['dominant_type'] == dominant_type or other_scores.get('secondary_type') == dominant_type:
                    user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                    if user_data and user_data['gender'] != current_user['gender']:
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
                            'dominant_type': other_scores['dominant_type'],
                            'match_percentage': match_percentage,
                            'liked': False  # Since filtered, always False
                        })
            
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:20]
        except Exception as e:
            logger.error(f"Get filtered matches error: {str(e)}")
            return []

    def unlike_user(self, user_id: str, matched_user_id: str) -> Dict[str, Any]:
        """Remove a like from a user"""
        try:
            result = self.likes.delete_one({'user_id': user_id, 'matched_user_id': matched_user_id})
            is_match = self.is_matched(user_id, matched_user_id)
            return {'success': result.deleted_count > 0, 'is_match': is_match}
        except Exception as e:
            logger.error(f"Unlike user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def block_user(self, user_id: str, blocked_user_id: str) -> Dict[str, Any]:
        try:
            result = self.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$addToSet': {'blocked_users': blocked_user_id}}
            )
            return {'success': result.modified_count > 0}
        except Exception as e:
            logger.error(f"Block user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def add_notification(self, user_id: str, message: str, type: str = 'general', related_id: str = None) -> Dict[str, Any]:
        try:
            notif_data = {
                'user_id': user_id,
                'message': message,
                'type': type,
                'related_id': related_id,
                'read': False,
                'timestamp': datetime.now(timezone.utc)
            }
            result = self.notifications.insert_one(notif_data)
            return {'success': True, 'notif_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Add notification error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_notifications(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            notifs = list(self.notifications.find({'user_id': user_id}).sort('timestamp', -1))
            for n in notifs:
                n['id'] = str(n['_id'])
                del n['_id']
                if n['timestamp'].tzinfo is None:
                    n['timestamp'] = pytz.UTC.localize(n['timestamp'])
                n['timestamp'] = n['timestamp'].isoformat()
            return notifs
        except Exception as e:
            logger.error(f"Get notifications error: {str(e)}")
            return []

    def mark_notification_read(self, notif_id: str, user_id: str) -> Dict[str, Any]:
        try:
            result = self.notifications.update_one(
                {'_id': ObjectId(notif_id), 'user_id': user_id},
                {'$set': {'read': True}}
            )
            return {'success': result.modified_count > 0}
        except Exception as e:
            logger.error(f"Mark notification read error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def clear_notifications(self, user_id: str) -> Dict[str, Any]:
        try:
            result = self.notifications.delete_many({'user_id': user_id})
            return {'success': True, 'deleted_count': result.deleted_count}
        except Exception as e:
            logger.error(f"Clear notifications error: {str(e)}")
            return {'success': False, 'error': str(e)}

class ChatService:
    def __init__(self):
        self.uri = "mongodb+srv://infoqiooo:Gjresr7SikhBmM5U@cluster0.hyzcpcz.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        self.client = MongoClient(self.uri)
        try:
            self.client.admin.command('ping')
            logger.info("Chat MongoDB connection successful")
        except Exception as e:
            logger.error(f"Chat MongoDB connection failed: {str(e)}")
        self.db = self.client['chat_db']
        self.messages = self.db['messages']

    def send_message(self, sender_id: str, receiver_id: str, message: str, replied_to: str = None) -> Dict[str, Any]:
        try:
            sender = mongo_service.get_user_by_id(sender_id)
            receiver = mongo_service.get_user_by_id(receiver_id)
            if receiver_id in sender.get('blocked_users', []) or sender_id in receiver.get('blocked_users', []):
                return {'success': False, 'error': 'Blocked'}
            msg_data = {
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'message': message,
                'timestamp': datetime.now(timezone.utc),
                'read': False
            }
            if replied_to:
                replied_msg = self.messages.find_one({'_id': ObjectId(replied_to)})
                if replied_msg:
                    msg_data['replied_to'] = replied_to
                    msg_data['replied_text'] = replied_msg['message']
            result = self.messages.insert_one(msg_data)
            msg_data['id'] = str(result.inserted_id)
            del msg_data['_id']
            msg_data['timestamp'] = msg_data['timestamp'].isoformat()
            # Emit to both sender and receiver rooms
            socketio.emit('new_message', msg_data, room=sender_id)
            socketio.emit('new_message', msg_data, room=receiver_id)
            return {'success': True, 'message_id': msg_data['id']}
        except Exception as e:
            logger.error(f"Send message error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_messages(self, user1: str, user2: str):
        try:
            user1_data = mongo_service.get_user_by_id(user1)
            user2_data = mongo_service.get_user_by_id(user2)
            if user2 in user1_data.get('blocked_users', []) or user1 in user2_data.get('blocked_users', []):
                return {'success': False, 'error': 'Blocked'}
            query = {'$or': [
                {'sender_id': user1, 'receiver_id': user2},
                {'sender_id': user2, 'receiver_id': user1}
            ]}
            msgs = list(self.messages.find(query).sort('timestamp', 1))
            updated = self.messages.update_many(
                {'receiver_id': user1, 'sender_id': user2, 'read': False},
                {'$set': {'read': True}}
            )
            if updated.modified_count > 0:
                socketio.emit('messages_read', {'conversation_id': user1}, room=user2)
            for msg in msgs:
                msg['id'] = str(msg['_id'])
                del msg['_id']
                if 'replied_to' in msg:
                    replied = self.messages.find_one({'_id': ObjectId(msg['replied_to'])})
                    if replied:
                        msg['replied_text'] = replied['message']
                if msg['timestamp'].tzinfo is None:
                    msg['timestamp'] = pytz.UTC.localize(msg['timestamp'])
                msg['timestamp'] = msg['timestamp'].isoformat()
            return msgs
        except Exception as e:
            logger.error(f"Get messages error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_last_message(self, user1: str, user2: str) -> Optional[Dict[str, Any]]:
        try:
            query = {'$or': [
                {'sender_id': user1, 'receiver_id': user2},
                {'sender_id': user2, 'receiver_id': user1}
            ]}
            msg = self.messages.find_one(query, sort=[('timestamp', -1)])
            if msg:
                msg['id'] = str(msg['_id'])
                del msg['_id']
                if msg['timestamp'].tzinfo is None:
                    msg['timestamp'] = pytz.UTC.localize(msg['timestamp'])
                return msg
            return None
        except Exception as e:
            logger.error(f"Get last message error: {str(e)}")
            return None

    def get_unread_count(self, user_id: str) -> int:
        try:
            return self.messages.count_documents({'receiver_id': user_id, 'read': False})
        except Exception as e:
            logger.error(f"Get unread count error: {str(e)}")
            return 0

    def get_unread_count_per_user(self, user_id: str, sender_id: str) -> int:
        try:
            return self.messages.count_documents({'receiver_id': user_id, 'sender_id': sender_id, 'read': False})
        except Exception as e:
            logger.error(f"Get unread per user error: {str(e)}")
            return 0

    def delete_message(self, message_id: str, sender_id: str, receiver_id: str) -> Dict[str, Any]:
        try:
            result = self.messages.delete_one({'_id': ObjectId(message_id)})
            if result.deleted_count > 0:
                # Emit to both
                socketio.emit('message_deleted', {'message_id': message_id}, room=sender_id)
                socketio.emit('message_deleted', {'message_id': message_id}, room=receiver_id)
            return {'success': result.deleted_count > 0}
        except Exception as e:
            logger.error(f"Delete message error: {str(e)}")
            return {'success': False, 'error': str(e)}

mongo_service = MongoService()
chat_service = ChatService()

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

def send_reset_email(email: str, reset_token: str) -> Dict[str, Any]:
    try:
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_user = 'ninakkaiforyou@gmail.com'
        smtp_password = os.environ.get('SMTP_PASSWORD', 'porz cqqt bumr wdgj')
        reset_url = f"https://www.ninakkai.com/reset-password/{reset_token}"
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = email
        msg['Subject'] = 'Reset Your Password - Ninakkai'
        body = f"""
        Hello,

        You requested a password reset for your Ninakkai account. Click the link below to reset your password:

        {reset_url}

        This link will expire in 1 hour. If you did not request this, please ignore this email.

        Best regards,
        The Ninakkai Team
        """
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, email, msg.as_string())
        logger.info(f"Reset email sent to {email}")
        return {'success': True}
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {str(e)}")
        return {'success': False, 'error': str(e)}

@app.after_request
def log_response(response):
    logger.debug(f"Response - Route: {request.path}, Status: {response.status_code}, Set-Cookie: {response.headers.get('Set-Cookie', 'None')}")
    return response

@app.before_request
def log_session_info():
    logger.debug(f"Before request - Route: {request.path}, Session: {session}, Cookies: {request.cookies}, Secret Key: {app.secret_key[:4]}...")
    for key, value in session.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            session[key] = pytz.UTC.localize(value)
            session.modified = True

@app.route('/', endpoint='home')
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
        return 'Template not found', 404

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except Exception as e:
        logger.error(f"Error serving favicon.ico: {str(e)}")
        return 'Favicon not found', 404
    
@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    error = None
    success = None
    verification_sent = False
    verification_success = False
    reset_sent = False
    email = session.get('email', '')

    if 'user_id' in session:
        logger.debug(f"User already logged in, redirecting to questions: {session['user_id']}")
        return redirect(url_for('questions'))

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'login':
            ip = request.remote_addr
            rate_key = f"login_{ip}"
            if not mongo_service.check_rate_limit(rate_key, 10):
                error = 'Too many failed login attempts. Please try again later.'
            else:
                email = request.form.get('email')
                password = request.form.get('password')
                if not email or not password:
                    error = 'Email and password are required'
                    mongo_service.inc_rate_limit(rate_key)
                else:
                    try:
                        result = mongo_service.verify_user(email, password)
                        if not result['success']:
                            mongo_service.inc_rate_limit(rate_key)
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
                            mongo_service.reset_rate_limit(rate_key)
                            session.permanent = True
                            session['email'] = email
                            session['user_id'] = result['user']['id']
                            session.modified = True
                            logger.debug(f"Session set after login: {session}")
                            user = result['user']
                            if not user.get('age_verified', False):
                                return redirect(url_for('age_verification'))
                            return redirect(url_for('questions'))
                    except Exception as e:
                        logger.error(f"Login error: {str(e)}")
                        mongo_service.inc_rate_limit(rate_key)
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
            agree_terms = request.form.get('agree_terms')
            agree_privacy = request.form.get('agree_privacy')
            if not agree_terms or not agree_privacy:
                error = 'You must agree to the terms and conditions and privacy policy'
            elif not all([data['email'], data['password'], data['full_name']]):
                error = 'Please fill all required fields'
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
                error = 'Please enter a valid email address'
            elif len(data['password']) < 8:
                error = 'Password must be at least 8 characters'
            elif data['password'] != request.form.get('confirm_password'):
                error = 'Passwords do not match'
            elif data['age'] is None or data['age'] < 18:
                error = 'You must be at least 18 years old'
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
        elif form_type == 'forgot_password':
            ip = request.remote_addr
            rate_key = f"forgot_{ip}"
            if not mongo_service.check_rate_limit(rate_key, 3):
                error = 'Too many reset requests. Please try again later.'
            else:
                email = request.form.get('email')
                if not email:
                    error = 'Email is required'
                else:
                    try:
                        user = mongo_service.get_user_by_email(email)
                        if not user:
                            error = 'No account found with this email'
                        else:
                            reset_token = secrets.token_urlsafe(32)
                            expiry = datetime.now(timezone.utc) + timedelta(hours=1)
                            update_result = mongo_service.update_user(user['id'], {
                                'reset_token': reset_token,
                                'reset_token_expiry': expiry
                            })
                            if not update_result['success']:
                                error = 'Failed to generate reset token'
                            else:
                                email_result = send_reset_email(email, reset_token)
                                if not email_result['success']:
                                    error = 'Failed to send reset email'
                                else:
                                    mongo_service.inc_rate_limit(rate_key)
                                    reset_sent = True
                                    success = 'Password reset link sent to your email'
                    except Exception as e:
                        logger.error(f"Forgot password error: {str(e)}")
                        error = 'An error occurred during password reset request. Please try again.'

    if request.cookies.get('email_verified') == '1':
        verification_success = True
        resp = make_response(render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, reset_sent=reset_sent, email=email))
        resp.set_cookie('email_verified', '', expires=0, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
        return resp

    return render_template('auth.html', error=error, success=success, verification_sent=verification_sent, verification_success=verification_success, reset_sent=reset_sent, email=email)

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
        user = mongo_service.get_user_by_id(result['user_id'])
        target = 'age_verification' if not user.get('age_verified', False) else 'questions'
        resp = make_response(redirect(url_for(target)))
        resp.set_cookie('email_verified', '1', max_age=60, path='/', secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
        return resp
    except Exception as e:
        logger.error(f"Verification error: {str(e)}")
        return redirect(url_for('auth', error='An unexpected error occurred during verification.'))

@app.route('/age-verification', methods=['GET', 'POST'])
def age_verification():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    user = mongo_service.get_user_by_id(session['user_id'])
    if user.get('age_verified', False):
        quiz_completed = bool(mongo_service.get_quiz_results(session['user_id']))
        return redirect(url_for('explore') if quiz_completed else url_for('questions'))
    if request.method == 'GET':
        return render_template('age_verification.html')
    if request.method == 'POST':
        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        try:
            # Upload to Cloudinary temporarily
            upload_result = cloudinary.uploader.upload(file, folder="temp_age_verify")
            url = upload_result['secure_url']
            public_id = upload_result['public_id']
            # Send to Age Detector API
            conn = http.client.HTTPSConnection("age-detector.p.rapidapi.com")
            payload = json.dumps({"url": url})
            headers = {
                'x-rapidapi-key': "3ced0e7048msh6cc7c5758e8cccc09p1ab6bajsn7456d8d95695",
                'x-rapidapi-host': "age-detector.p.rapidapi.com",
                'Content-Type': "application/json"
            }
            conn.request("POST", "/age-detection", payload, headers)
            res = conn.getresponse()
            if res.status != 200:
                error_data = res.read().decode("utf-8", errors='ignore')
                raise Exception(f"API error {res.status} {res.reason}: {error_data}")
            data = res.read().decode("utf-8")
            ages = json.loads(data)
            # Delete the temporary image from Cloudinary
            cloudinary.uploader.destroy(public_id)
            if not ages:
                return jsonify({'success': False, 'error': 'No face detected. Please try again.'}), 400
            age = ages[0]['age']
            if age >= 18:
                mongo_service.update_user(session['user_id'], {'age_verified': True})
                return jsonify({'success': True}), 200
            else:
                return jsonify({'success': False, 'error': 'You must be at least 18 years old. If you think this is a mistake, contact joel@ninakkai.com'}), 403
        except Exception as e:
            # Attempt to delete if public_id exists
            if 'public_id' in locals():
                cloudinary.uploader.destroy(public_id)
            logger.error(f"Age verification error: {str(e)}")
            return jsonify({'success': False, 'error': 'Verification failed. Please try again.'}), 500

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_endpoint():
    if request.method == 'GET':
        user = mongo_service.get_user_by_reset_token(token)
        if not user:
            return redirect(url_for('auth', error='Invalid or expired reset link'))
        return render_template('reset_password.html', token=token)

    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if not password or not confirm_password:
            return render_template('reset_password.html', token=token, error='Passwords are required')
        if password != confirm_password:
            return render_template('reset_password.html', token=token, error='Passwords do not match')
        if len(password) < 8:
            return render_template('reset_password.html', token=token, error='Password must be at least 8 characters')
        
        user = mongo_service.get_user_by_reset_token(token)
        if not user:
            return render_template('reset_password.html', token=token, error='Invalid or expired reset link')
        
        result = mongo_service.update_password(user['id'], password)
        if result['success']:
            return redirect(url_for('auth', success='Password reset successfully. Please login.'))
        else:
            return render_template('reset_password.html', token=token, error='Failed to update password')

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({'success': False, 'error': 'Missing passwords'}), 400
    user = mongo_service.get_user_by_id(session['user_id'])
    if not check_password_hash(user['password'], current_password):
        return jsonify({'success': False, 'error': 'Incorrect current password'}), 400
    if len(new_password) < 8:
        return jsonify({'success': False, 'error': 'New password must be at least 8 characters'}), 400
    result = mongo_service.update_password(session['user_id'], new_password)
    return jsonify(result)

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    result = mongo_service.delete_account(session['user_id'])
    if result['success']:
        session.clear()
    return jsonify(result)

@app.route('/mark_notification_read', methods=['POST'])
def mark_notification_read():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    notif_id = data.get('notif_id')
    if not notif_id:
        return jsonify({'success': False, 'error': 'No notification ID provided'}), 400
    result = mongo_service.mark_notification_read(notif_id, session['user_id'])
    return jsonify(result)

@app.route('/clear_notifications', methods=['POST'])
def clear_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    result = mongo_service.clear_notifications(session['user_id'])
    return jsonify(result)

@app.route('/explore')
def explore():
    logger.debug(f"Session in explore: {session}")
    if 'user_id' not in session:
        logger.debug("No user in session for /explore")
        return redirect(url_for('auth', error='Please log in to access the explore page'))
    
    try:
        user = mongo_service.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return redirect(url_for('auth', error='User not found. Please log in again.'))
        
        if not user.get('age_verified', False):
            return redirect(url_for('age_verification'))
        
        quiz_result = mongo_service.get_quiz_results(session['user_id'])
        if not quiz_result:
            return redirect(url_for('questions', error='Please complete the quiz to access the explore page'))
        
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
        
        # Render with empty data, load asynchronously
        resp = make_response(render_template('explore.html', profile=profile, matches=[], discovery=[], error=None))
        resp.headers['Cache-Control'] = 'public, max-age=300'  # Cache the page for 5 mins
        return resp
    except Exception as e:
        logger.error(f"Explore error: {str(e)}")
        return render_template('explore.html', profile={}, matches=[], discovery=[], error='An error occurred while loading the explore page. Please try again.')

@app.route('/api/matches', methods=['GET'])
def api_matches():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        matches = mongo_service.get_filtered_matches(session['user_id'])
        return jsonify({'success': True, 'matches': matches}), 200
    except Exception as e:
        logger.error(f"API matches error: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch matches'}), 500

@app.route('/like-user', methods=['POST'])
def like_user():
    logger.info(f"Like-user route called with session: {session}")
    if 'user_id' not in session:
        logger.warning("Unauthorized access to /like-user")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        matched_user_id = data.get('matched_user_id')
        logger.info(f"Received like request for user_id: {session['user_id']}, matched_user_id: {matched_user_id}")
        if not matched_user_id:
            logger.warning("No matched_user_id provided in /like-user")
            return jsonify({'success': False, 'error': 'No matched user ID provided'}), 400
        result = mongo_service.like_user(session['user_id'], matched_user_id)
        if result['success']:
            logger.info(f"Like successful for user_id: {session['user_id']}, matched_user_id: {matched_user_id}")
            return jsonify(result), 200
        else:
            logger.error(f"Like failed: {result.get('error', 'Unknown error')}")
            return jsonify({'success': False, 'error': result.get('error', 'Failed to like user')}), 500
    except Exception as e:
        logger.error(f"Like user endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/unlike-user', methods=['POST'])
def unlike_user_endpoint():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    matched_user_id = data.get('matched_user_id')
    if not matched_user_id:
        return jsonify({'success': False, 'error': 'No user ID provided'}), 400
    result = mongo_service.unlike_user(session['user_id'], matched_user_id)
    return jsonify(result)

@app.route('/pass-user', methods=['POST'])
def pass_user():
    logger.info(f"Pass-user route called with session: {session}")
    if 'user_id' not in session:
        logger.warning("Unauthorized access to /pass-user")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        passed_user_id = data.get('passed_user_id')
        logger.info(f"Received pass request for user_id: {session['user_id']}, passed_user_id: {passed_user_id}")
        if not passed_user_id:
            logger.warning("No passed_user_id provided in /pass-user")
            return jsonify({'success': False, 'error': 'No user ID provided'}), 400
        result = mongo_service.pass_user(session['user_id'], passed_user_id)
        if result['success']:
            logger.info(f"Pass successful for user_id: {session['user_id']}, passed_user_id: {passed_user_id}")
            return jsonify({'success': True}), 200
        else:
            logger.error(f"Pass failed: {result.get('error', 'Unknown error')}")
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
        third_person_personalities = {
            '🌿 Nurturer': {
                'dominant_type': '🌿 Nurturer',
                'title': '“This person is a Nurturer.”',
                'description': 'They’re gentle, loyal, and always ready to hold space for someone they love. They build relationships with quiet strength and warmth.',
                'tagline': '“Soft-hearted, deep-rooted.”',
                'strengths': ['Gentle', 'Loyal', 'Empathetic'],
                'compatibility': ['🛡️ Protector', '👂 Listener'],
                'color': '#4CAF50'
            },
            '🛡️ Protector': {
                'dominant_type': '🛡️ Protector',
                'title': '“This person is a Protector.”',
                'description': 'They’re grounded, trustworthy, and always ready to stand up for the people they care about. Love means loyalty — and showing up when it matters.',
                'tagline': '“Safe. Steady. Yours.”',
                'strengths': ['Grounded', 'Trustworthy', 'Loyal'],
                'compatibility': ['🌿 Nurturer', '🌙 Dreamer'],
                'color': '#2196F3'
            },
            '🌙 Dreamer': {
                'dominant_type': '🌙 Dreamer',
                'title': '“This person is a Dreamer.”',
                'description': 'They feel deeply and love boldly. They seek the kind of connection that feels written in the stars. They crave the kind of love that makes their soul glow.',
                'tagline': '“Romance is their religion.”',
                'strengths': ['Deep', 'Bold', 'Soulful'],
                'compatibility': ['💘 Romantic', '🌟 Idealist'],
                'color': '#9C27B0'
            },
            '👂 Listener': {
                'dominant_type': '👂 Listener',
                'title': '“This person is a Listener.”',
                'description': 'Calm and thoughtful, they hear more than what’s said. They bring comfort in silence and meaning in presence. They understand that real love sometimes just means being there.',
                'tagline': '“Still waters, true heart.”',
                'strengths': ['Calm', 'Thoughtful', 'Present'],
                'compatibility': ['🌿 Nurturer', '🛡️ Protector'],
                'color': '#03A9F4'
            },
            '💘 Romantic': {
                'dominant_type': '💘 Romantic',
                'title': '“This person is a Romantic.”',
                'description': 'They lead with their heart, express love freely, and long for emotional electricity. They don’t just fall in love — they dive in.',
                'tagline': '“Loving loudly. Feeling deeply.”',
                'strengths': ['Heart-led', 'Expressive', 'Passionate'],
                'compatibility': ['🌙 Dreamer', '🌟 Idealist'],
                'color': '#E91E63'
            },
            '🌟 Idealist': {
                'dominant_type': '🌟 Idealist',
                'title': '“This person is an Idealist.”',
                'description': 'They believe love should feel right — clear, mutual, and beautifully real. You wait for the one who understands your soul.',
                'tagline': '“Only real love will do.”',
                'strengths': ['Believer', 'Clear', 'Soul-seeking'],
                'compatibility': ['🌙 Dreamer', '💘 Romantic'],
                'color': '#FFEB3B'
            },
        }
        dominant_type = quiz_result['scores']['dominant_type'] if quiz_result else 'N/A'
        personality_info = third_person_personalities.get(dominant_type, {
            'dominant_type': dominant_type,
            'title': f'This person is a {dominant_type.replace(" ", "")}.',
            'description': 'Description not available.',
            'tagline': '',
            'strengths': [],
            'compatibility': [],
            'color': '#000000'
        })
        profile = {
            'id': user['id'],
            'full_name': user['full_name'],
            'age': user.get('age'),
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'photos': user.get('photos', []),
            'distance': 'N/A',
            'rating': '4.5',
            'match_percentage': 50,
            'liked': mongo_service.has_liked_user(session['user_id'], user_id),
            'personality': {
                'dominant_type': quiz_result['scores']['dominant_type'] if quiz_result else 'N/A',
                'dominant_percentage': quiz_result['scores']['dominant_percentage'] if quiz_result else 0,
                'secondary_type': quiz_result['scores']['secondary_type'] if quiz_result else 'N/A',
                'secondary_percentage': quiz_result['scores']['secondary_percentage'] if quiz_result else 0
            },
            'personality_info': personality_info
        }
        return jsonify({'success': True, 'user': profile}), 200
    except Exception as e:
        logger.error(f"User profile endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        user_id = session['user_id']
        join_room(user_id)
        logger.info(f"User {user_id} connected and joined room")
    else:
        logger.warning("Unauthorized WebSocket connection attempt")
        return False  # Reject connection

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        user_id = session['user_id']
        leave_room(user_id)
        logger.info(f"User {user_id} disconnected and left room")

@app.route('/send_typing', methods=['POST'])
def send_typing():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    to_user_id = data.get('to_user_id')
    if not to_user_id:
        return jsonify({'success': False, 'error': 'Missing to_user_id'}), 400
    socketio.emit('user_typing', {'sender_id': session['user_id']}, room=to_user_id)
    return jsonify({'success': True})

@app.route('/chat')
def chat():
    logger.debug(f"Session in chat: {session}")
    if 'user_id' not in session:
        logger.debug("No user in session for /chat")
        return redirect(url_for('auth', error='Please log in to access the chat page'))
    user = mongo_service.get_user_by_id(session['user_id'])
    if not user.get('age_verified', False):
        return redirect(url_for('age_verification'))
    try:
        current_user_id = session['user_id']
        user = mongo_service.get_user_by_id(current_user_id)
        if not user:
            session.clear()
            return redirect(url_for('auth', error='User not found. Please log in again.'))
        
        quiz_completed = mongo_service.get_quiz_results(current_user_id)
        if not quiz_completed:
            return redirect(url_for('questions', error='Please complete the quiz to access the chat page'))
        
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
            'dominant_type': quiz_completed['scores']['dominant_type'],
            'dominant_percentage': quiz_completed['scores']['dominant_percentage'],
            'secondary_type': quiz_completed['scores']['secondary_type'],
            'secondary_percentage': quiz_completed['scores']['secondary_percentage']
        }
        
        matched_user_ids = mongo_service.get_matched_users(current_user_id)
        unread_count = chat_service.get_unread_count(current_user_id)
        conversations = []
        for match_id in matched_user_ids:
            user = mongo_service.get_user_by_id(match_id)
            if user:
                last_msg = chat_service.get_last_message(current_user_id, match_id)
                unread = chat_service.get_unread_count_per_user(current_user_id, match_id)
                conv = {
                    'id': user['id'],
                    'full_name': user['full_name'],
                    'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                    'last_message': last_msg['message'] if last_msg else 'Start chatting!',
                    'time': last_msg['timestamp'].isoformat() if last_msg else '',
                    'sort_time': last_msg['timestamp'] if last_msg else datetime.min.replace(tzinfo=timezone.utc),
                    'unread': unread
                }
                conversations.append(conv)
        conversations.sort(key=lambda c: c['sort_time'], reverse=True)
        
        return render_template('chat.html', profile=profile, conversations=conversations, unread_count=unread_count, current_user_id=current_user_id)
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return render_template('chat.html', profile={'image': 'https://randomuser.me/api/portraits/women/44.jpg'}, conversations=[], unread_count=0, error=str(e), current_user_id='')

@app.route('/messages/<other_user_id>', methods=['GET'])
def get_messages(other_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    current_user_id = session['user_id']
    if not mongo_service.is_matched(current_user_id, other_user_id):
        return jsonify({'success': False, 'error': 'Not matched'}), 403
    try:
        messages = chat_service.get_messages(current_user_id, other_user_id)
        if isinstance(messages, dict):
            return jsonify(messages), 400
        else:
            return jsonify({'success': True, 'messages': messages}), 200
    except Exception as e:
        logger.error(f"Get messages endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        to_user_id = data.get('to_user_id')
        message = data.get('message')
        replied_to = data.get('replied_to')
        if not to_user_id or not message:
            return jsonify({'success': False, 'error': 'Missing parameters'}), 400
        current_user_id = session['user_id']
        if not mongo_service.is_matched(current_user_id, to_user_id):
            return jsonify({'success': False, 'error': 'Not matched'}), 403
        result = chat_service.send_message(current_user_id, to_user_id, message, replied_to)
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Failed to send message')}), 500
    except Exception as e:
        logger.error(f"Send message endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete_message', methods=['POST'])
def delete_message_endpoint():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    message_id = data.get('message_id')
    if not message_id:
        return jsonify({'success': False, 'error': 'No message ID provided'}), 400
    try:
        msg = chat_service.messages.find_one({'_id': ObjectId(message_id)})
        if msg and msg['sender_id'] == session['user_id']:
            result = chat_service.delete_message(message_id, msg['sender_id'], msg['receiver_id'])
            return jsonify(result)
        else:
            return jsonify({'success': False, 'error': 'Not authorized or not found'})
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/block_user', methods=['POST'])
def block_user_endpoint():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    blocked_user_id = data.get('blocked_user_id')
    if not blocked_user_id:
        return jsonify({'success': False, 'error': 'No user ID provided'}), 400
    result = mongo_service.block_user(session['user_id'], blocked_user_id)
    return jsonify(result)

@app.route('/profile')
def profile():
    logger.debug(f"Session in profile: {session}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /profile")
        return redirect(url_for('auth'))
    user = mongo_service.get_user_by_id(session['user_id'])
    if not user.get('age_verified', False):
        return redirect(url_for('age_verification'))
    try:
        user = mongo_service.get_user_by_id(session['user_id'])
        if not user:
            return render_template('profile.html', profile={}, pending_likers=[], notifications=[])
        quiz_result = mongo_service.get_quiz_results(session['user_id'])
        # Define personalities dict
        personalities = {
            '🌿 Nurturer': {
                'dominant_type': '🌿 Nurturer',
                'title': '“You are a Nurturer.”',
                'description': 'You’re gentle, loyal, and always ready to hold space for someone you love. You build relationships with quiet strength and warmth.',
                'tagline': '“Soft-hearted, deep-rooted.”',
                'strengths': ['Gentle', 'Loyal', 'Empathetic'],  # Add some strengths
                'compatibility': ['🛡️ Protector', '👂 Listener'],  # Examples
                'color': '#4CAF50'  # Green
            },
            '🛡️ Protector': {
                'dominant_type': '🛡️ Protector',
                'title': '“You are a Protector.”',
                'description': 'You’re grounded, trustworthy, and always ready to stand up for the people you care about. Love means loyalty — and showing up when it matters.',
                'tagline': '“Safe. Steady. Yours.”',
                'strengths': ['Grounded', 'Trustworthy', 'Loyal'],
                'compatibility': ['🌿 Nurturer', '🌙 Dreamer'],
                'color': '#2196F3'  # Blue
            },
            '🌙 Dreamer': {
                'dominant_type': '🌙 Dreamer',
                'title': '“You are a Dreamer.”',
                'description': 'You feel deeply and love boldly. You seek the kind of connection that feels written in the stars. You crave the kind of love that makes your soul glow.',
                'tagline': '“Romance is your religion.”',
                'strengths': ['Deep', 'Bold', 'Soulful'],
                'compatibility': ['💘 Romantic', '🌟 Idealist'],
                'color': '#9C27B0'  # Purple
            },
            '👂 Listener': {
                'dominant_type': '👂 Listener',
                'title': '“You are a Listener.”',
                'description': 'Calm and thoughtful, you hear more than what’s said. You bring comfort in silence and meaning in presence. You understand that real love sometimes just means being there.',
                'tagline': '“Still waters, true heart.”',
                'strengths': ['Calm', 'Thoughtful', 'Present'],
                'compatibility': ['🌿 Nurturer', '🛡️ Protector'],
                'color': '#03A9F4'  # Light Blue
            },
            '💘 Romantic': {
                'dominant_type': '💘 Romantic',
                'title': '“You are a Romantic.”',
                'description': 'You lead with your heart, express love freely, and long for emotional electricity. You don’t just fall in love — you dive in.',
                'tagline': '“Loving loudly. Feeling deeply.”',
                'strengths': ['Heart-led', 'Expressive', 'Passionate'],
                'compatibility': ['🌙 Dreamer', '🌟 Idealist'],
                'color': '#E91E63'  # Pink
            },
            '🌟 Idealist': {
                'dominant_type': '🌟 Idealist',
                'title': '“You are an Idealist.”',
                'description': 'You believe love should feel right — clear, mutual, and beautifully real. You wait for the one who understands your soul.',
                'tagline': '“Only real love will do.”',
                'strengths': ['Believer', 'Clear', 'Soul-seeking'],
                'compatibility': ['🌙 Dreamer', '💘 Romantic'],
                'color': '#FFEB3B'  # Yellow
            },
        }
        dominant_type = quiz_result['scores']['dominant_type'] if quiz_result else 'N/A'
        personality = personalities.get(dominant_type, {
            'dominant_type': dominant_type,
            'title': f'You are a {dominant_type.replace(" ", "")}.',
            'description': 'Description not available.',
            'tagline': '',
            'strengths': [],
            'compatibility': [],
            'color': '#000000'
        })
        # Format personality_info as HTML
        personality_info = f"""
        <strong>{personality['title']}</strong><br>
        {personality['description']}<br>
        <em>{personality['tagline']}</em><br>
        <strong>Strengths:</strong> {', '.join(personality['strengths'])}<br>
        <strong>Compatibility:</strong> {', '.join(personality['compatibility'])}
        """
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
            'dominant_type': dominant_type,
            'dominant_percentage': quiz_result['scores']['dominant_percentage'] if quiz_result else 0,
            'personality_info': personality_info
        }
        pending_likers = mongo_service.get_pending_likers(session['user_id'])
        notifications = mongo_service.get_notifications(session['user_id'])
        return render_template('profile.html', profile=profile, pending_likers=pending_likers, notifications=notifications)
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return render_template('profile.html', profile={}, pending_likers=[], notifications=[])

@app.route('/questions', methods=['GET'])
def questions():
    logger.debug(f"Session in questions: {session}")
    logger.debug(f"Incoming cookies: {request.cookies}")
    if 'user_id' not in session:
        logger.debug("No user_id in session for /questions")
        return redirect(url_for('auth'))
    user = mongo_service.get_user_by_id(session['user_id'])
    if not user.get('age_verified', False):
        return redirect(url_for('age_verification'))
    retake = request.args.get('retake') == 'true'
    if retake:
        mongo_service.delete_quiz_results(session['user_id'])
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

@app.route('/personality_results', methods=['GET'])
def personality_results():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    quiz_result = mongo_service.get_quiz_results(session['user_id'])
    if not quiz_result:
        return jsonify({'success': False, 'error': 'No quiz results found'}), 404
    dominant_type = quiz_result['scores']['dominant_type']
    # Now, map to the descriptions
    personalities = {
        '🌿 Nurturer': {
            'dominant_type': '🌿 Nurturer',
            'title': '“You are a Nurturer.”',
            'description': 'You’re gentle, loyal, and always ready to hold space for someone you love. You build relationships with quiet strength and warmth.',
            'tagline': '“Soft-hearted, deep-rooted.”',
            'strengths': ['Gentle', 'Loyal', 'Empathetic'],  # Add some strengths
            'compatibility': ['🛡️ Protector', '👂 Listener'],  # Examples
            'color': '#4CAF50'  # Green
        },
        '🛡️ Protector': {
            'dominant_type': '🛡️ Protector',
            'title': '“You are a Protector.”',
            'description': 'You’re grounded, trustworthy, and always ready to stand up for the people you care about. Love means loyalty — and showing up when it matters.',
            'tagline': '“Safe. Steady. Yours.”',
            'strengths': ['Grounded', 'Trustworthy', 'Loyal'],
            'compatibility': ['🌿 Nurturer', '🌙 Dreamer'],
            'color': '#2196F3'  # Blue
        },
        '🌙 Dreamer': {
            'dominant_type': '🌙 Dreamer',
            'title': '“You are a Dreamer.”',
            'description': 'You feel deeply and love boldly. You seek the kind of connection that feels written in the stars. You crave the kind of love that makes your soul glow.',
            'tagline': '“Romance is your religion.”',
            'strengths': ['Deep', 'Bold', 'Soulful'],
            'compatibility': ['💘 Romantic', '🌟 Idealist'],
            'color': '#9C27B0'  # Purple
        },
        '👂 Listener': {
            'dominant_type': '👂 Listener',
            'title': '“You are a Listener.”',
            'description': 'Calm and thoughtful, you hear more than what’s said. You bring comfort in silence and meaning in presence. You understand that real love sometimes just means being there.',
            'tagline': '“Still waters, true heart.”',
            'strengths': ['Calm', 'Thoughtful', 'Present'],
            'compatibility': ['🌿 Nurturer', '🛡️ Protector'],
            'color': '#03A9F4'  # Light Blue
        },
        '💘 Romantic': {
            'dominant_type': '💘 Romantic',
            'title': '“You are a Romantic.”',
            'description': 'You lead with your heart, express love freely, and long for emotional electricity. You don’t just fall in love — you dive in.',
            'tagline': '“Loving loudly. Feeling deeply.”',
            'strengths': ['Heart-led', 'Expressive', 'Passionate'],
            'compatibility': ['🌙 Dreamer', '🌟 Idealist'],
            'color': '#E91E63'  # Pink
        },
        '🌟 Idealist': {
            'dominant_type': '🌟 Idealist',
            'title': '“You are an Idealist.”',
            'description': 'You believe love should feel right — clear, mutual, and beautifully real. You wait for the one who understands your soul.',
            'tagline': '“Only real love will do.”',
            'strengths': ['Believer', 'Clear', 'Soul-seeking'],
            'compatibility': ['🌙 Dreamer', '💘 Romantic'],
            'color': '#FFEB3B'  # Yellow
        },
    }
    personality_info = personalities.get(dominant_type, {
        'dominant_type': dominant_type,
        'title': f'You are a {dominant_type.replace(" ", "")}.',
        'description': 'Description not available.',
        'tagline': '',
        'strengths': [],
        'compatibility': [],
        'color': '#000000'
    })
    return jsonify({'success': True, 'personality_info': personality_info})

@app.route('/logout', methods=['GET'])
def logout():
    logger.debug(f"Session in logout: {session}")
    session.clear()
    return jsonify({'success': True})

@app.route('/upload_profile_picture', methods=['POST'])
def upload_profile_picture():
    logger.info("Upload profile picture request received")
    if 'user_id' not in session:
        logger.warning("Unauthorized access to upload_profile_picture")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    file = request.files.get('file')
    if not file:
        logger.warning("No file provided in upload_profile_picture")
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    try:
        logger.info("Attempting to upload profile picture to Cloudinary")
        config = cloudinary.config()
        if not (config.cloud_name and config.api_key and config.api_secret):
            logger.error("Cloudinary configuration missing")
            return jsonify({'success': False, 'error': 'Cloudinary configuration missing'}), 500
        upload_result = cloudinary.uploader.upload(file, folder="profile_pictures")
        url = upload_result['secure_url']
        logger.info(f"Uploaded profile picture URL: {url}")
        update_result = mongo_service.update_user(session['user_id'], {'image': url})
        if update_result['success']:
            logger.info("User profile picture updated successfully in database")
            return jsonify({'success': True, 'url': url}), 200
        else:
            logger.error("Failed to update user profile picture in database")
            return jsonify({'success': False, 'error': 'Failed to update profile picture in database'}), 500
    except Exception as e:
        logger.error(f"Upload profile picture error: {str(e)}")
        return jsonify({'success': False, 'error': f"Upload failed: {str(e)}"}), 500

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    logger.info("Upload photo request received")
    if 'user_id' not in session:
        logger.warning("Unauthorized access to upload_photo")
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    file = request.files.get('file')
    if not file:
        logger.warning("No file provided in upload_photo")
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    user = mongo_service.get_user_by_id(session['user_id'])
    if len(len(user.get('photos', []))) >= 7:
        logger.warning("Maximum photos limit reached")
        return jsonify({'success': False, 'error': 'Maximum 7 photos allowed'}), 400
    try:
        logger.info("Attempting to upload photo to Cloudinary")
        config = cloudinary.config()
        if not (config.cloud_name and config.api_key and config.api_secret):
            logger.error("Cloudinary configuration missing")
            return jsonify({'success': False, 'error': 'Cloudinary configuration missing'}), 500
        upload_result = cloudinary.uploader.upload(file, folder="user_photos")
        url = upload_result['secure_url']
        logger.info(f"Uploaded photo URL: {url}")
        photos = user.get('photos', []) + [url]
        update_result = mongo_service.update_user(session['user_id'], {'photos': photos})
        if update_result['success']:
            # Notify matched users
            matches = mongo_service.get_matched_users(session['user_id'])
            for match_id in matches:
                mongo_service.add_notification(match_id, f"{user['full_name']} uploaded a new picture", 'new_photo', session['user_id'])
            logger.info("User photos updated successfully in database")
            return jsonify({'success': True, 'url': url}), 200
        else:
            logger.error("Failed to update user photos in database")
            return jsonify({'success': False, 'error': 'Failed to update photos in database'}), 500
    except Exception as e:
        logger.error(f"Upload photo error: {str(e)}")
        return jsonify({'success': False, 'error': f"Upload failed: {str(e)}"}), 500

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
    socketio.run(app, host='0.0.0.0', port=5050, debug=True)
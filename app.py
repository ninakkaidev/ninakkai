import eventlet
eventlet.monkey_patch(thread=False)  # Disable thread patching to avoid Werkzeug local issues

from flask import Flask, request, make_response, session, render_template, redirect, url_for, send_from_directory, jsonify, Response
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
import cloudinary.api
import pytz
import json
import http.client
import requests
import time

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
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_NAME='for_you_session',
    SESSION_COOKIE_PATH='/',
    SESSION_COOKIE_DOMAIN=None
)

# Initialize Cloudinary
configure_cloudinary()

# Personalities dictionary
PERSONALITIES = {
    '🌿 Nurturer': {
        'dominant_type': '🌿 Nurturer',
        'title': '“You are a Nurturer.”',
        'description': 'You’re gentle, loyal, and always ready to hold space for someone you love. You build relationships with quiet strength and warmth.',
        'tagline': '“Soft-hearted, deep-rooted.”',
        'strengths': ['Gentle', 'Loyal', 'Empathetic'],
        'compatibility': ['🛡️ Protector', '👂 Listener'],
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

# Question types configuration
QUESTION_TYPES = {
    'req1': ["👂 Listener", "💘 Romantic", "🌙 Dreamer", "🛡️ Protector"],
    'req2': ["🛡️ Protector", "🌿 Nurturer", "👂 Listener", "💘 Romantic"],
    'req3': ["🌿 Nurturer", "🛡️ Protector", "👂 Listener", "💘 Romantic"],
    'req4': ["👂 Listener", "💘 Romantic", "🛡️ Protector", "🌙 Dreamer"],
    'req5': ["🌿 Nurturer", "🛡️ Protector", "🌟 Idealist", "👂 Listener"],
    'req6': ["🌿 Nurturer", "💘 Romantic", "🌟 Idealist", "🌙 Dreamer"],
    'req7': ["🌙 Dreamer", "💘 Romantic", "🌿 Nurturer", "🛡️ Protector"],
    'req8': ["🌙 Dreamer", "🛡️ Protector", "🌟 Idealist", "👂 Listener"],
    'req9': ["🛡️ Protector", "🌿 Nurturer", "👂 Listener", "🌟 Idealist"],
    'req10': ["🛡️ Protector", "👂 Listener", "🌟 Idealist", "🌿 Nurturer"],
    'opt1': ["🌿 Nurturer", "👂 Listener", "💘 Romantic", "🛡️ Protector"],
    'opt2': ["👂 Listener", "🌿 Nurturer", "🛡️ Protector", "🌙 Dreamer"],
    'opt3': ["👂 Listener", "🛡️ Protector", "🌙 Dreamer", "🌟 Idealist"],
    'opt4': ["🌟 Idealist", "👂 Listener", "🌙 Dreamer", "🛡️ Protector"],
    'opt5': ["🛡️ Protector", "🌿 Nurturer", "💘 Romantic", "👂 Listener"],
    'opt6': ["🛡️ Protector", "🌿 Nurturer", "💘 Romantic", "🌟 Idealist"],
}

class MongoService:
    def __init__(self):
        self.uri = os.getenv('MONGODB_URI', "mongodb+srv://ninakkaiforyou:9t2GADiJUf8xFhDZ@cluster0.fdoiudh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
        self.client = MongoClient(self.uri, tlsAllowInvalidCertificates=True)
        self.db = self.client['ninakkai']
        self.users = self.db['users']
        self.quiz_results = self.db['quiz_results']
        self.likes = self.db['likes']
        self.passes = self.db['passes']
        self.notifications = self.db['notifications']
        self.reports = self.db['reports']

    def check_rate_limit(self, key: str, max_attempts: int, period: timedelta = timedelta(hours=1)) -> bool:
        now = datetime.now(timezone.utc)
        limit = self.db['rate_limits'].find_one({'key': key})
        if limit:
            last_reset = limit['last_reset']
            last_reset = pytz.UTC.localize(last_reset) if last_reset.tzinfo is None else last_reset
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
                default_image = 'https://i.ibb.co/tTg9CkS/653324ed-3b9c-48b1-b9b2-d1d8b16931ff.png'
            elif gender == 'female':
                default_image = 'https://i.ibb.co/KpKdK9xy/8e2b61f2-44cc-43cd-bc55-e5ebcaae9130.png'
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
                'age_verified': False,
                'verification_token': verification_token,
                'created_at': datetime.now(timezone.utc),
                'religion': None,
                'religion_importance': 'skip',
                'religion_public': False,
                'physical_public': False,
                'physical_importance': 'not_important',
                'physical_preferences': [],
                'physical_traits': [],
                'filter_settings': [],
                'profile_data': [],
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

            # Parse optional from answers and update user
            update_data = {}
            for ans in quiz_data['answers']:
                if 'section' in ans:
                    if ans['section'] == 'religion_importance':
                        importance_map = {
                            0: 'high',
                            1: 'medium',
                            2: 'low',
                            3: 'skip'
                        }
                        update_data['religion_importance'] = importance_map.get(ans.get('index'), 'skip')
                    elif ans['section'] == 'religion':
                        update_data['religion'] = ans.get('value')
                    elif ans['section'] == 'physical_preferences':
                        importance_map = {
                            0: 'very_important',
                            1: 'somewhat_important',
                            2: 'not_important'
                        }
                        update_data['physical_importance'] = importance_map.get(ans.get('index'), 'not_important')
                    elif ans['section'] == 'physical_traits_preferred':
                        update_data['physical_preferences'] = ans.get('responses', [])
                    elif ans['section'] == 'physical_traits_own':
                        update_data['physical_traits'] = ans.get('responses', [])
                    elif ans['section'] == 'filter_settings':
                        update_data['filter_settings'] = ans.get('toggles', [])
                    elif ans['section'] == 'profile_setup':
                        update_data['profile_data'] = ans.get('responses', [])

            if update_data:
                self.update_user(user_id, update_data)

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

    def _calculate_scores(self, answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        type_counts = {}
        mandatory_answers = [a for a in answers if 'question_id' in a and a['question_id'].startswith('req')]
        for answer in mandatory_answers:
            if 'type' in answer:
                answer_type = answer['type']
                type_counts[answer_type] = type_counts.get(answer_type, 0) + 1
        optional_answers = [a for a in answers if 'question_id' in a and a['question_id'].startswith('opt')]
        for answer in optional_answers:
            if 'type' in answer:
                answer_type = answer['type']
                type_counts[answer_type] = type_counts.get(answer_type, 0.0) + 0.2  # Little variation for optional
        if not type_counts:
            return {'dominant_type': None, 'dominant_percentage': 0}
        # Resolve tie if any
        max_count = max(type_counts.values())
        tied_types = [t for t, cnt in type_counts.items() if cnt == max_count]
        if len(tied_types) > 1:
            q2_answer = next((ans for ans in answers if ans.get('question_id') == 'req2'), None)
            if q2_answer:
                ranked_types = self._parse_ranked_types(q2_answer)
                dominant_type = self._resolve_tie_with_ranking(tied_types, ranked_types)
            else:
                dominant_type = tied_types[0]
        else:
            dominant_type = max(type_counts, key=type_counts.get)
        # Keeper Seeker
        ks_answers = [a for a in answers if 'question_id' in a and a['question_id'].startswith('ks')]
        keeper_count = sum(1 for a in ks_answers if a.get('keeperSeeker') == 'Keeper')
        seeker_count = len(ks_answers) - keeper_count
        if keeper_count > seeker_count:
            keeper_seeker = "Keeper"
        elif seeker_count > keeper_count:
            keeper_seeker = "Seeker"
        else:
            keeper_seeker = None
        # Optional boosts
        optional_boosts = self._calculate_optional_boosts(dominant_type, optional_answers)
        # Total for percentages
        total = sum(type_counts.values())
        dominant_score = type_counts.get(dominant_type, 0)
        dominant_percentage = int((dominant_score / total) * 100) if total > 0 else 0
        secondary_type = None
        secondary_score = 0
        secondary_percentage = 0
        temp_counts = type_counts.copy()
        if dominant_type in temp_counts:
            del temp_counts[dominant_type]
        if temp_counts:
            secondary_type = max(temp_counts, key=temp_counts.get)
            secondary_score = temp_counts[secondary_type]
            secondary_percentage = int((secondary_score / total) * 100) if total > 0 else 0
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

    def _parse_ranked_types(self, ranked_answer: Dict[str, Any]) -> List[str]:
        ranking = ranked_answer.get('ranking', [])
        if not ranking:
            return []
        # Sort by rank ascending (1 is highest)
        sorted_ranking = sorted(ranking, key=lambda r: r['rank'])
        item_to_type = {
            "Trust": "🛡️ Protector",
            "Emotional connection": "🌿 Nurturer",
            "Shared goals": "👂 Listener",
            "Physical intimacy": "💘 Romantic"
        }
        # Actually, since types are associated with answers indices
        return [QUESTION_TYPES['req2'][r['index']] for r in sorted_ranking]

    def _resolve_tie_with_ranking(self, tied_types: List[str], ranked_types: List[str]) -> str:
        for type_ in ranked_types:
            if type_ in tied_types:
                return type_
        return tied_types[0]

    def _calculate_optional_boosts(self, dominant_type: str, optional_answers: List[Dict[str, Any]]) -> Dict[str, int]:
        boosts = {}
        for answer in optional_answers:
            if 'type' in answer:
                answer_type = answer['type']
                if answer_type == dominant_type:
                    boosts[dominant_type] = boosts.get(dominant_type, 0) + 1
                elif answer_type in boosts:
                    boosts[answer_type] += 1
        return boosts

    def get_quiz_results(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            result = self.quiz_results.find_one({'user_id': user_id})
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
            result = self.quiz_results.delete_many({'user_id': user_id})
            return {'success': True, 'deleted_count': result.deleted_count}
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
            
            # Get user preferences
            religion_importance = current_user.get('religion_importance', 'skip')
            user_religion = current_user.get('religion')
            physical_importance = current_user.get('physical_importance', 'not_important')
            physical_preferences = current_user.get('physical_preferences', [])
            user_ks = user_scores.get('keeper_seeker_type')
            filter_settings = current_user.get('filter_settings', [])
            show_only_preferred_physical = any(t['value'] for t in filter_settings if t['label'] == 'Show only preferred physical traits')
            
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id}})
            matches = []
            
            for other_user in all_users:
                other_scores = other_user['scores']
                other_user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                
                if not other_user_data or other_user_data['gender'] == current_user['gender']:
                    continue
                
                # Step 1: Readiness filter
                other_ks = other_scores.get('keeper_seeker_type')
                if user_ks and other_ks and user_ks != other_ks:
                    continue  # No mismatch allowed
                
                # Step 2: Emotional compatibility
                match_percentage = self._calculate_match_percentage(user_scores, other_scores)
                
                # Step 3: Religion preferences
                if religion_importance != 'skip' and user_religion:
                    other_religion = other_user_data.get('religion')
                    is_same_religion = other_religion == user_religion
                    if religion_importance == 'high' and not is_same_religion:
                        continue
                    elif is_same_religion:
                        if religion_importance == 'medium':
                            match_percentage += 10
                        elif religion_importance == 'low':
                            match_percentage += 5
                
                # Step 4: Physical preferences
                if physical_importance != 'not_important' and physical_preferences:
                    other_physical = other_user_data.get('physical_traits', [])
                    physical_match_score = self._calculate_physical_match(physical_preferences, other_physical)
                    
                    if physical_importance == 'very_important':
                        if physical_match_score < 1.0:
                            continue
                    elif physical_importance == 'somewhat_important':
                        match_percentage += int(10 * physical_match_score)
                    
                    # Apply filter if set
                    if show_only_preferred_physical and physical_match_score < 1.0:
                        continue
                
                match_percentage = min(match_percentage, 100)
                
                matches.append({
                    'id': str(other_user_data['_id']),
                    'full_name': other_user_data['full_name'],
                    'age': other_user_data.get('age'),
                    'gender': other_user_data.get('gender'),
                    'image': other_user_data.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                    'occupation': other_user_data.get('occupation', 'N/A'),
                    'bio': other_user_data.get('bio', 'No bio available'),
                    'interests': other_user_data.get('interests', []),
                    'distance': 'N/A',
                    'rating': '4.5',
                    'dominant_type': other_scores['dominant_type'],
                    'match_percentage': match_percentage,
                    'keeper_seeker': other_scores.get('keeper_seeker_type', 'Unknown'),
                    'liked': self.has_liked_user(user_id, str(other_user_data['_id'])),
                    'passed': self.has_passed_user(user_id, str(other_user_data['_id']))
                })
            
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:20]
        except Exception as e:
            logger.error(f"Find matches error: {str(e)}")
            return []

    def get_potential_matches(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            current_user = self.get_user_by_id(user_id)
            if not current_user:
                return []
                
            user_quiz = self.get_quiz_results(user_id)
            if not user_quiz:
                return []
                
            user_scores = user_quiz['scores']
            dominant_type = user_scores['dominant_type']
            
            # Get user preferences
            religion_importance = current_user.get('religion_importance', 'skip')
            user_religion = current_user.get('religion')
            physical_importance = current_user.get('physical_importance', 'not_important')
            physical_preferences = current_user.get('physical_preferences', [])
            user_ks = user_scores.get('keeper_seeker_type')
            filter_settings = current_user.get('filter_settings', [])
            show_only_preferred_physical = any(t['value'] for t in filter_settings if t['label'] == 'Show only preferred physical traits')
            
            all_users = self.quiz_results.find({'user_id': {'$ne': user_id}})
            matches = []
            
            for other_user in all_users:
                other_scores = other_user['scores']
                other_user_data = self.users.find_one({'_id': ObjectId(other_user['user_id'])})
                
                if not other_user_data or other_user_data['gender'] == current_user['gender']:
                    continue
                
                # Step 1: Readiness filter
                other_ks = other_scores.get('keeper_seeker_type')
                if user_ks and other_ks and user_ks != other_ks:
                    continue  # No mismatch allowed
                
                # Step 2: Emotional compatibility
                match_percentage = self._calculate_match_percentage(user_scores, other_scores)
                
                # Step 3: Religion preferences
                if religion_importance != 'skip' and user_religion:
                    other_religion = other_user_data.get('religion')
                    is_same_religion = other_religion == user_religion
                    if religion_importance == 'high' and not is_same_religion:
                        continue
                    elif is_same_religion:
                        if religion_importance == 'medium':
                            match_percentage += 10
                        elif religion_importance == 'low':
                            match_percentage += 5
                
                # Step 4: Physical preferences
                if physical_importance != 'not_important' and physical_preferences:
                    other_physical = other_user_data.get('physical_traits', [])
                    physical_match_score = self._calculate_physical_match(physical_preferences, other_physical)
                    
                    if physical_importance == 'very_important':
                        if physical_match_score < 1.0:
                            continue
                    elif physical_importance == 'somewhat_important':
                        match_percentage += int(10 * physical_match_score)
                    
                    # Apply filter if set
                    if show_only_preferred_physical and physical_match_score < 1.0:
                        continue
                
                match_percentage = min(match_percentage, 100)
                
                matches.append({
                    'id': str(other_user_data['_id']),
                    'full_name': other_user_data['full_name'],
                    'age': other_user_data.get('age'),
                    'gender': other_user_data.get('gender'),
                    'image': other_user_data.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
                    'occupation': other_user_data.get('occupation', 'N/A'),
                    'bio': other_user_data.get('bio', 'No bio available'),
                    'interests': other_user_data.get('interests', []),
                    'distance': 'N/A',
                    'rating': '4.5',
                    'dominant_type': other_scores['dominant_type'],
                    'match_percentage': match_percentage,
                    'keeper_seeker': other_scores.get('keeper_seeker_type', 'Unknown'),
                    'liked': self.has_liked_user(user_id, str(other_user_data['_id'])),
                    'passed': self.has_passed_user(user_id, str(other_user_data['_id']))
                })
            
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:20]
        except Exception as e:
            logger.error(f"Get potential matches error: {str(e)}")
            return []

    def _calculate_physical_match(self, preferences: List, traits: List) -> float:
        if not preferences or not traits:
            return 1.0  # Full match if no preferences
        
        match_score = 0
        total_comparisons = 0
        
        pref_dict = {p['label']: p['value'] for p in preferences if p['value'] != 'No Preference'}
        trait_dict = {t['label']: t['value'] for t in traits}
        
        for label, pref_val in pref_dict.items():
            total_comparisons += 1
            if label in trait_dict:
                trait_val = trait_dict[label]
                if 'height' in label.lower():
                    try:
                        p = int(pref_val)
                        t = int(trait_val)
                        if abs(p - t) <= 10:
                            match_score += 1
                    except:
                        pass
                elif pref_val == trait_val:
                    match_score += 1
        
        return match_score / total_comparisons if total_comparisons > 0 else 1.0

    def _calculate_match_percentage(self, user_scores: Dict[str, Any], other_scores: Dict[str, Any]) -> int:
        try:
            user_types = user_scores.get('type_counts', {})
            other_types = other_scores.get('type_counts', {})
            all_types = set(user_types.keys()).union(other_types.keys())
            similarity = 0
            total = 0
            for t in all_types:
                u = user_types.get(t, 0)
                o = other_types.get(t, 0)
                similarity += min(u, o)
                total += max(u, o)
            base_percentage = int((similarity / total * 100) if total > 0 else 50)

            # Add bonuses
            keeper_seeker_bonus = 15 if user_scores.get('keeper_seeker_type') == other_scores.get('keeper_seeker_type') else 0

            return min(base_percentage + keeper_seeker_bonus, 100)
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

    def report_user(self, reporter_id: str, reported_id: str, reason: str) -> Dict[str, Any]:
        try:
            report_data = {
                'reporter_id': reporter_id,
                'reported_id': reported_id,
                'reason': reason,
                'timestamp': datetime.now(timezone.utc),
                'status': 'pending'
            }
            result = self.reports.insert_one(report_data)
            logger.info(f"Report submitted: reporter {reporter_id}, reported {reported_id}, reason {reason}")
            return {'success': True, 'report_id': str(result.inserted_id)}
        except Exception as e:
            logger.error(f"Report user error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def is_liked(self, user_id: str, matched_user_id: str) -> bool:
        return self.has_liked_user(user_id, matched_user_id)

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
                        'liked': self.has_liked_user(user_id, str(user_data['_id'])),
                        'passed': self.has_passed_user(user_id, str(user_data['_id']))
                    })
            return sorted(matches, key=lambda x: x['match_percentage'], reverse=True)[:10]
        except Exception as e:
            logger.error(f"Search matches error: {str(e)}")
            return []

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
            self.reports.delete_many({'$or': [{'reporter_id': user_id}, {'reported_id': user_id}]})
            return {'success': True}
        except Exception as e:
            logger.error(f"Delete account error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def has_liked_user(self, user_id: str, matched_user_id: str) -> bool:
        try:
            like = self.likes.find_one({'user_id': user_id, 'matched_user_id': matched_user_id})
            return bool(like)
        except Exception as e:
            logger.error(f"Has liked user error: {str(e)}")
            return False

    def has_passed_user(self, user_id: str, passed_user_id: str) -> bool:
        try:
            passed = self.passes.find_one({'user_id': user_id, 'passed_user_id': passed_user_id})
            return bool(passed)
        except Exception as e:
            logger.error(f"Has passed user error: {str(e)}")
            return False

    def unlike_user(self, user_id: str, matched_user_id: str) -> Dict[str, Any]:
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
                n['timestamp'] = n['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
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
        self.client = MongoClient(self.uri, tlsAllowInvalidCertificates=True)
        try:
            self.client.admin.command('ping')
            logger.info("Chat MongoDB connection successful")
        except Exception as e:
            logger.error(f"Chat MongoDB connection failed: {str(e)}")
        self.db = self.client['chat_db']
        self.messages = self.db['messages']
        self.typing = self.db['typing']
        self.typing.create_index("timestamp", expireAfterSeconds=10)

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
            is_typing = self.is_typing(user2, user1)
            return {'success': True, 'messages': msgs, 'is_typing': is_typing}
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
            return {'success': result.deleted_count > 0}
        except Exception as e:
            logger.error(f"Delete message error: {str(e)}")
            return {'success': False, 'error': str(e)}

    def start_typing(self, from_id: str, to_id: str):
        try:
            self.typing.update_one(
                {'from_id': from_id, 'to_id': to_id},
                {'$set': {'timestamp': datetime.now(timezone.utc)}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Start typing error: {str(e)}")

    def stop_typing(self, from_id: str, to_id: str):
        try:
            self.typing.delete_one({'from_id': from_id, 'to_id': to_id})
        except Exception as e:
            logger.error(f"Stop typing error: {str(e)}")

    def is_typing(self, from_id: str, to_id: str) -> bool:
        try:
            return bool(self.typing.find_one({'from_id': from_id, 'to_id': to_id}))
        except Exception as e:
            logger.error(f"Is typing error: {str(e)}")
            return False

mongo_service = MongoService()
chat_service = ChatService()

def send_verification_email(email: str, verification_token: str) -> Dict[str, Any]:
    try:
        smtp_server = 'smtp.gmail.com'
        smtp_port = '587'
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
        return {'success':False, 'error': str(e)}

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
    logger.debug(f"Verify-email session: {session}")
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
    if request.method == 'GET':
        if 'user_id' not in session:
            return redirect(url_for('auth'))
        user = mongo_service.get_user_by_id(session['user_id'])
        if user.get('age_verified', False):
            quiz_completed = bool(mongo_service.get_quiz_results(session['user_id']))
            return redirect(url_for('explore') if quiz_completed else url_for('questions'))
        return render_template('age_verification.html')

    if request.method == 'POST':
        # For POST, always return JSON – no redirects
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Session expired. Please log in again.', 'redirect': url_for('auth')}), 401
        
        user = mongo_service.get_user_by_id(session['user_id'])
        if user.get('age_verified', False):
            quiz_completed = bool(mongo_service.get_quiz_results(session['user_id']))
            redirect_to = url_for('explore') if quiz_completed else url_for('questions')
            return jsonify({'success': True, 'already_verified': True, 'redirect': redirect_to}), 200

        file = request.files.get('image')
        if not file:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        try:
            api_url = "https://sure-myrilla-mhdashikofficial-61e061ec.koyeb.app/predict"
            api_key = "74303dce-713f-4b91-829e-7e0a6c76a25c"
            headers = {"x-api-key": api_key}
            file.seek(0)  # Reset file pointer if needed
            file_bytes = file.read()
            files = {'file': ('image.jpg', file_bytes, 'image/jpeg')}
            retries = 0
            max_retries = 10
            while retries < max_retries:
                resp = requests.post(api_url, files=files, headers=headers, timeout=30)
                if resp.status_code == 200:
                    break
                elif resp.status_code == 503:
                    retries += 1
                    wait_time = 5 * retries
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"API response error: status {resp.status_code}, body: {resp.text}")
                    return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            if retries == max_retries:
                return jsonify({'success': False, 'error': 'Service unavailable after retries. Try again later.'}), 503

            data = resp.json()
            logger.info(f"API response data: {data}")  # Log for debugging
            results = data.get('results', [])
            if not results:
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 400
            prediction = results[0]
            if 'age' not in prediction:
                logger.error(f"Invalid API response - missing age: {prediction}")
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            age_group = prediction['age']
            if not isinstance(age_group, str) or not age_group.startswith('(') or not age_group.endswith(')'):
                logger.error(f"Unexpected age group format: {age_group}")
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            # Parse age, handle potential formats more robustly
            try:
                inner = age_group[1:-1]  # Remove parentheses
                age_lower, age_upper = map(int, inner.split('-'))
            except ValueError as ve:
                logger.error(f"Age parsing error: {ve}, age_group: {age_group}")
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            if 'gender' not in prediction:
                logger.error(f"Missing gender in prediction: {prediction}")
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            detected_gender = prediction['gender'].lower()
            if detected_gender != user['gender']:
                return jsonify({'success': False, 'error': 'Detected gender does not match registered gender. Try again or contact help`@ninakkai.com'}), 403
            if age_lower < 18:
                return jsonify({'success': False, 'error': 'You must be at least 18 years old. If you think this is a mistake, contact joel@ninakkai.com'}), 403
            update_result = mongo_service.update_user(session['user_id'], {'age_verified': True})
            if not update_result['success']:
                logger.error("Failed to update age_verified in DB")
                return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
            return jsonify({'success': True, 'redirect': url_for('questions')}), 200
        except requests.exceptions.RequestException as re:
            logger.error(f"API request exception: {re}")
            return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
        except json.JSONDecodeError as jde:
            logger.error(f"JSON decode error from API: {jde}, response: {resp.text if 'resp' in locals() else 'No response'}")
            return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500
        except Exception as e:
            logger.error(f"Unexpected age verification error: {str(e)}")
            return jsonify({'success': False, 'error': 'Align your face correctly and visibly under light and try again.'}), 500

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

@app.route('/report-user', methods=['POST'])
def report_user_endpoint():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    data = request.get_json()
    reported_user_id = data.get('reported_user_id')
    reason = data.get('reason')
    if not reported_user_id or not reason:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    result = mongo_service.report_user(session['user_id'], reported_user_id, reason)
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
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'distance': 'N/A',
            'rating': '4.5',
            'dominant_type': quiz_result['scores']['dominant_type'],
            'match_percentage': 50
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
        matches = mongo_service.get_potential_matches(session['user_id'])
        return jsonify({
            'success': True, 
            'matches': matches
        }), 200
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
        current_quiz = mongo_service.get_quiz_results(session['user_id'])
        match_percentage = 50
        if current_quiz and quiz_result:
            match_percentage = mongo_service._calculate_match_percentage(current_quiz['scores'], quiz_result['scores'])
        dominant_type = quiz_result['scores']['dominant_type'] if quiz_result else 'N/A'
        personality = PERSONALITIES.get(dominant_type, {
            'dominant_type': dominant_type,
            'title': f'This person is a {dominant_type.replace(" ", "")}.',
            'description': 'Description not available.',
            'tagline': '',
            'strengths': [],
            'compatibility': [],
            'color': '#000000'
        })
        personality_info = f"""
        <strong>{personality['title']}</strong><br>
        {personality['description']}<br>
        <em>{personality['tagline']}</em><br>
        <strong>Strengths:</strong> {', '.join(personality['strengths'])}<br>
        <strong>Compatibility:</strong> {', '.join(personality['compatibility'])}
        """

        secondary_personality_info = None
        if quiz_result and quiz_result['scores'].get('secondary_type'):
            secondary_type = quiz_result['scores']['secondary_type']
            secondary_personality = PERSONALITIES.get(secondary_type, {
                'dominant_type': secondary_type,
                'title': f'This person is a {secondary_type.replace(" ", "")}.',
                'description': 'Description not available.',
                'tagline': '',
                'strengths': [],
                'compatibility': [],
                'color': '#000000'
            })
            secondary_personality_info = f"""
            <br><strong>Secondary: {secondary_personality['title']}</strong><br>
            {secondary_personality['description']}<br>
            <em>{secondary_personality['tagline']}</em><br>
            <strong>Strengths:</strong> {', '.join(secondary_personality['strengths'])}<br>
            <strong>Compatibility:</strong> {', '.join(secondary_personality['compatibility'])}
            """

        profile = {
            'id': user['id'],
            'full_name': user['full_name'],
            'age': user.get('age'),
            'gender': user.get('gender'),
            'image': user.get('image', 'https://randomuser.me/api/portraits/women/44.jpg'),
            'occupation': user.get('occupation', 'N/A'),
            'bio': user.get('bio', 'No bio available'),
            'interests': user.get('interests', []),
            'distance': 'N/A',
            'rating': '4.5',
            'match_percentage': match_percentage,
            'liked': mongo_service.has_liked_user(session['user_id'], user_id),
            'passed': mongo_service.has_passed_user(session['user_id'], user_id),
            'personality': {
                'dominant_type': quiz_result['scores']['dominant_type'] if quiz_result else 'N/A',
                'dominant_percentage': quiz_result['scores']['dominant_percentage'] if quiz_result else 0,
                'secondary_type': quiz_result['scores']['secondary_type'] if quiz_result else 'N/A',
                'secondary_percentage': quiz_result['scores']['secondary_percentage'] if quiz_result else 0
            },
            'personality_info': personality_info,
            'secondary_personality_info': secondary_personality_info,
            'keeper_seeker': quiz_result['scores'].get('keeper_seeker_type', 'N/A') if quiz_result else 'N/A',
            'religion': user.get('religion', 'Not specified') if user.get('religion_public', False) else 'Private',
            'physical_traits': {t['label']: t['value'] for t in user.get('physical_traits', [])} if user.get('physical_public', False) else 'Private',  # Added conditional visibility
            'education_work': next((p['value'] for p in user.get('profile_data', []) if p['label'] == 'Education / Work'), 'N/A'),
            'summary': next((p['value'] for p in user.get('profile_data', []) if p['label'] == 'One-line self-summary (optional)'), 'N/A'),
            'photos': user.get('photos', [])
        }
        # Collect interests from profile_data
        profile['profile_interests'] = [p['value'] for p in user.get('profile_data', []) if p['label'] == 'Interests (select all that apply)']
        return jsonify({'success': True, 'user': profile}), 200
    except Exception as e:
        logger.error(f"User profile endpoint error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
        
        # Render with empty conversations for lazy loading
        return render_template('chat.html', profile=profile, conversations=[], unread_count=0, current_user_id=current_user_id)
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return render_template('chat.html', profile={'image': 'https://randomuser.me/api/portraits/women/44.jpg'}, conversations=[], unread_count=0, error=str(e), current_user_id='')

@app.route('/api/conversations', methods=['GET'])
def api_conversations():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    try:
        current_user_id = session['user_id']
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
        return jsonify({'success': True, 'conversations': conversations, 'unread_count': unread_count}), 200
    except Exception as e:
        logger.error(f"API conversations error: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to fetch conversations'}), 500

@app.route("/messages/<other_user_id>", methods=['GET'])
def get_messages(other_user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    current_user_id = session['user_id']
    if not mongo_service.is_matched(current_user_id, other_user_id):
        return jsonify({'success': False, 'error': 'Not matched'}), 403
    try:
        result = chat_service.get_messages(current_user_id, other_user_id)
        return jsonify(result), 200 if result['success'] else 400
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

@app.route('/start_typing/<to_id>', methods=['POST'])
def start_typing(to_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    chat_service.start_typing(session['user_id'], to_id)
    return jsonify({'success': True})

@app.route('/stop_typing/<to_id>', methods=['POST'])
def stop_typing(to_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    chat_service.stop_typing(session['user_id'], to_id)
    return jsonify({'success': True})

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
        dominant_type = quiz_result['scores']['dominant_type'] if quiz_result else 'N/A'
        personality = PERSONALITIES.get(dominant_type, {
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
        if quiz_result['scores']['secondary_type']:
            secondary_type = quiz_result['scores']['secondary_type']
            secondary_personality = PERSONALITIES.get(secondary_type, {
                'dominant_type': secondary_type,
                'title': f'You are a {secondary_type.replace(" ", "")}.',
                'description': 'Description not available.',
                'tagline': '',
                'strengths': [],
                'compatibility': [],
                'color': '#000000'
            })
            personality_info += f"""
            <br><strong>Secondary: {secondary_personality['title']}</strong><br>
            {secondary_personality['description']}<br>
            <em>{secondary_personality['tagline']}</em><br>
            <strong>Strengths:</strong> {', '.join(secondary_personality['strengths'])}<br>
            <strong>Compatibility:</strong> {', '.join(secondary_personality['compatibility'])}
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
            'personality_info': personality_info,
            'keeper_seeker': quiz_result['scores'].get('keeper_seeker_type', 'N/A') if quiz_result else 'N/A',
            'religion': user.get('religion', 'N/A'),
            'religion_importance': user.get('religion_importance', 'skip'),
            'religion_public': user.get('religion_public', False),  # Added for toggle
            'physical_traits': {t['label']: t['value'] for t in user.get('physical_traits', [])},
            'physical_importance': user.get('physical_importance', 'not_important'),
            'physical_public': user.get('physical_public', False),  # Added for toggle
            'education_work': next((p['value'] for p in user.get('profile_data', []) if p['label'] == 'Education / Work'), 'N/A'),
            'summary': next((p['value'] for p in user.get('profile_data', []) if p['label'] == 'One-line self-summary (optional)'), 'N/A')
        }
        # Collect interests from profile_data
        profile['profile_interests'] = [p['value'] for p in user.get('profile_data', []) if p['label'] == 'Interests (select all that apply)']
        pending_likers = mongo_service.get_pending_likers(session['user_id'])
        notifications = mongo_service.get_notifications(session['user_id'])
        return render_template('profile.html', profile=profile, pending_likers=pending_likers, notifications=notifications)
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return render_template('profile.html', profile={}, pending_likers=[], notifications=[])

@app.route('/questions', methods=['GET'])
def questions():
    logger.debug(f"Session in questions: {session}")
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
    logger.debug(f"Rendering questions.html for user {session['user_id']}")
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
        
        # Add types to answers for emotional questions
        for ans in answers:
            qid = ans.get('question_id')
            if qid in QUESTION_TYPES:
                if 'index' in ans:
                    ans['type'] = QUESTION_TYPES[qid][ans['index']]
                elif 'ranking' in ans:
                    if ans['ranking']:
                        top_rank = min(ans['ranking'], key=lambda r: r['rank'])
                        top_idx = top_rank['index']
                        ans['type'] = QUESTION_TYPES[qid][top_idx]
        
        quiz_data = {'answers': answers}
        result = mongo_service.save_quiz_results(session['user_id'], quiz_data)
        if result['success']:
            return jsonify(result), 200
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
    personality_info = PERSONALITIES.get(dominant_type, {
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
            logger.info("User profile profile picture updated successfully in database")
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
    if len(user.get('photos', [])) >= 7:
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
    if 'religion_public' in data:
        update_data['religion_public'] = data['religion_public']
    if 'physical_public' in data:
        update_data['physical_public'] = data['physical_public']
    if 'religion' in data:
        update_data['religion'] = data['religion']
    if 'religion_importance' in data:
        update_data['religion_importance'] = data['religion_importance']
    if 'physical_importance' in data:
        update_data['physical_importance'] = data['physical_importance']
    if 'physical_traits' in data:
        traits_dict = data['physical_traits']
        traits_list = [{'label': k, 'value': v} for k, v in traits_dict.items()]
        update_data['physical_traits'] = traits_list
    if update_data:
        result = mongo_service.update_user(session['user_id'], update_data)
        return jsonify(result)
    return jsonify({'success': True}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
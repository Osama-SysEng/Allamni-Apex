from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, date, timezone
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from shared.config.settings import settings
from shared.identity import active_session, create_session, record_consent, revoke_session, rotate_refresh
from shared.security import create_token, decode_token
from shared.store import store
from shared.models import (
    UserRole, Institution, Subscription, StudentCode, TeacherCode,
    InstitutionRegistrationRequest, StudentCodeRegistrationRequest,
    TeacherCodeRegistrationRequest, SelfRegistrationRequest
)
from shared.permissions import has_permission
from shared.enhanced_auth import get_enhanced_auth_service, SecurityLevel
from shared.advanced_security import get_advanced_security_service, SecurityConfig
import hashlib, os, hmac

app = FastAPI(title='Allamni Auth Service')
CONSENT_PURPOSE = 'personalized_learning'
CONSENT_VERSION = '2026-08'


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str
    role: str = 'student'
    goal_domain: str = 'general'

# New v4.0 registration requests
class InstitutionRegistrationRequest(BaseModel):
    name_ar: str
    name_en: str
    type: str
    sub_type: str = None
    country: str
    city: str
    address: str = None
    phone: str = None
    email: str = None
    website: str = None
    admin_name: str
    admin_email: str
    admin_phone: str
    plan_type: str = 'basic'

class StudentCodeRegistrationRequest(BaseModel):
    code: str
    full_name: str
    email: str = None
    phone: str = None
    password: str = Field(min_length=8)
    date_of_birth: date = None
    guardian_contact: str = None

class TeacherCodeRegistrationRequest(BaseModel):
    code: str
    full_name: str
    email: str
    phone: str
    password: str = Field(min_length=8)
    specialization: str = None
    qualifications: str = None

class SelfRegistrationRequest(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str = Field(min_length=8)
    role: str = 'student'
    level: str = None
    goals: list = []


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class ConsentRequest(BaseModel):
    granted: bool
    version: str = CONSENT_VERSION


def hash_password(password):
    salt = os.urandom(16)
    return salt.hex() + '$' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000).hex()


def verify(password, stored):
    salt, digest = stored.split('$')
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 210000).hex()
    return hmac.compare_digest(candidate, digest)


def token_pair(user: dict, session: dict) -> dict:
    return {
        'access_token': create_token(user['id'], user['role'], 'access', session['id']),
        'refresh_token': create_token(user['id'], user['role'], 'refresh', session['id'], session['refresh_jti']),
        'token_type': 'bearer',
        'expires_in': settings.jwt_access_minutes * 60,
        'session_id': session['id'],
        'user': {'id': user['id'], 'email': user['email'], 'full_name': user['full_name'], 'role': user['role']},
    }


def current(authorization: str) -> dict:
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'missing bearer token')
    try:
        claims = decode_token(authorization[7:])
    except Exception as exc:
        raise HTTPException(401, 'invalid token') from exc
    if claims.get('type') != 'access' or not active_session(claims.get('sid'), claims.get('sub')):
        raise HTTPException(401, 'session is not active')
    return claims


@app.get('/health')
def health(): return {'status': 'ok', 'service': 'auth'}


@app.post('/register')
def register(body: RegisterRequest):
    body.email = body.email.strip().lower()
    if body.role not in {'student', 'admin', 'institution_manager'}: raise HTTPException(400, 'invalid role')
    if body.email in store.users_by_email: raise HTTPException(409, 'email already registered')
    user_id = str(uuid4())
    user = {'id': user_id, 'email': body.email, 'full_name': body.full_name, 'role': body.role, 'password_hash': hash_password(body.password), 'active': True}
    store.users[user_id] = user; store.users_by_email[body.email] = user
    if body.role == 'student':
        from shared.models import LearningProfile, Skill, LearningPreferences
        store.profiles[user_id] = LearningProfile(student_id=user_id, goal_domain=body.goal_domain, learning_preferences=LearningPreferences(content_format=['video', 'interactive']), skills=[Skill(code='python_basics', name='أساسيات البرمجة', level=.35, target=.75, confidence=.55, importance=1), Skill(code='oop', name='البرمجة الكائنية', level=.22, target=.70, confidence=.48, importance=.9), Skill(code='problem_solving', name='حل المشكلات', level=.40, target=.80, confidence=.60, importance=.95), Skill(code='data_structures', name='هياكل البيانات', level=.15, target=.65, confidence=.35, importance=.85)])
    response = token_pair(user, create_session(user_id, body.role, settings.jwt_refresh_days))
    response['consent_required'] = body.role == 'student'
    return response


@app.post('/login')
def login(body: LoginRequest):
    user = store.users_by_email.get(body.email.strip().lower())
    if not user or not user.get('active', True) or not verify(body.password, user['password_hash']): raise HTTPException(401, 'invalid credentials')
    
    # Initialize Phase 5 services
    enhanced_auth = get_enhanced_auth_service(store)
    security_service = get_advanced_security_service(store)
    
    # Check rate limiting
    if not security_service.check_rate_limit(user['id'], '/api/login', 'minute'):
        raise HTTPException(429, 'Too many login attempts. Please try again later.')
    
    # Create enhanced session
    session = enhanced_auth.create_session(
        user_id=user['id'],
        ip_address='127.0.0.1',  # In production, get from request
        user_agent='web_client',  # In production, get from request
        device_id='default_device'
    )
    
    response = token_pair(user, create_session(user['id'], user['role'], settings.jwt_refresh_days))
    response['consent_required'] = user['role'] == 'student' and not store.consents.get((user['id'], CONSENT_PURPOSE), {}).get('granted')
    response['enhanced_session_id'] = session.id
    return response


@app.post('/refresh')
def refresh(body: RefreshRequest):
    try: claims = decode_token(body.refresh_token)
    except Exception as exc: raise HTTPException(401, 'invalid refresh token') from exc
    if claims.get('type') != 'refresh': raise HTTPException(401, 'invalid refresh token')
    session = rotate_refresh(claims.get('sid'), claims.get('jti'))
    user = store.users.get(claims.get('sub'))
    if not session or not user: raise HTTPException(401, 'refresh session is not active')
    return token_pair(user, session)


@app.post('/logout', status_code=204)
def logout(authorization: str = Header('')):
    claims = current(authorization)
    revoke_session(claims['sid'], 'user_logout', claims['sub'])


@app.post('/me/consent')
def consent(body: ConsentRequest, authorization: str = Header('')):
    claims = current(authorization)
    if claims['role'] != 'student': raise HTTPException(403, 'student role required')
    record_consent(claims['sub'], CONSENT_PURPOSE, body.granted, body.version)
    return {'status': 'recorded', 'purpose': CONSENT_PURPOSE, 'granted': body.granted}

# v4.0 New Endpoints

@app.post('/register/institution')
def register_institution(body: InstitutionRegistrationRequest):
    """Register a new institution with subscription"""
    # Validate institution type
    valid_types = ['school', 'university', 'training_center']
    if body.type not in valid_types:
        raise HTTPException(400, f'Invalid institution type. Must be one of: {valid_types}')
    
    # Check if admin email already exists
    if body.admin_email.lower() in store.users_by_email:
        raise HTTPException(409, 'Admin email already registered')
    
    # Create institution
    institution_id = str(uuid4())
    institution = {
        'id': institution_id,
        'name_ar': body.name_ar,
        'name_en': body.name_en,
        'type': body.type,
        'sub_type': body.sub_type,
        'country': body.country,
        'city': body.city,
        'address': body.address,
        'phone': body.phone,
        'email': body.email,
        'website': body.website,
        'is_active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Create subscription
    subscription_id = str(uuid4())
    from datetime import timedelta
    subscription = {
        'id': subscription_id,
        'institution_id': institution_id,
        'plan_type': body.plan_type,
        'status': 'trial',
        'start_date': datetime.now(timezone.utc).date().isoformat(),
        'end_date': (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat(),  # 30-day trial
        'max_students': 100 if body.plan_type == 'basic' else 500 if body.plan_type == 'professional' else None,
        'max_teachers': 10 if body.plan_type == 'basic' else 50 if body.plan_type == 'professional' else None,
        'max_admins': 1,
        'features': {},
        'billing_cycle': 'monthly',
        'auto_renew': False,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Create admin user
    admin_user_id = str(uuid4())
    admin_user = {
        'id': admin_user_id,
        'email': body.admin_email.strip().lower(),
        'full_name': body.admin_name,
        'phone': body.admin_phone,
        'role': 'institution_admin',
        'password_hash': hash_password('TempPassword123!'),  # Will be changed on first login
        'institution_id': institution_id,
        'active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Store everything
    store.institutions[institution_id] = institution
    store.subscriptions[subscription_id] = subscription
    store.users[admin_user_id] = admin_user
    store.users_by_email[admin_user['email']] = admin_user
    institution['admin_user_id'] = admin_user_id
    
    # Create session for admin
    session = create_session(admin_user_id, 'institution_admin', settings.jwt_refresh_days)
    response = token_pair(admin_user, session)
    response['institution'] = institution
    response['subscription'] = subscription
    response['requires_password_change'] = True
    
    return response

@app.post('/register/student-code')
def register_student_code(body: StudentCodeRegistrationRequest):
    """Register student using institution-issued code"""
    # Find the code
    code_data = None
    for code_id, code_info in store.student_codes.items():
        if code_info['code'] == body.code and code_info['is_active']:
            code_data = code_info
            code_id_key = code_id
            break
    
    if not code_data:
        raise HTTPException(404, 'Invalid or inactive student code')
    
    if code_data['student_id']:
        raise HTTPException(409, 'This code has already been used')
    
    # Check expiration
    if code_data.get('expires_at'):
        expires_at = datetime.fromisoformat(code_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(400, 'Student code has expired')
    
    # Check if email already exists
    if body.email and body.email.lower() in store.users_by_email:
        raise HTTPException(409, 'Email already registered')
    
    # Create student user
    student_id = str(uuid4())
    student_user = {
        'id': student_id,
        'email': body.email.strip().lower() if body.email else None,
        'phone': body.phone,
        'full_name': body.full_name,
        'role': 'student',
        'password_hash': hash_password(body.password),
        'institution_id': code_data['institution_id'],
        'class_id': code_data.get('class_id'),
        'grade_level': code_data.get('grade_level'),
        'academic_year': code_data.get('academic_year'),
        'date_of_birth': body.date_of_birth.isoformat() if body.date_of_birth else None,
        'guardian_contact': body.guardian_contact,
        'active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Update code
    store.student_codes[code_id_key]['student_id'] = student_id
    store.student_codes[code_id_key]['used_at'] = datetime.now(timezone.utc).isoformat()
    
    # Store user
    store.users[student_id] = student_user
    if body.email:
        store.users_by_email[student_user['email']] = student_user
    
    # Create learning profile
    from shared.models import LearningProfile, Skill, LearningPreferences
    store.profiles[student_id] = LearningProfile(
        student_id=student_id,
        goal_domain='general',
        learning_preferences=LearningPreferences(content_format=['video', 'interactive']),
        skills=[
            Skill(code='python_basics', name='أساسيات البرمجة', level=.35, target=.75, confidence=.55, importance=1),
            Skill(code='oop', name='البرمجة الكائنية', level=.22, target=.70, confidence=.48, importance=.9),
            Skill(code='problem_solving', name='حل المشكلات', level=.40, target=.80, confidence=.60, importance=.95),
            Skill(code='data_structures', name='هياكل البيانات', level=.15, target=.65, confidence=.35, importance=.85)
        ]
    )
    
    # Create session
    session = create_session(student_id, 'student', settings.jwt_refresh_days)
    response = token_pair(student_user, session)
    response['consent_required'] = True
    response['institution_id'] = code_data['institution_id']
    
    return response

@app.post('/register/teacher-code')
def register_teacher_code(body: TeacherCodeRegistrationRequest):
    """Register teacher using institution-issued code"""
    # Find the code
    code_data = None
    for code_id, code_info in store.teacher_codes.items():
        if code_info['code'] == body.code and code_info['is_active']:
            code_data = code_info
            code_id_key = code_id
            break
    
    if not code_data:
        raise HTTPException(404, 'Invalid or inactive teacher code')
    
    if code_data['teacher_id']:
        raise HTTPException(409, 'This code has already been used')
    
    # Check expiration
    if code_data.get('expires_at'):
        expires_at = datetime.fromisoformat(code_data['expires_at'])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(400, 'Teacher code has expired')
    
    # Check if email already exists
    if body.email.lower() in store.users_by_email:
        raise HTTPException(409, 'Email already registered')
    
    # Create teacher user
    teacher_id = str(uuid4())
    teacher_user = {
        'id': teacher_id,
        'email': body.email.strip().lower(),
        'phone': body.phone,
        'full_name': body.full_name,
        'role': 'teacher',
        'password_hash': hash_password(body.password),
        'institution_id': code_data['institution_id'],
        'department': code_data.get('department'),
        'subjects': code_data.get('subjects', []),
        'grade_levels': code_data.get('grade_levels', []),
        'specialization': body.specialization,
        'qualifications': body.qualifications,
        'active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Update code
    store.teacher_codes[code_id_key]['teacher_id'] = teacher_id
    store.teacher_codes[code_id_key]['used_at'] = datetime.now(timezone.utc).isoformat()
    
    # Store user
    store.users[teacher_id] = teacher_user
    store.users_by_email[teacher_user['email']] = teacher_user
    
    # Create session
    session = create_session(teacher_id, 'teacher', settings.jwt_refresh_days)
    response = token_pair(teacher_user, session)
    response['institution_id'] = code_data['institution_id']
    
    return response

@app.post('/register/self')
def self_register(body: SelfRegistrationRequest):
    """Self-registration for independent learners"""
    # Validate role
    valid_roles = ['student', 'teacher', 'parent']
    if body.role not in valid_roles:
        raise HTTPException(400, f'Invalid role. Must be one of: {valid_roles}')
    
    # Check if email already exists
    if body.email.lower() in store.users_by_email:
        raise HTTPException(409, 'Email already registered')
    
    # Create user
    user_id = str(uuid4())
    user = {
        'id': user_id,
        'email': body.email.strip().lower(),
        'phone': body.phone,
        'full_name': body.full_name,
        'role': body.role,
        'password_hash': hash_password(body.password),
        'level': body.level,
        'goals': body.goals,
        'active': True,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    
    # Store user
    store.users[user_id] = user
    store.users_by_email[user['email']] = user
    
    # Create learning profile for students
    if body.role == 'student':
        from shared.models import LearningProfile, Skill, LearningPreferences
        store.profiles[user_id] = LearningProfile(
            student_id=user_id,
            goal_domain=body.level or 'general',
            learning_preferences=LearningPreferences(content_format=['video', 'interactive']),
            skills=[
                Skill(code='general_basics', name='المهارات الأساسية', level=.30, target=.70, confidence=.50, importance=1),
            ]
        )
    
    # Create session
    session = create_session(user_id, body.role, settings.jwt_refresh_days)
    response = token_pair(user, session)
    response['consent_required'] = body.role == 'student'
    
    return response

# Phase 5 Enhanced Authentication Endpoints

@app.post('/auth/2fa/setup')
def setup_2fa(authorization: str = Header('')):
    """Setup two-factor authentication"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    
    two_factor = enhanced_auth.setup_2fa(
        user_id=claims['sub']
    )
    
    return {'status': '2fa_setup_initiated', 'method': two_factor.method, 'backup_codes': two_factor.backup_codes}

@app.post('/auth/2fa/verify')
def verify_2fa(code: str, authorization: str = Header('')):
    """Verify two-factor authentication code"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    
    # First enable 2FA if not enabled
    two_fa = enhanced_auth.store.two_factor_auths.get(claims['sub'])
    if two_fa and not two_fa.is_enabled:
        two_fa.is_enabled = True
    
    if enhanced_auth.verify_2fa(claims['sub'], code):
        return {'status': '2fa_verified'}
    else:
        raise HTTPException(400, 'Invalid 2FA code')

@app.post('/auth/biometric/register')
def register_biometric(authorization: str = Header('')):
    """Register biometric authentication"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    
    biometric = enhanced_auth.register_biometric(
        user_id=claims['sub'],
        biometric_type='fingerprint',
        device_id='default_device'
    )
    
    return {'status': 'biometric_registered', 'biometric_id': biometric.id}

@app.post('/auth/biometric/verify')
def verify_biometric(biometric_data: str, authorization: str = Header('')):
    """Verify biometric authentication"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    
    if enhanced_auth.verify_biometric(claims['sub'], biometric_data):
        return {'status': 'biometric_verified'}
    else:
        raise HTTPException(400, 'Biometric verification failed')

@app.get('/auth/sessions')
def get_active_sessions(authorization: str = Header(''), limit: int = 50, offset: int = 0):
    """Get all active sessions for user"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    sessions = enhanced_auth.get_active_sessions(claims['sub'])[offset:offset + limit]
    return {'sessions': [{'id': s.id, 'created_at': s.created_at.isoformat(), 'last_activity': s.last_activity.isoformat()} for s in sessions], 'limit': limit, 'offset': offset}

@app.post('/auth/sessions/{session_id}/revoke')
def revoke_session_endpoint(session_id: str, authorization: str = Header('')):
    """Revoke a specific session"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    
    if enhanced_auth.revoke_session(session_id, 'user_revoked', claims['sub']):
        return {'status': 'session_revoked'}
    else:
        raise HTTPException(404, 'Session not found')

@app.get('/auth/security-events')
def get_security_events(authorization: str = Header(''), limit: int = 50, offset: int = 0):
    """Get security events for user"""
    claims = current(authorization)
    enhanced_auth = get_enhanced_auth_service(store)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    events = enhanced_auth.get_security_events(claims['sub'])[offset:offset + limit]
    return {'events': [{'id': e.id, 'event_type': e.event_type, 'timestamp': e.timestamp.isoformat()} for e in events], 'limit': limit, 'offset': offset}

# Phase 5 Security Endpoints

@app.post('/security/encrypt')
def encrypt_endpoint(data: str, authorization: str = Header('')):
    """Encrypt sensitive data"""
    claims = current(authorization)
    security_service = get_advanced_security_service(store)
    
    encrypted = security_service.encrypt_data(data)
    return {'encrypted_data': encrypted}

@app.post('/security/decrypt')
def decrypt_endpoint(encrypted_data: str, authorization: str = Header('')):
    """Decrypt sensitive data"""
    claims = current(authorization)
    security_service = get_advanced_security_service(store)
    
    decrypted = security_service.decrypt_data(encrypted_data)
    return {'decrypted_data': decrypted}

@app.get('/security/metrics')
def get_security_metrics(authorization: str = Header('')):
    """Get security metrics (admin only)"""
    claims = current(authorization)
    if claims['role'] not in ['admin', 'institution_admin']:
        raise HTTPException(403, 'Admin access required')
    
    security_service = get_advanced_security_service(store)
    metrics = security_service.get_security_metrics()
    return metrics

@app.get('/security/scan')
def perform_security_scan(authorization: str = Header('')):
    """Perform security scan (admin only)"""
    claims = current(authorization)
    if claims['role'] not in ['admin', 'institution_admin']:
        raise HTTPException(403, 'Admin access required')
    
    security_service = get_advanced_security_service(store)
    scan_results = security_service.perform_security_scan()
    return scan_results

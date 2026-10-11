"""
Institution Management Service - Allamni v4.0
Handles institution administration, code generation, and subscription management
"""
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from uuid import uuid4
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional
from decimal import Decimal

from shared.config.settings import settings
from shared.security import decode_token
from shared.identity import active_session, generate_student_code, generate_teacher_code, audit
from shared.store import store
from shared.models import UserRole, InstitutionType, SubscriptionPlan, SubscriptionStatus
from shared.permissions import has_permission
from shared.billing import get_billing_service, InvoiceStatus, PaymentMethod

app = FastAPI(title="Allamni Institution Service", version="4.0.0")


# Request Models
class GenerateStudentCodeRequest(BaseModel):
    institution_id: str
    class_id: Optional[str] = None
    grade_level: Optional[str] = None
    academic_year: Optional[str] = None
    quantity: int = Field(default=1, ge=1, le=100)

class GenerateTeacherCodeRequest(BaseModel):
    institution_id: str
    department: Optional[str] = None
    subjects: Optional[List[str]] = None
    grade_levels: Optional[List[str]] = None
    quantity: int = Field(default=1, ge=1, le=50)

class UpdateInstitutionRequest(BaseModel):
    name_ar: Optional[str] = None
    name_en: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None

class UpdateSubscriptionRequest(BaseModel):
    plan_type: Optional[SubscriptionPlan] = None
    auto_renew: Optional[bool] = None

class InstitutionStatsRequest(BaseModel):
    institution_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None


# Authentication
def current(authorization: str = Header("")):
    """Get current user from JWT token"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        claims = decode_token(authorization[7:])
    except Exception as exc:
        raise HTTPException(401, "invalid token") from exc
    
    if claims.get('type') != 'access' or not active_session(claims.get('sid'), claims.get('sub')):
        raise HTTPException(401, "session is not active")
    
    return claims

def require_institution_admin(claims: dict):
    """Require institution admin or super admin role"""
    if claims['role'] not in {'institution_admin', 'super_admin'}:
        raise HTTPException(403, "institution admin role required")
    return claims

def verify_institution_access(claims: dict, institution_id: str):
    """Verify user has access to the institution"""
    if claims['role'] == 'super_admin':
        return True
    
    if claims['role'] == 'institution_admin':
        user_institution_id = claims.get('institution_id')
        if user_institution_id != institution_id:
            raise HTTPException(403, "access denied to this institution")
        return True
    
    raise HTTPException(403, "insufficient permissions")


# Health Check
@app.get("/health")
def health():
    return {"status": "ok", "service": "institution", "version": "4.0.0"}


# CODE GENERATION ENDPOINTS

@app.post("/codes/student/generate")
def generate_student_codes(body: GenerateStudentCodeRequest, authorization: str = Header("")):
    """Generate student registration codes"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, body.institution_id)
    
    # Check institution exists
    if body.institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Check subscription limits
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == body.institution_id and sub['status'] in ['trial', 'active']:
            subscription = sub
            break
    
    if not subscription:
        raise HTTPException(403, "no active subscription found")
    
    # Count existing students
    current_student_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == body.institution_id and u.get('role') == 'student'
    ])
    
    if subscription.get('max_students') and current_student_count + body.quantity > subscription['max_students']:
        raise HTTPException(403, f"subscription limit exceeded. Max students: {subscription['max_students']}")
    
    # Generate codes
    codes = []
    for _ in range(body.quantity):
        code_data = generate_student_code(
            institution_id=body.institution_id,
            class_id=body.class_id,
            grade_level=body.grade_level,
            academic_year=body.academic_year,
            issued_by=claims['sub']
        )
        codes.append({
            'code': code_data['code'],
            'class_id': code_data['class_id'],
            'grade_level': code_data['grade_level'],
            'academic_year': code_data['academic_year'],
            'expires_at': code_data['expires_at'],
            'created_at': code_data['issued_at']
        })
    
    audit(claims['sub'], 'STUDENT_CODES_GENERATED', 'Institution', body.institution_id, {
        'quantity': body.quantity,
        'class_id': body.class_id
    })
    
    return {
        'institution_id': body.institution_id,
        'codes': codes,
        'quantity': len(codes),
        'generated_by': claims['sub'],
        'generated_at': datetime.now(timezone.utc).isoformat()
    }


@app.post("/codes/teacher/generate")
def generate_teacher_codes(body: GenerateTeacherCodeRequest, authorization: str = Header("")):
    """Generate teacher registration codes"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, body.institution_id)
    
    # Check institution exists
    if body.institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Check subscription limits
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == body.institution_id and sub['status'] in ['trial', 'active']:
            subscription = sub
            break
    
    if not subscription:
        raise HTTPException(403, "no active subscription found")
    
    # Count existing teachers
    current_teacher_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == body.institution_id and u.get('role') == 'teacher'
    ])
    
    if subscription.get('max_teachers') and current_teacher_count + body.quantity > subscription['max_teachers']:
        raise HTTPException(403, f"subscription limit exceeded. Max teachers: {subscription['max_teachers']}")
    
    # Generate codes
    codes = []
    for _ in range(body.quantity):
        code_data = generate_teacher_code(
            institution_id=body.institution_id,
            department=body.department,
            subjects=body.subjects,
            grade_levels=body.grade_levels,
            issued_by=claims['sub']
        )
        codes.append({
            'code': code_data['code'],
            'department': code_data['department'],
            'subjects': code_data['subjects'],
            'grade_levels': code_data['grade_levels'],
            'expires_at': code_data['expires_at'],
            'created_at': code_data['issued_at']
        })
    
    audit(claims['sub'], 'TEACHER_CODES_GENERATED', 'Institution', body.institution_id, {
        'quantity': body.quantity,
        'department': body.department
    })
    
    return {
        'institution_id': body.institution_id,
        'codes': codes,
        'quantity': len(codes),
        'generated_by': claims['sub'],
        'generated_at': datetime.now(timezone.utc).isoformat()
    }


@app.get("/codes/student/list")
def list_student_codes(institution_id: str, authorization: str = Header(""), limit: int = 50, offset: int = 0):
    """List all student codes for an institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    codes = []
    for code_id, code_data in store.student_codes.items():
        if code_data['institution_id'] == institution_id:
            codes.append({
                'id': code_id,
                'code': code_data['code'],
                'student_id': code_data['student_id'],
                'class_id': code_data['class_id'],
                'grade_level': code_data['grade_level'],
                'is_active': code_data['is_active'],
                'used_at': code_data['used_at'],
                'expires_at': code_data['expires_at'],
                'created_at': code_data['issued_at']
            })
    
    return {
        'institution_id': institution_id,
        'codes': codes[offset:offset + limit],
        'total': len(codes),
        'limit': limit,
        'offset': offset,
        'active': len([c for c in codes if c['is_active'] and not c['student_id']]),
        'used': len([c for c in codes if c['student_id']])
    }


@app.get("/codes/teacher/list")
def list_teacher_codes(institution_id: str, authorization: str = Header(""), limit: int = 50, offset: int = 0):
    """List all teacher codes for an institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    codes = []
    for code_id, code_data in store.teacher_codes.items():
        if code_data['institution_id'] == institution_id:
            codes.append({
                'id': code_id,
                'code': code_data['code'],
                'teacher_id': code_data['teacher_id'],
                'department': code_data['department'],
                'subjects': code_data['subjects'],
                'is_active': code_data['is_active'],
                'used_at': code_data['used_at'],
                'expires_at': code_data['expires_at'],
                'created_at': code_data['issued_at']
            })
    
    return {
        'institution_id': institution_id,
        'codes': codes[offset:offset + limit],
        'total': len(codes),
        'limit': limit,
        'offset': offset,
        'active': len([c for c in codes if c['is_active'] and not c['teacher_id']]),
        'used': len([c for c in codes if c['teacher_id']])
    }


@app.delete("/codes/student/{code_id}")
def revoke_student_code(code_id: str, authorization: str = Header("")):
    """Revoke a student code"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    
    if code_id not in store.student_codes:
        raise HTTPException(404, "code not found")
    
    code_data = store.student_codes[code_id]
    verify_institution_access(claims, code_data['institution_id'])
    
    if code_data['student_id']:
        raise HTTPException(400, "cannot revoke code that has been used")
    
    store.student_codes[code_id]['is_active'] = False
    
    audit(claims['sub'], 'STUDENT_CODE_REVOKED', 'StudentCode', code_id, {
        'code': code_data['code']
    })
    
    return {'status': 'revoked', 'code_id': code_id}


@app.delete("/codes/teacher/{code_id}")
def revoke_teacher_code(code_id: str, authorization: str = Header("")):
    """Revoke a teacher code"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    
    if code_id not in store.teacher_codes:
        raise HTTPException(404, "code not found")
    
    code_data = store.teacher_codes[code_id]
    verify_institution_access(claims, code_data['institution_id'])
    
    if code_data['teacher_id']:
        raise HTTPException(400, "cannot revoke code that has been used")
    
    store.teacher_codes[code_id]['is_active'] = False
    
    audit(claims['sub'], 'TEACHER_CODE_REVOKED', 'TeacherCode', code_id, {
        'code': code_data['code']
    })
    
    return {'status': 'revoked', 'code_id': code_id}


# INSTITUTION DASHBOARD ENDPOINTS

@app.get("/institutions/{institution_id}")
def get_institution(institution_id: str, authorization: str = Header("")):
    """Get institution details"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    institution = store.institutions[institution_id].copy()
    
    # Get subscription info
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            break
    
    # Get stats
    student_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ])
    teacher_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ])
    
    return {
        'institution': institution,
        'subscription': subscription,
        'stats': {
            'students': student_count,
            'teachers': teacher_count,
            'total_users': student_count + teacher_count
        }
    }


@app.put("/institutions/{institution_id}")
def update_institution(institution_id: str, body: UpdateInstitutionRequest, authorization: str = Header("")):
    """Update institution details"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    institution = store.institutions[institution_id]
    
    # Update fields
    if body.name_ar is not None:
        institution['name_ar'] = body.name_ar
    if body.name_en is not None:
        institution['name_en'] = body.name_en
    if body.phone is not None:
        institution['phone'] = body.phone
    if body.email is not None:
        institution['email'] = body.email
    if body.website is not None:
        institution['website'] = body.website
    if body.address is not None:
        institution['address'] = body.address
    if body.logo_url is not None:
        institution['logo_url'] = body.logo_url
    
    institution['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    audit(claims['sub'], 'INSTITUTION_UPDATED', 'Institution', institution_id, body.model_dump(exclude_none=True))
    
    return institution


@app.get("/institutions/{institution_id}/dashboard")
def get_institution_dashboard(institution_id: str, authorization: str = Header("")):
    """Get institution dashboard with comprehensive stats"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Get users
    students = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ]
    teachers = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ]
    
    # Get active codes
    active_student_codes = len([
        c for c in store.student_codes.values() 
        if c['institution_id'] == institution_id and c['is_active'] and not c['student_id']
    ])
    active_teacher_codes = len([
        c for c in store.teacher_codes.values() 
        if c['institution_id'] == institution_id and c['is_active'] and not c['teacher_id']
    ])
    
    # Get subscription
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            break
    
    # Calculate usage
    usage = {
        'students': len(students),
        'teachers': len(teachers),
        'student_codes': active_student_codes,
        'teacher_codes': active_teacher_codes
    }
    
    limits = {
        'students': subscription.get('max_students') if subscription else None,
        'teachers': subscription.get('max_teachers') if subscription else None
    }
    
    # Get learning profiles for students
    active_profiles = 0
    at_risk_students = 0
    for student in students:
        if student['id'] in store.profiles:
            active_profiles += 1
            # Simple risk calculation (can be enhanced)
            profile = store.profiles[student['id']]
            avg_mastery = sum(s.level for s in profile.skills) / len(profile.skills) if profile.skills else 0
            if avg_mastery < 0.3:
                at_risk_students += 1
    
    return {
        'institution_id': institution_id,
        'institution': store.institutions[institution_id],
        'subscription': subscription,
        'overview': {
            'total_students': len(students),
            'total_teachers': len(teachers),
            'active_student_codes': active_student_codes,
            'active_teacher_codes': active_teacher_codes,
            'active_learning_profiles': active_profiles,
            'at_risk_students': at_risk_students
        },
        'usage': usage,
        'limits': limits,
        'utilization': {
            'students_percent': round(len(students) / limits['students'] * 100, 1) if limits['students'] else None,
            'teachers_percent': round(len(teachers) / limits['teachers'] * 100, 1) if limits['teachers'] else None
        }
    }


# STUDENT MANAGEMENT ENDPOINTS

@app.get("/institutions/{institution_id}/students")
def list_students(institution_id: str, authorization: str = Header(""), skip: int = 0, limit: int = 50):
    """List all students in an institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    skip = max(0, skip)
    limit = max(1, min(limit, 500))
    
    students = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ]
    
    # Add profile info where available
    students_with_profiles = []
    for student in students:
        student_data = student.copy()
        if student['id'] in store.profiles:
            profile = store.profiles[student['id']]
            student_data['has_profile'] = True
            student_data['grade_level'] = student.get('grade_level')
            student_data['skills_count'] = len(profile.skills)
        else:
            student_data['has_profile'] = False
            student_data['skills_count'] = 0
        students_with_profiles.append(student_data)
    
    # Pagination
    paginated = students_with_profiles[skip:skip + limit]
    
    return {
        'institution_id': institution_id,
        'students': paginated,
        'total': len(students_with_profiles),
        'skip': skip,
        'limit': limit
    }


@app.get("/institutions/{institution_id}/students/{student_id}")
def get_student_detail(institution_id: str, student_id: str, authorization: str = Header("")):
    """Get detailed information about a specific student"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if student_id not in store.users:
        raise HTTPException(404, "student not found")
    
    student = store.users[student_id]
    
    if student.get('institution_id') != institution_id or student.get('role') != 'student':
        raise HTTPException(404, "student not found in this institution")
    
    # Get learning profile
    profile = store.profiles.get(student_id)
    
    # Get cognitive snapshot and risk if profile exists
    cognitive = None
    risk = None
    if profile:
        from shared.intelligence import cognitive_snapshot, risk_score
        cognitive = cognitive_snapshot(profile)
        risk = risk_score(profile)
    
    return {
        'student': student,
        'profile': profile.model_dump() if profile else None,
        'cognitive': cognitive,
        'risk': risk
    }


@app.delete("/institutions/{institution_id}/students/{student_id}")
def deactivate_student(institution_id: str, student_id: str, authorization: str = Header("")):
    """Deactivate a student account"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if student_id not in store.users:
        raise HTTPException(404, "student not found")
    
    student = store.users[student_id]
    
    if student.get('institution_id') != institution_id or student.get('role') != 'student':
        raise HTTPException(404, "student not found in this institution")
    
    student['active'] = False
    
    audit(claims['sub'], 'STUDENT_DEACTIVATED', 'User', student_id, {
        'institution_id': institution_id
    })
    
    return {'status': 'deactivated', 'student_id': student_id}


# TEACHER MANAGEMENT ENDPOINTS

@app.get("/institutions/{institution_id}/teachers")
def list_teachers(institution_id: str, authorization: str = Header(""), skip: int = 0, limit: int = 50):
    """List all teachers in an institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    skip = max(0, skip)
    limit = max(1, min(limit, 500))
    
    teachers = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ]
    
    # Pagination
    paginated = teachers[skip:skip + limit]
    
    return {
        'institution_id': institution_id,
        'teachers': paginated,
        'total': len(teachers),
        'skip': skip,
        'limit': limit
    }


@app.get("/institutions/{institution_id}/teachers/{teacher_id}")
def get_teacher_detail(institution_id: str, teacher_id: str, authorization: str = Header("")):
    """Get detailed information about a specific teacher"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if teacher_id not in store.users:
        raise HTTPException(404, "teacher not found")
    
    teacher = store.users[teacher_id]
    
    if teacher.get('institution_id') != institution_id or teacher.get('role') != 'teacher':
        raise HTTPException(404, "teacher not found in this institution")
    
    # Count students assigned to this teacher (simplified - in real system would have assignments)
    assigned_students = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ])
    
    return {
        'teacher': teacher,
        'assigned_students': assigned_students
    }


@app.delete("/institutions/{institution_id}/teachers/{teacher_id}")
def deactivate_teacher(institution_id: str, teacher_id: str, authorization: str = Header("")):
    """Deactivate a teacher account"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if teacher_id not in store.users:
        raise HTTPException(404, "teacher not found")
    
    teacher = store.users[teacher_id]
    
    if teacher.get('institution_id') != institution_id or teacher.get('role') != 'teacher':
        raise HTTPException(404, "teacher not found in this institution")
    
    teacher['active'] = False
    
    audit(claims['sub'], 'TEACHER_DEACTIVATED', 'User', teacher_id, {
        'institution_id': institution_id
    })
    
    return {'status': 'deactivated', 'teacher_id': teacher_id}


# SUBSCRIPTION MANAGEMENT ENDPOINTS

@app.get("/institutions/{institution_id}/subscription")
def get_subscription(institution_id: str, authorization: str = Header("")):
    """Get current subscription details"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            break
    
    if not subscription:
        raise HTTPException(404, "subscription not found")
    
    # Calculate current usage
    student_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ])
    teacher_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ])
    
    return {
        'subscription': subscription,
        'usage': {
            'students': student_count,
            'teachers': teacher_count
        },
        'remaining': {
            'students': max(0, subscription.get('max_students', 0) - student_count) if subscription.get('max_students') else None,
            'teachers': max(0, subscription.get('max_teachers', 0) - teacher_count) if subscription.get('max_teachers') else None
        }
    }


@app.put("/institutions/{institution_id}/subscription")
def update_subscription(institution_id: str, body: UpdateSubscriptionRequest, authorization: str = Header("")):
    """Update subscription (plan change, auto-renew, etc.)"""
    claims = current(authorization)
    
    # Only super admin can change subscription plans
    if claims['role'] != 'super_admin':
        if body.plan_type is not None:
            raise HTTPException(403, "only super admin can change subscription plans")
        # Institution admins can only change auto-renew
        claims = require_institution_admin(claims)
        verify_institution_access(claims, institution_id)
    
    subscription = None
    sub_id = None
    for sid, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            sub_id = sid
            break
    
    if not subscription:
        raise HTTPException(404, "subscription not found")
    
    # Update fields
    if body.plan_type is not None:
        subscription['plan_type'] = body.plan_type.value
        
        # Update limits based on plan
        if body.plan_type == SubscriptionPlan.BASIC:
            subscription['max_students'] = 100
            subscription['max_teachers'] = 10
        elif body.plan_type == SubscriptionPlan.PROFESSIONAL:
            subscription['max_students'] = 500
            subscription['max_teachers'] = 50
        elif body.plan_type == SubscriptionPlan.ENTERPRISE:
            subscription['max_students'] = None  # Unlimited
            subscription['max_teachers'] = None  # Unlimited
    
    if body.auto_renew is not None:
        subscription['auto_renew'] = body.auto_renew
    
    subscription['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    audit(claims['sub'], 'SUBSCRIPTION_UPDATED', 'Subscription', sub_id, body.model_dump(exclude_none=True))
    
    return subscription


@app.post("/institutions/{institution_id}/subscription/cancel")
def cancel_subscription(institution_id: str, authorization: str = Header("")):
    """Cancel subscription"""
    claims = current(authorization)
    
    # Only super admin can cancel subscriptions
    if claims['role'] != 'super_admin':
        raise HTTPException(403, "only super admin can cancel subscriptions")
    
    subscription = None
    sub_id = None
    for sid, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            sub_id = sid
            break
    
    if not subscription:
        raise HTTPException(404, "subscription not found")
    
    subscription['status'] = SubscriptionStatus.CANCELLED.value
    subscription['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    audit(claims['sub'], 'SUBSCRIPTION_CANCELLED', 'Subscription', sub_id, {
        'institution_id': institution_id
    })
    
    return {'status': 'cancelled', 'subscription_id': sub_id}


# ANALYTICS AND REPORTING ENDPOINTS

@app.get("/institutions/{institution_id}/analytics/overview")
def get_analytics_overview(institution_id: str, authorization: str = Header(""), start_date: date = None, end_date: date = None):
    """Get analytics overview for institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Get students
    students = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ]
    
    # Get learning analytics
    total_skills = 0
    avg_mastery = 0
    at_risk_count = 0
    on_track_count = 0
    advanced_count = 0
    
    for student in students:
        if student['id'] in store.profiles:
            profile = store.profiles[student['id']]
            for skill in profile.skills:
                total_skills += 1
                avg_mastery += skill.level
            
            # Calculate student average
            if profile.skills:
                student_avg = sum(s.level for s in profile.skills) / len(profile.skills)
                if student_avg < 0.4:
                    at_risk_count += 1
                elif student_avg < 0.7:
                    on_track_count += 1
                else:
                    advanced_count += 1
    
    avg_mastery = avg_mastery / total_skills if total_skills > 0 else 0
    
    # Get activity data (simplified)
    active_students = len([s for s in students if s.get('active')])
    
    return {
        'institution_id': institution_id,
        'period': {
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None
        },
        'student_metrics': {
            'total_students': len(students),
            'active_students': active_students,
            'at_risk': at_risk_count,
            'on_track': on_track_count,
            'advanced': advanced_count
        },
        'learning_metrics': {
            'total_skills_tracked': total_skills,
            'average_mastery': round(avg_mastery, 3),
            'at_risk_rate': round(at_risk_count / len(students) * 100, 1) if students else 0
        },
        'engagement_metrics': {
            'active_rate': round(active_students / len(students) * 100, 1) if students else 0
        }
    }


@app.get("/institutions/{institution_id}/reports/summary")
def generate_summary_report(institution_id: str, authorization: str = Header(""), format: str = "json"):
    """Generate summary report for institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Get comprehensive data
    institution = store.institutions[institution_id]
    students = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ]
    teachers = [
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ]
    
    # Get subscription
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id:
            subscription = sub
            break
    
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generated_by': claims['sub'],
        'institution': {
            'id': institution_id,
            'name_ar': institution['name_ar'],
            'name_en': institution['name_en'],
            'type': institution['type'],
            'country': institution['country'],
            'city': institution['city']
        },
        'subscription': {
            'plan': subscription['plan_type'] if subscription else None,
            'status': subscription['status'] if subscription else None,
            'start_date': subscription['start_date'] if subscription else None,
            'end_date': subscription['end_date'] if subscription else None
        },
        'users': {
            'total_students': len(students),
            'total_teachers': len(teachers),
            'active_students': len([s for s in students if s.get('active')]),
            'active_teachers': len([t for t in teachers if t.get('active')])
        },
        'codes': {
            'student_codes': len([c for c in store.student_codes.values() if c['institution_id'] == institution_id]),
            'teacher_codes': len([c for c in store.teacher_codes.values() if c['institution_id'] == institution_id])
        }
    }
    
    audit(claims['sub'], 'REPORT_GENERATED', 'Institution', institution_id, {
        'report_type': 'summary',
        'format': format
    })
    
    return report


# BILLING ENDPOINTS

@app.get("/institutions/{institution_id}/billing/summary")
def get_billing_summary(institution_id: str, authorization: str = Header("")):
    """Get billing summary for institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    
    billing_service = get_billing_service(store)
    summary = billing_service.get_billing_summary(institution_id)
    
    return summary


@app.get("/institutions/{institution_id}/invoices")
def list_invoices(institution_id: str, authorization: str = Header(""), 
                  status: str = None, skip: int = 0, limit: int = 50):
    """List invoices for institution"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    verify_institution_access(claims, institution_id)
    skip = max(0, skip)
    limit = max(1, min(limit, 500))
    
    billing_service = get_billing_service(store)
    invoices = billing_service.get_invoices_by_institution(institution_id)
    
    # Filter by status if provided
    if status:
        invoices = [inv for inv in invoices if inv.status.value == status]
    
    # Convert to dict format
    invoices_data = [
        {
            'id': inv.id,
            'invoice_number': inv.invoice_number,
            'status': inv.status.value,
            'issue_date': inv.issue_date.isoformat(),
            'due_date': inv.due_date.isoformat(),
            'currency': inv.currency.value,
            'total_amount': float(inv.total_amount),
            'paid_date': inv.paid_date.isoformat() if inv.paid_date else None
        }
        for inv in invoices
    ]
    
    # Pagination
    paginated = invoices_data[skip:skip + limit]
    
    return {
        'institution_id': institution_id,
        'invoices': paginated,
        'total': len(invoices_data),
        'skip': skip,
        'limit': limit
    }


@app.post("/institutions/{institution_id}/invoices/generate")
def generate_invoice(institution_id: str, authorization: str = Header(""),
                    billing_cycle: str = "monthly", due_days: int = 30):
    """Generate a new invoice for the institution"""
    claims = current(authorization)
    
    # Only super admin can generate invoices
    if claims['role'] != 'super_admin':
        raise HTTPException(403, "only super admin can generate invoices")
    
    if institution_id not in store.institutions:
        raise HTTPException(404, "institution not found")
    
    # Get subscription
    subscription = None
    for sub_id, sub in store.subscriptions.items():
        if sub['institution_id'] == institution_id and sub['status'] in ['trial', 'active']:
            subscription = sub
            break
    
    if not subscription:
        raise HTTPException(400, "no active subscription found")
    
    # Get current usage
    student_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'student'
    ])
    teacher_count = len([
        u for u in store.users.values() 
        if u.get('institution_id') == institution_id and u.get('role') == 'teacher'
    ])
    
    # Generate invoice
    billing_service = get_billing_service(store)
    invoice = billing_service.create_invoice(
        institution_id=institution_id,
        subscription_id=subscription['id'],
        plan_type=subscription['plan_type'],
        billing_cycle=billing_cycle,
        student_count=student_count,
        teacher_count=teacher_count,
        due_days=due_days
    )
    
    audit(claims['sub'], 'INVOICE_GENERATED', 'Invoice', invoice.id, {
        'institution_id': institution_id,
        'invoice_number': invoice.invoice_number,
        'amount': float(invoice.total_amount)
    })
    
    return {
        'invoice': {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'status': invoice.status.value,
            'issue_date': invoice.issue_date.isoformat(),
            'due_date': invoice.due_date.isoformat(),
            'currency': invoice.currency.value,
            'subtotal': float(invoice.subtotal),
            'tax_amount': float(invoice.tax_amount),
            'discount_amount': float(invoice.discount_amount),
            'total_amount': float(invoice.total_amount),
            'items': [
                {
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total': float(item.total)
                }
                for item in invoice.items
            ]
        },
        'billing_summary': {
            'student_count': student_count,
            'teacher_count': teacher_count,
            'plan_type': subscription['plan_type'],
            'billing_cycle': billing_cycle
        }
    }


@app.get("/invoices/{invoice_id}")
def get_invoice_details(invoice_id: str, authorization: str = Header("")):
    """Get detailed invoice information"""
    claims = current(authorization)
    claims = require_institution_admin(claims)
    
    billing_service = get_billing_service(store)
    invoice = billing_service.get_invoice(invoice_id)
    
    if not invoice:
        raise HTTPException(404, "invoice not found")
    
    # Verify access
    verify_institution_access(claims, invoice.institution_id)
    
    # Get payments
    payments = billing_service.get_payments_by_invoice(invoice_id)
    
    return {
        'invoice': {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'institution_id': invoice.institution_id,
            'subscription_id': invoice.subscription_id,
            'status': invoice.status.value,
            'issue_date': invoice.issue_date.isoformat(),
            'due_date': invoice.due_date.isoformat(),
            'currency': invoice.currency.value,
            'subtotal': float(invoice.subtotal),
            'tax_amount': float(invoice.tax_amount),
            'discount_amount': float(invoice.discount_amount),
            'total_amount': float(invoice.total_amount),
            'payment_method': invoice.payment_method.value if invoice.payment_method else None,
            'paid_date': invoice.paid_date.isoformat() if invoice.paid_date else None,
            'notes': invoice.notes,
            'items': [
                {
                    'id': item.id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total': float(item.total)
                }
                for item in invoice.items
            ]
        },
        'payments': [
            {
                'id': payment.id,
                'amount': float(payment.amount),
                'payment_method': payment.payment_method.value,
                'payment_date': payment.payment_date.isoformat(),
                'transaction_id': payment.transaction_id,
                'status': payment.status,
                'notes': payment.notes
            }
            for payment in payments
        ],
        'amount_paid': sum(float(p.amount) for p in payments),
        'amount_remaining': float(invoice.total_amount) - sum(float(p.amount) for p in payments)
    }


@app.post("/invoices/{invoice_id}/payments")
def record_payment(invoice_id: str, amount: float, payment_method: str, 
                  transaction_id: str = None, notes: str = None,
                  authorization: str = Header("")):
    """Record a payment for an invoice"""
    claims = current(authorization)
    
    # Only super admin can record payments
    if claims['role'] != 'super_admin':
        raise HTTPException(403, "only super admin can record payments")
    
    billing_service = get_billing_service(store)
    invoice = billing_service.get_invoice(invoice_id)
    
    if not invoice:
        raise HTTPException(404, "invoice not found")
    
    try:
        payment = billing_service.record_payment(
            invoice_id=invoice_id,
            amount=Decimal(str(amount)),
            payment_method=PaymentMethod[payment_method.upper()],
            transaction_id=transaction_id,
            notes=notes
        )
        
        audit(claims['sub'], 'PAYMENT_RECORDED', 'Payment', payment.id, {
            'invoice_id': invoice_id,
            'amount': amount,
            'payment_method': payment_method
        })
        
        return {
            'payment': {
                'id': payment.id,
                'invoice_id': payment.invoice_id,
                'amount': float(payment.amount),
                'payment_method': payment.payment_method.value,
                'payment_date': payment.payment_date.isoformat(),
                'transaction_id': payment.transaction_id,
                'status': payment.status,
                'notes': payment.notes
            },
            'invoice_status': billing_service.get_invoice(invoice_id).status.value
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/invoices/{invoice_id}/status")
def update_invoice_status(invoice_id: str, status: str, authorization: str = Header("")):
    """Update invoice status"""
    claims = current(authorization)
    
    # Only super admin can update invoice status
    if claims['role'] != 'super_admin':
        raise HTTPException(403, "only super admin can update invoice status")
    
    billing_service = get_billing_service(store)
    
    try:
        invoice = billing_service.update_invoice_status(invoice_id, InvoiceStatus[status.upper()])
        
        if not invoice:
            raise HTTPException(404, "invoice not found")
        
        audit(claims['sub'], 'INVOICE_STATUS_UPDATED', 'Invoice', invoice_id, {
            'old_status': invoice.status.value,
            'new_status': status
        })
        
        return {
            'id': invoice.id,
            'invoice_number': invoice.invoice_number,
            'status': invoice.status.value,
            'updated_at': invoice.updated_at.isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(400, str(e))
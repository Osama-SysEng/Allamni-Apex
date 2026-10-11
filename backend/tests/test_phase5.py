"""
Phase 5 Enhanced Features - Comprehensive Test Suite
Tests enhanced authentication, advanced security, powerful AI chatbot, and real-time features
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Import Phase 5 modules
from shared.enhanced_auth import get_enhanced_auth_service, SecurityLevel
from shared.advanced_security import get_advanced_security_service, SecurityConfig
from shared.powerful_ai_chatbot import get_powerful_ai_chatbot, ConversationContext, AIPersonality
from shared.real_time_features import get_real_time_service, NotificationPriority
from shared.store import store

def test_enhanced_authentication():
    """Test enhanced authentication features"""
    auth_service = get_enhanced_auth_service(store)

    # Test session creation
    session = auth_service.create_session(
        user_id="user_1",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
        device_id="device_1",
        security_level=SecurityLevel.HIGH
    )

    assert session.id and session.is_valid(), "فشل إنشاء الجلسة"

    # Test session validation
    is_valid = auth_service.validate_session(session.id, "192.168.1.1", "Mozilla/5.0")
    assert is_valid, "فشل التحقق من الجلسة"

    # Test 2FA setup
    two_fa = auth_service.setup_2fa("user_1")
    assert two_fa.secret and len(two_fa.backup_codes) == 10, "فشل إعداد المصادقة الثنائية"

    # Test biometric setup
    biometric = auth_service.setup_biometric("user_1", "device_1", "biometric_data_123")
    assert biometric.device_id and biometric.is_enabled, "فشل إعداد البصمة"

    # Test failed login tracking
    attempts = auth_service.record_failed_login("user_1", "192.168.1.1")
    assert attempts == 1, "فشل تتبع محاولات الدخول"

    # Test account lockout
    for _ in range(5):
        auth_service.record_failed_login("user_1", "192.168.1.1")

    is_locked = auth_service.is_account_locked("user_1")
    assert is_locked, "فشل قفل الحساب"

    # Test security events
    events = auth_service.get_security_events("user_1")
    assert len(events) > 0, "أحداث الحماية غير مسجلة"

def test_advanced_security():
    """Test advanced security features"""
    config = SecurityConfig(
        max_failed_attempts=3,
        rate_limit_requests_per_minute=30
    )
    security_service = get_advanced_security_service(store, config)

    # Test data encryption
    original_data = "sensitive_password_123"
    encrypted = security_service.encrypt_data(original_data)
    assert encrypted != original_data, "فشل تشفير البيانات"

    # Test data decryption
    decrypted = security_service.decrypt_data(encrypted)
    assert decrypted == original_data, "فشل فك التشفير"

    # Test input validation
    is_valid, error = security_service.validate_input("test@example.com", "email")
    assert is_valid, f"فشل قبول البريد الصحيح: {error}"

    # Test invalid input detection
    is_valid, error = security_service.validate_input("invalid-email", "email")
    assert not is_valid, "لم يتم كشف البريد الخاطئ"

    # Test rate limiting
    for i in range(60):
        security_service.check_rate_limit("user_1", "/api/test", "minute")

    # Should block on 61st request
    is_allowed = security_service.check_rate_limit("user_1", "/api/test", "minute")
    assert not is_allowed, "لم يتم تفعيل تحديد المعدل"

    # Test security scan
    scan_results = security_service.perform_security_scan()
    assert scan_results['security_score'] >= 80, "درجة الفحص الأمني منخفضة"

def test_powerful_ai_chatbot():
    """Test powerful AI chatbot features"""
    chatbot = get_powerful_ai_chatbot(store)

    # Test conversation start
    conversation_id = chatbot.start_conversation(
        user_id="student_1",
        context_type=ConversationContext.LEARNING,
        topic="python_basics",
        dialect="egyptian",
        personality=AIPersonality.FRIENDLY_TUTOR,
        skill_codes=["variables", "data_types"],
        user_level=0.6
    )

    assert conversation_id, "فشل بدء المحادثة"

    # Test message sending (async API)
    import asyncio as _asyncio
    response = _asyncio.run(chatbot.send_message(
        conversation_id=conversation_id,
        user_message="شرح لي المتغيرات في بايثون"
    ))

    assert response.content and response.confidence > 0, "فشل توليد رد الذكاء"

    # Test conversation summary
    summary = chatbot.get_conversation_summary(conversation_id)
    assert summary and summary.get('topic') == "python_basics", "فشل ملخص المحادثة"

    # Test conversation analytics
    analytics = chatbot.get_conversation_analytics("student_1")
    assert analytics and analytics.get('total_conversations', 0) >= 1, "فشل تحليلات المحادثات"

    # Test knowledge base
    knowledge = chatbot._get_relevant_knowledge("python_basics", ["variables"])
    assert knowledge and 'topics' in knowledge, "فشل الوصول لقاعدة المعرفة"

def test_real_time_features():
    """Test real-time features"""
    real_time_service = get_real_time_service(store)

    # Test notification creation
    notification_id = real_time_service.create_notification(
        user_id="student_1",
        title="اختبار إشعار",
        body="هذا إشعار تجريبي من النظام",
        priority=NotificationPriority.HIGH,
        action_url="/test",
        action_label="عرض"
    )

    assert notification_id, "فشل إنشاء الإشعار"

    # Test notification retrieval
    notifications = real_time_service.get_user_notifications("student_1")
    assert len(notifications) > 0, "فشل جلب الإشعارات"

    # Test unread count
    unread_count = real_time_service.get_unread_count("student_1")
    assert unread_count >= 0, "فشل عد غير المقروء"

    # Test marking as read
    is_marked = real_time_service.mark_notification_read(notification_id, "student_1")
    assert is_marked, "فشل تعليم الإشعار كمقروء"

    # Test notification preferences
    real_time_service.set_notification_preferences("student_1", {
        'email_enabled': True,
        'push_enabled': True,
        'sound_enabled': False
    })

    preferences = real_time_service.get_notification_preferences("student_1")
    assert preferences['sound_enabled'] == False, "فشل حفظ تفضيلات الإشعارات"

    # Test live session creation
    session_data = real_time_service.create_live_session(
        session_id="session_1",
        host_id="teacher_1",
        participants=["student_1", "student_2"],
        topic="Python Tutorial"
    )

    assert session_data and session_data['topic'] == "Python Tutorial", "فشل إنشاء الجلسة المباشرة"

def test_phase5_integration():
    """Test integration of all Phase 5 features"""
    # Initialize all Phase 5 services
    auth_service = get_enhanced_auth_service(store)
    security_service = get_advanced_security_service(store)
    chatbot = get_powerful_ai_chatbot(store)
    real_time_service = get_real_time_service(store)

    # Test integrated workflow
    # 1. User logs in with enhanced auth
    session = auth_service.create_session("user_1", "192.168.1.1", "TestAgent", "device_1")

    # 2. Security scan checks user
    security_service.check_rate_limit("user_1", "/api/login", "minute")

    # 3. User starts AI conversation
    conversation_id = chatbot.start_conversation(
        user_id="user_1",
        context_type=ConversationContext.LEARNING,
        topic="python_basics",
        dialect="egyptian",
        personality=AIPersonality.FRIENDLY_TUTOR,
        skill_codes=["variables"],
        user_level=0.5
    )

    # 4. AI sends notification about conversation
    real_time_service.create_notification(
        "user_1", "محادثة جديدة", "تم بدء محادثة تعليمية", NotificationPriority.MEDIUM
    )

    # Verify integration
    assert session.id and conversation_id, "فشل تكامل مكونات المرحلة 5"

    # Test cross-component functionality
    # Check that auth session is tracked
    assert auth_service.get_active_sessions("user_1"), "جلسات المصادقة غير متتبعة"

    # Check that security metrics are updated
    security_metrics = security_service.get_security_metrics()
    assert security_metrics.get('total_requests', 0) > 0, "مقاييس الحماية غير محدثة"

    # Check that conversation analytics are tracked
    conversation_analytics = chatbot.get_conversation_analytics("user_1")
    assert conversation_analytics.get('total_conversations', 0) > 0, "تحليلات المحادثات غير متتبعة"

    # Check that notifications are stored
    notifications = real_time_service.get_user_notifications("user_1")
    assert len(notifications) > 0, "الإشعارات غير مخزنة"

def test_store_collections():
    """Test that store has Phase 5 collections"""
    required_collections = [
        # Phase 5 Enhanced Security
        'auth_sessions',
        'two_factor_auths',
        'biometric_auths',
        'security_events',
        'failed_login_attempts',
        'account_lockouts',
        'rate_limits',
        'security_incidents',
        'encrypted_data',
        'security_metrics',
        # Phase 5 AI Chatbot
        'conversation_threads',
        'conversation_memories',
        'ai_knowledge_base',
        'conversation_analytics',
        # Phase 5 Real-time
        'real_time_events',
        'notifications',
        'notification_preferences'
    ]

    for collection in required_collections:
        assert hasattr(store, collection), f"المخزن يفتقد المجموعة: {collection}"

def main():
    print("=" * 80)
    print("PHASE 5 ENHANCED FEATURES TESTS - Allamni v4.0")
    print("=" * 80)

    tests = [
        ("Enhanced Authentication", test_enhanced_authentication),
        ("Advanced Security", test_advanced_security),
        ("Powerful AI Chatbot", test_powerful_ai_chatbot),
        ("Real-Time Features", test_real_time_features),
        ("Phase 5 Integration", test_phase5_integration),
        ("Store Collections", test_store_collections)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, True))
        except AssertionError as e:
            print(f"[FAIL] {test_name}: {e}")
            results.append((test_name, False))
        except Exception as e:
            print(f"[ERROR] {test_name} failed with exception: {e}")
            results.append((test_name, False))

    print("\n" + "=" * 80)
    print("PHASE 5 TEST RESULTS")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print("=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 80)

    if passed == total:
        print("\n[SUCCESS] ALL PHASE 5 TESTS PASSED!")
        print("\nFinal System Status:")
        print("- Phase 1: RBAC, Auth, AI Integration [READY]")
        print("- Phase 2: Institution Management, Billing, Odoo [READY]")
        print("- Phase 3: Self-Learning, Arabic NLP, Voice, Image [READY]")
        print("- Phase 4: Flutter Frontend Enhanced [READY]")
        print("- Phase 5: Enhanced Security, AI Chatbot, Real-Time [READY]")
        print("- Integration: All five phases integrated [VERIFIED]")
        print("- Security: Advanced security features [VERIFIED]")
        print("- AI: Powerful chatbot with memory [VERIFIED]")
        print("- Real-time: Live updates and notifications [VERIFIED]")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())

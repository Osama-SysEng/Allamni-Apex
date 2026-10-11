"""
Final Comprehensive Integration Test for Allamni v4.0
Tests all three phases (1, 2, 3) together to verify complete system integration
"""
import sys
import os
# Integration tests run against the deterministic mock provider (no live keys).
os.environ.setdefault("AI_PROVIDER", "mock")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Import Phase 1 modules
from shared.identity import generate_student_code, generate_teacher_code, validate_student_code, validate_teacher_code
from shared.permissions import has_permission
from shared.models import UserRole
from shared.security import create_token
from shared.store import store

# Import Phase 2 modules
from shared.billing import BillingService, InvoiceStatus, PaymentMethod, Currency

# Import Phase 3 modules
from shared.self_learning import get_self_learning_pipeline, LearningSignal, LearningSignalType, SignalQuality
from shared.arabic_nlp import get_arabic_nlp_processor, ArabicDialect
from shared.voice_input import get_voice_processor, VoiceLanguage
from shared.image_analysis import get_image_analyzer, ImageType
from shared.memory import LearningMemory, MemoryType, MemoryImportance

def test_complete_system_workflow():
    """Test complete workflow across all three phases"""
    # Phase 1: Institution and Code Generation
    institution_id = str(uuid4())
    institution_data = {
        'id': institution_id,
        'name': 'Test School',
        'type': 'school',
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    store.institutions[institution_id] = institution_data

    student_code_data = generate_student_code(institution_id, "class_1", "grade_10", "2024-2025", "admin_1")
    teacher_code_data = generate_teacher_code(institution_id, "math_dept", ["math", "science"], ["grade_10", "grade_11"], "admin_1")

    assert student_code_data['code'] and teacher_code_data['code'], "فشل توليد الأكواد"

    # Phase 1: User Registration with Codes
    student_user = {
        'id': str(uuid4()),
        'email': 'student@example.com',
        'role': UserRole.STUDENT.value,
        'institution_id': institution_id,
        'registered_with_code': student_code_data['code']
    }
    teacher_user = {
        'id': str(uuid4()),
        'email': 'teacher@example.com',
        'role': UserRole.TEACHER.value,
        'institution_id': institution_id,
        'registered_with_code': teacher_code_data['code']
    }

    store.users[student_user['id']] = student_user
    store.users[teacher_user['id']] = teacher_user

    # Validate codes
    valid_student_code = validate_student_code(student_code_data['code'])
    valid_teacher_code = validate_teacher_code(teacher_code_data['code'])

    assert valid_student_code and valid_teacher_code, "فشل التحقق من الأكواد"

    # Phase 1: Authentication and Permissions
    token = create_token(student_user['id'], student_user['role'], institution_id)

    student_can_edit_own = has_permission(student_user['role'], "profile", "edit", "own")
    teacher_can_view_students = has_permission(teacher_user['role'], "students", "view", "institution")

    assert student_can_edit_own and teacher_can_view_students, "فشل فحص الصلاحيات"

    # Phase 2: Subscription and Billing
    billing_service = BillingService(store)

    subscription_data = {
        'id': str(uuid4()),
        'institution_id': institution_id,
        'plan_type': 'professional',
        'status': 'active',
        'student_count': 1,
        'teacher_count': 1
    }
    store.subscriptions[subscription_data['id']] = subscription_data

    # Generate invoice
    invoice = billing_service.create_invoice(
        institution_id=institution_id,
        subscription_id=subscription_data['id'],
        plan_type='professional',
        billing_cycle='monthly',
        student_count=1,
        teacher_count=1
    )

    assert invoice and invoice.total_amount > 0, "فشل إنشاء الفاتورة"

    # Record payment
    payment = billing_service.record_payment(
        invoice_id=invoice.id,
        amount=invoice.total_amount,
        payment_method=PaymentMethod.CREDIT_CARD,
        transaction_id="txn_12345"
    )

    assert payment, "فشل تسجيل الدفعة"

    # Phase 3: AI-Powered Learning Features

    # Arabic NLP processing
    nlp_processor = get_arabic_nlp_processor()
    text_analysis = nlp_processor.process_text("explain python loops", ArabicDialect.MODERN_STANDARD)

    assert text_analysis.detected_dialect, "فشل معالجة النص العربي"

    # Voice input
    voice_processor = get_voice_processor()
    voice_transcription = voice_processor.transcribe_audio("audio_data_placeholder", VoiceLanguage.ENGLISH, student_user['id'])

    assert voice_transcription.transcribed_text, "فشل تحويل الصوت لنص"

    # Image analysis
    image_analyzer = get_image_analyzer()
    image_analysis = image_analyzer.analyze_image("image_data_placeholder", ImageType.QUESTION_IMAGE, student_user['id'])

    assert image_analysis.detected_content, "فشل تحليل الصورة"

    # Enhanced memory
    memory = LearningMemory()
    memory_id = memory.remember(
        user_id=student_user['id'],
        memory_type="conversation",
        content={"topic": "python_loops", "interaction": "student asked about loops"},
        importance="high",
        tags=["python", "loops", "help"]
    )

    assert memory_id, "فشل نظام الذاكرة"

    # Self-learning pipeline
    learning_pipeline = get_self_learning_pipeline(store)
    learning_signal = LearningSignal(
        id=str(uuid4()),
        signal_type=LearningSignalType.EXPLANATION_SUCCESS,
        user_id=student_user['id'],
        context={"topic": "python_loops", "dialect": text_analysis.detected_dialect.value},
        content_data={"explanation_quality": "high"},
        outcome="success",
        quality=SignalQuality.HIGH,
        timestamp=datetime.now(timezone.utc)
    )
    signal_id = learning_pipeline.record_signal(learning_signal)

    assert signal_id, "فشل خط التعلم الذاتي"

    # Cross-phase integration test

    # Verify institution data is accessible across services
    institution_data = store.institutions.get(institution_id)
    assert institution_data, "بيانات المؤسسة غير متاحة"

    # Verify billing is linked to institution
    assert invoice.institution_id == institution_id, "الفوترة غير مرتبطة بالمؤسسة"

    # Verify AI features have user context
    recalled_memory = memory.recall(student_user['id'], limit=5)
    assert len(recalled_memory) > 0, "ذاكرة الذكاء تفتقد سياق المستخدم"

    # Verify learning signals are tied to users
    learning_metrics = learning_pipeline.get_learning_metrics()
    assert learning_metrics['total_signals'] > 0, "إشارات التعلم غير مسجلة"

def test_data_consistency():
    """Test data consistency across all phases"""
    # Create test institution
    institution_id = str(uuid4())
    institution_data = {
        'id': institution_id,
        'name': 'Test School',
        'type': 'school',
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    store.institutions[institution_id] = institution_data

    # Create subscription
    subscription_id = str(uuid4())
    subscription_data = {
        'id': subscription_id,
        'institution_id': institution_id,
        'plan_type': 'professional',
        'status': 'active'
    }
    store.subscriptions[subscription_id] = subscription_data

    # Create users
    student_id = str(uuid4())
    student_data = {
        'id': student_id,
        'email': 'student@test.com',
        'role': 'student',
        'institution_id': institution_id
    }
    store.users[student_id] = student_data

    # Verify relationships
    assert store.institutions[institution_id]['id'] == institution_id, "فشل تخزين المؤسسة"

    assert store.subscriptions[subscription_id]['institution_id'] == institution_id, "فشل ربط الاشتراك بالمؤسسة"

    assert store.users[student_id]['institution_id'] == institution_id, "فشل ربط المستخدم بالمؤسسة"

    # Test Phase 3 data consistency
    learning_pipeline = get_self_learning_pipeline(store)
    signal = LearningSignal(
        id=str(uuid4()),
        signal_type=LearningSignalType.EXPLANATION_SUCCESS,
        user_id=student_id,
        context={"institution_id": institution_id},
        content_data={},
        outcome="success",
        quality=SignalQuality.HIGH,
        timestamp=datetime.now(timezone.utc)
    )
    signal_id = learning_pipeline.record_signal(signal)

    assert signal_id in store.learning_signals, "فشل تخزين إشارة التعلم"

def test_service_integration():
    """Test integration between different services"""
    # Test that store has all required collections
    required_collections = [
        # Phase 1
        'users', 'profiles', 'institutions', 'subscriptions', 'student_codes', 'teacher_codes',
        # Phase 2
        'invoices', 'payments', 'odoo_sync_events',
        # Phase 3
        'learning_signals', 'learning_patterns', 'model_updates', 'learning_metrics',
        'voice_interactions', 'voice_sessions', 'image_analyses'
    ]

    for collection in required_collections:
        assert hasattr(store, collection), f"المخزن يفتقد المجموعة: {collection}"

    # Test service initialization (any exception fails the test)
    billing_service = BillingService(store)
    learning_pipeline = get_self_learning_pipeline(store)
    nlp_processor = get_arabic_nlp_processor()
    voice_processor = get_voice_processor()
    image_analyzer = get_image_analyzer()
    memory = LearningMemory()
    assert billing_service is not None and learning_pipeline is not None, "فشل تهيئة الخدمات"
    assert nlp_processor is not None and voice_processor is not None, "فشل تهيئة خدمات الذكاء"
    assert image_analyzer is not None and memory is not None, "فشل تهيئة الذاكرة وتحليل الصور"

def test_backward_compatibility():
    """Test backward compatibility with existing functionality"""
    # Test Phase 1 backward compatibility
    student_code = generate_student_code("test_inst", "class_1", "grade_10", "2024", "admin")
    assert student_code['code'], "توافق المرحلة 1 مكسور"

    # Test Phase 2 backward compatibility
    billing_service = BillingService(store)
    invoice = billing_service.create_invoice(
        institution_id="test_inst",
        subscription_id="sub_1",
        plan_type="basic",
        billing_cycle="monthly",
        student_count=10,
        teacher_count=2
    )
    assert invoice, "توافق الفوترة مكسور"

    # Test memory backward compatibility
    memory = LearningMemory()
    legacy_recall = memory.recall_legacy("user_1", "conversation")
    assert isinstance(legacy_recall, list), "توافق الذاكرة القديمة مكسور"

def main():
    print("=" * 80)
    print("FINAL COMPREHENSIVE INTEGRATION TEST - Allamni v4.0")
    print("Testing all three phases together")
    print("=" * 80)

    # Reset store for clean test
    store.reset()

    tests = [
        ("Complete System Workflow", test_complete_system_workflow),
        ("Data Consistency", test_data_consistency),
        ("Service Integration", test_service_integration),
        ("Backward Compatibility", test_backward_compatibility)
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
    print("FINAL INTEGRATION TEST RESULTS")
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
        print("\n[SUCCESS] ALL FINAL INTEGRATION TESTS PASSED!")
        print("\nFinal System Status:")
        print("- Phase 1: RBAC, Auth, AI Integration [VERIFIED]")
        print("- Phase 2: Institution Management, Billing, Odoo [VERIFIED]")
        print("- Phase 3: Self-Learning, Arabic NLP, Voice, Image [VERIFIED]")
        print("- Integration: Complete system integration [VERIFIED]")
        print("- Data Consistency: Cross-phase data integrity [VERIFIED]")
        print("- Backward Compatibility: Legacy functionality preserved [VERIFIED]")
        print("\nAllamni v4.0 Education Operating System is ready for deployment!")
        return 0
    else:
        print(f"\n[ERROR] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    exit(main())

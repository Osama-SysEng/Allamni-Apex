from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime, timezone
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from shared.security import decode_token
from shared.store import store
from shared.intelligence import AgentOrchestrator, cognitive_snapshot, risk_score
from shared.content import lesson_blueprint
from shared.ai_providers import get_ai_provider, AIProviderType, AIMessage, MessageRole
from shared.config.settings import settings
from shared.logging_utils import get_logger
from shared.arabic_nlp import get_arabic_nlp_processor, ArabicDialect
from shared.voice_input import get_voice_processor, VoiceLanguage
from shared.image_analysis import get_image_analyzer, ImageType
from shared.self_learning import get_self_learning_pipeline
from shared.powerful_ai_chatbot import get_powerful_ai_chatbot, ConversationContext, AIPersonality
from shared.real_time_features import get_real_time_service, NotificationPriority

app=FastAPI(title="Allamni AI Service", version="4.0.0")
logger = get_logger("ai-service")
orchestrator=AgentOrchestrator()

# Initialize AI provider based on configuration
provider_type = AIProviderType(os.getenv("AI_PROVIDER", "gemini"))
try:
    ai_provider = get_ai_provider(
        provider_type=provider_type,
        api_key=os.getenv("GEMINI_API_KEY"),
        model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    )
except Exception as e:
    logger.error(f"Error: Could not initialize AI provider: {e}")
    ai_provider = None

@app.on_event("startup")
async def startup_validation():
    """Validate AI provider on startup — fail fast if not configured"""
    provider_type = AIProviderType(os.getenv("AI_PROVIDER", "gemini"))
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key and os.getenv("ENVIRONMENT", "production") == "production":
        raise RuntimeError(
            "No AI API key configured. "
            "Set GEMINI_API_KEY in your .env file. "
            "Get it from: https://aistudio.google.com/app/apikey"
        )
    
    logger.info(f"AI Service started with provider: {provider_type}")
    logger.info(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')}")

class AnalyzeRequest(BaseModel): student_id:str
class GenerateRequest(BaseModel): student_id:str; prompt:str="Create adaptive learning material"; context:dict={}
class ChatRequest(BaseModel): student_id:str; message:str; conversation_history:list=[]; dialect:str="modern_standard"
class ExplainRequest(BaseModel): student_id:str; text:str; context:dict={}
class VoiceTranscribeRequest(BaseModel): student_id:str; audio_data:str; language:str="ar"
class ArabicNLPRequest(BaseModel): student_id:str; text:str; target_dialect:str=None
class ImageAnalysisRequest(BaseModel): student_id:str; image_data:str; image_type:str="question_image"
class LearningSignalRequest(BaseModel): student_id:str; signal_type:str; context:dict; content_data:dict; outcome:str

async def auth(authorization):
    if not authorization.startswith("Bearer "): raise HTTPException(401,"missing token")
    try:return decode_token(authorization[7:])
    except Exception as e:raise HTTPException(401,str(e))

@app.get("/health")
def health():return {"status":"ok","service":"ai","version":"3.0.0"}

@app.post("/students/analyze")
async def analyze(body:AnalyzeRequest,authorization:str=Header("")):
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"forbidden")
    profile=store.profiles.get(body.student_id)
    if not profile:raise HTTPException(404,"profile not found")
    
    # Use deterministic analysis for now (can be enhanced with AI later)
    analysis = {"summary":"Cognitive analysis complete","gaps":[s.code for s in profile.skills if s.target>s.level]}
    
    return {"cognitive":cognitive_snapshot(profile),"risk":risk_score(profile),"orchestration":orchestrator.run(profile),"provider":ai_provider.__class__.__name__,"analysis":analysis}

@app.post("/students/generate-plan")
async def generate_plan(body:AnalyzeRequest,authorization:str=Header("")):
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"forbidden")
    profile=store.profiles.get(body.student_id)
    if not profile:raise HTTPException(404,"profile not found")
    
    try:
        analysis_response = await ai_provider.analyze(profile.model_dump())
        analysis = analysis_response.model_dump() if hasattr(analysis_response, 'model_dump') else analysis_response
    except Exception as e:
        analysis = {"error": str(e), "fallback": "Using deterministic analysis"}
    
    return {"plan":lesson_blueprint(profile,store.resources),"analysis":analysis,"provider":ai_provider.__class__.__name__}

@app.post("/students/generate")
async def generate(body:GenerateRequest,authorization:str=Header("")):
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"forbidden")
    profile=store.profiles.get(body.student_id)
    if not profile: raise HTTPException(404,"profile not found")
    response = await ai_provider.generate(body.prompt,body.context | {"profile":profile.model_dump()})
    return response.model_dump()

# v4.0 New AI Companion Endpoints

@app.post("/students/chat")
async def chat(body:ChatRequest,authorization:str=Header("")):
    """AI Companion chat with Arabic dialect support"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    profile=store.profiles.get(body.student_id)
    if not profile: raise HTTPException(404,"profile not found")
    
    # Convert conversation history to AIMessage format
    messages = []
    for msg in body.conversation_history:
        role = MessageRole.USER if msg.get("role") == "user" else MessageRole.ASSISTANT
        messages.append(AIMessage(role=role, content=msg.get("content", "")))
    
    # Add current message
    messages.append(AIMessage(role=MessageRole.USER, content=body.message))
    
    # Set dialect-specific system instruction
    dialect_instructions = {
        "modern_standard": "أنت معلم ذكي يتحدث العربية الفصحى الحديثة.",
        "egyptian": "أنت معلم ذكي يتحدث العربية اللهجة المصرية.",
        "gulf": "أنت معلم ذكي يتحدث العربية اللهجة الخليجية.",
        "levantine": "أنت معلم ذكي يتحدث العربية اللهجة الشامية.",
    }
    
    system_instruction = dialect_instructions.get(body.dialect, dialect_instructions["modern_standard"])
    
    context = {
        "system_instruction": system_instruction,
        "profile": profile.model_dump(),
        "student_id": body.student_id
    }
    
    response = await ai_provider.chat(messages, context)
    return response.model_dump()

@app.post("/students/explain")
async def explain(body:ExplainRequest,authorization:str=Header("")):
    """AI explanation for highlighted text in content"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    profile=store.profiles.get(body.student_id)
    if not profile: raise HTTPException(404,"profile not found")
    
    prompt = f"""
    قم بشرح النص التالي للطالب بطريقة بسيطة وواضحة:
    
    النص: {body.text}
    
    السياق: {body.context}
    
    ملف الطالب: {profile.model_dump()}
    
    قدم شرحاً مبسطاً مع أمثلة عملية.
    """
    
    response = await ai_provider.generate(prompt, {
        "system_instruction": "أنت معلم ذكي يشرح المفاهيم بطريقة مبسطة ومفهومة للطلاب.",
        "profile": profile.model_dump()
    })
    
    return response.model_dump()

@app.post("/students/voice-transcribe")
async def voice_transcribe(body:VoiceTranscribeRequest,authorization:str=Header("")):
    """Voice input transcription (placeholder for speech-to-text)"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    
    # NOTE (documented scope): STT provider integration (e.g. Google Speech-to-Text)
    # requires a user-supplied API key; until then this endpoint returns an
    # explicit placeholder (status="placeholder", never presented as real).
    
    return {
        "transcribed_text": "النص المقترح من الصوت (خاصية قيد التطوير)",
        "confidence": 0.95,
        "language": body.language,
        "status": "placeholder"
    }

@app.post("/teachers/assistant")
async def teacher_assistant(body:GenerateRequest,authorization:str=Header("")):
    """AI Assistant for teachers"""
    c=await auth(authorization)
    if c["role"] not in {"teacher","admin","institution_manager"}: raise HTTPException(403,"teacher role required")
    
    prompt = f"""
    أنت مساعد ذكي للمعلمين. طلب المعلم: {body.prompt}
    
    السياق: {body.context}
    
    قدم مساعدة عملية ومفيدة للمعلم.
    """
    
    response = await ai_provider.generate(prompt, {
        "system_instruction": "أنت مساعد ذكي للمعلمين. تساعدهم في إعداد الدروس، إنشاء الاختبارات، وتحليل أداء الطلاب."
    })
    
    return response.model_dump()

@app.post("/institutions/insights")
async def institution_insights(body:AnalyzeRequest,authorization:str=Header("")):
    """AI-powered institution insights"""
    c=await auth(authorization)
    if c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"admin role required")
    
    # Gather institution data
    institution_id = c.get("institution_id")
    if not institution_id:
        raise HTTPException(400, "institution_id required")
    
    institution_data = {
        "institution_id": institution_id,
        "students_count": len([u for u in store.users.values() if u.get("institution_id") == institution_id and u.get("role") == "student"]),
        "teachers_count": len([u for u in store.users.values() if u.get("institution_id") == institution_id and u.get("role") == "teacher"]),
        "profiles": [store.profiles.get(u["id"]).model_dump() for u in store.users.values() if u.get("institution_id") == institution_id and u.get("role") == "student" and u["id"] in store.profiles]
    }
    
    response = await ai_provider.analyze(institution_data)
    return response.model_dump()

# Phase 3 New Endpoints

@app.post("/students/arabic-nlp")
async def arabic_nlp(body:ArabicNLPRequest,authorization:str=Header("")):
    """Advanced Arabic NLP processing"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    
    nlp_processor = get_arabic_nlp_processor()
    
    # Process text
    target_dialect = ArabicDialect(body.target_dialect) if body.target_dialect else None
    analysis = nlp_processor.process_text(body.text, target_dialect)
    
    return analysis.to_dict()

@app.post("/students/image-analysis")
async def image_analysis(body:ImageAnalysisRequest,authorization:str=Header("")):
    """Image analysis for homework help and question understanding"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    
    image_analyzer = get_image_analyzer()
    
    # Analyze image
    image_type = ImageType(body.image_type)
    analysis = image_analyzer.analyze_image(body.image_data, image_type, body.student_id)
    
    # Store analysis in store
    store.image_analyses[analysis.id] = analysis.to_dict()
    
    return analysis.to_dict()

@app.post("/students/voice-transcribe")
async def voice_transcribe(body:VoiceTranscribeRequest,authorization:str=Header("")):
    """Voice input transcription using Phase 3 voice processor"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    
    voice_processor = get_voice_processor()
    
    # Transcribe audio
    language = VoiceLanguage(body.language)
    transcription = voice_processor.transcribe_audio(body.audio_data, language, body.student_id)
    
    # Store transcription in store
    store.voice_interactions[transcription.id] = transcription.to_dict()
    
    return transcription.to_dict()

@app.post("/learning/record-signal")
async def record_learning_signal(body:LearningSignalRequest,authorization:str=Header("")):
    """Record a learning signal for self-learning pipeline"""
    c=await auth(authorization)
    if c["sub"]!=body.student_id and c["role"] not in {"admin","institution_manager","teacher"}: raise HTTPException(403,"forbidden")
    
    from shared.self_learning import LearningSignal, LearningSignalType, SignalQuality
    
    # Create learning signal
    signal = LearningSignal(
        id=str(uuid4()),
        signal_type=LearningSignalType(body.signal_type),
        user_id=body.student_id,
        context=body.context,
        content_data=body.content_data,
        outcome=body.outcome,
        quality=SignalQuality.MEDIUM,  # Default quality
        timestamp=datetime.now(timezone.utc)
    )
    
    # Record signal
    pipeline = get_self_learning_pipeline(store)
    signal_id = pipeline.record_signal(signal)
    
    return {"signal_id": signal_id, "status": "recorded"}

@app.get("/learning/metrics")
async def get_learning_metrics(authorization:str=Header("")):
    """Get self-learning pipeline metrics"""
    c=await auth(authorization)
    if c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"admin role required")
    
    pipeline = get_self_learning_pipeline(store)
    metrics = pipeline.get_learning_metrics()
    
    return metrics

@app.get("/learning/patterns")
async def get_learning_patterns(authorization:str=Header("")):
    """Get learned patterns"""
    c=await auth(authorization)
    if c["role"] not in {"admin","institution_manager"}: raise HTTPException(403,"admin role required")
    
    pipeline = get_self_learning_pipeline(store)
    patterns = pipeline.get_active_patterns()
    
    return {"patterns": patterns}

# Phase 5 Powerful AI Chatbot Endpoints

class ChatbotStartRequest(BaseModel):
    user_id: str
    context_type: str
    topic: str
    dialect: str = "modern_standard"
    personality: str = "friendly_tutor"
    skill_codes: list = []
    user_level: float = 0.5

class ChatbotMessageRequest(BaseModel):
    conversation_id: str
    user_message: str
    additional_context: dict = {}

@app.post("/chatbot/start")
async def start_chatbot_conversation(body: ChatbotStartRequest, authorization: str = Header("")):
    """Start a new AI chatbot conversation with memory"""
    c = await auth(authorization)
    if c["sub"] != body.user_id and c["role"] not in {"admin", "institution_manager", "teacher"}:
        raise HTTPException(403, "forbidden")
    
    chatbot = get_powerful_ai_chatbot(store)
    
    conversation_id = chatbot.start_conversation(
        user_id=body.user_id,
        context_type=ConversationContext(body.context_type),
        topic=body.topic,
        dialect=body.dialect,
        personality=AIPersonality(body.personality),
        skill_codes=body.skill_codes,
        user_level=body.user_level
    )
    
    return {"conversation_id": conversation_id, "status": "conversation_started"}

@app.post("/chatbot/message")
async def send_chatbot_message(body: ChatbotMessageRequest, authorization: str = Header("")):
    """Send a message to the AI chatbot"""
    c = await auth(authorization)
    
    chatbot = get_powerful_ai_chatbot(store)
    
    response = await chatbot.send_message(
        conversation_id=body.conversation_id,
        user_message=body.user_message,
        additional_context=body.additional_context
    )
    
    return response.to_dict()

@app.get("/chatbot/conversation/{conversation_id}")
async def get_chatbot_conversation(conversation_id: str, authorization: str = Header("")):
    """Get conversation summary"""
    c = await auth(authorization)
    
    chatbot = get_powerful_ai_chatbot(store)
    summary = chatbot.get_conversation_summary(conversation_id)
    
    if not summary:
        raise HTTPException(404, "Conversation not found")
    
    return summary

@app.get("/chatbot/analytics/{user_id}")
async def get_chatbot_analytics(user_id: str, authorization: str = Header("")):
    """Get conversation analytics for a user"""
    c = await auth(authorization)
    if c["sub"] != user_id and c["role"] not in {"admin", "institution_manager", "teacher"}:
        raise HTTPException(403, "forbidden")
    
    chatbot = get_powerful_ai_chatbot(store)
    analytics = chatbot.get_conversation_analytics(user_id)
    
    return analytics

# Phase 5 Real-Time Features Endpoints

class NotificationRequest(BaseModel):
    user_id: str
    title: str
    message: str
    priority: str = "medium"

class NotificationPreferencesRequest(BaseModel):
    sound_enabled: bool = True
    push_enabled: bool = True
    email_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"

@app.post("/notifications")
async def create_notification(body: NotificationRequest, authorization: str = Header("")):
    """Create a new notification"""
    c = await auth(authorization)
    if c["role"] not in {"admin", "institution_manager", "teacher"}:
        raise HTTPException(403, "forbidden")
    
    real_time_service = get_real_time_service(store)
    
    notification_id = real_time_service.create_notification(
        user_id=body.user_id,
        title=body.title,
        message=body.message,
        priority=NotificationPriority(body.priority)
    )
    
    return {"notification_id": notification_id, "status": "notification_created"}

@app.get("/notifications/{user_id}")
async def get_notifications(user_id: str, unread_only: bool = False, authorization: str = Header(""), limit: int = 50, offset: int = 0):
    """Get notifications for a user"""
    c = await auth(authorization)
    if c["sub"] != user_id and c["role"] not in {"admin", "institution_manager", "teacher"}:
        raise HTTPException(403, "forbidden")
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    real_time_service = get_real_time_service(store)
    notifications = real_time_service.get_notifications(user_id, unread_only)[offset:offset + limit]

    return {"notifications": notifications, "limit": limit, "offset": offset}

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, authorization: str = Header("")):
    """Mark notification as read"""
    c = await auth(authorization)
    
    real_time_service = get_real_time_service(store)
    real_time_service.mark_notification_read(notification_id)
    
    return {"status": "notification_marked_read"}

@app.get("/notifications/{user_id}/unread-count")
async def get_unread_count(user_id: str, authorization: str = Header("")):
    """Get unread notification count"""
    c = await auth(authorization)
    if c["sub"] != user_id and c["role"] not in {"admin", "institution_manager", "teacher"}:
        raise HTTPException(403, "forbidden")
    
    real_time_service = get_real_time_service(store)
    count = real_time_service.get_unread_count(user_id)
    
    return {"unread_count": count}

@app.put("/notifications/{user_id}/preferences")
async def set_notification_preferences(user_id: str, body: NotificationPreferencesRequest, authorization: str = Header("")):
    """Set notification preferences"""
    c = await auth(authorization)
    if c["sub"] != user_id:
        raise HTTPException(403, "forbidden")
    
    real_time_service = get_real_time_service(store)
    real_time_service.set_notification_preferences(
        user_id=user_id,
        sound_enabled=body.sound_enabled,
        push_enabled=body.push_enabled,
        email_enabled=body.email_enabled,
        quiet_hours_start=body.quiet_hours_start,
        quiet_hours_end=body.quiet_hours_end
    )
    
    return {"status": "preferences_updated"}

@app.get("/notifications/{user_id}/preferences")
async def get_notification_preferences(user_id: str, authorization: str = Header("")):
    """Get notification preferences"""
    c = await auth(authorization)
    if c["sub"] != user_id:
        raise HTTPException(403, "forbidden")
    
    real_time_service = get_real_time_service(store)
    preferences = real_time_service.get_notification_preferences(user_id)
    
    return preferences

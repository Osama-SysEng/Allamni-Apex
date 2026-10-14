"""
Powerful AI Chatbot System for Allamni v4.0
Features AI memory, context awareness, multi-turn conversations, and advanced AI capabilities
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import hashlib
import asyncio
from .logging_utils import get_logger

_logger = get_logger("allamni-shared")

class ConversationContext(str, Enum):
    """Conversation context types"""
    LEARNING = "learning"
    HOMEWORK_HELP = "homework_help"
    EXPLANATION = "explanation"
    PRACTICE = "practice"
    ASSESSMENT = "assessment"
    GENERAL = "general"

class MessageRole(str, Enum):
    """Message roles in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@dataclass
class ConversationMessage:
    """A single message in a conversation"""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'role': self.role.value,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

@dataclass
class ConversationMemory:
    """Memory for a conversation"""
    conversation_id: str
    user_id: str
    context_type: ConversationContext
    topic: str
    skill_codes: List[str]
    user_level: float
    dialect: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    important_points: List[str] = field(default_factory=list)
    user_confusion_points: List[str] = field(default_factory=list)
    learning_goals: List[str] = field(default_factory=list)
    conversation_summary: str = ""
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_summary(self, new_message: str):
        """Update conversation summary with new message"""
        if not self.conversation_summary:
            self.conversation_summary = new_message[:200]
        else:
            # Append new content to summary
            self.conversation_summary = f"{self.conversation_summary} {new_message[:100]}"
            # Keep summary concise
            if len(self.conversation_summary) > 500:
                self.conversation_summary = self.conversation_summary[:500]
        
        self.last_updated = datetime.now(timezone.utc)

@dataclass
class ConversationThread:
    """A complete conversation thread"""
    id: str
    user_id: str
    messages: List[ConversationMessage]
    memory: ConversationMemory
    created_at: datetime
    last_activity: datetime
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, message: ConversationMessage):
        """Add message to conversation"""
        self.messages.append(message)
        self.last_activity = message.timestamp
        self.memory.update_summary(message.content)
    
    def get_context_window(self, window_size: int = 5) -> List[ConversationMessage]:
        """Get recent messages for context window"""
        return self.messages[-window_size:] if len(self.messages) > window_size else self.messages
    
    def get_conversation_history(self) -> str:
        """Get formatted conversation history for AI context"""
        history = []
        for msg in self.messages:
            role_prefix = "User: " if msg.role == MessageRole.USER else "Assistant: "
            history.append(f"{role_prefix}{msg.content}")
        return "\n".join(history)

class AIPersonality(str, Enum):
    """AI personality types"""
    FRIENDLY_TUTOR = "friendly_tutor"
    STRICT_EXAMINER = "strict_examiner"
    PATIENT_MENTOR = "patient_mentor"
    ENTHUSIASTIC_GUIDE = "enthusiastic_guide"
    PROFESSIONAL_EXPERT = "professional_expert"

@dataclass
class AIResponse:
    """AI response with metadata"""
    content: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)
    difficulty_level: Optional[str] = None
    estimated_time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'content': self.content,
            'confidence': self.confidence,
            'sources': self.sources,
            'related_topics': self.related_topics,
            'follow_up_questions': self.follow_up_questions,
            'difficulty_level': self.difficulty_level,
            'estimated_time': self.estimated_time,
            'metadata': self.metadata
        }

class PowerfulAIChatbot:
    """Powerful AI chatbot with memory and context awareness"""
    
    def __init__(self, store, ai_provider=None):
        self.store = store
        self.ai_provider = ai_provider
        
        # Initialize collections
        if not hasattr(store, 'conversation_threads'):
            store.conversation_threads = {}
        if not hasattr(store, 'conversation_memories'):
            store.conversation_memories = {}
        if not hasattr(store, 'ai_knowledge_base'):
            store.ai_knowledge_base = {}
        if not hasattr(store, 'conversation_analytics'):
            store.conversation_analytics = {
                'total_conversations': 0,
                'total_messages': 0,
                'average_turns': 0,
                'successful_resolutions': 0,
                'topics_discussed': {},
                'user_satisfaction': {}
            }
        
        # Initialize knowledge base
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize AI knowledge base with educational content"""
        self.store.ai_knowledge_base = {
            'python_basics': {
                'topics': ['variables', 'data_types', 'operators', 'control_flow'],
                'difficulty': 'beginner',
                'estimated_time': '2-3 hours',
                'prerequisites': ['computer_basics'],
                'related_topics': ['data_structures', 'algorithms']
            },
            'data_structures': {
                'topics': ['arrays', 'lists', 'dictionaries', 'sets', 'tuples'],
                'difficulty': 'intermediate',
                'estimated_time': '4-5 hours',
                'prerequisites': ['python_basics'],
                'related_topics': ['algorithms', 'complexity_analysis']
            },
            'algorithms': {
                'topics': ['sorting', 'searching', 'recursion', 'dynamic_programming'],
                'difficulty': 'advanced',
                'estimated_time': '6-8 hours',
                'prerequisites': ['data_structures'],
                'related_topics': ['complexity_analysis', 'optimization']
            },
            'oop': {
                'topics': ['classes', 'objects', 'inheritance', 'polymorphism'],
                'difficulty': 'intermediate',
                'estimated_time': '3-4 hours',
                'prerequisites': ['python_basics'],
                'related_topics': ['design_patterns', 'software_architecture']
            }
        }
    
    def start_conversation(self, user_id: str, context_type: ConversationContext, 
                          topic: str, dialect: str, personality: AIPersonality = AIPersonality.FRIENDLY_TUTOR,
                          skill_codes: List[str] = None, user_level: float = 0.5) -> str:
        """Start a new conversation thread"""
        if not user_id or not isinstance(user_id, str):
            raise ValueError("user_id must be a non-empty string")
        if not topic or not isinstance(topic, str):
            raise ValueError("topic must be a non-empty string")
        if len(topic) > 500:
            raise ValueError("topic must be at most 500 characters")
        if not isinstance(context_type, ConversationContext):
            raise ValueError(f"context_type must be a ConversationContext (got {context_type!r})")
        try:
            user_level = float(user_level)
        except (TypeError, ValueError):
            raise ValueError("user_level must be a number between 0 and 1")
        user_level = max(0.0, min(1.0, user_level))
        conversation_id = str(uuid4())

        # Create conversation memory
        memory = ConversationMemory(
            conversation_id=conversation_id,
            user_id=user_id,
            context_type=context_type,
            topic=topic,
            skill_codes=skill_codes or [],
            user_level=user_level,
            dialect=dialect,
            preferences={'personality': personality.value}
        )
        
        # Create conversation thread
        thread = ConversationThread(
            id=conversation_id,
            user_id=user_id,
            messages=[],
            memory=memory,
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc),
            metadata={'personality': personality.value}
        )
        
        self.store.conversation_threads[conversation_id] = thread
        self.store.conversation_memories[conversation_id] = memory
        
        # Update analytics
        self.store.conversation_analytics['total_conversations'] = self.store.conversation_analytics.get('total_conversations', 0) + 1
        
        return conversation_id
    
    async def send_message(self, conversation_id: str, user_message: str, 
                    additional_context: Dict[str, Any] = None) -> AIResponse:
        """Send user message and get AI response"""
        if not conversation_id or not isinstance(conversation_id, str):
            raise ValueError("conversation_id must be a non-empty string")
        if not user_message or not isinstance(user_message, str) or not user_message.strip():
            raise ValueError("user_message must be a non-empty string")
        if len(user_message) > 10000:
            raise ValueError("user_message must be at most 10000 characters")
        thread = self.store.conversation_threads.get(conversation_id)
        if not thread:
            return AIResponse(
                content="Conversation not found. Please start a new conversation.",
                confidence=0.0
            )
        
        # Add user message
        user_msg = ConversationMessage(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=user_message,
            timestamp=datetime.now(timezone.utc),
            metadata=additional_context or {}
        )
        thread.add_message(user_msg)
        
        # Update analytics
        self.store.conversation_analytics['total_messages'] = self.store.conversation_analytics.get('total_messages', 0) + 1
        
        # Generate AI response
        response = await self._generate_ai_response(thread, user_message)
        
        # Add assistant message
        assistant_msg = ConversationMessage(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            timestamp=datetime.now(timezone.utc),
            metadata={
                'confidence': response.confidence,
                'sources': response.sources,
                'difficulty_level': response.difficulty_level
            }
        )
        thread.add_message(assistant_msg)
        
        # Update conversation memory
        self._update_conversation_memory(thread, user_message, response)
        
        return response
    
    async def _generate_ai_response(self, thread: ConversationThread, user_message: str) -> AIResponse:
        """Generate AI response based on context and memory"""
        # Get conversation context
        context_window = thread.get_context_window()
        conversation_history = thread.get_conversation_history()
        
        # Get relevant knowledge
        relevant_knowledge = self._get_relevant_knowledge(thread.memory.topic, thread.memory.skill_codes)
        
        # Build system prompt based on personality
        personality = thread.metadata.get('personality', AIPersonality.FRIENDLY_TUTOR.value)
        system_prompt = self._build_system_prompt(personality, thread.memory.dialect)
        
        # Build full context for AI
        full_context = {
            'system_instruction': system_prompt,
            'conversation_history': conversation_history,
            'user_level': thread.memory.user_level,
            'current_topic': thread.memory.topic,
            'dialect': thread.memory.dialect,
            'knowledge_base': relevant_knowledge,
            'user_confusion_points': thread.memory.user_confusion_points,
            'learning_goals': thread.memory.learning_goals,
            'context_type': thread.memory.context_type.value
        }
        
        # Build messages for AI (use provider-native message type, not the
        # local ConversationMessage, so role comparison stays exact).
        from shared.ai_providers import AIMessage as ProviderAIMessage
        from shared.ai_providers import MessageRole as ProviderRole
        _ROLE_MAP = {
            MessageRole.USER: ProviderRole.USER,
            MessageRole.ASSISTANT: ProviderRole.ASSISTANT,
            MessageRole.SYSTEM: ProviderRole.SYSTEM,
        }
        messages = [ProviderAIMessage(role=ProviderRole.SYSTEM, content=system_prompt)]

        # Add conversation history (formatted string) as context
        if conversation_history:
            messages.append(ProviderAIMessage(
                role=ProviderRole.SYSTEM,
                content=f"Conversation so far:\n{conversation_history}",
            ))

        # Add current message
        messages.append(ProviderAIMessage(role=ProviderRole.USER, content=user_message))
        
        # Get real AI response
        try:
            from shared.ai_providers import get_ai_provider, AIProviderType
            import os
            
            provider = get_ai_provider(
                provider_type=AIProviderType(os.getenv("AI_PROVIDER", "gemini")),
                api_key=os.getenv("GEMINI_API_KEY"),
                model=os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
            )
            
            ai_response = await provider.chat(messages, full_context)
            response_content = ai_response.content
            confidence = 0.9  # High confidence for real AI
        except Exception as e:
            # Rule-based fallback when the live provider is unreachable/misconfigured.
            _logger.warning(f"AI provider error: {e}. Using fallback response.")
            response_content = self._generate_mock_response(thread, user_message, full_context)
            confidence = 0.7
        
        # Create AI response object
        response = AIResponse(
            content=response_content,
            confidence=confidence,
            sources=self._extract_sources(relevant_knowledge),
            related_topics=self._extract_related_topics(thread.memory.topic),
            follow_up_questions=self._generate_follow_up_questions(thread.memory.topic),
            difficulty_level=relevant_knowledge.get('difficulty'),
            estimated_time=relevant_knowledge.get('estimated_time')
        )
        
        return response
    
    def _build_system_prompt(self, personality: str, dialect: str) -> str:
        """Build system prompt based on personality and dialect"""
        personality_prompts = {
            'friendly_tutor': f"أنت معلم ذكي وودود يتحدث اللهجة {dialect}. شجع الطالب وقدم شرحاً مبسطاً.",
            'strict_examiner': f"أنت معلم دقيق يتحدث اللهجة {dialect}. ركز على الدقة والمفاهيم الأساسية.",
            'patient_mentor': f"أنت معلم صبور يتحدث اللهجة {dialect}. اشرح ببطء وبشكل مفصل.",
            'enthusiastic_guide': f"أنت معلم متحمس يتحدث اللهجة {dialect}. استخدم طاقة إيجابية للتشجيع.",
            'professional_expert': f"أنت خبير محترف يتحدث اللهجة {dialect}. قدم معلومات دقيقة ومهنية."
        }
        
        base_prompt = personality_prompts.get(personality, personality_prompts['friendly_tutor'])
        
        return f"{base_prompt} \n\nأنت مصمم لمنصة Allamni التعليمية. تهدفك مساعدة الطلاب على فهم البرمجة والعلوم بشكل فعال وممتع."
    
    def _get_relevant_knowledge(self, topic: str, skill_codes: List[str]) -> Dict[str, Any]:
        """Get relevant knowledge from knowledge base"""
        # Simple keyword matching (in production would use semantic search)
        relevant_knowledge = {}
        
        for key, value in self.store.ai_knowledge_base.items():
            if topic.lower() in key.lower() or any(skill.lower() in key.lower() for skill in skill_codes):
                relevant_knowledge.update(value)
        
        return relevant_knowledge
    
    def _generate_mock_response(self, thread: ConversationThread, user_message: str, 
                               context: Dict[str, Any]) -> str:
        """Generate enhanced mock response based on context"""
        topic = context.get('current_topic', 'general')
        dialect = context.get('dialect', 'modern_standard')
        user_level = context.get('user_level', 0.5)
        
        # Analyze user message for intent
        user_message_lower = user_message.lower()
        
        if any(word in user_message_lower for word in ['شرح', 'ما هو', 'فهم', 'تعلم']):
            return self._generate_explanation(topic, user_level, dialect)
        elif any(word in user_message_lower for word in ['ساعد', 'حل', 'مشكلة', 'خطأ']):
            return self._generate_help_response(topic, user_message, dialect)
        elif any(word in user_message_lower for word in ['مثال', 'تدريب', 'تمرين']):
            return self._generate_practice_response(topic, dialect)
        elif any(word in user_message_lower for word in ['امتحان', 'اختبار', 'تقييم']):
            return self._generate_assessment_response(topic, dialect)
        else:
            return self._generate_general_response(topic, user_message, dialect)
    
    def _generate_explanation(self, topic: str, user_level: float, dialect: str) -> str:
        """Generate explanation response"""
        explanations = {
            'python_basics': f"المتغيرات في بايثون مثل الصناديق التي تخزن البيانات. يمكنك تخزين أنواع مختلفة من البيانات مثل الأرقام والنصوص. المستوى الحالي: {user_level:.1f}",
            'data_structures': f"القوائم في بايثون تجمع عناصر متعددة ويمكنك إضافة وإزالة العناصر بسهولة. مفيدة لتخزين مجموعات من البيانات.",
            'algorithms': f"الخوارزميات هي خطوات منظمة لحل المشكلات. مثال: خوارزمية البحث تبحث عن عنصر في مجموعة بيانات.",
            'oop': f"البرمجة الكائنية تحول البرمجة إلى علاقات بين كائنات. الكلاس هو تعريف، والكائن هو مثيل حقيقي للكلاس."
        }
        
        return explanations.get(topic, f"سأشرح لك {topic} بطريقة مبسطة ومفهومة. {topic} مفهوم مهم في البرمجة.")
    
    def _generate_help_response(self, topic: str, user_message: str, dialect: str) -> str:
        """Generate help response"""
        return f"أنا هنا لمساعدتك في {topic}. كيف يمكنني مساعدتك بشكل محدد؟ هل تواجه مشكلة معينة أو تريد مثالاً عملياً؟"
    
    def _generate_practice_response(self, topic: str, dialect: str) -> str:
        """Generate practice response"""
        return f"ممتاز! التدريب هو أفضل طريقة لتعلم {topic}. دعني أعطيك مثالاً تدريبياً. اكتب برنامج بسيط يستخدم المفاهيم التي تعلمناها."
    
    def _generate_assessment_response(self, topic: str, dialect: str) -> str:
        """Generate assessment response"""
        return f"التقييم مهم لقياس فهمك لـ {topic}. دعني أقترح عليك سؤالاً اختبارياً لتقياس مستواك."
    
    def _generate_general_response(self, topic: str, user_message: str, dialect: str) -> str:
        """Generate general response"""
        return f"شكراً على رسالتك حول {topic}. كيف يمكنني مساعدتك بشكل أفضل؟ هل تريد شرحاً مفصلاً، أمثالاً، أم حل مشكلة محددة؟"
    
    def _extract_sources(self, knowledge: Dict[str, Any]) -> List[str]:
        """Extract sources from knowledge"""
        sources = []
        if 'prerequisites' in knowledge:
            sources.extend(knowledge['prerequisites'])
        if 'related_topics' in knowledge:
            sources.extend(knowledge['related_topics'])
        return sources
    
    def _extract_related_topics(self, topic: str) -> List[str]:
        """Extract related topics"""
        knowledge = self.store.ai_knowledge_base.get(topic, {})
        return knowledge.get('related_topics', [])
    
    def _generate_follow_up_questions(self, topic: str) -> List[str]:
        """Generate follow-up questions"""
        questions = {
            'python_basics': [
                "هل تريد معرفة المزيد عن أنواع البيانات؟",
                "هل تريد مثالاً عملياً على المتغيرات؟",
                "هل هناك مفهوم محدد تريد توضيحه؟"
            ],
            'data_structures': [
                "هل تريد معرفة المزيد عن القوائم؟",
                "هل تريد فهم الفرق بين القوائم والمجموعات؟",
                "هل تريد مثالاً عملياً؟"
            ],
            'algorithms': [
                "هل تريد معرفة المزيد عن أنواع الخوارزميات؟",
                "هل تريد شرحاً تفصيلياً لخوارزمية محددة؟",
                "هل تريد مقارنة بين خوارزميات مختلفة؟"
            ],
            'oop': [
                "هل تريد معرفة المزيد عن الوراثة؟",
                "هل تريد مثالاً عملياً على الكلاسات؟",
                "هل تريد فهم الفرق بين الكلاس والكائن؟"
            ]
        }
        
        return questions.get(topic, [
            "هل تريد معرفة المزيد؟",
            "هل تريد مثالاً عملياً؟",
            "هل هناك جانب آخر تريد استكشافه؟"
        ])
    
    def _update_conversation_memory(self, thread: ConversationThread, user_message: str, 
                                  ai_response: AIResponse):
        """Update conversation memory based on interaction"""
        memory = thread.memory
        
        # Detect confusion from user message
        confusion_keywords = ['لا أفهم', 'غير واضح', 'مشكلة', 'صعب', 'معقد']
        if any(keyword in user_message.lower() for keyword in confusion_keywords):
            memory.user_confusion_points.append(user_message)
        
        # Extract learning goals from user message
        goal_keywords = ['أريد تعلم', 'أريد فهم', 'أريد معرفة', 'أريد اتقان']
        if any(keyword in user_message.lower() for keyword in goal_keywords):
            memory.learning_goals.append(user_message)
        
        # Store important points from AI response
        if ai_response.sources:
            memory.important_points.extend(ai_response.sources)
    
    def get_conversation_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get conversation analytics for a user"""
        user_threads = [
            thread for thread in self.store.conversation_threads.values()
            if thread.user_id == user_id
        ]
        
        if not user_threads:
            return {}
        
        total_messages = sum(len(thread.messages) for thread in user_threads)
        average_turns = total_messages / len(user_threads) if user_threads else 0
        
        return {
            'total_conversations': len(user_threads),
            'total_messages': total_messages,
            'average_turns_per_conversation': round(average_turns, 2),
            'active_conversations': len([t for t in user_threads if t.is_active]),
            'topics_discussed': list(set(t.memory.topic for t in user_threads))
        }
    
    def get_conversation_summary(self, conversation_id: str) -> Optional[Dict]:
        """Get summary of a conversation"""
        thread = self.store.conversation_threads.get(conversation_id)
        if not thread:
            return None
        
        return {
            'conversation_id': conversation_id,
            'user_id': thread.user_id,
            'topic': thread.memory.topic,
            'context_type': thread.memory.context_type.value,
            'message_count': len(thread.messages),
            'created_at': thread.created_at.isoformat(),
            'last_activity': thread.last_activity.isoformat(),
            'summary': thread.memory.conversation_summary,
            'learning_goals': thread.memory.learning_goals,
            'confusion_points': thread.memory.user_confusion_points,
            'important_points': thread.memory.important_points
        }
    
    def end_conversation(self, conversation_id: str) -> bool:
        """End a conversation thread"""
        thread = self.store.conversation_threads.get(conversation_id)
        if not thread:
            return False
        
        thread.is_active = False
        return True

# Factory function
def get_powerful_ai_chatbot(store, ai_provider=None) -> PowerfulAIChatbot:
    """Get or create powerful AI chatbot instance"""
    if not hasattr(store, 'powerful_ai_chatbot') or store.powerful_ai_chatbot is None:
        store.powerful_ai_chatbot = PowerfulAIChatbot(store, ai_provider)
    return store.powerful_ai_chatbot
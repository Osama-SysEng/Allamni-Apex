"""
Advanced Arabic NLP Processing for Allamni v4.0
Handles Arabic dialect detection, text processing, and language-specific features
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import re
from datetime import datetime, timezone
import json
import os
from .logging_utils import get_logger

_logger = get_logger("allamni-shared")

class ArabicDialect(str, Enum):
    """Arabic dialects supported by the system"""
    MODERN_STANDARD = "modern_standard"  # الفصحى الحديثة
    EGYPTIAN = "egyptian"               # مصرية
    GULF = "gulf"                       # خليجية
    LEVANTINE = "levantine"             # شامية
    MAGHREBI = "maghrebi"               # مغاربية
    IRAQI = "iraqi"                     # عراقية

class TextComplexity(str, Enum):
    """Complexity levels for Arabic text"""
    SIMPLE = "simple"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

@dataclass
class ArabicTextAnalysis:
    """Analysis result for Arabic text"""
    original_text: str
    detected_dialect: ArabicDialect
    confidence: float
    complexity: TextComplexity
    key_terms: List[str]
    grammatical_features: Dict[str, Any]
    sentiment: str  # positive, negative, neutral
    suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'original_text': self.original_text,
            'detected_dialect': self.detected_dialect.value,
            'confidence': self.confidence,
            'complexity': self.complexity.value,
            'key_terms': self.key_terms,
            'grammatical_features': self.grammatical_features,
            'sentiment': self.sentiment,
            'suggestions': self.suggestions
        }

class ArabicNLPProcessor:
    """Advanced Arabic NLP processing"""
    
    # Dialect-specific markers (simplified for demo)
    DIALECT_MARKERS = {
        ArabicDialect.EGYPTIAN: [
            r'\b(?:مش|ده|بتاع|يا معلم|يا ريس|بص\b)',
            r'\b(?:هو\b|هي\b|هم\b)',  # Pronouns
            r'\b(?:عشان|بسب\b)',  # Conjunctions
        ],
        ArabicDialect.GULF: [
            r'\b(?:خيو|أخوي|غالي|سوالف|يا شباب\b)',
            r'\b(?:ألله|ياب\b)',  # Expressions
        ],
        ArabicDialect.LEVANTINE: [
            r'\b(?:كيفك|شلون|مارحب|يا رفيق\b)',
            r'\b(?:أدي|شو\b)',  # Particles
        ],
        ArabicDialect.MAGHREBI: [
            r'\b(?:واش|براڤي|زيونة|بغيت\b)',
            r'\b(?:شنو|اش\b)',  # Question words
        ],
        ArabicDialect.IRAQI: [
            r'\b(?:أجي|شبي|مكتوب|ماكو\b)',
            r'\b(?:دش\b)',  # Negative particle
        ],
    }
    
    def __init__(self):
        # Initialize any required models or resources
        self._init_dialect_classifier()
        self._init_complexity_analyzer()
    
    def _init_dialect_classifier(self):
        """Initialize dialect classification model"""
        # Rule-based classifier (regex markers in DIALECT_MARKERS).
        # A trained ML model can replace this in production without changing callers.
        self._dialect_classifier_ready = True

    def _init_complexity_analyzer(self):
        """Initialize text complexity analyzer"""
        # Heuristic analyzer (word/sentence statistics in analyze_complexity).
        self._complexity_analyzer_ready = True

    def detect_dialect(self, text: str) -> Tuple[ArabicDialect, float]:
        """Detect Arabic dialect from text"""
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        text_lower = text.lower()
        
        dialect_scores = {}
        
        for dialect, markers in self.DIALECT_MARKERS.items():
            score = 0
            matches = 0
            for pattern in markers:
                found = re.findall(pattern, text_lower)
                if found:
                    matches += len(found)
                    score += len(found) * 2  # Weight matches
            
            if matches > 0:
                dialect_scores[dialect] = score
        
        if not dialect_scores:
            # Default to modern standard if no dialect markers found
            return ArabicDialect.MODERN_STANDARD, 0.5
        
        # Return dialect with highest score
        best_dialect = max(dialect_scores.items(), key=lambda x: x[1])
        confidence = min(1.0, best_dialect[1] / 10.0)  # Normalize confidence
        
        return best_dialect[0], confidence
    
    def analyze_complexity(self, text: str) -> TextComplexity:
        """Analyze text complexity"""
        # Simple heuristic-based complexity analysis
        text_length = len(text)
        words = text.split()
        word_count = len(words)
        
        # Average word length
        avg_word_length = sum(len(word) for word in words) / word_count if words else 0
        
        # Sentence count (simplified)
        sentences = text.split('.')
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Calculate complexity score
        complexity_score = 0
        
        if avg_word_length > 5:
            complexity_score += 1
        if sentence_count > 3:
            complexity_score += 1
        if text_length > 100:
            complexity_score += 1
        
        # Determine complexity level
        if complexity_score <= 1:
            return TextComplexity.SIMPLE
        elif complexity_score == 2:
            return TextComplexity.INTERMEDIATE
        else:
            return TextComplexity.ADVANCED
    
    def extract_key_terms(self, text: str, dialect: ArabicDialect) -> List[str]:
        """Extract key terms from Arabic text"""
        # Simplified key term extraction
        # In production, would use named entity recognition
        
        # Common Arabic educational terms
        educational_terms = [
            'درس', 'معلوم', 'تعلم', 'فهم', 'امتحان', 'واجب',
            'طالب', 'معلم', 'مدرسة', 'جامعة', 'شهادة',
            'برمجة', 'رياضيات', 'علوم', 'لغة', 'تاريخ'
        ]
        
        found_terms = []
        for term in educational_terms:
            if term in text:
                found_terms.append(term)
        
        return found_terms
    
    def analyze_grammar(self, text: str) -> Dict[str, Any]:
        """Analyze grammatical features"""
        # Simplified grammatical analysis
        analysis = {
            'has_hamza': 'ء' in text,
            'has_taa_marbuta': 'ة' in text,
            'has_alif_maqsura': 'ى' in text,
            'has_shadda': any(c in text for c in 'ًٌٍّ'),
            'has_tanween': any(c in text for c in 'ًٌٍ'),
            'sentence_count': len([s for s in text.split('.') if s.strip()]),
            'word_count': len(text.split())
        }
        return analysis
    
    def detect_sentiment(self, text: str) -> str:
        """Detect sentiment of Arabic text"""
        # Simplified sentiment analysis
        positive_words = ['ممتاز', 'رائع', 'جيد', 'جميل', 'مفيد', 'سهل', 'فهمت']
        negative_words = ['صعب', 'معقد', 'لم أفهم', 'غير واضح', 'معقد']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def generate_suggestions(self, text: str, analysis: ArabicTextAnalysis) -> List[str]:
        """Generate improvement suggestions for text"""
        suggestions = []
        
        # Complexity-based suggestions
        if analysis.complexity == TextComplexity.ADVANCED:
            suggestions.append("Consider simplifying the text for better comprehension")
        
        # Dialect-specific suggestions
        if analysis.detected_dialect != ArabicDialect.MODERN_STANDARD:
            suggestions.append(f"Text uses {analysis.detected_dialect.value} dialect - ensure target audience understands")
        
        # Length-based suggestions
        if len(text) > 500:
            suggestions.append("Consider breaking into smaller sections for better readability")
        
        # Sentiment-based suggestions
        if analysis.sentiment == 'negative':
            suggestions.append("Text may have negative tone - consider more encouraging language")
        
        return suggestions
    
    def process_text(self, text: str, target_dialect: Optional[ArabicDialect] = None) -> ArabicTextAnalysis:
        """Complete Arabic text processing pipeline"""
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        # Detect dialect
        detected_dialect, confidence = self.detect_dialect(text)
        
        # If target dialect specified, use it
        final_dialect = target_dialect if target_dialect else detected_dialect
        
        # Analyze complexity
        complexity = self.analyze_complexity(text)
        
        # Extract key terms
        key_terms = self.extract_key_terms(text, final_dialect)
        
        # Analyze grammar
        grammatical_features = self.analyze_grammar(text)
        
        # Detect sentiment
        sentiment = self.detect_sentiment(text)
        
        # Create analysis object
        analysis = ArabicTextAnalysis(
            original_text=text,
            detected_dialect=final_dialect,
            confidence=confidence,
            complexity=complexity,
            key_terms=key_terms,
            grammatical_features=grammatical_features,
            sentiment=sentiment
        )
        
        # Generate suggestions
        analysis.suggestions = self.generate_suggestions(text, analysis)
        
        return analysis
    
    def adapt_to_dialect(self, text: str, target_dialect: ArabicDialect) -> str:
        """Adapt text to target Arabic dialect (rule-based tag; full translation needs an ML model + user content)."""
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        adapted_text = text
        
        # Add note about dialect adaptation
        if target_dialect != ArabicDialect.MODERN_STANDARD:
            adapted_text = f"[Translated to {target_dialect.value}] {text}"
        
        return adapted_text
    
    def tokenize_arabic(self, text: str) -> List[str]:
        """Tokenize Arabic text"""
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        # Simplified Arabic tokenization
        # In production, would use proper Arabic tokenizer
        
        # Remove punctuation and split
        cleaned = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', text)
        tokens = [token for token in cleaned.split() if token.strip()]
        
        return tokens
    
    def get_reading_time(self, text: str, reading_speed: int = 200) -> int:
        """Estimate reading time in seconds"""
        if not text or not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        if not isinstance(reading_speed, int) or reading_speed <= 0:
            raise ValueError("reading_speed must be a positive integer (words per minute)")
        reading_speed = max(50, min(reading_speed, 1000))
        word_count = len(text.split())
        return max(1, (word_count * 60) // reading_speed)  # Convert to seconds

# Factory function
def get_arabic_nlp_processor() -> ArabicNLPProcessor:
    """Get Arabic NLP processor instance"""
    return ArabicNLPProcessor()


async def process_arabic_input(text: str, dialect: ArabicDialect = None) -> dict:
    """Process Arabic input with real dialect detection using Gemini"""
    from shared.ai_providers import get_ai_provider, AIProviderType

    if not text or not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    
    provider = get_ai_provider(
        provider_type=AIProviderType.GEMINI,
        api_key=os.getenv("GEMINI_API_KEY"),
        model="gemini-1.5-flash"  # Flash for fast dialect detection
    )
    
    prompt = f"""
Analyze this Arabic text and respond in JSON format:
Text: "{text}"

Return JSON with these exact keys:
- dialect: (egyptian/gulf/levantine/maghrebi/iraqi/modern_standard)
- intent: (question/request/greeting/complaint/other)
- sentiment: (positive/negative/neutral)
- cleaned_text: normalized Arabic text
- language_confidence: (0.0 to 1.0)
- key_terms: list of important terms found
- complexity: (simple/intermediate/advanced)
"""
    
    try:
        response = await provider.generate(prompt)
        result = json.loads(response.content)
        return result
    except Exception as e:
        # Fallback to rule-based processing if AI fails
        _logger.warning(f"AI dialect detection failed: {e}. Using rule-based fallback.")
        processor = get_arabic_nlp_processor()
        analysis = processor.process_text(text, dialect)
        return {
            'dialect': analysis.detected_dialect.value,
            'intent': 'other',
            'sentiment': analysis.sentiment,
            'cleaned_text': text,
            'language_confidence': analysis.confidence,
            'key_terms': analysis.key_terms,
            'complexity': analysis.complexity.value
        }
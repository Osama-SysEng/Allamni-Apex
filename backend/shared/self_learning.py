"""
Self-Learning Pipeline for Allamni v4.0
Implements federated learning and continuous improvement for AI models
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import hashlib
from collections import Counter
from .logging_utils import get_logger

_logger = get_logger("allamni-shared")

class LearningSignalType(str, Enum):
    """Types of learning signals from user interactions"""
    EXPLANATION_SUCCESS = "explanation_success"
    EXPLANATION_FAILURE = "explanation_failure"
    CONTENT_PREFERENCE = "content_preference"
    QUESTION_PATTERN = "question_pattern"
    MISCONCEPTION_DETECTED = "misconception_detected"
    ENGAGEMENT_SIGNAL = "engagement_signal"
    DIFFICULTY_FEEDBACK = "difficulty_feedback"

class SignalQuality(str, Enum):
    """Quality assessment of learning signals"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SPAM = "spam"

@dataclass
class LearningSignal:
    """A single learning signal from user interaction"""
    id: str
    signal_type: LearningSignalType
    user_id: str
    context: Dict[str, Any]
    content_data: Dict[str, Any]
    outcome: str  # success, failure, neutral
    quality: SignalQuality
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'signal_type': self.signal_type.value,
            'user_id': self.user_id,
            'context': self.context,
            'content_data': self.content_data,
            'outcome': self.outcome,
            'quality': self.quality.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }

@dataclass
class LearningPattern:
    """A learned pattern from aggregated signals"""
    id: str
    pattern_type: str
    pattern_data: Dict[str, Any]
    confidence: float
    frequency: int
    last_updated: datetime
    is_active: bool = True
    teacher_validated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelUpdate:
    """A proposed model update based on learning"""
    id: str
    update_type: str
    changes: Dict[str, Any]
    confidence: float
    priority: str  # high, medium, low
    requires_validation: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, approved, rejected, deployed

class SelfLearningPipeline:
    """Main pipeline for self-learning and continuous improvement"""
    
    def __init__(self, store):
        self.store = store
        # Initialize learning collections if not exist
        if not hasattr(store, 'learning_signals'):
            store.learning_signals = {}
        if not hasattr(store, 'learning_patterns'):
            store.learning_patterns = {}
        if not hasattr(store, 'model_updates'):
            store.model_updates = {}
        if not hasattr(store, 'learning_metrics'):
            store.learning_metrics = {
                'total_signals': 0,
                'successful_explanations': 0,
                'failed_explanations': 0,
                'patterns_learned': 0,
                'models_deployed': 0,
                'last_update': None
            }
        # Ensure metrics exist even if attribute exists
        if not isinstance(store.learning_metrics, dict):
            store.learning_metrics = {
                'total_signals': 0,
                'successful_explanations': 0,
                'failed_explanations': 0,
                'patterns_learned': 0,
                'models_deployed': 0,
                'last_update': None
            }
    
    def record_signal(self, signal: LearningSignal) -> str:
        """Record a learning signal from user interaction"""
        # Store signal
        self.store.learning_signals[signal.id] = signal
        
        # Update metrics
        if 'total_signals' not in self.store.learning_metrics:
            self.store.learning_metrics['total_signals'] = 0
        self.store.learning_metrics['total_signals'] += 1
        
        if signal.signal_type == LearningSignalType.EXPLANATION_SUCCESS:
            if 'successful_explanations' not in self.store.learning_metrics:
                self.store.learning_metrics['successful_explanations'] = 0
            self.store.learning_metrics['successful_explanations'] += 1
        elif signal.signal_type == LearningSignalType.EXPLANATION_FAILURE:
            if 'failed_explanations' not in self.store.learning_metrics:
                self.store.learning_metrics['failed_explanations'] = 0
            self.store.learning_metrics['failed_explanations'] += 1
        
        self.store.learning_metrics['last_update'] = datetime.now(timezone.utc).isoformat()
        
        return signal.id
    
    def analyze_signals(self, min_quality: SignalQuality = SignalQuality.MEDIUM) -> List[Dict]:
        """Analyze recent signals to identify patterns"""
        # Filter signals by quality and recency
        recent_signals = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)  # Last 7 days
        
        for signal in self.store.learning_signals.values():
            if signal.quality.value in [min_quality.value, "high"] and signal.timestamp > cutoff_time:
                recent_signals.append(signal.to_dict())
        
        # Group by signal type
        grouped = {}
        for signal in recent_signals:
            signal_type = signal['signal_type']
            if signal_type not in grouped:
                grouped[signal_type] = []
            grouped[signal_type].append(signal)
        
        # Analyze patterns
        patterns = []
        for signal_type, signals in grouped.items():
            if len(signals) >= 5:  # Minimum threshold for pattern detection
                success_rate = len([s for s in signals if s['outcome'] == 'success']) / len(signals)
                
                # Extract common features
                common_contexts = self._extract_common_features(signals)
                
                pattern = {
                    'pattern_type': signal_type,
                    'frequency': len(signals),
                    'success_rate': round(success_rate, 3),
                    'common_contexts': common_contexts,
                    'confidence': min(1.0, len(signals) / 20.0),  # More signals = higher confidence
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                patterns.append(pattern)
        
        return patterns
    
    def _extract_common_features(self, signals: List[Dict]) -> Dict[str, Any]:
        """Extract common features from a group of signals"""
        if not signals:
            return {}
        
        # Find common context keys
        all_contexts = [s.get('context', {}) for s in signals]
        common_features = {}
        
        # For each context key, find most common value
        for key in all_contexts[0].keys():
            values = [ctx.get(key) for ctx in all_contexts if key in ctx]
            if values:
                most_common = Counter(values).most_common(1)[0]
                if values.count(most_common) / len(values) > 0.5:  # >50% occurrence
                    common_features[key] = most_common
        
        return common_features
    
    def create_pattern(self, pattern_data: Dict) -> str:
        """Create a new learning pattern"""
        pattern_id = str(uuid4())
        
        pattern = LearningPattern(
            id=pattern_id,
            pattern_type=pattern_data['pattern_type'],
            pattern_data=pattern_data,
            confidence=pattern_data.get('confidence', 0.5),
            frequency=pattern_data.get('frequency', 1),
            last_updated=datetime.now(timezone.utc),
            is_active=True,
            teacher_validated=False
        )
        
        self.store.learning_patterns[pattern_id] = pattern
        
        if 'patterns_learned' not in self.store.learning_metrics:
            self.store.learning_metrics['patterns_learned'] = 0
        self.store.learning_metrics['patterns_learned'] += 1
        
        return pattern_id
    
    def propose_model_update(self, patterns: List[Dict]) -> str:
        """Propose a model update based on learned patterns"""
        update_id = str(uuid4())
        
        # Aggregate changes from patterns
        changes = {}
        priority = "low"
        
        for pattern in patterns:
            pattern_type = pattern['pattern_type']
            success_rate = pattern['success_rate']
            
            if success_rate < 0.3:
                # Low success rate suggests need for improvement
                priority = "high"
                changes[f'improve_{pattern_type}'] = {
                    'current_success_rate': success_rate,
                    'target_success_rate': 0.7,
                    'confidence': pattern['confidence']
                }
            elif success_rate > 0.8:
                # High success rate suggests good practice
                changes[f'reinforce_{pattern_type}'] = {
                    'current_success_rate': success_rate,
                    'confidence': pattern['confidence']
                }
        
        if not changes:
            return None
        
        # Calculate overall confidence
        avg_confidence = sum(p.get('confidence', 0.5) for p in patterns) / len(patterns)
        
        update = ModelUpdate(
            id=update_id,
            update_type="pattern_based",
            changes=changes,
            confidence=avg_confidence,
            priority=priority,
            requires_validation=True,
            status="pending"
        )
        
        self.store.model_updates[update_id] = update
        
        return update_id
    
    def validate_update(self, update_id: str, approved: bool, validator_id: str) -> bool:
        """Validate or reject a proposed model update"""
        if update_id not in self.store.model_updates:
            return False
        
        update = self.store.model_updates[update_id]
        
        if approved:
            update.status = "approved"
            # In production, this would trigger actual model deployment
            self._deploy_update(update)
        else:
            update.status = "rejected"
        
        update.metadata['validated_by'] = validator_id
        update.metadata['validated_at'] = datetime.now(timezone.utc).isoformat()
        
        return True
    
    def _deploy_update(self, update: ModelUpdate):
        """Deploy a validated update (simplified for demo)"""
        # In production, this would:
        # 1. Backup current model
        # 2. Apply changes to model
        # 3. Run validation tests
        # 4. Deploy to staging
        # 5. Monitor performance
        # 6. Rollback if issues detected
        
        update.status = "deployed"
        self.store.learning_metrics['models_deployed'] += 1
        
        # Log deployment
        _logger.info(f"Deployed model update {update.id} with confidence {update.confidence}")
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """Get current learning metrics"""
        return self.store.learning_metrics.copy()
    
    def get_active_patterns(self) -> List[Dict]:
        """Get all active learning patterns"""
        patterns = []
        for pattern in self.store.learning_patterns.values():
            if pattern.is_active:
                patterns.append({
                    'id': pattern.id,
                    'pattern_type': pattern.pattern_type,
                    'confidence': pattern.confidence,
                    'frequency': pattern.frequency,
                    'teacher_validated': pattern.teacher_validated,
                    'last_updated': pattern.last_updated.isoformat()
                })
        return patterns
    
    def get_pending_updates(self) -> List[Dict]:
        """Get all pending model updates requiring validation"""
        updates = []
        for update in self.store.model_updates.values():
            if update.status == "pending":
                updates.append({
                    'id': update.id,
                    'update_type': update.update_type,
                    'changes': update.changes,
                    'confidence': update.confidence,
                    'priority': update.priority,
                    'created_at': update.created_at.isoformat()
                })
        return updates

# Factory function
def get_self_learning_pipeline(store) -> SelfLearningPipeline:
    """Get or create self-learning pipeline instance"""
    if not hasattr(store, 'self_learning_pipeline') or store.self_learning_pipeline is None:
        store.self_learning_pipeline = SelfLearningPipeline(store)
    return store.self_learning_pipeline
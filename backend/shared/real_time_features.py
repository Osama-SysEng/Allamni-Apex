"""
Real-time Features for Allamni v4.0
WebSocket support, live updates, and real-time notifications
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import json
from collections import defaultdict
from .logging_utils import get_logger

_logger = get_logger("allamni-shared")

class EventType(str, Enum):
    """Real-time event types"""
    LEARNING_PROGRESS = "learning_progress"
    NEW_MESSAGE = "new_message"
    ASSIGNMENT_DUE = "assignment_due"
    NOTIFICATION = "notification"
    SYSTEM_UPDATE = "system_update"
    LIVE_SESSION = "live_session"

class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class RealTimeEvent:
    """Real-time event"""
    id: str
    event_type: EventType
    user_id: str
    data: Dict[str, Any]
    timestamp: datetime
    priority: NotificationPriority = NotificationPriority.MEDIUM
    ttl: Optional[int] = None  # Time to live in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'event_type': self.event_type.value,
            'user_id': self.user_id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority.value,
            'metadata': self.metadata
        }
    
    def is_expired(self) -> bool:
        """Check if event has expired"""
        if self.ttl is None:
            return False
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds() > self.ttl

@dataclass
class Notification:
    """User notification"""
    id: str
    user_id: str
    title: str
    body: str
    priority: NotificationPriority
    created_at: datetime
    read: bool = False
    read_at: Optional[datetime] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    icon: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'body': self.body,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'read': self.read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'action_url': self.action_url,
            'action_label': self.action_label,
            'icon': self.icon,
            'metadata': self.metadata
        }

class WebSocketConnection:
    """WebSocket connection manager"""
    def __init__(self):
        self.active_connections: Dict[str, set] = defaultdict(set)  # user_id -> connection_ids
        self.connection_subscriptions: Dict[str, set] = defaultdict(set)  # connection_id -> user_ids
        self.event_handlers: Dict[EventType, List[Callable]] = defaultdict(list)
    
    def add_connection(self, user_id: str, connection_id: str):
        """Add a new WebSocket connection"""
        self.active_connections[user_id].add(connection_id)
        self.connection_subscriptions[connection_id].add(user_id)
    
    def remove_connection(self, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.connection_subscriptions:
            for user_id in self.connection_subscriptions[connection_id]:
                self.active_connections[user_id].discard(connection_id)
            del self.connection_subscriptions[connection_id]
    
    def get_user_connections(self, user_id: str) -> set:
        """Get all connections for a user"""
        return self.active_connections[user_id]
    
    def broadcast_to_user(self, user_id: str, event: RealTimeEvent):
        """Broadcast event to all connections of a user"""
        connections = self.get_user_connections(user_id)
        event_data = event.to_dict()
        
        for connection_id in connections:
            # In production, this would send actual WebSocket message
            _logger.debug(f"WebSocket: Broadcasting to {connection_id} for user {user_id}: {event.event_type.value}")
    
    def broadcast_to_multiple_users(self, user_ids: List[str], event: RealTimeEvent):
        """Broadcast event to multiple users"""
        for user_id in user_ids:
            self.broadcast_to_user(user_id, event)
    
    def register_event_handler(self, event_type: EventType, handler: Callable):
        """Register handler for specific event type"""
        self.event_handlers[event_type].append(handler)
    
    def trigger_event_handlers(self, event: RealTimeEvent):
        """Trigger all handlers for an event type"""
        for handler in self.event_handlers[event.event_type]:
            try:
                handler(event)
            except Exception as e:
                _logger.exception(f"Error in event handler: {e}")

class RealTimeService:
    """Real-time service for live updates and notifications"""
    
    def __init__(self, store):
        self.store = store
        self.websocket_manager = WebSocketConnection()
        
        # Initialize collections
        if not hasattr(store, 'real_time_events'):
            store.real_time_events = {}
        if not hasattr(store, 'notifications'):
            store.notifications = {}
        if not hasattr(store, 'notification_preferences'):
            store.notification_preferences = {}
        
        # Register event handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default event handlers"""
        self.websocket_manager.register_event_handler(
            EventType.LEARNING_PROGRESS,
            self._handle_learning_progress
        )
        self.websocket_manager.register_event_handler(
            EventType.NEW_MESSAGE,
            self._handle_new_message
        )
        self.websocket_manager.register_event_handler(
            EventType.ASSIGNMENT_DUE,
            self._handle_assignment_due
        )
    
    def _handle_learning_progress(self, event: RealTimeEvent):
        """Handle learning progress events"""
        # Send notification to user
        self.create_notification(
            user_id=event.user_id,
            title="تحديث التقدم",
            body=f"تقدمك في {event.data.get('topic', 'الموضوع')} قد تحسن!",
            priority=NotificationPriority.MEDIUM,
            action_url=f"/learning/{event.data.get('topic')}",
            action_label="عرض التقدم"
        )
    
    def _handle_new_message(self, event: RealTimeEvent):
        """Handle new message events"""
        self.create_notification(
            user_id=event.user_id,
            title="رسالة جديدة",
            body=event.data.get('message_preview', 'لديك رسالة جديدة'),
            priority=NotificationPriority.HIGH,
            action_url="/messages",
            action_label="عرض الرسائل"
        )
    
    def _handle_assignment_due(self, event: RealTimeEvent):
        """Handle assignment due events"""
        self.create_notification(
            user_id=event.user_id,
            title="تذكير: واجب مستحق",
            body=f"الواجب {event.data.get('assignment_name')} مستحق في {event.data.get('due_date')}",
            priority=NotificationPriority.URGENT,
            action_url=f"/assignments/{event.data.get('assignment_id')}",
            action_label="عرض الواجب"
        )
    
    def create_notification(self, user_id: str, title: str, body: str, 
                          priority: NotificationPriority = NotificationPriority.MEDIUM,
                          action_url: str = None, action_label: str = None, 
                          icon: str = None, metadata: Dict[str, Any] = None) -> str:
        """Create a notification for a user"""
        notification_id = str(uuid4())
        
        notification = Notification(
            id=notification_id,
            user_id=user_id,
            title=title,
            body=body,
            priority=priority,
            created_at=datetime.now(timezone.utc),
            action_url=action_url,
            action_label=action_label,
            icon=icon,
            metadata=metadata or {}
        )
        
        self.store.notifications[notification_id] = notification
        
        # Broadcast to user via WebSocket
        event = RealTimeEvent(
            id=str(uuid4()),
            event_type=EventType.NOTIFICATION,
            user_id=user_id,
            data={'notification_id': notification_id},
            timestamp=datetime.now(timezone.utc),
            priority=priority
        )
        
        self.websocket_manager.broadcast_to_user(user_id, event)
        
        return notification_id
    
    def mark_notification_read(self, notification_id: str, user_id: str) -> bool:
        """Mark notification as read"""
        notification = self.store.notifications.get(notification_id)
        if not notification or notification.user_id != user_id:
            return False
        
        notification.read = True
        notification.read_at = datetime.now(timezone.utc)
        
        return True
    
    def get_user_notifications(self, user_id: str, unread_only: bool = False, 
                             limit: int = 50) -> List[Dict]:
        """Get notifications for a user"""
        notifications = []
        
        for notification in self.store.notifications.values():
            if notification.user_id == user_id:
                if unread_only and notification.read:
                    continue
                notifications.append(notification.to_dict())
        
        # Sort by created_at descending
        notifications.sort(key=lambda x: x['created_at'], reverse=True)
        
        return notifications[:limit]
    
    def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count for a user"""
        return sum(1 for n in self.store.notifications.values() 
                   if n.user_id == user_id and not n.read)
    
    def set_notification_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """Set notification preferences for a user"""
        self.store.notification_preferences[user_id] = preferences
    
    def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get notification preferences for a user"""
        return self.store.notification_preferences.get(user_id, {
            'email_enabled': True,
            'push_enabled': True,
            'sound_enabled': True,
            'quiet_hours': None
        })
    
    def cleanup_old_notifications(self, days: int = 30) -> int:
        """Clean up old notifications"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        count = 0
        
        for notification_id, notification in list(self.store.notifications.items()):
            if notification.created_at < cutoff_date:
                del self.store.notifications[notification_id]
                count += 1
        
        return count
    
    def broadcast_real_time_event(self, event: RealTimeEvent):
        """Broadcast a real-time event"""
        # Store event
        self.store.real_time_events[event.id] = event
        
        # Trigger event handlers
        self.websocket_manager.trigger_event_handlers(event)
        
        # Broadcast to user
        self.websocket_manager.broadcast_to_user(event.user_id, event)
    
    def create_live_session(self, session_id: str, host_id: str, participants: List[str], 
                         topic: str) -> Dict[str, Any]:
        """Create a live session"""
        session = {
            'id': session_id,
            'host_id': host_id,
            'participants': participants,
            'topic': topic,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'is_active': True,
            'metadata': {}
        }
        
        # Store session (would be in proper database in production)
        session_key = f"live_session_{session_id}"
        self.store.real_time_events[session_key] = session
        
        # Notify participants
        for participant in participants:
            self.create_notification(
                user_id=participant,
                title="جلسة مباشرة جديدة",
                body=f"تمت دعوتك إلى جلسة مباشرة: {topic}",
                priority=NotificationPriority.HIGH,
                action_url=f"/live-sessions/{session_id}",
                action_label="انضم"
            )
        
        return session
    
    def update_live_session(self, session_id: str, update_data: Dict[str, Any]):
        """Update live session"""
        session_key = f"live_session_{session_id}"
        if session_key in self.store.real_time_events:
            session = self.store.real_time_events[session_key]
            session.update(update_data)
            
            # Broadcast update to participants
            event = RealTimeEvent(
                id=str(uuid4()),
                event_type=EventType.LIVE_SESSION,
                user_id=session['host_id'],
                data={'session_id': session_id, 'update': update_data},
                timestamp=datetime.now(timezone.utc),
                priority=NotificationPriority.MEDIUM
            )
            
            self.websocket_manager.broadcast_to_multiple_users(session['participants'], event)

# Factory function
def get_real_time_service(store) -> RealTimeService:
    """Get or create real-time service instance"""
    if not hasattr(store, 'real_time_service') or store.real_time_service is None:
        store.real_time_service = RealTimeService(store)
    return store.real_time_service
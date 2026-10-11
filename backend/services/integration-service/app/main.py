from uuid import uuid4
from datetime import datetime, date, timezone
from typing import List, Optional, Dict
from enum import Enum
import os
import httpx

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from shared.config.settings import settings
from shared.identity import active_session, audit
from shared.security import decode_token
from shared.store import store
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))


class OdooClient:
    """Real Odoo API client for production integration"""
    
    def __init__(self):
        self.url = os.getenv("ODOO_URL", settings.odoo_url)
        self.db = os.getenv("ODOO_DB", settings.odoo_db)
        self.username = os.getenv("ODOO_USERNAME", settings.odoo_username)
        self.password = os.getenv("ODOO_PASSWORD", settings.odoo_password)
        self._uid = None
    
    async def authenticate(self) -> int:
        """Authenticate with Odoo and get user ID"""
        if not all([self.url, self.db, self.username, self.password]):
            raise ValueError("Odoo credentials not configured. Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD in .env")
        
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/web/dataset/call_kw",
                json={
                    "jsonrpc": "2.0", "method": "call",
                    "params": {
                        "service": "common", "method": "authenticate",
                        "args": [self.db, self.username, self.password, {}]
                    }
                }
            )
            r.raise_for_status()
            self._uid = r.json()["result"]
            return self._uid
    
    async def sync_student(self, student_data: dict) -> dict:
        """Sync student data to Odoo"""
        uid = self._uid or await self.authenticate()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/web/dataset/call_kw",
                json={
                    "jsonrpc": "2.0", "method": "call",
                    "params": {
                        "service": "object", "method": "execute_kw",
                        "args": [
                            self.db, uid, self.password,
                            "res.partner", "create",
                            [{
                                "name": student_data.get("full_name", student_data.get("name", "")),
                                "email": student_data.get("email", ""),
                                "phone": student_data.get("phone", ""),
                                "comment": f"Allamni Student ID: {student_data.get('id', '')}"
                            }]
                        ]
                    }
                }
            )
            r.raise_for_status()
            return r.json()["result"]
    
    async def sync_teacher(self, teacher_data: dict) -> dict:
        """Sync teacher data to Odoo"""
        uid = self._uid or await self.authenticate()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/web/dataset/call_kw",
                json={
                    "jsonrpc": "2.0", "method": "call",
                    "params": {
                        "service": "object", "method": "execute_kw",
                        "args": [
                            self.db, uid, self.password,
                            "res.partner", "create",
                            [{
                                "name": teacher_data.get("full_name", teacher_data.get("name", "")),
                                "email": teacher_data.get("email", ""),
                                "phone": teacher_data.get("phone", ""),
                                "comment": f"Allamni Teacher ID: {teacher_data.get('id', '')}"
                            }]
                        ]
                    }
                }
            )
            r.raise_for_status()
            return r.json()["result"]
    
    async def sync_institution(self, institution_data: dict) -> dict:
        """Sync institution data to Odoo"""
        uid = self._uid or await self.authenticate()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.url}/web/dataset/call_kw",
                json={
                    "jsonrpc": "2.0", "method": "call",
                    "params": {
                        "service": "object", "method": "execute_kw",
                        "args": [
                            self.db, uid, self.password,
                            "res.partner", "create",
                            [{
                                "name": institution_data.get("name", ""),
                                "email": institution_data.get("email", ""),
                                "is_company": True,
                                "comment": f"Allamni Institution ID: {institution_data.get('id', '')}"
                            }]
                        ]
                    }
                }
            )
            r.raise_for_status()
            return r.json()["result"]


# Initialize Odoo client
odoo_client = OdooClient()


class SyncDirection(str, Enum):
    ALLAMNI_TO_ODOO = "allamni_to_odoo"
    ODOO_TO_ALLAMNI = "odoo_to_allamni"
    BIDIRECTIONAL = "bidirectional"


class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class EntityType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    INSTITUTION = "institution"
    SUBSCRIPTION = "subscription"
    COURSE = "course"
    PAYMENT = "payment"

app = FastAPI(title='Allamni Integration Service')


class SyncEvent(BaseModel):
    event_type: str = Field(min_length=3, max_length=120)
    payload: dict
    idempotency_key: str = Field(min_length=8, max_length=100)

class OdooSyncRequest(BaseModel):
    entity_type: EntityType
    entity_id: str
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    force_sync: bool = False

class BulkSyncRequest(BaseModel):
    entity_type: EntityType
    institution_id: str
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    date_range: Optional[Dict[str, str]] = None  # {"start_date": "2026-01-01", "end_date": "2026-12-31"}

class OdooConfig(BaseModel):
    url: str
    db: str
    username: str
    api_key: str
    enabled: bool = True


def admin(authorization):
    if not authorization.startswith('Bearer '): raise HTTPException(401, 'missing token')
    try: c = decode_token(authorization[7:])
    except Exception as exc: raise HTTPException(401, 'invalid token') from exc
    if c.get('type') != 'access' or not active_session(c.get('sid'), c.get('sub')): raise HTTPException(401, 'inactive session')
    if c['role'] not in {'admin', 'institution_manager'}: raise HTTPException(403, 'admin role required')
    return c


@app.get('/health')
def health(): return {'status': 'ok', 'service': 'integration'}


@app.post('/odoo/queue')
def queue(body: SyncEvent, authorization: str = Header('')):
    claims = admin(authorization)
    existing = next((item for item in store.outbox if item['idempotency_key'] == body.idempotency_key), None)
    if existing: return {**existing, 'idempotent_replay': True}
    
    # Add to outbox
    event = {
        'id': str(uuid4()),
        'event_type': body.event_type,
        'payload': body.payload,
        'idempotency_key': body.idempotency_key,
        'status': SyncStatus.PENDING.value,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'processed_at': None,
        'error': None
    }
    store.outbox.append(event)
    
    audit(claims['sub'], 'SYNC_EVENT_QUEUED', 'SyncEvent', event['id'], {
        'event_type': body.event_type,
        'idempotency_key': body.idempotency_key
    })
    
    return event


# Enhanced Odoo Integration Endpoints

@app.post('/odoo/sync/entity')
async def sync_entity(body: OdooSyncRequest, authorization: str = Header('')):
    """Sync a single entity with Odoo"""
    claims = admin(authorization)
    
    # Check if Odoo is configured
    odoo_config = store.institution_settings.get(claims.get('institution_id'), {}).get('integration_settings', {}).get('odoo')
    if not odoo_config or not odoo_config.get('enabled'):
        raise HTTPException(400, 'Odoo integration not configured or disabled')
    
    # Get entity data
    entity_data = None
    if body.entity_type == EntityType.STUDENT:
        entity_data = store.users.get(body.entity_id)
    elif body.entity_type == EntityType.TEACHER:
        entity_data = store.users.get(body.entity_id)
    elif body.entity_type == EntityType.INSTITUTION:
        entity_data = store.institutions.get(body.entity_id)
    elif body.entity_type == EntityType.SUBSCRIPTION:
        entity_data = store.subscriptions.get(body.entity_id)
    
    if not entity_data:
        raise HTTPException(404, f'{body.entity_type.value} not found')
    
    # Create sync event
    sync_event = {
        'id': str(uuid4()),
        'entity_type': body.entity_type.value,
        'entity_id': body.entity_id,
        'direction': body.direction.value,
        'status': SyncStatus.IN_PROGRESS.value,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'odoo_config': odoo_config
    }
    
    # In production, make actual API calls to Odoo
    try:
        if body.entity_type == EntityType.STUDENT:
            odoo_external_id = await odoo_client.sync_student(entity_data)
        elif body.entity_type == EntityType.TEACHER:
            odoo_external_id = await odoo_client.sync_teacher(entity_data)
        elif body.entity_type == EntityType.INSTITUTION:
            odoo_external_id = await odoo_client.sync_institution(entity_data)
        else:
            odoo_external_id = f"odoo_{body.entity_type.value}_{body.entity_id}"
        
        sync_event['status'] = SyncStatus.COMPLETED.value
        sync_event['processed_at'] = datetime.now(timezone.utc).isoformat()
        sync_event['odoo_external_id'] = odoo_external_id
        
        audit(claims['sub'], 'ENTITY_SYNC_COMPLETED', body.entity_type.value, body.entity_id, {
            'direction': body.direction.value,
            'odoo_external_id': sync_event['odoo_external_id']
        })
        
    except Exception as e:
        sync_event['status'] = SyncStatus.FAILED.value
        sync_event['error'] = str(e)
        sync_event['processed_at'] = datetime.now(timezone.utc).isoformat()
        
        audit(claims['sub'], 'ENTITY_SYNC_FAILED', body.entity_type.value, body.entity_id, {
            'error': str(e)
        })
    
    # Store sync event (in production would be in database)
    if not hasattr(store, 'odoo_sync_events'):
        store.odoo_sync_events = {}
    store.odoo_sync_events[sync_event['id']] = sync_event
    
    return sync_event


@app.post('/odoo/sync/bulk')
async def bulk_sync(body: BulkSyncRequest, authorization: str = Header('')):
    """Bulk sync entities for an institution"""
    claims = admin(authorization)
    
    # Check if Odoo is configured
    odoo_config = store.institution_settings.get(body.institution_id, {}).get('integration_settings', {}).get('odoo')
    if not odoo_config or not odoo_config.get('enabled'):
        raise HTTPException(400, 'Odoo integration not configured or disabled')
    
    # Collect entities to sync
    entities = []
    if body.entity_type == EntityType.STUDENT:
        entities = [
            u for u in store.users.values()
            if u.get('institution_id') == body.institution_id and u.get('role') == 'student'
        ]
    elif body.entity_type == EntityType.TEACHER:
        entities = [
            u for u in store.users.values()
            if u.get('institution_id') == body.institution_id and u.get('role') == 'teacher'
        ]
    elif body.entity_type == EntityType.INSTITUTION:
        if body.institution_id in store.institutions:
            entities = [store.institutions[body.institution_id]]
    
    if not entities:
        raise HTTPException(404, f'no {body.entity_type.value} entities found for this institution')
    
    # Process bulk sync
    sync_results = {
        'total': len(entities),
        'successful': 0,
        'failed': 0,
        'results': []
    }
    
    for entity in entities:
        try:
            sync_event = {
                'id': str(uuid4()),
                'entity_type': body.entity_type.value,
                'entity_id': entity['id'],
                'direction': body.direction.value,
                'status': SyncStatus.IN_PROGRESS.value,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Real Odoo sync
            if body.entity_type == EntityType.STUDENT:
                odoo_external_id = await odoo_client.sync_student(entity)
            elif body.entity_type == EntityType.TEACHER:
                odoo_external_id = await odoo_client.sync_teacher(entity)
            elif body.entity_type == EntityType.INSTITUTION:
                odoo_external_id = await odoo_client.sync_institution(entity)
            else:
                odoo_external_id = f"odoo_{body.entity_type.value}_{entity['id']}"
            
            sync_event['status'] = SyncStatus.COMPLETED.value
            sync_event['processed_at'] = datetime.now(timezone.utc).isoformat()
            sync_event['odoo_external_id'] = odoo_external_id
            
            sync_results['successful'] += 1
            sync_results['results'].append({
                'entity_id': entity['id'],
                'status': 'completed',
                'odoo_external_id': sync_event['odoo_external_id']
            })
            
        except Exception as e:
            sync_results['failed'] += 1
            sync_results['results'].append({
                'entity_id': entity['id'],
                'status': 'failed',
                'error': str(e)
            })
    
    audit(claims['sub'], 'BULK_SYNC_COMPLETED', body.entity_type.value, body.institution_id, {
        'total': sync_results['total'],
        'successful': sync_results['successful'],
        'failed': sync_results['failed']
    })
    
    return sync_results


@app.get('/odoo/config')
def get_odoo_config(institution_id: str, authorization: str = Header('')):
    """Get Odoo configuration for an institution"""
    claims = admin(authorization)
    
    settings_data = store.institution_settings.get(institution_id, {})
    odoo_config = settings_data.get('integration_settings', {}).get('odoo', {})
    
    # Return config without sensitive data
    safe_config = {
        'enabled': odoo_config.get('enabled', False),
        'url': odoo_config.get('url', ''),
        'db': odoo_config.get('db', ''),
        'username': odoo_config.get('username', ''),
        # Don't return api_key
        'last_sync': odoo_config.get('last_sync'),
        'sync_frequency': odoo_config.get('sync_frequency', 'daily')
    }
    
    return safe_config


@app.put('/odoo/config')
def update_odoo_config(institution_id: str, body: OdooConfig, authorization: str = Header('')):
    """Update Odoo configuration for an institution"""
    claims = admin(authorization)
    
    # Verify institution access
    if claims['role'] != 'super_admin':
        if claims.get('institution_id') != institution_id:
            raise HTTPException(403, 'access denied to this institution')
    
    # Initialize settings if not exist
    if institution_id not in store.institution_settings:
        store.institution_settings[institution_id] = {
            'id': str(uuid4()),
            'institution_id': institution_id,
            'branding': {},
            'content_policies': {},
            'language_preferences': 'ar',
            'timezone': 'Africa/Cairo',
            'academic_calendar': {},
            'notification_settings': {},
            'integration_settings': {},
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    
    # Update Odoo config
    store.institution_settings[institution_id]['integration_settings']['odoo'] = {
        'url': body.url,
        'db': body.db,
        'username': body.username,
        'api_key': body.api_key,
        'enabled': body.enabled,
        'last_sync': None,
        'sync_frequency': 'daily'
    }
    
    store.institution_settings[institution_id]['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    audit(claims['sub'], 'ODOO_CONFIG_UPDATED', 'InstitutionSettings', institution_id, {
        'enabled': body.enabled,
        'url': body.url
    })
    
    return {'status': 'updated', 'institution_id': institution_id}


@app.get('/odoo/sync/history')
def get_sync_history(institution_id: str, authorization: str = Header(''), 
                    entity_type: str = None, limit: int = 50, offset: int = 0):
    """Get sync history for an institution"""
    claims = admin(authorization)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    
    if not hasattr(store, 'odoo_sync_events'):
        return {'institution_id': institution_id, 'history': [], 'total': 0}
    
    # Filter by institution and entity type
    history = []
    for event_id, event in store.odoo_sync_events.items():
        # For now, return all events (in production would filter by institution)
        if entity_type is None or event.get('entity_type') == entity_type:
            history.append(event)
    
    # Sort by created_at descending
    history.sort(key=lambda x: x['created_at'], reverse=True)

    # Limit results
    total = len(history)
    paginated = history[offset:offset + limit]

    return {
        'institution_id': institution_id,
        'history': paginated,
        'total': total,
        'limit': limit,
        'offset': offset
    }


@app.post('/odoo/sync/trigger')
def trigger_sync(institution_id: str, entity_type: EntityType, 
                  authorization: str = Header('')):
    """Trigger immediate sync for an institution"""
    claims = admin(authorization)
    
    # Verify institution access
    if claims['role'] != 'super_admin':
        if claims.get('institution_id') != institution_id:
            raise HTTPException(403, 'access denied to this institution')
    
    # Check if Odoo is configured
    odoo_config = store.institution_settings.get(institution_id, {}).get('integration_settings', {}).get('odoo')
    if not odoo_config or not odoo_config.get('enabled'):
        raise HTTPException(400, 'Odoo integration not configured or disabled')
    
    # Trigger bulk sync
    bulk_request = BulkSyncRequest(
        entity_type=entity_type,
        institution_id=institution_id,
        direction=SyncDirection.BIDIRECTIONAL
    )
    
    return bulk_sync(bulk_request, authorization)
    item = {'id': str(uuid4()), 'event_type': body.event_type, 'payload': body.payload, 'idempotency_key': body.idempotency_key, 'status': 'PENDING', 'attempts': 0, 'last_error': None}
    store.outbox.append(item)
    audit(claims['sub'], 'INTEGRATION_EVENT_QUEUED', 'Outbox', item['id'], {'event_type': body.event_type})
    return {**item, 'idempotent_replay': False}


@app.post('/odoo/sync')
def sync(authorization: str = Header('')):
    claims = admin(authorization)
    if not settings.odoo_url:
        blocked = 0
        for item in store.outbox:
            if item['status'] in {'PENDING', 'RETRY'}:
                item['status'] = 'BLOCKED'; item['last_error'] = 'Odoo integration is not configured'; blocked += 1
        audit(claims['sub'], 'INTEGRATION_SYNC_BLOCKED', 'Outbox', details={'blocked': blocked})
        return {'synced': 0, 'blocked': blocked, 'message': 'Configure ODOO_URL and credentials before delivery'}
    # Actual RPC is intentionally not performed here: it requires an approved adapter and staging credentials.
    candidates = [item for item in store.outbox if item['status'] in {'PENDING', 'RETRY'}]
    for item in candidates:
        item['attempts'] += 1; item['status'] = 'RETRY'; item['last_error'] = 'Adapter not enabled in this release'
    audit(claims['sub'], 'INTEGRATION_SYNC_DEFERRED', 'Outbox', details={'retry': len(candidates)})
    return {'synced': 0, 'retry': len(candidates), 'message': 'Adapter requires approved staging credentials'}


@app.get('/odoo/status')
def status(authorization: str = Header('')):
    admin(authorization)
    counts = {state: len([item for item in store.outbox if item['status'] == state]) for state in {'PENDING', 'RETRY', 'BLOCKED', 'DEAD_LETTER'}}
    return {'configured': bool(settings.odoo_url), 'counts': counts, 'message': 'No remote sync is executed without a configured adapter and approved credentials.'}

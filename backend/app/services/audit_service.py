"""
Audit and Logging Service
Records administrative actions, configuration modifications, and authentication attempts.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.database import get_db_connection

class AuditService:
    @staticmethod
    def log_action(
        actor_user_id: Optional[str],
        actor_username: Optional[str],
        action_type: str,
        target_resource: str,
        target_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Persist an audit log entry."""
        log_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (
                id, actor_user_id, actor_username, action_type,
                target_resource, target_id, old_values, new_values,
                ip_address, user_agent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                actor_user_id,
                actor_username,
                action_type,
                target_resource,
                target_id,
                json.dumps(old_values, ensure_ascii=False) if old_values else None,
                json.dumps(new_values, ensure_ascii=False) if new_values else None,
                ip_address,
                user_agent,
                created_at
            )
        )
        conn.commit()
        conn.close()
        return log_id

audit_service = AuditService()

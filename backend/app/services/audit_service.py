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

    @staticmethod
    def list_logs(
        search: str = "",
        action_type: str = "",
        page: int = 1,
        page_size: int = 25,
    ) -> Dict[str, Any]:
        """Read audit log entries with search/filter + server-side pagination."""
        page = max(1, int(page))
        page_size = min(100, max(1, int(page_size)))
        offset = (page - 1) * page_size

        conditions = []
        params: list = []
        if search:
            conditions.append(
                "(actor_username LIKE ? OR target_resource LIKE ? OR target_id LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like])
        if action_type:
            conditions.append("action_type = ?")
            params.append(action_type)

        where_sql = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) FROM audit_logs{where_sql}", tuple(params))
        total = int(cursor.fetchone()[0])

        cursor.execute(
            f"""
            SELECT id, actor_user_id, actor_username, action_type, target_resource,
                   target_id, old_values, new_values, ip_address, user_agent, created_at
            FROM audit_logs{where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params) + (page_size, offset),
        )
        items = []
        for row in cursor.fetchall():
            entry = {
                "id": row[0],
                "actor_user_id": row[1],
                "actor_username": row[2],
                "action_type": row[3],
                "target_resource": row[4],
                "target_id": row[5],
                "old_values": json.loads(row[6]) if row[6] else None,
                "new_values": json.loads(row[7]) if row[7] else None,
                "ip_address": row[8],
                "user_agent": row[9],
                "created_at": row[10],
            }
            items.append(entry)
        conn.close()

        return {"items": items, "total": total, "page": page, "page_size": page_size}

audit_service = AuditService()

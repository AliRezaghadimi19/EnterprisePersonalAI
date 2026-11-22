"""
Group Management Service
Handles enterprise groups, quota limits, file restrictions and policy bindings.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError
from app.schemas.user_management import GroupCreate, GroupUpdate
from app.services.audit_service import audit_service

class GroupService:
    @staticmethod
    def list_groups() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, COUNT(u.id) as member_count
            FROM groups g
            LEFT JOIN users u ON u.group_id = g.id
            GROUP BY g.id
            ORDER BY g.created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for g in rows:
            allowed_files = json.loads(g["allowed_file_types"]) if g["allowed_file_types"] else []
            result.append({
                "id": g["id"],
                "name": g["name"],
                "description": g["description"],
                "default_policy": g["default_policy"],
                "default_model_id": g["default_model_id"],
                "allow_model_selection": bool(g["allow_model_selection"]),
                "daily_question_limit": g["daily_question_limit"],
                "monthly_question_limit": g["monthly_question_limit"],
                "daily_token_limit": g["daily_token_limit"],
                "monthly_token_limit": g["monthly_token_limit"],
                "max_file_size_mb": g["max_file_size_mb"],
                "allowed_file_types": allowed_files,
                "member_count": g["member_count"],
                "created_at": g["created_at"]
            })
        return result

    @staticmethod
    def get_group_by_id(group_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.*, COUNT(u.id) as member_count
            FROM groups g
            LEFT JOIN users u ON u.group_id = g.id
            WHERE g.id = ?
            GROUP BY g.id
        """, (group_id,))
        g = cursor.fetchone()
        conn.close()
        if not g:
            raise ResourceNotFoundError(detail_fa="گروه سازمانی مورد نظر یافت نشد.")
            
        allowed_files = json.loads(g["allowed_file_types"]) if g["allowed_file_types"] else []
        return {
            "id": g["id"],
            "name": g["name"],
            "description": g["description"],
            "default_policy": g["default_policy"],
            "default_model_id": g["default_model_id"],
            "allow_model_selection": bool(g["allow_model_selection"]),
            "daily_question_limit": g["daily_question_limit"],
            "monthly_question_limit": g["monthly_question_limit"],
            "daily_token_limit": g["daily_token_limit"],
            "monthly_token_limit": g["monthly_token_limit"],
            "max_file_size_mb": g["max_file_size_mb"],
            "allowed_file_types": allowed_files,
            "member_count": g["member_count"],
            "created_at": g["created_at"]
        }

    @staticmethod
    def create_group(data: GroupCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM groups WHERE name = ?", (data.name,))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="گروهی با این نام در سازمان قبلاً تعریف شده است.")
            
        group_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        allowed_files_json = json.dumps(data.allowed_file_types, ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO groups (
                id, name, description, default_policy, default_model_id,
                allow_model_selection, daily_question_limit, monthly_question_limit,
                daily_token_limit, monthly_token_limit, max_file_size_mb,
                allowed_file_types, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            group_id, data.name, data.description, data.default_policy,
            data.default_model_id, int(data.allow_model_selection),
            data.daily_question_limit, data.monthly_question_limit,
            data.daily_token_limit, data.monthly_token_limit,
            data.max_file_size_mb, allowed_files_json, now
        ))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="GROUP_CREATED",
                target_resource="GROUPS",
                target_id=group_id,
                new_values=data.model_dump()
            )
            
        return GroupService.get_group_by_id(group_id)

    @staticmethod
    def update_group(group_id: str, data: GroupUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="گروه مورد نظر یافت نشد.")
            
        old_data = dict(row)
        
        fields = []
        params = []
        if data.name is not None:
            # check duplicate name if name changed
            if data.name != row["name"]:
                cursor.execute("SELECT id FROM groups WHERE name = ? AND id != ?", (data.name, group_id))
                if cursor.fetchone():
                    conn.close()
                    raise PersianAppException(detail_fa="نام گروه جدید با گروه دیگری تداخل دارد.")
            fields.append("name = ?")
            params.append(data.name)
        if data.description is not None:
            fields.append("description = ?")
            params.append(data.description)
        if data.default_policy is not None:
            fields.append("default_policy = ?")
            params.append(data.default_policy)
        if data.default_model_id is not None:
            fields.append("default_model_id = ?")
            params.append(data.default_model_id)
        if data.allow_model_selection is not None:
            fields.append("allow_model_selection = ?")
            params.append(int(data.allow_model_selection))
        if data.daily_question_limit is not None:
            fields.append("daily_question_limit = ?")
            params.append(data.daily_question_limit)
        if data.monthly_question_limit is not None:
            fields.append("monthly_question_limit = ?")
            params.append(data.monthly_question_limit)
        if data.daily_token_limit is not None:
            fields.append("daily_token_limit = ?")
            params.append(data.daily_token_limit)
        if data.monthly_token_limit is not None:
            fields.append("monthly_token_limit = ?")
            params.append(data.monthly_token_limit)
        if data.max_file_size_mb is not None:
            fields.append("max_file_size_mb = ?")
            params.append(data.max_file_size_mb)
        if data.allowed_file_types is not None:
            fields.append("allowed_file_types = ?")
            params.append(json.dumps(data.allowed_file_types, ensure_ascii=False))

        if fields:
            params.append(group_id)
            cursor.execute(f"UPDATE groups SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="GROUP_UPDATED",
                target_resource="GROUPS",
                target_id=group_id,
                old_values={"name": old_data["name"]},
                new_values=data.model_dump(exclude_unset=True)
            )
            
        return GroupService.get_group_by_id(group_id)

    @staticmethod
    def delete_group(group_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM groups WHERE id = ?", (group_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="گروه سازمانی مورد نظر یافت نشد.")
            
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE group_id = ?", (group_id,))
        count = cursor.fetchone()["count"]
        if count > 0:
            conn.close()
            raise PersianAppException(detail_fa=f"این گروه دارای {count} کاربر عضو است و قابل حذف نمی‌باشد. ابتدا کاربران را به گروه دیگری منتقل کنید.")
            
        cursor.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="GROUP_DELETED",
                target_resource="GROUPS",
                target_id=group_id,
                old_values={"name": row["name"]}
            )
        return True

group_service = GroupService()

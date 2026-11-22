"""
Role & RBAC Management Service
Provides CRUD and permission matrix administration for system and custom roles.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError, PermissionDeniedError
from app.schemas.user_management import RoleCreate, RoleUpdate
from app.services.audit_service import audit_service

class RoleService:
    @staticmethod
    def list_roles() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles ORDER BY is_system DESC, created_at ASC")
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            perms = []
            if r["permissions"]:
                try:
                    perms = json.loads(r["permissions"])
                except Exception:
                    perms = []
            result.append({
                "id": r["id"],
                "name": r["name"],
                "display_name_fa": r["display_name_fa"],
                "permissions": perms,
                "is_system": bool(r["is_system"]),
                "created_at": r["created_at"]
            })
        return result

    @staticmethod
    def get_role_by_id(role_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        r = cursor.fetchone()
        conn.close()
        if not r:
            raise ResourceNotFoundError(detail_fa="نقش مورد نظر یافت نشد.")
            
        perms = json.loads(r["permissions"]) if r["permissions"] else []
        return {
            "id": r["id"],
            "name": r["name"],
            "display_name_fa": r["display_name_fa"],
            "permissions": perms,
            "is_system": bool(r["is_system"]),
            "created_at": r["created_at"]
        }

    @staticmethod
    def create_role(data: RoleCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check duplicate name
        cursor.execute("SELECT id FROM roles WHERE name = ?", (data.name,))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="نقشی با این شناسه انگلیسی قبلاً تعریف شده است.")
            
        role_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        perms_json = json.dumps(data.permissions, ensure_ascii=False)
        
        cursor.execute("""
            INSERT INTO roles (id, name, display_name_fa, permissions, is_system, created_at)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (role_id, data.name, data.display_name_fa, perms_json, now))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="ROLE_CREATED",
                target_resource="ROLES",
                target_id=role_id,
                new_values=data.model_dump()
            )
            
        return {
            "id": role_id,
            "name": data.name,
            "display_name_fa": data.display_name_fa,
            "permissions": data.permissions,
            "is_system": False,
            "created_at": now
        }

    @staticmethod
    def update_role(role_id: str, data: RoleUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="نقش مورد نظر یافت نشد.")
            
        old_data = {
            "display_name_fa": row["display_name_fa"],
            "permissions": json.loads(row["permissions"]) if row["permissions"] else []
        }
        
        new_title = data.display_name_fa if data.display_name_fa is not None else row["display_name_fa"]
        new_perms = json.dumps(data.permissions, ensure_ascii=False) if data.permissions is not None else row["permissions"]
        
        cursor.execute("""
            UPDATE roles SET display_name_fa = ?, permissions = ? WHERE id = ?
        """, (new_title, new_perms, role_id))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="ROLE_UPDATED",
                target_resource="ROLES",
                target_id=role_id,
                old_values=old_data,
                new_values={"display_name_fa": new_title, "permissions": data.permissions}
            )
            
        return RoleService.get_role_by_id(role_id)

    @staticmethod
    def delete_role(role_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="نقش مورد نظر یافت نشد.")
            
        if row["is_system"]:
            conn.close()
            raise PermissionDeniedError("امکان حذف نقش‌های پیش‌فرض و پایه‌ای سیستم وجود ندارد.")
            
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE role_id = ?", (role_id,))
        user_count = cursor.fetchone()["count"]
        if user_count > 0:
            conn.close()
            raise PersianAppException(detail_fa=f"این نقش به {user_count} کاربر انتساب داده شده و قابل حذف نیست. ابتدا نقش کاربران را تغییر دهید.")
            
        cursor.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="ROLE_DELETED",
                target_resource="ROLES",
                target_id=role_id,
                old_values={"name": row["name"], "display_name_fa": row["display_name_fa"]}
            )
        return True

role_service = RoleService()

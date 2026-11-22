"""
User Management Business Logic Service
Handles User CRUD, role assignments, hierarchical policy overrides, and safety locks.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.core.exceptions import (
    PersianAppException,
    ResourceNotFoundError,
    PermissionDeniedError
)
from app.core.security import hash_password
from app.schemas.user_management import UserCreate, UserUpdate
from app.services.audit_service import audit_service

class UserService:
    @staticmethod
    def _get_system_default_policy() -> str:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'default_response_policy'")
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else "HYBRID"

    @classmethod
    def list_users(
        cls,
        search: Optional[str] = None,
        group_id: Optional[str] = None,
        role_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        auth_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        system_policy = cls._get_system_default_policy()
        
        query = """
            SELECT u.*, r.name as role_name, r.display_name_fa as role_title,
                   g.name as group_name, g.default_policy as group_policy,
                   g.daily_question_limit as group_daily_limit,
                   g.allow_model_selection as group_allow_model
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN groups g ON u.group_id = g.id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (u.username LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ? OR u.email LIKE ?)"
            like_val = f"%{search}%"
            params.extend([like_val, like_val, like_val, like_val])
            
        if group_id:
            query += " AND u.group_id = ?"
            params.append(group_id)
            
        if role_id:
            query += " AND u.role_id = ?"
            params.append(role_id)
            
        if is_active is not None:
            query += " AND u.is_active = ?"
            params.append(1 if is_active else 0)
            
        if auth_type:
            query += " AND u.auth_type = ?"
            params.append(auth_type.upper())
            
        query += " ORDER BY u.created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for r in rows:
            # Hierarchy resolution: User override > Group policy > System default
            effective_policy = r["override_policy"] or r["group_policy"] or system_policy
            effective_daily = r["custom_daily_limit"] if r["custom_daily_limit"] is not None else (r["group_daily_limit"] or 100)
            
            result.append({
                "id": r["id"],
                "username": r["username"],
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "email": r["email"],
                "auth_type": r["auth_type"],
                "department": r["department"],
                "is_active": bool(r["is_active"]),
                "role_id": r["role_id"],
                "role_name": r["role_name"],
                "role_title": r["role_title"],
                "group_id": r["group_id"],
                "group_name": r["group_name"],
                "override_policy": r["override_policy"],
                "effective_policy": effective_policy,
                "custom_daily_limit": r["custom_daily_limit"],
                "effective_daily_limit": effective_daily,
                "can_upload_files": bool(r["can_upload_files"]),
                "expires_at": r["expires_at"],
                "created_at": r["created_at"]
            })
        return result

    @classmethod
    def get_user_by_id(cls, user_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        system_policy = cls._get_system_default_policy()
        cursor.execute("""
            SELECT u.*, r.name as role_name, r.display_name_fa as role_title,
                   g.name as group_name, g.default_policy as group_policy,
                   g.daily_question_limit as group_daily_limit,
                   g.monthly_question_limit as group_monthly_limit,
                   g.allow_model_selection as group_allow_model
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN groups g ON u.group_id = g.id
            WHERE u.id = ?
        """, (user_id,))
        r = cursor.fetchone()
        conn.close()
        if not r:
            raise ResourceNotFoundError(detail_fa="کاربر مورد نظر یافت نشد.")
            
        effective_policy = r["override_policy"] or r["group_policy"] or system_policy
        effective_daily = r["custom_daily_limit"] if r["custom_daily_limit"] is not None else (r["group_daily_limit"] or 100)
        effective_monthly = r["custom_monthly_limit"] if r["custom_monthly_limit"] is not None else (r["group_monthly_limit"] or (effective_daily * 30))

        return {
            "id": r["id"],
            "username": r["username"],
            "first_name": r["first_name"],
            "last_name": r["last_name"],
            "email": r["email"],
            "auth_type": r["auth_type"],
            "department": r["department"],
            "is_active": bool(r["is_active"]),
            "role_id": r["role_id"],
            "role_name": r["role_name"],
            "role_title": r["role_title"],
            "group_id": r["group_id"],
            "group_name": r["group_name"],
            "default_model_id": r["default_model_id"],
            "allow_model_selection": r["allow_model_selection"] if r["allow_model_selection"] is not None else r["group_allow_model"],
            "override_policy": r["override_policy"],
            "effective_policy": effective_policy,
            "custom_daily_limit": r["custom_daily_limit"],
            "effective_daily_limit": effective_daily,
            "custom_monthly_limit": r["custom_monthly_limit"],
            "effective_monthly_limit": effective_monthly,
            "can_upload_files": bool(r["can_upload_files"]),
            "expires_at": r["expires_at"],
            "created_at": r["created_at"]
        }

    @classmethod
    def get_user_quotas_and_policy(cls, user_id: str) -> Dict[str, Any]:
        """Resolve current remaining quotas and active policy for user."""
        from datetime import date
        user = cls.get_user_by_id(user_id)
        today_str = date.today().isoformat()
        month_prefix = today_str[:7]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(question_count) as today_used FROM usage_metrics WHERE user_id = ? AND usage_date = ?", (user_id, today_str))
        r1 = cursor.fetchone()
        today_used = r1["today_used"] if r1 and r1["today_used"] else 0

        cursor.execute("SELECT SUM(question_count) as month_used FROM usage_metrics WHERE user_id = ? AND usage_date LIKE ?", (user_id, f"{month_prefix}%"))
        r2 = cursor.fetchone()
        month_used = r2["month_used"] if r2 and r2["month_used"] else 0
        conn.close()

        daily_limit = user["effective_daily_limit"]
        monthly_limit = user["effective_monthly_limit"]

        return {
            "policy": user["effective_policy"],
            "daily_limit": daily_limit,
            "monthly_limit": monthly_limit,
            "daily_quota_remaining": max(0, daily_limit - today_used),
            "monthly_quota_remaining": max(0, monthly_limit - month_used),
            "allow_model_selection": bool(user["allow_model_selection"]),
            "default_model_id": user["default_model_id"]
        }

    @classmethod
    def create_user(cls, data: UserCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Uniqueness check for username
        cursor.execute("SELECT id FROM users WHERE username = ?", (data.username,))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="این نام کاربری قبلاً در سامانه ثبت شده است.")
            
        # 2. Check Role and Group existence
        cursor.execute("SELECT id FROM roles WHERE id = ?", (data.role_id,))
        if not cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="نقش کاربری مشخص‌شده معتبر نیست.")
            
        cursor.execute("SELECT id FROM groups WHERE id = ?", (data.group_id,))
        if not cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="گروه سازمانی مشخص‌شده معتبر نیست.")
            
        # 3. Password handling for local users
        hashed_pwd = None
        if data.auth_type == "LOCAL":
            if not data.password:
                conn.close()
                raise PersianAppException(detail_fa="تعیین رمز عبور برای کاربران با احراز هویت محلی الزامی است.")
            hashed_pwd = hash_password(data.password)

        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO users (
                id, username, email, password_hash, first_name, last_name,
                auth_type, department, role_id, group_id, is_active, expires_at,
                default_model_id, allow_model_selection, override_policy,
                custom_daily_limit, custom_monthly_limit, can_upload_files, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, data.username, data.email, hashed_pwd, data.first_name, data.last_name,
            data.auth_type, data.department, data.role_id, data.group_id, int(data.is_active),
            data.expires_at, data.default_model_id,
            int(data.allow_model_selection) if data.allow_model_selection is not None else None,
            data.override_policy, data.custom_daily_limit, data.custom_monthly_limit,
            int(data.can_upload_files), now
        ))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="USER_CREATED",
                target_resource="USERS",
                target_id=user_id,
                new_values={
                    "username": data.username,
                    "first_name": data.first_name,
                    "last_name": data.last_name,
                    "role_id": data.role_id,
                    "group_id": data.group_id
                }
            )
            
        return cls.get_user_by_id(user_id)

    @classmethod
    def update_user(cls, user_id: str, data: UserUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT u.*, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id WHERE u.id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="کاربر مورد نظر یافت نشد.")
            
        old_data = dict(row)
        
        # Safety Check: Prevent deactivating the last active super_admin
        if data.is_active is False and row["role_name"] == "super_admin":
            cursor.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id = r.id WHERE r.name = 'super_admin' AND u.is_active = 1")
            super_count = cursor.fetchone()["count"]
            if super_count <= 1:
                conn.close()
                raise PermissionDeniedError("امکان غیرفعال‌سازی تنها مدیر کل فعال سامانه وجود ندارد.")
                
        fields = []
        params = []
        
        if data.first_name is not None:
            fields.append("first_name = ?")
            params.append(data.first_name)
        if data.last_name is not None:
            fields.append("last_name = ?")
            params.append(data.last_name)
        if data.email is not None:
            fields.append("email = ?")
            params.append(data.email)
        if data.department is not None:
            fields.append("department = ?")
            params.append(data.department)
        if data.role_id is not None:
            # check role exists
            cursor.execute("SELECT id FROM roles WHERE id = ?", (data.role_id,))
            if not cursor.fetchone():
                conn.close()
                raise PersianAppException(detail_fa="نقش انتخابی معتبر نیست.")
            fields.append("role_id = ?")
            params.append(data.role_id)
        if data.group_id is not None:
            # check group exists
            cursor.execute("SELECT id FROM groups WHERE id = ?", (data.group_id,))
            if not cursor.fetchone():
                conn.close()
                raise PersianAppException(detail_fa="گروه انتخابی معتبر نیست.")
            fields.append("group_id = ?")
            params.append(data.group_id)
        if data.is_active is not None:
            fields.append("is_active = ?")
            params.append(int(data.is_active))
        if data.expires_at is not None:
            fields.append("expires_at = ?")
            params.append(data.expires_at if data.expires_at != "" else None)
        if data.default_model_id is not None:
            fields.append("default_model_id = ?")
            params.append(data.default_model_id)
        if data.allow_model_selection is not None:
            fields.append("allow_model_selection = ?")
            params.append(int(data.allow_model_selection))
        if data.override_policy is not None:
            fields.append("override_policy = ?")
            params.append(data.override_policy if data.override_policy != "" else None)
        if data.custom_daily_limit is not None:
            fields.append("custom_daily_limit = ?")
            params.append(data.custom_daily_limit)
        if data.custom_monthly_limit is not None:
            fields.append("custom_monthly_limit = ?")
            params.append(data.custom_monthly_limit)
        if data.can_upload_files is not None:
            fields.append("can_upload_files = ?")
            params.append(int(data.can_upload_files))
        if data.password:
            fields.append("password_hash = ?")
            params.append(hash_password(data.password))

        if fields:
            params.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="USER_UPDATED",
                target_resource="USERS",
                target_id=user_id,
                old_values={"username": old_data["username"]},
                new_values=data.model_dump(exclude_unset=True, exclude={"password"})
            )
            
        return cls.get_user_by_id(user_id)

    @classmethod
    def delete_user(cls, user_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT u.*, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id WHERE u.id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="کاربر مورد نظر یافت نشد.")
            
        if actor_user and actor_user["id"] == user_id:
            conn.close()
            raise PermissionDeniedError("شما نمی‌توانید حساب کاربری جاری خود را حذف کنید.")
            
        if row["role_name"] == "super_admin":
            cursor.execute("SELECT COUNT(*) as count FROM users u JOIN roles r ON u.role_id = r.id WHERE r.name = 'super_admin'")
            super_count = cursor.fetchone()["count"]
            if super_count <= 1:
                conn.close()
                raise PermissionDeniedError("امکان حذف تنها مدیر کل سامانه وجود ندارد.")
                
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="USER_DELETED",
                target_resource="USERS",
                target_id=user_id,
                old_values={"username": row["username"]}
            )
        return True

user_service = UserService()

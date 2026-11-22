"""
Enterprise Authentication Service
Handles:
- Local Authentication with bcrypt/PBKDF2 hash verification
- Active Directory (LDAP/LDAPS) authentication
- Enforcement of system authentication modes (LOCAL_ONLY, AD_ONLY, BOTH)
- User auto-provisioning upon first successful AD sign-in
- JWT Token issuance and refresh
- Session and audit log recording
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings
from app.core.database import get_db_connection
from app.core.exceptions import (
    AuthenticationError,
    AccountDisabledError,
    PermissionDeniedError,
    PersianAppException
)
from app.core.ldap_auth import LDAPAuthenticator, escape_ldap_filter
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_sensitive_data
)
from app.services.audit_service import audit_service

class AuthService:
    
    @staticmethod
    def get_auth_mode() -> str:
        """Fetch current auth mode from system settings."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = 'auth_mode'")
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else "BOTH"

    @classmethod
    def authenticate_user(
        cls,
        username: str,
        password: str,
        auth_method: str = "AUTO",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Authenticate user according to configured policy and credentials.
        """
        system_auth_mode = cls.get_auth_mode()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if local user exists
        cursor.execute("""
            SELECT u.*, r.name as role_name, r.display_name_fa as role_display_name_fa,
                   r.permissions as role_permissions, g.name as group_name,
                   g.default_policy as group_policy, g.allow_model_selection as group_allow_model,
                   g.daily_question_limit, g.monthly_question_limit
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN groups g ON u.group_id = g.id
            WHERE u.username = ?
        """, (username,))
        user_row = cursor.fetchone()
        
        authenticated_user = None
        auth_type_used = "LOCAL"

        # 1. Try Local Authentication if allowed or if Super Admin emergency login
        can_try_local = system_auth_mode in ("BOTH", "LOCAL_ONLY") or (user_row and user_row["role_name"] == "super_admin")
        
        if auth_method in ("AUTO", "LOCAL") and can_try_local and user_row and user_row["password_hash"]:
            if verify_password(password, user_row["password_hash"]):
                authenticated_user = user_row
                auth_type_used = "LOCAL"

        # 2. Try Active Directory if not authenticated locally yet
        if not authenticated_user and (auth_method in ("AUTO", "ACTIVE_DIRECTORY")):
            if system_auth_mode == "LOCAL_ONLY":
                conn.close()
                raise PermissionDeniedError("ورود از طریق اکتیو دایرکتوری در تنظیمات سامانه غیرفعال است.")
                
            # Fetch AD settings
            cursor.execute("SELECT * FROM active_directory_configs LIMIT 1")
            ad_row = cursor.fetchone()
            
            if not ad_row or not ad_row["is_enabled"]:
                if auth_method == "ACTIVE_DIRECTORY":
                    conn.close()
                    raise PersianAppException(detail_fa="سرویس اکتیو دایرکتوری غیرفعال است.")
            else:
                bind_pwd = decrypt_sensitive_data(ad_row["encrypted_bind_password"]) if ad_row["encrypted_bind_password"] else ""
                allowed_groups = json.loads(ad_row["allowed_groups"]) if ad_row["allowed_groups"] else []
                group_role_mapping = json.loads(ad_row["group_role_mapping"]) if ad_row["group_role_mapping"] else {}
                
                ldap_client = LDAPAuthenticator(
                    server_host=ad_row["server_host"],
                    port=ad_row["port_ssl"] if ad_row["use_ssl"] else ad_row["port"],
                    use_ssl=bool(ad_row["use_ssl"]),
                    domain_name=ad_row["domain_name"],
                    base_dn=ad_row["base_dn"],
                    user_search_base=ad_row["user_search_base"],
                    group_search_base=ad_row["group_search_base"],
                    bind_dn=ad_row["bind_dn"],
                    bind_password=bind_pwd,
                    allowed_groups=allowed_groups,
                    group_role_mapping=group_role_mapping
                )
                
                success, ad_user_data, msg = ldap_client.authenticate(username, password)
                if success and ad_user_data:
                    auth_type_used = "ACTIVE_DIRECTORY"
                    # User authenticated against AD
                    if not user_row:
                        # Auto-provision user if enabled
                        if not ad_row["auto_provision"]:
                            conn.close()
                            raise PermissionDeniedError("ثبت خودکار کاربران اکتیو دایرکتوری غیرفعال است.")
                            
                        # Resolve role and group
                        role_target = ad_user_data.get("mapped_role", "normal_subscriber")
                        cursor.execute("SELECT id FROM roles WHERE name = ? OR display_name_fa = ?", (role_target, role_target))
                        r_row = cursor.fetchone()
                        role_id = r_row["id"] if r_row else None
                        
                        cursor.execute("SELECT id FROM groups WHERE name = 'کاربران عمومی'")
                        g_row = cursor.fetchone()
                        group_id = g_row["id"] if g_row else None
                        
                        new_user_id = str(uuid.uuid4())
                        now = datetime.now(timezone.utc).isoformat()
                        cursor.execute("""
                            INSERT INTO users (
                                id, username, email, password_hash, first_name, last_name,
                                auth_type, department, role_id, group_id, is_active, can_upload_files, created_at
                            ) VALUES (?, ?, ?, NULL, ?, ?, 'ACTIVE_DIRECTORY', ?, ?, ?, 1, 1, ?)
                        """, (
                            new_user_id, ad_user_data["username"], ad_user_data.get("email"),
                            ad_user_data.get("first_name", "کاربر"), ad_user_data.get("last_name", "سازمانی"),
                            ad_user_data.get("department", "عمومی"), role_id, group_id, now
                        ))
                        conn.commit()
                        
                        # Re-fetch provisioned user
                        cursor.execute("""
                            SELECT u.*, r.name as role_name, r.display_name_fa as role_display_name_fa,
                                   r.permissions as role_permissions, g.name as group_name,
                                   g.default_policy as group_policy, g.allow_model_selection as group_allow_model,
                                   g.daily_question_limit, g.monthly_question_limit
                            FROM users u
                            LEFT JOIN roles r ON u.role_id = r.id
                            LEFT JOIN groups g ON u.group_id = g.id
                            WHERE u.id = ?
                        """, (new_user_id,))
                        authenticated_user = cursor.fetchone()
                    else:
                        authenticated_user = user_row
                else:
                    if auth_method == "ACTIVE_DIRECTORY":
                        conn.close()
                        raise AuthenticationError(msg)

        if not authenticated_user:
            conn.close()
            audit_service.log_action(
                actor_user_id=None,
                actor_username=username,
                action_type="LOGIN_FAILED",
                target_resource="AUTH",
                ip_address=ip_address,
                user_agent=user_agent
            )
            raise AuthenticationError("نام کاربری یا رمز عبور اشتباه است.")

        # Check user active status and expiration
        if not authenticated_user["is_active"]:
            conn.close()
            raise AccountDisabledError("حساب کاربری شما غیرفعال شده است.")

        if authenticated_user["expires_at"]:
            try:
                exp_date = datetime.fromisoformat(authenticated_user["expires_at"])
                if datetime.now(timezone.utc) > exp_date:
                    conn.close()
                    raise AccountDisabledError("تاریخ انقضای حساب کاربری شما به پایان رسیده است.")
            except ValueError:
                pass

        # Build permissions list
        perms = []
        if authenticated_user["role_permissions"]:
            try:
                perms = json.loads(authenticated_user["role_permissions"])
            except Exception:
                perms = []

        # Effective policy resolution: User Override > Group Policy > System Default
        system_policy = "HYBRID"
        cursor.execute("SELECT value FROM system_settings WHERE key = 'default_response_policy'")
        sp_row = cursor.fetchone()
        if sp_row:
            system_policy = sp_row["value"]
            
        effective_policy = authenticated_user["override_policy"] or authenticated_user["group_policy"] or system_policy
        effective_allow_model = bool(
            authenticated_user["allow_model_selection"] 
            if authenticated_user["allow_model_selection"] is not None 
            else authenticated_user["group_allow_model"]
        )

        user_info = {
            "id": authenticated_user["id"],
            "username": authenticated_user["username"],
            "email": authenticated_user["email"],
            "first_name": authenticated_user["first_name"],
            "last_name": authenticated_user["last_name"],
            "auth_type": auth_type_used,
            "department": authenticated_user["department"],
            "role_name": authenticated_user["role_name"] or "normal_subscriber",
            "role_display_name_fa": authenticated_user["role_display_name_fa"] or "مشترک عادی",
            "group_name": authenticated_user["group_name"],
            "permissions": perms,
            "default_model_id": authenticated_user["default_model_id"],
            "allow_model_selection": effective_allow_model,
            "policy": effective_policy,
            "daily_quota_remaining": authenticated_user["custom_daily_limit"] or authenticated_user["daily_question_limit"] or 100,
            "monthly_quota_remaining": authenticated_user["custom_monthly_limit"] or authenticated_user["monthly_question_limit"] or 3000,
            "can_upload_files": bool(authenticated_user["can_upload_files"])
        }

        # Generate Tokens
        access_token = create_access_token(
            subject=authenticated_user["id"],
            extra_claims={"username": authenticated_user["username"], "role": authenticated_user["role_name"]}
        )
        refresh_token = create_refresh_token(subject=authenticated_user["id"])

        # Audit successful login
        audit_service.log_action(
            actor_user_id=authenticated_user["id"],
            actor_username=authenticated_user["username"],
            action_type="LOGIN_SUCCESS",
            target_resource="AUTH",
            new_values={"auth_type": auth_type_used},
            ip_address=ip_address,
            user_agent=user_agent
        )

        conn.close()
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user_info
        }

    @classmethod
    def get_current_user_by_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch complete user profile by user id."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.*, r.name as role_name, r.display_name_fa as role_display_name_fa,
                   r.permissions as role_permissions, g.name as group_name,
                   g.default_policy as group_policy, g.allow_model_selection as group_allow_model,
                   g.daily_question_limit, g.monthly_question_limit
            FROM users u
            LEFT JOIN roles r ON u.role_id = r.id
            LEFT JOIN groups g ON u.group_id = g.id
            WHERE u.id = ? AND u.is_active = 1
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
            
        perms = []
        if row["role_permissions"]:
            try:
                perms = json.loads(row["role_permissions"])
            except Exception:
                perms = []

        system_policy = "HYBRID"
        cursor.execute("SELECT value FROM system_settings WHERE key = 'default_response_policy'")
        sp_row = cursor.fetchone()
        if sp_row:
            system_policy = sp_row["value"]

        effective_policy = row["override_policy"] or row["group_policy"] or system_policy
        effective_allow_model = bool(
            row["allow_model_selection"] if row["allow_model_selection"] is not None else row["group_allow_model"]
        )

        data = {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "auth_type": row["auth_type"],
            "department": row["department"],
            "role_name": row["role_name"] or "normal_subscriber",
            "role_display_name_fa": row["role_display_name_fa"] or "مشترک عادی",
            "group_name": row["group_name"],
            "permissions": perms,
            "default_model_id": row["default_model_id"],
            "allow_model_selection": effective_allow_model,
            "policy": effective_policy,
            "daily_quota_remaining": row["custom_daily_limit"] or row["daily_question_limit"] or 100,
            "monthly_quota_remaining": row["custom_monthly_limit"] or row["monthly_question_limit"] or 3000,
            "can_upload_files": bool(row["can_upload_files"])
        }
        conn.close()
        return data

    @classmethod
    def refresh_user_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Validate refresh token and issue new token pair."""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthenticationError("توکن تمدید نشست (Refresh Token) نامعتبر یا منقضی است.")
            
        user_id = payload.get("sub")
        user = cls.get_current_user_by_id(user_id)
        if not user:
            raise AccountDisabledError("حساب کاربری یافت نشد یا غیرفعال شده است.")
            
        new_access = create_access_token(
            subject=user["id"],
            extra_claims={"username": user["username"], "role": user["role_name"]}
        )
        new_refresh = create_refresh_token(subject=user["id"])
        
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": user
        }

auth_service = AuthService()

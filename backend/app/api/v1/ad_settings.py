"""
Active Directory Settings API Endpoints
"""

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status

from app.api.deps import require_super_admin
from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException
from app.core.ldap_auth import LDAPAuthenticator
from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data
from app.schemas.ad_settings import (
    ADConfigUpdate,
    ADConfigResponse,
    ADTestConnectionRequest,
    ADTestConnectionResponse
)
from app.services.audit_service import audit_service

router = APIRouter(prefix="/ad-settings", tags=["تنظیمات Active Directory"])

@router.get("", response_model=ADConfigResponse, summary="دریافت تنظیمات کنترلر دامنه")
def get_ad_settings(current_user: dict = Depends(require_super_admin)):
    """دریافت تنظیمات فعال Active Directory بدون نمایش مستقیم رمز عبور Bind."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_directory_configs LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise PersianAppException(detail_fa="تنظیمات اکتیو دایرکتوری در سامانه ثبت نشده است.")
        
    allowed_groups = json.loads(row["allowed_groups"]) if row["allowed_groups"] else []
    group_role_mapping = json.loads(row["group_role_mapping"]) if row["group_role_mapping"] else {}
    has_pwd = bool(row["encrypted_bind_password"])
    
    return {
        "id": row["id"],
        "is_enabled": bool(row["is_enabled"]),
        "server_host": row["server_host"],
        "port": row["port"],
        "port_ssl": row["port_ssl"],
        "use_ssl": bool(row["use_ssl"]),
        "domain_name": row["domain_name"],
        "base_dn": row["base_dn"],
        "user_search_base": row["user_search_base"],
        "group_search_base": row["group_search_base"],
        "bind_dn": row["bind_dn"],
        "allowed_groups": allowed_groups,
        "group_role_mapping": group_role_mapping,
        "auto_provision": bool(row["auto_provision"]),
        "has_bind_password": has_pwd,
        "updated_at": row["updated_at"]
    }

@router.put("", response_model=ADConfigResponse, summary="به‌روزرسانی تنظیمات Active Directory")
def update_ad_settings(body: ADConfigUpdate, current_user: dict = Depends(require_super_admin)):
    """به‌روزرسانی تنظیمات کنترلر دامنه و رمزنگاری رمز عبور حساب Bind."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM active_directory_configs LIMIT 1")
    row = cursor.fetchone()
    
    now = datetime.now(timezone.utc).isoformat()
    encrypted_pwd = row["encrypted_bind_password"] if row else ""
    if body.bind_password:
        encrypted_pwd = encrypt_sensitive_data(body.bind_password)
        
    allowed_groups_json = json.dumps(body.allowed_groups, ensure_ascii=False)
    group_role_json = json.dumps(body.group_role_mapping, ensure_ascii=False)
    
    if row:
        config_id = row["id"]
        cursor.execute("""
            UPDATE active_directory_configs SET
                is_enabled = ?, server_host = ?, port = ?, port_ssl = ?,
                use_ssl = ?, domain_name = ?, base_dn = ?, user_search_base = ?,
                group_search_base = ?, bind_dn = ?, encrypted_bind_password = ?,
                allowed_groups = ?, group_role_mapping = ?, auto_provision = ?, updated_at = ?
            WHERE id = ?
        """, (
            int(body.is_enabled), body.server_host, body.port, body.port_ssl,
            int(body.use_ssl), body.domain_name, body.base_dn, body.user_search_base,
            body.group_search_base, body.bind_dn, encrypted_pwd,
            allowed_groups_json, group_role_json, int(body.auto_provision), now, config_id
        ))
    else:
        import uuid
        config_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO active_directory_configs (
                id, is_enabled, server_host, port, port_ssl, use_ssl,
                domain_name, base_dn, user_search_base, group_search_base,
                bind_dn, encrypted_bind_password, allowed_groups, group_role_mapping,
                auto_provision, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            config_id, int(body.is_enabled), body.server_host, body.port, body.port_ssl,
            int(body.use_ssl), body.domain_name, body.base_dn, body.user_search_base,
            body.group_search_base, body.bind_dn, encrypted_pwd,
            allowed_groups_json, group_role_json, int(body.auto_provision), now
        ))
        
    conn.commit()
    conn.close()
    
    audit_service.log_action(
        actor_user_id=current_user["id"],
        actor_username=current_user["username"],
        action_type="AD_CONFIG_UPDATED",
        target_resource="ACTIVE_DIRECTORY",
        target_id=config_id,
        new_values={"is_enabled": body.is_enabled, "server_host": body.server_host, "domain_name": body.domain_name}
    )
    
    return {
        "id": config_id,
        "is_enabled": body.is_enabled,
        "server_host": body.server_host,
        "port": body.port,
        "port_ssl": body.port_ssl,
        "use_ssl": body.use_ssl,
        "domain_name": body.domain_name,
        "base_dn": body.base_dn,
        "user_search_base": body.user_search_base,
        "group_search_base": body.group_search_base,
        "bind_dn": body.bind_dn,
        "allowed_groups": body.allowed_groups,
        "group_role_mapping": body.group_role_mapping,
        "auto_provision": body.auto_provision,
        "has_bind_password": bool(encrypted_pwd),
        "updated_at": now
    }

@router.post("/test", response_model=ADTestConnectionResponse, summary="تست ارتباط با Active Directory")
def test_ad_connection(body: ADTestConnectionRequest, current_user: dict = Depends(require_super_admin)):
    """ارزیابی برقراری ارتباط با Domain Controller و درگاه LDAP/LDAPS."""
    port_to_use = body.port if not body.use_ssl else 636
    authenticator = LDAPAuthenticator(
        server_host=body.server_host,
        port=port_to_use,
        use_ssl=body.use_ssl,
        domain_name=body.domain_name or ""
    )
    success, message = authenticator.test_connection()
    return {"success": success, "message": message}

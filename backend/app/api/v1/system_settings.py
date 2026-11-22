"""
System Configuration API Endpoints
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status

from app.api.deps import require_super_admin
from app.core.database import get_db_connection
from app.schemas.system_settings import SystemSettingsDTO
from app.services.audit_service import audit_service

router = APIRouter(prefix="/settings", tags=["تنظیمات سامانه"])

@router.get("", response_model=SystemSettingsDTO, summary="دریافت تنظیمات سراسری سامانه")
def get_system_settings():
    """دریافت مقادیر پیکربندی اصلی سامانه شامل شیوه احراز هویت و سیاست پاسخگویی."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM system_settings")
    rows = cursor.fetchall()
    conn.close()
    
    settings_dict = {row["key"]: row["value"] for row in rows}
    
    return {
        "auth_mode": settings_dict.get("auth_mode", "BOTH"),
        "default_response_policy": settings_dict.get("default_response_policy", "HYBRID"),
        "default_ai_language": settings_dict.get("default_ai_language", "fa"),
        "max_file_size_mb": int(settings_dict.get("max_file_size_mb", 25)),
        "allow_file_upload_globally": settings_dict.get("allow_file_upload_globally", "true").lower() in ("true", "1"),
        "session_timeout_minutes": int(settings_dict.get("session_timeout_minutes", 480))
    }

@router.put("", response_model=SystemSettingsDTO, summary="ویرایش تنظیمات سراسری سامانه")
def update_system_settings(body: SystemSettingsDTO, current_user: dict = Depends(require_super_admin)):
    """ویرایش تنظیمات پیکربندی سامانه توسط مدیر کل."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    updates = [
        ("auth_mode", body.auth_mode),
        ("default_response_policy", body.default_response_policy),
        ("default_ai_language", body.default_ai_language),
        ("max_file_size_mb", str(body.max_file_size_mb)),
        ("allow_file_upload_globally", str(body.allow_file_upload_globally).lower()),
        ("session_timeout_minutes", str(body.session_timeout_minutes))
    ]
    
    for key, val in updates:
        cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (val, now, key))
        
    conn.commit()
    conn.close()
    
    audit_service.log_action(
        actor_user_id=current_user["id"],
        actor_username=current_user["username"],
        action_type="SYSTEM_SETTINGS_UPDATED",
        target_resource="SYSTEM_SETTINGS",
        new_values=body.model_dump()
    )
    
    return body

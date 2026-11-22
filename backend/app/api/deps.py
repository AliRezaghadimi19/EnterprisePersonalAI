"""
FastAPI Dependencies Module
Provides authentication context, RBAC validation, and database connections.
"""

from typing import Any, Callable, Dict, List, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.services.auth_service import auth_service

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> Dict[str, Any]:
    """Validate Bearer token and return active user profile."""
    if not credentials or not credentials.credentials:
        raise AuthenticationError("توکن احراز هویت ارائه نشده است.")
        
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise AuthenticationError("توکن امنیتی منقضی شده یا نامعتبر است.")
        
    user_id = payload.get("sub")
    user = auth_service.get_current_user_by_id(user_id)
    if not user:
        raise AuthenticationError("حساب کاربری یافت نشد یا غیرفعال شده است.")
        
    return user

def require_permission(permission: str) -> Callable:
    """Dependency factory checking if current user has the specific permission."""
    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        permissions: List[str] = current_user.get("permissions", [])
        if "*" in permissions or permission in permissions:
            return current_user
        raise PermissionDeniedError(f"شما مجوز عملیات '{permission}' را ندارید.")
    return permission_checker

def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency verifying that the user is an Administrator (super_admin or system_admin)."""
    role = current_user.get("role_name")
    if role in ("super_admin", "system_admin"):
        return current_user
    raise PermissionDeniedError("دسترسی به این بخش صرفاً برای مدیران سامانه مجاز است.")

def require_super_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency verifying that the user is the Super Administrator."""
    if current_user.get("role_name") == "super_admin":
        return current_user
    raise PermissionDeniedError("این عملیات انحصاراً برای مدیر کل سامانه مجاز است.")

"""
Authentication API Endpoints
"""

from fastapi import APIRouter, Depends, Request, status
from app.api.deps import get_current_user
from app.core.exceptions import PersianAppException
from app.core.rate_limiter import rate_limiter
from app.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest, UserInfoResponse
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["احراز هویت"])

@router.post("/login", response_model=TokenResponse, summary="ورود به سامانه (محلی یا اکتیو دایرکتوری)")
def login(request: Request, body: LoginRequest):
    """
    احراز هویت کاربر از طریق حساب داخلی یا Active Directory بر اساس تنظیمات سامانه.
    دارای محافظت در برابر حملات Brute-Force.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    rate_key = f"login_attempt:{client_ip}:{body.username}"
    
    # Check rate limit (10 attempts per minute)
    if rate_limiter.is_rate_limited(rate_key, max_requests=10, window_seconds=60):
        raise PersianAppException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail_fa="تعداد تلاش‌های ورود بیش از حد مجاز است. لطفاً یک دقیقه دیگر تلاش کنید.",
            error_code="RATE_LIMIT_EXCEEDED"
        )
        
    user_agent = request.headers.get("user-agent", "")
    
    result = auth_service.authenticate_user(
        username=body.username.strip(),
        password=body.password,
        auth_method=body.auth_method or "AUTO",
        ip_address=client_ip,
        user_agent=user_agent
    )
    return result

@router.post("/refresh", response_model=TokenResponse, summary="تمدید توکن احراز هویت")
def refresh_token(body: RefreshTokenRequest):
    """
    تمدید توکن نشست با استفاده از Refresh Token معتبر.
    """
    return auth_service.refresh_user_token(body.refresh_token)

@router.get("/me", response_model=UserInfoResponse, summary="دریافت اطلاعات پروفایل کاربر فعلی")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    دریافت مشخصات کامل کاربر وارد شده شامل نقش، دسترسی‌ها و سهمیه باقی‌مانده.
    """
    return current_user

@router.post("/logout", summary="خروج از سامانه")
def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    ثبت رویداد خروج کاربر در لاگ ممیزی امنیتی.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    audit_service.log_action(
        actor_user_id=current_user["id"],
        actor_username=current_user["username"],
        action_type="LOGOUT",
        target_resource="AUTH",
        ip_address=client_ip
    )
    return {"success": True, "message": "خروج از حساب کاربری با موفقیت انجام شد."}

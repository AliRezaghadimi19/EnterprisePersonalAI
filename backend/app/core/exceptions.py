"""
Standard Persian Exceptions and Error Formatting
Provides consistent JSON error bodies for frontend display with RTL support.
"""

from typing import Any, Dict, Optional

try:
    from fastapi import HTTPException, status
except ImportError:
    class HTTPException(Exception):
        def __init__(self, status_code: int = 400, detail: Any = None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(str(detail))

    class _Status:
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_403_FORBIDDEN = 403
        HTTP_404_NOT_FOUND = 404
        HTTP_422_UNPROCESSABLE_ENTITY = 422
        HTTP_429_TOO_MANY_REQUESTS = 429

    status = _Status()

class PersianAppException(HTTPException):
    """Base application exception with Persian error messaging."""
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail_fa: str = "خطایی در پردازش درخواست رخ داده است.",
        error_code: str = "BUSINESS_LOGIC_ERROR",
        extra_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "success": False,
                "message": detail_fa,
                "error_code": error_code,
                "data": extra_data or {}
            }
        )

class AuthenticationError(PersianAppException):
    def __init__(self, detail_fa: str = "نام کاربری یا رمز عبور نامعتبر است."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail_fa=detail_fa,
            error_code="AUTH_CREDENTIALS_INVALID"
        )

class PermissionDeniedError(PersianAppException):
    def __init__(self, detail_fa: str = "شما مجوز دسترسی به این بخش را ندارید."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail_fa=detail_fa,
            error_code="PERMISSION_DENIED"
        )

class AccountDisabledError(PersianAppException):
    def __init__(self, detail_fa: str = "حساب کاربری شما غیرفعال یا منقضی شده است. لطفا با مدیر تماس بگیرید."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail_fa=detail_fa,
            error_code="ACCOUNT_SUSPENDED"
        )

class QuotaExceededError(PersianAppException):
    def __init__(self, detail_fa: str = "سهمیه مصرف مجاز شما به اتمام رسیده است."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail_fa=detail_fa,
            error_code="QUOTA_EXCEEDED"
        )

class ResourceNotFoundError(PersianAppException):
    def __init__(self, detail_fa: str = "اطلاعات مورد نظر در سامانه یافت نشد."):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail_fa=detail_fa,
            error_code="RESOURCE_NOT_FOUND"
        )

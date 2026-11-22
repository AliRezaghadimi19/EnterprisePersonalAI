"""
Authentication and Authorization Data Schemas
"""

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self, *args, **kwargs):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    def Field(default=None, default_factory=None, description=""):
        if default_factory is not None:
            return default_factory()
        return default

class LoginRequest(BaseModel):
    username: str = Field(..., description="نام کاربری (داخلی یا اکتیو دایرکتوری)")
    password: str = Field(..., description="رمز عبور")
    auth_method: Optional[str] = Field("AUTO", description="روش ورود: AUTO, LOCAL, ACTIVE_DIRECTORY")

class UserInfoResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    first_name: str
    last_name: str
    auth_type: str
    department: Optional[str]
    role_name: str
    role_display_name_fa: str
    group_name: Optional[str]
    permissions: List[str]
    default_model_id: Optional[str]
    allow_model_selection: bool
    policy: str
    daily_quota_remaining: int
    monthly_quota_remaining: int
    can_upload_files: bool

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse

class RefreshTokenRequest(BaseModel):
    refresh_token: str

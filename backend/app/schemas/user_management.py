"""
User, Group and Role Management Data Schemas for Phase 2
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
            exclude = kwargs.get('exclude', set()) or set()
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_') and k not in exclude}
    def Field(default=None, default_factory=None, description=""):
        if default_factory is not None:
            return default_factory()
        return default

# ------------------------------------------------------------------------------
# Role Schemas
# ------------------------------------------------------------------------------

class RoleBase(BaseModel):
    name: str = Field(..., description="شناسه سیستمی نقش، مثال: senior_analyst")
    display_name_fa: str = Field(..., description="عنوان نمایشی فارسی، مثال: تحلیل‌گر ارشد")
    permissions: List[str] = Field(default_factory=list, description="لیست مجوزهای دسترسی نقش")

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    display_name_fa: Optional[str] = None
    permissions: Optional[List[str]] = None

class RoleResponse(RoleBase):
    id: str
    is_system: bool
    created_at: str

# ------------------------------------------------------------------------------
# Group Schemas
# ------------------------------------------------------------------------------

class GroupBase(BaseModel):
    name: str = Field(..., description="نام گروه سازمانی")
    description: Optional[str] = Field(None, description="توضیحات عملکرد گروه")
    default_policy: str = Field("HYBRID", description="سیاست پاسخگویی پیش‌فرض: KNOWLEDGE_ONLY, HYBRID, FREE_AI")
    default_model_id: Optional[str] = Field(None, description="مدل هوش مصنوعی پیش‌فرض")
    allow_model_selection: bool = Field(True, description="اجازه انتخاب مدل توسط اعضای گروه")
    daily_question_limit: int = Field(100, description="سهمیه تعداد سؤال روزانه")
    monthly_question_limit: int = Field(3000, description="سهمیه تعداد سؤال ماهانه")
    daily_token_limit: int = Field(200000, description="سقف توکن روزانه")
    monthly_token_limit: int = Field(5000000, description="سقف توکن ماهانه")
    max_file_size_mb: int = Field(25, description="حداکثر حجم مجاز فایل ارسالی به مگابایت")
    allowed_file_types: List[str] = Field(
        default_factory=lambda: ["pdf", "docx", "xlsx", "txt", "png", "jpg"],
        description="فرمت‌های مجاز فایل برای این گروه"
    )

class GroupCreate(GroupBase):
    pass

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_policy: Optional[str] = None
    default_model_id: Optional[str] = None
    allow_model_selection: Optional[bool] = None
    daily_question_limit: Optional[int] = None
    monthly_question_limit: Optional[int] = None
    daily_token_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None
    max_file_size_mb: Optional[int] = None
    allowed_file_types: Optional[List[str]] = None

class GroupResponse(GroupBase):
    id: str
    created_at: str
    member_count: int = 0

# ------------------------------------------------------------------------------
# User Schemas
# ------------------------------------------------------------------------------

class UserBase(BaseModel):
    username: str = Field(..., description="نام کاربری")
    first_name: str = Field(..., description="نام")
    last_name: str = Field(..., description="نام خانوادگی")
    email: Optional[str] = Field(None, description="پست الکترونیک سازمانی")
    department: Optional[str] = Field(None, description="واحد سازمانی، مثال: منابع انسانی، IT")
    role_id: str = Field(..., description="شناسه نقش")
    group_id: str = Field(..., description="شناسه گروه سازمانی")
    is_active: bool = Field(True, description="وضعیت فعال/غیرفعال بودن حساب")
    expires_at: Optional[str] = Field(None, description="تاریخ انقضای حساب کاربری (ISO Format)")
    default_model_id: Optional[str] = Field(None, description="مدل هوش مصنوعی پیش‌فرض اختصاصی کاربر")
    allow_model_selection: Optional[bool] = Field(None, description="مجوز انتخاب مدل (خالی یعنی ارث‌بری از گروه)")
    override_policy: Optional[str] = Field(None, description="سیاست پاسخگویی اختصاصی کاربر")
    custom_daily_limit: Optional[int] = Field(None, description="سهمیه روزانه اختصاصی")
    custom_monthly_limit: Optional[int] = Field(None, description="سهمیه ماهانه اختصاصی")
    can_upload_files: bool = Field(True, description="مجوز ارسال فایل در چت")

class UserCreate(UserBase):
    password: Optional[str] = Field(None, description="رمز عبور برای کاربران محلی (برای AD اختیاری است)")
    auth_type: str = Field("LOCAL", description="نوع احراز هویت: LOCAL یا ACTIVE_DIRECTORY")

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role_id: Optional[str] = None
    group_id: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[str] = None
    default_model_id: Optional[str] = None
    allow_model_selection: Optional[bool] = None
    override_policy: Optional[str] = None
    custom_daily_limit: Optional[int] = None
    custom_monthly_limit: Optional[int] = None
    can_upload_files: Optional[bool] = None
    password: Optional[str] = Field(None, description="رمز عبور جدید در صورت نیاز به تغییر")

class UserListItem(BaseModel):
    id: str
    username: str
    first_name: str
    last_name: str
    email: Optional[str]
    auth_type: str
    department: Optional[str]
    is_active: bool
    role_id: Optional[str]
    role_name: Optional[str]
    role_title: Optional[str]
    group_id: Optional[str]
    group_name: Optional[str]
    override_policy: Optional[str]
    effective_policy: str
    custom_daily_limit: Optional[int]
    effective_daily_limit: int
    can_upload_files: bool
    expires_at: Optional[str]
    created_at: str

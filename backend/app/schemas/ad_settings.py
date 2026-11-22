"""
Active Directory Settings Data Schemas
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class ADConfigBase(BaseModel):
    is_enabled: bool = Field(False, description="فعال یا غیرفعال بودن احراز هویت Active Directory")
    server_host: str = Field(..., description="آدرس سرور کنترلر دامنه (Domain Controller IP or Hostname)")
    port: int = Field(389, description="پورت استاندارد LDAP")
    port_ssl: int = Field(636, description="پورت امن LDAPS")
    use_ssl: bool = Field(False, description="استفاده از پروتکل امن LDAPS")
    domain_name: str = Field(..., description="نام دامنه سازمان، مثال: enterprise.local")
    base_dn: str = Field(..., description="Base DN، مثال: DC=enterprise,DC=local")
    user_search_base: Optional[str] = Field(None, description="مسیر جستجوی کاربران، مثال: OU=Users,DC=enterprise,DC=local")
    group_search_base: Optional[str] = Field(None, description="مسیر جستجوی گروه‌ها")
    bind_dn: Optional[str] = Field(None, description="حساب کاربری سرویس جهت اتصال (Bind Account)")
    allowed_groups: List[str] = Field(default_factory=list, description="گروه‌های مجاز جهت ورود به سامانه")
    group_role_mapping: Dict[str, str] = Field(default_factory=dict, description="نگاشت گروه‌های AD به نقش‌های سامانه")
    auto_provision: bool = Field(True, description="ایجاد خودکار پروفایل در اولین ورود موفق")

class ADConfigUpdate(ADConfigBase):
    bind_password: Optional[str] = Field(None, description="رمز عبور حساب Bind (اختیاری در زمان به‌روزرسانی)")

class ADConfigResponse(ADConfigBase):
    id: str
    has_bind_password: bool = Field(..., description="آیا رمز عبور Bind قبلا ذخیره شده است")
    updated_at: str

class ADTestConnectionRequest(BaseModel):
    server_host: str
    port: int = 389
    use_ssl: bool = False
    domain_name: Optional[str] = None
    bind_dn: Optional[str] = None
    bind_password: Optional[str] = None

class ADTestConnectionResponse(BaseModel):
    success: bool
    message: str

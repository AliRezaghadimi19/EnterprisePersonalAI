"""
System Settings Schemas
"""

from typing import Optional
from pydantic import BaseModel, Field

class SystemSettingsDTO(BaseModel):
    auth_mode: str = Field("BOTH", description="حالت ورود: BOTH, LOCAL_ONLY, AD_ONLY")
    default_response_policy: str = Field("HYBRID", description="سیاست پاسخگویی پیش‌فرض سامانه: KNOWLEDGE_ONLY, HYBRID, FREE_AI")
    default_ai_language: str = Field("fa", description="زبان پیش‌فرض پاسخگویی هوش مصنوعی")
    max_file_size_mb: int = Field(25, description="حداکثر حجم مجاز فایل‌ها (مگابایت)")
    allow_file_upload_globally: bool = Field(True, description="فعال بودن ارسال فایل در کل سامانه")
    session_timeout_minutes: int = Field(480, description="مدت زمان اعتبار سشن (دقیقه)")

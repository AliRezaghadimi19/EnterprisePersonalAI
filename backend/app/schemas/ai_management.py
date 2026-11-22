"""
AI Gateway & Model Management Data Schemas (Phase 3)
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
# AI Provider Schemas
# ------------------------------------------------------------------------------

class AIProviderBase(BaseModel):
    name: str = Field(..., description="نام نمایشی ارائه‌دهنده، مثال: سرویس رسمی OpenAI")
    provider_type: str = Field(..., description="نوع سرویس: OPENAI, ANTHROPIC, GEMINI, CUSTOM, OPENAI_COMPATIBLE")
    base_url: Optional[str] = Field(None, description="آدرس اختصاصی API Endpoint در صورت نیاز")
    is_active: bool = Field(True, description="فعال یا غیرفعال بودن ارائه‌دهنده")
    config_params: Dict[str, Any] = Field(default_factory=dict, description="تنظیمات اضافی (Organization ID, Headers)")

class AIProviderCreate(AIProviderBase):
    api_key: str = Field(..., description="کلید API ارائه‌دهنده (به صورت رمزنگاری‌شده ذخیره می‌شود)")

class AIProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = Field(None, description="کلید API جدید در صورت تمایل به تغییر")
    is_active: Optional[bool] = None
    config_params: Optional[Dict[str, Any]] = None

class AIProviderResponse(AIProviderBase):
    id: str
    masked_api_key: str = Field(..., description="کلید ماسک‌شده بدون افشای متن اصلی")
    created_at: str
    models_count: int = 0

class AIProviderTestRequest(BaseModel):
    provider_type: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    provider_id: Optional[str] = None

class AIProviderTestResponse(BaseModel):
    success: bool
    latency_ms: float
    message: str

# ------------------------------------------------------------------------------
# AI Model Schemas
# ------------------------------------------------------------------------------

class AIModelBase(BaseModel):
    provider_id: str = Field(..., description="شناسه ارائه‌دهنده هوش مصنوعی")
    model_identifier: str = Field(..., description="شناسه فنی مدل در API، مثال: gpt-4o, claude-3-5-sonnet-20241022, gemini-1.5-pro")
    display_name_fa: str = Field(..., description="نام نمایشی فارسی مدل")
    is_active: bool = Field(True, description="فعال بودن مدل در سامانه")
    is_default: bool = Field(False, description="تعیین به عنوان مدل پیش‌فرض سامانه")
    input_cost_per_k_tokens: float = Field(0.005, description="هزینه ورودی به ازای هر ۱۰۰۰ توکن ($)")
    output_cost_per_k_tokens: float = Field(0.015, description="هزینه خروجی به ازای هر ۱۰۰۰ توکن ($)")
    max_context_tokens: int = Field(32000, description="سقف پنجره کانتکست (Context Window)")
    fallback_model_id: Optional[str] = Field(None, description="شناسه مدل جایگزین در صورت بروز خطا")

class AIModelCreate(AIModelBase):
    pass

class AIModelUpdate(BaseModel):
    provider_id: Optional[str] = None
    model_identifier: Optional[str] = None
    display_name_fa: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    input_cost_per_k_tokens: Optional[float] = None
    output_cost_per_k_tokens: Optional[float] = None
    max_context_tokens: Optional[int] = None
    fallback_model_id: Optional[str] = None

class AIModelResponse(AIModelBase):
    id: str
    provider_name: str
    provider_type: str
    fallback_model_name: Optional[str] = None
    created_at: str

class ModelAccessMatrixUpdate(BaseModel):
    group_id: str
    allowed_model_ids: List[str]

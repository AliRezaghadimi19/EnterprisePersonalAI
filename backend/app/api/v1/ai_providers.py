"""
AI Provider Management API Endpoints (Phase 3)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_admin
from app.schemas.ai_management import (
    AIProviderCreate,
    AIProviderUpdate,
    AIProviderResponse,
    AIProviderTestRequest,
    AIProviderTestResponse
)
from app.services.ai_model_service import ai_model_service

router = APIRouter(prefix="/ai-providers", tags=["مدیریت ارائه‌دهندگان هوش مصنوعی"])

@router.get("", response_model=List[AIProviderResponse], summary="فهرست سرویس‌دهندگان هوش مصنوعی")
def get_providers(current_user: dict = Depends(require_admin)):
    return ai_model_service.list_providers()

@router.get("/{provider_id}", response_model=AIProviderResponse, summary="مشخصات ارائه‌دهنده")
def get_provider(provider_id: str, current_user: dict = Depends(require_admin)):
    return ai_model_service.get_provider_by_id(provider_id)

@router.post("", response_model=AIProviderResponse, status_code=status.HTTP_201_CREATED, summary="افزودن ارائه‌دهنده جدید")
def create_provider(body: AIProviderCreate, current_user: dict = Depends(require_admin)):
    return ai_model_service.create_provider(body, actor_user=current_user)

@router.put("/{provider_id}", response_model=AIProviderResponse, summary="ویرایش ارائه‌دهنده")
def update_provider(provider_id: str, body: AIProviderUpdate, current_user: dict = Depends(require_admin)):
    return ai_model_service.update_provider(provider_id, body, actor_user=current_user)

@router.delete("/{provider_id}", summary="حذف ارائه‌دهنده")
def delete_provider(provider_id: str, current_user: dict = Depends(require_admin)):
    ai_model_service.delete_provider(provider_id, actor_user=current_user)
    return {"success": True, "message": "ارائه‌دهنده هوش مصنوعی با موفقیت حذف شد."}

@router.post("/test-connection", response_model=AIProviderTestResponse, summary="تست ارتباط با ارائه‌دهنده")
def test_connection(body: AIProviderTestRequest, current_user: dict = Depends(require_admin)):
    return ai_model_service.test_provider_connection(
        provider_id=body.provider_id,
        provider_type=body.provider_type,
        api_key=body.api_key,
        base_url=body.base_url
    )

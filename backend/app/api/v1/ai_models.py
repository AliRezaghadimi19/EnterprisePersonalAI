"""
AI Models Management API Endpoints (Phase 3)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_admin, get_current_user
from app.schemas.ai_management import (
    AIModelCreate,
    AIModelUpdate,
    AIModelResponse,
    ModelAccessMatrixUpdate
)
from app.services.ai_model_service import ai_model_service

router = APIRouter(prefix="/ai-models", tags=["مدیریت مدل‌های زبانی هوش مصنوعی"])

@router.get("", response_model=List[AIModelResponse], summary="فهرست مدل‌های هوش مصنوعی")
def get_models(
    only_active: bool = Query(False, description="فقط مدل‌های فعال"),
    current_user: dict = Depends(require_admin)
):
    return ai_model_service.list_models(only_active=only_active)

@router.get("/my-available-models", summary="مدل‌های مجاز برای کاربر جاری بر اساس سیاست گروه")
def get_my_available_models(current_user: dict = Depends(get_current_user)):
    return ai_model_service.get_user_allowed_models(current_user["id"])

@router.get("/{model_id}", response_model=AIModelResponse, summary="مشخصات یک مدل")
def get_model(model_id: str, current_user: dict = Depends(require_admin)):
    return ai_model_service.get_model_by_id(model_id)

@router.post("", response_model=AIModelResponse, status_code=status.HTTP_201_CREATED, summary="ثبت مدل جدید")
def create_model(body: AIModelCreate, current_user: dict = Depends(require_admin)):
    return ai_model_service.create_model(body, actor_user=current_user)

@router.put("/{model_id}", response_model=AIModelResponse, summary="ویرایش مدل هوش مصنوعی")
def update_model(model_id: str, body: AIModelUpdate, current_user: dict = Depends(require_admin)):
    return ai_model_service.update_model(model_id, body, actor_user=current_user)

@router.delete("/{model_id}", summary="حذف مدل")
def delete_model(model_id: str, current_user: dict = Depends(require_admin)):
    ai_model_service.delete_model(model_id, actor_user=current_user)
    return {"success": True, "message": "مدل هوش مصنوعی با موفقیت حذف شد."}

@router.post("/group-access", summary="تنظیم مدل‌های مجاز برای یک گروه سازمانی")
def set_group_models(body: ModelAccessMatrixUpdate, current_user: dict = Depends(require_admin)):
    ai_model_service.set_group_allowed_models(body.group_id, body.allowed_model_ids, actor_user=current_user)
    return {"success": True, "message": "ماتریس دسترسی مدل‌ها برای گروه به‌روزرسانی شد."}

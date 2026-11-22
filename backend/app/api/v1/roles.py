"""
Roles and Permissions API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import require_admin, require_super_admin
from app.schemas.user_management import RoleCreate, RoleUpdate, RoleResponse
from app.services.role_service import role_service

router = APIRouter(prefix="/roles", tags=["نقش‌ها و سطح دسترسی"])

@router.get("", response_model=List[RoleResponse], summary="فهرست نقش‌های سامانه")
def get_roles(current_user: dict = Depends(require_admin)):
    """دریافت لیست تمام نقش‌های سیستمی و سفارشی به همراه ماتریس دسترسی."""
    return role_service.list_roles()

@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED, summary="ایجاد نقش سفارشی جدید")
def create_role(body: RoleCreate, current_user: dict = Depends(require_super_admin)):
    """تعریف نقش جدید در سیستم توسط مدیر کل."""
    return role_service.create_role(body, actor_user=current_user)

@router.put("/{role_id}", response_model=RoleResponse, summary="ویرایش نقش و مجوزها")
def update_role(role_id: str, body: RoleUpdate, current_user: dict = Depends(require_super_admin)):
    """به‌روزرسانی عنوان فارسی و مجوزهای یک نقش."""
    return role_service.update_role(role_id, body, actor_user=current_user)

@router.delete("/{role_id}", summary="حذف نقش سفارشی")
def delete_role(role_id: str, current_user: dict = Depends(require_super_admin)):
    """حذف نقش سفارشی (نقش‌های پایه سیستم قابل حذف نیستند)."""
    role_service.delete_role(role_id, actor_user=current_user)
    return {"success": True, "message": "نقش مورد نظر با موفقیت حذف گردید."}

"""
User Management API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_admin
from app.schemas.user_management import (
    UserCreate,
    UserUpdate,
    UserListItem
)
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["مدیریت کاربران"])

@router.get("", response_model=List[UserListItem], summary="فهرست کاربران سامانه با فیلتر پیشرفته")
def get_users(
    search: Optional[str] = Query(None, description="جستجو در نام، نام خانوادگی، نام کاربری یا ایمیل"),
    group_id: Optional[str] = Query(None, description="فیلتر بر اساس گروه سازمانی"),
    role_id: Optional[str] = Query(None, description="فیلتر بر اساس نقش"),
    is_active: Optional[bool] = Query(None, description="فیلتر بر اساس وضعیت فعال/غیرفعال"),
    auth_type: Optional[str] = Query(None, description="فیلتر بر اساس نوع احراز هویت (LOCAL یا ACTIVE_DIRECTORY)"),
    current_user: dict = Depends(require_admin)
):
    """دریافت فهرست کاربران با سهمیه‌ها و سیاست‌های مؤثر سلسله‌مراتبی."""
    return user_service.list_users(
        search=search,
        group_id=group_id,
        role_id=role_id,
        is_active=is_active,
        auth_type=auth_type
    )

@router.get("/{user_id}", summary="دریافت مشخصات کامل یک کاربر")
def get_user(user_id: str, current_user: dict = Depends(require_admin)):
    return user_service.get_user_by_id(user_id)

@router.post("", status_code=status.HTTP_201_CREATED, summary="ایجاد کاربر جدید")
def create_user(body: UserCreate, current_user: dict = Depends(require_admin)):
    """تعریف کاربر جدید (داخلی یا ثبت دستی کاربر اکتیو دایرکتوری)."""
    return user_service.create_user(body, actor_user=current_user)

@router.put("/{user_id}", summary="ویرایش اطلاعات کاربر")
def update_user(user_id: str, body: UserUpdate, current_user: dict = Depends(require_admin)):
    """ویرایش مشخصات، نقش، گروه، سهمیه اختصاصی یا رمز عبور کاربر."""
    return user_service.update_user(user_id, body, actor_user=current_user)

@router.patch("/{user_id}/toggle-status", summary="فعال یا غیرفعال کردن حساب کاربر")
def toggle_user_status(user_id: str, is_active: bool = Query(...), current_user: dict = Depends(require_admin)):
    """تغییر وضعیت فعال بودن کاربر با محافظت از تنها ادمین کل سامانه."""
    return user_service.update_user(user_id, UserUpdate(is_active=is_active), actor_user=current_user)

@router.delete("/{user_id}", summary="حذف کاربر")
def delete_user(user_id: str, current_user: dict = Depends(require_admin)):
    """حذف کاربر با قفل امنیتی روی حساب جاری و تنها مدیر کل."""
    user_service.delete_user(user_id, actor_user=current_user)
    return {"success": True, "message": "کاربر مورد نظر با موفقیت حذف شد."}

"""
Groups Management API Endpoints
"""

from typing import List
from fastapi import APIRouter, Depends, status

from app.api.deps import require_admin
from app.schemas.user_management import GroupCreate, GroupUpdate, GroupResponse
from app.services.group_service import group_service

router = APIRouter(prefix="/groups", tags=["مدیریت گروه‌ها"])

@router.get("", response_model=List[GroupResponse], summary="فهرست گروه‌های سازمانی")
def get_groups(current_user: dict = Depends(require_admin)):
    """دریافت لیست تمام گروه‌ها به همراه تعداد اعضا و سهمیه‌های مربوطه."""
    return group_service.list_groups()

@router.get("/{group_id}", response_model=GroupResponse, summary="مشخصات یک گروه")
def get_group(group_id: str, current_user: dict = Depends(require_admin)):
    return group_service.get_group_by_id(group_id)

@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED, summary="ایجاد گروه جدید")
def create_group(body: GroupCreate, current_user: dict = Depends(require_admin)):
    """تعریف گروه سازمانی جدید با سهمیه‌ها و محدودیت‌های اختصاصی."""
    return group_service.create_group(body, actor_user=current_user)

@router.put("/{group_id}", response_model=GroupResponse, summary="ویرایش مشخصات گروه")
def update_group(group_id: str, body: GroupUpdate, current_user: dict = Depends(require_admin)):
    """به‌روزرسانی تنظیمات سهمیه، مدل پیش‌فرض و فرمت‌های مجاز یک گروه."""
    return group_service.update_group(group_id, body, actor_user=current_user)

@router.delete("/{group_id}", summary="حذف گروه")
def delete_group(group_id: str, current_user: dict = Depends(require_admin)):
    """حذف گروه سازمانی (در صورت نداشتن کاربر عضو)."""
    group_service.delete_group(group_id, actor_user=current_user)
    return {"success": True, "message": "گروه با موفقیت حذف گردید."}

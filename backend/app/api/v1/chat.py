"""
Enterprise Chat API Endpoints (Phase 5)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user
from app.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationListItem,
    ConversationDetail,
    SendMessageRequest,
    SendMessageResponse
)
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["سامانه چت و گفتگوی هوشمند"])

@router.get("/conversations", response_model=List[ConversationListItem], summary="فهرست گفتگوهای کاربر جاری")
def get_conversations(current_user: dict = Depends(get_current_user)):
    return chat_service.list_user_conversations(current_user["id"])

@router.post("/conversations", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED, summary="ایجاد گفتگوی جدید")
def create_conversation(body: ConversationCreate, current_user: dict = Depends(get_current_user)):
    return chat_service.create_conversation(current_user["id"], body)

@router.get("/conversations/{conversation_id}", response_model=ConversationDetail, summary="دریافت تاریخچه پیام‌های یک گفتگو")
def get_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    return chat_service.get_conversation_detail(conversation_id, current_user["id"])

@router.patch("/conversations/{conversation_id}/pin", summary="سنجاق کردن یا برداشتن سنجاق گفتگو")
def toggle_pin(conversation_id: str, current_user: dict = Depends(get_current_user)):
    is_pinned = chat_service.toggle_pin_conversation(conversation_id, current_user["id"])
    return {"success": True, "is_pinned": is_pinned}

@router.delete("/conversations/{conversation_id}", summary="حذف یک گفتگو و پیام‌های آن")
def delete_conversation(conversation_id: str, current_user: dict = Depends(get_current_user)):
    chat_service.delete_conversation(conversation_id, current_user["id"])
    return {"success": True, "message": "گفتگو با موفقیت حذف شد."}

@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse, summary="ارسال پیام کاربر و دریافت پاسخ هوشمند")
def send_message(conversation_id: str, body: SendMessageRequest, current_user: dict = Depends(get_current_user)):
    return chat_service.send_message(conversation_id, current_user["id"], body)

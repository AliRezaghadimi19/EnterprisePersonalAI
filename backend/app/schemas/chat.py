"""
Enterprise Chat & Conversation Schemas (Phase 5)
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
            def _to_dict(val):
                if hasattr(val, 'model_dump'):
                    return val.model_dump(*args, **kwargs)
                elif isinstance(val, list):
                    return [_to_dict(x) for x in val]
                elif isinstance(val, dict):
                    return {k: _to_dict(v) for k, v in val.items()}
                return val
            return {k: _to_dict(v) for k, v in self.__dict__.items() if not k.startswith('_') and k not in exclude}
    def Field(default=None, default_factory=None, description=""):
        if default_factory is not None:
            return default_factory()
        return default

# ------------------------------------------------------------------------------
# Citation Schema
# ------------------------------------------------------------------------------

class CitationItem(BaseModel):
    document_id: str
    document_title: str
    category_name: str
    chunk_index: int
    content_snippet: str
    similarity_score: float

# ------------------------------------------------------------------------------
# Message Schemas
# ------------------------------------------------------------------------------

class MessageItem(BaseModel):
    id: str
    conversation_id: str
    sender_role: str = Field(..., description="'user' یا 'assistant'")
    content: str
    model_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    processing_time_sec: float = 0.0
    response_policy_used: Optional[str] = None
    citations: List[CitationItem] = Field(default_factory=list)
    created_at: str

class SendMessageRequest(BaseModel):
    content: str = Field(..., description="متن پیام کاربر")
    model_id: Optional[str] = Field(None, description="شناسه مدل انتخابی در صورت مجاز بودن")
    category_id: Optional[str] = Field(None, description="محدودسازی به پایگاه دانش خاص")

class SendMessageResponse(BaseModel):
    message: MessageItem
    daily_quota_remaining: int
    monthly_quota_remaining: int

# ------------------------------------------------------------------------------
# Conversation Schemas
# ------------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, description="عنوان گفتگو (در صورت خالی بودن خودکار تولید می‌شود)")
    model_id: Optional[str] = Field(None, description="مدل پیش‌فرض این گفتگو")

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None

class ConversationListItem(BaseModel):
    id: str
    title: str
    model_id: Optional[str] = None
    is_pinned: bool = False
    messages_count: int = 0
    last_message_preview: Optional[str] = None
    created_at: str
    updated_at: str

class ConversationDetail(BaseModel):
    id: str
    title: str
    model_id: Optional[str] = None
    is_pinned: bool = False
    messages: List[MessageItem]
    created_at: str
    updated_at: str

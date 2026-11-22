"""
Enterprise Knowledge Base & RAG Schemas (Phase 4)
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
# Category Schemas
# ------------------------------------------------------------------------------

class KnowledgeCategoryBase(BaseModel):
    name: str = Field(..., description="نام دسته‌بندی دانش (مثال: آیین‌نامه‌ها، منابع انسانی، مستندات فنی)")
    description: Optional[str] = Field(None, description="توضیحات دسته‌بندی")

class KnowledgeCategoryCreate(KnowledgeCategoryBase):
    pass

class KnowledgeCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class KnowledgeCategoryResponse(KnowledgeCategoryBase):
    id: str
    documents_count: int = 0
    created_at: str

# ------------------------------------------------------------------------------
# Document Schemas
# ------------------------------------------------------------------------------

class KnowledgeDocumentBase(BaseModel):
    category_id: str = Field(..., description="شناسه دسته‌بندی مربوطه")
    title: str = Field(..., description="عنوان سند یا سوال متداول")
    document_type: str = Field("FAQ", description="نوع سند: FAQ, TXT, PDF, DOCX, POLICY")
    content_text: str = Field(..., description="متن کامل سند یا محتوای پرسش و پاسخ")
    status: str = Field("APPROVED", description="وضعیت تایید سند: PENDING, APPROVED, REJECTED")

class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass

class KnowledgeDocumentUpdate(BaseModel):
    category_id: Optional[str] = None
    title: Optional[str] = None
    document_type: Optional[str] = None
    content_text: Optional[str] = None
    status: Optional[str] = None

class KnowledgeChunkItem(BaseModel):
    id: str
    chunk_index: int
    chunk_content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    id: str
    category_name: str
    version: int = 1
    chunks_count: int = 0
    created_by: Optional[str] = None
    created_at: str

# ------------------------------------------------------------------------------
# Semantic Search Schemas
# ------------------------------------------------------------------------------

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., description="عبارت جستجو یا پرسش کاربر")
    category_id: Optional[str] = Field(None, description="محدودسازی به دسته‌بندی خاص")
    top_k: int = Field(5, description="حداکثر تعداد نتایج بازیابی‌شده")
    min_similarity: float = Field(0.1, description="حداقل آستانه شباهت معنایی")

class SemanticSearchResultItem(BaseModel):
    document_id: str
    document_title: str
    category_id: str
    category_name: str
    chunk_id: str
    chunk_index: int
    content: str
    similarity_score: float

class SemanticSearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SemanticSearchResultItem]

"""
Knowledge Base & Semantic Search API Endpoints (Phase 4)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_admin, get_current_user
from app.schemas.knowledge import (
    KnowledgeCategoryCreate,
    KnowledgeCategoryUpdate,
    KnowledgeCategoryResponse,
    KnowledgeDocumentCreate,
    KnowledgeDocumentUpdate,
    KnowledgeDocumentResponse,
    SemanticSearchRequest,
    SemanticSearchResponse
)
from app.services.knowledge_service import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["پایگاه دانش سازمانی و بازیابی معنایی"])

# ------------------------------------------------------------------------------
# Categories Endpoints
# ------------------------------------------------------------------------------

@router.get("/categories", response_model=List[KnowledgeCategoryResponse], summary="فهرست دسته‌بندی‌های پایگاه دانش")
def get_categories(current_user: dict = Depends(get_current_user)):
    return knowledge_service.list_categories()

@router.post("/categories", response_model=KnowledgeCategoryResponse, status_code=status.HTTP_201_CREATED, summary="ایجاد دسته‌بندی جدید")
def create_category(body: KnowledgeCategoryCreate, current_user: dict = Depends(require_admin)):
    return knowledge_service.create_category(body, actor_user=current_user)

@router.delete("/categories/{category_id}", summary="حذف دسته‌بندی")
def delete_category(category_id: str, current_user: dict = Depends(require_admin)):
    knowledge_service.delete_category(category_id, actor_user=current_user)
    return {"success": True, "message": "دسته‌بندی با موفقیت حذف شد."}

# ------------------------------------------------------------------------------
# Documents Endpoints
# ------------------------------------------------------------------------------

@router.get("/documents", response_model=List[KnowledgeDocumentResponse], summary="فهرست اسناد پایگاه دانش")
def get_documents(
    category_id: Optional[str] = Query(None, description="فیلتر بر اساس دسته‌بندی"),
    status: Optional[str] = Query(None, description="فیلتر بر اساس وضعیت (APPROVED, PENDING, REJECTED)"),
    search: Optional[str] = Query(None, description="جستجو در عنوان یا متن سند"),
    current_user: dict = Depends(get_current_user)
):
    return knowledge_service.list_documents(category_id=category_id, status=status, search=search)

@router.get("/documents/{document_id}", response_model=KnowledgeDocumentResponse, summary="دریافت مشخصات کامل یک سند")
def get_document(document_id: str, current_user: dict = Depends(get_current_user)):
    return knowledge_service.get_document_by_id(document_id)

@router.post("/documents", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED, summary="ایجاد و ایندکس سند جدید")
def create_document(body: KnowledgeDocumentCreate, current_user: dict = Depends(require_admin)):
    return knowledge_service.create_document(body, actor_user=current_user)

@router.put("/documents/{document_id}", response_model=KnowledgeDocumentResponse, summary="ویرایش سند و بازایندکس چانک‌ها")
def update_document(document_id: str, body: KnowledgeDocumentUpdate, current_user: dict = Depends(require_admin)):
    return knowledge_service.update_document(document_id, body, actor_user=current_user)

@router.delete("/documents/{document_id}", summary="حذف سند و چانک‌های برداری آن")
def delete_document(document_id: str, current_user: dict = Depends(require_admin)):
    knowledge_service.delete_document(document_id, actor_user=current_user)
    return {"success": True, "message": "سند و چانک‌های مرتبط با موفقیت حذف شدند."}

# ------------------------------------------------------------------------------
# Semantic Search (RAG) Endpoint
# ------------------------------------------------------------------------------

@router.post("/search", response_model=SemanticSearchResponse, summary="جستجوی معنایی و بازیابی چانک‌ها (RAG)")
def search_knowledge_base(body: SemanticSearchRequest, current_user: dict = Depends(get_current_user)):
    return knowledge_service.semantic_search(body)

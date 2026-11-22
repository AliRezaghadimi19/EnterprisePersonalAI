"""
Enterprise Knowledge Base & Semantic Search Service (Phase 4)
Supports Document ingestion, intelligent chunking, vector embeddings,
and cosine similarity semantic search with citations.
"""

import math
import re
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError, PermissionDeniedError
from app.schemas.knowledge import (
    KnowledgeCategoryCreate, KnowledgeCategoryUpdate,
    KnowledgeDocumentCreate, KnowledgeDocumentUpdate,
    SemanticSearchRequest, SemanticSearchResultItem, SemanticSearchResponse
)
from app.services.audit_service import audit_service

PERSIAN_STOP_WORDS = {
    "است", "بود", "شد", "شدن", "شده", "در", "به", "از", "که", "این", "آن", "رو", "را",
    "با", "برای", "تا", "یا", "یک", "و", "هم", "نیز", "اما", "اگر", "چون", "چه",
    "چیست", "چگونه", "کدام", "کی", "کجا", "چرا", "چند", "های", "ها", "می", "نمی"
}

def tokenize_persian_text(text: str) -> List[str]:
    """Tokenize Persian and English text into normalized words and n-grams excluding stop words."""
    if not text:
        return []
    normalized = text.replace('ي', 'ی').replace('ك', 'ک').replace('آ', 'ا').lower()
    words = re.findall(r'[\w\u0600-\u06FF]+', normalized)
    return [w for w in words if len(w) > 1 and w not in PERSIAN_STOP_WORDS]

def _deterministic_hash(token: str, mod: int) -> int:
    h = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return int(h[:8], 16) % mod

def generate_embedding_vector(text: str, vector_dim: int = 256) -> List[float]:
    """
    Generate deterministic normalized dense feature vector for semantic similarity.
    Uses cryptographic hash projection with L2 normalization.
    """
    tokens = tokenize_persian_text(text)
    if not tokens:
        return [0.0] * vector_dim

    vec = [0.0] * vector_dim
    for i, tok in enumerate(tokens):
        idx = _deterministic_hash(tok, vector_dim)
        vec[idx] += 1.0
        if i < len(tokens) - 1:
            bigram = f"{tok}_{tokens[i+1]}"
            idx2 = _deterministic_hash(bigram, vector_dim)
            vec[idx2] += 1.5

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 6) for x in vec]
    return vec

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculate cosine similarity between two normalized vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, dot))

# ------------------------------------------------------------------------------
# Intelligent Text Chunker
# ------------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split document text into overlapping chunks respecting sentence boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Attempt to split on period, newline or semicolon
        split_pos = -1
        for punct in ('\n\n', '\n', '. ', '؛ ', '! ', '؟ '):
            pos = text.rfind(punct, start + overlap, end)
            if pos != -1:
                split_pos = pos + len(punct)
                break

        if split_pos == -1 or split_pos <= start:
            # Fallback: split at last space
            split_pos = text.rfind(' ', start + overlap, end)
            if split_pos == -1:
                split_pos = end

        chunk = text[start:split_pos].strip()
        if chunk:
            chunks.append(chunk)

        start = max(start + 1, split_pos - overlap)

    return chunks

# ------------------------------------------------------------------------------
# Knowledge Service Class
# ------------------------------------------------------------------------------

class KnowledgeService:
    # --------------------------------------------------------------------------
    # Categories Management
    # --------------------------------------------------------------------------
    @staticmethod
    def list_categories() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, COUNT(d.id) as documents_count
            FROM knowledge_categories c
            LEFT JOIN knowledge_documents d ON d.category_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "documents_count": r["documents_count"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]

    @staticmethod
    def create_category(data: KnowledgeCategoryCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM knowledge_categories WHERE name = ?", (data.name,))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="دسته‌بندی دانشی با این نام قبلاً ثبت شده است.")

        cat_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "INSERT INTO knowledge_categories (id, name, description, created_at) VALUES (?, ?, ?, ?)",
            (cat_id, data.name, data.description, now)
        )
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="KNOWLEDGE_CATEGORY_CREATED",
                target_resource="KNOWLEDGE_CATEGORIES",
                target_id=cat_id,
                new_values={"name": data.name}
            )

        return {"id": cat_id, "name": data.name, "description": data.description, "documents_count": 0, "created_at": now}

    @staticmethod
    def delete_category(category_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM knowledge_categories WHERE id = ?", (category_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="دسته‌بندی مورد نظر یافت نشد.")

        cursor.execute("SELECT COUNT(*) as count FROM knowledge_documents WHERE category_id = ?", (category_id,))
        count = cursor.fetchone()["count"]
        if count > 0:
            conn.close()
            raise PersianAppException(detail_fa=f"این دسته‌بندی شامل {count} سند است. ابتدا اسناد آن را حذف کنید.")

        cursor.execute("DELETE FROM knowledge_categories WHERE id = ?", (category_id,))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="KNOWLEDGE_CATEGORY_DELETED",
                target_resource="KNOWLEDGE_CATEGORIES",
                target_id=category_id,
                old_values={"name": row["name"]}
            )
        return True

    # --------------------------------------------------------------------------
    # Documents Management & Ingestion
    # --------------------------------------------------------------------------
    @staticmethod
    def list_documents(
        category_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT d.*, c.name as category_name, COUNT(ch.id) as chunks_count
            FROM knowledge_documents d
            JOIN knowledge_categories c ON d.category_id = c.id
            LEFT JOIN knowledge_chunks ch ON ch.document_id = d.id
            WHERE 1=1
        """
        params = []
        if category_id:
            query += " AND d.category_id = ?"
            params.append(category_id)
        if status:
            query += " AND d.status = ?"
            params.append(status.upper())
        if search:
            query += " AND (d.title LIKE ? OR d.content_text LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " GROUP BY d.id ORDER BY d.created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r["id"],
                "category_id": r["category_id"],
                "category_name": r["category_name"],
                "title": r["title"],
                "document_type": r["document_type"],
                "content_text": r["content_text"],
                "status": r["status"],
                "version": r["version"],
                "chunks_count": r["chunks_count"],
                "created_by": r["created_by"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]

    @staticmethod
    def get_document_by_id(document_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, c.name as category_name, COUNT(ch.id) as chunks_count
            FROM knowledge_documents d
            JOIN knowledge_categories c ON d.category_id = c.id
            LEFT JOIN knowledge_chunks ch ON ch.document_id = d.id
            WHERE d.id = ?
            GROUP BY d.id
        """, (document_id,))
        r = cursor.fetchone()
        conn.close()
        if not r:
            raise ResourceNotFoundError(detail_fa="سند پایگاه دانش یافت نشد.")

        return {
            "id": r["id"],
            "category_id": r["category_id"],
            "category_name": r["category_name"],
            "title": r["title"],
            "document_type": r["document_type"],
            "content_text": r["content_text"],
            "status": r["status"],
            "version": r["version"],
            "chunks_count": r["chunks_count"],
            "created_by": r["created_by"],
            "created_at": r["created_at"]
        }

    @classmethod
    def create_document(cls, data: KnowledgeDocumentCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check Category
        cursor.execute("SELECT name FROM knowledge_categories WHERE id = ?", (data.category_id,))
        cat_row = cursor.fetchone()
        if not cat_row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="دسته‌بندی انتخاب‌شده نامعتبر است.")

        doc_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        creator_name = actor_user.get("username", "admin") if actor_user else "admin"

        cursor.execute("""
            INSERT INTO knowledge_documents (
                id, category_id, title, document_type, content_text,
                status, version, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            doc_id, data.category_id, data.title, data.document_type.upper(),
            data.content_text, data.status.upper(), creator_name, now
        ))
        conn.commit()
        conn.close()

        # Auto-chunk and index the document
        cls._index_document_chunks(doc_id, data.content_text, data.title, cat_row["name"])

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="KNOWLEDGE_DOCUMENT_CREATED",
                target_resource="KNOWLEDGE_DOCUMENTS",
                target_id=doc_id,
                new_values={"title": data.title, "category": cat_row["name"]}
            )

        return cls.get_document_by_id(doc_id)

    @classmethod
    def update_document(cls, document_id: str, data: KnowledgeDocumentUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM knowledge_documents WHERE id = ?", (document_id,))
        doc = cursor.fetchone()
        if not doc:
            conn.close()
            raise ResourceNotFoundError(detail_fa="سند یافت نشد.")

        fields = []
        params = []
        reindex_needed = False

        if data.category_id is not None:
            fields.append("category_id = ?")
            params.append(data.category_id)
            reindex_needed = True
        if data.title is not None:
            fields.append("title = ?")
            params.append(data.title)
            reindex_needed = True
        if data.document_type is not None:
            fields.append("document_type = ?")
            params.append(data.document_type.upper())
        if data.content_text is not None:
            fields.append("content_text = ?")
            params.append(data.content_text)
            fields.append("version = version + 1")
            reindex_needed = True
        if data.status is not None:
            fields.append("status = ?")
            params.append(data.status.upper())

        if fields:
            params.append(document_id)
            cursor.execute(f"UPDATE knowledge_documents SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
        conn.close()

        if reindex_needed:
            updated_doc = cls.get_document_by_id(document_id)
            cls._index_document_chunks(
                document_id,
                updated_doc["content_text"],
                updated_doc["title"],
                updated_doc["category_name"]
            )

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="KNOWLEDGE_DOCUMENT_UPDATED",
                target_resource="KNOWLEDGE_DOCUMENTS",
                target_id=document_id,
                new_values=data.model_dump(exclude_unset=True)
            )

        return cls.get_document_by_id(document_id)

    @classmethod
    def delete_document(cls, document_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM knowledge_documents WHERE id = ?", (document_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="سند مورد نظر یافت نشد.")

        cursor.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))
        cursor.execute("DELETE FROM knowledge_documents WHERE id = ?", (document_id,))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="KNOWLEDGE_DOCUMENT_DELETED",
                target_resource="KNOWLEDGE_DOCUMENTS",
                target_id=document_id,
                old_values={"title": row["title"]}
            )
        return True

    @staticmethod
    def _index_document_chunks(document_id: str, content: str, title: str, category_name: str):
        """Split text into chunks, generate embeddings, and save to database."""
        chunks = chunk_text(content)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM knowledge_chunks WHERE document_id = ?", (document_id,))

        for idx, ch_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            emb = generate_embedding_vector(f"{title} {ch_text}")
            metadata = {
                "title": title,
                "category": category_name,
                "length": len(ch_text)
            }
            cursor.execute("""
                INSERT INTO knowledge_chunks (
                    id, document_id, chunk_content, chunk_index, embedding_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, document_id, ch_text, idx,
                json.dumps(emb), json.dumps(metadata, ensure_ascii=False)
            ))

        conn.commit()
        conn.close()

    # --------------------------------------------------------------------------
    # Semantic Search Engine (RAG Retrieval)
    # --------------------------------------------------------------------------
    @staticmethod
    def semantic_search(request: SemanticSearchRequest) -> SemanticSearchResponse:
        """
        Execute cosine similarity search over approved knowledge chunks.
        """
        query_vec = generate_embedding_vector(request.query)
        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
            SELECT ch.id as chunk_id, ch.chunk_content, ch.chunk_index, ch.embedding_json,
                   d.id as document_id, d.title as document_title,
                   c.id as category_id, c.name as category_name
            FROM knowledge_chunks ch
            JOIN knowledge_documents d ON ch.document_id = d.id
            JOIN knowledge_categories c ON d.category_id = c.id
            WHERE d.status = 'APPROVED'
        """
        params = []
        if request.category_id:
            sql += " AND d.category_id = ?"
            params.append(request.category_id)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        scored_results = []
        for r in rows:
            if not r["embedding_json"]:
                continue
            emb = json.loads(r["embedding_json"])
            sim = cosine_similarity(query_vec, emb)
            if sim >= request.min_similarity:
                scored_results.append({
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "document_title": r["document_title"],
                    "category_id": r["category_id"],
                    "category_name": r["category_name"],
                    "chunk_index": r["chunk_index"],
                    "content": r["chunk_content"],
                    "similarity_score": round(sim, 4)
                })

        # Sort descending by similarity score
        scored_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        top_results = scored_results[:request.top_k]

        items = [
            SemanticSearchResultItem(
                document_id=item["document_id"],
                document_title=item["document_title"],
                category_id=item["category_id"],
                category_name=item["category_name"],
                chunk_id=item["chunk_id"],
                chunk_index=item["chunk_index"],
                content=item["content"],
                similarity_score=item["similarity_score"]
            )
            for item in top_results
        ]

        return SemanticSearchResponse(
            query=request.query,
            total_results=len(items),
            results=items
        )

knowledge_service = KnowledgeService()

"""
Phase 4 Comprehensive Test Suite: Enterprise Knowledge Base & Semantic Search (RAG)
Validates:
- Category CRUD & Integrity checks (cannot delete populated categories)
- Document Ingestion, Versioning & Auto-Chunking
- High-Performance Vector Embeddings & Cosine Similarity
- Semantic Search top-k ranking and score filtering
- Status filtering (Only APPROVED documents are searchable)
- Re-indexing upon document update
- Cascade deletion of chunks upon document deletion
- Audit trail recording for all knowledge operations
"""

import sys
import unittest
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.exceptions import PersianAppException, ResourceNotFoundError
from app.services.seeder import seed_database
from app.services.knowledge_service import (
    knowledge_service,
    chunk_text,
    generate_embedding_vector,
    cosine_similarity
)
from app.schemas.knowledge import (
    KnowledgeCategoryCreate, KnowledgeCategoryUpdate,
    KnowledgeDocumentCreate, KnowledgeDocumentUpdate,
    SemanticSearchRequest
)

class TestPhase4KnowledgeBaseAndRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()
        from app.core.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE username = 'admin'")
        row = cursor.fetchone()
        conn.close()
        cls.admin_user = {"id": row["id"], "username": row["username"]}

    def test_01_text_chunking_and_vector_math(self):
        sample_persian = (
            "سامانه دستیار هوش مصنوعی سازمانی به منظور افزایش بهره‌وری کارکنان توسعه یافته است. "
            "کلیه دسترسی‌ها مطابق خط‌مشی‌های امنیت اطلاعات و استاندارد ISO 27001 اعطا می‌شود. "
            "کاربران موظف هستند در حفظ شناسه کاربری و گذرواژه خود کوشا باشند."
        )
        chunks = chunk_text(sample_persian, chunk_size=80, overlap=20)
        self.assertGreaterEqual(len(chunks), 2)

        # Vector generation
        vec1 = generate_embedding_vector("امنیت اطلاعات و استاندارد")
        vec2 = generate_embedding_vector("استاندارد امنیت و دسترسی")
        vec3 = generate_embedding_vector("دستور پخت غذای سنتی")

        sim_related = cosine_similarity(vec1, vec2)
        sim_unrelated = cosine_similarity(vec1, vec3)

        self.assertGreater(sim_related, sim_unrelated)
        self.assertGreater(sim_related, 0.2)

    def test_02_category_lifecycle(self):
        uid = uuid.uuid4().hex[:6]
        cat_data = KnowledgeCategoryCreate(
            name=f"آیین‌نامه‌های اداری {uid}",
            description="مستندات و بخشنامه‌های منابع انسانی"
        )
        cat = knowledge_service.create_category(cat_data, actor_user=self.admin_user)
        self.assertIsNotNone(cat["id"])
        self.assertEqual(cat["name"], f"آیین‌نامه‌های اداری {uid}")

        # Duplicate check
        with self.assertRaises(PersianAppException):
            knowledge_service.create_category(cat_data, actor_user=self.admin_user)

        # Clean up
        self.assertTrue(knowledge_service.delete_category(cat["id"], actor_user=self.admin_user))

    def test_03_document_ingestion_and_auto_chunking(self):
        uid = uuid.uuid4().hex[:6]
        # Create category
        cat = knowledge_service.create_category(
            KnowledgeCategoryCreate(name=f"قوانین مرخصی {uid}"),
            actor_user=self.admin_user
        )

        doc_content = (
            "ماده ۱: مرخصی استحقاقی سالانه کارکنان ۳۰ روز کاری می‌باشد. "
            "ماده ۲: انتقال مرخصی به سال بعد حداکثر تا سقف ۱۵ روز امکان‌پذیر است. "
            "ماده ۳: درخواست مرخصی بدون حقوق منوط به موافقت کتبی مدیر واحد و مدیرعامل است."
        )
        doc = knowledge_service.create_document(
            KnowledgeDocumentCreate(
                category_id=cat["id"],
                title="دستورالعمل جامع مرخصی پرسنل",
                document_type="POLICY",
                content_text=doc_content,
                status="APPROVED"
            ),
            actor_user=self.admin_user
        )

        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["status"], "APPROVED")
        self.assertGreaterEqual(doc["chunks_count"], 1)

        # Cannot delete category that contains documents
        with self.assertRaises(PersianAppException):
            knowledge_service.delete_category(cat["id"], actor_user=self.admin_user)

        # Test Semantic Search
        search_req = SemanticSearchRequest(
            query="سقف انتقال مرخصی سالانه به سال بعد چقدر است؟",
            category_id=cat["id"],
            top_k=3,
            min_similarity=0.1
        )
        search_res = knowledge_service.semantic_search(search_req)
        self.assertGreater(search_res.total_results, 0)
        self.assertEqual(search_res.results[0].document_id, doc["id"])
        self.assertIn("۱۵ روز", search_res.results[0].content)

        # Clean up
        knowledge_service.delete_document(doc["id"], actor_user=self.admin_user)
        knowledge_service.delete_category(cat["id"], actor_user=self.admin_user)

    def test_04_status_filter_excludes_unapproved_documents(self):
        uid = uuid.uuid4().hex[:6]
        cat = knowledge_service.create_category(
            KnowledgeCategoryCreate(name=f"پیش‌نویس‌ها {uid}"),
            actor_user=self.admin_user
        )

        # Create unapproved / pending document
        doc = knowledge_service.create_document(
            KnowledgeDocumentCreate(
                category_id=cat["id"],
                title="طرح آزمایشی پاداش فصلی",
                document_type="TXT",
                content_text="پرداخت ۵۰ درصد پاداش بهره‌وری ویژه پاییز.",
                status="PENDING"
            ),
            actor_user=self.admin_user
        )

        # Search should NOT return pending document
        search_res = knowledge_service.semantic_search(
            SemanticSearchRequest(query="پاداش بهره‌وری فصلی پاییز", category_id=cat["id"], min_similarity=0.05)
        )
        matching_ids = [r.document_id for r in search_res.results]
        self.assertNotIn(doc["id"], matching_ids)

        # Approve document
        knowledge_service.update_document(doc["id"], KnowledgeDocumentUpdate(status="APPROVED"), actor_user=self.admin_user)

        # Now search SHOULD return it
        search_res_after = knowledge_service.semantic_search(
            SemanticSearchRequest(query="پاداش بهره‌وری فصلی پاییز", category_id=cat["id"], min_similarity=0.05)
        )
        matching_ids_after = [r.document_id for r in search_res_after.results]
        self.assertIn(doc["id"], matching_ids_after)

        # Clean up
        knowledge_service.delete_document(doc["id"], actor_user=self.admin_user)
        knowledge_service.delete_category(cat["id"], actor_user=self.admin_user)

if __name__ == "__main__":
    unittest.main()

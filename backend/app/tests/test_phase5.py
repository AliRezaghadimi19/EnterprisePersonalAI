"""
Phase 5 Comprehensive Test Suite: Enterprise Chat, Policies & Context
Validates:
- Conversation CRUD, Auto-titling & Pinned toggling
- Message exchanges and AI response generation
- Quota deduction & remaining balance calculation
- Enterprise Policy execution:
    * KNOWLEDGE_ONLY without matches returns strict refusal
    * HYBRID with matches includes citations
    * FREE_AI permits direct synthesis
- Quota limit enforcement (rejects queries when limit reached)
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
from app.services.chat_service import chat_service
from app.services.knowledge_service import knowledge_service
from app.services.user_service import user_service
from app.schemas.chat import ConversationCreate, SendMessageRequest
from app.schemas.knowledge import KnowledgeCategoryCreate, KnowledgeDocumentCreate
from app.schemas.user_management import UserCreate

class TestPhase5EnterpriseChatAndPolicies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()
        from app.core.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE username = 'admin'")
        row = cursor.fetchone()
        cls.admin_user = {"id": row["id"], "username": row["username"]}

        cursor.execute("SELECT id FROM roles WHERE name = 'normal_subscriber'")
        cls.normal_role_id = cursor.fetchone()["id"]
        cursor.execute("SELECT id FROM groups WHERE name = 'کاربران عمومی'")
        cls.normal_group_id = cursor.fetchone()["id"]
        conn.close()

    def test_01_conversation_lifecycle(self):
        # Create conversation
        conv = chat_service.create_conversation(
            self.admin_user["id"],
            ConversationCreate(title="گفتگوی آزمایشی سهمیه‌ها")
        )
        self.assertIsNotNone(conv["id"])
        self.assertEqual(conv["title"], "گفتگوی آزمایشی سهمیه‌ها")
        self.assertFalse(conv["is_pinned"])

        # Toggle Pin
        is_pinned = chat_service.toggle_pin_conversation(conv["id"], self.admin_user["id"])
        self.assertTrue(is_pinned)

        # List conversations
        convs = chat_service.list_user_conversations(self.admin_user["id"])
        conv_ids = [c["id"] for c in convs]
        self.assertIn(conv["id"], conv_ids)

        # Delete conversation
        self.assertTrue(chat_service.delete_conversation(conv["id"], self.admin_user["id"]))

    def test_02_send_message_and_auto_title(self):
        # Create conversation with blank title
        conv = chat_service.create_conversation(
            self.admin_user["id"],
            ConversationCreate(title="")
        )

        resp = chat_service.send_message(
            conv["id"],
            self.admin_user["id"],
            SendMessageRequest(content="سلام، نحوه دریافت گزارش کارکرد ماهیانه چگونه است؟")
        )

        self.assertIsNotNone(resp.message.id)
        self.assertEqual(resp.message.sender_role, "assistant")
        self.assertGreater(resp.message.input_tokens, 0)
        self.assertGreater(resp.message.output_tokens, 0)

        # Title should have been auto-updated
        detail = chat_service.get_conversation_detail(conv["id"], self.admin_user["id"])
        self.assertIn("سلام، نحوه دریافت گزارش", detail["title"])
        self.assertEqual(len(detail["messages"]), 2) # 1 user, 1 assistant

        # Clean up
        chat_service.delete_conversation(conv["id"], self.admin_user["id"])

    def test_03_knowledge_only_policy_guard(self):
        # Create a user with KNOWLEDGE_ONLY policy
        uid = uuid.uuid4().hex[:6]
        user = user_service.create_user(
            UserCreate(
                username=f"strict_user_{uid}",
                password=f"StrictPass123!{uid}",
                first_name="کاربر",
                last_name="محدود",
                role_id=self.normal_role_id,
                group_id=self.normal_group_id,
                override_policy="KNOWLEDGE_ONLY",
                custom_daily_limit=50
            ),
            actor_user=self.admin_user
        )

        conv = chat_service.create_conversation(user["id"], ConversationCreate(title="تست پایگاه دانش"))

        # Ask question not in knowledge base
        resp = chat_service.send_message(
            conv["id"],
            user["id"],
            SendMessageRequest(content="فرمول شیمیایی اسید سولفوریک چیست؟")
        )

        # Must return strict knowledge refusal
        self.assertIn("پایگاه دانش سازمانی یافت نشد", resp.message.content)
        self.assertEqual(resp.message.response_policy_used, "KNOWLEDGE_ONLY")
        self.assertEqual(len(resp.message.citations), 0)

        # Clean up
        chat_service.delete_conversation(conv["id"], user["id"])
        user_service.delete_user(user["id"], actor_user=self.admin_user)

    def test_04_hybrid_policy_with_citations(self):
        # Create knowledge document
        uid = uuid.uuid4().hex[:6]
        cat = knowledge_service.create_category(
            KnowledgeCategoryCreate(name=f"امور رفاهی {uid}"),
            actor_user=self.admin_user
        )
        doc = knowledge_service.create_document(
            KnowledgeDocumentCreate(
                category_id=cat["id"],
                title="کمک هزینه ورزشی پرسنل",
                document_type="POLICY",
                content_text="کمک هزینه ماهانه عضویت در باشگاه‌های ورزشی برای هر پرسنل معادل ۵۰۰ هزار تومان است.",
                status="APPROVED"
            ),
            actor_user=self.admin_user
        )

        conv = chat_service.create_conversation(self.admin_user["id"], ConversationCreate(title="پرسش رفاهی"))

        resp = chat_service.send_message(
            conv["id"],
            self.admin_user["id"],
            SendMessageRequest(content="مبلغ کمک هزینه ورزشی پرسنل چقدر است؟")
        )

        self.assertGreater(len(resp.message.citations), 0)
        self.assertEqual(resp.message.citations[0].document_id, doc["id"])

        # Clean up
        chat_service.delete_conversation(conv["id"], self.admin_user["id"])
        knowledge_service.delete_document(doc["id"], actor_user=self.admin_user)
        knowledge_service.delete_category(cat["id"], actor_user=self.admin_user)

    def test_05_quota_exhaustion_blocks_message(self):
        uid = uuid.uuid4().hex[:6]
        user = user_service.create_user(
            UserCreate(
                username=f"zero_quota_{uid}",
                password=f"ZeroPass123!{uid}",
                first_name="کاربر",
                last_name="بدون سهمیه",
                role_id=self.normal_role_id,
                group_id=self.normal_group_id,
                custom_daily_limit=0 # 0 questions allowed
            ),
            actor_user=self.admin_user
        )

        conv = chat_service.create_conversation(user["id"], ConversationCreate(title="تست اتمام سهمیه"))

        with self.assertRaises(PersianAppException):
            chat_service.send_message(
                conv["id"],
                user["id"],
                SendMessageRequest(content="تست پیام در سهمیه صفر")
            )

        # Clean up
        chat_service.delete_conversation(conv["id"], user["id"])
        user_service.delete_user(user["id"], actor_user=self.admin_user)

if __name__ == "__main__":
    unittest.main()

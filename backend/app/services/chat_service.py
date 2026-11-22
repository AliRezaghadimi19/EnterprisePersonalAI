"""
Enterprise Chat, Context & Policy Enforcement Service (Phase 5)
Handles:
- Conversations CRUD & Title auto-generation
- Conversation history tracking
- Quota enforcement (daily & monthly question limits)
- Enterprise policy execution (KNOWLEDGE_ONLY, HYBRID, FREE_AI)
- Context augmentation with Semantic Citations (RAG)
"""

import time
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError, PermissionDeniedError
from app.schemas.chat import (
    ConversationCreate, ConversationUpdate, ConversationListItem, ConversationDetail,
    MessageItem, CitationItem, SendMessageRequest, SendMessageResponse
)
from app.schemas.knowledge import SemanticSearchRequest
from app.services.knowledge_service import knowledge_service
from app.services.ai_gateway.gateway import ai_gateway
from app.services.ai_model_service import ai_model_service
from app.services.user_service import user_service

class ChatService:
    # --------------------------------------------------------------------------
    # Conversations Management
    # --------------------------------------------------------------------------
    @staticmethod
    def list_user_conversations(user_id: str) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, COUNT(m.id) as messages_count,
                   (SELECT content FROM messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) as last_preview
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.is_pinned DESC, c.updated_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r["id"],
                "title": r["title"],
                "model_id": r["model_id"],
                "is_pinned": bool(r["is_pinned"]),
                "messages_count": r["messages_count"],
                "last_message_preview": r["last_preview"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            }
            for r in rows
        ]

    @staticmethod
    def create_conversation(user_id: str, data: ConversationCreate) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        title = data.title.strip() if data.title and data.title.strip() else "گفتگوی جدید"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversations (id, user_id, model_id, title, is_pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)
        """, (conv_id, user_id, data.model_id, title, now, now))
        conn.commit()
        conn.close()

        return {
            "id": conv_id,
            "title": title,
            "model_id": data.model_id,
            "is_pinned": False,
            "messages": [],
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def get_conversation_detail(conversation_id: str, user_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        conv = cursor.fetchone()
        if not conv:
            conn.close()
            raise ResourceNotFoundError(detail_fa="گفتگوی مورد نظر یافت نشد.")

        cursor.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
        msg_rows = cursor.fetchall()
        conn.close()

        messages = []
        for m in msg_rows:
            citations_list = json.loads(m["citations_json"]) if m["citations_json"] else []
            messages.append({
                "id": m["id"],
                "conversation_id": m["conversation_id"],
                "sender_role": m["sender_role"],
                "content": m["content"],
                "model_id": m["model_id"],
                "input_tokens": m["input_tokens"],
                "output_tokens": m["output_tokens"],
                "processing_time_sec": m["processing_time_sec"],
                "response_policy_used": m["response_policy_used"],
                "citations": citations_list,
                "created_at": m["created_at"]
            })

        return {
            "id": conv["id"],
            "title": conv["title"],
            "model_id": conv["model_id"],
            "is_pinned": bool(conv["is_pinned"]),
            "messages": messages,
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"]
        }

    @staticmethod
    def toggle_pin_conversation(conversation_id: str, user_id: str) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_pinned FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="گفتگو یافت نشد.")

        new_status = 0 if row["is_pinned"] else 1
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("UPDATE conversations SET is_pinned = ?, updated_at = ? WHERE id = ?", (new_status, now, conversation_id))
        conn.commit()
        conn.close()
        return bool(new_status)

    @staticmethod
    def delete_conversation(conversation_id: str, user_id: str) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        if not cursor.fetchone():
            conn.close()
            raise ResourceNotFoundError(detail_fa="گفتگو یافت نشد.")

        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        conn.close()
        return True

    # --------------------------------------------------------------------------
    # Message Processing & Policy Pipeline
    # --------------------------------------------------------------------------
    @classmethod
    def send_message(
        cls,
        conversation_id: str,
        user_id: str,
        request: SendMessageRequest
    ) -> SendMessageResponse:
        start_time = time.time()
        user_text = request.content.strip()
        if not user_text:
            raise PersianAppException(detail_fa="متن پیام نمی‌تواند خالی باشد.")

        # 1. Fetch User Hierarchy Quotas & Effective Policy
        hierarchy = user_service.get_user_quotas_and_policy(user_id)
        if hierarchy["daily_quota_remaining"] <= 0:
            raise PersianAppException(detail_fa="سقف پرسش روزانه شما تکمیل شده است. لطفاً فردا تلاش نمایید یا با مدیر تماس بگیرید.")
        if hierarchy["monthly_quota_remaining"] <= 0:
            raise PersianAppException(detail_fa="سقف پرسش ماهانه سازمانی شما تکمیل شده است.")

        # 2. Check Conversation existence & ownership
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
        conv = cursor.fetchone()
        if not conv:
            conn.close()
            raise ResourceNotFoundError(detail_fa="گفتگوی مورد نظر یافت نشد.")

        # Auto-update conversation title if it's the first message
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE conversation_id = ?", (conversation_id,))
        is_first_message = (cursor.fetchone()["count"] == 0)
        conn.close()

        # 3. Model Resolution
        allowed_models = ai_model_service.get_user_allowed_models(user_id)
        if not allowed_models:
            raise PersianAppException(detail_fa="هیچ مدل هوش مصنوعی فعالی برای گروه شما در دسترس نیست.")

        chosen_model_id = None
        if request.model_id and hierarchy["allow_model_selection"]:
            # Check if requested model is in allowed models
            if any(m["id"] == request.model_id for m in allowed_models):
                chosen_model_id = request.model_id

        if not chosen_model_id:
            # Fallback to conversation model, user default model, or first allowed model
            if conv["model_id"] and any(m["id"] == conv["model_id"] for m in allowed_models):
                chosen_model_id = conv["model_id"]
            elif hierarchy["default_model_id"] and any(m["id"] == hierarchy["default_model_id"] for m in allowed_models):
                chosen_model_id = hierarchy["default_model_id"]
            else:
                chosen_model_id = next((m["id"] for m in allowed_models if m.get("is_default")), allowed_models[0]["id"])

        # 4. Save User Message
        user_msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (
                id, conversation_id, sender_role, content, model_id,
                input_tokens, output_tokens, processing_time_sec, created_at
            ) VALUES (?, ?, 'user', ?, ?, 0, 0, 0.0, ?)
        """, (user_msg_id, conversation_id, user_text, chosen_model_id, now))

        if is_first_message:
            # Short auto title
            auto_title = user_text[:35] + ("..." if len(user_text) > 35 else "")
            cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (auto_title, conversation_id))
        conn.commit()
        conn.close()

        # 5. Policy Enforcement & RAG Retrieval
        policy = hierarchy["policy"] # 'KNOWLEDGE_ONLY' | 'HYBRID' | 'FREE_AI'
        citations = []
        rag_context_text = ""

        if policy in ("KNOWLEDGE_ONLY", "HYBRID"):
            # Search knowledge base
            search_res = knowledge_service.semantic_search(SemanticSearchRequest(
                query=user_text,
                category_id=request.category_id,
                top_k=4,
                min_similarity=0.15
            ))
            for r in search_res.results:
                citations.append({
                    "document_id": r.document_id,
                    "document_title": r.document_title,
                    "category_name": r.category_name,
                    "chunk_index": r.chunk_index,
                    "content_snippet": r.content[:150] + ("..." if len(r.content) > 150 else ""),
                    "similarity_score": r.similarity_score
                })

            if citations:
                rag_context_text = "\n\n".join([
                    f"--- مستند: {c['document_title']} (بخش {c['chunk_index']+1}) ---\n{c['content_snippet']}"
                    for c in citations
                ])

        # Strict KNOWLEDGE_ONLY policy guard
        if policy == "KNOWLEDGE_ONLY" and not citations:
            assistant_reply = (
                "پاسخی برای پرسش شما در پایگاه دانش سازمانی یافت نشد. "
                "مطابق با خط‌مشی گروه کاربری شما (فقط پایگاه دانش)، پاسخ‌دهی خارج از مستندات رسمی سازمان مجاز نمی‌باشد."
            )
            asst_msg_id = str(uuid.uuid4())
            asst_now = datetime.now(timezone.utc).isoformat()
            duration = round(time.time() - start_time, 3)

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (
                    id, conversation_id, sender_role, content, model_id,
                    input_tokens, output_tokens, processing_time_sec,
                    response_policy_used, citations_json, created_at
                ) VALUES (?, ?, 'assistant', ?, ?, 10, 30, ?, 'KNOWLEDGE_ONLY', '[]', ?)
            """, (asst_msg_id, conversation_id, assistant_reply, chosen_model_id, duration, asst_now))
            cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (asst_now, conversation_id))
            conn.commit()
            conn.close()

            item = MessageItem(
                id=asst_msg_id,
                conversation_id=conversation_id,
                sender_role="assistant",
                content=assistant_reply,
                model_id=chosen_model_id,
                input_tokens=10,
                output_tokens=30,
                processing_time_sec=duration,
                response_policy_used="KNOWLEDGE_ONLY",
                citations=[],
                created_at=asst_now
            )
            return SendMessageResponse(
                message=item,
                daily_quota_remaining=max(0, hierarchy["daily_quota_remaining"] - 1),
                monthly_quota_remaining=max(0, hierarchy["monthly_quota_remaining"] - 1)
            )

        # 6. Build LLM Messages Context (History + System + RAG)
        system_instruction = "شما دستیار هوشمند، رسمی و امین سازمان هستید. همواره به زبان فارسی سلیس و محترمانه پاسخ دهید."
        if policy == "KNOWLEDGE_ONLY":
            system_instruction += (
                f"\n\nمستندات پایگاه دانش سازمانی برای پاسخ به این سوال:\n{rag_context_text}\n\n"
                "دستورالعمل حیاتی: فقط و فقط با اتکا به متن مستندات بالا پاسخ دهید و به هیچ وجه از خود اطلاعات اضافه نکنید."
            )
        elif policy == "HYBRID" and rag_context_text:
            system_instruction += (
                f"\n\nمستندات تکمیلی از پایگاه دانش سازمانی:\n{rag_context_text}\n\n"
                "در صورت ارتباط، از مستندات بالا برای پاسخ دقیق‌تر استفاده کرده و منابع را ذکر نمایید."
            )

        llm_messages = [{"role": "system", "content": system_instruction}]

        # Append last 6 turns of conversation history
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sender_role, content FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC LIMIT 8
        """, (conversation_id,))
        hist_rows = list(reversed(cursor.fetchall()))
        conn.close()

        for h in hist_rows:
            llm_messages.append({
                "role": "user" if h["sender_role"] == "user" else "assistant",
                "content": h["content"]
            })

        # 7. Execute AI Gateway
        ai_resp = ai_gateway.execute_completion(
            model_id=chosen_model_id,
            messages=llm_messages,
            user_id=user_id
        )

        asst_reply_content = ai_resp["content"]
        asst_msg_id = str(uuid.uuid4())
        asst_now = datetime.now(timezone.utc).isoformat()
        duration = round(time.time() - start_time, 3)

        # 8. Save Assistant Message
        citations_json = json.dumps(citations, ensure_ascii=False)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (
                id, conversation_id, sender_role, content, model_id,
                input_tokens, output_tokens, processing_time_sec,
                response_policy_used, citations_json, created_at
            ) VALUES (?, ?, 'assistant', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            asst_msg_id, conversation_id, asst_reply_content, chosen_model_id,
            ai_resp["input_tokens"], ai_resp["output_tokens"], duration,
            policy, citations_json, asst_now
        ))
        cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (asst_now, conversation_id))
        conn.commit()
        conn.close()

        item = MessageItem(
            id=asst_msg_id,
            conversation_id=conversation_id,
            sender_role="assistant",
            content=asst_reply_content,
            model_id=chosen_model_id,
            input_tokens=ai_resp["input_tokens"],
            output_tokens=ai_resp["output_tokens"],
            processing_time_sec=duration,
            response_policy_used=policy,
            citations=[CitationItem(**c) for c in citations],
            created_at=asst_now
        )

        return SendMessageResponse(
            message=item,
            daily_quota_remaining=max(0, hierarchy["daily_quota_remaining"] - 1),
            monthly_quota_remaining=max(0, hierarchy["monthly_quota_remaining"] - 1)
        )

chat_service = ChatService()

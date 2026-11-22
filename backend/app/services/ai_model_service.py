"""
AI Provider and Model Management Business Service
Handles CRUD, encrypted API key storage, connection testing,
group access control and model permission resolution.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError, PermissionDeniedError
from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data
from app.schemas.ai_management import (
    AIProviderCreate, AIProviderUpdate,
    AIModelCreate, AIModelUpdate
)
from app.services.ai_gateway.gateway import ai_gateway
from app.services.audit_service import audit_service

def mask_api_key(key: str) -> str:
    """Mask sensitive API key (e.g., sk-proj-1234567890abcdef -> sk-proj-****cdef)."""
    if not key:
        return ""
    if len(key) <= 8:
        return "********"
    return f"{key[:7]}****{key[-4:]}"

class AIModelService:
    # --------------------------------------------------------------------------
    # AI Providers Management
    # --------------------------------------------------------------------------
    @staticmethod
    def list_providers() -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, COUNT(m.id) as models_count
            FROM ai_providers p
            LEFT JOIN ai_models m ON m.provider_id = p.id
            GROUP BY p.id
            ORDER BY p.created_at ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            decrypted = decrypt_sensitive_data(r["encrypted_api_key"])
            cfg = json.loads(r["config_params"]) if r["config_params"] else {}
            result.append({
                "id": r["id"],
                "name": r["name"],
                "provider_type": r["provider_type"],
                "base_url": r["base_url"],
                "is_active": bool(r["is_active"]),
                "config_params": cfg,
                "masked_api_key": mask_api_key(decrypted),
                "models_count": r["models_count"],
                "created_at": r["created_at"]
            })
        return result

    @staticmethod
    def get_provider_by_id(provider_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, COUNT(m.id) as models_count
            FROM ai_providers p
            LEFT JOIN ai_models m ON m.provider_id = p.id
            WHERE p.id = ?
            GROUP BY p.id
        """, (provider_id,))
        r = cursor.fetchone()
        conn.close()
        if not r:
            raise ResourceNotFoundError(detail_fa="ارائه‌دهنده هوش مصنوعی یافت نشد.")

        decrypted = decrypt_sensitive_data(r["encrypted_api_key"])
        cfg = json.loads(r["config_params"]) if r["config_params"] else {}
        return {
            "id": r["id"],
            "name": r["name"],
            "provider_type": r["provider_type"],
            "base_url": r["base_url"],
            "is_active": bool(r["is_active"]),
            "config_params": cfg,
            "masked_api_key": mask_api_key(decrypted),
            "models_count": r["models_count"],
            "created_at": r["created_at"]
        }

    @staticmethod
    def create_provider(data: AIProviderCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM ai_providers WHERE name = ?", (data.name,))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="ارائه‌دهنده‌ای با این نام قبلاً ثبت شده است.")

        provider_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        encrypted_key = encrypt_sensitive_data(data.api_key)
        cfg_json = json.dumps(data.config_params, ensure_ascii=False) if data.config_params else "{}"

        cursor.execute("""
            INSERT INTO ai_providers (
                id, name, provider_type, base_url, encrypted_api_key, is_active, config_params, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            provider_id, data.name, data.provider_type.upper(), data.base_url,
            encrypted_key, int(data.is_active), cfg_json, now
        ))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_PROVIDER_CREATED",
                target_resource="AI_PROVIDERS",
                target_id=provider_id,
                new_values={"name": data.name, "provider_type": data.provider_type}
            )

        return AIModelService.get_provider_by_id(provider_id)

    @staticmethod
    def update_provider(provider_id: str, data: AIProviderUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="ارائه‌دهنده هوش مصنوعی یافت نشد.")

        fields = []
        params = []
        if data.name is not None:
            fields.append("name = ?")
            params.append(data.name)
        if data.provider_type is not None:
            fields.append("provider_type = ?")
            params.append(data.provider_type.upper())
        if data.base_url is not None:
            fields.append("base_url = ?")
            params.append(data.base_url)
        if data.api_key:
            fields.append("encrypted_api_key = ?")
            params.append(encrypt_sensitive_data(data.api_key))
        if data.is_active is not None:
            fields.append("is_active = ?")
            params.append(int(data.is_active))
        if data.config_params is not None:
            fields.append("config_params = ?")
            params.append(json.dumps(data.config_params, ensure_ascii=False))

        if fields:
            params.append(provider_id)
            cursor.execute(f"UPDATE ai_providers SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_PROVIDER_UPDATED",
                target_resource="AI_PROVIDERS",
                target_id=provider_id,
                new_values=data.model_dump(exclude_unset=True, exclude={"api_key"})
            )

        return AIModelService.get_provider_by_id(provider_id)

    @staticmethod
    def delete_provider(provider_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM ai_providers WHERE id = ?", (provider_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="ارائه‌دهنده یافت نشد.")

        cursor.execute("SELECT COUNT(*) as count FROM ai_models WHERE provider_id = ?", (provider_id,))
        count = cursor.fetchone()["count"]
        if count > 0:
            conn.close()
            raise PersianAppException(detail_fa=f"این ارائه‌دهنده دارای {count} مدل فعال است. ابتدا مدل‌ها را حذف یا به ارائه‌دهنده دیگری منتقل کنید.")

        cursor.execute("DELETE FROM ai_providers WHERE id = ?", (provider_id,))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_PROVIDER_DELETED",
                target_resource="AI_PROVIDERS",
                target_id=provider_id,
                old_values={"name": row["name"]}
            )
        return True

    @staticmethod
    def test_provider_connection(provider_id: Optional[str] = None, provider_type: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
        """Test reachability of provider either by ID or ad-hoc test payload."""
        if provider_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,))
            row = cursor.fetchone()
            conn.close()
            if not row:
                raise ResourceNotFoundError(detail_fa="ارائه‌دهنده یافت نشد.")
            provider_type = row["provider_type"]
            api_key = decrypt_sensitive_data(row["encrypted_api_key"])
            base_url = row["base_url"]

        if not provider_type:
            raise PersianAppException(detail_fa="نوع ارائه‌دهنده هوش مصنوعی مشخص نشده است.")

        provider = ai_gateway._create_provider_instance(provider_type, api_key or "mock-key", base_url, {})
        ok, latency, msg = provider.test_connection()
        return {"success": ok, "latency_ms": latency, "message": msg}

    # --------------------------------------------------------------------------
    # AI Models Management
    # --------------------------------------------------------------------------
    @staticmethod
    def list_models(only_active: bool = False) -> List[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT m.*, p.name as provider_name, p.provider_type,
                   fb.display_name_fa as fallback_model_name
            FROM ai_models m
            JOIN ai_providers p ON m.provider_id = p.id
            LEFT JOIN ai_models fb ON m.fallback_model_id = fb.id
        """
        if only_active:
            query += " WHERE m.is_active = 1 AND p.is_active = 1"
        query += " ORDER BY m.is_default DESC, m.created_at ASC"

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r["id"],
                "provider_id": r["provider_id"],
                "provider_name": r["provider_name"],
                "provider_type": r["provider_type"],
                "model_identifier": r["model_identifier"],
                "display_name_fa": r["display_name_fa"],
                "is_active": bool(r["is_active"]),
                "is_default": bool(r["is_default"]),
                "input_cost_per_k_tokens": r["input_cost_per_k_tokens"],
                "output_cost_per_k_tokens": r["output_cost_per_k_tokens"],
                "max_context_tokens": r["max_context_tokens"],
                "fallback_model_id": r["fallback_model_id"],
                "fallback_model_name": r["fallback_model_name"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]

    @staticmethod
    def get_model_by_id(model_id: str) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.*, p.name as provider_name, p.provider_type,
                   fb.display_name_fa as fallback_model_name
            FROM ai_models m
            JOIN ai_providers p ON m.provider_id = p.id
            LEFT JOIN ai_models fb ON m.fallback_model_id = fb.id
            WHERE m.id = ?
        """, (model_id,))
        r = cursor.fetchone()
        conn.close()
        if not r:
            raise ResourceNotFoundError(detail_fa="مدل هوش مصنوعی یافت نشد.")

        return {
            "id": r["id"],
            "provider_id": r["provider_id"],
            "provider_name": r["provider_name"],
            "provider_type": r["provider_type"],
            "model_identifier": r["model_identifier"],
            "display_name_fa": r["display_name_fa"],
            "is_active": bool(r["is_active"]),
            "is_default": bool(r["is_default"]),
            "input_cost_per_k_tokens": r["input_cost_per_k_tokens"],
            "output_cost_per_k_tokens": r["output_cost_per_k_tokens"],
            "max_context_tokens": r["max_context_tokens"],
            "fallback_model_id": r["fallback_model_id"],
            "fallback_model_name": r["fallback_model_name"],
            "created_at": r["created_at"]
        }

    @staticmethod
    def create_model(data: AIModelCreate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check provider exists
        cursor.execute("SELECT id FROM ai_providers WHERE id = ?", (data.provider_id,))
        if not cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="شناسه ارائه‌دهنده هوش مصنوعی معتبر نیست.")

        # Check duplicate model identifier under same provider
        cursor.execute("SELECT id FROM ai_models WHERE provider_id = ? AND model_identifier = ?", (data.provider_id, data.model_identifier))
        if cursor.fetchone():
            conn.close()
            raise PersianAppException(detail_fa="این مدل قبلاً برای این ارائه‌دهنده ثبت شده است.")

        model_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # If this model is default, unset any previous default
        if data.is_default:
            cursor.execute("UPDATE ai_models SET is_default = 0")

        cursor.execute("""
            INSERT INTO ai_models (
                id, provider_id, model_identifier, display_name_fa,
                is_active, is_default, input_cost_per_k_tokens,
                output_cost_per_k_tokens, max_context_tokens,
                fallback_model_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            model_id, data.provider_id, data.model_identifier, data.display_name_fa,
            int(data.is_active), int(data.is_default), data.input_cost_per_k_tokens,
            data.output_cost_per_k_tokens, data.max_context_tokens,
            data.fallback_model_id, now
        ))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_MODEL_CREATED",
                target_resource="AI_MODELS",
                target_id=model_id,
                new_values={"model_identifier": data.model_identifier, "display_name_fa": data.display_name_fa}
            )

        return AIModelService.get_model_by_id(model_id)

    @staticmethod
    def update_model(model_id: str, data: AIModelUpdate, actor_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="مدل هوش مصنوعی یافت نشد.")

        fields = []
        params = []

        if data.provider_id is not None:
            fields.append("provider_id = ?")
            params.append(data.provider_id)
        if data.model_identifier is not None:
            fields.append("model_identifier = ?")
            params.append(data.model_identifier)
        if data.display_name_fa is not None:
            fields.append("display_name_fa = ?")
            params.append(data.display_name_fa)
        if data.is_active is not None:
            fields.append("is_active = ?")
            params.append(int(data.is_active))
        if data.is_default is not None:
            if data.is_default:
                cursor.execute("UPDATE ai_models SET is_default = 0")
            fields.append("is_default = ?")
            params.append(int(data.is_default))
        if data.input_cost_per_k_tokens is not None:
            fields.append("input_cost_per_k_tokens = ?")
            params.append(data.input_cost_per_k_tokens)
        if data.output_cost_per_k_tokens is not None:
            fields.append("output_cost_per_k_tokens = ?")
            params.append(data.output_cost_per_k_tokens)
        if data.max_context_tokens is not None:
            fields.append("max_context_tokens = ?")
            params.append(data.max_context_tokens)
        if data.fallback_model_id is not None:
            fields.append("fallback_model_id = ?")
            params.append(data.fallback_model_id if data.fallback_model_id != "" else None)

        if fields:
            params.append(model_id)
            cursor.execute(f"UPDATE ai_models SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_MODEL_UPDATED",
                target_resource="AI_MODELS",
                target_id=model_id,
                new_values=data.model_dump(exclude_unset=True)
            )

        return AIModelService.get_model_by_id(model_id)

    @staticmethod
    def delete_model(model_id: str, actor_user: Optional[Dict[str, Any]] = None) -> bool:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ResourceNotFoundError(detail_fa="مدل هوش مصنوعی یافت نشد.")

        # Check if set as fallback model for other models
        cursor.execute("SELECT display_name_fa FROM ai_models WHERE fallback_model_id = ?", (model_id,))
        dependents = [r["display_name_fa"] for r in cursor.fetchall()]
        if dependents:
            conn.close()
            raise PersianAppException(detail_fa=f"این مدل به عنوان مدل جایگزین (Fallback) برای «{', '.join(dependents)}» تعیین شده است. ابتدا ارجاع آن‌ها را بردارید.")

        cursor.execute("DELETE FROM ai_models WHERE id = ?", (model_id,))
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="AI_MODEL_DELETED",
                target_resource="AI_MODELS",
                target_id=model_id,
                old_values={"model_identifier": row["model_identifier"]}
            )
        return True

    # --------------------------------------------------------------------------
    # Model Permissions & User Access Matrix
    # --------------------------------------------------------------------------
    @staticmethod
    def get_user_allowed_models(user_id: str) -> List[Dict[str, Any]]:
        """
        Resolve models that a user has access to.
        Rules:
        - If user belongs to a group with specific model permissions, only return those.
        - If group has no specific restriction or user is Super Admin, return all active models.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT u.group_id, r.name as role_name FROM users u LEFT JOIN roles r ON u.role_id = r.id WHERE u.id = ?", (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            conn.close()
            return []

        # Super Admin has access to all active models
        if user_row["role_name"] == "super_admin":
            conn.close()
            return AIModelService.list_models(only_active=True)

        group_id = user_row["group_id"]
        # Check if group has specific assigned models
        cursor.execute("SELECT model_id FROM group_model_permissions WHERE group_id = ?", (group_id,))
        allowed_ids = [r["model_id"] for r in cursor.fetchall()]
        conn.close()

        all_active = AIModelService.list_models(only_active=True)
        if not allowed_ids:
            # If no restriction defined for the group, all active models are available
            return all_active

        return [m for m in all_active if m["id"] in allowed_ids]

    @staticmethod
    def set_group_allowed_models(group_id: str, model_ids: List[str], actor_user: Optional[Dict[str, Any]] = None):
        """Bind specific AI models to a group."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM group_model_permissions WHERE group_id = ?", (group_id,))

        now = datetime.now(timezone.utc).isoformat()
        for mid in model_ids:
            cursor.execute(
                "INSERT INTO group_model_permissions (group_id, model_id, created_at) VALUES (?, ?, ?)",
                (group_id, mid, now)
            )
        conn.commit()
        conn.close()

        if actor_user:
            audit_service.log_action(
                actor_user_id=actor_user["id"],
                actor_username=actor_user["username"],
                action_type="GROUP_MODEL_PERMISSIONS_UPDATED",
                target_resource="GROUPS",
                target_id=group_id,
                new_values={"allowed_model_ids": model_ids}
            )

ai_model_service = AIModelService()

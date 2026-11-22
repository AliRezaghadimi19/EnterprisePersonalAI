"""
Central AI Gateway Router and Dispatcher
Features:
- Dynamic model resolution from database (zero hardcoding)
- In-memory API key decryption
- Automatic fallback model invocation on failure
- Token accounting and cost calculation
- Integration with audit logging
"""

import json
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException, ResourceNotFoundError
from app.core.security import decrypt_sensitive_data
from app.services.ai_gateway.providers import (
    BaseLLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
    MockProvider
)
from app.services.audit_service import audit_service

class AIGateway:
    @staticmethod
    def _create_provider_instance(provider_type: str, api_key: str, base_url: Optional[str], config_params: Dict[str, Any]) -> BaseLLMProvider:
        ptype = provider_type.upper()
        if ptype == "OPENAI":
            return OpenAIProvider(api_key, base_url, config_params)
        elif ptype == "ANTHROPIC":
            return AnthropicProvider(api_key, base_url, config_params)
        elif ptype == "GEMINI":
            return GeminiProvider(api_key, base_url, config_params)
        elif ptype in ("OPENAI_COMPATIBLE", "CUSTOM"):
            return OpenAICompatibleProvider(api_key, base_url, config_params)
        else:
            return MockProvider(api_key, base_url, config_params)

    @classmethod
    def get_model_details(cls, model_id: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.*, p.name as provider_name, p.provider_type, p.base_url,
                   p.encrypted_api_key, p.config_params, p.is_active as provider_active,
                   fb.model_identifier as fallback_identifier
            FROM ai_models m
            JOIN ai_providers p ON m.provider_id = p.id
            LEFT JOIN ai_models fb ON m.fallback_model_id = fb.id
            WHERE m.id = ?
        """, (model_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @classmethod
    def execute_completion(
        cls,
        model_id: str,
        messages: List[Dict[str, str]],
        user_id: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Execute completion with automatic fallback resolution and token tracking.
        """
        model_info = cls.get_model_details(model_id)
        if not model_info:
            raise ResourceNotFoundError(detail_fa="مدل هوش مصنوعی درخواستی در سامانه یافت نشد.")
            
        if not model_info["is_active"] or not model_info["provider_active"]:
            raise PersianAppException(detail_fa="مدل هوش مصنوعی یا سرویس‌دهنده آن در حال حاضر غیرفعال است.")

        fallback_used = False
        effective_model_id = model_id
        effective_model_identifier = model_info["model_identifier"]

        try:
            # 1. Decrypt API Key
            decrypted_key = decrypt_sensitive_data(model_info["encrypted_api_key"])
            cfg = json.loads(model_info["config_params"]) if model_info["config_params"] else {}
            provider = cls._create_provider_instance(
                model_info["provider_type"],
                decrypted_key,
                model_info["base_url"],
                cfg
            )
            # 2. Invoke Provider
            result = provider.generate(
                messages=messages,
                model_identifier=model_info["model_identifier"],
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as primary_error:
            # Primary model failed -> Attempt Fallback if configured
            fallback_id = model_info.get("fallback_model_id")
            if fallback_id and fallback_id != model_id:
                fallback_info = cls.get_model_details(fallback_id)
                if fallback_info and fallback_info["is_active"]:
                    fallback_used = True
                    effective_model_id = fallback_id
                    effective_model_identifier = fallback_info["model_identifier"]
                    
                    decrypted_fb_key = decrypt_sensitive_data(fallback_info["encrypted_api_key"])
                    fb_cfg = json.loads(fallback_info["config_params"]) if fallback_info["config_params"] else {}
                    fb_provider = cls._create_provider_instance(
                        fallback_info["provider_type"],
                        decrypted_fb_key,
                        fallback_info["base_url"],
                        fb_cfg
                    )
                    result = fb_provider.generate(
                        messages=messages,
                        model_identifier=fallback_info["model_identifier"],
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    # Record fallback event in audit logs
                    audit_service.log_action(
                        actor_user_id=user_id,
                        actor_username="SYSTEM",
                        action_type="AI_FALLBACK_TRIGGERED",
                        target_resource="AI_MODELS",
                        target_id=model_id,
                        old_values={"primary_model": model_info["model_identifier"], "error": str(primary_error)},
                        new_values={"fallback_model": fallback_info["model_identifier"]}
                    )
                else:
                    raise PersianAppException(detail_fa=f"خطا در مدل اصلی و عدم دسترسی به مدل جایگزین: {str(primary_error)}")
            else:
                raise PersianAppException(detail_fa=f"خطا در پردازش توسط مدل هوش مصنوعی: {str(primary_error)}")

        # 3. Calculate Cost
        active_model_meta = cls.get_model_details(effective_model_id) or model_info
        in_cost_rate = active_model_meta.get("input_cost_per_k_tokens", 0.0)
        out_cost_rate = active_model_meta.get("output_cost_per_k_tokens", 0.0)
        
        input_tokens = result.get("input_tokens", 0)
        output_tokens = result.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        
        estimated_cost = (
            (input_tokens / 1000.0 * in_cost_rate) +
            (output_tokens / 1000.0 * out_cost_rate)
        )

        # 4. Record Usage in Database
        if user_id:
            cls._record_usage_metrics(
                user_id=user_id,
                model_id=effective_model_id,
                tokens=total_tokens,
                cost=estimated_cost
            )

        return {
            "content": result["content"],
            "model_id": effective_model_id,
            "model_identifier": effective_model_identifier,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "latency_ms": result.get("latency_ms", 0.0),
            "fallback_used": fallback_used,
            "finish_reason": result.get("finish_reason", "stop")
        }

    @classmethod
    def _record_usage_metrics(cls, user_id: str, model_id: str, tokens: int, cost: float):
        conn = None
        try:
            today_str = date.today().isoformat()
            metric_id = str(uuid.uuid4())
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, question_count, total_tokens, estimated_cost
                FROM usage_metrics
                WHERE user_id = ? AND model_id = ? AND usage_date = ?
            """, (user_id, model_id, today_str))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE usage_metrics SET
                        question_count = question_count + 1,
                        total_tokens = total_tokens + ?,
                        estimated_cost = estimated_cost + ?
                    WHERE id = ?
                """, (tokens, cost, row["id"]))
            else:
                cursor.execute("""
                    INSERT INTO usage_metrics (
                        id, user_id, model_id, usage_date, question_count, total_tokens, estimated_cost
                    ) VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (metric_id, user_id, model_id, today_str, tokens, cost))
                
            conn.commit()
        except Exception:
            pass
        finally:
            if conn:
                conn.close()

ai_gateway = AIGateway()

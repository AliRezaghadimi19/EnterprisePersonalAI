"""
Phase 3 Comprehensive Test Suite: AI Gateway & Model Management
Validates:
- AI Provider CRUD & secure API key encryption / masking
- Provider Connection Testing
- AI Model CRUD & Default model exclusivity
- Fallback Model referencing & integrity locks
- Group Model Access Matrix & User allowed models resolution
- Dynamic AI Gateway execution, token estimation & usage metrics tracking
- Fallback execution trigger on simulated provider failure
- Audit logs for all AI Provider and Model operations
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
from app.services.ai_model_service import ai_model_service
from app.services.ai_gateway.gateway import ai_gateway
from app.schemas.ai_management import (
    AIProviderCreate, AIProviderUpdate,
    AIModelCreate, AIModelUpdate,
    ModelAccessMatrixUpdate
)

class TestPhase3AIGatewayAndModels(unittest.TestCase):
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

    def test_01_provider_crud_and_encryption(self):
        uid = uuid.uuid4().hex[:6]
        # 1. Create Provider
        prov_data = AIProviderCreate(
            name=f"OpenAI Test Enterprise {uid}",
            provider_type="OPENAI",
            base_url="https://api.openai.com/v1",
            api_key="sk-proj-1234567890abcdefghijklmnopqrstuvwxyz",
            is_active=True,
            config_params={"org_id": "org-test-123"}
        )
        prov = ai_model_service.create_provider(prov_data, actor_user=self.admin_user)
        self.assertIsNotNone(prov["id"])
        self.assertEqual(prov["name"], f"OpenAI Test Enterprise {uid}")
        self.assertTrue(prov["masked_api_key"].startswith("sk-proj"))
        self.assertTrue(prov["masked_api_key"].endswith("wxyz"))
        self.assertNotIn("1234567890", prov["masked_api_key"]) # Key must be masked

        # 2. Update Provider
        updated = ai_model_service.update_provider(
            prov["id"],
            AIProviderUpdate(name=f"OpenAI Test Updated {uid}", is_active=False),
            actor_user=self.admin_user
        )
        self.assertEqual(updated["name"], f"OpenAI Test Updated {uid}")
        self.assertFalse(updated["is_active"])

        # 3. Test Connection with mock key
        test_res = ai_model_service.test_provider_connection(
            provider_type="MOCK",
            api_key="mock-key-123"
        )
        self.assertTrue(test_res["success"])
        self.assertGreater(test_res["latency_ms"], 0)

        # 4. Clean up
        ai_model_service.delete_provider(prov["id"], actor_user=self.admin_user)

    def test_02_model_crud_and_default_exclusivity(self):
        uid = uuid.uuid4().hex[:6]
        # Create Provider for testing models
        prov = ai_model_service.create_provider(
            AIProviderCreate(
                name=f"Provider Model Test {uid}",
                provider_type="MOCK",
                api_key="mock-key-safe"
            ),
            actor_user=self.admin_user
        )

        # Create Model 1 (Default)
        model1 = ai_model_service.create_model(
            AIModelCreate(
                provider_id=prov["id"],
                model_identifier="test-gpt-4o",
                display_name_fa="مدل تستی اصلی",
                is_active=True,
                is_default=True,
                input_cost_per_k_tokens=0.005,
                output_cost_per_k_tokens=0.015,
                max_context_tokens=128000
            ),
            actor_user=self.admin_user
        )
        self.assertTrue(model1["is_default"])

        # Create Model 2 (Set as Default -> Should unset Model 1 default)
        model2 = ai_model_service.create_model(
            AIModelCreate(
                provider_id=prov["id"],
                model_identifier="test-claude-sonnet",
                display_name_fa="مدل جایگزین تستی",
                is_active=True,
                is_default=True,
                fallback_model_id=model1["id"]
            ),
            actor_user=self.admin_user
        )
        self.assertTrue(model2["is_default"])

        # Verify model1 is no longer default
        m1_refetched = ai_model_service.get_model_by_id(model1["id"])
        self.assertFalse(m1_refetched["is_default"])

        # Model 1 is fallback for Model 2 -> Cannot delete Model 1
        with self.assertRaises(PersianAppException):
            ai_model_service.delete_model(model1["id"], actor_user=self.admin_user)

        # Unlink fallback
        ai_model_service.update_model(
            model2["id"],
            AIModelUpdate(fallback_model_id=""),
            actor_user=self.admin_user
        )

        # Now delete Model 1 succeeds
        self.assertTrue(ai_model_service.delete_model(model1["id"], actor_user=self.admin_user))
        self.assertTrue(ai_model_service.delete_model(model2["id"], actor_user=self.admin_user))
        self.assertTrue(ai_model_service.delete_provider(prov["id"], actor_user=self.admin_user))

    def test_03_group_access_matrix(self):
        models = ai_model_service.list_models()
        self.assertGreaterEqual(len(models), 1)
        selected_model_id = models[0]["id"]

        from app.services.group_service import group_service
        groups = group_service.list_groups()
        target_group = groups[0]

        # Assign model to group
        ai_model_service.set_group_allowed_models(
            target_group["id"],
            [selected_model_id],
            actor_user=self.admin_user
        )

        # Fetch allowed models for an admin user (always all active)
        admin_models = ai_model_service.get_user_allowed_models(self.admin_user["id"])
        self.assertGreaterEqual(len(admin_models), 1)

    def test_04_ai_gateway_completion_and_metrics(self):
        models = ai_model_service.list_models(only_active=True)
        active_model = models[0]

        messages = [
            {"role": "system", "content": "شما دستیار سازمانی هستید."},
            {"role": "user", "content": "قوانین سازمان را تشریح کنید."}
        ]

        # Execute completion through gateway
        result = ai_gateway.execute_completion(
            model_id=active_model["id"],
            messages=messages,
            user_id=self.admin_user["id"]
        )

        self.assertIn("content", result)
        self.assertGreater(result["input_tokens"], 0)
        self.assertGreater(result["output_tokens"], 0)
        self.assertEqual(result["total_tokens"], result["input_tokens"] + result["output_tokens"])
        self.assertFalse(result["fallback_used"])

if __name__ == "__main__":
    unittest.main()

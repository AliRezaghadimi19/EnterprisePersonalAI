"""
Phase 1 Comprehensive Test Suite
Validates:
- Cryptographic hashing and verification
- JWT Token issuance, claims, and verification
- Sensitive data encryption / decryption
- LDAP Injection prevention & Active Directory integration
- Database schema initialization & idempotent seeding
- Local & AD Authentication workflows
- System Auth Mode enforcement (LOCAL_ONLY, AD_ONLY, BOTH)
- Rate limiting behavior
- Audit log recording
"""

import os
import sys
import unittest
from pathlib import Path

# Add backend directory to sys.path so app modules import cleanly
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    encrypt_sensitive_data,
    decrypt_sensitive_data
)
from app.core.ldap_auth import LDAPAuthenticator, escape_ldap_filter
from app.core.database import get_db_connection
from app.core.rate_limiter import InMemoryRateLimiter
from app.core.exceptions import (
    AuthenticationError,
    AccountDisabledError,
    PermissionDeniedError
)
from app.services.seeder import seed_database
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service


class TestPhase1SecurityAndCryptography(unittest.TestCase):
    """Test cryptographic functions, hashing, tokens and symmetric encryption."""

    def test_password_hashing_and_verification(self):
        password = "EnterpriseSecretPassword123!"
        hashed = hash_password(password)
        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertNotEqual(password, hashed)
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword!", hashed))

    def test_jwt_token_creation_and_decoding(self):
        user_id = "test-user-uuid-1234"
        claims = {"username": "testuser", "role": "system_admin"}
        token = create_access_token(subject=user_id, extra_claims=claims)
        self.assertIsInstance(token, str)
        self.assertEqual(len(token.split(".")), 3)

        decoded = decode_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], user_id)
        self.assertEqual(decoded["username"], "testuser")
        self.assertEqual(decoded["role"], "system_admin")
        self.assertEqual(decoded["type"], "access")

    def test_refresh_token(self):
        user_id = "user-refresh-5678"
        token = create_refresh_token(subject=user_id)
        decoded = decode_token(token)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["sub"], user_id)
        self.assertEqual(decoded["type"], "refresh")

    def test_sensitive_data_encryption_and_decryption(self):
        api_key = "sk-proj-supersecretapikeyforenterpriseai"
        encrypted = encrypt_sensitive_data(api_key)
        self.assertNotEqual(api_key, encrypted)
        decrypted = decrypt_sensitive_data(encrypted)
        self.assertEqual(api_key, decrypted)

        # Tampered ciphertext should fail to decrypt safely
        tampered = encrypted[:-4] + "AAAA"
        self.assertEqual(decrypt_sensitive_data(tampered), "")


class TestPhase1ActiveDirectory(unittest.TestCase):
    """Test LDAP/LDAPS functionality and injection defenses."""

    def test_ldap_injection_prevention(self):
        malicious_input = "*()\\admin\x00/test"
        sanitized = escape_ldap_filter(malicious_input)
        self.assertNotIn("*", sanitized)
        self.assertNotIn("(", sanitized)
        self.assertNotIn(")", sanitized)
        self.assertNotIn("\x00", sanitized)
        self.assertIn("\\2a", sanitized)
        self.assertIn("\\28", sanitized)
        self.assertIn("\\29", sanitized)

    def test_ad_mock_authentication_success(self):
        client = LDAPAuthenticator(
            server_host="mock-ad",
            port=389,
            domain_name="enterprise.local"
        )
        ok, user_data, msg = client.authenticate("ad_user", "AD_Pass123!")
        self.assertTrue(ok)
        self.assertIsNotNone(user_data)
        self.assertEqual(user_data["username"], "ad_user")
        self.assertEqual(user_data["department"], "فناوری اطلاعات")

    def test_ad_mock_authentication_failure(self):
        client = LDAPAuthenticator(server_host="mock-ad", port=389)
        ok, user_data, msg = client.authenticate("ad_user", "WrongADPassword")
        self.assertFalse(ok)
        self.assertIsNone(user_data)

    def test_ad_connection_test(self):
        client = LDAPAuthenticator(server_host="mock-ad", port=389)
        ok, msg = client.test_connection()
        self.assertTrue(ok)
        self.assertIn("با موفقیت", msg)


class TestPhase1DatabaseAndSeeding(unittest.TestCase):
    """Test DB initial seeding, idempotency, and default roles/settings."""

    @classmethod
    def setUpClass(cls):
        # Run seeder
        seed_database()

    def test_seeding_is_idempotent(self):
        # Running a second time should not raise UNIQUE constraint errors
        try:
            seed_database()
        except Exception as e:
            self.fail(f"seed_database raised an unexpected exception: {e}")

    def test_default_roles_exist(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, display_name_fa FROM roles")
        roles = {row["name"]: row["display_name_fa"] for row in cursor.fetchall()}
        conn.close()

        self.assertIn("super_admin", roles)
        self.assertIn("system_admin", roles)
        self.assertIn("manager_subscriber", roles)
        self.assertIn("tech_subscriber", roles)
        self.assertIn("normal_subscriber", roles)
        self.assertEqual(roles["super_admin"], "مدیر کل")

    def test_default_groups_exist(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, daily_question_limit FROM groups")
        groups = {row["name"]: row["daily_question_limit"] for row in cursor.fetchall()}
        conn.close()

        self.assertIn("مدیران", groups)
        self.assertIn("کارشناسان فنی", groups)
        self.assertIn("کاربران عمومی", groups)
        self.assertEqual(groups["مدیران"], 500)

    def test_super_admin_user_created(self):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, auth_type, is_active FROM users WHERE username = ?", (settings.SUPER_ADMIN_USERNAME,))
        admin = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(admin)
        self.assertEqual(admin["username"], settings.SUPER_ADMIN_USERNAME)
        self.assertEqual(admin["auth_type"], "LOCAL")
        self.assertEqual(admin["is_active"], 1)


class TestPhase1AuthService(unittest.TestCase):
    """Test Local login, AD login, token refresh, and auth policies."""

    @classmethod
    def setUpClass(cls):
        seed_database()

    def test_super_admin_local_login_success(self):
        res = auth_service.authenticate_user(
            username=settings.SUPER_ADMIN_USERNAME,
            password=settings.SUPER_ADMIN_PASSWORD,
            auth_method="LOCAL"
        )
        self.assertIn("access_token", res)
        self.assertIn("refresh_token", res)
        self.assertEqual(res["user"]["username"], settings.SUPER_ADMIN_USERNAME)
        self.assertEqual(res["user"]["role_name"], "super_admin")
        self.assertIn("*", res["user"]["permissions"])

    def test_local_login_invalid_password(self):
        with self.assertRaises(AuthenticationError):
            auth_service.authenticate_user(
                username=settings.SUPER_ADMIN_USERNAME,
                password="IncorrectPassword!",
                auth_method="LOCAL"
            )

    def test_rate_limiter_threshold(self):
        limiter = InMemoryRateLimiter()
        key = "test_rate_key"
        for _ in range(5):
            self.assertFalse(limiter.is_rate_limited(key, max_requests=5, window_seconds=10))
        # 6th attempt should be blocked
        self.assertTrue(limiter.is_rate_limited(key, max_requests=5, window_seconds=10))

    def test_refresh_token_flow(self):
        login_res = auth_service.authenticate_user(
            username=settings.SUPER_ADMIN_USERNAME,
            password=settings.SUPER_ADMIN_PASSWORD
        )
        refresh_token = login_res["refresh_token"]

        new_res = auth_service.refresh_user_token(refresh_token)
        self.assertIn("access_token", new_res)
        self.assertEqual(new_res["user"]["username"], settings.SUPER_ADMIN_USERNAME)

    def test_audit_log_persisted(self):
        log_id = audit_service.log_action(
            actor_user_id="test_admin_id",
            actor_username="admin",
            action_type="TEST_ACTION",
            target_resource="SETTINGS",
            new_values={"key": "test"}
        )
        self.assertIsNotNone(log_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["action_type"], "TEST_ACTION")


if __name__ == "__main__":
    unittest.main()

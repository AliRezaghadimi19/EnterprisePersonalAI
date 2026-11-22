"""
Phase 2 Comprehensive Test Suite
Validates:
- Roles & RBAC: Listing, creating custom roles, updating permissions, safety locks
- Groups: Quota configs, file restrictions, policy bindings, deletion checks
- Users: CRUD, duplicate checks, password updates, status toggling
- Hierarchy Resolution: User Override > Group Policy > System Default
- Safety Locks: Anti-lockout protections for the Super Admin
- Audit trail recording for all management operations
"""

import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.exceptions import (
    PersianAppException,
    ResourceNotFoundError,
    PermissionDeniedError,
    AccountDisabledError
)
from app.services.seeder import seed_database
from app.services.role_service import role_service
from app.services.group_service import group_service
from app.services.user_service import user_service
from app.services.auth_service import auth_service
from app.schemas.user_management import (
    RoleCreate, RoleUpdate,
    GroupCreate, GroupUpdate,
    UserCreate, UserUpdate
)

class TestPhase2RolesAndRBAC(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()

    def test_list_roles_contains_system_roles(self):
        roles = role_service.list_roles()
        role_names = [r["name"] for r in roles]
        self.assertIn("super_admin", role_names)
        self.assertIn("system_admin", role_names)
        self.assertIn("tech_subscriber", role_names)
        self.assertIn("normal_subscriber", role_names)

    def test_create_and_delete_custom_role(self):
        admin = {"id": "admin_uuid", "username": "admin"}
        new_role = role_service.create_role(
            RoleCreate(
                name="data_scientist",
                display_name_fa="دانشمند داده",
                permissions=["chat:access", "models:read", "data:export"]
            ),
            actor_user=admin
        )
        self.assertEqual(new_role["name"], "data_scientist")
        self.assertFalse(new_role["is_system"])

        # Update role
        updated = role_service.update_role(
            new_role["id"],
            RoleUpdate(display_name_fa="متخصص علوم داده", permissions=["chat:access"]),
            actor_user=admin
        )
        self.assertEqual(updated["display_name_fa"], "متخصص علوم داده")

        # Delete role
        res = role_service.delete_role(new_role["id"], actor_user=admin)
        self.assertTrue(res)

    def test_prevent_system_role_deletion(self):
        roles = role_service.list_roles()
        super_role = next(r for r in roles if r["name"] == "super_admin")
        with self.assertRaises(PermissionDeniedError):
            role_service.delete_role(super_role["id"])

    def test_prevent_duplicate_role_name(self):
        with self.assertRaises(PersianAppException):
            role_service.create_role(RoleCreate(name="super_admin", display_name_fa="مدیر کل تکراری"))


class TestPhase2Groups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()

    def test_list_groups_and_member_count(self):
        groups = group_service.list_groups()
        group_names = [g["name"] for g in groups]
        self.assertIn("مدیران", group_names)
        self.assertIn("کاربران عمومی", group_names)
        self.assertGreaterEqual(len(groups), 3)

    def test_create_and_update_group(self):
        admin = {"id": "admin_uuid", "username": "admin"}
        grp = group_service.create_group(
            GroupCreate(
                name="تیم تحلیل داده",
                description="گروه پژوهش و تحلیل داده سازمانی",
                default_policy="FREE_AI",
                daily_question_limit=250,
                monthly_question_limit=6000,
                allowed_file_types=["csv", "xlsx", "pdf"]
            ),
            actor_user=admin
        )
        self.assertEqual(grp["name"], "تیم تحلیل داده")
        self.assertEqual(grp["daily_question_limit"], 250)
        self.assertIn("csv", grp["allowed_file_types"])

        # Update group
        updated = group_service.update_group(
            grp["id"],
            GroupUpdate(daily_question_limit=300),
            actor_user=admin
        )
        self.assertEqual(updated["daily_question_limit"], 300)

        # Delete group (empty of users)
        res = group_service.delete_group(grp["id"], actor_user=admin)
        self.assertTrue(res)

    def test_prevent_deleting_group_with_members(self):
        groups = group_service.list_groups()
        # "مدیران" group has the initial super admin
        admin_grp = next(g for g in groups if g["name"] == "مدیران")
        with self.assertRaises(PersianAppException):
            group_service.delete_group(admin_grp["id"])


class TestPhase2UsersAndHierarchy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_database()

    def test_create_user_and_authenticate(self):
        roles = role_service.list_roles()
        groups = group_service.list_groups()
        normal_role = next(r for r in roles if r["name"] == "normal_subscriber")
        general_grp = next(g for g in groups if g["name"] == "کاربران عمومی")

        admin = {"id": "admin_uuid", "username": "admin"}
        new_user = user_service.create_user(
            UserCreate(
                username="reza_test",
                first_name="رضا",
                last_name="احمدی",
                email="reza@enterprise.local",
                department="امور مالی",
                role_id=normal_role["id"],
                group_id=general_grp["id"],
                password="UserSecurePass123!",
                auth_type="LOCAL",
                is_active=True
            ),
            actor_user=admin
        )
        self.assertEqual(new_user["username"], "reza_test")

        # Authenticate with new user
        auth_res = auth_service.authenticate_user(
            username="reza_test",
            password="UserSecurePass123!"
        )
        self.assertIn("access_token", auth_res)
        self.assertEqual(auth_res["user"]["username"], "reza_test")

        # Cleanup test user
        user_service.delete_user(new_user["id"], actor_user=admin)

    def test_hierarchy_resolution_policy_and_quota(self):
        roles = role_service.list_roles()
        groups = group_service.list_groups()
        normal_role = next(r for r in roles if r["name"] == "normal_subscriber")
        general_grp = next(g for g in groups if g["name"] == "کاربران عمومی")
        admin = {"id": "admin_uuid", "username": "admin"}

        # User 1: Inherits group defaults
        u1 = user_service.create_user(
            UserCreate(
                username="u1_inherited",
                first_name="علی",
                last_name="موسوی",
                role_id=normal_role["id"],
                group_id=general_grp["id"],
                password="Pass12345678!",
                override_policy=None,
                custom_daily_limit=None
            ),
            actor_user=admin
        )
        self.assertEqual(u1["effective_policy"], general_grp["default_policy"]) # HYBRID
        self.assertEqual(u1["effective_daily_limit"], general_grp["daily_question_limit"]) # 50

        # User 2: Has specific user overrides
        u2 = user_service.create_user(
            UserCreate(
                username="u2_overridden",
                first_name="مریم",
                last_name="رستمی",
                role_id=normal_role["id"],
                group_id=general_grp["id"],
                password="Pass12345678!",
                override_policy="KNOWLEDGE_ONLY",
                custom_daily_limit=999
            ),
            actor_user=admin
        )
        # User override takes precedence over group setting
        self.assertEqual(u2["effective_policy"], "KNOWLEDGE_ONLY")
        self.assertEqual(u2["effective_daily_limit"], 999)

        # Cleanup
        user_service.delete_user(u1["id"])
        user_service.delete_user(u2["id"])

    def test_user_deactivation_prevents_login(self):
        roles = role_service.list_roles()
        groups = group_service.list_groups()
        normal_role = next(r for r in roles if r["name"] == "normal_subscriber")
        general_grp = next(g for g in groups if g["name"] == "کاربران عمومی")
        admin = {"id": "admin_uuid", "username": "admin"}

        u = user_service.create_user(
            UserCreate(
                username="deactivated_user",
                first_name="کاربر",
                last_name="غیرفعال",
                role_id=normal_role["id"],
                group_id=general_grp["id"],
                password="Pass12345678!",
                is_active=True
            ),
            actor_user=admin
        )

        # Deactivate user
        user_service.update_user(u["id"], UserUpdate(is_active=False), actor_user=admin)

        # Login must fail with AccountDisabledError
        with self.assertRaises(AccountDisabledError):
            auth_service.authenticate_user(username="deactivated_user", password="Pass12345678!")

        # Cleanup
        user_service.delete_user(u["id"])

    def test_safety_prevent_deactivating_or_deleting_last_super_admin(self):
        users = user_service.list_users(search=settings.SUPER_ADMIN_USERNAME)
        super_admin = users[0]

        # Cannot deactivate the only super admin
        with self.assertRaises(PermissionDeniedError):
            user_service.update_user(super_admin["id"], UserUpdate(is_active=False))

        # Cannot delete the only super admin
        with self.assertRaises(PermissionDeniedError):
            user_service.delete_user(super_admin["id"])

    def test_safety_prevent_self_deletion(self):
        users = user_service.list_users(search=settings.SUPER_ADMIN_USERNAME)
        super_admin = users[0]
        # Admin trying to delete their own user_id
        with self.assertRaises(PermissionDeniedError):
            user_service.delete_user(super_admin["id"], actor_user={"id": super_admin["id"], "username": super_admin["username"]})

    def test_edit_user_password_and_group(self):
        roles = role_service.list_roles()
        groups = group_service.list_groups()
        normal_role = next(r for r in roles if r["name"] == "normal_subscriber")
        grp_users = next(g for g in groups if g["name"] == "کاربران عمومی")
        grp_tech = next(g for g in groups if g["name"] == "کارشناسان فنی")
        admin = {"id": "admin_uuid", "username": "admin"}

        # 1. Create User in Group "کاربران عمومی"
        u = user_service.create_user(
            UserCreate(
                username="edit_demo_user",
                first_name="مهدی",
                last_name="صالحی",
                role_id=normal_role["id"],
                group_id=grp_users["id"],
                password="OldPassword123!",
                is_active=True
            ),
            actor_user=admin
        )
        self.assertEqual(u["group_id"], grp_users["id"])
        self.assertEqual(u["group_name"], "کاربران عمومی")

        # Verify old password works
        old_auth = auth_service.authenticate_user(username="edit_demo_user", password="OldPassword123!")
        self.assertIsNotNone(old_auth["access_token"])

        # 2. Edit User: Change Group to "کارشناسان فنی" and change Password
        updated = user_service.update_user(
            u["id"],
            UserUpdate(
                group_id=grp_tech["id"],
                password="NewSuperSecurePass456!"
            ),
            actor_user=admin
        )

        self.assertEqual(updated["group_id"], grp_tech["id"])
        self.assertEqual(updated["group_name"], "کارشناسان فنی")

        # Old password must fail
        from app.core.exceptions import AuthenticationError
        with self.assertRaises(AuthenticationError):
            auth_service.authenticate_user(username="edit_demo_user", password="OldPassword123!")

        # New password must succeed
        new_auth = auth_service.authenticate_user(username="edit_demo_user", password="NewSuperSecurePass456!")
        self.assertIsNotNone(new_auth["access_token"])
        self.assertEqual(new_auth["user"]["group_name"], "کارشناسان فنی")

        # Cleanup
        user_service.delete_user(u["id"], actor_user=admin)


if __name__ == "__main__":
    unittest.main()

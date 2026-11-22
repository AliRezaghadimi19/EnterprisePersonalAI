"""
Database Initialization and Seed Data Module
Initializes system roles, default groups, initial super admin, and settings.
"""

import json
import uuid
from datetime import datetime, timezone
from app.core.config import settings
from app.core.database import get_db_connection
from app.core.security import hash_password, encrypt_sensitive_data

INITIAL_ROLES = [
    {
        "name": "super_admin",
        "display_name_fa": "مدیر کل",
        "permissions": ["*"],
        "is_system": 1
    },
    {
        "name": "system_admin",
        "display_name_fa": "مدیر سامانه",
        "permissions": [
            "users:read", "users:write", "groups:read", "groups:write",
            "models:read", "models:write", "knowledge:read", "knowledge:write",
            "quotas:read", "quotas:write", "logs:read", "chat:access"
        ],
        "is_system": 1
    },
    {
        "name": "manager_subscriber",
        "display_name_fa": "مشترک مدیریتی",
        "permissions": ["chat:access", "chat:file_upload", "reports:view_team"],
        "is_system": 1
    },
    {
        "name": "tech_subscriber",
        "display_name_fa": "مشترک فنی",
        "permissions": ["chat:access", "chat:file_upload", "chat:select_model"],
        "is_system": 1
    },
    {
        "name": "normal_subscriber",
        "display_name_fa": "مشترک عادی",
        "permissions": ["chat:access"],
        "is_system": 1
    }
]

INITIAL_GROUPS = [
    {
        "name": "مدیران",
        "description": "گروه راهبران و مدیران ارشد سازمان",
        "default_policy": "HYBRID",
        "daily_question_limit": 500,
        "monthly_question_limit": 15000,
        "daily_token_limit": 1000000,
        "monthly_token_limit": 30000000,
        "max_file_size_mb": 50,
        "allowed_file_types": ["pdf", "docx", "xlsx", "txt", "pptx", "csv", "png", "jpg"]
    },
    {
        "name": "کارشناسان فنی",
        "description": "گروه مهندسان و متخصصان فنی",
        "default_policy": "FREE_AI",
        "daily_question_limit": 300,
        "monthly_question_limit": 10000,
        "daily_token_limit": 800000,
        "monthly_token_limit": 25000000,
        "max_file_size_mb": 30,
        "allowed_file_types": ["pdf", "docx", "xlsx", "txt", "csv", "png", "jpg"]
    },
    {
        "name": "کاربران عمومی",
        "description": "کارکنان و مشترکان عادی سازمان",
        "default_policy": "HYBRID",
        "daily_question_limit": 50,
        "monthly_question_limit": 1500,
        "daily_token_limit": 100000,
        "monthly_token_limit": 3000000,
        "max_file_size_mb": 15,
        "allowed_file_types": ["pdf", "docx", "txt", "png", "jpg"]
    }
]

INITIAL_SETTINGS = [
    ("auth_mode", "BOTH", "روش ورود کاربران به سامانه (LOCAL_ONLY, AD_ONLY, BOTH)"),
    ("default_response_policy", "HYBRID", "سیاست پاسخگویی پیش‌فرض هوش مصنوعی (KNOWLEDGE_ONLY, HYBRID, FREE_AI)"),
    ("default_ai_language", "fa", "زبان پیش‌فرض پاسخ‌دهی سیستم (fa, en)"),
    ("max_file_size_mb", "25", "حداکثر سقف مجاز آپلود فایل به مگابایت"),
    ("allow_file_upload_globally", "true", "مجوز سراسری ارسال فایل در چت"),
    ("session_timeout_minutes", "480", "مدت اعتبار نشست کاری کاربران به دقیقه")
]

def seed_database():
    """Seed initial records idempotently."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # 1. Seed Roles
    role_map = {}
    for r in INITIAL_ROLES:
        cursor.execute("SELECT id FROM roles WHERE name = ?", (r["name"],))
        row = cursor.fetchone()
        if not row:
            role_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO roles (id, name, display_name_fa, permissions, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (role_id, r["name"], r["display_name_fa"], json.dumps(r["permissions"]), r["is_system"], now)
            )
            role_map[r["name"]] = role_id
        else:
            role_map[r["name"]] = row["id"]

    # 2. Seed Groups
    group_map = {}
    for g in INITIAL_GROUPS:
        cursor.execute("SELECT id FROM groups WHERE name = ?", (g["name"],))
        row = cursor.fetchone()
        if not row:
            group_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO groups (
                    id, name, description, default_policy, allow_model_selection,
                    daily_question_limit, monthly_question_limit, daily_token_limit,
                    monthly_token_limit, max_file_size_mb, allowed_file_types, created_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id, g["name"], g["description"], g["default_policy"],
                    g["daily_question_limit"], g["monthly_question_limit"],
                    g["daily_token_limit"], g["monthly_token_limit"],
                    g["max_file_size_mb"], json.dumps(g["allowed_file_types"]), now
                )
            )
            group_map[g["name"]] = group_id
        else:
            group_map[g["name"]] = row["id"]

    # 3. Seed Super Admin User
    admin_username = settings.SUPER_ADMIN_USERNAME
    cursor.execute("SELECT id FROM users WHERE username = ?", (admin_username,))
    admin_row = cursor.fetchone()
    if not admin_row:
        admin_id = str(uuid.uuid4())
        hashed_pwd = hash_password(settings.SUPER_ADMIN_PASSWORD)
        cursor.execute(
            """
            INSERT INTO users (
                id, username, email, password_hash, first_name, last_name,
                auth_type, department, role_id, group_id, is_active, can_upload_files, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'LOCAL', 'مدیریت فناوری اطلاعات', ?, ?, 1, 1, ?)
            """,
            (
                admin_id, admin_username, settings.SUPER_ADMIN_EMAIL, hashed_pwd,
                "مدیر کل", "سامانه", role_map["super_admin"], group_map["مدیران"], now
            )
        )

    # 4. Seed System Settings
    for key, val, desc in INITIAL_SETTINGS:
        cursor.execute("SELECT key FROM system_settings WHERE key = ?", (key,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO system_settings (key, value, description_fa, updated_at) VALUES (?, ?, ?, ?)",
                (key, val, desc, now)
            )

    # 5. Seed Default Active Directory Configuration
    cursor.execute("SELECT id FROM active_directory_configs LIMIT 1")
    if not cursor.fetchone():
        ad_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO active_directory_configs (
                id, is_enabled, server_host, port, port_ssl, use_ssl,
                domain_name, base_dn, user_search_base, group_search_base,
                bind_dn, encrypted_bind_password, allowed_groups, group_role_mapping,
                auto_provision, updated_at
            ) VALUES (?, 0, 'dc1.enterprise.local', 389, 636, 0,
                      'enterprise.local', 'DC=enterprise,DC=local',
                      'CN=Users,DC=enterprise,DC=local', 'CN=Groups,DC=enterprise,DC=local',
                      'CN=svc_ai,CN=Users,DC=enterprise,DC=local', '',
                      ?, ?, 1, ?)
            """,
            (
                ad_id,
                json.dumps(["Domain Admins", "IT-Staff", "Enterprise-Users"]),
                json.dumps({"Domain Admins": "super_admin", "IT-Staff": "tech_subscriber"}),
                now
            )
        )

    # 6. Seed Default AI Providers and Models (Phase 3)
    cursor.execute("SELECT id FROM ai_providers WHERE name = 'سرویس هوش مصنوعی پیش‌فرض (Mock / Local)'")
    mock_prov = cursor.fetchone()
    if not mock_prov:
        prov_id = str(uuid.uuid4())
        enc_key = encrypt_sensitive_data("mock-enterprise-api-key-safe")
        cursor.execute("""
            INSERT INTO ai_providers (
                id, name, provider_type, base_url, encrypted_api_key, is_active, config_params, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prov_id, "سرویس هوش مصنوعی پیش‌فرض (Mock / Local)", "MOCK", None,
            enc_key, 1, json.dumps({}), now
        ))
        
        # Seed default models
        model1_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ai_models (
                id, provider_id, model_identifier, display_name_fa,
                is_active, is_default, input_cost_per_k_tokens,
                output_cost_per_k_tokens, max_context_tokens,
                fallback_model_id, created_at
            ) VALUES (?, ?, ?, ?, 1, 1, 0.005, 0.015, 32000, NULL, ?)
        """, (model1_id, prov_id, "enterprise-smart-v1", "مدل هوشمند سازمانی (پیش‌فرض)", now))

        model2_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO ai_models (
                id, provider_id, model_identifier, display_name_fa,
                is_active, is_default, input_cost_per_k_tokens,
                output_cost_per_k_tokens, max_context_tokens,
                fallback_model_id, created_at
            ) VALUES (?, ?, ?, ?, 1, 0, 0.001, 0.002, 16000, ?, ?)
        """, (model2_id, prov_id, "enterprise-fast-v1", "مدل سریع و سبک سازمانی", model1_id, now))

    conn.commit()
    conn.close()

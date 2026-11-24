"""
Enterprise Database Connector & Session Manager
Supports both PostgreSQL + SQLAlchemy in production Docker containers,
and an embedded transactional SQLite engine for standalone/offline host environments.
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
from pathlib import Path

from app.core.config import settings

# ------------------------------------------------------------------------------
# Embedded Relational Engine for Standalone / Local Execution
# ------------------------------------------------------------------------------

class StandaloneDB:
    """Lightweight SQLite-backed relational engine for standalone execution."""
    _instance = None

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Env override first (Docker volume), then SQLite file in backend root
            env_path = os.environ.get("DB_PATH")
            if env_path:
                self.db_path = env_path
            else:
                backend_dir = Path(__file__).resolve().parent.parent.parent
                self.db_path = str(backend_dir / "enterprise_ai.db")
        else:
            self.db_path = db_path
        # Ensure the parent directory exists (Docker volume mount points)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_sqlite_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def _init_sqlite_schema(self):
        """Create all tables required by the Enterprise AI Platform."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 1. Roles table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name_fa TEXT NOT NULL,
            permissions TEXT NOT NULL,
            is_system INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

        # 2. Groups table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            default_policy TEXT DEFAULT 'HYBRID',
            default_model_id TEXT,
            allow_model_selection INTEGER DEFAULT 1,
            daily_question_limit INTEGER DEFAULT 100,
            monthly_question_limit INTEGER DEFAULT 3000,
            daily_token_limit INTEGER DEFAULT 200000,
            monthly_token_limit INTEGER DEFAULT 5000000,
            max_file_size_mb INTEGER DEFAULT 25,
            allowed_file_types TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 3. Users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            auth_type TEXT DEFAULT 'LOCAL', -- 'LOCAL' or 'ACTIVE_DIRECTORY'
            department TEXT,
            role_id TEXT,
            group_id TEXT,
            is_active INTEGER DEFAULT 1,
            expires_at TEXT,
            default_model_id TEXT,
            allow_model_selection INTEGER DEFAULT 1,
            override_policy TEXT,
            custom_daily_limit INTEGER,
            custom_monthly_limit INTEGER,
            can_upload_files INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES roles (id),
            FOREIGN KEY (group_id) REFERENCES groups (id)
        )
        """)

        # 4. Active Directory Configuration table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS active_directory_configs (
            id TEXT PRIMARY KEY,
            is_enabled INTEGER DEFAULT 0,
            server_host TEXT NOT NULL,
            port INTEGER DEFAULT 389,
            port_ssl INTEGER DEFAULT 636,
            use_ssl INTEGER DEFAULT 0,
            domain_name TEXT NOT NULL,
            base_dn TEXT NOT NULL,
            user_search_base TEXT,
            group_search_base TEXT,
            bind_dn TEXT,
            encrypted_bind_password TEXT,
            allowed_groups TEXT,
            group_role_mapping TEXT,
            auto_provision INTEGER DEFAULT 1,
            updated_at TEXT NOT NULL
        )
        """)

        # 5. System Settings table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            description_fa TEXT,
            updated_at TEXT NOT NULL
        )
        """)

        # 6. AI Providers table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_providers (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            provider_type TEXT NOT NULL, -- 'OPENAI', 'ANTHROPIC', 'GEMINI', 'CUSTOM', 'OPENAI_COMPATIBLE'
            base_url TEXT,
            encrypted_api_key TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            config_params TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 7. AI Models table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_models (
            id TEXT PRIMARY KEY,
            provider_id TEXT NOT NULL,
            model_identifier TEXT NOT NULL,
            display_name_fa TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_default INTEGER DEFAULT 0,
            input_cost_per_k_tokens REAL DEFAULT 0.0,
            output_cost_per_k_tokens REAL DEFAULT 0.0,
            max_context_tokens INTEGER DEFAULT 32000,
            fallback_model_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (provider_id) REFERENCES ai_providers (id)
        )
        """)

        # 7.1 Group Model Permissions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_model_permissions (
            group_id TEXT NOT NULL,
            model_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (group_id, model_id),
            FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE CASCADE,
            FOREIGN KEY (model_id) REFERENCES ai_models (id) ON DELETE CASCADE
        )
        """)

        # 8. Knowledge Categories table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_categories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 9. Knowledge Documents table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id TEXT PRIMARY KEY,
            category_id TEXT NOT NULL,
            title TEXT NOT NULL,
            document_type TEXT NOT NULL, -- 'FAQ', 'PDF', 'DOCX', 'TXT'
            content_text TEXT NOT NULL,
            status TEXT DEFAULT 'APPROVED', -- 'PENDING', 'APPROVED', 'REJECTED'
            version INTEGER DEFAULT 1,
            created_by TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES knowledge_categories (id)
        )
        """)

        # 10. Knowledge Chunks (Embeddings) table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            embedding_json TEXT,
            metadata_json TEXT,
            FOREIGN KEY (document_id) REFERENCES knowledge_documents (id) ON DELETE CASCADE
        )
        """)

        # 11. Conversations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model_id TEXT,
            title TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """)

        # 12. Messages table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            sender_role TEXT NOT NULL, -- 'user' or 'assistant'
            content TEXT NOT NULL,
            model_id TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            processing_time_sec REAL DEFAULT 0.0,
            response_policy_used TEXT,
            citations_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
        )
        """)

        # 13. Audit Logs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            actor_user_id TEXT,
            actor_username TEXT,
            action_type TEXT NOT NULL, -- 'LOGIN', 'USER_CREATE', 'CONFIG_CHANGE', etc.
            target_resource TEXT NOT NULL,
            target_id TEXT,
            old_values TEXT,
            new_values TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 14. Usage Metrics table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_metrics (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            model_id TEXT,
            usage_date TEXT NOT NULL,
            question_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            estimated_cost REAL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)

        conn.commit()
        conn.close()

    def _migrate(self):
        """Lightweight idempotent migrations for schema evolution."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # conversations.deleted_at — user-side soft delete (admin history is unaffected)
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(conversations)").fetchall()]
        if 'deleted_at' not in cols:
            cursor.execute("ALTER TABLE conversations ADD COLUMN deleted_at TEXT")
        conn.commit()
        conn.close()

# Global database instance
db = StandaloneDB()
db._migrate()

def get_db_connection() -> sqlite3.Connection:
    """Dependency / helper to get an active database connection."""
    return db.get_connection()

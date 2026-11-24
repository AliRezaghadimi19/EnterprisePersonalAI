#!/usr/bin/env python3
"""
Enterprise AI Platform - Standalone Production-Ready Web & API Server
Serves both the REST API and the Persian RTL Enterprise Web Application.
Zero external pip dependencies required for immediate execution.
"""

import os
import sys
import json
import uuid
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, List, Optional

# Ensure backend root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings
from app.core.security import decode_token
from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException
from app.services.seeder import seed_database
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service
from app.services.user_service import user_service
from app.services.group_service import group_service
from app.services.role_service import role_service
from app.core.ldap_auth import LDAPAuthenticator
from app.core.security import encrypt_sensitive_data
from app.schemas.user_management import UserCreate, UserUpdate, GroupCreate, GroupUpdate, RoleCreate, RoleUpdate
from app.services.ai_model_service import ai_model_service
from app.services.knowledge_service import knowledge_service
from app.services.chat_service import chat_service
from app.services import admin_service
from app.schemas.ai_management import AIProviderCreate, AIProviderUpdate, AIModelCreate, AIModelUpdate
from app.schemas.knowledge import KnowledgeCategoryCreate, KnowledgeDocumentCreate, KnowledgeDocumentUpdate, SemanticSearchRequest
from app.schemas.chat import ConversationCreate, SendMessageRequest

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class EnterpriseAIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: Any):
        def _default(o):
            if hasattr(o, "model_dump"):
                return o.model_dump()
            if hasattr(o, "__dict__"):
                return {k: v for k, v in o.__dict__.items() if not k.startswith('_')}
            return str(o)
        body = json.dumps(data, ensure_ascii=False, default=_default).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, status_code: int, body: bytes, content_type: str, extra_headers: Optional[Dict[str, str]] = None):
        """Send raw bytes (CSV / backup downloads)."""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content: str):
        body = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def _get_bearer_user(self):
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header[7:].strip()
        payload = decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        return auth_service.get_current_user_by_id(payload.get("sub"))

    def _read_json_body(self):
        content_len = int(self.headers.get('Content-Length', 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode('utf-8')
        return json.loads(raw)

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path

        # 1. Health checks
        if path in ('/health', '/api/v1/health'):
            return self._send_json(200, {
                "status": "healthy",
                "service": "Enterprise AI Assistant Server",
                "version": "1.0.0",
                "language": "fa"
            })

        # 2. Get current user profile
        if path == '/api/v1/auth/me':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "توکن احراز هویت نامعتبر است."})
            return self._send_json(200, user)

        # 3. Get AD Settings
        if path == '/api/v1/ad-settings':
            user = self._get_bearer_user()
            if not user or user.get("role_name") != "super_admin":
                return self._send_json(403, {"success": False, "message": "دسترسی منحصر به مدیر کل است."})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM active_directory_configs LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if not row:
                return self._send_json(404, {"success": False, "message": "تنظیمات AD یافت نشد."})
            return self._send_json(200, {
                "id": row["id"],
                "is_enabled": bool(row["is_enabled"]),
                "server_host": row["server_host"],
                "port": row["port"],
                "port_ssl": row["port_ssl"],
                "use_ssl": bool(row["use_ssl"]),
                "domain_name": row["domain_name"],
                "base_dn": row["base_dn"],
                "user_search_base": row["user_search_base"],
                "group_search_base": row["group_search_base"],
                "bind_dn": row["bind_dn"],
                "allowed_groups": json.loads(row["allowed_groups"]) if row["allowed_groups"] else [],
                "group_role_mapping": json.loads(row["group_role_mapping"]) if row["group_role_mapping"] else {},
                "auto_provision": bool(row["auto_provision"]),
                "has_bind_password": bool(row["encrypted_bind_password"]),
                "updated_at": row["updated_at"]
            })

        # 4. Get System Settings
        if path == '/api/v1/settings':
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM system_settings")
            rows = cursor.fetchall()
            conn.close()
            s_dict = {r["key"]: r["value"] for r in rows}
            return self._send_json(200, {
                "auth_mode": s_dict.get("auth_mode", "BOTH"),
                "default_response_policy": s_dict.get("default_response_policy", "HYBRID"),
                "default_ai_language": s_dict.get("default_ai_language", "fa"),
                "max_file_size_mb": int(s_dict.get("max_file_size_mb", 25)),
                "allow_file_upload_globally": s_dict.get("allow_file_upload_globally", "true").lower() in ("true", "1"),
                "session_timeout_minutes": int(s_dict.get("session_timeout_minutes", 480))
            })

        # 5. Get Users list (Admin)
        if path == '/api/v1/users':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            active_raw = q.get("is_active", [None])[0]
            users_list = user_service.list_users(
                search=q.get("search", [None])[0],
                group_id=q.get("group_id", [None])[0],
                role_id=q.get("role_id", [None])[0],
                is_active=(active_raw.lower() in ("1", "true")) if active_raw is not None else None,
                auth_type=q.get("auth_type", [None])[0],
            )
            return self._send_json(200, {"users": users_list, "total": len(users_list)})

        if path.startswith('/api/v1/users/'):
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            target_id = path.split('/')[-1]
            try:
                target_user = user_service.get_user_by_id(target_id)
                return self._send_json(200, target_user)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # 6. Get Roles list (Admin)
        if path == '/api/v1/roles':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            roles = role_service.list_roles()
            return self._send_json(200, roles)

        # 7. Get Groups list (Admin)
        if path == '/api/v1/groups':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            groups = group_service.list_groups()
            return self._send_json(200, groups)

        if path.startswith('/api/v1/groups/'):
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            group_id = path.split('/')[-1]
            try:
                grp = group_service.get_group_by_id(group_id)
                return self._send_json(200, grp)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # 8. AI Providers & Models (Phase 3)
        if path == '/api/v1/ai-providers':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, ai_model_service.list_providers())

        if path == '/api/v1/ai-models':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, ai_model_service.list_models())

        if path == '/api/v1/ai-models/my-available-models':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, ai_model_service.get_user_allowed_models(user["id"]))

        # 9. Knowledge Base & RAG (Phase 4)
        if path == '/api/v1/knowledge/categories':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, knowledge_service.list_categories())

        if path == '/api/v1/knowledge/documents':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, knowledge_service.list_documents())

        # 10. Chat & Conversations (Phase 5)
        if path == '/api/v1/chat/conversations':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            return self._send_json(200, chat_service.list_user_conversations(user["id"]))

        if path.startswith('/api/v1/chat/conversations/'):
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            conv_id = path.split('/')[-1]
            try:
                detail = chat_service.get_conversation_detail(conv_id, user["id"])
                return self._send_json(200, detail)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # 10b. Admin Panel APIs (Phase 2+)
        if path == '/api/v1/admin/stats':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            days = int(q.get("days", ["30"])[0])
            try:
                return self._send_json(200, admin_service.get_dashboard_stats(days=days))
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطای آمار: {str(e)}"})

        if path == '/api/v1/admin/audit-logs':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            try:
                return self._send_json(200, audit_service.list_logs(
                    search=q.get("search", [""])[0],
                    action_type=q.get("action_type", [""])[0],
                    page=int(q.get("page", ["1"])[0]),
                    page_size=int(q.get("page_size", ["25"])[0]),
                ))
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطای لاگ‌ها: {str(e)}"})

        if path == '/api/v1/admin/conversations':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            try:
                return self._send_json(200, chat_service.list_all_conversations(
                    search=q.get("search", [""])[0],
                    user_id=q.get("user_id", [""])[0],
                    page=int(q.get("page", ["1"])[0]),
                    page_size=int(q.get("page_size", ["25"])[0]),
                ))
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطای مکالمات: {str(e)}"})

        if path.startswith('/api/v1/admin/conversations/'):
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            conv_id = path.rsplit('/', 1)[-1]
            try:
                return self._send_json(200, chat_service.admin_get_conversation_detail(conv_id))
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطا: {str(e)}"})

        if path == '/api/v1/admin/usage-report':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            try:
                return self._send_json(200, admin_service.get_usage_report(
                    from_date=q.get("from_date", [None])[0],
                    to_date=q.get("to_date", [None])[0],
                    group_by=q.get("group_by", ["day"])[0],
                ))
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطای گزارش: {str(e)}"})

        if path == '/api/v1/admin/export':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            q = parse_qs(url.query)
            entity = q.get("entity", ["users"])[0]
            try:
                headers, rows = admin_service.build_csv(entity)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)
            import csv as _csv
            import io as _io
            buf = _io.StringIO()
            writer = _csv.writer(buf)
            writer.writerow(headers)
            writer.writerows(rows)
            content = "﻿" + buf.getvalue()  # UTF-8 BOM for Excel Persian
            filename = f"{entity}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
            return self._send_raw(200, content.encode("utf-8"),
                                  "text/csv; charset=utf-8",
                                  {"Content-Disposition": f"attachment; filename={filename}"})

        if path == '/api/v1/admin/backup':
            user = self._get_bearer_user()
            if not user or user.get("role_name") != "super_admin":
                return self._send_json(403, {"success": False, "message": "این عملیات منحصر به مدیر کل است."})
            data = admin_service.export_backup()
            filename = f"enterprise-ai-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
            return self._send_raw(200, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
                                  "application/json; charset=utf-8",
                                  {"Content-Disposition": f"attachment; filename={filename}"})

        # 11. Web Application UI (Single Page Enterprise Portal)
        return self._send_html(ENTERPRISE_WEB_APP_HTML)

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        body = self._read_json_body()

        # Login
        if path == '/api/v1/auth/login':
            try:
                username = body.get("username", "").strip()
                password = body.get("password", "")
                auth_method = body.get("auth_method", "AUTO")
                client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
                user_agent = self.headers.get("User-Agent", "")

                result = auth_service.authenticate_user(
                    username=username,
                    password=password,
                    auth_method=auth_method,
                    ip_address=client_ip,
                    user_agent=user_agent
                )
                return self._send_json(200, result)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)
            except Exception as e:
                return self._send_json(500, {"success": False, "message": f"خطای سیستمی: {str(e)}"})

        # Refresh
        if path == '/api/v1/auth/refresh':
            try:
                token = body.get("refresh_token", "")
                res = auth_service.refresh_user_token(token)
                return self._send_json(200, res)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Test AD Connection
        if path == '/api/v1/ad-settings/test':
            user = self._get_bearer_user()
            if not user or user.get("role_name") != "super_admin":
                return self._send_json(403, {"success": False, "message": "دسترسی مجاز نیست."})
            host = body.get("server_host", "dc1.enterprise.local")
            port = int(body.get("port", 389))
            use_ssl = bool(body.get("use_ssl", False))
            client = LDAPAuthenticator(server_host=host, port=port, use_ssl=use_ssl)
            ok, msg = client.test_connection()
            return self._send_json(200, {"success": ok, "message": msg})

        # Logout
        if path == '/api/v1/auth/logout':
            user = self._get_bearer_user()
            if user:
                audit_service.log_action(
                    actor_user_id=user["id"],
                    actor_username=user["username"],
                    action_type="LOGOUT",
                    target_resource="AUTH",
                    ip_address=self.client_address[0] if self.client_address else ""
                )
            return self._send_json(200, {"success": True, "message": "خروج با موفقیت انجام شد."})

        # Create User
        if path == '/api/v1/users':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = user_service.create_user(UserCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Create Group
        if path == '/api/v1/groups':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = group_service.create_group(GroupCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Create Role
        if path == '/api/v1/roles':
            user = self._get_bearer_user()
            if not user or user.get("role_name") != "super_admin":
                return self._send_json(403, {"success": False, "message": "دسترسی منحصر به مدیر کل است."})
            try:
                created = role_service.create_role(RoleCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # AI Provider Create (Phase 3)
        if path == '/api/v1/ai-providers':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = ai_model_service.create_provider(AIProviderCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # AI Provider Test Connection
        if path == '/api/v1/ai-providers/test-connection':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            res = ai_model_service.test_provider_connection(
                provider_id=body.get("provider_id"),
                provider_type=body.get("provider_type"),
                api_key=body.get("api_key"),
                base_url=body.get("base_url")
            )
            return self._send_json(200, res)

        # AI Model Create
        if path == '/api/v1/ai-models':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = ai_model_service.create_model(AIModelCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Knowledge Category Create (Phase 4)
        if path == '/api/v1/knowledge/categories':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = knowledge_service.create_category(KnowledgeCategoryCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Knowledge Document Create
        if path == '/api/v1/knowledge/documents':
            user = self._get_bearer_user()
            if not user or user.get("role_name") not in ("super_admin", "system_admin"):
                return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})
            try:
                created = knowledge_service.create_document(KnowledgeDocumentCreate(**body), actor_user=user)
                return self._send_json(201, created)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Knowledge Semantic Search (RAG Test)
        if path == '/api/v1/knowledge/search':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            res = knowledge_service.semantic_search(SemanticSearchRequest(**body))
            return self._send_json(200, res.model_dump())

        # Chat Conversation Create (Phase 5)
        if path == '/api/v1/chat/conversations':
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            conv = chat_service.create_conversation(user["id"], ConversationCreate(**body))
            return self._send_json(201, conv)

        # Chat Send Message
        if path.startswith('/api/v1/chat/conversations/') and path.endswith('/messages'):
            user = self._get_bearer_user()
            if not user:
                return self._send_json(401, {"success": False, "message": "احراز هویت الزامی است."})
            parts = path.split('/')
            conv_id = parts[-2]
            try:
                resp = chat_service.send_message(conv_id, user["id"], SendMessageRequest(**body))
                return self._send_json(200, resp.model_dump())
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        return self._send_json(404, {"success": False, "message": "مسیر درخواستی یافت نشد."})

    def do_DELETE(self):
        url = urlparse(self.path)
        path = url.path
        user = self._get_bearer_user()
        if not user or user.get("role_name") not in ("super_admin", "system_admin"):
            return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})

        # Delete User
        if path.startswith('/api/v1/users/'):
            user_id = path.split('/')[-1]
            try:
                user_service.delete_user(user_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "کاربر با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete Group
        if path.startswith('/api/v1/groups/'):
            group_id = path.split('/')[-1]
            try:
                group_service.delete_group(group_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "گروه با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete Role
        if path.startswith('/api/v1/roles/'):
            if user.get("role_name") != "super_admin":
                return self._send_json(403, {"success": False, "message": "حذف نقش فقط توسط مدیر کل مجاز است."})
            role_id = path.split('/')[-1]
            try:
                role_service.delete_role(role_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "نقش با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete AI Provider
        if path.startswith('/api/v1/ai-providers/'):
            prov_id = path.split('/')[-1]
            try:
                ai_model_service.delete_provider(prov_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "ارائه‌دهنده با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete AI Model
        if path.startswith('/api/v1/ai-models/'):
            model_id = path.split('/')[-1]
            try:
                ai_model_service.delete_model(model_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "مدل با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete Knowledge Category
        if path.startswith('/api/v1/knowledge/categories/'):
            cat_id = path.split('/')[-1]
            try:
                knowledge_service.delete_category(cat_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "دسته‌بندی با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete Knowledge Document
        if path.startswith('/api/v1/knowledge/documents/'):
            doc_id = path.split('/')[-1]
            try:
                knowledge_service.delete_document(doc_id, actor_user=user)
                return self._send_json(200, {"success": True, "message": "سند با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Delete Chat Conversation
        if path.startswith('/api/v1/chat/conversations/'):
            conv_id = path.split('/')[-1]
            try:
                chat_service.delete_conversation(conv_id, user["id"])
                return self._send_json(200, {"success": True, "message": "گفتگو با موفقیت حذف شد."})
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        return self._send_json(404, {"success": False, "message": "مسیر درخواستی یافت نشد."})

    def do_PUT(self):
        url = urlparse(self.path)
        path = url.path
        body = self._read_json_body()
        user = self._get_bearer_user()
        if not user or user.get("role_name") not in ("super_admin", "system_admin"):
            return self._send_json(403, {"success": False, "message": "دسترسی غیرمجاز."})

        # Update User
        if path.startswith('/api/v1/users/'):
            user_id = path.split('/')[-1]
            try:
                updated = user_service.update_user(user_id, UserUpdate(**body), actor_user=user)
                return self._send_json(200, updated)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Update Group
        if path.startswith('/api/v1/groups/'):
            group_id = path.split('/')[-1]
            try:
                updated = group_service.update_group(group_id, GroupUpdate(**body), actor_user=user)
                return self._send_json(200, updated)
            except PersianAppException as e:
                return self._send_json(e.status_code, e.detail)

        # Super admin only operations
        if user.get("role_name") != "super_admin":
            return self._send_json(403, {"success": False, "message": "دسترسی منحصر به مدیر کل است."})

        # Update System Settings
        if path == '/api/v1/settings':
            conn = get_db_connection()
            cursor = conn.cursor()
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            for key, val in body.items():
                cursor.execute("UPDATE system_settings SET value = ?, updated_at = ? WHERE key = ?", (str(val), now, key))
            conn.commit()
            conn.close()
            audit_service.log_action(
                actor_user_id=user["id"],
                actor_username=user["username"],
                action_type="SYSTEM_SETTINGS_UPDATED",
                target_resource="SYSTEM_SETTINGS",
                new_values=body
            )
            return self._send_json(200, {"success": True, "message": "تنظیمات با موفقیت ذخیره شدند."})

        # Update AD Settings
        if path == '/api/v1/ad-settings':
            conn = get_db_connection()
            cursor = conn.cursor()
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            enc_pwd = encrypt_sensitive_data(body["bind_password"]) if body.get("bind_password") else None
            cursor.execute("""
                UPDATE active_directory_configs SET
                    is_enabled = ?, server_host = ?, port = ?, domain_name = ?,
                    base_dn = ?, auto_provision = ?, updated_at = ?
                WHERE id = (SELECT id FROM active_directory_configs LIMIT 1)
            """, (
                int(body.get("is_enabled", False)), body.get("server_host", ""),
                int(body.get("port", 389)), body.get("domain_name", ""),
                body.get("base_dn", ""), int(body.get("auto_provision", True)), now
            ))
            if enc_pwd:
                cursor.execute("UPDATE active_directory_configs SET encrypted_bind_password = ?", (enc_pwd,))
            conn.commit()
            conn.close()
            audit_service.log_action(
                actor_user_id=user["id"],
                actor_username=user["username"],
                action_type="AD_CONFIG_UPDATED",
                target_resource="ACTIVE_DIRECTORY",
                new_values=body
            )
            return self._send_json(200, {"success": True, "message": "تنظیمات اکتیو دایرکتوری با موفقیت به‌روز شد."})

        return self._send_json(404, {"success": False, "message": "مسیر درخواستی یافت نشد."})

# ------------------------------------------------------------------------------
# Full Enterprise UI Single-Page Application (HTML5, Tailwind, Vazirmatn, RTL)
# ------------------------------------------------------------------------------
ENTERPRISE_WEB_APP_HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>سامانه هوش مصنوعی سازمانی | Enterprise AI Platform</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: { vazir: ['Vazirmatn', 'sans-serif'] },
          colors: {
            enterprise: { 50: '#eff6ff', 100: '#dbeafe', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
            dark: { bg: '#0b0f19', card: '#1e293b', border: '#334155', text: '#f8fafc', muted: '#94a3b8' }
          }
        }
      }
    }
  </script>
  <style>
    body { font-family: 'Vazirmatn', sans-serif; direction: rtl; text-align: right; }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-thumb { background: #94a3b8; border-radius: 4px; }
  </style>
</head>
<body class="h-full bg-slate-50 dark:bg-dark-bg text-slate-800 dark:text-dark-text transition-colors duration-200">

  <!-- TOP NOTIFICATION BANNER -->
  <div id="toast" class="fixed top-5 left-1/2 -translate-x-1/2 z-50 hidden px-6 py-3 rounded-xl shadow-xl text-white font-medium text-sm transition-all duration-300"></div>

  <!-- VIEW 1: LOGIN PAGE -->
  <div id="loginView" class="min-h-full flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md text-center">
      <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-700 to-indigo-600 shadow-lg shadow-blue-500/30 text-white mb-4">
        <svg class="w-9 h-9" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
      </div>
      <h2 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">سامانه هوش مصنوعی سازمانی</h2>
      <p class="mt-2 text-sm text-slate-500 dark:text-dark-muted">ورود ایمن کارکنان و مدیران سازمان</p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div class="bg-white dark:bg-dark-card py-8 px-6 shadow-xl rounded-2xl sm:px-10 border border-slate-200/80 dark:border-dark-border">
        <!-- Auth Method Selector Tabs -->
        <div class="flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1 mb-6">
          <button id="tabLocal" onclick="setAuthMethod('LOCAL')" class="flex-1 py-2 text-xs font-semibold rounded-lg transition-all bg-white dark:bg-dark-card shadow text-blue-600 dark:text-blue-400">حساب کاربری محلی</button>
          <button id="tabAD" onclick="setAuthMethod('ACTIVE_DIRECTORY')" class="flex-1 py-2 text-xs font-semibold rounded-lg transition-all text-slate-500 hover:text-slate-800 dark:text-dark-muted">Active Directory / Domain</button>
        </div>

        <form onsubmit="handleLogin(event)" class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1" id="lblUsername">نام کاربری</label>
            <input id="usernameInput" type="text" value="admin" required class="w-full px-4 py-2.5 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">رمز عبور</label>
            <input id="passwordInput" type="password" value="Enterprise@Admin123!" required class="w-full px-4 py-2.5 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          </div>
          <div class="flex items-center justify-between text-xs pt-1">
            <span class="text-slate-500 dark:text-dark-muted">اتصال امن رمزنگاری‌شده (TLS/HTTPS)</span>
            <button type="button" onclick="toggleTheme()" class="text-blue-600 dark:text-blue-400 hover:underline">تغییر تم</button>
          </div>
          <button type="submit" id="loginBtn" class="w-full mt-4 flex justify-center py-3 px-4 rounded-xl shadow-lg shadow-blue-500/25 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none transition-all">
            ورود به سامانه
          </button>
        </form>

        <div class="mt-6 pt-4 border-t border-slate-200 dark:border-dark-border text-center text-xs text-slate-400">
          شناسه کاربر پیش‌فرض: <code class="text-blue-600 dark:text-blue-400 font-mono">admin</code> | کلمه عبور: <code class="text-blue-600 dark:text-blue-400 font-mono">Enterprise@Admin123!</code>
        </div>
      </div>
    </div>
  </div>

  <!-- VIEW 2: ENTERPRISE MAIN PORTAL (ADMIN + CHAT) -->
  <div id="mainView" class="hidden min-h-full flex flex-row">
    <!-- RIGHT SIDEBAR (MENU-STRUCTURE OF 20 ITEMS) -->
    <aside class="w-64 bg-white dark:bg-dark-card border-l border-slate-200 dark:border-dark-border flex flex-col flex-shrink-0 select-none">
      <div class="p-5 flex items-center gap-3 border-b border-slate-200 dark:border-dark-border">
        <div class="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-lg shadow-md shadow-blue-500/30">AI</div>
        <div>
          <h1 class="font-bold text-sm text-slate-900 dark:text-white leading-tight">هوش مصنوعی سازمانی</h1>
          <span class="text-[11px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1">● نسخه عملیاتی ۱.۰</span>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto p-3 space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
        <!-- 20 Enterprise Menu Items -->
        <button onclick="switchTab('dashboard')" class="menu-item active w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>📊</span><span>۱. داشبورد مدیریت</span></button>
        <button onclick="switchTab('chat')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition text-blue-600 dark:text-blue-400 font-bold"><span>💬</span><span>محیط چت کاربران</span></button>
        <button onclick="switchTab('users')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>👥</span><span>۲. مدیریت کاربران</span></button>
        <button onclick="switchTab('groups')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>🏢</span><span>۳. مدیریت گروه‌ها</span></button>
        <button onclick="switchTab('roles')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>🛡️</span><span>۴. نقش‌ها و دسترسی‌ها</span></button>
        <button onclick="switchTab('ad')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>🌐</span><span>۵. تنظیمات Active Directory</span></button>
        <button onclick="switchTab('ai-providers')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>🔌</span><span>۶. مدیریت Providerها</span></button>
        <button onclick="switchTab('ai-models')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>🤖</span><span>۷. مدیریت مدل‌ها</span></button>
        <button onclick="switchTab('policies')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>⚖️</span><span>۸. سیاست پاسخگویی</span></button>
        <button onclick="switchTab('knowledge')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>📚</span><span>۹. پایگاه دانش (RAG)</span></button>
        <button onclick="switchTab('settings')" class="menu-item w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition"><span>⚙️</span><span>۱۰. تنظیمات سامانه</span></button>
      </nav>

      <!-- USER PROFILE FOOTER -->
      <div class="p-3 border-t border-slate-200 dark:border-dark-border bg-slate-50/50 dark:bg-slate-800/30">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs" id="userAvatar">A</div>
            <div>
              <div class="text-xs font-bold text-slate-800 dark:text-white" id="userNameLabel">مدیر کل سامانه</div>
              <div class="text-[10px] text-slate-400" id="userRoleLabel">Super Admin</div>
            </div>
          </div>
          <button onclick="handleLogout()" title="خروج از حساب" class="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>
          </button>
        </div>
      </div>
    </aside>

    <!-- MAIN CONTENT AREA -->
    <main class="flex-1 overflow-y-auto flex flex-col">
      <!-- HEADER -->
      <header class="h-14 bg-white dark:bg-dark-card border-b border-slate-200 dark:border-dark-border px-6 flex items-center justify-between">
        <div class="text-sm font-bold text-slate-800 dark:text-white" id="pageTitle">داشبورد مدیریتی</div>
        <div class="flex items-center gap-3">
          <span class="text-xs px-2.5 py-1 rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300 font-mono" id="jalaliDateBadge">امروز: ۱۵ آبان ۱۴۰۳</span>
          <button onclick="toggleTheme()" class="p-2 rounded-xl text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 text-sm">🌓</button>
        </div>
      </header>

      <!-- TAB 1: DASHBOARD -->
      <div id="tab-dashboard" class="tab-panel p-6 space-y-6">
        <!-- STATS CARDS -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="bg-white dark:bg-dark-card p-5 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <span class="text-xs text-slate-400">کل کاربران سامانه</span>
            <div class="text-2xl font-bold mt-1 text-slate-900 dark:text-white" id="statUsers">۱ کاربر فعال</div>
            <div class="text-[11px] text-emerald-600 mt-2">● ۱۰۰٪ حساب‌های فعال</div>
          </div>
          <div class="bg-white dark:bg-dark-card p-5 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <span class="text-xs text-slate-400">سهمیه روزانه باقیمانده</span>
            <div class="text-2xl font-bold mt-1 text-blue-600" id="statQuota">۵۰۰ سؤال</div>
            <div class="text-[11px] text-slate-400 mt-2">ریست خودکار در ساعت ۰۰:۰۰</div>
          </div>
          <div class="bg-white dark:bg-dark-card p-5 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <span class="text-xs text-slate-400">سیاست پاسخگویی فعال</span>
            <div class="text-2xl font-bold mt-1 text-indigo-600" id="statPolicy">Hybrid RAG</div>
            <div class="text-[11px] text-slate-400 mt-2">ترکیبی (پایگاه دانش + هوش عمومی)</div>
          </div>
          <div class="bg-white dark:bg-dark-card p-5 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <span class="text-xs text-slate-400">ارتباط با اکتیو دایرکتوری</span>
            <div class="text-2xl font-bold mt-1 text-emerald-600" id="statAD">آماده به کار</div>
            <div class="text-[11px] text-slate-400 mt-2">حالت ورود دوگانه (BOTH)</div>
          </div>
        </div>

        <!-- QUICK ACTION CARDS -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <h3 class="font-bold text-sm mb-4">آزمون هوش مصنوعی و ورود به چت</h3>
            <p class="text-xs text-slate-500 mb-4 leading-relaxed">کاربران سازمان از این پنجره می‌توانند با حفظ کامل حریم خصوصی و تفکیک سازمانی مستندات، پرسش‌های خود را با پشتیبانی از مدل‌های هوش مصنوعی مطرح نمایند.</p>
            <button onclick="switchTab('chat')" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow">ورود به محیط گفت‌وگو 💬</button>
          </div>
          <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm">
            <h3 class="font-bold text-sm mb-4">وضعیت اتصال پایگاه داده و امبدینگ</h3>
            <div class="space-y-2 text-xs">
              <div class="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span class="text-slate-400">پایگاه داده:</span>
                <span class="font-mono text-emerald-600 font-semibold">PostgreSQL / SQLite Dual Engine</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span class="text-slate-400">موتور برداری:</span>
                <span class="font-mono text-blue-600 font-semibold">pgvector Semantic Search</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-slate-400">رمزنگاری کلیدها:</span>
                <span class="font-mono text-indigo-600 font-semibold">Fernet / AES Authenticated</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 2: CHAT INTERFACE (CHATGPT-LIKE RTL) -->
      <div id="tab-chat" class="tab-panel hidden flex-1 flex flex-col h-[calc(100vh-3.5rem)]">
        <!-- CHAT HEADER WITH MODEL BADGE AND QUOTA -->
        <div class="px-6 py-3 border-b border-slate-200 dark:border-dark-border bg-white dark:bg-dark-card flex items-center justify-between text-xs">
          <div class="flex items-center gap-3">
            <span class="font-bold">مدل فعال:</span>
            <span class="px-2.5 py-1 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 font-medium">Enterprise Assistant (GPT-4o / Claude 3.5 Sonnet)</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-slate-400">سهمیه باقیمانده امروز:</span>
            <span class="font-bold text-blue-600" id="chatQuotaBadge">۴۹۹ سؤال</span>
          </div>
        </div>

        <!-- MESSAGES SCROLL AREA -->
        <div id="chatMessages" class="flex-1 overflow-y-auto p-6 space-y-4">
          <!-- ASSISTANT WELCOME MESSAGE -->
          <div class="flex items-start gap-3 max-w-3xl">
            <div class="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">AI</div>
            <div class="bg-white dark:bg-dark-card p-4 rounded-2xl rounded-tr-none border border-slate-200 dark:border-dark-border text-xs leading-relaxed shadow-sm">
              <p class="font-semibold mb-1 text-blue-600 dark:text-blue-400">سامانه هوش مصنوعی سازمانی</p>
              سلام! من دستیار هوشمند سازمانی شما هستم. کلیه پاسخ‌ها بر اساس سیاست‌های دسترسی تعریف‌شده توسط مدیر سازمان، پایگاه دانش سازمانی (RAG) و مدل‌های زبانی مجاز ارائه می‌شوند. چگونه می‌توانم به شما کمک کنم؟
            </div>
          </div>
        </div>

        <!-- CHAT INPUT BAR -->
        <div class="p-4 bg-white dark:bg-dark-card border-t border-slate-200 dark:border-dark-border">
          <form onsubmit="handleSendMessage(event)" class="max-w-4xl mx-auto flex items-center gap-2">
            <input id="chatInput" type="text" placeholder="پیام خود را به فارسی بنویسید..." class="flex-1 px-4 py-3 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
            <button type="submit" class="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow transition">ارسال 🚀</button>
          </form>
        </div>
      </div>

      <!-- TAB 3: ACTIVE DIRECTORY SETTINGS -->
      <div id="tab-ad" class="tab-panel hidden p-6 max-w-4xl space-y-6">
        <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm">
          <div class="flex items-center justify-between mb-4 pb-3 border-b border-slate-100 dark:border-dark-border">
            <div>
              <h3 class="font-bold text-sm text-slate-800 dark:text-white">پیکربندی اتصال به Active Directory / LDAPS</h3>
              <p class="text-xs text-slate-400 mt-1">تنظیمات کنترلر دامنه جهت احراز هویت یکپارچه سازمانی (SSO)</p>
            </div>
            <button onclick="testADConnection()" id="btnTestAD" class="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-blue-600 text-xs font-semibold hover:bg-slate-200 transition">تست زنده اتصال 🔌</button>
          </div>

          <form onsubmit="handleSaveADSettings(event)" class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div>
              <label class="block font-semibold mb-1">آدرس کنترلر دامنه (Domain Controller)</label>
              <input id="adHost" type="text" value="dc1.enterprise.local" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <div>
              <label class="block font-semibold mb-1">نام دامنه (Domain Name)</label>
              <input id="adDomain" type="text" value="enterprise.local" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <div>
              <label class="block font-semibold mb-1">پورت LDAP</label>
              <input id="adPort" type="number" value="389" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <div>
              <label class="block font-semibold mb-1">Base DN</label>
              <input id="adBaseDN" type="text" value="DC=enterprise,DC=local" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
            </div>
            <div class="md:col-span-2">
              <label class="block font-semibold mb-1">حساب سرویس Bind (Bind Account DN)</label>
              <input id="adBindDN" type="text" value="CN=svc_ai,CN=Users,DC=enterprise,DC=local" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
            </div>
            <div class="md:col-span-2 flex items-center gap-2 pt-2">
              <input id="adAutoProvision" type="checkbox" checked class="rounded text-blue-600">
              <label for="adAutoProvision">ایجاد خودکار پروفایل کاربران AD در اولین ورود موفق (Auto-Provisioning)</label>
            </div>
            <div class="md:col-span-2 pt-2">
              <button type="submit" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow">ذخیره تنظیمات Active Directory</button>
            </div>
          </form>
        </div>
      </div>

      <!-- TAB 4: USERS MANAGEMENT -->
      <div id="tab-users" class="tab-panel hidden p-6 space-y-6">
        <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm">
          <div class="flex flex-col sm:flex-row items-center justify-between gap-4 mb-4">
            <div>
              <h3 class="font-bold text-sm">مدیریت کاربران سازمان</h3>
              <p class="text-xs text-slate-400">کنترل دسترسی، سهمیه‌ها و نوع احراز هویت اعضا</p>
            </div>
            <div class="flex items-center gap-2 w-full sm:w-auto">
              <input id="userSearchInput" oninput="loadUsersList()" type="text" placeholder="جستجو در کاربران..." class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-dark-border text-xs bg-slate-50 dark:bg-slate-800">
              <button onclick="openCreateUserModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow flex items-center gap-1 flex-shrink-0">
                <span>+</span><span>کاربر جدید</span>
              </button>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-right text-xs">
              <thead class="bg-slate-50 dark:bg-slate-800/50 text-slate-500">
                <tr>
                  <th class="p-3">نام و نام خانوادگی</th>
                  <th class="p-3">نام کاربری</th>
                  <th class="p-3">نوع ورود</th>
                  <th class="p-3">نقش</th>
                  <th class="p-3">گروه سازمانی</th>
                  <th class="p-3">سیاست مؤثر</th>
                  <th class="p-3">سهمیه روزانه</th>
                  <th class="p-3">وضعیت</th>
                  <th class="p-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody id="usersTableBody" class="divide-y divide-slate-100 dark:divide-dark-border">
                <!-- Injected via API -->
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- EDIT USER MODAL -->
      <div id="editUserModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4 max-h-[92vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <h3 class="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <span class="text-blue-600">✏️</span><span>ویرایش مشخصات، گروه و رمز عبور کاربر</span>
            </h3>
            <button onclick="closeEditUserModal()" class="text-slate-400 hover:text-slate-600 dark:hover:text-white text-lg font-bold">✕</button>
          </div>
          <form id="editUserForm" onsubmit="submitEditUser(event)" class="space-y-3.5 text-xs">
            <input type="hidden" id="editUserId">
            <div>
              <label class="block font-medium mb-1 text-slate-500">نام کاربری (غیرقابل تغییر)</label>
              <input id="editUsername" type="text" disabled class="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-dark-border bg-slate-100 dark:bg-slate-800/80 text-slate-500 font-mono">
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block font-medium mb-1">نام</label>
                <input id="editFirstName" type="text" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
              </div>
              <div>
                <label class="block font-medium mb-1">نام خانوادگی</label>
                <input id="editLastName" type="text" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
              </div>
            </div>
            <div>
              <label class="block font-medium mb-1">گروه سازمانی</label>
              <select id="editGroupId" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-medium text-slate-800 dark:text-slate-100">
                <!-- Injected via API -->
              </select>
            </div>
            <div>
              <label class="block font-medium mb-1">نقش کاربری (RBAC)</label>
              <select id="editRoleId" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-medium text-slate-800 dark:text-slate-100">
                <!-- Injected via API -->
              </select>
            </div>
            <div class="p-3 bg-amber-50/70 dark:bg-amber-950/20 rounded-xl border border-amber-200/60 dark:border-amber-900/40">
              <label class="block font-medium mb-1 text-amber-900 dark:text-amber-200">تغییر رمز عبور کاربر</label>
              <input id="editPassword" type="password" placeholder="در صورت خالی ماندن، رمز عبور تغییر نخواهد کرد" class="w-full px-3 py-2 rounded-xl border border-amber-300 dark:border-amber-800/50 bg-white dark:bg-slate-800 text-xs">
              <span class="text-[10px] text-amber-700 dark:text-amber-400 mt-1 block">تنها در صورتی که می‌خواهید رمز جدید ست کنید، این فیلد را پر کنید.</span>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block font-medium mb-1">سیاست پاسخگویی اختصاصی</label>
                <select id="editOverridePolicy" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
                  <option value="">ارث‌بری از گروه سازمانی</option>
                  <option value="HYBRID">ترکیبی (Hybrid RAG)</option>
                  <option value="KNOWLEDGE_ONLY">صرفاً پایگاه دانش (Knowledge Only)</option>
                  <option value="FREE_AI">آزاد (Free AI)</option>
                </select>
              </div>
              <div>
                <label class="block font-medium mb-1">سهمیه روزانه اختصاصی</label>
                <input id="editCustomDailyLimit" type="number" placeholder="خالی = ارث‌بری از گروه" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
              </div>
            </div>
            <div class="flex items-center gap-2 pt-1">
              <input id="editIsActive" type="checkbox" class="rounded text-blue-600 focus:ring-blue-500 w-4 h-4">
              <label for="editIsActive" class="font-medium cursor-pointer">حساب کاربری فعال باشد</label>
            </div>
            <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <button type="button" onclick="closeEditUserModal()" class="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold">انصراف</button>
              <button type="submit" class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow">ذخیره تغییرات</button>
            </div>
          </form>
        </div>
      </div>

      <!-- TAB: GROUPS MANAGEMENT -->
      <div id="tab-groups" class="tab-panel hidden p-6 space-y-6">
        <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-bold text-sm">مدیریت گروه‌های سازمانی</h3>
              <p class="text-xs text-slate-400">تعیین سقف توکن، سهمیه روزانه و فایل‌های مجاز هر واحد</p>
            </div>
            <button onclick="openCreateGroupModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow">
              + تعریف گروه جدید
            </button>
          </div>
          <div id="groupsGrid" class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <!-- Injected via API -->
          </div>
        </div>
      </div>

      <!-- EDIT GROUP MODAL -->
      <div id="editGroupModal" class="hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
        <div class="bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4 max-h-[92vh] overflow-y-auto">
          <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
            <h3 class="font-bold text-sm text-slate-900 dark:text-white flex items-center gap-2">
              <span class="text-blue-600">🏢</span><span>ویرایش تنظیمات و سهمیه‌های گروه</span>
            </h3>
            <button onclick="closeEditGroupModal()" class="text-slate-400 hover:text-slate-600 dark:hover:text-white text-lg font-bold">✕</button>
          </div>
          <form id="editGroupForm" onsubmit="submitEditGroup(event)" class="space-y-3.5 text-xs">
            <input type="hidden" id="editGroupIdVal">
            <div>
              <label class="block font-medium mb-1">نام گروه سازمانی</label>
              <input id="editGroupName" type="text" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <div>
              <label class="block font-medium mb-1">توضیحات عملکرد گروه</label>
              <input id="editGroupDesc" type="text" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <div>
              <label class="block font-medium mb-1">سیاست پاسخگویی پیش‌فرض</label>
              <select id="editGroupPolicy" required class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-medium">
                <option value="HYBRID">ترکیبی (Hybrid RAG: پایگاه دانش + هوش عمومی)</option>
                <option value="KNOWLEDGE_ONLY">صرفاً پایگاه دانش (Knowledge Only: عدم پاسخ بدون منبع)</option>
                <option value="FREE_AI">آزاد (Free AI: پاسخ عمومی بدون محدودیت منبع)</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block font-medium mb-1">سهمیه روزانه سؤال</label>
                <input id="editGroupDailyQuestion" type="number" required min="1" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
              </div>
              <div>
                <label class="block font-medium mb-1">سهمیه ماهانه سؤال</label>
                <input id="editGroupMonthlyQuestion" type="number" required min="1" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block font-medium mb-1">سقف توکن روزانه</label>
                <input id="editGroupDailyToken" type="number" required min="1000" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
              </div>
              <div>
                <label class="block font-medium mb-1">سقف توکن ماهانه</label>
                <input id="editGroupMonthlyToken" type="number" required min="10000" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block font-medium mb-1">حداکثر حجم فایل (مگابایت)</label>
                <input id="editGroupMaxFileSize" type="number" required min="1" max="500" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 font-mono">
              </div>
              <div>
                <label class="block font-medium mb-1">اجازه انتخاب مدل</label>
                <select id="editGroupAllowModel" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
                  <option value="true">مجاز</option>
                  <option value="false">غیرمجاز (فقط مدل پیش‌فرض)</option>
                </select>
              </div>
            </div>
            <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <button type="button" onclick="closeEditGroupModal()" class="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-semibold">انصراف</button>
              <button type="submit" class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow">ذخیره تنظیمات گروه</button>
            </div>
          </form>
        </div>
      </div>

      <!-- TAB: ROLES & RBAC -->
      <div id="tab-roles" class="tab-panel hidden p-6 space-y-6">
        <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="font-bold text-sm">نقش‌ها و ماتریس دسترسی (RBAC)</h3>
              <p class="text-xs text-slate-400">نقش‌های پایه سیستم و نقش‌های سفارشی تعریف‌شده توسط مدیر</p>
            </div>
            <button onclick="openCreateRoleModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow">
              + تعریف نقش سفارشی
            </button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-right text-xs">
              <thead class="bg-slate-50 dark:bg-slate-800/50 text-slate-500">
                <tr>
                  <th class="p-3">عنوان فارسی نقش</th>
                  <th class="p-3">شناسه سیستمی</th>
                  <th class="p-3">نوع نقش</th>
                  <th class="p-3">مجوزهای دسترسی</th>
                  <th class="p-3 text-center">عملیات</th>
                </tr>
              </thead>
              <tbody id="rolesTableBody" class="divide-y divide-slate-100 dark:divide-dark-border">
                <!-- Injected via API -->
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- TAB 5: SYSTEM SETTINGS -->
      <div id="tab-settings" class="tab-panel hidden p-6 max-w-3xl space-y-6">
        <div class="bg-white dark:bg-dark-card p-6 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm">
          <h3 class="font-bold text-sm mb-4">تنظیمات اصلی سامانه</h3>
          <form onsubmit="handleSaveSystemSettings(event)" class="space-y-4 text-xs">
            <div>
              <label class="block font-semibold mb-1">روش احراز هویت مجاز کاربران</label>
              <select id="sysAuthMode" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
                <option value="BOTH">ورود دوگانه (هم حساب کاربری محلی و هم Active Directory)</option>
                <option value="LOCAL_ONLY">فقط کاربران محلی</option>
                <option value="AD_ONLY">فقط کاربران Active Directory</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">سیاست پاسخگویی پیش‌فرض هوش مصنوعی</label>
              <select id="sysPolicy" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
                <option value="HYBRID">ترکیبی (Hybrid RAG: اولویت با پایگاه دانش، سپس هوش عمومی)</option>
                <option value="KNOWLEDGE_ONLY">صرفاً پایگاه دانش (Knowledge Only: عدم پاسخ بدون منبع مستند)</option>
                <option value="FREE_AI">آزاد (Free AI: پاسخ عمومی بدون محدودیت منبع)</option>
              </select>
            </div>
            <div>
              <label class="block font-semibold mb-1">حداکثر سقف مجاز فایل‌های ارسالی (مگابایت)</label>
              <input id="sysMaxFileSize" type="number" value="25" class="w-full px-3 py-2 rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800">
            </div>
            <button type="submit" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow">به‌روزرسانی تنظیمات سراسری</button>
          </form>
        </div>
      </div>

      <!-- TAB 8: AI PROVIDERS (PHASE 3) -->
      <div id="tab-ai-providers" class="tab-panel hidden p-6 space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-slate-900 dark:text-white">ارائه‌دهندگان هوش مصنوعی (AI Providers)</h2>
            <p class="text-xs text-slate-500 mt-1">مدیریت اتصال به ارائه‌دهندگان ابری و محلی با رمزنگاری کلیدهای دسترسی</p>
          </div>
          <button onclick="openCreateProviderModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow flex items-center gap-1.5">+ افزودن ارائه‌دهنده جدید</button>
        </div>
        <div class="bg-white dark:bg-dark-card rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm overflow-hidden">
          <table class="w-full text-xs text-right">
            <thead class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-dark-border text-slate-500">
              <tr>
                <th class="p-3">نام نمایشی</th>
                <th class="p-3">نوع سرویس</th>
                <th class="p-3">کلید API (ماسک‌شده)</th>
                <th class="p-3">تعداد مدل‌ها</th>
                <th class="p-3">وضعیت</th>
                <th class="p-3 text-center">آزمون اتصال</th>
                <th class="p-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody id="providersTableBody" class="divide-y divide-slate-100 dark:divide-slate-800"></tbody>
          </table>
        </div>
      </div>

      <!-- TAB 9: AI MODELS (PHASE 3) -->
      <div id="tab-ai-models" class="tab-panel hidden p-6 space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-slate-900 dark:text-white">مدل‌های زبانی هوش مصنوعی (LLMs)</h2>
            <p class="text-xs text-slate-500 mt-1">پیکربندی پنجره کانتکست، هزینه توکن، مدل پیش‌فرض و مکانیزم Fallback</p>
          </div>
          <button onclick="openCreateModelModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow flex items-center gap-1.5">+ ثبت مدل هوش مصنوعی</button>
        </div>
        <div class="bg-white dark:bg-dark-card rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm overflow-hidden">
          <table class="w-full text-xs text-right">
            <thead class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-dark-border text-slate-500">
              <tr>
                <th class="p-3">نام نمایشی فارسی</th>
                <th class="p-3">شناسه فنی مدل</th>
                <th class="p-3">ارائه‌دهنده</th>
                <th class="p-3">کانتکست (توکن)</th>
                <th class="p-3">مدل جایگزین (Fallback)</th>
                <th class="p-3">پیش‌فرض</th>
                <th class="p-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody id="modelsTableBody" class="divide-y divide-slate-100 dark:divide-slate-800"></tbody>
          </table>
        </div>
      </div>

      <!-- TAB 10: KNOWLEDGE BASE (PHASE 4) -->
      <div id="tab-knowledge" class="tab-panel hidden p-6 space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-slate-900 dark:text-white">پایگاه دانش سازمانی و بازیابی معنایی (RAG)</h2>
            <p class="text-xs text-slate-500 mt-1">اسناد، آیین‌نامه‌ها، پرسش و پاسخ‌های متداول همراه با خردسازی (Chunking) و بردارسازی خودکار</p>
          </div>
          <div class="flex gap-2">
            <button onclick="openCreateDocModal()" class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow flex items-center gap-1.5">+ ثبت سند جدید</button>
          </div>
        </div>

        <!-- RAG SEMANTIC TEST BOX -->
        <div class="bg-white dark:bg-dark-card p-4 rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm flex items-center gap-3">
          <input id="ragTestInput" type="text" placeholder="آزمون جستجوی معنایی در پایگاه دانش (مثال: سقف مرخصی یا کمک‌هزینه ورزشی...)" class="flex-1 px-3 py-2 text-xs rounded-xl border border-slate-300 dark:border-dark-border bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <button onclick="testRAGSearch()" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow">جستجوی معنایی RAG 🔍</button>
        </div>
        <div id="ragSearchResults" class="hidden bg-indigo-50/50 dark:bg-indigo-950/20 p-4 rounded-2xl border border-indigo-100 dark:border-indigo-900/40 text-xs space-y-2"></div>

        <div class="bg-white dark:bg-dark-card rounded-2xl border border-slate-200/80 dark:border-dark-border shadow-sm overflow-hidden">
          <table class="w-full text-xs text-right">
            <thead class="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-dark-border text-slate-500">
              <tr>
                <th class="p-3">عنوان سند</th>
                <th class="p-3">دسته‌بندی</th>
                <th class="p-3">نوع سند</th>
                <th class="p-3">نسخه</th>
                <th class="p-3">تعداد چانک‌های برداری</th>
                <th class="p-3">وضعیت تایید</th>
                <th class="p-3 text-center">عملیات</th>
              </tr>
            </thead>
            <tbody id="knowledgeTableBody" class="divide-y divide-slate-100 dark:divide-slate-800"></tbody>
          </table>
        </div>
      </div>
    </main>
  </div>

  <script>
    let currentAuthMethod = 'LOCAL';
    let authToken = localStorage.getItem('access_token') || '';
    let currentUser = null;

    function showToast(message, isError = false) {
      const toast = document.getElementById('toast');
      toast.innerText = message;
      toast.className = `fixed top-5 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-xl shadow-xl text-white font-medium text-xs transition-all duration-300 ${isError ? 'bg-red-600' : 'bg-emerald-600'}`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 3500);
    }

    function toggleTheme() {
      document.documentElement.classList.toggle('dark');
    }

    function setAuthMethod(method) {
      currentAuthMethod = method;
      const tabLocal = document.getElementById('tabLocal');
      const tabAD = document.getElementById('tabAD');
      const lbl = document.getElementById('lblUsername');
      if (method === 'LOCAL') {
        tabLocal.className = "flex-1 py-2 text-xs font-semibold rounded-lg bg-white dark:bg-dark-card shadow text-blue-600 dark:text-blue-400";
        tabAD.className = "flex-1 py-2 text-xs font-semibold rounded-lg text-slate-500 hover:text-slate-800 dark:text-dark-muted";
        lbl.innerText = "نام کاربری (حساب داخلی)";
      } else {
        tabAD.className = "flex-1 py-2 text-xs font-semibold rounded-lg bg-white dark:bg-dark-card shadow text-blue-600 dark:text-blue-400";
        tabLocal.className = "flex-1 py-2 text-xs font-semibold rounded-lg text-slate-500 hover:text-slate-800 dark:text-dark-muted";
        lbl.innerText = "نام کاربری سازمانی (sAMAccountName یا UPN)";
      }
    }

    async function handleLogin(e) {
      e.preventDefault();
      const username = document.getElementById('usernameInput').value;
      const password = document.getElementById('passwordInput').value;
      const btn = document.getElementById('loginBtn');
      btn.innerText = 'در حال اعتبارسنجی...';

      try {
        const res = await fetch('/api/v1/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password, auth_method: currentAuthMethod })
        });
        const data = await res.json();
        if (!res.ok) {
          showToast(data.message || 'خطا در ورود به سامانه', true);
          btn.innerText = 'ورود به سامانه';
          return;
        }

        authToken = data.access_token;
        currentUser = data.user;
        localStorage.setItem('access_token', authToken);
        showToast('خوش آمدید! ورود موفقیت‌آمیز بود.');
        initDashboard();
      } catch (err) {
        showToast('عدم برقراری ارتباط با سرور', true);
      } finally {
        btn.innerText = 'ورود به سامانه';
      }
    }

    function initDashboard() {
      document.getElementById('loginView').classList.add('hidden');
      document.getElementById('mainView').classList.remove('hidden');
      const fn = (currentUser && currentUser.first_name) ? currentUser.first_name : 'مدیر';
      const ln = (currentUser && currentUser.last_name) ? currentUser.last_name : '';
      const rn = (currentUser && (currentUser.role_display_name_fa || currentUser.role_name)) ? (currentUser.role_display_name_fa || currentUser.role_name) : 'کاربر';
      document.getElementById('userNameLabel').innerText = `${fn} ${ln}`.trim();
      document.getElementById('userRoleLabel').innerText = rn;
      document.getElementById('userAvatar').innerText = fn[0] || 'U';
      loadUsersList();
      loadGroupsList();
      loadRolesList();
      loadSystemSettings();
    }

    window.addEventListener('DOMContentLoaded', async () => {
      if (authToken) {
        try {
          const res = await fetch('/api/v1/auth/me', {
            headers: { 'Authorization': `Bearer ${authToken}` }
          });
          if (res.ok) {
            currentUser = await res.json();
            initDashboard();
          } else {
            localStorage.removeItem('access_token');
            authToken = '';
          }
        } catch (e) {
          localStorage.removeItem('access_token');
          authToken = '';
        }
      }
    });

    function switchTab(tabName) {
      document.querySelectorAll('.tab-panel').forEach(el => el.classList.add('hidden'));
      document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active', 'bg-blue-50', 'dark:bg-slate-800', 'text-blue-600'));
      
      const target = document.getElementById(`tab-${tabName}`);
      if (target) target.classList.remove('hidden');
      
      const titles = {
        'dashboard': 'داشبورد مدیریتی',
        'chat': 'محیط گفت‌وگوی سازمانی',
        'ad': 'تنظیمات Active Directory',
        'users': 'مدیریت کاربران و دسترسی‌ها',
        'groups': 'مدیریت گروه‌های سازمانی',
        'roles': 'نقش‌ها و ماتریس دسترسی (RBAC)',
        'ai-providers': 'مدیریت ارائه‌دهندگان هوش مصنوعی',
        'ai-models': 'مدیریت مدل‌های زبانی (LLMs)',
        'knowledge': 'پایگاه دانش سازمانی و بازیابی معنایی (RAG)',
        'settings': 'تنظیمات سراسری سامانه'
      };
      if (titles[tabName]) document.getElementById('pageTitle').innerText = titles[tabName];
      if (tabName === 'users') loadUsersList();
      if (tabName === 'groups') loadGroupsList();
      if (tabName === 'roles') loadRolesList();
      if (tabName === 'ai-providers') loadProvidersList();
      if (tabName === 'ai-models') loadModelsList();
      if (tabName === 'knowledge') loadKnowledgeList();
      if (tabName === 'chat') ensureActiveConversation();
    }

    async function loadUsersList() {
      try {
        const search = document.getElementById('userSearchInput') ? document.getElementById('userSearchInput').value : '';
        const res = await fetch(`/api/v1/users${search ? '?search=' + encodeURIComponent(search) : ''}`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.getElementById('usersTableBody');
        tbody.innerHTML = data.users.map(u => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td class="p-3 font-semibold">${u.first_name} ${u.last_name}</td>
            <td class="p-3 font-mono">${u.username}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${u.auth_type === 'LOCAL' ? 'bg-slate-100 text-slate-700' : 'bg-purple-100 text-purple-700'}">${u.auth_type}</span></td>
            <td class="p-3">${u.role_title || 'کاربر'}</td>
            <td class="p-3">${u.group_name || 'عمومی'}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 font-mono">${u.effective_policy}</span></td>
            <td class="p-3 font-mono">${u.effective_daily_limit} سؤال</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${u.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}">${u.is_active ? 'فعال' : 'غیرفعال'}</span></td>
            <td class="p-3 text-center space-x-1 space-x-reverse whitespace-nowrap">
              <button onclick="openEditUserModal('${u.id}')" class="text-blue-600 hover:text-blue-800 text-xs px-2.5 py-1 rounded hover:bg-blue-50 font-semibold transition">✏️ ویرایش</button>
              ${u.username === 'admin' ? '<span class="text-slate-400 text-[10px]">ادمین اصلی</span>' : `<button onclick="deleteUser('${u.id}')" class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50 transition">حذف</button>`}
            </td>
          </tr>
        `).join('');
      } catch (err) {}
    }

    async function openEditUserModal(id) {
      try {
        const [userRes, rolesRes, groupsRes] = await Promise.all([
          fetch(`/api/v1/users/${id}`, { headers: { 'Authorization': `Bearer ${authToken}` } }),
          fetch('/api/v1/roles', { headers: { 'Authorization': `Bearer ${authToken}` } }),
          fetch('/api/v1/groups', { headers: { 'Authorization': `Bearer ${authToken}` } })
        ]);

        if (!userRes.ok) {
          showToast('خطا در دریافت اطلاعات کاربر', true);
          return;
        }

        const u = await userRes.json();
        const roles = await rolesRes.json();
        const groups = await groupsRes.json();

        document.getElementById('editUserId').value = u.id;
        document.getElementById('editUsername').value = u.username;
        document.getElementById('editFirstName').value = u.first_name || '';
        document.getElementById('editLastName').value = u.last_name || '';
        document.getElementById('editPassword').value = '';
        document.getElementById('editOverridePolicy').value = u.override_policy || '';
        document.getElementById('editCustomDailyLimit').value = (u.custom_daily_limit !== null && u.custom_daily_limit !== undefined) ? u.custom_daily_limit : '';
        document.getElementById('editIsActive').checked = !!u.is_active;

        // Populate Groups dropdown
        const groupSelect = document.getElementById('editGroupId');
        groupSelect.innerHTML = groups.map(g => `
          <option value="${g.id}" ${g.id === u.group_id ? 'selected' : ''}>${g.name} (${g.default_policy} - روزانه ${g.daily_question_limit} سؤال)</option>
        `).join('');

        // Populate Roles dropdown
        const roleSelect = document.getElementById('editRoleId');
        roleSelect.innerHTML = roles.map(r => `
          <option value="${r.id}" ${r.id === u.role_id ? 'selected' : ''}>${r.display_name_fa || r.name} (${r.name})</option>
        `).join('');

        document.getElementById('editUserModal').classList.remove('hidden');
      } catch (err) {
        showToast('خطا در بارگذاری مودال ویرایش کاربر', true);
      }
    }

    function closeEditUserModal() {
      document.getElementById('editUserModal').classList.add('hidden');
    }

    async function submitEditUser(e) {
      e.preventDefault();
      const id = document.getElementById('editUserId').value;
      const firstName = document.getElementById('editFirstName').value.trim();
      const lastName = document.getElementById('editLastName').value.trim();
      const groupId = document.getElementById('editGroupId').value;
      const roleId = document.getElementById('editRoleId').value;
      const password = document.getElementById('editPassword').value.trim();
      const overridePolicy = document.getElementById('editOverridePolicy').value;
      const customDailyRaw = document.getElementById('editCustomDailyLimit').value.trim();
      const isActive = document.getElementById('editIsActive').checked;

      const body = {
        first_name: firstName,
        last_name: lastName,
        group_id: groupId,
        role_id: roleId,
        override_policy: overridePolicy || null,
        custom_daily_limit: customDailyRaw !== '' ? parseInt(customDailyRaw, 10) : null,
        is_active: isActive
      };

      if (password) {
        body.password = password;
      }

      try {
        const res = await fetch(`/api/v1/users/${id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
          showToast('مشخصات کاربر با موفقیت به‌روزرسانی شد!');
          closeEditUserModal();
          loadUsersList();
        } else {
          showToast(data.message || 'خطا در ذخیره تغییرات کاربر', true);
        }
      } catch (err) {
        showToast('خطا در برقراری ارتباط با سرور', true);
      }
    }

    async function deleteUser(id) {
      if (!confirm('آیا از حذف این کاربر اطمینان دارید؟')) return;
      try {
        const res = await fetch(`/api/v1/users/${id}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const data = await res.json();
        if (res.ok) {
          showToast('کاربر با موفقیت حذف شد.');
          loadUsersList();
        } else {
          showToast(data.message || 'خطا در حذف کاربر', true);
        }
      } catch (e) {
        showToast('خطا در برقراری ارتباط با سرور', true);
      }
    }

    async function loadGroupsList() {
      try {
        const res = await fetch('/api/v1/groups', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) return;
        const groups = await res.json();
        const grid = document.getElementById('groupsGrid');
        grid.innerHTML = groups.map(g => `
          <div class="bg-white dark:bg-dark-card p-5 rounded-2xl border border-slate-200 dark:border-dark-border shadow-sm flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between mb-2">
                <h4 class="font-bold text-sm text-slate-800 dark:text-white">${g.name}</h4>
                <span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 font-mono">${g.member_count} عضو</span>
              </div>
              <p class="text-xs text-slate-400 mb-4">${g.description || 'بدون توضیحات'}</p>
              <div class="space-y-1.5 text-xs border-t border-slate-100 dark:border-slate-800 pt-3">
                <div class="flex justify-between"><span class="text-slate-400">سهمیه روزانه:</span><span class="font-bold font-mono">${g.daily_question_limit} سؤال</span></div>
                <div class="flex justify-between"><span class="text-slate-400">سقف توکن روزانه:</span><span class="font-mono text-indigo-600">${g.daily_token_limit.toLocaleString()}</span></div>
                <div class="flex justify-between"><span class="text-slate-400">سیاست پاسخگویی:</span><span class="font-mono text-emerald-600">${g.default_policy}</span></div>
                <div class="flex justify-between"><span class="text-slate-400">حداکثر حجم فایل:</span><span class="font-mono">${g.max_file_size_mb} MB</span></div>
              </div>
            </div>
            <div class="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center text-[10px]">
              <span class="text-slate-400">فرمت‌ها: ${(g.allowed_file_types || []).slice(0, 3).join(', ')}...</span>
              <div class="flex items-center gap-2">
                <button onclick="openEditGroupModal('${g.id}')" class="text-blue-600 hover:text-blue-800 font-semibold px-2 py-0.5 rounded hover:bg-blue-50">ویرایش</button>
                ${g.name === 'مدیران' ? '' : `<button onclick="deleteGroup('${g.id}')" class="text-red-500 hover:text-red-700 px-2 py-0.5 rounded hover:bg-red-50">حذف</button>`}
              </div>
            </div>
          </div>
        `).join('');
      } catch (err) {}
    }

    async function openEditGroupModal(id) {
      try {
        const res = await fetch(`/api/v1/groups/${id}`, { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) {
          showToast('خطا در دریافت اطلاعات گروه', true);
          return;
        }
        const g = await res.json();
        document.getElementById('editGroupIdVal').value = g.id;
        document.getElementById('editGroupName').value = g.name || '';
        document.getElementById('editGroupDesc').value = g.description || '';
        document.getElementById('editGroupPolicy').value = g.default_policy || 'HYBRID';
        document.getElementById('editGroupDailyQuestion').value = g.daily_question_limit;
        document.getElementById('editGroupMonthlyQuestion').value = g.monthly_question_limit;
        document.getElementById('editGroupDailyToken').value = g.daily_token_limit;
        document.getElementById('editGroupMonthlyToken').value = g.monthly_token_limit;
        document.getElementById('editGroupMaxFileSize').value = g.max_file_size_mb;
        document.getElementById('editGroupAllowModel').value = g.allow_model_selection ? 'true' : 'false';

        document.getElementById('editGroupModal').classList.remove('hidden');
      } catch (err) {
        showToast('خطا در بارگذاری اطلاعات گروه', true);
      }
    }

    function closeEditGroupModal() {
      document.getElementById('editGroupModal').classList.add('hidden');
    }

    async function submitEditGroup(e) {
      e.preventDefault();
      const id = document.getElementById('editGroupIdVal').value;
      const name = document.getElementById('editGroupName').value.trim();
      const desc = document.getElementById('editGroupDesc').value.trim();
      const policy = document.getElementById('editGroupPolicy').value;
      const dailyQ = parseInt(document.getElementById('editGroupDailyQuestion').value, 10);
      const monthlyQ = parseInt(document.getElementById('editGroupMonthlyQuestion').value, 10);
      const dailyT = parseInt(document.getElementById('editGroupDailyToken').value, 10);
      const monthlyT = parseInt(document.getElementById('editGroupMonthlyToken').value, 10);
      const maxFile = parseInt(document.getElementById('editGroupMaxFileSize').value, 10);
      const allowModel = document.getElementById('editGroupAllowModel').value === 'true';

      const body = {
        name,
        description: desc,
        default_policy: policy,
        daily_question_limit: dailyQ,
        monthly_question_limit: monthlyQ,
        daily_token_limit: dailyT,
        monthly_token_limit: monthlyT,
        max_file_size_mb: maxFile,
        allow_model_selection: allowModel
      };

      try {
        const res = await fetch(`/api/v1/groups/${id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
          showToast('تنظیمات گروه با موفقیت به‌روزرسانی شد!');
          closeEditGroupModal();
          loadGroupsList();
        } else {
          showToast(data.message || 'خطا در ویرایش گروه', true);
        }
      } catch (err) {
        showToast('خطا در برقراری ارتباط با سرور', true);
      }
    }

    async function deleteGroup(id) {
      if (!confirm('آیا از حذف این گروه اطمینان دارید؟')) return;
      const res = await fetch(`/api/v1/groups/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (res.ok) {
        showToast('گروه با موفقیت حذف گردید.');
        loadGroupsList();
      } else {
        showToast(data.message || 'خطا در حذف گروه', true);
      }
    }

    async function loadRolesList() {
      try {
        const res = await fetch('/api/v1/roles', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) return;
        const roles = await res.json();
        const tbody = document.getElementById('rolesTableBody');
        tbody.innerHTML = roles.map(r => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td class="p-3 font-semibold">${r.display_name_fa}</td>
            <td class="p-3 font-mono">${r.name}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${r.is_system ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'}">${r.is_system ? 'پایه سیستمی' : 'سفارشی'}</span></td>
            <td class="p-3 text-[11px] font-mono text-slate-500 max-w-xs truncate">${r.permissions.join(', ')}</td>
            <td class="p-3 text-center">
              ${r.is_system ? '<span class="text-slate-400 text-[10px]">غیرقابل حذف</span>' : `<button onclick="deleteRole('${r.id}')" class="text-red-500 hover:text-red-700 text-xs">حذف</button>`}
            </td>
          </tr>
        `).join('');
      } catch (err) {}
    }

    async function deleteRole(id) {
      if (!confirm('آیا از حذف این نقش اطمینان دارید؟')) return;
      const res = await fetch(`/api/v1/roles/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (res.ok) {
        showToast('نقش با موفقیت حذف شد.');
        loadRolesList();
      } else {
        showToast(data.message || 'خطا در حذف نقش', true);
      }
    }

    function openCreateUserModal() {
      const username = prompt('نام کاربری را وارد کنید (مثال: ali_rad):');
      if (!username) return;
      const firstName = prompt('نام (مثال: علی):', 'علی') || 'علی';
      const lastName = prompt('نام خانوادگی (مثال: راد):', 'راد') || 'راد';
      const password = prompt('رمز عبور کاربر:', 'Pass@123456') || 'Pass@123456';

      // Fetch roles and groups to map default
      fetch('/api/v1/roles', { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json()).then(roles => {
        fetch('/api/v1/groups', { headers: { 'Authorization': `Bearer ${authToken}` } }).then(g => g.json()).then(groups => {
          const roleId = roles.find(x => x.name === 'normal_subscriber')?.id || roles[0].id;
          const groupId = groups[0].id;

          const body = {
            username,
            first_name: firstName,
            last_name: lastName,
            password,
            auth_type: 'LOCAL',
            role_id: roleId,
            group_id: groupId,
            is_active: true
          };

          fetch('/api/v1/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify(body)
          }).then(res => res.json()).then(data => {
            if (data.id) {
              showToast('کاربر با موفقیت در پایگاه داده ایجاد شد!');
              loadUsersList();
            } else {
              showToast(data.message || 'خطا در ایجاد کاربر', true);
            }
          });
        });
      });
    }

    function openCreateGroupModal() {
      const name = prompt('نام گروه سازمانی را وارد کنید (مثال: تیم تحقیق و توسعه):');
      if (!name) return;
      const desc = prompt('توضیح کوتاه گروه:', 'تیم توسعه و تحقیقات سازمان') || '';
      const daily = parseInt(prompt('سهمیه روزانه سؤال:', '150') || '150', 10);

      const body = {
        name,
        description: desc,
        daily_question_limit: daily,
        monthly_question_limit: daily * 30,
        daily_token_limit: 300000,
        monthly_token_limit: 9000000,
        max_file_size_mb: 25,
        allowed_file_types: ["pdf", "docx", "txt", "xlsx"]
      };

      fetch('/api/v1/groups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(body)
      }).then(res => res.json()).then(data => {
        if (data.id) {
          showToast('گروه جدید با موفقیت ثبت شد!');
          loadGroupsList();
        } else {
          showToast(data.message || 'خطا در ایجاد گروه', true);
        }
      });
    }

    function openCreateRoleModal() {
      const name = prompt('شناسه انگلیسی نقش (مثال: security_auditor):');
      if (!name) return;
      const title = prompt('عنوان فارسی نقش (مثال: ممیز امنیت):', 'ممیز امنیت') || 'ممیز امنیت';

      const body = {
        name,
        display_name_fa: title,
        permissions: ["chat:access", "logs:read"]
      };

      fetch('/api/v1/roles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(body)
      }).then(res => res.json()).then(data => {
        if (data.id) {
          showToast('نقش سفارشی با موفقیت ایجاد گردید!');
          loadRolesList();
        } else {
          showToast(data.message || 'خطا در تعریف نقش', true);
        }
      });
    }

    async function loadSystemSettings() {
      try {
        const res = await fetch('/api/v1/settings');
        if (!res.ok) return;
        const data = await res.json();
        document.getElementById('sysAuthMode').value = data.auth_mode;
        document.getElementById('sysPolicy').value = data.default_response_policy;
        document.getElementById('sysMaxFileSize').value = data.max_file_size_mb;
      } catch (err) {}
    }

    async function handleSaveSystemSettings(e) {
      e.preventDefault();
      const body = {
        auth_mode: document.getElementById('sysAuthMode').value,
        default_response_policy: document.getElementById('sysPolicy').value,
        max_file_size_mb: parseInt(document.getElementById('sysMaxFileSize').value, 10),
        default_ai_language: 'fa',
        allow_file_upload_globally: true,
        session_timeout_minutes: 480
      };
      const res = await fetch('/api/v1/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(body)
      });
      if (res.ok) showToast('تنظیمات سراسری با موفقیت به‌روز شدند.');
      else showToast('خطا در ذخیره تنظیمات', true);
    }

    async function testADConnection() {
      const btn = document.getElementById('btnTestAD');
      btn.innerText = 'در حال تست...';
      const body = {
        server_host: document.getElementById('adHost').value,
        port: parseInt(document.getElementById('adPort').value, 10),
        domain_name: document.getElementById('adDomain').value
      };
      try {
        const res = await fetch('/api/v1/ad-settings/test', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify(body)
        });
        const data = await res.json();
        showToast(data.message, !data.success);
      } catch (e) {
        showToast('خطا در برقراری ارتباط با سرور', true);
      } finally {
        btn.innerText = 'تست زنده اتصال 🔌';
      }
    }

    async function handleSaveADSettings(e) {
      e.preventDefault();
      const body = {
        is_enabled: true,
        server_host: document.getElementById('adHost').value,
        domain_name: document.getElementById('adDomain').value,
        port: parseInt(document.getElementById('adPort').value, 10),
        port_ssl: 636,
        use_ssl: false,
        base_dn: document.getElementById('adBaseDN').value,
        bind_dn: document.getElementById('adBindDN').value,
        auto_provision: document.getElementById('adAutoProvision').checked,
        allowed_groups: ["Domain Admins", "IT-Staff"],
        group_role_mapping: {"Domain Admins": "super_admin"}
      };
      const res = await fetch('/api/v1/ad-settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(body)
      });
      if (res.ok) showToast('تنظیمات اکتیو دایرکتوری ذخیره شد.');
      else showToast('خطا در ذخیره تنظیمات AD', true);
    }

    // -------------------------------------------------------------------------
    // Phase 3: AI Providers & Models Functions
    // -------------------------------------------------------------------------
    async function loadProvidersList() {
      try {
        const res = await fetch('/api/v1/ai-providers', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.getElementById('providersTableBody');
        tbody.innerHTML = data.map(p => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td class="p-3 font-semibold">${p.name}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] bg-indigo-100 text-indigo-700 font-mono">${p.provider_type}</span></td>
            <td class="p-3 font-mono text-[11px] text-slate-500">${p.masked_api_key}</td>
            <td class="p-3 font-mono">${p.models_count} مدل</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${p.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}">${p.is_active ? 'فعال' : 'غیرفعال'}</span></td>
            <td class="p-3 text-center">
              <button onclick="testProvider('${p.id}')" class="px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-[11px] font-medium">⚡ تست اتصال</button>
            </td>
            <td class="p-3 text-center">
              <button onclick="deleteProvider('${p.id}')" class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50">حذف</button>
            </td>
          </tr>
        `).join('');
      } catch (err) {}
    }

    async function testProvider(id) {
      showToast('در حال تست ارتباط با سرور هوش مصنوعی...');
      try {
        const res = await fetch('/api/v1/ai-providers/test-connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify({ provider_id: id })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`ارتباط موفق بود! زمان پاسخ: ${data.latency_ms}ms`);
        } else {
          showToast(`خطا در ارتباط: ${data.message}`, true);
        }
      } catch (err) {
        showToast('خطا در تست اتصال', true);
      }
    }

    async function deleteProvider(id) {
      if (!confirm('آیا از حذف این ارائه‌دهنده اطمینان دارید؟')) return;
      const res = await fetch(`/api/v1/ai-providers/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (res.ok) {
        showToast('ارائه‌دهنده حذف شد.');
        loadProvidersList();
      } else {
        showToast(data.message || 'خطا در حذف', true);
      }
    }

    function openCreateProviderModal() {
      const name = prompt('نام نمایشی ارائه‌دهنده (مثال: OpenAI، Google Gemini، Anthropic، یا Ollama):');
      if (!name) return;
      const ptype = prompt('نوع سرویس (OPENAI, GEMINI, ANTHROPIC, OPENAI_COMPATIBLE, MOCK):', 'OPENAI') || 'OPENAI';
      let baseUrl = null;
      if (ptype.toUpperCase().includes('COMPATIBLE') || ptype.toUpperCase().includes('CUSTOM')) {
        baseUrl = prompt('آدرس اختصاصی Base URL (مثال: http://localhost:11434/v1 یا https://openrouter.ai/api/v1):', 'http://localhost:11434/v1');
      }
      const apiKey = prompt('کلید API ارائه‌دهنده (برای Ollama می‌توانید هر متنی بگذارید):', 'sk-proj-...') || '';

      const body = {
        name,
        provider_type: ptype.toUpperCase(),
        api_key: apiKey,
        base_url: baseUrl,
        is_active: true
      };

      fetch('/api/v1/ai-providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify(body)
      }).then(r => r.json()).then(data => {
        if (data.id) {
          showToast('ارائه‌دهنده با موفقیت ثبت شد!');
          loadProvidersList();
        } else {
          showToast(data.message || 'خطا در ثبت ارائه‌دهنده', true);
        }
      });
    }

    function openCreateModelModal() {
      fetch('/api/v1/ai-providers', { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json()).then(provs => {
        if (!provs.length) {
          showToast('ابتدا حداقل یک ارائه‌دهنده هوش مصنوعی ثبت نمایید.', true);
          return;
        }

        let provId = provs[0].id;
        if (provs.length > 1) {
          const provChoices = provs.map((p, idx) => `${idx + 1}. ${p.name} (${p.provider_type})`).join(String.fromCharCode(10));
          const choice = prompt(`ارائه‌دهنده مربوطه را انتخاب کنید (عدد ۱ تا ${provs.length}):\n${provChoices}`, '1');
          const idx = parseInt(choice || '1', 10) - 1;
          if (provs[idx]) provId = provs[idx].id;
        }

        const identifier = prompt('شناسه فنی مدل در API (مثال: gpt-4o, gemini-1.5-flash, claude-3-5-sonnet-20241022, llama3.2):', 'gpt-4o');
        if (!identifier) return;
        const displayName = prompt('نام نمایشی فارسی مدل:', 'مدل هوشمند ' + identifier) || identifier;
        const isDefault = confirm('آیا این مدل به عنوان مدل پیش‌فرض جدید سامانه تعیین شود؟');

        fetch('/api/v1/ai-models', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify({
            provider_id: provId,
            model_identifier: identifier,
            display_name_fa: displayName,
            is_active: true,
            is_default: isDefault,
            max_context_tokens: 32000
          })
        }).then(r => r.json()).then(data => {
          if (data.id) {
            showToast('مدل هوش مصنوعی با موفقیت ثبت شد!');
            loadModelsList();
          } else {
            showToast(data.message || 'خطا در ثبت مدل', true);
          }
        });
      });
    }

    async function deleteModel(id) {
      if (!confirm('آیا از حذف این مدل هوش مصنوعی اطمینان دارید؟')) return;
      const res = await fetch(`/api/v1/ai-models/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (res.ok) {
        showToast('مدل حذف شد.');
        loadModelsList();
      } else {
        showToast(data.message || 'خطا در حذف مدل', true);
      }
    }

    // -------------------------------------------------------------------------
    // Phase 4: Knowledge Base & RAG Functions
    // -------------------------------------------------------------------------
    async function loadKnowledgeList() {
      try {
        const res = await fetch('/api/v1/knowledge/documents', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) return;
        const data = await res.json();
        const tbody = document.getElementById('knowledgeTableBody');
        tbody.innerHTML = data.map(d => `
          <tr class="hover:bg-slate-50 dark:hover:bg-slate-800/40">
            <td class="p-3 font-semibold">${d.title}</td>
            <td class="p-3">${d.category_name}</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700 font-mono">${d.document_type}</span></td>
            <td class="p-3 font-mono">v${d.version}</td>
            <td class="p-3 font-mono text-indigo-600 font-semibold">${d.chunks_count} چانک برداری</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded text-[10px] ${d.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">${d.status === 'APPROVED' ? 'تاییدشده' : d.status}</span></td>
            <td class="p-3 text-center">
              <button onclick="deleteKnowledgeDoc('${d.id}')" class="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded hover:bg-red-50">حذف</button>
            </td>
          </tr>
        `).join('');
      } catch (err) {}
    }

    async function testRAGSearch() {
      const q = document.getElementById('ragTestInput').value.trim();
      if (!q) return;
      const box = document.getElementById('ragSearchResults');
      box.classList.remove('hidden');
      box.innerHTML = '<span class="text-slate-500">در حال جستجوی معنایی و ارزیابی تشابه کسینوسی بردارها...</span>';

      try {
        const res = await fetch('/api/v1/knowledge/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify({ query: q, top_k: 3, min_similarity: 0.1 })
        });
        const data = await res.json();
        if (!data.results || !data.results.length) {
          box.innerHTML = '<span class="text-amber-600">هیچ چانکی با آستانه تشابه معنایی در پایگاه دانش یافت نشد.</span>';
          return;
        }
        box.innerHTML = `
          <div class="font-bold text-indigo-900 dark:text-indigo-200 mb-1">نتایج بازیابی معنایی (${data.results.length} چانک استخراج شد):</div>
          ${data.results.map(r => `
            <div class="p-2.5 rounded-xl bg-white dark:bg-dark-card border border-indigo-100 dark:border-indigo-900/50">
              <div class="flex justify-between font-semibold text-slate-800 dark:text-slate-200">
                <span>📌 ${r.document_title} (${r.category_name})</span>
                <span class="text-emerald-600 font-mono text-[11px]">ضریب شباهت: ${(r.similarity_score * 100).toFixed(1)}%</span>
              </div>
              <p class="text-slate-600 dark:text-slate-400 mt-1 leading-relaxed text-[11px]">${r.content}</p>
            </div>
          `).join('')}
        `;
      } catch (err) {
        box.innerHTML = '<span class="text-red-500">خطا در جستجوی معنایی</span>';
      }
    }

    function openCreateDocModal() {
      fetch('/api/v1/knowledge/categories', { headers: { 'Authorization': `Bearer ${authToken}` } }).then(r => r.json()).then(cats => {
        let catId = cats[0]?.id;
        const title = prompt('عنوان سند یا پرسش متداول:', 'آیین‌نامه ساعت کاری و حضور و غیاب');
        if (!title) return;
        const content = prompt('متن سند را وارد کنید (به طور خودکار چانک و بردارسازی می‌شود):', 'ساعت کاری رسمی از شنبه تا چهارشنبه از ساعت ۸:۰۰ الی ۱۶:۳۰ می‌باشد. تاخیر بیش از ۱۵ دقیقه در سامانه کسر کار ثبت می‌شود.');
        if (!content) return;

        const body = {
          category_id: catId,
          title,
          document_type: 'POLICY',
          content_text: content,
          status: 'APPROVED'
        };

        fetch('/api/v1/knowledge/documents', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify(body)
        }).then(r => r.json()).then(data => {
          if (data.id) {
            showToast('سند با موفقیت ثبت، چانک و ایندکس برداری شد!');
            loadKnowledgeList();
          } else {
            showToast(data.message || 'خطا در ثبت سند', true);
          }
        });
      });
    }

    async function deleteKnowledgeDoc(id) {
      if (!confirm('آیا از حذف این سند و بردارهای آن اطمینان دارید؟')) return;
      const res = await fetch(`/api/v1/knowledge/documents/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (res.ok) {
        showToast('سند حذف شد.');
        loadKnowledgeList();
      } else {
        showToast('خطا در حذف سند', true);
      }
    }

    // -------------------------------------------------------------------------
    // Phase 5: Enterprise Chat Functions
    // -------------------------------------------------------------------------
    let activeConversationId = null;

    async function ensureActiveConversation() {
      if (activeConversationId) return;
      try {
        const res = await fetch('/api/v1/chat/conversations', { headers: { 'Authorization': `Bearer ${authToken}` } });
        if (!res.ok) return;
        const convs = await res.json();
        if (convs.length > 0) {
          activeConversationId = convs[0].id;
        } else {
          const createRes = await fetch('/api/v1/chat/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify({ title: 'گفتگوی سازمانی' })
          });
          const newConv = await createRes.json();
          activeConversationId = newConv.id;
        }
      } catch (err) {}
    }

    async function handleSendMessage(e) {
      e.preventDefault();
      const input = document.getElementById('chatInput');
      const text = input.value.trim();
      if (!text) return;
      input.value = '';

      const container = document.getElementById('chatMessages');
      // User message bubble
      container.innerHTML += `
        <div class="flex items-start gap-3 justify-end max-w-3xl ml-auto">
          <div class="bg-blue-600 text-white p-3.5 rounded-2xl rounded-tl-none text-xs leading-relaxed shadow-sm">
            ${text}
          </div>
          <div class="w-8 h-8 rounded-xl bg-slate-300 dark:bg-slate-700 text-slate-800 dark:text-white flex items-center justify-center font-bold text-xs flex-shrink-0">من</div>
        </div>
      `;
      container.scrollTop = container.scrollHeight;

      await ensureActiveConversation();
      if (!activeConversationId) {
        showToast('خطا در بارگذاری شناسه گفتگو', true);
        return;
      }

      // Indicator bubble
      const loadingId = 'ai-loading-' + Date.now();
      container.innerHTML += `
        <div id="${loadingId}" class="flex items-start gap-3 max-w-3xl">
          <div class="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0 animate-pulse">AI</div>
          <div class="bg-white dark:bg-dark-card p-4 rounded-2xl rounded-tr-none border border-slate-200 dark:border-dark-border text-xs text-slate-400">
            در حال پردازش در بستر هوش مصنوعی و جستجوی پایگاه دانش...
          </div>
        </div>
      `;
      container.scrollTop = container.scrollHeight;

      try {
        const res = await fetch(`/api/v1/chat/conversations/${activeConversationId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
          body: JSON.stringify({ content: text })
        });
        const data = await res.json();
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();

        if (!res.ok) {
          container.innerHTML += `
            <div class="flex items-start gap-3 max-w-3xl">
              <div class="w-8 h-8 rounded-xl bg-red-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">!</div>
              <div class="bg-red-50 text-red-700 p-4 rounded-2xl border border-red-200 text-xs">
                ${data.message || 'خطا در دریافت پاسخ از هوش مصنوعی'}
              </div>
            </div>
          `;
          return;
        }

        const msg = data.message;
        let citationsHtml = '';
        if (msg.citations && msg.citations.length) {
          citationsHtml = `
            <div class="mt-2.5 pt-2.5 border-t border-slate-100 dark:border-slate-800 space-y-1">
              <div class="text-[10px] text-emerald-600 font-bold flex items-center gap-1">✓ منابع معتبر پایگاه دانش سازمانی (RAG):</div>
              ${msg.citations.map(c => `
                <div class="text-[10px] bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-300 px-2 py-1 rounded border border-emerald-200/50">
                  📌 ${c.document_title} - ضریب اطمینان: ${(c.similarity_score * 100).toFixed(0)}%
                </div>
              `).join('')}
            </div>
          `;
        }

        container.innerHTML += `
          <div class="flex items-start gap-3 max-w-3xl">
            <div class="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-xs flex-shrink-0">AI</div>
            <div class="bg-white dark:bg-dark-card p-4 rounded-2xl rounded-tr-none border border-slate-200 dark:border-dark-border text-xs leading-relaxed shadow-sm">
              <div class="text-[10px] text-slate-400 mb-1 flex justify-between">
                <span>سیاست: <b class="text-indigo-600">${msg.response_policy_used || 'HYBRID'}</b></span>
                <span>زمان: ${msg.processing_time_sec}s | توکن: ${msg.input_tokens + msg.output_tokens}</span>
              </div>
              <div class="text-slate-800 dark:text-slate-100 whitespace-pre-wrap">${msg.content}</div>
              ${citationsHtml}
            </div>
          </div>
        `;
        document.getElementById('chatQuotaBadge').innerText = `${data.daily_quota_remaining} سؤال`;
        container.scrollTop = container.scrollHeight;
      } catch (err) {
        const loadingEl = document.getElementById(loadingId);
        if (loadingEl) loadingEl.remove();
        showToast('عدم برقراری ارتباط با چت', true);
      }
    }

    function handleLogout() {
      localStorage.removeItem('access_token');
      location.reload();
    }
  </script>
</body>
</html>
"""

def run(port: int = 8080):
    seed_database()
    server_address = ('0.0.0.0', port)
    httpd = ThreadedHTTPServer(server_address, EnterpriseAIHandler)
    print(f"================================================================================")
    print(f"🚀 سامانه هوش مصنوعی سازمانی با موفقیت راه‌اندازی شد!")
    print(f"🌐 آدرس وب‌اپلیکیشن: http://localhost:{port}")
    print(f"📡 آدرس API: http://localhost:{port}/api/v1")
    print(f"🔑 کاربر مدیر پیش‌فرض: admin")
    print(f"🔒 رمز عبور مدیر: Enterprise@Admin123!")
    print(f"================================================================================")
    httpd.serve_forever()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)

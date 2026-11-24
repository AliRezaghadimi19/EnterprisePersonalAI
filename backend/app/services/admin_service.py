"""
Admin Service — dashboard statistics, audit log reading, usage reports,
CSV export and backup. Shared by the FastAPI app (app/api/v1/admin.py)
and the standalone server (run_server.py).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import get_db_connection
from app.core.exceptions import PersianAppException

ADMIN_ROLES = ("super_admin", "system_admin")


def _row_to_dict(cursor, row) -> Dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ---------------------------------------------------------------------------
# Dashboard statistics
# ---------------------------------------------------------------------------
def get_dashboard_stats(days: int = 30) -> Dict[str, Any]:
    if not isinstance(days, int) or days < 1 or days > 365:
        days = 30

    conn = get_db_connection()
    cursor = conn.cursor()

    stats: Dict[str, Any] = {}

    # Totals -----------------------------------------------------------------
    def scalar(sql: str, params: tuple = ()) -> int:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    stats["totals"] = {
        "users": scalar("SELECT COUNT(*) FROM users"),
        "active_users": scalar("SELECT COUNT(*) FROM users WHERE is_active = 1"),
        "groups": scalar("SELECT COUNT(*) FROM groups"),
        "conversations": scalar("SELECT COUNT(*) FROM conversations"),
        "messages": scalar("SELECT COUNT(*) FROM messages"),
        "documents": scalar("SELECT COUNT(*) FROM knowledge_documents"),
        "providers": scalar("SELECT COUNT(*) FROM ai_providers"),
        "models": scalar("SELECT COUNT(*) FROM ai_models"),
    }

    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Messages per day ---------------------------------------------------------
    cursor.execute(
        """
        SELECT substr(created_at, 1, 10) AS day,
               COUNT(*) AS cnt,
               COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) AS tokens
        FROM messages
        WHERE created_at >= ?
        GROUP BY day ORDER BY day ASC
        """,
        (cutoff,),
    )
    stats["messages_per_day"] = [
        {"date": r[0], "count": int(r[1]), "tokens": int(r[2])} for r in cursor.fetchall()
    ]

    # Messages per model ------------------------------------------------------
    cursor.execute(
        """
        SELECT m.model_id,
               COALESCE(am.display_name_fa, m.model_id, 'نامشخص') AS model_name,
               COUNT(*) AS cnt,
               COALESCE(SUM(COALESCE(m.input_tokens, 0) + COALESCE(m.output_tokens, 0)), 0) AS tokens
        FROM messages m
        LEFT JOIN ai_models am ON am.id = m.model_id
        GROUP BY m.model_id ORDER BY cnt DESC LIMIT 10
        """
    )
    stats["messages_per_model"] = [
        {"model_id": r[0], "model_name": r[1], "count": int(r[2]), "tokens": int(r[3])}
        for r in cursor.fetchall()
    ]

    # Users per group ----------------------------------------------------------
    cursor.execute(
        """
        SELECT g.id, COALESCE(g.name, 'بدون گروه') AS group_name, COUNT(u.id) AS cnt
        FROM users u
        LEFT JOIN groups g ON g.id = u.group_id
        GROUP BY g.id ORDER BY cnt DESC
        """
    )
    stats["users_per_group"] = [
        {"group_id": r[0], "group_name": r[1], "count": int(r[2])} for r in cursor.fetchall()
    ]

    # Policy distribution -------------------------------------------------------
    cursor.execute(
        """
        SELECT COALESCE(u.override_policy, COALESCE(g.default_policy, 'HYBRID')) AS policy,
               COUNT(u.id) AS cnt
        FROM users u
        LEFT JOIN groups g ON g.id = u.group_id
        GROUP BY policy
        """
    )
    stats["policy_distribution"] = [{"policy": r[0] or "HYBRID", "count": int(r[1])} for r in cursor.fetchall()]

    # Top users ------------------------------------------------------------------
    cursor.execute(
        """
        SELECT u.id, u.username, u.first_name || ' ' || u.last_name AS full_name,
               COUNT(m.id) AS msg_count
        FROM users u
        LEFT JOIN conversations c ON c.user_id = u.id
        LEFT JOIN messages m ON m.conversation_id = c.id
        GROUP BY u.id ORDER BY msg_count DESC LIMIT 5
        """
    )
    stats["top_users"] = [
        {"user_id": r[0], "username": r[1], "full_name": r[2] or r[1], "message_count": int(r[3])}
        for r in cursor.fetchall()
    ]

    # Auth types -------------------------------------------------------------
    cursor.execute("SELECT auth_type, COUNT(*) FROM users GROUP BY auth_type")
    auth_counts = {r[0]: int(r[1]) for r in cursor.fetchall()}
    stats["auth_types"] = {
        "LOCAL": auth_counts.get("LOCAL", 0),
        "ACTIVE_DIRECTORY": auth_counts.get("ACTIVE_DIRECTORY", 0),
    }

    # Token usage ------------------------------------------------------------
    today = datetime.utcnow().strftime("%Y-%m-%d")
    month_prefix = datetime.utcnow().strftime("%Y-%m")
    cursor.execute(
        "SELECT COALESCE(SUM(question_count), 0), COALESCE(SUM(total_tokens), 0), "
        "COALESCE(SUM(estimated_cost), 0) FROM usage_metrics WHERE usage_date = ?",
        (today,),
    )
    row = cursor.fetchone()
    today_q, today_tokens, _ = int(row[0]), int(row[1]), float(row[2])
    cursor.execute(
        "SELECT COALESCE(SUM(question_count), 0), COALESCE(SUM(total_tokens), 0), "
        "COALESCE(SUM(estimated_cost), 0) FROM usage_metrics WHERE usage_date LIKE ?",
        (f"{month_prefix}%",),
    )
    row = cursor.fetchone()
    month_q, month_tokens, month_cost = int(row[0]), int(row[1]), float(row[2])
    stats["token_usage"] = {
        "today": today_tokens,
        "month": month_tokens,
        "estimated_cost": round(month_cost, 4),
        "questions_today": today_q,
        "questions_month": month_q,
    }

    conn.close()
    return stats


# ---------------------------------------------------------------------------
# Usage report
# ---------------------------------------------------------------------------
def get_usage_report(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    group_by: str = "day",
) -> Dict[str, Any]:
    if group_by not in ("day", "user", "model"):
        group_by = "day"

    conn = get_db_connection()
    cursor = conn.cursor()

    if not to_date:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
    if not from_date:
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    params: List[Any] = [from_date, to_date]

    if group_by == "day":
        bucket_sql = "usage_date"
        label_sql = "usage_date"
    elif group_by == "user":
        bucket_sql = "um.user_id"
        label_sql = "COALESCE(u.username, um.user_id)"
    else:  # model
        bucket_sql = "COALESCE(um.model_id, '—')"
        label_sql = "COALESCE(am.display_name_fa, um.model_id, 'نامشخص')"

    sql = f"""
        SELECT {bucket_sql} AS bucket,
               {label_sql} AS label,
               COALESCE(SUM(um.question_count), 0) AS question_count,
               COALESCE(SUM(um.total_tokens), 0) AS total_tokens,
               COALESCE(SUM(um.estimated_cost), 0) AS estimated_cost
        FROM usage_metrics um
        LEFT JOIN users u ON u.id = um.user_id
        LEFT JOIN ai_models am ON am.id = um.model_id
        WHERE um.usage_date >= ? AND um.usage_date <= ?
        GROUP BY bucket ORDER BY question_count DESC
    """
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()

    # Fallback: if usage_metrics is empty, aggregate from messages table
    if not rows:
        if group_by == "day":
            bucket_sql = "substr(m.created_at, 1, 10)"
            label_sql = "substr(m.created_at, 1, 10)"
        elif group_by == "user":
            bucket_sql = "c.user_id"
            label_sql = "COALESCE(u.username, c.user_id)"
        else:
            bucket_sql = "COALESCE(m.model_id, '—')"
            label_sql = "COALESCE(am.display_name_fa, m.model_id, 'نامشخص')"

        cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        sql = f"""
            SELECT {bucket_sql} AS bucket,
                   {label_sql} AS label,
                   COUNT(*) AS question_count,
                   COALESCE(SUM(COALESCE(m.input_tokens, 0) + COALESCE(m.output_tokens, 0)), 0) AS total_tokens,
                   0.0 AS estimated_cost
            FROM messages m
            LEFT JOIN conversations c ON c.id = m.conversation_id
            LEFT JOIN users u ON u.id = c.user_id
            LEFT JOIN ai_models am ON am.id = m.model_id
            WHERE m.created_at >= ?
            GROUP BY bucket ORDER BY question_count DESC
        """
        cursor.execute(sql, (cutoff,))
        rows = cursor.fetchall()

    conn.close()

    report_rows = [
        {
            "bucket": r[0],
            "label": r[1],
            "question_count": int(r[2]),
            "total_tokens": int(r[3]),
            "estimated_cost": float(r[4]),
        }
        for r in rows
    ]

    summary = {
        "total_questions": sum(r["question_count"] for r in report_rows),
        "total_tokens": sum(r["total_tokens"] for r in report_rows),
        "total_cost": round(sum(r["estimated_cost"] for r in report_rows), 4),
        "active_users": len({r["bucket"] for r in report_rows}) if group_by != "day" else len(
            {r["bucket"] for r in report_rows}
        ),
    }

    return {"rows": report_rows, "summary": summary, "group_by": group_by}


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
def build_csv(entity: str) -> Tuple[List[str], List[List[Any]]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    if entity == "users":
        cursor.execute(
            """
            SELECT u.id, u.username, u.first_name, u.last_name, u.email, u.auth_type,
                   u.department, COALESCE(r.display_name_fa, '') AS role_name,
                   COALESCE(g.name, '') AS group_name,
                   CASE u.is_active WHEN 1 THEN 'فعال' ELSE 'غیرفعال' END AS status,
                   u.created_at
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            LEFT JOIN groups g ON g.id = u.group_id
            ORDER BY u.created_at
            """
        )
        headers = ["شناسه", "نام کاربری", "نام", "نام خانوادگی", "ایمیل", "نوع احراز",
                   "واحد سازمانی", "نقش", "گروه", "وضعیت", "تاریخ ایجاد"]
    elif entity == "groups":
        cursor.execute(
            """
            SELECT id, name, description, default_policy,
                   daily_question_limit, monthly_question_limit,
                   daily_token_limit, monthly_token_limit, max_file_size_mb, created_at
            FROM groups ORDER BY created_at
            """
        )
        headers = ["شناسه", "نام گروه", "توضیحات", "سیاست پیش‌فرض",
                   "سقف روزانه", "سقف ماهانه", "سقف توکن روزانه", "سقف توکن ماهانه",
                   "حداکثر حجم فایل (MB)", "تاریخ ایجاد"]
    elif entity == "conversations":
        cursor.execute(
            """
            SELECT c.id, c.title, COALESCE(u.username, '') AS username, c.model_id,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS messages_count,
                   c.created_at, c.updated_at
            FROM conversations c
            LEFT JOIN users u ON u.id = c.user_id
            ORDER BY c.created_at DESC
            """
        )
        headers = ["شناسه", "عنوان", "کاربر", "مدل", "تعداد پیام", "تاریخ ایجاد", "آخرین بروزرسانی"]
    elif entity == "audit_logs":
        cursor.execute(
            """
            SELECT id, actor_username, action_type, target_resource, target_id,
                   old_values, new_values, ip_address, created_at
            FROM audit_logs ORDER BY created_at DESC
            """
        )
        headers = ["شناسه", "کاربر", "نوع رخداد", "منبع", "شناسه منبع",
                   "مقادیر قبلی", "مقادیر جدید", "IP", "تاریخ"]
    elif entity == "usage":
        cursor.execute(
            """
            SELECT um.usage_date, COALESCE(u.username, '') AS username,
                   COALESCE(am.display_name_fa, '') AS model_name,
                   um.question_count, um.total_tokens, um.estimated_cost
            FROM usage_metrics um
            LEFT JOIN users u ON u.id = um.user_id
            LEFT JOIN ai_models am ON am.id = um.model_id
            ORDER BY um.usage_date DESC
            """
        )
        headers = ["تاریخ", "کاربر", "مدل", "تعداد سؤال", "توکن", "هزینه تخمینی"]
    else:
        conn.close()
        raise PersianAppException(400, "نوع خروجی نامعتبر است.")

    data = [list(row) for row in cursor.fetchall()]
    conn.close()
    return headers, data


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def export_backup() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    table_names = [r[0] for r in cursor.fetchall()]

    backup: Dict[str, Any] = {
        "meta": {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "table_count": len(table_names),
            "table_rows": {},
        },
        "tables": {},
    }

    for table in table_names:
        cursor.execute(f"SELECT * FROM {table}")  # noqa: S608 — table names from schema
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        backup["tables"][table] = rows
        backup["meta"]["table_rows"][table] = len(rows)

    conn.close()
    return backup

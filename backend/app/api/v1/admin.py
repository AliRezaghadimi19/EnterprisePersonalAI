"""
Admin API — statistics, audit logs, conversations, usage reports, export, backup.
Parity endpoints for run_server.py (standalone) — same JSON shapes.
"""

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import require_admin, require_super_admin
from app.services import admin_service
from app.services.audit_service import audit_service
from app.services.chat_service import chat_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", summary="آمار داشبورد مدیریتی")
def get_stats(days: int = Query(30, ge=1, le=365), current_user: dict = Depends(require_admin)):
    return admin_service.get_dashboard_stats(days=days)


@router.get("/audit-logs", summary="فهرست لاگ‌های ممیزی")
def list_audit_logs(
    search: str = "",
    action_type: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    return audit_service.list_logs(search=search, action_type=action_type, page=page, page_size=page_size)


@router.get("/conversations", summary="فهرست همه مکالمات کاربران")
def list_conversations(
    search: str = "",
    user_id: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: dict = Depends(require_admin),
):
    return chat_service.list_all_conversations(search=search, user_id=user_id, page=page, page_size=page_size)


@router.get("/conversations/{conversation_id}", summary="جزئیات مکالمه (بدون محدودیت مالکیت)")
def get_conversation(conversation_id: str, current_user: dict = Depends(require_admin)):
    try:
        return chat_service.admin_get_conversation_detail(conversation_id)
    except Exception:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("مکالمه یافت نشد.")


@router.get("/usage-report", summary="گزارش مصرف")
def usage_report(
    from_date: str = "",
    to_date: str = "",
    group_by: str = Query("day", pattern="^(day|user|model)$"),
    current_user: dict = Depends(require_admin),
):
    return admin_service.get_usage_report(
        from_date=from_date or None, to_date=to_date or None, group_by=group_by
    )


@router.get("/export", summary="خروجی CSV")
def export_csv(entity: str = "users", current_user: dict = Depends(require_admin)):
    headers, rows = admin_service.build_csv(entity)

    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    content = '\ufeff' + buf.getvalue()  # UTF-8 BOM for Excel

    from datetime import datetime
    filename = f"{entity}-{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/backup", summary="پشتیبان‌گیری کامل JSON")
def backup(current_user: dict = Depends(require_super_admin)):
    from datetime import datetime
    data = admin_service.export_backup()
    filename = f"enterprise-ai-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    return Response(
        content=__import__("json").dumps(data, ensure_ascii=False, default=str).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
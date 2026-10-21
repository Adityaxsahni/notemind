"""Admin-only views: analytics and the audit log. Admin rights are granted from the command
line (python -m app.admin grant <email>), never through the API, and every request here is
itself written to the audit log."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select

from app import audit
from app.deps import CurrentUser, SessionDep
from app.models import AnalyticsEvent, AuditLog, User

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


@router.get("/analytics")
def analytics(
    admin: AdminUser,
    session: SessionDep,
    request: Request,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    recent = AnalyticsEvent.created_at >= since

    def grouped(column, limit: int = 20) -> list[dict[str, Any]]:
        rows = session.execute(
            select(column, func.count())
            .where(recent)
            .group_by(column)
            .order_by(func.count().desc())
            .limit(limit)
        ).all()
        return [{"key": key, "views": views} for key, views in rows]

    day = func.date_trunc("day", AnalyticsEvent.created_at)
    per_day = session.execute(
        select(day, func.count()).where(recent).group_by(day).order_by(day)
    ).all()
    audit.record(
        session, "admin.view_analytics", actor_id=admin.id, request=request, details={"days": days}
    )
    session.commit()
    return {
        "days": days,
        "total_views": session.scalar(select(func.count()).where(recent)) or 0,
        "per_day": [{"day": d.date().isoformat(), "views": n} for d, n in per_day],
        "top_pages": grouped(AnalyticsEvent.path),
        "referrers": grouped(AnalyticsEvent.referrer_host, limit=10),
        "devices": grouped(AnalyticsEvent.device, limit=5),
    }


@router.get("/audit-log")
def audit_log(
    admin: AdminUser,
    session: SessionDep,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, Any]]:
    rows = session.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()
    audit.record(session, "admin.view_audit_log", actor_id=admin.id, request=request)
    session.commit()
    return [
        {
            "id": entry.id,
            "at": entry.created_at,
            "actor": email or (str(entry.actor_id) if entry.actor_id else "command line"),
            "action": entry.action,
            "target": f"{entry.target_type}:{entry.target_id}" if entry.target_type else None,
            "details": entry.details,
        }
        for entry, email in rows
    ]

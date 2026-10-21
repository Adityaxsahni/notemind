"""Operator commands. They connect as the database owner (no row-level security), so they
can do what the app's role never can: grant admin, and prune old audit/analytics rows.

    python -m app.admin grant alice@example.com
    python -m app.admin revoke alice@example.com
    python -m app.admin prune --days 365      # run periodically, e.g. a daily cron job

Every command is recorded in the audit log.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app import audit
from app.config import get_settings
from app.models import AnalyticsEvent, AuditLog, User


def _set_admin(session: Session, email: str, value: bool) -> int:
    user = session.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        print(f"no user with email {email}", file=sys.stderr)
        return 1
    user.is_admin = value
    audit.record(
        session,
        "admin.grant" if value else "admin.revoke",
        actor_id=None,
        target_type="user",
        target_id=user.id,
        details={"via": "cli"},
    )
    session.commit()
    print(f"{email}: admin={value}")
    return 0


def _prune(session: Session, days: int) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    views = session.execute(delete(AnalyticsEvent).where(AnalyticsEvent.created_at < cutoff))
    entries = session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
    audit.record(
        session,
        "admin.prune",
        actor_id=None,
        details={"days": days, "analytics": views.rowcount, "audit": entries.rowcount},
    )
    session.commit()
    print(f"deleted {views.rowcount} page views and {entries.rowcount} audit entries")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("grant", "revoke"):
        sub.add_parser(name).add_argument("email")
    sub.add_parser("prune").add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    with Session(create_engine(get_settings().database_url)) as session:
        if args.command == "prune":
            return _prune(session, args.days)
        return _set_admin(session, args.email, args.command == "grant")


if __name__ == "__main__":
    sys.exit(main())

"""Audit trail for admin and security-relevant actions (account and collection deletion,
sharing changes, every admin action). Rows are append-only for the app's database role.

Callers commit; the entry is saved with the action it describes or not at all.
"""

import hashlib
import hmac
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditLog
from app.rate_limit import client_ip


def ip_hash(request: Request | None) -> str | None:
    """Keyed hash: lets us see that two events came from one address without storing it."""
    if request is None:
        return None
    key = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(key, client_ip(request).encode(), hashlib.sha256).hexdigest()[:32]


def record(
    session: Session,
    action: str,
    *,
    actor_id: uuid.UUID | None,
    request: Request | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    # A plain INSERT, not session.add: the ORM would add RETURNING, and only admins may read
    # audit rows back (row-level security).
    session.connection().execute(  # Core: no ORM RETURNING
        insert(AuditLog.__table__).values(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details or {},
            ip_hash=ip_hash(request),
        )
    )

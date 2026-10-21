"""Row-level security in the database itself: queries with no tenant filter at all must still
return only the caller's rows. These bypass the API on purpose, as a buggy query would."""

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.db import set_rls_user
from app.models import AuditLog, Chunk, Collection, CollectionMember, Document, DocumentPage, Role
from tests.conftest import signup
from tests.files import make_pdf


@pytest.fixture
def world(make_client):
    """Alice owns a collection with an indexed document and shares it with Bob; Eve is a
    stranger with her own collection."""
    alice, bob, eve = make_client(), make_client(), make_client()
    ids = {
        name: signup(c, f"{name}@x.com")["id"]
        for name, c in [("alice", alice), ("bob", bob), ("eve", eve)]
    }
    cid = alice.post("/collections", json={"name": "DBMS"}).json()["id"]
    alice.post(
        f"/collections/{cid}/documents",
        params={"filename": "n.pdf"},
        content=make_pdf(["3.1 Normalization\nThird normal form removes transitive dependencies."]),
    )
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    bob.post("/invites/accept", json={"token": token})
    eve_cid = eve.post("/collections", json={"name": "Eve's"}).json()["id"]
    return {**ids, "cid": cid, "eve_cid": eve_cid}


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_no_user_sees_nothing(app_db, world):
    with app_db() as s:
        for model in (Collection, CollectionMember, Document, DocumentPage, Chunk):
            assert count(s, model) == 0, model.__name__


def test_owner_sees_only_their_rows_without_any_filter(app_db, world):
    with app_db() as s:
        set_rls_user(s, world["alice"])
        assert [c.id.hex for c in s.scalars(select(Collection))] == [world["cid"].replace("-", "")]
        assert count(s, Document) == 1
        assert count(s, DocumentPage) == 1
        assert count(s, Chunk) >= 1


def test_stranger_sees_none_of_alices_rows(app_db, world):
    with app_db() as s:
        set_rls_user(s, world["eve"])
        assert [str(c.id) for c in s.scalars(select(Collection))] == [world["eve_cid"]]
        assert count(s, Document) == 0
        assert count(s, Chunk) == 0
        assert count(s, CollectionMember) == 0


def test_viewer_reads_shared_rows_but_cannot_write_them(app_db, world):
    with app_db() as s:
        set_rls_user(s, world["bob"])
        assert count(s, Document) == 1
        assert count(s, Chunk) >= 1
        # UPDATE/DELETE silently match nothing for rows outside the write policy.
        assert s.execute(update(Document).values(filename="hacked.pdf")).rowcount == 0
        assert s.execute(delete(Chunk)).rowcount == 0
        assert s.execute(update(Collection).values(name="mine now")).rowcount == 0
        s.rollback()


def test_stranger_cannot_insert_into_someone_elses_collection(app_db, world):
    with app_db() as s:
        set_rls_user(s, world["eve"])
        s.add(CollectionMember(collection_id=world["cid"], user_id=world["eve"], role=Role.VIEWER))
        # Alice's collection has an open invite, so self-joining is allowed by the policy only
        # because the invite exists; revoke it and the same insert is refused.
        s.flush()
        s.rollback()
    with app_db() as s:
        set_rls_user(s, world["alice"])
        s.execute(text("UPDATE invite_links SET revoked_at = now()"))
        s.commit()
    with app_db() as s:
        set_rls_user(s, world["eve"])
        s.add(CollectionMember(collection_id=world["cid"], user_id=world["eve"], role=Role.VIEWER))
        with pytest.raises(DBAPIError, match="row-level security"):
            s.flush()


def test_user_id_setting_does_not_leak_to_the_next_transaction(app_db, world):
    with app_db() as s:
        s.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": world["alice"]})
        assert count(s, Document) == 1
        s.commit()  # transaction-scoped: gone after commit
        assert count(s, Document) == 0


def test_app_role_cannot_change_schema_or_rewrite_audit_history(app_db, db, world):
    with db() as owner:
        owner.add(AuditLog(actor_id=None, action="test.event"))
        owner.commit()
    with app_db() as s:
        set_rls_user(s, world["alice"])
        for sql in ("DROP TABLE chunks", "TRUNCATE documents", "DELETE FROM audit_log"):
            with pytest.raises(DBAPIError):
                s.execute(text(sql))
            s.rollback()
            set_rls_user(s, world["alice"])
        # Non-admins can't read the audit log either.
        assert count(s, AuditLog) == 0


def test_admin_reads_audit_log(app_db, db, world):
    with db() as owner:
        owner.execute(text("UPDATE users SET is_admin = true WHERE email = 'alice@x.com'"))
        owner.add(AuditLog(actor_id=None, action="test.event"))
        owner.commit()
    with app_db() as s:
        set_rls_user(s, world["alice"])
        assert count(s, AuditLog) >= 1

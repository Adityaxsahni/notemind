"""Postgres row-level security: the database itself refuses rows from other tenants.

Authorization still happens in Python (app/authz.py) with clear 403/404s. RLS is the second
layer: if a query ever forgets its tenant filter, Postgres returns nothing instead of another
student's notes.

How it fits together:
- The app's engine runs every connection as the restricted role `notemind_app` (SET ROLE, see
  app/db.py). It has data privileges only: no DDL, no TRUNCATE, and audit rows are append-only.
- Each transaction carries the signed-in user's id in the `app.user_id` setting
  (set_rls_user in app/db.py). Policies compare rows against it.
- Migrations, tests' fixtures and admin scripts connect as the table owner, which RLS doesn't
  restrict (it isn't FORCEd), so they can manage everything.
- Policies call SECURITY DEFINER helpers that return the caller's collection ids as an array.
  Wrapped in a scalar subquery, Postgres evaluates them once per statement, not per row.

Scope: tenant data (collections, members, invites, documents, pages, chunks) plus the admin
tables. `users` and `refresh_tokens` are deliberately outside RLS: signing in has to look a
user up before anyone is signed in.

Threat model note: this protects against application bugs (a missing WHERE clause, an IDOR).
It does not stop SQL injection, which could set `app.user_id` itself; parameterized queries
everywhere are the defence for that.

Every statement is idempotent, so a later migration can re-run `apply` after changing a policy.
"""

from collections.abc import Callable

APP_ROLE = "notemind_app"

_TENANT_TABLES = (
    "collections",
    "collection_members",
    "invite_links",
    "documents",
    "document_pages",
    "chunks",
)
_ADMIN_TABLES = ("audit_log", "analytics_events")

_FUNCTIONS = [
    """
    CREATE OR REPLACE FUNCTION app_user() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$
    """,
    # Collections the current user owns or is a member of.
    """
    CREATE OR REPLACE FUNCTION app_readable_collections() RETURNS uuid[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$
        SELECT coalesce(array_agg(id), '{}') FROM (
            SELECT id FROM collections WHERE owner_id = app_user()
            UNION
            SELECT collection_id FROM collection_members WHERE user_id = app_user()
        ) ids
    $$
    """,
    # Only owners change a collection's contents; viewers read.
    """
    CREATE OR REPLACE FUNCTION app_writable_collections() RETURNS uuid[]
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$ SELECT coalesce(array_agg(id), '{}') FROM collections WHERE owner_id = app_user() $$
    """,
    # Joining through an invite: the joiner isn't a member yet, so it can't see the invite.
    """
    CREATE OR REPLACE FUNCTION app_has_open_invite(cid uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$
        SELECT EXISTS (
            SELECT 1 FROM invite_links
            WHERE collection_id = cid AND revoked_at IS NULL AND expires_at > now()
        )
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION app_find_invite(hash text)
    RETURNS TABLE (collection_id uuid, owner_id uuid, expires_at timestamptz,
                   revoked_at timestamptz)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$
        SELECT i.collection_id, c.owner_id, i.expires_at, i.revoked_at
        FROM invite_links i JOIN collections c ON c.id = i.collection_id
        WHERE i.token_hash = hash
    $$
    """,
    # Background jobs get only a document id; they act as that document's collection owner.
    """
    CREATE OR REPLACE FUNCTION app_document_owner(doc uuid) RETURNS uuid
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$
        SELECT c.owner_id FROM documents d JOIN collections c ON c.id = d.collection_id
        WHERE d.id = doc
    $$
    """,
    """
    CREATE OR REPLACE FUNCTION app_is_admin() RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
    AS $$ SELECT coalesce((SELECT is_admin FROM users WHERE id = app_user()), false) $$
    """,
]

_READ = "((SELECT app_readable_collections())::uuid[])"  # an array, computed once per statement
_WRITE = "((SELECT app_writable_collections())::uuid[])"
# Built only from the constants above, never from input.
_PAGE_WRITE = (
    "EXISTS (SELECT 1 FROM documents d "  # noqa: S608
    f"WHERE d.id = document_id AND d.collection_id = ANY {_WRITE})"
)

# (table, policy name, command, USING, WITH CHECK)
_POLICIES = [
    # owner_id first: INSERT ... RETURNING checks the new row against this policy, and the
    # helper's snapshot can't see a row the same statement is inserting.
    ("collections", "read", "SELECT", f"owner_id = app_user() OR id = ANY {_READ}", None),
    ("collections", "create", "INSERT", None, "owner_id = app_user()"),
    ("collections", "update", "UPDATE", "owner_id = app_user()", "owner_id = app_user()"),
    ("collections", "delete", "DELETE", "owner_id = app_user()", None),
    # Your own membership rows always (same RETURNING reason as collections above).
    (
        "collection_members",
        "read",
        "SELECT",
        f"user_id = app_user() OR collection_id = ANY {_READ}",
        None,
    ),
    (
        "collection_members",
        "add",
        "INSERT",
        None,
        f"collection_id = ANY {_WRITE} "
        "OR (user_id = app_user() AND app_has_open_invite(collection_id))",
    ),
    ("collection_members", "update", "UPDATE", f"collection_id = ANY {_WRITE}", None),
    (
        "collection_members",
        "remove",
        "DELETE",
        f"collection_id = ANY {_WRITE} OR user_id = app_user()",  # owners, or leaving yourself
        None,
    ),
    (
        "invite_links",
        "owner",
        "ALL",
        f"collection_id = ANY {_WRITE}",
        f"collection_id = ANY {_WRITE}",
    ),
    ("documents", "read", "SELECT", f"collection_id = ANY {_READ}", None),
    ("documents", "write", "INSERT", None, f"collection_id = ANY {_WRITE}"),
    (
        "documents",
        "update",
        "UPDATE",
        f"collection_id = ANY {_WRITE}",
        f"collection_id = ANY {_WRITE}",
    ),
    ("documents", "delete", "DELETE", f"collection_id = ANY {_WRITE}", None),
    # Pages have no collection_id of their own: they follow their document's visibility.
    (
        "document_pages",
        "read",
        "SELECT",
        "EXISTS (SELECT 1 FROM documents d WHERE d.id = document_id)",
        None,
    ),
    (
        "document_pages",
        "write",
        "ALL",
        _PAGE_WRITE,
        _PAGE_WRITE,
    ),
    ("chunks", "read", "SELECT", f"collection_id = ANY {_READ}", None),
    ("chunks", "write", "INSERT", None, f"collection_id = ANY {_WRITE}"),
    ("chunks", "delete", "DELETE", f"collection_id = ANY {_WRITE}", None),
    # Admin tables: anyone may append; only admins read. No UPDATE/DELETE policy, so the app
    # can never rewrite history (pruning runs as the owner, see app/admin.py).
    ("audit_log", "append", "INSERT", None, "true"),
    ("audit_log", "admin_read", "SELECT", "app_is_admin()", None),
    ("analytics_events", "append", "INSERT", None, "true"),
    ("analytics_events", "admin_read", "SELECT", "app_is_admin()", None),
]


def statements() -> list[str]:
    stmts = [
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END $$
        """,
        # Lets a non-superuser owner (managed Postgres) SET ROLE to it.
        f"GRANT {APP_ROLE} TO CURRENT_USER",
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}",
        f"""ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}""",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}",
        # Append-only audit trail; the app can't touch migration state.
        f"REVOKE UPDATE, DELETE ON audit_log FROM {APP_ROLE}",
        f"""
        DO $$ BEGIN
            IF to_regclass('public.alembic_version') IS NOT NULL THEN
                REVOKE ALL ON alembic_version FROM {APP_ROLE};
            END IF;
        END $$
        """,
        *_FUNCTIONS,
    ]
    for table in (*_TENANT_TABLES, *_ADMIN_TABLES):
        stmts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    for table, name, command, using, check in _POLICIES:
        policy = f"nm_{name}"  # prefixed: names like "create" are reserved words
        stmts.append(f"DROP POLICY IF EXISTS {policy} ON {table}")
        sql = f"CREATE POLICY {policy} ON {table} FOR {command} TO {APP_ROLE}"
        if using:
            sql += f" USING ({using})"
        if check:
            sql += f" WITH CHECK ({check})"
        stmts.append(sql)
    return stmts


def apply(execute: Callable[[str], object]) -> None:
    """Run every statement with `execute` (alembic's op.execute, or a connection's)."""
    for statement in statements():
        execute(statement)

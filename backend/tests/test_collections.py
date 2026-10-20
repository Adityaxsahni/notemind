"""Collections, sharing, and the most important property: tenant isolation (threat T1/T2)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import InviteLink
from tests.conftest import GOOD_PASSWORD, signup


@pytest.fixture
def alice(make_client):
    client = make_client()
    signup(client, "alice@x.com")
    return client


@pytest.fixture
def bob(make_client):
    client = make_client()
    signup(client, "bob@x.com")
    return client


@pytest.fixture
def carol(make_client):
    client = make_client()
    signup(client, "carol@x.com")
    return client


def _create(client, name="DBMS Sem 5"):
    response = client.post("/collections", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def _invite_and_join(owner, joiner, collection_id):
    token = owner.post(f"/collections/{collection_id}/invites", json={}).json()["token"]
    response = joiner.post("/invites/accept", json={"token": token})
    assert response.status_code == 200, response.text
    return response.json()


# --- owner basics ---------------------------------------------------------------------------


def test_owner_crud(alice):
    created = _create(alice, "  OS Sem 4  ")
    assert created["name"] == "OS Sem 4"  # whitespace stripped
    assert created["role"] == "owner"
    cid = created["id"]

    assert [c["id"] for c in alice.get("/collections").json()] == [cid]
    assert alice.patch(f"/collections/{cid}", json={"name": "OS"}).json()["name"] == "OS"
    assert alice.delete(f"/collections/{cid}").status_code == 204
    assert alice.get(f"/collections/{cid}").status_code == 404


@pytest.mark.parametrize("name", ["", "   ", "x" * 121])
def test_invalid_collection_names(alice, name):
    assert alice.post("/collections", json={"name": name}).status_code == 422


def test_collections_require_login(make_client):
    assert make_client().get("/collections").status_code == 401


# --- tenant isolation -----------------------------------------------------------------------


def test_stranger_cannot_see_or_touch_private_collection(alice, bob):
    cid = _create(alice)["id"]

    assert bob.get("/collections").json() == []
    # 404 (not 403) for every operation: the collection's existence isn't revealed.
    assert bob.get(f"/collections/{cid}").status_code == 404
    assert bob.patch(f"/collections/{cid}", json={"name": "pwned"}).status_code == 404
    assert bob.delete(f"/collections/{cid}").status_code == 404
    assert bob.get(f"/collections/{cid}/members").status_code == 404
    assert bob.post(f"/collections/{cid}/invites", json={}).status_code == 404
    assert bob.get(f"/collections/{cid}/invites").status_code == 404

    # And nothing changed for Alice.
    assert alice.get(f"/collections/{cid}").json()["name"] == "DBMS Sem 5"


def test_unknown_and_malformed_ids(alice):
    assert alice.get("/collections/00000000-0000-0000-0000-000000000000").status_code == 404
    assert alice.get("/collections/not-a-uuid").status_code == 422


# --- sharing --------------------------------------------------------------------------------


def test_invite_grants_read_only_access(alice, bob):
    cid = _create(alice)["id"]
    joined = _invite_and_join(alice, bob, cid)
    assert joined["role"] == "viewer"

    assert bob.get(f"/collections/{cid}").json()["role"] == "viewer"
    assert [c["id"] for c in bob.get("/collections").json()] == [cid]

    # Viewers can't manage. Now 403: they already know the collection exists.
    assert bob.patch(f"/collections/{cid}", json={"name": "x"}).status_code == 403
    assert bob.delete(f"/collections/{cid}").status_code == 403
    assert bob.post(f"/collections/{cid}/invites", json={}).status_code == 403
    assert bob.get(f"/collections/{cid}/members").status_code == 403  # no email harvesting


def test_accepting_twice_is_idempotent(alice, bob):
    cid = _create(alice)["id"]
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    for _ in range(2):
        assert bob.post("/invites/accept", json={"token": token}).status_code == 200
    assert len(alice.get(f"/collections/{cid}/members").json()) == 1


def test_owner_accepting_own_invite_stays_owner(alice):
    cid = _create(alice)["id"]
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    assert alice.post("/invites/accept", json={"token": token}).json()["role"] == "owner"
    assert alice.get(f"/collections/{cid}/members").json() == []


def test_revoked_invite_stops_working(alice, bob):
    cid = _create(alice)["id"]
    invite = alice.post(f"/collections/{cid}/invites", json={}).json()
    assert alice.delete(f"/collections/{cid}/invites/{invite['id']}").status_code == 204
    assert bob.post("/invites/accept", json={"token": invite["token"]}).status_code == 404
    assert bob.get(f"/collections/{cid}").status_code == 404


def test_expired_invite_stops_working(alice, bob, db):
    cid = _create(alice)["id"]
    invite = alice.post(f"/collections/{cid}/invites", json={}).json()
    with db() as session:
        row = session.get(InviteLink, invite["id"])
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    assert bob.post("/invites/accept", json={"token": invite["token"]}).status_code == 404


def test_bogus_invite_token(bob):
    assert bob.post("/invites/accept", json={"token": "guess"}).status_code == 404


def test_invite_list_never_exposes_tokens(alice):
    cid = _create(alice)["id"]
    token = alice.post(f"/collections/{cid}/invites", json={}).json()["token"]
    listing = alice.get(f"/collections/{cid}/invites")
    assert listing.status_code == 200
    assert token not in listing.text


def test_cannot_revoke_invite_via_another_collection(alice):
    first = _create(alice, "A")["id"]
    second = _create(alice, "B")["id"]
    invite = alice.post(f"/collections/{first}/invites", json={}).json()
    assert alice.delete(f"/collections/{second}/invites/{invite['id']}").status_code == 404


def test_owner_removes_member(alice, bob):
    cid = _create(alice)["id"]
    _invite_and_join(alice, bob, cid)
    bob_id = bob.get("/me").json()["id"]
    assert alice.delete(f"/collections/{cid}/members/{bob_id}").status_code == 204
    assert bob.get(f"/collections/{cid}").status_code == 404


def test_member_can_leave_but_owner_cannot(alice, bob):
    cid = _create(alice)["id"]
    _invite_and_join(alice, bob, cid)
    bob_id = bob.get("/me").json()["id"]
    alice_id = alice.get("/me").json()["id"]
    assert bob.delete(f"/collections/{cid}/members/{bob_id}").status_code == 204
    assert bob.get(f"/collections/{cid}").status_code == 404
    assert alice.delete(f"/collections/{cid}/members/{alice_id}").status_code == 400


def test_viewer_cannot_remove_other_members(alice, bob, carol):
    cid = _create(alice)["id"]
    _invite_and_join(alice, bob, cid)
    _invite_and_join(alice, carol, cid)
    carol_id = carol.get("/me").json()["id"]
    assert bob.delete(f"/collections/{cid}/members/{carol_id}").status_code == 403
    assert carol.get(f"/collections/{cid}").status_code == 200


# --- account deletion & export (DPDP rights) -----------------------------------------------


def test_delete_account_requires_password_and_erases_data(alice, bob, make_client):
    cid = _create(alice)["id"]
    _invite_and_join(alice, bob, cid)

    wrong = alice.request("DELETE", "/me", json={"password": "nope-nope-nope"})
    assert wrong.status_code == 403

    assert alice.request("DELETE", "/me", json={"password": GOOD_PASSWORD}).status_code == 204
    # Session is dead, data is gone, and the shared collection vanished for Bob too.
    assert alice.get("/me").status_code == 401
    assert bob.get(f"/collections/{cid}").status_code == 404
    login = make_client().post(
        "/auth/login", json={"email": "alice@x.com", "password": GOOD_PASSWORD}
    )
    assert login.status_code == 401


def test_export_contains_only_own_data(alice, bob):
    owned = _create(alice, "Alice private")["id"]
    shared = _create(bob, "Bob shared")["id"]
    _create(bob, "Bob private")
    _invite_and_join(bob, alice, shared)

    export = alice.get("/me/export").json()
    assert export["user"]["email"] == "alice@x.com"
    assert [c["id"] for c in export["collections_owned"]] == [owned]
    assert [c["id"] for c in export["collections_shared_with_me"]] == [shared]
    assert "Bob private" not in str(export)

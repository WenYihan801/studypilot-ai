"""Proves Postgres Row Level Security against a REAL Supabase project (skipped unless configured).

Run after `supabase db push` on your *dev* project:

    RLS_SUPABASE_URL=https://xxxx.supabase.co \
    RLS_PUBLISHABLE_KEY=sb_publishable_... \
    RLS_USER_A_EMAIL=a@example.com RLS_USER_A_PASSWORD=... \
    RLS_USER_B_EMAIL=b@example.com RLS_USER_B_PASSWORD=... \
    uv run pytest tests/integration -v

Create the two users in Supabase Dashboard -> Authentication -> Users -> "Add user" (auto-confirm).
These tests talk to PostgREST directly with each user's JWT, bypassing our backend entirely,
which is exactly what an attacker holding the public publishable key could do.
"""

import os
import uuid

import pytest

REQUIRED = [
    "RLS_SUPABASE_URL",
    "RLS_PUBLISHABLE_KEY",
    "RLS_USER_A_EMAIL",
    "RLS_USER_A_PASSWORD",
    "RLS_USER_B_EMAIL",
    "RLS_USER_B_PASSWORD",
]
pytestmark = pytest.mark.skipif(any(not os.environ.get(k) for k in REQUIRED), reason="live Supabase RLS env not set")


def _login(prefix: str):
    from supabase import create_client

    client = create_client(os.environ["RLS_SUPABASE_URL"], os.environ["RLS_PUBLISHABLE_KEY"])
    session = client.auth.sign_in_with_password(
        {"email": os.environ[f"{prefix}_EMAIL"], "password": os.environ[f"{prefix}_PASSWORD"]}
    )
    return client, session.user.id


@pytest.fixture(scope="module")
def users():
    a, a_id = _login("RLS_USER_A")
    b, b_id = _login("RLS_USER_B")
    ws = a.table("workspaces").insert({"user_id": a_id, "name": f"rls-test-{uuid.uuid4().hex[:6]}"}).execute().data[0]
    yield {"a": a, "a_id": a_id, "b": b, "b_id": b_id, "ws": ws}
    a.table("workspaces").delete().eq("id", ws["id"]).execute()


def test_b_cannot_read_a_workspace(users):
    rows = users["b"].table("workspaces").select("*").eq("id", users["ws"]["id"]).execute().data
    assert rows == []


def test_b_cannot_update_or_delete_a_workspace(users):
    users["b"].table("workspaces").update({"name": "hacked"}).eq("id", users["ws"]["id"]).execute()
    users["b"].table("workspaces").delete().eq("id", users["ws"]["id"]).execute()
    row = users["a"].table("workspaces").select("name").eq("id", users["ws"]["id"]).execute().data[0]
    assert row["name"].startswith("rls-test-")


def test_b_cannot_insert_rows_owned_by_a(users):
    from postgrest.exceptions import APIError

    with pytest.raises(APIError):
        users["b"].table("workspaces").insert({"user_id": users["a_id"], "name": "spoof"}).execute()


def test_b_cannot_attach_document_to_a_workspace(users):
    from postgrest.exceptions import APIError

    with pytest.raises(APIError):
        users["b"].table("documents").insert(
            {
                "workspace_id": users["ws"]["id"],
                "user_id": users["b_id"],
                "filename": "x.txt",
                "storage_path": "x",
                "mime_type": "text/plain",
                "size_bytes": 1,
                "sha256": "0" * 64,
            }
        ).execute()


def test_users_cannot_forge_usage_or_scores(users):
    from postgrest.exceptions import APIError

    with pytest.raises(APIError):
        users["a"].table("ai_usage_events").insert(
            {"user_id": users["a_id"], "provider": "x", "model": "x", "operation": "x"}
        ).execute()
    users["a"].table("ai_usage_events").delete().eq("user_id", users["a_id"]).execute()  # silently affects 0 rows


def test_match_chunks_returns_nothing_for_foreign_workspace(users):
    rows = (
        users["b"]
        .rpc(
            "match_chunks",
            {
                "query_embedding": [0.0] * 767 + [1.0],
                "p_workspace_id": users["ws"]["id"],
                "p_user_id": users["a_id"],
                "match_count": 5,
            },
        )
        .execute()
        .data
    )
    assert rows == []


def test_storage_paths_are_private(users):
    path = f"{users['a_id']}/rls-test/{uuid.uuid4()}.txt"
    users["a"].storage.from_("documents").upload(path, b"secret", {"content-type": "text/plain"})
    try:
        with pytest.raises(Exception):  # noqa: B017 - storage raises a client error type that varies by version
            users["b"].storage.from_("documents").download(path)
        with pytest.raises(Exception):  # noqa: B017
            users["b"].storage.from_("documents").upload(f"{users['a_id']}/evil.txt", b"x", {"content-type": "text/plain"})
    finally:
        users["a"].storage.from_("documents").remove([path])

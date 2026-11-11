"""Health, authentication, workspace CRUD and cross-user isolation."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import security
from app.core.config import get_settings
from app.core.errors import UnauthorizedError


def test_health_is_public(anon):
    r = anon.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["ai_provider"] == "mock"


def test_protected_endpoint_requires_token(anon):
    r = anon.get("/api/v1/workspaces")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_cors_allowlist(anon):
    ok = anon.options("/api/v1/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = anon.options("/api/v1/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


# ---------------------------------------------------------------- real JWT verification (no network)
class _FakeJWKClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, token):
        class K:
            key = self._key

        return K()


@pytest.fixture
def es256(monkeypatch):
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(security, "_jwks_client", lambda url: _FakeJWKClient(private.public_key()))
    return private


def _token(private, **overrides):
    s = get_settings()
    claims = {
        "sub": "user-123",
        "email": "a@example.com",
        "aud": "authenticated",
        "iss": s.supabase_jwt_issuer,
        "exp": int(time.time()) + 600,
        **overrides,
    }
    return jwt.encode(claims, private, algorithm="ES256")


def test_valid_supabase_jwt_is_accepted(es256):
    claims = security.verify_access_token(_token(es256), get_settings())
    assert claims["sub"] == "user-123"


@pytest.mark.parametrize(
    "override,code",
    [
        ({"exp": int(time.time()) - 10}, "token_expired"),
        ({"aud": "anon"}, "unauthorized"),
        ({"iss": "https://attacker.supabase.co/auth/v1"}, "unauthorized"),
    ],
)
def test_invalid_jwts_are_rejected(es256, override, code):
    with pytest.raises(UnauthorizedError) as exc:
        security.verify_access_token(_token(es256, **override), get_settings())
    assert exc.value.code == code


def test_jwt_signed_by_other_key_is_rejected(es256):
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(UnauthorizedError):
        security.verify_access_token(_token(other), get_settings())


def test_hs256_token_is_rejected(es256):
    s = get_settings()
    forged = jwt.encode(
        {"sub": "x", "aud": "authenticated", "iss": s.supabase_jwt_issuer, "exp": int(time.time()) + 60},
        "guessable-secret",
        algorithm="HS256",
    )
    with pytest.raises(UnauthorizedError):
        security.verify_access_token(forged, s)


# ---------------------------------------------------------------- workspaces
def test_workspace_crud(client_a):
    r = client_a.post("/api/v1/workspaces", json={"name": "  Cybersecurity  ", "description": "Week 1-12"})
    assert r.status_code == 201
    ws = r.json()
    assert ws["name"] == "Cybersecurity" and ws["document_count"] == 0

    assert [w["id"] for w in client_a.get("/api/v1/workspaces").json()] == [ws["id"]]

    r = client_a.patch(f"/api/v1/workspaces/{ws['id']}", json={"name": "Cyber Security"})
    assert r.status_code == 200 and r.json()["name"] == "Cyber Security"
    assert r.json()["description"] == "Week 1-12"

    assert client_a.delete(f"/api/v1/workspaces/{ws['id']}").status_code == 204
    assert client_a.get(f"/api/v1/workspaces/{ws['id']}").status_code == 404


def test_workspace_validation(client_a):
    r = client_a.post("/api/v1/workspaces", json={"name": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_failed"
    r = client_a.post("/api/v1/workspaces", json={"name": "x" * 121})
    assert r.status_code == 422


def test_users_cannot_see_or_modify_each_others_workspaces(client_a, client_b, workspace):
    wid = workspace["id"]
    assert client_b.get("/api/v1/workspaces").json() == []
    assert client_b.get(f"/api/v1/workspaces/{wid}").status_code == 404
    assert client_b.patch(f"/api/v1/workspaces/{wid}", json={"name": "hacked"}).status_code == 404
    assert client_b.delete(f"/api/v1/workspaces/{wid}").status_code == 404
    assert client_a.get(f"/api/v1/workspaces/{wid}").json()["name"] == "Database Systems"


def test_profile_update(client_a):
    r = client_a.patch("/api/v1/me", json={"display_name": "Wei Ming"})
    assert r.status_code == 200 and r.json()["display_name"] == "Wei Ming"
    assert client_a.get("/api/v1/me").json()["display_name"] == "Wei Ming"

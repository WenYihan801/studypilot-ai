"""Supabase Auth JWT verification using the project's public JWKS (asymmetric signing keys).

Supabase signs access tokens with a private key and publishes the public keys at
{SUPABASE_URL}/auth/v1/.well-known/jwks.json, so the backend can verify tokens locally
without storing any signing secret.
"""

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import UnauthorizedError

ALLOWED_ALGORITHMS = ["ES256", "RS256"]


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    access_token: str


@lru_cache
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    # Caches keys in memory; refetches when it sees an unknown `kid` (key rotation).
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)


def verify_access_token(token: str, settings: Settings) -> dict:
    try:
        signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_jwt_issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Session expired. Please sign in again.", code="token_expired") from exc
    except (jwt.PyJWKClientError, jwt.InvalidTokenError) as exc:
        raise UnauthorizedError("Invalid authentication token.") from exc


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("Missing bearer token.")
    return token.strip()


def get_current_user(request: Request, settings: Settings = Depends(get_settings)) -> CurrentUser:
    token = _bearer_token(request)
    claims = verify_access_token(token, settings)
    return CurrentUser(id=claims["sub"], email=claims.get("email"), access_token=token)

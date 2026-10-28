"""Session handling (FR-0.1, FR-0.2, NFR-8).

Login itself happens in the browser with Supabase Auth (Google sign-in per the UI
prototype). The browser sends the Supabase access token as a Bearer token and we
verify it here, so we never see or store passwords.

Before Supabase is set up, DEV_AUTH lets you use tokens like "dev:alice@example.com".
Turn it off for anything public."""

from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _decode(token: str) -> dict:
    s = get_settings()
    if s.dev_auth and token.startswith("dev:"):
        email = token[4:].strip().lower() or "guest@example.com"
        return {"sub": f"dev-{email}", "email": email, "user_metadata": {"full_name": email.split("@")[0]}}
    try:
        if s.supabase_jwt_secret:  # legacy HS256 projects
            return jwt.decode(token, s.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        if s.supabase_url:  # current Supabase projects sign with asymmetric keys
            key = _jwks_client(s.supabase_url).get_signing_key_from_jwt(token)
            return jwt.decode(token, key.key, algorithms=["ES256", "RS256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid session: {e}") from e
    raise HTTPException(401, "Auth isn't configured on the server")


def _user_from_claims(db: Session, claims: dict) -> User:
    uid = str(claims["sub"])
    user = db.get(User, uid)
    meta = claims.get("user_metadata") or {}
    if user is None:
        user = User(id=uid, email=claims.get("email"), display_name=meta.get("full_name") or meta.get("name"))
        db.add(user)
        db.commit()
    return user


def optional_user(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return _user_from_claims(db, _decode(authorization[7:].strip()))


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Please sign in to use this feature")
    return user

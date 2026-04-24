"""Password hashing + JWT helpers for the PlantPal backend.

Roles in use:
- ``editor`` — can create/modify/delete plants
- ``viewer`` — read-only (default for newly issued tokens)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from app.config import Settings, get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def create_access_token(
    *,
    subject: str,
    settings: Settings | None = None,
    roles: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.jwt_expiry_minutes))
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "roles": roles or ["viewer"],
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def require_role(*allowed_roles: str):
    """Return a FastAPI dependency that enforces at least one of the roles."""

    def _dependency(token: str | None = Depends(oauth2_scheme)) -> dict:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = decode_token(token)
        user_roles = set(payload.get("roles", []))
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return payload

    return _dependency


# ---------------------------------------------------------------------------
# In-memory user store (demo / EX3 baseline).  In a real deployment this
# would live in the DB — kept inline to stay KISS for the coursework.
# ---------------------------------------------------------------------------

_USERS: dict[str, dict] = {}


def _seed_users() -> None:
    settings = get_settings()
    if settings.default_editor_username in _USERS:
        return
    _USERS[settings.default_editor_username] = {
        "username": settings.default_editor_username,
        "hashed_password": hash_password(settings.default_editor_password),
        "roles": ["editor"],
    }
    # A read-only demo user so we can also show 403 behaviour cleanly.
    _USERS.setdefault(
        "viewer",
        {
            "username": "viewer",
            "hashed_password": hash_password("viewer"),
            "roles": ["viewer"],
        },
    )


def authenticate_user(username: str, password: str) -> dict | None:
    _seed_users()
    record = _USERS.get(username)
    if not record or not verify_password(password, record["hashed_password"]):
        return None
    return record

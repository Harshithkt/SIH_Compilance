"""Authentication and role-based access control.

Identity comes from a signed bearer token on every request and never from a name in
the request body. The officer named on a review, a correction or a case closure is
what the evidence record and the docket's certificate carry, so a client free to set
that field could attribute its own actions to another officer.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import get_db
from app.models import AuditLog, User

logger = logging.getLogger(__name__)

# Ranked: each role holds every permission of the ones before it.
ROLES: tuple[str, ...] = ("officer", "supervisor", "admin")
_RANK = {role: rank for rank, role in enumerate(ROLES)}

_ALGORITHM = "HS256"
# bcrypt ignores everything past 72 bytes, which would make two different long
# passwords interchangeable — reject rather than silently truncate.
_MAX_PASSWORD_BYTES = 72
_DEFAULT_BOOTSTRAP_PASSWORD = Settings.model_fields["bootstrap_password"].default

if settings.jwt_secret:
    _SECRET = settings.jwt_secret
else:
    _SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "LABELLENS_JWT_SECRET is not set — signing tokens with a random per-process "
        "secret, so everyone is signed out when the server restarts."
    )


class PasswordTooLong(ValueError):
    pass


def hash_password(password: str) -> str:
    if len(password.encode()) > _MAX_PASSWORD_BYTES:
        raise PasswordTooLong(f"Password must be at most {_MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode()) > _MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(user: User) -> tuple[str, datetime]:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.jwt_expiry_minutes)
    token = jwt.encode(
        {
            "sub": user.username,
            "role": user.role,
            "name": user.full_name,
            "iat": issued_at,
            "exp": expires_at,
        },
        _SECRET,
        algorithm=_ALGORITHM,
    )
    return token, expires_at


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _credentials_error()
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        raise _credentials_error() from None

    user = db.execute(
        select(User).where(User.username == payload.get("sub"))
    ).scalar_one_or_none()
    # Re-read from the database rather than trusting the token's claims, so a
    # deactivated account or a changed role takes effect at once instead of at expiry.
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


def require_role(minimum: str):
    """Dependency admitting only `minimum` and the roles above it."""
    if minimum not in _RANK:
        raise ValueError(f"Unknown role: {minimum}")

    def dependency(user: User = Depends(get_current_user)) -> User:
        if _RANK[user.role] < _RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the {minimum} role.",
            )
        return user

    return dependency


def outranks(user: User, minimum: str) -> bool:
    return _RANK[user.role] >= _RANK[minimum]


def record_audit(
    db: Session,
    *,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_username=actor.username,
            actor_role=actor.role,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )
    db.flush()


def bootstrap_users(db: Session) -> None:
    """Create the starting accounts, once, on a database that has none.

    Without this a fresh deployment has no way in at all. It never touches a database
    that already holds accounts, so a changed password is never reset underneath a
    running deployment.
    """
    if db.execute(select(User)).first():
        return

    if settings.bootstrap_password == _DEFAULT_BOOTSTRAP_PASSWORD:
        logger.warning(
            "Creating the starting accounts with the default bootstrap password. "
            "Set LABELLENS_BOOTSTRAP_PASSWORD before any real deployment."
        )

    # Hashed once: the three accounts start from the same password by construction, so
    # per-account salts would only pay bcrypt's cost twice more for no added secrecy.
    password_hash = hash_password(settings.bootstrap_password)

    for username, full_name, role in (
        ("officer", "Insp. R. Sharma", "officer"),
        ("supervisor", settings.supervisor_role_name, "supervisor"),
        ("admin", "System Administrator", "admin"),
    ):
        db.add(
            User(
                username=username,
                full_name=full_name,
                role=role,
                password_hash=password_hash,
            )
        )
    db.commit()

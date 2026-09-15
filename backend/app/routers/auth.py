import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    ROLES,
    PasswordTooLong,
    create_access_token,
    get_current_user,
    hash_password,
    record_audit,
    require_role,
    verify_password,
)
from app.database import get_db
from app.models import AuditLog, User
from app.schemas import (
    AuditLogOut,
    LoginIn,
    PasswordChangeIn,
    TokenOut,
    UserCreateIn,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == payload.username.strip().lower())
    ).scalar_one_or_none()

    # One message for every failure mode, and the hash comparison runs even when there
    # is no such account, so the response neither confirms which usernames exist nor
    # leaks it through how long the request took.
    if user is None:
        verify_password(payload.password, hash_password("no-such-account"))
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    if not verify_password(payload.password, user.password_hash) or not user.is_active:
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    token, expires_at = create_access_token(user)
    record_audit(db, actor=user, action="auth.login")
    db.commit()
    return TokenOut(access_token=token, expires_at=expires_at, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/password", response_model=UserOut)
def change_password(
    payload: PasswordChangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Current password is incorrect.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    try:
        user.password_hash = hash_password(payload.new_password)
    except PasswordTooLong as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(db, actor=user, action="auth.password_changed")
    db.commit()
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    return db.execute(select(User).order_by(User.username)).scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreateIn,
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
):
    username = payload.username.strip().lower()
    if not username:
        raise HTTPException(status_code=422, detail="Username is required.")
    if payload.role not in ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {ROLES}")
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="That username is already taken.")

    try:
        password_hash = hash_password(payload.password)
    except PasswordTooLong as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user = User(
        username=username,
        full_name=payload.full_name.strip() or username,
        role=payload.role,
        password_hash=password_hash,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor=actor,
        action="auth.user_created",
        target_type="user",
        target_id=user.id,
        detail={"username": user.username, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{username}/active", response_model=UserOut)
def set_user_active(
    username: str,
    active: bool = Query(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_role("admin")),
):
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="No such account.")
    # An administrator who deactivates their own account would lock the deployment out
    # of user management entirely if they were the last one.
    if user.id == actor.id and not active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account.")

    user.is_active = active
    record_audit(
        db,
        actor=actor,
        action="auth.user_activated" if active else "auth.user_deactivated",
        target_type="user",
        target_id=user.id,
        detail={"username": user.username},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit", response_model=list[AuditLogOut])
def read_audit_log(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_role("supervisor")),
):
    return (
        db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )

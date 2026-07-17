import hashlib
import secrets
from datetime import timedelta

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.child import utc_now
from app.models.user import User, UserSession

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def login_user(session: Session, username: str, password: str) -> tuple[User, str] | None:
    user = session.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        return None
    raw_token = secrets.token_urlsafe(32)
    user.last_login_at = utc_now()
    session.add(UserSession(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(days=30),
    ))
    session.commit()
    return user, raw_token


def get_user_for_token(session: Session, raw_token: str) -> User | None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = session.execute(
        select(User).join(UserSession, UserSession.user_id == User.id).where(
            UserSession.token_hash == token_hash,
            UserSession.expires_at > utc_now(),
        )
    )
    return result.scalar_one_or_none()


def logout_token(session: Session, raw_token: str) -> None:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    stored = session.scalar(select(UserSession).where(UserSession.token_hash == token_hash))
    if stored is not None:
        session.delete(stored)
        session.commit()

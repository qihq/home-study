from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.user import User
from app.services.users import get_user_for_token

DbSession = Annotated[Session, Depends(get_db_session)]


def require_user(session: DbSession, family_learning_session: Annotated[str | None, Cookie()] = None) -> User:
    if family_learning_session is None:
        raise HTTPException(status_code=401, detail={'code': 'AUTH_REQUIRED', 'message': '请先登录'})
    user = get_user_for_token(session, family_learning_session)
    if user is None:
        raise HTTPException(status_code=401, detail={'code': 'AUTH_REQUIRED', 'message': '会话已失效'})
    return user


def require_resource_owner(session, owner_user_id: str | None, user: User) -> None:
    """Allow unowned legacy resources only while the installation has one account."""
    if owner_user_id == user.id:
        return
    if owner_user_id is None and session.scalar(select(func.count(User.id))) == 1:
        return
    raise HTTPException(403, detail={'code': 'RESOURCE_ACCESS_DENIED', 'message': 'æ— æƒè®¿é—®è¯¥èµ„æº'})

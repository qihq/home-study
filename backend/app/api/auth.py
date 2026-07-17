from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DbSession, require_user
from app.core.config import get_settings
from app.models.user import User
from app.services.users import hash_password, login_user, logout_token

router = APIRouter(tags=['auth'])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=512)


@router.get('/setup/status')
def setup_status(session: DbSession) -> dict[str, bool]:
    return {'needs_initial_admin': not bool(session.scalar(select(func.count()).select_from(User)))}


@router.post('/setup/initial-admin', status_code=201)
def initial_admin(payload: LoginRequest, session: DbSession) -> dict[str, str]:
    if session.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=409, detail={'code': 'INITIAL_ADMIN_EXISTS', 'message': '管理员已经创建'})
    user = User(username=payload.username, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    return {'id': user.id, 'username': user.username}


@router.post('/auth/login')
def login(payload: LoginRequest, response: Response, session: DbSession) -> dict[str, str]:
    result = login_user(session, payload.username, payload.password)
    if result is None:
        raise HTTPException(status_code=401, detail={'code': 'LOGIN_FAILED', 'message': '用户名或密码不正确'})
    user, raw_token = result
    response.set_cookie(
        key='family_learning_session',
        value=raw_token,
        httponly=True,
        secure=get_settings().environment == 'production',
        samesite='lax',
        max_age=30 * 24 * 60 * 60,
    )
    return {'id': user.id, 'username': user.username}


@router.post('/auth/logout')
def logout(response: Response, session: DbSession, family_learning_session: Annotated[str | None, Cookie()] = None) -> dict[str, bool]:
    if family_learning_session:
        logout_token(session, family_learning_session)
    response.delete_cookie('family_learning_session', httponly=True, samesite='lax')
    return {'ok': True}


@router.get('/me')
def me(user: Annotated[User, __import__('fastapi').Depends(require_user)]) -> dict[str, str]:
    return {'id': user.id, 'username': user.username}

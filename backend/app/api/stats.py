from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DbSession, require_user
from app.models.child import Child
from app.models.user import User
from app.services.reading_stats import build_reading_stats
from app.services.dictation_stats import build_dictation_stats, build_mistakes

router = APIRouter(tags=['stats'])


@router.get('/stats/reading')
def reading_stats(
    session: DbSession,
    _user: Annotated[User, Depends(require_user)],
    period: Literal['week', 'month'] = 'week',
    reference_date: date = Query(default_factory=date.today, alias='date'),
) -> dict:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        raise HTTPException(404, detail={'code': 'CHILD_NOT_FOUND', 'message': '孩子档案不存在'})
    return build_reading_stats(session, child.id, period, reference_date)


@router.get('/stats/dictation')
def dictation_stats(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        raise HTTPException(404, detail={'code': 'CHILD_NOT_FOUND', 'message': '孩子档案不存在'})
    return build_dictation_stats(session, child.id)


@router.get('/stats/mistakes')
def mistakes(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> list[dict]:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        raise HTTPException(404, detail={'code': 'CHILD_NOT_FOUND', 'message': '孩子档案不存在'})
    return build_mistakes(session, child.id)

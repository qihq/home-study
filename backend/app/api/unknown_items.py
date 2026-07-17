from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, require_user
from app.models.child import Child
from app.models.user import User
from app.services.unknown_items import create_learning_list_from_unknown_items, delete_unknown_item, list_unknown_items, mark_unknown, update_unknown_status

router = APIRouter(tags=['unknown-items'])


def _current_child(session):
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='孩子', slug='default-child')
        session.add(child)
        session.flush()
    return child


class UnknownItemStatus(BaseModel):
    status: Literal['unknown', 'mastered']


class UnknownItemSelection(BaseModel):
    unknown_item_ids: list[str]


@router.post('/dictionary/entries/{entry_id}/mark-unknown')
def mark(entry_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        unknown = mark_unknown(session, _current_child(session).id, entry_id)
    except ValueError as error:
        raise HTTPException(404, detail={'code': str(error), 'message': '辞典条目不存在'}) from error
    return {'id': unknown.id, 'status': unknown.status}


@router.get('/unknown-items')
def list_items(
    session: DbSession,
    _user: Annotated[User, Depends(require_user)],
    status: Literal['unknown', 'mastered'] | None = None,
    item_type: Literal['word', 'phrase', 'sentence'] | None = None,
) -> list[dict]:
    return [
        {'id': item.id, 'item_type': item.item_type, 'source_text': item.source_text,
         'translation_text': item.translation_text, 'status': item.status}
        for item in list_unknown_items(session, _current_child(session).id, status, item_type)
    ]


@router.patch('/unknown-items/{unknown_id}')
def update(unknown_id: str, payload: UnknownItemStatus, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        item = update_unknown_status(session, _current_child(session).id, unknown_id, payload.status)
    except ValueError as error:
        raise HTTPException(404, detail={'code': str(error), 'message': '生词不存在'}) from error
    return {'id': item.id, 'status': item.status}


@router.delete('/unknown-items/{unknown_id}', status_code=204)
def delete(unknown_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> None:
    try:
        delete_unknown_item(session, _current_child(session).id, unknown_id)
    except ValueError as error:
        raise HTTPException(404, detail={'code': str(error), 'message': '生词不存在'}) from error


@router.post('/learning-lists/from-unknown-items', status_code=201)
def create_learning_list(payload: UnknownItemSelection, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        learning_list = create_learning_list_from_unknown_items(session, _current_child(session).id, payload.unknown_item_ids)
    except ValueError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': '未选择生词'}) from error
    return {'id': learning_list.id, 'status': learning_list.status}

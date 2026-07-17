from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_user
from app.models.child import Child
from app.models.learning_item import LearningItem, LearningList, LearningListVersion
from app.models.user import User
from app.services.learning_items import confirm_learning_list, create_learning_list

router = APIRouter(tags=['learning-lists'])


class LearningItemInput(BaseModel):
    display_text: str = Field(min_length=1, max_length=2_000)
    item_type: Literal['word', 'phrase', 'sentence'] | None = None
    source_language: Literal['en', 'zh'] = 'en'
    target_language: Literal['en', 'zh'] | None = None
    translation_text: str | None = None


class CreateLearningList(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    items: list[LearningItemInput] = Field(min_length=1)


@router.get('/learning-lists')
def list_learning_lists(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> list[dict]:
    lists = session.scalars(select(LearningList).order_by(LearningList.created_at.desc())).all()
    response = []
    for learning_list in lists:
        version = session.scalar(select(LearningListVersion).where(
            LearningListVersion.word_list_id == learning_list.id,
            LearningListVersion.version == learning_list.current_version,
        )) if learning_list.current_version else None
        items = session.scalars(select(LearningItem).where(
            LearningItem.word_list_version_id == version.id
        ).order_by(LearningItem.position)).all() if version else []
        response.append({'id': learning_list.id, 'title': learning_list.title, 'status': learning_list.status,
                         'learning_list_version_id': version.id if version else None,
                         'items': [{'display_text': item.display_text, 'item_type': item.item_type} for item in items]})
    return response


@router.post('/learning-lists', status_code=status.HTTP_201_CREATED)
def create(payload: CreateLearningList, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='孩子', slug='default-child')
        session.add(child)
        session.flush()
    learning_list = create_learning_list(session, child.id, payload.title, [item.model_dump(exclude_none=True) for item in payload.items])
    return {'id': learning_list.id, 'status': learning_list.status, 'item_count': len(payload.items)}


@router.post('/learning-lists/{learning_list_id}/confirm')
def confirm(learning_list_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        version = confirm_learning_list(session, learning_list_id)
    except ValueError:
        raise HTTPException(404, detail={'code': 'LEARNING_LIST_NOT_FOUND', 'message': '学习本不存在'})
    return {'learning_list_version_id': version.id, 'version': version.version}

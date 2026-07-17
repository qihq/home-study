from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, require_user
from app.models.child import Child
from app.models.word_list import WordItem, WordList, WordListVersion
from app.models.user import User
from app.models.job import Job
from app.services.jobs import enqueue_once
from app.services.words import confirm_word_list, create_draft_word_list, parse_pasted_words
from app.services.learning_items import replace_confirmed_learning_list
from app.services.ai_config import spelling_ocr_provider
from app.services.openai_chat import OpenAiChatError
from app.services.spelling_ocr import SpellingOcrError, recognize_spelling_image

router = APIRouter(tags=['word-lists'])


class CreateWordList(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    pasted_text: str = Field(min_length=1, max_length=20_000)
    source_type: Literal['paste', 'image', 'file'] = 'paste'


class UpdateWordList(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    pasted_text: str = Field(min_length=1, max_length=20_000)


class PronunciationSourceInput(BaseModel):
    pronunciation_source: Literal['default', 'configured', 'custom']


def _tts_progress(session: DbSession, version_id: str) -> dict:
    item_ids = list(session.scalars(select(WordItem.id).where(
        WordItem.word_list_version_id == version_id,
        WordItem.source_language == 'en',
    )))
    if not item_ids:
        return {'total': 0, 'ready': 0, 'queued': 0, 'running': 0, 'failed': 0, 'progress': 100}
    jobs = session.scalars(select(Job).where(
        Job.type == 'generate_tts', Job.entity_id.in_(item_ids),
    )).all()
    counts = {status: sum(job.status == status for job in jobs) for status in ('queued', 'running', 'failed')}
    ready = sum(item.tts_asset_id is not None for item in session.scalars(select(WordItem).where(WordItem.id.in_(item_ids))))
    progress = round((ready * 100 + sum(job.progress for job in jobs if job.status in {'queued', 'running'})) / len(item_ids))
    return {'total': len(item_ids), 'ready': ready, **counts, 'progress': min(progress, 100)}


@router.post('/word-lists/recognize-image')
async def recognize_image(
    session: DbSession, _user: Annotated[User, Depends(require_user)], file: UploadFile = File(...),
) -> dict:
    if not (file.content_type or '').startswith('image/'):
        raise HTTPException(422, detail={'code': 'OCR_IMAGE_INVALID', 'message': 'Please upload an image'})
    image = await file.read()
    if not image or len(image) > 10 * 1024 * 1024:
        raise HTTPException(422, detail={'code': 'OCR_IMAGE_INVALID', 'message': 'Image must be between 1 byte and 10 MB'})
    try:
        secret, base_url, model, timeout_seconds, _temperature = spelling_ocr_provider(session)
        words = recognize_spelling_image(image, file.content_type or 'image/jpeg', api_key=secret, base_url=base_url, model=model, timeout_seconds=timeout_seconds)
    except ValueError as error:
        raise HTTPException(409, detail={'code': str(error), 'message': 'Spelling recognition AI is not configured'}) from error
    except OpenAiChatError as error:
        raise HTTPException(502, detail={'code': str(error), 'message': 'Spelling recognition AI request failed'}) from error
    except SpellingOcrError as error:
        raise HTTPException(422, detail={'code': str(error), 'message': 'No usable English words were recognized'}) from error
    return {'words': words}


@router.get('/word-lists')
def list_word_lists(session: DbSession, _user: Annotated[User, Depends(require_user)]) -> list[dict]:
    lists = session.scalars(select(WordList).where(WordList.status != 'archived').order_by(WordList.created_at.desc())).all()
    result = []
    for word_list in lists:
        version = session.scalar(select(WordListVersion).where(WordListVersion.word_list_id == word_list.id, WordListVersion.version == word_list.current_version)) if word_list.current_version else None
        items = session.scalars(select(WordItem).where(WordItem.word_list_version_id == version.id).order_by(WordItem.position)).all() if version else []
        result.append({
            'id': word_list.id, 'title': word_list.title, 'status': word_list.status,
            'source_type': word_list.source_type, 'word_list_version_id': version.id if version else None,
            'items': [item.display_text for item in items],
            'item_details': [
                {'id': item.id, 'display_text': item.display_text, 'pronunciation_source': item.pronunciation_source,
                 'audio_ready': item.tts_asset_id is not None}
                for item in items
            ],
            'tts_progress': _tts_progress(session, version.id) if version else None,
        })
    return result


@router.post('/word-lists', status_code=status.HTTP_201_CREATED)
def create_word_list(payload: CreateWordList, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None:
        child = Child(display_name='孩子', slug='default-child')
        session.add(child); session.flush()
    items = parse_pasted_words(payload.pasted_text)
    if not items:
        raise HTTPException(422, detail={'code': 'NO_WORDS_FOUND', 'message': '没有识别到单词'})
    word_list = create_draft_word_list(session, child.id, payload.title, items)
    word_list.source_type = payload.source_type
    session.commit()
    return {'id': word_list.id, 'status': word_list.status, 'item_count': len(items)}


@router.post('/word-lists/{word_list_id}/confirm')
def confirm(word_list_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    try:
        version = confirm_word_list(session, word_list_id)
    except ValueError:
        raise HTTPException(404, detail={'code': 'WORD_LIST_NOT_FOUND', 'message': '单词本不存在'})
    progress = _tts_progress(session, version.id)
    return {'word_list_version_id': version.id, 'version': version.version, 'queued_item_count': progress['queued'], 'tts_progress': progress}


@router.patch('/word-lists/{word_list_id}')
def update_word_list(word_list_id: str, payload: UpdateWordList, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    items = parse_pasted_words(payload.pasted_text)
    if not items:
        raise HTTPException(422, detail={'code': 'NO_WORDS_FOUND', 'message': 'No words found'})
    try:
        version = replace_confirmed_learning_list(session, word_list_id, payload.title, items)
    except ValueError:
        raise HTTPException(404, detail={'code': 'WORD_LIST_NOT_FOUND', 'message': 'Word list not found'})
    return {'word_list_version_id': version.id, 'version': version.version, 'tts_progress': _tts_progress(session, version.id)}


@router.delete('/word-lists/{word_list_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_word_list(word_list_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> None:
    word_list = session.get(WordList, word_list_id)
    if word_list is None:
        raise HTTPException(404, detail={'code': 'WORD_LIST_NOT_FOUND', 'message': 'Word list not found'})
    # Keep referenced versions for dictation history while removing the list from active views.
    word_list.status = 'archived'
    session.commit()


@router.patch('/word-items/{item_id}/pronunciation')
def update_pronunciation(item_id: str, payload: PronunciationSourceInput, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    item = session.get(WordItem, item_id)
    if item is None:
        raise HTTPException(404, detail={'code': 'WORD_ITEM_NOT_FOUND', 'message': 'Word item not found'})
    item.pronunciation_source = payload.pronunciation_source
    item.tts_asset_id = None
    enqueue_once(session, 'generate_tts', item.id)
    session.commit()
    return {'id': item.id, 'pronunciation_source': item.pronunciation_source, 'audio_ready': False}


@router.get('/word-list-versions/{version_id}/tts-progress')
def tts_progress(version_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    if session.get(WordListVersion, version_id) is None:
        raise HTTPException(404, detail={'code': 'WORD_LIST_VERSION_NOT_FOUND', 'message': 'Word list version not found'})
    return _tts_progress(session, version_id)

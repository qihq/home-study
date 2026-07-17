import random
from hashlib import sha256
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, require_resource_owner, require_user
from app.models.child import Child
from app.models.dictation import DictationResult, DictationSession
from app.models.learning_item_audio import LearningItemAudio
from app.models.tts_asset import TtsAsset
from app.models.word_list import WordListVersion
from app.models.word_list import WordItem
from app.models.user import User
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.services.dictation import score_result, start_dictation
from app.services.dictation_stats import create_review_list
from app.services.jobs import enqueue_once
from app.services.speakers import cache_learning_item_audio
from app.workers.voice import generate_text_with_voice
from app.workers.tts import regenerate_configured_item_tts

router = APIRouter(tags=['dictation'])
class StartDictation(BaseModel):
    word_list_version_id: str
    mode: Literal['ordered', 'random'] = 'ordered'
    speaker_profile_id: str | None = None
    voice_version_id: str | None = None
class ScoreDictation(BaseModel): result: Literal['correct','incorrect','unscored']
class ReviewListRequest(BaseModel): normalized_words: list[str]
class DictationPronunciationInput(BaseModel):
    pronunciation_source: Literal['configured', 'custom']
    regenerate: bool = False


def _selected_voice_item_asset_id(
    session: DbSession, user: User, item: WordItem, speaker: SpeakerProfile, voice: VoiceVersion,
) -> str:
    fingerprint = sha256(f'dictation:{user.id}:{voice.id}:{voice.reference_sha256 or ""}'.encode()).hexdigest()
    cached = session.scalar(select(LearningItemAudio).where(
        LearningItemAudio.learning_item_id == item.id,
        LearningItemAudio.config_fingerprint == fingerprint,
    ))
    if cached is not None:
        return cached.tts_asset_id

    cache_key = sha256(
        f'dictation:{user.id}:{voice.id}:{voice.reference_sha256 or ""}:{item.id}'.encode()
    ).hexdigest()
    asset = session.scalar(select(TtsAsset).where(
        TtsAsset.cache_key == cache_key,
        TtsAsset.owner_user_id == user.id,
        TtsAsset.status == 'ready',
    ))
    if asset is None:
        try:
            path = generate_text_with_voice(session, voice.id, item.display_text)
        except ValueError as error:
            raise HTTPException(502, detail={'code': str(error), 'message': 'voice audio generation failed'}) from error
        asset = TtsAsset(
            owner_user_id=user.id,
            cache_key=cache_key,
            provider='mimo_voiceclone',
            model=voice.model,
            voice=voice.id,
            locale=item.source_language,
            speed=1.0,
            normalized_text=item.normalized_text[:160],
            path=str(path),
        )
        session.add(asset)
        session.flush()
    return cache_learning_item_audio(
        session, item.id, fingerprint, asset.id, speaker.id, voice.id,
    ).tts_asset_id


def _item_assets(session: DbSession, version_id: str, user: User, voice_version_id: str | None = None) -> dict[str, str | None]:
    items = session.scalars(select(WordItem).where(WordItem.word_list_version_id == version_id)).all()
    if voice_version_id is None:
        return {item.id: item.tts_asset_id for item in items}
    audio_rows = session.execute(select(LearningItemAudio.learning_item_id, LearningItemAudio.tts_asset_id).join(
        TtsAsset, LearningItemAudio.tts_asset_id == TtsAsset.id,
    ).where(
        LearningItemAudio.voice_version_id == voice_version_id,
        TtsAsset.owner_user_id == user.id,
        TtsAsset.status == 'ready',
    )).all()
    voice_assets = dict(audio_rows)
    return {
        item.id: item.tts_asset_id if item.pronunciation_source == 'configured' else voice_assets.get(item.id)
        for item in items
    }


def _result_payload(item: DictationResult, item_assets: dict[str, str | None], words: dict[str, WordItem]) -> dict:
    word = words[item.word_item_id]
    return {
        'id': item.id, 'sequence': item.sequence, 'result': item.result,
        'revealed': item.answer_revealed_at is not None,
        'item_type': item.item_type_snapshot, 'word_item_id': item.word_item_id,
        'pronunciation_source': word.pronunciation_source,
        'audio_asset_id': item_assets.get(item.word_item_id),
    }

@router.post('/dictation-sessions', status_code=status.HTTP_201_CREATED)
def start(payload: StartDictation, session: DbSession, user: Annotated[User, Depends(require_user)]):
    version = session.get(WordListVersion, payload.word_list_version_id)
    if version is None: raise HTTPException(404, detail={'code':'WORD_LIST_VERSION_NOT_FOUND','message':'单词本版本不存在'})
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None: raise HTTPException(404, detail={'code':'CHILD_NOT_FOUND','message':'孩子档案不存在'})
    speaker_name = None
    voice_name = None
    speaker = None
    voice = None
    if payload.speaker_profile_id or payload.voice_version_id:
        if not payload.speaker_profile_id or not payload.voice_version_id:
            raise HTTPException(422, detail={'code': 'VOICE_SELECTION_INVALID', 'message': 'speaker and voice must be selected together'})
        speaker = session.get(SpeakerProfile, payload.speaker_profile_id)
        if speaker is None:
            raise HTTPException(404, detail={'code': 'SPEAKER_NOT_FOUND', 'message': 'speaker not found'})
        require_resource_owner(session, speaker.owner_user_id, user)
        voice = session.get(VoiceVersion, payload.voice_version_id)
        if voice is None or voice.speaker_profile_id != speaker.id or voice.status != 'ready':
            raise HTTPException(409, detail={'code': 'VOICE_VERSION_NOT_READY', 'message': 'selected voice is unavailable'})
        speaker_name = speaker.display_name
        voice_name = voice.display_name
    record = start_dictation(
        session, child.id, version.id, payload.mode, random.SystemRandom(),
        payload.speaker_profile_id, payload.voice_version_id, speaker_name, voice_name,
    )
    if voice is None or speaker is None or not voice.reference_audio_path:
        item_assets = _item_assets(session, version.id, user)
    else:
        item_assets = {
            item.id: _selected_voice_item_asset_id(session, user, item, speaker, voice)
            for item in session.scalars(select(WordItem).where(WordItem.word_list_version_id == version.id))
        }
    words = {item.id: item for item in session.scalars(select(WordItem).where(WordItem.word_list_version_id == version.id))}
    return {'id':record.id,'ordered_item_ids':record.ordered_item_ids,'speaker_profile_name_snapshot':record.speaker_profile_name_snapshot,'voice_version_name_snapshot':record.voice_version_name_snapshot,'results':[_result_payload(item, item_assets, words) for item in record.results]}

@router.patch('/dictation-sessions/{session_id}/results/{result_id}')
def score(session_id: str, result_id: str, payload: ScoreDictation, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    try: item = score_result(session, session_id, result_id, payload.result)
    except ValueError: raise HTTPException(404, detail={'code':'DICTATION_RESULT_NOT_FOUND','message':'默写结果不存在'})
    return {'id':item.id,'result':item.result}


@router.get('/dictation-sessions/{session_id}')
def get_session(session_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = session.get(DictationSession, session_id)
    if record is None: raise HTTPException(404, detail={'code':'DICTATION_SESSION_NOT_FOUND','message':'默写会话不存在'})
    results = session.scalars(select(DictationResult).where(DictationResult.session_id == record.id).order_by(DictationResult.sequence)).all()
    item_assets = _item_assets(session, record.word_list_version_id, _user, record.voice_version_id)
    words = {item.id: item for item in session.scalars(select(WordItem).where(WordItem.word_list_version_id == record.word_list_version_id))}
    return {'id': record.id, 'status': record.status, 'ordered_item_ids': record.ordered_item_ids, 'speaker_profile_name_snapshot': record.speaker_profile_name_snapshot, 'voice_version_name_snapshot': record.voice_version_name_snapshot, 'results': [_result_payload(item, item_assets, words) for item in results]}


@router.patch('/dictation-sessions/{session_id}/results/{result_id}/pronunciation')
def update_result_pronunciation(
    session_id: str, result_id: str, payload: DictationPronunciationInput,
    session: DbSession, user: Annotated[User, Depends(require_user)],
) -> dict:
    record = session.get(DictationSession, session_id)
    result = session.get(DictationResult, result_id)
    if record is None or result is None or result.session_id != record.id:
        raise HTTPException(404, detail={'code': 'DICTATION_RESULT_NOT_FOUND', 'message': 'Dictation result not found'})
    item = session.get(WordItem, result.word_item_id)
    if item is None:
        raise HTTPException(404, detail={'code': 'WORD_ITEM_NOT_FOUND', 'message': 'Word item not found'})

    item.pronunciation_source = payload.pronunciation_source
    if payload.pronunciation_source == 'configured':
        if payload.regenerate:
            try:
                asset_id = regenerate_configured_item_tts(session, item)
            except ValueError as error:
                raise HTTPException(409, detail={'code': str(error), 'message': 'Native pronunciation is not configured'}) from error
        else:
            asset_id = item.tts_asset_id
        if asset_id is None:
            enqueue_once(session, 'generate_tts', item.id)
        session.commit()
        return {'pronunciation_source': 'configured', 'audio_asset_id': asset_id, 'regenerated': payload.regenerate}

    voice = session.get(VoiceVersion, record.voice_version_id) if record.voice_version_id else None
    speaker = session.get(SpeakerProfile, record.speaker_profile_id) if record.speaker_profile_id else None
    if voice is None or speaker is None or not voice.reference_audio_path:
        raise HTTPException(409, detail={'code': 'CUSTOM_VOICE_NOT_SELECTED', 'message': 'This dictation session has no custom voice'})
    require_resource_owner(session, speaker.owner_user_id, user)
    fingerprint = sha256(f'dictation:{user.id}:{voice.id}:{voice.reference_sha256 or ""}'.encode()).hexdigest()
    cached = session.scalar(select(LearningItemAudio).where(
        LearningItemAudio.learning_item_id == item.id,
        LearningItemAudio.config_fingerprint == fingerprint,
    ))
    if cached is None:
        asset_id = _selected_voice_item_asset_id(session, user, item, speaker, voice)
    else:
        asset_id = cached.tts_asset_id
        if payload.regenerate:
            asset = session.get(TtsAsset, asset_id)
            path = generate_text_with_voice(session, voice.id, item.display_text, force=True)
            if asset is not None:
                asset.path = str(path)
    session.commit()
    return {'pronunciation_source': 'custom', 'audio_asset_id': asset_id, 'regenerated': payload.regenerate}


@router.get('/dictation/latest-in-progress')
def latest_in_progress(session: DbSession, user: Annotated[User, Depends(require_user)]) -> dict | None:
    record = session.scalar(select(DictationSession).where(
        DictationSession.status == 'in_progress',
    ).order_by(DictationSession.started_at.desc()))
    if record is None:
        return None
    items = {item.id: item.display_text for item in session.scalars(select(WordItem).where(
        WordItem.word_list_version_id == record.word_list_version_id,
    ))}
    results = session.scalars(select(DictationResult).where(DictationResult.session_id == record.id).order_by(DictationResult.sequence)).all()
    return {
        'id': record.id, 'word_list_version_id': record.word_list_version_id,
        'words': [items[result.word_item_id] for result in results],
        'next_position': next((index for index, result in enumerate(results) if result.result == 'unscored'), len(results) - 1),
    }


@router.post('/dictation-sessions/{session_id}/results/{result_id}/reveal')
def reveal(session_id: str, result_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    result = session.get(DictationResult, result_id)
    if result is None or result.session_id != session_id: raise HTTPException(404, detail={'code':'DICTATION_RESULT_NOT_FOUND','message':'默写结果不存在'})
    item = session.get(WordItem, result.word_item_id)
    from app.models.child import utc_now
    result.answer_revealed_at = utc_now()
    session.commit()
    # Keep the original field for clients that consume the revealed item payload.
    return {'id': result.id, 'answer': item.display_text, 'display_text': item.display_text}


@router.post('/dictation-sessions/{session_id}/complete')
def complete(session_id: str, session: DbSession, _user: Annotated[User, Depends(require_user)]) -> dict:
    record = session.get(DictationSession, session_id)
    if record is None: raise HTTPException(404, detail={'code':'DICTATION_SESSION_NOT_FOUND','message':'默写会话不存在'})
    unscored = session.query(DictationResult).filter_by(session_id=record.id, result='unscored').count()
    if unscored: raise HTTPException(409, detail={'code':'DICTATION_HAS_UNSCORED_RESULTS','message':'还有未评分单词'})
    from app.models.child import utc_now
    record.status = 'completed'; record.completed_at = utc_now(); session.commit()
    return {'id': record.id, 'status': record.status}


@router.post('/review-lists/from-mistakes', status_code=status.HTTP_201_CREATED)
def review_list(payload: ReviewListRequest, session: DbSession, _user: Annotated[User, Depends(require_user)]):
    child = session.scalar(select(Child).where(Child.active.is_(True)).limit(1))
    if child is None: raise HTTPException(404, detail={'code':'CHILD_NOT_FOUND','message':'孩子档案不存在'})
    try: created = create_review_list(session, child.id, payload.normalized_words)
    except ValueError: raise HTTPException(422, detail={'code':'NO_MISTAKES_SELECTED','message':'没有可复习的错词'})
    return {'id': created.id, 'title': created.title, 'status': created.status}

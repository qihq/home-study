from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dictation import DictationSession
from app.models.speaker import SpeakerProfile, VoiceVersion
from app.models.learning_item_audio import LearningItemAudio


def create_speaker(
    session: Session, display_name: str, note: str | None = None, avatar_color: str = 'blue', owner_user_id: str | None = None,
) -> SpeakerProfile:
    speaker = SpeakerProfile(display_name=display_name, note=note, avatar_color=avatar_color, owner_user_id=owner_user_id)
    session.add(speaker)
    session.commit()
    session.refresh(speaker)
    return speaker


def get_speaker(session: Session, speaker_id: str) -> SpeakerProfile:
    speaker = session.get(SpeakerProfile, speaker_id)
    if speaker is None:
        raise ValueError('SPEAKER_NOT_FOUND')
    return speaker


def create_voice_version(session: Session, speaker_id: str, display_name: str, **values) -> VoiceVersion:
    get_speaker(session, speaker_id)
    voice = VoiceVersion(speaker_profile_id=speaker_id, display_name=display_name, **values)
    session.add(voice)
    session.commit()
    session.refresh(voice)
    return voice


def make_default(session: Session, speaker_id: str, voice_id: str) -> SpeakerProfile:
    speaker = get_speaker(session, speaker_id)
    voice = session.get(VoiceVersion, voice_id)
    if voice is None or voice.speaker_profile_id != speaker.id or voice.status != 'ready':
        raise ValueError('VOICE_VERSION_NOT_READY')
    speaker.default_voice_version_id = voice.id
    session.commit()
    session.refresh(speaker)
    return speaker


def delete_voice_version(session: Session, voice_id: str) -> VoiceVersion:
    voice = session.get(VoiceVersion, voice_id)
    if voice is None:
        raise ValueError('VOICE_VERSION_NOT_FOUND')
    referenced = session.scalar(select(DictationSession.id).where(DictationSession.voice_version_id == voice.id).limit(1))
    if referenced is not None:
        voice.status = 'disabled'
        session.commit()
        session.refresh(voice)
        return voice
    session.delete(voice)
    session.commit()
    return voice


def audio_config_fingerprint(
    protocol: str, model: str, endpoint: str, voice: str, speed: float, reference_audio_sha256: str,
) -> str:
    value = '\n'.join((protocol, model, endpoint.rstrip('/'), voice, str(speed), reference_audio_sha256))
    return sha256(value.encode()).hexdigest()


def cache_learning_item_audio(
    session: Session, learning_item_id: str, config_fingerprint: str, tts_asset_id: str,
    speaker_profile_id: str | None = None, voice_version_id: str | None = None,
) -> LearningItemAudio:
    existing = session.scalar(select(LearningItemAudio).where(
        LearningItemAudio.learning_item_id == learning_item_id,
        LearningItemAudio.config_fingerprint == config_fingerprint,
    ))
    if existing is not None:
        return existing
    cached = LearningItemAudio(
        learning_item_id=learning_item_id,
        speaker_profile_id=speaker_profile_id,
        voice_version_id=voice_version_id,
        tts_asset_id=tts_asset_id,
        config_fingerprint=config_fingerprint,
    )
    session.add(cached)
    session.commit()
    session.refresh(cached)
    return cached
